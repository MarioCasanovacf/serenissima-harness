"""Falsifier tests for dispatch_token.py: T-432 option 5, ratified 2026-10-21.

Mirrors test_warrant.py's shape on purpose: its own throwaway root key, generated in a
temp dir, never touching the live .harness/trust store, the operator's real
~/.ssh/harness_root, or any other live private material.
"""
import inspect
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".harness" / "bin"
LIVE_HARNESS = ROOT / ".harness"

sys.path.insert(0, str(BIN_DIR))
import dispatch_token as dt  # noqa: E402
import warrant as w  # noqa: E402


def keygen(path, comment="test"):
    subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", comment,
                    "-f", str(path), "-q"], check=True, capture_output=True)
    return pathlib.Path(str(path) + ".pub")


def root_sign(payload_path, key_path, namespace=dt.NAMESPACE):
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

    def full_set(self, epic="e-1", dispatches=None, ttl_seconds=3600):
        """Enroll, draft, sign, return (token_set_id, payload)."""
        self.enroll()
        if dispatches is None:
            dispatches = ["worker-a:T-432:worker", "worker-b:T-433:verifier"]
        d = dt.draft(self.root, epic, dispatches, ttl_seconds)
        root_sign(pathlib.Path(d["path"]), self.root_key)
        payload = json.loads(pathlib.Path(d["path"]).read_text(encoding="utf-8"))
        return d["token_set_id"], payload

    def present(self, payload, index=0, **overrides):
        """Build the dict a holder would present: the canonical token's own fields plus
        the token_set_id, with any deliberate overrides layered on top (for tamper
        tests)."""
        canonical = payload["tokens"][index]
        out = {"token_set_id": payload["token_set_id"], **canonical}
        out.update(overrides)
        return out


# ---------------------------------------------------------------------------------
# The central claim, same as warrant.py's: this process cannot mint. D-16, D-17.
# ---------------------------------------------------------------------------------

class TheModuleCannotSign(GateCase):

    def test_no_code_path_in_dispatch_token_py_signs_anything(self):
        src = pathlib.Path(BIN_DIR / "dispatch_token.py").read_text(encoding="utf-8")
        self.assertNotIn('"-Y", "sign"', src,
                         "dispatch_token.py invokes ssh-keygen -Y sign; it must not be "
                         "able to")
        self.assertIn('"-Y", "verify"', src, "dispatch_token.py must still verify")

    def test_dispatch_token_module_never_invokes_ssh_keygen_sign(self):
        for name in dir(dt):
            fn = getattr(dt, name)
            if not callable(fn) or not getattr(fn, "__module__", "") == "dispatch_token":
                continue
            try:
                src = inspect.getsource(fn)
            except (OSError, TypeError):
                continue
            self.assertNotIn('"-Y", "sign"', src,
                             f"dispatch_token.{name} signs; it must not be able to")

    def test_a_drafted_set_is_unsigned_and_does_not_verify(self):
        self.enroll()
        d = dt.draft(self.root, "e-1", ["worker-a:T-432:worker"])
        self.assertFalse(pathlib.Path(d["path"] + ".sig").exists())
        with self.assertRaises(dt.TrustError) as cm:
            dt.verify_token_set(self.root, d["token_set_id"])
        self.assertIn("unsigned", str(cm.exception))

    def test_draft_prints_the_sign_command_targeting_the_operator_root(self):
        self.enroll()
        d = dt.draft(self.root, "e-1", ["worker-a:T-432:worker"])
        self.assertIn("ssh-keygen -Y sign", d["sign_with"])
        self.assertIn("harness_root", d["sign_with"])
        self.assertIn(dt.NAMESPACE, d["sign_with"])


# ---------------------------------------------------------------------------------
# Distinct namespace from both warrant.py and attest.py -- no cross-surface replay.
# ---------------------------------------------------------------------------------

class NamespaceIsolation(GateCase):

    def test_namespace_is_distinct_from_warrant_and_attest(self):
        import attest
        self.assertNotEqual(dt.NAMESPACE, w.NAMESPACE)
        self.assertNotEqual(dt.NAMESPACE, attest.NAMESPACE)

    def test_a_token_set_signed_in_the_warrant_namespace_does_not_verify(self):
        """A signature minted for warrant.py must not authorize a dispatch token set,
        even though both are signed by the same operator root."""
        self.enroll()
        d = dt.draft(self.root, "e-1", ["worker-a:T-432:worker"])
        root_sign(pathlib.Path(d["path"]), self.root_key, namespace=w.NAMESPACE)
        with self.assertRaises(dt.TrustError):
            dt.verify_token_set(self.root, d["token_set_id"])


