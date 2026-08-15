#!/usr/bin/env python3
"""roster.py - a bookkeeping roll of issued names and published plazas.

WHAT THIS IS, STATED AFTER AN ADVERSARIAL PANEL TOOK THE FIRST VERSION APART. This is a
ROLL, not a gate, and its integrity claim is against ACCIDENT ONLY:

  - it prevents a name being issued twice,
  - it prevents a plaza being over-filled,
  - it prevents two concurrent writers silently losing each other's entries,
  - it prevents a typo minting a parallel seat (`judge` vs `judge ` vs `Judge`).

IT DOES NOT PREVENT AN ADVERSARY, and the first version of this file implied otherwise.
The panel demonstrated three attacks against it: a trailing space in `--role` minted a
fresh seat, `charter` silently overwrote a rival's declared incentive, and a self-issued
charter plus `--count 500` minted five hundred plazas. The first two are fixed below and
the third is bounded by PLAZA_MAX. None of the three is CLOSED, because `--by` defaults
to `hc.agent_id()`, which reads an environment variable: every authorization check in
this file is a string comparison an attacker controls both sides of.

That is exactly PR-023's holding (tier 1, active, computed force `binding`), clause 4:
"Sybil minting is closed by this gate and by nothing else: nothing else closes it, do not
pretend otherwise." An appeal seeking to narrow that scope was drafted at operator
instruction and REFUSED by an adversarial panel on 2026-08-15; the draft and the refusal
are on record in `.harness/appeal-PR-023.md`. Seat scarcity is not a substitute for the
gate. This module is bookkeeping until an authenticated identity exists, and says so
rather than implying a guarantee it cannot deliver.

WHY `eligible` IS A REPORT. Replacing spawn-lineage with colegiado membership as the
basis for recusal would be a better substrate - one field on a record that already stores
`published_by`, leaving PRECEDENT.md section 14's refusal of session infrastructure
untouched. But changing what F6 computes from is a constitutional act, and PR-017
requires the amending record before the text lands. `eligible` prints the partition and
says in its own output that it decides nothing.

NO CONSEQUENCE ATTACHES. Nothing here varies a burden, a weight, a discount, a quorum or
a permission by standing. PR-022 clause 4 ("NO CONSEQUENCE ATTACHES. NONE") and PR-026
clause 5 forbid it at tier 1. `.harness/tests/test_roster.py` asserts that no exported
callable takes a threshold, gate, weight, burden or permission parameter. That test is a
real file with a real assertion: the previous version of this docstring cited it while it
did not exist, which the panel found and which is repaired here.

ROOT OVERRIDE, mirroring `precedent.py`'s V1-48 convention: `--root` beats `ROSTER_ROOT`
beats the live `.harness/`. Under an overridden root the roll, the guard and the event
sidecar all live inside that root, so no test can touch live state.

FOOTPRINT, per the operator's constraint: one flat JSON file, three collections, a
persona capped at PERSONA_MAX characters, no history. The event log carries the trail.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness_common as hc  # noqa: E402

DEFAULT_ROOT = hc.HARNESS
PRECEDENTS_SUBDIR = "precedents"
ROSTER_NAME = "roster.json"

PERSONA_MAX = 240
PLAZA_MAX = 64          # a bound on accident, not on an adversary; see docstring
SCHEMA_VERSION = 1

PUBLIC_API = ("resolve_root", "load", "charter", "plazas", "issue",
              "eligible_report", "norm")


# ------------------------------------------------------------------ root resolution

def resolve_root(flag: str | None = None) -> pathlib.Path:
    """--root flag wins over ROSTER_ROOT env; default is the live `.harness/`."""
    if flag:
        return pathlib.Path(flag).expanduser().resolve()
    env = os.environ.get("ROSTER_ROOT")
    if env:
        return pathlib.Path(env).expanduser().resolve()
    return DEFAULT_ROOT


def is_live_root(root) -> bool:
    try:
        return pathlib.Path(root).resolve() == DEFAULT_ROOT.resolve()
    except OSError:
        return False


def _roster_path(root) -> pathlib.Path:
    return pathlib.Path(root) / ROSTER_NAME


def _emit(root, kind: str, **fields) -> None:
    """Live root -> the live events.jsonl via hc.log_event, byte-identical to before.
    Overridden root -> the same record shape in `<root>/events.jsonl`. Same routing
    rule as `precedent.py:emit_event`, for the same reason."""
    if is_live_root(root):
        hc.log_event(kind, **fields)
        return
    record = {"ts": hc.now_iso(), "event": kind, "agent": hc.agent_id()}
    record.update(fields)
    hc.append_jsonl(pathlib.Path(root) / "events.jsonl", record)


class _guard:
    """Serialize read-modify-write on the roll.

    Live root delegates to `hc.guarded()` verbatim, so roster writes serialize against
    every other harness tool on the same `.harness/locks/.guard` flock. An overridden
    root gets its own guard file inside that root. NEVER nested, per the harness_common
    warning that a flock on a second file handle would deadlock.
    """

    def __init__(self, root):
        self._root = root
        self._inner = None
        self._fh = None

    def __enter__(self):
        if is_live_root(self._root):
            self._inner = hc.guarded()
            self._inner.__enter__()
        else:
            path = pathlib.Path(self._root) / "locks" / ".guard"
            path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(path, "a+")
            fcntl.flock(self._fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if self._inner is not None:
            return self._inner.__exit__(*exc)
        fcntl.flock(self._fh, fcntl.LOCK_UN)
        self._fh.close()
        return False


# ------------------------------------------------------------------- normalisation

def norm(token: str) -> str:
    """Canonical form of an identifier.

    Case-folded and whitespace-collapsed, so `judge`, `Judge` and `judge ` are ONE
    identifier rather than three parallel seats. The panel minted a seat with a trailing
    space against the previous version; this is the repair.
    """
    token = " ".join(str(token).split()).casefold()
    if not token:
        raise ValueError("identifier is empty after normalisation")
    if "/" in token:
        raise ValueError("identifiers may not contain '/': it separates colegiado/role")
    return token


def _empty() -> dict:
    return {"schema_version": SCHEMA_VERSION, "colegiados": {}, "plazas": {}, "names": {}}


def load(root=None) -> dict:
    root = resolve_root() if root is None else pathlib.Path(root)
    data = hc.read_json(_roster_path(root), default=None)
    if not isinstance(data, dict):
        return _empty()
    for key in ("colegiados", "plazas", "names"):
        data.setdefault(key, {})
    data.setdefault("schema_version", SCHEMA_VERSION)
    return data


# --------------------------------------------------------------------------- charter

def charter(colegiado: str, incentive: str, by: str, root=None) -> dict:
    """Declare a colegiado and, in its own words, what it is paid for.

    Refuses to overwrite a charter declared by a DIFFERENT author. That refusal is a
    guard against accident, not against an adversary: `by` is self-asserted, so anyone
    willing to type the original author's name still gets through.
    """
    root = resolve_root() if root is None else pathlib.Path(root)
    colegiado = norm(colegiado)
    incentive = str(incentive).strip()
    if not incentive:
        raise ValueError("a colegiado must declare what it is paid for")
    with _guard(root):
        data = load(root)
        prior = data["colegiados"].get(colegiado)
        if prior is not None and prior.get("declared_by") != by:
            raise KeyError(
                f"colegiado {colegiado!r} was chartered by {prior.get('declared_by')!r}; "
                f"{by!r} may not redeclare it")
        data["colegiados"][colegiado] = {
            "incentive": incentive,
            "declared_by": by,
            "declared_at": hc.now_iso(),
        }
        hc.atomic_write_json(_roster_path(root), data)
        entry = data["colegiados"][colegiado]
    _emit(root, "roster_charter", colegiado=colegiado, agent=by,
          amended=prior is not None)
    return entry


# ---------------------------------------------------------------------------- plazas

def plazas(epic: str, colegiado: str, role: str, count: int, by: str, root=None) -> dict:
    """Publish N seats for an epic BEFORE any of them is filled.

    Publication-before-filling is the property that matters: a seat count announced after
    the agents exist is a description; announced before, it is a constraint.
    """
    root = resolve_root() if root is None else pathlib.Path(root)
    epic, colegiado, role = norm(epic), norm(colegiado), norm(role)
    if not isinstance(count, int) or isinstance(count, bool):
        raise ValueError("count must be an integer")
    if not 1 <= count <= PLAZA_MAX:
        raise ValueError(f"count must be between 1 and {PLAZA_MAX}")
    key = f"{colegiado}/{role}"
    with _guard(root):
        data = load(root)
        if colegiado not in data["colegiados"]:
            raise KeyError(f"colegiado {colegiado!r} has no charter; declare it first")
        bucket = data["plazas"].setdefault(epic, {})
        if key in bucket:
            raise KeyError(f"plazas for {key} in {epic} already published; "
                           "republishing after the fact would defeat the point")
        bucket[key] = {"count": count, "declared_by": by, "declared_at": hc.now_iso()}
        hc.atomic_write_json(_roster_path(root), data)
        entry = bucket[key]
    _emit(root, "roster_plazas", epic=epic, colegiado=colegiado, role=role,
          count=count, agent=by)
    return entry


def _filled(data: dict, epic: str, key: str) -> int:
    return sum(1 for n in data["names"].values()
               if n["epic"] == epic and f"{n['colegiado']}/{n['role']}" == key)


# ----------------------------------------------------------------------------- issue

def issue(name: str, colegiado: str, role: str, epic: str, by: str,
          persona: str = "", root=None) -> dict:
    """Issue a name into a declared, still-free plaza. Refuses otherwise.

    The whole read-check-write runs inside ONE guard. The previous version ran it inside
    none, and the panel measured 4 silent lost writes out of 5 concurrent issuances into
    a 5-seat plaza, each of which had logged a success event for a row that never reached
    the roll. That is the defect this guard exists to close.
    """
    root = resolve_root() if root is None else pathlib.Path(root)
    name, colegiado, role, epic = norm(name), norm(colegiado), norm(role), norm(epic)
    persona = str(persona).strip()
    if len(persona) > PERSONA_MAX:
        raise ValueError(f"persona exceeds {PERSONA_MAX} chars; the operator's "
                         "constraint is that this stays small")
    key = f"{colegiado}/{role}"
    with _guard(root):
        data = load(root)
        if name in data["names"]:
            raise KeyError(f"name {name!r} is already issued; names are not reused")
        if colegiado not in data["colegiados"]:
            raise KeyError(f"colegiado {colegiado!r} has no charter")
        seat = data["plazas"].get(epic, {}).get(key)
        if seat is None:
            raise KeyError(f"no plazas published for {key} in {epic}")
        used = _filled(data, epic, key)
        if used >= seat["count"]:
            raise KeyError(f"all {seat['count']} plazas for {key} in {epic} are filled")
        data["names"][name] = {
            "colegiado": colegiado, "role": role, "epic": epic,
            "persona": persona, "issued_by": by, "issued_at": hc.now_iso(),
        }
        hc.atomic_write_json(_roster_path(root), data)
        entry = data["names"][name]
        seated = f"{used + 1}/{seat['count']}"
    _emit(root, "roster_issue", name=name, colegiado=colegiado, role=role,
          epic=epic, agent=by, seat=seated)
    return entry


# ------------------------------------------------------------------- eligible REPORT

def eligible_report(record_id: str, root=None) -> dict:
    """REPORT, never a gate. See module docstring and PR-017."""
    root = resolve_root() if root is None else pathlib.Path(root)
    rec = hc.read_json(pathlib.Path(root) / PRECEDENTS_SUBDIR / f"{record_id}.json",
                       default=None)
    if rec is None:
        raise KeyError(f"no record {record_id}")
    author = rec.get("published_by")
    data = load(root)
    entry = data["names"].get(norm(author)) if author else None
    same, other, undecidable = [], [], []
    for n, v in data["names"].items():
        if entry is not None and n == norm(author):
            continue
        if entry is None:
            undecidable.append(n)
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
        "undecidable_author_not_issued": sorted(undecidable),
        "IS_NOT_A_GATE": "advisory only; F6 is not computed from this field until an "
                         "amending record is published (PR-017)",
    }


# ------------------------------------------------------------------------------- cli

def _render_roster(data: dict, epic) -> None:
    want = norm(epic) if epic else None
    print("COLEGIADOS")
    if not data["colegiados"]:
        print("  (ninguno declarado)")
    for c, v in sorted(data["colegiados"].items()):
        print(f"  {c:22s} paga por: {v['incentive']}")
    print("\nPLAZAS  (publicadas antes de llenarse)")
    shown = False
    for e, bucket in sorted(data["plazas"].items()):
        if want and e != want:
            continue
        for key, seat in sorted(bucket.items()):
            shown = True
            print(f"  {e:18s} {key:28s} {_filled(data, e, key)}/{seat['count']}")
    if not shown:
        print("  (ninguna publicada)")
    print("\nNOMBRES EMITIDOS")
    rows = [(n, v) for n, v in sorted(data["names"].items())
            if not want or v["epic"] == want]
    if not rows:
        print("  (ninguno)")
    for n, v in rows:
        print(f"  {n:22s} {v['colegiado']}/{v['role']:12s} {v['epic']}")
        if v["persona"]:
            print(f"    {v['persona']}")
    print("\nEste padron es contabilidad, no compuerta: la identidad sigue siendo")
    print("autoafirmada y PR-023 sigue vigente. Ver el docstring del modulo.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="roster.py - roll of issued names and published plazas. "
                    "Integrity against accident only; PR-023 still holds.")
    ap.add_argument("--root", help="override the harness root (else ROSTER_ROOT env, "
                                   "else the live .harness/)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("charter", help="declare a colegiado and what it is paid for")
    c.add_argument("--colegiado", required=True)
    c.add_argument("--incentive", required=True)
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
    root = resolve_root(a.root)
    try:
        if a.cmd == "charter":
            print(json.dumps(charter(a.colegiado, a.incentive, a.by, root),
                             indent=2, ensure_ascii=False))
        elif a.cmd == "plazas":
            print(json.dumps(plazas(a.epic, a.colegiado, a.role, a.count, a.by, root),
                             indent=2, ensure_ascii=False))
        elif a.cmd == "issue":
            print(json.dumps(issue(a.name, a.colegiado, a.role, a.epic, a.by,
                                   a.persona, root), indent=2, ensure_ascii=False))
        elif a.cmd == "roster":
            data = load(root)
            if a.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                _render_roster(data, a.epic)
        elif a.cmd == "eligible":
            out = eligible_report(a.record, root)
            if a.json:
                print(json.dumps(out, indent=2, ensure_ascii=False))
            else:
                print(f"record {out['record']} - autor {out['author']} - "
                      f"colegiado {out['author_colegiado']}")
                print(f"  mismo colegiado (quedaria excluido): "
                      f"{', '.join(out['same_colegiado_would_be_excluded']) or '-'}")
                print(f"  otro colegiado (quedaria elegible):  "
                      f"{', '.join(out['other_colegiado_would_be_eligible']) or '-'}")
                if out["undecidable_author_not_issued"]:
                    print("  INDECIDIBLE: el autor no tiene nombre emitido")
                print(f"  {out['IS_NOT_A_GATE']}")
    except (KeyError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
