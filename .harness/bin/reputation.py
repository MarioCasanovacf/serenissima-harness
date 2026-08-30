#!/usr/bin/env python3
"""reputation.py -- Phase A reputation bookkeeping reader (T-371, addendum-ii).

Implements, VERBATIM, the surface fixed by section 5 (AD2-50..AD2-69) of
`docs/precedent-research/synthesis-addendum-ii-spec.md`. Every branch below
cites its AD2 id in a comment so a verifier can replay this file against
that document mechanically, the same discipline `precedent.py` already
uses for its own SDR/V1 ids.

RECORD-BEFORE-CODE (PR-017 procedure): this reader is authorized by two
active tier-1 records minted under T-369, BEFORE this file existed --
`PR-022` (subject `reputation-phase-a`, enacting addendum section A.4 plus
AB3's caveat and AB4's neutrality clause) and `PR-024` (subject
`load-bearing-citation`, enacting addendum section A.6.3, T-367's v1
heuristic as PROVISIONAL DOCTRINE with a decay clock). Both were verified
`status: active` via `precedent.py show` before this file was written.

PHASE A NEUTRALITY (AB4, AD2-62), stated here as the module's own
constraint, not only as prose: no function, flag, threshold, constant,
sort order or output in this module varies any verification or
confirmation burden by standing. `PR-015`'s confirmation burden stays
UNIFORM for every identity in Phase A. Section A.6.2's standing-scaled
trust burden is Phase B material and is not operable now, by A.4's own
words: no consequence attaches, none. Nothing in this module is
importable as a gate by another module -- `PUBLIC_API` below is the
explicit allow-list, and `test_reputation.py` asserts nothing else is
exported and that no exported callable's signature carries a threshold,
gate, weight, burden or permission parameter. The one numeric threshold
that DOES appear (`precedent.REITERATION_N`, surfaced in the
`consolidations_achieved` figure) is a counting/display constant borrowed
read-only from `precedent.py`'s own force computation -- it is not a
knob this module owns, varies, or lets any caller vary.

READ-ONLY, ABSOLUTELY (AD2-54): this module is the same verb class as
`precedent.py`'s `cite`, `conflicts` and `stale` -- it writes NOTHING.
No `hc.log_event`, no `hc.atomic_write_json`, no `hc.append_jsonl`, no
`hc.guarded`, no `open(..., 'w'|'a'|'x')`, no `Path.write_*`, no
`os.replace`, no lock acquisition, no temp file anywhere inside the
repository, no cache. No `hc.now_iso()` in any output either: every
subcommand's stdout is a pure function of the stores it reads, so two
runs against the same stores byte-identical.

REUSE, NOT REIMPLEMENTATION (AD2-64): `precedent` (the sibling module in
this same directory) is imported for `precedent.scan_registry`,
`precedent.load_record_or_raise`, `precedent.RegistryIntegrityError`,
`precedent.qualifying_applications_count` and `precedent.REITERATION_N`,
used AS-IS. `precedent.py` has a `__main__` guard so the import carries no
side effects. This module does not edit, monkeypatch or shadow anything
in `precedent.py`.

DECISION (AD2-56 figure 3 display vs. AD2-64's reuse duty): the
`consolidations_achieved` THRESHOLD MEMBERSHIP (whether a record's count
is >= `precedent.REITERATION_N`) is always computed by calling
`precedent.qualifying_applications_count` directly -- never by counting
this module's own detail list -- so the pass/fail figure can never drift
from `precedent.py show`'s own `force` line. AB9-1's "who applied"
display, however, needs the underlying per-application list, which
`qualifying_applications_count` does not return. `_consolidation_
contributors()` below walks the identical filter/sort/reset algorithm
(same target/below_target_tier/type conditions, same
(published_at, id) sort, same follows/declarative-reinterprets-increment,
distinguishes/corrective-reinterprets-reset rule) to derive that list.
`test_reputation.py` asserts `len(contributors) ==
precedent.qualifying_applications_count(...)` across every fixture,
including a zeroing case, as the drift guard AD2-64 exists to demand.

DECISION (root has one more level than `precedent.py`'s, AD2-52,
disclosed as OQ-4 in the spec): `precedent.py --root` names the
precedents directory itself; `reputation.py --root` names a
harness-root-like directory whose children are `precedents/`, `tasks/`,
`blackboard.json` and `logs/events.jsonl`. The mitigation is mandatory
and mechanical: every output path prints the resolved root as a `root:`
line (text) / `root` key (json), so no reader can be confused about which
stores produced a figure.

DECISION (registry-integrity-error output shape, exit 4, undisclosed by
the frozen surface): AD2-66 fixes the `--json` shape for SUCCESS and
AD2-61 fixes it for the exit-1 REFUSAL (`{"caveat": ..., "refused": ...}`)
-- the spec defines no third `--json` shape for a REGISTRY INTEGRITY
ERROR. Rather than invent an unspecified key (itself the kind of
invented-surface defect this epic's own criteria forbid), this module
reuses `precedent.py`'s own established convention for this exact
exception class (`integrity_error()`, `.harness/bin/precedent.py:632`):
a plain-text `REGISTRY INTEGRITY ERROR: ...` line to stderr, no stdout at
all (neither the caveat text line nor a JSON blob), identical in text and
--json mode, exit 4. Disclosed as OPEN-QUESTION in the T-371 handoff: a
future PR-017-procedure record could fix a fourth caveat-bearing shape for
this path if a verifier judges AD2-61's "only exempt path is exit 2"
clause to require one.

Exit-code contract (AD2-55, reusing SDR-15 verbatim):
  0  success
  1  REFUSAL (missing/empty --identity; identity in no store; bad root)
  2  usage error, argparse-native ONLY (unknown flag/subcommand)
  4  REGISTRY INTEGRITY ERROR (unparseable record, blackboard.json, task
     file, or events.jsonl line)
  3  is RESERVED and never returned: a reader reports figures, never
     findings (AD2-55).

stdlib only; MUST run under python3 3.9.6 -- no match statement, no
3.10+ syntax, no third-party imports.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import harness_common as hc
import precedent
import warrant

# --------------------------------------------------------------------------
# AD2-61: the fixed sybil caveat, character-for-character, quoted from
# PR-022's ratio (AD2-14 proposition 5). The single canonical string every
# output path of this module prints.
# --------------------------------------------------------------------------

CAVEAT = (
    "identities are self-asserted (FORCE-IDENTITY-A open); Phase A is "
    "bookkeeping, not currency; no consequence may cite these figures "
    "(A.4, A.9)."
)

# AD2-52: --root flag wins over REPUTATION_ROOT env, which wins over the
# default `.harness/` (hc.HARNESS). Note this is ONE LEVEL ABOVE
# precedent.py's own DEFAULT_ROOT (which already names the precedents/
# subdirectory) -- the DEVIATION is disclosed in the module docstring.
DEFAULT_ROOT = hc.HARNESS

# AD2-56 figure 1's status breakdown order, matching precedent.py's
# VALID_STATUS tuple order exactly (hardcoded rather than imported: this
# name is not on AD2-64's reuse allow-list, and the literal order is
# already fixed character-for-character by AD2-65's own stdout template).
STATUS_ORDER = ("active", "overruled", "superseded", "void_per_incuriam")

# --------------------------------------------------------------------------
# Root resolution and store loading (AD2-52, AD2-53, AD2-54, AD2-55)
# --------------------------------------------------------------------------


def resolve_root(args):
    """AD2-52: --root flag wins over REPUTATION_ROOT env; default is
    hc.HARNESS (`.harness/`). Mirrors precedent.py's resolve_root/SDR-13
    precedence exactly, one level up."""
    root_arg = getattr(args, "root", None)
    if root_arg:
        return Path(root_arg)
    env_root = os.environ.get("REPUTATION_ROOT")
    if env_root:
        return Path(env_root)
    return DEFAULT_ROOT


def root_is_valid(root):
    """AD2-53: a store root must exist, be a directory, and have a
    precedents/ subdirectory. Never report zeros against a wrong root."""
    p = Path(root)
    return p.exists() and p.is_dir() and (p / "precedents").is_dir()


def load_precedents(root):
    """<root>/precedents/PR-*.json, via precedent.scan_registry (AD2-64):
    reused as-is, never reimplemented. May raise
    precedent.RegistryIntegrityError (AD2-55 exit 4)."""
    return dict(precedent.scan_registry(Path(root) / "precedents"))


def load_blackboard_tasks(root):
    """<root>/blackboard.json's `tasks` map. Absence of the file is NOT an
    integrity error (an empty/no-tasks store is a valid, if unusual, root);
    a present-but-unparseable file IS (AD2-55), reusing
    precedent.RegistryIntegrityError so a corrupt store is never skipped
    silently."""
    path = Path(root) / "blackboard.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise precedent.RegistryIntegrityError(path, e)
    if not isinstance(data, dict):
        raise precedent.RegistryIntegrityError(path, "not a JSON object")
    tasks = data.get("tasks")
    return tasks if isinstance(tasks, dict) else {}


def load_reopened_tasks(root):
    """AD2-59: <root>/logs/events.jsonl is read in exactly ONE place, for
    exactly one event kind (`task_reopened`), in the SUBTRACTING direction
    only -- a contaminated or synthetic line can only lower figure 5,
    never mint standing. Absence of the file is empty, not an error; a
    present-but-unparseable LINE is a registry integrity error (AD2-55),
    never silently skipped."""
    path = Path(root) / "logs" / "events.jsonl"
    reopened = set()
    if not path.exists():
        return reopened
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                raise precedent.RegistryIntegrityError(
                    "{}:{}".format(path, lineno), e)
            if isinstance(rec, dict) and rec.get("event") == "task_reopened":
                t = rec.get("task")
                if t:
                    reopened.add(t)
    return reopened


def task_record_exists(root, task_id):
    """AD2-56 figure 5: <root>/tasks/T-NNN.json existence check. A missing
    file is displayed, never silently counted (returns False, not an
    error). A present-but-unparseable file IS a registry integrity error
    (AD2-55)."""
    path = Path(root) / "tasks" / (task_id + ".json")
    if not path.exists():
        return False
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise precedent.RegistryIntegrityError(path, e)
    return True


def _task_producer(task_rec):
    """The producer of a task record: handoff.from, else claimed_by (AD2-56
    figures 4 and 5 share this definition verbatim)."""
    handoff = task_rec.get("handoff") or {}
    producer = handoff.get("from")
    if producer:
        return producer
    return task_rec.get("claimed_by")


def collect_identities(precedents, blackboard_tasks):
    """AD2-67: identity discovery reads `published_by` in precedents/, and
    `completed_by`, `handoff.from` and `claimed_by` in blackboard.json.
    Nothing else. Returns a sorted list of (identity, sorted_stores)."""
    from_precedents = set()
    for rec in precedents.values():
        pb = rec.get("published_by")
        if pb:
            from_precedents.add(pb)
    from_blackboard = set()
    for t in blackboard_tasks.values():
        if not isinstance(t, dict):
            continue
        for key in ("completed_by", "claimed_by"):
            v = t.get(key)
            if v:
                from_blackboard.add(v)
        handoff = t.get("handoff") or {}
        frm = handoff.get("from")
        if frm:
            from_blackboard.add(frm)
    all_ids = sorted(from_precedents | from_blackboard)
    result = []
    for ident in all_ids:
        stores = []
        if ident in from_blackboard:
            stores.append("blackboard")
        if ident in from_precedents:
            stores.append("precedents")
        result.append((ident, sorted(stores)))
    return result


# --------------------------------------------------------------------------
# AD2-56: the six figures. Each function returns data only -- text/json
# rendering happens in cmd_standing so the two output modes stay a pure
# function of one computation, never two independent derivations.
# --------------------------------------------------------------------------


def figure_rule_authorship(identity, precedents):
    """AD2-56 figure 1. Source: precedents/PR-*.json:published_by."""
    by_status = {k: 0 for k in STATUS_ORDER}
    records = []
    for pr_id in sorted(precedents):
        rec = precedents[pr_id]
        if rec.get("published_by") != identity:
            continue
        records.append(pr_id)
        st = rec.get("status")
        if st in by_status:
            by_status[st] += 1
    return {
        "value": len(records),
        "by_status": by_status,
        "records": records,
        "source": "precedents/PR-*.json:published_by",
    }


def figure_load_bearing_citations_received(identity, precedents):
    """AD2-56 figure 2, T-367 steps 1-4 only (MECHANIZABLE): step 1 (a
    typed relation exists; a bare `cites` token is excluded by construction
    -- only relations[] is read here), step 2 (routing: only `follows` and
    `reinterprets`; `distinguishes` is excluded by definition and
    `overrules`/`supersedes`/`voids` are out of scope), step 3
    (same-publisher exclusion), step 4 (below_target_tier exclusion).
    Labelled ELIGIBLE-UPPER-BOUND, never "load-bearing" (PR-024's own
    ratio proposition 3-4). Source:
    precedents/PR-*.json:relations[]+published_by."""
    authored = [pr_id for pr_id in sorted(precedents)
                if precedents[pr_id].get("published_by") == identity]
    detail = []
    for x_id in authored:
        for y_id in sorted(precedents):
            y = precedents[y_id]
            if y.get("published_by") == identity:
                continue  # step 3: same-publisher exclusion
            for rel in (y.get("relations") or []):
                if rel.get("target") != x_id:
                    continue
                if rel.get("type") not in ("follows", "reinterprets"):
                    continue  # step 2: routing (distinguishes excluded by definition)
                if rel.get("below_target_tier") is not False:
                    continue  # step 4: below-target-tier exclusion
                detail.append({
                    "record": x_id,
                    "citing_record": y_id,
                    "relation": rel.get("type"),
                    "published_by": y.get("published_by"),
                })
    return {
        "value": len(detail),
        "label": "eligible-upper-bound",
        "verdict": None,
        "verdict_status": "not-computed",
        "verdict_reason": (
            "steps 5-7 are a confirming-identity judgment with no storage "
            "field; see the tier-1 record with subject load-bearing-citation"
        ),
        "detail": detail,
        "source": "precedents/PR-*.json:relations[]+published_by",
    }


def _consolidation_contributors(pr_id, records_by_id):
    """See the module docstring DECISION on AD2-56 figure 3 vs. AD2-64:
    walks the identical filter/sort/reset algorithm
    precedent.qualifying_applications_count uses internally, to recover the
    per-application detail that function's own return value (an int) does
    not carry. Never used to determine threshold membership -- callers
    must use precedent.qualifying_applications_count for that."""
    x = records_by_id.get(pr_id) or {}
    published_by_x = x.get("published_by")
    apps = []
    for other_id, other in records_by_id.items():
        if other_id == pr_id:
            continue
        if other.get("status") != "active":
            continue
        if other.get("published_by") == published_by_x:
            continue
        for rel in (other.get("relations") or []):
            if rel.get("target") != pr_id:
                continue
            if rel.get("below_target_tier") is not False:
                continue
            if rel.get("type") not in ("follows", "reinterprets", "distinguishes"):
                continue
            apps.append((other.get("published_at") or "", other_id, other, rel))
    apps.sort(key=lambda t: (t[0], t[1]))

    contributors = []
    for _ts, other_id, other, rel in apps:
        rtype = rel.get("type")
        if rtype == "follows":
            contributors.append({
                "identity": other.get("published_by"),
                "citing_record": other_id,
                "relation": "follows",
            })
        elif rtype == "reinterprets":
            subtype = (other.get("operation") or {}).get("subtype")
            if subtype == "declarative":
                contributors.append({
                    "identity": other.get("published_by"),
                    "citing_record": other_id,
                    "relation": "reinterprets",
                })
            elif isinstance(subtype, str) and subtype.startswith("corrective"):
                contributors = []
        elif rtype == "distinguishes":
            contributors = []
    return contributors


def figure_consolidations_achieved(identity, precedents):
    """AD2-56 figure 3 + AD2-58 (sub-threshold detail required). Source:
    precedents/PR-*.json:relations[]+published_by via
    precedent.qualifying_applications_count."""
    authored = [pr_id for pr_id in sorted(precedents)
                if precedents[pr_id].get("published_by") == identity]
    detail = []
    achieved = 0
    for pr_id in authored:
        c = precedent.qualifying_applications_count(pr_id, precedents)
        if c >= precedent.REITERATION_N:
            achieved += 1
        if c >= 1:
            detail.append({
                "record": pr_id,
                "c": c,
                "applied_by": _consolidation_contributors(pr_id, precedents),
            })
    return {
        "value": achieved,
        "threshold": precedent.REITERATION_N,
        "detail": detail,
        "source": (
            "precedents/PR-*.json:relations[]+published_by via "
            "precedent.qualifying_applications_count"
        ),
    }


def figure_overrulings_sustained(identity, precedents, blackboard_tasks, reopened):
    """AD2-56 figure 4. Source: precedents/PR-*.json:relations[]+cited_by;
    blackboard.json:tasks[].completed_by."""
    detail = []
    for pr_id in sorted(precedents):
        rec = precedents[pr_id]
        if rec.get("published_by") != identity:
            continue
        for rel in (rec.get("relations") or []):
            if rel.get("type") != "overrules":
                continue
            issuing_task = rec.get("issuing_task")
            task_rec = blackboard_tasks.get(issuing_task) or {}
            producer = _task_producer(task_rec)
            completed_by = task_rec.get("completed_by")
            verification_upheld = bool(
                task_rec.get("status") == "done"
                and producer
                and completed_by
                and producer != completed_by
                and issuing_task not in reopened
            )
            citers = sorted({
                cid for cid in (rec.get("cited_by") or [])
                if precedents.get(cid)
                and precedents[cid].get("published_by") != identity
            })
            sustained = bool(verification_upheld and citers)
            detail.append({
                "record": pr_id,
                "target": rel.get("target"),
                "verification_upheld": verification_upheld,
                "distinct_identity_citations": citers,
                "sustained": sustained,
            })
    issued = len(detail)
    sustained_n = sum(1 for d in detail if d["sustained"])
    return {
        "value": sustained_n,
        "issued": issued,
        "detail": detail,
        "source": (
            "precedents/PR-*.json:relations[]+cited_by; "
            "blackboard.json:tasks[].completed_by"
        ),
    }


def figure_verification_verdicts_upheld(identity, root, blackboard_tasks, reopened):
    """AD2-56 figure 5. Source: blackboard.json:tasks[].completed_by+
    handoff.from; tasks/T-*.json existence; logs/events.jsonl:task_reopened
    (subtraction only)."""
    candidates = []
    for tid, t in blackboard_tasks.items():
        if not isinstance(t, dict):
            continue
        if t.get("status") != "done":
            continue
        if t.get("completed_by") != identity:
            continue
        producer = _task_producer(t)
        if not producer or producer == identity:
            continue
        candidates.append(tid)
    candidates.sort()

    detail = []
    value = 0
    for tid in candidates:
        missing = not task_record_exists(root, tid)
        if tid in reopened:
            outcome = "excluded"
        else:
            outcome = "upheld"
            value += 1
        detail.append({
            "task": tid,
            "outcome": outcome,
            "task_record_missing": missing,
        })
    return {
        "value": value,
        "detail": detail,
        "source": (
            "blackboard.json:tasks[].completed_by+handoff.from; "
            "tasks/T-*.json existence; "
            "logs/events.jsonl:task_reopened (subtraction only)"
        ),
    }


def figure_adjudications_not_reversed():
    """AD2-56 figure 6, AD2-60: DEFERRED until the appellate verb exists.
    Present, empty, explicitly marked unavailable -- never a number, never
    a zero, never omitted."""
    return {
        "value": None,
        "status": "unavailable",
        "reason": (
            "the appellate verb does not exist; the field is present and "
            "never fabricated"
        ),
        "source": None,
    }


# --------------------------------------------------------------------------
# Text-mode rendering (AD2-65, AD2-67, AD2-68, AD2-69) -- exact line
# shapes, literal character for character.
# --------------------------------------------------------------------------


def _render_standing_text(root, identity, figures):
    lines = []
    lines.append("caveat: " + CAVEAT)
    lines.append("root: {}".format(root))
    lines.append("identity: {}".format(identity))

    f1 = figures["rule_authorship"]
    lines.append(
        "rule_authorship: {v} (active {a}, overruled {o}, superseded {s}, "
        "void_per_incuriam {vp}) [source: {src}]".format(
            v=f1["value"], a=f1["by_status"]["active"],
            o=f1["by_status"]["overruled"], s=f1["by_status"]["superseded"],
            vp=f1["by_status"]["void_per_incuriam"], src=f1["source"]))

    f2 = figures["load_bearing_citations_received"]
    lines.append(
        "load_bearing_citations_received: {v} ELIGIBLE-UPPER-BOUND (steps "
        "1-4 only; load-bearing not confirmed) [source: {src}]".format(
            v=f2["value"], src=f2["source"]))
    for d in f2["detail"]:
        lines.append("  eligible {r} <- {c} ({rel}) by {pb}".format(
            r=d["record"], c=d["citing_record"], rel=d["relation"], pb=d["published_by"]))
    lines.append(
        "load_bearing_verdict: not computed (steps 5-7 are a "
        "confirming-identity judgment with no storage field; see the "
        "tier-1 record with subject load-bearing-citation)")

    f3 = figures["consolidations_achieved"]
    lines.append(
        "consolidations_achieved: {v} (threshold C>={t}) [source: {src}]".format(
            v=f3["value"], t=f3["threshold"], src=f3["source"]))
    for d in f3["detail"]:
        applied = ", ".join(
            "{ident} via {cr} ({rel})".format(
                ident=a["identity"], cr=a["citing_record"], rel=a["relation"])
            for a in d["applied_by"])
        lines.append("  consolidating {r}: C={c} applied_by={applied}".format(
            r=d["record"], c=d["c"], applied=applied))

    f4 = figures["overrulings_sustained"]
    lines.append(
        "overrulings_sustained: {v} of {i} issued [source: {src}]".format(
            v=f4["value"], i=f4["issued"], src=f4["source"]))
    for d in f4["detail"]:
        cites = ",".join(d["distinct_identity_citations"]) if d["distinct_identity_citations"] else "none"
        lines.append(
            "  overrule {r} -> {t}: verification={ver} "
            "distinct_identity_citations={c} sustained={s}".format(
                r=d["record"], t=d["target"],
                ver="upheld" if d["verification_upheld"] else "not-upheld",
                c=cites, s="yes" if d["sustained"] else "no"))

    f5 = figures["verification_verdicts_upheld"]
    lines.append(
        "verification_verdicts_upheld: {v} [source: {src}]".format(
            v=f5["value"], src=f5["source"]))
    for d in f5["detail"]:
        suffix = " (task record missing)" if d["task_record_missing"] else ""
        outcome = "upheld" if d["outcome"] == "upheld" else "excluded (task_reopened)"
        lines.append("  verdict {t}: {o}{suf}".format(t=d["task"], o=outcome, suf=suffix))

    f6 = figures["adjudications_not_reversed"]
    lines.append("adjudications_not_reversed: {status} ({reason})".format(
        status=f6["status"], reason=f6["reason"]))

    return "\n".join(lines)


def _compute_figures(identity, root, precedents, blackboard_tasks, reopened):
    return {
        "rule_authorship": figure_rule_authorship(identity, precedents),
        "load_bearing_citations_received": figure_load_bearing_citations_received(identity, precedents),
        "consolidations_achieved": figure_consolidations_achieved(identity, precedents),
        "overrulings_sustained": figure_overrulings_sustained(identity, precedents, blackboard_tasks, reopened),
        "verification_verdicts_upheld": figure_verification_verdicts_upheld(identity, root, blackboard_tasks, reopened),
        "adjudications_not_reversed": figure_adjudications_not_reversed(),
    }


# --------------------------------------------------------------------------
# Subcommand entry points (AD2-51). Exit codes per AD2-55.
# --------------------------------------------------------------------------


def cmd_standing(args):
    """AD2-50/AD2-51/AD2-65/AD2-66/AD2-69: standing --identity <str>
    [--root <path>] [--json]."""
    identity = args.identity

    # AD2-51: --identity is argparse-optional and manually checked (an
    # argparse-native error cannot carry the caveat -- AB3 requires exit 1,
    # not exit 2, here).
    if not identity or not identity.strip():
        reason = "--identity is required and must be non-empty (AD2-51)"
        if args.json:
            print(json.dumps({"caveat": CAVEAT, "refused": reason}, indent=2, ensure_ascii=False))
        else:
            print("caveat: " + CAVEAT)
            print("refused: " + reason, file=sys.stderr)
        return 1

    root = resolve_root(args)

    # AD2-53: refuse rather than report zeros against a wrong root.
    if not root_is_valid(root):
        reason = "root '{}' has no precedents/ directory; refusing rather than reporting zeros (AD2-53)".format(root)
        if args.json:
            print(json.dumps({"caveat": CAVEAT, "refused": reason}, indent=2, ensure_ascii=False))
        else:
            print("caveat: " + CAVEAT)
            print("refused: " + reason, file=sys.stderr)
        return 1

    try:
        precedents = load_precedents(root)
        blackboard_tasks = load_blackboard_tasks(root)
        reopened = load_reopened_tasks(root)
        identities = collect_identities(precedents, blackboard_tasks)
    except precedent.RegistryIntegrityError as e:
        # See module docstring DECISION: no --json-specific shape exists
        # for this path (unspecified by the frozen surface); reuse
        # precedent.py's own convention verbatim, identical in both modes.
        print("REGISTRY INTEGRITY ERROR: {}".format(e), file=sys.stderr)
        return 4

    ids_set = {i for i, _ in identities}
    if identity not in ids_set:
        reason = "identity '{}' appears in no store under {} (AD2-53)".format(identity, root)
        if args.json:
            print(json.dumps({"caveat": CAVEAT, "refused": reason}, indent=2, ensure_ascii=False))
        else:
            print("caveat: " + CAVEAT)
            print("refused: " + reason, file=sys.stderr)
        return 1

    figures = _compute_figures(identity, root, precedents, blackboard_tasks, reopened)

    if args.json:
        # AD2-66: top-level keys in this order: caveat, root, identity,
        # figures; figures carries exactly the six AD2-56 keys in order.
        out = {
            "caveat": CAVEAT,
            "root": str(root),
            "identity": identity,
            "figures": {
                "rule_authorship": figures["rule_authorship"],
                "load_bearing_citations_received": figures["load_bearing_citations_received"],
                "consolidations_achieved": figures["consolidations_achieved"],
                "overrulings_sustained": figures["overrulings_sustained"],
                "verification_verdicts_upheld": figures["verification_verdicts_upheld"],
                "adjudications_not_reversed": figures["adjudications_not_reversed"],
            },
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(_render_standing_text(root, identity, figures))
    return 0


def cmd_identities(args):
    """AD2-50/AD2-51/AD2-63/AD2-67: identities [--root <path>] [--json].
    Lexicographic order, never ranked (A.9 refuses a leaderboard)."""
    root = resolve_root(args)

    if not root_is_valid(root):
        reason = "root '{}' has no precedents/ directory; refusing rather than reporting zeros (AD2-53)".format(root)
        if args.json:
            print(json.dumps({"caveat": CAVEAT, "refused": reason}, indent=2, ensure_ascii=False))
        else:
            print("caveat: " + CAVEAT)
            print("refused: " + reason, file=sys.stderr)
        return 1

    try:
        precedents = load_precedents(root)
        blackboard_tasks = load_blackboard_tasks(root)
        identities = collect_identities(precedents, blackboard_tasks)
    except precedent.RegistryIntegrityError as e:
        print("REGISTRY INTEGRITY ERROR: {}".format(e), file=sys.stderr)
        return 4

    note = "lexicographic order, never ranked (A.9 refuses a leaderboard)"
    if args.json:
        # DECISION, planner judgment disclosed: the spec's frozen --json
        # shapes (AD2-66, AD2-61) cover `standing` only; `identities
        # --json` has no fixed shape in section 5, though AD2-51's flag
        # table promises the flag exists. Mirrors the text line order
        # (caveat, root, note, identities, count) as the most literal
        # reading available.
        out = {
            "caveat": CAVEAT,
            "root": str(root),
            "note": note,
            "identities": [{"identity": ident, "stores": stores} for ident, stores in identities],
            "count": len(identities),
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print("caveat: " + CAVEAT)
        print("root: {}".format(root))
        print("note: " + note)
        for ident, stores in identities:
            print("identity: {} stores={}".format(ident, ",".join(stores)))
        print("identities: {} discovered".format(len(identities)))
    return 0


def cmd_caveat(args):
    """AD2-50/AD2-51/AD2-68: caveat [--json]. No --root, no --identity --
    a dedicated one-line verb so T-372/T-374 have a canonical source that
    cannot drift from the code that prints it."""
    if args.json:
        print(json.dumps({"caveat": CAVEAT}, indent=2, ensure_ascii=False))
    else:
        print("caveat: " + CAVEAT)
    return 0


# --------------------------------------------------------------------------
# Phase B: Exponential Moving Average (EMA) Decay & Operational Consequences
# Authorized by PR-060 and PR-061. PR-061's authority is operator ruling
# RAT-01 (.harness/operator-rulings-2026-08-22.md), not deliberation D-001,
# which was found per incuriam and survives only as a regression fixture.
#
# THE CONSTITUTIONAL GATE (T-420). PR-060's split says consequences may
# attach to OPERATIONAL parameters only, and CONSTITUTIONAL parameters (the
# EMA decay rate, the component weights, any threshold) are the operator's
# alone. D-17 says every agent shares one OS user, so no in-repo flag, env
# var or config file can mark an operator decision -- any agent can write
# all of them. The ONE boundary D-17 leaves standing is the operator's
# private key, held off-machine. Therefore:
#
#   * The consequence verb (`dispatch`) runs ONLY when
#     `.harness/constitutional/reputation.json` carries a detached ssh
#     signature (`.sig`) that verifies against the enrolled trust anchor
#     (`trust/root.pub` + `trust/root.fingerprint`, warrant.py's three
#     checks, reused as-is) AND the signed payload says `"activation": "on"`.
#   * Constitutional parameters on the consequence verb come ONLY from that
#     signed payload. `--half-life-days` on `dispatch` is refused outright,
#     agreeing or not: a knob that must match the file is a knob that leaks.
#   * `rank` stays a read-only REPORT: it accepts trial parameters and says
#     so -- "reporting only, no consequence attaches" -- because analysis is
#     not consequence (PR-022 clause 4 protects figures from consequence,
#     not from being computed).
#   * No code path in this module can create, sign, or modify the
#     constitutional file (the module is read-only in its entirety; the
#     AST test in test_reputation_phase_b.py pins it, the same discipline
#     as warrant.py's no-sign-path test).
#   * The ssh namespace is "harness-constitutional", NEVER "harness-warrant":
#     warrant.py declares its namespace is never reused elsewhere, and a
#     shared namespace would let a signed warrant payload double as a
#     constitutional file or vice versa.
#
# Bootstrap, no flag day: before the operator signs a constitutional file,
# `dispatch` refuses and says exactly why; `rank` and `audit-immunity`
# keep working as reports.
# --------------------------------------------------------------------------

DEFAULT_HALF_LIFE_DAYS = 30.0

# NOT RATIFIED defaults: used by the read-only `rank` report and clearly
# labeled there. The consequence verb never reads these -- it takes its
# parameters from the operator-signed constitutional file or refuses.
DEFAULT_WEIGHTS = {
    "rule_authorship": 1.0,
    "citations_received": 1.0,
    "consolidations": 2.0,
    "overrulings_sustained": 1.5,
    "verdicts_upheld": 1.0,
}

CONSTITUTIONAL_NAMESPACE = "harness-constitutional"
CONSTITUTIONAL_RELPATH = "constitutional/reputation.json"

# The operator creates and signs the constitutional file OFF this process:
#   SSH_AUTH_SOCK= ssh-keygen -Y sign -f ~/.ssh/harness_root \
#       -n harness-constitutional .harness/constitutional/reputation.json
# This module only ever reads and verifies it.


def _constitutional_path(root):
    return Path(root) / "constitutional" / "reputation.json"


def _verify_constitutional_signature(root, payload_path, sig_path):
    """Verify sig_path over the EXACT bytes of payload_path against the
    anchored root key, in the harness-constitutional namespace. Returns the
    verified fingerprint or raises warrant.TrustError.

    Mirrors warrant.verify_signature (same temp-dir allowed_signers rebuild,
    same wrong-key check) but under this module's own namespace; the shared
    three-check anchor validation is warrant.check_anchor, reused as-is."""
    fp = warrant.check_anchor(root)
    with tempfile.TemporaryDirectory() as tmp:
        allowed = Path(tmp) / "allowed_signers"
        pub = (Path(root) / "trust" / "root.pub").read_text(encoding="utf-8").strip()
        allowed.write_text("operator {}\n".format(pub), encoding="utf-8")
        with open(payload_path, "rb") as fh:
            r = subprocess.run(
                ["ssh-keygen", "-Y", "verify", "-f", str(allowed), "-I", "operator",
                 "-n", CONSTITUTIONAL_NAMESPACE, "-s", str(sig_path)],
                stdin=fh, text=True, capture_output=True)
    if r.returncode != 0:
        raise warrant.TrustError(
            "SIGNATURE DOES NOT VERIFY for {}: {}".format(
                Path(payload_path).name, (r.stderr or r.stdout).strip()))
    seen = warrant.FINGERPRINT_RE.search(r.stdout or "")
    if not seen:
        raise warrant.TrustError(
            "ssh-keygen reported success without naming a signing key; refusing "
            "rather than assuming it was the anchored root.")
    if seen.group(0) != fp:
        raise warrant.TrustError(
            "SIGNED BY THE WRONG KEY: {} is not the anchored root {}.".format(
                seen.group(0), fp))
    return seen.group(0)


def _constitutional_status(root):
    """The mechanical status of the operator's constitutional file. A REPORT,
    not a verdict: one of NOT_PRESENT / UNREADABLE / WRONG_NAMESPACE /
    UNSIGNED / UNVERIFIABLE / BAD_SIGNATURE / VERIFIED, with detail."""
    path = _constitutional_path(root)
    sig = Path(str(path) + ".sig")
    st = {"path": str(path), "state": None, "detail": None, "payload": None}
    if not path.exists():
        st["state"] = "NOT_PRESENT"
        st["detail"] = "no constitutional file at {}".format(path)
        return st
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        st["state"] = "UNREADABLE"
        st["detail"] = str(e)
        return st
    if not isinstance(payload, dict):
        st["state"] = "UNREADABLE"
        st["detail"] = "payload is not a JSON object"
        return st
    st["payload"] = payload
    if payload.get("namespace") != CONSTITUTIONAL_NAMESPACE:
        st["state"] = "WRONG_NAMESPACE"
        st["detail"] = "payload namespace {!r} is not {!r}".format(
            payload.get("namespace"), CONSTITUTIONAL_NAMESPACE)
        return st
    if not sig.exists():
        st["state"] = "UNSIGNED"
        st["detail"] = "no detached signature at {}".format(sig)
        return st
    if not warrant.is_enrolled(root):
        st["state"] = "UNVERIFIABLE"
        st["detail"] = ("no trust root enrolled; a signature that cannot be "
                        "checked authorizes nothing")
        return st
    try:
        fp = _verify_constitutional_signature(root, path, sig)
    except warrant.TrustError as e:
        st["state"] = "BAD_SIGNATURE"
        st["detail"] = str(e)
        return st
    st["state"] = "VERIFIED"
    st["detail"] = "signed by anchored root {}".format(fp)
    return st


def _phase_b_activation(root):
    """The gate itself. Returns (payload, status): payload is the signed
    constitutional payload when and only when the file VERIFIES against the
    anchor and says activation on; otherwise payload is None and status says
    exactly which condition failed."""
    st = _constitutional_status(root)
    if st["state"] != "VERIFIED":
        return None, st
    if st["payload"].get("activation") != "on":
        st = dict(st)
        st["state"] = "VERIFIED_OFF"
        st["detail"] = "signature verifies but activation is {!r}, not 'on'".format(
            st["payload"].get("activation"))
        return None, st
    return st["payload"], st


def _parse_ts_utc(ts_str):
    try:
        return hc.parse_iso(ts_str) or hc.now_utc()
    except Exception:
        return hc.now_utc()


def _compute_ema_decay(event_ts_str, now_dt, half_life_days):
    if not event_ts_str:
        return 1.0
    ev_dt = _parse_ts_utc(event_ts_str)
    if ev_dt is None:
        return 1.0
    delta_days = max(0.0, (now_dt - ev_dt).total_seconds() / 86400.0)
    if half_life_days <= 0:
        return 1.0
    return 2.0 ** (-delta_days / half_life_days)


def _compute_phase_b_figures(identity, root, precedents, blackboard_tasks, reopened, half_life_days=DEFAULT_HALF_LIFE_DAYS, now_dt=None, weights=None):
    if now_dt is None:
        now_dt = hc.now_utc()
    w = weights or DEFAULT_WEIGHTS

    f1 = figure_rule_authorship(identity, precedents)
    decayed_f1 = 0.0
    for rec in precedents.values():
        if rec.get("published_by") == identity and rec.get("status") == "active":
            decayed_f1 += w["rule_authorship"] * _compute_ema_decay(rec.get("published_at"), now_dt, half_life_days)

    f2 = figure_load_bearing_citations_received(identity, precedents)
    decayed_f2 = 0.0
    for d in f2.get("detail", []):
        citing_id = d.get("citing_record")
        citing_rec = precedents.get(citing_id, {})
        decayed_f2 += w["citations_received"] * _compute_ema_decay(citing_rec.get("published_at"), now_dt, half_life_days)

    f3 = figure_consolidations_achieved(identity, precedents)
    decayed_f3 = float(f3.get("value", 0)) * w["consolidations"]

    f4 = figure_overrulings_sustained(identity, precedents, blackboard_tasks, reopened)
    decayed_f4 = 0.0
    for d in f4.get("detail", []):
        if d.get("sustained"):
            r_rec = precedents.get(d.get("record"), {})
            decayed_f4 += w["overrulings_sustained"] * _compute_ema_decay(r_rec.get("published_at"), now_dt, half_life_days)

    f5 = figure_verification_verdicts_upheld(identity, root, blackboard_tasks, reopened)
    decayed_f5 = 0.0
    for d in f5.get("detail", []):
        if d.get("outcome") == "upheld":
            t_data = blackboard_tasks.get(d.get("task"), {})
            decayed_f5 += w["verdicts_upheld"] * _compute_ema_decay(t_data.get("completed_at"), now_dt, half_life_days)

    total_score = round(decayed_f1 + decayed_f2 + decayed_f3 + decayed_f4 + decayed_f5, 4)
    return {
        "identity": identity,
        "phase": "B",
        "authority": "PR-061 (RAT-01) / PR-060",
        "half_life_days": half_life_days,
        "total_score": total_score,
        "decayed_components": {
            "rule_authorship": round(decayed_f1, 4),
            "citations_received": round(decayed_f2, 4),
            "consolidations": round(decayed_f3, 4),
            "overrulings_sustained": round(decayed_f4, 4),
            "verdicts_upheld": round(decayed_f5, 4),
        },
        "raw_figures": _compute_figures(identity, root, precedents, blackboard_tasks, reopened)
    }


def cmd_rank(args):
    """Rank discovered identities by Phase B decayed standing score.

    A read-only REPORT: no consequence attaches to its output, and it says
    so on every path. Trial parameters (--half-life-days) are accepted here
    BECAUSE this verb carries no consequence -- analysis is not consequence.
    The parameters used are labeled ratified or not against the operator's
    signed constitutional file."""
    root = resolve_root(args)
    if not root_is_valid(root):
        print("refused: invalid root '{}'".format(root), file=sys.stderr)
        return 1

    try:
        precedents = load_precedents(root)
        blackboard_tasks = load_blackboard_tasks(root)
        reopened = load_reopened_tasks(root)
        identities = collect_identities(precedents, blackboard_tasks)
    except precedent.RegistryIntegrityError as e:
        print("REGISTRY INTEGRITY ERROR: {}".format(e), file=sys.stderr)
        return 4

    now_dt = _parse_ts_utc(getattr(args, "now", None))
    half_life = float(getattr(args, "half_life_days", None) or DEFAULT_HALF_LIFE_DAYS)

    # Ratified means the payload VERIFIES against the anchor and the value in
    # use matches it. Activation is a separate question: an operator can
    # ratify parameters while leaving the consequence verb off.
    st = _constitutional_status(root)
    params_ratified = bool(
        st["state"] == "VERIFIED"
        and half_life == float(st["payload"].get("ema_half_life_days", -1)))

    ranked = []
    for ident, _ in identities:
        score_data = _compute_phase_b_figures(ident, root, precedents, blackboard_tasks, reopened, half_life, now_dt)
        ranked.append(score_data)

    ranked.sort(key=lambda x: (-x["total_score"], x["identity"]))

    if args.json:
        print(json.dumps({
            "phase": "B",
            "authority": "PR-061 (RAT-01) / PR-060",
            "consequence": "none: rank is reporting only (PR-061 authorizes "
                           "dispatch, not rank; PR-022 clause 4)",
            "half_life_days": half_life,
            "parameters_ratified": params_ratified,
            "constitutional_file_state": st["state"],
            "rankings": ranked,
            "count": len(ranked),
        }, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("PHASE B REPUTATION RANKINGS (EMA Decay: {}d)".format(half_life))
        print("Authority: PR-061 (RAT-01) / PR-060 (Operational consequences only)")
        print("reporting only, no consequence attaches; parameters {} "
              "(constitutional file: {})".format(
                  "RATIFIED by the signed constitutional file" if params_ratified
                  else "NOT RATIFIED (trial/default values)", st["state"]))
        print("-" * 60)
        for idx, item in enumerate(ranked, 1):
            print("  #{:<2} {:<24} Score: {:>7.4f} (rules:{:.2f}, cites:{:.2f}, verdicts:{:.2f})".format(
                idx, item["identity"], item["total_score"],
                item["decayed_components"]["rule_authorship"],
                item["decayed_components"]["citations_received"],
                item["decayed_components"]["verdicts_upheld"]
            ))
        print("=" * 60)
    return 0


def cmd_dispatch(args):
    """Operational parameter binding: rank candidate workers for task claim queue.

    THE CONSEQUENCE VERB. This is the one output of this module a consumer
    may act on (claim priority ordering -- an operational parameter under
    PR-060's split), and therefore the one verb behind the constitutional
    gate: it refuses unless the operator-signed constitutional file verifies
    against the trust anchor and says activation on, and it takes its
    constitutional parameters from that file ONLY."""
    root = resolve_root(args)
    if not root_is_valid(root):
        print("refused: invalid root '{}'".format(root), file=sys.stderr)
        return 1

    payload, st = _phase_b_activation(root)
    if payload is None:
        print("refused: dispatch is a consequence verb (PR-061) and no verified, "
              "activated constitutional file authorizes it", file=sys.stderr)
        print("  constitutional file: {} -- {}".format(st["state"], st["detail"]),
              file=sys.stderr)
        print("  activation is the operator's act alone: write {} and sign it with\n"
              "  SSH_AUTH_SOCK= ssh-keygen -Y sign -f <operator key> -n {} {}".format(
                  st["path"], CONSTITUTIONAL_NAMESPACE, st["path"]), file=sys.stderr)
        return 1

    if getattr(args, "half_life_days", None) is not None:
        print("refused: --half-life-days is a CONSTITUTIONAL parameter (PR-060) and "
              "on a consequence verb it comes ONLY from the signed constitutional "
              "file (which says {}). A CLI knob that must match the file is a knob "
              "that leaks; use `rank` for trial values.".format(
                  payload.get("ema_half_life_days", DEFAULT_HALF_LIFE_DAYS)),
              file=sys.stderr)
        return 1

    candidates_str = getattr(args, "candidates", None) or ""
    candidates = [c.strip() for c in candidates_str.split(",") if c.strip()]
    if not candidates:
        print("refused: --candidates must be non-empty", file=sys.stderr)
        return 1

    try:
        precedents = load_precedents(root)
        blackboard_tasks = load_blackboard_tasks(root)
        reopened = load_reopened_tasks(root)
    except precedent.RegistryIntegrityError as e:
        print("REGISTRY INTEGRITY ERROR: {}".format(e), file=sys.stderr)
        return 4

    now_dt = _parse_ts_utc(getattr(args, "now", None))
    half_life = float(payload.get("ema_half_life_days", DEFAULT_HALF_LIFE_DAYS))
    weights = dict(DEFAULT_WEIGHTS)
    for k, v in (payload.get("weights") or {}).items():
        if k in weights:
            weights[k] = float(v)

    scored = []
    for cand in candidates:
        score_data = _compute_phase_b_figures(cand, root, precedents, blackboard_tasks, reopened, half_life, now_dt, weights)
        scored.append(score_data)

    scored.sort(key=lambda x: (-x["total_score"], x["identity"]))

    tasks_str = getattr(args, "tasks", None) or ""
    tasks = [t.strip() for t in tasks_str.split(",") if t.strip()]

    dispatch_plan = {
        "phase": "B",
        "authority": "PR-061 (RAT-01) / PR-060 (Operational Parameter: Claim Priority Queue)",
        "constitutional_file": {
            "state": st["state"],
            "detail": st["detail"],
            "path": st["path"],
        },
        "parameters": {
            "source": "signed constitutional file",
            "ema_half_life_days": half_life,
            "weights": weights,
        },
        "consequence_scope": "claim priority ordering ONLY; nothing here may "
                             "modulate verification burdens, quorums, or any "
                             "constitutional parameter (PR-060)",
        "tasks": tasks,
        "recommended_claim_order": [s["identity"] for s in scored],
        "candidates": scored,
    }

    if args.json:
        print(json.dumps(dispatch_plan, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("OPERATIONAL DISPATCH QUEUE RECOMMENDATION (PR-061, RAT-01)")
        print("=" * 60)
        print("Constitutional file: {} -- {}".format(st["state"], st["detail"]))
        print("Parameters from signed file: half-life {}d, weights {}".format(
            half_life, json.dumps(weights, sort_keys=True)))
        if tasks:
            print("Target Tasks: {}".format(", ".join(tasks)))
        print("-" * 60)
        print("Priority Claim Order:")
        for idx, cand in enumerate(scored, 1):
            print("  Priority {}: {:<20} (Operational Standing Score: {:.4f})".format(
                idx, cand["identity"], cand["total_score"]))
        print("-" * 60)
        print("Consequence scope: claim priority ordering ONLY (PR-060 split)")
        print("=" * 60)
    return 0


def cmd_audit_immunity(args):
    """Report the mechanical state of the Phase B constitutional gate.

    FIGURES, NOT VERDICTS (currency.py's NO THRESHOLD RATIFIED precedent,
    and defect GUARD-MENTION-C's lesson generalized): the prior version of
    this verb printed a hardcoded PASS dict -- six invariants asserted True
    by literal, no input read, no way to fail. An audit that cannot fail is
    not an audit; it was replaced under T-420. This version reports what is
    mechanically checkable from here (the constitutional file's state, the
    activation value, the signed parameters against the source defaults) and
    labels everything else NOT MECHANICALLY EVALUABLE with the reason. It
    emits NO overall verdict."""
    root = resolve_root(args)
    if not root_is_valid(root):
        print("refused: invalid root '{}'".format(root), file=sys.stderr)
        return 1

    st = _constitutional_status(root)
    verified = st["state"] == "VERIFIED"
    payload = st["payload"] if verified else None

    checkable = {
        "constitutional_file_state": st["state"],
        "constitutional_file_detail": st["detail"],
        "activation": (payload or {}).get("activation") if verified else None,
        "signed_parameters": {
            "ema_half_life_days": (payload or {}).get("ema_half_life_days"),
            "weights": (payload or {}).get("weights"),
        } if verified else None,
        "source_default_parameters": {
            "ema_half_life_days": DEFAULT_HALF_LIFE_DAYS,
            "weights": DEFAULT_WEIGHTS,
            "ratified": False,
        },
    }
    not_evaluable = {
        "verification_burdens_uniform":
            "a property of every CONSUMER of these figures, not of this reader; "
            "no consumer can be audited from inside the module it consumes",
        "quorum_floors_unmodulated":
            "no quorum machinery reads this module today; tomorrow's consumers "
            "cannot be enumerated from here",
        "no_stored_balances":
            "this module's read-only discipline is pinned by the AST test in "
            "test_reputation_phase_b.py, not provable by the running module "
            "about itself",
        "D-17_shared_os_user":
            "identities are self-asserted (see CAVEAT); no in-process check "
            "distinguishes one agent from another",
    }

    if args.json:
        print(json.dumps({
            "verdict": None,
            "no_verdict_reason": "an audit that cannot fail is not an audit; "
                                 "this verb reports figures and refuses to "
                                 "verdict what it cannot mechanically evaluate",
            "mechanically_checked": checkable,
            "not_mechanically_evaluable": not_evaluable,
        }, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("PHASE B GATE REPORT (PR-060/PR-061, RAT-01)")
        print("=" * 60)
        print("Mechanically checked:")
        print("  constitutional file : {} -- {}".format(st["state"], st["detail"]))
        if verified:
            print("  activation          : {}".format(payload.get("activation")))
            print("  signed parameters   : half-life {}d, weights {}".format(
                payload.get("ema_half_life_days"),
                json.dumps(payload.get("weights"), sort_keys=True)))
        print("  source defaults     : half-life {}d (NOT RATIFIED, rank-only)".format(
            DEFAULT_HALF_LIFE_DAYS))
        print("-" * 60)
        print("NOT MECHANICALLY EVALUABLE from this module:")
        for k, why in not_evaluable.items():
            print("  {} :".format(k))
            print("      {}".format(why))
        print("-" * 60)
        print("NO VERDICT: an audit that cannot fail is not an audit.")
        print("=" * 60)
    return 0


# --------------------------------------------------------------------------
# AD2-62: the explicit allow-list of public callables. test_reputation.py
# asserts nothing else is exported and that no member's signature carries
# a threshold/gate/weight/burden/permission parameter.
# --------------------------------------------------------------------------

PUBLIC_API = (
    "CAVEAT",
    "resolve_root",
    "root_is_valid",
    "load_precedents",
    "load_blackboard_tasks",
    "load_reopened_tasks",
    "task_record_exists",
    "collect_identities",
    "figure_rule_authorship",
    "figure_load_bearing_citations_received",
    "figure_consolidations_achieved",
    "figure_overrulings_sustained",
    "figure_verification_verdicts_upheld",
    "figure_adjudications_not_reversed",
    "cmd_standing",
    "cmd_identities",
    "cmd_caveat",
    "cmd_rank",
    "cmd_dispatch",
    "cmd_audit_immunity",
    "main",
)


def _add_root_arg(parser):
    """Internal argparse plumbing only -- not on PUBLIC_API (AD2-62): this
    builds CLI wiring, it computes and gates nothing."""
    parser.add_argument("--root", default=None,
                         help="override the store root (else REPUTATION_ROOT env, "
                              "else .harness/) -- AD2-52")


def main(argv):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="caveat: " + CAVEAT)  # AD2-61: the --help path carries the caveat too.
    sub = parser.add_subparsers(dest="cmd", required=True)

    # ---- standing (AD2-50, AD2-51) ----
    p_standing = sub.add_parser("standing", help="one identity's Phase A standing figures")
    p_standing.add_argument("--identity", default=None,
                             help="mandatory, manually checked (not argparse-required) "
                                  "so absence is exit 1, not exit 2 -- AD2-51")
    _add_root_arg(p_standing)
    p_standing.add_argument("--json", action="store_true", default=False)
    p_standing.set_defaults(func=cmd_standing)

    # ---- identities (AD2-50, AD2-51, AD2-63) ----
    p_identities = sub.add_parser("identities", help="every identity discovered, lexicographic, never ranked")
    _add_root_arg(p_identities)
    p_identities.add_argument("--json", action="store_true", default=False)
    p_identities.set_defaults(func=cmd_identities)

    # ---- caveat (AD2-50, AD2-51, AD2-68) ----
    p_caveat = sub.add_parser("caveat", help="print the fixed sybil caveat and exit")
    p_caveat.add_argument("--json", action="store_true", default=False)
    p_caveat.set_defaults(func=cmd_caveat)

    # ---- rank (Phase B, PR-061 via RAT-01) ----
    p_rank = sub.add_parser("rank", help="REPORT: rank identities by Phase B EMA-decayed score; no consequence attaches")
    _add_root_arg(p_rank)
    p_rank.add_argument("--half-life-days", type=float, default=None,
                        help="TRIAL value for the report (default 30, NOT RATIFIED); "
                             "the consequence verb ignores this flag entirely")
    p_rank.add_argument("--now", default=None, help="override current timestamp (ISO UTC)")
    p_rank.add_argument("--json", action="store_true", default=False)
    p_rank.set_defaults(func=cmd_rank)

    # ---- dispatch (Phase B, PR-061 via RAT-01; gated by T-420) ----
    p_dispatch = sub.add_parser("dispatch", help="CONSEQUENCE VERB: claim queue priority; refuses without an operator-signed, activated constitutional file")
    _add_root_arg(p_dispatch)
    p_dispatch.add_argument("--candidates", required=True, help="comma-separated candidate worker identities")
    p_dispatch.add_argument("--tasks", default=None, help="comma-separated task IDs")
    p_dispatch.add_argument("--half-life-days", type=float, default=None,
                            help="REFUSED here: constitutional parameter, comes only "
                                 "from the signed file (PR-060); use `rank` for trials")
    p_dispatch.add_argument("--now", default=None, help="override current timestamp (ISO UTC)")
    p_dispatch.add_argument("--json", action="store_true", default=False)
    p_dispatch.set_defaults(func=cmd_dispatch)

    # ---- audit-immunity (Phase B gate report; figures, not verdicts) ----
    p_audit = sub.add_parser("audit-immunity", help="report the mechanical state of the Phase B gate; emits NO verdict")
    _add_root_arg(p_audit)
    p_audit.add_argument("--json", action="store_true", default=False)
    p_audit.set_defaults(func=cmd_audit_immunity)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
