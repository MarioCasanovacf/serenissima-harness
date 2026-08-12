"""Unit tests for the `conflicts` subcommand of .harness/bin/precedent.py (T-342).

OWNS the `conflicts` subcommand's test coverage. Writing a NEW test file (rather
than extending test_precedent.py) is deliberate per T-342 AC-1: it never races
T-340's test file for a write lock, and the acceptance glob `test_precedent*.py`
discovers both. (One assertion in test_precedent.py that specifically checked
'conflicts is not yet registered' was updated in place as an unavoidable, fully
disclosed consequence of this task landing -- see that file's SmokeTests class
docstring -- but no other file is touched here.)

Every test invokes the real CLI via subprocess (matching test_precedent.py's own
convention) so the exit-code contract and report format are exercised exactly as
a caller/verifier would see them. Every test uses an isolated `--root` (a fresh
TemporaryDirectory per test); the dedicated RootIsolationTests class additionally
asserts, with an explicit before/after snapshot, that NOTHING lands under the
live `.harness/precedents/` registry during this entire test run (T-342 AC-5).

Five detectors under test (T-342 AC-2), each with both a triggering fixture and
a clean/near-miss control fixture proving it does NOT fire on the adjacent
legitimate case (a detector with no false-positive test is untested, per AC-5):
  1. same-subject ratio contradiction between two ACTIVE records
  2. an ACTIVE record citing an OVERRULED record as binding support
  3. overrules/voids/supersedes by a lower-authority tier against a higher-
     tier target (supersedes added by T-353, carried defect ii)
  4. same-tier scope-condition overlap between two ACTIVE records, divergent ratio
  5. dangling citations (includes the P-023-shaped fixture named in AC-5)

---- T-353 amendment (schema v2 core) --------------------------------------

`docs/precedent-research/synthesis-v1-requirements.md` makes `--sources` and
`--code-version` mandatory on every publish (V1-11/V1-15), and `--validity`
mandatory non-empty at tiers 1-3 (V1-10 #28). This file's own `publish()`
helper (below) is amended to inject `--sources <task>` and
`--code-version v1` unconditionally, and `--validity <placeholder>` at
tiers 1-3, mirroring test_precedent.py's identical, identically-disclosed
amendment -- infrastructure only, no assertion in this file changes meaning.
`write_raw_record()` is UNCHANGED: it bypasses the CLI entirely to build
schema_version-1-shaped fixtures for detector 3's tamper-stand-in tests, and
the v2 CLI's dual-read tolerance (V1-36) is exactly what keeps those
fixtures valid input for `conflicts` without any v2 field.
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


def run(*args, env=None):
    cmd = [sys.executable, str(PRECEDENT_PY)] + list(args)
    return subprocess.run(cmd, text=True, capture_output=True, env=env)


class ConflictsTestCase(unittest.TestCase):
    """Base class: isolated registry root per test (never the live registry)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name) / "registry"

    def tearDown(self):
        self._tmp.cleanup()

    # -- shared helpers -----------------------------------------------

    def publish(self, task, subject, tier=4, ratio="some ratio text", width="narrow",
                tier_evidence=None, scope=None, revisit_trigger=None, title="Title",
                extra_args=None):
        # DEVIATION (bugfix, resuming worker-build-3): the obvious default
        # `[task]` (mirroring test_precedent.py's own helper) silently makes
        # every non-overridden tier_evidence token equal to this file's own
        # synthetic --task value (T-600..T-999999 range, chosen precisely so
        # these fixtures never collide with a real board task under
        # .harness/tasks/). detector 5 registry-wide-scans tier_evidence
        # (module docstring: reuses iter_all_citation_resolutions, which
        # includes tier_evidence -- see _record_citation_tokens), so that
        # default made EVERY fixture in this file dangling by construction,
        # polluting every "clean control" test's zero-findings assertion
        # (caught as 10 of 86 suite failures). T-330 is a real, permanent
        # task (docs/precedent-research/01-stare-decisis-mechanics.md) --
        # already used explicitly elsewhere in this file (test_flags_dangling_
        # relation_controlling_authority's sibling clean test, FullyCleanRegistryTests)
        # as the resolvable anchor -- so defaulting to it here keeps every
        # non-overridden fixture registry-integrity-clean unless a test
        # deliberately overrides tier_evidence or adds a dangling --cites.
        te = tier_evidence if tier_evidence is not None else ["T-330"]
        # T-353 (V1-11/V1-15/V1-10 #28): --sources/--code-version mandatory
        # on every publish; --validity mandatory non-empty at tiers 1-3 --
        # see this file's module docstring, the T-353 amendment note.
        # DEFAULT SOURCES TO "T-330", not `task`: this file's synthetic
        # --task values (T-600..T-999999) are deliberately chosen to never
        # resolve as real board tasks (see the tier_evidence default's own
        # comment above); V1-45 makes `conflicts` detector 5 walk `sources`
        # registry-wide, so a non-resolving default would turn EVERY clean-
        # control fixture in this file into a dangling-citation finding.
        args = ["publish", "--root", str(self.root), "--task", task, "--title", title,
                "--subject", subject, "--tier", str(tier), "--ratio", ratio, "--width", width,
                "--sources", "T-330", "--code-version", "v1"]
        for t in te:
            args += ["--tier-evidence", t]
        if tier in (1, 2, 3):
            sc = scope if scope is not None else ["role:worker"]
            rt = revisit_trigger if revisit_trigger is not None else "revisit if X"
            for s in sc:
                args += ["--scope", s]
            args += ["--revisit-trigger", rt]
            args += ["--validity", "validity condition placeholder"]
        elif scope is not None:
            for s in scope:
                args += ["--scope", s]
        if extra_args:
            args += extra_args
        return run(*args)

    def publish_ok(self, **kwargs):
        result = self.publish(**kwargs)
        self.assertEqual(result.returncode, 0, "stdout={!r} stderr={!r}".format(result.stdout, result.stderr))
        pr_id = result.stdout.strip().splitlines()[-1].split()[-1]
        return pr_id, result

    def conflicts_json(self, root=None):
        root = root if root is not None else self.root
        result = run("conflicts", "--root", str(root), "--json")
        payload = json.loads(result.stdout) if result.stdout.strip() else []
        return result, payload

    def findings_for(self, payload, detector):
        return [f for f in payload if f["detector"] == detector]

    def write_raw_record(self, root, pr_id, **fields):
        """Hand-crafted registry record, bypassing `publish` entirely. Needed
        for detector 3: `publish` refuses a lower-tier-attacks-higher-tier
        overrule at write time (SDR-17.8), so the only way to exercise the
        registry-wide sweep that catches this after the fact is to write a
        record that could never have been minted through the CLI (a stand-in
        for tampered/legacy/hand-edited data)."""
        root = pathlib.Path(root)
        root.mkdir(parents=True, exist_ok=True)
        # DEVIATION (bugfix, resuming worker-build-3): same fix as publish()'s
        # default above -- "T-1" does not resolve (no .harness/tasks/T-1.json;
        # real tasks are zero-padded, T-001.json), so every hand-crafted
        # record silently carried a dangling tier_evidence token, which broke
        # this class's own "no flag" clean-control tests (detector 3 correctly
        # reported nothing, but the overall sweep still returned exit 3 via
        # detector 5). T-330 matches the resolvable anchor used throughout
        # this file.
        rec = {
            "id": pr_id, "schema_version": 1, "title": "t", "subject": "subj",
            "status": "active", "authority_tier": 4, "tier_evidence": ["T-330"],
            "ratio": "r", "dicta": [], "scope_conditions": [], "declared_width": "narrow",
            "revisit_trigger": None, "confirmation_status": "unconfirmed",
            "confirmed_by": None, "confirmed_at": None, "narrowed_scope": None,
            "confirmation_note": None, "relations": [], "cites": [], "cited_by": [],
            "overruled_by": None, "superseded_by": None, "voided_by": None,
            "issuing_task": "T-1", "published_by": "test", "published_at": "2026-01-01T00:00:00Z",
        }
        rec.update(fields)
        (root / (pr_id + ".json")).write_text(json.dumps(rec, indent=2), encoding="utf-8")
        return rec


