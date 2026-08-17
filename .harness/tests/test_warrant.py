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

    def test_a_verified_fork_is_divergence_not_proof_of_two_parties(self):
        wid, keys = self.full_warrant()
        first = attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit")
        self.forge("aurelia", keys["aurelia"], first["prev"], 99)
        fork = attest.forks(self.root)[0]
        self.assertTrue(fork["all_branches_verified"])
        self.assertNotIn("PROOF", fork,
                         "a fork is divergence, not proof; the key `PROOF` is retracted")
        self.assertIn("DIVERGENCE, signed", fork["MEANS"])
        self.assertIn("is retracted", fork["MEANS"])

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
        msg = str(cm.exception)
        # D3b (T-401) widened the set of identities that can sign to include DELEGATED
        # credentials, so this refusal now has to rule out BOTH routes rather than one. The
        # assertion was tightened along with the message: checking only the warrant half
        # would leave the new route untested by the test whose whole job is "cannot sign".
        self.assertIn("issued inside a root-signed warrant", msg)
        self.assertIn("delegated credential", msg)


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
        # `contest` became a privileged kind on 2026-08-17 (D3a, T-400): an accuser must
        # declare the intent to accuse before accusing. Checked against AF-5 before it was
        # allowed -- filing an intent is SELF-SERVICE, on the accuser's own chain with the
        # accuser's own key, so no third party sits in the path and nobody can be stalled.
        # The cost is one extra signature by the accuser, which is the direction AF-3
        # already points.
        attest.declare_intent(self.root, "orso", keys["orso"], "contest", "T-x",
                              "acuso a aurelia de firmar un acto que no es mio")
        filed = attest.contest(self.root, "orso", keys["orso"], "aurelia", 0,
                               "esa firma no es mia", task="T-x")
        self.assertEqual(filed["name"], "orso")
        chain = attest.chain(self.root, "orso")
        self.assertEqual(len(chain), 2, "intent then contest, both on orso's own chain")
        self.assertEqual(chain[0]["kind"], attest.INTENT_KIND)
        self.assertEqual(chain[1]["kind"], "contest")
        self.assertEqual(chain[1]["ref"], "aurelia#0")
        self.assertIn("AF_3", chain[1]["body"])
        # DIS-5 unchanged and now doubly so: the accusation costs the accuser TWO permanent
        # signed positions in its own record, not one.
        self.assertEqual(chain[1]["intent"], chain[0]["_digest"])

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
        self.assertIn("identities remain self-asserted", out["NOTE"])
        self.assertIn("NOT a quotation of PR-022 clause 5", out["NOTE"])
        self.assertNotIn("CAVEAT", out,
                         "PR-022 clause 5 designates a canonical string; this module "
                         "must not paraphrase it and call the result a caveat")

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

    def test_nothing_in_this_suite_touches_the_live_trust_store(self):
        """The claim is ISOLATION, not un-enrolment.

        This test previously asserted `(LIVE_HARNESS / "trust").exists()` is False,
        which conflated two different facts: that no test writes to the live store,
        and that the operator has not enrolled yet. The operator enrolled on
        2026-08-16 and the test began failing on a correct harness -- a false
        positive that would have trained readers to ignore it.

        What it must actually pin is that running this suite leaves the live trust
        store byte-identical, whatever state the operator left it in. Both the
        enrolled and un-enrolled cases are legitimate; a CHANGE is not.
        """
        def snapshot():
            trust = LIVE_HARNESS / "trust"
            if not trust.exists():
                return None
            return {p.name: p.read_bytes() for p in sorted(trust.iterdir()) if p.is_file()}

        before = snapshot()
        self.full_warrant()
        self.assertEqual(snapshot(), before,
                         "this suite must never create, modify or delete anything in the "
                         "live trust store; it generates its own root in a temp dir")

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


# ---------------------------------------------------------------------------------
# EVERY TEST BELOW EXISTS BECAUSE A BLIND PANEL BROKE THE BUILD THESE FILES SHIPPED.
# The panel also proved the ORIGINAL suite was vacuous: replacing the whole warrant
# check with `if by == "mallory"` left 71 tests passing, because no test had ever
# passed a `warrant:`-prefixed string as an attack input. These do.
# ---------------------------------------------------------------------------------

