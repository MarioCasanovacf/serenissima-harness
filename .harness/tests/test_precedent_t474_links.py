"""T-474: link the claimant's contest act, the respondent's answer act and a party's
appeal act into the suit record, and make `case show` report the suit's state in words.

Scope, per board T-474 and `design-T-452-courts.md` sections 1, 2 and 5: `precedent.py`'s
`case claim`/`case answer`/`case appeal` verbs and `case show`'s suit-state/retraction
reporting. `attest.py` is NOT edited here (T-472 owns it, and is changing `file_claim`'s
signature in parallel) -- every act below is built directly with attest.py's EXISTING
`contest`, `answer`, `appeal` and `verdict` verbs, never through `file_claim`.

NOT RATIFIED, BUILT ANYWAY AS ABSENT: decision 3's three numbers (objection window,
pursue-or-lapse window, damages cap). Nothing under test computes any of them.

Everything here runs against a throwaway harness root built with the REAL warrant.py
draft/sign/apply flow, never the operator's own key and never the live `.harness` tree --
mirrors test_precedent_t468_suits.py's CourtCase fixture exactly, extended with the
claimant/respondent act helpers this file needs.
"""
import json
import pathlib
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


def _board_in_throwaway_root(hroot):
    """`case notice` goes through the REAL blackboard.py add-task, which resolves its data
    root from its OWN file location (T-422): copy bin/ into the throwaway root so the LIVE
    board is never touched. Mirrors test_precedent_t468_suits.py's TheNoticeVerb setUp."""
    import importlib.util
    import shutil
    spec = importlib.util.spec_from_file_location(
        "t468_fixture", pathlib.Path(__file__).resolve().parent / "test_precedent_t468_suits.py")
    t468 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t468)
    shutil.copytree(BIN_DIR, hroot / "bin", ignore=shutil.ignore_patterns("__pycache__"))
    for sub in ("locks", "logs", "tasks"):
        (hroot / sub).mkdir(parents=True, exist_ok=True)
    (hroot / "blackboard.json").write_text(json.dumps({
        "schema_version": "0.1.0", "generation": 0, "tasks": {}, "epics": {},
        "updated_at": "2026-10-21T00:00:00Z", "updated_by": "test-init",
    }))
    (hroot / "state.json").write_text(json.dumps(t468.FRESH_STATE))
    (hroot / "logs" / "events.jsonl").write_text("")


class SuitCase(unittest.TestCase):
    """Throwaway, enrolled harness root. Mirrors test_precedent_t468_suits.py's
    `CourtCase` fixture."""

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
        priv, pub = self.agent_key(name)
        d = w.draft(self.hroot, epic, ["{}={}".format(colegiado, incentive)],
                   ["{}/{}=1".format(colegiado, role)],
                   ["{}:{}/{}:{}:drafted for T-474 tests".format(name, colegiado, role, pub)])
        root_sign(pathlib.Path(d["path"]), self.root_key)
        w.apply_warrant(self.hroot, d["warrant_id"])
        return name

    def issue_party(self, name, epic="gen-10-courts"):
        return self.issue(name, "party", "worker", epic, incentive="a party to a suit")

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

    def show(self, case_id):
        return self.cli("case", "show", case_id)

    # ------------------------------------------------------------- acts

    def intent(self, name, for_kind, task, declares="por que", for_ref=""):
        return attest.declare_intent(self.hroot, name, self.keys[name], for_kind, task,
                                     declares, for_ref)

    def contest_act(self, accuser, target_name, target_seq, reason, task="T-9"):
        self.intent(accuser, "contest", task, declares="disputa de {}".format(target_name))
        return attest.contest(self.hroot, accuser, self.keys[accuser], target_name,
                              target_seq, reason, task=task)

    def answer_act(self, name, task, ref, disputes="niego el incumplimiento"):
        return attest.answer(self.hroot, name, self.keys[name], task, ref, disputes)

    def appeal_act(self, name, task, ref, grounds="la decision es erronea"):
        return attest.appeal(self.hroot, name, self.keys[name], task, ref, grounds)

    def verdict_act(self, judge, task, case, body=None):
        self.intent(judge, "verdict", task, declares="juicio sobre {}".format(case))
        return attest.sign_act(self.hroot, judge, self.keys[judge], "verdict", ref=case,
                               task=task, body=body or {"case": case, "order": "none"})

    def act_seq(self, act):
        return act["seq"]

    def chain_act(self, name, seq):
        return next(a for a in attest.chain(self.hroot, name) if a.get("seq") == seq)


# ----------------------------------------------------------------------------------
# `case claim`: link the claimant's own contest act (section 1 / AC-1)
# ----------------------------------------------------------------------------------

