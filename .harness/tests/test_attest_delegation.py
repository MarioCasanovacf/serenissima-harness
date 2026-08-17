"""T-401 / D3b: the delegation ceiling, and credentials that expire and cannot extend.

Two properties the operator ruled YES on: no identity delegates more privilege than it
holds, and a subagent credential carries a TTL the subagent cannot extend.

T-401 asks for a test that tries to exceed the ceiling AND SHOWS WHAT IS NOT STOPPED. Both
halves are here, and the second half is the more important one:

  WHAT IS STOPPED. Granting a kind you do not hold. Granting past your own expiry. Granting
  to yourself. Granting to a warranted name. Re-granting to a name that already holds a
  credential. Signing a kind you were not granted. Signing after expiry.

  WHAT IS NOT STOPPED, and is demonstrated rather than asserted. An adversary. D-17 puts
  every private key on a filesystem every agent reads, so an agent that wants a privilege it
  was not granted does not attack the ceiling -- it reads the grantor's key and signs as the
  grantor. `test_the_ceiling_is_bypassed_entirely_by_reading_the_grantors_key` does exactly
  that and asserts it WORKS. If it ever starts failing, someone has claimed a wall this
  module does not have.

  AND WHAT IS VACUOUS. The ceiling does not constrain a warranted name at all, because
  nothing in this harness restricts a warranted name by role yet, so a warranted name holds
  every privileged kind. The ceiling binds from the SECOND hop. That is pinned too, so the
  limitation cannot quietly be forgotten.
"""
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import attest  # noqa: E402
import warrant as w  # noqa: E402

from test_attest_intent import Enrolled, _keygen, _sign_file  # noqa: E402

FAR = "2099-01-01T00:00:00Z"
NEAR = "2030-01-01T00:00:00Z"
PAST = "2020-01-01T00:00:00Z"


class Delegating(Enrolled):
    """aurelia and orso are warranted (W-001, valid_until 2099). Sub keys are not."""

    def setUp(self):
        super().setUp()
        self.subdir = pathlib.Path(self._tmp.name) / "subkeys"
        self.subdir.mkdir()

    def sub(self, name):
        k = _keygen(self.subdir / name, name)
        return k, k.with_suffix(".pub").read_text(encoding="utf-8").strip()

    def grant(self, to_name, kinds=("verdict",), expires=NEAR, by="aurelia", task="T-1"):
        # `grant` is itself privileged (D3a), so an intent comes first. That composition is
        # the point: delegation is exactly the act whose deliberation belongs on the record.
        attest.declare_intent(self.root, by, self.keys[by], "grant", task,
                              "delego a %s" % to_name)
        key, pub = self.sub(to_name)
        act = attest.grant_privilege(self.root, by, self.keys[by], to_name, pub,
                                     list(kinds), expires, task)
        return key, act


