"""Unit tests for the schema v2 core of .harness/bin/precedent.py (T-353).

Covers exactly T-353's slice of `docs/precedent-research/synthesis-v1-
requirements.md`: the schema v2 field table (sources, validity_conditions,
operation, interpretive_code_version -- V1-10..V1-17), the citation-token
grammar extension (`doi:`/`decision:` -- V1-18/V1-19), the corrective-
sources enforcement (A1 -- V1-11/V1-20/V1-21), typed operations and their
per-operation required-field matrix (A4 -- V1-13/V1-14), the task-anchored
overruling anchor mechanism (V1-31/V1-32), the `migrate` verb's mechanics
(V1-36/V1-37/V1-40), and the two carried defects from T-346 (V1-48 test-
event isolation; V1-49 supersedes tier check). Does NOT test graded force,
decay, `stale`, or the show/list v2 stdout lines -- those are T-354's
routing (V1-22..V1-30, V1-34/V1-35, V1-43/V1-44), tested in T-354's own
test file.

Convention matches test_precedent.py/test_precedent_conflicts.py: every
test invokes the real CLI via subprocess against an isolated `--root` (a
fresh TemporaryDirectory per test), except the dedicated carried-defect-i
class which additionally snapshots the LIVE `.harness/logs/events.jsonl`
line count before/after a full publish/confirm/overrule cycle run entirely
under an overridden root -- NOTHING in this file ever writes a PR-*.json
record under the live `.harness/precedents/` registry (T-353's own
OWNS-EXACTLY clause forbids it).
"""
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
REAL_TASK_B = "T-344"
REAL_TASK_C = "T-339"
NEVER_REAL_TASK = "T-999999"

CANONICAL_DOI = "doi:10.22201/iij.24487937e.2026.20.20316#3"


def run(*args, input_text=None, env=None):
    cmd = [sys.executable, str(PRECEDENT_PY)] + list(args)
    return subprocess.run(cmd, input=input_text, text=True, capture_output=True, env=env)