# ==========================================================================
# CLI smoke / exit-code contract
# ==========================================================================

class SmokeTests(ConflictsTestCase):
    def test_conflicts_registered_help(self):
        result = run("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("conflicts", result.stdout)

    def test_empty_registry_exits_zero_zero_findings(self):
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload, [])

    def test_nonexistent_root_exits_zero(self):
        """A root that was never created (no publish call at all) behaves
        identically to an empty one -- scan_registry tolerates a missing
        directory."""
        result = run("conflicts", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_usage_error_distinct_code(self):
        """Unknown flag -> argparse native usage error (exit 2), distinct from
        the findings code (3) and the clean code (0), per T-342 AC-3."""
        result = run("conflicts", "--root", str(self.root), "--not-a-real-flag")
        self.assertEqual(result.returncode, 2)

    def test_corrupt_record_returns_4(self):
        self.publish_ok(task="T-500", subject="subj-corrupt-a")
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "PR-777.json").write_text("not json at all", encoding="utf-8")
        result = run("conflicts", "--root", str(self.root))
        self.assertEqual(result.returncode, 4)
        self.assertIn("REGISTRY INTEGRITY ERROR", result.stderr)

    def test_text_report_names_detector_records_and_evidence(self):
        """AC-4 (REPORT FORMAT): every finding names the detector, the
        records by PR-NNN, and the evidence -- checked against the
        human-readable (non-json) output, not just the machine one."""
        self.publish_ok(task="T-501", subject="dangle-report", tier=4,
                         extra_args=["--cites", "T-999999"])
        result = run("conflicts", "--root", str(self.root))
        self.assertEqual(result.returncode, 3)
        self.assertIn("detector=5", result.stdout)
        self.assertIn("dangling-citation", result.stdout)
        self.assertIn("PR-001", result.stdout)
        self.assertIn("T-999999", result.stdout)


