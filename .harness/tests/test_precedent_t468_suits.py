"""T-452/T-468: suits in the case register, case verdict, notice, and the judge seat draft.

Scope, per the operator ruling of 2026-10-21 (decision 3) and `design-T-452-courts.md`
section 9 items 1, 3, 4: this file covers `precedent.py`'s slice only (item 2, `attest.py`'s
`answer`/`appeal` kinds, belongs to T-466 and is not touched here).

NOT RATIFIED, BUILT ANYWAY AS ABSENT: decision 3's three numbers (objection window,
pursue-or-lapse window, damages cap). Nothing under test computes any of them; the notice
title's deadline slot is pinned to the literal string "window not ratified" and tests assert
that literal rather than any date arithmetic.

Everything here runs against a throwaway harness root built with the REAL warrant.py
draft/sign/apply flow (mirroring test_warrant.py's GateCase), never the operator's own key
and never the live `.harness` tree. The notice tests additionally copy the real `.harness/bin`
into that throwaway root, because `blackboard.py` resolves its own data root from its OWN
file location (T-422) rather than from a flag -- the same mechanism
test_blackboard_redact.py already relies on.
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".harness" / "bin"
CLI = BIN_DIR / "precedent.py"
sys.path.insert(0, str(BIN_DIR))
import attest      # noqa: E402
import precedent    # noqa: E402
import warrant as w  # noqa: E402


def keygen(path, comment="k"):
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", comment,
                   "-f", str(path)], check=True, capture_output=True)
    return pathlib.Path(str(path) + ".pub")


def root_sign(payload_path, key_path):
    r = subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key_path),
                        "-n", w.NAMESPACE, str(payload_path)],
                       text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return pathlib.Path(str(payload_path) + ".sig")


class CourtCase(unittest.TestCase):
    """A throwaway, enrolled harness root. `self.hroot` is named `.harness` on purpose
    (load-bearing for `TheNoticeVerb` below, not decorative elsewhere)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = pathlib.Path(self._tmp.name)
        self.hroot = self.base / ".harness"
        self.hroot.mkdir()
        self.reg = self.hroot / "precedents"
        self.reg.mkdir()
        self.keys_dir = self.base / "keys"
        self.keys_dir.mkdir()
        self.root_key = self.keys_dir / "root"
        self.root_pub = keygen(self.root_key, "root@operator")
        w.init(self.hroot, self.root_pub)
        self.keys = {}

    # ------------------------------------------------------------- identity setup

    def agent_key(self, name):
        k = self.keys_dir / name
        pub = keygen(k, name)
        self.keys[name] = k
        return k, pub

    def issue(self, name, colegiado, role, epic, incentive="paga por algo"):
        """Issue `name` into `colegiado/role` via a real signed-and-applied warrant."""
        priv, pub = self.agent_key(name)
        d = w.draft(self.hroot, epic, ["{}={}".format(colegiado, incentive)],
                   ["{}/{}=1".format(colegiado, role)],
                   ["{}:{}/{}:{}:drafted for T-468 tests".format(name, colegiado, role, pub)])
        root_sign(pathlib.Path(d["path"]), self.root_key)
        w.apply_warrant(self.hroot, d["warrant_id"])
        return name

    def issue_judge(self, name="judge1", epic="gen-10-courts"):
        return self.issue(name, "judge", "verifier", epic,
                          incentive="a reasoned verdict on a filed suit, paid to distrust "
                                    "both parties")

    # ------------------------------------------------------------- precedent CLI

    def cli(self, *argv):
        return subprocess.run([sys.executable, str(CLI)] + list(argv) + ["--root", str(self.reg)],
                              capture_output=True, text=True)

    def open_case(self, question="suit question", task="T-1", **suit):
        argv = ["case", "open", "--question", question, "--task", task]
        for flag, val in suit.items():
            if val is not None:
                argv += ["--" + flag.replace("_", "-"), val]
        return self.cli(*argv)

    def last_case_id(self):
        cases = sorted((self.hroot / "cases").glob("C-*.json"))
        return cases[-1].stem

    def load_case(self, case_id):
        return json.loads((self.hroot / "cases" / (case_id + ".json")).read_text(encoding="utf-8"))

    # ------------------------------------------------------------- acts

    def intent(self, name, for_kind, task, declares="por que", for_ref=""):
        return attest.declare_intent(self.hroot, name, self.keys[name], for_kind, task,
                                     declares, for_ref)

    def sign(self, name, kind, ref="", body=None, task=None):
        return attest.sign_act(self.hroot, name, self.keys[name], kind, ref=ref,
                               body=body, task=task)

    def verdict_act(self, judge, task, case, body=None):
        self.intent(judge, "verdict", task, declares="juicio sobre {}".format(case))
        return self.sign(judge, "verdict", ref=case, task=task,
                         body=body or {"case": case, "order": "none"})

    def act_path(self, name, seq):
        return self.hroot / "acts" / name / "{:03d}.json".format(seq)


