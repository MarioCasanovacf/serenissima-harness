"""T-406 / T-448: the `retract` verb -- a speaker disowning their own act, on their own
chain. The design is `.harness/design-T-406-retraction.md`; this is part (a), the verb
itself. Part (b), the live retraction of the 2026-08-17 false verdict, is T-460 and does
not happen here: every fixture below lives in a temporary directory, never in the live
`.harness/acts`.

WHAT THESE TESTS ARE MOSTLY FOR, same shape as test_attest_intent.py: not the happy path,
but the four refusals the design lists, backward resolution computed on read, the D-17
limit (a thief can forge a false retraction of a true act, and this design does not stop
that), and an output-shape guard pinning PR-022 clause 4 -- no counter, weight or gate
anywhere in this module reads a retraction field.
"""
import ast
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ATTEST_PY = ROOT / ".harness" / "bin" / "attest.py"
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import attest  # noqa: E402
import warrant as w  # noqa: E402


def _keygen(path, comment="k"):
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", comment,
                    "-f", str(path)], check=True, capture_output=True)
    return path


def _sign_file(path, key, namespace):
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", namespace,
                    str(path)], check=True, capture_output=True)


class Enrolled(unittest.TestCase):
    """A real warrant, signed by a real root key, issuing two real names, in a temporary
    directory. Never the live registry (T-448's own instruction, and T-406's own limit:
    "a reader who bypasses the tools bypasses the resolution")."""

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
        (self.root / "trust" / "root.fingerprint").write_text(fp + "\n", encoding="utf-8")
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

    def commit(self, name="orso", ref="x"):
        """An ordinary unprivileged act: something to retract."""
        return attest.sign_act(self.root, name, self.keys[name], "commit", ref=ref)

    def retract(self, name="orso", seq=None, reason="era un error"):
        return attest.retract(self.root, name, self.keys[name], seq, reason)

    def acts_on(self, name):
        return sorted(p.name for p in attest.acts_dir(self.root, name).glob("*.json"))

    def run_cli(self, *argv):
        return subprocess.run(
            [sys.executable, str(ATTEST_PY), "--root", str(self.root)] + list(argv),
            capture_output=True, text=True)


class TheKindIsUnprivileged(Enrolled):

    def test_RETRACT_KIND_is_the_string_retract(self):
        self.assertEqual(attest.RETRACT_KIND, "retract")

    def test_RETRACT_KIND_needs_no_intent(self):
        self.assertNotIn(attest.RETRACT_KIND, attest.PRIVILEGED_KINDS)

    def test_a_retraction_succeeds_with_no_declared_intent_on_file(self):
        c = self.commit()
        self.assertEqual(attest.open_intents(self.root, "orso"), [],
                         "the fixture must start with no open intent, or this test proves "
                         "nothing about retract needing none")
        a = self.retract(seq=c["seq"])
        self.assertFalse(a["privileged"])
        self.assertEqual(a["intent"], "")


class TheBodyShape(Enrolled):

    def test_the_act_carries_retracts_digest_retracts_seq_and_reason(self):
        c = self.commit()
        a = self.retract(seq=c["seq"], reason="era falso")
        path = pathlib.Path(a["path"])
        body = json.loads(path.read_text(encoding="utf-8"))["body"]
        self.assertEqual(body["retracts"], c["digest"])
        self.assertEqual(body["retracts_seq"], c["seq"])
        self.assertEqual(body["reason"], "era falso")

    def test_a_blank_reason_is_refused(self):
        c = self.commit()
        for blank in ("", "   "):
            with self.assertRaises(attest.AttestError) as e:
                self.retract(seq=c["seq"], reason=blank)
            self.assertIn("reason", str(e.exception).lower())

    def test_a_blank_reason_refusal_writes_nothing(self):
        c = self.commit()
        before = self.acts_on("orso")
        with self.assertRaises(attest.AttestError):
            self.retract(seq=c["seq"], reason="")
        self.assertEqual(self.acts_on("orso"), before)

    def test_the_cli_exposes_retract(self):
        c = self.commit()
        r = self.run_cli("retract", "--name", "orso", "--key", str(self.keys["orso"]),
                         "--seq", str(c["seq"]), "--reason", "era falso")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertTrue(out["path"])

    def test_the_cli_refuses_a_blank_reason(self):
        c = self.commit()
        r = self.run_cli("retract", "--name", "orso", "--key", str(self.keys["orso"]),
                         "--seq", str(c["seq"]), "--reason", " ")
        self.assertEqual(r.returncode, 2)
        self.assertIn("reason", r.stderr.lower())