class TheCeiling(Delegating):

    def test_a_grant_creates_a_signing_identity_that_holds_only_what_was_granted(self):
        key, _ = self.grant("sub-a", kinds=("verdict",))
        self.assertEqual(attest.held_kinds(self.root, "sub-a"), {"verdict"})
        self.assertIn("sub-a", attest.signing_keys(self.root))
        # and it can actually exercise it, or the grant handed out nothing
        attest.declare_intent(self.root, "sub-a", key, "verdict", "T-2", "reviso")
        a = attest.sign_act(self.root, "sub-a", key, "verdict", ref="x", task="T-2")
        self.assertTrue(a["privileged"])

    def test_a_delegate_cannot_sign_a_kind_it_was_not_granted(self):
        key, _ = self.grant("sub-b", kinds=("verdict",))
        attest.declare_intent(self.root, "sub-b", key, "contest", "T-2", "quiero acusar")
        with self.assertRaises(attest.AttestError) as e:
            attest.sign_act(self.root, "sub-b", key, "contest", ref="y", task="T-2")
        self.assertIn("DELEGATION CEILING", str(e.exception))

    def test_a_delegate_cannot_grant_more_than_it_holds(self):
        """The hop where the ceiling actually bites."""
        key, _ = self.grant("sub-c", kinds=("verdict", "grant"))
        attest.declare_intent(self.root, "sub-c", key, "grant", "T-3", "sub-delego")
        _, pub = self.sub("sub-c-child")
        with self.assertRaises(attest.AttestError) as e:
            attest.grant_privilege(self.root, "sub-c", key, "sub-c-child", pub,
                                   ["verdict", "contest"], NEAR, "T-3")
        msg = str(e.exception)
        self.assertIn("DELEGATION CEILING", msg)
        self.assertIn("contest", msg)
        self.assertIn("cannot grant", msg)

    def test_a_delegate_that_was_not_granted_grant_cannot_re_delegate_at_all(self):
        """A GAP A TEST FOUND, not a property designed up front.

        The first implementation checked only that the delegated KINDS were a subset of what
        the grantor held. It never checked that the grantor held `grant` itself. So any
        delegate could re-delegate forever: the ceiling bounded WHAT was passed on and left
        WHETHER it could be passed on unbounded, which is half a ceiling.

        A credential is now non-re-delegable by default. Handing on the power to hand on has
        to be an explicit decision, and the refusal says so.
        """
        key, _ = self.grant("sub-nog", kinds=("verdict",))
        attest.declare_intent(self.root, "sub-nog", key, "grant", "T-3", "intento delegar")
        _, pub = self.sub("sub-nog-child")
        with self.assertRaises(attest.AttestError) as e:
            attest.grant_privilege(self.root, "sub-nog", key, "sub-nog-child", pub,
                                   ["verdict"], NEAR, "T-3")
        msg = str(e.exception)
        self.assertIn("NOT 'grant'", msg)
        self.assertIn("not re-delegable by default", msg)
        self.assertNotIn("sub-nog-child", attest.delegated_keys(self.root))

    def test_a_delegate_can_grant_a_subset_of_what_it_holds(self):
        key, _ = self.grant("sub-d", kinds=("verdict", "distinguish", "grant"))
        attest.declare_intent(self.root, "sub-d", key, "grant", "T-3", "sub-delego")
        _, pub = self.sub("sub-d-child")
        attest.grant_privilege(self.root, "sub-d", key, "sub-d-child", pub,
                               ["verdict"], NEAR, "T-3")
        self.assertEqual(attest.held_kinds(self.root, "sub-d-child"), {"verdict"})
        self.assertEqual(attest.delegated_keys(self.root)["sub-d-child"]["depth"], 2)

    def test_the_ceiling_is_VACUOUS_at_the_first_hop_and_says_so(self):
        """Not a happy-path test. A limitation, pinned so it cannot be forgotten.

        A warranted name holds every privileged kind, so the ceiling restrains the
        coordinator's first grant not at all. Anyone who cites D3b as a bound on a warranted
        name is citing something that does not exist.
        """
        self.assertEqual(attest.held_kinds(self.root, "aurelia"),
                         set(attest.PRIVILEGED_KINDS))
        d = attest.delegations(self.root)
        self.assertIn("VACUOUS AT THE FIRST HOP",
                      d["CEILING_IS_VACUOUS_AT_THE_FIRST_HOP"].upper())

    def test_a_narrowed_grantor_narrows_its_descendants_on_the_next_read(self):
        """The ceiling is applied transitively ON EVERY READ, which is why there is no cache.

        sub-e holds verdict+distinguish and passes both to a child. Its own grant is then
        edited down to verdict only and re-signed. The child must lose distinguish
        immediately, without any act of the child's own being touched.
        """
        key, act = self.grant("sub-e", kinds=("verdict", "distinguish", "grant"))
        attest.declare_intent(self.root, "sub-e", key, "grant", "T-3", "sub-delego")
        _, pub = self.sub("sub-e-child")
        attest.grant_privilege(self.root, "sub-e", key, "sub-e-child", pub,
                               ["verdict", "distinguish"], NEAR, "T-3")
        self.assertEqual(attest.held_kinds(self.root, "sub-e-child"),
                         {"verdict", "distinguish"})

        p = pathlib.Path(act["path"])
        payload = json.loads(p.read_text(encoding="utf-8"))
        payload["body"]["kinds"] = ["verdict", "grant"]
        p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        p.with_suffix(".json.sig").unlink()
        _sign_file(p, self.keys["aurelia"], attest.NAMESPACE)

        # `grant` stays in sub-e's set so the narrowing under test is `distinguish` alone;
        # stripping `grant` too would make the child lose it for the wrong reason.
        self.assertEqual(attest.held_kinds(self.root, "sub-e"), {"verdict", "grant"})
        self.assertEqual(attest.held_kinds(self.root, "sub-e-child"), {"verdict"},
                         "the child kept a privilege its grantor no longer holds; the "
                         "ceiling is not being applied transitively")

    def test_a_grant_signed_by_the_wrong_key_creates_nothing(self):
        key, act = self.grant("sub-f")
        p = pathlib.Path(act["path"])
        p.with_suffix(".json.sig").unlink()
        _sign_file(p, self.keys["orso"], attest.NAMESPACE)
        self.assertNotIn("sub-f", attest.delegated_keys(self.root))

    def test_an_unsigned_grant_creates_nothing(self):
        key, act = self.grant("sub-g")
        pathlib.Path(act["path"]).with_suffix(".json.sig").unlink()
        self.assertNotIn("sub-g", attest.delegated_keys(self.root))


