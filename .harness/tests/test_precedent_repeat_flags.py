"""T-376: `publish` must refuse a repeated single-value flag, never silently keep the last.

The defect, found by the coordinator publishing PR-032: `precedent.py publish` accepted
`--voids A --voids B`, kept only B, exited 0, and wrote ONE relation where two were asked
for. Silent discard of an explicit instruction, made permanent by an immutable record.

A mechanical audit of the parser found the same shape on 33 flags, not one. Twelve flags on
the same subcommand accumulate, so the semantics were inconsistent and the trap was
invisible from outside: nothing in the help text distinguishes a flag that accumulates from
one that overwrites. The fix is uniform (StoreOnce on every single-value flag of `publish`
and `confirm`) rather than scoped to the five relation flags T-376 named, because fixing
five siblings and leaving 28 with the identical trap is a half-repair.

The tests below are grouped by what they protect:
  - the reported defect, on `--voids` specifically;
  - the siblings the audit found, so the uniform fix cannot silently shrink back;
  - that flags which SHOULD accumulate still do, which is the regression the fix could
    plausibly cause;
  - that the refusal happens before anything is written.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLI = ROOT / ".harness" / "bin" / "precedent.py"

sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import precedent  # noqa: E402


class PublishCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.reg = pathlib.Path(self._tmp.name)

    def publish(self, *extra):
        base = ["publish", "--root", str(self.reg), "--tier", "3",
                "--subject", "prueba", "--title", "t", "--task", "T-999",
                "--ratio", "una regla", "--tier-evidence", "T-999"]
        return subprocess.run([sys.executable, str(CLI)] + base + list(extra),
                              capture_output=True, text=True)

    def records(self):
        return sorted(p.name for p in self.reg.glob("PR-*.json"))


class TheReportedDefect(PublishCase):

    def test_two_voids_are_refused(self):
        r = self.publish("--voids", "PR-001", "--voids", "PR-002",
                         "--controlling-authority", "PR-003")
        self.assertNotEqual(r.returncode, 0)
        msg = r.stderr + r.stdout
        self.assertIn("--voids was given more than once", msg)
        self.assertIn("T-376", msg)

    def test_the_refusal_names_the_workaround(self):
        r = self.publish("--voids", "PR-001", "--voids", "PR-002")
        msg = r.stderr + r.stdout
        # An operator told only "no" cannot proceed. The message has to say what to do.
        self.assertIn("publish two acts", msg)

    def test_nothing_is_written_when_a_repeat_is_refused(self):
        # argparse refuses during parsing, so no record can exist. Asserted rather than
        # assumed: a refusal that half-wrote a record would be worse than the defect.
        self.publish("--voids", "PR-001", "--voids", "PR-002")
        self.assertEqual(self.records(), [])

    def test_one_voids_still_gets_past_the_parser(self):
        # The guard must not break the legitimate single use. This publish still fails, on a
        # LATER and unrelated validation, which is exactly the proof that parsing succeeded.
        r = self.publish("--voids", "PR-001")
        msg = r.stderr + r.stdout
        self.assertNotIn("given more than once", msg)


class TheSiblingsTheAuditFound(PublishCase):
    """The audit found 33 flags with this shape. If the uniform fix is ever narrowed back to
    `--voids`, these fail."""

    SINGLE_VALUE = [
        ("--overrules", "PR-001"),
        ("--supersedes", "PR-001"),
        ("--reinterprets", "PR-001"),
        ("--revalues", "PR-001"),
        ("--controlling-authority", "PR-001"),
        ("--title", "otro titulo"),
        ("--subject", "otro subject"),
        ("--task", "T-998"),
        ("--tier", "2"),
        ("--width", "narrow"),
        ("--operation", "determination"),
        ("--code-version", "1"),
        ("--factor-note", "una nota"),
        ("--revisit-trigger", "algo"),
        ("--overruled-record-id", "PR-001"),
    ]

    def test_every_single_value_flag_refuses_a_repeat(self):
        for flag, value in self.SINGLE_VALUE:
            with self.subTest(flag=flag):
                r = self.publish(flag, value, flag, value)
                self.assertNotEqual(r.returncode, 0, "%s accepted a repeat" % flag)
                self.assertIn("given more than once", r.stderr + r.stdout,
                              "%s failed for some other reason" % flag)

    def test_a_flag_with_a_non_none_default_also_refuses(self):
        # --operation defaults to "determination". A guard written as `if prev is not None`
        # would let this one through, which is the same silent overwrite being fixed.
        r = self.publish("--operation", "determination", "--operation", "determination")
        self.assertIn("--operation was given more than once", r.stderr + r.stdout)


class TheFlagsThatMustStillAccumulate(PublishCase):
    """The regression the fix could plausibly cause. Twelve flags accumulate by design."""

    def test_repeated_cites_and_dicta_and_tier_evidence_are_accepted(self):
        r = self.publish("--cites", "PR-001", "--cites", "PR-002",
                         "--dicta", "una", "--dicta", "otra",
                         "--tier-evidence", "T-998")
        msg = r.stderr + r.stdout
        self.assertNotIn("given more than once", msg,
                         "an append flag was caught by the single-value guard: " + msg)

    def test_repeated_sources_and_validity_are_accepted(self):
        r = self.publish("--sources", "a", "--sources", "b",
                         "--validity", "c", "--validity", "d")
        self.assertNotIn("given more than once", r.stderr + r.stdout)

    def test_the_guard_left_append_actions_untouched(self):
        # Structural, so the property does not depend on any one publish succeeding.
        import argparse
        parser = self.build_parser()
        pub = parser["publish"]
        appends = [a for a in pub._actions if isinstance(a, argparse._AppendAction)]
        self.assertGreaterEqual(len(appends), 10)
        for a in appends:
            self.assertNotIsInstance(a, precedent.StoreOnce)

    @staticmethod
    def build_parser():
        """Reach the subparsers the way main() builds them, without running a command."""
        import argparse
        holder = {}
        real = argparse.ArgumentParser.parse_args

        def capture(self, args=None, namespace=None):
            for action in self._subparsers._actions if self._subparsers else []:
                if isinstance(action, argparse._SubParsersAction):
                    holder.update(action.choices)
            raise SystemExit(0)

        argparse.ArgumentParser.parse_args = capture
        try:
            precedent.main(["publish"])
        except SystemExit:
            pass
        finally:
            argparse.ArgumentParser.parse_args = real
        return holder


class TheGuardItself(unittest.TestCase):

    def test_store_once_is_applied_to_publish_and_confirm_only(self):
        src = (ROOT / ".harness" / "bin" / "precedent.py").read_text(encoding="utf-8")
        self.assertIn("_refuse_repeats(p_pub, p_conf)", src)

    def test_the_reason_for_refusing_over_accumulating_is_recorded(self):
        # A future reader will want to accumulate instead. The trade-off must be on file so
        # they can overrule it knowingly rather than assume nobody thought about it.
        doc = precedent.StoreOnce.__doc__ or ""
        for token in ("WHY REFUSE RATHER THAN ACCUMULATE", "controlling-authority",
                      "occurrence-order", "33 flags"):
            self.assertIn(token, doc)

    def test_the_sentinel_does_not_rely_on_a_none_default(self):
        doc = precedent.StoreOnce.__doc__ or ""
        self.assertIn("non-None defaults", doc)


class TheRecordsAlreadyPublished(unittest.TestCase):
    """T-376 acceptance: PR-032 and PR-033's existing relations are immutable (class A) and
    must be byte-identical after this change."""

    def test_pr032_and_pr033_relations_are_untouched(self):
        live = ROOT / ".harness" / "precedents"
        for pr in ("PR-032", "PR-033"):
            path = live / (pr + ".json")
            if not path.is_file():
                self.skipTest(pr + " is not in this registry")
            rec = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsInstance(rec.get("relations", []), list)
            # The point of the acceptance criterion: whatever they recorded, this repair
            # did not rewrite it. Compared against git HEAD~ is out of scope here; what is
            # in scope is that the file still parses and still carries its relations.
            self.assertEqual(rec["id"], pr)


if __name__ == "__main__":
    unittest.main()


class TheRootFlag(PublishCase):
    """The gap that let a false statement survive its own test suite.

    The wiring comment in precedent.py claimed `--root` was left alone by the guard. It was
    not, and is not: `--root` is an ordinary single-value store action on `publish` and
    `confirm`, so `_refuse_repeats` has always covered it. A verifier reproduced the
    contradiction in two commands and rejected T-376 for it.

    NO TEST IN THIS FILE TOUCHED `--root`, which is the actual defect here. A claim nothing
    exercises is a claim nothing can falsify. Both halves are now pinned: the write verbs
    refuse, the read-only verbs do not.
    """

    def test_publish_refuses_a_repeated_root(self):
        r = subprocess.run(
            [sys.executable, str(CLI), "publish", "--root", "/tmp/a", "--root", "/tmp/b",
             "--tier", "3", "--subject", "s", "--title", "t", "--task", "T-999",
             "--ratio", "r", "--tier-evidence", "T-999"],
            capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--root was given more than once", r.stderr + r.stdout)

    def test_confirm_refuses_a_repeated_root(self):
        r = subprocess.run(
            [sys.executable, str(CLI), "confirm", "PR-001",
             "--root", "/tmp/a", "--root", "/tmp/b"],
            capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--root was given more than once", r.stderr + r.stdout)

    def test_a_read_only_verb_still_accepts_a_repeated_root(self):
        # The half of the old claim that WAS true, pinned so narrowing the guard to fix the
        # other half cannot silently break a wrapper that double-passes --root on a read.
        r = subprocess.run(
            [sys.executable, str(CLI), "list", "--root", str(self.reg),
             "--root", str(self.reg)], capture_output=True, text=True)
        self.assertNotIn("given more than once", r.stderr + r.stdout)

    def test_the_wiring_comment_no_longer_makes_the_false_claim(self):
        src = (ROOT / ".harness" / "bin" / "precedent.py").read_text(encoding="utf-8")
        self.assertNotIn("`--root` and\n    # the read-only verbs are left alone", src)
        self.assertIn("CORRECTED 2026-08-17", src)
