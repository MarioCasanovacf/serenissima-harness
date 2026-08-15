"""Adversarial tests for warrant.py and attest.py: the identity gate PR-023 asks for.

Every class below is named for a claim the modules make. The design rule this suite
enforces is the one the refused PR-023 appeal violated: a module may only claim what a
test can demonstrate, and where a guarantee is unavailable the test proves the LIMIT
rather than pretending it away.

The suite generates its own throwaway root key in a temp dir. It never reads, requests
or creates a key under the operator's real ~/.ssh, and never touches live .harness state.
"""
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
LIVE_HARNESS = ROOT / ".harness"

sys.path.insert(0, str(BIN_DIR))
import warrant as w  # noqa: E402
import attest  # noqa: E402
import roster  # noqa: E402


def keygen(path, comment="test"):
    subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", comment,
                    "-f", str(path), "-q"], check=True, capture_output=True)
    return pathlib.Path(str(path) + ".pub")


def root_sign(payload_path, key_path, namespace=w.NAMESPACE):
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

    def agent_key(self, name):
        k = self.keys / name
        keygen(k, name)
        return k, pathlib.Path(str(k) + ".pub")

    def full_warrant(self, epic="e-1", count=2, valid_until=None):
        """Enroll, draft, sign, apply. Returns (warrant_id, {name: privkey})."""
        self.enroll()
        keys = {}
        specs = []
        for name in ("aurelia", "orso")[:count]:
            priv, pub = self.agent_key(name)
            keys[name] = priv
            specs.append(f"{name}:banco/judge:{pub}")
        d = w.draft(self.root, epic, ["banco=paga por prestamos cobrados"],
                    [f"banco/judge={count}"], specs, valid_until)
        root_sign(pathlib.Path(d["path"]), self.root_key)
        w.apply_warrant(self.root, d["warrant_id"])
        return d["warrant_id"], keys


# ---------------------------------------------------------------------------------
# The central claim: this process cannot mint. D-16, D-17.
# ---------------------------------------------------------------------------------

class TheHarnessCannotSign(GateCase):

    def test_no_code_path_in_warrant_py_signs_anything(self):
        """The separation IS the mechanism. A process that could produce both the
        document and its signature would be a trust root, and D-17 forbids one here."""
        src = pathlib.Path(BIN_DIR / "warrant.py").read_text(encoding="utf-8")
        self.assertNotIn('"-Y", "sign"', src,
                         "warrant.py invokes ssh-keygen -Y sign; it must not be able to")
        self.assertIn('"-Y", "verify"', src, "warrant.py must still verify")

    def test_warrant_module_never_invokes_ssh_keygen_sign(self):
        for name in dir(w):
            fn = getattr(w, name)
            if not callable(fn) or not getattr(fn, "__module__", "") == "warrant":
                continue
            try:
                src = inspect.getsource(fn)
            except (OSError, TypeError):
                continue
            self.assertNotIn('"-Y", "sign"', src,
                             f"warrant.{name} signs; it must not be able to")

    def test_init_refuses_a_private_key(self):
        with self.assertRaises(w.TrustError) as cm:
            w.init(self.root, self.root_key)
        self.assertIn("PRIVATE", str(cm.exception))

    def test_a_drafted_warrant_is_unsigned_and_does_not_apply(self):
        self.enroll()
        priv, pub = self.agent_key("aurelia")
        d = w.draft(self.root, "e-1", ["banco=x"], ["banco/judge=1"],
                    [f"aurelia:banco/judge:{pub}"])
        self.assertFalse(pathlib.Path(d["path"] + ".sig").exists())
        with self.assertRaises(w.TrustError) as cm:
            w.apply_warrant(self.root, d["warrant_id"])
        self.assertIn("unsigned", str(cm.exception))
        self.assertEqual(roster.load(self.root)["names"], {})


# ---------------------------------------------------------------------------------
# The hole the probe found: allowed_signers self-enrollment. This is its closure.
# ---------------------------------------------------------------------------------