class TheWarrantPrefixIsNotAnAuthorization(GateCase):

    def test_an_invented_warrant_id_mints_nothing(self):
        """The finding that refuted the whole build: `--by warrant:ME-LO-INVENTE`
        minted five names and sixty-four plazas against a genuinely enrolled root."""
        self.full_warrant()
        for forged in ("warrant:ME-LO-INVENTE", "warrant:", "warrant:W-999",
                       "warrant: W-001", "warrant:W-001 "):
            with self.assertRaises(KeyError, msg=f"{forged!r} was accepted"):
                roster.charter("sybil", "minteo", forged, self.root)
            with self.assertRaises(KeyError, msg=f"{forged!r} was accepted"):
                roster.issue("phantom", "banco", "judge", "e-1", forged, "", self.root)
        self.assertEqual(sorted(roster.load(self.root)["names"]), ["aurelia", "orso"])

    def test_a_real_warrant_does_not_authorize_what_it_does_not_say(self):
        """A verified signature says the operator signed SOMETHING, not THIS."""
        wid, _ = self.full_warrant()
        by = f"warrant:{wid}"
        with self.assertRaises(KeyError) as cm:
            roster.charter("gremio-que-nadie-firmo", "minteo", by, self.root)
        self.assertIn("does not authorize", str(cm.exception))
        with self.assertRaises(KeyError):
            roster.issue("phantom", "banco", "judge", "e-1", by, "", self.root)
        with self.assertRaises(KeyError):
            roster.plazas("e-1", "banco", "notary", 64, by, self.root)

    def test_a_real_warrant_does_authorize_what_it_does_say(self):
        """The gate must not be a brick: re-applying a verified warrant is idempotent,
        not refused for the wrong reason."""
        wid, _ = self.full_warrant()
        out = w.apply_warrant(self.root, wid)
        self.assertEqual(out["names"], [])
        self.assertTrue(out["already"])

    def test_the_warrant_check_is_not_a_denylist(self):
        """Mutation guard. The panel replaced the check with `if by == "mallory"` and
        the whole suite still passed. Any authorization that only refuses one literal
        string must fail here."""
        self.full_warrant()
        for by in ("mallory", "warrant:mallory", "coordinator", "", "warrant",
                   "WARRANT:W-001", "warrant:W-001/../W-001"):
            with self.assertRaises(KeyError, msg=f"{by!r} was accepted"):
                roster.charter("sybil", "x", by, self.root)


class TheRollIsReconciledAgainstTheWarrants(GateCase):

    def test_un_enrolling_minting_and_re_enrolling_leaves_orphans(self):
        """No in-process check can stop this (D-17); the point is that it is FOUND.
        The panel ran exactly this sequence and `audit` reported everything clean."""
        wid, _ = self.full_warrant()
        pub = w.trust_dir(self.root) / "root.pub"
        stashed = pub.parent / "root.pub.stashed"
        pub.rename(stashed)
        roster.charter("evil", "sybils", "mallory", self.root)
        roster.plazas("e-1", "evil", "judge", 64, "mallory", self.root)
        roster.issue("ghost-1", "evil", "judge", "e-1", "mallory", "", self.root)
        stashed.rename(pub)

        rec = w.reconcile(self.root)
        self.assertFalse(rec["clean"])
        self.assertEqual({o["kind"] for o in rec["orphans"]},
                         {"colegiado", "plaza", "name"})
        self.assertIn("ghost-1", [o["id"] for o in rec["orphans"]])

    def test_a_hand_edited_roll_leaves_orphans(self):
        self.full_warrant()
        path = self.root / "roster.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["names"]["colado"] = {"colegiado": "banco", "role": "judge",
                                   "epic": "e-1", "persona": "",
                                   "issued_by": "warrant:W-001",
                                   "issued_at": "2026-08-15T00:00:00Z"}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        rec = w.reconcile(self.root)
        self.assertFalse(rec["clean"])
        self.assertEqual([o["id"] for o in rec["orphans"]], ["colado"])

    def test_a_clean_roll_reconciles(self):
        self.full_warrant()
        rec = w.reconcile(self.root)
        self.assertTrue(rec["clean"], rec["orphans"])
        self.assertGreater(rec["checked"], 0)

    def test_audit_surfaces_the_alarm(self):
        self.full_warrant()
        (self.root / "roster.json").write_text(json.dumps({
            "schema_version": 1, "colegiados": {}, "plazas": {},
            "names": {"colado": {"colegiado": "x", "role": "y", "epic": "e-1",
                                 "persona": "", "issued_by": "warrant:W-001",
                                 "issued_at": "2026-08-15T00:00:00Z"}}}),
            encoding="utf-8")
        out = w.audit(self.root)
        self.assertFalse(out["roll_clean"])
        self.assertIn("ALARM", out)


