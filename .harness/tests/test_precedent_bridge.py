"""Unit tests for the displacement-bridge enforcement in the `--overrules`
path of .harness/bin/precedent.py (T-370).

Implements EXACTLY what `docs/precedent-research/synthesis-addendum-ii-
spec.md` section 3 fixes (`AD2-30`..`AD2-39`), enacted by the tier-1 record
`PR-019` (subject `displacement-bridge-embedding`, published by T-369
BEFORE this file, per PR-017's record-before-code procedure -- confirmed
active at T-370's start: `status: active`, `authority_tier: 1`,
`issuing_task: T-369`). Every test method cites the `AD2-NN` requirement id
and/or the exact refusal message it targets, mirroring the convention
already used across `test_precedent.py`/`test_precedent_v2.py`/
`test_precedent_conflicts.py`.

Every test invokes the real CLI via subprocess against an isolated `--root`
(a fresh TemporaryDirectory per test) -- NOTHING here ever writes a
PR-*.json record under the live `.harness/precedents/` registry, and
`LiveIsolationTests` snapshots the live `.harness/logs/events.jsonl` line
count and the live `precedents/` file set before/after a representative
battery of calls (success, refusal, decision-anchor) run entirely under
overridden roots, proving zero contamination (V1-06/V1-48; AD2-35 mints no
new event kind).
"""
import argparse
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PRECEDENT_PY = ROOT / ".harness" / "bin" / "precedent.py"
LIVE_REGISTRY = ROOT / ".harness" / "precedents"
LIVE_EVENTS = ROOT / ".harness" / "logs" / "events.jsonl"

# Real, permanent, tracked task files used as decision:-anchor T-NNN halves
# and as ordinary resolvable T tokens -- never a fixture this file created.
REAL_TASK_A = "T-330"
REAL_TASK_B = "T-344"  # the T-NNN half of PR-009's own live target, decision:T-344#R-2
NEVER_REAL_TASK = "T-999999"

# AD2-34's fixed marker, quoted here rather than imported so a test failure
# shows the literal string a human can diff against the spec by eye.
DECISION_ANCHOR_MARKER = "unavailable: decision-anchored target has no published_by"


def run(*args, env=None):
    cmd = [sys.executable, str(PRECEDENT_PY)] + list(args)
    return subprocess.run(cmd, text=True, capture_output=True, env=env)


