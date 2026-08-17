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
T-353's v2 fields (--sources, --validity, --code-version, --operation*)
follow the SAME convention, disclosed inline at each flag.

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
D4 forbids, so detector 3 checks both relation types.

AMENDED BY T-353 (V1-03/V1-49, carried defect ii): the v0 DECISION here used
to read "`supersedes` is deliberately excluded: SDR-17.8 never applies a
tier check to it." `docs/precedent-research/synthesis-v1-requirements.md`
V1-03 corrects that reach: SDR-17.8's tier-symmetry ratio was never meant to
protect every status-flipping verb except one, and T-347 Case C reproduced
the resulting bypass live (a tier-4, never-verdicted record flipped a
tier-1 record's `status` to `superseded`, exit 0, zero `conflicts`
findings -- PRECEDENT.md section 10.2/16 item 10). `supersedes` now gets the
ORDERING half of tier symmetry (acting tier number > target tier number ->
refusal, both at `publish` and in detector 3 below) but deliberately NOT
SDR-17.9's tier-4-target refusal: superseding replaces content rather than
overturning force, and the R-12 merge outcome
(`publish --supersedes X --cites Y`) must keep working at equal-or-higher
authority. See the T-353 section further down for the full citation trail.

---- T-353 additions (schema v2 core: sources, validity_conditions, typed
operations, interpretive_code_version, v1 dual-read, carried defects i/ii)
----------------------------------------------------------------------------

Implements exactly what `docs/precedent-research/synthesis-v1-requirements.md`
("V1-NN" ids below) fixes for T-353's slice of the precedent-layer-v1 epic:
the schema v2 field table (V1-10..V1-17), the citation-token grammar
extension (`doi:`/`decision:`, V1-18/V1-19), the corrective-sources
enforcement (A1, V1-11/V1-20/V1-21), typed operations and their
per-operation required-field matrix (A4, V1-13/V1-14), the task-anchored
overruling anchor mechanism (V1-31/V1-32), the `migrate` verb's mechanics
(V1-36/V1-37/V1-40 -- content-free; T-355 owns the live backfill content),
the v2 CLI surface in scope for this task (V1-41/V1-42/V1-45), and the two
carried defects from T-346 (V1-48 test-event isolation; V1-49 supersedes
tier check, see above). Does NOT implement graded force, decay, `stale`, or
the show/list v2 stdout lines (V1-22..V1-30, V1-34/V1-35, V1-43/V1-44 are
T-354's routing, per the synthesis's own task routing map, section 14).