class TheFourRefusals(Enrolled):
    """Each one, if it did not hold, would make the verb worse than its absence."""

    def test_no_act_at_that_seq_is_refused(self):
        with self.assertRaises(attest.AttestError) as e:
            self.retract(seq=999)
        self.assertIn("no act at seq", str(e.exception))

    def test_a_retraction_cannot_target_another_names_act(self):
        """STRUCTURAL, not merely checked: there is no parameter through which a foreign
        name's act could be named. aurelia and orso each sign a `commit` landing at the
        SAME seq number; orso's retraction by that seq number retracts ORSO's own act,
        never aurelia's, no matter that the sequence numbers collide."""
        a_act = attest.sign_act(self.root, "aurelia", self.keys["aurelia"], "commit",
                                ref="a")
        o_act = self.commit(ref="o")
        self.assertEqual(a_act["seq"], o_act["seq"],
                         "the fixture needs colliding seq numbers to prove the point")
        r = self.retract(seq=o_act["seq"])
        path = pathlib.Path(r["path"])
        body = json.loads(path.read_text(encoding="utf-8"))["body"]
        self.assertEqual(body["retracts"], o_act["digest"])
        self.assertNotEqual(body["retracts"], a_act["digest"],
                            "a retraction filed as orso must never be able to name "
                            "aurelia's act; that is `contest`, a different verb")

    def test_the_target_must_verify_an_unsigned_act_is_refused(self):
        c = self.commit()
        path = pathlib.Path(c["path"])
        path.with_suffix(".json.sig").unlink()
        with self.assertRaises(attest.AttestError) as e:
            self.retract(seq=c["seq"])
        self.assertIn("does not verify", str(e.exception))

    def test_the_target_must_verify_a_tampered_act_is_refused(self):
        c = self.commit()
        path = pathlib.Path(c["path"])
        body = json.loads(path.read_text(encoding="utf-8"))
        body["ref"] = "tampered"
        path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(attest.AttestError) as e:
            self.retract(seq=c["seq"])
        self.assertIn("does not verify", str(e.exception))

    def test_a_second_retraction_of_the_same_target_is_refused_not_a_silent_duplicate(self):
        c = self.commit()
        first = self.retract(seq=c["seq"], reason="primera")
        with self.assertRaises(attest.AttestError) as e:
            self.retract(seq=c["seq"], reason="segunda")
        msg = str(e.exception)
        self.assertIn("already retracted", msg)
        self.assertIn(str(first["seq"]), msg)
        # And it wrote nothing: still exactly two acts (the commit and the one retraction).
        self.assertEqual(len(self.acts_on("orso")), 2)

    def test_a_retraction_cannot_be_retracted(self):
        c = self.commit()
        r = self.retract(seq=c["seq"])
        with self.assertRaises(attest.AttestError) as e:
            self.retract(seq=r["seq"], reason="deshago la retractacion")
        self.assertIn("cannot be retracted", str(e.exception))
        # No flip-flop: still exactly two acts.
        self.assertEqual(len(self.acts_on("orso")), 2)

    def test_refusals_write_nothing(self):
        c = self.commit()
        before = self.acts_on("orso")
        for seq in (999,):
            with self.assertRaises(attest.AttestError):
                self.retract(seq=seq)
        self.assertEqual(self.acts_on("orso"), before)


