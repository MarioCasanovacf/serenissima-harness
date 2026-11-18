"""T-466/T-472: the commit act (T-436 section 1), answer and appeal (T-452 sections 2
and 5), and file_claim (T-436 section 5 / T-452 section 1 / T-472).

Ratified: operator-rulings-2026-10-08.md decision 2 (damages are operational budget,
never reputation) and operator-rulings-2026-10-21.md decision 3 (suits, notice, an
agentic judge, appeal to the operator). NOT ratified (decision 3's own text, "still owed
by the operator"): the objection window, the pursue-or-lapse window, and the damages cap.
Nothing below computes any of the three -- see WINDOWS_NOT_RATIFIED and the guard class
at the bottom that pins it by parsing the source, not by trusting this sentence.

T-472: `file_claim` no longer takes `observed_value`/`source` from the caller -- the
coordinator's finding on T-466 was that a claimant could type any value and defeat the
gap check. The observed value now comes from `attest.PARAMETER_READERS`, one reader per
parameter, reading events.jsonl (deadline, iteration_bound) or usage_report.py (budget,
engine); `task` and `order` have no reader and are always refused. The FileClaim* classes
below write synthetic events.jsonl lines or monkeypatch `usage_report.collect_units`
directly, rather than running real goal_mode.py/blackboard.py/transcripts, because none
of those tools are parameterized by a throwaway `--root` the way attest.py's own acts are.

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
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
ATTEST_PY = ROOT / ".harness" / "bin" / "attest.py"
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import attest  # noqa: E402
import usage_report  # noqa: E402
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

    def write_event(self, **fields):
        """Append one synthetic events.jsonl line under this fixture's own root -- the
        same file `attest._emit` writes an act's own event to for a non-live root
        (`w.is_live(self.root)` is False here), so a reader and this fixture agree on
        which file is "the" event log without needing real goal_mode.py/blackboard.py
        runs scoped to a throwaway root (neither tool accepts one)."""
        rec = {"ts": "2026-10-21T00:00:00Z", "agent": "test"}
        rec.update(fields)
        path = self.root / "events.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def fake_usage_unit(self, tasks, models, in_=100, out=50, cache_write=0, cache_read=0):
        return {"tasks": list(tasks), "models": list(models), "in": in_, "out": out,
                "cache_write": cache_write, "cache_read": cache_read}

    def patch_usage(self, units):
        """`attest._read_budget`/`_read_engine` lazily `import usage_report as ur` and
        call `ur.collect_units(ur.project_transcript_dir())` -- patching this test
        module's own `usage_report.collect_units` reaches the identical module object
        (sys.modules caches it), so no subprocess is needed to exercise either reader."""
        return mock.patch.object(usage_report, "collect_units", return_value=units)

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
    """No gap: nothing is written, anywhere. The observed value comes from
    `attest.PARAMETER_READERS["budget"]`, via a mocked `usage_report.collect_units` --
    never a caller argument, since T-472 removed that argument entirely."""

    def test_agreement_refuses_and_writes_nothing_hashed_before_and_after(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        before = self._tree_digest()
        with self.patch_usage([self.fake_usage_unit(["T-1"], ["claude-sonnet-5"],
                                                     in_=4000, out=0)]):
            with self.assertRaises(attest.AttestError) as e:
                attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                  c["seq"], task="T-1")
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
        with self.patch_usage([self.fake_usage_unit(["T-1"], ["claude-sonnet-5"],
                                                     in_=4000, out=0)]):
            with self.assertRaises(attest.AttestError):
                attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                  c["seq"])


class FileClaimOutcomeB(Enrolled):
    """The gap replays: exactly one contest act, naming the respondent, the commit
    digest, the observed source and the gap."""

    def test_a_true_gap_files_exactly_one_contest_act(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        self.declare_contest_intent("aurelia", "T-1", for_ref="orso#%d" % c["seq"])
        before = self.acts_on("aurelia")
        with self.patch_usage([self.fake_usage_unit(["T-1"], ["claude-sonnet-5"],
                                                     in_=9000, out=0)]):
            result = attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                       c["seq"], task="T-1")
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
        with self.patch_usage([self.fake_usage_unit(["T-1"], ["claude-sonnet-5"],
                                                     in_=9000, out=0)]):
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertEqual(self.acts_on("orso"), before_orso,
                         "filing a claim must never write to the RESPONDENT's own chain")

    def test_the_cli_exposes_file_claim(self):
        """CLI exercise uses `iteration_bound`, not `budget`: the CLI runs attest.py in a
        SEPARATE PROCESS, so an in-process mock of `usage_report.collect_units` cannot
        reach it -- events.jsonl, written to `self.root` directly, crosses that process
        boundary because it is a real file under `--root`."""
        c = self.commit(name="orso", task="T-1", parameter="iteration_bound", value="4")
        self.declare_contest_intent("aurelia", "T-1", for_ref="orso#%d" % c["seq"])
        self.write_event(event="goal_abandoned", task="T-1", iterations_used=9, max_iters=4)
        r = self.run_cli("file-claim", "--by", "aurelia", "--key",
                         str(self.keys["aurelia"]), "--name", "orso", "--seq",
                         str(c["seq"]), "--task", "T-1")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["name"], "aurelia")

    def test_the_cli_refuses_a_non_replaying_claim(self):
        c = self.commit(name="orso", task="T-1", parameter="iteration_bound", value="9")
        self.write_event(event="goal_reached", task="T-1", iterations_used=9, max_iters=9)
        r = self.run_cli("file-claim", "--by", "aurelia", "--key",
                         str(self.keys["aurelia"]), "--name", "orso", "--seq",
                         str(c["seq"]), "--task", "T-1")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no gap", r.stderr)

    def test_the_cli_no_longer_accepts_observed_value_or_source(self):
        """T-472: these two flags are gone, not merely ignored -- argparse refuses an
        unrecognized argument outright, which is the mechanical half of 'a claimant
        cannot influence the observed value through any argument'."""
        c = self.commit(name="orso", task="T-1", parameter="iteration_bound", value="4")
        r = self.run_cli("file-claim", "--by", "aurelia", "--key",
                         str(self.keys["aurelia"]), "--name", "orso", "--seq",
                         str(c["seq"]), "--task", "T-1", "--observed-value", "9999",
                         "--source", "whatever i like")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unrecognized", r.stderr.lower())


