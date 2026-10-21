"""T-466: the commit act (T-436 section 1), answer and appeal (T-452 sections 2 and 5),
and file_claim (T-436 section 5 / T-452 section 1).

Ratified: operator-rulings-2026-10-08.md decision 2 (damages are operational budget,
never reputation) and operator-rulings-2026-10-21.md decision 3 (suits, notice, an
agentic judge, appeal to the operator). NOT ratified (decision 3's own text, "still owed
by the operator"): the objection window, the pursue-or-lapse window, and the damages cap.
Nothing below computes any of the three -- see WINDOWS_NOT_RATIFIED and the guard class
at the bottom that pins it by parsing the source, not by trusting this sentence.

Every fixture lives in a temporary directory, never the live `.harness/acts` (same
discipline as test_attest_retraction.py and test_attest_intent.py).
"""
import ast
import hashlib
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
    """A real warrant, signed by a real throwaway root key, issuing two real names, in a
    temporary directory. Never the live registry."""

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

    def commit(self, name="orso", task="T-1", parameter="budget", value="1000"):
        return attest.commit(self.root, name, self.keys[name], task, parameter, value)

    def declare_contest_intent(self, name, task, for_ref, declares="porque si"):
        return attest.declare_intent(self.root, name, self.keys[name], "contest", task,
                                     declares, for_ref=for_ref)

    def acts_on(self, name):
        return sorted(p.name for p in attest.acts_dir(self.root, name).glob("*.json"))

    def run_cli(self, *argv):
        return subprocess.run(
            [sys.executable, str(ATTEST_PY), "--root", str(self.root)] + list(argv),
            capture_output=True, text=True)

    def _tree_digest(self):
        """A single digest over every file under the harness root's acts/ directory PLUS
        the event log, by name and content. Used to prove a refusal wrote nothing at all,
        anywhere -- not just that one expected file is missing."""
        h = hashlib.sha256()
        acts_dir = self.root / "acts"
        paths = []
        if acts_dir.exists():
            paths.extend(sorted(acts_dir.rglob("*")))
        events = self.root / "events.jsonl"
        if events.exists():
            paths.append(events)
        for p in paths:
            if p.is_file():
                h.update(str(p.relative_to(self.root)).encode("utf-8"))
                h.update(p.read_bytes())
        return h.hexdigest()


# --------------------------------------------------------------------- kinds

class TheKindsAreUnprivileged(Enrolled):

    def test_the_three_kind_strings(self):
        self.assertEqual(attest.COMMIT_KIND, "commit")
        self.assertEqual(attest.ANSWER_KIND, "answer")
        self.assertEqual(attest.APPEAL_KIND, "appeal")

    def test_none_joins_privileged_kinds(self):
        self.assertNotIn(attest.COMMIT_KIND, attest.PRIVILEGED_KINDS)
        self.assertNotIn(attest.ANSWER_KIND, attest.PRIVILEGED_KINDS)
        self.assertNotIn(attest.APPEAL_KIND, attest.PRIVILEGED_KINDS)

    def test_privileged_kinds_set_is_exactly_what_it_was(self):
        """Pins the set unchanged, per the acceptance criterion's own wording."""
        self.assertEqual(attest.PRIVILEGED_KINDS,
                         frozenset({"verdict", "contest", "distinguish", "grant"}))

    def test_a_commit_act_needs_no_declared_intent(self):
        self.assertEqual(attest.open_intents(self.root, "orso"), [])
        c = self.commit()
        self.assertFalse(c["privileged"])
        self.assertEqual(c["intent"], "")

    def test_an_answer_act_needs_no_declared_intent(self):
        a = attest.answer(self.root, "orso", self.keys["orso"], "T-1", "C-1", "no es cierto")
        self.assertFalse(a["privileged"])
        self.assertEqual(a["intent"], "")

    def test_an_appeal_act_needs_no_declared_intent(self):
        a = attest.appeal(self.root, "orso", self.keys["orso"], "T-1", "V-1", "injusto")
        self.assertFalse(a["privileged"])
        self.assertEqual(a["intent"], "")


# --------------------------------------------------------------------- commit