class TheExpiry(Delegating):

    def test_a_grant_past_the_grantors_own_expiry_is_REFUSED_not_clamped(self):
        """Refused rather than clamped, and the distinction is deliberate.

        Silently keeping a smaller value than the caller typed is defect T-376's exact shape
        (`--voids A --voids B` kept B and exited 0). Here the value would be a SECURITY
        parameter, so a silent substitution is worse: the operator would believe a credential
        lives until the date they typed.
        """
        attest.declare_intent(self.root, "aurelia", self.keys["aurelia"], "grant", "T-1",
                              "delego demasiado tiempo")
        _, pub = self.sub("sub-h")
        with self.assertRaises(attest.AttestError) as e:
            attest.grant_privilege(self.root, "aurelia", self.keys["aurelia"], "sub-h",
                                   pub, ["verdict"], "2100-01-01T00:00:00Z", "T-1")
        msg = str(e.exception)
        self.assertIn("later than", msg)
        self.assertIn("Refused rather than clamped", msg)
        self.assertNotIn("sub-h", attest.delegated_keys(self.root))

    def test_an_expiry_is_required(self):
        attest.declare_intent(self.root, "aurelia", self.keys["aurelia"], "grant", "T-1",
                              "sin vencimiento")
        _, pub = self.sub("sub-i")
        with self.assertRaises(attest.AttestError) as e:
            attest.grant_privilege(self.root, "aurelia", self.keys["aurelia"], "sub-i",
                                   pub, ["verdict"], "", "T-1")
        self.assertIn("standing privilege", str(e.exception))

    def test_a_past_expiry_is_refused_at_grant_time(self):
        attest.declare_intent(self.root, "aurelia", self.keys["aurelia"], "grant", "T-1",
                              "ya vencido")
        _, pub = self.sub("sub-j")
        with self.assertRaises(attest.AttestError) as e:
            attest.grant_privilege(self.root, "aurelia", self.keys["aurelia"], "sub-j",
                                   pub, ["verdict"], PAST, "T-1")
        self.assertIn("already in the past", str(e.exception))

    def test_an_expired_credential_simply_does_not_exist(self):
        key, act = self.grant("sub-k", expires=NEAR)
        self.assertIn("sub-k", attest.delegated_keys(self.root))
        p = pathlib.Path(act["path"])
        payload = json.loads(p.read_text(encoding="utf-8"))
        payload["body"]["expires"] = PAST
        p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        p.with_suffix(".json.sig").unlink()
        _sign_file(p, self.keys["aurelia"], attest.NAMESPACE)
        self.assertNotIn("sub-k", attest.delegated_keys(self.root))
        with self.assertRaises(attest.AttestError) as e:
            attest.sign_act(self.root, "sub-k", key, "commit")
        self.assertIn("can sign nothing", str(e.exception))

    def test_a_credential_cannot_extend_itself_by_granting_to_itself(self):
        """Barrier one of two."""
        key, _ = self.grant("sub-l", kinds=("verdict", "grant"), expires=NEAR)
        attest.declare_intent(self.root, "sub-l", key, "grant", "T-3", "me extiendo")
        _, pub = self.sub("sub-l-again")
        with self.assertRaises(attest.AttestError) as e:
            attest.grant_privilege(self.root, "sub-l", key, "sub-l", pub,
                                   ["verdict"], FAR, "T-3")
        self.assertIn("cannot grant to itself", str(e.exception))

    def test_a_credential_cannot_be_extended_through_an_intermediary_either(self):
        """Barrier two of two, and the one that matters, because barrier one is easy to walk
        around: sub-m grants to sub-n, and sub-n tries to grant BACK a longer credential.

        Every expiry is clamped to the grantor's on read, so no path through the graph
        produces a date later than the warrant at its root. This is the property that makes
        'the subagent cannot extend its TTL' true rather than merely intended.
        """
        key_m, _ = self.grant("sub-m", kinds=("verdict", "grant"), expires=NEAR)
        attest.declare_intent(self.root, "sub-m", key_m, "grant", "T-3", "delego a sub-n")
        key_n, pub_n = self.sub("sub-n")
        attest.grant_privilege(self.root, "sub-m", key_m, "sub-n", pub_n,
                               ["verdict", "grant"], NEAR, "T-3")
        self.assertEqual(attest.effective_expiry(self.root, "sub-n"), NEAR)

        # sub-n now tries to mint a LONGER credential for a fresh name. Refused at sign time.
        attest.declare_intent(self.root, "sub-n", key_n, "grant", "T-4", "extiendo")
        _, pub_o = self.sub("sub-o")
        with self.assertRaises(attest.AttestError) as e:
            attest.grant_privilege(self.root, "sub-n", key_n, "sub-o", pub_o,
                                   ["verdict"], FAR, "T-4")
        self.assertIn("later than", str(e.exception))

    def test_a_forged_longer_expiry_is_clamped_on_read(self):
        """Sign-time refusal only binds the shipped verb. A party writing the act directly
        needs the READ side to clamp, and this is the test that the read side does.

        sub-p's grant is rewritten by hand to expire in 2100, later than W-001's 2099, and
        re-signed with the grantor's key so it verifies. The credential must still not
        outlive the warrant it descends from.
        """
        key, act = self.grant("sub-p", expires=NEAR)
        p = pathlib.Path(act["path"])
        payload = json.loads(p.read_text(encoding="utf-8"))
        payload["body"]["expires"] = "2100-01-01T00:00:00Z"
        p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        p.with_suffix(".json.sig").unlink()
        _sign_file(p, self.keys["aurelia"], attest.NAMESPACE)
        self.assertEqual(attest.effective_expiry(self.root, "sub-p"),
                         "2099-01-01T00:00:00Z",
                         "a hand-written grant outlived its root warrant; the read-side "
                         "clamp is not being applied")