# ----------------------------------------------------------------------------------
# Item 1: suit fields on `case open`, stored as one schema (section 1 / AC-1)
# ----------------------------------------------------------------------------------

class TheSuitFields(CourtCase):

    def test_a_case_opened_with_no_suit_fields_is_byte_for_byte_the_old_schema(self):
        r = self.open_case()
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.load_case(self.last_case_id())
        self.assertEqual(set(rec.keys()),
                         {"id", "question", "task", "opened_by", "ts", "status", "disposal"})
        self.assertNotIn("suit", rec)

    def test_a_case_opened_with_suit_fields_stores_one_suit_block(self):
        r = self.open_case(claimant="aurelia", respondent="orso",
                           contract="T-100", damages_claimed="40 tokens")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.load_case(self.last_case_id())
        self.assertEqual(rec["suit"], {
            "claimant": "aurelia", "respondent": "orso",
            "contract": "T-100", "damages_claimed": "40 tokens",
        })
        # and the rest of the schema is untouched
        self.assertEqual(rec["status"], "open")
        self.assertIsNone(rec["disposal"])

    def test_a_partial_suit_block_still_writes_one_dict_with_the_rest_none(self):
        r = self.open_case(claimant="aurelia")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.load_case(self.last_case_id())
        self.assertEqual(rec["suit"]["claimant"], "aurelia")
        self.assertIsNone(rec["suit"]["respondent"])
        self.assertIsNone(rec["suit"]["contract"])
        self.assertIsNone(rec["suit"]["damages_claimed"])

    def test_damages_claimed_is_never_read_by_the_disposal_or_verdict_machinery(self):
        """Informational only (design section 1): pinned by checking the SOURCE of the
        functions that touch disposal, rather than trusting that no test happens to exercise
        a computation. A substring scan, same rigor level `test_warrant.py` already uses for
        an equivalent claim ("no code path signs"), disclosed as such."""
        import inspect
        for fn in (precedent.dispose_case, precedent.cmd_case_verdict,
                  precedent.validate_case_for_disposal, precedent._ref_already_disposes_a_case):
            src = inspect.getsource(fn)
            self.assertNotIn("damages", src,
                             "{} must never read the suit's damages_claimed field"
                             .format(fn.__name__))


# ----------------------------------------------------------------------------------
# Item 1 (verdict half) + section 4: `case verdict`
# ----------------------------------------------------------------------------------