class FileClaimInheritsPrivilegedGuards(Enrolled):
    """Outcome B calls `contest`, so D3a's guards (held kinds, --task, intent first) are
    inherited unchanged -- this class proves the inheritance rather than asserting it."""

    def test_a_gap_with_no_task_is_refused_exactly_as_contest_refuses_it(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        with self.patch_usage([self.fake_usage_unit(["T-1"], ["claude-sonnet-5"],
                                                     in_=9000, out=0)]):
            with self.assertRaises(attest.AttestError) as e:
                attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                  c["seq"], task=None)
        self.assertIn("--task is required", str(e.exception))

    def test_a_gap_with_no_prior_intent_is_refused_and_writes_nothing(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        before = self.acts_on("aurelia")
        with self.patch_usage([self.fake_usage_unit(["T-1"], ["claude-sonnet-5"],
                                                     in_=9000, out=0)]):
            with self.assertRaises(attest.AttestError) as e:
                attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                  c["seq"], task="T-1")
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
        with self.patch_usage([self.fake_usage_unit(["T-1"], ["claude-sonnet-5"],
                                                     in_=9000, out=0)]):
            with self.assertRaises(attest.AttestError) as e:
                attest.file_claim(self.root, "delegado", dk, "orso", c["seq"], task="T-1")
        msg = str(e.exception)
        self.assertIn("DELEGATION CEILING", msg)
        self.assertIn("contest", msg)