class TheAnchorAfterThePanel(GateCase):

    def test_a_second_operator_line_in_root_pub_is_refused(self):
        """The panel appended a second `operator` line, left the fingerprint untouched
        because ssh-keygen -lf reports only the FIRST key, and had Mallory's warrants
        verify cleanly."""
        wid, _ = self.full_warrant()
        evil = self.keys / "evil"
        evil_pub = keygen(evil, "mallory")
        pub = w.trust_dir(self.root) / "root.pub"
        pub.write_text(pub.read_text(encoding="utf-8").rstrip() + "\n"
                       + evil_pub.read_text(encoding="utf-8"), encoding="utf-8")
        with self.assertRaises(w.TrustError) as cm:
            w.check_anchor(self.root)
        self.assertIn("holds 2 keys", str(cm.exception))
        with self.assertRaises(w.TrustError):
            w.verify_warrant(self.root, wid)

    def test_verify_reports_the_actual_signer_not_the_anchor(self):
        """verify_signature used to return the ANCHORED fingerprint regardless of who
        signed, so the audit trail actively misattributed."""
        wid, _ = self.full_warrant()
        self.assertEqual(w.verify_warrant(self.root, wid)["signed_by"],
                         w.key_fingerprint(self.root_pub))

    def test_init_refuses_to_re_anchor_an_enrolled_harness(self):
        self.enroll()
        evil = self.keys / "evil"
        evil_pub = keygen(evil, "mallory")
        with self.assertRaises(w.TrustError) as cm:
            w.init(self.root, evil_pub)
        self.assertIn("ALREADY ENROLLED", str(cm.exception))
        self.assertEqual(w.check_anchor(self.root), w.key_fingerprint(self.root_pub))

    def test_re_enrolling_the_same_key_is_harmless(self):
        self.enroll()
        self.assertEqual(w.init(self.root, self.root_pub)["fingerprint"],
                         w.key_fingerprint(self.root_pub))


class ActsSurviveConcurrency(GateCase):

    def test_concurrent_acts_lose_nothing(self):
        """Measured against the shipped build: 37 of 50 acts silently lost and 1 fork
        detected in 10 trials. sign_act had no guard at all, in the module that IS the
        evidentiary record."""
        import concurrent.futures
        wid, keys = self.full_warrant()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(
                lambda i: attest.sign_act(self.root, "aurelia", keys["aurelia"],
                                          "commit", f"ref-{i}"), range(5)))
        on_disk = sorted(p.name for p in
                         attest.acts_dir(self.root, "aurelia").glob("*.json"))
        self.assertEqual(len(results), 5)
        self.assertEqual(len(on_disk), 5, f"silent lost writes: {on_disk}")
        self.assertEqual(attest.verify_name(self.root, "aurelia")["signature_failures"],
                         [])

    def test_a_removed_act_does_not_cause_a_seq_overwrite(self):
        """Seq used to be len(glob), so removing act 0 made the next act reuse its path
        and overwrite a signed record."""
        wid, keys = self.full_warrant()
        a0 = attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit", "one")
        a1 = attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit", "two")
        os.remove(a0["path"])
        a2 = attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit", "three")
        self.assertNotEqual(a2["path"], a1["path"])
        self.assertTrue(pathlib.Path(a1["path"]).exists())


