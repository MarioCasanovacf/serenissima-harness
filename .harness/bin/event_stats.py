#!/usr/bin/env python3
"""event_stats.py - read-only event-log reader with a DECLARED denominator and a
DECLARED provenance filter.

WHY THIS EXISTS. The raw event log over-counts. At the 2026-08-15 cut it held
13,193 events of which 10,496 fell on a single pre-isolation day; `precedent_published`
appeared 5,186 times but resolved to 61 distinct record ids against 59 live records,
with `PR-001` alone carrying 3,090 publish events issued by task ids outside this
workspace's range. Any catch-rate, incident count or reopen rate computed over the raw
log is dominated by that burst. Registered as defect TELEMETRY-PROVENANCE-A.

THE TWO RULES THIS TOOL EXISTS TO ENFORCE (M-1 and M-2 of the metric epic):

  M-1 DECLARED DENOMINATOR. No figure is printed without the unit it is computed in.
      Every count in this tool is reported TWICE, as `raw` and as `distinct`, and
      neither is ever printed alone. A reader who wants one number must choose which,
      and the choice is visible in the output rather than buried in the code.

  M-2 DECLARED PROVENANCE. No figure is printed without the filter that produced it.
      The dedup rule, the source path, the line count and the number of unparseable
      lines are printed with every run, including `--json`. Nothing is excluded
      silently and nothing is deleted: the burst is still in the file, and the file is
      still the record. It is excluded from a DENOMINATOR, which is a different act
      from erasure.

THE DEDUP PREDICATE (operator decision D-9, ruling round 2.5, 2026-08-15). Two events
are the SAME event when they agree on every field except the timestamp. Chosen over a
date cut - 2026-08-11 carries both the 10,496-event burst and 240 legitimate task
events, so no date separates them - and over a task-id range filter, which is fragile
because it depends on a manually maintained list of valid ranges. The dedup criterion
is mechanical and requires nobody to judge which run was a test.

WHAT THIS TOOL DELIBERATELY DOES NOT DO. It does not decide which of `raw` or
`distinct` is correct for a given question, because that answer differs by question:
`distinct` is right for "how many records were published", `raw` is right for "how much
churn did the fleet generate". It does not compute a catch-rate, because a catch-rate
needs a falsifier attached (M-3) and no falsifier has been ratified yet. Printing a
figure the operator cannot falsify is the defect this epic exists to remove, and this
tool will not commit it on the way to fixing it.

READ-ONLY, ABSOLUTELY. Same verb class as `token_share.py` and `usage_report.py`:
no writes, no `hc.log_event`, no lock acquisition, no cache, no temp file.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

DEFAULT_LOG = pathlib.Path(__file__).resolve().parents[1] / "logs" / "events.jsonl"

# M-2: the predicate, stated as data so a verifier can read it without reading code.
DEDUP_RULE = "two events are identical when they agree on every field except 'ts'"
DEDUP_IGNORES = ("ts",)


def identity(event: dict) -> tuple:
    """The identity tuple of an event under D-9: every field except the timestamp."""
    return tuple(sorted(
        (k, json.dumps(v, sort_keys=True))
        for k, v in event.items() if k not in DEDUP_IGNORES
    ))


def load(path: pathlib.Path) -> tuple[list[dict], int]:
    """Return (events, unparseable_line_count). Unparseable lines are counted, never
    silently dropped: a log that is 5 percent garbage is a different log from a clean
    one, and the reader is entitled to know which one produced the figures."""
    rows, bad = [], 0
    if not path.exists():
        return rows, bad
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                bad += 1
                continue
            if isinstance(obj, dict):
                rows.append(obj)
            else:
                bad += 1
    return rows, bad


def summarize(rows: list[dict]) -> dict:
    raw = collections.Counter()
    seen: dict[str, set] = collections.defaultdict(set)
    for e in rows:
        name = str(e.get("event", "<unnamed>"))
        raw[name] += 1
        seen[name].add(identity(e))

    per_event = {}
    for name, n in raw.items():
        d = len(seen[name])
        per_event[name] = {
            "raw": n,
            "distinct": d,
            "replay_factor": round(n / d, 2) if d else None,
        }

    days_raw = collections.Counter(str(e.get("ts", ""))[:10] for e in rows)
    days_distinct = collections.Counter()
    global_seen = set()
    for e in rows:
        key = identity(e)
        if key not in global_seen:
            global_seen.add(key)
            days_distinct[str(e.get("ts", ""))[:10]] += 1

    return {
        "per_event": dict(sorted(per_event.items(), key=lambda kv: -kv[1]["raw"])),
        "totals": {
            "raw": sum(raw.values()),
            "distinct": len(global_seen),
            "replay_factor": (round(sum(raw.values()) / len(global_seen), 2)
                              if global_seen else None),
        },
        "by_day": {
            d: {"raw": days_raw[d], "distinct": days_distinct.get(d, 0)}
            for d in sorted(days_raw, reverse=True)
        },
    }


def provenance(path: pathlib.Path, rows: list[dict], bad: int) -> dict:
    """M-2: everything a reader needs to reproduce or distrust these figures."""
    return {
        "source": str(path),
        "source_exists": path.exists(),
        "lines_parsed": len(rows),
        "lines_unparseable": bad,
        "dedup_rule": DEDUP_RULE,
        "dedup_ignores": list(DEDUP_IGNORES),
        "authority": "operator decision D-9, ruling round 2.5, 2026-08-15",
        "defect_addressed": "TELEMETRY-PROVENANCE-A",
        "excluded_from_denominator": "nothing is deleted; replays collapse into their "
                                     "identity tuple and the difference is reported as "
                                     "replay_factor",
    }


def render(prov: dict, summ: dict, top: int) -> None:
    print("PROVENANCE (M-2)")
    print(f"  source              {prov['source']}")
    print(f"  lines parsed        {prov['lines_parsed']}")
    print(f"  lines unparseable   {prov['lines_unparseable']}")
    print(f"  dedup rule          {prov['dedup_rule']}")
    print(f"  authority           {prov['authority']}")
    print(f"  addresses           {prov['defect_addressed']}")
    print()

    t = summ["totals"]
    print("TOTALS (M-1: both denominators, never one alone)")
    print(f"  raw events          {t['raw']}")
    print(f"  distinct events     {t['distinct']}")
    print(f"  replay factor       {t['replay_factor']}x")
    print()

    print(f"BY EVENT TYPE  (top {top} by raw count)")
    print(f"  {'event':34s} {'raw':>8s} {'distinct':>9s} {'replay':>8s}")
    for name, v in list(summ["per_event"].items())[:top]:
        rf = "-" if v["replay_factor"] is None else f"{v['replay_factor']}x"
        print(f"  {name:34s} {v['raw']:8d} {v['distinct']:9d} {rf:>8s}")
    print()

    print(f"BY DAY  (top {top} by raw count)")
    worst = sorted(summ["by_day"].items(), key=lambda kv: -kv[1]["raw"])[:top]
    print(f"  {'day':12s} {'raw':>8s} {'distinct':>9s} {'share of raw':>13s}")
    for day, v in worst:
        share = v["raw"] / t["raw"] * 100 if t["raw"] else 0
        print(f"  {day:12s} {v['raw']:8d} {v['distinct']:9d} {share:12.1f}%")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="event_stats.py - event-log counts with a declared denominator "
                    "(M-1) and a declared provenance filter (M-2).")
    ap.add_argument("--log", type=pathlib.Path, default=DEFAULT_LOG,
                    help="path to events.jsonl (default: .harness/logs/events.jsonl)")
    ap.add_argument("--top", type=int, default=12,
                    help="rows to show per table (default 12)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    rows, bad = load(args.log)
    prov = provenance(args.log, rows, bad)

    if not rows:
        payload = {"provenance": prov, "totals": {"raw": 0, "distinct": 0},
                   "per_event": {}, "by_day": {}}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"no parseable events at {args.log}")
        return 0

    summ = summarize(rows)
    if args.json:
        print(json.dumps({"provenance": prov, **summ}, indent=2))
    else:
        render(prov, summ, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
