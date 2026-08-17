#!/usr/bin/env python3
"""westphalia_kpi.py - the PR-029 reconciliation-cost KPI (D4b, T-403).

WHAT PR-029 ACTUALLY SAYS, READ BEFORE ANYTHING WAS BUILT. Its `dicta` are empty, so every
clause below is RATIO and binds on publication under SDR-01:

  (1) the load-bearing empirical question of Part C is how expensive divergence repair is;
  (2) the operator baseline: ~3 months of human effort reconciling architecture and
      redundancy differences between two simple systems;
  (3) the measure: wall-clock hours PLUS tokens to reconcile two domain registries or two
      workstreams diverged for N weeks;
  (4) the cadence: quarterly, alongside the Part VI monitoring duty and the T-349 watch;
  (5) the interpretation rule: trending toward negligible means Part C's containment is
      over-engineered and should be simplified; staying expensive means Westphalia stands;
  (6) "The metric is measurable only once two domain registries exist; until then it is
      recorded as not yet measurable with that reason, never as zero."

Clause 6 is quoted in its own casing. An earlier draft of this docstring set it in capitals
for emphasis, which alters quoted ratio text -- a small thing, except that this module's whole
subject is not misquoting records, and the coordinator has four tier-1 miscitations on file
from 2026-08-17. Emphasis goes outside the quotation marks.

CLAUSE 6 IS THIS TOOL'S ENTIRE SHAPE, AND IT IS AN INSTRUCTION TO REFUSE. One domain registry
exists. So the correct output today is NOT YET MEASURABLE and the reason, and a tool that
printed 0 hours and 0 tokens would VIOLATE A TIER-1 RATIO while looking like it was working.
That is the whole reason this file refuses to emit a cost figure, and a test asserts no code
path in it can.

WHY THAT IS NOT PEDANTRY. A KPI reading zero reads as "divergence repair is free", which is
clause 5's first branch, which concludes Part C's containment architecture is over-engineered
and should be SIMPLIFIED. So a zero here does not merely mislead; it argues for dismantling
the containment layer, from a measurement that was never taken.

NO THRESHOLD RATIFIED. Clause 5 gives a DIRECTION (toward negligible / stays expensive) and
names no failing point, no units for "negligible", and no comparison basis against the 3-month
baseline. currency.py set the precedent for exactly this situation: emit the figure, refuse
the verdict. A tool that invents the threshold has decided the conjunction on the operator's
behalf.

WHAT IS AND IS NOT INSTRUMENTED, stated so the gap is not mistaken for a value of zero:
  TOKENS         partially. `usage_report.py` harvests the runner's transcripts. It is a
                 HARVESTER, not a counter this harness writes -- read its cache split before
                 treating raw tokens as cost.
  WALL-CLOCK     NOT INSTRUMENTED AT ALL. The harness writes no duration counters. Clause 3
                 requires hours PLUS tokens, so even with two registries the measure would be
                 half-blind, and that is reported rather than silently dropped.

COUNTS ARE REPORTED TWICE, raw and distinct, per TELEMETRY-PROVENANCE-A -- whose measurement
was that the raw event log replays at 3.93x overall and up to 47x on some event types.

A COUNT OF ZERO MEASUREMENTS IS NOT A COST OF ZERO, and this file keeps those apart
everywhere. "No measurement has been taken" is a true and useful count. "Reconciliation costs
zero" is the forbidden claim. Conflating them is the specific defect clause 6 legislates
against.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness_common as hc  # noqa: E402

RECORD_ID = "PR-029"
NOT_MEASURABLE = "NOT YET MEASURABLE"
REQUIRED_REGISTRIES = 2
QUARTERLY_WATCH_TASK = "T-349"
MEASUREMENTS_NEEDED_FOR_REVISIT = 3

PUBLIC_API = ("domain_registries", "measurements", "report")


def domain_registries(root) -> dict:
    """What counts as a domain registry, and WHOSE DEFINITION THAT IS.

    PR-029 does not define the term. So this is THE TOOL'S OPERATIONALIZATION and it is
    labelled as such in the output rather than presented as the record's: a domain registry is
    a directory under the harness root holding numbered, immutable records with their own id
    prefix. Today that is `precedents/` (PR-*) and nothing else.

    The definition is printed with every run precisely because it is contestable, and because
    it is the switch that decides whether clause 6's refusal still applies. If someone wants
    the KPI to become measurable, the cheapest way is to argue this definition wider rather
    than to build a second registry -- so the definition has to be visible enough to argue
    with.
    """
    root = pathlib.Path(root)
    found = []
    candidates = {"precedents": "PR-"}
    for name, prefix in sorted(candidates.items()):
        d = root / name
        if not d.is_dir():
            continue
        n = len(list(d.glob(prefix + "*.json")))
        if n:
            found.append({"name": name, "prefix": prefix, "records": n})
    return {
        "registries_raw": len(found),
        "registries_distinct": len({f["name"] for f in found}),
        "registries": found,
        "THIS_DEFINITION_IS_THE_TOOLS_NOT_THE_RECORDS": (
            "PR-029 does not define 'domain registry'. This tool counts a directory of "
            "numbered immutable records with its own id prefix. The definition is printed "
            "because it is contestable AND because it is the switch that decides whether "
            "clause 6's refusal applies: widening it is a cheaper way to make this KPI "
            "'measurable' than building a second registry, so it must be visible enough to "
            "argue with."),
    }


def measurements(root) -> dict:
    """Reconciliation measurements on file. Zero today, and zero MEASUREMENTS is not zero COST.

    Storage is `<root>/kpi/westphalia/*.json`. The directory does not exist and this function
    does NOT create it: a tool that made its own empty store on read would make "the store is
    empty" indistinguishable from "the store was never set up", and those are different facts.
    """
    d = pathlib.Path(root) / "kpi" / "westphalia"
    rows = []
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            try:
                m = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                rows.append({"_unparseable": str(p)})
                continue
            m["_path"] = str(p)
            rows.append(m)
    good = [r for r in rows if "_unparseable" not in r]
    return {
        "store": str(d),
        "store_exists": d.is_dir(),
        "measurements_raw": len(rows),
        "measurements_distinct": len({r.get("quarter") for r in good}) if good else 0,
        "unparseable": [r["_unparseable"] for r in rows if "_unparseable" in r],
        "measurements": good,
        "A_COUNT_OF_ZERO_IS_NOT_A_COST_OF_ZERO": (
            "measurements_raw is how many times the cost was measured. It is NOT the cost. "
            "PR-029 clause 6 forbids recording this metric as zero, and conflating an empty "
            "measurement set with a zero cost is exactly the error it legislates against."),
    }


def report(root) -> dict:
    """The KPI. Emits NO cost figure while clause 6's condition holds."""
    reg = domain_registries(root)
    mes = measurements(root)
    enough = reg["registries_distinct"] >= REQUIRED_REGISTRIES

    out = {
        "record": RECORD_ID,
        "status": NOT_MEASURABLE if not enough else "MEASURABLE (conditions met)",
        "registries_raw": reg["registries_raw"],
        "registries_distinct": reg["registries_distinct"],
        "registries_required": REQUIRED_REGISTRIES,
        "registries": reg["registries"],
        "measurements_raw": mes["measurements_raw"],
        "measurements_distinct": mes["measurements_distinct"],
        "measurements_needed_for_revisit": MEASUREMENTS_NEEDED_FOR_REVISIT,
        "quarterly_watch": QUARTERLY_WATCH_TASK,
        "operator_baseline": ("approximately 3 months of human effort reconciling "
                              "architecture and redundancy differences between two simple "
                              "systems (PR-029 clause 2, verbatim substance)"),
        "measure_required_by_clause_3": ["wall_clock_hours", "tokens"],
        "instrumentation": {
            "tokens": ("PARTIAL. usage_report.py harvests the runner's transcripts. It is a "
                       "harvester, not a counter this harness writes; read its cache split "
                       "before treating raw tokens as cost."),
            "wall_clock_hours": ("NOT INSTRUMENTED. The harness writes no duration counters. "
                                 "Clause 3 requires hours PLUS tokens, so even once two "
                                 "registries exist this measure would be half-blind. Reported "
                                 "rather than silently dropped."),
        },
        "THIS_DEFINITION_IS_THE_TOOLS_NOT_THE_RECORDS":
            reg["THIS_DEFINITION_IS_THE_TOOLS_NOT_THE_RECORDS"],
        "A_COUNT_OF_ZERO_IS_NOT_A_COST_OF_ZERO":
            mes["A_COUNT_OF_ZERO_IS_NOT_A_COST_OF_ZERO"],
        "NO_THRESHOLD_RATIFIED": (
            "PR-029 clause 5 gives a DIRECTION and no failing point: 'if reconciliation cost "
            "trends toward negligible, the containment architecture of Part C is "
            "over-engineered and should be simplified; if it stays expensive, Westphalia "
            "stands.' It defines no units for negligible and no comparison basis against the "
            "3-month baseline. So no verdict is emitted here. currency.py set this precedent: "
            "emit the figure, refuse the verdict."),
    }
    if not enough:
        out["WHY_NO_FIGURE"] = (
            "PR-029 clause 6, which is RATIO and therefore binding: 'The metric is measurable "
            "only once two domain registries exist; until then it is recorded as not yet "
            "measurable with that reason, never as zero.' {} domain registry/registries "
            "exist. THE REASON, as clause 6 requires it be recorded: only one domain registry "
            "exists, so there is nothing to reconcile against and no divergence to repair. "
            "This tool therefore emits NO cost figure. A zero here would read as 'divergence "
            "repair is free', which is clause 5's first branch, which argues for SIMPLIFYING "
            "the containment layer -- from a measurement never taken."
            .format(reg["registries_distinct"]))
        out["cost"] = None
    else:
        out["WHY_NO_FIGURE"] = (
            "Clause 6's precondition is now met: {} domain registries exist. This tool still "
            "emits no cost, because measuring one requires an actual reconciliation to "
            "observe and clause 3's wall-clock half is not instrumented. Record a measurement "
            "in {} and re-run.".format(reg["registries_distinct"], mes["store"]))
        out["cost"] = None
    return out


