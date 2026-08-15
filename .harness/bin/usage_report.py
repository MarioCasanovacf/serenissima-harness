#!/usr/bin/env python3
"""usage_report.py - cosecha telemetria de consumo por corrida, rol y modelo.

The harness itself writes no token counters: `events.jsonl` records claims,
locks and handoffs, never usage. The runner, however, writes a full `usage`
block on every assistant message of every session and subagent transcript under
~/.claude/projects/<slug>/. This tool harvests that and reduces it to the
per-run, per-role, per-model numbers the harness needs for cost policy.

It is the harvest half of the missing instrumentation flagged in
.harness/logs/audit_telemetry_2026-08-14.html. Companion to token_share.py,
which answers only the frontier-share question against the P-030 band.

Definitions (all derived, none of them emitted by the harness itself):
  unit  - one subagent transcript = one dispatched agent
  run   - a cluster of units separated from the next by more than --gap minutes.
          A heuristic: the harness emits no run_id. See --gap.
  role  - parsed from the first user message of a subagent transcript
          ("You are worker-v1-7 ..."). Units with no harness role fall in
          'workflow' (orchestrator fan-out) or 'other'.
  raw   - input + cache_creation + cache_read + output. Cache reads dominate by
          ~95%, so raw is NOT a proxy for billable cost; read the cache split.

Usage:
  python3 .harness/bin/usage_report.py                    # human-readable
  python3 .harness/bin/usage_report.py --runs 5           # last 5 runs only
  python3 .harness/bin/usage_report.py --json             # machine-readable
  python3 .harness/bin/usage_report.py --gap 30           # tighter clustering
  python3 .harness/bin/usage_report.py --project-dir PATH

Known blind spots (documented, not fixable from local disk):
  - Tokens of API attempts that failed before producing a response: no `usage`
    block is ever written, so they are invisible here and in token_share.py.
  - Context compaction and auto-titling are LLM calls the runner makes on its
    own; they carry no assistant message, so they are absent from every total.
    `--json` reports the compaction events it can see under `compaction`.

Exit codes:
  0  report produced
  1  no transcripts found
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTIER_MARKERS = ("fable", "opus")
CHEAP_MARKERS = ("sonnet", "haiku")

# role tag -> canonical role, matched against the "You are <tag>" of the prompt
ROLE_PATTERNS = [
    (re.compile(r"verifier|verificador"), "verifier"),
    (re.compile(r"worker"), "worker"),
    (re.compile(r"thinker|planner"), "thinker"),
    (re.compile(r"scout"), "scout"),
    (re.compile(r"librarian"), "librarian"),
    (re.compile(r"evolution"), "evolution"),
    (re.compile(r"judge|juez"), "judge"),
]


def project_transcript_dir():
    """Same slug rule token_share.py uses, so both tools read one source."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(REPO_ROOT))
    return Path.home() / ".claude" / "projects" / slug


def parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def tier_of(model):
    lowered = (model or "").lower()
    if any(k in lowered for k in FRONTIER_MARKERS):
        return "frontier"
    if any(k in lowered for k in CHEAP_MARKERS):
        return "cheap"
    return "unknown"


def role_of(prompt, is_workflow):
    head = prompt[:1500].lower()
    tag = re.search(r"you are ([a-z0-9\-]+)", head)
    tag = tag.group(1) if tag else ""
    for pattern, name in ROLE_PATTERNS:
        if pattern.search(tag) or pattern.search(head[:400]):
            return name
    return "workflow" if is_workflow else "other"


def read_transcript(path):
    """Assistant messages deduplicated by message.id, plus the opening prompt."""
    messages, seen, first_user = [], set(), ""
    for line in path.open(errors="replace"):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") == "user" and not first_user:
            content = entry.get("message", {}).get("content")
            first_user = content if isinstance(content, str) else json.dumps(content)
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message", {})
        mid = message.get("id")
        if mid in seen:
            continue
        seen.add(mid)
        usage = message.get("usage") or {}
        messages.append({
            "ts": parse_ts(entry.get("timestamp")),
            "model": message.get("model", "unknown"),
            "in": usage.get("input_tokens") or 0,
            "out": usage.get("output_tokens") or 0,
            "cache_write": usage.get("cache_creation_input_tokens") or 0,
            "cache_read": usage.get("cache_read_input_tokens") or 0,
        })
    return messages, first_user