class WhatForkDetectionDoesNotCatch(GateCase):
    """The limits, asserted so no future edit can quietly re-inflate the claim."""

    def test_a_forger_using_the_shipped_verb_leaves_no_fork(self):
        """Measured. DIS-1 detects concurrent signing and retroactive insertion, NOT
        forgery in general, and the docstring must keep saying so.

        RE-MEASURED after D3a (T-400, 2026-08-17) and THE CONCLUSION DID NOT MOVE. `verdict`
        is now a privileged kind, so the forger has to file an intent first -- which it does,
        below, with the same stolen key, because under D-17 there is only one key to steal.
        Two signatures instead of one, still no fork, still no detection. That is the point:
        D3a raises the price of a forged privileged act and closes nothing.
        """
        wid, keys = self.full_warrant()
        attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit", "honest-1")
        attest.declare_intent(self.root, "aurelia", keys["aurelia"], "verdict", "T-x",
                              "intencion tambien forjada, con la misma llave robada")
        attest.sign_act(self.root, "aurelia", keys["aurelia"], "verdict", "FORGED",
                        task="T-x")
        attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit", "honest-2")
        rep = attest.verify_name(self.root, "aurelia")
        self.assertEqual(rep["forks"], [], "if this ever passes, update the docstring")
        self.assertFalse(rep["contested"])
        self.assertIn("WHAT IT DOES NOT CATCH", attest.__doc__)
        self.assertIn("leaves NO fork", attest.__doc__)
        # And the trace agrees the forgery is fully anchored, which is the honest report.
        t = attest.trace(self.root, "aurelia")
        forged = [r for r in t["rows"] if r["kind"] == "verdict"][0]
        self.assertTrue(forged["complete"],
                        "D3a must not be read as authenticating the actor; if this row is "
                        "incomplete the trace is claiming something it cannot know")

    def test_a_keyless_fabricated_fork_is_not_reported_as_proof(self):
        """Two write_text calls used to produce a CONTESTED verdict with an
        unconditional PROOF string claiming two parties held the key."""
        wid, keys = self.full_warrant()
        attest.sign_act(self.root, "aurelia", keys["aurelia"], "commit", "honest")
        d = attest.acts_dir(self.root, "aurelia")
        for seq in (50, 51):
            (d / f"{seq:03d}.json").write_text(json.dumps({
                "schema_version": 1, "name": "aurelia", "seq": seq, "kind": "basura",
                "ref": "", "body": {}, "prev": "genesis",
                "ts": "2026-08-15T00:00:00Z", "namespace": attest.NAMESPACE}) + "\n",
                encoding="utf-8")
        fork = attest.forks(self.root)[0]
        self.assertFalse(fork["all_branches_verified"])
        self.assertEqual(fork["STATUS"], "UNVERIFIED-DIVERGENCE")
        self.assertIn("NOT PROOF", fork["MEANS"])
        self.assertIn("no key at all", fork["MEANS"])


