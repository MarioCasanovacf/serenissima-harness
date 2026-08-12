"""Unit tests for .harness/bin/precedent.py (T-340).

Every test invokes the real CLI via subprocess (matching test_data_loss_guard.py's
convention) so the exit-code contract (SDR-15) and stdout contract (SDR-20/21/22)
are exercised exactly as a caller would see them, not just their Python internals.

Every test that publishes/confirms passes an isolated `--root` (a fresh
TemporaryDirectory per test) or, for the dedicated isolation test, the
PRECEDENT_ROOT env var -- NOTHING here ever writes into the live
`.harness/precedents/` registry (AC-5 / SDR-13 / SDR-30 check 6).

RESERVES the name `conflicts` for T-342 (SDR-27): this file does not test it
and does not create test_precedent_conflicts.py.

---- T-353 amendments (schema v2 core) -------------------------------------

`docs/precedent-research/synthesis-v1-requirements.md` (V1-11/V1-15/V1-10
#28) makes `--sources` and `--code-version` mandatory on EVERY publish, and
`--validity`/`--validity-file` mandatory non-empty at tiers 1-3. Every test
in this file that publishes was written against the v1 CLI, which had no
such requirement, so every one of them would now refuse at exit 1 unless
patched -- this is "your own schema change invalidates the assertion" per
board T-353's OWNS-EXACTLY clause, not new test behavior. Amendments, each
disclosed:

  1. `PrecedentCLITestCase.publish()` (the shared helper used by nearly
     every test below) now injects `--sources <task>` (any non-empty
     citation token satisfies V1-11; it need not resolve -- a dangling
     source is a WARNING, never a refusal, V1-11) and `--code-version v1`
     unconditionally, and `--validity <placeholder>` whenever tier is in
     (1, 2, 3), unless the caller passes `sources=`/`validity=` explicitly.
     This is pure test-infrastructure -- it does not change what any test
     asserts.
  2. Six tests build their CLI argv directly via raw `run(...)`/inline
     subprocess lists rather than through the helper (`test_ratio_file_
     and_stdin_forms`, `test_scope_file_newline_delimited`,
     `ConcurrentPublishTests.test_two_concurrent_publishes_get_distinct_
     monotonic_ids`, `test_precedent_root_env_var_isolates_from_live_
     registry`, `test_root_flag_wins_over_env_var`) -- each of those raw
     calls now also passes `--sources`/`--code-version` (and `--validity`
     where tier is 1-3) so the success path they assert is unaffected.
     `test_refuses_out_of_range_tier`/`test_refuses_missing_tier_evidence`/
     `test_refuses_bad_width` are UNCHANGED: each refuses at a check that
     runs strictly before T-353's new v2 checks (tier range, tier_evidence
     presence, width), so the missing --sources/--code-version never
     matters for them.
  3. `test_minimal_tier4_publish_defaults` asserted
     `rec["schema_version"] == 1`; T-353/V1-10 #2 makes every NEW publish
     write `schema_version 2` (the live seed records stay at 1 until
     T-355 runs `migrate` -- board T-353 AC-3's ordering invariant). Updated
     to `== 2`, with a comment citing V1-10 #2. Comprehensive v2 field
     assertions (sources/validity_conditions/operation/
     interpretive_code_version defaults, refusals, typed operations, the
     carried defects) live in the new `test_precedent_v2.py` rather than
     here, per T-353's OWNS-EXACTLY scope ("solely to update assertions
     your own schema change invalidates").
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PRECEDENT_PY = ROOT / ".harness" / "bin" / "precedent.py"
LIVE_REGISTRY = ROOT / ".harness" / "precedents"


def run(*args, input_text=None, env=None):
    cmd = [sys.executable, str(PRECEDENT_PY)] + list(args)
    return subprocess.run(cmd, input=input_text, text=True, capture_output=True, env=env)


class PrecedentCLITestCase(unittest.TestCase):
    """Base class: gives every test its own isolated registry root."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name) / "registry"

    def tearDown(self):
        self._tmp.cleanup()

    # -- shared helpers -----------------------------------------------

    def publish(self, task="T-100", title="Title", subject="subject-a", tier=4,
                tier_evidence=None, ratio="some ratio text", width="narrow",
                scope=None, revisit_trigger=None, sources=None, validity=None,
                code_version="v1", extra_args=None, root=None):
        # T-353 (V1-11/V1-15/V1-10 #28): --sources and --code-version are
        # mandatory on every publish now; --validity is mandatory non-empty
        # at tiers 1-3. Defaulted here so the ~90 pre-existing calls below
        # (written against the v1 CLI) keep exercising their OWN targeted
        # refusal/success path instead of tripping a new v2 check first --
        # see this file's module docstring, amendment 1.
        root = root if root is not None else self.root
        te = tier_evidence if tier_evidence is not None else [task]
        src = sources if sources is not None else [task]
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
        elif scope is not None:
            for s in scope:
                args += ["--scope", s]
            if revisit_trigger is not None:
                args += ["--revisit-trigger", revisit_trigger]
            if validity is not None:
                for v in validity:
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