def live_events_line_count():
    try:
        with open(LIVE_EVENTS, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def live_pr_files():
    if not LIVE_REGISTRY.exists():
        return set()
    return set(p.name for p in LIVE_REGISTRY.glob("PR-*.json"))


class BridgeTestCase(unittest.TestCase):
    """Base class: isolated registry root per test (never the live one)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name) / "registry"
        self._file_counter = 0

    def tearDown(self):
        self._tmp.cleanup()

    # -- shared helpers -----------------------------------------------

    def publish(self, task="T-100", title="Title", subject="subject-a", tier=3,
                tier_evidence=None, ratio="some ratio text", width="narrow",
                scope=None, revisit_trigger=None, sources=None, validity=None,
                code_version="v1", extra_args=None, root=None):
        root = root if root is not None else self.root
        te = tier_evidence if tier_evidence is not None else [REAL_TASK_A]
        src = sources if sources is not None else [REAL_TASK_A]
        args = ["publish", "--root", str(root), "--task", task, "--title", title,
                "--subject", subject, "--tier", str(tier), "--ratio", ratio, "--width", width,
                "--code-version", code_version]
        for t in te:
            args += ["--tier-evidence", t]
        for s in src:
            args += ["--sources", s]
        if tier in (1, 2, 3):
            sc = scope if scope is not None else ["role:worker"]
            rt = revisit_trigger if revisit_trigger is not None else "revisit if X"
            vc = validity if validity is not None else ["validity condition placeholder"]
            for s in sc:
                args += ["--scope", s]
            args += ["--revisit-trigger", rt]
            for v in vc:
                args += ["--validity", v]
        if extra_args:
            args += extra_args
        return run(*args)

    def publish_ok(self, **kwargs):
        result = self.publish(**kwargs)
        self.assertEqual(result.returncode, 0, "stdout={!r} stderr={!r}".format(result.stdout, result.stderr))
        pr_id = result.stdout.strip().splitlines()[-1].split()[-1]
        return pr_id, result

    def load(self, pr_id, root=None):
        root = root if root is not None else self.root
        return json.loads((root / (pr_id + ".json")).read_text(encoding="utf-8"))

    def record_files(self, root=None):
        root = root if root is not None else self.root
        if not root.exists():
            return set()
        return set(p.name for p in root.glob("PR-*.json"))

    def write_ratio_file(self, text):
        self._file_counter += 1
        f = pathlib.Path(self._tmp.name) / "ratio-{}.txt".format(self._file_counter)
        f.write_text(text, encoding="utf-8")
        return f

    def overrule_embedding_args(self, target_id, root=None):
        """The four flags a compliant --overrules call needs, read straight
        off the target's own on-disk fields so the AD2-33 byte-exact ratio
        match always holds."""
        target = self.load(target_id, root=root)
        f = self.write_ratio_file(target["ratio"])
        return ["--overruled-ratio-file", str(f),
                "--overruled-record-id", target_id,
                "--overruled-published-by", target["published_by"],
                "--overruled-issuing-task", target["issuing_task"]]


# ==========================================================================
# A. Presence refusals (AD2-33 checks 1-4) -- ratio, then each of the three
#    authorship elements missing in turn, each its own test method.
# ==========================================================================

class PresenceRefusalTests(BridgeTestCase):
    def test_refusal_no_embedded_ratio(self):
        target_id, _ = self.publish_ok(task="T-700", subject="bridge-target-a", tier=3,
                                        ratio="the overruled ratio, verbatim")
        result = self.publish(task="T-701", subject="bridge-successor-a", tier=3,
                               extra_args=["--overrules", target_id, "--factor", "doctrinal_change",
                                           "--factor-note", "note",
                                           "--overruled-record-id", target_id,
                                           "--overruled-published-by", "someone",
                                           "--overruled-issuing-task", "T-700"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stderr.strip(),
            "refused: --overrules requires --overruled-ratio or --overruled-ratio-file: the "
            "overruled ratio must be embedded verbatim (AD2-33)")
        # nothing was written -- only the target file exists.
        self.assertEqual(self.record_files(), {target_id + ".json"})

    def test_refusal_missing_record_id(self):
        target_id, _ = self.publish_ok(task="T-702", subject="bridge-target-b", tier=3,
                                        ratio="the overruled ratio, verbatim")
        result = self.publish(task="T-703", subject="bridge-successor-b", tier=3,
                               extra_args=["--overrules", target_id, "--factor", "doctrinal_change",
                                           "--factor-note", "note",
                                           "--overruled-ratio", "the overruled ratio, verbatim",
                                           "--overruled-published-by", "someone",
                                           "--overruled-issuing-task", "T-702"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stderr.strip(),
            "refused: --overrules requires --overruled-record-id: authorship element "
            "'record id' is missing (AD2-33)")
        self.assertEqual(self.record_files(), {target_id + ".json"})

    def test_refusal_missing_published_by(self):
        target_id, _ = self.publish_ok(task="T-704", subject="bridge-target-c", tier=3,
                                        ratio="the overruled ratio, verbatim")
        result = self.publish(task="T-705", subject="bridge-successor-c", tier=3,
                               extra_args=["--overrules", target_id, "--factor", "doctrinal_change",
                                           "--factor-note", "note",
                                           "--overruled-ratio", "the overruled ratio, verbatim",
                                           "--overruled-record-id", target_id,
                                           "--overruled-issuing-task", "T-704"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stderr.strip(),
            "refused: --overrules requires --overruled-published-by: authorship element "
            "'published_by' is missing (AD2-33)")
        self.assertEqual(self.record_files(), {target_id + ".json"})

    def test_refusal_missing_issuing_task(self):
        target_id, _ = self.publish_ok(task="T-706", subject="bridge-target-d", tier=3,
                                        ratio="the overruled ratio, verbatim")
        result = self.publish(task="T-707", subject="bridge-successor-d", tier=3,
                               extra_args=["--overrules", target_id, "--factor", "doctrinal_change",
                                           "--factor-note", "note",
                                           "--overruled-ratio", "the overruled ratio, verbatim",
                                           "--overruled-record-id", target_id,
                                           "--overruled-published-by", "someone"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stderr.strip(),
            "refused: --overrules requires --overruled-issuing-task: authorship element "
            "'issuing task' is missing (AD2-33)")
        self.assertEqual(self.record_files(), {target_id + ".json"})

    def test_refusal_whitespace_only_ratio_treated_as_absent(self):
        """AD2-35's own note: 'the first message covers both absence and
        whitespace-only content'."""
        target_id, _ = self.publish_ok(task="T-708", subject="bridge-target-e", tier=3)
        result = self.publish(task="T-709", subject="bridge-successor-e", tier=3,
                               extra_args=["--overrules", target_id, "--factor", "doctrinal_change",
                                           "--factor-note", "note", "--overruled-ratio", "   ",
                                           "--overruled-record-id", target_id,
                                           "--overruled-published-by", "someone",
                                           "--overruled-issuing-task", "T-708"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("the overruled ratio must be embedded verbatim (AD2-33)", result.stderr)


# ==========================================================================
# B. Verification-against-the-registry refusals (AD2-33 checks 5-8): once
#    all four elements are present, each is checked against the target's
#    own stored fields.
# ==========================================================================

class VerificationMismatchTests(BridgeTestCase):
    def test_refusal_record_id_does_not_name_target(self):
        target_id, _ = self.publish_ok(task="T-710", subject="bridge-mismatch-a", tier=3,
                                        ratio="ratio text A")
        args = self.overrule_embedding_args(target_id)
        args[args.index("--overruled-record-id") + 1] = "PR-999"
        result = self.publish(task="T-711", subject="bridge-mismatch-a2", tier=3,
                               extra_args=["--overrules", target_id, "--factor", "doctrinal_change",
                                           "--factor-note", "note"] + args)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stderr.strip(),
            "refused: --overruled-record-id 'PR-999' does not name the --overrules target "
            "'{}' (AD2-33)".format(target_id))

    def test_refusal_ratio_does_not_match_byte_for_byte(self):
        target_id, _ = self.publish_ok(task="T-712", subject="bridge-mismatch-b", tier=3,
                                        ratio="ratio text B")
        tampered = self.write_ratio_file("ratio text B, tampered by one character")
        target = self.load(target_id)
        result = self.publish(
            task="T-713", subject="bridge-mismatch-b2", tier=3,
            extra_args=["--overrules", target_id, "--factor", "doctrinal_change", "--factor-note", "note",
                        "--overruled-ratio-file", str(tampered),
                        "--overruled-record-id", target_id,
                        "--overruled-published-by", target["published_by"],
                        "--overruled-issuing-task", target["issuing_task"]])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stderr.strip(),
            "refused: embedded ratio does not match {}'s stored ratio byte-for-byte "
            "(AD2-33)".format(target_id))

    def test_refusal_published_by_does_not_match(self):
        target_id, _ = self.publish_ok(task="T-714", subject="bridge-mismatch-c", tier=3,
                                        ratio="ratio text C")
        target = self.load(target_id)
        args = self.overrule_embedding_args(target_id)
        args[args.index("--overruled-published-by") + 1] = "wrong-author"
        result = self.publish(task="T-715", subject="bridge-mismatch-c2", tier=3,
                               extra_args=["--overrules", target_id, "--factor", "doctrinal_change",
                                           "--factor-note", "note"] + args)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stderr.strip(),
            "refused: --overruled-published-by 'wrong-author' does not match {}'s published_by "
            "'{}' (AD2-33)".format(target_id, target["published_by"]))

    def test_refusal_issuing_task_does_not_match(self):
        target_id, _ = self.publish_ok(task="T-716", subject="bridge-mismatch-d", tier=3,
                                        ratio="ratio text D")
        target = self.load(target_id)
        args = self.overrule_embedding_args(target_id)
        args[args.index("--overruled-issuing-task") + 1] = "T-999"
        result = self.publish(task="T-717", subject="bridge-mismatch-d2", tier=3,
                               extra_args=["--overrules", target_id, "--factor", "doctrinal_change",
                                           "--factor-note", "note"] + args)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stderr.strip(),
            "refused: --overruled-issuing-task 'T-999' does not match {}'s issuing_task "
            "'{}' (AD2-33)".format(target_id, target["issuing_task"]))