class TheClaimVerb(SuitCase):

    def setUp(self):
        super().setUp()
        self.issue_party("aurelia")
        self.issue_party("orso")
        self.open_case(question="breach of T-100", task="T-9",
                       claimant="aurelia", respondent="orso", contract="T-100")
        self.case = self.last_case_id()

    def file_contest(self, reason="breach of T-100 found by direct read"):
        # target_seq is any seq on orso's own chain for the contest's ref -- here a
        # placeholder "commit" act, built directly, never through file_claim.
        commit = attest.sign_act(self.hroot, "orso", self.keys["orso"], "commit",
                                 ref="deadline", body={"parameter": "deadline", "value": "5"},
                                 task="T-9")
        return self.contest_act("aurelia", "orso", commit["seq"], reason, task="T-9")

    def test_the_happy_path_records_the_claim_in_the_suit_block(self):
        act = self.file_contest()
        r = self.cli("case", "claim", "--case", self.case, "--claimant-seq", str(act["seq"]))
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.load_case(self.case)
        self.assertEqual(rec["suit"]["claim"]["by"], "aurelia")
        self.assertEqual(rec["suit"]["claim"]["seq"], act["seq"])

    def test_refuses_an_act_that_is_not_kind_contest(self):
        act = attest.sign_act(self.hroot, "aurelia", self.keys["aurelia"], "commit",
                              ref="deadline", body={"parameter": "deadline", "value": "3"},
                              task="T-9")
        r = self.cli("case", "claim", "--case", self.case, "--claimant-seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("is kind 'commit'", r.stderr)
        self.assertNotIn("claim", self.load_case(self.case).get("suit", {}))

    def test_refuses_a_seq_not_on_the_claimants_own_chain(self):
        # The act exists, but on orso's chain, not aurelia's (the suit's claimant).
        act = attest.sign_act(self.hroot, "orso", self.keys["orso"], "commit",
                              ref="deadline", body={}, task="T-9")
        r = self.cli("case", "claim", "--case", self.case, "--claimant-seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("no act #{}".format(act["seq"]), r.stderr)

    def test_refuses_an_act_that_does_not_verify(self):
        act = self.file_contest()
        path = pathlib.Path(self.hroot / "acts" / "aurelia" / "{:03d}.json".format(act["seq"]))
        data = json.loads(path.read_text(encoding="utf-8"))
        data["body"] = {"tampered": True}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        r = self.cli("case", "claim", "--case", self.case, "--claimant-seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not verify under", r.stderr)

    def test_refuses_a_contest_that_does_not_name_the_suits_respondent(self):
        self.issue_party("someoneelse")
        commit = attest.sign_act(self.hroot, "someoneelse", self.keys["someoneelse"],
                                 "commit", ref="deadline", body={}, task="T-9")
        act = self.contest_act("aurelia", "someoneelse", commit["seq"],
                               "breach of T-100 found by direct read")
        r = self.cli("case", "claim", "--case", self.case, "--claimant-seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not name the suit's respondent", r.stderr)

    def test_refuses_a_contest_that_does_not_name_the_suits_contract(self):
        commit = attest.sign_act(self.hroot, "orso", self.keys["orso"], "commit",
                                 ref="deadline", body={}, task="T-9")
        act = self.contest_act("aurelia", "orso", commit["seq"], "breach found, no contract named")
        r = self.cli("case", "claim", "--case", self.case, "--claimant-seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not name the suit's contract", r.stderr)

    def test_refuses_a_case_with_no_suit_block(self):
        self.open_case(question="not a suit", task="T-10")
        plain_case = self.last_case_id()
        act = self.file_contest()
        r = self.cli("case", "claim", "--case", plain_case, "--claimant-seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("has no suit block", r.stderr)


# ----------------------------------------------------------------------------------
# `case answer`: link the respondent's own answer act (section 2 / AC-2)
# ----------------------------------------------------------------------------------

class TheAnswerVerb(SuitCase):

    def setUp(self):
        super().setUp()
        self.issue_party("aurelia")
        self.issue_party("orso")
        self.open_case(question="breach of T-100", task="T-9",
                       claimant="aurelia", respondent="orso", contract="T-100")
        self.case = self.last_case_id()

    def test_the_happy_path_records_the_answer_in_the_suit_block(self):
        act = self.answer_act("orso", "T-9", self.case)
        r = self.cli("case", "answer", "--case", self.case, "--seq", str(act["seq"]))
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.load_case(self.case)
        self.assertEqual(rec["suit"]["answer"]["by"], "orso")
        self.assertEqual(rec["suit"]["answer"]["seq"], act["seq"])

    def test_refuses_an_act_that_is_not_kind_answer(self):
        act = attest.sign_act(self.hroot, "orso", self.keys["orso"], "commit",
                              ref=self.case, body={}, task="T-9")
        r = self.cli("case", "answer", "--case", self.case, "--seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("is kind 'commit'", r.stderr)

    def test_refuses_a_seq_not_on_the_respondents_own_chain(self):
        act = self.answer_act("aurelia", "T-9", self.case)
        r = self.cli("case", "answer", "--case", self.case, "--seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("no act #{}".format(act["seq"]), r.stderr)

    def test_refuses_an_act_that_does_not_verify(self):
        act = self.answer_act("orso", "T-9", self.case)
        path = pathlib.Path(self.hroot / "acts" / "orso" / "{:03d}.json".format(act["seq"]))
        data = json.loads(path.read_text(encoding="utf-8"))
        data["body"] = {"tampered": True}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        r = self.cli("case", "answer", "--case", self.case, "--seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not verify under", r.stderr)

    def test_refuses_an_answer_that_does_not_reference_this_case(self):
        act = self.answer_act("orso", "T-9", "C-999")
        r = self.cli("case", "answer", "--case", self.case, "--seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not reference case", r.stderr)


# ----------------------------------------------------------------------------------
# `case appeal`: link a party's appeal act, only after a verdict (section 5 / AC-2)
# ----------------------------------------------------------------------------------

class TheAppealVerb(SuitCase):

    def setUp(self):
        super().setUp()
        self.issue_party("aurelia")
        self.issue_party("orso")
        self.issue_judge("judge1")
        self.open_case(question="breach of T-100", task="T-9",
                       claimant="aurelia", respondent="orso", contract="T-100")
        self.case = self.last_case_id()

    def judge_the_case(self):
        act = self.verdict_act("judge1", "T-9", self.case)
        r = self.cli("case", "verdict", "--case", self.case, "--judge", "judge1",
                    "--seq", str(act["seq"]), "--task", "T-9")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_refuses_an_appeal_before_any_verdict(self):
        act = self.appeal_act("orso", "T-9", self.case)
        r = self.cli("case", "appeal", "--case", self.case, "--by", "orso",
                    "--seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("has no verdict on file yet", r.stderr)

    def test_the_happy_path_records_the_appeal_after_a_verdict(self):
        self.judge_the_case()
        act = self.appeal_act("orso", "T-9", self.case)
        r = self.cli("case", "appeal", "--case", self.case, "--by", "orso",
                    "--seq", str(act["seq"]))
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.load_case(self.case)
        self.assertEqual(len(rec["suit"]["appeals"]), 1)
        self.assertEqual(rec["suit"]["appeals"][0]["by"], "orso")

    def test_the_claimant_may_also_appeal(self):
        self.judge_the_case()
        act = self.appeal_act("aurelia", "T-9", self.case)
        r = self.cli("case", "appeal", "--case", self.case, "--by", "aurelia",
                    "--seq", str(act["seq"]))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_refuses_an_appeal_by_a_non_party(self):
        self.judge_the_case()
        self.issue_party("bystander")
        act = self.appeal_act("bystander", "T-9", self.case)
        r = self.cli("case", "appeal", "--case", self.case, "--by", "bystander",
                    "--seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("is neither the suit's claimant", r.stderr)

    def test_refuses_an_act_that_is_not_kind_appeal(self):
        self.judge_the_case()
        act = attest.sign_act(self.hroot, "orso", self.keys["orso"], "commit",
                              ref=self.case, body={}, task="T-9")
        r = self.cli("case", "appeal", "--case", self.case, "--by", "orso",
                    "--seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("is kind 'commit'", r.stderr)

    def test_refuses_a_second_appeal_by_the_same_party(self):
        self.judge_the_case()
        act1 = self.appeal_act("orso", "T-9", self.case)
        r1 = self.cli("case", "appeal", "--case", self.case, "--by", "orso",
                     "--seq", str(act1["seq"]))
        self.assertEqual(r1.returncode, 0, r1.stderr)
        act2 = self.appeal_act("orso", "T-9", self.case, grounds="segundo motivo")
        r2 = self.cli("case", "appeal", "--case", self.case, "--by", "orso",
                     "--seq", str(act2["seq"]))
        self.assertEqual(r2.returncode, 1)
        self.assertIn("already appealed this case", r2.stderr)

    def test_refuses_an_appeal_act_that_does_not_verify(self):
        self.judge_the_case()
        act = self.appeal_act("orso", "T-9", self.case)
        path = pathlib.Path(self.hroot / "acts" / "orso" / "{:03d}.json".format(act["seq"]))
        data = json.loads(path.read_text(encoding="utf-8"))
        data["body"] = {"tampered": True}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        r = self.cli("case", "appeal", "--case", self.case, "--by", "orso",
                    "--seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not verify under", r.stderr)
        self.assertNotIn("appeals", self.load_case(self.case)["suit"])

    def test_refuses_an_appeal_seq_not_on_the_appellants_own_chain(self):
        self.judge_the_case()
        act = self.appeal_act("aurelia", "T-9", self.case)
        r = self.cli("case", "appeal", "--case", self.case, "--by", "orso",
                    "--seq", str(act["seq"]))
        self.assertEqual(r.returncode, 1)
        self.assertIn("no act #{}".format(act["seq"]), r.stderr)

    def test_refuses_an_appeal_on_a_case_with_no_suit_block(self):
        self.open_case(question="plain case", task="T-1")
        plain = self.last_case_id()
        r = self.cli("case", "appeal", "--case", plain, "--by", "orso", "--seq", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no suit block", r.stderr)

    def test_a_second_appeal_by_the_OTHER_party_is_allowed(self):
        self.judge_the_case()
        act1 = self.appeal_act("orso", "T-9", self.case)
        r1 = self.cli("case", "appeal", "--case", self.case, "--by", "orso",
                     "--seq", str(act1["seq"]))
        self.assertEqual(r1.returncode, 0, r1.stderr)
        act2 = self.appeal_act("aurelia", "T-9", self.case)
        r2 = self.cli("case", "appeal", "--case", self.case, "--by", "aurelia",
                     "--seq", str(act2["seq"]))
        self.assertEqual(r2.returncode, 0, r2.stderr)
        rec = self.load_case(self.case)
        self.assertEqual(len(rec["suit"]["appeals"]), 2)


# ----------------------------------------------------------------------------------
# `case show`: the suit's state in words, and retraction reporting
# ----------------------------------------------------------------------------------

class TheSuitStateReport(SuitCase):

    def setUp(self):
        super().setUp()
        self.issue_party("aurelia")
        self.issue_party("orso")
        self.issue_judge("judge1")
        self.open_case(question="breach of T-100", task="T-9",
                       claimant="aurelia", respondent="orso", contract="T-100")
        self.case = self.last_case_id()

    def commit_and_contest(self, reason="breach of T-100 found by direct read"):
        commit = attest.sign_act(self.hroot, "orso", self.keys["orso"], "commit",
                                 ref="deadline", body={}, task="T-9")
        return self.contest_act("aurelia", "orso", commit["seq"], reason, task="T-9")

    def test_a_freshly_opened_suit_reports_opened(self):
        r = self.show(self.case)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Suit state: opened", r.stdout)

    def test_a_claimed_suit_reports_claimed(self):
        act = self.commit_and_contest()
        r1 = self.cli("case", "claim", "--case", self.case, "--claimant-seq", str(act["seq"]))
        self.assertEqual(r1.returncode, 0, r1.stderr)
        r2 = self.show(self.case)
        self.assertIn("Suit state: claimed", r2.stdout)

    def test_a_noticed_suit_reports_noticed(self):
        _board_in_throwaway_root(self.hroot)
        r1 = self.cli("case", "notice", "--case", self.case, "--respondent", "orso",
                     "--task-id", "T-900")
        self.assertEqual(r1.returncode, 0, r1.stderr)
        r2 = self.show(self.case)
        self.assertIn("Suit state: noticed", r2.stdout)
        self.assertIn("not ratified", r2.stdout + r1.stdout)

    def test_an_answered_suit_reports_answered(self):
        act = self.answer_act("orso", "T-9", self.case)
        r1 = self.cli("case", "answer", "--case", self.case, "--seq", str(act["seq"]))
        self.assertEqual(r1.returncode, 0, r1.stderr)
        r2 = self.show(self.case)
        self.assertIn("Suit state: answered", r2.stdout)

    def test_a_judged_suit_reports_judged(self):
        vact = self.verdict_act("judge1", "T-9", self.case)
        r1 = self.cli("case", "verdict", "--case", self.case, "--judge", "judge1",
                     "--seq", str(vact["seq"]), "--task", "T-9")
        self.assertEqual(r1.returncode, 0, r1.stderr)
        r2 = self.show(self.case)
        self.assertIn("Suit state: judged", r2.stdout)
        self.assertIn("Linked verdict act: judge1#{}".format(vact["seq"]), r2.stdout)

    def test_an_appealed_suit_reports_appealed_to_the_operator_and_freezes(self):
        vact = self.verdict_act("judge1", "T-9", self.case)
        r1 = self.cli("case", "verdict", "--case", self.case, "--judge", "judge1",
                     "--seq", str(vact["seq"]), "--task", "T-9")
        self.assertEqual(r1.returncode, 0, r1.stderr)
        aact = self.appeal_act("orso", "T-9", self.case)
        r2 = self.cli("case", "appeal", "--case", self.case, "--by", "orso",
                     "--seq", str(aact["seq"]))
        self.assertEqual(r2.returncode, 0, r2.stderr)
        r3 = self.show(self.case)
        self.assertIn("Suit state: appealed to the operator", r3.stdout)
        self.assertIn("FROZEN until the operator rules", r3.stdout)
        self.assertIn("not ratified", r3.stdout)

    def test_no_window_deadline_lapse_or_amount_is_ever_computed_in_show(self):
        """Mirrors test_precedent_t468_suits.py's own damages-cap pin: the suit-state/
        linked-act machinery in `case show` names no date arithmetic and no amount."""
        import inspect
        for fn in (precedent._suit_state, precedent._linked_acts,
                  precedent._act_retraction_note, precedent.cmd_case_show):
            src = inspect.getsource(fn)
            for forbidden in ("deadline", "lapse", "7200", "25%", "0.25"):
                self.assertNotIn(forbidden, src)

    def test_a_retracted_claim_act_is_reported_at_show_time(self):
        act = self.commit_and_contest()
        r1 = self.cli("case", "claim", "--case", self.case, "--claimant-seq", str(act["seq"]))
        self.assertEqual(r1.returncode, 0, r1.stderr)
        attest.retract(self.hroot, "aurelia", self.keys["aurelia"], act["seq"],
                      "filed in error")
        r2 = self.show(self.case)
        self.assertIn("RETRACTED by aurelia", r2.stdout)

    def test_an_unretracted_claim_act_shows_no_retraction_note(self):
        act = self.commit_and_contest()
        r1 = self.cli("case", "claim", "--case", self.case, "--claimant-seq", str(act["seq"]))
        self.assertEqual(r1.returncode, 0, r1.stderr)
        r2 = self.show(self.case)
        self.assertNotIn("RETRACTED", r2.stdout)


# ----------------------------------------------------------------------------------
# An ordinary non-suit case stays byte-for-byte unchanged (AC-4)
# ----------------------------------------------------------------------------------

class TheOrdinaryCaseIsUntouched(SuitCase):

    def test_notice_on_a_suit_case_does_not_disturb_a_sibling_plain_case(self):
        self.open_case(question="plain case", task="T-1")
        plain_case = self.last_case_id()
        before = self.load_case(plain_case)
        self.open_case(question="suit", task="T-2", claimant="a", respondent="b",
                       contract="T-100")
        after = self.load_case(plain_case)
        self.assertEqual(before, after)
        self.assertNotIn("suit", after)

    def test_a_plain_case_show_is_byte_for_byte_the_pre_suit_rendering(self):
        """Pinned golden: no suit-state line, no linked-act line, nothing else."""
        import re
        self.open_case(question="plain q", task="T-1")
        plain = self.last_case_id()
        r = self.show(plain)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = re.sub(r"at \d{4}-\d{2}-\d{2}T[\d:]+Z", "at <ts>", r.stdout)
        self.assertEqual(got, "Case {}\n  Question:  plain q\n  Task:      T-1\n"
                              "  Opened by: main at <ts>\n  Status:    open\n".format(plain))

    def test_notice_on_a_plain_case_leaves_its_record_without_a_suit_block(self):
        self.open_case(question="plain case", task="T-1")
        plain = self.last_case_id()
        before = self.load_case(plain)
        _board_in_throwaway_root(self.hroot)
        r = self.cli("case", "notice", "--case", plain, "--respondent", "orso",
                    "--task-id", "T-901")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.load_case(plain), before)

    def test_case_answer_on_a_plain_case_refuses_and_writes_nothing(self):
        self.open_case(question="plain case", task="T-1")
        plain = self.last_case_id()
        before = self.load_case(plain)
        r = self.cli("case", "answer", "--case", plain, "--seq", "1")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.load_case(plain), before)

    def test_case_claim_on_a_plain_case_refuses_and_writes_nothing(self):
        self.open_case(question="plain case", task="T-1")
        plain_case = self.last_case_id()
        before = self.load_case(plain_case)
        r = self.cli("case", "claim", "--case", plain_case, "--claimant-seq", "1")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.load_case(plain_case), before)


if __name__ == "__main__":
    unittest.main()