class FileClaimReferenceRefusals(Enrolled):
    """These refusals happen before the reader is ever looked up, so no usage/event
    fixture is needed for any of them."""

    def test_a_seq_not_on_the_respondents_own_chain_is_refused(self):
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", 999,
                              task="T-1")
        self.assertIn("no act at seq", str(e.exception))

    def test_a_reference_to_a_non_commit_act_is_refused(self):
        other = attest.sign_act(self.root, "orso", self.keys["orso"], "filing", ref="x")
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                              other["seq"], task="T-1")
        self.assertIn("not", str(e.exception))
        self.assertIn("commit", str(e.exception))

    def test_an_unsigned_commit_act_is_refused(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        pathlib.Path(c["path"]).with_suffix(".json.sig").unlink()
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertIn("does not verify", str(e.exception))

    def test_these_refusals_write_nothing(self):
        before = self._tree_digest()
        for seq in (999,):
            with self.assertRaises(attest.AttestError):
                attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", seq,
                                  task="T-1")
        after = self._tree_digest()
        self.assertEqual(before, after)


# ------------------------------------------------------- T-472: no caller-chosen value

class FileClaimCannotBeInfluenced(Enrolled):
    """T-472's own claim, checked mechanically: no argument reaches the observed value."""

    def test_file_claim_takes_no_observed_value_argument_at_all(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        with self.assertRaises(TypeError):
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                              c["seq"], observed_value="9999999", task="T-1")

    def test_file_claim_takes_no_source_argument_at_all(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        with self.assertRaises(TypeError):
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                              c["seq"], source="whatever i like", task="T-1")

    def test_a_dishonest_positional_fifth_argument_lands_on_task_not_a_value(self):
        """The fifth positional slot is now `task`, not `observed_value` -- so even an
        attacker who blindly re-sends T-466's old call shape cannot smuggle a value in;
        it is read as this claim's own `task` context, which only changes which intent
        `contest` consumes, never what gets compared."""
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        with self.patch_usage([self.fake_usage_unit(["T-1"], ["claude-sonnet-5"],
                                                     in_=4000, out=0)]):
            with self.assertRaises(attest.AttestError) as e:
                attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                  c["seq"], "9999999")
        # it is read as --task "9999999", not as an observed value of 4000's budget
        self.assertIn("no gap", str(e.exception))


# ---------------------------------------------------- T-472: a parameter with no reader

class NoReaderIsRefusedBeforeAnythingIsWritten(Enrolled):
    """`task` and `order` have no entry in PARAMETER_READERS (see its own docstring for
    why): a claim against either is refused before any gap-check, with a message naming
    that the harness cannot replay it -- pinned by hashing acts/ and the event log."""

    def test_order_has_no_reader(self):
        self.assertNotIn("order", attest.PARAMETER_READERS)

    def test_task_has_no_reader(self):
        self.assertNotIn("task", attest.PARAMETER_READERS)

    def test_a_claim_against_order_is_refused_and_writes_nothing(self):
        c = self.commit(name="orso", task="T-1", parameter="order", value="2")
        before = self._tree_digest()
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertIn("cannot replay", str(e.exception))
        self.assertIn("order", str(e.exception))
        after = self._tree_digest()
        self.assertEqual(before, after)

    def test_a_claim_against_task_is_refused_and_writes_nothing(self):
        c = self.commit(name="orso", task="T-1", parameter="task", value="T-1")
        before = self._tree_digest()
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertIn("cannot replay", str(e.exception))
        after = self._tree_digest()
        self.assertEqual(before, after)

    def test_refusal_needs_no_declared_intent_either(self):
        """Same shape as Outcome A: a parameter with no reader must refuse before
        sign_act is ever reached, so it is refused even with nothing else on file."""
        c = self.commit(name="orso", task="T-1", parameter="order", value="2")
        self.assertEqual(attest.open_intents(self.root, "aurelia"), [])
        with self.assertRaises(attest.AttestError):
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"])


