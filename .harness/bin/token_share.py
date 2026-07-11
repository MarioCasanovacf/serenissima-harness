#!/usr/bin/env python3
"""token_share.py - measure frontier-tier token share against the P-030 budget band.

Reads every Claude Code transcript (coordinator sessions + subagent transcripts)
for this project from ~/.claude/projects/<slug>/, deduplicates assistant messages
by message.id, and reports the frontier-tier share of raw tokens (input + output +
cache creation + cache read) against the cost_policy.frontier_budget band in
.harness/state.json (P-030 as amended: [0.53, 0.65]).

Tier classification is substring-based on the model id: fable/opus = frontier,
sonnet/haiku = cheap. Unknown models are reported separately and excluded from
the share denominator only if --strict is given.

Usage:
  python3 .harness/bin/token_share.py                 # full history, human-readable
  python3 .harness/bin/token_share.py --since 2026-07-04 --until 2026-07-07
  python3 .harness/bin/token_share.py --json          # machine-readable
  python3 .harness/bin/token_share.py --project-dir /path/to/transcripts

Exit codes:
  0  frontier share inside or below the band
  1  error / no assistant messages found
  2  frontier share ABOVE the band (budget breach -> mandatory finding at next
     section-5A audit, per state.json cost_policy rule 1)
"""
import argparse
import json
import re
import sys
from pathlib import Path

FRONTIER_MARKERS = ("fable", "opus")
CHEAP_MARKERS = ("sonnet", "haiku")
DEFAULT_BAND = (0.53, 0.65)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_PATH = REPO_ROOT / ".harness" / "state.json"


def project_transcript_dir():
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(REPO_ROOT))
    return Path.home() / ".claude" / "projects" / slug


def load_band():
    try:
        state = json.loads(STATE_PATH.read_text())
        lo, hi = state["cost_policy"]["frontier_budget"][
            "target_band_frontier_share_raw_tokens"
        ]
        return float(lo), float(hi)
    except Exception:
        return DEFAULT_BAND


def tier_of(model):
    m = model.lower()
    if any(k in m for k in FRONTIER_MARKERS):
        return "frontier"
    if any(k in m for k in CHEAP_MARKERS):
        return "cheap"
    return "other"


def raw_tokens(usage):
    return sum(
        usage.get(k) or 0
        for k in (
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        )
    )


def collect(project_dir, since, until):
    """Return {message_id: (model, usage, output_tokens)} deduped, keeping the
    occurrence with the largest output_tokens (streamed lines repeat an id with
    growing usage)."""
    messages = {}
    for path in sorted(project_dir.rglob("*.jsonl")):
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "assistant":
                continue
            ts = (entry.get("timestamp") or "")[:10]
            if since and ts and ts < since:
                continue
            if until and ts and ts >= until:
                continue
            msg = entry.get("message") or {}
            mid, model, usage = msg.get("id"), msg.get("model"), msg.get("usage")
            if not (mid and model and usage) or model.startswith("<"):
                continue
            out = usage.get("output_tokens") or 0
            if mid not in messages or out > messages[mid][2]:
                messages[mid] = (model, usage, out)
    return messages


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", help="ISO date lower bound (inclusive), e.g. 2026-07-04")
    ap.add_argument("--until", help="ISO date upper bound (exclusive)")
    ap.add_argument("--project-dir", type=Path, help="override transcript directory")
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exclude unknown-tier models from the share denominator",
    )
    args = ap.parse_args()

    project_dir = args.project_dir or project_transcript_dir()
    if not project_dir.is_dir():
        print(f"error: transcript directory not found: {project_dir}", file=sys.stderr)
        return 1

    messages = collect(project_dir, args.since, args.until)
    if not messages:
        print("error: no assistant messages found in window", file=sys.stderr)
        return 1

    per_model = {}
    for model, usage, out in messages.values():
        row = per_model.setdefault(
            model, {"messages": 0, "raw": 0, "output": 0, "tier": tier_of(model)}
        )
        row["messages"] += 1
        row["raw"] += raw_tokens(usage)
        row["output"] += out

    def tier_sum(tier, key):
        return sum(r[key] for r in per_model.values() if r["tier"] == tier)

    denom_tiers = ("frontier", "cheap") if args.strict else ("frontier", "cheap", "other")
    total_raw = sum(tier_sum(t, "raw") for t in denom_tiers)
    total_out = sum(tier_sum(t, "output") for t in denom_tiers)
    if total_raw == 0:
        print("error: zero raw tokens in window", file=sys.stderr)
        return 1

    share_raw = tier_sum("frontier", "raw") / total_raw
    share_out = tier_sum("frontier", "output") / total_out if total_out else 0.0
    lo, hi = load_band()
    status = "above-band" if share_raw > hi else ("below-band" if share_raw < lo else "in-band")

    report = {
        "project_dir": str(project_dir),
        "window": {"since": args.since, "until": args.until},
        "messages_deduped": len(messages),
        "band_frontier_share_raw_tokens": [lo, hi],
        "frontier_share_raw_tokens": round(share_raw, 4),
        "frontier_share_output_tokens": round(share_out, 4),
        "status": status,
        "per_model": {
            m: {**r} for m, r in sorted(per_model.items(), key=lambda kv: -kv[1]["raw"])
        },
    }
    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        print(f"transcripts: {project_dir}")
        print(f"window: {args.since or 'begin'} .. {args.until or 'now'}  "
              f"({len(messages)} assistant messages, deduped by message.id)")
        print(f"{'model':<28} {'tier':<9} {'messages':>9} {'raw tokens':>14} {'output':>10}")
        for m, r in sorted(per_model.items(), key=lambda kv: -kv[1]["raw"]):
            print(f"{m:<28} {r['tier']:<9} {r['messages']:>9} {r['raw']:>14,} {r['output']:>10,}")
        print(f"\nfrontier share (raw tokens):    {share_raw:.1%}   band [{lo:.0%}, {hi:.0%}]  -> {status}")
        print(f"frontier share (output tokens): {share_out:.1%}")
        if status == "above-band":
            print("BREACH: mandatory finding at next section-5A audit (cost_policy rule 1, P-030)")
    return 2 if status == "above-band" else 0


if __name__ == "__main__":
    sys.exit(main())
