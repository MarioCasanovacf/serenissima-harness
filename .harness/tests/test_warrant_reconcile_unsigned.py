"""Pins defect RECONCILE-UNSIGNED-DIRTY and, more importantly, the claim used to justify
narrowing `clean`.

The defect. `reconcile` computed `clean = not orphans and not warrants_invalid`, and
`warrants_invalid` collected every warrant file that failed to verify -- including files
with no signature at all. But `draft` writes an UNSIGNED payload by construction, because
the coordinator cannot sign. So the ordinary state between drafting and signing reported
`clean: false`, and a signature that EXISTS and FAILS reported the identical `clean: false`.
Found 2026-08-17, the first time a real operator-signed warrant was applied: W-002 verified,
19 roll rows all traced, zero orphans, and the indicator still said false because a
withdrawn W-001 draft was sitting in the directory. An indicator that is false in the normal
case trains its reader to ignore it, and then the real alarm arrives in the same colour.

The fix separates `warrants_unsigned` (informational) from `warrants_invalid` (sets clean
false). The justification is a claim, and a claim in a control plane needs a test:

    AN UNSIGNED WARRANT AUTHORIZES NOTHING, SO DROPPING IT FROM `clean` LOSES NO DETECTION.

If that claim is false, this narrowing is a hole. `test_unsigned_warrant_still_produces_an
_orphan` is the test that would catch it: it puts a roll row on the books that ONLY an
unsigned warrant could explain, and demands that reconcile still reports it and still says
clean is false. Every other test here is secondary to that one.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import warrant  # noqa: E402
import roster   # noqa: E402


def sh(*args):
    return subprocess.run(list(args), capture_output=True, text=True, check=True)


class Sandbox(unittest.TestCase):
    """A real enrolled harness in a temp dir, with a real signing key. Never touches the
    live trust store; a test in test_warrant.py asserts that separately."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = pathlib.Path(self._tmp.name)
        self.hroot = self.base / ".harness"
        self.hroot.mkdir()
        self.rootkey = self.base / "rootkey"
        sh("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.rootkey), "-C", "root")
        self.agentkey = self.base / "agentkey"
        sh("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.agentkey), "-C", "agent")
        warrant.init_root(self.hroot, self.rootkey.with_suffix(".pub")) \
            if hasattr(warrant, "init_root") else self.cli("init", "--root-pub",
                                                           str(self.rootkey.with_suffix(".pub")))

    def cli(self, *args):
        r = subprocess.run(
            [sys.executable, str(ROOT / ".harness" / "bin" / "warrant.py"),
             "--root", str(self.hroot)] + list(args),
            capture_output=True, text=True)
        return r

    def draft(self, epic, name):
        r = self.cli("draft", "--epic", epic,
                     "--colegiado", "banco=paga por prestamos cobrados",
                     "--plaza", "banco/judge=1",
                     "--name", "{}:banco/judge:{}:Ana".format(name, self.agentkey.with_suffix(".pub")))
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def sign(self, payload_path):
        # The operator's job, done here with a passphrase-less throwaway key. This is the
        # ONLY place a test may sign, and it signs its own sandbox key, never the operator's.
        sh("ssh-keygen", "-Y", "sign", "-f", str(self.rootkey),
           "-n", warrant.NAMESPACE, str(payload_path))

    def reconcile(self):
        r = self.cli("reconcile")
        return json.loads(r.stdout)


class TheDefect(Sandbox):

    def test_a_pending_draft_does_not_make_the_harness_dirty(self):
        signed = self.draft("epic-signed", "worker-signed")
        self.sign(signed["path"])
        self.cli("apply", "--warrant", signed["warrant_id"])
        self.draft("epic-pending", "worker-pending")     # never signed

        out = self.reconcile()
        self.assertEqual(out["orphans"], [])
        self.assertEqual(out["warrants_invalid"], [])
        self.assertEqual([w["id"] for w in out["warrants_unsigned"]], ["W-002"])
        self.assertTrue(out["clean"],
                        "a draft awaiting the operator must not read as dirty: %r" % out)
        self.assertIn("NORMAL state of a draft", out["note"])

    def test_a_signature_that_fails_still_makes_the_harness_dirty(self):
        signed = self.draft("epic-signed", "worker-signed")
        self.sign(signed["path"])
        self.cli("apply", "--warrant", signed["warrant_id"])
        # Tamper AFTER signing: the .sig exists and no longer matches the bytes.
        p = pathlib.Path(signed["path"])
        payload = json.loads(p.read_text(encoding="utf-8"))
        payload["epic"] = "epic-tampered"
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        out = self.reconcile()
        self.assertEqual([w["id"] for w in out["warrants_unsigned"]], [])
        self.assertEqual([w["id"] for w in out["warrants_invalid"]], ["W-001"])
        self.assertFalse(out["clean"], "a failing signature must be dirty: %r" % out)

    def test_a_failing_signature_is_dirty_even_with_no_orphan(self):
        """The test the first version of this file was MISSING, and a negative control
        caught it.

        The case above tampers with a warrant that had already been APPLIED, so its roll
        rows lose their backing and become orphans. `clean` then goes false through
        `orphans`, and the assertion passes even if `warrants_invalid` stops counting at
        all. Deleting `warrants_invalid` from the `clean` expression left that test green,
        which means it was not testing what its name claimed.

        This one tampers with a warrant that was never applied, so the roll is spotless and
        `warrants_invalid` is the ONLY thing that can condemn the harness.
        """
        good = self.draft("epic-good", "worker-good")
        self.sign(good["path"])
        self.cli("apply", "--warrant", good["warrant_id"])

        rogue = self.draft("epic-rogue", "worker-rogue")
        self.sign(rogue["path"])                      # signature exists and is valid...
        p = pathlib.Path(rogue["path"])
        payload = json.loads(p.read_text(encoding="utf-8"))
        payload["epic"] = "epic-rogue-tampered"       # ...and now covers different bytes
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        # deliberately NOT applied, so nothing from it is on the roll

        out = self.reconcile()
        self.assertEqual(out["orphans"], [],
                         "this case must isolate warrants_invalid; got orphans %r"
                         % out["orphans"])
        self.assertEqual([w["id"] for w in out["warrants_unsigned"]], [])
        self.assertEqual([w["id"] for w in out["warrants_invalid"]], [rogue["warrant_id"]])
        self.assertFalse(
            out["clean"],
            "a warrant whose signature fails must set clean false on its own, with no "
            "orphan to lean on: %r" % out)


class TheJustification(Sandbox):
    """The claim the narrowing rests on. If these fail, the narrowing is a hole."""

    def test_unsigned_warrant_still_produces_an_orphan(self):
        # THE test. A roll row that only an unsigned warrant could explain must still be
        # reported, and must still set clean false. Written directly to roster.json, which
        # is exactly the tampering path reconcile exists to catch.
        pending = self.draft("epic-pending", "worker-pending")
        payload = json.loads(pathlib.Path(pending["path"]).read_text(encoding="utf-8"))
        data = roster.load(self.hroot)
        data.setdefault("colegiados", {})["banco"] = {"charter": "smuggled"}
        data.setdefault("plazas", {}).setdefault("epic-pending", {})["banco/judge"] = 1
        data.setdefault("names", {})["worker-pending"] = {
            "colegiado": "banco", "role": "judge", "epic": "epic-pending",
            "issued_by": "warrant:{}".format(pending["warrant_id"])}
        (self.hroot / "roster.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        out = self.reconcile()
        kinds = {o["kind"] for o in out["orphans"]}
        self.assertIn("colegiado", kinds)
        self.assertIn("plaza", kinds)
        self.assertIn("name", kinds)
        self.assertFalse(out["clean"],
                         "rows backed only by an unsigned warrant must be dirty: %r" % out)
        self.assertEqual([w["id"] for w in out["warrants_unsigned"]], [pending["warrant_id"]])
        # And the point of the whole exercise: the unsigned file is reported as such, while
        # the ORPHANS are what condemn the harness. Detection did not move.
        self.assertTrue(out["orphans"])

    def test_apply_refuses_an_unsigned_warrant(self):
        pending = self.draft("epic-pending", "worker-pending")
        r = self.cli("apply", "--warrant", pending["warrant_id"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unsigned", (r.stdout + r.stderr).lower())
        # Nothing reached the roll.
        data = roster.load(self.hroot)
        self.assertEqual(data.get("names", {}), {})

    def test_verify_refuses_an_unsigned_warrant(self):
        pending = self.draft("epic-pending", "worker-pending")
        r = self.cli("verify", "--warrant", pending["warrant_id"])
        self.assertNotEqual(r.returncode, 0)


class TheExceptionType(unittest.TestCase):

    def test_unsigned_is_a_subclass_so_existing_callers_are_unchanged(self):
        # The whole reason a new type is safe here. Any `except TrustError` still catches it.
        self.assertTrue(issubclass(warrant.UnsignedWarrant, warrant.TrustError))

    def test_the_narrowing_is_documented_where_it_happens(self):
        src = (ROOT / ".harness" / "bin" / "warrant.py").read_text(encoding="utf-8")
        self.assertIn("RECONCILE-UNSIGNED-DIRTY", src)
        self.assertIn("authorizes NOTHING", src)


if __name__ == "__main__":
    unittest.main()