# --------------------------------------------------------- the per-parameter readers

class DeadlineReader(Enrolled):
    """OBSERVED SOURCE: events.jsonl's task_handoff / task_updated(done)."""

    def test_no_handoff_or_completion_event_is_refused(self):
        c = self.commit(name="orso", task="T-1", parameter="deadline",
                        value="2026-10-21T00:00:00Z")
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertIn("cannot replay", str(e.exception))

    def test_a_handoff_before_the_committed_deadline_is_no_gap(self):
        c = self.commit(name="orso", task="T-1", parameter="deadline",
                        value="2026-10-21T12:00:00Z")
        self.write_event(event="task_handoff", task="T-1", ts="2026-10-21T10:00:00Z")
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertIn("no gap", str(e.exception))

    def test_a_handoff_after_the_committed_deadline_is_a_gap(self):
        c = self.commit(name="orso", task="T-1", parameter="deadline",
                        value="2026-10-21T12:00:00Z")
        self.write_event(event="task_handoff", task="T-1", ts="2026-10-21T18:00:00Z")
        self.declare_contest_intent("aurelia", "T-1", for_ref="orso#%d" % c["seq"])
        result = attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                   c["seq"], task="T-1")
        act = json.loads(pathlib.Path(result["path"]).read_text(encoding="utf-8"))
        reason = act["body"]["reason"]
        self.assertIn("events.jsonl", reason)
        self.assertIn("2026-10-21T18:00:00Z", reason)

    def test_a_done_task_updated_event_is_also_read(self):
        c = self.commit(name="orso", task="T-1", parameter="deadline",
                        value="2026-10-21T12:00:00Z")
        self.write_event(event="task_updated", task="T-1", status="in_progress",
                         ts="2026-10-21T11:00:00Z")
        self.write_event(event="task_updated", task="T-1", status="done",
                         ts="2026-10-21T20:00:00Z")
        self.declare_contest_intent("aurelia", "T-1", for_ref="orso#%d" % c["seq"])
        result = attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                   c["seq"], task="T-1")
        act = json.loads(pathlib.Path(result["path"]).read_text(encoding="utf-8"))
        self.assertIn("2026-10-21T20:00:00Z", act["body"]["reason"])

    def test_another_tasks_late_event_never_manufactures_a_gap(self):
        """Cross-task decoy: T-2's handoff sits FIRST in the log and is past T-1's
        committed deadline. A reader that ignores the commit act's task would read it."""
        c = self.commit(name="orso", task="T-1", parameter="deadline",
                        value="2026-10-21T12:00:00Z")
        self.write_event(event="task_handoff", task="T-2", ts="2026-10-21T23:00:00Z")
        self.write_event(event="task_handoff", task="T-1", ts="2026-10-21T10:00:00Z")
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertIn("no gap", str(e.exception))

    def test_only_another_tasks_event_means_nothing_to_replay(self):
        c = self.commit(name="orso", task="T-1", parameter="deadline",
                        value="2026-10-21T12:00:00Z")
        self.write_event(event="task_handoff", task="T-2", ts="2026-10-21T23:00:00Z")
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertIn("cannot replay", str(e.exception))

    def test_the_earliest_delivery_wins_over_a_later_one(self):
        """An on-time handoff followed by a late done-update for the same task: the
        earliest delivery is the observed value, so there is no gap."""
        c = self.commit(name="orso", task="T-1", parameter="deadline",
                        value="2026-10-21T12:00:00Z")
        self.write_event(event="task_handoff", task="T-1", ts="2026-10-21T10:00:00Z")
        self.write_event(event="task_updated", task="T-1", status="done",
                         ts="2026-10-21T20:00:00Z")
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertIn("no gap", str(e.exception))


