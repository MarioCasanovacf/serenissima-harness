"""T-400 / D3a: a privileged act needs a declared intent BEFORE it, and the whole trace
back to the operator has to be walkable.

The operator ruled YES on D3 on 2026-08-17. The CSA framework asks for three anchoring
records per privileged action -- intent declared, privilege granted, privilege exercised --
linked by agent identity plus task id so any action reconstructs to the authorizing human.
Two of those three already existed in this harness: the warrant IS the grant, and the
signed act IS the exercise. Only the intent was missing.

WHAT THESE TESTS ARE MOSTLY FOR. Not the happy path. The happy path is four lines. These
pin the BYPASSES, because every one of them makes the feature worse than its absence:

  - an UNSIGNED intent would satisfy the requirement for the price of one write_text, with
    no key at all, and would then "authorize" a forged act;
  - an intent on SOMEONE ELSE'S chain would let an attacker manufacture evidence that the
    victim deliberated (the framing surface T-400 names);
  - ONE intent authorizing MANY acts is a standing authorization, not a declared intent;
  - an intent with an UNPARSEABLE timestamp must fall closed, because the actor writes that
    field and it is the actor the bound constrains;
  - a refusal that half-writes an act would be worse than the missing requirement.

AND WHAT THEY PIN ABOUT THE LIMITS, which matters as much. D-17 is untouched: a test below
forges a privileged act by stealing the victim's key, files the intent as the victim too,
and asserts the trace comes back COMPLETE. It is supposed to. Three records raise a forged
act from one signature to two and authenticate nobody, and if that assertion ever starts
failing, someone has added a claim this module cannot support.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import attest  # noqa: E402
import warrant as w  # noqa: E402


def attribute_docstring(varname):
    """The string literal written directly under a module-level assignment.

    Needed because Python does NOT attach these to the object: `PRIVILEGED_KINDS.__doc__`
    is frozenset's docstring and `INTENT_MAX_AGE_S.__doc__` is int's. Two tests below were
    first written against `__doc__` and both PASSED VACUOUSLY -- they were asserting a
    substring against the builtin type's documentation, and would have kept passing with
    the module's prose deleted entirely.

    A substring scan over the source would be the other easy way to do this, and it is
    wrong for the reason already on this project's defect register three times over
    (GUARD-MENTION-C): the source also contains prose that DISCUSSES these constants, so a
    scan cannot tell the definition from a mention of it. This parses.
    """
    import ast
    body = ast.parse((ROOT / ".harness" / "bin" / "attest.py").read_text(
        encoding="utf-8")).body
    for i, node in enumerate(body):
        targets = getattr(node, "targets", [])
        if (isinstance(node, ast.Assign) and targets
                and isinstance(targets[0], ast.Name) and targets[0].id == varname):
            nxt = body[i + 1] if i + 1 < len(body) else None
            if (isinstance(nxt, ast.Expr) and isinstance(nxt.value, ast.Constant)
                    and isinstance(nxt.value.value, str)):
                return nxt.value.value
    return None


def _keygen(path, comment="k"):
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", comment,
                    "-f", str(path)], check=True, capture_output=True)
    return path


def _sign_file(path, key, namespace):
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", namespace,
                    str(path)], check=True, capture_output=True)


class Enrolled(unittest.TestCase):
    """A real warrant, signed by a real root key, issuing two real names.

    Built rather than mocked: the intent check calls warrant.enrolled_keys, which DERIVES
    the key set from verified warrants on purpose (there is no cache to stub). A mock here
    would test a different module than the one that ships.
    """

    NAMES = [("aurelia", "registro", "author"), ("orso", "revision", "verifier")]

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name) / "h"
        (self.root / "trust").mkdir(parents=True)
        (self.root / "warrants").mkdir(parents=True)

        kd = pathlib.Path(self._tmp.name) / "keys"
        kd.mkdir()
        self.rootkey = _keygen(kd / "root", "operator")
        (self.root / "trust" / "root.pub").write_text(
            (self.rootkey.with_suffix(".pub")).read_text(encoding="utf-8"),
            encoding="utf-8")
        fp = subprocess.run(["ssh-keygen", "-lf", str(self.root / "trust" / "root.pub")],
                            capture_output=True, text=True, check=True).stdout.split()[1]
        (self.root / "trust" / "root.fingerprint").write_text(fp + "\n",
                                                              encoding="utf-8")
        self.fingerprint = fp

        self.keys = {}
        names = []
        for n, col, role in self.NAMES:
            k = _keygen(kd / n, n)
            self.keys[n] = k
            names.append({"name": n, "colegiado": col, "role": role,
                          "pubkey": k.with_suffix(".pub").read_text(
                              encoding="utf-8").strip()})
        payload = {
            "schema_version": 1, "warrant_id": "W-001", "epic": "E-test",
            # `namespace` and `valid_until` are not decoration: verify_warrant refuses a
            # payload whose namespace is not warrant.NAMESPACE, which is what stops a root
            # signature made for an act from being replayed as a warrant.
            "namespace": w.NAMESPACE,
            "colegiados": [{"name": "registro", "purpose": "p"},
                           {"name": "revision", "purpose": "p"}],
            "plazas": [{"colegiado": "registro", "role": "author", "seats": 2},
                       {"colegiado": "revision", "role": "verifier", "seats": 2}],
            "names": names, "valid_until": "2099-01-01T00:00:00Z",
            "issued": "2026-01-01T00:00:00Z",
        }
        wp = self.root / "warrants" / "W-001.json"
        wp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        _sign_file(wp, self.rootkey, w.NAMESPACE)
        self.assertIn("aurelia", attest.enrolled_keys(self.root),
                      "the fixture itself is broken; nothing below would mean anything")

    # ------------------------------------------------------------------ helpers

    def intent(self, name="orso", for_kind="verdict", task="T-1", declares="por que",
               for_ref=""):
        return attest.declare_intent(self.root, name, self.keys[name], for_kind, task,
                                     declares, for_ref)

    def verdict(self, name="orso", task="T-1", ref="aurelia#1"):
        return attest.sign_act(self.root, name, self.keys[name], "verdict", ref=ref,
                               task=task)

    def acts_on(self, name):
        return sorted(p.name for p in attest.acts_dir(self.root, name).glob("*.json"))


class TheRequirement(Enrolled):

    def test_a_privileged_act_is_refused_with_no_intent(self):
        with self.assertRaises(attest.AttestError) as e:
            self.verdict()
        msg = str(e.exception)
        self.assertIn("no open intent", msg)
        self.assertIn("declare-intent", msg, "a refusal must name the command that fixes it")

    def test_the_refusal_writes_nothing(self):
        # A half-written act would be worse than the missing requirement: it would sit in
        # the chain forever and steer future `prev` values.
        with self.assertRaises(attest.AttestError):
            self.verdict()
        self.assertEqual(self.acts_on("orso"), [])

    def test_intent_then_act_succeeds_and_records_the_link(self):
        i = self.intent()
        a = self.verdict()
        self.assertEqual(a["intent"], i["digest"])
        self.assertEqual(a["task"], "T-1")
        self.assertTrue(a["privileged"])

    def test_an_unprivileged_act_still_needs_nothing(self):
        # The regression this change could most easily cause. `commit` and `filing` are a
        # name doing its own work and were never privileged.
        a = attest.sign_act(self.root, "aurelia", self.keys["aurelia"], "commit", "x")
        self.assertEqual(a["intent"], "")
        self.assertFalse(a["privileged"])

    def test_a_privileged_act_without_a_task_is_refused_before_the_chain_is_read(self):
        self.intent()
        with self.assertRaises(attest.AttestError) as e:
            attest.sign_act(self.root, "orso", self.keys["orso"], "verdict", task="")
        self.assertIn("--task is required", str(e.exception))

    def test_intent_cannot_declare_an_intent(self):
        with self.assertRaises(attest.AttestError) as e:
            attest.declare_intent(self.root, "orso", self.keys["orso"],
                                  attest.INTENT_KIND, "T-1", "x")
        self.assertIn("regress", str(e.exception))

    def test_an_empty_declaration_is_refused(self):
        # An intent whose prose is blank is a checkbox. Checkboxes anchor nothing, and the
        # whole point of D3a is that the record be reconstructable by a reader.
        for blank in ("", "   "):
            with self.assertRaises(attest.AttestError):
                attest.declare_intent(self.root, "orso", self.keys["orso"], "verdict",
                                      "T-1", blank)


class TheDeclaredTargetBinds(Enrolled):
    """T-408. The gap the verifier revision-ataque found while accepting T-400.

    An intent reading "I am going to issue a verdict on aurelia#1" authorized a verdict on
    orso#7 just as well: matching compared (for_kind, task) and never read for_ref. Not a
    false claim -- the docstring promised kind plus task -- but a gap between what an intent
    SAID and what it BOUND.

    THE RULE CHOSEN IS BIND-WHEN-DECLARED, and the alternative was measured before choosing.
    Bind-always would force one intent per target. The live chain holds ONE privileged act,
    in one (name, kind, task) group, against one target; a population of one settles nothing
    about a typical session, so the decision does not rest on it. Bind-when-declared costs
    zero extra intents for anyone who leaves the field empty and narrows only the signer who
    chose to name a target.
    """

    def test_an_intent_naming_a_target_does_not_authorize_a_different_one(self):
        self.intent(for_ref="aurelia#1")
        with self.assertRaises(attest.AttestError) as e:
            self.verdict(ref="orso#7")
        msg = str(e.exception)
        self.assertIn("NAMES A DIFFERENT TARGET", msg)
        self.assertIn("aurelia#1", msg)
        self.assertIn("orso#7", msg)

    def test_the_refusal_writes_nothing_and_leaves_the_intent_open(self):
        i = self.intent(for_ref="aurelia#1")
        with self.assertRaises(attest.AttestError):
            self.verdict(ref="orso#7")
        # One act on the chain: the intent itself. The refused verdict wrote nothing, and
        # the intent is still spendable on the target it actually named.
        self.assertEqual(len(self.acts_on("orso")), 1)
        self.assertEqual([o["digest"] for o in attest.open_intents(self.root, "orso")],
                         [i["digest"]])
        a = self.verdict(ref="aurelia#1")
        self.assertEqual(a["intent"], i["digest"])

    def test_an_intent_naming_a_target_authorizes_that_target(self):
        i = self.intent(for_ref="aurelia#1")
        a = self.verdict(ref="aurelia#1")
        self.assertEqual(a["intent"], i["digest"])

    def test_an_intent_that_names_no_target_still_authorizes_any_target(self):
        """NO NET NARROWING BEYOND THE MISMATCH. Every intent filed before T-408 left the
        field empty, and each one keeps working exactly as it did."""
        i = self.intent()
        a = self.verdict(ref="whatever#99")
        self.assertEqual(a["intent"], i["digest"])

    def test_the_right_intent_is_chosen_when_several_are_open(self):
        """Selection, not first-match. Two open intents differing only in target."""
        wrong = self.intent(for_ref="aurelia#1")
        right = self.intent(for_ref="orso#7")
        a = self.verdict(ref="orso#7")
        self.assertEqual(a["intent"], right["digest"])
        self.assertNotEqual(a["intent"], wrong["digest"])
        self.assertEqual([o["digest"] for o in attest.open_intents(self.root, "orso")],
                         [wrong["digest"]], "the unused intent must remain open")

    def test_binding_two_self_asserted_fields_authenticates_nothing(self):
        """THE LIMIT, pinned so no reader mistakes this for a control on a thief.

        for_ref is written by the signer, exactly like ref. A holder of another agent's key
        -- which under D-17 is every agent on this filesystem -- files the matching intent
        and proceeds. What the binding buys is that a deviation is WRITTEN DOWN, on that
        name's own chain, credited to that name.
        """
        stolen = self.keys["orso"]
        attest.declare_intent(self.root, "orso", stolen, "verdict", "T-1", "robo",
                              "aurelia#1")
        a = attest.sign_act(self.root, "orso", stolen, "verdict", ref="aurelia#1",
                            task="T-1")
        self.assertTrue(a["privileged"])
        t = attest.trace(self.root, "orso")
        self.assertTrue(all(r["complete"] for r in t["rows"]),
                        "the trace reads COMPLETE for a thief, and that is the point")

    def test_the_trace_reports_a_target_mismatch_rather_than_calling_it_complete(self):
        """A mismatch cannot be produced through sign_act any more, so it is written onto
        the chain directly -- which is exactly the state an editor of the acts directory
        would leave behind, and the state trace exists to report."""
        i = self.intent(for_ref="aurelia#1")
        a = self.verdict(ref="aurelia#1")
        path = attest.acts_dir(self.root, "orso") / ("%03d.json" % a["seq"])
        body = json.loads(path.read_text(encoding="utf-8"))
        body["ref"] = "orso#7"
        path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")

        t = attest.trace(self.root, "orso")
        row = next(r for r in t["rows"] if r["seq"] == a["seq"])
        self.assertFalse(row["intent_ref_agrees"])
        self.assertFalse(row["complete"])
        gap = next(g for g in t["gaps"] if g["seq"] == a["seq"])
        self.assertTrue(any("T-408" in m for m in gap["missing"]),
                        "the mismatch must be named as such: %r" % gap["missing"])
        self.assertEqual(i["digest"], row["intent_digest"])

    def test_the_trace_counts_acts_authorized_by_an_intent_that_named_no_target(self):
        """The looseness has to be countable or it is invisible: a row reading `complete`
        looks identical whether the intent bound the target or bound nothing about it."""
        self.intent()
        self.verdict(ref="aurelia#1")
        self.intent(for_ref="aurelia#2")
        self.verdict(ref="aurelia#2")
        t = attest.trace(self.root, "orso")
        self.assertEqual(t["ref_open_intent_raw"], 1)
        self.assertEqual(t["ref_open_intent_distinct"], 1)
        self.assertEqual(t["ref_open_intent"][0]["ref"], "aurelia#1")
        self.assertIn("authenticates nothing", t["T_408_REF_BINDS_WHEN_DECLARED"].lower())


class TheBypasses(Enrolled):
    """Each of these, if it worked, would make the feature worse than not having it."""

    def test_an_unsigned_intent_does_not_count(self):
        """The cheapest attack: no key required at all.

        DIS-1 measured a fabricated fork at the cost of two write_text calls. An intent is
        the same shape of artefact, so if an unsigned one satisfied the requirement, then
        anyone -- with no key, no name and no warrant -- could pre-authorize a forged
        privileged act. The intent must VERIFY, not merely exist.
        """
        i = self.intent()
        pathlib.Path(i["path"]).with_suffix(".json.sig").unlink()
        self.assertEqual(attest.open_intents(self.root, "orso"), [])
        with self.assertRaises(attest.AttestError):
            self.verdict()

    def test_an_intent_signed_by_the_wrong_key_does_not_count(self):
        i = self.intent()
        sig = pathlib.Path(i["path"]).with_suffix(".json.sig")
        sig.unlink()
        _sign_file(pathlib.Path(i["path"]), self.keys["aurelia"], attest.NAMESPACE)
        self.assertEqual(attest.open_intents(self.root, "orso"), [])

    def test_an_intent_declared_by_another_name_does_not_authorize(self):
        """The framing surface T-400 warns about: manufacturing evidence that the victim
        deliberated.

        A NEGATIVE CONTROL CORRECTED THIS TEST'S EXPLANATION. It first claimed the
        protection came from chain-locality -- the intent living in the actor's own act
        directory. Pooling every name's intents into one shared set passed all 33 tests,
        which proves the directory is not the mechanism. The mechanism is the signature: an
        intent must VERIFY under the actor's own enrolled key, so aurelia's intent, signed
        by aurelia, is invisible to orso no matter where the file sits.

        AND THE LIMIT, pinned by the test below this one: inside this harness that bounds
        nobody, because D-17 hands every agent every key.
        """
        attest.declare_intent(self.root, "aurelia", self.keys["aurelia"], "verdict",
                              "T-1", "declaro por orso")
        self.assertEqual(attest.open_intents(self.root, "orso"), [])
        with self.assertRaises(attest.AttestError):
            self.verdict()

    def test_the_mechanism_is_the_signature_and_not_the_directory(self):
        """Pins what the negative control established, so the corrected claim cannot drift
        back to the stronger one.

        aurelia's intent act is copied verbatim into ORSO's own act directory, signature and
        all. It is now on orso's chain by every structural measure. It still does not
        authorize orso, because it verifies under aurelia's key and not orso's.
        """
        i = attest.declare_intent(self.root, "aurelia", self.keys["aurelia"], "verdict",
                                  "T-1", "declaro por orso")
        src = pathlib.Path(i["path"])
        dst = attest.acts_dir(self.root, "orso")
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "001.json").write_bytes(src.read_bytes())
        (dst / "001.json.sig").write_bytes(src.with_suffix(".json.sig").read_bytes())
        self.assertTrue((dst / "001.json").is_file(), "the fixture did not copy the act")
        self.assertEqual(attest.open_intents(self.root, "orso"), [],
                         "an intent on orso's chain signed by aurelia must not authorize "
                         "orso; if this passes, the signature check was dropped")

    def test_one_intent_authorizes_exactly_one_act(self):
        self.intent()
        self.verdict()
        with self.assertRaises(attest.AttestError) as e:
            self.verdict()
        self.assertIn("no open intent", str(e.exception))

    def test_an_intent_for_a_different_kind_does_not_transfer(self):
        self.intent(for_kind="contest")
        with self.assertRaises(attest.AttestError) as e:
            self.verdict()
        self.assertIn("none for a 'verdict'", str(e.exception))
        # and the refusal has to say what IS open, or the operator is stuck guessing
        self.assertIn("contest", str(e.exception))

    def test_an_intent_for_a_different_task_does_not_transfer(self):
        self.intent(task="T-1")
        with self.assertRaises(attest.AttestError):
            attest.sign_act(self.root, "orso", self.keys["orso"], "verdict", task="T-2")

    def test_a_stale_intent_does_not_count(self):
        i = self.intent()
        p = pathlib.Path(i["path"])
        act = json.loads(p.read_text(encoding="utf-8"))
        act["ts"] = "2020-01-01T00:00:00Z"
        p.write_text(json.dumps(act, indent=2) + "\n", encoding="utf-8")
        p.with_suffix(".json.sig").unlink()
        _sign_file(p, self.keys["orso"], attest.NAMESPACE)
        self.assertEqual(attest.open_intents(self.root, "orso"), [])

    def test_an_unreadable_timestamp_falls_CLOSED(self):
        """The actor writes `ts`, and `ts` is what bounds the actor. So an unparseable
        value must expire the intent, never exempt it. A guard that treats "cannot tell how
        old this is" as "fresh" hands the bound to the party it constrains."""
        i = self.intent()
        p = pathlib.Path(i["path"])
        act = json.loads(p.read_text(encoding="utf-8"))
        act["ts"] = "manana por la manana"
        p.write_text(json.dumps(act, indent=2) + "\n", encoding="utf-8")
        p.with_suffix(".json.sig").unlink()
        _sign_file(p, self.keys["orso"], attest.NAMESPACE)
        self.assertEqual(attest.open_intents(self.root, "orso"), [])
        self.assertIsNone(attest._age_seconds("manana"))
        self.assertIsNone(attest._age_seconds(None))

    def test_consumption_is_derived_and_not_stored_in_a_ledger(self):
        """PR-010's computed-on-read doctrine, and the roster.py cache defect.

        A consumption ledger would be a second registry nothing reconciles -- exactly the
        `trust/agent_keys.json` failure a panel exploited by hand-appending one entry. So
        the only thing that marks an intent consumed is the act's own `intent` field. Proof:
        clear that field and the intent is open again, with no other file touched.
        """
        i = self.intent()
        a = self.verdict()
        self.assertEqual(attest.open_intents(self.root, "orso"), [])
        p = pathlib.Path(a["path"])
        act = json.loads(p.read_text(encoding="utf-8"))
        act["intent"] = ""
        p.write_text(json.dumps(act, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(len(attest.open_intents(self.root, "orso")), 1,
                         "consumption is not derived from the act; a ledger crept in")
        # Tampering is not free: the act no longer verifies, which is the trade this design
        # makes on purpose. Detection, not prevention.
        self.assertTrue(attest.verify_name(self.root, "orso")["signature_failures"])


class TheLimits(Enrolled):
    """What D3a does NOT close. If these start failing, a claim was added that the module
    cannot support, and that is a defect and not an improvement."""

    def test_a_thief_with_the_key_files_the_intent_too_and_the_trace_says_COMPLETE(self):
        """D-17, exercised rather than asserted.

        Every agent runs as the same OS user and can read `.harness/keys/`. So an attacker
        forging as orso files orso's intent with orso's key and then orso's verdict with
        orso's key. Both verify. The trace is complete. IT IS SUPPOSED TO BE.

        The security gain is arithmetic: two signatures instead of one. The DESIGN gain is
        DIS-2 -- both signatures credit orso, so the forgery still cannot enrich the
        forger. This test exists so nobody can quietly upgrade the claim.
        """
        stolen = self.keys["orso"]              # read by a party that is not orso
        attest.declare_intent(self.root, "orso", stolen, "verdict", "T-9", "forjado")
        attest.sign_act(self.root, "orso", stolen, "verdict", ref="aurelia#1", task="T-9")
        t = attest.trace(self.root, "orso")
        rows = [r for r in t["rows"] if r["kind"] == "verdict"]
        self.assertTrue(rows and rows[0]["complete"],
                        "the forged pair must trace COMPLETE; D3a authenticates nobody")
        self.assertIn("authenticates nobody", t["D_17_UNCHANGED"])

    def test_the_module_states_D_17_is_untouched(self):
        doc = attest.__doc__ or ""
        self.assertIn("WHAT D3a DOES NOT CLOSE", doc)
        self.assertIn("D-17 IS UNTOUCHED", doc)
        self.assertIn("one signature to", doc)

    def test_the_kind_based_hole_is_named_as_a_defect(self):
        """An actor can label a disposal `commit` and escape the requirement. The hole is
        not closeable (ref is also actor-controlled), so it must be NAMED."""
        doc = attribute_docstring("PRIVILEGED_KINDS")
        self.assertIsNotNone(doc, "PRIVILEGED_KINDS has no explanation at all")
        self.assertIn("INTENT-BY-KIND-A", doc)
        self.assertIn("THE CRITERION", doc, "the set must not be an arbitrary list")

    def test_an_act_labelled_unprivileged_is_reported_by_trace_in_its_own_bucket(self):
        """The mitigation for INTENT-BY-KIND-A, and the FIRST version of this test found a
        real reporting flaw rather than passing.

        It originally looked in `gaps`, and nothing was there: a `commit` with a valid
        signature, a warrant and an anchor is `complete` -- correctly, because no intent is
        required of it -- so it never reached the gap branch. The mislabelled-disposal
        surface was therefore reported NOWHERE, which is exactly the silence the defect note
        promised it would avoid. It now has its own bucket, because these acts are not
        defects; they are the population a human has to read.
        """
        attest.sign_act(self.root, "aurelia", self.keys["aurelia"], "commit",
                        ref="orso#1")
        t = attest.trace(self.root, "aurelia")
        self.assertEqual(t["unprivileged_no_intent_raw"], 1)
        self.assertEqual(t["unprivileged_no_intent"][0]["ref"], "orso#1",
                         "the ref must be shown; it is the only clue a disposal is hiding")
        self.assertIn("INTENT-BY-KIND-A", t["INTENT_BY_KIND_A"])
        # And it must NOT be filed as a gap, or every honest act becomes a finding and the
        # report is noise (the alarm-fatigue shape of RECONCILE-UNSIGNED-DIRTY).
        self.assertEqual(t["gaps"], [])


class TheThresholdDoc(unittest.TestCase):

    def test_the_lifetime_constant_disclaims_a_ratified_threshold(self):
        # currency.py precedent: a tool that invents a threshold has decided the question
        # the record left open. 24h here is this module's default and nothing ratified it.
        doc = attribute_docstring("INTENT_MAX_AGE_S")
        self.assertIsNotNone(doc, "INTENT_MAX_AGE_S has no explanation at all")
        self.assertIn("NO THRESHOLD RATIFIED", doc)
        self.assertIn("T-401", doc, "the general TTL question must be attributed")

    def test_the_helper_this_file_relies_on_is_not_vacuous(self):
        """A negative control on the test helper itself, because two tests in this file
        already passed vacuously against a builtin's __doc__."""
        self.assertIsNone(attribute_docstring("NAMESPACE"),
                          "NAMESPACE carries a trailing comment, not a docstring; if this "
                          "returns a string the helper is matching the wrong node")
        self.assertIsNone(attribute_docstring("no_such_constant_anywhere"))


class TheTrace(Enrolled):

    def test_the_walk_reaches_the_warrant_and_the_anchor(self):
        self.intent()
        self.verdict()
        t = attest.trace(self.root, "orso")
        row = [r for r in t["rows"] if r["kind"] == "verdict"][0]
        self.assertEqual(row["granted_by_warrant"], "W-001")
        self.assertEqual(row["colegiado"], "revision")
        self.assertEqual(row["anchor"], self.fingerprint)
        self.assertTrue(row["complete"])

    def test_every_count_is_reported_raw_and_distinct(self):
        self.intent()
        self.verdict()
        t = attest.trace(self.root)
        for stem in ("acts", "privileged", "complete", "names"):
            self.assertIn(stem + "_raw", t)
            self.assertIn(stem + "_distinct", t)

    def test_the_report_marks_its_own_anchor_unverified(self):
        t = attest.trace(self.root)
        self.assertIn("ANCHOR_IS_UNVERIFIED", t)
        self.assertIn("audit --expect", t["ANCHOR_IS_UNVERIFIED"])

    def test_the_report_does_not_hand_back_the_fingerprint_to_paste_into_expect(self):
        """The first version of this note interpolated the on-disk fingerprint straight into
        the --expect command, which invites the operator to check the suspect file against
        itself and call it an audit. AUDIT-EXPECT-DISCARDED's family.

        The value may still be DISPLAYED -- an operator comparing by eye needs to see it --
        but never inside the command line they are being told to run.
        """
        self.intent()
        self.verdict()
        note = attest.trace(self.root)["ANCHOR_IS_UNVERIFIED"]
        cmd = [ln for ln in note.splitlines() if "--expect" in ln]
        self.assertTrue(cmd, "the note stopped naming the command that settles it")
        self.assertNotIn(self.fingerprint, "\n".join(cmd),
                         "the command hands back the value it is supposed to check")
        self.assertIn("OFF this machine", "\n".join(cmd))
        self.assertIn(self.fingerprint, note, "the untrusted value must still be shown")

    def test_a_missing_anchor_makes_every_row_incomplete(self):
        self.intent()
        self.verdict()
        (self.root / "trust" / "root.fingerprint").unlink()
        t = attest.trace(self.root)
        self.assertEqual(t["complete_raw"], 0)
        self.assertTrue(any("fingerprint" in m for g in t["gaps"] for m in g["missing"]))

    def test_trace_never_refuses(self):
        """The half of D3a that survives if a verifier rules the sign-time refusal out of
        order under PR-022 clause 4. It must therefore not depend on the refusal at all."""
        d = attest.acts_dir(self.root, "orso")
        d.mkdir(parents=True, exist_ok=True)
        (d / "001.json").write_text('{"kind":"verdict","seq":1,"prev":"genesis",'
                                    '"task":"T-1","intent":""}\n', encoding="utf-8")
        t = attest.trace(self.root, "orso")          # no exception
        self.assertEqual(t["privileged_raw"], 1)
        self.assertEqual(t["complete_raw"], 0)
        self.assertTrue(any("no intent record" in m
                            for g in t["gaps"] for m in g["missing"]))


class TheRendererBug(Enrolled):
    """RENDER-FORK-KEYERROR, found while building D3a.

    When DIS-1's proof claim was retracted, the fork dict's `PROOF` key was renamed to
    `MEANS` and `_render` was not updated. So `attest.py verify` -- no --name, no --json --
    raised KeyError whenever a fork existed: the human-readable renderer crashed on the one
    condition it exists to report. No test rendered a fork, which is why it survived.
    """

    def test_verify_renders_a_fork_without_crashing(self):
        first = attest.sign_act(self.root, "aurelia", self.keys["aurelia"], "commit")
        d = attest.acts_dir(self.root, "aurelia")
        forged = d / "002.json"
        act = json.loads(pathlib.Path(first["path"]).read_text(encoding="utf-8"))
        act["seq"] = 2
        forged.write_text(json.dumps(act, indent=2) + "\n", encoding="utf-8")
        _sign_file(forged, self.keys["aurelia"], attest.NAMESPACE)
        self.assertTrue(attest.forks(self.root), "the fixture did not produce a fork")

        env = dict(os.environ, WARRANT_ROOT=str(self.root))
        r = subprocess.run([sys.executable, str(ROOT / ".harness" / "bin" / "attest.py"),
                            "--root", str(self.root), "verify"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("FORK", r.stdout)
        self.assertNotIn("KeyError", r.stderr)

    def test_the_renderer_does_not_reference_the_retracted_key(self):
        import ast
        src = (ROOT / ".harness" / "bin" / "attest.py").read_text(encoding="utf-8")
        # AST, not a substring scan: the comment explaining the bug names PROOF on purpose,
        # and a scan would match it forever (GUARD-MENTION-C).
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
                self.assertNotEqual(node.slice.value, "PROOF",
                                    "the renamed key is subscripted again")


class TheCli(Enrolled):

    def run_cli(self, *argv):
        return subprocess.run(
            [sys.executable, str(ROOT / ".harness" / "bin" / "attest.py"),
             "--root", str(self.root)] + list(argv),
            capture_output=True, text=True)

    def test_declare_intent_then_sign_through_the_cli(self):
        r = self.run_cli("declare-intent", "--name", "orso",
                         "--key", str(self.keys["orso"]), "--for-kind", "verdict",
                         "--task", "T-7", "--declares", "reviso el acto de aurelia")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_cli("sign", "--name", "orso", "--key", str(self.keys["orso"]),
                         "--kind", "verdict", "--ref", "aurelia#1", "--task", "T-7")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["task"], "T-7")

    def test_signing_a_privileged_kind_with_no_intent_exits_2(self):
        r = self.run_cli("sign", "--name", "orso", "--key", str(self.keys["orso"]),
                         "--kind", "verdict", "--task", "T-7")
        self.assertEqual(r.returncode, 2)
        self.assertIn("declare-intent", r.stderr)

    def test_trace_renders(self):
        self.intent()
        self.verdict()
        r = self.run_cli("trace")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("W-001", r.stdout)
        self.assertIn("audit --expect", r.stdout)

    def test_intents_says_why_an_empty_list_may_be_empty(self):
        r = self.run_cli("intents", "--name", "orso")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("signed by that name's enrolled key", r.stderr)


if __name__ == "__main__":
    unittest.main()
