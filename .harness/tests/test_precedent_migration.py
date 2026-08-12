"""Unit tests for T-355's migration of PR-001..PR-004 to schema v2
(`.harness/bin/precedent.py migrate`, per `docs/precedent-research/
synthesis-v1-requirements.md` V1-36..V1-40/V1-38 and
`.harness/coordinator-decisions-addendum.md` A1/A9.2).

This is the CONTENT half of the migration: T-353 built the `migrate` verb's
mechanics (all-or-nothing, guarded, idempotent) and owns its generic tests
in `test_precedent_v2.py::MigrateVerbTests` -- against synthetic temp
roots, never the live registry. This file owns the opposite half: did THIS
task's real invocation, against the LIVE `.harness/precedents/` root with
T-355's own backfill content, actually do the right thing to the four real
seed records -- content preservation (AC-3), idempotency of the real run
(AC-4), touch-nothing-but-the-four (AC-5), the sources ledger's grammar
validity and real-origin resolution (AC-2), and that no state.json/
blackboard.json write path exists in `migrate` at all (AC-7).

Content-preservation is checked against `git show <commit>:...` -- the same
independent replay path the board task's own acceptance criteria names for
the verifier -- not against an in-memory "before" this file could get
wrong. T-364 note: this was originally `git show HEAD:...`, correct only
while T-355's migration stayed uncommitted; commit f89a7f0 later committed
that work and moved HEAD to already hold the migrated v2 records, so the
pre-migration baseline below is pinned to the immutable v0 commit
(V0_BASELINE_COMMIT) instead -- see git_show_v0.
"""
import hashlib
import importlib.util
import inspect
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PRECEDENT_PY = ROOT / ".harness" / "bin" / "precedent.py"
LIVE_REGISTRY = ROOT / ".harness" / "precedents"
LIVE_README = LIVE_REGISTRY / "README.md"
LIVE_STATE = ROOT / ".harness" / "state.json"
LIVE_BLACKBOARD = ROOT / ".harness" / "blackboard.json"
LIVE_EVENTS = ROOT / ".harness" / "logs" / "events.jsonl"

# Load precedent.py as a module so schema checks reuse ITS OWN vocabulary
# (token_kind, resolve_citation, SCHEMA_VERSION_V2) -- same convention as
# test_precedent_seed.py.
if str(PRECEDENT_PY.parent) not in sys.path:
    sys.path.insert(0, str(PRECEDENT_PY.parent))
_spec = importlib.util.spec_from_file_location("precedent_under_test_migration", str(PRECEDENT_PY))
precedent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(precedent)


def run(*args):
    """Invoke the real CLI against the LIVE registry explicitly (--root
    pinned), matching test_precedent_seed.py's own convention."""
    cmd = [sys.executable, str(PRECEDENT_PY)] + list(args) + ["--root", str(LIVE_REGISTRY)]
    return subprocess.run(cmd, text=True, capture_output=True)


def load_record(pr_id):
    return json.loads((LIVE_REGISTRY / (pr_id + ".json")).read_text(encoding="utf-8"))


def git_show_head(relpath):
    """Fetch a tracked file's content as of HEAD. Used only for checks that
    are genuinely about "has anything changed since the last commit" (e.g.
    TouchNothingButTheFourTests.test_readme_is_unchanged) -- NOT for the
    pre-migration (v1) baseline; see git_show_v0 below for that."""
    result = subprocess.run(["git", "show", "HEAD:" + relpath], cwd=str(ROOT),
                             capture_output=True, text=True, check=True)
    return result.stdout