class TheTrustAnchor(GateCase):

    def test_swapping_root_pub_breaks_the_anchor(self):
        """A probe of ssh-keygen showed an attacker who appends to an allowed_signers
        file enrolls itself and verifies cleanly. So no allowed_signers file is stored,
        and the signing key must be THE anchored key."""
        wid, _ = self.full_warrant()
        evil = self.keys / "evil"
        evil_pub = keygen(evil, "mallory")
        (w.trust_dir(self.root) / "root.pub").write_text(
            evil_pub.read_text(encoding="utf-8"), encoding="utf-8")
        with self.assertRaises(w.TrustError) as cm:
            w.verify_warrant(self.root, wid)
        self.assertIn("TRUST ROOT TAMPERED", str(cm.exception))

    def test_a_warrant_signed_by_a_foreign_key_does_not_verify(self):
        self.enroll()
        evil = self.keys / "evil"
        keygen(evil, "mallory")
        priv, pub = self.agent_key("aurelia")
        d = w.draft(self.root, "e-1", ["banco=x"], ["banco/judge=1"],
                    [f"aurelia:banco/judge:{pub}"])
        root_sign(pathlib.Path(d["path"]), evil)
        with self.assertRaises(w.TrustError):
            w.verify_warrant(self.root, d["warrant_id"])

    def test_tampering_with_a_signed_payload_invalidates_it(self):
        wid, _ = self.full_warrant()
        path = w.warrants_dir(self.root) / f"{wid}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["plazas"]["banco/judge"] = 500
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(w.TrustError) as cm:
            w.verify_warrant(self.root, wid)
        self.assertIn("SIGNATURE DOES NOT VERIFY", str(cm.exception))

    def test_the_anchor_is_one_human_verifiable_string(self):
        out = self.enroll()
        self.assertRegex(out["fingerprint"], r"^SHA256:[A-Za-z0-9+/=]{43}$")
        self.assertIn("out of band", out["verify_out_of_band"].lower())

    def test_a_warrant_signature_cannot_be_replayed_as_an_act(self):
        """Namespaces must not be interchangeable, or the root's signature could be
        replayed into an agent's chain."""
        self.assertNotEqual(w.NAMESPACE, attest.NAMESPACE)
        wid, _ = self.full_warrant()
        path = w.warrants_dir(self.root) / f"{wid}.json"
        with self.assertRaises(w.TrustError):
            with tempfile.TemporaryDirectory() as tmp:
                allowed = pathlib.Path(tmp) / "a"
                allowed.write_text(
                    f"operator {(w.trust_dir(self.root)/'root.pub').read_text().strip()}\n")
                with path.open("rb") as fh:
                    r = subprocess.run(
                        ["ssh-keygen", "-Y", "verify", "-f", str(allowed),
                         "-I", "operator", "-n", attest.NAMESPACE,
                         "-s", str(path) + ".sig"],
                        stdin=fh, text=True, capture_output=True)
                if r.returncode != 0:
                    raise w.TrustError("namespace mismatch rejected, as required")


# ---------------------------------------------------------------------------------
# Minting is closed. This is the whole PR-023 clause 3 claim.
# ---------------------------------------------------------------------------------

