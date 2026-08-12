"""Unit tests for T-371's .harness/bin/reputation.py: the Phase A reputation
bookkeeping reader fixed by section 5 (AD2-50..AD2-69) of
`docs/precedent-research/synthesis-addendum-ii-spec.md`.

Convention matches test_precedent_force.py/test_precedent_v2.py: every test
invokes the real CLI via subprocess against an isolated `--root` (a fresh
TemporaryDirectory per test) EXCEPT the two dedicated classes named for it
below, which deliberately exercise the module against the LIVE
`.harness/` stores -- read-only, because that is exactly what T-371's own
OWNS-EXACTLY criterion 2 demands as its proof ("hashes every store ...
before and after invoking EVERY subcommand on EVERY output path"). Nothing
in this file ever writes a PR-*.json record, a blackboard.json task, or an
events.jsonl line under the live `.harness/` tree; the live-store classes
are the mechanical proof of that claim, not an exception to it.
"""
import hashlib
import inspect
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".harness" / "bin"
REPUTATION_PY = BIN_DIR / "reputation.py"
LIVE_HARNESS = ROOT / ".harness"
LIVE_PRECEDENTS = LIVE_HARNESS / "precedents"
LIVE_BLACKBOARD = LIVE_HARNESS / "blackboard.json"
LIVE_STATE = LIVE_HARNESS / "state.json"
LIVE_EVENTS = LIVE_HARNESS / "logs" / "events.jsonl"

sys.path.insert(0, str(BIN_DIR))
import reputation as rep  # noqa: E402  (white-box tests only import for introspection)

CAVEAT = rep.CAVEAT


def run(*args, env=None):
    cmd = [sys.executable, str(REPUTATION_PY)] + list(args)
    e = dict(os.environ) if env is None else dict(env)
    e.pop("REPUTATION_ROOT", None)
    if env is not None:
        e.update(env)
    return subprocess.run(cmd, text=True, capture_output=True, env=e)