class IterationBoundReader(Enrolled):
    """OBSERVED SOURCE: events.jsonl's goal_reached / goal_abandoned, as goal_mode.py
    itself writes them, keyed by the --task it was called with."""

    def test_no_goal_mode_run_for_this_task_is_refused(self):
        c = self.commit(name="orso", task="T-1", parameter="iteration_bound", value="3")
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertIn("cannot replay", str(e.exception))

    def test_a_declared_lower_bound_than_what_actually_ran_is_a_gap(self):
        c = self.commit(name="orso", task="T-1", parameter="iteration_bound", value="3")
        self.write_event(event="goal_abandoned", task="T-1", iterations_used=7,
                         max_iters=3)
        self.declare_contest_intent("aurelia", "T-1", for_ref="orso#%d" % c["seq"])
        result = attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                   c["seq"], task="T-1")
        act = json.loads(pathlib.Path(result["path"]).read_text(encoding="utf-8"))
        self.assertIn("goal_mode.py", act["body"]["reason"])
        self.assertIn("7", act["body"]["reason"])

    def test_a_bound_actually_met_is_no_gap(self):
        c = self.commit(name="orso", task="T-1", parameter="iteration_bound", value="3")
        self.write_event(event="goal_reached", task="T-1", iterations_used=2, max_iters=3)
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertIn("no gap", str(e.exception))

    def test_the_most_recent_matching_event_wins(self):
        c = self.commit(name="orso", task="T-1", parameter="iteration_bound", value="3")
        self.write_event(event="goal_abandoned", task="T-1", iterations_used=9,
                         max_iters=3)
        self.write_event(event="goal_reached", task="T-1", iterations_used=2, max_iters=3)
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertIn("no gap", str(e.exception))


    def test_another_tasks_run_never_manufactures_a_gap(self):
        """Cross-task decoy: T-2's run is the LAST goal_mode event and overran the bound."""
        c = self.commit(name="orso", task="T-1", parameter="iteration_bound", value="3")
        self.write_event(event="goal_reached", task="T-1", iterations_used=2, max_iters=3)
        self.write_event(event="goal_abandoned", task="T-2", iterations_used=9,
                         max_iters=3)
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertIn("no gap", str(e.exception))

    def test_only_another_tasks_run_means_nothing_to_replay(self):
        c = self.commit(name="orso", task="T-1", parameter="iteration_bound", value="3")
        self.write_event(event="goal_abandoned", task="T-2", iterations_used=9,
                         max_iters=3)
        with self.assertRaises(attest.AttestError) as e:
            attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso", c["seq"],
                              task="T-1")
        self.assertIn("cannot replay", str(e.exception))


class BudgetReaderAmbiguity(Enrolled):
    """`usage_report.py` ties tokens to a SET of task mentions per unit; only a singleton
    match is a single-task fact."""

    def test_no_matching_unit_is_refused(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        with self.patch_usage([]):
            with self.assertRaises(attest.AttestError) as e:
                attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                  c["seq"], task="T-1")
        self.assertIn("cannot replay", str(e.exception))

    def test_a_unit_mentioning_two_tasks_is_not_a_single_task_fact(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        with self.patch_usage([self.fake_usage_unit(["T-1", "T-2"], ["claude-sonnet-5"],
                                                     in_=9000, out=0)]):
            with self.assertRaises(attest.AttestError) as e:
                attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                  c["seq"], task="T-1")
        self.assertIn("cannot replay", str(e.exception))

    def test_two_singleton_units_for_the_same_task_are_summed(self):
        c = self.commit(name="orso", task="T-1", parameter="budget", value="4000")
        self.declare_contest_intent("aurelia", "T-1", for_ref="orso#%d" % c["seq"])
        with self.patch_usage([self.fake_usage_unit(["T-1"], ["claude-sonnet-5"],
                                                     in_=3000, out=0),
                               self.fake_usage_unit(["T-1"], ["claude-sonnet-5"],
                                                    in_=3000, out=0)]):
            result = attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                       c["seq"], task="T-1")
        act = json.loads(pathlib.Path(result["path"]).read_text(encoding="utf-8"))
        self.assertIn("6000", act["body"]["reason"])