def live_events_line_count():
    try:
        with open(LIVE_EVENTS, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


class V2TestCase(unittest.TestCase):
    """Base class: isolated registry root per test (never the live one)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name) / "registry"

    def tearDown(self):
        self._tmp.cleanup()

    # -- shared helpers -----------------------------------------------

    def publish(self, task="T-100", title="Title", subject="subject-a", tier=4,
                tier_evidence=None, ratio="some ratio text", width="narrow",
                scope=None, revisit_trigger=None, sources=None, validity=None,
                code_version="v1", operation=None, operation_subtype=None,
                extra_args=None, root=None, env=None):
        root = root if root is not None else self.root
        te = tier_evidence if tier_evidence is not None else [REAL_TASK_A]
        src = sources if sources is not None else [REAL_TASK_A]
        args = ["publish", "--root", str(root), "--task", task, "--title", title,
                "--subject", subject, "--tier", str(tier), "--ratio", ratio, "--width", width]
        if code_version is not None:
            args += ["--code-version", code_version]
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
        else:
            if scope is not None:
                for s in scope:
                    args += ["--scope", s]
            if revisit_trigger is not None:
                args += ["--revisit-trigger", revisit_trigger]
            if validity is not None:
                for v in validity:
                    args += ["--validity", v]
        if operation is not None:
            args += ["--operation", operation]
        if operation_subtype is not None:
            args += ["--operation-subtype", operation_subtype]
        if extra_args:
            args += extra_args
        return run(*args, env=env)

    def publish_ok(self, **kwargs):
        result = self.publish(**kwargs)
        self.assertEqual(result.returncode, 0, "stdout={!r} stderr={!r}".format(result.stdout, result.stderr))
        pr_id = result.stdout.strip().splitlines()[-1].split()[-1]
        return pr_id, result

    def load(self, pr_id, root=None):
        root = root if root is not None else self.root
        return json.loads((root / (pr_id + ".json")).read_text(encoding="utf-8"))

    def overrule_embedding_args(self, target_id, root=None):
        """T-370 amendment (PR-019, A.3.1): every successful `--overrules`
        call against a PR-NNN target now must embed the overruled record's
        ratio verbatim plus its authorship (record id, published_by,
        issuing task) or the publish is refused. Reads the target's own
        on-disk fields so the required byte-exact ratio match holds
        regardless of this test's own ratio/agent/task values -- see the
        amended-assertion list in this task's handoff."""
        target = self.load(target_id, root=root)
        ratio_file = pathlib.Path(self._tmp.name) / (target_id + "-overruled-ratio.txt")
        ratio_file.write_text(target["ratio"], encoding="utf-8")
        return ["--overruled-ratio-file", str(ratio_file),
                "--overruled-record-id", target_id,
                "--overruled-published-by", target["published_by"],
                "--overruled-issuing-task", target["issuing_task"]]

    def record_files(self, root=None):
        root = root if root is not None else self.root
        if not root.exists():
            return set()
        return set(p.name for p in root.glob("PR-*.json"))

    def write_v1_record(self, root, pr_id, **fields):
        """A hand-crafted schema_version-1-shaped record: no sources,
        validity_conditions, operation, or interpretive_code_version --
        exactly the shape T-353 must dual-read (V1-36) since the live
        registry stays at v1 until T-355 runs `migrate`."""
        root = pathlib.Path(root)
        root.mkdir(parents=True, exist_ok=True)
        rec = {
            "id": pr_id, "schema_version": 1, "title": "v1 record", "subject": "v1-subject",
            "status": "active", "authority_tier": 3, "tier_evidence": [REAL_TASK_A],
            "ratio": "a v1-shaped ratio", "dicta": [], "scope_conditions": ["role:worker"],
            "declared_width": "narrow", "revisit_trigger": "revisit if v1 changes",
            "confirmation_status": "unconfirmed", "confirmed_by": None, "confirmed_at": None,
            "narrowed_scope": None, "confirmation_note": None, "relations": [], "cites": [],
            "cited_by": [], "overruled_by": None, "superseded_by": None, "voided_by": None,
            "issuing_task": REAL_TASK_A, "published_by": "v1-author",
            "published_at": "2026-01-01T00:00:00Z",
        }
        rec.update(fields)
        (root / (pr_id + ".json")).write_text(json.dumps(rec, indent=2), encoding="utf-8")
        return rec


# ==========================================================================
# A. Schema v2 field table -- defaults and presence (V1-10)
# ==========================================================================

class SchemaV2FieldTests(V2TestCase):
    def test_publish_writes_schema_version_2(self):
        pr_id, _ = self.publish_ok()
        rec = self.load(pr_id)
        self.assertEqual(rec["schema_version"], 2)

    def test_operation_defaults_to_determination_when_omitted(self):
        """V1-13: 'The CLI flag defaults to determination, so every
        v0-shaped publish writes {"type": "determination", "subtype":
        null}' -- the field is ALWAYS present."""
        pr_id, _ = self.publish_ok()
        rec = self.load(pr_id)
        self.assertEqual(rec["operation"], {"type": "determination", "subtype": None})

    def test_interpretive_code_version_stored_exactly(self):
        pr_id, _ = self.publish_ok(code_version="v3")
        rec = self.load(pr_id)
        self.assertEqual(rec["interpretive_code_version"], "v3")

    def test_validity_conditions_optional_at_tier4_defaults_empty(self):
        pr_id, _ = self.publish_ok(tier=4)
        rec = self.load(pr_id)
        self.assertEqual(rec["validity_conditions"], [])

    def test_validity_conditions_stored_at_tier1(self):
        pr_id, _ = self.publish_ok(tier=1, tier_evidence=[REAL_TASK_A],
                                    validity=["path exists check", ".harness/bin/precedent.py:1"])
        rec = self.load(pr_id)
        self.assertEqual(rec["validity_conditions"], ["path exists check", ".harness/bin/precedent.py:1"])

    def test_sources_stored_exactly(self):
        pr_id, _ = self.publish_ok(sources=[REAL_TASK_A, REAL_TASK_B])
        rec = self.load(pr_id)
        self.assertEqual(rec["sources"], [REAL_TASK_A, REAL_TASK_B])

    def test_validity_file_form(self):
        vfile = pathlib.Path(self._tmp.name) / "validity.txt"
        vfile.write_text("entry one\n\nentry two\n", encoding="utf-8")
        # validity=[] suppresses the helper's own auto-injected placeholder
        # --validity flag (mutually exclusive with --validity-file).
        pr_id, _ = self.publish_ok(tier=1, tier_evidence=[REAL_TASK_A], validity=[],
                                    extra_args=["--validity-file", str(vfile)])
        rec = self.load(pr_id)
        self.assertEqual(rec["validity_conditions"], ["entry one", "entry two"])


# ==========================================================================
# B. Sources enforcement (A1, V1-11/V1-20/V1-21)
# ==========================================================================

class SourcesEnforcementTests(V2TestCase):
    def test_missing_sources_on_plain_determination_refused_generic_message(self):
        result = self.publish(sources=[])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("sources must be non-empty (A1, V1-11)", result.stderr)
        self.assertEqual(self.record_files(), set())

    def test_missing_sources_on_overrules_refused_with_a1_message_no_file_written(self):
        """Board T-353 AC-4's mandated test: exact exit code AND that no
        record file was created by the refused call."""
        target_id, _ = self.publish_ok(task="T-500", subject="subj-a1-target", tier=3)
        before = self.record_files()
        result = self.publish(task="T-501", subject="subj-a1-actor", tier=3, sources=[],
                               extra_args=["--overrules", target_id, "--factor", "unworkability",
                                           "--factor-note", "note"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("corrective act cites no sources (A1, V1-20)", result.stderr)
        after = self.record_files()
        self.assertEqual(before, after, "a refused corrective publish must create no record file")

    def test_missing_sources_on_voids_refused_with_a1_message(self):
        target_id, _ = self.publish_ok(task="T-502", subject="subj-a1-void-target", tier=3)
        result = self.publish(task="T-503", subject="subj-a1-void-actor", tier=3, sources=[],
                               extra_args=["--voids", target_id, "--controlling-authority", REAL_TASK_A])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("corrective act cites no sources (A1, V1-20)", result.stderr)

    def test_missing_sources_on_corrective_reinterpretation_refused_with_a1_message(self):
        target_id, _ = self.publish_ok(task="T-504", subject="subj-a1-corr-target", tier=3)
        result = self.publish(task="T-505", subject="subj-a1-corr-actor", tier=3, sources=[],
                               operation="reinterpretation", operation_subtype="corrective-restrictive",
                               extra_args=["--reinterprets", target_id])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("corrective act cites no sources (A1, V1-20)", result.stderr)

    def test_sources_present_but_dangling_warns_not_refuses(self):
        result = self.publish(sources=[NEVER_REAL_TASK])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dangling", result.stdout.lower())
        self.assertIn(NEVER_REAL_TASK, result.stdout)

    def test_sources_delta_warning_when_corrective_cites_nothing_new(self):
        target_id, _ = self.publish_ok(task="T-506", subject="subj-delta-target", tier=3,
                                        sources=[REAL_TASK_A])
        result = self.publish(task="T-507", subject="subj-delta-actor", tier=3, sources=[REAL_TASK_A],
                               operation="reinterpretation", operation_subtype="corrective-restrictive",
                               extra_args=["--reinterprets", target_id])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("corrective act cites nothing the target did not already consult (V1-21)",
                       result.stdout)

    def test_sources_delta_no_warning_when_new_source_added(self):
        target_id, _ = self.publish_ok(task="T-508", subject="subj-delta2-target", tier=3,
                                        sources=[REAL_TASK_A])
        result = self.publish(task="T-509", subject="subj-delta2-actor", tier=3,
                               sources=[REAL_TASK_A, REAL_TASK_B],
                               operation="reinterpretation", operation_subtype="corrective-restrictive",
                               extra_args=["--reinterprets", target_id])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("V1-21", result.stdout)


# ==========================================================================
# C. validity_conditions requirement (A5, V1-10 #28)
# ==========================================================================

class ValidityConditionsTests(V2TestCase):
    def test_validity_required_nonempty_at_tier1(self):
        result = self.publish(tier=1, tier_evidence=[REAL_TASK_A], validity=[])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("validity_conditions must be non-empty at tiers 1-3", result.stderr)

    def test_validity_required_nonempty_at_tier3(self):
        result = self.publish(tier=3, validity=[])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("validity_conditions must be non-empty at tiers 1-3", result.stderr)


# ==========================================================================
# D. --code-version (A3, V1-15)
# ==========================================================================

class CodeVersionTests(V2TestCase):
    def test_code_version_missing_refused(self):
        result = self.publish(code_version=None)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("--code-version is required", result.stderr)

    def test_code_version_malformed_refused(self):
        result = self.publish(code_version="version-one")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("must match", result.stderr)

    def test_code_version_pre_code_refused_at_publish(self):
        """V1-15: 'pre-code' is the migrate-only sentinel; publish REFUSES it."""
        result = self.publish(code_version="pre-code")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("migrate-only sentinel", result.stderr)


# ==========================================================================
# E. Typed operations + per-operation matrix (A4, V1-13/V1-14)
# One test per operation type INCLUDING its refusal path (board T-353 AC-5).
# ==========================================================================

class TypedOperationDeterminationTests(V2TestCase):
    def test_determination_default_success(self):
        pr_id, _ = self.publish_ok()
        rec = self.load(pr_id)
        self.assertEqual(rec["operation"]["type"], "determination")

    def test_determination_refuses_carrying_reinterprets_relation(self):
        target_id, _ = self.publish_ok(task="T-510", subject="subj-det-target", tier=3)
        result = self.publish(task="T-511", subject="subj-det-actor", tier=3,
                               extra_args=["--reinterprets", target_id])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("a determination may never carry a reinterprets/revalues relation", result.stderr)

    def test_determination_subtype_must_be_null(self):
        result = self.publish(operation="determination", operation_subtype="declarative")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("subtype must be null", result.stderr)

    def test_operation_invalid_type_refused(self):
        result = self.publish(operation="adjudication")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("--operation must be one of", result.stderr)


class TypedOperationReinterpretationTests(V2TestCase):
    def test_reinterpretation_declarative_success(self):
        target_id, _ = self.publish_ok(task="T-520", subject="subj-decl-target", tier=3)
        pr_id, result = self.publish_ok(task="T-521", subject="subj-decl-actor", tier=4,
                                         operation="reinterpretation", operation_subtype="declarative",
                                         extra_args=["--reinterprets", target_id])
        rec = self.load(pr_id)
        self.assertEqual(rec["operation"], {"type": "reinterpretation", "subtype": "declarative"})
        self.assertEqual(len(rec["relations"]), 1)
        self.assertEqual(rec["relations"][0]["type"], "reinterprets")
        self.assertEqual(rec["relations"][0]["target"], target_id)
        # declarative reinterpretation carries NO tier-order refusal: acting
        # tier 4 targeting a tier-2 record succeeds, merely below_target_tier.
        self.assertTrue(rec["relations"][0]["below_target_tier"])
        # V1-07: reinterprets never flips the target's status.
        target_rec = self.load(target_id)
        self.assertEqual(target_rec["status"], "active")
        self.assertIn(pr_id, target_rec["cited_by"])

    def test_reinterpretation_refuses_without_reinterprets_relation(self):
        result = self.publish(operation="reinterpretation", operation_subtype="declarative")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("reinterpretation requires exactly one --reinterprets relation", result.stderr)

    def test_corrective_restrictive_success(self):
        target_id, _ = self.publish_ok(task="T-522", subject="subj-corr-target", tier=3,
                                        sources=[REAL_TASK_A])
        pr_id, _ = self.publish_ok(task="T-523", subject="subj-corr-actor", tier=3,
                                    sources=[REAL_TASK_B],
                                    operation="reinterpretation", operation_subtype="corrective-restrictive",
                                    extra_args=["--reinterprets", target_id])
        rec = self.load(pr_id)
        self.assertEqual(rec["operation"]["subtype"], "corrective-restrictive")

    def test_corrective_refuses_acting_tier_exceeds_target(self):
        """V1-14: corrective reinterpretation refuses when acting tier
        number > target tier number ('sufficient authority level')."""
        target_id, _ = self.publish_ok(task="T-524", subject="subj-corr2-target", tier=1,
                                        tier_evidence=[REAL_TASK_A])
        result = self.publish(task="T-525", subject="subj-corr2-actor", tier=3,
                               operation="reinterpretation", operation_subtype="corrective-extensive",
                               extra_args=["--reinterprets", target_id])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("exceeds target tier", result.stderr)

    def test_corrective_refuses_target_tier4(self):
        """V1-14: corrective reinterpretation of a tier-4 target is a
        category error."""
        target_id, _ = self.publish_ok(task="T-526", subject="subj-corr3-target", tier=4)
        result = self.publish(task="T-527", subject="subj-corr3-actor", tier=4,
                               operation="reinterpretation", operation_subtype="corrective-restrictive",
                               extra_args=["--reinterprets", target_id])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("category error", result.stderr)

    def test_reinterprets_refuses_nonactive_target(self):
        target_id, _ = self.publish_ok(task="T-528", subject="subj-corr4-target", tier=4)
        self.publish_ok(task="T-5281", subject="subj-corr4-target-super", tier=4,
                         extra_args=["--supersedes", target_id])
        result = self.publish(task="T-529", subject="subj-corr4-actor", tier=4,
                               operation="reinterpretation", operation_subtype="declarative",
                               extra_args=["--reinterprets", target_id])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("not active", result.stderr)


class TypedOperationValuationTests(V2TestCase):
    def test_valuation_obiter_success(self):
        target_id, _ = self.publish_ok(task="T-530", subject="subj-val-target", tier=3)
        pr_id, _ = self.publish_ok(task="T-531", subject="subj-val-actor", tier=3,
                                    operation="valuation", operation_subtype="obiter",
                                    extra_args=["--revalues", target_id,
                                                "--valuation-note", "this passage is obiter"])
        rec = self.load(pr_id)
        self.assertEqual(rec["operation"], {"type": "valuation", "subtype": "obiter"})
        self.assertEqual(rec["relations"][0]["type"], "revalues")
        # V1-07: revalues never flips the target's status either.
        target_rec = self.load(target_id)
        self.assertEqual(target_rec["status"], "active")

    def test_valuation_refuses_without_note(self):
        target_id, _ = self.publish_ok(task="T-532", subject="subj-val2-target", tier=3)
        result = self.publish(task="T-533", subject="subj-val2-actor", tier=3,
                               operation="valuation", operation_subtype="obiter",
                               extra_args=["--revalues", target_id])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("valuation requires --valuation-note", result.stderr)

    def test_valuation_error_in_pronouncement_requires_factor(self):
        target_id, _ = self.publish_ok(task="T-534", subject="subj-val3-target", tier=3)
        refused = self.publish(task="T-535", subject="subj-val3-actor", tier=3,
                                operation="valuation", operation_subtype="error-in-pronouncement",
                                extra_args=["--revalues", target_id,
                                            "--valuation-note", "the earlier reasoning was wrong"])
        self.assertEqual(refused.returncode, 1, refused.stderr)
        self.assertIn("requires --factor reasoning_error", refused.stderr)

        ok = self.publish(task="T-536", subject="subj-val3-actor2", tier=3,
                           operation="valuation", operation_subtype="error-in-pronouncement",
                           extra_args=["--revalues", target_id, "--factor", "reasoning_error",
                                       "--factor-note", "the earlier reasoning was wrong",
                                       "--valuation-note", "the earlier reasoning was wrong"])
        self.assertEqual(ok.returncode, 0, ok.stderr)

    def test_valuation_refuses_without_revalues_relation(self):
        result = self.publish(operation="valuation", operation_subtype="obiter",
                               extra_args=["--valuation-note", "note"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("valuation requires exactly one --revalues relation", result.stderr)


# ==========================================================================
# F. Citation-token grammar extension (V1-02, V1-18/V1-19)
# ==========================================================================

class CitationGrammarExtensionTests(V2TestCase):
    def test_doi_token_resolves_and_never_dangling_in_cite(self):
        pr_id, _ = self.publish_ok(sources=[CANONICAL_DOI])
        result = run("cite", "--record", pr_id, "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("EXTERNAL (unchecked)", result.stdout)
        self.assertNotIn("DANGLING", result.stdout)

    def test_doi_token_never_appears_in_conflicts_detector5(self):
        self.publish_ok(sources=[CANONICAL_DOI])
        result = run("conflicts", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_decision_token_resolves_on_task_half_cite(self):
        pr_id, _ = self.publish_ok(sources=["decision:{}#R-2".format(REAL_TASK_B)])
        result = run("cite", "--record", pr_id, "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK (fragment unchecked)", result.stdout)

    def test_decision_token_dangling_when_task_absent(self):
        pr_id, _ = self.publish_ok(sources=["decision:T-999999#R-1"])
        result = run("cite", "--record", pr_id, "--root", str(self.root))
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("DANGLING (fragment unchecked)", result.stdout)


# ==========================================================================
# G. Overruling anchor mechanism (V1-31/V1-32) -- decision:T-NNN#anchor
# ==========================================================================

class OverrulingAnchorTests(V2TestCase):
    def _decision_token(self, task=REAL_TASK_B, anchor="R-2"):
        return "decision:{}#{}".format(task, anchor)

    def test_decision_anchored_overrules_requires_target_tier(self):
        result = self.publish(tier=1, tier_evidence=[REAL_TASK_A],
                               extra_args=["--overrules", self._decision_token(),
                                           "--factor", "doctrinal_change", "--factor-note", "n"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("requires --target-tier", result.stderr)

    def test_decision_anchored_overrules_success_no_side_effects(self):
        """V1-32: no status flip (no record), no cited_by side effect, no
        --acknowledge-reliance needed, below_target_tier stamped against
        target_tier_declared.

        T-370 AMENDMENT (PR-019, A.3.1; AD2-34): a decision:-anchored
        overrule now also needs the adapted embedding -- the publisher's
        own quotation, the anchor token as the record id, the fixed
        unavailable-published_by marker, and the T-NNN half as the issuing
        task."""
        pr_id, _ = self.publish_ok(
            tier=1, tier_evidence=[REAL_TASK_A],
            extra_args=["--overrules", self._decision_token(), "--target-tier", "3",
                        "--factor", "doctrinal_change", "--factor-note", "the doctrine changed",
                        "--overruled-ratio", "quoted text of decision:T-344#R-2's framing",
                        "--overruled-record-id", self._decision_token(),
                        "--overruled-published-by",
                        "unavailable: decision-anchored target has no published_by",
                        "--overruled-issuing-task", REAL_TASK_B])
        rec = self.load(pr_id)
        rel = rec["relations"][0]
        self.assertEqual(rel["type"], "overrules")
        self.assertEqual(rel["target"], self._decision_token())
        self.assertEqual(rel["target_tier_declared"], 3)
        self.assertFalse(rel["below_target_tier"])  # acting tier 1 <= declared tier 3
        # AD2-32: the embedded predecessor material, decision-anchor shape.
        embedded = rel["overruled_predecessor"]
        self.assertEqual(sorted(embedded), ["issuing_task", "published_by", "ratio", "record_id"])
        self.assertEqual(embedded["record_id"], self._decision_token())
        self.assertEqual(embedded["published_by"],
                          "unavailable: decision-anchored target has no published_by")
        self.assertEqual(embedded["issuing_task"], REAL_TASK_B)
        # no PR file exists for the decision: target -- nothing else was touched.
        self.assertEqual(self.record_files(), {pr_id + ".json"})

    def test_decision_token_invalid_on_supersedes_relation_type(self):
        result = self.publish(extra_args=["--supersedes", self._decision_token(), "--target-tier", "4"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("valid only as an overrules/reinterprets", result.stderr)

    def test_decision_anchored_overrules_tier_symmetry_refusal(self):
        result = self.publish(tier=3, tier_evidence=[REAL_TASK_A],
                               extra_args=["--overrules", self._decision_token(), "--target-tier", "1",
                                           "--factor", "doctrinal_change", "--factor-note", "n"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("SDR-17.8", result.stderr)

    def test_decision_anchored_overrules_tier4_declared_refused(self):
        result = self.publish(tier=4, extra_args=["--overrules", self._decision_token(), "--target-tier", "4"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("category error", result.stderr)

    def test_decision_anchored_overrules_tier3_declared_requires_factor(self):
        result = self.publish(tier=3, extra_args=["--overrules", self._decision_token(), "--target-tier", "3"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("requires >=1 --factor", result.stderr)

    def test_decision_anchored_reinterprets_success(self):
        pr_id, _ = self.publish_ok(
            tier=1, tier_evidence=[REAL_TASK_A], operation="reinterpretation",
            operation_subtype="declarative",
            extra_args=["--reinterprets", self._decision_token(), "--target-tier", "3"])
        rec = self.load(pr_id)
        self.assertEqual(rec["relations"][0]["type"], "reinterprets")
        self.assertEqual(rec["relations"][0]["target_tier_declared"], 3)

    def test_decision_target_must_resolve_on_task_half(self):
        result = self.publish(tier=1, tier_evidence=[REAL_TASK_A],
                               extra_args=["--overrules", "decision:T-999999#R-1", "--target-tier", "3",
                                           "--factor", "doctrinal_change", "--factor-note", "n"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("does not resolve", result.stderr)


# ==========================================================================
# H. migrate verb (V1-36..V1-40) -- mechanics only
# ==========================================================================

class MigrateVerbTests(V2TestCase):
    def _backfill_file(self, mapping):
        f = pathlib.Path(self._tmp.name) / "backfill-{}.json".format(id(mapping))
        f.write_text(json.dumps(mapping), encoding="utf-8")
        return f

    def test_migrate_success_writes_exactly_four_fields(self):
        v1 = self.write_v1_record(self.root, "PR-001", authority_tier=3)
        backfill = self._backfill_file({
            "PR-001": {"sources": [REAL_TASK_A], "validity_conditions": ["a validity fact"]},
        })
        result = run("migrate", "--root", str(self.root), "--agent", "t355-worker",
                      "--backfill", str(backfill))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("migrated 1 record(s): PR-001", result.stdout)

        migrated = self.load("PR-001")
        self.assertEqual(migrated["schema_version"], 2)
        self.assertEqual(migrated["sources"], [REAL_TASK_A])
        self.assertEqual(migrated["validity_conditions"], ["a validity fact"])
        self.assertEqual(migrated["operation"], {"type": "determination", "subtype": None})
        self.assertEqual(migrated["interpretive_code_version"], "pre-code")
        # every pre-existing key/value is preserved byte-for-byte.
        for key, value in v1.items():
            if key not in ("schema_version",):
                self.assertEqual(migrated[key], value, "key {} was altered by migrate".format(key))

    def test_migrate_idempotent_second_run_byte_identical(self):
        self.write_v1_record(self.root, "PR-001", authority_tier=3)
        backfill = self._backfill_file({
            "PR-001": {"sources": [REAL_TASK_A], "validity_conditions": ["a validity fact"]},
        })
        r1 = run("migrate", "--root", str(self.root), "--backfill", str(backfill))
        self.assertEqual(r1.returncode, 0, r1.stderr)
        bytes_after_first = (self.root / "PR-001.json").read_bytes()

        r2 = run("migrate", "--root", str(self.root), "--backfill", str(backfill))
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn("no-op", r2.stdout)
        bytes_after_second = (self.root / "PR-001.json").read_bytes()
        self.assertEqual(bytes_after_first, bytes_after_second)

    def test_migrate_all_or_nothing_refuses_missing_backfill_entry(self):
        self.write_v1_record(self.root, "PR-001", authority_tier=3)
        self.write_v1_record(self.root, "PR-002", authority_tier=3)
        # backfill covers PR-001 but not PR-002 -- must refuse, writing NOTHING.
        backfill = self._backfill_file({
            "PR-001": {"sources": [REAL_TASK_A], "validity_conditions": ["a validity fact"]},
        })
        before_1 = (self.root / "PR-001.json").read_bytes()
        before_2 = (self.root / "PR-002.json").read_bytes()
        result = run("migrate", "--root", str(self.root), "--backfill", str(backfill))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("all-or-nothing", result.stderr)
        self.assertEqual((self.root / "PR-001.json").read_bytes(), before_1,
                          "all-or-nothing: PR-001 must not be migrated when PR-002's entry is missing")
        self.assertEqual((self.root / "PR-002.json").read_bytes(), before_2)

    def test_migrate_refuses_validity_conditions_missing_at_tier1_3(self):
        self.write_v1_record(self.root, "PR-001", authority_tier=2)
        backfill = self._backfill_file({"PR-001": {"sources": [REAL_TASK_A]}})
        result = run("migrate", "--root", str(self.root), "--backfill", str(backfill))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("validity_conditions", result.stderr)

    def test_migrate_skips_already_v2_records(self):
        self.write_v1_record(self.root, "PR-001", authority_tier=3)
        # PR-002 is already schema_version 2 (born there, e.g. minted by
        # publish) -- migrate must leave it untouched and needs no backfill
        # entry for it.
        self.write_v1_record(self.root, "PR-002", authority_tier=4, schema_version=2,
                              sources=["x"], validity_conditions=[],
                              operation={"type": "determination", "subtype": None},
                              interpretive_code_version="v1")
        before_2 = (self.root / "PR-002.json").read_bytes()
        backfill = self._backfill_file({
            "PR-001": {"sources": [REAL_TASK_A], "validity_conditions": ["a validity fact"]},
        })
        result = run("migrate", "--root", str(self.root), "--backfill", str(backfill))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "PR-002.json").read_bytes(), before_2)

    def test_migrate_backfill_invalid_json_refused(self):
        self.write_v1_record(self.root, "PR-001", authority_tier=4)
        bad = pathlib.Path(self._tmp.name) / "bad.json"
        bad.write_text("{not valid json", encoding="utf-8")
        result = run("migrate", "--root", str(self.root), "--backfill", str(bad))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("not valid JSON", result.stderr)

    def test_migrate_noop_on_all_v2_registry(self):
        self.publish_ok()  # a real v2 publish
        backfill = self._backfill_file({})
        result = run("migrate", "--root", str(self.root), "--backfill", str(backfill))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no-op", result.stdout)


# ==========================================================================
# I. Carried defect (i): test-event isolation (V1-06/V1-48)
# ==========================================================================

class TestEventIsolationTests(V2TestCase):
    def test_full_publish_confirm_overrule_cycle_under_override_root_does_not_touch_live_events(self):
        """Board T-353's mandated test: (a) live events.jsonl line count
        recorded, (b) a full publish/confirm/overrule cycle runs entirely
        under an overridden root, (c) the live line count is UNCHANGED."""
        before = live_events_line_count()

        target_id, r1 = self.publish_ok(task="T-540", subject="subj-iso-target", tier=3,
                                         extra_args=["--cites", NEVER_REAL_TASK])  # exercises dangling_reference
        self.assertEqual(r1.returncode, 0, r1.stderr)

        confirm_result = run("confirm", target_id, "--root", str(self.root), "--agent", "verifier-iso",
                              "--outcome", "confirmed", "--note", "scope confirmed under isolated root")
        self.assertEqual(confirm_result.returncode, 0, confirm_result.stderr)

        # T-370 AMENDMENT (PR-019, A.3.1): a successful --overrules publish
        # now also needs the displacement-bridge embedding.
        overrule_id, r2 = self.publish_ok(task="T-541", subject="subj-iso-overrule", tier=3,
                                           extra_args=["--overrules", target_id, "--factor",
                                                       "unworkability", "--factor-note", "note"]
                                           + self.overrule_embedding_args(target_id))
        self.assertEqual(r2.returncode, 0, r2.stderr)

        # also exercise a refusal (event-logged too) entirely under the override root
        refused = self.publish(task="T-542", subject="subj-iso-refused", sources=[])
        self.assertEqual(refused.returncode, 1)

        after = live_events_line_count()
        self.assertEqual(before, after,
                          "a publish/confirm/overrule cycle under an OVERRIDDEN root must never "
                          "append to the live .harness/logs/events.jsonl (V1-06/V1-48)")

    def test_events_land_in_root_sidecar_when_root_overridden(self):
        """The flip side of the isolation test: events are not simply
        dropped -- they land in `<root>/events.jsonl` instead."""
        self.publish_ok(task="T-543", subject="subj-sidecar")
        sidecar = self.root / "events.jsonl"
        self.assertTrue(sidecar.exists(), "expected a root-local events.jsonl sidecar")
        lines = [json.loads(l) for l in sidecar.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertTrue(any(rec.get("event") == "precedent_published" for rec in lines))

    def test_precedent_root_env_var_also_isolates_events(self):
        import os
        before = live_events_line_count()
        env = dict(os.environ)
        env["PRECEDENT_ROOT"] = str(self.root)
        result = run("publish", "--task", "T-544", "--title", "env isolation", "--subject",
                      "subj-env-iso", "--tier", "4", "--tier-evidence", REAL_TASK_A,
                      "--ratio", "r", "--width", "narrow", "--sources", REAL_TASK_A,
                      "--code-version", "v1", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = live_events_line_count()
        self.assertEqual(before, after)
        self.assertTrue((self.root / "events.jsonl").exists())


# ==========================================================================
# J. Carried defect (ii): supersedes tier check (V1-03/V1-49)
# ==========================================================================

class SupersedesTierCheckTests(V2TestCase):
    def test_supersedes_refuses_lower_tier_attacking_higher(self):
        target_id, _ = self.publish_ok(task="T-550", subject="subj-super-tier-target", tier=1,
                                        tier_evidence=[REAL_TASK_A])
        result = self.publish(task="T-551", subject="subj-super-tier-actor", tier=3,
                               extra_args=["--supersedes", target_id])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("carried defect ii", result.stderr)
        self.assertIn("V1-03/V1-49", result.stderr)
        target_rec = self.load(target_id)
        self.assertEqual(target_rec["status"], "active", "a refused supersedes must not flip status")

    def test_supersedes_allowed_equal_or_higher_tier(self):
        """The R-12 merge outcome must keep working at equal-or-higher
        authority (V1-03's own reasoning)."""
        target_id, _ = self.publish_ok(task="T-552", subject="subj-super-ok-target", tier=3)
        new_id, result = self.publish_ok(task="T-553", subject="subj-super-ok-actor", tier=3,
                                          extra_args=["--supersedes", target_id])
        target_rec = self.load(target_id)
        self.assertEqual(target_rec["status"], "superseded")
        self.assertEqual(target_rec["superseded_by"], new_id)

        target2_id, _ = self.publish_ok(task="T-554", subject="subj-super-ok2-target", tier=3)
        new2_id, _ = self.publish_ok(task="T-555", subject="subj-super-ok2-actor", tier=1,
                                      tier_evidence=[REAL_TASK_A],
                                      extra_args=["--supersedes", target2_id])
        target2_rec = self.load(target2_id)
        self.assertEqual(target2_rec["status"], "superseded")
        self.assertEqual(target2_rec["superseded_by"], new2_id)

    def test_conflicts_detector3_flags_tampered_supersedes_lower_tier(self):
        """Detector 3 widens to scan `supersedes` too (V1-03/V1-49): a
        hand-crafted record (standing in for tampered/legacy data, since
        `publish` refuses this at write time) must be flagged."""
        self.write_v1_record(self.root, "PR-001", authority_tier=1, subject="d3-super-a")
        self.write_v1_record(
            self.root, "PR-002", authority_tier=4, subject="d3-super-b",
            relations=[{"type": "supersedes", "target": "PR-001", "distinguishing_facts": None,
                        "factors": [], "factor_note": None, "controlling_authority": None,
                        "target_tier_declared": None, "below_target_tier": False}])
        result = run("conflicts", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 3, result.stderr)
        payload = json.loads(result.stdout)
        findings = [f for f in payload if f["detector"] == 3]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["records"], ["PR-002", "PR-001"])
        self.assertIn("supersedes", findings[0]["evidence"])

    def test_conflicts_detector3_does_not_flag_equal_tier_supersedes(self):
        self.write_v1_record(self.root, "PR-001", authority_tier=3, subject="d3-super-clean-a")
        self.write_v1_record(
            self.root, "PR-002", authority_tier=3, subject="d3-super-clean-b",
            relations=[{"type": "supersedes", "target": "PR-001", "distinguishing_facts": None,
                        "factors": [], "factor_note": None, "controlling_authority": None,
                        "target_tier_declared": None, "below_target_tier": False}])
        result = run("conflicts", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])


# ==========================================================================
# K. Dual-read: schema_version 1 tolerance (V1-36)
# ==========================================================================

class DualReadTests(V2TestCase):
    def test_v1_record_loads_via_show(self):
        self.write_v1_record(self.root, "PR-001")
        result = run("show", "PR-001", "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"schema_version": 1', result.stdout)
        self.assertIn("scope: UNCONFIRMED (does not bind)", result.stdout)

    def test_v1_record_included_in_list(self):
        self.write_v1_record(self.root, "PR-001")
        result = run("list", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual([entry["id"] for entry in payload], ["PR-001"])

    def test_v1_record_cite_tolerates_missing_sources_field(self):
        self.write_v1_record(self.root, "PR-001")
        result = run("cite", "--record", "PR-001", "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_v1_record_as_relation_target_for_new_v2_publish(self):
        """A schema_version-1 record must remain a valid --follows target
        for a brand-new v2 publish (V1-36's own load-and-tolerate-on-every-
        mutating-path requirement, exercised at the write side)."""
        self.write_v1_record(self.root, "PR-001", authority_tier=2)
        pr_id, result = self.publish_ok(task="T-560", subject="subj-follows-v1", tier=4,
                                         extra_args=["--follows", "PR-001"])
        self.assertEqual(result.returncode, 0, result.stderr)
        v1_after = self.load("PR-001")
        self.assertIn(pr_id, v1_after["cited_by"])

    def test_v1_record_conflicts_scan_tolerates_missing_v2_fields(self):
        self.write_v1_record(self.root, "PR-001", authority_tier=3)
        # same subject, divergent ratio, no acknowledging relation -- a
        # genuine detector-1 finding, run against records with NO v2
        # fields at all (proving conflicts never chokes on their absence).
        self.write_v1_record(self.root, "PR-002", authority_tier=3,
                              ratio="a different v1-shaped ratio")
        result = run("conflicts", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 3, result.stderr)  # subject collision, expected
        payload = json.loads(result.stdout)
        self.assertTrue(any(f["detector"] == 1 for f in payload))

    def test_v2_publish_dangling_source_and_v1_record_coexist_cleanly(self):
        self.write_v1_record(self.root, "PR-001", authority_tier=4, subject="v1-clean",
                              scope_conditions=[])
        pr_id, result = self.publish_ok(task="T-561", subject="subj-coexist", tier=4)
        self.assertEqual(result.returncode, 0, result.stderr)
        result2 = run("conflicts", "--root", str(self.root), "--json")
        self.assertEqual(result2.returncode, 0, result2.stderr)


if __name__ == "__main__":
    unittest.main()