class TheRefusals(Delegating):

    def test_a_grant_cannot_target_a_warranted_name(self):
        attest.declare_intent(self.root, "aurelia", self.keys["aurelia"], "grant", "T-1",
                              "intento tocar a orso")
        _, pub = self.sub("whatever")
        with self.assertRaises(attest.AttestError) as e:
            attest.grant_privilege(self.root, "aurelia", self.keys["aurelia"], "orso",
                                   pub, ["verdict"], NEAR, "T-1")
        msg = str(e.exception)
        self.assertIn("WARRANTED name", msg)
        self.assertIn("agent-writable state on the authorization path", msg)

    def test_a_second_grant_to_the_same_name_is_refused_not_merged(self):
        """Merging is how a ceiling gets raised one act at a time."""
        self.grant("sub-q", kinds=("verdict",))
        attest.declare_intent(self.root, "aurelia", self.keys["aurelia"], "grant", "T-9",
                              "amplio a sub-q")
        _, pub = self.sub("sub-q2")
        with self.assertRaises(attest.AttestError) as e:
            attest.grant_privilege(self.root, "aurelia", self.keys["aurelia"], "sub-q",
                                   pub, ["contest"], NEAR, "T-9")
        self.assertIn("already holds a delegated credential", str(e.exception))
        self.assertEqual(attest.held_kinds(self.root, "sub-q"), {"verdict"})

    def test_granting_requires_a_declared_intent_first(self):
        """D3a and D3b compose: delegation is a privileged act."""
        _, pub = self.sub("sub-r")
        with self.assertRaises(attest.AttestError) as e:
            attest.grant_privilege(self.root, "aurelia", self.keys["aurelia"], "sub-r",
                                   pub, ["verdict"], NEAR, "T-1")
        self.assertIn("no open intent", str(e.exception))
        self.assertNotIn("sub-r", attest.delegated_keys(self.root))

    def test_granting_nothing_is_refused(self):
        attest.declare_intent(self.root, "aurelia", self.keys["aurelia"], "grant", "T-1",
                              "nada")
        _, pub = self.sub("sub-s")
        with self.assertRaises(attest.AttestError):
            attest.grant_privilege(self.root, "aurelia", self.keys["aurelia"], "sub-s",
                                   pub, [], NEAR, "T-1")