class SecondPanelRegressions(GateCase):
    """One test per finding of the second blind panel, which verdicted the previous
    build NOT compliant with PR-023 and named three separate minting paths that all
    ended with `audit` printing clean."""

    def test_agent_keys_json_is_not_a_second_registry(self):
        """F1. attest.sign_act trusted trust/agent_keys.json, a cache reconcile never
        read. The panel appended one entry by hand and its sybil signed acts while
        reconcile reported clean. The set is now DERIVED from verified warrants."""
        wid, keys = self.full_warrant()
        evil, evil_pub = self.agent_key("evil")
        (w.trust_dir(self.root) / "agent_keys.json").write_text(json.dumps({
            "sybil-1": {"pubkey": evil_pub.read_text(encoding="utf-8").strip(),
                        "warrant": wid, "epic": "e-1", "colegiado": "banco",
                        "role": "judge"}}), encoding="utf-8")
        with self.assertRaises(attest.AttestError):
            attest.sign_act(self.root, "sybil-1", evil, "verdict", "PR-999")
        self.assertNotIn("sybil-1", attest.enrolled_keys(self.root))

    def test_init_guards_on_either_trust_file(self):
        """F2. init guarded on root.fingerprint while is_enrolled guarded on root.pub,
        so renaming one file aside allowed a full re-anchor."""
        wid, _ = self.full_warrant()
        evil, evil_pub = self.agent_key("evil")
        fp = w.trust_dir(self.root) / "root.fingerprint"
        fp.rename(fp.parent / ".fp.bak")
        with self.assertRaises(w.TrustError) as cm:
            w.init(self.root, evil_pub)
        self.assertIn("ALREADY ENROLLED", str(cm.exception))

    def test_audit_without_expect_is_marked_unverified(self):
        """F3. Every check inside this module is consistent with whatever trust/ says,
        and trust/ is writable by every agent and untracked by git."""
        self.full_warrant()
        out = w.audit(self.root)
        self.assertIsNone(out["anchor_matches_operator"])
        self.assertIn("UNVERIFIED", out)
        self.assertIn("cannot distinguish", out["UNVERIFIED"])

    def test_audit_with_expect_catches_a_rewritten_anchor(self):
        wid, _ = self.full_warrant()
        good = w.check_anchor(self.root)
        evil, evil_pub = self.agent_key("evil")
        td = w.trust_dir(self.root)
        (td / "root.pub").write_text(evil_pub.read_text(encoding="utf-8"),
                                     encoding="utf-8")
        (td / "root.fingerprint").write_text(w.key_fingerprint(evil_pub) + "\n",
                                             encoding="utf-8")
        out = w.audit(self.root, expect=good)
        self.assertFalse(out["anchor_matches_operator"])
        self.assertIn("TRUST ROOT REPLACED", out["ALARM"])

    def test_a_warrant_authorizes_its_values_not_only_its_keys(self):
        """F4. The panel signed banco/judge=2 and wrote 64, signed one incentive and
        rewrote it, and seated a name in a role the warrant never gave it."""
        wid, _ = self.full_warrant()
        by = f"warrant:{wid}"
        data = roster.load(self.root)
        data["plazas"]["e-1"].pop("banco/judge")
        (self.root / "roster.json").write_text(json.dumps(data, indent=2),
                                               encoding="utf-8")
        with self.assertRaises(KeyError):
            roster.plazas("e-1", "banco", "judge", 64, by, self.root)
        with self.assertRaises(KeyError):
            roster.charter("banco", "paga por lo que yo diga", by, self.root)
        with self.assertRaises(KeyError):
            roster.issue("aurelia", "banco", "notary", "e-1", by, "", self.root)

    def test_require_warrant_checks_expiry(self):
        """F5. apply_warrant refused an expired warrant; roster.py accepted it, which
        voided --valid-until's whole stated purpose."""
        self.enroll()
        priv, pub = self.agent_key("aurelia")
        d = w.draft(self.root, "e-1", ["banco=x"], ["banco/judge=1"],
                    [f"aurelia:banco/judge:{pub}"],
                    valid_until="2020-01-01T00:00:00Z")
        root_sign(pathlib.Path(d["path"]), self.root_key)
        with self.assertRaises(KeyError) as cm:
            roster.charter("banco", "x", f"warrant:{d['warrant_id']}", self.root)
        self.assertIn("expired", str(cm.exception))

    def test_one_key_signing_concurrently_does_not_manufacture_a_fork(self):
        """F6. The guard covered the seq computation and the O_EXCL create but was
        released before the JSON body was written, so a peer read a zero-byte act,
        head() rewound, and one party's six sign calls produced a fork the tool then
        called proof that two parties held the key."""
        import concurrent.futures
        wid, keys = self.full_warrant()
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda i: attest.sign_act(self.root, "aurelia",
                                                    keys["aurelia"], "commit", f"r{i}"),
                          range(6)))
        rep = attest.verify_name(self.root, "aurelia")
        self.assertEqual(rep["acts"], 6)
        self.assertEqual(rep["forks"], [], "one key, one party, a fabricated fork")

    def test_reconcile_survives_a_hostile_roll(self):
        """F7. reconcile died on a traceback when names was a list, and failed OPEN on
        an unparseable roster.json because roster.load swallows the decode error."""
        self.full_warrant()
        path = self.root / "roster.json"
        path.write_text(json.dumps({"schema_version": 1, "colegiados": {},
                                    "plazas": {}, "names": []}), encoding="utf-8")
        rec = w.reconcile(self.root)
        self.assertFalse(rec["clean"])
        path.write_text("{not json at all", encoding="utf-8")
        rec = w.reconcile(self.root)
        self.assertFalse(rec["clean"])
        self.assertIn("unreadable", rec["orphans"][0]["reason"])

    def test_the_warrant_id_is_a_filename_not_a_path(self):
        """F9. `warrant:../stash/W-001` verified a document outside warrants/, so
        authorization and reconciliation read different sets."""
        wid, _ = self.full_warrant()
        for bad in ("../stash/W-001", "W-001/../W-001", "/etc/passwd", "W-1", "w-001"):
            with self.assertRaises(KeyError, msg=f"{bad!r} accepted"):
                roster.charter("banco", "x", f"warrant:{bad}", self.root)

    def test_the_governing_record_carries_the_retraction(self):
        """F8. The code retracted `unforgeable proof that two parties held the key`
        while D-20 DIS-1 still asserted it."""
        record = (ROOT / ".harness" / "coordinator-decisions-ruling-round-2.md"
                  ).read_text(encoding="utf-8")
        self.assertIn("RETRACTED", record)
        self.assertNotIn("unforgeable proof that two parties held the key", record)