# ==========================================================================
# CLI smoke
# ==========================================================================

class SmokeTests(PrecedentCLITestCase):
    def test_help_exits_zero(self):
        result = run("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("publish", result.stdout)

    def test_conflicts_subcommand_is_registered_and_clean_on_empty_registry(self):
        """SDR-27 reserved 'conflicts' for T-342; T-342 has now implemented it
        (.harness/tests/test_precedent_conflicts.py is its dedicated test
        file, per T-342 AC-1's own instruction to write a NEW test file
        rather than edit this one). This test's invariant is updated
        in place -- disclosed here, not silently reworded -- because the
        original assertion ("must fail as an unknown subcommand") became
        false the moment T-342 landed, and leaving a stale, always-failing
        assertion in the shared discover-glob would break the acceptance
        command for every future task that touches this file. Uses an
        isolated --root (never the live registry, SDR-13/AC-5) and asserts
        a clean sweep exits 0 with zero findings."""
        with tempfile.TemporaryDirectory() as tmp:
            result = run("conflicts", "--root", str(pathlib.Path(tmp) / "registry"))
        self.assertEqual(result.returncode, 0, "stdout={!r} stderr={!r}".format(result.stdout, result.stderr))
        self.assertIn("0 findings", result.stdout)


# ==========================================================================
# publish -- success path + field defaults
# ==========================================================================

class PublishSuccessTests(PrecedentCLITestCase):
    def test_minimal_tier4_publish_defaults(self):
        pr_id, result = self.publish_ok(tier=4)
        self.assertEqual(pr_id, "PR-001")
        self.assertIn("published PR-001", result.stdout)
        rec = self.load(pr_id)
        # T-353/V1-10 #2: every new publish writes schema_version 2 now
        # (the live registry stays at 1 until T-355 runs `migrate` --
        # board T-353 AC-3's ordering invariant). Amended assertion,
        # disclosed in this file's module docstring, amendment 3.
        self.assertEqual(rec["schema_version"], 2)
        self.assertEqual(rec["status"], "active")
        self.assertEqual(rec["authority_tier"], 4)
        self.assertEqual(rec["confirmation_status"], "unconfirmed")
        self.assertIsNone(rec["confirmed_by"])
        self.assertIsNone(rec["confirmed_at"])
        self.assertIsNone(rec["narrowed_scope"])
        self.assertIsNone(rec["confirmation_note"])
        self.assertEqual(rec["cited_by"], [])
        self.assertIsNone(rec["overruled_by"])
        self.assertIsNone(rec["superseded_by"])
        self.assertIsNone(rec["voided_by"])
        self.assertEqual(rec["relations"], [])
        self.assertEqual(rec["dicta"], [])
        self.assertEqual(rec["cites"], [])

    def test_ids_are_monotonic_and_zero_padded(self):
        id1, _ = self.publish_ok(task="T-101", subject="subj-1")
        id2, _ = self.publish_ok(task="T-102", subject="subj-2")
        id3, _ = self.publish_ok(task="T-103", subject="subj-3")
        self.assertEqual([id1, id2, id3], ["PR-001", "PR-002", "PR-003"])

    def test_ratio_file_and_stdin_forms(self):
        # publish() always injects a bare --ratio, which conflicts (mutually
        # exclusive group) with --ratio-file/--ratio-stdin -- both forms are
        # exercised via raw run() calls instead of the publish() helper.
        rfile = pathlib.Path(self._tmp.name) / "ratio.txt"
        rfile.write_text("ratio via file, with `backticks` and $(danger)", encoding="utf-8")
        result = run("publish", "--root", str(self.root), "--task", "T-110", "--title", "t",
                     "--subject", "subj-file", "--tier", "4", "--tier-evidence", "T-110",
                     "--ratio-file", str(rfile), "--width", "narrow",
                     "--sources", "T-110", "--code-version", "v1")
        self.assertEqual(result.returncode, 0, result.stderr)
        pr_id = result.stdout.strip().splitlines()[-1].split()[-1]
        rec = self.load(pr_id)
        self.assertEqual(rec["ratio"], "ratio via file, with `backticks` and $(danger)")

        result2 = run("publish", "--root", str(self.root), "--task", "T-111", "--title", "t",
                     "--subject", "subj-file2", "--tier", "4", "--tier-evidence", "T-111",
                     "--ratio-stdin", "--width", "narrow", "--sources", "T-111",
                     "--code-version", "v1", input_text="ratio via stdin")
        self.assertEqual(result2.returncode, 0, result2.stderr)

    def test_scope_file_newline_delimited(self):
        sfile = pathlib.Path(self._tmp.name) / "scope.txt"
        sfile.write_text("role:worker\n\nrole:verifier\n", encoding="utf-8")
        result = run("publish", "--root", str(self.root), "--task", "T-120", "--title", "t",
                     "--subject", "subj-scopefile", "--tier", "3", "--tier-evidence", "T-120",
                     "--ratio", "r", "--width", "narrow", "--scope-file", str(sfile),
                     "--revisit-trigger", "x", "--sources", "T-120", "--code-version", "v1",
                     "--validity", "validity condition placeholder")
        self.assertEqual(result.returncode, 0, result.stderr)
        pr_id = result.stdout.strip().splitlines()[-1].split()[-1]
        rec = self.load(pr_id)
        self.assertEqual(rec["scope_conditions"], ["role:worker", "role:verifier"])

    def test_dicta_and_cites_are_lists(self):
        pr_id, _ = self.publish_ok(task="T-130", subject="subj-dicta",
                                    extra_args=["--dicta", "d1", "--dicta", "d2"])
        rec = self.load(pr_id)
        self.assertEqual(rec["dicta"], ["d1", "d2"])


# ==========================================================================
# publish -- SDR-17 structural validation (exit 1 refusals)
# ==========================================================================

class PublishRefusalTests(PrecedentCLITestCase):
    def assertRefused(self, result, needle):
        self.assertEqual(result.returncode, 1, "stdout={!r} stderr={!r}".format(result.stdout, result.stderr))
        self.assertIn(needle, result.stderr)

    def test_refuses_empty_ratio(self):
        result = self.publish(ratio="   ")
        self.assertRefused(result, "ratio must be non-empty")

    def test_refuses_bad_subject_slug(self):
        result = self.publish(subject="Not A Slug!")
        self.assertRefused(result, "slug regex")

    def test_refuses_title_too_long(self):
        result = self.publish(title="x" * 81)
        self.assertRefused(result, "title exceeds 80")

    def test_refuses_out_of_range_tier(self):
        result = run("publish", "--root", str(self.root), "--task", "T-1", "--title", "t",
                     "--subject", "s", "--tier", "9", "--tier-evidence", "T-1", "--ratio", "r",
                     "--width", "narrow")
        self.assertRefused(result, "tier must be one of 1,2,3,4")

    def test_refuses_missing_tier_evidence(self):
        result = run("publish", "--root", str(self.root), "--task", "T-1", "--title", "t",
                     "--subject", "s", "--tier", "4", "--ratio", "r", "--width", "narrow")
        self.assertRefused(result, "tier_evidence must be non-empty")

    def test_refuses_wrong_tier_evidence_kind(self):
        # tier 2 needs a P-NNN token; a T-NNN token is the wrong kind.
        result = self.publish(tier=2, tier_evidence=["T-100"])
        self.assertRefused(result, "lacks a required token kind")

    def test_refuses_missing_scope_at_tier3(self):
        result = self.publish(tier=3, scope=[], revisit_trigger="x")
        self.assertRefused(result, "scope_conditions must be non-empty")

    def test_refuses_missing_revisit_trigger_at_tier1(self):
        result = self.publish(tier=1, tier_evidence=["T-100"], revisit_trigger="")
        self.assertRefused(result, "revisit_trigger must be non-empty")

    def test_refuses_bad_width(self):
        result = run("publish", "--root", str(self.root), "--task", "T-1", "--title", "t",
                     "--subject", "s", "--tier", "4", "--tier-evidence", "T-100", "--ratio", "r",
                     "--width", "sideways")
        self.assertRefused(result, "declared_width must be")

    def test_refuses_dangling_relation_target(self):
        result = self.publish(extra_args=["--follows", "PR-999"])
        self.assertRefused(result, "does not resolve to an existing record")

    def test_refuses_invalid_factor_name(self):
        target_id, _ = self.publish_ok(task="T-140", subject="subj-factor", tier=3)
        result = self.publish(task="T-141", subject="subj-factor2", tier=3,
                               extra_args=["--overrules", target_id, "--factor", "bogus_factor",
                                           "--factor-note", "note"])
        self.assertRefused(result, "not one of")


# ==========================================================================
# publish -- distinguishes (SDR-17.7 + below_target_tier)
# ==========================================================================

class DistinguishTests(PrecedentCLITestCase):
    def test_distinguish_requires_nonempty_facts(self):
        target_id, _ = self.publish_ok(task="T-150", subject="subj-dist", tier=1)
        result = self.publish(task="T-151", subject="subj-dist2", tier=4,
                               extra_args=["--distinguishes", target_id,
                                           "--distinguishing-facts", ""])
        self.assertEqual(result.returncode, 1)
        self.assertIn("non-empty distinguishing_facts", result.stderr)

    def test_distinguish_requires_nonempty_target_scope(self):
        # tier 4 target -> its scope_conditions defaults to [] in this test's publish()
        target_id, _ = self.publish_ok(task="T-160", subject="subj-noscope", tier=4)
        result = self.publish(task="T-161", subject="subj-noscope2", tier=4,
                               extra_args=["--distinguishes", target_id,
                                           "--distinguishing-facts", "these facts differ"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("scope_conditions is empty", result.stderr)

    def test_distinguish_accepted_and_stamps_below_target_tier(self):
        target_id, _ = self.publish_ok(task="T-170", subject="subj-below", tier=1)
        acting_id, _ = self.publish_ok(task="T-171", subject="subj-below2", tier=4,
                                        extra_args=["--distinguishes", target_id,
                                                    "--distinguishing-facts", "material facts differ"])
        rec = self.load(acting_id)
        self.assertEqual(len(rec["relations"]), 1)
        rel = rec["relations"][0]
        self.assertEqual(rel["type"], "distinguishes")
        self.assertEqual(rel["target"], target_id)
        self.assertTrue(rel["below_target_tier"])  # acting tier 4 > target tier 1

    def test_distinguish_facts_file_form(self):
        target_id, _ = self.publish_ok(task="T-172", subject="subj-below3", tier=1)
        ffile = pathlib.Path(self._tmp.name) / "facts.txt"
        ffile.write_text("facts from a file", encoding="utf-8")
        acting_id, _ = self.publish_ok(task="T-173", subject="subj-below4", tier=4,
                                        extra_args=["--distinguishes", target_id,
                                                    "--distinguishing-facts-file", str(ffile)])
        rec = self.load(acting_id)
        self.assertEqual(rec["relations"][0]["distinguishing_facts"], "facts from a file")

    def test_distinguish_mismatched_counts_refused(self):
        t1, _ = self.publish_ok(task="T-174", subject="subj-below5", tier=1)
        t2, _ = self.publish_ok(task="T-175", subject="subj-below6", tier=1)
        result = self.publish(task="T-176", subject="subj-below7", tier=4,
                               extra_args=["--distinguishes", t1, "--distinguishes", t2,
                                           "--distinguishing-facts", "only one fact given"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("exactly one paired", result.stderr)


# ==========================================================================
# publish -- overrules / voids / supersedes (SDR-17.8-13, SDR-19.3/19.4)
# ==========================================================================

class OverruleVoidSupersedeTests(PrecedentCLITestCase):
    def test_overrules_refuses_lower_authority_attacking_higher(self):
        target_id, _ = self.publish_ok(task="T-180", subject="subj-auth", tier=1)
        result = self.publish(task="T-181", subject="subj-auth2", tier=4,
                               extra_args=["--overrules", target_id])
        self.assertEqual(result.returncode, 1)
        self.assertIn("lower authority than", result.stderr)

    def test_overrules_refuses_tier4_target(self):
        target_id, _ = self.publish_ok(task="T-190", subject="subj-t4", tier=4)
        result = self.publish(task="T-191", subject="subj-t4b", tier=3,
                               extra_args=["--overrules", target_id])
        self.assertEqual(result.returncode, 1)
        self.assertIn("category error", result.stderr)

    def test_overrules_tier3_target_requires_factor(self):
        target_id, _ = self.publish_ok(task="T-200", subject="subj-t3", tier=3)
        result = self.publish(task="T-201", subject="subj-t3b", tier=3,
                               extra_args=["--overrules", target_id])
        self.assertEqual(result.returncode, 1)
        self.assertIn("requires >=1 --factor", result.stderr)

    def test_overrules_with_factor_requires_note(self):
        target_id, _ = self.publish_ok(task="T-202", subject="subj-t3c", tier=3)
        result = self.publish(task="T-203", subject="subj-t3d", tier=3,
                               extra_args=["--overrules", target_id, "--factor", "reasoning_error"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("factor-note", result.stderr)

    def test_overrules_refuses_on_nonempty_cited_by_without_ack(self):
        target_id, _ = self.publish_ok(task="T-210", subject="subj-cb", tier=3)
        # a citing record populates target's cited_by
        self.publish_ok(task="T-211", subject="subj-cb-citer", tier=4,
                        extra_args=["--cites", target_id])
        result = self.publish(task="T-212", subject="subj-cb2", tier=3,
                               extra_args=["--overrules", target_id, "--factor", "reasoning_error",
                                           "--factor-note", "reasoning no longer holds"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("acknowledge-reliance", result.stderr)

        # with the acknowledgement, it succeeds and flips the target's status
        result2 = self.publish(task="T-213", subject="subj-cb3", tier=3,
                                extra_args=["--overrules", target_id, "--factor", "reasoning_error",
                                            "--factor-note", "reasoning no longer holds",
                                            "--acknowledge-reliance"])
        self.assertEqual(result2.returncode, 0, result2.stderr)
        new_id = result2.stdout.strip().splitlines()[-1].split()[-1]
        target_rec = self.load(target_id)
        self.assertEqual(target_rec["status"], "overruled")
        self.assertEqual(target_rec["overruled_by"], new_id)
        self.assertIn(new_id, target_rec["cited_by"])

    def test_overrules_refuses_nonactive_target(self):
        target_id, _ = self.publish_ok(task="T-220", subject="subj-na", tier=3)
        r1 = self.publish(task="T-221", subject="subj-na2", tier=3,
                          extra_args=["--overrules", target_id, "--factor", "unworkability",
                                      "--factor-note", "note one"])
        self.assertEqual(r1.returncode, 0, r1.stderr)
        r2 = self.publish(task="T-222", subject="subj-na3", tier=3,
                          extra_args=["--overrules", target_id, "--factor", "unworkability",
                                      "--factor-note", "note two"])
        self.assertEqual(r2.returncode, 1)
        self.assertIn("not active", r2.stderr)

    def test_voids_requires_resolvable_controlling_authority(self):
        target_id, _ = self.publish_ok(task="T-230", subject="subj-void", tier=3)
        r1 = self.publish(task="T-231", subject="subj-void2", tier=3,
                          extra_args=["--voids", target_id])
        self.assertEqual(r1.returncode, 1)
        self.assertIn("controlling-authority", r1.stderr)

        r2 = self.publish(task="T-232", subject="subj-void3", tier=3,
                          extra_args=["--voids", target_id, "--controlling-authority", "T-999999"])
        self.assertEqual(r2.returncode, 1)
        self.assertIn("controlling-authority", r2.stderr)

        # T-330 is a real, permanent task in this repo's live .harness/tasks/
        r3 = self.publish(task="T-233", subject="subj-void4", tier=3,
                          extra_args=["--voids", target_id, "--controlling-authority", "T-330"])
        self.assertEqual(r3.returncode, 0, r3.stderr)
        new_id = r3.stdout.strip().splitlines()[-1].split()[-1]
        target_rec = self.load(target_id)
        self.assertEqual(target_rec["status"], "void_per_incuriam")
        self.assertEqual(target_rec["voided_by"], new_id)

    def test_supersedes_flips_status_and_backref(self):
        target_id, _ = self.publish_ok(task="T-240", subject="subj-super", tier=4)
        new_id, _ = self.publish_ok(task="T-241", subject="subj-super2", tier=4,
                                     extra_args=["--supersedes", target_id])
        target_rec = self.load(target_id)
        self.assertEqual(target_rec["status"], "superseded")
        self.assertEqual(target_rec["superseded_by"], new_id)

    def test_supersedes_refuses_nonactive_target(self):
        target_id, _ = self.publish_ok(task="T-250", subject="subj-super3", tier=4)
        self.publish_ok(task="T-251", subject="subj-super4", tier=4,
                        extra_args=["--supersedes", target_id])
        result = self.publish(task="T-252", subject="subj-super5", tier=4,
                               extra_args=["--supersedes", target_id])
        self.assertEqual(result.returncode, 1)
        self.assertIn("not active", result.stderr)


# ==========================================================================
# show / list / cite
# ==========================================================================

class ShowListCiteTests(PrecedentCLITestCase):
    def test_show_unknown_record_refused(self):
        result = run("show", "PR-999", "--root", str(self.root))
        self.assertEqual(result.returncode, 1)

    def test_show_prints_binding_summary_unconfirmed(self):
        pr_id, _ = self.publish_ok(task="T-260", subject="subj-show")
        result = run("show", pr_id, "--root", str(self.root))
        self.assertEqual(result.returncode, 0)
        self.assertIn("UNCONFIRMED (does not bind)", result.stdout)

    def test_show_corrupt_record_returns_4(self):
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "PR-005.json").write_text("{not valid json", encoding="utf-8")
        result = run("show", "PR-005", "--root", str(self.root))
        self.assertEqual(result.returncode, 4)
        self.assertIn("REGISTRY INTEGRITY ERROR", result.stderr)

    def test_list_detects_corrupt_record(self):
        self.publish_ok(task="T-270", subject="subj-list-a")
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "PR-777.json").write_text("not json at all", encoding="utf-8")
        result = run("list", "--root", str(self.root))
        self.assertEqual(result.returncode, 4)

    def test_list_filters_by_tier_and_status(self):
        self.publish_ok(task="T-280", subject="subj-list-b", tier=4)
        self.publish_ok(task="T-281", subject="subj-list-c", tier=1)
        result = run("list", "--root", str(self.root), "--tier", "1")
        self.assertEqual(result.returncode, 0)
        self.assertIn("subj-list-c", result.stdout)
        self.assertNotIn("subj-list-b", result.stdout)

    def test_list_json_mode(self):
        self.publish_ok(task="T-290", subject="subj-list-json")
        result = run("list", "--root", str(self.root), "--json")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["subject"], "subj-list-json")

    def test_cite_bare_tokens_resolve_and_dangle(self):
        pr_id, _ = self.publish_ok(task="T-300", subject="subj-cite")
        result_ok = run("cite", "T-300", "--root", str(self.root))
        self.assertEqual(result_ok.returncode, 0)
        result_dangling = run("cite", "T-999999", "--root", str(self.root))
        self.assertEqual(result_dangling.returncode, 3)

    def test_cite_record_form(self):
        target_id, _ = self.publish_ok(task="T-310", subject="subj-cite2", tier=1)
        result = run("cite", "--record", target_id, "--root", str(self.root))
        self.assertEqual(result.returncode, 0)

    def test_cite_all_form_detects_dangling(self):
        self.publish_ok(task="T-320", subject="subj-cite3",
                        extra_args=["--cites", "T-999999"])
        result = run("cite", "--all", "--root", str(self.root))
        self.assertEqual(result.returncode, 3)

    def test_cite_no_args_is_usage_error(self):
        result = run("cite", "--root", str(self.root))
        self.assertEqual(result.returncode, 2)

    def test_publish_dangling_cites_warns_but_still_publishes(self):
        result = self.publish(task="T-3302", subject="subj-dangle",
                              extra_args=["--cites", "T-999999"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("dangling", result.stdout.lower())


# ==========================================================================
# confirm (SDR-24/25)
# ==========================================================================

class ConfirmTests(PrecedentCLITestCase):
    def test_confirm_refuses_self_confirmation(self):
        pr_id, _ = self.publish_ok(task="T-3401", subject="subj-conf")
        result = run("confirm", pr_id, "--root", str(self.root), "--agent", "main",
                     "--outcome", "confirmed", "--note", "self attempt")
        self.assertEqual(result.returncode, 1)
        self.assertIn("SDR-24.1", result.stderr)

    def test_confirm_requires_note(self):
        pr_id, _ = self.publish_ok(task="T-3402", subject="subj-conf2")
        result = run("confirm", pr_id, "--root", str(self.root), "--agent", "verifier-x",
                     "--outcome", "confirmed")
        self.assertEqual(result.returncode, 1)

    def test_confirm_narrowed_requires_scope(self):
        pr_id, _ = self.publish_ok(task="T-3403", subject="subj-conf3")
        result = run("confirm", pr_id, "--root", str(self.root), "--agent", "verifier-x",
                     "--outcome", "narrowed", "--note", "narrowing")
        self.assertEqual(result.returncode, 1)
        self.assertIn("narrowed", result.stderr)

    def test_confirm_invalid_outcome(self):
        pr_id, _ = self.publish_ok(task="T-3404", subject="subj-conf4")
        result = run("confirm", pr_id, "--root", str(self.root), "--agent", "verifier-x",
                     "--outcome", "bogus", "--note", "n")
        self.assertEqual(result.returncode, 1)

    def test_confirm_refuses_nonactive_target(self):
        target_id, _ = self.publish_ok(task="T-3405", subject="subj-conf5", tier=4)
        self.publish_ok(task="T-3406", subject="subj-conf6", tier=4,
                        extra_args=["--supersedes", target_id])
        result = run("confirm", target_id, "--root", str(self.root), "--agent", "verifier-x",
                     "--outcome", "confirmed", "--note", "trying anyway")
        self.assertEqual(result.returncode, 1)
        self.assertIn("SDR-24.2", result.stderr)

    def test_confirm_success_confirmed(self):
        pr_id, _ = self.publish_ok(task="T-3407", subject="subj-conf7")
        result = run("confirm", pr_id, "--root", str(self.root), "--agent", "verifier-x",
                     "--outcome", "confirmed", "--note", "scope holds")
        self.assertEqual(result.returncode, 0, result.stderr)
        rec = self.load(pr_id)
        self.assertEqual(rec["confirmation_status"], "confirmed")
        self.assertEqual(rec["confirmed_by"], "verifier-x")
        self.assertIsNotNone(rec["confirmed_at"])
        self.assertEqual(rec["confirmation_note"], "scope holds")

    def test_confirm_success_narrowed_sets_narrowed_scope(self):
        pr_id, _ = self.publish_ok(task="T-3408", subject="subj-conf8")
        result = run("confirm", pr_id, "--root", str(self.root), "--agent", "verifier-x",
                     "--outcome", "narrowed", "--note", "scope is narrower than declared",
                     "--scope", "role:worker only")
        self.assertEqual(result.returncode, 0, result.stderr)
        rec = self.load(pr_id)
        self.assertEqual(rec["confirmation_status"], "narrowed")
        self.assertEqual(rec["narrowed_scope"], ["role:worker only"])

    def test_confirm_shows_in_binding_summary(self):
        pr_id, _ = self.publish_ok(task="T-3409", subject="subj-conf9")
        run("confirm", pr_id, "--root", str(self.root), "--agent", "verifier-x",
            "--outcome", "rejected", "--note", "scope claim rejected")
        result = run("show", pr_id, "--root", str(self.root))
        self.assertIn("REJECTED", result.stdout)


# ==========================================================================
# MANDATORY (AC-4): concurrent publish -- two subprocesses, distinct IDs
# ==========================================================================

class ConcurrentPublishTests(PrecedentCLITestCase):
    def test_two_concurrent_publishes_get_distinct_monotonic_ids(self):
        """AC-4: PR-NNN IDs are minted inside hc.guarded() so two concurrent
        publishes cannot collide, and allocation is monotonic. Launches both
        subprocesses before waiting on either, so they genuinely race for the
        guard rather than running sequentially."""

        def build(task, subject):
            return [sys.executable, str(PRECEDENT_PY), "publish", "--root", str(self.root),
                    "--task", task, "--title", "concurrent test", "--subject", subject,
                    "--tier", "4", "--tier-evidence", task, "--ratio", "concurrent ratio text",
                    "--width", "narrow", "--sources", task, "--code-version", "v1"]

        p1 = subprocess.Popen(build("T-401", "concurrent-a"), stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
        p2 = subprocess.Popen(build("T-402", "concurrent-b"), stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
        out1, err1 = p1.communicate(timeout=30)
        out2, err2 = p2.communicate(timeout=30)

        self.assertEqual(p1.returncode, 0, err1)
        self.assertEqual(p2.returncode, 0, err2)

        id1 = out1.strip().splitlines()[-1].split()[-1]
        id2 = out2.strip().splitlines()[-1].split()[-1]

        self.assertNotEqual(id1, id2, "two concurrent publishes minted the same id")
        self.assertEqual({id1, id2}, {"PR-001", "PR-002"},
                         "allocation must be monotonic and gap-free even under contention")

        for pid, task in ((id1, "T-401"), (id2, "T-402")):
            path = self.root / (pid + ".json")
            self.assertTrue(path.exists(), "{} record missing after concurrent publish".format(pid))
            rec = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(rec["id"], pid)
            self.assertEqual(rec["issuing_task"], task)


# ==========================================================================
# MANDATORY (AC-5): --root / PRECEDENT_ROOT isolation from the live registry
# ==========================================================================

class RootIsolationTests(PrecedentCLITestCase):
    def _live_pr_files(self):
        if not LIVE_REGISTRY.exists():
            return set()
        return set(p.name for p in LIVE_REGISTRY.glob("PR-*.json"))

    def test_root_flag_isolates_from_live_registry(self):
        before = self._live_pr_files()
        result = self.publish(task="T-410", subject="subj-isolation-flag")
        self.assertEqual(result.returncode, 0, result.stderr)
        after = self._live_pr_files()
        self.assertEqual(before, after, "publish with --root wrote into the live registry")
        # and it DID land in the override root, proving the override is not a no-op
        pr_id = result.stdout.strip().splitlines()[-1].split()[-1]
        self.assertTrue((self.root / (pr_id + ".json")).exists())

    def test_precedent_root_env_var_isolates_from_live_registry(self):
        """SDR-13: PRECEDENT_ROOT env var also redirects the registry (no
        --root flag passed at all here)."""
        before = self._live_pr_files()
        env = dict(os.environ)
        env["PRECEDENT_ROOT"] = str(self.root)
        result = run("publish", "--task", "T-411", "--title", "env override test",
                     "--subject", "subj-isolation-env", "--tier", "4",
                     "--tier-evidence", "T-411", "--ratio", "r", "--width", "narrow",
                     "--sources", "T-411", "--code-version", "v1",
                     env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = self._live_pr_files()
        self.assertEqual(before, after, "publish with PRECEDENT_ROOT wrote into the live registry")
        pr_id = result.stdout.strip().splitlines()[-1].split()[-1]
        self.assertTrue((self.root / (pr_id + ".json")).exists(),
                        "PRECEDENT_ROOT override did not redirect the write at all")

    def test_root_flag_wins_over_env_var(self):
        """SDR-13: --root wins over PRECEDENT_ROOT when both are given."""
        other_root = pathlib.Path(self._tmp.name) / "other-registry"
        env = dict(os.environ)
        env["PRECEDENT_ROOT"] = str(other_root)
        result = run("publish", "--root", str(self.root), "--task", "T-412",
                     "--title", "flag wins", "--subject", "subj-flag-wins", "--tier", "4",
                     "--tier-evidence", "T-412", "--ratio", "r", "--width", "narrow",
                     "--sources", "T-412", "--code-version", "v1",
                     env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        pr_id = result.stdout.strip().splitlines()[-1].split()[-1]
        self.assertTrue((self.root / (pr_id + ".json")).exists())
        self.assertFalse(other_root.exists(), "PRECEDENT_ROOT was consulted despite --root being given")


if __name__ == "__main__":
    unittest.main()
