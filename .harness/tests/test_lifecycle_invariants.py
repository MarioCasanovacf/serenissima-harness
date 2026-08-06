"""Hermetic lifecycle-invariant tests for blackboard.py.

Every prior suite either tested adapters/guards or (test_codex_integration)
ran the CLI against the LIVE board, so the core state-machine invariants had
zero coverage -- exactly where the terminal-state / double-credit / lease bugs
lived. These tests build a throwaway harness tree in a TemporaryDirectory and
drive the real CLI over it via subprocess, so they touch nothing under the repo
and model how the system is actually invoked.

To prove a test genuinely catches a regression, point it at an older blackboard
via HARNESS_TEST_BB_SRC and watch the relevant cases fail:

    git show HEAD:.harness/bin/blackboard.py > /tmp/bb_orig.py
    HARNESS_TEST_BB_SRC=/tmp/bb_orig.py python3 .harness/tests/test_lifecycle_invariants.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_BIN = REPO_ROOT / ".harness" / "bin"
# Allow swapping in an alternate blackboard.py (e.g. the pre-fix version) to
# confirm these tests actually fail without the fixes.
BB_SRC = Path(os.environ.get("HARNESS_TEST_BB_SRC", REPO_BIN / "blackboard.py"))

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


class LifecycleInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="harness-invariants-")
        cls.root = Path(cls._tmp)
        bindir = cls.root / ".harness" / "bin"
        shutil.copytree(REPO_BIN, bindir)
        # Overlay the blackboard under test (defaults to a verbatim copy).
        shutil.copy(BB_SRC, bindir / "blackboard.py")
        for sub in ("locks", "logs", "tasks"):
            (cls.root / ".harness" / sub).mkdir(parents=True, exist_ok=True)
        cls.bb = bindir / "blackboard.py"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        # Fresh board + state before every test.
        h = self.root / ".harness"
        (h / "blackboard.json").write_text(json.dumps({
            "schema_version": "0.1.0", "generation": 0, "tasks": {}, "epics": {},
            "updated_at": "2026-08-05T00:00:00Z", "updated_by": "test-init",
        }))
        (h / "state.json").write_text(json.dumps(FRESH_STATE))
        (h / "logs" / "events.jsonl").write_text("")
        for leftover in (h / "tasks").glob("*.json"):
            leftover.unlink()

    # ---- helpers -----------------------------------------------------------
    def cli(self, *args):
        return subprocess.run([sys.executable, str(self.bb), *args],
                              capture_output=True, text=True, cwd=str(self.root))

    def task(self, tid):
        data = json.loads((self.root / ".harness" / "blackboard.json").read_text())
        return data["tasks"][tid]

    def reputation(self):
        return json.loads((self.root / ".harness" / "state.json").read_text())["agents"]["reputation"]

    def seed_reviewed(self, tid="T-001", producer="worker-A"):
        """Create a worker task and carry it to 'review' via a real handoff."""
        self.cli("add-task", "--agent", "planner", "--id", tid, "--title", "x",
                 "--role", "worker", "--engine", "any")
        self.cli("claim", tid, "--agent", producer)
        self.cli("update", tid, "--status", "in_progress", "--agent", producer, "--note", "plan")
        self.cli("handoff", tid, "--to-role", "verifier", "--agent", producer, "--note", "done, replay: true")

    # ---- pre-existing invariants (were untested) ---------------------------
    def test_cascade_gate_blocks_dependent(self):
        self.cli("add-task", "--agent", "p", "--id", "T-001", "--title", "a", "--role", "worker", "--engine", "any")
        self.cli("add-task", "--agent", "p", "--id", "T-002", "--title", "b", "--role", "verifier",
                 "--engine", "any", "--depends-on", "T-001")
        r = self.cli("claim", "T-002", "--agent", "w")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("cascade gate", (r.stdout + r.stderr).lower())

    def test_producer_cannot_approve_own_work(self):
        self.seed_reviewed()
        r = self.cli("update", "T-001", "--status", "done", "--agent", "worker-A")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("producer", (r.stdout + r.stderr).lower())
        # a different agent may verdict
        r2 = self.cli("update", "T-001", "--status", "done", "--agent", "verifier-B")
        self.assertEqual(r2.returncode, 0)
        self.assertEqual(self.task("T-001")["status"], "done")

    def test_override_requires_note(self):
        self.seed_reviewed()
        r = self.cli("update", "T-001", "--status", "done", "--agent", "worker-A", "--override-producer-check")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("note", (r.stdout + r.stderr).lower())

    # ---- fixes applied 2026-08-05 ------------------------------------------
    def test_terminal_done_refuses_update_to_open(self):
        self.seed_reviewed()
        self.cli("update", "T-001", "--status", "done", "--agent", "verifier-B")
        r = self.cli("update", "T-001", "--status", "open", "--agent", "attacker")
        self.assertNotEqual(r.returncode, 0, "update must not resurrect a terminal task")
        self.assertEqual(self.task("T-001")["status"], "done")

    def test_terminal_refuses_rehandoff(self):
        self.seed_reviewed()
        self.cli("update", "T-001", "--status", "done", "--agent", "verifier-B")
        r = self.cli("handoff", "T-001", "--to-role", "verifier", "--agent", "x", "--note", "n")
        self.assertNotEqual(r.returncode, 0, "handoff must not move a terminal task back to review")
        self.assertEqual(self.task("T-001")["status"], "done")

    def test_no_double_reputation_credit(self):
        self.seed_reviewed()
        self.cli("update", "T-001", "--status", "done", "--agent", "verifier-B")
        # a second verdict on an already-done task must be refused, not re-credited
        self.cli("update", "T-001", "--status", "done", "--agent", "verifier-C")
        self.assertEqual(self.reputation().get("worker-A", {}).get("tasks_done"), 1)

    def test_orphan_failure_credits_nobody(self):
        # a task with no handoff and no claimant, marked failed, must not credit
        # whoever ran the command.
        self.cli("add-task", "--agent", "p", "--id", "T-001", "--title", "x", "--role", "worker", "--engine", "any")
        self.cli("update", "T-001", "--status", "failed", "--agent", "janitor")
        self.assertNotIn("janitor", self.reputation())

    def test_lease_expiry_returns_review_not_open(self):
        self.seed_reviewed()  # T-001 now in 'review' with handoff from worker-A
        self.cli("claim", "T-001", "--agent", "verifier-D", "--lease", "1")
        self.assertEqual(self.task("T-001")["status"], "claimed")
        time.sleep(2)
        self.cli("status")  # any command triggers expire_claims
        self.assertEqual(self.task("T-001")["status"], "review",
                         "expired lease on a handed-off task must return to review, not open")

    def test_reset_refuses_without_yes_and_wipes_with_it(self):
        self.seed_reviewed()  # one task on the board
        self.cli("add-task", "--agent", "p", "--id", "T-009", "--title", "y",
                 "--role", "worker", "--engine", "any")
        # without --yes: refused, board untouched
        r = self.cli("reset", "--agent", "operator")
        self.assertNotEqual(r.returncode, 0)
        board = json.loads((self.root / ".harness" / "blackboard.json").read_text())
        self.assertTrue(board["tasks"], "reset without --yes must not wipe the board")
        # with --yes: board emptied and the old board archived under trash/
        r2 = self.cli("reset", "--agent", "operator", "--yes")
        self.assertEqual(r2.returncode, 0)
        board2 = json.loads((self.root / ".harness" / "blackboard.json").read_text())
        self.assertEqual(board2["tasks"], {}, "reset --yes must empty the board")
        trash = self.root / ".harness" / "trash"
        archived = list(trash.glob("reset-*/blackboard.json"))
        self.assertTrue(archived, "reset must archive the prior board for reversibility")
        prior = json.loads(archived[0].read_text())
        self.assertIn("T-009", prior["tasks"], "the archived board must hold the pre-reset tasks")

    def test_lease_less_inprogress_gets_a_lease(self):
        # driving a task to in_progress via update (bypassing claim) must still
        # attach a live lease, or expire_claims could never free it.
        self.cli("add-task", "--agent", "p", "--id", "T-001", "--title", "x", "--role", "worker", "--engine", "any")
        self.cli("update", "T-001", "--status", "in_progress", "--agent", "w", "--note", "p")
        self.assertIsNotNone(self.task("T-001").get("claim_expires_at"),
                             "in_progress task must carry a lease")


if __name__ == "__main__":
    unittest.main(verbosity=2)