# ---------------------------------------------------------------------------------
# The five falsifiers the acceptance criteria name, one class, one test each.
# ---------------------------------------------------------------------------------

class Falsifiers(GateCase):

    def test_a_valid_token_is_accepted(self):
        dtid, payload = self.full_set()
        presented = self.present(payload, 0)
        out = dt.verify(self.root, presented, claim_agent="worker-a",
                        claim_task="T-432", claim_role="worker")
        self.assertEqual(out["agent_name"], "worker-a")
        self.assertEqual(out["task_id"], "T-432")
        self.assertEqual(out["role"], "worker")
        self.assertFalse(out["expired"])

    def test_a_tampered_agent_name_is_refused(self):
        dtid, payload = self.full_set()
        presented = self.present(payload, 0, agent_name="worker-mallory")
        with self.assertRaises(dt.TrustError) as cm:
            dt.verify(self.root, presented)
        self.assertIn("TAMPERED", str(cm.exception))

    def test_an_expired_token_is_refused(self):
        dtid, payload = self.full_set(dispatches=["worker-a:T-432:worker:1"])
        presented = self.present(payload, 0)
        import time
        time.sleep(2)
        with self.assertRaises(dt.TrustError) as cm:
            dt.verify(self.root, presented)
        self.assertIn("expired", str(cm.exception))

    def test_a_token_for_worker_a_presented_as_worker_b_is_refused(self):
        dtid, payload = self.full_set(
            dispatches=["worker-a:T-999:worker", "worker-b:T-433:verifier"])
        presented = self.present(payload, 0)  # the genuine worker-a/T-999/worker token
        with self.assertRaises(dt.TrustError) as cm:
            dt.verify(self.root, presented, claim_agent="worker-b",
                     claim_task="T-999", claim_role="worker")
        self.assertIn("IDENTITY MISMATCH", str(cm.exception))

    def test_right_agent_and_role_but_wrong_task_is_refused(self):
        """T-464: the T-455 verifier found that narrowing verify()'s identity match to
        agent_name ALONE still passes the whole suite -- every existing mismatch test
        here also varies the agent, so an agent-only check would still catch them by
        accident. This test holds agent_name and role fixed at their genuine, correct
        values and varies ONLY task_id, so an agent-only narrowing has nothing left to
        catch it on and must (incorrectly) accept it."""
        dtid, payload = self.full_set(dispatches=["worker-a:T-432:worker"])
        presented = self.present(payload, 0)  # genuine worker-a/T-432/worker token
        with self.assertRaises(dt.TrustError) as cm:
            dt.verify(self.root, presented, claim_agent="worker-a",
                     claim_task="T-999", claim_role="worker")
        self.assertIn("IDENTITY MISMATCH", str(cm.exception))

    def test_right_agent_and_task_but_wrong_role_is_refused(self):
        """T-464: the mirror of the task-only falsifier above -- agent_name and task_id
        are held at their genuine, correct values and ONLY role varies. An agent-only
        narrowing of the identity match has nothing to catch this on either."""
        dtid, payload = self.full_set(dispatches=["worker-a:T-432:worker"])
        presented = self.present(payload, 0)  # genuine worker-a/T-432/worker token
        with self.assertRaises(dt.TrustError) as cm:
            dt.verify(self.root, presented, claim_agent="worker-a",
                     claim_task="T-432", claim_role="verifier")
        self.assertIn("IDENTITY MISMATCH", str(cm.exception))

    def test_a_set_signed_by_a_key_that_is_not_the_enrolled_root_is_refused(self):
        self.enroll()
        d = dt.draft(self.root, "e-1", ["worker-a:T-432:worker"])
        evil = self.keys / "evil"
        keygen(evil, "mallory")
        root_sign(pathlib.Path(d["path"]), evil)
        payload = json.loads(pathlib.Path(d["path"]).read_text(encoding="utf-8"))
        presented = self.present(payload, 0)
        with self.assertRaises(dt.TrustError):
            dt.verify(self.root, presented)

    def test_a_payload_that_names_its_own_signer_as_trusted_is_still_refused(self):
        """Regression for T-447 bullet 3's third mutant ("verify against any key the
        file names"), which the verifier's adversarial replay found had no pin: a
        future edit to `_verify_file_signature` that sourced `allowed_signers` from a
        field INSIDE the payload (e.g. a `trusted_signer_pubkey` the payload names
        about itself) instead of always from `trust/root.pub` would let an attacker
        sign with its own key, embed that same key as "trusted" in the payload, and
        have the module accept it -- silently defeating the module's own stated
        invariant ("the signing key must be THE anchored key, or nothing verifies").

        D-17: never trust a key the token/file itself names. This test signs with a
        non-root key AND has the payload claim that exact key as trusted, then asserts
        verification still fails -- i.e. the signer source is always the enrolled
        trust/root.pub, independent of anything the payload says about itself. The
        shipped module needs no code change for this to pass (it never reads such a
        field); this pins that it must stay that way."""
        self.enroll()
        d = dt.draft(self.root, "e-1", ["worker-a:T-432:worker"])
        evil = self.keys / "evil"
        evil_pub = keygen(evil, "mallory")
        on_disk = json.loads(pathlib.Path(d["path"]).read_text(encoding="utf-8"))
        on_disk["trusted_signer_pubkey"] = evil_pub.read_text(encoding="utf-8").strip()
        on_disk["trusted_signer_fingerprint"] = w.key_fingerprint(evil_pub)
        pathlib.Path(d["path"]).write_text(
            json.dumps(on_disk, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        root_sign(pathlib.Path(d["path"]), evil)  # signed by the attacker's own key
        with self.assertRaises(dt.TrustError) as cm:
            dt.verify_token_set(self.root, d["token_set_id"])
        self.assertNotIn("trusted_signer", str(cm.exception).lower(),
                         "the refusal must come from the anchor mismatch, not from any "
                         "code path that even looked at the payload-embedded field")


# ---------------------------------------------------------------------------------
# Nonces: stated NOT single-use in this module, and pinned rather than assumed.
# ---------------------------------------------------------------------------------

class NoncesAreNotSingleUseHere(GateCase):

    def test_a_valid_token_verifies_twice(self):
        """This module keeps no consumption state (no wiring into claim/lock -- that is
        T-454), so presenting the same genuine, unexpired token a second time succeeds
        again rather than being refused as a replay. Pinned so a future change to this
        is a deliberate decision, not an accidental regression."""
        dtid, payload = self.full_set()
        presented = self.present(payload, 0)
        first = dt.verify(self.root, presented, claim_agent="worker-a",
                          claim_task="T-432", claim_role="worker")
        second = dt.verify(self.root, presented, claim_agent="worker-a",
                           claim_task="T-432", claim_role="worker")
        self.assertEqual(first, second)

    def test_the_module_docstring_states_the_limit(self):
        self.assertIn("NOT SINGLE-USE", dt.__doc__.upper())
        self.assertIn("T-454", dt.__doc__)


# ---------------------------------------------------------------------------------
# Grain: one signature covers the whole epic's set, not one token at a time.
# ---------------------------------------------------------------------------------

class EpicGrain(GateCase):

    def test_one_signature_covers_every_token_for_the_epic(self):
        dtid, payload = self.full_set(
            dispatches=["worker-a:T-432:worker", "worker-b:T-433:verifier",
                       "worker-c:T-434:worker"])
        self.assertEqual(len(payload["tokens"]), 3)
        for i in range(3):
            presented = self.present(payload, i)
            out = dt.verify(self.root, presented)
            self.assertEqual(out["token_set_id"], dtid)

    def test_tampering_one_token_in_the_file_invalidates_the_whole_signed_set(self):
        """The signature covers the file's exact bytes; editing any one token breaks
        verification for every token in the set, not only the edited one."""
        dtid, payload = self.full_set()
        path = dt.token_sets_dir(self.root) / f"{dtid}.json"
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        on_disk["tokens"][0]["role"] = "judge"
        path.write_text(json.dumps(on_disk, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(dt.TrustError) as cm:
            dt.verify_token_set(self.root, dtid)
        self.assertIn("SIGNATURE DOES NOT VERIFY", str(cm.exception))


# ---------------------------------------------------------------------------------
# Wiring: T-454 wires this module into blackboard.py claim and lock.py acquire, as an
# optional, additive check. This supersedes T-446's NoWiring pin, which correctly
# described the state before T-454 existed -- the import graph now proves the opposite.
# ---------------------------------------------------------------------------------

class Wiring(GateCase):

    def test_blackboard_and_lock_import_dispatch_token(self):
        import ast
        for name in ("blackboard.py", "lock.py"):
            src = (BIN_DIR / name).read_text(encoding="utf-8")
            imported = set()
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertIn("dispatch_token", imported,
                         f"{name} must import dispatch_token (T-454 wiring)")


# ---------------------------------------------------------------------------------
# epic_requires_token / required: the field T-454 reads to decide whether an epic's
# claim/lock-acquire calls may proceed without a token at all. Lives INSIDE the epic's
# own signed token-set payload rather than a second, separately-signed record (T-454's
# design choice, recorded in blackboard.py's and lock.py's own gate docstrings).
# ---------------------------------------------------------------------------------

class EpicRequirement(GateCase):

    def test_no_token_sets_at_all_does_not_require_a_token(self):
        self.enroll()
        self.assertFalse(dt.epic_requires_token(self.root, "e-1"))

    def test_an_unsigned_required_draft_does_not_require_a_token(self):
        self.enroll()
        dt.draft(self.root, "e-1", ["worker-a:T-432:worker"], required=True)
        self.assertFalse(dt.epic_requires_token(self.root, "e-1"),
                         "an unsigned draft must never make an epic require a token")

    def test_required_defaults_to_false(self):
        dtid, payload = self.full_set(epic="e-1")
        self.assertFalse(payload.get("required"))
        self.assertFalse(dt.epic_requires_token(self.root, "e-1"))

    def test_a_signed_required_set_makes_its_own_epic_require_a_token(self):
        self.enroll()
        d = dt.draft(self.root, "e-1", ["worker-a:T-432:worker"], required=True)
        root_sign(pathlib.Path(d["path"]), self.root_key)
        self.assertTrue(dt.epic_requires_token(self.root, "e-1"))

    def test_a_signed_required_set_does_not_affect_a_different_epic(self):
        self.enroll()
        d = dt.draft(self.root, "e-1", ["worker-a:T-432:worker"], required=True)
        root_sign(pathlib.Path(d["path"]), self.root_key)
        self.assertFalse(dt.epic_requires_token(self.root, "e-2"))

    def test_a_required_set_signed_by_the_wrong_key_does_not_count(self):
        self.enroll()
        d = dt.draft(self.root, "e-1", ["worker-a:T-432:worker"], required=True)
        evil = self.keys / "evil-required"
        keygen(evil, "mallory")
        root_sign(pathlib.Path(d["path"]), evil)
        self.assertFalse(dt.epic_requires_token(self.root, "e-1"))


class LiveStoreIsolation(GateCase):

    def test_nothing_in_this_suite_touches_the_live_trust_store(self):
        def snapshot():
            trust = LIVE_HARNESS / "trust"
            if not trust.exists():
                return None
            return {p.name: p.read_bytes() for p in sorted(trust.iterdir()) if p.is_file()}

        before = snapshot()
        self.full_set()
        self.assertEqual(snapshot(), before,
                         "this suite must never create, modify or delete anything in "
                         "the live trust store; it generates its own root in a temp dir")

    def test_nothing_in_this_suite_touches_the_live_dispatch_tokens_dir(self):
        live_dt = LIVE_HARNESS / "dispatch_tokens"
        before = live_dt.exists()
        self.full_set()
        self.assertEqual(live_dt.exists(), before,
                         "this suite must never create .harness/dispatch_tokens/ in "
                         "the live tree")


class NoPrivateKeyIsEverTracked(unittest.TestCase):
    """Same discipline as test_warrant.py's class of the same name: scans everything
    git tracks for an OpenSSH private key header."""

    def test_no_tracked_file_contains_a_private_key(self):
        listing = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                                 capture_output=True, text=True)
        self.assertEqual(listing.returncode, 0, listing.stderr)
        offenders = []
        for rel in listing.stdout.split("\0"):
            if not rel:
                continue
            path = ROOT / rel
            if not path.is_file():
                continue
            try:
                head = path.read_bytes()[:4096]
            except OSError:
                continue
            if b"PRIVATE KEY-----" in head:
                offenders.append(rel)
        self.assertEqual(offenders, [], f"private key material is tracked: {offenders}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