# T-364 repair: HEAD is a moving anchor, not a fixed one. This suite's
# ContentPreservationTests used to read the pre-migration (v1) baseline via
# `git show HEAD:...`, which was correct only while T-355's migrated v2
# records stayed uncommitted. Commit f89a7f0 ("Precedent layer v1") landed
# that work and moved HEAD to already hold the migrated v2 content, so a
# HEAD-relative "before" diffed against "after" computed to empty and the
# added-fields/schema-version assertions failed -- a test presupposing an
# environment fact (HEAD holds schema v1 seeds) that legitimate activity
# (the migration commit itself) invalidated. Same defect class as
# TEST-SEED-A (validity_conditions): fix the anchor, not the assertion.
# a2aceac ("Precedent layer v0: jurisprudence for agent sessions") is the
# immutable pre-migration commit -- PR-001..PR-004 are still schema_version
# 1 there, and always will be, since it is a historical commit no one can
# move. That makes it the permanent v0 baseline for these checks.
V0_BASELINE_COMMIT = "a2aceac"


def git_show_v0(relpath):
    """Fetch a tracked file's content as of the immutable V0_BASELINE_COMMIT
    -- the pre-migration (schema v1) content. Unlike git_show_head, this
    anchor never moves, so migration content-preservation checks stay
    correct regardless of what gets committed to HEAD afterward."""
    result = subprocess.run(["git", "show", V0_BASELINE_COMMIT + ":" + relpath], cwd=str(ROOT),
                             capture_output=True, text=True, check=True)
    return result.stdout


SEED_IDS = ("PR-001", "PR-002", "PR-003", "PR-004")

# V1-38's exact, fixed backfill minimum. Every token below was verified by
# this task against its real origin before being written to the live
# registry: T-302/T-044/T-052/T-049/T-031/T-021/T-029 all resolve to a
# tracked task file; every ORCHESTRATION.md:a-b range was re-read and its
# content matches the record's own quoted `ratio`/`dicta` (the same ranges
# test_precedent_seed.py::RatioQuotationFidelityTests independently
# verifies); `.harness/bin/blackboard.py:470` is `cmd_reopen`'s def line.
# No token here was invented -- P-023 and the two evidence-only anchors
# .harness/state.json:846 / event:2026-07-05T00:56:51Z were deliberately
# LEFT OUT of sources (they stay in cites/tier_evidence, where they already
# lived) per the synthesis's own derivation rule and the handoff note.
EXPECTED_SOURCES = {
    "PR-001": ["T-302", "ORCHESTRATION.md:58-67", ".harness/bin/blackboard.py:470"],
    "PR-002": ["T-044", "T-052", "ORCHESTRATION.md:82-90"],
    "PR-003": ["T-049", "ORCHESTRATION.md:211-218"],
    "PR-004": ["T-031", "T-021", "T-029", "ORCHESTRATION.md:119-126"],
}
EXPECTED_VALIDITY = {
    "PR-001": [".harness/bin/blackboard.py:470-517",
               "blackboard.py reopen is the only verb that moves a task off done/failed"],
    "PR-002": ["ORCHESTRATION.md:82-90",
               "the substrate test suite runs via python3 -m unittest discover -s .harness/tests"],
    "PR-003": ["ORCHESTRATION.md:211-218",
               "promotion to ORCHESTRATION.md quotes the note verbatim rather than paraphrasing"],
    "PR-004": ["ORCHESTRATION.md:119-126",
               "events.jsonl records verdicting verifier identities per task"],
}

# V1-01/V1-17 (SDR-01 as amended): every one of these must be byte-identical
# before/after migration. ADDED_V2_FIELDS is the ONLY permitted key-set diff
# besides schema_version's 1->2 bump.
IMMUTABLE_UNCHANGED_FIELDS = (
    "id", "title", "subject", "authority_tier", "tier_evidence", "ratio", "dicta",
    "scope_conditions", "declared_width", "revisit_trigger", "confirmation_status",
    "confirmed_by", "confirmed_at", "narrowed_scope", "confirmation_note", "relations",
    "cites", "cited_by", "overruled_by", "superseded_by", "voided_by", "issuing_task",
    "published_by", "published_at", "status",
)
ADDED_V2_FIELDS = frozenset(("sources", "validity_conditions", "operation",
                              "interpretive_code_version"))


def _empty_backfill_path(tmpdir):
    p = pathlib.Path(tmpdir) / "backfill-empty.json"
    p.write_text("{}", encoding="utf-8")
    return p