def collect_units(directory):
    units = []
    for path in sorted(directory.rglob("agent-*.jsonl")):
        if "subagents" not in str(path):
            continue
        messages, prompt = read_transcript(path)
        if not messages:
            continue
        stamps = [m["ts"] for m in messages if m["ts"]]
        if not stamps:
            continue
        workflow = re.search(r"workflows/(wf_[^/]+)/", str(path))
        ctx = [m["in"] + m["cache_write"] + m["cache_read"] for m in messages]
        units.append({
            "path": str(path.relative_to(directory)),
            "workflow": workflow.group(1) if workflow else None,
            "role": role_of(prompt, bool(workflow)),
            "tasks": sorted(set(re.findall(r"\bT-\d{3}\b", prompt))),
            "start": min(stamps),
            "end": max(stamps),
            "turns": len(messages),
            "in": sum(m["in"] for m in messages),
            "out": sum(m["out"] for m in messages),
            "cache_write": sum(m["cache_write"] for m in messages),
            "cache_read": sum(m["cache_read"] for m in messages),
            "models": sorted({m["model"] for m in messages}),
            "context_first": ctx[0],
            "context_peak": max(ctx),
        })
    return sorted(units, key=lambda u: u["start"])


def collect_coordinator(directory):
    messages = []
    for path in sorted(directory.glob("*.jsonl")):
        found, _ = read_transcript(path)
        for m in found:
            m["session"] = path.stem
        messages.extend(found)
    return sorted(messages, key=lambda m: m["ts"] or datetime.min.replace(tzinfo=timezone.utc))


def collect_compaction(directory):
    """Runner-side context management: real LLM calls with no usage block."""
    events, titles = [], 0
    for path in directory.rglob("*.jsonl"):
        if path.name == "journal.jsonl":
            continue
        for line in path.open(errors="replace"):
            if '"ai-title"' in line:
                titles += 1
            if "compact_boundary" not in line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            meta = entry.get("compactMetadata") or {}
            if meta.get("preTokens"):
                events.append({
                    "ts": entry.get("timestamp"),
                    "trigger": meta.get("trigger"),
                    "pre_tokens": meta.get("preTokens"),
                    "post_tokens": meta.get("postTokens"),
                    "dropped_tokens": meta.get("cumulativeDroppedTokens"),
                    "duration_ms": meta.get("durationMs"),
                })
    return {"events": events, "auto_titles": titles,
            "note": "unmetered: these calls carry no usage block"}


def cluster_runs(units, gap_minutes):
    if not units:
        return []
    gap = timedelta(minutes=gap_minutes)
    runs, current = [], [units[0]]
    for unit in units[1:]:
        if unit["start"] - max(u["end"] for u in current) > gap:
            runs.append(current)
            current = [unit]
        else:
            current.append(unit)
    runs.append(current)
    return runs


def concurrency(units):
    """Time-weighted concurrency over the busy window, and the serial share."""
    edges = sorted([(u["start"], 1) for u in units] + [(u["end"], -1) for u in units])
    live = peak = 0
    area = busy = solo = timedelta(0)
    previous = edges[0][0]
    for stamp, delta in edges:
        span = stamp - previous
        area += span * live
        if live >= 1:
            busy += span
        if live == 1:
            solo += span
        live += delta
        peak = max(peak, live)
        previous = stamp
    seconds = busy.total_seconds()
    return {
        "peak": peak,
        "mean": round(area.total_seconds() / seconds, 2) if seconds else 0.0,
        "serial_pct": round(100 * solo.total_seconds() / seconds, 1) if seconds else 0.0,
        "busy_minutes": round(seconds / 60, 1),
    }