class MintingIsClosed(GateCase):

    def test_before_enrollment_the_roll_is_bookkeeping_as_before(self):
        roster.charter("banco", "x", "anyone", self.root)
        self.assertIn("banco", roster.load(self.root)["colegiados"])

    def test_after_enrollment_an_unwarranted_charter_is_refused(self):
        self.enroll()
        with self.assertRaises(KeyError) as cm:
            roster.charter("banco", "x", "mallory", self.root)
        self.assertIn("verified warrant", str(cm.exception))

    def test_after_enrollment_an_unwarranted_plaza_is_refused(self):
        self.full_warrant()
        with self.assertRaises(KeyError):
            roster.plazas("e-1", "banco", "notary", 500, "mallory", self.root)

    def test_after_enrollment_an_unwarranted_issue_is_refused(self):
        self.full_warrant()
        with self.assertRaises(KeyError):
            roster.issue("phantom", "banco", "judge", "e-1", "mallory", "", self.root)
        self.assertNotIn("phantom", roster.load(self.root)["names"])

    def test_a_signed_warrant_puts_names_on_the_roll(self):
        wid, keys = self.full_warrant()
        rolled = roster.load(self.root)
        self.assertEqual(sorted(rolled["names"]), ["aurelia", "orso"])
        for entry in rolled["names"].values():
            self.assertEqual(entry["issued_by"], f"warrant:{wid}")

    def test_a_warrant_cannot_over_fill_its_own_plaza(self):
        """warrant.py adds authority on top of roster.py's guards, never replacing
        them, so a signed document still cannot break the roll's invariants."""
        self.enroll()
        specs, pubs = [], []
        for name in ("a", "b", "c"):
            _, pub = self.agent_key(name)
            pubs.append(pub)
            specs.append(f"{name}:banco/judge:{pub}")
        with self.assertRaises(ValueError) as cm:
            w.draft(self.root, "e-1", ["banco=x"], ["banco/judge=2"], specs)
        self.assertIn("3 names claim", str(cm.exception))

    def test_a_warrant_cannot_name_an_unchartered_colegiado(self):
        self.enroll()
        _, pub = self.agent_key("a")
        with self.assertRaises(ValueError):
            w.draft(self.root, "e-1", [], ["banco/judge=1"], [f"a:banco/judge:{pub}"])

    def test_plaza_counts_stay_bounded_inside_a_warrant(self):
        self.enroll()
        with self.assertRaises(ValueError):
            w.draft(self.root, "e-1", ["banco=x"], ["banco/judge=999"], [])

    def test_an_expired_warrant_does_not_apply(self):
        self.enroll()
        _, pub = self.agent_key("aurelia")
        d = w.draft(self.root, "e-1", ["banco=x"], ["banco/judge=1"],
                    [f"aurelia:banco/judge:{pub}"], valid_until="2020-01-01T00:00:00Z")
        root_sign(pathlib.Path(d["path"]), self.root_key)
        with self.assertRaises(w.TrustError) as cm:
            w.apply_warrant(self.root, d["warrant_id"])
        self.assertIn("expired", str(cm.exception))


# ---------------------------------------------------------------------------------
# DIS-1: fork detection. The detector the refused appeal's G2 promised.
# ---------------------------------------------------------------------------------