class TheVerdict(CourtCase):

    def setUp(self):
        super().setUp()
        self.issue_judge("judge1")
        self.open_case(task="T-9")
        self.case = self.last_case_id()

    def test_the_happy_path_disposes_the_case(self):
        act = self.verdict_act("judge1", "T-9", self.case)
        r = self.cli("case", "verdict", "--case", self.case, "--judge", "judge1",
                    "--seq", str(act["seq"]), "--task", "T-9")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.load_case(self.case)
        self.assertEqual(rec["status"], "disposed")
        self.assertEqual(rec["disposal"]["verb"], "verdict")
        self.assertEqual(rec["disposal"]["ref"], "judge1_{}".format(act["seq"]))
        self.assertEqual(rec["disposal"]["by"], "judge1")
        self.assertEqual(rec["disposal"]["task"], "T-9")

    def test_refuses_an_act_that_is_not_kind_verdict(self):
        # "commit" is unprivileged (no intent required), so this needs no intent at all.
        act = self.sign("judge1", "commit", ref=self.case, task="T-9", body={})
        r = self.cli("case", "verdict", "--case", self.case, "--judge", "judge1",
                    "--seq", str(act["seq"]), "--task", "T-9")
        self.assertEqual(r.returncode, 1)
        self.assertIn("is kind 'commit'", r.stderr)
        rec = self.load_case(self.case)
        self.assertEqual(rec["status"], "open")

    def test_refuses_an_act_that_does_not_verify_under_the_judges_key(self):
        act = self.verdict_act("judge1", "T-9", self.case)
        path = self.act_path("judge1", act["seq"])
        data = json.loads(path.read_text(encoding="utf-8"))
        data["body"] = {"tampered": True}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        r = self.cli("case", "verdict", "--case", self.case, "--judge", "judge1",
                    "--seq", str(act["seq"]), "--task", "T-9")
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not verify under", r.stderr)
        rec = self.load_case(self.case)
        self.assertEqual(rec["status"], "open")

    def test_refuses_a_judge_name_not_issued_in_the_judge_colegiado(self):
        self.issue("notjudge1", "banco", "verifier", "gen-10-courts")
        self.intent("notjudge1", "verdict", "T-9", declares="juicio")
        act = self.sign("notjudge1", "verdict", ref=self.case, task="T-9", body={})
        r = self.cli("case", "verdict", "--case", self.case, "--judge", "notjudge1",
                    "--seq", str(act["seq"]), "--task", "T-9")
        self.assertEqual(r.returncode, 1)
        self.assertIn("is issued in colegiado 'banco', not 'judge'", r.stderr)
        rec = self.load_case(self.case)
        self.assertEqual(rec["status"], "open")

    def test_refuses_a_task_mismatch(self):
        act = self.verdict_act("judge1", "T-9", self.case)
        r = self.cli("case", "verdict", "--case", self.case, "--judge", "judge1",
                    "--seq", str(act["seq"]), "--task", "T-OTHER")
        self.assertEqual(r.returncode, 1)
        self.assertIn("task mismatch", r.stderr)
        rec = self.load_case(self.case)
        self.assertEqual(rec["status"], "open")

    def test_refuses_a_case_already_disposed(self):
        act = self.verdict_act("judge1", "T-9", self.case)
        r1 = self.cli("case", "verdict", "--case", self.case, "--judge", "judge1",
                     "--seq", str(act["seq"]), "--task", "T-9")
        self.assertEqual(r1.returncode, 0, r1.stderr)
        self.intent("judge1", "verdict", "T-9", declares="segundo juicio")
        act2 = self.sign("judge1", "verdict", ref=self.case, task="T-9", body={})
        r2 = self.cli("case", "verdict", "--case", self.case, "--judge", "judge1",
                     "--seq", str(act2["seq"]), "--task", "T-9")
        self.assertEqual(r2.returncode, 1)
        self.assertIn("already disposed", r2.stderr)

    def test_refuses_a_verdict_act_already_disposing_another_case(self):
        act = self.verdict_act("judge1", "T-9", self.case)
        r1 = self.cli("case", "verdict", "--case", self.case, "--judge", "judge1",
                     "--seq", str(act["seq"]), "--task", "T-9")
        self.assertEqual(r1.returncode, 0, r1.stderr)

        self.open_case(question="segunda cuestion", task="T-9")
        other_case = self.last_case_id()
        self.assertNotEqual(other_case, self.case)

        r2 = self.cli("case", "verdict", "--case", other_case, "--judge", "judge1",
                     "--seq", str(act["seq"]), "--task", "T-9")
        self.assertEqual(r2.returncode, 1)
        self.assertIn("already disposes case", r2.stderr)
        self.assertIn(self.case, r2.stderr)
        rec = self.load_case(other_case)
        self.assertEqual(rec["status"], "open")

    def test_damages_cap_and_windows_are_never_computed_here(self):
        """Nothing in the verdict CLI's own source names a deadline, a lapse, or a
        damages amount -- those three numbers are unratified (decision 3) and the whole
        point of this test is that there is no code path to find them under."""
        import inspect
        src = inspect.getsource(precedent.cmd_case_verdict)
        for forbidden in ("deadline", "lapse", "7200", "25%", "0.25", "cap"):
            self.assertNotIn(forbidden, src)


