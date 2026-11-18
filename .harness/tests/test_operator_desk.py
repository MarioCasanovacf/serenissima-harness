"""Tests for operator_desk.py (design T-484 sections 3, 5 and 8).

Everything runs in throwaway roots and throwaway git repositories. The only remote any
test pushes to is a bare repository inside its own temporary directory. No test calls a
model or touches the live board, the live rulings or the live decisions.

Leak fixtures are assembled from pieces so that this file itself holds no leak.
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".harness" / "bin"
sys.path.insert(0, str(BIN_DIR))
import operator_desk as od  # noqa: E402

HOME_LEAK = "/Us" + "ers/jdoe/project/file.py"
LINUX_LEAK = "/ho" + "me/jdoe/project"
TMP_LEAK = "/pri" + "vate/tm" + "p/scratch"
KEY_LEAK = "-----BEGIN OPENSSH " + "PRIVATE KEY-----"
EMOJI_LEAK = "done \U0001F600"


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def tree_digest(root):
    out = {}
    for p in sorted(pathlib.Path(root).rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            out[str(p.relative_to(root))] = sha(p)
    return out


class Fixture(unittest.TestCase):
    """A throwaway root: copied harness tools, an empty board, a git repository."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = pathlib.Path(self._tmp.name)
        self.root = self.base / "repo"
        (self.root / ".harness").mkdir(parents=True)
        shutil.copytree(str(BIN_DIR), str(self.root / ".harness" / "bin"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (self.root / ".harness" / "tasks").mkdir()
        (self.root / ".harness" / "locks").mkdir()
        (self.root / ".harness" / "logs").mkdir()
        (self.root / ".harness" / "blackboard.json").write_text(json.dumps(
            {"schema_version": "0.1.0", "generation": 1, "tasks": {}, "announcements": []}))
        (self.root / ".harness" / "state.json").write_text(json.dumps({"limits": {}}))
        self.git("init", "-q")
        self.git("config", "user.email", "desk@example.invalid")
        self.git("config", "user.name", "Desk Test")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", os.devnull)
        (self.root / ".gitignore").write_text("ignored.txt\n__pycache__/\n.harness/logs/\n")

    # -- helpers
    def git(self, *args, cwd=None, check=True):
        cp = subprocess.run(["git"] + list(args), cwd=str(cwd or self.root),
                            universal_newlines=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
        if check and cp.returncode != 0:
            raise AssertionError("git {} failed: {}".format(args, cp.stderr))
        return cp.stdout.strip()

    def bb(self, *args, agent="worker-x"):
        env = dict(os.environ)
        env.pop("CLAUDE_HARNESS_AGENT_ID", None)
        cp = subprocess.run(
            [sys.executable, str(self.root / ".harness" / "bin" / "blackboard.py")]
            + list(args) + ["--agent", agent], cwd=str(self.root), env=env,
            universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(cp.returncode, 0, cp.stderr + cp.stdout)
        return cp.stdout

    def board(self):
        return json.loads((self.root / ".harness" / "blackboard.json").read_text())

    def task_in_review(self, tid="T-001", producer="worker-x"):
        self.bb("add-task", "--id", tid, "--title", "a task", agent="coordinator")
        self.bb("claim", tid, agent=producer)
        self.bb("handoff", tid, "--to-role", "verifier", "--note", "built", agent=producer)
        self.assertEqual(self.board()["tasks"][tid]["status"], "review")

    def card(self, did="D-001", options=("yes", "no"), **extra):
        d = {"id": did, "title": "a title", "question": "plain words",
             "recommendation": options[0], "if_yes": "A happens", "if_no": "B happens",
             "options": list(options), "blocks": [], "status": "open",
             "created": "2026-11-17"}
        d.update(extra)
        p = self.root / ".harness" / "decisions" / (did + ".json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, indent=2))
        return p

    def run_file(self, rid="run-1", status="awaiting_operator", gate=None, **extra):
        run = {"id": rid, "flow": "speed-wave", "mode": "agents", "status": status,
               "started": "2026-11-17T10:00:00Z", "steps": [],
               "gate": gate if gate is not None else {"status": "pending",
                                                      "suite": {"passed": 12, "failed": 0}}}
        run.update(extra)
        p = self.root / ".harness" / "runs" / rid / "run.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(run, indent=2))
        return p

    def commit_all(self, msg="base"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def msgfile(self, text):
        p = self.base / "msg.txt"
        p.write_text(text)
        return p


# ---------------------------------------------------------------- leak scan

class LeakScanPins(unittest.TestCase):
    """LEAK_PATTERNS is the one list of patterns; these tests pin it."""

    def test_pattern_names_are_pinned(self):
        self.assertEqual([n for n, _ in od.LEAK_PATTERNS], [
            "home-path-macos", "home-path-linux", "home-path-windows", "temp-path",
            "private-key-block", "chat-bot-token", "api-key", "emoji"])

    def test_each_pattern_hits_its_positive_and_misses_its_negative(self):
        samples = {
            "home-path-macos": (HOME_LEAK, "/Users/<user>/project"),
            "home-path-linux": (LINUX_LEAK, "/home/<user>/project"),
            "home-path-windows": ("C:" + "\\Us" + "ers\\jdoe\\x", "C:\\Users\\<user>\\x"),
            "temp-path": (TMP_LEAK, "<tmp>/scratch and mktemp-style names"),
            "private-key-block": (KEY_LEAK, "-----BEGIN PUBLIC KEY-----"),
            "chat-bot-token": ("12345678" + ":" + "A" * 35, "12:short"),
            "api-key": ("sk" + "-" + "a" * 24, "sk-short"),
            "emoji": (EMOJI_LEAK, "an em dash \u2014 and an arrow \u2192"),
        }
        self.assertEqual(set(samples), {n for n, _ in od.LEAK_PATTERNS})
        for name, rx in od.LEAK_PATTERNS:
            pos, neg = samples[name]
            self.assertTrue(rx.search(pos), name)
            self.assertFalse(rx.search(neg), name)

    def test_scan_text_names_rule_and_never_echoes_the_match(self):
        hits = od.scan_text("ok\nsee " + HOME_LEAK, "f.py")
        self.assertEqual([(h["where"], h["line"], h["rule"]) for h in hits],
                         [("f.py", 2, "home-path-macos")])
        self.assertNotIn("jdoe", json.dumps(hits))

    def test_runtime_literals_flag_this_machines_user_and_home(self):
        with mock.patch.object(od.getpass, "getuser", return_value="fixtureuser"), \
                mock.patch.dict(os.environ, {"HOME": "/fixture/homedir"}):
            hits = od.scan_text("by fixtureuser at /fixture/homedir/x", "n")
            self.assertEqual({h["rule"] for h in hits}, {"os-username", "home-directory"})
            self.assertEqual(od.scan_text("fixtureusers and notfixtureuser", "n"), [])

    def test_generic_account_names_are_not_literals(self):
        with mock.patch.object(od.getpass, "getuser", return_value="root"):
            self.assertEqual(od.scan_text("the root of the problem", "n"), [])

    def test_operator_terms_from_env_and_argument(self):
        with mock.patch.dict(os.environ, {od.LEAK_TERMS_ENV: "sibling-one, sibling-two"}):
            self.assertEqual([h["rule"] for h in od.scan_text("see Sibling-One", "n")],
                             ["operator-term"])
        self.assertEqual([h["rule"] for h in od.scan_text("see sibling-three", "n",
                                                          extra=["sibling-three"])],
                         ["operator-term"])

    def test_private_paths_are_refused_by_name(self):
        for p in (".harness/keys/agent", "a/id_ed25519", "x/cert.pem",
                  ".harness/notify_config.json", ".env.local"):
            self.assertTrue(od.scan_path_name(p), p)
        for p in (".harness/trust/root.pub", "a/id_ed25519.pub", "docs/keys.md"):
            self.assertEqual(od.scan_path_name(p), [], p)

    def test_only_added_lines_of_a_diff_are_scanned(self):
        diff = ("+++ b/a.txt\n-" + HOME_LEAK + "\n " + HOME_LEAK + "\n+clean line\n"
                "+++ b/b.txt\n+" + HOME_LEAK + "\n")
        hits = od._scan_added(diff)
        self.assertEqual([(h["where"], h["rule"]) for h in hits], [("b.txt", "home-path-macos")])


# ---------------------------------------------------------------- decisions and rulings

class DecisionsAndRulings(Fixture):
    def test_decisions_lists_cards_with_their_ruling(self):
        self.card("D-001")
        self.card("D-002", options=("a", "b", "c"))
        cards, problems = od.decisions(self.root)
        self.assertEqual([c["id"] for c in cards], ["D-001", "D-002"])
        self.assertEqual(problems, [])
        self.assertIsNone(cards[0]["ruling"])
        od.rule(self.root, "D-001", "yes")
        ruled, _ = od.decisions(self.root, "ruled")
        self.assertEqual([c["id"] for c in ruled], ["D-001"])
        self.assertEqual(ruled[0]["ruling"]["choice"], "yes")
        opened, _ = od.decisions(self.root, "open")
        self.assertEqual([c["id"] for c in opened], ["D-002"])

    def test_a_broken_card_is_reported_not_dropped(self):
        self.card("D-001")
        (self.root / ".harness" / "decisions" / "D-002.json").write_text("{not json")
        (self.root / ".harness" / "decisions" / "D-003.json").write_text(
            json.dumps({"id": "D-003", "title": "t"}))
        cards, problems = od.decisions(self.root)
        self.assertEqual([c["id"] for c in cards], ["D-001"])
        self.assertEqual(sorted(p["file"] for p in problems), ["D-002.json", "D-003.json"])

    def test_no_directories_means_an_empty_list(self):
        self.assertEqual(od.decisions(self.root), ([], []))

    def test_rule_writes_one_new_r_file_in_the_design_shape_and_flips_the_card(self):
        cardp = self.card("D-001", blocks=["T-123"])
        rec = od.rule(self.root, "D-001", "yes", "because", via="console")
        self.assertEqual(set(rec), {"id", "decision", "choice", "note", "ts", "by", "via"})
        self.assertEqual((rec["id"], rec["decision"], rec["choice"], rec["note"], rec["by"],
                          rec["via"]), ("R-001", "D-001", "yes", "because", "operator", "console"))
        self.assertRegex(rec["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        on_disk = json.loads((self.root / ".harness" / "rulings" / "R-001.json").read_text())
        self.assertEqual(on_disk, rec)
        card = json.loads(cardp.read_text())
        self.assertEqual(card["status"], "ruled")
        self.assertEqual(card["ruling"], "R-001")
        self.assertEqual(card["blocks"], ["T-123"])
        self.assertEqual(card["question"], "plain words")

    def test_rulings_append_never_rewrite(self):
        self.card("D-001")
        self.card("D-002")
        od.rule(self.root, "D-001", "yes")
        first = sha(self.root / ".harness" / "rulings" / "R-001.json")
        od.rule(self.root, "D-002", "no")
        self.assertEqual(sha(self.root / ".harness" / "rulings" / "R-001.json"), first)
        self.assertTrue((self.root / ".harness" / "rulings" / "R-002.json").is_file())

    def test_dated_records_are_never_touched(self):
        dated = self.write(".harness/operator-rulings-2026-11-17.md", "# signed record\n")
        coord = self.write(".harness/coordinator-decisions-x.md", "# decisions\n")
        before = (sha(dated), sha(coord))
        self.card("D-001")
        od.rule(self.root, "D-001", "yes")
        self.assertEqual((sha(dated), sha(coord)), before)

    def test_a_decision_cannot_be_ruled_twice(self):
        self.card("D-001")
        od.rule(self.root, "D-001", "yes")
        before = tree_digest(self.root / ".harness" / "rulings")
        with self.assertRaises(od.Refused):
            od.rule(self.root, "D-001", "no")
        self.assertEqual(tree_digest(self.root / ".harness" / "rulings"), before)

    def test_refusals_write_nothing(self):
        self.card("D-001")
        self.card("D-002", status="ruled")
        before = tree_digest(self.root / ".harness")
        for args in (("D-001", "maybe"), ("D-009", "yes"), ("../D-001", "yes"), ("D-002", "yes"),
                     ("D-001", "yes", "see " + HOME_LEAK)):
            with self.assertRaises(od.Refused, msg=str(args)):
                od.rule(self.root, *args)
        with self.assertRaises(od.Refused):
            od.rule(self.root, "D-001", "yes", via="web")
        self.assertEqual(tree_digest(self.root / ".harness"), before)

    def test_an_interrupted_ruling_is_completed_not_duplicated(self):
        cardp = self.card("D-001")
        od.rule(self.root, "D-001", "yes")
        card = json.loads(cardp.read_text())
        card["status"] = "open"
        card.pop("ruling")
        cardp.write_text(json.dumps(card))
        with self.assertRaises(od.Refused):
            od.rule(self.root, "D-001", "no")
        self.assertEqual(json.loads(cardp.read_text())["status"], "ruled")
        self.assertEqual(len(list((self.root / ".harness" / "rulings").glob("R-*.json"))), 1)

    def test_concurrent_rulings_get_distinct_ids(self):
        for i in range(1, 9):
            self.card("D-%03d" % i)
        errors = []

        def go(i):
            try:
                od.rule(self.root, "D-%03d" % i, "yes")
            except Exception as e:  # pragma: no cover
                errors.append(e)

        ts = [threading.Thread(target=go, args=(i,)) for i in range(1, 9)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(errors, [])
        rs = sorted((self.root / ".harness" / "rulings").glob("R-*.json"))
        self.assertEqual(len(rs), 8)
        decided = sorted(json.loads(p.read_text())["decision"] for p in rs)
        self.assertEqual(decided, ["D-%03d" % i for i in range(1, 9)])

    def test_cli_round_trip(self):
        self.card("D-001")
        cp = subprocess.run([sys.executable, str(BIN_DIR / "operator_desk.py"), "--root",
                             str(self.root), "rule", "D-001", "--choice", "no", "--json"],
                            universal_newlines=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertEqual(json.loads(cp.stdout)["choice"], "no")
        cp = subprocess.run([sys.executable, str(BIN_DIR / "operator_desk.py"), "--root",
                             str(self.root), "rule", "D-001", "--choice", "no"],
                            universal_newlines=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
        self.assertEqual(cp.returncode, 2)
        self.assertIn("refused", cp.stderr)


# ---------------------------------------------------------------- operator verdict

class OperatorVerdict(Fixture):
    def test_done_closes_a_task_in_review_as_the_operator(self):
        self.task_in_review()
        res = od.verdict(self.root, "T-001", "done", "checked")
        self.assertEqual(res["status"], "done")
        t = self.board()["tasks"]["T-001"]
        self.assertEqual((t["status"], t["completed_by"]), ("done", "operator"))

    def test_open_sends_it_back_with_a_rejected_note(self):
        self.task_in_review()
        res = od.verdict(self.root, "T-001", "open", "tests missing")
        self.assertEqual(res["status"], "open")
        detail = json.loads((self.root / ".harness" / "tasks" / "T-001.json").read_text())
        notes = json.dumps(detail["notes"])
        self.assertIn("REJECTED: tests missing", notes)
        self.assertIn("operator", notes)

    def test_open_needs_a_note(self):
        self.task_in_review()
        before = tree_digest(self.root / ".harness")
        with self.assertRaises(od.Refused):
            od.verdict(self.root, "T-001", "open", "")
        self.assertEqual(tree_digest(self.root / ".harness"), before)

    def test_only_a_task_in_review(self):
        self.bb("add-task", "--id", "T-001", "--title", "t", agent="coordinator")
        self.bb("add-task", "--id", "T-002", "--title", "t", agent="coordinator")
        self.bb("claim", "T-002", agent="worker-x")
        before = sha(self.root / ".harness" / "blackboard.json")
        for tid in ("T-001", "T-002", "T-404"):
            with self.assertRaises(od.Refused, msg=tid):
                od.verdict(self.root, tid, "done")
        self.assertEqual(sha(self.root / ".harness" / "blackboard.json"), before)

    def test_refuses_when_the_operator_produced_it(self):
        self.task_in_review(producer="operator")
        before = tree_digest(self.root / ".harness")
        for outcome in ("done", "open"):
            with self.assertRaises(od.Refused) as cm:
                od.verdict(self.root, "T-001", outcome, "note")
            self.assertIn("producer", str(cm.exception))
        self.assertEqual(self.board()["tasks"]["T-001"]["status"], "review")
        self.assertEqual(tree_digest(self.root / ".harness"), before)

    def test_bad_ids_and_outcomes(self):
        for args in (("../T-001", "done"), ("T-1; rm", "done"), ("T-001", "failed")):
            with self.assertRaises(od.Refused, msg=str(args)):
                od.verdict(self.root, *args)

    def test_a_note_with_a_leak_changes_nothing(self):
        self.task_in_review()
        before = tree_digest(self.root / ".harness")
        with self.assertRaises(od.Refused):
            od.verdict(self.root, "T-001", "done", "see " + HOME_LEAK)
        self.assertEqual(tree_digest(self.root / ".harness"), before)

    def test_blackboards_own_refusal_surfaces_as_refused(self):
        self.task_in_review()
        self.bb("update", "T-001", "--status", "claimed", agent="worker-x")
        # the task moved on: no longer in review, desk refuses before blackboard is asked
        with self.assertRaises(od.Refused):
            od.verdict(self.root, "T-001", "done")

    def test_a_root_without_its_own_blackboard_is_never_served_by_the_live_one(self):
        bare = self.base / "bare"
        (bare / ".harness").mkdir(parents=True)
        (bare / ".harness" / "blackboard.json").write_text(json.dumps({"tasks": {
            "T-001": {"status": "review", "handoff": {"from": "worker-x"}}}}))
        live_board = sha(ROOT / ".harness" / "blackboard.json")
        with self.assertRaises(od.Refused):
            od.verdict(bare, "T-001", "done")
        self.assertEqual(sha(ROOT / ".harness" / "blackboard.json"), live_board)

    def test_never_edits_the_board_directly(self):
        src = (BIN_DIR / "operator_desk.py").read_text()
        self.assertNotIn("BLACKBOARD", src)
        self.assertNotIn('"blackboard.json", "w"', src)


# ---------------------------------------------------------------- wave gate

class WaveGate(Fixture):
    def test_approve_writes_the_decision_into_run_json(self):
        p = self.run_file()
        run = od.record_gate_decision(self.root, "run-1", "approve", "looks good", via="console")
        on_disk = json.loads(p.read_text())
        self.assertEqual(on_disk, run)
        self.assertEqual(on_disk["status"], "approved")
        g = on_disk["gate"]
        self.assertEqual((g["status"], g["by"], g["note"], g["via"]),
                         ("approved", "operator", "looks good", "console"))
        self.assertRegex(g["decided"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(g["suite"], {"passed": 12, "failed": 0})
        self.assertEqual(on_disk["flow"], "speed-wave")
        self.assertEqual(on_disk["steps"], [])

    def test_reject(self):
        self.run_file()
        run = od.record_gate_decision(self.root, "run-1", "reject")
        self.assertEqual((run["status"], run["gate"]["status"]), ("rejected", "rejected"))

    def test_only_a_run_awaiting_the_operator_with_a_pending_gate(self):
        cases = {
            "run-a": dict(status="running"),
            "run-b": dict(status="awaiting_operator", gate={"status": "approved"}),
            "run-c": dict(status="stopped"),
        }
        for rid, kw in cases.items():
            p = self.run_file(rid, **kw)
            before = sha(p)
            with self.assertRaises(od.Refused, msg=rid):
                od.record_gate_decision(self.root, rid, "approve")
            self.assertEqual(sha(p), before)
        nogate = self.run_file("run-d")
        data = json.loads(nogate.read_text())
        del data["gate"]
        nogate.write_text(json.dumps(data))
        with self.assertRaises(od.Refused):
            od.record_gate_decision(self.root, "run-d", "approve")

    def test_a_second_decision_is_refused(self):
        p = self.run_file()
        od.record_gate_decision(self.root, "run-1", "approve")
        after = sha(p)
        with self.assertRaises(od.Refused):
            od.record_gate_decision(self.root, "run-1", "reject")
        self.assertEqual(sha(p), after)

    def test_bad_run_ids_decisions_and_notes(self):
        p = self.run_file()
        before = sha(p)
        for rid in ("../run-1", "run-1/../..", "", ".", "..", "a b"):
            with self.assertRaises(od.Refused, msg=repr(rid)):
                od.record_gate_decision(self.root, rid, "approve")
        with self.assertRaises(od.Refused):
            od.record_gate_decision(self.root, "run-9", "approve")
        with self.assertRaises(od.Refused):
            od.record_gate_decision(self.root, "run-1", "maybe")
        with self.assertRaises(od.Refused):
            od.record_gate_decision(self.root, "run-1", "approve", "at " + HOME_LEAK)
        self.assertEqual(sha(p), before)

    def test_concurrent_decisions_one_wins(self):
        p = self.run_file()
        results = []

        def go(d):
            try:
                od.record_gate_decision(self.root, "run-1", d)
                results.append(d)
            except od.Refused:
                results.append("refused")

        ts = [threading.Thread(target=go, args=(d,)) for d in ("approve", "reject") * 3]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(len([r for r in results if r != "refused"]), 1)
        self.assertIn(json.loads(p.read_text())["status"], ("approved", "rejected"))

    def test_cli(self):
        self.run_file()
        cp = subprocess.run([sys.executable, str(BIN_DIR / "operator_desk.py"), "--root",
                             str(self.root), "gate", "run-1", "--reject", "--note", "no",
                             "--json"], universal_newlines=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertEqual(json.loads(cp.stdout)["gate"]["status"], "rejected")

    def test_the_function_name_flow_runner_calls_exists(self):
        import inspect
        sig = inspect.signature(od.record_gate_decision)
        self.assertEqual(list(sig.parameters)[:4], ["root", "run_id", "decision", "note"])


# ---------------------------------------------------------------- commit

class CommitCase(Fixture):
    def setUp(self):
        super().setUp()
        self.write("README.md", "base\n")
        self.commit_all()
        self.head0 = self.git("rev-parse", "HEAD")

    def head(self):
        return self.git("rev-parse", "HEAD")

    def staged(self):
        return self.git("diff", "--cached", "--name-only")

    def test_clean_commit_shows_the_stat_first_and_commits_the_message_bytes(self):
        self.write("README.md", "base\nmore\n")
        self.write("new.txt", "hello\nworld\n")
        self.write("ignored.txt", "never\n")
        seen = []
        msg = "add things\n\nbody line\n"

        def stat_out(s):
            seen.append((s, self.head()))  # nothing has been committed yet

        res = od.commit(self.root, self.msgfile(msg), stat_out=stat_out)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][1], self.head0)
        self.assertIn("README.md", seen[0][0])
        self.assertIn("new.txt", seen[0][0])
        self.assertTrue(res["committed"])
        self.assertNotEqual(self.head(), self.head0)
        self.assertEqual(self.git("log", "-1", "--format=%B"), msg.strip())
        self.assertEqual(self.git("show", "--name-only", "--format=", "HEAD").split(),
                         ["README.md", "new.txt"])
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_dry_run_scans_and_shows_but_does_not_commit_or_stage(self):
        self.write("new.txt", "hello\n")
        seen = []
        res = od.commit(self.root, self.msgfile("m"), dry_run=True, stat_out=seen.append)
        self.assertFalse(res["committed"])
        self.assertEqual(len(seen), 1)
        self.assertEqual(self.head(), self.head0)
        self.assertEqual(self.staged(), "")

    def assertRefusedClean(self, msg="m", **kw):
        with self.assertRaises(od.Refused) as cm:
            od.commit(self.root, self.msgfile(msg), **kw)
        self.assertEqual(self.head(), self.head0)
        self.assertEqual(self.staged(), "", "a refused commit must not stage anything")
        return str(cm.exception)

    def test_leak_in_an_added_line_of_a_tracked_file_refuses(self):
        self.write("README.md", "base\npath " + HOME_LEAK + "\n")
        why = self.assertRefusedClean()
        self.assertIn("README.md", why)
        self.assertIn("home-path-macos", why)
        self.assertNotIn("jdoe", why)

    def test_leak_in_a_new_untracked_file_refuses(self):
        self.write("docs/new.md", "key\n" + KEY_LEAK + "\n")
        self.assertIn("private-key-block", self.assertRefusedClean())

    def test_leak_in_the_message_refuses(self):
        self.write("new.txt", "fine\n")
        self.assertIn("commit message", self.assertRefusedClean(msg="from " + TMP_LEAK))

    def test_leak_in_a_file_name_refuses(self):
        self.write("docs/" + "jdoe-notes.md", "fine\n")
        self.assertIn("operator-term", self.assertRefusedClean(extra=["jdoe"]))

    def test_private_material_path_refuses(self):
        self.write(".harness/keys/agent-key", "bytes\n")
        # the key directory is not ignored in this throwaway repo, so it is in the change set
        self.assertIn("private-material-path", self.assertRefusedClean())

    def test_emoji_refuses(self):
        self.write("new.txt", EMOJI_LEAK + "\n")
        self.assertIn("emoji", self.assertRefusedClean())

    def test_operator_terms_from_the_environment_refuse(self):
        self.write("new.txt", "mentions sibling-project-zz here\n")
        with mock.patch.dict(os.environ, {od.LEAK_TERMS_ENV: "sibling-project-zz"}):
            self.assertIn("operator-term", self.assertRefusedClean())

    def test_a_leak_committed_long_ago_does_not_block_an_unrelated_change(self):
        self.write("old.txt", HOME_LEAK + "\n")
        self.commit_all("old leak, already public")
        self.head0 = self.head()
        self.write("README.md", "base\nfine\n")
        res = od.commit(self.root, self.msgfile("unrelated"))
        self.assertTrue(res["committed"])

    def test_nothing_to_commit_and_empty_message_and_missing_file(self):
        with self.assertRaises(od.Refused):
            od.commit(self.root, self.msgfile("m"))
        self.write("new.txt", "x\n")
        with self.assertRaises(od.Refused):
            od.commit(self.root, self.msgfile("  \n"))
        with self.assertRaises(od.Refused):
            od.commit(self.root, self.base / "absent.txt")
        self.assertEqual(self.head(), self.head0)

    def test_commit_in_a_repository_with_no_commits_yet(self):
        fresh = self.base / "fresh"
        fresh.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(fresh), check=True)
        for k, v in (("user.email", "d@example.invalid"), ("user.name", "D"),
                     ("commit.gpgsign", "false"), ("core.hooksPath", os.devnull)):
            subprocess.run(["git", "config", k, v], cwd=str(fresh), check=True)
        (fresh / "a.txt").write_text("a\n")
        res = od.commit(fresh, self.msgfile("first"))
        self.assertTrue(res["committed"])
        (fresh / "b.txt").write_text(HOME_LEAK + "\n")
        with self.assertRaises(od.Refused):
            od.commit(fresh, self.msgfile("second"))

    def test_the_sources_never_skip_hooks_or_use_a_broad_flag(self):
        src = (BIN_DIR / "operator_desk.py").read_text()
        self.assertNotIn("--no-verify", src)
        self.assertNotIn('"-n"', src)

    def test_cli_exit_codes(self):
        self.write("new.txt", HOME_LEAK + "\n")
        cp = subprocess.run([sys.executable, str(BIN_DIR / "operator_desk.py"), "--root",
                             str(self.root), "commit", "--message-file",
                             str(self.msgfile("m"))], universal_newlines=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(cp.returncode, 2)
        self.assertIn("refused: leak scan", cp.stderr)
        self.assertEqual(self.head(), self.head0)


# ---------------------------------------------------------------- push

class PushCase(Fixture):
    def setUp(self):
        super().setUp()
        self.remote = self.base / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        self.git("remote", "add", "origin", str(self.remote))
        self.write("README.md", "base\n")
        self.commit_all("base")
        self.git("branch", "-M", "main")
        self.git("push", "-q", "origin", "main")  # test fixture: bare repo in own temp dir
        self.git("checkout", "-q", "-b", "feature/x")
        self.main0 = self.remote_ref("main")

    def remote_ref(self, branch):
        cp = subprocess.run(["git", "--git-dir", str(self.remote), "rev-parse", "--verify", "-q",
                             "refs/heads/" + branch], universal_newlines=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return cp.stdout.strip() or None

    def remote_branches(self):
        out = subprocess.run(["git", "--git-dir", str(self.remote), "for-each-ref",
                              "--format=%(refname:short)"], universal_newlines=True,
                             stdout=subprocess.PIPE).stdout
        return sorted(out.split())

    def add_commit(self, rel="f.txt", text="x\n", msg="work"):
        self.write(rel, text)
        self.commit_all(msg)

    def test_pushes_only_the_current_branch_and_never_touches_main(self):
        self.add_commit()
        seen = []
        res = od.push(self.root, stat_out=seen.append)
        self.assertTrue(res["pushed"])
        self.assertEqual(res["commits"], 1)
        self.assertEqual(len(seen), 1)
        self.assertIn("f.txt", seen[0])
        self.assertEqual(self.remote_ref("feature/x"), self.git("rev-parse", "HEAD"))
        self.assertEqual(self.remote_branches(), ["feature/x", "main"])
        self.assertEqual(self.remote_ref("main"), self.main0)

    def test_dry_run_scans_and_shows_but_sends_nothing(self):
        self.add_commit()
        seen = []
        res = od.push(self.root, dry_run=True, stat_out=seen.append)
        self.assertFalse(res["pushed"])
        self.assertEqual(len(seen), 1)
        self.assertIsNone(self.remote_ref("feature/x"))

    def test_a_second_push_sends_only_what_is_new(self):
        self.add_commit()
        od.push(self.root)
        with self.assertRaises(od.Refused):  # nothing new
            od.push(self.root)
        self.add_commit("g.txt", "y\n", "more")
        res = od.push(self.root)
        self.assertEqual(res["commits"], 1)

    def test_main_and_master_are_never_pushed(self):
        for name in ("main", "master"):
            self.git("checkout", "-q", "-B", name)
            self.add_commit(name + ".txt", "x\n", "on " + name)
            with self.assertRaises(od.Refused) as cm:
                od.push(self.root)
            self.assertIn(name, str(cm.exception))
        self.assertEqual(self.remote_ref("main"), self.main0)
        self.assertIsNone(self.remote_ref("master"))

    def test_detached_head_is_refused(self):
        self.add_commit()
        self.git("checkout", "-q", "--detach")
        with self.assertRaises(od.Refused):
            od.push(self.root)

    def test_a_leak_in_the_tip_commit_refuses_and_sends_nothing(self):
        self.add_commit("leak.txt", HOME_LEAK + "\n", "has leak")
        with self.assertRaises(od.Refused) as cm:
            od.push(self.root)
        self.assertIn("home-path-macos", str(cm.exception))
        self.assertNotIn("jdoe", str(cm.exception))
        self.assertEqual(self.remote_branches(), ["main"])

    def test_a_leak_buried_under_a_clean_commit_still_refuses(self):
        self.add_commit("leak.txt", KEY_LEAK + "\n", "leak")
        self.add_commit("clean.txt", "fine\n", "clean tip")
        with self.assertRaises(od.Refused):
            od.push(self.root)
        self.assertEqual(self.remote_branches(), ["main"])

    def test_a_leak_in_a_commit_message_or_author_refuses(self):
        self.add_commit("a.txt", "ok\n", "from " + TMP_LEAK)
        with self.assertRaises(od.Refused):
            od.push(self.root)
        self.git("commit", "-q", "--amend", "-m", "clean now")
        self.git("config", "user.email", "sibling-q@example.invalid")
        self.git("commit", "-q", "--amend", "--reset-author", "--no-edit")
        with self.assertRaises(od.Refused):
            od.push(self.root, extra=["sibling-q"])
        self.assertEqual(self.remote_branches(), ["main"])

    def test_the_command_has_no_force_and_no_plus_and_no_wide_flags(self):
        cmd = od.build_push_command("origin", "feature/x")
        self.assertEqual(cmd, ["push", "origin", "refs/heads/feature/x:refs/heads/feature/x"])
        bad = {"--force", "-f", "--force-with-lease", "--force-if-includes", "--mirror",
               "--all", "--tags", "--delete", "-d", "--prune"}
        self.assertFalse(bad & set(cmd))
        self.assertFalse([a for a in cmd if a.startswith(("+", "-"))])

    def test_every_git_call_a_push_makes_is_free_of_force_flags(self):
        self.add_commit()
        calls = []
        real = od._git

        def spy(root, *args, **kw):
            calls.append(list(args))
            return real(root, *args, **kw)

        with mock.patch.object(od, "_git", spy):
            od.push(self.root)
        pushes = [c for c in calls if c and c[0] == "push"]
        self.assertEqual(len(pushes), 1)
        for c in calls:
            for a in c:
                self.assertNotIn(a, ("--force", "-f", "--force-with-lease", "--mirror",
                                     "--all", "--tags"))
                self.assertFalse(a.startswith("+"), c)

    def test_remote_and_branch_names_that_look_like_options_are_refused(self):
        for remote in ("--upload-pack=x", "-o", "a b", ""):
            with self.assertRaises(od.Refused, msg=remote):
                od.build_push_command(remote, "feature/x")
        for branch in ("-d", "a..b", "x.lock", "a b", ""):
            with self.assertRaises(od.Refused, msg=branch):
                od.build_push_command("origin", branch)

    def test_unknown_remote_is_refused(self):
        self.add_commit()
        with self.assertRaises(od.Refused):
            od.push(self.root, remote="nowhere")

    def test_a_diverged_remote_is_refused_by_git_and_left_alone(self):
        self.add_commit()
        od.push(self.root)
        # someone else moved the remote branch
        other = self.base / "other"
        subprocess.run(["git", "clone", "-q", "-b", "feature/x", str(self.remote), str(other)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for k, v in (("user.email", "o@example.invalid"), ("user.name", "O"),
                     ("commit.gpgsign", "false"), ("core.hooksPath", os.devnull)):
            subprocess.run(["git", "config", k, v], cwd=str(other), check=True)
        (other / "o.txt").write_text("o\n")
        subprocess.run(["git", "add", "-A"], cwd=str(other), check=True)
        subprocess.run(["git", "commit", "-q", "-m", "o"], cwd=str(other), check=True)
        subprocess.run(["git", "push", "-q", "origin", "feature/x"], cwd=str(other), check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        theirs = self.remote_ref("feature/x")
        # ours diverges from theirs
        self.git("reset", "-q", "--hard", "HEAD~1")
        self.add_commit("mine.txt", "m\n", "mine")
        self.git("update-ref", "refs/remotes/origin/feature/x",
                 self.git("rev-parse", "HEAD~1"))
        with self.assertRaises(od.Refused):
            od.push(self.root)
        self.assertEqual(self.remote_ref("feature/x"), theirs)

    def test_a_configured_wide_push_refspec_does_not_widen_the_push(self):
        self.git("config", "remote.origin.push", "+refs/heads/*:refs/heads/*")
        self.git("config", "push.default", "matching")
        self.add_commit()
        od.push(self.root)
        self.assertEqual(self.remote_branches(), ["feature/x", "main"])
        self.assertEqual(self.remote_ref("main"), self.main0)

    def test_cli_refusal_exit_code(self):
        self.add_commit("leak.txt", HOME_LEAK + "\n", "leak")
        cp = subprocess.run([sys.executable, str(BIN_DIR / "operator_desk.py"), "--root",
                             str(self.root), "push"], universal_newlines=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(cp.returncode, 2)
        self.assertEqual(self.remote_branches(), ["main"])


# ---------------------------------------------------------------- repository hygiene

class RepoHygiene(unittest.TestCase):
    def test_readmes_exist_for_the_two_directories(self):
        for d in ("decisions", "rulings"):
            self.assertTrue((ROOT / ".harness" / d / "README.md").is_file(), d)

    def test_no_leak_in_the_files_this_task_ships(self):
        files = [BIN_DIR / "operator_desk.py", pathlib.Path(__file__),
                 ROOT / ".harness" / "decisions" / "README.md",
                 ROOT / ".harness" / "rulings" / "README.md"]
        for f in files:
            hits = od.scan_text(f.read_text(encoding="utf-8"), f.name)
            self.assertEqual(hits, [], f.name)

    def test_no_model_or_network_modules(self):
        src = (BIN_DIR / "operator_desk.py").read_text()
        for word in ("urllib", "http.client", "socket", "requests", "anthropic"):
            self.assertNotIn("import " + word, src)


if __name__ == "__main__":
    unittest.main()