class ForkDetection(GateCase):

    def forge(self, name, key, prev, seq, kind="forged"):
        """What a forger actually does: sign a second act onto the same predecessor."""
        d = attest.acts_dir(self.root, name)
        path = d / f"{seq:03d}.json"
        path.write_text(json.dumps({
            "schema_version": 1, "name": name, "seq": seq, "kind": kind,
            "ref": "", "body": {}, "prev": prev, "ts": "2026-08-15T12:00:00Z",
            "namespace": attest.NAMESPACE}, indent=2) + "\n", encoding="utf-8")
        root_sign(path, key, attest.NAMESPACE)
        return path

    def test_a_clean_chain_verifies_with_no_forks(self):
        wid, keys = self.full_warrant()
        attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit", "abc")
        attest.sign_act(self.root, "aurelia", keys["aurelia"], "filing", "def")
        rep = attest.verify_name(self.root, "aurelia")
        self.assertEqual(rep["acts"], 2)
        self.assertEqual(rep["signature_failures"], [])
        self.assertEqual(rep["forks"], [])
        self.assertFalse(rep["contested"])

    def test_two_acts_on_one_predecessor_are_reported_as_a_fork(self):
        wid, keys = self.full_warrant()
        first = attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit", "abc")
        self.forge("aurelia", keys["aurelia"], first["prev"], 99)

        rep = attest.verify_name(self.root, "aurelia")
        self.assertTrue(rep["contested"])
        self.assertEqual(len(rep["forks"]), 1)
        fork = rep["forks"][0]
        self.assertEqual(fork["prev"], first["prev"])
        self.assertEqual(len(fork["branches"]), 2)
        self.assertEqual(fork["STATUS"], "CONTESTED")

    def test_the_fork_is_proof_not_an_opinion(self):
        wid, keys = self.full_warrant()
        first = attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit")
        self.forge("aurelia", keys["aurelia"], first["prev"], 99)
        fork = attest.forks(self.root)[0]
        self.assertIn("two acts share one predecessor", fork["PROOF"])
        self.assertIn("mechanical", fork["PROOF"])

    def test_a_fork_freezes_nothing(self):
        """DIS-3 and AF-5: a saboteur must not be able to halt a rival, and no mechanism
        may wait on an operator who may be asleep."""
        wid, keys = self.full_warrant()
        first = attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit")
        self.forge("aurelia", keys["aurelia"], first["prev"], 99)
        after = attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit")
        self.assertIsNotNone(after["digest"])
        self.assertTrue(attest.verify_name(self.root, "aurelia")["contested"])
        other = attest.sign_act(self.root, "orso", keys["orso"], "commit")
        self.assertIsNotNone(other["digest"])
        self.assertFalse(attest.verify_name(self.root, "orso")["contested"])

    def test_an_act_signed_by_the_wrong_key_fails_signature_verification(self):
        wid, keys = self.full_warrant()
        attest.sign_act(self.root, "aurelia", keys["orso"], "commit")
        rep = attest.verify_name(self.root, "aurelia")
        self.assertEqual(len(rep["signature_failures"]), 1)

    def test_an_unissued_name_cannot_sign_at_all(self):
        self.full_warrant()
        ghost, _ = self.agent_key("ghost")
        with self.assertRaises(attest.AttestError) as cm:
            attest.sign_act(self.root, "ghost", ghost, "commit")
        self.assertIn("only inside a root-signed warrant", str(cm.exception))


# ---------------------------------------------------------------------------------
# DIS-2 and DIS-5: motive and accusation.
# ---------------------------------------------------------------------------------

class Disincentives(GateCase):

    def test_every_act_states_that_credit_follows_the_signature(self):
        wid, keys = self.full_warrant()
        act = attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit")
        body = json.loads(pathlib.Path(act["path"]).read_text(encoding="utf-8"))
        self.assertIn("CREDIT_FOLLOWS_THE_SIGNATURE", body)
        self.assertIn("accrues to the signing name", body["CREDIT_FOLLOWS_THE_SIGNATURE"])

    def test_a_contest_is_an_act_on_the_accusers_own_chain(self):
        wid, keys = self.full_warrant()
        attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit")
        filed = attest.contest(self.root, "orso", keys["orso"], "aurelia", 0,
                               "esa firma no es mia")
        self.assertEqual(filed["name"], "orso")
        chain = attest.chain(self.root, "orso")
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0]["kind"], "contest")
        self.assertEqual(chain[0]["ref"], "aurelia#0")
        self.assertIn("AF_3", chain[0]["body"])

    def test_a_name_cannot_contest_its_own_act(self):
        wid, keys = self.full_warrant()
        attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit")
        with self.assertRaises(attest.AttestError):
            attest.contest(self.root, "aurelia", keys["aurelia"], "aurelia", 0, "x")

    def test_a_contest_by_an_unissued_name_is_refused(self):
        wid, keys = self.full_warrant()
        ghost, _ = self.agent_key("ghost")
        with self.assertRaises(attest.AttestError):
            attest.contest(self.root, "ghost", ghost, "aurelia", 0, "x")


# ---------------------------------------------------------------------------------
# The limits, asserted so no future edit can quietly drop them.
# ---------------------------------------------------------------------------------