def summarize_run(index, units, coordinator):
    start = min(u["start"] for u in units)
    end = max(u["end"] for u in units)
    window = [m for m in coordinator
              if m["ts"] and start - timedelta(minutes=20) <= m["ts"] <= end + timedelta(minutes=20)]
    roles = defaultdict(lambda: defaultdict(int))
    models = defaultdict(lambda: defaultdict(int))
    for unit in units:
        bucket = roles[unit["role"]]
        bucket["agents"] += 1
        for key in ("in", "out", "cache_write", "cache_read"):
            bucket[key] += unit[key]
        # a unit's tokens are split evenly across the models that served it
        for model in unit["models"]:
            models[model]["agents"] += 1
            for key in ("in", "out", "cache_write", "cache_read"):
                models[model][key] += unit[key] // len(unit["models"])
    totals = {key: sum(u[key] for u in units) for key in ("in", "out", "cache_write", "cache_read")}
    coord = {key: sum(m[key] for m in window) for key in ("in", "out", "cache_write", "cache_read")}
    return {
        "run": index,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "agents": len(units),
        "tasks": sorted({t for u in units for t in u["tasks"]}),
        "wall_minutes": round((end - start).total_seconds() / 60, 1),
        "subagents": dict(totals, raw=sum(totals.values())),
        "coordinator": dict(coord, raw=sum(coord.values()), turns=len(window)),
        "roles": {r: dict(v, raw=sum(v[k] for k in ("in", "out", "cache_write", "cache_read")))
                  for r, v in roles.items()},
        "models": {m: dict(v, tier=tier_of(m),
                           raw=sum(v[k] for k in ("in", "out", "cache_write", "cache_read")))
                   for m, v in models.items()},
        "concurrency": concurrency(units),
        "context_peak": max(u["context_peak"] for u in units),
    }


def percentile(values, fraction):
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(int(fraction * len(ordered)), len(ordered) - 1)]