class TheCommitAct(Enrolled):

    def test_operational_parameters_is_pr060_clause1s_six(self):
        self.assertEqual(attest.OPERATIONAL_PARAMETERS,
                         frozenset({"task", "order", "budget", "deadline", "engine",
                                    "iteration_bound"}))

    def test_a_commit_records_the_parameter_and_value(self):
        c = self.commit(parameter="budget", value="4000")
        body = json.loads(pathlib.Path(c["path"]).read_text(encoding="utf-8"))["body"]
        self.assertEqual(body["parameter"], "budget")
        self.assertEqual(body["value"], "4000")

    def test_each_of_the_six_parameters_is_accepted(self):
        for i, p in enumerate(sorted(attest.OPERATIONAL_PARAMETERS)):
            c = self.commit(task="T-%d" % i, parameter=p, value="x")
            self.assertEqual(c["privileged"], False)

    def test_a_parameter_outside_the_list_is_refused(self):
        with self.assertRaises(attest.AttestError) as e:
            self.commit(parameter="standing")
        self.assertIn("standing", str(e.exception))

    def test_a_blank_task_is_refused(self):
        with self.assertRaises(attest.AttestError) as e:
            self.commit(task="")
        self.assertIn("task", str(e.exception).lower())

    def test_a_blank_value_is_refused(self):
        with self.assertRaises(attest.AttestError) as e:
            self.commit(value="  ")
        self.assertIn("value", str(e.exception).lower())

    def test_refusals_write_nothing(self):
        before = self.acts_on("orso")
        for kwargs in ({"parameter": "standing"}, {"task": ""}, {"value": " "}):
            with self.assertRaises(attest.AttestError):
                self.commit(**kwargs)
        self.assertEqual(self.acts_on("orso"), before)

    def test_the_cli_exposes_commit(self):
        r = self.run_cli("commit", "--name", "orso", "--key", str(self.keys["orso"]),
                         "--task", "T-9", "--parameter", "engine", "--value", "claude")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        body = json.loads(pathlib.Path(out["path"]).read_text(encoding="utf-8"))["body"]
        self.assertEqual(body["parameter"], "engine")
        self.assertEqual(body["value"], "claude")

    def test_the_cli_refuses_an_unrecognized_parameter(self):
        r = self.run_cli("commit", "--name", "orso", "--key", str(self.keys["orso"]),
                         "--task", "T-9", "--parameter", "standing", "--value", "x")
        self.assertEqual(r.returncode, 2)
        self.assertIn("standing", r.stderr)

    def test_the_commit_body_never_fixes_a_consequence(self):
        c = self.commit()
        body = json.loads(pathlib.Path(c["path"]).read_text(encoding="utf-8"))["body"]
        self.assertIn("THIS RECORD AUTHORIZES NO CONSEQUENCE NOW", body["PR_060_CLAUSE_6"])


# --------------------------------------------------------------- answer / appeal

class AnswerAndAppeal(Enrolled):

    def test_a_blank_disputes_is_refused(self):
        with self.assertRaises(attest.AttestError) as e:
            attest.answer(self.root, "orso", self.keys["orso"], "T-1", "C-1", "   ")
        self.assertIn("disputes", str(e.exception).lower())

    def test_a_blank_grounds_is_refused(self):
        with self.assertRaises(attest.AttestError) as e:
            attest.appeal(self.root, "orso", self.keys["orso"], "T-1", "V-1", "")
        self.assertIn("grounds", str(e.exception).lower())

    def test_refusals_write_nothing(self):
        before = self.acts_on("orso")
        with self.assertRaises(attest.AttestError):
            attest.answer(self.root, "orso", self.keys["orso"], "T-1", "C-1", "")
        with self.assertRaises(attest.AttestError):
            attest.appeal(self.root, "orso", self.keys["orso"], "T-1", "V-1", "")
        self.assertEqual(self.acts_on("orso"), before)

    def test_every_act_carries_the_not_ratified_marker(self):
        a = attest.answer(self.root, "orso", self.keys["orso"], "T-1", "C-1", "fuente mala")
        body_a = json.loads(pathlib.Path(a["path"]).read_text(encoding="utf-8"))["body"]
        self.assertIn("NOT RATIFIED", body_a["NUMBERS_NOT_RATIFIED"])
        p = attest.appeal(self.root, "orso", self.keys["orso"], "T-1", "V-1", "injusto")
        body_p = json.loads(pathlib.Path(p["path"]).read_text(encoding="utf-8"))["body"]
        self.assertIn("NOT RATIFIED", body_p["NUMBERS_NOT_RATIFIED"])

    def test_the_cli_exposes_both(self):
        r = self.run_cli("answer", "--name", "orso", "--key", str(self.keys["orso"]),
                         "--task", "T-9", "--ref", "C-1", "--disputes", "no es correcto")
        self.assertEqual(r.returncode, 0, r.stderr)
        r2 = self.run_cli("appeal", "--name", "orso", "--key", str(self.keys["orso"]),
                          "--task", "T-9", "--ref", "V-1", "--grounds", "injusto")
        self.assertEqual(r2.returncode, 0, r2.stderr)