class EngineReader(Enrolled):
    """OBSERVED SOURCE: usage_report.py's per-unit model list, mapped to a family."""

    def test_a_matching_engine_family_is_no_gap(self):
        c = self.commit(name="orso", task="T-1", parameter="engine", value="claude")
        with self.patch_usage([self.fake_usage_unit(["T-1"], ["claude-sonnet-5"])]):
            with self.assertRaises(attest.AttestError) as e:
                attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                  c["seq"], task="T-1")
        self.assertIn("no gap", str(e.exception))

    def test_a_mismatched_engine_family_is_a_gap(self):
        c = self.commit(name="orso", task="T-1", parameter="engine", value="claude")
        self.declare_contest_intent("aurelia", "T-1", for_ref="orso#%d" % c["seq"])
        with self.patch_usage([self.fake_usage_unit(["T-1"], ["gemini-antigravity"])]):
            result = attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                       c["seq"], task="T-1")
        act = json.loads(pathlib.Path(result["path"]).read_text(encoding="utf-8"))
        self.assertIn("gemini", act["body"]["reason"])
        self.assertIn("claude", act["body"]["reason"])

    def test_more_than_one_family_for_a_singleton_task_is_refused(self):
        c = self.commit(name="orso", task="T-1", parameter="engine", value="claude")
        with self.patch_usage([self.fake_usage_unit(["T-1"], ["claude-sonnet-5"]),
                               self.fake_usage_unit(["T-1"], ["gemini-antigravity"])]):
            with self.assertRaises(attest.AttestError) as e:
                attest.file_claim(self.root, "aurelia", self.keys["aurelia"], "orso",
                                  c["seq"], task="T-1")
        self.assertIn("cannot replay", str(e.exception))


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

    THE CLAIM: none of `commit`, `answer`, `appeal`, `file_claim`, or any of T-472's
    reader functions computes a deadline, a window, a lapse, a debit or a damages amount
    (no arithmetic, no ordering comparison against a wall-clock or numeric bound anywhere
    in their bodies), and none reads or writes a reputation figure. T-472's own addition:
    an ordering comparison may exist in exactly ONE place in this module, `_gap`, and the
    four contract functions plus every reader stay as clean of it as they always were.
    """

    CONTRACT_FUNCTIONS = ("commit", "answer", "appeal", "file_claim")

    READER_FUNCTIONS = ("_read_deadline", "_read_iteration_bound", "_read_budget",
                        "_read_engine", "_usage_units_for_task", "_events_for",
                        "_engine_family", "_coerce_order")
    """T-472's readers and their own helpers: they fetch and parse a value, they never
    decide whether it constitutes a gap -- that decision belongs to `_gap` alone. Note
    `_coerce_order` is here too: it parses a value into something comparable but never
    itself compares two values with `<`/`>`/`<=`/`>=`."""

    COMPARATOR_FUNCTION = "_gap"
    """The ONE place in this module an ordering comparison may legitimately appear."""

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

    def test_the_reader_and_comparator_functions_exist(self):
        fns = self._function_sources()
        missing = (set(self.READER_FUNCTIONS) | {self.COMPARATOR_FUNCTION}) - set(fns)
        self.assertEqual(missing, set(),
                         "the guard's reader/comparator list names a function that does "
                         "not exist")

    def _ordering_and_arithmetic(self, node):
        offenders = []
        for n in ast.walk(node):
            if isinstance(n, ast.BinOp):
                offenders.append("BinOp")
            if isinstance(n, ast.Compare):
                for op in n.ops:
                    if isinstance(op, (ast.Lt, ast.Gt, ast.LtE, ast.GtE)):
                        offenders.append(type(op).__name__)
        return offenders

    def test_none_of_the_four_contains_arithmetic_or_ordering_comparison(self):
        """No BinOp (no +, -, *, / of any value) and no <, >, <=, >= anywhere in these
        four functions' bodies. A window, a lapse or a debit cannot be computed without
        one of those; their total absence is the mechanical form of 'nothing is
        computed'."""
        fns = self._function_sources()
        offenders = {name: self._ordering_and_arithmetic(fns[name])
                    for name in self.CONTRACT_FUNCTIONS
                    if self._ordering_and_arithmetic(fns[name])}
        self.assertEqual(offenders, {},
                         "a function that should only compare for exact equality "
                         "contains ordering/arithmetic, which is how a window or a "
                         "damages amount would be computed: %r" % offenders)

    def test_none_of_the_readers_contains_ordering_comparison(self):
        """T-472's own addition: a reader FETCHES a value; it never decides whether that
        value constitutes a gap. `_gap` is the only function in this module allowed an
        ordering comparison -- readers may still contain a BinOp (e.g. the token sum in
        `_read_budget`, or `_coerce_order`'s own parsing), so only ordering is checked
        here, not arithmetic."""
        fns = self._function_sources()
        offenders = {}
        for name in self.READER_FUNCTIONS:
            for node in ast.walk(fns[name]):
                if isinstance(node, ast.Compare):
                    for op in node.ops:
                        if isinstance(op, (ast.Lt, ast.Gt, ast.LtE, ast.GtE)):
                            offenders.setdefault(name, []).append(type(op).__name__)
        self.assertEqual(offenders, {},
                         "a reader decided a gap itself instead of leaving that to "
                         "_gap: %r" % offenders)

    def test_the_comparator_is_the_only_place_ordering_appears(self):
        """Positive control, the mirror of the negative one below: `_gap` DOES contain an
        ordering comparison, proving the two tests above are checking something real and
        not vacuously passing because nothing anywhere ever compares ordering."""
        fns = self._function_sources()
        node = fns[self.COMPARATOR_FUNCTION]
        found = any(isinstance(op, (ast.Lt, ast.Gt, ast.LtE, ast.GtE))
                   for n in ast.walk(node) if isinstance(n, ast.Compare)
                   for op in n.ops)
        self.assertTrue(found, "_gap itself contains no ordering comparison; the "
                               "'only inside the comparator' guard would be vacuous")

    def _all_guarded_function_names(self):
        return tuple(self.CONTRACT_FUNCTIONS) + tuple(self.READER_FUNCTIONS) + \
               (self.COMPARATOR_FUNCTION,)

    def test_none_of_the_four_mentions_a_forbidden_identifier(self):
        fns = self._function_sources()
        hits = {}
        for name in self._all_guarded_function_names():
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
        self.assertEqual(hits, {}, "a contracts/reader/comparator function reads/writes "
                                   "a forbidden reputation or computed-consequence "
                                   "field: %r" % hits)

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

    def test_the_reader_guard_catches_a_planted_ordering_comparison(self):
        """Same negative control, for T-472's new reader scope: inject a '>' into
        `_read_budget` in a patched copy and confirm the walk this test module performs
        on READER_FUNCTIONS would actually catch it."""
        with tempfile.TemporaryDirectory() as tmp:
            patched = pathlib.Path(tmp) / "attest_patched.py"
            src = ATTEST_PY.read_text(encoding="utf-8")
            needle = "def _read_budget(root, task_id):"
            self.assertIn(needle, src)
            injected = src.replace(
                needle,
                needle + "\n    _planted = 1 if len(str(task_id)) > 9999 else 0  "
                        "# injected\n",
                1)
            patched.write_text(injected, encoding="utf-8")
            tree = ast.parse(patched.read_text(encoding="utf-8"))
            fns = {n.name: n for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            found = any(isinstance(op, ast.Gt)
                       for node in ast.walk(fns["_read_budget"])
                       if isinstance(node, ast.Compare)
                       for op in node.ops)
            self.assertTrue(found, "the guard failed to catch a planted ordering "
                                   "comparison in a reader; it would be checking "
                                   "nothing for real")

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