class BackwardResolution(Enrolled):
    """`retractions()` is computed on read, from the chain alone -- no side ledger."""

    def test_retractions_maps_digest_to_the_retracting_act(self):
        c = self.commit()
        r = self.retract(seq=c["seq"])
        m = attest.retractions(self.root, "orso")
        self.assertIn(c["digest"], m)
        self.assertEqual(m[c["digest"]]["seq"], r["seq"])

    def test_an_unretracted_act_is_absent_from_the_map(self):
        c = self.commit()
        self.assertEqual(attest.retractions(self.root, "orso"), {})
        self.commit(ref="y")
        self.retract(seq=c["seq"])
        other = self.commit(ref="z")
        m = attest.retractions(self.root, "orso")
        self.assertNotIn(other["digest"], m)

    def test_there_is_no_side_ledger_removing_the_act_file_changes_the_read(self):
        """PR-010's doctrine, exercised exactly as test_attest_intent.py exercises it for
        intent consumption: the only state is the chain itself."""
        c = self.commit()
        self.retract(seq=c["seq"])
        self.assertTrue(attest.retractions(self.root, "orso"))
        # Hand-edit the retracting act's body so it no longer names the target -- the same
        # shape as clearing `intent` in test_attest_intent.py's consumption test.
        acts = attest.chain(self.root, "orso")
        retract_act = [a for a in acts if a.get("kind") == attest.RETRACT_KIND][0]
        p = pathlib.Path(retract_act["_path"])
        body = json.loads(p.read_text(encoding="utf-8"))
        body["body"]["retracts"] = ""
        p.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(attest.retractions(self.root, "orso"), {},
                         "retractions is not derived from the chain alone; a ledger crept "
                         "in")

    def test_first_retraction_in_chain_order_wins_if_the_refusal_is_bypassed(self):
        """`retract()` refuses a second filing; a direct editor of the acts directory
        bypasses every refusal this module ships, same as every other guard here. The read
        side must still answer deterministically."""
        c = self.commit()
        first = self.retract(seq=c["seq"], reason="primera")
        # Hand-craft a second retracting act directly, bypassing the refusal.
        second = attest.sign_act(self.root, "orso", self.keys["orso"], attest.RETRACT_KIND,
                                 ref="orso#%d" % c["seq"],
                                 body={"retracts": c["digest"], "retracts_seq": c["seq"],
                                       "reason": "segunda, escrita a mano"})
        m = attest.retractions(self.root, "orso")
        self.assertEqual(m[c["digest"]]["seq"], first["seq"])
        self.assertNotEqual(m[c["digest"]]["seq"], second["seq"])


class TraceAndVerifyConsultIt(Enrolled):

    def test_trace_marks_the_row_retracted_and_names_the_retracting_seq(self):
        c = self.commit()
        r = self.retract(seq=c["seq"])
        t = attest.trace(self.root, "orso")
        row = next(x for x in t["rows"] if x["seq"] == c["seq"])
        self.assertTrue(row["retracted"])
        self.assertEqual(row["retracted_by"], r["seq"])

    def test_complete_keeps_its_own_meaning_independent_of_retracted(self):
        """Design T-406, verbatim: a retracted row reads complete: true, retracted: true --
        properly signed, properly anchored, and disowned. Collapsing the two destroys
        information."""
        c = self.commit()
        self.retract(seq=c["seq"])
        t = attest.trace(self.root, "orso")
        row = next(x for x in t["rows"] if x["seq"] == c["seq"])
        self.assertTrue(row["complete"])
        self.assertTrue(row["retracted"])

    def test_an_unretracted_row_is_not_marked_retracted(self):
        self.commit()
        t = attest.trace(self.root, "orso")
        self.assertFalse(any(r["retracted"] for r in t["rows"]))

    def test_the_retracting_act_itself_is_not_marked_retracted(self):
        c = self.commit()
        self.retract(seq=c["seq"])
        t = attest.trace(self.root, "orso")
        retract_row = next(x for x in t["rows"] if x["kind"] == attest.RETRACT_KIND)
        self.assertFalse(retract_row["retracted"])

    def test_counts_are_reported_raw_and_distinct(self):
        c = self.commit()
        self.retract(seq=c["seq"])
        t = attest.trace(self.root)
        self.assertIn("retracted_raw", t)
        self.assertIn("retracted_distinct", t)
        self.assertEqual(t["retracted_raw"], 1)
        self.assertEqual(t["retracted_distinct"], 1)

    def test_verify_name_reports_the_retraction_and_does_not_call_it_a_signature_failure(self):
        c = self.commit()
        r = self.retract(seq=c["seq"], reason="era falso")
        v = attest.verify_name(self.root, "orso")
        self.assertEqual(v["signature_failures"], [])
        self.assertEqual(len(v["retracted"]), 1)
        self.assertEqual(v["retracted"][0]["seq"], c["seq"])
        self.assertEqual(v["retracted"][0]["retracted_by_seq"], r["seq"])
        self.assertEqual(v["retracted"][0]["reason"], "era falso")

    def test_chain_renders_the_retraction_inline(self):
        c = self.commit()
        self.retract(seq=c["seq"])
        r = self.run_cli("chain", "--name", "orso")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        target_line = next(ln for ln in lines
                           if ln.strip().startswith(str(c["seq"]) + " "))
        self.assertIn("RETRACTED", target_line)

    def test_trace_renders_through_the_cli_without_crashing(self):
        c = self.commit()
        self.retract(seq=c["seq"])
        r = self.run_cli("trace", "--name", "orso")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("retractados", r.stdout)