def _render(out) -> None:
    print("KPI {} -- {}".format(out["record"], out["status"]))
    print("registros de dominio   {} crudos / {} distintos  (se requieren {})".format(
        out["registries_raw"], out["registries_distinct"], out["registries_required"]))
    for r in out["registries"]:
        print("    {} ({}) {} registros".format(r["name"], r["prefix"], r["records"]))
    print("mediciones en archivo  {} crudas / {} distintas  (se requieren {} para revisar)"
          .format(out["measurements_raw"], out["measurements_distinct"],
                  out["measurements_needed_for_revisit"]))
    print("vigilancia trimestral  {}".format(out["quarterly_watch"]))
    print("costo                  {}".format(
        "NO EMITIDO" if out["cost"] is None else out["cost"]))
    print("\nPOR QUE NO HAY CIFRA\n" + out["WHY_NO_FIGURE"])
    print("\nLINEA BASE DEL OPERADOR\n" + out["operator_baseline"])
    print("\nINSTRUMENTACION")
    for k, v in out["instrumentation"].items():
        print("  {}: {}".format(k, v))
    print("\n" + out["A_COUNT_OF_ZERO_IS_NOT_A_COST_OF_ZERO"])
    print("\n" + out["THIS_DEFINITION_IS_THE_TOOLS_NOT_THE_RECORDS"])
    print("\nNO THRESHOLD RATIFIED\n" + out["NO_THRESHOLD_RATIFIED"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="PR-029 reconciliation-cost KPI. Read-only. Emits NO cost figure while "
                    "clause 6's precondition is unmet, and NO verdict ever.")
    ap.add_argument("--root", default=None,
                    help="harness root (default: the .harness/ containing this file)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    root = pathlib.Path(args.root) if args.root else pathlib.Path(__file__).resolve().parent.parent
    out = report(root)
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        _render(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