# ==========================================================================
# Fully clean control fixture -- zero findings across ALL detectors
# ==========================================================================

class FullyCleanRegistryTests(ConflictsTestCase):
    def test_realistic_clean_registry_has_zero_findings(self):
        """A registry built entirely through legitimate `publish` calls --
        distinct subjects, distinct/disjoint scope, an acknowledged
        follow, a properly-acked overrule, resolvable citations -- must
        report exactly zero findings. This is the AC-5 "CLEAN control
        fixture... assert zero findings" requirement at the whole-registry
        level (per-detector near-miss controls live in each detector's own
        test class below)."""
        base_id, _ = self.publish_ok(task="T-600", subject="clean-base", tier=3,
                                      ratio="base ratio", scope=["role:worker"])
        # an acknowledged follow: different subject, would-be divergent ratio,
        # but explicitly linked -- must not trip detector 1.
        self.publish_ok(task="T-601", subject="clean-followup", tier=3,
                         ratio="a differently-worded ratio", scope=["role:verifier"],
                         extra_args=["--follows", base_id])
        # a properly-acked overrule of an unrelated tier-3 record. DEVIATION
        # (bugfix, resuming worker-build-3): both calls originally omitted
        # `scope`, so both defaulted to ["role:worker"] (publish()'s own
        # tier-1/2/3 default) -- identical to clean-base's scope. The
        # successor (still ACTIVE, unlike the record it overrules) then
        # collided with clean-base under detector 4 (same tier, overlapping
        # scope, divergent ratio, no relations[]/cites[] link to clean-base
        # specifically) -- a real, correctly-detected finding this "clean"
        # fixture never intended to create. Scoped to a track that does not
        # overlap role:worker.
        overruled_id, _ = self.publish_ok(task="T-602", subject="clean-to-overrule", tier=3,
                                           ratio="soon overruled", scope=["role:overrule-track"])
        self.publish_ok(task="T-603", subject="clean-overrule-successor", tier=3,
                         ratio="successor ratio", scope=["role:overrule-track"],
                         extra_args=["--overrules", overruled_id, "--factor", "unworkability",
                                     "--factor-note", "no longer workable"])
        # a resolvable citation to a real, permanent task in this repo.
        self.publish_ok(task="T-604", subject="clean-cites-real-task", tier=4,
                         extra_args=["--cites", "T-330"])

        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 0, "unexpected findings: {}".format(payload))
        self.assertEqual(payload, [])


# ==========================================================================
# Detector 1 -- same-subject ratio contradiction
# ==========================================================================