class SchemaVersionMigratedTests(unittest.TestCase):
    """V1-01/V1-37: every one of the four seeds is now schema_version 2."""

    def test_all_four_are_schema_version_2(self):
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                self.assertEqual(rec.get("schema_version"), precedent.SCHEMA_VERSION_V2)


class BackfilledFieldShapeTests(unittest.TestCase):
    """V1-38: exactly the fixed minimum sources/validity_conditions, the
    `determination` operation, and the `pre-code` sentinel -- for all
    four, byte-exact (no silent addition, no silent omission)."""

    def test_sources_match_v1_38_exactly(self):
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                self.assertEqual(rec.get("sources"), EXPECTED_SOURCES[pr_id])

    def test_validity_conditions_match_v1_38_exactly(self):
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                self.assertEqual(rec.get("validity_conditions"), EXPECTED_VALIDITY[pr_id])

    def test_operation_is_determination_for_all_four(self):
        """V1-38: 'verified by inspection: all four declare what binds and
        none reinterprets or revalues anything (relations == [] on all
        four, live)'."""
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                self.assertEqual(rec.get("operation"), {"type": "determination", "subtype": None})
                self.assertEqual(rec.get("relations"), [])

    def test_interpretive_code_version_is_pre_code_sentinel(self):
        """V1-15: `pre-code` is the honest statement that these records
        predate the interpretive code -- claiming a real version would be
        false. Writable only by `migrate`; `publish` refuses it."""
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                self.assertEqual(rec.get("interpretive_code_version"), "pre-code")

    def test_validity_conditions_non_empty_at_every_seed_tier(self):
        """All four seeds are tier 2 or 3 (never 4) -- validity_conditions
        is required non-empty for all of them (V1-10 #28)."""
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                self.assertIn(rec["authority_tier"], (1, 2, 3))
                self.assertTrue(rec.get("validity_conditions"))


class SourcesGrammarAndOriginTests(unittest.TestCase):
    """A1 / addendum sec3: 'a source you cannot point at is not a source'.
    Verified three ways: grammar (token_kind), resolution
    (resolve_citation -- none dangling), and, for path-shaped tokens, that
    the referenced file/range actually exists on disk today."""

    def test_every_source_token_is_grammar_valid(self):
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                self.assertTrue(rec["sources"], "sources must be non-empty (A1/V1-11)")
                for tok in rec["sources"]:
                    self.assertIsNotNone(precedent.token_kind(tok),
                                          "{}: source token {!r} fails the V1-02 grammar"
                                          .format(pr_id, tok))

    def test_every_source_token_resolves_none_dangling(self):
        """The board's exact bar (T-355 AC-6): a SECOND dangling finding
        beyond PR-001's recorded P-023 gap means the backfilled sources do
        not resolve. None of the sources tokens may ever be that second
        finding."""
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                dangling = [t for t in rec["sources"]
                            if not precedent.resolve_citation(t, LIVE_REGISTRY)]
                self.assertEqual(dangling, [], "{}: dangling source token(s) {}"
                                  .format(pr_id, dangling))

    def test_path_shaped_source_tokens_resolve_on_disk(self):
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                for tok in rec["sources"]:
                    if precedent.token_kind(tok) == "path":
                        relpath = tok.rsplit(":", 1)[0]
                        self.assertTrue((ROOT / relpath).exists(),
                                         "{}: source path {!r} does not exist".format(pr_id, relpath))

    def test_task_shaped_source_tokens_have_a_real_task_file(self):
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                rec = load_record(pr_id)
                for tok in rec["sources"]:
                    if precedent.token_kind(tok) == "T":
                        self.assertTrue((ROOT / ".harness" / "tasks" / (tok + ".json")).exists(),
                                         "{}: source task {!r} has no task file".format(pr_id, tok))

    def test_orchestration_source_range_matches_the_ratio_quotation_range(self):
        """Ties each record's ORCHESTRATION.md source token to the SAME
        range test_precedent_seed.py::RatioQuotationFidelityTests
        independently re-reads and verifies the ratio was quoted from --
        proof the backfilled source names the record's real origin rather
        than an anchor invented for this task."""
        expected_orch_token = {
            "PR-001": "ORCHESTRATION.md:58-67",
            "PR-002": "ORCHESTRATION.md:82-90",
            "PR-003": "ORCHESTRATION.md:211-218",
            "PR-004": "ORCHESTRATION.md:119-126",
        }
        for pr_id, token in expected_orch_token.items():
            with self.subTest(pr_id=pr_id):
                self.assertIn(token, load_record(pr_id)["sources"])

    def test_sources_never_reintroduce_the_dropped_evidence_only_anchors(self):
        """V1-38's derivation rule: `sources` is `cites` MINUS pure
        evidence anchors -- PR-001 must not carry P-023 or
        .harness/state.json:846 in `sources` (copying the deliberately
        dangling P-023 token into sources would double the registry's
        dangling-citation count); PR-004 must not carry the
        event:...  tier-evidence timestamp."""
        pr001 = load_record("PR-001")
        self.assertNotIn("P-023", pr001["sources"])
        self.assertNotIn(".harness/state.json:846", pr001["sources"])
        pr004 = load_record("PR-004")
        self.assertNotIn("event:2026-07-05T00:56:51Z", pr004["sources"])
        # both anchors remain exactly where they always lived, untouched.
        self.assertIn("P-023", pr001["cites"])
        self.assertIn(".harness/state.json:846", pr001["cites"])
        self.assertIn("event:2026-07-05T00:56:51Z", pr004["cites"])


