"""Falsifier tests for revoke.py: T-432 option 6a, ratified 2026-10-21 ("A verb that
revokes a name by operator order. A revocation is an operator-signed record, never an
agent act... From that moment every token for that name is refused, expired or not.").

Mirrors test_warrant.py's and test_dispatch_token.py's shape on purpose: its own
throwaway root key, generated in a temp dir, never touching the live .harness/trust
store, the operator's real ~/.ssh/harness_root, or any other live private material.
"""
import inspect
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".harness" / "bin"
LIVE_HARNESS = ROOT / ".harness"

sys.path.insert(0, str(BIN_DIR))
import revoke as rv  # noqa: E402
import dispatch_token as dt  # noqa: E402
import warrant as w  # noqa: E402
import roster  # noqa: E402


def keygen(path, comment="test"):
    subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", comment,
                    "-f", str(path), "-q"], check=True, capture_output=True)
    return pathlib.Path(str(path) + ".pub")


def root_sign(payload_path, key_path, namespace):
    r = subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key_path),
                        "-n", namespace, str(payload_path)],
                       text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return pathlib.Path(str(payload_path) + ".sig")


class GateCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = pathlib.Path(self._tmp.name)
        self.root = self.base / "harness"
        self.root.mkdir()
        self.keys = self.base / "keys"
        self.keys.mkdir()
        self.root_key = self.keys / "root"
        self.root_pub = keygen(self.root_key, "root@operator")

    def enroll(self):
        return w.init(self.root, self.root_pub)

    def draft_and_sign(self, name, reason="", key=None):
        d = rv.draft(self.root, name, reason)
        root_sign(pathlib.Path(d["path"]), key or self.root_key, rv.NAMESPACE)
        return d["revocation_id"]

    def full_token_set(self, epic="e-1", dispatches=None, ttl_seconds=3600):
        if dispatches is None:
            dispatches = ["worker-a:T-432:worker"]
        d = dt.draft(self.root, epic, dispatches, ttl_seconds)
        root_sign(pathlib.Path(d["path"]), self.root_key, dt.NAMESPACE)
        payload = json.loads(pathlib.Path(d["path"]).read_text(encoding="utf-8"))
        return payload

    def present(self, payload, index=0, **overrides):
        canonical = payload["tokens"][index]
        out = {"token_set_id": payload["token_set_id"], **canonical}
        out.update(overrides)
        return out


# ---------------------------------------------------------------------------------
# The central claim, same as warrant.py's and dispatch_token.py's: this process
# cannot mint a signature. D-16, D-17.
# ---------------------------------------------------------------------------------

class TheModuleCannotSign(GateCase):

    def test_no_code_path_in_revoke_py_signs_anything(self):
        src = pathlib.Path(BIN_DIR / "revoke.py").read_text(encoding="utf-8")
        self.assertNotIn('"-Y", "sign"', src,
                         "revoke.py invokes ssh-keygen -Y sign; it must not be able to")
        self.assertIn('"-Y", "verify"', src, "revoke.py must still verify")

    def test_revoke_module_never_invokes_ssh_keygen_sign(self):
        for name in dir(rv):
            fn = getattr(rv, name)
            if not callable(fn) or not getattr(fn, "__module__", "") == "revoke":
                continue
            try:
                src = inspect.getsource(fn)
            except (OSError, TypeError):
                continue
            self.assertNotIn('"-Y", "sign"', src,
                             f"revoke.{name} signs; it must not be able to")

    def test_a_drafted_revocation_is_unsigned_and_does_not_apply(self):
        self.enroll()
        d = rv.draft(self.root, "worker-a")
        self.assertFalse(pathlib.Path(d["path"] + ".sig").exists())
        with self.assertRaises(rv.TrustError) as cm:
            rv.apply(self.root, d["revocation_id"])
        self.assertIn("unsigned", str(cm.exception))
        # Unsigned revocation authorizes nothing: it must not show up as revoked.
        self.assertIsNone(rv.is_revoked(self.root, "worker-a"))

    def test_draft_prints_the_sign_command_targeting_the_operator_root(self):
        self.enroll()
        d = rv.draft(self.root, "worker-a", "stolen key")
        self.assertIn("ssh-keygen -Y sign", d["sign_with"])
        self.assertIn("harness_root", d["sign_with"])
        self.assertIn(rv.NAMESPACE, d["sign_with"])

    def test_any_agent_may_draft_but_drafting_alone_revokes_nothing(self):
        """Drafting is the verb "any agent may run" (ruling 2026-10-21): it commits
        nothing. Only a verified, operator-signed revocation is in force."""
        self.enroll()
        rv.draft(self.root, "worker-a", "no operator involved yet")
        self.assertIsNone(rv.is_revoked(self.root, "worker-a"))