class Detector1SubjectRatioTests(ConflictsTestCase):
    def test_flags_undisclosed_divergent_ratio_same_subject(self):
        a_id, _ = self.publish_ok(task="T-610", subject="d1-subject", tier=3,
                                   ratio="rule binds when X holds")
        b_id, _ = self.publish_ok(task="T-611", subject="d1-subject", tier=1,
                                   ratio="rule binds when X does NOT hold")
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 3, result.stderr)
        findings = self.findings_for(payload, 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(set(findings[0]["records"]), {a_id, b_id})
        self.assertIn("d1-subject", findings[0]["evidence"])

    def test_clean_control_no_flag_when_relation_acknowledges_divergence(self):
        """Near-miss: same subject, different ratio, but B explicitly
        --follows A -- the divergence is disclosed, not silent, so
        detector 1 must NOT fire (module docstring DECISION)."""
        a_id, _ = self.publish_ok(task="T-612", subject="d1-acked", tier=3,
                                   ratio="ratio A")
        self.publish_ok(task="T-613", subject="d1-acked", tier=3,
                         ratio="ratio B, refined", extra_args=["--follows", a_id])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(self.findings_for(payload, 1), [])

    def test_clean_control_no_flag_when_ratio_identical(self):
        self.publish_ok(task="T-614", subject="d1-identical", tier=4, ratio="same ratio text")
        self.publish_ok(task="T-615", subject="d1-identical", tier=2,
                         ratio="same ratio text", tier_evidence=["P-024"])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(self.findings_for(payload, 1), [])

    def test_clean_control_no_flag_when_one_side_overruled(self):
        """A pair that WAS in genuine conflict, but one side is no longer
        ACTIVE (already reconciled via overrule), must not be reported --
        detectors 1/4 only consider live, currently-active law."""
        a_id, _ = self.publish_ok(task="T-616", subject="d1-reconciled", tier=3,
                                   ratio="ratio A")
        self.publish_ok(task="T-617", subject="d1-reconciled", tier=3,
                         ratio="ratio B superseding A",
                         extra_args=["--overrules", a_id, "--factor", "doctrinal_change",
                                     "--factor-note", "changed"])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(self.findings_for(payload, 1), [])


# ==========================================================================
# Detector 2 -- active record citing an overruled record as binding support
# ==========================================================================

class Detector2OverruledCitedTests(ConflictsTestCase):
    def _make_overruled(self):
        g_id, _ = self.publish_ok(task="T-620", subject="d2-subject", tier=3, ratio="G ratio")
        h_id, _ = self.publish_ok(task="T-621", subject="d2-subject-h", tier=3, ratio="H ratio",
                                   extra_args=["--overrules", g_id, "--factor", "reasoning_error",
                                               "--factor-note", "G's reasoning no longer holds"])
        return g_id, h_id

    def test_flags_follows_of_overruled_record(self):
        g_id, h_id = self._make_overruled()
        i_id, _ = self.publish_ok(task="T-622", subject="d2-follower", tier=4,
                                   extra_args=["--follows", g_id])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 3, result.stderr)
        findings = self.findings_for(payload, 2)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["records"], [i_id, g_id])
        self.assertIn(h_id, findings[0]["evidence"])

    def test_flags_cites_of_overruled_record(self):
        g_id, _h_id = self._make_overruled()
        j_id, _ = self.publish_ok(task="T-623", subject="d2-citer", tier=4,
                                   extra_args=["--cites", g_id])
        result, payload = self.conflicts_json()
        findings = self.findings_for(payload, 2)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["records"], [j_id, g_id])

    def test_clean_control_no_flag_when_target_still_active(self):
        base_id, _ = self.publish_ok(task="T-624", subject="d2-still-active", tier=3,
                                      ratio="still good law")
        self.publish_ok(task="T-625", subject="d2-follower-clean", tier=4,
                         extra_args=["--follows", base_id])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(self.findings_for(payload, 2), [])

    def test_clean_control_no_flag_for_distinguishes_of_overruled_record(self):
        """Distinguishing dead law is not reliance on it -- detector 2 must
        not fire for a `distinguishes` relation (module docstring DECISION),
        only for `follows`/`cites`."""
        g_id, _h_id = self._make_overruled()
        self.publish_ok(task="T-626", subject="d2-distinguisher", tier=4,
                         extra_args=["--distinguishes", g_id, "--distinguishing-facts",
                                     "the facts here differ from G's"])
        result, payload = self.conflicts_json()
        self.assertEqual(self.findings_for(payload, 2), [])