class StatedLimits(GateCase):

    def test_attest_states_it_cannot_prevent_impersonation(self):
        self.assertIn("WHAT THIS CANNOT DO, SAID FIRST", attest.__doc__)
        self.assertIn("cannot stop it", attest.__doc__)

    def test_verify_all_prints_the_self_asserted_caveat(self):
        self.full_warrant()
        out = attest.verify_all(self.root)
        self.assertIn("identities are self-asserted", out["CAVEAT"])
        self.assertIn("What IS closed is minting", out["CAVEAT"])

    def test_a_stolen_agent_key_forges_successfully(self):
        """The limit, proven rather than asserted. Any agent can read any key on this
        shared filesystem (D-17), and a forged act verifies. What it cannot do is
        avoid leaving a fork."""
        wid, keys = self.full_warrant()
        first = attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit")
        stolen = keys["aurelia"]          # orso simply reads it
        forged = attest.acts_dir(self.root, "aurelia") / "099.json"
        forged.write_text(json.dumps({
            "schema_version": 1, "name": "aurelia", "seq": 99, "kind": "forged",
            "ref": "", "body": {}, "prev": first["prev"],
            "ts": "2026-08-15T12:00:00Z", "namespace": attest.NAMESPACE},
            indent=2) + "\n", encoding="utf-8")
        root_sign(forged, stolen, attest.NAMESPACE)

        rep = attest.verify_name(self.root, "aurelia")
        self.assertEqual(rep["signature_failures"], [],
                         "the forged signature verifies: that is the limit")
        self.assertTrue(rep["contested"],
                        "but the fork is unavoidable: that is the disincentive")

    def test_no_module_attaches_a_consequence(self):
        """PR-022 clause 4: NO CONSEQUENCE ATTACHES. NONE."""
        forbidden = ("threshold", "weight", "burden", "permission", "discount",
                     "quorum", "penalt")
        for mod in (w, attest):
            for name in mod.PUBLIC_API:
                fn = getattr(mod, name)
                if not callable(fn):
                    continue
                for param in inspect.signature(fn).parameters:
                    for bad in forbidden:
                        self.assertNotIn(bad, param.lower(),
                                         f"{mod.__name__}.{name}({param})")


class LiveStoreIsolation(GateCase):

    def test_nothing_in_this_suite_enrolls_a_root_in_the_live_harness(self):
        self.full_warrant()
        self.assertFalse((LIVE_HARNESS / "trust").exists(),
                         "the live harness must stay un-enrolled until the operator "
                         "runs init with their own key")

    def test_audit_reports_un_enrolled_cleanly(self):
        out = w.audit(self.base / "empty")
        self.assertFalse(out["enrolled"])
        self.assertIn("PR-023's gate remains closed", out["note"])

    def test_audit_verifies_every_warrant(self):
        wid, _ = self.full_warrant()
        out = w.audit(self.root)
        self.assertTrue(out["enrolled"])
        self.assertEqual(out["ok"], 1)
        self.assertEqual(out["invalid"], [])
        self.assertEqual(out["warrants"][0]["id"], wid)


class NoPrivateKeyIsEverTracked(unittest.TestCase):
    """The whole design rests on the operator holding a key this repository does not.

    A .gitignore pattern is a hope; this is a check. It scans every file git tracks for
    an OpenSSH private key header, so a key committed by accident fails the suite
    instead of reaching a public remote.
    """

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

    def test_the_live_trust_dir_holds_no_private_key(self):
        td = LIVE_HARNESS / "trust"
        if not td.exists():
            self.skipTest("harness un-enrolled; nothing to check yet")
        for path in td.rglob("*"):
            if path.is_file():
                self.assertNotIn("PRIVATE KEY-----",
                                 path.read_text(encoding="utf-8", errors="replace"),
                                 f"{path} holds a private key")


if __name__ == "__main__":
    unittest.main(verbosity=2)