# ---------------------------------------------------------------------------------
# Distinct namespace from warrant.py, dispatch_token.py and attest.py -- no
# cross-surface replay of a signature minted for one into proof for another.
# ---------------------------------------------------------------------------------

class NamespaceIsolation(GateCase):

    def test_namespace_is_distinct_from_warrant_dispatch_token_and_attest(self):
        import attest
        self.assertNotEqual(rv.NAMESPACE, w.NAMESPACE)
        self.assertNotEqual(rv.NAMESPACE, dt.NAMESPACE)
        self.assertNotEqual(rv.NAMESPACE, attest.NAMESPACE)

    def test_a_revocation_signed_in_the_warrant_namespace_does_not_verify(self):
        self.enroll()
        d = rv.draft(self.root, "worker-a")
        root_sign(pathlib.Path(d["path"]), self.root_key, w.NAMESPACE)
        with self.assertRaises(rv.TrustError):
            rv.verify_revocation(self.root, d["revocation_id"])

    def test_a_revocation_signed_in_the_dispatch_token_namespace_does_not_verify(self):
        self.enroll()
        d = rv.draft(self.root, "worker-a")
        root_sign(pathlib.Path(d["path"]), self.root_key, dt.NAMESPACE)
        with self.assertRaises(rv.TrustError):
            rv.verify_revocation(self.root, d["revocation_id"])


# ---------------------------------------------------------------------------------
# apply/verify accept a revocation ONLY against the enrolled root, never against a
# key the revocation file names about itself.
# ---------------------------------------------------------------------------------

class OnlyTheEnrolledRootAuthorizes(GateCase):

    def test_a_revocation_signed_by_a_foreign_key_is_refused(self):
        self.enroll()
        rid = rv.draft(self.root, "worker-a")["revocation_id"]
        evil = self.keys / "evil"
        keygen(evil, "mallory")
        root_sign(rv.revocations_dir(self.root) / f"{rid}.json", evil, rv.NAMESPACE)
        with self.assertRaises(rv.TrustError) as cm:
            rv.apply(self.root, rid)
        self.assertIn("SIGNATURE DOES NOT VERIFY", str(cm.exception))
        self.assertIsNone(rv.is_revoked(self.root, "worker-a"))

    def test_apply_accepts_a_genuinely_root_signed_revocation(self):
        self.enroll()
        rid = self.draft_and_sign("worker-a", "stolen key")
        out = rv.apply(self.root, rid)
        self.assertTrue(out["applied"])
        self.assertEqual(out["name"], "worker-a")
        self.assertIsNotNone(rv.is_revoked(self.root, "worker-a"))

    def test_a_revocation_that_names_its_own_signer_as_trusted_is_still_refused(self):
        """D-17: never trust a key the revocation file itself names. Sign with a
        non-root key, have the payload claim that exact key as trusted, and assert
        verification still fails -- the signer source is always the enrolled
        trust/root.pub, independent of anything the payload says about itself."""
        self.enroll()
        d = rv.draft(self.root, "worker-a")
        path = pathlib.Path(d["path"])
        evil = self.keys / "evil"
        evil_pub = keygen(evil, "mallory")
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["trusted_signer_pubkey"] = evil_pub.read_text(encoding="utf-8").strip()
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        root_sign(path, evil, rv.NAMESPACE)
        with self.assertRaises(rv.TrustError):
            rv.apply(self.root, d["revocation_id"])


# ---------------------------------------------------------------------------------
# The falsifier the acceptance criteria name directly.
# ---------------------------------------------------------------------------------

