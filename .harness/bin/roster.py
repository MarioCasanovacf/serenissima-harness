#!/usr/bin/env python3
"""roster.py - issued names and published plazas. The identity half of the
agentic-society design, and only that half.

WHAT THIS IS. Today an agent's identity is `os.environ.get("CLAUDE_HARNESS_AGENT_ID",
"main")` and `--agent` is an unvalidated free string, so every eligibility check in the
stack is a comparison against a name the agent gave itself. The registry already carries
108 names against 7 real record authors, minted by accident. This module makes a name
ISSUED and SCARCE instead of self-asserted: a colegiado declares what it is paid for, a
plaza is PUBLISHED BEFORE the work exists, and a name can only be issued into a plaza
that was declared and is still free.

WHAT THIS IS NOT, and the line is a ratified one. PR-023 (tier 1, active) gates Phase B
- "verification-burden discounts, quorum weight, charter contestability" - on
cryptographic identity with an external trust root, and its scope condition is "any
proposal attaching consequence, weighting, quorum weight or charter contestability to
standing". Its clause 4 is written in words that anticipate this file: "Sybil minting is
closed by this gate and by nothing else: nothing else closes it, do not pretend
otherwise."

So, stated plainly rather than blurred: **issuance and scarcity close the failure mode
actually observed - names minted by accident - and they do not close the adversarial
one.** An agent that deliberately writes another agent's name into `--agent` is not
stopped by anything here. That is PR-023's gate and it is not this module's job. Nothing
in this file attaches a consequence, a weight, a discount or a burden to any standing
figure, and `test_roster.py` asserts that no exported callable takes such a parameter.

WHY ELIGIBILITY IS A REPORT AND NOT A GATE. The operator's design replaces spawn-lineage
with colegiado membership as the basis for recusal, which is a better substrate: it needs
one field on a record that already stores `published_by`, and it leaves PRECEDENT.md
section 14's refusal of session infrastructure untouched. But changing what F6's exclusion
is computed from is a constitutional act, and PR-017 requires the amending record to be
published BEFORE the text lands. Until that record exists, `eligible` PRINTS the
colegiado partition and refuses to decide anything with it. A reporter today, a gate only
once a record authorises it.

FOOTPRINT. The operator's constraint was explicit: recorded for posterity, but small,
because bloat slows the system. One flat JSON file, three collections, a persona capped
at PERSONA_MAX characters, and no history: the event log already carries the trail.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness_common as hc  # noqa: E402

ROSTER = pathlib.Path(__file__).resolve().parents[1] / "roster.json"
PRECEDENTS = pathlib.Path(__file__).resolve().parents[1] / "precedents"

PERSONA_MAX = 240
SCHEMA_VERSION = 1

PUBLIC_API = ("load", "charter", "plazas", "issue", "eligible_report")


def _empty() -> dict:
    return {"schema_version": SCHEMA_VERSION, "colegiados": {}, "plazas": {}, "names": {}}


def load() -> dict:
    data = hc.read_json(ROSTER, default=None)
    if not isinstance(data, dict):
        return _empty()
    for key in ("colegiados", "plazas", "names"):
        data.setdefault(key, {})
    data.setdefault("schema_version", SCHEMA_VERSION)
    return data


def _save(data: dict) -> None:
    hc.atomic_write_json(ROSTER, data)


# --------------------------------------------------------------------------- charter

def charter(colegiado: str, incentive: str, by: str) -> dict:
    """Declare a colegiado and, in its own words, WHAT IT IS PAID FOR.

    The incentive is required and is the whole point of the operator's design: a forest
    of lineages with one objective function is a forest of names, not of judgement. It
    is stored as text and read by humans and agents; nothing in this module computes
    with it, because computing with it would be attaching weight to standing.
    """
    data = load()
    existed = colegiado in data["colegiados"]
    data["colegiados"][colegiado] = {
        "incentive": incentive,
        "declared_by": by,
        "declared_at": hc.now_iso(),
    }
    _save(data)
    hc.log_event("roster_charter", colegiado=colegiado, agent=by, amended=existed)
    return data["colegiados"][colegiado]


# ---------------------------------------------------------------------------- plazas

def plazas(epic: str, colegiado: str, role: str, count: int, by: str) -> dict:
    """Publish N seats for an epic BEFORE any of them is filled.

    Publication-before-filling is the property that matters. A seat count announced
    after the agents exist is a description; announced before, it is a constraint, and
    it is the only thing here that makes a name scarce.
    """
    if count < 1:
        raise ValueError("a plaza count must be at least 1")
    data = load()
    if colegiado not in data["colegiados"]:
        raise KeyError(f"colegiado {colegiado!r} has no charter; declare it first")
    bucket = data["plazas"].setdefault(epic, {})
    key = f"{colegiado}/{role}"
    if key in bucket:
        raise KeyError(f"plazas for {key} in {epic} already published; "
                       "republishing after the fact would defeat the point")
    bucket[key] = {"count": count, "declared_by": by, "declared_at": hc.now_iso()}
    _save(data)
    hc.log_event("roster_plazas", epic=epic, colegiado=colegiado, role=role,
                 count=count, agent=by)
    return bucket[key]


def _filled(data: dict, epic: str, key: str) -> int:
    return sum(1 for n in data["names"].values()
               if n["epic"] == epic and f"{n['colegiado']}/{n['role']}" == key)


# ----------------------------------------------------------------------------- issue

def issue(name: str, colegiado: str, role: str, epic: str, by: str,
          persona: str = "") -> dict:
    """Issue a name into a declared, still-free plaza. Refuses otherwise."""
    data = load()
    if name in data["names"]:
        raise KeyError(f"name {name!r} is already issued; names are not reused")
    if colegiado not in data["colegiados"]:
        raise KeyError(f"colegiado {colegiado!r} has no charter")
    key = f"{colegiado}/{role}"
    seat = data["plazas"].get(epic, {}).get(key)
    if seat is None:
        raise KeyError(f"no plazas published for {key} in {epic}")
    used = _filled(data, epic, key)
    if used >= seat["count"]:
        raise KeyError(f"all {seat['count']} plazas for {key} in {epic} are filled")
    if len(persona) > PERSONA_MAX:
        raise ValueError(f"persona exceeds {PERSONA_MAX} chars; the operator's "
                         "constraint is that this stays small")
    data["names"][name] = {
        "colegiado": colegiado, "role": role, "epic": epic,
        "persona": persona, "issued_by": by, "issued_at": hc.now_iso(),
    }
    _save(data)
    hc.log_event("roster_issue", name=name, colegiado=colegiado, role=role,
                 epic=epic, agent=by, seat=f"{used + 1}/{seat['count']}")
    return data["names"][name]


# ------------------------------------------------------------------- eligible REPORT

def eligible_report(record_id: str) -> dict:
    """REPORT, never a gate (see module docstring, PR-017).

    Prints the colegiado partition for a record's author. It decides nothing, returns
    no permission, and every caller is told so in the output itself.
    """
    path = PRECEDENTS / f"{record_id}.json"
    rec = hc.read_json(path, default=None)
    if rec is None:
        raise KeyError(f"no record {record_id}")
    author = rec.get("published_by")
    data = load()
    entry = data["names"].get(author)
    same, other, unissued = [], [], []
    for n, v in data["names"].items():
        if n == author:
            continue
        if entry is None:
            unissued.append(n)
        elif v["colegiado"] == entry["colegiado"]:
            same.append(n)
        else:
            other.append(n)
    return {
        "record": record_id,
        "author": author,
        "author_colegiado": entry["colegiado"] if entry else None,
        "author_is_issued": entry is not None,
        "same_colegiado_would_be_excluded": sorted(same),
        "other_colegiado_would_be_eligible": sorted(other),
        "undecidable_author_not_issued": sorted(unissued),
        "IS_NOT_A_GATE": "advisory only; F6 is not computed from this field until an "
                         "amending record is published (PR-017)",
    }


# ------------------------------------------------------------------------------- cli

def _render_roster(data: dict, epic: str | None) -> None:
    print("COLEGIADOS")
    if not data["colegiados"]:
        print("  (ninguno declarado)")
    for c, v in sorted(data["colegiados"].items()):
        print(f"  {c:22s} paga por: {v['incentive']}")
    print()
    print("PLAZAS  (publicadas antes de llenarse)")
    for e, bucket in sorted(data["plazas"].items()):
        if epic and e != epic:
            continue
        for key, seat in sorted(bucket.items()):
            used = _filled(data, e, key)
            print(f"  {e:18s} {key:28s} {used}/{seat['count']}")
    if not data["plazas"]:
        print("  (ninguna publicada)")
    print()
    print("NOMBRES EMITIDOS")
    rows = [(n, v) for n, v in sorted(data["names"].items())
            if not epic or v["epic"] == epic]
    if not rows:
        print("  (ninguno)")
    for n, v in rows:
        print(f"  {n:22s} {v['colegiado']}/{v['role']:12s} {v['epic']}")
        if v["persona"]:
            print(f"    {v['persona']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="roster.py - issued names and published plazas. Issuance and "
                    "scarcity only; PR-023 still gates everything that attaches a "
                    "consequence to standing.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("charter", help="declare a colegiado and what it is paid for")
    c.add_argument("--colegiado", required=True)
    c.add_argument("--incentive", required=True, help="what this group is paid for")
    c.add_argument("--by", default=hc.agent_id())

    p = sub.add_parser("plazas", help="publish N seats for an epic, before filling them")
    p.add_argument("--epic", required=True)
    p.add_argument("--colegiado", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--count", type=int, required=True)
    p.add_argument("--by", default=hc.agent_id())

    i = sub.add_parser("issue", help="issue a name into a declared, free plaza")
    i.add_argument("--name", required=True)
    i.add_argument("--colegiado", required=True)
    i.add_argument("--role", required=True)
    i.add_argument("--epic", required=True)
    i.add_argument("--persona", default="", help=f"max {PERSONA_MAX} chars")
    i.add_argument("--by", default=hc.agent_id())

    r = sub.add_parser("roster", help="show colegiados, plazas and issued names")
    r.add_argument("--epic")
    r.add_argument("--json", action="store_true")

    e = sub.add_parser("eligible", help="REPORT the colegiado partition for a record")
    e.add_argument("--record", required=True)
    e.add_argument("--json", action="store_true")

    a = ap.parse_args(argv)
    try:
        if a.cmd == "charter":
            print(json.dumps(charter(a.colegiado, a.incentive, a.by), indent=2))
        elif a.cmd == "plazas":
            print(json.dumps(plazas(a.epic, a.colegiado, a.role, a.count, a.by), indent=2))
        elif a.cmd == "issue":
            print(json.dumps(issue(a.name, a.colegiado, a.role, a.epic, a.by,
                                   a.persona), indent=2))
        elif a.cmd == "roster":
            data = load()
            print(json.dumps(data, indent=2, ensure_ascii=False) if a.json
                  else _render_roster(data, a.epic) or "", end="")
        elif a.cmd == "eligible":
            out = eligible_report(a.record)
            if a.json:
                print(json.dumps(out, indent=2))
            else:
                print(f"record {out['record']} · autor {out['author']} · "
                      f"colegiado {out['author_colegiado']}")
                print(f"  mismo colegiado (quedaria excluido): "
                      f"{', '.join(out['same_colegiado_would_be_excluded']) or '-'}")
                print(f"  otro colegiado (quedaria elegible):  "
                      f"{', '.join(out['other_colegiado_would_be_eligible']) or '-'}")
                if out["undecidable_author_not_issued"]:
                    print(f"  INDECIDIBLE: el autor no tiene nombre emitido")
                print(f"  {out['IS_NOT_A_GATE']}")
    except (KeyError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