class ContentPreservationTests(unittest.TestCase):
    """AC-3: the migration must not alter a single character of any
    pre-existing field. Compares the CURRENT live record against the
    PRE-MIGRATION content recoverable from git at the immutable
    V0_BASELINE_COMMIT (`git show a2aceac:...`) -- the verifier's own
    independent replay path, anchored so it survives HEAD moving forward."""

    def test_immutable_fields_are_byte_identical_to_pre_migration_git_head(self):
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                before = json.loads(git_show_v0(".harness/precedents/{}.json".format(pr_id)))
                after = load_record(pr_id)
                for field in IMMUTABLE_UNCHANGED_FIELDS:
                    self.assertEqual(after.get(field), before.get(field),
                                      "{}: field {!r} changed by migration".format(pr_id, field))

    def test_schema_version_bumped_from_1_to_2_and_nothing_else_about_it(self):
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                before = json.loads(git_show_v0(".harness/precedents/{}.json".format(pr_id)))
                self.assertEqual(before.get("schema_version"), 1,
                                  "{}: pre-migration v0-commit content was not schema_version 1 "
                                  "-- this test's baseline assumption is stale".format(pr_id))
                after = load_record(pr_id)
                self.assertEqual(after.get("schema_version"), 2)

    def test_only_the_four_v2_fields_were_added_nothing_removed(self):
        for pr_id in SEED_IDS:
            with self.subTest(pr_id=pr_id):
                before = json.loads(git_show_v0(".harness/precedents/{}.json".format(pr_id)))
                after = load_record(pr_id)
                added = set(after.keys()) - set(before.keys())
                removed = set(before.keys()) - set(after.keys())
                self.assertEqual(added, ADDED_V2_FIELDS,
                                  "{}: unexpected added keys {}".format(pr_id, added))
                self.assertEqual(removed, set(),
                                  "{}: unexpected removed keys {}".format(pr_id, removed))