# ----------------------------------------------------------------------------------
# Item 3 + section 2: the notice verb, through the REAL blackboard.py
# ----------------------------------------------------------------------------------

FRESH_STATE = {
    "limits": {
        "claim_lease_seconds_default": 3600,
        "lock_ttl_seconds_default": 900,
        "max_steps_per_task": 50,
        "max_retries_per_failure": 3,
        "max_parallel_workers": 3,
    },
    "agents": {"reputation": {}},
    "run": {"run_counter": 0, "last_run_id": None, "last_session_start": None},
}


class TheNoticeVerb(CourtCase):
    """`case notice` must go through the REAL `blackboard.py add-task` -- never a
    hand-written task file -- and must never touch the LIVE board. `self.hroot`'s own
    `bin/` is a full copy of the real one, so `blackboard.py` (which resolves its data
    root from its OWN file location, T-422) reads and writes only inside this throwaway
    tree."""

    def setUp(self):
        super().setUp()
        bindir = self.hroot / "bin"
        shutil.copytree(BIN_DIR, bindir, ignore=shutil.ignore_patterns("__pycache__"))
        for sub in ("locks", "logs", "tasks"):
            (self.hroot / sub).mkdir(parents=True, exist_ok=True)
        (self.hroot / "blackboard.json").write_text(json.dumps({
            "schema_version": "0.1.0", "generation": 0, "tasks": {}, "epics": {},
            "updated_at": "2026-10-21T00:00:00Z", "updated_by": "test-init",
        }))
        (self.hroot / "state.json").write_text(json.dumps(FRESH_STATE))
        (self.hroot / "logs" / "events.jsonl").write_text("")
        self.open_case(question="breach of T-100", task="T-9",
                       claimant="aurelia", respondent="orso", contract="T-100")
        self.case = self.last_case_id()

    def live_board_tasks(self):
        live_bb = json.loads((ROOT / ".harness" / "blackboard.json").read_text(encoding="utf-8"))
        return live_bb.get("tasks", {})

    def test_notice_creates_the_board_task_with_the_exact_title_and_shape(self):
        before_live = set(self.live_board_tasks())
        r = self.cli("case", "notice", "--case", self.case, "--respondent", "orso",
                    "--task-id", "T-900")
        self.assertEqual(r.returncode, 0, r.stderr)

        task = json.loads((self.hroot / "tasks" / "T-900.json").read_text(encoding="utf-8"))
        bb = json.loads((self.hroot / "blackboard.json").read_text(encoding="utf-8"))
        entry = bb["tasks"]["T-900"]
        self.assertEqual(entry["title"],
                         "NOTICE to orso: answer suit {} by window not ratified".format(self.case))
        self.assertEqual(entry["role"], "worker")
        self.assertEqual(entry["engine"], "any")
        self.assertEqual(entry["depends_on"], [])
        self.assertEqual(entry["status"], "open")

        # and the LIVE board, not the throwaway one, is untouched
        self.assertEqual(set(self.live_board_tasks()), before_live)
        self.assertNotIn("T-900", self.live_board_tasks())

    def test_the_deadline_is_the_literal_unratified_string_never_a_computed_date(self):
        r = self.cli("case", "notice", "--case", self.case, "--respondent", "orso",
                    "--task-id", "T-901")
        self.assertEqual(r.returncode, 0, r.stderr)
        bb = json.loads((self.hroot / "blackboard.json").read_text(encoding="utf-8"))
        self.assertIn("window not ratified", bb["tasks"]["T-901"]["title"])
        import re
        self.assertNotRegex(bb["tasks"]["T-901"]["title"], r"\d{4}-\d{2}-\d{2}")

    def test_notice_refuses_an_unregistered_case(self):
        r = self.cli("case", "notice", "--case", "C-999", "--respondent", "orso",
                    "--task-id", "T-902")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not registered", r.stderr)
        self.assertFalse((self.hroot / "tasks" / "T-902.json").exists())


if __name__ == "__main__":
    unittest.main()