def build_report(directory, gap_minutes, limit):
    units = collect_units(directory)
    if not units:
        return None
    coordinator = collect_coordinator(directory)
    runs = cluster_runs(units, gap_minutes)
    if limit:
        runs = runs[-limit:]
    summaries = [summarize_run(i, r, coordinator) for i, r in enumerate(runs, 1)]
    scoped = [u for r in runs for u in r]
    costs = [u["in"] + u["out"] + u["cache_write"] + u["cache_read"] for u in scoped]
    total_in = sum(u["in"] + u["cache_write"] + u["cache_read"] for u in scoped)
    top_decile = sorted(costs)[-max(1, len(costs) // 10):]
    return {
        "transcripts": str(directory),
        "generated_from": "runner transcripts; the harness emits no usage counters",
        "gap_minutes": gap_minutes,
        "runs": summaries,
        "cache": {
            "input_total": total_in,
            "read_pct": round(100 * sum(u["cache_read"] for u in scoped) / total_in, 2) if total_in else 0,
            "write_pct": round(100 * sum(u["cache_write"] for u in scoped) / total_in, 2) if total_in else 0,
            "uncached_pct": round(100 * sum(u["in"] for u in scoped) / total_in, 4) if total_in else 0,
        },
        "context_payload": {
            "median": percentile([u["context_peak"] for u in scoped], 0.5),
            "p90": percentile([u["context_peak"] for u in scoped], 0.9),
            "max": max(u["context_peak"] for u in scoped),
            "first_turn_median": percentile([u["context_first"] for u in scoped], 0.5),
        },
        "cost_tail": {
            "p50": percentile(costs, 0.5),
            "p90": percentile(costs, 0.9),
            "p95": percentile(costs, 0.95),
            "top_decile_share_pct": round(100 * sum(top_decile) / sum(costs), 1) if costs else 0,
        },
        "compaction": collect_compaction(directory),
    }


def print_human(report):
    print("transcripts: {}".format(report["transcripts"]))
    print("runs clustered at a {}-minute gap (the harness emits no run_id)\n"
          .format(report["gap_minutes"]))
    header = "{:>3} {:16} {:>5} {:>6} {:>14} {:>12} {:>7} {:>6} {:>7}"
    print(header.format("run", "start", "agts", "tasks", "raw tokens", "output",
                        "wall", "conc", "serial"))
    for run in report["runs"]:
        total = run["subagents"]["raw"] + run["coordinator"]["raw"]
        out = run["subagents"]["out"] + run["coordinator"]["out"]
        print(header.format(
            run["run"], run["start"][5:16].replace("T", " "), run["agents"],
            len(run["tasks"]), "{:,}".format(total), "{:,}".format(out),
            "{:.0f}m".format(run["wall_minutes"]),
            "{:.2f}x".format(run["concurrency"]["mean"]),
            "{:.0f}%".format(run["concurrency"]["serial_pct"])))

    roles = defaultdict(lambda: defaultdict(int))
    models = defaultdict(lambda: defaultdict(int))
    for run in report["runs"]:
        for role, v in run["roles"].items():
            roles[role]["agents"] += v["agents"]
            roles[role]["raw"] += v["raw"]
            roles[role]["out"] += v["out"]
        for model, v in run["models"].items():
            models[model]["agents"] += v["agents"]
            models[model]["raw"] += v["raw"]

    role_total = sum(v["raw"] for v in roles.values()) or 1
    print("\nby role")
    for role, v in sorted(roles.items(), key=lambda kv: -kv[1]["raw"]):
        print("  {:12} agents={:>4} raw={:>15,} ({:>5.1f}%) output={:>9,}"
              .format(role, v["agents"], v["raw"], 100 * v["raw"] / role_total, v["out"]))

    model_total = sum(v["raw"] for v in models.values()) or 1
    print("\nby model")
    for model, v in sorted(models.items(), key=lambda kv: -kv[1]["raw"]):
        print("  {:22} {:9} agents={:>4} raw={:>15,} ({:>5.1f}%)"
              .format(model, tier_of(model), v["agents"], v["raw"],
                      100 * v["raw"] / model_total))

    cache = report["cache"]
    print("\ncache split of input: read {:.2f}% / write {:.2f}% / uncached {:.3f}%"
          .format(cache["read_pct"], cache["write_pct"], cache["uncached_pct"]))
    print("  raw token counts are ~95% cache re-reads; do not read them as billable cost")

    ctx = report["context_payload"]
    print("\ncontext payload per agent: median {:,} | p90 {:,} | max {:,} | first turn {:,}"
          .format(ctx["median"], ctx["p90"], ctx["max"], ctx["first_turn_median"]))

    tail = report["cost_tail"]
    print("cost per agent: p50 {:,} | p90 {:,} | p95 {:,} | top decile holds {:.1f}%"
          .format(tail["p50"], tail["p90"], tail["p95"], tail["top_decile_share_pct"]))

    comp = report["compaction"]
    print("\nunmetered runner calls (no usage block, absent from every total above)")
    print("  auto-titling calls: {}".format(comp["auto_titles"]))
    for event in comp["events"]:
        print("  compaction {}: {:,} -> {:,} tokens in {:.0f}s ({} trigger)".format(
            (event["ts"] or "")[:19], event["pre_tokens"] or 0, event["post_tokens"] or 0,
            (event["duration_ms"] or 0) / 1000, event["trigger"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--project-dir", help="transcript directory override")
    parser.add_argument("--gap", type=int, default=45,
                        help="minutes of silence that separate two runs (default 45)")
    parser.add_argument("--runs", type=int, default=0,
                        help="report only the last N runs (default: all)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    directory = Path(args.project_dir) if args.project_dir else project_transcript_dir()
    if not directory.is_dir():
        sys.stderr.write("no transcripts at {}\n".format(directory))
        return 1

    report = build_report(directory, args.gap, args.runs)
    if report is None:
        sys.stderr.write("no subagent transcripts under {}\n".format(directory))
        return 1

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