# ==========================================================================
# Detector 3 -- illegitimate overruling by a lower-authority tier
# ==========================================================================

class Detector3IllegitimateOverruleTests(ConflictsTestCase):
    def test_flags_lower_tier_overruling_higher_tier(self):
        # PR-001: tier 1 (operator, highest authority), active.
        self.write_raw_record(self.root, "PR-001", authority_tier=1, subject="d3-a")
        # PR-002: tier 3 (verdicted), records an illegitimate overrules
        # relation against the tier-1 record -- publish() would refuse this
        # at write time (SDR-17.8), so it stands in for tampered/legacy data.
        self.write_raw_record(
            self.root, "PR-002", authority_tier=3, subject="d3-b",
            relations=[{"type": "overrules", "target": "PR-001", "distinguishing_facts": None,
                        "factors": ["reasoning_error"], "factor_note": "n",
                        "controlling_authority": None, "below_target_tier": False}])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 3, result.stderr)
        findings = self.findings_for(payload, 3)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["records"], ["PR-002", "PR-001"])
        self.assertIn("tier 3", findings[0]["evidence"])
        self.assertIn("tier 1", findings[0]["evidence"])

    def test_flags_lower_tier_voiding_higher_tier(self):
        self.write_raw_record(self.root, "PR-001", authority_tier=2, subject="d3-void-a")
        self.write_raw_record(
            self.root, "PR-002", authority_tier=4, subject="d3-void-b",
            relations=[{"type": "voids", "target": "PR-001", "distinguishing_facts": None,
                        "factors": [], "factor_note": None,
                        "controlling_authority": "T-330", "below_target_tier": False}])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 3)
        findings = self.findings_for(payload, 3)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["records"], ["PR-002", "PR-001"])

    def test_clean_control_no_flag_for_equal_tier_overrule(self):
        """SDR-07: equal-tier overruling is explicitly legitimate (equal
        adversarial weight suffices) -- must not be flagged."""
        self.write_raw_record(self.root, "PR-001", authority_tier=3, subject="d3-equal-a")
        self.write_raw_record(
            self.root, "PR-002", authority_tier=3, subject="d3-equal-b",
            relations=[{"type": "overrules", "target": "PR-001", "distinguishing_facts": None,
                        "factors": ["reasoning_error"], "factor_note": "n",
                        "controlling_authority": None, "below_target_tier": False}])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(self.findings_for(payload, 3), [])

    def test_clean_control_no_flag_for_higher_tier_overruling_lower(self):
        """Legitimate direction: a tier-1 record overruling a tier-3 record
        (higher authority attacking lower) must not be flagged."""
        self.write_raw_record(self.root, "PR-001", authority_tier=3, subject="d3-hi-a")
        self.write_raw_record(
            self.root, "PR-002", authority_tier=1, subject="d3-hi-b",
            relations=[{"type": "overrules", "target": "PR-001", "distinguishing_facts": None,
                        "factors": [], "factor_note": None,
                        "controlling_authority": None, "below_target_tier": False}])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(self.findings_for(payload, 3), [])

    def test_real_registry_never_produces_detector3_findings(self):
        """Belt-and-suspenders: every overrule/void produced through the
        real `publish` CLI (which enforces SDR-17.8 at write time) must
        never trigger detector 3."""
        target_id, _ = self.publish_ok(task="T-630", subject="d3-real-target", tier=3)
        self.publish_ok(task="T-631", subject="d3-real-successor", tier=3,
                         extra_args=["--overrules", target_id, "--factor", "unworkability",
                                     "--factor-note", "note"])
        result, payload = self.conflicts_json()
        self.assertEqual(self.findings_for(payload, 3), [])


# ==========================================================================
# Detector 4 -- same-tier scope-condition overlap, divergent ratio
# ==========================================================================