def sha256_of(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def count_lines(path):
    path = pathlib.Path(path)
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def snapshot_live_stores():
    """T-371 OWNS-EXACTLY criterion 2, literally: hash every
    .harness/precedents/*.json + .harness/blackboard.json +
    .harness/state.json, plus the events.jsonl line count. Also the full
    recursive path listing of .harness/ (AD2-54's "no temp file
    ANYWHERE inside the repository")."""
    hashes = {}
    if LIVE_PRECEDENTS.is_dir():
        for f in sorted(LIVE_PRECEDENTS.glob("PR-*.json")):
            hashes["precedents/" + f.name] = sha256_of(f)
    if LIVE_BLACKBOARD.exists():
        hashes["blackboard.json"] = sha256_of(LIVE_BLACKBOARD)
    if LIVE_STATE.exists():
        hashes["state.json"] = sha256_of(LIVE_STATE)
    events_lines = count_lines(LIVE_EVENTS)
    all_paths = sorted(
        str(p.relative_to(LIVE_HARNESS)) for p in LIVE_HARNESS.rglob("*") if p.is_file()
    )
    return hashes, events_lines, all_paths


# --------------------------------------------------------------------------
# Fixture construction: schema-v2-shaped raw records, blackboard tasks,
# task-record files, and events.jsonl lines -- the same sanctioned
# hand-crafted-JSON pattern test_precedent_force.py's base_record/rel use,
# because reputation.py's figures need exact control over published_by,
# below_target_tier, operation.subtype and published_at ordering that no
# `publish` call is available here to produce (this module owns no writer).
# --------------------------------------------------------------------------


def rel(rtype, target, below_target_tier=False, **extra):
    r = {"type": rtype, "target": target, "distinguishing_facts": None,
         "factors": [], "factor_note": None, "controlling_authority": None,
         "target_tier_declared": None, "below_target_tier": below_target_tier}
    r.update(extra)
    return r


def base_record(pr_id, **overrides):
    rec = {
        "id": pr_id, "schema_version": 2, "title": "t", "subject": "subj-" + pr_id.lower(),
        "status": "active", "authority_tier": 1, "tier_evidence": ["T-900"],
        "ratio": "r", "dicta": [], "scope_conditions": ["s"],
        "declared_width": "narrow", "revisit_trigger": "revisit",
        "confirmation_status": "unconfirmed", "confirmed_by": None, "confirmed_at": None,
        "narrowed_scope": None, "confirmation_note": None,
        "relations": [], "cites": [], "cited_by": [],
        "overruled_by": None, "superseded_by": None, "voided_by": None,
        "issuing_task": "T-900", "published_by": "author-a",
        "published_at": "2026-01-01T00:00:00Z",
        "sources": ["T-900"], "validity_conditions": ["v"],
        "operation": {"type": "determination", "subtype": None},
        "interpretive_code_version": "v1",
    }
    rec.update(overrides)
    return rec


class FixtureRootTestCase(unittest.TestCase):
    """Base class for hand-crafted-fixture tests: isolated store root under
    a fresh TemporaryDirectory, never the live `.harness/` tree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name) / "store"
        (self.root / "precedents").mkdir(parents=True)
        (self.root / "tasks").mkdir(parents=True)
        (self.root / "logs").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def write_precedent(self, rec):
        (self.root / "precedents" / (rec["id"] + ".json")).write_text(
            json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_blackboard(self, tasks):
        (self.root / "blackboard.json").write_text(
            json.dumps({"tasks": tasks}, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_task_file(self, task_id, data=None):
        (self.root / "tasks" / (task_id + ".json")).write_text(
            json.dumps(data or {"id": task_id}, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_events(self, events):
        with open(self.root / "logs" / "events.jsonl", "w", encoding="utf-8") as f:
            for e in events:
                if isinstance(e, str):
                    f.write(e + "\n")
                else:
                    f.write(json.dumps(e) + "\n")

    def build_canonical_fixture(self):
        """The exact fixture the spec's own section 9.3 replay builds and
        quotes stdout for -- PR-001..PR-004, T-900/T-901/T-902, one
        task_reopened event on T-901."""
        self.write_precedent(base_record(
            "PR-001", subject="alpha", published_by="author-a", cited_by=["PR-002"]))
        self.write_precedent(base_record(
            "PR-002", subject="beta", published_by="author-b",
            relations=[rel("follows", "PR-001", below_target_tier=False)]))
        self.write_precedent(base_record(
            "PR-003", subject="gamma", published_by="author-a", issuing_task="T-900",
            relations=[rel("overrules", "decision:T-901#R-1", below_target_tier=False)],
            cited_by=["PR-004"]))
        self.write_precedent(base_record(
            "PR-004", subject="delta", published_by="author-b", cites=["PR-003"]))
        self.write_blackboard({
            "T-900": {"status": "done", "handoff": {"from": "author-b"}, "completed_by": "author-a"},
            "T-901": {"status": "done", "handoff": {"from": "author-b"}, "completed_by": "author-a"},
            "T-902": {"status": "done", "handoff": {"from": "author-a"}, "completed_by": "author-a"},
        })
        for tid in ("T-900", "T-901", "T-902"):
            self.write_task_file(tid)
        self.write_events([
            {"ts": "2026-01-01T00:00:00Z", "event": "task_reopened", "agent": "x", "task": "T-901"},
            {"ts": "2026-01-01T00:00:00Z", "event": "precedent_published", "agent": "x", "record": "PR-001"},
        ])


# --------------------------------------------------------------------------
# 1. --help / caveat subcommand (AD2-50, AD2-61, AD2-68)
# --------------------------------------------------------------------------


class HelpAndCaveatTests(unittest.TestCase):
    def test_help_exit_zero_carries_caveat_in_epilog(self):
        result = run("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("caveat: " + CAVEAT, result.stdout)
        self.assertIn("standing", result.stdout)
        self.assertIn("identities", result.stdout)
        self.assertIn("caveat", result.stdout)

    def test_caveat_text_exact(self):
        result = run("caveat")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "caveat: " + CAVEAT + "\n")
        self.assertEqual(result.stderr, "")

    def test_caveat_json_exact(self):
        result = run("caveat", "--json")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"caveat": CAVEAT})

    def test_unknown_subcommand_is_argparse_exit_2(self):
        result = run("bogus-subcommand")
        self.assertEqual(result.returncode, 2)

    def test_unknown_flag_is_argparse_exit_2(self):
        result = run("caveat", "--not-a-real-flag")
        self.assertEqual(result.returncode, 2)


# --------------------------------------------------------------------------
# 2. `standing` success path: exact stdout, both modes, against the
#    spec's own section 9.3 fixture (AD2-65, AD2-66, AD2-69).
# --------------------------------------------------------------------------


class StandingCanonicalFixtureTests(FixtureRootTestCase):
    def setUp(self):
        super().setUp()
        self.build_canonical_fixture()

    def test_standing_text_author_a_matches_spec_exactly(self):
        result = run("standing", "--identity", "author-a", "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = "\n".join([
            "caveat: " + CAVEAT,
            "root: {}".format(self.root),
            "identity: author-a",
            "rule_authorship: 2 (active 2, overruled 0, superseded 0, void_per_incuriam 0) "
            "[source: precedents/PR-*.json:published_by]",
            "load_bearing_citations_received: 1 ELIGIBLE-UPPER-BOUND (steps 1-4 only; "
            "load-bearing not confirmed) [source: precedents/PR-*.json:relations[]+published_by]",
            "  eligible PR-001 <- PR-002 (follows) by author-b",
            "load_bearing_verdict: not computed (steps 5-7 are a confirming-identity "
            "judgment with no storage field; see the tier-1 record with subject "
            "load-bearing-citation)",
            "consolidations_achieved: 0 (threshold C>=3) [source: precedents/PR-*.json:"
            "relations[]+published_by via precedent.qualifying_applications_count]",
            "  consolidating PR-001: C=1 applied_by=author-b via PR-002 (follows)",
            "overrulings_sustained: 1 of 1 issued [source: precedents/PR-*.json:relations[]"
            "+cited_by; blackboard.json:tasks[].completed_by]",
            "  overrule PR-003 -> decision:T-901#R-1: verification=upheld "
            "distinct_identity_citations=PR-004 sustained=yes",
            "verification_verdicts_upheld: 1 [source: blackboard.json:tasks[].completed_by"
            "+handoff.from; tasks/T-*.json existence; logs/events.jsonl:task_reopened "
            "(subtraction only)]",
            "  verdict T-900: upheld",
            "  verdict T-901: excluded (task_reopened)",
            "adjudications_not_reversed: unavailable (the appellate verb does not exist; "
            "the field is present and never fabricated)",
        ])
        self.assertEqual(result.stdout.rstrip("\n"), expected)

    def test_standing_text_author_b_all_zero_no_detail_lines(self):
        result = run("standing", "--identity", "author-b", "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = "\n".join([
            "caveat: " + CAVEAT,
            "root: {}".format(self.root),
            "identity: author-b",
            "rule_authorship: 2 (active 2, overruled 0, superseded 0, void_per_incuriam 0) "
            "[source: precedents/PR-*.json:published_by]",
            "load_bearing_citations_received: 0 ELIGIBLE-UPPER-BOUND (steps 1-4 only; "
            "load-bearing not confirmed) [source: precedents/PR-*.json:relations[]+published_by]",
            "load_bearing_verdict: not computed (steps 5-7 are a confirming-identity "
            "judgment with no storage field; see the tier-1 record with subject "
            "load-bearing-citation)",
            "consolidations_achieved: 0 (threshold C>=3) [source: precedents/PR-*.json:"
            "relations[]+published_by via precedent.qualifying_applications_count]",
            "overrulings_sustained: 0 of 0 issued [source: precedents/PR-*.json:relations[]"
            "+cited_by; blackboard.json:tasks[].completed_by]",
            "verification_verdicts_upheld: 0 [source: blackboard.json:tasks[].completed_by"
            "+handoff.from; tasks/T-*.json existence; logs/events.jsonl:task_reopened "
            "(subtraction only)]",
            "adjudications_not_reversed: unavailable (the appellate verb does not exist; "
            "the field is present and never fabricated)",
        ])
        self.assertEqual(result.stdout.rstrip("\n"), expected)

    def test_standing_json_author_a_matches_spec_exactly(self):
        result = run("standing", "--identity", "author-a", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        obj = json.loads(result.stdout)
        expected = {
            "caveat": CAVEAT,
            "root": str(self.root),
            "identity": "author-a",
            "figures": {
                "rule_authorship": {
                    "value": 2,
                    "by_status": {"active": 2, "overruled": 0, "superseded": 0, "void_per_incuriam": 0},
                    "records": ["PR-001", "PR-003"],
                    "source": "precedents/PR-*.json:published_by",
                },
                "load_bearing_citations_received": {
                    "value": 1,
                    "label": "eligible-upper-bound",
                    "verdict": None,
                    "verdict_status": "not-computed",
                    "verdict_reason": (
                        "steps 5-7 are a confirming-identity judgment with no storage "
                        "field; see the tier-1 record with subject load-bearing-citation"
                    ),
                    "detail": [{"record": "PR-001", "citing_record": "PR-002",
                                "relation": "follows", "published_by": "author-b"}],
                    "source": "precedents/PR-*.json:relations[]+published_by",
                },
                "consolidations_achieved": {
                    "value": 0,
                    "threshold": 3,
                    "detail": [{"record": "PR-001", "c": 1,
                                "applied_by": [{"identity": "author-b", "citing_record": "PR-002",
                                                 "relation": "follows"}]}],
                    "source": ("precedents/PR-*.json:relations[]+published_by via "
                               "precedent.qualifying_applications_count"),
                },
                "overrulings_sustained": {
                    "value": 1,
                    "issued": 1,
                    "detail": [{"record": "PR-003", "target": "decision:T-901#R-1",
                                "verification_upheld": True,
                                "distinct_identity_citations": ["PR-004"], "sustained": True}],
                    "source": "precedents/PR-*.json:relations[]+cited_by; blackboard.json:tasks[].completed_by",
                },
                "verification_verdicts_upheld": {
                    "value": 1,
                    "detail": [{"task": "T-900", "outcome": "upheld", "task_record_missing": False},
                               {"task": "T-901", "outcome": "excluded", "task_record_missing": False}],
                    "source": ("blackboard.json:tasks[].completed_by+handoff.from; "
                               "tasks/T-*.json existence; logs/events.jsonl:task_reopened "
                               "(subtraction only)"),
                },
                "adjudications_not_reversed": {
                    "value": None,
                    "status": "unavailable",
                    "reason": "the appellate verb does not exist; the field is present and never fabricated",
                    "source": None,
                },
            },
        }
        self.assertEqual(obj, expected)
        # AD2-66: top-level key order.
        self.assertEqual(list(obj.keys()), ["caveat", "root", "identity", "figures"])
        # AD2-56: the six figures, in AB2's own order.
        self.assertEqual(list(obj["figures"].keys()), [
            "rule_authorship", "load_bearing_citations_received", "consolidations_achieved",
            "overrulings_sustained", "verification_verdicts_upheld", "adjudications_not_reversed",
        ])


class IdentitiesTests(FixtureRootTestCase):
    def setUp(self):
        super().setUp()
        self.build_canonical_fixture()

    def test_identities_text_exact(self):
        result = run("identities", "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = "\n".join([
            "caveat: " + CAVEAT,
            "root: {}".format(self.root),
            "note: lexicographic order, never ranked (A.9 refuses a leaderboard)",
            "identity: author-a stores=blackboard,precedents",
            "identity: author-b stores=blackboard,precedents",
            "identities: 2 discovered",
        ])
        self.assertEqual(result.stdout.rstrip("\n"), expected)

    def test_identities_json_carries_caveat_first_key_and_note(self):
        result = run("identities", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        obj = json.loads(result.stdout)
        self.assertEqual(list(obj.keys())[0], "caveat")
        self.assertEqual(obj["caveat"], CAVEAT)
        self.assertIn("A.9 refuses a leaderboard", obj["note"])
        self.assertEqual(obj["count"], 2)
        self.assertEqual(
            sorted((i["identity"], tuple(i["stores"])) for i in obj["identities"]),
            [("author-a", ("blackboard", "precedents")), ("author-b", ("blackboard", "precedents"))],
        )


# --------------------------------------------------------------------------
# 3. Refusal paths (AB3, AD2-51, AD2-53, AD2-69) -- one test per output
#    path, including the error paths, in both text and --json mode.
# --------------------------------------------------------------------------


class RefusalTests(FixtureRootTestCase):
    def setUp(self):
        super().setUp()
        self.build_canonical_fixture()

    def test_missing_identity_text(self):
        result = run("standing", "--root", str(self.root))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "caveat: " + CAVEAT + "\n")
        self.assertEqual(
            result.stderr.strip(),
            "refused: --identity is required and must be non-empty (AD2-51)",
        )

    def test_missing_identity_json(self):
        result = run("standing", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout), {
            "caveat": CAVEAT,
            "refused": "--identity is required and must be non-empty (AD2-51)",
        })

    def test_empty_string_identity_is_also_refused(self):
        result = run("standing", "--identity", "   ", "--root", str(self.root))
        self.assertEqual(result.returncode, 1)
        self.assertIn("--identity is required and must be non-empty", result.stderr)

    def test_identity_not_found_text(self):
        result = run("standing", "--identity", "nobody", "--root", str(self.root))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "caveat: " + CAVEAT + "\n")
        self.assertEqual(
            result.stderr.strip(),
            "refused: identity 'nobody' appears in no store under {} (AD2-53)".format(self.root),
        )

    def test_identity_not_found_json(self):
        result = run("standing", "--identity", "nobody", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout), {
            "caveat": CAVEAT,
            "refused": "identity 'nobody' appears in no store under {} (AD2-53)".format(self.root),
        })

    def test_bad_root_nonexistent_path(self):
        bad = str(self.root / "does-not-exist-at-all")
        result = run("standing", "--identity", "author-a", "--root", bad)
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "refused: root '{}' has no precedents/ directory; refusing rather than "
            "reporting zeros (AD2-53)".format(bad), result.stderr)

    def test_bad_root_path_is_a_file_not_a_directory(self):
        f = self.root / "im-a-file.txt"
        f.write_text("not a directory", encoding="utf-8")
        result = run("standing", "--identity", "author-a", "--root", str(f))
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no precedents/ directory", result.stderr)

    def test_bad_root_missing_precedents_subdir(self):
        empty_root = self.root.parent / "no-precedents-here"
        empty_root.mkdir()
        result = run("standing", "--identity", "author-a", "--root", str(empty_root))
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no precedents/ directory", result.stderr)

    def test_bad_root_for_identities_subcommand_too(self):
        bad = str(self.root / "nope")
        result = run("identities", "--root", bad)
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no precedents/ directory", result.stderr)


# --------------------------------------------------------------------------
# 4. Root resolution precedence (AD2-52: flag wins over env, env wins over
#    default).
# --------------------------------------------------------------------------


class RootPrecedenceTests(FixtureRootTestCase):
    def setUp(self):
        super().setUp()
        self.build_canonical_fixture()

    def test_flag_wins_over_env(self):
        wrong = self.root.parent / "wrong-env-root"
        wrong.mkdir()
        env = dict(os.environ)
        env["REPUTATION_ROOT"] = str(wrong)
        result = run("standing", "--identity", "author-a", "--root", str(self.root), env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("root: {}".format(self.root), result.stdout)

    def test_env_used_when_no_flag(self):
        env = dict(os.environ)
        env["REPUTATION_ROOT"] = str(self.root)
        result = run("standing", "--identity", "author-a", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("root: {}".format(self.root), result.stdout)


# --------------------------------------------------------------------------
# 5. Registry integrity errors (AD2-55 exit 4) -- corrupt record, corrupt
#    blackboard.json, corrupt events.jsonl line; missing (not corrupt)
#    task record is a DIFFERENT, non-error path (AD2-56 figure 5).
# --------------------------------------------------------------------------


class RegistryIntegrityTests(FixtureRootTestCase):
    def setUp(self):
        super().setUp()
        self.build_canonical_fixture()

    def test_corrupt_precedent_record_is_exit_4(self):
        (self.root / "precedents" / "PR-999.json").write_text("{not valid json", encoding="utf-8")
        result = run("standing", "--identity", "author-a", "--root", str(self.root))
        self.assertEqual(result.returncode, 4)
        self.assertIn("REGISTRY INTEGRITY ERROR", result.stderr)

    def test_corrupt_blackboard_json_is_exit_4(self):
        (self.root / "blackboard.json").write_text("{not valid json either", encoding="utf-8")
        result = run("standing", "--identity", "author-a", "--root", str(self.root))
        self.assertEqual(result.returncode, 4)
        self.assertIn("REGISTRY INTEGRITY ERROR", result.stderr)

    def test_corrupt_events_line_is_exit_4(self):
        with open(self.root / "logs" / "events.jsonl", "a", encoding="utf-8") as f:
            f.write("this is not json\n")
        result = run("standing", "--identity", "author-a", "--root", str(self.root))
        self.assertEqual(result.returncode, 4)
        self.assertIn("REGISTRY INTEGRITY ERROR", result.stderr)

    def test_missing_task_record_is_displayed_not_an_error(self):
        """AD2-56 figure 5: a missing tasks/T-NNN.json is displayed
        (task_record_missing: true) and still COUNTED when otherwise
        upheld -- never silently omitted, never a registry integrity
        error."""
        self.write_blackboard({
            "T-900": {"status": "done", "handoff": {"from": "author-b"}, "completed_by": "author-a"},
            "T-950": {"status": "done", "handoff": {"from": "author-c"}, "completed_by": "author-a"},
        })
        # Deliberately no tasks/T-950.json written.
        result = run("standing", "--identity", "author-a", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        obj = json.loads(result.stdout)
        detail = obj["figures"]["verification_verdicts_upheld"]["detail"]
        by_task = {d["task"]: d for d in detail}
        self.assertIn("T-950", by_task)
        self.assertTrue(by_task["T-950"]["task_record_missing"])
        self.assertEqual(by_task["T-950"]["outcome"], "upheld")
        self.assertEqual(obj["figures"]["verification_verdicts_upheld"]["value"], 2)


# --------------------------------------------------------------------------
# 6. AB9-1 visibility: consolidation figure shows WHO applied; a
#    same-identity ("recruit yourself") attempt is invisible because the
#    distinct-identity floor excludes it entirely, never fabricating
#    credit or a false display line.
# --------------------------------------------------------------------------


class AB9VisibilityTests(FixtureRootTestCase):
    def test_same_identity_application_produces_no_detail_and_no_credit(self):
        self.write_precedent(base_record("PR-010", subject="s10", published_by="author-x"))
        self.write_precedent(base_record(
            "PR-011", subject="s11", published_by="author-x",  # SAME identity as PR-010's author
            relations=[rel("follows", "PR-010", below_target_tier=False)]))
        self.write_blackboard({})
        result = run("standing", "--identity", "author-x", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        obj = json.loads(result.stdout)
        detail = obj["figures"]["consolidations_achieved"]["detail"]
        self.assertEqual([d for d in detail if d["record"] == "PR-010"], [],
                          "same-publisher application must not appear as a qualifying "
                          "consolidation applicant (P-011 self-dealing exclusion)")

    def test_distinct_identity_application_is_visible_with_applicant_named(self):
        self.write_precedent(base_record("PR-020", subject="s20", published_by="author-y"))
        self.write_precedent(base_record(
            "PR-021", subject="s21", published_by="author-z",  # DIFFERENT identity
            relations=[rel("follows", "PR-020", below_target_tier=False)]))
        self.write_blackboard({})
        result = run("standing", "--identity", "author-y", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        obj = json.loads(result.stdout)
        detail = obj["figures"]["consolidations_achieved"]["detail"]
        matches = [d for d in detail if d["record"] == "PR-020"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["c"], 1)
        self.assertEqual(matches[0]["applied_by"], [
            {"identity": "author-z", "citing_record": "PR-021", "relation": "follows"}
        ])


# --------------------------------------------------------------------------
# 7. Figure-2 (load-bearing-citations-received) step routing: `distinguishes`
#    is excluded by definition, and below_target_tier=True is excluded
#    (T-367 steps 2 and 4).
# --------------------------------------------------------------------------


class Figure2RoutingTests(FixtureRootTestCase):
    def test_distinguishes_relation_excluded(self):
        self.write_precedent(base_record("PR-030", subject="s30", published_by="author-p"))
        self.write_precedent(base_record(
            "PR-031", subject="s31", published_by="author-q",
            relations=[rel("distinguishes", "PR-030", below_target_tier=False)]))
        self.write_blackboard({})
        result = run("standing", "--identity", "author-p", "--root", str(self.root), "--json")
        obj = json.loads(result.stdout)
        self.assertEqual(obj["figures"]["load_bearing_citations_received"]["value"], 0)

    def test_below_target_tier_excluded(self):
        self.write_precedent(base_record("PR-040", subject="s40", published_by="author-p"))
        self.write_precedent(base_record(
            "PR-041", subject="s41", published_by="author-q",
            relations=[rel("follows", "PR-040", below_target_tier=True)]))
        self.write_blackboard({})
        result = run("standing", "--identity", "author-p", "--root", str(self.root), "--json")
        obj = json.loads(result.stdout)
        self.assertEqual(obj["figures"]["load_bearing_citations_received"]["value"], 0)

    def test_bare_cites_token_excluded_relations_only(self):
        """Step 1: a bare `cites` token (not a typed relation) never counts."""
        self.write_precedent(base_record("PR-050", subject="s50", published_by="author-p"))
        self.write_precedent(base_record(
            "PR-051", subject="s51", published_by="author-q", cites=["PR-050"]))
        self.write_blackboard({})
        result = run("standing", "--identity", "author-p", "--root", str(self.root), "--json")
        obj = json.loads(result.stdout)
        self.assertEqual(obj["figures"]["load_bearing_citations_received"]["value"], 0)


# --------------------------------------------------------------------------
# 8. Figure-4 (overrulings sustained) granular logic.
# --------------------------------------------------------------------------


class Figure4OverrulingsTests(FixtureRootTestCase):
    def _base(self):
        self.write_precedent(base_record(
            "PR-060", subject="s60", published_by="author-o", issuing_task="T-960",
            relations=[rel("overrules", "PR-999-target", below_target_tier=False)],
            cited_by=[]))

    def test_not_sustained_when_no_distinct_citation(self):
        self._base()
        self.write_blackboard({
            "T-960": {"status": "done", "handoff": {"from": "author-b"}, "completed_by": "author-o"},
        })
        result = run("standing", "--identity", "author-o", "--root", str(self.root), "--json")
        obj = json.loads(result.stdout)
        d = obj["figures"]["overrulings_sustained"]["detail"][0]
        self.assertTrue(d["verification_upheld"])
        self.assertEqual(d["distinct_identity_citations"], [])
        self.assertFalse(d["sustained"])
        self.assertEqual(obj["figures"]["overrulings_sustained"]["value"], 0)
        self.assertEqual(obj["figures"]["overrulings_sustained"]["issued"], 1)

    def test_not_sustained_when_task_not_done(self):
        self.write_precedent(base_record(
            "PR-061", subject="s61", published_by="author-o", issuing_task="T-961",
            relations=[rel("overrules", "PR-999-target", below_target_tier=False)],
            cited_by=["PR-062"]))
        self.write_precedent(base_record("PR-062", subject="s62", published_by="author-other"))
        self.write_blackboard({
            "T-961": {"status": "open", "handoff": {"from": "author-b"}, "completed_by": None},
        })
        result = run("standing", "--identity", "author-o", "--root", str(self.root), "--json")
        obj = json.loads(result.stdout)
        d = obj["figures"]["overrulings_sustained"]["detail"][0]
        self.assertFalse(d["verification_upheld"])
        self.assertFalse(d["sustained"])

    def test_not_sustained_when_producer_equals_approver(self):
        self.write_precedent(base_record(
            "PR-063", subject="s63", published_by="author-o", issuing_task="T-963",
            relations=[rel("overrules", "PR-999-target", below_target_tier=False)],
            cited_by=["PR-064"]))
        self.write_precedent(base_record("PR-064", subject="s64", published_by="author-other"))
        self.write_blackboard({
            "T-963": {"status": "done", "handoff": {"from": "author-o"}, "completed_by": "author-o"},
        })
        result = run("standing", "--identity", "author-o", "--root", str(self.root), "--json")
        obj = json.loads(result.stdout)
        d = obj["figures"]["overrulings_sustained"]["detail"][0]
        self.assertFalse(d["verification_upheld"])


# --------------------------------------------------------------------------
# 9. Events.jsonl reading discipline (AD2-59): exactly ONE event kind
#    read, in the subtracting direction only; unrelated event kinds are
#    ignored and never raise, never mint standing.
# --------------------------------------------------------------------------


class EventsDisciplineTests(FixtureRootTestCase):
    def setUp(self):
        super().setUp()
        self.build_canonical_fixture()

    def test_other_event_kinds_ignored(self):
        self.write_events([
            {"ts": "2026-01-01T00:00:00Z", "event": "task_reopened", "agent": "x", "task": "T-901"},
            {"ts": "2026-01-01T00:00:00Z", "event": "precedent_published", "agent": "x", "record": "PR-001"},
            {"ts": "2026-01-01T00:00:00Z", "event": "precedent_confirmed", "agent": "x", "record": "PR-001"},
            {"ts": "2026-01-01T00:00:00Z", "event": "task_reopened", "agent": "x", "task": "T-999-not-a-candidate"},
        ])
        result = run("standing", "--identity", "author-a", "--root", str(self.root), "--json")
        obj = json.loads(result.stdout)
        # Same result as the canonical fixture -- extra noise event kinds
        # and an unrelated task_reopened target change nothing.
        self.assertEqual(obj["figures"]["verification_verdicts_upheld"]["value"], 1)


# --------------------------------------------------------------------------
# 10. Phase A neutrality (AB4, AD2-62) as code: the explicit allow-list,
#     and no gate-shaped parameter on any exported callable.
# --------------------------------------------------------------------------


class NeutralityTests(unittest.TestCase):
    def test_public_api_allowlist_is_exhaustive(self):
        exported = {
            name for name, obj in vars(rep).items()
            if not name.startswith("_")
            and (inspect.isfunction(obj) or (name == "CAVEAT"))
            and (not inspect.isfunction(obj) or obj.__module__ == rep.__name__)
        }
        self.assertEqual(exported, set(rep.PUBLIC_API))

    def test_no_exported_callable_takes_a_gate_shaped_parameter(self):
        forbidden_substrings = ("threshold", "gate", "weight", "burden", "permission")
        offenders = []
        for name in rep.PUBLIC_API:
            obj = getattr(rep, name)
            if not inspect.isfunction(obj):
                continue
            for pname in inspect.signature(obj).parameters:
                low = pname.lower()
                if any(bad in low for bad in forbidden_substrings):
                    offenders.append((name, pname))
        self.assertEqual(offenders, [], "gate-shaped parameter found: {}".format(offenders))

    def test_consolidations_achieved_threshold_is_a_display_constant_not_a_gate(self):
        """The one 'threshold' word in the whole output is REITERATION_N,
        displayed for counting purposes only -- confirm it is borrowed
        read-only from precedent.py, never redefined locally."""
        import precedent
        self.assertIs(rep.figure_consolidations_achieved.__globals__["precedent"], precedent)


# --------------------------------------------------------------------------
# 11. Reuse-not-reimplementation drift guard (AD2-64 DECISION in the
#     module docstring): the local contributor-listing walk must never
#     disagree with precedent.qualifying_applications_count's own count,
#     including across a zeroing (distinguishes) event.
# --------------------------------------------------------------------------


class NoDriftFromPrecedentPyTests(unittest.TestCase):
    def test_contributor_count_matches_qualifying_applications_count(self):
        import precedent as prec
        records = {
            "PR-100": base_record("PR-100", published_by="author-m"),
            "PR-101": base_record(
                "PR-101", published_by="author-n",
                relations=[rel("follows", "PR-100", below_target_tier=False)]),
            "PR-102": base_record(
                "PR-102", published_by="author-o",
                relations=[rel("follows", "PR-100", below_target_tier=False)],
                published_at="2026-02-01T00:00:00Z"),
        }
        c = prec.qualifying_applications_count("PR-100", records)
        contributors = rep._consolidation_contributors("PR-100", records)
        self.assertEqual(len(contributors), c)
        self.assertEqual(c, 2)

    def test_contributor_count_matches_after_a_zeroing_distinguish(self):
        import precedent as prec
        records = {
            "PR-110": base_record("PR-110", published_by="author-m"),
            "PR-111": base_record(
                "PR-111", published_by="author-n",
                relations=[rel("follows", "PR-110", below_target_tier=False)],
                published_at="2026-01-01T00:00:00Z"),
            "PR-112": base_record(
                "PR-112", published_by="author-o",
                relations=[rel("distinguishes", "PR-110", below_target_tier=False)],
                published_at="2026-02-01T00:00:00Z"),
        }
        c = prec.qualifying_applications_count("PR-110", records)
        contributors = rep._consolidation_contributors("PR-110", records)
        self.assertEqual(c, 0)
        self.assertEqual(len(contributors), 0)


# --------------------------------------------------------------------------
# 12. READ-ONLY, ABSOLUTELY (AD2-54, T-371 OWNS-EXACTLY criterion 2) --
#     the mandatory proof, against the fixture root AND against the LIVE
#     .harness/ stores by name, for EVERY subcommand and EVERY output
#     path (text/json, success/refusal).
# --------------------------------------------------------------------------


class FixtureRootZeroWritesTests(FixtureRootTestCase):
    def setUp(self):
        super().setUp()
        self.build_canonical_fixture()

    def _snapshot(self):
        hashes = {}
        for f in sorted((self.root / "precedents").glob("*.json")):
            hashes["precedents/" + f.name] = sha256_of(f)
        hashes["blackboard.json"] = sha256_of(self.root / "blackboard.json")
        for f in sorted((self.root / "tasks").glob("*.json")):
            hashes["tasks/" + f.name] = sha256_of(f)
        events_lines = count_lines(self.root / "logs" / "events.jsonl")
        all_paths = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file())
        return hashes, events_lines, all_paths

    def test_zero_writes_across_every_subcommand_and_output_path(self):
        before_hashes, before_events, before_paths = self._snapshot()

        invocations = [
            ["standing", "--identity", "author-a", "--root", str(self.root)],
            ["standing", "--identity", "author-a", "--root", str(self.root), "--json"],
            ["standing", "--identity", "author-b", "--root", str(self.root)],
            ["standing", "--identity", "nobody", "--root", str(self.root)],
            ["standing", "--identity", "nobody", "--root", str(self.root), "--json"],
            ["standing", "--root", str(self.root)],
            ["standing", "--root", str(self.root), "--json"],
            ["identities", "--root", str(self.root)],
            ["identities", "--root", str(self.root), "--json"],
            ["caveat"],
            ["caveat", "--json"],
            ["--help"],
        ]
        for args in invocations:
            result = run(*args)
            self.assertIn(result.returncode, (0, 1, 4), "{} -> {}".format(args, result.returncode))

        after_hashes, after_events, after_paths = self._snapshot()
        self.assertEqual(before_hashes, after_hashes)
        self.assertEqual(before_events, after_events)
        self.assertEqual(before_paths, after_paths)


class LiveStoreZeroWritesTests(unittest.TestCase):
    """T-371 OWNS-EXACTLY criterion 2, literally: this is the test that
    hashes the ACTUAL .harness/precedents/*.json, .harness/blackboard.json
    and .harness/state.json files, and counts the ACTUAL
    .harness/logs/events.jsonl lines, before and after invoking every
    subcommand on every output path against the LIVE default root (no
    --root, no REPUTATION_ROOT) -- safe, because reputation.py is
    read-only, exactly like precedent.py's cite/conflicts/stale."""

    def test_live_stores_byte_identical_across_every_subcommand(self):
        before_hashes, before_events, before_paths = snapshot_live_stores()

        # Discover one real identity from the live stores themselves, so
        # this test needs no hardcoded identity name and stays correct as
        # the registry grows.
        ident_result = run("identities")
        self.assertEqual(ident_result.returncode, 0, ident_result.stderr)
        ident_lines = [l for l in ident_result.stdout.splitlines() if l.startswith("identity: ")]
        self.assertTrue(ident_lines, "the live harness has no discoverable identity to test against")
        real_identity = ident_lines[0].split()[1]

        invocations = [
            ["standing", "--identity", real_identity],
            ["standing", "--identity", real_identity, "--json"],
            ["standing", "--identity", "definitely-not-a-real-identity-xyz"],
            ["standing", "--identity", "definitely-not-a-real-identity-xyz", "--json"],
            ["standing"],
            ["standing", "--json"],
            ["identities"],
            ["identities", "--json"],
            ["caveat"],
            ["caveat", "--json"],
            ["--help"],
        ]
        for args in invocations:
            result = run(*args)
            self.assertIn(result.returncode, (0, 1, 4), "{} -> {}".format(args, result.returncode))

        after_hashes, after_events, after_paths = snapshot_live_stores()
        self.assertEqual(before_hashes, after_hashes,
                          "reputation.py must never modify a live .harness store")
        self.assertEqual(before_events, after_events,
                          "reputation.py must never append to the live events.jsonl")
        self.assertEqual(before_paths, after_paths,
                          "reputation.py must never create a temp file anywhere under .harness/")


if __name__ == "__main__":
    unittest.main()