# ==========================================================================
# C. Success: the complete embedding, stored byte-for-byte (AD2-32/AD2-33).
# ==========================================================================

class SuccessEmbeddingTests(BridgeTestCase):
    def test_success_complete_embedding_stores_predecessor_byte_for_byte(self):
        target_id, _ = self.publish_ok(
            task="T-720", subject="bridge-success-a", tier=3,
            ratio="the exact ratio text that must survive verbatim, including 'quotes', "
                  "punctuation, and a trailing newline.\n")
        successor_id, _ = self.publish_ok(
            task="T-721", subject="bridge-success-a2", tier=3,
            extra_args=["--overrules", target_id, "--factor", "doctrinal_change", "--factor-note", "note"]
            + self.overrule_embedding_args(target_id))
        target_rec = self.load(target_id)
        successor_rec = self.load(successor_id)
        rel = successor_rec["relations"][0]
        self.assertEqual(rel["type"], "overrules")
        embedded = rel["overruled_predecessor"]
        # AD2-32: exactly these four keys, present on the relation object.
        self.assertEqual(sorted(embedded), ["issuing_task", "published_by", "ratio", "record_id"])
        # AD2-33: byte-for-byte, no strip, no normalization.
        self.assertEqual(embedded["ratio"], target_rec["ratio"])
        self.assertEqual(embedded["record_id"], target_id)
        self.assertEqual(embedded["published_by"], target_rec["published_by"])
        self.assertEqual(embedded["issuing_task"], target_rec["issuing_task"])
        # the shipped side effects (SDR-19.3/19.4) are untouched by the new field.
        self.assertEqual(target_rec["status"], "overruled")
        self.assertEqual(target_rec["overruled_by"], successor_id)
        self.assertIn(successor_id, target_rec["cited_by"])

    def test_success_other_relations_on_the_same_record_stay_null(self):
        """A record that carries BOTH a --follows and an --overrules
        relation only embeds the predecessor on the overrules relation."""
        followed_id, _ = self.publish_ok(task="T-722", subject="bridge-success-b", tier=4)
        overruled_id, _ = self.publish_ok(task="T-723", subject="bridge-success-c", tier=3,
                                           ratio="to be overruled")
        successor_id, _ = self.publish_ok(
            task="T-724", subject="bridge-success-d", tier=3,
            extra_args=["--follows", followed_id, "--overrules", overruled_id,
                        "--factor", "doctrinal_change", "--factor-note", "note"]
            + self.overrule_embedding_args(overruled_id))
        rec = self.load(successor_id)
        by_type = {r["type"]: r for r in rec["relations"]}
        self.assertIsNone(by_type["follows"]["overruled_predecessor"])
        self.assertIsNotNone(by_type["overrules"]["overruled_predecessor"])
        self.assertEqual(by_type["overrules"]["overruled_predecessor"]["record_id"], overruled_id)