class TheLimits(Delegating):
    """T-401 asks explicitly for what is and is not stopped. This class is the second half."""

    def test_the_ceiling_is_bypassed_entirely_by_reading_the_grantors_key(self):
        """MUST KEEP PASSING. D-17, exercised rather than asserted.

        A subagent that wants `contest` and holds only `verdict` does not attack the ceiling.
        It reads aurelia's private key off the filesystem -- every agent runs as the same OS
        user -- and signs as aurelia, who holds everything. The ceiling is not a wall. It
        bounds ACCIDENT and makes overreach ATTRIBUTABLE, and DIS-2 is what makes the bypass
        unprofitable: the act credits aurelia, not the subagent.
        """
        key, _ = self.grant("sub-t", kinds=("verdict",))
        self.assertEqual(attest.held_kinds(self.root, "sub-t"), {"verdict"})
        stolen = self.keys["aurelia"]                      # readable by every agent
        attest.declare_intent(self.root, "aurelia", stolen, "contest", "T-5", "forjado")
        a = attest.sign_act(self.root, "aurelia", stolen, "contest", ref="orso#1",
                            task="T-5")
        self.assertTrue(a["privileged"],
                        "if this raises, the module is claiming a wall it does not have")
        # And the honest consolation, which is the only real one:
        self.assertEqual(a["name"], "aurelia",
                         "DIS-2: the forged privilege credits the grantor, never the "
                         "subagent that wanted it")

    def test_reconcile_reports_clean_while_a_delegated_identity_can_sign(self):
        """DEFECT DELEGATION-OUTSIDE-RECONCILE-A, demonstrated.

        `reconcile` asks whether every ROLL row traces to a warrant. A delegated identity is
        in no roll, so reconcile is clean and silent about it. That is reconcile answering a
        narrower question, not reconcile failing -- but an auditor who runs only reconcile
        gets an incomplete answer to 'who can sign here', and the report says so.
        """
        self.grant("sub-u", kinds=("verdict",))
        self.assertIn("sub-u", attest.signing_keys(self.root))
        rec = w.reconcile(self.root)
        self.assertTrue(rec["clean"], "the fixture is not exercising the defect")
        self.assertNotIn("sub-u", json.dumps(rec))
        d = attest.delegations(self.root)
        self.assertIn("DELEGATION-OUTSIDE-RECONCILE-A", d["RECONCILE_DOES_NOT_SEE_THESE"])
        self.assertIn("Run both verbs", d["RECONCILE_DOES_NOT_SEE_THESE"])

    def test_the_report_states_it_does_not_bound_an_adversary(self):
        d = attest.delegations(self.root)
        self.assertIn("does not bound an adversary", d["D_17_UNCHANGED"])
        self.assertIn("ACCIDENT", d["D_17_UNCHANGED"])

    def test_warrant_enrolled_keys_is_not_widened_by_a_grant(self):
        """The property warrant.py's own guarantees are stated in terms of.

        If a grant could add to enrolled_keys, then `reconcile`'s roll-traces-to-warrant
        check would be reasoning over agent-created identities and 'minting is closed'
        would be false. So enrolled_keys stays WARRANTED-ONLY and signing_keys is the wider
        set. This test is the fence around that distinction.
        """
        before = set(w.enrolled_keys(self.root))
        self.grant("sub-v", kinds=("verdict",))
        self.assertEqual(set(w.enrolled_keys(self.root)), before)
        self.assertIn("sub-v", set(attest.signing_keys(self.root)) - before)


