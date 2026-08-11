#!/usr/bin/env python3
"""precedent.py -- the citation index and precedent-aware record schema (T-340).

Implements, verbatim, the schema and CLI surface fixed by
`docs/precedent-research/synthesis-design-requirements.md` (T-339, the SDR
document). Every structural rule below cites its SDR item so a verifier can
replay this file against that document mechanically (P-024, T-346).

EXTENDED BY T-342: the `conflicts` subcommand (reserved by SDR-27, implemented
below) is an ON-DEMAND CLI pass per coordinator decision D6 -- modeled on
`lock.py sweep` / `blackboard.py expire-claims`, never a hook, never a hard
gate, identical behavior for every engine. It is fully READ-ONLY: like `cite`
(SDR-23's own words, "never writes anything, including events -- C-2: signals
are read-only queries"), `conflicts` logs no event and mutates nothing, so it
can never block, gate, or slow any other CLI call. `merge` is reserved for
nobody in this epic (SDR-27) -- a successor `publish --supersedes X --cites Y`
is v0's merge outcome.

Registry: one JSON file per record at `<root>/PR-NNN.json`, default root
`.harness/precedents/` (D5), overridable via `--root` or `PRECEDENT_ROOT`
(flag wins, SDR-13) so T-342's tests and T-343's live seeds never collide.

stdlib only; MUST run under python3 3.9.6 -- no match statement, no tomllib
at module scope, no dataclass slots, no 3.10+ syntax. Reuses
harness_common (hc) for guarded(), atomic_write_json, append_jsonl,
log_event, now_iso, agent_id rather than reimplementing any of them (C-2).

Exit-code contract (SDR-15), fixed for every subcommand:
  0  success (read verbs: ran clean, zero findings)
  1  REFUSAL -- a named precondition failed (validation, authority asymmetry,
     producer-confirms-own-record, non-active target, missing mandatory
     field). "validation" is the general umbrella SDR-15 names first, so
     every business/schema-validity failure below returns 1, whether or not
     SDR-17/SDR-24 individually enumerate that exact case.
  2  usage error (argparse native: unknown flag, bad --tier value that
     fails int() conversion, conflicting mutually-exclusive flags, unknown
     subcommand -- see the DECISION note below for why --tier/--width/etc.
     are NOT argparse `choices=`-constrained)
  3  FINDINGS -- the verb ran and found problems to report (cite: >=1
     dangling reference)
  4  REGISTRY INTEGRITY ERROR -- an unparseable/schema-invalid record was
     encountered during any read; never skipped silently

DECISION (exit-code split, SDR-15): fields that SDR-17/SDR-24 name as
"required" (ratio, tier, tier_evidence, declared_width, scope_conditions,
revisit_trigger, --outcome, --factor names) are deliberately left
argparse-OPTIONAL (no `required=True`, no `choices=`) so that BOTH total
absence and an out-of-range/garbled value flow through the SAME manual
check and produce exit 1 -- matching SDR-15's own example, "missing
mandatory field" filed under REFUSAL (exit 1), not under "usage error"
(exit 2). Fields SDR-17/SDR-24 never mention at all (--task, --title,
--subject) stay ordinary argparse `required=True` (exit 2 if the flag is
absent altogether) since there is no SDR text to route their absence to
exit 1; their FORMAT, once given, is still validated per SDR-17.2 as exit 1.

DECISION (relation `factor_note` enforcement, section 2.2 field table):
SDR-17's list names factor_note only via item 11 (tier-3 overrule targets).
The relation field table (section 2.2) independently requires factor_note
"iff factors present", which would otherwise let a tier-1/2 overrule attach
factors with no note. Enforced here for every overrule with any --factor,
not just tier-3 targets -- disclosed, not a silent reword.

DECISION (bare forms for distinguishing-facts/factor-note): SDR-16 states
generally that "bare-string forms exist for short values" for every
long-text field; the section 5.3 ASCII grammar shows only the `-file` form
for `--distinguishing-facts` and `--factor-note`. Both bare and `-file`
forms are implemented here per SDR-16's general statement.

DEVIATION (repeated `--distinguishes` relations): the ASCII grammar's
trailing "..." after `[--distinguishes PR-NNN --distinguishing-facts-file
<f>]` denotes the whole bracketed pair repeating, which argparse cannot
express as a literal repeated flag-GROUP. Implemented as two append lists
(`--distinguishes`, `--distinguishing-facts`/`--distinguishing-facts-file`)
zipped by occurrence order -- documented in --help and enforced (refused if
counts mismatch or both forms are mixed in one call).

DECISION (`--scope-file` / `narrowed`'s `--scope-file` format): SDR-16 does
not specify a wire format for list-valued `-file` flags. One non-empty,
stripped scope condition per line -- undocumented elsewhere, disclosed here.

---- T-342 additions (conflicts subcommand) -------------------------------

DECISION (conflicts exit codes): T-342 AC-3 asks for "0 when no conflicts, a
documented nonzero code when conflicts are found, and a distinct code for
usage errors." SDR-15 already fixes that exact shape for "every current and
future subcommand" -- 0 clean / 3 FINDINGS / 2 usage error (argparse native)
/ 4 registry integrity error -- so `conflicts` reuses those four verbatim
rather than minting new ones.

DECISION (conflicts is read-only, logs no event): SDR-23 states `cite`
"never writes anything, including events (C-2: signals are read-only
queries)". `conflicts` is the same class of verb -- a registry-wide sweep,
D6 "pass, not gate" -- and detector 5 explicitly reuses `cite --all`'s
resolution core. Consistency with that adjacent, closely-related verb (and
with C-2's "no new... signal that re-verifies") outweighs T-342 AC-4's
permissive "use harness_common.log_event if an event is warranted": no event
is warranted here, because logging one would make `conflicts` the only read
verb in this file with a side effect, which is exactly the kind of asymmetry
a future engine-parity audit would have to explain.

DECISION (detector 1 and detector 4 exclude ALREADY-RELATED pairs): a pair
connected by any `relations[]` link (either direction) or a `cites[]` entry
has disclosed its divergence -- SDR-12: "the structural citation field is
what makes silent divergence detectable at all." Both contradiction
detectors (1: same subject, 4: same-tier scope overlap) therefore flag only
UNACKNOWLEDGED divergence between active records, matching S-08's own
"no shared ancestor" clause. An acknowledged disagreement (A follows/cites/
distinguishes B) is exactly the citation-index doing its job, not a defect.

DECISION (detector 2 scope: `follows`/`cites`, not `distinguishes`):
"citing an OVERRULED record as binding support" means relying on it as
authority. Distinguishing an overruled record is not reliance -- it is
citing it for context/history, which remains legitimate even after the
target is dead law -- so `distinguishes` relations are excluded on purpose.

DECISION (detector 3 also covers `voids`, not just `overrules`): the AC text
says "overruling", but SDR-17.8's tier-symmetry rule governs `overrules` AND
`voids` identically ("`overrules`/`voids` refuse when..."). A voids act by a
lower-tier record against a higher-tier target is the same illegitimacy
D4 forbids, so detector 3 checks both relation types. `supersedes` is
deliberately excluded: SDR-17.8 never applies a tier check to it.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import harness_common as hc

# --------------------------------------------------------------------------
# Constants / schema vocabulary (section 2, 2.1, 2.2)
# --------------------------------------------------------------------------

SCHEMA_VERSION = 1
DEFAULT_ROOT = hc.HARNESS / "precedents"

VALID_TIERS = (1, 2, 3, 4)
VALID_STATUS = ("active", "overruled", "superseded", "void_per_incuriam")
VALID_WIDTH = ("narrow", "wide")
VALID_CONFIRMATION_OUTCOMES = ("confirmed", "narrowed", "rejected")
RELATION_TYPES = ("follows", "distinguishes", "overrules", "supersedes", "voids")
FACTOR_ENUM = ("reasoning_error", "unworkability", "doctrinal_change", "factual_change", "reliance")

# relation type -> (status it stamps on the target, backref field it fills)
TIER_STATUS_TARGET = {
    "overrules": "overruled",
    "supersedes": "superseded",
    "voids": "void_per_incuriam",
}
TIER_BACKREF_FIELD = {
    "overrules": "overruled_by",
    "supersedes": "superseded_by",
    "voids": "voided_by",
}
FLIP_EVENT = {
    "overrules": "precedent_overruled",
    "supersedes": "precedent_superseded",
    "voids": "precedent_voided",
}

# --------------------------------------------------------------------------
# Citation token grammar (SDR-10)
# --------------------------------------------------------------------------

PR_RE = re.compile(r"^PR-\d{3,}$")
T_RE = re.compile(r"^T-\d{3,}$")
P_RE = re.compile(r"^P-\d{3}$")
GEN_RE = re.compile(r"^gen:\d+$")
AGENT_RE = re.compile(r"^agent:[A-Za-z0-9_.-]+$")
EVENT_RE = re.compile(r"^event:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
PATH_RE = re.compile(r"^([^\s:]+\.[A-Za-z0-9]+):(\d+(?:-\d+)?)$")
SUBJECT_RE = re.compile(r"^[a-z0-9-]+$")
PR_ID_NUM_RE = re.compile(r"^PR-(\d+)$")


def token_kind(token):
    """Classify a citation token per SDR-10's grammar table. None if none match."""
    if not isinstance(token, str):
        return None
    if PR_RE.match(token):
        return "PR"
    if T_RE.match(token):
        return "T"
    if P_RE.match(token):
        return "P"
    if GEN_RE.match(token):
        return "gen"
    if AGENT_RE.match(token):
        return "agent"
    if EVENT_RE.match(token):
        return "event"
    if PATH_RE.match(token):
        return "path"
    return None


