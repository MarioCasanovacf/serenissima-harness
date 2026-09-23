"""Hermetic tests for `blackboard.py redact` (T-430 round 2).

The verb exists because an operator identifier sat inside an old handoff note
and blackboard.py, the only sanctioned writer of the board, had no way to take
text back out. These tests build a throwaway harness tree, drive the real CLI
over it by subprocess, and touch nothing under the repository.

The literal below is synthetic. It stands in for whatever leaked; no real
identifier appears in this file.

Discrimination: every test here fails against a blackboard.py without the verb.

    git show <commit-before-the-verb>:.harness/bin/blackboard.py > <scratch>/bb_old.py
    HARNESS_TEST_BB_SRC=<scratch>/bb_old.py python3 -m pytest -q .harness/tests/test_blackboard_redact.py

The refusal tests assert the verb's own refusal text, not just a nonzero exit,
so an argparse "invalid choice" error from the old CLI cannot pass them.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_BIN = REPO_ROOT / ".harness" / "bin"
BB_SRC = Path(os.environ.get("HARNESS_TEST_BB_SRC", REPO_BIN / "blackboard.py"))

LITERAL = "zq-withheld-token-77"
REPLACEMENT = "<withheld>"

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


class RedactVerb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="harness-redact-")
        cls.root = Path(cls._tmp)
        bindir = cls.root / ".harness" / "bin"
        shutil.copytree(REPO_BIN, bindir, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(BB_SRC, bindir / "blackboard.py")
        for sub in ("locks", "logs", "tasks"):
            (cls.root / ".harness" / sub).mkdir(parents=True, exist_ok=True)
        cls.bb = bindir / "blackboard.py"
        cls.scratch = cls.root / "scratch"
        cls.scratch.mkdir()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        h = self.root / ".harness"
        (h / "blackboard.json").write_text(json.dumps({
            "schema_version": "0.1.0", "generation": 0, "tasks": {}, "epics": {},
            "updated_at": "2026-09-22T00:00:00Z", "updated_by": "test-init",
        }))
        (h / "state.json").write_text(json.dumps(FRESH_STATE))
        (h / "logs" / "events.jsonl").write_text("")
        for leftover in (h / "tasks").glob("*.json"):
            leftover.unlink()
        self.literal_file = self.write_scratch("literal.txt", LITERAL + "\n")
        self.note_file = self.write_scratch("why.txt", "scrub a leaked identifier before publishing")

    # ---- helpers -----------------------------------------------------------
    def write_scratch(self, name, text):
        p = self.scratch / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(self.bb), *args],
                              capture_output=True, text=True, cwd=str(self.root))

    def board_path(self):
        return self.root / ".harness" / "blackboard.json"

    def task_path(self, tid):
        return self.root / ".harness" / "tasks" / "{}.json".format(tid)

    def snapshot(self):
        """Every board byte: blackboard.json plus each tasks/*.json."""
        h = self.root / ".harness"
        snap = {"blackboard.json": (h / "blackboard.json").read_bytes()}
        for p in sorted((h / "tasks").glob("*.json")):
            snap["tasks/" + p.name] = p.read_bytes()
        return snap

    def events(self, kind):
        out = []
        for line in (self.root / ".harness" / "logs" / "events.jsonl").read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec.get("event") == kind:
                    out.append(rec)
        return out

    def seed_leak(self):
        """T-001 carries the literal in its handoff note (board index) and in a detail-file
        note; T-002 carries none and must come through byte-identical."""
        self.cli("add-task", "--agent", "planner", "--id", "T-001", "--title", "leaky", "--role", "worker")
        self.cli("add-task", "--agent", "planner", "--id", "T-002", "--title", "clean", "--role", "worker")
        self.cli("claim", "T-001", "--agent", "worker-A")
        leak = self.write_scratch("leak.txt", "ran: grep -n \"{}\" file -> no output".format(LITERAL))
        self.cli("update", "T-001", "--status", "in_progress", "--agent", "worker-A", "--note-file", leak)
        r = self.cli("handoff", "T-001", "--to-role", "verifier", "--agent", "worker-A", "--note-file", leak)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(LITERAL, self.board_path().read_text())
        self.assertIn(LITERAL, self.task_path("T-001").read_text())

    def redact(self, *extra):
        return self.cli("redact", "--agent", "scrubber", "--literal-file", self.literal_file,
                        "--replacement", REPLACEMENT, *extra)

    # ---- the verb does its job ---------------------------------------------
    def test_removes_every_occurrence_and_keeps_the_rest(self):
        self.seed_leak()
        before = self.snapshot()
        before_board = json.loads(before["blackboard.json"])
        r = self.redact("--note-file", self.note_file)
        self.assertEqual(r.returncode, 0, r.stderr)
        after = self.snapshot()
        for name, data in after.items():
            self.assertNotIn(LITERAL.encode(), data, name)
        # A file without the literal is untouched, byte for byte.
        self.assertEqual(before["tasks/T-002.json"], after["tasks/T-002.json"])
        # In the board, the only changes are the replaced string and the save stamp.
        after_board = json.loads(after["blackboard.json"])
        expected = json.loads(before["blackboard.json"].decode().replace(LITERAL, REPLACEMENT))
        for key in ("updated_at", "updated_by"):
            expected.pop(key)
            after_board.pop(key)
        self.assertEqual(expected, after_board)
        self.assertEqual(
            after_board["tasks"]["T-001"]["handoff"]["note"],
            before_board["tasks"]["T-001"]["handoff"]["note"].replace(LITERAL, REPLACEMENT))

    def test_appends_a_redacted_note_and_logs_the_hash_not_the_literal(self):
        self.seed_leak()
        r = self.redact("--note-file", self.note_file)
        self.assertEqual(r.returncode, 0, r.stderr)
        notes = json.loads(self.task_path("T-001").read_text())["notes"]
        self.assertTrue(notes[-1]["note"].startswith("REDACTED:"), notes[-1])
        self.assertEqual(notes[-1]["agent"], "scrubber")
        self.assertIn(REPLACEMENT, notes[-1]["note"])
        self.assertIn("scrub a leaked identifier", notes[-1]["note"])
        self.assertEqual(json.loads(self.task_path("T-002").read_text())["notes"], [])
        events = self.events("notes_redacted")
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["agent"], "scrubber")
        self.assertEqual(ev["literal_sha256"], hashlib.sha256(LITERAL.encode()).hexdigest())
        self.assertEqual(ev["tasks"], ["T-001"])
        self.assertEqual(sum(ev["files"].values()), ev["occurrences"])
        self.assertNotIn(LITERAL, json.dumps(ev))

    def test_dry_run_counts_and_writes_nothing(self):
        self.seed_leak()
        before = self.snapshot()
        r = self.redact("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("dry run:", r.stdout)
        self.assertIn(".harness/blackboard.json: 1 occurrence(s)", r.stdout)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.events("notes_redacted"), [])

    def test_second_run_finds_nothing_and_changes_nothing(self):
        self.seed_leak()
        self.assertEqual(self.redact("--note-file", self.note_file).returncode, 0)
        before = self.snapshot()
        r = self.redact("--note-file", self.note_file)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no occurrences of the literal", r.stdout)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(len(self.events("notes_redacted")), 1)
        dry = self.redact("--dry-run")
        self.assertIn("dry run: 0 occurrence(s) in 0 file(s)", dry.stdout)

    # ---- the verb refuses, and says why ------------------------------------
    def assert_refused(self, r, phrase):
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("refused", r.stderr)
        self.assertIn(phrase, r.stderr)

    def test_refuses_without_a_note(self):
        self.seed_leak()
        before = self.snapshot()
        self.assert_refused(self.redact(), "no note means no redaction")
        self.assertEqual(before, self.snapshot())

    def test_refuses_a_note_that_contains_the_literal(self):
        self.seed_leak()
        before = self.snapshot()
        bad = self.write_scratch("bad-why.txt", "removing {} from notes".format(LITERAL))
        self.assert_refused(self.redact("--note-file", bad), "the note contains the literal")
        self.assertEqual(before, self.snapshot())

    def test_refuses_a_replacement_that_keeps_the_literal(self):
        self.seed_leak()
        before = self.snapshot()
        r = self.cli("redact", "--agent", "scrubber", "--literal-file", self.literal_file,
                     "--replacement", "x" + LITERAL, "--note-file", self.note_file)
        self.assert_refused(r, "--replacement contains the literal")
        self.assertEqual(before, self.snapshot())

    def test_refuses_a_literal_too_short_to_be_specific(self):
        self.seed_leak()
        before = self.snapshot()
        short = self.write_scratch("short.txt", "ran")
        r = self.cli("redact", "--agent", "scrubber", "--literal-file", short,
                     "--replacement", REPLACEMENT, "--note-file", self.note_file)
        self.assert_refused(r, "at least 4")
        self.assertEqual(before, self.snapshot())

    def test_refuses_to_rewrite_an_identifier(self):
        # "T-00" is a prefix of the task ids, which are keys on the board.
        self.seed_leak()
        before = self.snapshot()
        ident = self.write_scratch("ident.txt", "T-00")
        r = self.cli("redact", "--agent", "scrubber", "--literal-file", ident,
                     "--replacement", REPLACEMENT, "--note-file", self.note_file)
        self.assert_refused(r, "never rewrites them")
        self.assertEqual(before, self.snapshot())

    def test_refuses_when_a_task_file_cannot_be_read(self):
        self.seed_leak()
        self.task_path("T-009").write_text("{ not json")
        before = self.snapshot()
        self.assert_refused(self.redact("--note-file", self.note_file), "T-009.json")
        self.assertEqual(before, self.snapshot())

    def test_literal_is_not_accepted_on_argv(self):
        r = self.cli("redact", "--agent", "scrubber", "--literal", LITERAL,
                     "--replacement", REPLACEMENT, "--note-file", self.note_file)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--literal-file", r.stderr)


if __name__ == "__main__":
    unittest.main()