class TheCounts(Delegating):

    def test_delegations_reports_every_count_raw_and_distinct(self):
        self.grant("sub-w", kinds=("verdict",))
        d = attest.delegations(self.root)
        for stem in ("warranted", "delegated", "can_sign"):
            self.assertIn(stem + "_raw", d)
            self.assertIn(stem + "_distinct", d)
        self.assertEqual(d["delegated_raw"], 1)
        self.assertEqual(d["can_sign_raw"], d["warranted_raw"] + 1)


class TheCli(Delegating):

    def run_cli(self, *argv):
        return subprocess.run(
            [sys.executable, str(ROOT / ".harness" / "bin" / "attest.py"),
             "--root", str(self.root)] + list(argv), capture_output=True, text=True)

    def test_grant_and_delegations_and_holds_through_the_cli(self):
        attest.declare_intent(self.root, "aurelia", self.keys["aurelia"], "grant", "T-1",
                              "delego por cli")
        _, pub = self.sub("sub-x")
        r = self.run_cli("grant", "--by", "aurelia", "--key", str(self.keys["aurelia"]),
                         "--to", "sub-x", "--pubkey", pub, "--kinds", "verdict",
                         "--expires", NEAR, "--task", "T-1")
        self.assertEqual(r.returncode, 0, r.stderr)

        r = self.run_cli("delegations")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("sub-x", r.stdout)
        self.assertIn("DELEGATION-OUTSIDE-RECONCILE-A", r.stdout)

        r = self.run_cli("holds", "--name", "sub-x")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["privileged_kinds"], ["verdict"])
        self.assertEqual(out["expires"], NEAR)
        self.assertFalse(out["warranted"])

    def test_exceeding_the_ceiling_through_the_cli_exits_2(self):
        key, _ = self.grant("sub-y", kinds=("verdict", "grant"))
        attest.declare_intent(self.root, "sub-y", key, "grant", "T-3", "excedo")
        _, pub = self.sub("sub-y-child")
        r = self.run_cli("grant", "--by", "sub-y", "--key", str(key),
                         "--to", "sub-y-child", "--pubkey", pub,
                         "--kinds", "verdict", "contest",
                         "--expires", NEAR, "--task", "T-3")
        self.assertEqual(r.returncode, 2)
        self.assertIn("DELEGATION CEILING", r.stderr)


if __name__ == "__main__":
    unittest.main()