# --------------------------------------------------------------- file_claim

class FileClaimOutcomeA(Enrolled):
    """No gap: nothing is written, anywhere."""

    def test_agreement_refuses_and_writes_nothing_hashed_before_and_after(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        before = self._tree_digest()
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              "4000", "usage_report.py", task="T-1")
        self.assertIn("no gap", str(e.exception))
        after = self._tree_digest()
        self.assertEqual(before, after,
                         "Outcome A must leave acts/ and the event log byte-identical")

    def test_agreement_refuses_even_with_no_prior_intent_and_no_held_contest_kind(self):
        """Outcome A must refuse BEFORE sign_act is ever reached, so it does not matter
        that the claimant has no open intent for `contest` and no task at all declared --
        none of that machinery is touched on the no-gap path."""
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        self.assertEqual(attest.open_intents(self.root, "aurelia"), [])
        with self.assertRaises(attest.AttestError):
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              "4000", "usage_report.py")


class FileClaimOutcomeB(Enrolled):
    """The gap replays: exactly one contest act, naming the respondent, the commit
    digest, the observed source and the gap."""

    def test_a_true_gap_files_exactly_one_contest_act(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        self.declare_contest_intent("aurelia", "T-1", for_ref="orso#%d" % c["seq"])
        before = self.acts_on("aurelia")
        result = attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                   c["seq"], "9000", "usage_report.py", task="T-1")
        self.assertTrue(result["privileged"])
        after = self.acts_on("aurelia")
        self.assertEqual(len(after), len(before) + 1, "exactly one act must be filed")
        act = json.loads(pathlib.Path(result["path"]).read_text(encoding="utf-8"))
        self.assertEqual(act["kind"], "contest")
        self.assertEqual(act["ref"], "orso#%d" % c["seq"])
        reason = act["body"]["reason"]
        self.assertIn(c["digest"], reason)
        self.assertIn("9000", reason)
        self.assertIn("usage_report.py", reason)
        self.assertIn("4000", reason)

    def test_the_contest_act_lands_on_the_claimants_own_chain_not_the_respondents(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        self.declare_contest_intent("aurelia", "T-1", for_ref="orso#%d" % c["seq"])
        before_orso = self.acts_on("orso")
        attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                          "9000", "usage_report.py", task="T-1")
        self.assertEqual(self.acts_on("orso"), before_orso,
                         "filing a claim must never write to the RESPONDENT's own chain")

    def test_the_cli_exposes_file_claim(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        self.declare_contest_intent("aurelia", "T-1", for_ref="orso#%d" % c["seq"])
        r = self.run_cli("file-claim", "--by", "aurelia", "--key",
                         str(self.keys["aurelia"]), "--name", "orso", "--seq",
                         str(c["seq"]), "--observed-value", "9000", "--source",
                         "usage_report.py", "--task", "T-1")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["name"], "aurelia")

    def test_the_cli_refuses_a_non_replaying_claim(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        r = self.run_cli("file-claim", "--by", "aurelia", "--key",
                         str(self.keys["aurelia"]), "--name", "orso", "--seq",
                         str(c["seq"]), "--observed-value", "4000", "--source",
                         "usage_report.py", "--task", "T-1")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no gap", r.stderr)


class FileClaimInheritsPrivilegedGuards(Enrolled):
    """Outcome B calls `contest`, so D3a's guards (held kinds, --task, intent first) are
    inherited unchanged -- this class proves the inheritance rather than asserting it."""

    def test_a_gap_with_no_task_is_refused_exactly_as_contest_refuses_it(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              "9000", "usage_report.py", task=None)
        self.assertIn("--task is required", str(e.exception))

    def test_a_gap_with_no_prior_intent_is_refused_and_writes_nothing(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        before = self.acts_on("aurelia")
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              "9000", "usage_report.py", task="T-1")
        self.assertIn("no open intent", str(e.exception))
        self.assertEqual(self.acts_on("aurelia"), before)

    def test_a_claimant_with_no_held_contest_kind_gets_the_delegation_ceiling_refusal(self):
        """A delegated identity granted only `verdict` (never `contest`) cannot reach
        Outcome B at all, and the refusal message names the kind it lacks -- the same
        message any other delegate reaching past D3b's ceiling gets, not a bespoke or
        vaguer one from this function."""
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        dk = _keygen(pathlib.Path(self._tmp.name) / "keys" / "delegate", "delegate")
        attest.declare_intent(self.root, "aurelia", self.keys["aurelia"], "grant", "T-1",
                              "delegating verdict only")
        attest.grant_privilege(self.root, "aurelia", self.keys["aurelia"], "delegado",
                               dk.with_suffix(".pub").read_text(encoding="utf-8").strip(),
                               ["verdict"], "2099-01-01T00:00:00Z", "T-1")
        self.keys["delegado"] = dk
        self.declare_contest_intent("delegado", "T-1", for_ref="orso#%d" % c["seq"])
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "delegado", dk, "orso", c["seq"], "9000",
                              "usage_report.py", task="T-1")
        msg = str(e.exception)
        self.assertIn("DELEGATION CEILING", msg)
        self.assertIn("contest", msg)