class ThirdPanelRegressions(GateCase):
    """The third blind panel found that BOTH detectors go silent on an un-enrolled
    harness, which is the state an attacker produces by deleting one untracked
    directory. The previous repair fixed `audit` to look at the roll; it left the
    early return that fires before `audit` looks at anything at all."""

    def test_expect_on_an_unenrolled_harness_is_an_alarm_not_a_clean_report(self):
        """DEFECT AUDIT-EXPECT-DISCARDED. `audit --expect SHA256:anything` returned
        {"enrolled": false} and exit 0 -- the fingerprint was read, discarded and never
        compared, because the un-enrolled early return sat above the expect block.
        Three states produced identical silence: un-enrolled, forged-root-without-expect,
        and genuine-root-with-matching-expect."""
        out = w.audit(self.root, expect="SHA256:" + "Z" * 43)
        self.assertFalse(out["enrolled"])
        self.assertIn("ALARM", out, "a false operator assertion must be loud")
        self.assertIn("NO TRUST ROOT", out["ALARM"])
        self.assertIs(out["anchor_matches_operator"], False)
        self.assertTrue(out["expect_supplied"])

    def test_the_alarm_reaches_the_exit_code(self):
        """A detector nothing keys on is decoration. main() returns 3 on ALARM, so the
        fix has to travel all the way to the shell, not just into the JSON."""
        rc = w.main(["--root", str(self.root), "audit",
                     "--expect", "SHA256:" + "Z" * 43])
        self.assertEqual(rc, 3)

    def test_unenrolled_without_expect_stays_exit_zero_and_says_not_assessed(self):
        """The asymmetry is the whole design: silence when nobody claimed anything,
        alarm when someone claimed and the claim is false. Before enrolment there is no
        flag day, so this path must NOT start failing."""
        out = w.audit(self.root)
        self.assertNotIn("ALARM", out)
        self.assertIn("UNVERIFIED", out)
        self.assertIsNone(out["anchor_matches_operator"])
        self.assertFalse(out["expect_supplied"])
        self.assertEqual(w.main(["--root", str(self.root), "audit"]), 0)

    def test_the_downgrade_attack_no_longer_reads_as_clean(self):
        """DEFECT RECONCILE-SILENT-UNENROLLED. Enroll, mint an unwarranted name, then
        delete trust/. reconcile used to answer {"orphans": [], "checked": 0} with no
        `clean` key, which every caller read as clean while the illegitimate row sat
        untouched on the roll. trust/ is untracked, so the deletion leaves no trace in
        `git status` either. This is the exact sequence reconcile's own docstring names.
        """
        import roster
        self.full_warrant()
        roster.load(self.root)                       # roll now holds warranted rows
        before = w.reconcile(self.root)
        self.assertTrue(before["clean"])
        self.assertGreater(before["checked"], 0)

        for p in sorted(w.trust_dir(self.root).iterdir()):
            p.unlink()
        w.trust_dir(self.root).rmdir()

        after = w.reconcile(self.root)
        self.assertFalse(after["enrolled"])
        self.assertIsNone(after["clean"], "NOT ASSESSED must never read as clean")
        self.assertGreater(after["roll_rows_unbacked"], 0,
                           "the rows survived the deletion and must be counted")
        self.assertIn("UN-ENROLLED", after["note"])
        # and the verb that DOES refuse it, with the operator's real fingerprint
        alarm = w.audit(self.root, expect="SHA256:" + "Q" * 43)
        self.assertIn("ALARM", alarm)

    def test_records_are_not_issued_under_warrants_and_nothing_pretends_they_are(self):
        """The panel's condition-(a) finding: `reconcile` walks roster.json, while every
        standing figure is computed from precedents/PR-*.json:published_by. There is no
        join. Any future clause claiming a figure is 'computed from records issued under
        warrants' names a relationship that does not exist, and this test fails the day
        someone wires one without saying so."""
        import ast
        src = (ROOT / ".harness" / "bin" / "precedent.py").read_text(encoding="utf-8")
        imported = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertNotIn("warrant", imported)
        self.assertNotIn("roster", imported)


if __name__ == "__main__":
    unittest.main(verbosity=2)