# ==========================================================================
# D. The decision-anchor case (AD2-34), as its own case -- PR-009's own
#    live target decision:T-344#R-2 is exactly this shape.
# ==========================================================================

class DecisionAnchorTests(BridgeTestCase):
    def _decision_token(self, task=REAL_TASK_B, anchor="R-2"):
        return "decision:{}#{}".format(task, anchor)

    def test_decision_anchor_success(self):
        pr_id, _ = self.publish_ok(
            task="T-730", subject="bridge-decision-a", tier=1, tier_evidence=[REAL_TASK_A],
            extra_args=["--overrules", self._decision_token(), "--target-tier", "3",
                        "--factor", "doctrinal_change", "--factor-note", "note",
                        "--overruled-ratio", "the publisher's own quotation of R-2's framing",
                        "--overruled-record-id", self._decision_token(),
                        "--overruled-published-by", DECISION_ANCHOR_MARKER,
                        "--overruled-issuing-task", REAL_TASK_B])
        rec = self.load(pr_id)
        rel = rec["relations"][0]
        self.assertEqual(rel["type"], "overrules")
        self.assertEqual(rel["target"], self._decision_token())
        embedded = rel["overruled_predecessor"]
        self.assertEqual(sorted(embedded), ["issuing_task", "published_by", "ratio", "record_id"])
        self.assertEqual(embedded["record_id"], self._decision_token())
        self.assertEqual(embedded["published_by"], DECISION_ANCHOR_MARKER)
        self.assertEqual(embedded["issuing_task"], REAL_TASK_B)
        self.assertEqual(embedded["ratio"], "the publisher's own quotation of R-2's framing")
        # V1-32, unaffected by this task: no PR file exists for the target.
        self.assertEqual(self.record_files(), {pr_id + ".json"})

    def test_decision_anchor_refuses_wrong_published_by_marker(self):
        result = self.publish(
            task="T-731", subject="bridge-decision-b", tier=1, tier_evidence=[REAL_TASK_A],
            extra_args=["--overrules", self._decision_token(), "--target-tier", "3",
                        "--factor", "doctrinal_change", "--factor-note", "note",
                        "--overruled-ratio", "quoted text",
                        "--overruled-record-id", self._decision_token(),
                        "--overruled-published-by", "some real name",
                        "--overruled-issuing-task", REAL_TASK_B])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stderr.strip(),
            "refused: --overruled-published-by for the decision-anchored target {} must be "
            "exactly: {} (AD2-34)".format(self._decision_token(), DECISION_ANCHOR_MARKER))

    def test_decision_anchor_refuses_issuing_task_not_matching_anchor_half(self):
        result = self.publish(
            task="T-732", subject="bridge-decision-c", tier=1, tier_evidence=[REAL_TASK_A],
            extra_args=["--overrules", self._decision_token(), "--target-tier", "3",
                        "--factor", "doctrinal_change", "--factor-note", "note",
                        "--overruled-ratio", "quoted text",
                        "--overruled-record-id", self._decision_token(),
                        "--overruled-published-by", DECISION_ANCHOR_MARKER,
                        "--overruled-issuing-task", REAL_TASK_A])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stderr.strip(),
            "refused: --overruled-issuing-task '{}' must be the T-NNN half of the "
            "decision-anchored target {} (AD2-34)".format(REAL_TASK_A, self._decision_token()))

    def test_decision_anchor_refuses_record_id_not_matching_anchor_token(self):
        result = self.publish(
            task="T-733", subject="bridge-decision-d", tier=1, tier_evidence=[REAL_TASK_A],
            extra_args=["--overrules", self._decision_token(), "--target-tier", "3",
                        "--factor", "doctrinal_change", "--factor-note", "note",
                        "--overruled-ratio", "quoted text",
                        "--overruled-record-id", "decision:T-999999#R-9",
                        "--overruled-published-by", DECISION_ANCHOR_MARKER,
                        "--overruled-issuing-task", REAL_TASK_B])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stderr.strip(),
            "refused: --overruled-record-id 'decision:T-999999#R-9' does not name the "
            "--overrules target '{}' (AD2-33)".format(self._decision_token()))

    def test_decision_anchor_still_requires_presence_first(self):
        """Checks 1-4 (AD2-33) apply to the decision-anchored branch too --
        this is the CLI-reachable regression baseline for AD2-30..AD2-35:
        before T-370, this exact call published clean (section 9.2's own
        replayed baseline)."""
        result = self.publish(
            task="T-735", subject="bridge-decision-e", tier=1, tier_evidence=[REAL_TASK_A],
            extra_args=["--overrules", self._decision_token(), "--target-tier", "3",
                        "--factor", "doctrinal_change", "--factor-note", "note"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stderr.strip(),
            "refused: --overrules requires --overruled-ratio or --overruled-ratio-file: the "
            "overruled ratio must be embedded verbatim (AD2-33)")

    def test_decision_anchor_ruling_matches_pr009s_own_target_shape(self):
        """The exact scenario AD2-34's ruling exists for: PR-009's own live
        target decision:T-344#R-2 (replayed synthetically here; this file
        never touches the live registry)."""
        self.assertEqual(self._decision_token(), "decision:T-344#R-2")
        pr_id, _ = self.publish_ok(
            task="T-736", subject="bridge-decision-pr009-shape", tier=1, tier_evidence=[REAL_TASK_A],
            extra_args=["--overrules", "decision:T-344#R-2", "--target-tier", "3",
                        "--factor", "unworkability", "--factor-note",
                        "reasoning no longer holds",
                        "--overruled-ratio",
                        "repeated confirmation becomes a separate, non-binding reiterated flag "
                        "on tier-4 records -- not a replacement of tier 3 and not a new binding tier",
                        "--overruled-record-id", "decision:T-344#R-2",
                        "--overruled-published-by", DECISION_ANCHOR_MARKER,
                        "--overruled-issuing-task", "T-344"])
        rec = self.load(pr_id)
        self.assertEqual(rec["relations"][0]["target"], "decision:T-344#R-2")


# ==========================================================================
# E. Negative control (AD2-35's own words): "any publish with no
#    --overrules is completely unaffected". The enforcement must not tax
#    ordinary publishes.
# ==========================================================================

class NegativeControlTests(BridgeTestCase):
    def test_ordinary_publish_no_overrules_unaffected(self):
        pr_id, result = self.publish_ok(task="T-740", subject="bridge-negative-a", tier=4)
        self.assertNotIn("AD2-", result.stderr)
        self.assertEqual(result.stderr, "")
        rec = self.load(pr_id)
        self.assertEqual(rec["relations"], [])

    def test_follows_relation_carries_present_but_null_overruled_predecessor(self):
        target_id, _ = self.publish_ok(task="T-741", subject="bridge-negative-b", tier=4)
        acting_id, _ = self.publish_ok(task="T-742", subject="bridge-negative-c", tier=4,
                                        extra_args=["--follows", target_id])
        rec = self.load(acting_id)
        self.assertEqual(rec["relations"][0]["type"], "follows")
        self.assertIn("overruled_predecessor", rec["relations"][0])  # present ...
        self.assertIsNone(rec["relations"][0]["overruled_predecessor"])  # ... and null

    def test_distinguishes_relation_unaffected(self):
        target_id, _ = self.publish_ok(task="T-743", subject="bridge-negative-d", tier=1,
                                        tier_evidence=[REAL_TASK_A])
        acting_id, result = self.publish_ok(
            task="T-744", subject="bridge-negative-e", tier=4,
            extra_args=["--distinguishes", target_id, "--distinguishing-facts", "facts differ"])
        self.assertNotIn("AD2-", result.stderr)
        rec = self.load(acting_id)
        self.assertIsNone(rec["relations"][0]["overruled_predecessor"])

    def test_supersedes_and_voids_are_out_of_scope_by_delimitation(self):
        """AD2-38: the enforcement binds --overrules ONLY. A --supersedes
        (or --voids) publish that carries none of the five new flags is
        CORRECT-PER-SPEC and must still succeed -- widening the refusal to
        those relation types is explicitly out of scope for this task."""
        target_id, _ = self.publish_ok(task="T-745", subject="bridge-negative-f", tier=3)
        acting_id, result = self.publish_ok(task="T-746", subject="bridge-negative-g", tier=3,
                                             extra_args=["--supersedes", target_id])
        self.assertNotIn("AD2-", result.stderr)
        rec = self.load(acting_id)
        self.assertIsNone(rec["relations"][0]["overruled_predecessor"])


# ==========================================================================
# F. Defensive coverage of AD2-35 message 11, which is structurally
#    UNREACHABLE through the CLI (check 10 already forces
#    --overruled-issuing-task to equal the anchor's T-NNN half, and that
#    half was already proven to resolve by the earlier, pre-existing
#    relation-target check that runs before any of this task's checks).
#    Exercised directly against build_overruled_predecessor() so the
#    branch as written is still verified, without claiming a real publish
#    call can reach it.
# ==========================================================================

def _import_precedent_module():
    spec = importlib.util.spec_from_file_location("precedent_bridge_under_test", str(PRECEDENT_PY))
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(PRECEDENT_PY.parent))  # so precedent's own `import harness_common` resolves
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(PRECEDENT_PY.parent))
    return mod