class TheFalsifier(GateCase):

    def test_revoking_the_name_refuses_a_valid_unexpired_token(self):
        self.enroll()
        payload = self.full_token_set(dispatches=["worker-a:T-432:worker"],
                                      ttl_seconds=3600)
        presented = self.present(payload, 0)

        # Before revocation, the token verifies cleanly.
        out = dt.verify(self.root, presented)
        self.assertEqual(out["agent_name"], "worker-a")
        self.assertFalse(out["expired"])

        # Revoke the name by operator order.
        rid = self.draft_and_sign("worker-a", "stolen key")
        rv.apply(self.root, rid)

        # The SAME valid, unexpired token is now refused.
        with self.assertRaises(dt.TrustError) as cm:
            dt.verify(self.root, presented)
        self.assertIn("REVOKED", str(cm.exception))

    def test_revocation_refuses_an_expired_token_too(self):
        """'expired or not' -- the ruling's own words. A revoked name's EXPIRED token
        must report revoked, not merely expired, confirming the check applies either
        way rather than only catching the not-yet-expired case."""
        self.enroll()
        payload = self.full_token_set(dispatches=["worker-a:T-432:worker:1"])
        presented = self.present(payload, 0)
        time.sleep(2)
        rid = self.draft_and_sign("worker-a")
        rv.apply(self.root, rid)
        with self.assertRaises(dt.TrustError) as cm:
            dt.verify(self.root, presented)
        self.assertIn("REVOKED", str(cm.exception))

    def test_a_revocation_signed_by_any_other_key_is_refused(self):
        """Second half of the falsifier: 'A revocation signed by any other key is
        refused.'"""
        self.enroll()
        payload = self.full_token_set(dispatches=["worker-a:T-432:worker"])
        presented = self.present(payload, 0)
        d = rv.draft(self.root, "worker-a")
        evil = self.keys / "evil"
        keygen(evil, "mallory")
        root_sign(pathlib.Path(d["path"]), evil, rv.NAMESPACE)
        with self.assertRaises(rv.TrustError):
            rv.apply(self.root, d["revocation_id"])
        # The token verifies exactly as before: a revocation signed by the wrong key
        # is not in force.
        out = dt.verify(self.root, presented)
        self.assertEqual(out["agent_name"], "worker-a")

    def test_revoking_one_name_does_not_refuse_another(self):
        self.enroll()
        payload = self.full_token_set(
            dispatches=["worker-a:T-432:worker", "worker-b:T-433:verifier"])
        presented_a = self.present(payload, 0)
        presented_b = self.present(payload, 1)
        rid = self.draft_and_sign("worker-a")
        rv.apply(self.root, rid)
        with self.assertRaises(dt.TrustError):
            dt.verify(self.root, presented_a)
        out_b = dt.verify(self.root, presented_b)
        self.assertEqual(out_b["agent_name"], "worker-b")


# ---------------------------------------------------------------------------------
# No consequence attaches beyond refusing the token (PR-022 clause 4). roster.py
# reports, it does not gate.
# ---------------------------------------------------------------------------------

class NoConsequenceBeyondTheToken(GateCase):

    def test_roster_reports_the_name_as_revoked(self):
        self.enroll()
        priv, pub = (self.keys / "worker-a", None)
        pub = keygen(priv, "worker-a")
        warrant_id = w.draft(self.root, "e-1", ["banco=paga por prestamos cobrados"],
                             ["banco/worker=1"],
                             [f"worker-a:banco/worker:{pub}"])
        root_sign(pathlib.Path(warrant_id["path"]), self.root_key, w.NAMESPACE)
        w.apply_warrant(self.root, warrant_id["warrant_id"])

        rid = self.draft_and_sign("worker-a", "stolen key")
        rv.apply(self.root, rid)

        report = roster.revoked_report(self.root)
        self.assertIn("worker-a", report)
        self.assertEqual(report["worker-a"]["revocation_id"], rid)

    def test_roster_report_is_empty_with_no_revocations(self):
        self.enroll()
        self.assertEqual(roster.revoked_report(self.root), {})

    def test_revocation_carries_no_consequence_marker(self):
        """The payload itself states PR-022 clause 4 is not being varied."""
        self.enroll()
        d = rv.draft(self.root, "worker-a")
        payload = json.loads(pathlib.Path(d["path"]).read_text(encoding="utf-8"))
        self.assertIn("NOT_A_CONSEQUENCE", payload)

    def test_no_exported_callable_takes_a_threshold_gate_weight_burden_or_permission(self):
        """Same discipline test_roster.py already pins for roster.py itself."""
        import re
        for name in rv.PUBLIC_API:
            fn = getattr(rv, name)
            if not callable(fn):
                continue
            sig = inspect.signature(fn)
            for pname in sig.parameters:
                self.assertNotRegex(
                    pname, re.compile(r"threshold|gate|weight|burden|permission", re.I),
                    f"revoke.{name} takes {pname!r}; PR-022 clause 4 forbids it")


if __name__ == "__main__":
    unittest.main()