class FileClaimReferenceRefusals(Enrolled):

    def test_a_seq_not_on_the_respondents_own_chain_is_refused(self):
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", 999,
                              "9000", "usage_report.py", task="T-1")
        self.assertIn("no act at seq", str(e.exception))

    def test_a_reference_to_a_non_commit_act_is_refused(self):
        other = attest.sign_act(self.root, "orso", self.keys["orso"], "filing", ref="x")
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                              other["seq"], "9000", "usage_report.py", task="T-1")
        self.assertIn("not", str(e.exception))
        self.assertIn("commit", str(e.exception))

    def test_an_unsigned_commit_act_is_refused(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        pathlib.Path(c["path"]).with_suffix(".json.sig").unlink()
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              "9000", "usage_report.py", task="T-1")
        self.assertIn("does not verify", str(e.exception))

    def test_these_refusals_write_nothing(self):
        before = self._tree_digest()
        for seq in (999,):
            with self.assertRaises(attest.AttestError):
                attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", seq,
                                  "9000", "usage_report.py", task="T-1")
        after = self._tree_digest()
        self.assertEqual(before, after)


# -------------------------------------------------------------- the BYPASS residual

class TheRawContestVerbStillWrites(Enrolled):
    """T-436's own BYPASS residual, named as open, not closed: `attest.py contest` stays
    directly callable, with no gap-check, and writes unconditionally. This pins that it
    still writes, so a reader does not mistake file_claim's existence for having closed
    it."""

    def test_calling_contest_directly_writes_even_with_no_real_gap(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        self.declare_contest_intent("aurelia", "T-1", for_ref="orso#%d" % c["seq"])
        before = self.acts_on("aurelia")
        # No gap-check anywhere in this call -- contest() takes a free-text reason only.
        result = attest.contest(self.root, "aurelia", self.keys["aurelia"], "orso",
                                c["seq"], "alegacion sin verificar ninguna brecha",
                                task="T-1")
        after = self.acts_on("aurelia")
        self.assertEqual(len(after), len(before) + 1,
                         "the raw verb is NOT gated -- a falsifier for 'bypass is closed'")
        act = json.loads(pathlib.Path(result["path"]).read_text(encoding="utf-8"))
        self.assertEqual(act["ref"], "orso#%d" % c["seq"])

    def test_the_cli_raw_contest_verb_is_still_present_and_unguarded(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        self.declare_contest_intent("aurelia", "T-1", for_ref="orso#%d" % c["seq"])
        r = self.run_cli("contest", "--by", "aurelia", "--key", str(self.keys["aurelia"]),
                         "--name", "orso", "--seq", str(c["seq"]), "--reason",
                         "sin brecha real", "--task", "T-1")
        self.assertEqual(r.returncode, 0, r.stderr)


# ----------------------------------------------------------------- output-shape guards

class OutputShapeGuard(unittest.TestCase):
    """PR-060 clause 6 / PR-022 clause 4 / decision 3's own 'still owed' list, pinned by
    parsing the source rather than by trusting a docstring -- the same discipline
    test_attest_retraction.py's OutputShapeGuard class applies to retraction fields.

    THE CLAIM: none of `commit`, `answer`, `appeal` or `file_claim` computes a deadline, a
    window, a lapse, a debit or a damages amount (no arithmetic, no ordering comparison
    against a wall-clock or numeric bound anywhere in their bodies), and none reads or
    writes a reputation figure.
    """

    CONTRACT_FUNCTIONS = ("commit", "answer", "appeal", "file_claim")

    FORBIDDEN_IDENTIFIERS = {"reputation", "reputation_score", "standing", "debit",
                             "damages_amount", "lapse_at", "objection_deadline"}

    def _function_sources(self):
        src = ATTEST_PY.read_text(encoding="utf-8")
        tree = ast.parse(src)
        out = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[node.name] = node
        return out

    def test_the_four_functions_exist(self):
        fns = self._function_sources()
        missing = set(self.CONTRACT_FUNCTIONS) - set(fns)
        self.assertEqual(missing, set(),
                         "the guard's target list names a function that does not exist")

    def test_none_of_the_four_contains_arithmetic_or_ordering_comparison(self):
        """No BinOp (no +, -, *, / of any value) and no <, >, <=, >= anywhere in these
        four functions' bodies. A window, a lapse or a debit cannot be computed without
        one of those; their total absence is the mechanical form of 'nothing is
        computed'."""
        fns = self._function_sources()
        offenders = {}
        for name in self.CONTRACT_FUNCTIONS:
            for node in ast.walk(fns[name]):
                if isinstance(node, ast.BinOp):
                    offenders.setdefault(name, []).append("BinOp")
                if isinstance(node, ast.Compare):
                    for op in node.ops:
                        if isinstance(op, (ast.Lt, ast.Gt, ast.LtE, ast.GtE)):
                            offenders.setdefault(name, []).append(type(op).__name__)
        self.assertEqual(offenders, {},
                         "a function that should only compare for exact equality "
                         "contains ordering/arithmetic, which is how a window or a "
                         "damages amount would be computed: %r" % offenders)

    def test_none_of_the_four_mentions_a_forbidden_identifier(self):
        fns = self._function_sources()
        hits = {}
        for name in self.CONTRACT_FUNCTIONS:
            for node in ast.walk(fns[name]):
                val = None
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    val = node.value
                elif isinstance(node, ast.Name):
                    val = node.id
                elif isinstance(node, ast.Attribute):
                    val = node.attr
                if val in self.FORBIDDEN_IDENTIFIERS:
                    hits.setdefault(name, []).append(val)
        self.assertEqual(hits, {}, "a contracts function reads/writes a forbidden "
                                   "reputation or computed-consequence field: %r" % hits)

    def test_the_guard_catches_a_planted_ordering_comparison(self):
        """Negative control: inject a '>' comparison into a PATCHED COPY (never the live
        file) and confirm the AST walk catches it, the same discipline
        test_attest_retraction.py applies to its own planted-violation control."""
        with tempfile.TemporaryDirectory() as tmp:
            patched = pathlib.Path(tmp) / "attest_patched.py"
            src = ATTEST_PY.read_text(encoding="utf-8")
            needle = "def commit(root, name, key_path, task, parameter, value) -> dict:"
            self.assertIn(needle, src)
            injected = src.replace(
                needle,
                needle + "\n    _planted = 1 if len(str(task)) > 9999 else 0  # injected\n",
                1)
            patched.write_text(injected, encoding="utf-8")
            tree = ast.parse(patched.read_text(encoding="utf-8"))
            fns = {n.name: n for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            found = any(isinstance(op, ast.Gt)
                       for node in ast.walk(fns["commit"])
                       if isinstance(node, ast.Compare)
                       for op in node.ops)
            self.assertTrue(found, "the guard failed to catch a planted ordering "
                                   "comparison; it would be checking nothing for real")

    def test_windows_not_ratified_is_the_literal_currency_py_pattern(self):
        self.assertIn("NOT RATIFIED", attest.WINDOWS_NOT_RATIFIED)
        self.assertIn("decision 3", attest.WINDOWS_NOT_RATIFIED)

    def test_commit_and_answer_and_appeal_bodies_carry_the_not_ratified_marker(self):
        """Behavioural pair to the AST guard above: where a number would appear, the
        literal string appears instead, in the actual written body -- not only in a
        docstring that could drift from the code."""
        src = ATTEST_PY.read_text(encoding="utf-8")
        fns = self._function_sources()
        for name in ("commit", "answer", "appeal"):
            calls = [n for n in ast.walk(fns[name]) if isinstance(n, ast.Call)]
            self.assertTrue(
                any("WINDOWS_NOT_RATIFIED" in ast.dump(c) for c in calls),
                "%s's body does not reference WINDOWS_NOT_RATIFIED" % name)


if __name__ == "__main__":
    unittest.main()