class TheD17Limit(Enrolled):
    """What this design ACCEPTS rather than fixes (design doc, weakness #2): same key,
    same name -- a thief who holds orso's key can file a false retraction of a TRUE act,
    exactly as it could file a false act in the first place. DIS-2 is the entire defence:
    the forgery is credited to orso, not to the thief, and it can only damage orso's own
    record."""

    def test_a_thief_with_the_stolen_key_retracts_a_true_act_and_it_verifies_clean(self):
        stolen = self.keys["orso"]              # read by a party that is not orso
        c = attest.sign_act(self.root, "orso", stolen, "commit", ref="legitimo")
        r = attest.retract(self.root, "orso", stolen, c["seq"], "mentira del ladron")
        v = attest.verify_name(self.root, "orso")
        self.assertEqual(v["signature_failures"], [],
                         "the forged retraction verifies cleanly under orso's own key; "
                         "D-17 is untouched and this design does not claim otherwise")
        self.assertEqual(v["retracted"][0]["seq"], c["seq"])
        t = attest.trace(self.root, "orso")
        rows = [x for x in t["rows"] if x["seq"] == c["seq"]]
        self.assertTrue(rows[0]["complete"], "a forged retraction traces COMPLETE; the "
                        "signature is a fact about the key, not about who typed it")
        # DIS-2: the forged act is credited to orso -- there is no field anywhere naming
        # the thief, because the chain only records who the KEY says signed it.
        self.assertEqual(r["name"], "orso")

    def test_the_design_states_this_limit_is_accepted_not_fixed(self):
        # RETRACT_KIND is a plain str; `RETRACT_KIND.__doc__` would be str's builtin
        # docstring, not this module's -- the exact vacuous-match trap
        # test_attest_intent.py's `attribute_docstring` helper exists to avoid. Parse the
        # literal string constant sitting directly under the assignment instead.
        src = ATTEST_PY.read_text(encoding="utf-8")
        tree = ast.parse(src)
        found = None
        for i, node in enumerate(tree.body):
            targets = getattr(node, "targets", [])
            if (isinstance(node, ast.Assign) and targets
                    and isinstance(targets[0], ast.Name) and targets[0].id == "RETRACT_KIND"):
                nxt = tree.body[i + 1]
                found = nxt.value.value
                break
        self.assertIsNotNone(found, "RETRACT_KIND has no attached docstring")
        self.assertIn("ACCEPTED", found)
        self.assertIn("D-17", found)
        self.assertIn("DIS-2", found)