class Detector4ScopeOverlapTests(ConflictsTestCase):
    def test_flags_overlapping_scope_same_tier_divergent_ratio(self):
        a_id, _ = self.publish_ok(task="T-640", subject="d4-a", tier=2, ratio="ratio A",
                                   tier_evidence=["P-024"],
                                   scope=["role:worker", "path:one.py:1"])
        b_id, _ = self.publish_ok(task="T-641", subject="d4-b", tier=2, ratio="ratio B",
                                   tier_evidence=["P-025"],
                                   scope=["role:worker", "path:two.py:1"])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 3, result.stderr)
        findings = self.findings_for(payload, 4)
        self.assertEqual(len(findings), 1)
        self.assertEqual(set(findings[0]["records"]), {a_id, b_id})
        self.assertIn("role:worker", findings[0]["evidence"])

    def test_clean_control_no_flag_disjoint_scope(self):
        self.publish_ok(task="T-642", subject="d4-disjoint-a", tier=2, ratio="ratio A",
                         tier_evidence=["P-024"], scope=["role:worker"])
        self.publish_ok(task="T-643", subject="d4-disjoint-b", tier=2, ratio="ratio B",
                         tier_evidence=["P-025"], scope=["role:verifier"])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(self.findings_for(payload, 4), [])

    def test_clean_control_no_flag_different_tier(self):
        # DEVIATION (bugfix, resuming worker-build-3): the explicit override
        # here was itself dangling (T-644 does not resolve); swapped for the
        # resolvable T-330 anchor used throughout this file.
        self.publish_ok(task="T-644", subject="d4-tier-a", tier=1, tier_evidence=["T-330"],
                         ratio="ratio A", scope=["role:worker"])
        self.publish_ok(task="T-645", subject="d4-tier-b", tier=3, ratio="ratio B",
                         scope=["role:worker"])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(self.findings_for(payload, 4), [])

    def test_clean_control_no_flag_same_ratio(self):
        self.publish_ok(task="T-646", subject="d4-agree-a", tier=2, ratio="agreed ratio",
                         tier_evidence=["P-024"], scope=["role:worker"])
        self.publish_ok(task="T-647", subject="d4-agree-b", tier=2, ratio="agreed ratio",
                         tier_evidence=["P-025"], scope=["role:worker"])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(self.findings_for(payload, 4), [])

    def test_clean_control_no_flag_when_disclosed_via_follows(self):
        a_id, _ = self.publish_ok(task="T-648", subject="d4-disclosed-a", tier=2, ratio="ratio A",
                                   tier_evidence=["P-024"], scope=["role:worker"])
        self.publish_ok(task="T-649", subject="d4-disclosed-b", tier=2, ratio="ratio B",
                         tier_evidence=["P-025"], scope=["role:worker"],
                         extra_args=["--follows", a_id])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(self.findings_for(payload, 4), [])


# ==========================================================================
# Detector 5 -- dangling citations, including the P-023-shaped fixture
# ==========================================================================

class Detector5DanglingCitationTests(ConflictsTestCase):
    def test_flags_dangling_t_number_cites(self):
        pr_id, _ = self.publish_ok(task="T-650", subject="d5-t-dangle", tier=4,
                                    extra_args=["--cites", "T-999999"])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 3, result.stderr)
        findings = self.findings_for(payload, 5)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["records"], [pr_id])
        self.assertIn("T-999999", findings[0]["evidence"])

    def test_p023_shaped_fixture_dangling_tier_evidence(self):
        """AC-5: reproduce the P-023-shaped case -- a record whose cited
        authority does not resolve. P-023 (the `reopen` verb) is applied in
        both code (`blackboard.py:470`) and prose (`ORCHESTRATION.md:58`)
        but has NO entry in `evolution.accepted_mutations` or
        `pending_proposals` in the live state.json (verified: this is a
        standing, deliberately-unfixed gap -- SDR out-of-scope item 4,
        `.harness/context-brief-precedent-layer.md` sec 2.4, `state.json:791`
        gen-5 backlog note -- so this fixture's non-resolution is not a
        flaky assumption about transient state, it is the documented
        permanent shape of the gap this detector exists to catch). A tier-2
        record citing "P-023" as tier_evidence therefore never resolves."""
        pr_id, _ = self.publish_ok(task="T-651", subject="d5-p023-shaped", tier=2,
                                    tier_evidence=["P-023"], scope=["role:worker"],
                                    revisit_trigger="revisit if P-023 is ever ledgered")
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 3, result.stderr)
        findings = self.findings_for(payload, 5)
        matching = [f for f in findings if f["records"] == [pr_id]]
        self.assertEqual(len(matching), 1,
                          "expected exactly one dangling-citation finding for {} citing "
                          "P-023, got {}".format(pr_id, findings))
        self.assertIn("P-023", matching[0]["evidence"])

    def test_flags_dangling_relation_controlling_authority(self):
        target_id, _ = self.publish_ok(task="T-652", subject="d5-void-target", tier=3)
        # publish() itself refuses an unresolvable --controlling-authority
        # (SDR-17.13), so this dangling shape is only reachable via a
        # hand-written record -- same rationale as detector 3's fixtures.
        self.write_raw_record(
            self.root, "PR-777", authority_tier=3, subject="d5-void-actor", status="active",
            relations=[{"type": "voids", "target": target_id, "distinguishing_facts": None,
                        "factors": [], "factor_note": None,
                        "controlling_authority": "T-999999", "below_target_tier": False}])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 3)
        findings = self.findings_for(payload, 5)
        self.assertTrue(any(f["records"] == ["PR-777"] and "T-999999" in f["evidence"]
                             for f in findings))

    def test_clean_control_no_flag_for_resolvable_citations(self):
        self.publish_ok(task="T-653", subject="d5-clean", tier=4,
                         extra_args=["--cites", "T-330"])
        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(self.findings_for(payload, 5), [])