class DefensiveUnreachableBranchTests(unittest.TestCase):
    def test_message_11_fires_when_the_task_store_check_is_exercised_directly(self):
        precedent = _import_precedent_module()
        rel = precedent.make_relation("overrules", "decision:{}#R-1".format(NEVER_REAL_TASK))
        args = argparse.Namespace(
            overruled_record_id="decision:{}#R-1".format(NEVER_REAL_TASK),
            overruled_published_by=precedent.DECISION_ANCHOR_PUBLISHED_BY_MARKER,
            overruled_issuing_task=NEVER_REAL_TASK,
        )
        _predecessor, err = precedent.build_overruled_predecessor(
            rel, {}, args, "a quotation of the anchored decision", ROOT / ".harness" / "precedents")
        self.assertIsNotNone(err)
        self.assertEqual(
            err,
            "--overruled-issuing-task '{}' does not resolve against the tasks store "
            "(AD2-34)".format(NEVER_REAL_TASK))


# ==========================================================================
# G. Live-substrate isolation: zero writes to .harness/precedents/, zero
#    new lines in .harness/logs/events.jsonl, across a representative
#    battery of success/refusal/decision-anchor calls run entirely under
#    overridden roots (V1-06/V1-48).
# ==========================================================================

class LiveIsolationTests(BridgeTestCase):
    def test_battery_of_bridge_calls_never_touches_the_live_substrate(self):
        before_events = live_events_line_count()
        before_pr_files = live_pr_files()

        target_id, _ = self.publish_ok(task="T-750", subject="bridge-iso-a", tier=3,
                                        ratio="isolation target ratio")
        # a refusal (also event-logged, still under the override root)
        refused = self.publish(task="T-751", subject="bridge-iso-b", tier=3,
                                extra_args=["--overrules", target_id, "--factor",
                                            "doctrinal_change", "--factor-note", "note"])
        self.assertEqual(refused.returncode, 1)
        # a success
        successor_id, _ = self.publish_ok(
            task="T-752", subject="bridge-iso-c", tier=3,
            extra_args=["--overrules", target_id, "--factor", "doctrinal_change", "--factor-note", "note"]
            + self.overrule_embedding_args(target_id))
        # a decision-anchored success
        self.publish_ok(
            task="T-753", subject="bridge-iso-d", tier=1, tier_evidence=[REAL_TASK_A],
            extra_args=["--overrules", "decision:{}#R-2".format(REAL_TASK_B), "--target-tier", "3",
                        "--factor", "doctrinal_change", "--factor-note", "note",
                        "--overruled-ratio", "quoted text",
                        "--overruled-record-id", "decision:{}#R-2".format(REAL_TASK_B),
                        "--overruled-published-by", DECISION_ANCHOR_MARKER,
                        "--overruled-issuing-task", REAL_TASK_B])

        after_events = live_events_line_count()
        after_pr_files = live_pr_files()
        self.assertEqual(before_events, after_events,
                          "a bridge-enforcement call under an OVERRIDDEN root must never append "
                          "to the live .harness/logs/events.jsonl (V1-06/V1-48)")
        self.assertEqual(before_pr_files, after_pr_files,
                          "a bridge-enforcement call under an OVERRIDDEN root must never write "
                          "into the live .harness/precedents/ registry")
        # and the sidecar under the overridden root DID receive the events
        # (the flip side of isolation -- events are not simply dropped).
        sidecar = self.root / "events.jsonl"
        self.assertTrue(sidecar.exists())
        lines = [json.loads(l) for l in sidecar.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertTrue(any(rec.get("event") == "precedent_publish_refused" for rec in lines))
        self.assertTrue(any(rec.get("event") == "precedent_published" and rec.get("id") == successor_id
                             for rec in lines))


if __name__ == "__main__":
    unittest.main()