def _read_state():
    return hc.read_json(hc.STATE) or {}


def _p_number_exists(token):
    state = _read_state()
    ev = state.get("evolution", {}) or {}
    for key in ("accepted_mutations", "pending_proposals"):
        for entry in ev.get(key, []) or []:
            if isinstance(entry, dict) and entry.get("id") == token:
                return True
    return False


def _gen_le_current(token):
    n = int(token.split(":", 1)[1])
    state = _read_state()
    try:
        gen = int(state.get("harness_generation", -1))
    except (TypeError, ValueError):
        gen = -1
    return n <= gen


def _agent_known(token):
    name = token.split(":", 1)[1]
    state = _read_state()
    agents = state.get("agents", {}) or {}
    registry = agents.get("registry", {}) or {}
    reputation = agents.get("reputation", {}) or {}
    if isinstance(registry, dict) and name in registry:
        return True
    if isinstance(reputation, dict) and name in reputation:
        return True
    return False


def _event_ts_exists(token):
    ts = token.split(":", 1)[1]
    try:
        with open(hc.EVENTS, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("ts") == ts:
                    return True
    except OSError:
        return False
    return False


def _path_token_exists(token):
    m = PATH_RE.match(token)
    relpath = m.group(1)
    p = Path(relpath)
    if not p.is_absolute():
        p = hc.ROOT / p
    return p.exists()


def resolve_citation(token, root):
    """Read-only resolution of one citation token per SDR-10. `root` is only
    consulted for PR-NNN tokens (the registry currently in scope)."""
    kind = token_kind(token)
    if kind == "PR":
        return record_path(root, token).exists()
    if kind == "T":
        return (hc.TASKS / (token + ".json")).exists()
    if kind == "P":
        return _p_number_exists(token)
    if kind == "gen":
        return _gen_le_current(token)
    if kind == "agent":
        return _agent_known(token)
    if kind == "event":
        return _event_ts_exists(token)
    if kind == "path":
        return _path_token_exists(token)
    return False


def tier_evidence_kind_ok(tier, tokens):
    """Section 3 table: each tier requires >=1 token of a specific kind."""
    kinds = [token_kind(t) for t in tokens]
    if tier == 1:
        return any(k in ("T", "event") for k in kinds)
    if tier == 2:
        return any(k == "P" for k in kinds)
    if tier in (3, 4):
        return any(k == "T" for k in kinds)
    return False


# --------------------------------------------------------------------------
# Registry I/O (read-only helpers + atomic writes via harness_common)
# --------------------------------------------------------------------------

class RegistryIntegrityError(Exception):
    """Raised when a record file is unparseable or schema-shapeless.
    SDR-15 exit 4: never skipped silently."""

    def __init__(self, path, cause):
        super().__init__("{} is unparseable: {}".format(path, cause))
        self.path = path


class FileArgError(Exception):
    """Raised when a -file argument (--ratio-file, --scope-file, etc.)
    cannot be read as utf-8 text."""


def resolve_root(args):
    """SDR-13: --root flag wins over PRECEDENT_ROOT env; default is D5's
    `.harness/precedents/`. Every subcommand honors this."""
    root_arg = getattr(args, "root", None)
    if root_arg:
        return Path(root_arg)
    env_root = os.environ.get("PRECEDENT_ROOT")
    if env_root:
        return Path(env_root)
    return DEFAULT_ROOT


def record_path(root, pr_id):
    return Path(root) / (pr_id + ".json")


def load_record_or_raise(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise RegistryIntegrityError(path, e)
    if not isinstance(data, dict) or "id" not in data:
        raise RegistryIntegrityError(path, "missing 'id' field or not a JSON object")
    return data


def scan_registry(root):
    """Yield (id, record) for every PR-*.json under root, sorted by numeric
    id. Raises RegistryIntegrityError on the first corrupt record (SDR-15:
    never skip one silently)."""
    root = Path(root)
    if not root.exists():
        return
    files = sorted(root.glob("PR-*.json"), key=lambda p: p.name)
    for f in files:
        rec = load_record_or_raise(f)
        yield rec.get("id"), rec


def allocate_next_id(root):
    """SDR-19.1: scan <root>/PR-*.json, id = max numeric + 1, zero-padded to
    3 digits, growing naturally past 999. MUST be called while holding
    hc.guarded() (AC-4 / SDR-19)."""
    root = Path(root)
    max_n = 0
    if root.exists():
        for f in root.glob("PR-*.json"):
            m = PR_ID_NUM_RE.match(f.stem)
            if m:
                n = int(m.group(1))
                if n > max_n:
                    max_n = n
    return "PR-{:03d}".format(max_n + 1)


def read_file_text(path):
    """Byte-exact utf-8 read, mirroring blackboard.py's --note-file (P-021):
    no stripping, so shell-hazard-adjacent content survives intact."""
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8")
    except OSError as e:
        raise FileArgError("cannot read file {}: {}".format(path, e))
    except UnicodeDecodeError as e:
        raise FileArgError("file {} is not valid utf-8: {}".format(path, e))


def integrity_error(path, cause):
    print("REGISTRY INTEGRITY ERROR: {} is unparseable: {}".format(path, cause), file=sys.stderr)
    return 4


def refuse(event_kind, reason, **fields):
    """Log a refusal event (SDR-26) and print the message. Callers do
    `return refuse(...)` -- this function itself never exits the process,
    so `with hc.guarded():` blocks unwind and release their lock normally."""
    hc.log_event(event_kind, reason=reason, **fields)
    print("refused: " + reason, file=sys.stderr)
    return 1


# --------------------------------------------------------------------------
# publish
# --------------------------------------------------------------------------

def make_relation(rtype, target, distinguishing_facts=None, factors=None,
                   factor_note=None, controlling_authority=None):
    return {
        "type": rtype,
        "target": target,
        "distinguishing_facts": distinguishing_facts,
        "factors": factors or [],
        "factor_note": factor_note,
        "controlling_authority": controlling_authority,
        "below_target_tier": None,  # stamped by the CLI once the target's tier is known
    }


def resolve_ratio(args):
    if args.ratio_stdin:
        return sys.stdin.buffer.read().decode("utf-8")
    if args.ratio_file:
        return read_file_text(args.ratio_file)
    return args.ratio or ""


def resolve_scope(scope_list_arg, scope_file_arg):
    if scope_file_arg:
        return [line.strip() for line in read_file_text(scope_file_arg).splitlines() if line.strip()]
    return list(scope_list_arg or [])


def assemble_relations(args):
    """Build the relations[] list from CLI args. Returns (relations, error)
    -- error is a plain string (never raised) so callers can route it
    through the same refuse() -> exit 1 path as every other SDR-17 check."""
    relations = []
    for target in (args.follows or []):
        relations.append(make_relation("follows", target))

    dtargets = args.distinguishes or []
    dfacts_bare = args.distinguishing_facts or []
    dfacts_file = args.distinguishing_facts_file or []
    if dtargets:
        if dfacts_bare and dfacts_file:
            return None, ("--distinguishing-facts and --distinguishing-facts-file cannot both "
                           "be used in the same publish call -- pick one form for every "
                           "--distinguishes relation (argparse cannot represent mixed repeated "
                           "flag-pairs; see the DEVIATION note in this file's module docstring)")
        facts_source = dfacts_file if dfacts_file else dfacts_bare
        if len(facts_source) != len(dtargets):
            return None, ("each --distinguishes needs exactly one paired --distinguishing-facts "
                           "or --distinguishing-facts-file, matched by occurrence order "
                           "({} target(s), {} facts given)".format(len(dtargets), len(facts_source)))
        for target, src in zip(dtargets, facts_source):
            facts_text = read_file_text(src) if dfacts_file else src
            relations.append(make_relation("distinguishes", target, distinguishing_facts=facts_text))
    elif dfacts_bare or dfacts_file:
        return None, "--distinguishing-facts(-file) given without a matching --distinguishes target"

    if args.overrules:
        factor_note = read_file_text(args.factor_note_file) if args.factor_note_file else args.factor_note
        relations.append(make_relation("overrules", args.overrules,
                                        factors=list(args.factor or []), factor_note=factor_note))
    if args.supersedes:
        relations.append(make_relation("supersedes", args.supersedes))
    if args.voids:
        relations.append(make_relation("voids", args.voids, controlling_authority=args.controlling_authority))

    return relations, None


def cmd_publish(args):
    root = resolve_root(args)

    try:
        ratio = resolve_ratio(args)
        scope_list = resolve_scope(args.scope, args.scope_file)
        relations, rel_err = assemble_relations(args)
    except FileArgError as e:
        print("refused: {}".format(e), file=sys.stderr)
        return 1
    if rel_err:
        return refuse("precedent_publish_refused", rel_err, task=args.task)

    dicta_list = list(args.dicta or [])
    cites_list = list(args.cites or [])
    te_list = list(args.tier_evidence or [])
    subject = args.subject
    title = args.title
    tier = args.tier
    width = args.width
    revisit_trigger = args.revisit_trigger

    # ---- SDR-17 items 1-5: pure argument-shape checks, no registry needed ----
    if not ratio.strip():
        return refuse("precedent_publish_refused", "ratio must be non-empty (SDR-17.1)", task=args.task)
    if not SUBJECT_RE.match(subject or ""):
        return refuse("precedent_publish_refused",
                       "subject '{}' must match the slug regex ^[a-z0-9-]+$ (SDR-17.2)".format(subject),
                       task=args.task)
    if len(title) > 80:
        return refuse("precedent_publish_refused", "title exceeds 80 chars (SDR-17.2)", task=args.task)
    if tier not in VALID_TIERS:
        return refuse("precedent_publish_refused", "tier must be one of 1,2,3,4 (SDR-17.3)", task=args.task)
    if not te_list:
        return refuse("precedent_publish_refused", "tier_evidence must be non-empty (SDR-17.3)", task=args.task)
    if not tier_evidence_kind_ok(tier, te_list):
        return refuse("precedent_publish_refused",
                       "tier_evidence for tier {} lacks a required token kind "
                       "(section 3 table, SDR-17.3)".format(tier), task=args.task)
    if tier in (1, 2, 3):
        if not scope_list:
            return refuse("precedent_publish_refused",
                           "scope_conditions must be non-empty at tiers 1-3 (SDR-17.4)", task=args.task)
        if not revisit_trigger or not revisit_trigger.strip():
            return refuse("precedent_publish_refused",
                           "revisit_trigger must be non-empty at tiers 1-3 (SDR-17.4)", task=args.task)
    if width not in VALID_WIDTH:
        return refuse("precedent_publish_refused",
                       "declared_width must be 'narrow' or 'wide' (SDR-17.5)", task=args.task)
    for rel in relations:
        if rel["type"] == "overrules":
            for f in rel["factors"]:
                if f not in FACTOR_ENUM:
                    return refuse("precedent_publish_refused",
                                   "--factor '{}' is not one of {} (SDR-17.11's factor enum)"
                                   .format(f, ", ".join(FACTOR_ENUM)), task=args.task)

    # ---- SDR-17 items 6-14 (registry-dependent) + SDR-19 commit, ONE guard ----
    same_subject_missing = []
    dangling_tokens = []
    side_effects = []
    new_id = None
    try:
        with hc.guarded():
            target_cache = {}

            # item 6: every relation target must resolve
            for rel in relations:
                tid = rel["target"]
                p = record_path(root, tid)
                if not p.exists():
                    return refuse("precedent_publish_refused",
                                   "relation target {} does not resolve to an existing record "
                                   "(SDR-17.6)".format(tid), task=args.task)
                if tid not in target_cache:
                    target_cache[tid] = load_record_or_raise(p)

            # item 7: distinguishes needs non-empty facts + non-empty target scope
            for rel in relations:
                if rel["type"] == "distinguishes":
                    if not (rel.get("distinguishing_facts") or "").strip():
                        return refuse("precedent_publish_refused",
                                       "distinguishes against {} requires non-empty "
                                       "distinguishing_facts (SDR-17.7)".format(rel["target"]),
                                       task=args.task)
                    if not target_cache[rel["target"]].get("scope_conditions"):
                        return refuse("precedent_publish_refused",
                                       "cannot distinguish against {}: target's scope_conditions "
                                       "is empty (SDR-17.7)".format(rel["target"]), task=args.task)

            # items 8-9: overrules/voids tier symmetry + tier-4-target refusal
            for rel in relations:
                if rel["type"] in ("overrules", "voids"):
                    tgt = target_cache[rel["target"]]
                    tgt_tier = tgt.get("authority_tier")
                    if tier > (tgt_tier or 0):
                        return refuse("precedent_publish_refused",
                                       "{} of {} refused: acting tier {} is lower authority than "
                                       "target tier {} (SDR-17.8)".format(rel["type"], rel["target"],
                                                                           tier, tgt_tier),
                                       task=args.task)
                    if tgt_tier == 4:
                        return refuse("precedent_publish_refused",
                                       "{} of {} refused: target is tier 4 -- a category error, cite "
                                       "or distinguish instead (SDR-17.9)".format(rel["type"], rel["target"]),
                                       task=args.task)

            # item 10: overrules/supersedes/voids need an active target
            for rel in relations:
                if rel["type"] in ("overrules", "supersedes", "voids"):
                    tgt = target_cache[rel["target"]]
                    if tgt.get("status") != "active":
                        return refuse("precedent_publish_refused",
                                       "{} of {} refused: target status is '{}', not active "
                                       "(SDR-17.10)".format(rel["type"], rel["target"], tgt.get("status")),
                                       task=args.task)

            # item 11 (+ section 2.2 factor_note rule) and item 12 (reliance ack)
            for rel in relations:
                if rel["type"] == "overrules":
                    tgt = target_cache[rel["target"]]
                    if tgt.get("authority_tier") == 3 and not rel["factors"]:
                        return refuse("precedent_publish_refused",
                                       "overrules of tier-3 target {} requires >=1 --factor "
                                       "(SDR-17.11)".format(rel["target"]), task=args.task)
                    if rel["factors"] and not (rel.get("factor_note") or "").strip():
                        return refuse("precedent_publish_refused",
                                       "overrules with --factor requires --factor-note or "
                                       "--factor-note-file (section 2.2 field table)", task=args.task)
                    if tgt.get("cited_by") and not args.acknowledge_reliance:
                        return refuse("precedent_publish_refused",
                                       "overrules of {} refused: target is cited_by {} -- pass "
                                       "--acknowledge-reliance after reviewing the blast radius "
                                       "(SDR-17.12)".format(rel["target"], tgt.get("cited_by")),
                                       task=args.task)

            # item 13: voids requires a resolvable controlling_authority
            for rel in relations:
                if rel["type"] == "voids":
                    ca = rel.get("controlling_authority")
                    if not ca or not resolve_citation(ca, root):
                        return refuse("precedent_publish_refused",
                                       "voids of {} requires --controlling-authority with a "
                                       "resolvable token (SDR-17.13)".format(rel["target"]), task=args.task)

            # item 14 (+ generalized to every relation per the field table): stamp below_target_tier
            for rel in relations:
                tgt = target_cache[rel["target"]]
                rel["below_target_tier"] = tier > (tgt.get("authority_tier") or 0)

            # item 15 is satisfied by construction: no CLI path sets confirmation_*.

            # SDR-18: S-09 citation-completeness scan (mandatory, non-blocking)
            covered = set(cites_list) | set(rel["target"] for rel in relations)
            try:
                for pid, rec in scan_registry(root):
                    if (rec.get("subject") == subject and rec.get("status") == "active"
                            and rec.get("authority_tier") in (1, 2, 3) and pid not in covered):
                        same_subject_missing.append(pid)
            except RegistryIntegrityError as e:
                return integrity_error(e.path, e)

            # SDR-18/SDR-12: dangling cites/tier_evidence tokens (non-blocking)
            for token in cites_list + te_list:
                if not resolve_citation(token, root):
                    dangling_tokens.append(token)

            # SDR-19: commit
            new_id = allocate_next_id(root)
            record = {
                "id": new_id,
                "schema_version": SCHEMA_VERSION,
                "title": title,
                "subject": subject,
                "status": "active",
                "authority_tier": tier,
                "tier_evidence": te_list,
                "ratio": ratio,
                "dicta": dicta_list,
                "scope_conditions": scope_list,
                "declared_width": width,
                "revisit_trigger": revisit_trigger,
                "confirmation_status": "unconfirmed",
                "confirmed_by": None,
                "confirmed_at": None,
                "narrowed_scope": None,
                "confirmation_note": None,
                "relations": relations,
                "cites": cites_list,
                "cited_by": [],
                "overruled_by": None,
                "superseded_by": None,
                "voided_by": None,
                "issuing_task": args.task,
                "published_by": args.agent,
                "published_at": hc.now_iso(),
            }
            hc.atomic_write_json(record_path(root, new_id), record)

            # SDR-19.3/19.4: cited_by back-references + status flips on targets
            targets_touch = {}
            for rel in relations:
                entry = targets_touch.setdefault(rel["target"], {"cited_by": False, "flip": None})
                entry["cited_by"] = True
                if rel["type"] in TIER_STATUS_TARGET:
                    entry["flip"] = rel["type"]
            for c in cites_list:
                if PR_RE.match(c) and record_path(root, c).exists():
                    targets_touch.setdefault(c, {"cited_by": False, "flip": None})["cited_by"] = True

            for tid, entry in targets_touch.items():
                tp = record_path(root, tid)
                trec = target_cache.get(tid)
                if trec is None:
                    trec = load_record_or_raise(tp)
                if entry["cited_by"] and new_id not in trec.get("cited_by", []):
                    trec.setdefault("cited_by", []).append(new_id)
                if entry["flip"]:
                    trec["status"] = TIER_STATUS_TARGET[entry["flip"]]
                    trec[TIER_BACKREF_FIELD[entry["flip"]]] = new_id
                    side_effects.append((entry["flip"], tid))
                hc.atomic_write_json(tp, trec)
    except RegistryIntegrityError as e:
        return integrity_error(e.path, e)

    # ---- SDR-19.5: log events only after the guard releases ----
    hc.log_event("precedent_published", id=new_id, agent=args.agent, tier=tier,
                 subject=subject, issuing_task=args.task)
    for rtype, tid in side_effects:
        hc.log_event(FLIP_EVENT[rtype], id=tid, by=new_id, agent=args.agent)
    for token in dangling_tokens:
        hc.log_event("dangling_reference", record=new_id, token=token)
    if dangling_tokens:
        print("warning: {} dangling citation token(s): {}".format(
            len(dangling_tokens), ", ".join(dangling_tokens)))
    if same_subject_missing:
        hc.log_event("citation_gap", record=new_id, subject=subject, missing=same_subject_missing)
        print("warning: citation-completeness gap -- active tier 1-3 record(s) sharing subject "
              "'{}' not cited: {}".format(subject, ", ".join(same_subject_missing)))
    print("published {}".format(new_id))
    return 0


# --------------------------------------------------------------------------
# show
# --------------------------------------------------------------------------

def binding_summary_line(rec):
    """SDR-02/SDR-21: render the unconfirmed/confirmed/narrowed/rejected
    state explicitly -- scope never binds silently."""
    cs = rec.get("confirmation_status")
    cb = rec.get("confirmed_by")
    ca = rec.get("confirmed_at")
    if cs == "unconfirmed":
        return "scope: UNCONFIRMED (does not bind)"
    if cs == "confirmed":
        return "scope: CONFIRMED by {} at {}".format(cb, ca)
    if cs == "narrowed":
        return "scope: NARROWED by {} at {} -> {}".format(cb, ca, rec.get("narrowed_scope"))
    if cs == "rejected":
        return "scope: REJECTED by {} at {}".format(cb, ca)
    return "scope: UNKNOWN ({})".format(cs)


def cmd_show(args):
    root = resolve_root(args)
    path = record_path(root, args.pr_id)
    if not path.exists():
        print("refused: no such precedent record: {}".format(args.pr_id), file=sys.stderr)
        return 1
    try:
        rec = load_record_or_raise(path)
    except RegistryIntegrityError as e:
        return integrity_error(e.path, e)
    print(json.dumps(rec, indent=2, ensure_ascii=False))
    print(binding_summary_line(rec))
    return 0


# --------------------------------------------------------------------------
# list
# --------------------------------------------------------------------------

def cmd_list(args):
    root = resolve_root(args)
    try:
        records = list(scan_registry(root))
    except RegistryIntegrityError as e:
        return integrity_error(e.path, e)

    filtered = []
    for pid, rec in records:
        if args.tier is not None and rec.get("authority_tier") != args.tier:
            continue
        if args.status is not None and rec.get("status") != args.status:
            continue
        if args.subject is not None and rec.get("subject") != args.subject:
            continue
        filtered.append((pid, rec))

    if args.json:
        out = [{"id": pid, "authority_tier": rec.get("authority_tier"), "status": rec.get("status"),
                "confirmation_status": rec.get("confirmation_status"), "subject": rec.get("subject"),
                "title": rec.get("title")} for pid, rec in filtered]
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print("{:<8} {:<5} {:<16} {:<14} {:<24} {}".format(
            "ID", "TIER", "STATUS", "CONFIRM", "SUBJECT", "TITLE"))
        for pid, rec in filtered:
            print("{:<8} {:<5} {:<16} {:<14} {:<24} {}".format(
                pid, rec.get("authority_tier"), rec.get("status"), rec.get("confirmation_status"),
                str(rec.get("subject"))[:24], str(rec.get("title"))[:60]))
    return 0


# --------------------------------------------------------------------------
# cite
# --------------------------------------------------------------------------

def _record_citation_tokens(rec):
    tokens = list(rec.get("cites") or [])
    tokens.extend(rec.get("tier_evidence") or [])
    for rel in (rec.get("relations") or []):
        if rel.get("target"):
            tokens.append(rel["target"])
        if rel.get("controlling_authority"):
            tokens.append(rel["controlling_authority"])
    return tokens


def iter_all_citation_resolutions(root, records=None):
    """The read-only registry-wide dangling-citation sweep (SDR-23's `cite
    --all`). Yields (pid, token, ok) in scan order. `precedent.py conflicts`
    detector 5 (T-342 AC-2 item 5) calls this exact generator rather than
    reimplementing the sweep -- SDR-23's own words: "the read-only core
    that T-342's detector 5 will reuse rather than reimplement" (C-2)."""
    if records is None:
        records = list(scan_registry(root))
    for pid, rec in records:
        for token in _record_citation_tokens(rec):
            yield pid, token, resolve_citation(token, root)


def cmd_cite(args):
    """SDR-23: three forms. Read-only -- never writes anything, including
    events (C-2: signals are read-only queries)."""
    root = resolve_root(args)
    forms_given = sum([bool(args.all), bool(args.record), bool(args.tokens)])
    if forms_given == 0:
        print("usage: pass token(s), --record PR-NNN, or --all", file=sys.stderr)
        return 2
    if forms_given > 1:
        print("usage: tokens, --record and --all are mutually exclusive", file=sys.stderr)
        return 2

    total = 0
    dangling = 0

    if args.all:
        try:
            records = list(scan_registry(root))
        except RegistryIntegrityError as e:
            return integrity_error(e.path, e)
        for pid, token, ok in iter_all_citation_resolutions(root, records):
            total += 1
            print("{} cites {}: {}".format(pid, token, "OK" if ok else "DANGLING"))
            if not ok:
                dangling += 1
    elif args.record:
        path = record_path(root, args.record)
        if not path.exists():
            print("refused: no such precedent record: {}".format(args.record), file=sys.stderr)
            return 1
        try:
            rec = load_record_or_raise(path)
        except RegistryIntegrityError as e:
            return integrity_error(e.path, e)
        for token in _record_citation_tokens(rec):
            total += 1
            ok = resolve_citation(token, root)
            print("{} cites {}: {}".format(args.record, token, "OK" if ok else "DANGLING"))
            if not ok:
                dangling += 1
    else:
        for token in args.tokens:
            total += 1
            ok = resolve_citation(token, root)
            print("{}: {}".format(token, "OK" if ok else "DANGLING"))
            if not ok:
                dangling += 1

    if dangling:
        print("{} of {} citation(s) dangling".format(dangling, total))
        return 3
    return 0


# --------------------------------------------------------------------------
# confirm
# --------------------------------------------------------------------------

def refuse_confirm(reason, pr_id, agent):
    hc.log_event("precedent_confirm_refused", pr=pr_id, agent=agent, reason=reason)
    print("refused: " + reason, file=sys.stderr)
    return 1


def cmd_confirm(args):
    root = resolve_root(args)

    try:
        note = read_file_text(args.note_file) if args.note_file else args.note
        scope_list = None
        if args.outcome == "narrowed":
            scope_list = resolve_scope(args.scope, args.scope_file)
    except FileArgError as e:
        print("refused: {}".format(e), file=sys.stderr)
        return 1

    if args.outcome not in VALID_CONFIRMATION_OUTCOMES:
        return refuse_confirm(
            "--outcome must be one of {} (validation, SDR-15)".format(", ".join(VALID_CONFIRMATION_OUTCOMES)),
            args.pr_id, args.agent)

    previous_status = None
    try:
        with hc.guarded():
            path = record_path(root, args.pr_id)
            if not path.exists():
                print("refused: no such precedent record: {}".format(args.pr_id), file=sys.stderr)
                return 1
            rec = load_record_or_raise(path)

            # SDR-24.1: the publishing author never flips their own record's confirmation
            if args.agent == rec.get("published_by"):
                return refuse_confirm(
                    "the publishing author ({}) may never confirm/narrow/reject their own "
                    "record's scope (SDR-24.1)".format(args.agent), args.pr_id, args.agent)
            # SDR-24.2: record must be active
            if rec.get("status") != "active":
                return refuse_confirm(
                    "record {} status is '{}', not active (SDR-24.2)".format(args.pr_id, rec.get("status")),
                    args.pr_id, args.agent)
            # SDR-24.3: narrowed requires a scope restatement
            if args.outcome == "narrowed" and not scope_list:
                return refuse_confirm(
                    "--outcome narrowed requires a scope restatement via --scope/--scope-file "
                    "(SDR-24.3)", args.pr_id, args.agent)
            # SDR-24.4: mandatory reasoning
            if not note or not note.strip():
                return refuse_confirm(
                    "confirm requires --note or --note-file (SDR-24.4)", args.pr_id, args.agent)

            previous_status = rec.get("confirmation_status")
            rec["confirmation_status"] = args.outcome
            rec["confirmed_by"] = args.agent
            rec["confirmed_at"] = hc.now_iso()
            rec["confirmation_note"] = note
            rec["narrowed_scope"] = scope_list if args.outcome == "narrowed" else None
            hc.atomic_write_json(path, rec)
    except RegistryIntegrityError as e:
        return integrity_error(e.path, e)

    hc.log_event("precedent_scope_reviewed", pr=args.pr_id, agent=args.agent,
                 outcome=args.outcome, previous_confirmation_status=previous_status)
    print("confirmed {} scope outcome={} by {}".format(args.pr_id, args.outcome, args.agent))
    return 0


# --------------------------------------------------------------------------
# conflicts (T-342) -- on-demand conflict-detection pass, D6: pass not gate
# --------------------------------------------------------------------------
#
# Read-only, mirrors `cite`'s contract (see the T-342 DECISION block in the
# module docstring): never mutates the registry, never logs an event, never
# blocks/gates/slows any other CLI call. Five detectors, T-342 AC-2:
#   1. same-subject ratio contradiction between two ACTIVE records
#   2. an ACTIVE record citing an OVERRULED record as binding support
#   3. an overrules/voids relation by a lower-authority-tier acting record
#      against a higher-tier target (illegitimate per D4/SDR-17.8)
#   4. same-tier scope-condition overlap between two ACTIVE records with
#      divergent ratio
#   5. dangling citations (reuses iter_all_citation_resolutions, SDR-23/C-2)
#
# Detectors 1/2/4 operate only on ACTIVE records: a record that has already
# been overruled/superseded/voided is no longer live law, so a divergence
# involving it is history, not a conflict. Detector 3 scans every record
# regardless of current status -- the illegitimacy is a fact about how the
# relation was formed, not about what it later became. Detector 5 scans the
# whole registry, any status, matching `cite --all`.


def _related_pair(records_by_id, a, b):
    """True iff a and b acknowledge each other via a relations[] link (either
    direction) or a cites[] entry (either direction). Used by detectors 1
    and 4 to exclude disclosed divergence -- see the module docstring's
    DECISION note (SDR-12: the citation graph is what makes SILENT
    divergence detectable; an acknowledged disagreement is not silent)."""
    ra, rb = records_by_id[a], records_by_id[b]
    a_targets = set(rel.get("target") for rel in (ra.get("relations") or []))
    b_targets = set(rel.get("target") for rel in (rb.get("relations") or []))
    if b in a_targets or a in b_targets:
        return True
    if b in (ra.get("cites") or []) or a in (rb.get("cites") or []):
        return True
    return False


def _finding(detector, name, records, evidence):
    return {"detector": detector, "name": name, "records": list(records), "evidence": evidence}


def detect_subject_ratio_conflicts(records_by_id, active_ids):
    """Detector 1 (T-342 AC-2 item 1): two ACTIVE records whose ratio
    decisions contradict on the same subject key. Mechanical proxy for
    "contradict" (semantic judgment stays a verifier's job, R-6): same
    `subject`, both active, non-empty ratio text that differs verbatim, and
    no relation/cites link acknowledging the other -- an unreconciled,
    UNDISCLOSED divergent ruling on the same question (S-08's circuit-split
    shape, keyed on `subject` rather than scope-text overlap, per this
    task's own wording)."""
    findings = []
    by_subject = {}
    for pid in active_ids:
        subject = records_by_id[pid].get("subject")
        if subject:
            by_subject.setdefault(subject, []).append(pid)
    for subject, ids in by_subject.items():
        ids = sorted(ids)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                ratio_a = (records_by_id[a].get("ratio") or "").strip()
                ratio_b = (records_by_id[b].get("ratio") or "").strip()
                if not ratio_a or not ratio_b or ratio_a == ratio_b:
                    continue
                if _related_pair(records_by_id, a, b):
                    continue
                findings.append(_finding(
                    1, "subject-ratio-contradiction", [a, b],
                    "{} and {} are both ACTIVE with subject '{}', carry different ratios "
                    "({!r} vs {!r}), and no relations[]/cites[] link connects them -- an "
                    "undisclosed divergent ruling on the same subject".format(
                        a, b, subject, ratio_a, ratio_b)))
    return findings


def detect_overruled_cited_as_binding(records_by_id, active_ids):
    """Detector 2 (T-342 AC-2 item 2): an ACTIVE record citing an OVERRULED
    record as binding support -- `relations[].type == "follows"` or a
    `cites[]` entry pointing at a target whose current status is
    "overruled". `distinguishes` is excluded on purpose (see module
    docstring DECISION): distinguishing dead law is not reliance on it."""
    findings = []
    for pid in active_ids:
        rec = records_by_id[pid]
        supporting = set()
        for rel in (rec.get("relations") or []):
            if rel.get("type") == "follows" and rel.get("target"):
                supporting.add(rel["target"])
        for c in (rec.get("cites") or []):
            if PR_RE.match(c):
                supporting.add(c)
        for tgt in sorted(supporting):
            trec = records_by_id.get(tgt)
            if trec is not None and trec.get("status") == "overruled":
                findings.append(_finding(
                    2, "cites-overruled-as-binding-support", [pid, tgt],
                    "{} is ACTIVE and cites/follows {} as binding support, but {} was "
                    "overruled by {}".format(pid, tgt, tgt, trec.get("overruled_by"))))
    return findings


def detect_illegitimate_overrule_tier(records_by_id, all_ids):
    """Detector 3 (T-342 AC-2 item 3): an overrules/voids relation recorded
    by a LOWER-authority acting record (higher tier number) against a
    HIGHER-authority target (lower tier number) -- illegitimate per D4 and
    SDR-17.8. `publish` refuses this at write time, so this only fires
    against data that reached the registry outside that path (a corrupted
    or hand-edited record, or a legacy/tampered file) -- exactly the class
    of defect a registry-wide sweep exists to catch after the fact.
    Runs over every record regardless of current status: the illegitimacy
    is a fact about how the relation was formed."""
    findings = []
    for pid in sorted(all_ids):
        rec = records_by_id[pid]
        acting_tier = rec.get("authority_tier")
        for rel in (rec.get("relations") or []):
            if rel.get("type") not in ("overrules", "voids") or not rel.get("target"):
                continue
            trec = records_by_id.get(rel["target"])
            if trec is None:
                continue  # dangling target -- detector 5's job
            target_tier = trec.get("authority_tier")
            if not (isinstance(acting_tier, int) and isinstance(target_tier, int)):
                continue
            if acting_tier > target_tier:
                findings.append(_finding(
                    3, "illegitimate-overrule-lower-tier", [pid, rel["target"]],
                    "{} (tier {}) records relation type='{}' against {} (tier {}) -- a "
                    "higher tier number is LOWER authority, so a tier-{} record cannot "
                    "legitimately {} a tier-{} record (D4; SDR-17.8)".format(
                        pid, acting_tier, rel["type"], rel["target"], target_tier,
                        acting_tier, rel["type"], target_tier)))
    return findings


def detect_scope_overlap_conflicts(records_by_id, active_ids):
    """Detector 4 (T-342 AC-2 item 4): scope-condition overlap -- two
    ACTIVE records of the SAME authority tier claiming overlapping scope
    with divergent ratio, and (per the module docstring DECISION, applying
    the same disclosed-divergence exclusion as detector 1) no relations[]/
    cites[] link acknowledging the other."""
    findings = []
    by_tier = {}
    for pid in active_ids:
        tier = records_by_id[pid].get("authority_tier")
        by_tier.setdefault(tier, []).append(pid)
    for tier, ids in by_tier.items():
        ids = sorted(ids)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                scope_a = set(s.strip() for s in (records_by_id[a].get("scope_conditions") or []) if s.strip())
                scope_b = set(s.strip() for s in (records_by_id[b].get("scope_conditions") or []) if s.strip())
                overlap = scope_a & scope_b
                if not overlap:
                    continue
                ratio_a = (records_by_id[a].get("ratio") or "").strip()
                ratio_b = (records_by_id[b].get("ratio") or "").strip()
                if not ratio_a or not ratio_b or ratio_a == ratio_b:
                    continue
                if _related_pair(records_by_id, a, b):
                    continue
                findings.append(_finding(
                    4, "same-tier-scope-overlap", [a, b],
                    "{} and {} are both ACTIVE at tier {}, declare overlapping scope_conditions "
                    "{}, carry different ratios ({!r} vs {!r}), and no relations[]/cites[] link "
                    "connects them".format(a, b, tier, sorted(overlap), ratio_a, ratio_b)))
    return findings


def detect_dangling_citations(root, records=None):
    """Detector 5 (T-342 AC-2 item 5): dangling citations -- a PR-NNN, T-NNN,
    or any other SDR-10 token that does not resolve, registry-wide, any
    status. Reuses iter_all_citation_resolutions (`cite --all`'s core)
    rather than reimplementing it (SDR-23/C-2). This is the class the
    harness's own live integrity gap belongs to: a `tier_evidence`/`cites`
    entry of "P-023" never resolves, because `evolution.accepted_mutations`
    has no such entry (`.harness/context-brief-precedent-layer.md` sec 2.4,
    `state.json:791`) -- applied in code and prose, never logged in the
    ledger."""
    findings = []
    for pid, token, ok in iter_all_citation_resolutions(root, records):
        if not ok:
            findings.append(_finding(
                5, "dangling-citation", [pid],
                "{} cites token '{}' which does not resolve".format(pid, token)))
    return findings


def cmd_conflicts(args):
    """Registry-wide, on-demand conflict-detection sweep (T-342; D6: a pass,
    never a gate). Exit codes reuse SDR-15's fixed table verbatim (module
    docstring DECISION): 0 clean, 3 findings, 4 registry integrity error,
    2 usage error (argparse native)."""
    root = resolve_root(args)
    try:
        records = list(scan_registry(root))
    except RegistryIntegrityError as e:
        return integrity_error(e.path, e)

    records_by_id = dict(records)
    all_ids = list(records_by_id.keys())
    active_ids = [pid for pid in all_ids if records_by_id[pid].get("status") == "active"]

    findings = []
    findings += detect_subject_ratio_conflicts(records_by_id, active_ids)
    findings += detect_overruled_cited_as_binding(records_by_id, active_ids)
    findings += detect_illegitimate_overrule_tier(records_by_id, all_ids)
    findings += detect_scope_overlap_conflicts(records_by_id, active_ids)
    findings += detect_dangling_citations(root, records)

    if args.json:
        print(json.dumps(findings, indent=2, ensure_ascii=False))
    elif not findings:
        print("conflicts: 0 findings across {} record(s)".format(len(all_ids)))
    else:
        for f in findings:
            print("CONFLICT detector={} [{}] records={}: {}".format(
                f["detector"], f["name"], ",".join(f["records"]), f["evidence"]))
        print("{} conflict finding(s) across {} record(s)".format(len(findings), len(all_ids)))

    return 3 if findings else 0


# --------------------------------------------------------------------------
# argparse wiring
# --------------------------------------------------------------------------

def add_root_arg(parser):
    parser.add_argument("--root", default=None,
                         help="override the registry root (else PRECEDENT_ROOT env, "
                              "else .harness/precedents/) -- SDR-13")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    # ---- publish ----
    p_pub = sub.add_parser("publish", help="mint a new PR-NNN record")
    p_pub.add_argument("--agent", default=hc.agent_id())
    p_pub.add_argument("--task", required=True, help="issuing_task, T-NNN (not SDR-17-enumerated; "
                        "kept argparse-required, see module docstring DECISION)")
    p_pub.add_argument("--title", required=True)
    p_pub.add_argument("--subject", required=True)
    p_pub.add_argument("--tier", type=int, default=None)
    p_pub.add_argument("--tier-evidence", dest="tier_evidence", action="append", default=None)
    ratio_grp = p_pub.add_mutually_exclusive_group()
    ratio_grp.add_argument("--ratio", default=None)
    ratio_grp.add_argument("--ratio-file", dest="ratio_file", default=None)
    ratio_grp.add_argument("--ratio-stdin", dest="ratio_stdin", action="store_true", default=False)
    p_pub.add_argument("--dicta", action="append", default=None)
    scope_grp = p_pub.add_mutually_exclusive_group()
    scope_grp.add_argument("--scope", action="append", default=None)
    scope_grp.add_argument("--scope-file", dest="scope_file", default=None)
    p_pub.add_argument("--width", default=None, help="narrow | wide (SDR-17.5)")
    p_pub.add_argument("--revisit-trigger", dest="revisit_trigger", default=None,
                        help="required at tiers 1-3 (SDR-17.4)")
    p_pub.add_argument("--cites", action="append", default=None)
    p_pub.add_argument("--follows", action="append", default=None)
    p_pub.add_argument("--distinguishes", action="append", default=None)
    p_pub.add_argument("--distinguishing-facts", dest="distinguishing_facts", action="append", default=None)
    p_pub.add_argument("--distinguishing-facts-file", dest="distinguishing_facts_file",
                        action="append", default=None)
    p_pub.add_argument("--overrules", default=None)
    p_pub.add_argument("--factor", action="append", default=None,
                        help="one of {} (SDR-17.11)".format(", ".join(FACTOR_ENUM)))
    p_pub.add_argument("--factor-note", dest="factor_note", default=None)
    p_pub.add_argument("--factor-note-file", dest="factor_note_file", default=None)
    p_pub.add_argument("--acknowledge-reliance", dest="acknowledge_reliance",
                        action="store_true", default=False)
    p_pub.add_argument("--supersedes", default=None)
    p_pub.add_argument("--voids", default=None)
    p_pub.add_argument("--controlling-authority", dest="controlling_authority", default=None)
    add_root_arg(p_pub)
    p_pub.set_defaults(func=cmd_publish)

    # ---- show ----
    p_show = sub.add_parser("show", help="print one record + its binding summary")
    p_show.add_argument("pr_id", metavar="PR-NNN")
    add_root_arg(p_show)
    p_show.set_defaults(func=cmd_show)

    # ---- list ----
    p_list = sub.add_parser("list", help="one line per record, filterable")
    p_list.add_argument("--tier", type=int, default=None)
    p_list.add_argument("--status", default=None)
    p_list.add_argument("--subject", default=None)
    p_list.add_argument("--json", action="store_true", default=False)
    add_root_arg(p_list)
    p_list.set_defaults(func=cmd_list)

    # ---- cite ----
    p_cite = sub.add_parser("cite", help="resolve citation tokens; report dangling references")
    p_cite.add_argument("tokens", nargs="*")
    p_cite.add_argument("--record", default=None, metavar="PR-NNN")
    p_cite.add_argument("--all", action="store_true", default=False)
    add_root_arg(p_cite)
    p_cite.set_defaults(func=cmd_cite)

    # ---- confirm ----
    p_conf = sub.add_parser("confirm", help="scope-confirmation lifecycle (SDR-24/25)")
    p_conf.add_argument("pr_id", metavar="PR-NNN")
    p_conf.add_argument("--agent", default=hc.agent_id())
    p_conf.add_argument("--outcome", default=None)
    note_grp = p_conf.add_mutually_exclusive_group()
    note_grp.add_argument("--note", default=None)
    note_grp.add_argument("--note-file", dest="note_file", default=None)
    scope_grp2 = p_conf.add_mutually_exclusive_group()
    scope_grp2.add_argument("--scope", action="append", default=None)
    scope_grp2.add_argument("--scope-file", dest="scope_file", default=None)
    add_root_arg(p_conf)
    p_conf.set_defaults(func=cmd_confirm)

    # ---- conflicts (T-342, SDR-27's reserved name) ----
    p_conflicts = sub.add_parser(
        "conflicts", help="on-demand conflict-detection sweep (D6: pass, never a gate)")
    p_conflicts.add_argument("--json", action="store_true", default=False)
    add_root_arg(p_conflicts)
    p_conflicts.set_defaults(func=cmd_conflicts)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
