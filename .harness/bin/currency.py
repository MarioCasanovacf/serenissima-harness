#!/usr/bin/env python3
"""currency.py - the A.8 currency-health indicator. Read-only. Emits no verdict.

WHY THIS EXISTS. PR-023 clause 5, verbatim: "The gate is conjunctive with the A.8
currency-health indicator: even with the gate closed, Phase B does not ship if the
currency is failing." The indicator was DEFINED in addendum AB7 and never built. It rode
as a note on T-349's quarterly watch, next due 2026-11-10, with no tool computing it. So
the second arm of a tier-1 conjunction had no instrument, and any claim that Phase B was
ready would have been resting on an unmeasured condition.

THE TWO MEASURES, from AB7 verbatim: "load-bearing vs name-drop convergence; standing
concentration without verified work - either failing means Phase B does not ship
regardless of the identity gate."

  A.8.1 CONVERGENCE. A record can cite another two ways: a bare token in `cites`, or a
        TYPED relation in `relations[]` routed as `follows` or `reinterprets`. Only the
        second can ever be load-bearing (reputation.py's figure 2, T-367 steps 1-4).
        A citation economy where the bare tokens outgrow the typed relations is one
        where a citation has stopped meaning anything -- the reputational currency
        inflates, exactly as a coin does when the mint stops caring what is in it.
        Reported as the share of citation edges that are typed, and as its trend across
        the publication sequence.

  A.8.2 CONCENTRATION WITHOUT VERIFIED WORK. Standing accruing to a few names is not by
        itself a problem; a small registry has few authors. Standing accruing to names
        who have done no VERIFIED work is rent. Reported as the top-1 and top-3 share of
        authored records, alongside how much of that standing belongs to identities that
        satisfy NEITHER mechanical signal of verified work: a record confirmed by a
        different identity (PR-015's floor), or a record a different identity typed a
        load-bearing-eligible citation at.

        THE FIRST SIGNAL IS CURRENTLY DEGENERATE and the tool says so on every run. Zero
        of the 59 live records carry a `confirmed_by`: PR-015's distinct-identity floor
        has never once been exercised in this registry. A measure that separates nobody
        from anybody is not measuring, which is the entire reason the second signal is
        here rather than shipping a tidy 100%.

WHAT THIS TOOL REFUSES TO DO, AND WHY THAT IS THE POINT. It emits NO pass/fail verdict.
"Failing" in PR-023 clause 5 is not defined by any ratified threshold, and inventing one
here would hand a tier-1 conjunction a number nobody voted on -- which is precisely the
defect the metric epic exists to remove. `event_stats.py` refuses to compute a catch-rate
for the same reason: a figure the operator cannot falsify is worse than no figure. The
threshold is an operator decision, and until it is ratified this tool reports the
measures, the trend, and the words NO THRESHOLD RATIFIED.

M-1 AND M-2 APPLY. Every count carries its denominator, and the provenance -- source
paths, record count, exclusions -- prints with every run including `--json`. Both rules
were set by operator decision D-9 and are enforced by `event_stats.py` already.

READ-ONLY, ABSOLUTELY. Same verb class as token_share.py, usage_report.py and
event_stats.py: no writes, no hc.log_event, no lock, no cache, no temp file. It cannot
attach a consequence because it cannot write anything (PR-022 clause 4, PR-017).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness_common as hc  # noqa: E402

DEFAULT_ROOT = hc.HARNESS
TYPED_LOAD_BEARING = ("follows", "reinterprets")
MIN_WINDOW_EDGES = 20   # below this a half-window share is noise, not a trend
NO_THRESHOLD = ("NO THRESHOLD RATIFIED: PR-023 clause 5 conditions Phase B on this "
                "indicator but defines no failing point. This tool reports the "
                "measures and refuses to invent one.")

PUBLIC_API = ("load_records", "convergence", "concentration", "structure", "report")

# A.8.3 window: how many of the most recent records LIVENESS looks back over. Chosen to
# match MIN_WINDOW_EDGES' discipline rather than a round number -- a window is only
# reportable when the registry is large enough for it to mean something.
LIVENESS_WINDOW = 25


def load_records(root) -> dict:
    d = pathlib.Path(root) / "precedents"
    out = {}
    if not d.exists():
        return out
    for path in sorted(d.glob("PR-*.json")):
        rec = hc.read_json(path, default=None)
        if isinstance(rec, dict) and rec.get("id"):
            out[rec["id"]] = rec
    return out


# ------------------------------------------------------------------ A.8.1 convergence

def convergence(records: dict) -> dict:
    """Share of citation edges that are TYPED and load-bearing-eligible.

    An edge is counted once per (citing record, cited record) pair. A pair that appears
    both as a bare `cites` token and as a typed relation counts as TYPED: the typed form
    is strictly more informative and the bare token is then redundant, not a name-drop.
    """
    typed_pairs, bare_pairs, per_record = set(), set(), []
    for rid in sorted(records):
        rec = records[rid]
        typed_here = set()
        for rel in (rec.get("relations") or []):
            target = rel.get("target")
            if target and rel.get("type") in TYPED_LOAD_BEARING:
                typed_here.add(target)
        cited_here = {c for c in (rec.get("cites") or []) if c}
        bare_here = cited_here - typed_here
        typed_pairs |= {(rid, t) for t in typed_here}
        bare_pairs |= {(rid, b) for b in bare_here}
        total_here = len(typed_here) + len(bare_here)
        per_record.append({
            "record": rid,
            "published_at": rec.get("published_at"),
            "typed": len(typed_here),
            "bare": len(bare_here),
            "share_typed": round(len(typed_here) / total_here, 3) if total_here else None,
        })

    typed, bare = len(typed_pairs), len(bare_pairs)
    total = typed + bare
    half = len(per_record) // 2
    def window(rows):
        t = sum(r["typed"] for r in rows)
        b = sum(r["bare"] for r in rows)
        return {"records": len(rows), "typed": t, "bare": b,
                "share_typed": round(t / (t + b), 3) if (t + b) else None}
    early, late = window(per_record[:half]), window(per_record[half:])
    drift = None
    if early["share_typed"] is not None and late["share_typed"] is not None:
        drift = round(late["share_typed"] - early["share_typed"], 3)
    # A share computed on a handful of edges is not a trend. The first version of this
    # function named a DIRECTION off a second half holding six edges, and the direction
    # was reported to the operator as "converging". That is the exact defect this epic
    # exists to remove: a figure whose denominator is too small to carry it.
    thin = min(early["typed"] + early["bare"], late["typed"] + late["bare"])
    drift_is_reportable = thin >= MIN_WINDOW_EDGES

    return {
        "citation_edges_total": total,
        "typed_load_bearing_eligible": typed,
        "bare_name_drop": bare,
        "share_typed": round(typed / total, 3) if total else None,
        "first_half": early,
        "second_half": late,
        "drift_share_typed": drift,
        "min_window_edges": thin,
        "drift_is_reportable": drift_is_reportable,
        "DIRECTION": (
            f"NOT REPORTABLE: the thinner half carries {thin} citation edges, below the "
            f"{MIN_WINDOW_EDGES} this tool requires before naming a direction. A share "
            "computed on a handful of edges is not a trend."
            if drift is not None and not drift_is_reportable else
            "unknown (too few records to split)" if drift is None else
            "converging: typed citations are gaining on bare name-drops" if drift > 0 else
            "flat" if drift == 0 else
            "DIVERGING: bare name-drops are outgrowing typed citations, which is what "
            "an inflating citation currency looks like"),
        "eligibility_caveat": (
            "typed here means routed `follows`/`reinterprets` per reputation.py figure 2 "
            "steps 1-4. It is an ELIGIBLE-UPPER-BOUND, never a load-bearing verdict: "
            "steps 5-7 need a confirming identity and have no storage field (PR-024)."),
        "NO_THRESHOLD_RATIFIED": NO_THRESHOLD,
    }


# ---------------------------------------------------------------- A.8.2 concentration

def concentration(records: dict) -> dict:
    """Top-share of authorship, and how much of it belongs to names with no verified work.

    VERIFIED WORK is read mechanically, under either of two signals: a record CONFIRMED
    by a different identity (PR-015's floor), or a record a different identity typed a
    load-bearing-eligible citation at. Nothing here judges quality; it distinguishes a
    name some second party stood behind or built on from a name that only published.
    """
    authored, confirmed_for, built_on = {}, {}, {}
    for rid in sorted(records):
        rec = records[rid]
        who = rec.get("published_by") or "<unattributed>"
        authored.setdefault(who, []).append(rid)
        confirmer = rec.get("confirmed_by")
        if confirmer and confirmer != who:
            confirmed_for.setdefault(who, []).append(rid)

    # Second, independent signal. The confirmation signal above is currently degenerate:
    # 0 of 59 live records carry a confirmed_by, so it reports 100% unverified and
    # distinguishes nobody from anybody. A measure that cannot separate its subjects is
    # not measuring. This one asks whether a DIFFERENT identity typed a load-bearing
    # citation at your record -- someone else built on your work, which is the thing
    # "verified work" is trying to name.
    by_author = {rid: (records[rid].get("published_by") or "<unattributed>")
                 for rid in records}
    for rid in sorted(records):
        citer = by_author[rid]
        for rel in (records[rid].get("relations") or []):
            target = rel.get("target")
            if (target in by_author and rel.get("type") in TYPED_LOAD_BEARING
                    and by_author[target] != citer):
                built_on.setdefault(by_author[target], set()).add(rid)

    total = sum(len(v) for v in authored.values())
    ranked = sorted(authored.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    def share(n):
        return round(sum(len(v) for _, v in ranked[:n]) / total, 3) if total else None

    # An identity counts as having verified work under EITHER signal.
    verified = set(confirmed_for) | set(built_on)
    unverified = {who: recs for who, recs in authored.items() if who not in verified}
    unverified_records = sum(len(v) for v in unverified.values())
    confirmed_total = sum(len(v) for v in confirmed_for.values())

    return {
        "identities": len(authored),
        "records_total": total,
        "top1_share": share(1),
        "top3_share": share(3),
        "signal_1_confirmations_total": confirmed_total,
        "signal_1_is_degenerate": confirmed_total == 0,
        "signal_1_note": (
            "0 confirmations across the whole registry means PR-015's distinct-identity "
            "floor has never once been exercised. Reported, not interpreted: a measure "
            "that separates nobody from anybody is not measuring, which is why signal 2 "
            "exists." if confirmed_total == 0 else None),
        "ranking": [{"identity": who, "records": len(recs),
                     "confirmed_by_another": len(confirmed_for.get(who, [])),
                     "built_on_by_another": len(built_on.get(who, set())),
                     "has_verified_work": who in verified}
                    for who, recs in ranked],
        "identities_without_verified_work": sorted(unverified),
        "records_held_without_verified_work": unverified_records,
        "share_without_verified_work": (round(unverified_records / total, 3)
                                        if total else None),
        "verified_work_definition": (
            "EITHER signal 1, an authored record confirmed by a DIFFERENT identity "
            "(PR-015's floor), OR signal 2, an authored record that a DIFFERENT "
            "identity typed a load-bearing-eligible citation at. Both are mechanical. "
            "Neither judges quality, and a broader definition would need a judgment this "
            "tool is not entitled to make."),
        "NO_THRESHOLD_RATIFIED": NO_THRESHOLD,
    }


# ------------------------------------------------------------------- A.8.3 structure

def structure(records: dict) -> dict:
    """BREADTH, LIVENESS and RECIPROCITY over the citation graph. Emits no verdict.

    WHY THESE THREE. The third blind panel refused the three-functions-of-money candidate
    for the A.8 failing point and proposed these instead. The refusal was structural, not
    stylistic: medium-of-exchange is unsatisfiable here because standing is derived on read
    and never held (PR-022 clause 1, PR-010), and D-22 IMP-1 makes the ABSENCE of a
    transfer verb the anti-forgery guarantee. Ratifying that candidate would have made the
    currency permanently failing and PR-023 clause 5's conjunction permanently closed --
    barring Phase B by definition rather than by evidence.

    These three are supply-side. None is circular. None requires alienability. None is
    satisfiable by bulk publication or by writing one sentence, which were the two attacks
    that killed the previous candidate's arms.

      A.8.3.1 BREADTH. Of the N*(N-1) ordered author-pairs possible among the publishing
              identities, how many carry a typed citation, and what share of typed
              citations is issued from OUTSIDE the top-3 by authorship. This is the direct
              structural brake on a closed ring, which no other measure in this module
              detects. Self-citation is excluded from both the numerator and the
              denominator: a pair needs two parties.

      A.8.3.2 LIVENESS. Typed citations issued per record published over the trailing
              window. Carries its denominator per M-1 and reuses convergence()'s
              refuse-on-thin-data discipline, so a window that cannot support a rate says
              so instead of printing one.

      A.8.3.3 RECIPROCITY. The share of realized cross-author pairs that lie on a mutual
              pair. Reported as a MEASURE and never as a verdict, because this module
              cannot distinguish a genuine reciprocal citation from a manufactured one and
              neither could the panelist who raised it. A high value is a reason to look,
              never a finding of wrongdoing.

    NO THRESHOLD IS RATIFIED FOR ANY OF THE THREE. Same refusal as everywhere else in this
    module: PR-023 clause 5 defines no failing point and a tool that invents one has
    decided a tier-1 conjunction.
    """
    by_author = {rid: (records[rid].get("published_by") or "<unattributed>")
                 for rid in records}
    identities = sorted(set(by_author.values()))
    n = len(identities)

    authored = {}
    for rid in sorted(records):
        authored.setdefault(by_author[rid], []).append(rid)
    top3 = {who for who, _ in sorted(authored.items(),
                                     key=lambda kv: (-len(kv[1]), kv[0]))[:3]}

    pairs, self_edges, external_edges, issued_by = {}, 0, 0, {}
    for rid in sorted(records):
        citer = by_author[rid]
        for rel in (records[rid].get("relations") or []):
            target = rel.get("target")
            if not target or rel.get("type") not in TYPED_LOAD_BEARING:
                continue
            issued_by[citer] = issued_by.get(citer, 0) + 1
            if target not in by_author:
                external_edges += 1          # points outside the registry: not a pair
                continue
            cited = by_author[target]
            if cited == citer:
                self_edges += 1              # not a pair: a pair needs two parties
                continue
            pairs[(citer, cited)] = pairs.get((citer, cited), 0) + 1

    possible = n * (n - 1)
    realized = sorted(pairs)
    mutual = sorted(p for p in pairs if (p[1], p[0]) in pairs)
    cross_edges = sum(pairs.values())
    issued_total = sum(issued_by.values())
    outside_top3 = sum(v for k, v in issued_by.items() if k not in top3)

    # THE MEASURE THAT ANSWERS THE QUESTION, and why the obvious one does not. The panel
    # proposed "share issued from outside the top-3 BY AUTHORSHIP". Computed literally on
    # this registry that returns 0.417, which reads as a mostly-open economy -- and it is
    # an artifact. The top-3 by authorship and the set of identities that actually
    # participate in the citation graph are DIFFERENT SETS here: the largest publisher has
    # never cited or been cited, while the 4th-largest issues a third of all citations. So
    # the top-3-by-authorship figure measures the mismatch between those two sets, not the
    # openness of the economy.
    #
    # The set that matters is the INCUMBENTS: identities already holding a cross-author
    # typed citation received. The share issued from outside it answers "is anyone new
    # participating", which is the question breadth exists to ask. Both are reported,
    # separately named, because the panel's literal words are on the record and silently
    # substituting a different measure for them would be its own defect.
    incumbents = {cited for _, cited in pairs}
    outside_incumbents = sum(v for k, v in issued_by.items() if k not in incumbents)

    # LIVENESS over the trailing window, by publication order.
    ordered = sorted(records)
    window = ordered[-LIVENESS_WINDOW:]
    win_issued = 0
    for rid in window:
        for rel in (records[rid].get("relations") or []):
            if rel.get("target") and rel.get("type") in TYPED_LOAD_BEARING:
                win_issued += 1

    return {
        "A_8_3_1_breadth": {
            "identities": n,
            "ordered_pairs_possible": possible,
            "ordered_pairs_realized": len(realized),
            "share_realized": round(len(realized) / possible, 3) if possible else None,
            "realized_pairs": [f"{a} -> {b} ({pairs[(a, b)]})" for a, b in realized],
            "typed_issued_total": issued_total,
            "incumbents": sorted(incumbents),
            "typed_issued_outside_incumbents": outside_incumbents,
            "share_issued_outside_incumbents": (round(outside_incumbents / issued_total, 3)
                                                if issued_total else None),
            "incumbents_note": (
                "incumbents are the identities already holding a cross-author typed "
                "citation RECEIVED. The share issued from outside them answers whether "
                "anyone new is participating, which is what breadth exists to ask."),
            "typed_issued_outside_top3_by_authorship": outside_top3,
            "share_issued_outside_top3_by_authorship": (
                round(outside_top3 / issued_total, 3) if issued_total else None),
            "top3_by_authorship": sorted(top3),
            "why_two_figures": (
                "the panel's words were 'outside the top-3 by authorship'; on this "
                "registry that returns a healthy-looking number because the top-3 by "
                "authorship and the identities that actually cite are different sets -- "
                "the largest publisher has never cited nor been cited, and the "
                "4th-largest issues a third of all citations. Both figures print so the "
                "panel's literal measure stays on the record and the substitution is "
                "visible rather than silent."),
            "excluded_from_pairs": {
                "self_citations": self_edges,
                "targets_outside_registry": external_edges,
                "why": "a pair needs two parties, and a target this registry does not "
                       "hold cannot be attributed to an identity",
            },
        },
        "A_8_3_2_liveness": {
            "window_records": len(window),
            "window_declared": LIVENESS_WINDOW,
            "typed_issued_in_window": win_issued,
            "typed_per_record": (round(win_issued / len(window), 3) if window else None),
            "REPORTABLE": win_issued >= MIN_WINDOW_EDGES,
            "note": (
                f"{win_issued} typed citation(s) in the trailing {len(window)} records, "
                f"below the {MIN_WINDOW_EDGES} this module requires before a rate carries "
                "any weight. The number prints because suppressing it would be a "
                "different defect; it is not a trend."
                if win_issued < MIN_WINDOW_EDGES else
                f"{win_issued} typed citation(s) over {len(window)} records."),
        },
        "A_8_3_3_reciprocity": {
            "cross_author_edges": cross_edges,
            "realized_pairs": len(realized),
            "pairs_on_a_mutual_edge": len(mutual),
            "mutual_pairs": [f"{a} <-> {b}" for a, b in mutual if a < b],
            "share_of_pairs_mutual": (round(len(mutual) / len(realized), 3)
                                      if realized else None),
            "NOT_A_FINDING": (
                "This module cannot distinguish a genuine reciprocal citation from a "
                "manufactured one, and no instrument in this harness can. A high value "
                "is a reason to look, never a finding of wrongdoing."),
        },
        "NO_THRESHOLD_RATIFIED": NO_THRESHOLD,
    }


# ---------------------------------------------------------------------------- report

def report(root) -> dict:
    root = pathlib.Path(root)
    records = load_records(root)
    return {
        "provenance": {
            "source": str(root / "precedents"),
            "records_read": len(records),
            "typed_relations_counted": list(TYPED_LOAD_BEARING),
            "authority": "PR-023 clause 5; addendum AB7; T-349 quarterly note",
            "excluded": "nothing; every PR-*.json that parses is counted, and the "
                        "record count prints so a reader can check it against `ls`",
            "read_only": "no writes, no events, no locks; this tool cannot attach a "
                         "consequence because it cannot write (PR-022 clause 4)",
        },
        "A_8_1_convergence": convergence(records),
        "A_8_2_concentration": concentration(records),
        "A_8_3_structure": structure(records),
        "VERDICT": ("NOT COMPUTED. " + NO_THRESHOLD + " A tool that invents the failing "
                    "point of a tier-1 conjunction has decided the conjunction."),
    }


def render(out: dict) -> None:
    p, c, k = out["provenance"], out["A_8_1_convergence"], out["A_8_2_concentration"]
    print("PROVENANCE (M-2)")
    print(f"  source            {p['source']}")
    print(f"  records read      {p['records_read']}")
    print(f"  authority         {p['authority']}")
    print()
    print("A.8.1  CONVERGENCIA  (citas tipadas vs menciones de nombre)")
    print(f"  aristas de cita   {c['citation_edges_total']}")
    print(f"  tipadas           {c['typed_load_bearing_eligible']}")
    print(f"  menciones simples {c['bare_name_drop']}")
    print(f"  share tipado      {c['share_typed']}")
    print(f"  primera mitad     {c['first_half']['share_typed']}   "
          f"segunda mitad {c['second_half']['share_typed']}   "
          f"deriva {c['drift_share_typed']}")
    print(f"  aristas min. mitad {c['min_window_edges']}")
    print(f"  direccion         {c['DIRECTION']}")
    print()
    print("A.8.2  CONCENTRACION SIN TRABAJO VERIFICADO")
    print(f"  identidades       {k['identities']}")
    print(f"  registros         {k['records_total']}")
    print(f"  top-1 / top-3     {k['top1_share']} / {k['top3_share']}")
    print(f"  sin trabajo verif {k['share_without_verified_work']} "
          f"({k['records_held_without_verified_work']}/{k['records_total']} registros)")
    if k["signal_1_is_degenerate"]:
        print(f"  AVISO             {k['signal_1_note']}")
    print(f"  {'identidad':24s} {'registros':>9s} {'confirm':>8s} {'citado por otro':>16s}"
          f"  verificada")
    for row in k["ranking"][:10]:
        print(f"  {row['identity'][:24]:24s} {row['records']:9d} "
              f"{row['confirmed_by_another']:8d} {row['built_on_by_another']:16d}"
              f"  {row['has_verified_work']}")
    print()
    s = out["A_8_3_structure"]
    b, lv, rc = s["A_8_3_1_breadth"], s["A_8_3_2_liveness"], s["A_8_3_3_reciprocity"]
    print("A.8.3  ESTRUCTURA DEL GRAFO DE CITAS")
    print(f"  amplitud          {b['ordered_pairs_realized']}/"
          f"{b['ordered_pairs_possible']} pares ordenados  ({b['share_realized']})")
    print(f"  emitidas por nuevos {b['typed_issued_outside_incumbents']}/"
          f"{b['typed_issued_total']}  ({b['share_issued_outside_incumbents']})")
    print(f"    ya establecidos   {', '.join(b['incumbents']) or 'ninguno'}")
    print(f"    medida literal del panel (fuera del top-3 por autoria): "
          f"{b['share_issued_outside_top3_by_authorship']}, ver why_two_figures")
    print(f"  actividad         {lv['typed_issued_in_window']} citas en los ultimos "
          f"{lv['window_records']} registros  (reportable: {lv['REPORTABLE']})")
    print(f"  reciprocidad      {rc['pairs_on_a_mutual_edge']}/{rc['realized_pairs']} "
          f"pares realizados son mutuos  ({rc['share_of_pairs_mutual']})")
    for p in b["realized_pairs"]:
        print(f"      {p}")
    print()
    print(out["VERDICT"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="currency.py - the A.8 currency-health indicator (PR-023 clause 5). "
                    "Read-only. Reports the two measures and emits no verdict.")
    ap.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT,
                    help="harness root (default: the live .harness/)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    out = report(args.root)
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        render(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