class OutputShapeGuard(unittest.TestCase):
    """PR-022 clause 4: NO CONSEQUENCE ATTACHES. This pins it the way test_westphalia_kpi.py
    pins its own clause-4-shaped claims -- by parsing the source, not by trusting a comment.

    THE CLAIM: no function in this module that computes a privilege, a ceiling, an expiry,
    a contested/forked verdict, or a delegation reads `retracts`, `retracts_seq`, `reason`,
    `retracted` or `retracted_by` anywhere in its body. Those five identifiers appear ONLY
    inside the small set of functions whose entire purpose is reporting the retraction:
    `retract`, `retractions`, `trace`, `verify_name`, and the CLI's own `chain`/`_render_*`
    rendering. Everything else in the module must be blind to them.
    """

    RETRACTION_FIELDS = {"retracts", "retracts_seq", "retracted", "retracted_by",
                         "retracted_by_seq"}

    ALLOWED_FUNCTIONS = {
        "retract", "retractions", "trace", "verify_name", "main",
        "_render_trace", "_render",
    }

    CONSEQUENCE_BEARING = {
        "held_kinds", "effective_expiry", "sign_act", "grant_privilege",
        "delegated_keys", "signing_keys", "verify_all", "forks", "open_intents",
        "declare_intent", "_match_intent", "intent_binds_ref", "head", "enrolled_keys",
        "delegations",
    }

    def _function_sources(self):
        src = ATTEST_PY.read_text(encoding="utf-8")
        tree = ast.parse(src)
        out = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[node.name] = node
        return out

    def _body_mentions_a_retraction_field(self, fn_node):
        for node in ast.walk(fn_node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in self.RETRACTION_FIELDS:
                    return node.value
            if isinstance(node, ast.Name) and node.id in self.RETRACTION_FIELDS:
                return node.id
            if isinstance(node, ast.Attribute) and node.attr in self.RETRACTION_FIELDS:
                return node.attr
        return None

    def test_every_consequence_bearing_function_exists_in_the_source(self):
        """Negative control on the guard's own target list: if a name here is stale (the
        function was renamed or removed), the guard below would vacuously pass on nothing
        rather than checking anything, which is exactly how the westphalia attack slipped
        past four earlier guards."""
        fns = self._function_sources()
        missing = self.CONSEQUENCE_BEARING - set(fns)
        self.assertEqual(missing, set(),
                         "the guard's target list names a function that does not exist; "
                         "it would be checking nothing")

    def test_no_consequence_bearing_function_reads_a_retraction_field(self):
        fns = self._function_sources()
        hits = {}
        for name in self.CONSEQUENCE_BEARING:
            found = self._body_mentions_a_retraction_field(fns[name])
            if found:
                hits[name] = found
        self.assertEqual(hits, {},
                         "a function that computes a privilege, ceiling, expiry, fork "
                         "verdict or delegation reads a retraction field -- PR-022 clause 4 "
                         "is violated: %r" % hits)

    def test_the_guard_itself_can_detect_a_planted_violation(self):
        """NEGATIVE CONTROL for the test above, same discipline test_westphalia_kpi.py
        applies: inject a read of a retraction field into a consequence-bearing function in
        a PATCHED COPY of the source (never the live file under lock) and confirm the AST
        walk catches it."""
        with tempfile.TemporaryDirectory() as tmp:
            patched = pathlib.Path(tmp) / "attest_patched.py"
            src = ATTEST_PY.read_text(encoding="utf-8")
            needle = "def held_kinds(root, name) -> set:"
            self.assertIn(needle, src)
            injected = src.replace(
                needle,
                needle + "\n    _planted_violation = locals().get('retracted', None)  "
                        "# injected by test\n",
                1)
            patched.write_text(injected, encoding="utf-8")
            tree = ast.parse(patched.read_text(encoding="utf-8"))
            fns = {n.name: n for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            found = self._body_mentions_a_retraction_field(fns["held_kinds"])
            self.assertEqual(found, "retracted",
                             "the guard failed to catch a planted read of a retraction "
                             "field; it would be checking nothing in the real test")

    def test_the_fields_this_guard_watches_actually_appear_somewhere(self):
        """Another vacuity control: if RETRACTION_FIELDS named strings that never occur in
        the module at all, every assertion above would pass for free."""
        src = ATTEST_PY.read_text(encoding="utf-8")
        for field in self.RETRACTION_FIELDS - {"retracted_by_seq"}:
            self.assertIn(field, src, "%r never appears in attest.py at all" % field)

    def test_the_fields_live_exactly_in_the_reporting_functions_not_nowhere(self):
        """POSITIVE control, paired with the vacuity control above: the allowlist is not
        'everything is allowed' -- it is the specific small set of functions whose job is
        reporting the retraction, and the fields really do live there and not in some
        fourth place this guard never looks at."""
        fns = self._function_sources()
        reporting = {"retract", "retractions", "trace", "verify_name"}
        live_in = {name for name in reporting
                  if self._body_mentions_a_retraction_field(fns[name])}
        self.assertEqual(live_in, reporting,
                         "a reporting function that should carry a retraction field does "
                         "not; %r is missing it" % (reporting - live_in))


class BehaviouralClauseFourGuard(Enrolled):
    """The AST guard above pins the source; this pins the OBSERVABLE BEHAVIOUR, the same
    discipline T-410 asks for: validate the reported output, not only identifier names.
    Retracting an act must not change what a name may sign, for how long, or whether its
    chain is reported contested.
    """

    def test_retracting_an_act_does_not_change_held_kinds(self):
        c = self.commit()
        before = attest.held_kinds(self.root, "orso")
        self.retract(seq=c["seq"])
        after = attest.held_kinds(self.root, "orso")
        self.assertEqual(before, after)

    def test_retracting_an_act_does_not_change_effective_expiry(self):
        c = self.commit()
        before = attest.effective_expiry(self.root, "orso")
        self.retract(seq=c["seq"])
        after = attest.effective_expiry(self.root, "orso")
        self.assertEqual(before, after)

    def test_retracting_an_act_does_not_mark_the_chain_contested(self):
        c = self.commit()
        self.retract(seq=c["seq"])
        v = attest.verify_name(self.root, "orso")
        self.assertFalse(v["contested"])
        self.assertEqual(v["forks"], [])

    def test_a_name_may_still_sign_privileged_acts_after_retracting_something(self):
        c = self.commit()
        self.retract(seq=c["seq"])
        attest.declare_intent(self.root, "orso", self.keys["orso"], "verdict", "T-1", "x")
        a = attest.sign_act(self.root, "orso", self.keys["orso"], "verdict",
                            ref="aurelia#1", task="T-1")
        self.assertTrue(a["privileged"])


class AppendOnly(Enrolled):

    def test_retracting_does_not_remove_or_rewrite_the_target_file(self):
        c = self.commit()
        before = pathlib.Path(c["path"]).read_bytes()
        self.retract(seq=c["seq"])
        after = pathlib.Path(c["path"]).read_bytes()
        self.assertEqual(before, after, "the target act's file must be byte-identical; "
                         "retraction is a NEW act, never an edit to an old one")

    def test_the_target_signature_file_is_untouched_too(self):
        c = self.commit()
        sig_path = pathlib.Path(c["path"]).with_suffix(".json.sig")
        before = sig_path.read_bytes()
        self.retract(seq=c["seq"])
        self.assertEqual(sig_path.read_bytes(), before)

    def test_a_direct_reader_of_the_target_file_still_sees_only_the_original_act(self):
        """The limit the design names rather than glosses: `cat`ing the file directly does
        not learn of the retraction. Only the tools (trace/verify_name/chain) do."""
        c = self.commit(ref="verdadero")
        self.retract(seq=c["seq"])
        raw = json.loads(pathlib.Path(c["path"]).read_text(encoding="utf-8"))
        self.assertEqual(raw["ref"], "verdadero")
        self.assertNotIn("retracted", raw)


if __name__ == "__main__":
    unittest.main()