# ==========================================================================
# MANDATORY (AC-5): registry-root isolation from the live registry
# ==========================================================================

class RootIsolationTests(ConflictsTestCase):
    def _live_pr_files(self):
        if not LIVE_REGISTRY.exists():
            return set()
        return set(p.name for p in LIVE_REGISTRY.glob("PR-*.json"))

    def test_conflicts_writes_nothing_under_root_it_scans(self):
        """`conflicts` is read-only (mirrors `cite`'s contract, module
        docstring DECISION): running it must not create, modify, or delete
        any file under the very root it just scanned."""
        self.publish_ok(task="T-660", subject="d-isolation-a", tier=3)
        self.publish_ok(task="T-661", subject="d-isolation-b", tier=3,
                         extra_args=["--cites", "T-999999"])
        before = sorted(p.name for p in self.root.glob("*"))
        result = run("conflicts", "--root", str(self.root))
        self.assertEqual(result.returncode, 3, result.stderr)
        after = sorted(p.name for p in self.root.glob("*"))
        self.assertEqual(before, after, "conflicts mutated its own scanned root")

    def test_whole_run_never_touches_live_precedents_registry(self):
        """AC-5: assert .harness/precedents/ is NOT written during this
        test run. Publishes several records (including ones deliberately
        engineered to trigger every detector) and runs `conflicts` many
        times, always against an isolated --root, then diffs the live
        registry's PR-*.json file set before vs after."""
        before = self._live_pr_files()

        g_id, _ = self.publish_ok(task="T-670", subject="iso-d2", tier=3, ratio="G")
        self.publish_ok(task="T-671", subject="iso-d2b", tier=3, ratio="H",
                         extra_args=["--overrules", g_id, "--factor", "reasoning_error",
                                     "--factor-note", "n"])
        self.publish_ok(task="T-672", subject="iso-d1", tier=3, ratio="A")
        self.publish_ok(task="T-673", subject="iso-d1", tier=1, tier_evidence=["T-673"],
                         ratio="B contradicts A")
        self.publish_ok(task="T-674", subject="iso-d5", tier=4, extra_args=["--cites", "T-999999"])
        self.write_raw_record(self.root, "PR-900", authority_tier=3, subject="iso-d3-a")
        self.write_raw_record(
            self.root, "PR-901", authority_tier=4, subject="iso-d3-b",
            relations=[{"type": "overrules", "target": "PR-900", "distinguishing_facts": None,
                        "factors": ["reasoning_error"], "factor_note": "n",
                        "controlling_authority": None, "below_target_tier": False}])

        result, payload = self.conflicts_json()
        self.assertEqual(result.returncode, 3)
        self.assertTrue(len(payload) >= 4, "expected multiple detectors to fire: {}".format(payload))

        after = self._live_pr_files()
        self.assertEqual(before, after,
                          "conflicts (or its fixtures) wrote into the live .harness/precedents/ registry")


if __name__ == "__main__":
    unittest.main()
