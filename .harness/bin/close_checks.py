#!/usr/bin/env python3
"""close_checks.py - the epic-close report: three read-only checks, one printout.

Ratified 2026-10-21, operator decision 1, option 6b (.harness/operator-rulings-2026-10-21.md):
  (b) Routine checks at every epic close: `attest.py forks`, `warrant.py reconcile`, and
  IMP-6 -- an act with no matching `act_signed` event is anomalous
  (.harness/coordinator-decisions-ruling-round-2.md, D-22). IMP-6 was not built yet; this
  is that build, plus the one command that runs all three and prints one report.

WHY attest.py AND warrant.py ARE CALLED THROUGH THEIR CLI, NOT IMPORTED. Both modules are
under concurrent edit elsewhere in this epic (T-448 and siblings). Importing their
internals here would couple this tool, and its test suite, to whichever half-finished
state they are in at import time. Calling the shipped CLI binds this tool to the public
contract instead, and costs nothing: both commands already print a single JSON blob.

THE IMP-6 CHECK, DEDUPED PER TELEMETRY-PROVENANCE-A. event_stats.py's dedup predicate
(operator decision D-9: two events are identical when they agree on every field except
`ts`) is IMPORTED from event_stats.py, never reimplemented, so this tool cannot drift
from the ratified predicate by having its own slightly-different copy. The count of
act_signed events is reported TWICE -- raw and distinct -- never one alone (M-1), exactly
as event_stats.py reports every other event type. Each act on disk (root/acts/<name>/
<seq>.json, attest.sign_act's own layout) is then matched by (name, seq) against the
DISTINCT set of act_signed identities. An act with no match is listed as anomalous. IMP-6's
own text: "Neither [writing the file directly, or using the tool under a traceable id] is
proof -- the id is self-asserted -- but the forger must pick one of two traceable
behaviours, and the cross-check costs nothing to run." This module IS that cross-check; it
decides nothing about what an anomaly means.

IMP-7, SAID ONCE AND ENFORCED HERE. PR-022 clause 4 is unamended: no weighting, no
gating, no privileges. None of the three checks below changes this tool's exit code --
not a fork, not an orphaned roll row, not an anomalous act. `test_close_checks.py` builds
a scenario with all three present and asserts the command still exits 0, and asserts the
returned/printed payload carries no verdict field (no `ok`, no `passed`, no `clean`
computed BY THIS TOOL -- `clean` inside the embedded `reconcile` payload is `warrant.py`'s
own field, reported verbatim and not read by this tool as a gate).

READ-ONLY, ABSOLUTELY. Same verb class as event_stats.py and currency.py: no writes, no
hc.log_event, no lock acquisition, no file this tool did not open for reading.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness_common as hc  # noqa: E402 -- stable, read-only use (HARNESS, EVENTS)
import event_stats  # noqa: E402 -- only for the ratified D-9 dedup predicate

import subprocess  # noqa: E402

DEFAULT_ROOT = hc.HARNESS


def resolve_root(flag=None) -> pathlib.Path:
    """Same shape as warrant.resolve_root / attest's --root handling, duplicated here
    (not imported) because both source modules are under concurrent edit right now."""
    if flag:
        return pathlib.Path(flag).expanduser().resolve()
    return DEFAULT_ROOT


# --------------------------------------------------------------- sibling CLI calls

def _run_cli(tool: str, args: list, root: pathlib.Path) -> dict:
    """Run a sibling CLI tool as a subprocess and capture its report, verbatim.

    Never raises and never inspects the exit code for a verdict: `warrant.py reconcile`
    exits 3 when it finds orphans and `attest.py verify` can exit 2 on a refusal -- both
    are THAT tool's own decision about ITS exit code, not a signal this tool gates on
    (IMP-7). The exit code is recorded in the report so a reader can see it; it is never
    branched on here.
    """
    cmd = [sys.executable, str(HERE / tool), "--root", str(root), *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        exit_code, out, err = r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as exc:  # a detector must never die silently
        exit_code, out, err = None, "", f"{type(exc).__name__}: {exc}"
    parsed = None
    if out:
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            parsed = None
    return {"cmd": " ".join(cmd), "exit_code": exit_code, "stdout": out,
            "stderr": err, "parsed": parsed}


# ------------------------------------------------------------------------- IMP-6

def _load_acts(root: pathlib.Path) -> tuple:
    """Every act on disk, read directly: root/acts/<name>/<seq>.json, one JSON object
    per file. This mirrors attest.sign_act's own layout but does not import attest.py,
    for the reason given at the top of this file."""
    acts_dir = pathlib.Path(root) / "acts"
    acts, unparseable = [], 0
    if not acts_dir.exists():
        return acts, unparseable
    for name_dir in sorted(p for p in acts_dir.iterdir() if p.is_dir()):
        for path in sorted(name_dir.glob("*.json")):
            try:
                act = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                unparseable += 1
                continue
            if not isinstance(act, dict):
                unparseable += 1
                continue
            act = dict(act)
            act["_path"] = str(path)
            act.setdefault("name", name_dir.name)
            acts.append(act)
    return acts, unparseable


def _signed_event_keys(events_path: pathlib.Path) -> tuple:
    """The (name, seq) pairs act_signed events certify, deduplicated per D-9
    (event_stats.identity), plus the raw/distinct counts M-1 requires printed together.
    """
    rows, bad = event_stats.load(events_path)
    signed_raw = [e for e in rows if e.get("event") == "act_signed"]

    seen, distinct_events = set(), []
    for e in signed_raw:
        ident = event_stats.identity(e)
        if ident not in seen:
            seen.add(ident)
            distinct_events.append(e)

    keys = {(e.get("name"), e.get("seq")) for e in distinct_events}
    counts = {
        "raw": len(signed_raw),
        "distinct": len(distinct_events),
        "replay_factor": (round(len(signed_raw) / len(distinct_events), 2)
                          if distinct_events else None),
        "lines_unparseable": bad,
        "dedup_rule": event_stats.DEDUP_RULE,
        "source": str(events_path),
    }
    return keys, counts


def imp6_check(root, events_path=None) -> dict:
    """IMP-6: an act with no corresponding act_signed event is anomalous.

    Computes and reports ONLY (IMP-7). The returned dict carries no pass/fail field by
    design -- `test_close_checks.py` asserts that directly, via the key set, so a future
    edit that adds one fails the test rather than failing silently.
    """
    root = pathlib.Path(root)
    events_path = (pathlib.Path(events_path) if events_path
                   else root / "logs" / "events.jsonl")
    acts, unparseable_acts = _load_acts(root)
    signed_keys, event_counts = _signed_event_keys(events_path)

    matched, anomalous = [], []
    for act in acts:
        key = (act.get("name"), act.get("seq"))
        row = {"name": act.get("name"), "seq": act.get("seq"), "kind": act.get("kind"),
               "task": act.get("task"), "path": act.get("_path")}
        (matched if key in signed_keys else anomalous).append(row)

    return {
        "authority": "IMP-6, coordinator-decisions-ruling-round-2.md D-22",
        "acts_total": len(acts),
        "acts_unparseable": unparseable_acts,
        "acts_matched": len(matched),
        "acts_anomalous": anomalous,
        "act_signed_events": event_counts,
        "dedup_predicate_source": "event_stats.py identity() (D-9, TELEMETRY-PROVENANCE-A)",
    }


# --------------------------------------------------------------------- epic-close

def epic_close(root, events_path=None) -> dict:
    """The one command the coordinator runs at every epic close (option 6b).

    Runs attest.py forks, warrant.py reconcile and the IMP-6 check, and returns ONE
    report dict. Nothing here is a verdict (IMP-7, PR-022 clause 4): the dict carries
    the three sub-reports verbatim, plus a note saying so, and no field this tool
    computed itself decides pass or fail.
    """
    root = pathlib.Path(root)
    forks = _run_cli("attest.py", ["forks"], root)
    reconcile = _run_cli("warrant.py", ["reconcile"], root)
    imp6 = imp6_check(root, events_path)
    return {
        "report": "epic-close checks (option 6b, ratified 2026-10-21)",
        "IMP_7": "computed and reported only; nothing here gates, weighs or grants a "
                 "privilege (PR-022 clause 4)",
        "forks": forks,
        "reconcile": reconcile,
        "imp6": imp6,
    }


# ------------------------------------------------------------------------- render

def _render_imp6(out: dict) -> None:
    ec = out["act_signed_events"]
    print("IMP-6 (acts on disk vs act_signed events)")
    print(f"  authority           {out['authority']}")
    print(f"  dedup predicate     {ec['dedup_rule']}  ({out['dedup_predicate_source']})")
    print(f"  act_signed events   raw={ec['raw']}  distinct={ec['distinct']}  "
          f"replay={ec['replay_factor']}x  unparseable_lines={ec['lines_unparseable']}")
    print(f"  acts on disk        total={out['acts_total']}  "
          f"matched={out['acts_matched']}  anomalous={len(out['acts_anomalous'])}  "
          f"unparseable={out['acts_unparseable']}")
    for a in out["acts_anomalous"]:
        print(f"    ANOMALOUS  {a['name']}#{a['seq']}  kind={a['kind']}  task={a['task']}"
              f"  {a['path']}")


def _render(out: dict) -> None:
    print(out["report"])
    print(f"  {out['IMP_7']}")
    print()

    f = out["forks"]
    print(f"attest.py forks        exit={f['exit_code']}")
    forks_list = f["parsed"] if isinstance(f["parsed"], list) else None
    if forks_list is not None:
        print(f"  forks found: {len(forks_list)}")
    else:
        print(f"  (unparsed output) stderr={f['stderr'][:200]}")
    print()

    r = out["reconcile"]
    print(f"warrant.py reconcile    exit={r['exit_code']}")
    rp = r["parsed"] or {}
    if r["parsed"] is not None:
        print(f"  orphans: {len(rp.get('orphans') or [])}   "
              f"reported clean={rp.get('clean')}")
    else:
        print(f"  (unparsed output) stderr={r['stderr'][:200]}")
    print()

    _render_imp6(out["imp6"])


# ----------------------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="close_checks.py - the epic-close report: attest.py forks, "
                    "warrant.py reconcile and IMP-6 (act vs act_signed event), one "
                    "printout, read-only (IMP-7, PR-022 clause 4).")
    ap.add_argument("--root", help="harness root (default: .harness)")
    ap.add_argument("--events", default=None,
                    help="path to events.jsonl (default: <root>/logs/events.jsonl)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("epic-close", help="run all three checks, print one report")
    sub.add_parser("imp6", help="only the IMP-6 check (acts vs act_signed events)")
    args = ap.parse_args(argv)
    cmd = args.cmd or "epic-close"

    root = resolve_root(args.root)
    events = pathlib.Path(args.events) if args.events else None

    if cmd == "imp6":
        out = imp6_check(root, events)
        if args.json:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            _render_imp6(out)
    else:
        out = epic_close(root, events)
        if args.json:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            _render(out)

    # IMP-7: this tool reports; it never gates. Exit 0 regardless of what the three
    # checks found -- pinned by test_close_checks.py.
    return 0


if __name__ == "__main__":
    sys.exit(main())