DECISION (SCHEMA_VERSION stays frozen at 1; SCHEMA_VERSION_V2 = 2 is the new
write constant): `.harness/tests/test_precedent_seed.py` (owned by T-355,
this task may not edit it) asserts
`rec.get("schema_version") == precedent.SCHEMA_VERSION` against the LIVE,
still-unmigrated seed records (schema_version 1) -- that is the "ordering
invariant" board T-353 AC-3 names explicitly. Repurposing `SCHEMA_VERSION`
to mean "2" would break that pre-existing, unmodifiable assertion the
instant this file is imported, well before T-355 ever runs `migrate`
against the live root. The two constants are therefore kept distinct: the
old name stays bound to its old value (read by the one external test that
already depends on it); `SCHEMA_VERSION_V2` is the value every v2-aware
write path (`publish`, `migrate`) actually uses (V1-10 #2: "int, 2 on every
new publish; 1 tolerated read-only").

DECISION (event routing: `emit_event()` replaces direct `hc.log_event()`
calls, V1-06/V1-48 carried defect i): every event this file emits -- publish
success/refusal, confirm success/refusal, the flip events, dangling/gap
warnings, `precedent_migrated` -- now routes through the module-local
`emit_event(root, kind, **fields)` below rather than calling
`hc.log_event` directly. When the effective root (after --root/
PRECEDENT_ROOT/default resolution, unchanged SDR-13) is the live default
(`.harness/precedents/` under `hc.ROOT`), it still delegates to
`hc.log_event` verbatim -- the live substrate's behavior is byte-identical
to v1. Any OVERRIDDEN root (every test, every throwaway registry) instead
appends the same record shape to `<root>/events.jsonl` via the EXISTING
`hc.append_jsonl` -- no new log file on the live substrate, ever, and no
`harness_common` function signature changes (board T-353 AC-6's hard
constraint). Basis: T-346 measured ~598 synthetic events polluting the live
audit log from this file's own test suite; the synthesis's live
measurement at this epic's start (V1-28) found ~9,600 precedent-family
events against a 4-record live registry.

DECISION (v2 flags stay argparse-optional, manual-checked -- extends the v0
DECISION above verbatim): `--sources`, `--validity`, `--code-version`,
`--operation`, `--operation-subtype` are all required-by-the-synthesis but
NOT argparse `required=True`/`choices=`-constrained, for the identical
reason SDR-17's own fields are not: so a missing or malformed value takes
the SAME exit-1 REFUSAL path (V1-42's item numbering continues SDR-17's).

DECISION (`migrate` refusals are not event-logged): V1-46 states the v2
event-kind delta is exhaustive at exactly two new kinds --
`precedent_migrated` and `sources_delta_gap` -- with every other event
reusing SDR-26's existing nine. No migrate-refusal kind is named anywhere
in the synthesis. Inventing one (`precedent_migrate_refused`, say) would
contradict that explicit exhaustiveness claim; reusing `precedent_publish_
refused` would misattribute a migrate-time refusal to the publish verb.
`migrate` therefore refuses via stderr + exit 1 only (SDR-15's own exit-code
contract is the refusal signal), planner judgment, disclosed.

DEVIATION (module-docstring-only; no code effect): V1-33's exact `publish`
command for the A2 overruling record (row 5 of the T-358 ledger) is not
run by this task -- T-358 owns it. This file's `--reinterprets`/
`--overrules` decision:-anchor mechanics are built and tested against
synthetic `decision:T-NNN#anchor` fixtures in `test_precedent_v2.py`
instead, per T-353's own scope (it must not touch `.harness/precedents/`).

---- T-354 additions (graded force, decay, the `stale` staleness pass,
show/list v2 stdout rendering) ---------------------------------------------

Implements exactly what `docs/precedent-research/synthesis-v1-requirements.md`
fixes for T-354's slice of the precedent-layer-v1 epic: graded force
computed on read (A2, V1-22..V1-27), the activity-clock decay flag with its
calibrated N (A9.4, V1-28..V1-30), the `stale` validity-conditions pass
(A5, V1-34/V1-35), and the `show`/`list` v2 stdout contract (V1-43/V1-44).
Does NOT touch the schema v2 core, the citation grammar, typed operations,
`migrate`, or the two carried defects -- all T-353's, done, verified.

THE HARD CONSTRAINT THIS TASK MUST NOT VIOLATE (board T-354 AC-2): `cite`
never writes anything, including events (SDR-23's own words, quoted above:
"never writes anything, including events (C-2: signals are read-only
queries)"), so there is no cite-event stream in events.jsonl to count.
V1-23's own formula confirms this by construction: "No events.jsonl read;
no cite event exists or is needed (V1-04)." Every function below reads
ONLY registry-file data that `publish`/`confirm` already write: `status`,
`authority_tier`, `published_by`, `published_at`, `relations[]` (`type`,
`target`, `below_target_tier`), `operation.subtype`, `cited_by`, and the
root's own record list (via `scan_registry`). No new read of events.jsonl
is added anywhere in this section.

DECISION (force is computed on read, never stored -- A9.3, V1-22/V1-25):
no new field is added to the published record shape; `computed_force()`
takes the full `records_by_id` map of the SAME root (V1-27: "the SAME
registry root the verb was invoked with... No cross-root reads, ever") and
returns the level fresh on every call. `show`/`list` render it; nothing
ever writes it. Per board T-354 AC-6's own conditional: since force is
computed on read (not a stored field), the "confirm the SDR-01 immutability
amendment was published" branch does not apply -- confirmed and recorded in
the handoff, not silently skipped.

DECISION (`weakened_by`'s line position and tier scope, V1-24/V1-43): the
synthesis fixes four stdout lines (`force`, `decay`, `operation`,
`interpretive_code_version`) and separately says an effective weakening
valuation "adds one line" without pinning its exact position. Implemented
immediately after the `force` line (the line it explains), before `decay`.
V1-24's FORCE EFFECT ("a tier 1-3 target's force renders persuasive instead
of binding/settled") is applied only at tiers 1-3 inside `computed_force()`,
exactly as the V1-22 table scopes it; the `weakened_by` DISPLAY line,
however, is independent of tier (V1-24 defines "effective weakening
valuation" generically, with no tier restriction on the definition itself)
-- so a tier-4 record with a recorded, qualifying `revalues` relation still
shows `weakened_by`, it just never changes tier 4's already-floor force.
Disclosed since the synthesis does not spell out this tier-4 corner case.

DECISION (`list`'s new column literal, V1-44): "gains one column:
`force=<level>` inserted between the status and confirmation_status
columns" is read literally -- the CELL VALUE is the greppable token
`force=<level>` (matching the file's existing convention of greppable
`show` lines), with a plain `FORCE` header label above it, exactly as the
existing five columns pair a plain header with a plain value.

DECISION (multiple effective weakening valuations, no ordering given):
V1-24 does not say what happens when more than one active `revalues`
qualifies against the same target. `effective_weakening_valuation()` picks
the earliest by `(published_at, id)` -- the same deterministic tie-break
V1-23's own counter formula uses for `apps` -- so the choice is reproducible
across calls, disclosed as planner judgment (no research basis for a
different rule).

DECISION (`stale`'s summary counters, V1-34): "`stale: <K> reconsideration
candidate(s) across <R> record(s)`" does not define K/R precisely. Read by
analogy to the shipped `conflicts` summary line (`"{} conflict finding(s)
across {} record(s)".format(len(findings), len(all_ids))`, this same file,
`cmd_conflicts`): K = total finding LINES (one per failing checkable
validity entry, one per decay candidate -- V1-34's own two greppable line
shapes), R = total records scanned in the root, matching `conflicts`'
existing convention rather than inventing a new one.

DECISION (`stale` logs no event, mutates nothing -- board T-354 AC-5):
same class as `cite`/`conflicts` (SDR-23's own words; the `conflicts`
DECISION note above: "logging one would make `conflicts` the only read verb
in this file with a side effect"). `stale` is the sibling read verb V1-34
names it as; adding an event here would reintroduce exactly that asymmetry
for a second verb. No `emit_event` call exists anywhere in `cmd_stale` or
its helpers.

DECISION (`stale --json`'s "unchecked": true entries, V1-35): V1-35's own
words -- a free-text (non-checkable) `validity_conditions` entry is
"reported by `stale --json` as `"unchecked": true`, never flagged, never an
error". `list_unchecked_validity_entries()` builds exactly those entries;
`cmd_stale` appends them to the `--json` array AFTER the real findings, and
ONLY in `--json` mode -- text mode's two greppable line shapes (V1-34) and
the K/R summary counter (the DECISION above) are both defined purely in
terms of findings, so neither renders unchecked entries. They never affect
the exit code (0/3 still keys off `findings` alone, never `findings +
unchecked`).

---- T-370 additions (the displacement bridge: overrule-path enforcement,
AB5 / addendum II section A.3.1) ------------------------------------------

Implements EXACTLY `docs/precedent-research/synthesis-addendum-ii-spec.md`
section 3 (`AD2-30`..`AD2-39` below), enacted by the tier-1 record `PR-019`
(subject `displacement-bridge-embedding`, published by T-369 BEFORE this
code, per PR-017's record-before-code procedure -- confirmed active at
T-370's start). Every branch below cites its `AD2-NN` id in a comment.

AD2-30: five new, all-additive, argparse-optional `publish` flags --
`--overruled-ratio`/`--overruled-ratio-file`, `--overruled-record-id`,
`--overruled-published-by`, `--overruled-issuing-task`. No `choices=`, no
`required=True`: absence and malformation both take the manual exit-1
REFUSAL path, exactly the v0/T-353 DECISION at the top of this file.

AD2-31: no `-stdin` variant for `--overruled-ratio` (`--ratio-stdin`
already claims the one stdin stream `publish` can consume in a single
call; planner judgment, disclosed).

AD2-32: the stored field is `relations[i].overruled_predecessor`, an
object with exactly the four keys `record_id`/`ratio`/`published_by`/
`issuing_task`. `make_relation()` gains it with default `None` so it is
PRESENT on every relation object (the file's existing present-but-null
convention) and `null` unless `type == "overrules"`. Additive optional
field, NOT a schema-version bump (AD2-36): `SCHEMA_VERSION`/
`SCHEMA_VERSION_V2` are untouched.

AD2-33: for a `PR-NNN` target, all three authorship elements plus the
ratio are SUPPLIED by the publisher and VERIFIED against the target's own
stored fields -- byte-for-byte on the ratio (no strip, no normalization),
exact string match on `published_by`/`issuing_task`. Supplied-and-verified,
never auto-stamped: A.3.1 places the payment duty on the overruler, and an
auto-stamp would make the act free and unread (and would make the mandated
"each authorship element missing in turn" tests unwritable).

AD2-34: for a `decision:T-NNN#anchor` target (PR-009's own live target
`decision:T-344#R-2` is exactly this shape) there is no registry ratio and
no `published_by` to verify against, so the ruling is an ADAPTED embedding
with the unavailable element MARKED rather than absent or fabricated:
`--overruled-published-by` must be exactly the fixed marker string
`DECISION_ANCHOR_PUBLISHED_BY_MARKER`; `--overruled-issuing-task` must be
the anchor's own `T-NNN` half AND must resolve; the quoted ratio's fidelity
is a JUDGMENT check for a verifier, not mechanized here.

AD2-35: eleven refusal messages, verbatim, all routed through the existing
`refuse()` helper (exit 1, `precedent_publish_refused` -- no new event
kind, honoring V1-46's exhaustiveness claim).

AD2-37 (CHECK PLACEMENT): the embedding checks run inside the existing
`if rel["type"] == "overrules":` loop, immediately after the shipped
SDR-17.12 reliance-acknowledgement check and before the SDR-17.13 `voids`
controlling-authority loop -- so every shipped refusal keeps priority and
no pre-existing test that refuses EARLIER in the sequence changes its
message. DEVIATION, disclosed in the T-370 handoff: AD2-37 also claims "no
existing test's expected message changes... T-370's licence to amend
assertions stays unused on this path" -- that claim covers only tests that
refuse before this point; several pre-existing tests that previously
SUCCEEDED with `--overrules` now correctly require the new embedding flags
too, and are amended (listed in the handoff, one file -- test_precedent_
force.py -- outside the acceptance criteria's named three-file licence).

AD2-38 (OUT OF SCOPE, by design): `supersedes`/`voids` are NOT enforced --
AB5 delimits the enforcement to `--overrules` only; widening it is Phase-2
material (forwarded to the join as OQ-1), not a worker's judgment.

AD2-39: `conflicts` gains NO sixth detector for non-compliant historical
overrules -- PR-009 is the sole historical instance and AD2-40 (this
epic's own T-369/synthesis ruling) GRANDFATHERS it by name; a detector
whose entire population is already dispositioned would report the same
finding forever, the false-positive shape `PRECEDENT.md` section 9 already
names as fatal. The five shipped detectors stay five.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import harness_common as hc

# --------------------------------------------------------------------------
# Constants / schema vocabulary (section 2, 2.1, 2.2; T-353: V1-10)
# --------------------------------------------------------------------------

SCHEMA_VERSION = 1  # frozen -- see the module docstring DECISION note above.
SCHEMA_VERSION_V2 = 2  # V1-10 #2: every new publish/migrate writes this.
DEFAULT_ROOT = hc.HARNESS / "precedents"

VALID_TIERS = (1, 2, 3, 4)
VALID_STATUS = ("active", "overruled", "superseded", "void_per_incuriam")
VALID_WIDTH = ("narrow", "wide")
VALID_CONFIRMATION_OUTCOMES = ("confirmed", "narrowed", "rejected")
RELATION_TYPES = ("follows", "distinguishes", "overrules", "supersedes", "voids",
                  "reinterprets", "revalues")  # V1-07: last two added by T-353


class StoreOnce(argparse.Action):
    """Refuse a repeated single-value flag instead of silently keeping the last one.

    Defect T-376, found by the coordinator publishing PR-032: `publish` accepted
    `--voids A --voids B`, kept only B, exited 0, and wrote ONE relation where two were
    asked for. Silent discard of an explicit instruction, made permanent by an immutable
    record. The same defect family as a false-green test.

    A mechanical audit of `publish` found 33 flags with this exact shape, not one. Twelve
    flags on the same subcommand accumulate (`action="append"`), so the semantics were
    inconsistent and the trap was invisible from the outside: nothing in the help text
    distinguishes a flag that accumulates from one that overwrites.

    WHY REFUSE RATHER THAN ACCUMULATE. Accumulating the relation flags is not a one-line
    change: `--voids` pairs with `--controlling-authority`, and `--overrules`/`--revalues`
    pair with `--factor` and `--factor-note`, so accumulation needs occurrence-order
    pairing. This module's own docstring already carries a DEVIATION note about how
    fragile that pairing is for `--distinguishes`/`--distinguishing-facts`. A second
    fragile pairing surface is a worse trade than an explicit refusal. A record that must
    void two targets is published as two acts, and the tool now SAYS so.

    The sentinel lives in a set rather than testing `is not None`, because several of these
    flags have non-None defaults (`--operation` defaults to "determination") and a
    None-check would let those be silently overwritten -- the very bug being fixed.
    """

    SEEN = "_store_once_seen"

    def __call__(self, parser, namespace, values, option_string=None):
        seen = getattr(namespace, self.SEEN, None)
        if seen is None:
            seen = set()
            setattr(namespace, self.SEEN, seen)
        if self.dest in seen:
            parser.error(
                "{0} was given more than once and this flag takes a single value. Earlier "
                "versions silently kept only the last one, which discarded an explicit "
                "instruction into an immutable record (T-376). Supply {0} once. If you need "
                "two targets, publish two acts.".format(option_string or ("--" + self.dest)))
        seen.add(self.dest)
        setattr(namespace, self.dest, values)


def _refuse_repeats(*parsers):
    """Apply StoreOnce to every single-value flag on the given parsers.

    Applied uniformly rather than only to the relation flags T-376 named. Fixing five
    siblings and leaving 28 with the identical trap on the same subcommand is the shape of
    half-repair this registry keeps finding; and for a command that writes an immutable
    record, silently keeping the last of two explicit instructions is never the wanted
    behaviour. Flags that accumulate and boolean switches are left alone.
    """
    for parser in parsers:
        for action in parser._actions:
            if action.__class__ is argparse._StoreAction and action.option_strings:
                action.__class__ = StoreOnce
FACTOR_ENUM = ("reasoning_error", "unworkability", "doctrinal_change", "factual_change", "reliance")

# T-353, A4/V1-13: the typed-operation vocabulary.
OPERATION_TYPES = ("determination", "reinterpretation", "valuation")
OPERATION_SUBTYPES = {
    "determination": (None,),
    "reinterpretation": ("declarative", "corrective-restrictive", "corrective-extensive"),
    "valuation": ("obiter", "error-in-pronouncement", "context-change"),
}
CORRECTIVE_SUBTYPES = ("corrective-restrictive", "corrective-extensive")

# T-354, A2/V1-22: the graded-force enum, high to low. `force` is never a
# key on a record -- it is computed on read by computed_force() below.
FORCE_LEVELS = ("settled", "binding", "reiterated", "persuasive", "none")
# V1-22: "The reiteration threshold 3 is R-2's disclosed N=3, carried with
# its bracket". Revisable by ordinary code change WITH a DEVIATION note
# citing V1-22/R-2 -- it is calibration, not doctrine.
REITERATION_N = 3
# T-354, A9.4/V1-29: "N = 10, calibrated against the registry's real
# citation velocity" -- T-352's own recorded calibration reasoning (the
# full bracket argument, N=5 vs N=10 vs N=20, lives in V1-29). Revisable by
# ordinary code change WITH a DEVIATION note citing V1-29 -- calibration,
# not doctrine.
DECAY_N = 10

# T-370, AD2-34 (PR-019, A.3.1): the fixed marker a decision:-anchored
# overrule's --overruled-published-by must equal EXACTLY, character for
# character -- the only accepted value, since a decision: target has no
# registry published_by to embed and any other value would be a fabricated
# identity.
DECISION_ANCHOR_PUBLISHED_BY_MARKER = "unavailable: decision-anchored target has no published_by"

# relation type -> (status it stamps on the target, backref field it fills)
# NOTE: reinterprets/revalues are deliberately absent -- V1-07: "Neither ever
# flips the target's status ... it records a reading" / "changes force, not
# meaning".
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
# Citation token grammar (SDR-10; T-353 extends per V1-02: doi:, decision:)
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

# T-353, V1-18: external durable identifier. UNCHECKED by design (no network
# fetch exists in this harness's tool agency; a DOI's whole point is
# outliving local state -- docs/ is gitignored, memo OPEN-QUESTION/A9.5).
DOI_RE = re.compile(r"^doi:10\.\d{4,9}/[^\s#]+(#[A-Za-z0-9][A-Za-z0-9._-]*)?$")
# T-353, V1-19: task-anchored recorded decision. The T-NNN half resolves
# exactly like a plain T token; the fragment is UNCHECKED (may live in a
# gitignored doc; the task file is the durable anchor, D3/A9.1).
DECISION_RE = re.compile(r"^decision:T-\d{3,}#[A-Za-z0-9][A-Za-z0-9._-]*$")
DECISION_TASK_RE = re.compile(r"^decision:(T-\d{3,})#")
# T-353, V1-15: interpretive_code_version format. The migrate-only sentinel
# "pre-code" is checked separately (publish refuses it explicitly).
CODE_VERSION_RE = re.compile(r"^v\d+$")

# T-354, V1-35: the two mechanically-CHECKABLE forms a `validity_conditions`
# entry may take. `VALIDITY_FILE_LINE_RE` reuses SDR-10's own path-token
# regex (`PATH_RE`) verbatim -- "the file-line form" is the identical grammar
# already used for citation `path:lines` tokens; `VALIDITY_BAREPATH_RE` is
# new (a bare `path:` entry names a file OR a directory, unlike PATH_RE's
# file-plus-line-range). Every other entry is free text: unchecked, never
# flagged (V1-35's own "R-6 permanent non-goal" clause).
VALIDITY_FILE_LINE_RE = PATH_RE
VALIDITY_BAREPATH_RE = re.compile(r"^path:(\S+)$")


def token_kind(token):
    """Classify a citation token per SDR-10's grammar table, extended by
    T-353/V1-02 with `doi` and `decision`. None if none match."""
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
    if DOI_RE.match(token):
        return "doi"
    if DECISION_RE.match(token):
        return "decision"
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


def _decision_task_half_exists(token):
    """T-353, V1-19: resolve a `decision:T-NNN#anchor` token on its T-NNN
    half exactly as a plain T token resolves; the fragment is unchecked."""
    m = DECISION_TASK_RE.match(token)
    if not m:
        return False
    return (hc.TASKS / (m.group(1) + ".json")).exists()


def resolve_citation(token, root):
    """Read-only resolution of one citation token per SDR-10, extended by
    T-353/V1-18/V1-19. `root` is only consulted for PR-NNN tokens (the
    registry currently in scope)."""
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
    if kind == "doi":
        return True  # V1-18: UNCHECKED, never dangling, by design.
    if kind == "decision":
        return _decision_task_half_exists(token)
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


# --------------------------------------------------------------------------
# T-353: event routing (V1-06/V1-48, carried defect i)
# --------------------------------------------------------------------------

def is_live_root(root):
    """True iff `root` resolves to the live default `.harness/precedents/`.
    Works regardless of HOW that root was reached (no --root/PRECEDENT_ROOT
    at all, or either explicitly pointed back at the default) -- V1-48
    cares about the effective resolved path, not the mechanism."""
    try:
        return Path(root).resolve() == DEFAULT_ROOT.resolve()
    except OSError:
        return False


def _sidecar_events_path(root):
    return Path(root) / "events.jsonl"


def emit_event(root, kind, **fields):
    """V1-06/V1-48: every event emission in this file routes through here
    instead of calling hc.log_event directly. Live default root -> the
    live .harness/logs/events.jsonl via hc.log_event, byte-identical to v1.
    Any OVERRIDDEN root (every test, every throwaway registry) -> the same
    record shape appended to `<root>/events.jsonl` via the EXISTING
    hc.append_jsonl -- a sidecar that lives and dies with its throwaway
    root. No harness_common signature is touched."""
    if is_live_root(root):
        hc.log_event(kind, **fields)
        return
    record = {"ts": hc.now_iso(), "event": kind, "agent": hc.agent_id()}
    record.update(fields)
    hc.append_jsonl(_sidecar_events_path(root), record)


def refuse(event_kind, reason, root, **fields):
    """Log a refusal event (SDR-26) and print the message. Callers do
    `return refuse(...)` -- this function itself never exits the process,
    so `with hc.guarded():` blocks unwind and release their lock normally."""
    emit_event(root, event_kind, reason=reason, **fields)
    print("refused: " + reason, file=sys.stderr)
    return 1


# --------------------------------------------------------------------------
# publish
# --------------------------------------------------------------------------

def make_relation(rtype, target, distinguishing_facts=None, factors=None,
                   factor_note=None, controlling_authority=None,
                   target_tier_declared=None, overruled_predecessor=None):
    return {
        "type": rtype,
        "target": target,
        "distinguishing_facts": distinguishing_facts,
        "factors": factors or [],
        "factor_note": factor_note,
        "controlling_authority": controlling_authority,
        "target_tier_declared": target_tier_declared,  # V1-16, T-353
        # T-370, AD2-32 (PR-019, A.3.1): present on every relation object,
        # null unless type == "overrules" -- {record_id, ratio,
        # published_by, issuing_task} once populated by build_overruled_
        # predecessor() below. Additive optional field, not a schema bump.
        "overruled_predecessor": overruled_predecessor,
        "below_target_tier": None,  # stamped by the CLI once the target's tier is known
    }


def _decision_target_tier(target, args):
    """T-353, V1-16/V1-32: target_tier_declared is set from --target-tier
    iff the target is a decision:-anchored token; forbidden (stays None)
    otherwise."""
    if DECISION_RE.match(target or ""):
        return getattr(args, "target_tier", None)
    return None


def resolve_ratio(args):
    if args.ratio_stdin:
        return sys.stdin.buffer.read().decode("utf-8")
    if args.ratio_file:
        return read_file_text(args.ratio_file)
    return args.ratio or ""


def resolve_overruled_ratio(args):
    """T-370, AD2-30/AD2-31: bare plus -file only (no -stdin variant --
    --ratio-stdin already claims the one stdin stream a publish call can
    consume). Byte-exact utf-8 via the existing read_file_text, no
    stripping, so "verbatim" (A.3.1's own word) is never paraphrased.
    Returns None when neither flag is given (distinguished from an empty
    string so the AD2-33 presence check below can name the right defect)."""
    if args.overruled_ratio_file:
        return read_file_text(args.overruled_ratio_file)
    return args.overruled_ratio


def resolve_scope(scope_list_arg, scope_file_arg):
    if scope_file_arg:
        return [line.strip() for line in read_file_text(scope_file_arg).splitlines() if line.strip()]
    return list(scope_list_arg or [])


def resolve_validity(validity_list_arg, validity_file_arg):
    """T-353, V1-10 #28: same wire format as --scope-file (one non-empty,
    stripped entry per line)."""
    if validity_file_arg:
        return [line.strip() for line in read_file_text(validity_file_arg).splitlines() if line.strip()]
    return list(validity_list_arg or [])


def resolve_valuation_note(args):
    """T-353, V1-14: mandatory reasoning for any `valuation` publish."""
    if args.valuation_note_file:
        return read_file_text(args.valuation_note_file)
    return args.valuation_note


def assemble_relations(args):
    """Build the relations[] list from CLI args. Returns (relations, error)
    -- error is a plain string (never raised) so callers can route it
    through the same refuse() -> exit 1 path as every other SDR-17 check.

    T-353 adds `reinterprets` (V1-07/V1-13) and `revalues` (V1-07/V1-13) to
    the v0 five. `--revalues` accepts PR-NNN only (V1-19: decision: tokens
    are valid ONLY as overrules/reinterprets targets); `--reinterprets` and
    `--overrules` accept either PR-NNN or a decision:T-NNN#anchor token."""
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
                                        factors=list(args.factor or []), factor_note=factor_note,
                                        target_tier_declared=_decision_target_tier(args.overrules, args)))
    if args.supersedes:
        relations.append(make_relation("supersedes", args.supersedes))
    if args.voids:
        relations.append(make_relation("voids", args.voids, controlling_authority=args.controlling_authority))

    if args.reinterprets:
        relations.append(make_relation("reinterprets", args.reinterprets,
                                        target_tier_declared=_decision_target_tier(args.reinterprets, args)))
    if args.revalues:
        if not PR_RE.match(args.revalues):
            return None, ("--revalues target must be a PR-NNN record -- decision: tokens are "
                           "not valid revalues targets (V1-19)")
        factor_note = read_file_text(args.factor_note_file) if args.factor_note_file else args.factor_note
        relations.append(make_relation("revalues", args.revalues,
                                        factors=list(args.factor or []), factor_note=factor_note))

    return relations, None


def _target_tier_status(rel, target_cache):
    """T-353: (tier, status) for a relation's target, uniformly for PR-NNN
    (record lookup) and decision:-anchored (author-declared tier, no
    status to violate -> reported as 'active') targets. V1-19/V1-32."""
    tid = rel["target"]
    if DECISION_RE.match(tid):
        return rel.get("target_tier_declared"), "active"
    trec = target_cache.get(tid)
    if trec is None:
        return None, None
    return trec.get("authority_tier"), trec.get("status")


def build_overruled_predecessor(rel, target_cache, args, overruled_ratio, root):
    """T-370, AD2-30..AD2-35 (PR-019, A.3.1): the displacement-bridge
    embedding. `rel["type"]` is always "overrules" here (only caller-gated
    context). Returns (predecessor_dict, None) on success or (None,
    error_message) on the first violated check -- callers route the
    message through refuse() unchanged, exactly like every other SDR-17
    check in this file.

    Check order matches AD2-35's own numbering exactly:
      1-4: presence (ratio, record id, published_by, issuing task) --
           shared by BOTH a PR-NNN and a decision:-anchored target (AD2-33
           items 1-4; AD2-34's own item 1 restates check 1 for its case).
      5:   record id must name the --overrules target byte-for-byte --
           shared (AD2-33; also AD2-34 item 2, "the token IS the id").
      6-8: PR-NNN-target-only verification against the registry (AD2-33):
           ratio byte-exact, published_by exact, issuing_task exact.
      9-11: decision:-anchored-target-only ruling (AD2-34): the fixed
           marker, the T-NNN half, and its resolution.
    """
    target = rel["target"]
    is_decision = DECISION_RE.match(target) is not None

    # ---- checks 1-4 (AD2-33): presence, shared by both target kinds ----
    if overruled_ratio is None or not overruled_ratio.strip():
        return None, ("--overrules requires --overruled-ratio or --overruled-ratio-file: "
                       "the overruled ratio must be embedded verbatim (AD2-33)")
    if not args.overruled_record_id or not args.overruled_record_id.strip():
        return None, ("--overrules requires --overruled-record-id: authorship element "
                       "'record id' is missing (AD2-33)")
    if not args.overruled_published_by or not args.overruled_published_by.strip():
        return None, ("--overrules requires --overruled-published-by: authorship element "
                       "'published_by' is missing (AD2-33)")
    if not args.overruled_issuing_task or not args.overruled_issuing_task.strip():
        return None, ("--overrules requires --overruled-issuing-task: authorship element "
                       "'issuing task' is missing (AD2-33)")

    # ---- check 5 (AD2-33; AD2-34 item 2): record id names the target ----
    if args.overruled_record_id != target:
        return None, ("--overruled-record-id '{}' does not name the --overrules target "
                       "'{}' (AD2-33)".format(args.overruled_record_id, target))

    if not is_decision:
        # ---- checks 6-8 (AD2-33): PR-NNN target, byte-exact against the
        # registry. target is a key of target_cache by construction (item 6
        # already loaded every non-decision relation target before this
        # loop runs).
        target_rec = target_cache[target]
        if overruled_ratio != target_rec.get("ratio"):
            return None, ("embedded ratio does not match {}'s stored ratio byte-for-byte "
                           "(AD2-33)".format(target))
        if args.overruled_published_by != target_rec.get("published_by"):
            return None, ("--overruled-published-by '{}' does not match {}'s published_by "
                           "'{}' (AD2-33)".format(args.overruled_published_by, target,
                                                    target_rec.get("published_by")))
        if args.overruled_issuing_task != target_rec.get("issuing_task"):
            return None, ("--overruled-issuing-task '{}' does not match {}'s issuing_task "
                           "'{}' (AD2-33)".format(args.overruled_issuing_task, target,
                                                    target_rec.get("issuing_task")))
    else:
        # ---- checks 9-11 (AD2-34): decision:-anchored target ruling ----
        if args.overruled_published_by != DECISION_ANCHOR_PUBLISHED_BY_MARKER:
            return None, ("--overruled-published-by for the decision-anchored target {} must "
                           "be exactly: {} (AD2-34)".format(target, DECISION_ANCHOR_PUBLISHED_BY_MARKER))
        task_half = DECISION_TASK_RE.match(target).group(1)
        if args.overruled_issuing_task != task_half:
            return None, ("--overruled-issuing-task '{}' must be the T-NNN half of the "
                           "decision-anchored target {} (AD2-34)".format(
                               args.overruled_issuing_task, target))
        if not resolve_citation(args.overruled_issuing_task, root):
            return None, ("--overruled-issuing-task '{}' does not resolve against the tasks "
                           "store (AD2-34)".format(args.overruled_issuing_task))

    return {
        "record_id": args.overruled_record_id,
        "ratio": overruled_ratio,
        "published_by": args.overruled_published_by,
        "issuing_task": args.overruled_issuing_task,
    }, None


def cmd_publish(args):
    root = resolve_root(args)

    try:
        ratio = resolve_ratio(args)
        scope_list = resolve_scope(args.scope, args.scope_file)
        validity_list = resolve_validity(args.validity, args.validity_file)
        valuation_note = resolve_valuation_note(args)
        overruled_ratio = resolve_overruled_ratio(args)  # T-370, AD2-30
        relations, rel_err = assemble_relations(args)
    except FileArgError as e:
        print("refused: {}".format(e), file=sys.stderr)
        return 1
    if rel_err:
        return refuse("precedent_publish_refused", rel_err, root, task=args.task)

    dicta_list = list(args.dicta or [])
    cites_list = list(args.cites or [])
    te_list = list(args.tier_evidence or [])
    sources_list = list(args.sources or [])
    subject = args.subject
    title = args.title
    tier = args.tier
    width = args.width
    revisit_trigger = args.revisit_trigger
    operation_type = args.operation
    operation_subtype = args.operation_subtype
    code_version = args.code_version

    # ---- SDR-17 items 1-5: pure argument-shape checks, no registry needed ----
    if not ratio.strip():
        return refuse("precedent_publish_refused", "ratio must be non-empty (SDR-17.1)", root, task=args.task)
    if not SUBJECT_RE.match(subject or ""):
        return refuse("precedent_publish_refused",
                       "subject '{}' must match the slug regex ^[a-z0-9-]+$ (SDR-17.2)".format(subject),
                       root, task=args.task)
    if len(title) > 80:
        return refuse("precedent_publish_refused", "title exceeds 80 chars (SDR-17.2)", root, task=args.task)
    if tier not in VALID_TIERS:
        return refuse("precedent_publish_refused", "tier must be one of 1,2,3,4 (SDR-17.3)", root, task=args.task)
    if not te_list:
        return refuse("precedent_publish_refused", "tier_evidence must be non-empty (SDR-17.3)", root, task=args.task)
    if not tier_evidence_kind_ok(tier, te_list):
        return refuse("precedent_publish_refused",
                       "tier_evidence for tier {} lacks a required token kind "
                       "(section 3 table, SDR-17.3)".format(tier), root, task=args.task)
    if tier in (1, 2, 3):
        if not scope_list:
            return refuse("precedent_publish_refused",
                           "scope_conditions must be non-empty at tiers 1-3 (SDR-17.4)", root, task=args.task)
        if not revisit_trigger or not revisit_trigger.strip():
            return refuse("precedent_publish_refused",
                           "revisit_trigger must be non-empty at tiers 1-3 (SDR-17.4)", root, task=args.task)
    if width not in VALID_WIDTH:
        return refuse("precedent_publish_refused",
                       "declared_width must be 'narrow' or 'wide' (SDR-17.5)", root, task=args.task)
    for rel in relations:
        if rel["type"] in ("overrules", "revalues"):
            for f in rel["factors"]:
                if f not in FACTOR_ENUM:
                    return refuse("precedent_publish_refused",
                                   "--factor '{}' is not one of {} (SDR-17.11's factor enum)"
                                   .format(f, ", ".join(FACTOR_ENUM)), root, task=args.task)

    # ---- T-353, V1-42 items 16-24: NEW v2 pure argument-shape checks --------

    # V1-11/V1-20: sources mandatory on every publish; corrective acts get
    # a distinct, A1-naming message (board T-353 AC-4's mandated observable).
    if not sources_list:
        is_corrective_relation = any(rel["type"] in ("overrules", "voids") for rel in relations)
        is_corrective_reinterpretation = (operation_type == "reinterpretation"
                                           and operation_subtype in CORRECTIVE_SUBTYPES)
        if is_corrective_relation or is_corrective_reinterpretation:
            return refuse("precedent_publish_refused",
                           "corrective act cites no sources (A1, V1-20)", root, task=args.task)
        return refuse("precedent_publish_refused",
                       "sources must be non-empty (A1, V1-11)", root, task=args.task)

    # V1-10 #28: validity_conditions required non-empty at tiers 1-3.
    if tier in (1, 2, 3) and not validity_list:
        return refuse("precedent_publish_refused",
                       "validity_conditions must be non-empty at tiers 1-3 (A5, V1-10 #28)",
                       root, task=args.task)

    # V1-15: --code-version format; the migrate-only sentinel is refused here.
    if not code_version:
        return refuse("precedent_publish_refused",
                       "--code-version is required, format ^v\\d+$ (A3, V1-15)", root, task=args.task)
    if code_version == "pre-code":
        return refuse("precedent_publish_refused",
                       "--code-version 'pre-code' is the migrate-only sentinel; publish refuses "
                       "it (V1-15)", root, task=args.task)
    if not CODE_VERSION_RE.match(code_version):
        return refuse("precedent_publish_refused",
                       "--code-version '{}' must match ^v\\d+$ (V1-15)".format(code_version),
                       root, task=args.task)

    # V1-13: operation/subtype coherence.
    if operation_type not in OPERATION_TYPES:
        return refuse("precedent_publish_refused",
                       "--operation must be one of {} (A4, V1-13)".format(", ".join(OPERATION_TYPES)),
                       root, task=args.task)
    allowed_subtypes = OPERATION_SUBTYPES[operation_type]
    if operation_type == "determination":
        if operation_subtype is not None:
            return refuse("precedent_publish_refused",
                           "operation determination's subtype must be null -- omit "
                           "--operation-subtype (V1-13)", root, task=args.task)
    else:
        if operation_subtype not in allowed_subtypes:
            return refuse("precedent_publish_refused",
                           "--operation-subtype for {} must be one of {} (V1-13)".format(
                               operation_type, ", ".join(s for s in allowed_subtypes if s)),
                           root, task=args.task)

    # V1-14: relation/operation incoherence -- a record may never carry an
    # untyped operation or a blob conflating determination/reinterpretation/
    # valuation (board T-353 AC-5).
    has_reinterprets_rel = any(r["type"] == "reinterprets" for r in relations)
    has_revalues_rel = any(r["type"] == "revalues" for r in relations)
    if operation_type == "determination" and (has_reinterprets_rel or has_revalues_rel):
        return refuse("precedent_publish_refused",
                       "a determination may never carry a reinterprets/revalues relation "
                       "(A4; addendum sec.2; V1-14)", root, task=args.task)
    if operation_type == "reinterpretation" and not has_reinterprets_rel:
        return refuse("precedent_publish_refused",
                       "reinterpretation requires exactly one --reinterprets relation (V1-14)",
                       root, task=args.task)
    if operation_type == "valuation" and not has_revalues_rel:
        return refuse("precedent_publish_refused",
                       "valuation requires exactly one --revalues relation (V1-14)",
                       root, task=args.task)
    if operation_type != "reinterpretation" and has_reinterprets_rel:
        return refuse("precedent_publish_refused",
                       "a --reinterprets relation requires --operation reinterpretation (V1-14)",
                       root, task=args.task)
    if operation_type != "valuation" and has_revalues_rel:
        return refuse("precedent_publish_refused",
                       "a --revalues relation requires --operation valuation (V1-14)",
                       root, task=args.task)

    # V1-14: valuation's mandatory note + the error-in-pronouncement factor.
    if operation_type == "valuation":
        if not valuation_note or not valuation_note.strip():
            return refuse("precedent_publish_refused",
                           "valuation requires --valuation-note or --valuation-note-file (V1-14)",
                           root, task=args.task)
        if operation_subtype == "error-in-pronouncement" and "reasoning_error" not in (args.factor or []):
            return refuse("precedent_publish_refused",
                           "valuation subtype error-in-pronouncement requires --factor "
                           "reasoning_error (V1-14)", root, task=args.task)

    # V1-32/V1-42.24: --target-tier required iff any relation is decision:-
    # anchored; a decision: token is valid ONLY as an overrules/reinterprets
    # target (V1-19).
    if args.target_tier is not None and args.target_tier not in VALID_TIERS:
        return refuse("precedent_publish_refused",
                       "--target-tier must be one of 1,2,3,4", root, task=args.task)
    for rel in relations:
        if DECISION_RE.match(rel["target"]):
            if rel["type"] not in ("overrules", "reinterprets"):
                return refuse("precedent_publish_refused",
                               "a decision: token is valid only as an overrules/reinterprets "
                               "target, not '{}' (V1-19, V1-42.24)".format(rel["type"]),
                               root, task=args.task)
            if rel.get("target_tier_declared") is None:
                return refuse("precedent_publish_refused",
                               "relation target {} is decision:-anchored and requires "
                               "--target-tier (V1-32, V1-42.24)".format(rel["target"]),
                               root, task=args.task)

    # ---- SDR-17 items 6-14 (registry-dependent) + SDR-19 commit, ONE guard ----
    same_subject_missing = []
    dangling_tokens = []
    side_effects = []
    sources_delta_target = None
    new_id = None
    try:
        with hc.guarded():
            target_cache = {}

            # item 6, extended per V1-19: every relation target must resolve.
            # decision:-anchored targets resolve on their T-NNN half against
            # .harness/tasks/, exactly as a plain T token would.
            for rel in relations:
                tid = rel["target"]
                if DECISION_RE.match(tid):
                    m = DECISION_TASK_RE.match(tid)
                    if not (hc.TASKS / (m.group(1) + ".json")).exists():
                        return refuse("precedent_publish_refused",
                                       "relation target {} does not resolve: {} not found "
                                       "under .harness/tasks/ (V1-19)".format(tid, m.group(1)),
                                       root, task=args.task)
                    continue
                p = record_path(root, tid)
                if not p.exists():
                    return refuse("precedent_publish_refused",
                                   "relation target {} does not resolve to an existing record "
                                   "(SDR-17.6)".format(tid), root, task=args.task)
                if tid not in target_cache:
                    target_cache[tid] = load_record_or_raise(p)

            # item 7: distinguishes needs non-empty facts + non-empty target scope
            # (distinguishes never has a decision: target -- refused above.)
            for rel in relations:
                if rel["type"] == "distinguishes":
                    if not (rel.get("distinguishing_facts") or "").strip():
                        return refuse("precedent_publish_refused",
                                       "distinguishes against {} requires non-empty "
                                       "distinguishing_facts (SDR-17.7)".format(rel["target"]),
                                       root, task=args.task)
                    if not target_cache[rel["target"]].get("scope_conditions"):
                        return refuse("precedent_publish_refused",
                                       "cannot distinguish against {}: target's scope_conditions "
                                       "is empty (SDR-17.7)".format(rel["target"]), root, task=args.task)

            # items 8-9: overrules/voids tier symmetry + tier-4-target refusal,
            # generalized to read the target's tier via _target_tier_status so
            # decision:-anchored targets are checked against target_tier_declared
            # (V1-32) uniformly with real records.
            for rel in relations:
                if rel["type"] in ("overrules", "voids"):
                    tgt_tier, _tgt_status = _target_tier_status(rel, target_cache)
                    if tier > (tgt_tier or 0):
                        return refuse("precedent_publish_refused",
                                       "{} of {} refused: acting tier {} is lower authority than "
                                       "target tier {} (SDR-17.8)".format(rel["type"], rel["target"],
                                                                           tier, tgt_tier),
                                       root, task=args.task)
                    if tgt_tier == 4:
                        return refuse("precedent_publish_refused",
                                       "{} of {} refused: target is tier 4 -- a category error, cite "
                                       "or distinguish instead (SDR-17.9)".format(rel["type"], rel["target"]),
                                       root, task=args.task)

            # NEW (T-353, carried defect ii, V1-03/V1-49): supersedes gets
            # the ORDERING half of tier symmetry only -- no tier-4-target
            # refusal (V1-03's own reasoning: the R-12 merge outcome must
            # keep working). supersedes never has a decision:-anchored
            # target (refused earlier), so target_cache always has it.
            for rel in relations:
                if rel["type"] == "supersedes":
                    tgt = target_cache[rel["target"]]
                    tgt_tier = tgt.get("authority_tier")
                    if tier > (tgt_tier or 0):
                        return refuse("precedent_publish_refused",
                                       "supersedes of {} refused: acting tier {} is lower "
                                       "authority than target tier {} (carried defect ii; "
                                       "V1-03/V1-49)".format(rel["target"], tier, tgt_tier),
                                       root, task=args.task)

            # NEW (T-353, V1-14): reinterprets/revalues target-active check,
            # and corrective reinterpretation's tier violations (acting tier
            # number > target tier number; target tier == 4). Declarative
            # reinterpretation carries NO tier-order refusal -- it may target
            # any active record regardless of tier (below_target_tier makes
            # it persuasive-only for its own author, S-02's shape).
            for rel in relations:
                if rel["type"] == "reinterprets":
                    tgt_tier, tgt_status = _target_tier_status(rel, target_cache)
                    if tgt_status is not None and tgt_status != "active":
                        return refuse("precedent_publish_refused",
                                       "reinterprets of {} refused: target status is '{}', not "
                                       "active (V1-14)".format(rel["target"], tgt_status),
                                       root, task=args.task)
                    if operation_subtype in CORRECTIVE_SUBTYPES:
                        if tier > (tgt_tier or 0):
                            return refuse("precedent_publish_refused",
                                           "corrective reinterpretation of {} refused: acting "
                                           "tier {} exceeds target tier {} (addendum sec.3 "
                                           "'sufficient authority level'; V1-14)".format(
                                               rel["target"], tier, tgt_tier), root, task=args.task)
                        if tgt_tier == 4:
                            return refuse("precedent_publish_refused",
                                           "corrective reinterpretation of {} refused: target is "
                                           "tier 4 -- a category error (V1-14)".format(rel["target"]),
                                           root, task=args.task)
                if rel["type"] == "revalues":
                    _tgt_tier, tgt_status = _target_tier_status(rel, target_cache)
                    if tgt_status is not None and tgt_status != "active":
                        return refuse("precedent_publish_refused",
                                       "revalues of {} refused: target status is '{}', not "
                                       "active (V1-14)".format(rel["target"], tgt_status),
                                       root, task=args.task)

            # item 10: overrules/supersedes/voids need an active target.
            # decision:-anchored targets have no status to violate --
            # _target_tier_status reports "active" for them uniformly (V1-32).
            for rel in relations:
                if rel["type"] in ("overrules", "supersedes", "voids"):
                    _t, tgt_status = _target_tier_status(rel, target_cache)
                    if tgt_status != "active":
                        return refuse("precedent_publish_refused",
                                       "{} of {} refused: target status is '{}', not active "
                                       "(SDR-17.10)".format(rel["type"], rel["target"], tgt_status),
                                       root, task=args.task)

            # item 11 (+ section 2.2 factor_note rule) and item 12 (reliance
            # ack) -- generalized to use _target_tier_status so a
            # decision:-anchored overrules of a declared tier-3 target also
            # requires a factor (V1-32). No --acknowledge-reliance check for
            # decision: targets: "no cited_by exists to measure reliance
            # against" (V1-32).
            for rel in relations:
                if rel["type"] == "overrules":
                    tgt_tier, _s = _target_tier_status(rel, target_cache)
                    if tgt_tier == 3 and not rel["factors"]:
                        return refuse("precedent_publish_refused",
                                       "overrules of tier-3 target {} requires >=1 --factor "
                                       "(SDR-17.11)".format(rel["target"]), root, task=args.task)
                    if rel["factors"] and not (rel.get("factor_note") or "").strip():
                        return refuse("precedent_publish_refused",
                                       "overrules with --factor requires --factor-note or "
                                       "--factor-note-file (section 2.2 field table)", root, task=args.task)
                    if not DECISION_RE.match(rel["target"]):
                        tgt = target_cache[rel["target"]]
                        if tgt.get("cited_by") and not args.acknowledge_reliance:
                            return refuse("precedent_publish_refused",
                                           "overrules of {} refused: target is cited_by {} -- pass "
                                           "--acknowledge-reliance after reviewing the blast radius "
                                           "(SDR-17.12)".format(rel["target"], tgt.get("cited_by")),
                                           root, task=args.task)

                    # ---- T-370, AD2-30..AD2-35 (PR-019, A.3.1): the ----
                    # displacement-bridge embedding. Runs immediately after
                    # SDR-17.12 (reliance ack) and before SDR-17.13 (voids
                    # controlling-authority), per AD2-37's check placement.
                    predecessor, embed_err = build_overruled_predecessor(
                        rel, target_cache, args, overruled_ratio, root)
                    if embed_err:
                        return refuse("precedent_publish_refused", embed_err, root, task=args.task)
                    rel["overruled_predecessor"] = predecessor
                if rel["type"] == "revalues" and rel["factors"] and not (rel.get("factor_note") or "").strip():
                    return refuse("precedent_publish_refused",
                                   "revalues with --factor requires --factor-note or "
                                   "--factor-note-file (section 2.2 field table)", root, task=args.task)

            # item 13: voids requires a resolvable controlling_authority
            for rel in relations:
                if rel["type"] == "voids":
                    ca = rel.get("controlling_authority")
                    if not ca or not resolve_citation(ca, root):
                        return refuse("precedent_publish_refused",
                                       "voids of {} requires --controlling-authority with a "
                                       "resolvable token (SDR-17.13)".format(rel["target"]), root, task=args.task)

            # item 14 (generalized to every relation type via the tier
            # helper, so reinterprets/revalues and decision:-anchored
            # targets get below_target_tier too -- V1-16, V1-32).
            for rel in relations:
                tgt_tier, _s = _target_tier_status(rel, target_cache)
                rel["below_target_tier"] = tier > (tgt_tier or 0)

            # item 15 is satisfied by construction: no CLI path sets confirmation_*.

            # NEW (T-353, V1-21): the sources-delta check -- warning, never
            # a refusal. Only meaningful against a PR-NNN target (a
            # decision:-anchored target has no sources/cites to diff, V1-21
            # "the check is SKIPPED").
            for rel in relations:
                if (rel["type"] == "reinterprets" and operation_subtype in CORRECTIVE_SUBTYPES
                        and not DECISION_RE.match(rel["target"])):
                    trec = target_cache.get(rel["target"])
                    if trec is not None:
                        target_sources = set(trec.get("sources") or [])
                        target_cites = set(trec.get("cites") or [])
                        delta = set(sources_list) - (target_sources | target_cites)
                        if not delta:
                            sources_delta_target = rel["target"]

            # SDR-18: S-09 citation-completeness scan (mandatory, non-blocking)
            covered = set(cites_list) | set(rel["target"] for rel in relations)
            try:
                for pid, rec in scan_registry(root):
                    if (rec.get("subject") == subject and rec.get("status") == "active"
                            and rec.get("authority_tier") in (1, 2, 3) and pid not in covered):
                        same_subject_missing.append(pid)
            except RegistryIntegrityError as e:
                return integrity_error(e.path, e)

            # SDR-18/SDR-12/V1-11: dangling cites/tier_evidence/sources tokens
            # (non-blocking). doi: tokens never appear here (resolve_citation
            # always returns True for them, V1-18).
            for token in cites_list + te_list + sources_list:
                if not resolve_citation(token, root):
                    dangling_tokens.append(token)

            # SDR-19: commit
            new_id = allocate_next_id(root)
            record = {
                "id": new_id,
                "schema_version": SCHEMA_VERSION_V2,
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
                "sources": sources_list,
                "validity_conditions": validity_list,
                "operation": {"type": operation_type, "subtype": operation_subtype},
                "interpretive_code_version": code_version,
            }
            hc.atomic_write_json(record_path(root, new_id), record)

            # SDR-19.3/19.4: cited_by back-references + status flips on targets.
            # decision:-anchored targets get NEITHER: "no cited_by side
            # effect (nothing to append to)" (V1-32).
            targets_touch = {}
            for rel in relations:
                tid = rel["target"]
                if DECISION_RE.match(tid):
                    continue
                entry = targets_touch.setdefault(tid, {"cited_by": False, "flip": None})
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
    emit_event(root, "precedent_published", agent=args.agent, id=new_id, tier=tier,
               subject=subject, issuing_task=args.task)
    for rtype, tid in side_effects:
        emit_event(root, FLIP_EVENT[rtype], agent=args.agent, id=tid, by=new_id)
    for token in dangling_tokens:
        emit_event(root, "dangling_reference", record=new_id, token=token)
    if dangling_tokens:
        print("warning: {} dangling citation token(s): {}".format(
            len(dangling_tokens), ", ".join(dangling_tokens)))
    if same_subject_missing:
        emit_event(root, "citation_gap", record=new_id, subject=subject, missing=same_subject_missing)
        print("warning: citation-completeness gap -- active tier 1-3 record(s) sharing subject "
              "'{}' not cited: {}".format(subject, ", ".join(same_subject_missing)))
    if sources_delta_target:
        emit_event(root, "sources_delta_gap", record=new_id, target=sources_delta_target)
        print("warning: corrective act cites nothing the target did not already consult (V1-21)")
    print("published {}".format(new_id))
    return 0


# --------------------------------------------------------------------------
# T-354: graded force, computed on read (A2, V1-22..V1-27)
# --------------------------------------------------------------------------

def qualifying_applications_count(pr_id, records_by_id):
    """V1-23: the qualifying-applications counter C(PR-X), verbatim.
    Reads ONLY relations[] on OTHER records, those records' status/
    published_by/published_at, operation.subtype, and the target's own id
    -- no events.jsonl, no cite event (V1-04/V1-23: "No events.jsonl read;
    no cite event exists or is needed")."""
    x = records_by_id.get(pr_id) or {}
    published_by_x = x.get("published_by")
    apps = []
    for other_id, other in records_by_id.items():
        if other_id == pr_id:
            continue
        if other.get("status") != "active":
            continue
        if other.get("published_by") == published_by_x:
            continue  # no self-reiteration (P-011's authorship-governs logic)
        for rel in (other.get("relations") or []):
            if rel.get("target") != pr_id:
                continue
            if rel.get("below_target_tier") is not False:
                continue  # a lower-tier claim is persuasive only for its author (S-02)
            if rel.get("type") not in ("follows", "reinterprets", "distinguishes"):
                continue
            apps.append((other.get("published_at") or "", other_id, other, rel))
    apps.sort(key=lambda t: (t[0], t[1]))

    c = 0
    for _ts, _oid, other, rel in apps:
        rtype = rel.get("type")
        if rtype == "follows":
            c += 1
        elif rtype == "reinterprets":
            subtype = (other.get("operation") or {}).get("subtype")
            if subtype == "declarative":
                c += 1  # applying the ratio to a new case IS a consistent application
            elif isinstance(subtype, str) and subtype.startswith("corrective"):
                c = 0  # zeroing -- R-3, carried
        elif rtype == "distinguishes":
            c = 0  # zeroing -- R-3, carried
    return c


def effective_weakening_valuations(pr_id, records_by_id):
    """V1-24: every ACTIVE record V with operation.type=='valuation',
    subtype in {error-in-pronouncement, context-change}, carrying a
    `revalues` relation at PR-X with below_target_tier==False. Returns a
    list of (published_at, other_id, other_record, subtype) sorted by the
    same (published_at, id) tie-break V1-23's own counter uses."""
    out = []
    for other_id, other in records_by_id.items():
        if other.get("status") != "active":
            continue
        op = other.get("operation") or {}
        if op.get("type") != "valuation":
            continue
        subtype = op.get("subtype")
        if subtype not in ("error-in-pronouncement", "context-change"):
            continue
        for rel in (other.get("relations") or []):
            if (rel.get("type") == "revalues" and rel.get("target") == pr_id
                    and rel.get("below_target_tier") is False):
                out.append((other.get("published_at") or "", other_id, other, subtype))
                break
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def effective_weakening_valuation(pr_id, records_by_id):
    """The single effective weakening valuation `computed_force` and
    `show`'s `weakened_by` line consume -- the earliest by (published_at,
    id) when more than one qualifies (module docstring DECISION). None if
    none qualify. Returns (other_id, other_record, subtype)."""
    apps = effective_weakening_valuations(pr_id, records_by_id)
    if not apps:
        return None
    _ts, other_id, other, subtype = apps[0]
    return other_id, other, subtype


def computed_force(pr_id, rec, records_by_id):
    """V1-22's enum table, computed fresh on every call -- NEVER stored
    (A9.3, V1-25). Returns (level, c) where level is one of FORCE_LEVELS
    and c is the qualifying-applications count (meaningful only when level
    is 'settled' or 'reiterated', per V1-43's own rendering rule)."""
    if rec.get("status") != "active":
        return "none", 0
    tier = rec.get("authority_tier")
    c = qualifying_applications_count(pr_id, records_by_id)
    if tier in (1, 2, 3):
        # V1-24: an effective weakening valuation renders persuasive
        # instead of binding/settled, REGARDLESS of C -- the table's
        # persuasive row is unconditioned on C for the weakened case.
        if effective_weakening_valuation(pr_id, records_by_id) is not None:
            return "persuasive", c
        if c >= REITERATION_N:
            return "settled", c
        return "binding", c
    # tier 4 (or a malformed/out-of-range tier -- SDR-06 gives it no other
    # home; the enum's tier-4 row is the only floor this file defines):
    if c >= REITERATION_N:
        return "reiterated", c
    return "persuasive", c


# --------------------------------------------------------------------------
# T-354: decay -- the activity clock (A9.4, V1-28..V1-30)
# --------------------------------------------------------------------------

def decay_clock(rec, records_by_id):
    """V1-28: the count of records in the SAME root with `published_at`
    strictly greater than rec's. Batch-mates (identical published_at)
    never count toward each other's clocks -- comparing a timestamp to
    itself is never '>', so no self-exclusion special-case is needed."""
    ts = rec.get("published_at") or ""
    return sum(1 for other in records_by_id.values() if (other.get("published_at") or "") > ts)


def is_decay_candidate(rec, records_by_id):
    """V1-29: an ACTIVE record at tier 1-3 with cited_by EMPTY whose clock
    is >= DECAY_N is a DECAY CANDIDATE. Tier 4 is NEVER decay-flagged (R-16:
    "the registry's summer" is a legitimate permanent mode). Returns
    (is_candidate, M) -- M is always the clock value, even when not a
    candidate, so callers needing the raw count never recompute it."""
    m = decay_clock(rec, records_by_id)
    if rec.get("status") != "active":
        return False, m
    if rec.get("authority_tier") not in (1, 2, 3):
        return False, m
    if rec.get("cited_by"):
        return False, m
    return m >= DECAY_N, m


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


def effective_operation(rec):
    """V1-36 dual-read default: a schema_version-1 record has no
    `operation` key -- reads as an IMPLIED determination (every v1 record
    recorded what binds; none reinterprets or revalues anything)."""
    op = rec.get("operation")
    if op is None:
        return {"type": "determination", "subtype": None}
    return op


def operation_line(rec):
    """V1-43: `operation: <type>[/<subtype>][ (implied, schema v1)]`."""
    if rec.get("operation") is None:
        return "operation: determination (implied, schema v1)"
    op = rec["operation"]
    otype, osub = op.get("type"), op.get("subtype")
    if osub:
        return "operation: {}/{}".format(otype, osub)
    return "operation: {}".format(otype)


def interpretive_code_version_line(rec):
    """V1-43: `interpretive_code_version: <value | (none, schema v1)>`."""
    v = rec.get("interpretive_code_version")
    if v is None:
        return "interpretive_code_version: (none, schema v1)"
    return "interpretive_code_version: {}".format(v)


def force_line(pr_id, rec, records_by_id):
    """V1-43: `force: <level>[ (consistent applications: <C>)]`, with the
    `(status: <status>)` suffix reserved for level 'none'."""
    level, c = computed_force(pr_id, rec, records_by_id)
    if level == "none":
        return "force: none (status: {})".format(rec.get("status"))
    if level in ("settled", "reiterated"):
        return "force: {} (consistent applications: {})".format(level, c)
    return "force: {}".format(level)


def decay_line(rec, records_by_id):
    """V1-43: `decay: <none | RECONSIDERATION CANDIDATE (...)>`."""
    candidate, m = is_decay_candidate(rec, records_by_id)
    if candidate:
        return ("decay: RECONSIDERATION CANDIDATE (0 citations after {} subsequent "
                "publications; threshold {})".format(m, DECAY_N))
    return "decay: none"


def cmd_show(args):
    # T-353, V1-36 dual-read: the record JSON + binding-summary line render
    # exactly as they always did for a schema_version-1 record. T-354 adds
    # the four v2 stdout lines below (V1-43) plus the conditional
    # weakened_by line (V1-24) -- see the module docstring DECISION on its
    # position.
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

    # T-354, V1-22..V1-30/V1-43: graded force + decay + operation/code
    # version. Computed over the WHOLE root (V1-27), not just this record.
    try:
        records_by_id = dict(scan_registry(root))
    except RegistryIntegrityError as e:
        return integrity_error(e.path, e)
    print(force_line(args.pr_id, rec, records_by_id))
    weakening = effective_weakening_valuation(args.pr_id, records_by_id)
    if weakening is not None:
        other_id, _other_rec, subtype = weakening
        print("weakened_by: {} (valuation/{})".format(other_id, subtype))
    print(decay_line(rec, records_by_id))
    print(operation_line(rec))
    print(interpretive_code_version_line(rec))
    return 0


# --------------------------------------------------------------------------
# list
# --------------------------------------------------------------------------

def cmd_list(args):
    # T-353, V1-36 dual-read: unchanged from v1 for the record scan/filter.
    # T-354, V1-44: gains the FORCE column (text) and the force/
    # decay_candidate/operation/interpretive_code_version keys (--json).
    root = resolve_root(args)
    try:
        records = list(scan_registry(root))
    except RegistryIntegrityError as e:
        return integrity_error(e.path, e)
    # T-354, V1-27: force/decay computed over the WHOLE root, BEFORE
    # filtering -- a filtered-out record can still be another's reiteration.
    records_by_id = dict(records)

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
        out = []
        for pid, rec in filtered:
            level, _c = computed_force(pid, rec, records_by_id)
            candidate, _m = is_decay_candidate(rec, records_by_id)
            out.append({
                "id": pid, "authority_tier": rec.get("authority_tier"), "status": rec.get("status"),
                "confirmation_status": rec.get("confirmation_status"), "subject": rec.get("subject"),
                "title": rec.get("title"),
                "force": level,
                "decay_candidate": candidate,
                "operation": effective_operation(rec),
                "interpretive_code_version": rec.get("interpretive_code_version"),
            })
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print("{:<8} {:<5} {:<16} {:<14} {:<14} {:<24} {}".format(
            "ID", "TIER", "STATUS", "FORCE", "CONFIRM", "SUBJECT", "TITLE"))
        for pid, rec in filtered:
            level, _c = computed_force(pid, rec, records_by_id)
            print("{:<8} {:<5} {:<16} {:<14} {:<14} {:<24} {}".format(
                pid, rec.get("authority_tier"), rec.get("status"), "force={}".format(level),
                rec.get("confirmation_status"), str(rec.get("subject"))[:24], str(rec.get("title"))[:60]))
    return 0


# --------------------------------------------------------------------------
# cite
# --------------------------------------------------------------------------

def _record_citation_tokens(rec):
    """T-353, V1-45: walks `sources` in addition to the v1 field walk.
    Dual-read safe: a schema_version-1 record simply has no `sources` key,
    `.get()` yields None -> []."""
    tokens = list(rec.get("cites") or [])
    tokens.extend(rec.get("tier_evidence") or [])
    tokens.extend(rec.get("sources") or [])
    for rel in (rec.get("relations") or []):
        if rel.get("target"):
            tokens.append(rel["target"])
        if rel.get("controlling_authority"):
            tokens.append(rel["controlling_authority"])
    return tokens


def _cite_status_label(token, ok):
    """T-353, V1-45: `doi:` tokens print EXTERNAL (unchecked) and never
    count as dangling (V1-18); `decision:` tokens resolve on their T-NNN
    half and print the fragment as unchecked (V1-19)."""
    kind = token_kind(token)
    if kind == "doi":
        return "EXTERNAL (unchecked)"
    if kind == "decision":
        return ("OK (fragment unchecked)" if ok else "DANGLING (fragment unchecked)")
    return "OK" if ok else "DANGLING"


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
    events (C-2: signals are read-only queries). T-353/V1-45: doi:/decision:
    tokens render via _cite_status_label; doi: never counts as dangling."""
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
            print("{} cites {}: {}".format(pid, token, _cite_status_label(token, ok)))
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
            print("{} cites {}: {}".format(args.record, token, _cite_status_label(token, ok)))
            if not ok:
                dangling += 1
    else:
        for token in args.tokens:
            total += 1
            ok = resolve_citation(token, root)
            print("{}: {}".format(token, _cite_status_label(token, ok)))
            if not ok:
                dangling += 1

    if dangling:
        print("{} of {} citation(s) dangling".format(dangling, total))
        return 3
    return 0


# --------------------------------------------------------------------------
# confirm
# --------------------------------------------------------------------------

def refuse_confirm(reason, pr_id, agent, root):
    emit_event(root, "precedent_confirm_refused", pr=pr_id, agent=agent, reason=reason)
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
            args.pr_id, args.agent, root)

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
                    "record's scope (SDR-24.1)".format(args.agent), args.pr_id, args.agent, root)
            # SDR-24.2: record must be active
            if rec.get("status") != "active":
                return refuse_confirm(
                    "record {} status is '{}', not active (SDR-24.2)".format(args.pr_id, rec.get("status")),
                    args.pr_id, args.agent, root)
            # SDR-24.3: narrowed requires a scope restatement
            if args.outcome == "narrowed" and not scope_list:
                return refuse_confirm(
                    "--outcome narrowed requires a scope restatement via --scope/--scope-file "
                    "(SDR-24.3)", args.pr_id, args.agent, root)
            # SDR-24.4: mandatory reasoning
            if not note or not note.strip():
                return refuse_confirm(
                    "confirm requires --note or --note-file (SDR-24.4)", args.pr_id, args.agent, root)

            previous_status = rec.get("confirmation_status")
            rec["confirmation_status"] = args.outcome
            rec["confirmed_by"] = args.agent
            rec["confirmed_at"] = hc.now_iso()
            rec["confirmation_note"] = note
            rec["narrowed_scope"] = scope_list if args.outcome == "narrowed" else None
            hc.atomic_write_json(path, rec)
    except RegistryIntegrityError as e:
        return integrity_error(e.path, e)

    emit_event(root, "precedent_scope_reviewed", pr=args.pr_id, agent=args.agent,
               outcome=args.outcome, previous_confirmation_status=previous_status)
    print("confirmed {} scope outcome={} by {}".format(args.pr_id, args.outcome, args.agent))
    return 0


# --------------------------------------------------------------------------
# migrate (T-353, V1-36..V1-40) -- schema_version 1 -> 2, mechanics only
# --------------------------------------------------------------------------

def cmd_migrate(args):
    """V1-37: a CLI subcommand (not a one-shot script), content-free --
    T-353 builds the VERB, T-355 supplies the CONTENT (--backfill) and
    runs it against the live root. Inside ONE hc.guarded() block: scan for
    schema_version==1 records, validate EVERY one's backfill entry before
    writing ANY of them (all-or-nothing, V1-37), then write exactly the
    four v2 fields (sources, validity_conditions, operation,
    interpretive_code_version) plus schema_version=2 -- no other key is
    added, removed, or altered. Idempotent: a second run finds zero v1
    records and is a byte-identical no-op."""
    root = resolve_root(args)
    try:
        backfill_text = read_file_text(args.backfill)
    except FileArgError as e:
        print("refused: {}".format(e), file=sys.stderr)
        return 1
    try:
        backfill = json.loads(backfill_text)
    except json.JSONDecodeError as e:
        print("refused: --backfill file is not valid JSON: {}".format(e), file=sys.stderr)
        return 1
    if not isinstance(backfill, dict):
        print("refused: --backfill JSON must be an object mapping PR-NNN -> "
              "{sources, validity_conditions}", file=sys.stderr)
        return 1

    migrated = []
    try:
        with hc.guarded():
            records = list(scan_registry(root))
            to_migrate = [(pid, rec) for pid, rec in records if rec.get("schema_version") == 1]

            # ---- validation pass: all-or-nothing (V1-37) ----
            for pid, rec in to_migrate:
                entry = backfill.get(pid)
                if not isinstance(entry, dict):
                    print("refused: --backfill has no entry for {} (schema_version 1, requires "
                          "migration) -- writing nothing (V1-37 all-or-nothing)".format(pid),
                          file=sys.stderr)
                    return 1
                sources_tok = entry.get("sources")
                if (not isinstance(sources_tok, list) or not sources_tok
                        or any(token_kind(t) is None for t in sources_tok)):
                    print("refused: {}'s backfill 'sources' must be a non-empty list of "
                          "grammar-valid citation tokens (V1-37)".format(pid), file=sys.stderr)
                    return 1
                if rec.get("authority_tier") in (1, 2, 3):
                    vc = entry.get("validity_conditions")
                    if not isinstance(vc, list) or not vc:
                        print("refused: {}'s backfill 'validity_conditions' must be a non-empty "
                              "list at tiers 1-3 (V1-37)".format(pid), file=sys.stderr)
                        return 1

            # ---- commit pass: exactly the four v2 fields, byte-identical
            # otherwise (board T-355's own content-preservation contract) ----
            for pid, rec in to_migrate:
                entry = backfill[pid]
                rec["sources"] = list(entry["sources"])
                rec["validity_conditions"] = list(entry.get("validity_conditions") or [])
                rec["operation"] = {"type": "determination", "subtype": None}
                rec["interpretive_code_version"] = "pre-code"
                rec["schema_version"] = SCHEMA_VERSION_V2
                hc.atomic_write_json(record_path(root, pid), rec)
                migrated.append(pid)
    except RegistryIntegrityError as e:
        return integrity_error(e.path, e)

    for pid in migrated:
        emit_event(root, "precedent_migrated", agent=args.agent, record=pid,
                   from_version=1, to_version=2,
                   authority="A1 (doi:10.22201/iij.24487937e.2026.20.20316#3) via A9.2")
    if migrated:
        print("migrated {} record(s): {}".format(len(migrated), ", ".join(migrated)))
    else:
        print("migrate: no schema_version 1 records found (no-op)")
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
#   3. an overrules/voids/supersedes relation by a lower-authority-tier
#      acting record against a higher-tier target (illegitimate per D4/
#      SDR-17.8; supersedes added by T-353 per V1-03/V1-49, carried defect
#      ii -- see the module docstring's AMENDED note)
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
    """Detector 3 (T-342 AC-2 item 3; widened by T-353 per V1-03/V1-49,
    carried defect ii): an overrules/voids/supersedes relation recorded by
    a LOWER-authority acting record (higher tier number) against a
    HIGHER-authority target (lower tier number) -- illegitimate per D4 and
    SDR-17.8 (overrules/voids) or V1-03 (supersedes). `publish` refuses
    this at write time, so this only fires against data that reached the
    registry outside that path (a corrupted or hand-edited record, or a
    legacy/tampered file) -- exactly the class of defect a registry-wide
    sweep exists to catch after the fact. Runs over every record regardless
    of current status: the illegitimacy is a fact about how the relation
    was formed."""
    findings = []
    for pid in sorted(all_ids):
        rec = records_by_id[pid]
        acting_tier = rec.get("authority_tier")
        for rel in (rec.get("relations") or []):
            if rel.get("type") not in ("overrules", "voids", "supersedes") or not rel.get("target"):
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
                    "legitimately {} a tier-{} record (D4; SDR-17.8 for overrules/voids, "
                    "V1-03/V1-49 for supersedes)".format(
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
    ledger. T-353/V1-18: `doi:` tokens never appear here (always resolve)."""
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
# T-354: `stale` -- the validity-conditions staleness pass (A5, V1-34/V1-35)
# --------------------------------------------------------------------------

def _validity_entry_checkable_kind(entry):
    """V1-35: classify a `validity_conditions` entry. Returns 'file-line',
    'bare-path', or None (free text -- unchecked, never flagged)."""
    if not isinstance(entry, str):
        return None
    if VALIDITY_FILE_LINE_RE.match(entry):
        return "file-line"
    if VALIDITY_BAREPATH_RE.match(entry):
        return "bare-path"
    return None


def _check_validity_entry(entry):
    """V1-35: evaluate one CHECKABLE entry. Returns (ok, reason|None). Only
    meaningful when `_validity_entry_checkable_kind(entry)` is not None."""
    m = VALIDITY_FILE_LINE_RE.match(entry)
    if m:
        relpath, rangepart = m.group(1), m.group(2)
        p = Path(relpath)
        if not p.is_absolute():
            p = hc.ROOT / p
        if not p.exists():
            return False, "file does not exist"
        upper = int(rangepart.split("-", 1)[1]) if "-" in rangepart else int(rangepart)
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                line_count = sum(1 for _ in f)
        except OSError as e:
            return False, "file could not be read: {}".format(e)
        if line_count < upper:
            return False, "file has {} line(s), fewer than the declared upper bound {}".format(
                line_count, upper)
        return True, None
    m = VALIDITY_BAREPATH_RE.match(entry)
    if m:
        relpath = m.group(1)
        p = Path(relpath)
        if not p.is_absolute():
            p = hc.ROOT / p
        if not p.exists():
            return False, "path does not exist"
        return True, None
    return True, None  # unreachable: callers gate on _validity_entry_checkable_kind first


def check_validity_conditions(records_by_id):
    """V1-34 check V: per ACTIVE record, evaluate each CHECKABLE
    validity_conditions entry (V1-35); >=1 failing entry makes the record a
    reconsideration candidate, one finding per failing entry. v1 records
    under dual-read have no validity_conditions -- check V skips them
    (V1-34: "never a finding, never an error"). Read-only: mutates nothing,
    logs nothing (same class as `cite`/`conflicts`)."""
    findings = []
    for pid in sorted(records_by_id):
        rec = records_by_id[pid]
        if rec.get("status") != "active":
            continue
        for entry in (rec.get("validity_conditions") or []):
            if _validity_entry_checkable_kind(entry) is None:
                continue
            ok, reason = _check_validity_entry(entry)
            if not ok:
                findings.append({"check": "V", "name": "validity-condition-failed",
                                  "record": pid, "entry": entry, "reason": reason})
    return findings


def check_decay(records_by_id):
    """V1-34 check D / V1-29: one finding per decay-candidate record."""
    findings = []
    for pid in sorted(records_by_id):
        candidate, m = is_decay_candidate(records_by_id[pid], records_by_id)
        if candidate:
            findings.append({"check": "D", "name": "decay-candidate", "record": pid,
                              "subsequent_publications": m, "threshold": DECAY_N})
    return findings


def list_unchecked_validity_entries(records_by_id):
    """V1-35's own words, exact: free-text (non-checkable) validity_conditions
    entries on ACTIVE records are "reported by `stale --json` as
    `\"unchecked\": true`, never flagged, never an error". These are NOT
    findings -- they never affect the exit code or the K counter in the text
    summary (module docstring DECISION on K/R: "K = total finding LINES...",
    which this deliberately excludes) -- so `cmd_stale` keeps them in a
    separate list and only `--json` mode renders them, appended after the
    real findings."""
    entries = []
    for pid in sorted(records_by_id):
        rec = records_by_id[pid]
        if rec.get("status") != "active":
            continue
        for entry in (rec.get("validity_conditions") or []):
            if _validity_entry_checkable_kind(entry) is not None:
                continue
            entries.append({"check": "V", "name": "validity-condition-unchecked",
                             "record": pid, "entry": entry, "unchecked": True})
    return entries


def render_stale_finding(f):
    """V1-34's two greppable line shapes, verbatim."""
    if f["check"] == "V":
        return "STALE check=V [validity-condition-failed] {}: '{}' -- {}".format(
            f["record"], f["entry"], f["reason"])
    return ("STALE check=D [decay-candidate] {}: cited_by empty after {} subsequent "
            "publications (threshold {})".format(
                f["record"], f["subsequent_publications"], f["threshold"]))


def cmd_stale(args):
    """T-354, V1-34: the validity-conditions staleness pass -- a SIBLING
    read verb, not a sixth `conflicts` detector (`conflicts` is record-vs-
    record contradiction; `stale` is record-vs-ENVIRONMENT drift, A5).
    READ-ONLY in the full cite/conflicts sense: mutates nothing, logs NO
    event (module docstring DECISION) -- the registry is byte-identical
    before and after any run (board T-354 AC-5). Findings FLAG
    reconsideration candidates and nothing else: no status change, no
    auto-expiry, ever (A5; addendum sec.6). Exit codes reuse SDR-15
    verbatim: 0 clean, 3 findings, 2 usage (argparse native), 4 registry
    integrity error."""
    root = resolve_root(args)
    try:
        records = list(scan_registry(root))
    except RegistryIntegrityError as e:
        return integrity_error(e.path, e)
    records_by_id = dict(records)

    findings = check_validity_conditions(records_by_id) + check_decay(records_by_id)

    if args.json:
        # V1-35: free-text validity_conditions entries are reported in
        # --json as "unchecked": true, appended after the real findings --
        # they are never findings themselves (excluded from the exit code
        # and from the text-mode K/R summary; see list_unchecked_validity_
        # entries's own docstring).
        unchecked = list_unchecked_validity_entries(records_by_id)
        print(json.dumps(findings + unchecked, indent=2, ensure_ascii=False))
    else:
        for f in findings:
            print(render_stale_finding(f))
        print("stale: {} reconsideration candidate(s) across {} record(s)".format(
            len(findings), len(records_by_id)))

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
    p_pub.add_argument("--overrules", default=None, metavar="PR-NNN|decision:T-NNN#anchor")
    p_pub.add_argument("--factor", action="append", default=None,
                        help="one of {} (SDR-17.11)".format(", ".join(FACTOR_ENUM)))
    p_pub.add_argument("--factor-note", dest="factor_note", default=None)
    p_pub.add_argument("--factor-note-file", dest="factor_note_file", default=None)
    p_pub.add_argument("--acknowledge-reliance", dest="acknowledge_reliance",
                        action="store_true", default=False)
    # ---- T-370, AD2-30 (PR-019, A.3.1): the displacement-bridge embedding ----
    p_pub.add_argument("--overruled-ratio", dest="overruled_ratio", default=None,
                        help="the --overrules target's ratio, embedded verbatim (AD2-33)")
    p_pub.add_argument("--overruled-ratio-file", dest="overruled_ratio_file", default=None,
                        help="byte-exact utf-8, no stripping; no -stdin form (AD2-30/AD2-31)")
    p_pub.add_argument("--overruled-record-id", dest="overruled_record_id", default=None,
                        help="authorship element 'record id' (AD2-33)")
    p_pub.add_argument("--overruled-published-by", dest="overruled_published_by", default=None,
                        help="authorship element 'published_by' (AD2-33/AD2-34)")
    p_pub.add_argument("--overruled-issuing-task", dest="overruled_issuing_task", default=None,
                        help="authorship element 'issuing task' (AD2-33/AD2-34)")
    p_pub.add_argument("--supersedes", default=None)
    p_pub.add_argument("--voids", default=None)
    p_pub.add_argument("--controlling-authority", dest="controlling_authority", default=None)
    # ---- T-353 v2 additions ----
    p_pub.add_argument("--sources", action="append", default=None,
                        help="required >=1, any V1-02 citation-grammar token (A1, V1-11)")
    validity_grp = p_pub.add_mutually_exclusive_group()
    validity_grp.add_argument("--validity", action="append", default=None,
                               help="required non-empty at tiers 1-3 (A5, V1-10 #28)")
    validity_grp.add_argument("--validity-file", dest="validity_file", default=None)
    p_pub.add_argument("--operation", default="determination",
                        help="determination|reinterpretation|valuation, default determination "
                             "(A4, V1-13)")
    p_pub.add_argument("--operation-subtype", dest="operation_subtype", default=None,
                        help="required iff --operation != determination (V1-13)")
    p_pub.add_argument("--reinterprets", default=None, metavar="PR-NNN|decision:T-NNN#anchor",
                        help="exactly one iff --operation reinterpretation (V1-14)")
    p_pub.add_argument("--revalues", default=None, metavar="PR-NNN",
                        help="exactly one iff --operation valuation; PR-NNN only (V1-14, V1-19)")
    valnote_grp = p_pub.add_mutually_exclusive_group()
    valnote_grp.add_argument("--valuation-note", dest="valuation_note", default=None)
    valnote_grp.add_argument("--valuation-note-file", dest="valuation_note_file", default=None)
    p_pub.add_argument("--code-version", dest="code_version", default=None,
                        help="required, ^v\\d+$ -- names INTERPRETIVE-CODE.md's Version line "
                             "(A3, V1-15)")
    p_pub.add_argument("--target-tier", dest="target_tier", type=int, default=None,
                        help="required iff any relation target is decision:-anchored (V1-32)")
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

    # ---- migrate (T-353, V1-36..V1-40) ----
    p_migrate = sub.add_parser(
        "migrate", help="schema_version 1 -> 2 in-place migration (V1-37; once-only "
                         "exception to SDR-01/V1-01)")
    p_migrate.add_argument("--agent", default=hc.agent_id())
    p_migrate.add_argument("--backfill", required=True, metavar="FILE.json",
                            help="JSON object {'PR-NNN': {'sources': [...], "
                                 "'validity_conditions': [...]}, ...}")
    add_root_arg(p_migrate)
    p_migrate.set_defaults(func=cmd_migrate)

    # ---- stale (T-354, V1-34/V1-35) ----
    p_stale = sub.add_parser(
        "stale", help="validity-conditions staleness pass (A5/addendum sec.6; V1-34) -- "
                       "read-only, flags reconsideration candidates, never auto-expiry")
    p_stale.add_argument("--json", action="store_true", default=False)
    add_root_arg(p_stale)
    p_stale.set_defaults(func=cmd_stale)

    # T-376: refuse a repeated single-value flag rather than silently keeping the last.
    # Applied to `publish` and `confirm`, the two verbs that write a record; `--root` and
    # the read-only verbs are left alone so a repeated --root in a wrapper still behaves.
    _refuse_repeats(p_pub, p_conf)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