class IdempotencyTests(unittest.TestCase):
    """AC-4: re-running `migrate` against the (now all-v2) live root is a
    byte-identical no-op -- exercised via the real CLI against the real
    live root, not a simulation. Safe under T-358's concurrent PR-005+
    minting because these four files are lock-held by this task for the
    duration of the run (T-358 owns disjoint ids)."""

    def _snapshot_seeds(self):
        return {pid: hashlib.sha256((LIVE_REGISTRY / (pid + ".json")).read_bytes()).hexdigest()
                for pid in SEED_IDS}

    def test_second_live_migrate_run_is_a_byte_identical_noop(self):
        with tempfile.TemporaryDirectory() as td:
            backfill_path = _empty_backfill_path(td)
            # Zero schema_version-1 records remain in the live root after
            # this task's first (real) migration (V1-39: "structurally
            # consumed") -- an empty backfill object is therefore honest,
            # not a shortcut: there is nothing left for it to cover.
            before = self._snapshot_seeds()
            result = run("migrate", "--agent", "test-precedent-migration",
                         "--backfill", str(backfill_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("no-op", result.stdout)
            after = self._snapshot_seeds()
            self.assertEqual(before, after,
                              "a no-op migrate run changed a seed record's bytes")

    def test_running_migrate_twice_in_a_row_yields_byte_identical_files(self):
        """The board's own phrasing of AC-4's test: 'runs it twice and
        asserts byte-identical output.'"""
        with tempfile.TemporaryDirectory() as td:
            backfill_path = _empty_backfill_path(td)
            r1 = run("migrate", "--backfill", str(backfill_path))
            self.assertEqual(r1.returncode, 0, r1.stderr)
            snap1 = self._snapshot_seeds()
            r2 = run("migrate", "--backfill", str(backfill_path))
            self.assertEqual(r2.returncode, 0, r2.stderr)
            snap2 = self._snapshot_seeds()
            self.assertEqual(snap1, snap2)


class MigrateNeverCreatesNewRecordsTests(unittest.TestCase):
    """AC-5's structural half, proven in isolation (T-353 owns generic
    migrate mechanics in test_precedent_v2.py; this pins the specific
    guarantee T-355's OWNS-EXACTLY clause depends on): `migrate` only
    rewrites record files `scan_registry` already found on disk -- it
    never mints a new PR-NNN id. Uses a throwaway temp root, never the
    live registry."""

    def test_migrate_creates_no_new_record_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td) / "registry"
            root.mkdir()
            v1 = {
                "id": "PR-001", "schema_version": 1, "title": "t", "subject": "s",
                "status": "active", "authority_tier": 4, "tier_evidence": ["T-100"],
                "ratio": "r", "dicta": [], "scope_conditions": [], "declared_width": "narrow",
                "revisit_trigger": None, "confirmation_status": "unconfirmed",
                "confirmed_by": None, "confirmed_at": None, "narrowed_scope": None,
                "confirmation_note": None, "relations": [], "cites": [], "cited_by": [],
                "overruled_by": None, "superseded_by": None, "voided_by": None,
                "issuing_task": "T-100", "published_by": "x",
                "published_at": "2026-01-01T00:00:00Z",
            }
            (root / "PR-001.json").write_text(json.dumps(v1), encoding="utf-8")
            backfill_path = pathlib.Path(td) / "backfill.json"
            backfill_path.write_text(json.dumps({
                "PR-001": {"sources": ["T-100"], "validity_conditions": []},
            }), encoding="utf-8")
            before_ids = sorted(p.stem for p in root.glob("PR-*.json"))
            result = subprocess.run(
                [sys.executable, str(PRECEDENT_PY), "migrate", "--root", str(root),
                 "--backfill", str(backfill_path)],
                text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            after_ids = sorted(p.stem for p in root.glob("PR-*.json"))
            self.assertEqual(before_ids, after_ids, "migrate must never create a new record file")


class TouchNothingButTheFourTests(unittest.TestCase):
    """AC-5: every record in the live root, after this task, must be
    schema_version 2 -- the four seeds via `migrate`, any PR-005+ (T-358's
    concurrent mints, if present by the time this runs) born at v2
    directly. A single-timepoint property check (never a live before/after
    diff on files this task does not lock), so it cannot flake against
    T-358's own legitimate concurrent writes."""

    def test_every_record_in_the_live_root_is_schema_version_2(self):
        all_ids = sorted(p.stem for p in LIVE_REGISTRY.glob("PR-*.json"))
        self.assertIn("PR-001", all_ids)
        for pid in all_ids:
            with self.subTest(pid=pid):
                rec = load_record(pid)
                self.assertEqual(rec.get("schema_version"), 2,
                                  "{} is schema_version {} -- every record must be v2 after "
                                  "this task (seeds via migrate, others born v2)"
                                  .format(pid, rec.get("schema_version")))

    def test_readme_is_unchanged(self):
        before = git_show_head(".harness/precedents/README.md")
        after = LIVE_README.read_text(encoding="utf-8")
        self.assertEqual(after, before, "README.md must not be touched by this task")


class NoStateOrBlackboardWritePathTests(unittest.TestCase):
    """T-355's MUST-NOT clause: migrate may never write state.json or
    blackboard.json. Checked as a STATIC property of `cmd_migrate`'s own
    source (never a live before/after hash): this harness runs many
    concurrent agents whose OWN sanctioned blackboard.py/state.json writes
    would make a live snapshot comparison flake for reasons that have
    nothing to do with this task's `migrate` call."""

    def test_cmd_migrate_source_never_references_state_or_blackboard(self):
        source = inspect.getsource(precedent.cmd_migrate)
        self.assertNotIn("STATE", source,
                          "cmd_migrate must never reference hc.STATE / state.json")
        self.assertNotIn("BLACKBOARD", source,
                          "cmd_migrate must never reference hc.BLACKBOARD / blackboard.json")

    def test_empty_noop_migrate_invocation_does_not_disturb_state_or_blackboard(self):
        """Belt-and-suspenders: a real, harmless (no-op) invocation, with a
        BEFORE/AFTER window kept as short as possible to minimize (not
        eliminate) exposure to unrelated concurrent harness activity. The
        static test above is the one this task's correctness rests on;
        this one is a live sanity check, not the proof."""
        def _hash(path):
            return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

        before_state = _hash(LIVE_STATE)
        before_bb = _hash(LIVE_BLACKBOARD)
        with tempfile.TemporaryDirectory() as td:
            backfill_path = _empty_backfill_path(td)
            result = run("migrate", "--backfill", str(backfill_path))
        self.assertEqual(result.returncode, 0, result.stderr)
        after_state = _hash(LIVE_STATE)
        after_bb = _hash(LIVE_BLACKBOARD)
        if before_state != after_state or before_bb != after_bb:
            self.skipTest("state.json/blackboard.json changed during this test's window -- "
                           "concurrent harness activity (other agents' sanctioned writes), "
                           "not this task's migrate call; see the static test above for the "
                           "property this task's correctness actually rests on")


class MigrationEventLoggedTests(unittest.TestCase):
    """V1-37's events clause: one `precedent_migrated` event per migrated
    record, into the LIVE events.jsonl, naming the operator directive as
    authority (A9.2)."""

    def test_precedent_migrated_events_recorded_for_all_four_with_operator_authority(self):
        seen = {}
        with open(LIVE_EVENTS, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("event") == "precedent_migrated" and ev.get("record") in SEED_IDS:
                    seen[ev["record"]] = ev
        for pid in SEED_IDS:
            with self.subTest(pid=pid):
                self.assertIn(pid, seen, "no precedent_migrated event found for {}".format(pid))
                ev = seen[pid]
                self.assertEqual(ev.get("from_version"), 1)
                self.assertEqual(ev.get("to_version"), 2)
                self.assertIn("A9.2", ev.get("authority", ""))
                self.assertIn("10.22201/iij.24487937e.2026.20.20316", ev.get("authority", ""))


class CiteAllBaselineTests(unittest.TestCase):
    """The board's exact acceptance baseline for `cite --all` post-
    migration: exit 3, exactly one dangling finding (PR-001's recorded
    P-023 gap). A second dangling finding would mean the backfilled
    sources do not resolve."""

    def test_cite_all_baseline_exactly_one_dangling(self):
        result = run("cite", "--all")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("DANGLING"), 1,
                          "expected exactly one dangling citation (PR-001's P-023); got:\n{}"
                          .format(result.stdout))
        self.assertIn("PR-001 cites P-023: DANGLING", result.stdout)


if __name__ == "__main__":
    unittest.main()
