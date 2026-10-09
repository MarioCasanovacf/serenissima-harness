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
        # the class shares one root; clear reset archives so each test's trash/ is its own
        if (h / "trash").exists():
            shutil.rmtree(h / "trash")
        # T-434: same isolation for any precedent records a reset-citation test wrote
        if (h / "precedents").exists():
            shutil.rmtree(h / "precedents")

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

    def test_reset_backups_do_not_collide(self):
        # two resets in the same wall-clock second must each keep their archive
        # (the backup dir carries a uuid suffix, not just a second-granular stamp).
        self.cli("add-task", "--agent", "p", "--id", "T-001", "--title", "a",
                 "--role", "worker", "--engine", "any")
        self.cli("reset", "--agent", "op", "--yes")
        self.cli("add-task", "--agent", "p", "--id", "T-002", "--title", "b",
                 "--role", "worker", "--engine", "any")
        self.cli("reset", "--agent", "op", "--yes")
        backups = list((self.root / ".harness" / "trash").glob("reset-*"))
        self.assertEqual(len(backups), 2, "each reset must preserve its own archive")

    # ---- T-434: reset refuses while a precedent cites a task on the live board ----

    def _write_precedent(self, pr_id, cites):
        pdir = self.root / ".harness" / "precedents"
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "{}.json".format(pr_id)).write_text(json.dumps({
            "id": pr_id, "status": "active", "cites": cites,
        }))

    def _events(self):
        path = self.root / ".harness" / "logs" / "events.jsonl"
        if not path.exists():
            return []
        return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]

    def test_reset_refuses_when_a_precedent_cites_a_live_task(self):
        self.cli("add-task", "--agent", "p", "--id", "T-001", "--title", "a",
                 "--role", "worker", "--engine", "any")
        self._write_precedent("PR-900", ["T-001"])

        r = self.cli("reset", "--agent", "operator", "--yes")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PR-900", r.stdout + r.stderr)
        self.assertIn("T-001", self.task_ids())

        events = [e for e in self._events() if e.get("event") == "board_reset_refused_citations"]
        self.assertEqual(len(events), 1, "refusal must log exactly one named event")
        self.assertIn("PR-900 cites T-001", events[0]["citations"])
        # the board itself (and the precedent) must be completely untouched
        self.assertTrue((self.root / ".harness" / "precedents" / "PR-900.json").exists())
        self.assertEqual(list((self.root / ".harness" / "trash").glob("reset-*")), [])

    def test_reset_override_with_reason_proceeds_and_logs_it(self):
        self.cli("add-task", "--agent", "p", "--id", "T-001", "--title", "a",
                 "--role", "worker", "--engine", "any")
        self._write_precedent("PR-900", ["T-001"])

        # the override flag alone, with no --note, is still refused -- no
        # reason means no override.
        r0 = self.cli("reset", "--agent", "operator", "--yes", "--override-precedent-citations")
        self.assertNotEqual(r0.returncode, 0, r0.stdout + r0.stderr)
        self.assertIn("T-001", self.task_ids())

        r = self.cli("reset", "--agent", "operator", "--yes",
                      "--override-precedent-citations", "--note", "PR-900 is being retired too")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.task_ids(), [])

        overrides = [e for e in self._events() if e.get("event") == "board_reset_citations_overridden"]
        self.assertEqual(len(overrides), 1)
        self.assertEqual(overrides[0]["reason"], "PR-900 is being retired too")
        self.assertIn("PR-900 cites T-001", overrides[0]["citations"])
        # the wipe itself still happened and archived the task, same as always
        self.assertEqual(len([e for e in self._events() if e.get("event") == "board_reset"]), 1)
        archived = list((self.root / ".harness" / "trash").glob("reset-*/tasks/T-001.json"))
        self.assertTrue(archived, "override must still archive the task for reversibility")

    def test_reset_proceeds_when_nobody_cites_the_board(self):
        self.cli("add-task", "--agent", "p", "--id", "T-001", "--title", "a",
                 "--role", "worker", "--engine", "any")
        # a precedent exists, but names no task currently on the board (its
        # citation is already dangling for an unrelated reason) -- this must
        # NOT be mistaken for a live-board citation.
        self._write_precedent("PR-901", ["T-999"])

        r = self.cli("reset", "--agent", "operator", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.task_ids(), [])
        self.assertEqual(
            [e for e in self._events() if e.get("event") == "board_reset_refused_citations"], [])

    def test_reset_proceeds_with_no_precedent_registry_at_all(self):
        self.cli("add-task", "--agent", "p", "--id", "T-001", "--title", "a",
                 "--role", "worker", "--engine", "any")
        r = self.cli("reset", "--agent", "operator", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.task_ids(), [])

    # ---- T-438: the fail-CLOSED branch -- `cite --all` itself cannot be
    # trusted (exits 4, REGISTRY INTEGRITY ERROR), not merely "found a hit" ----

    def _write_unparseable_precedent(self, pr_id="PR-900"):
        """Writes a PR-*.json that `precedent.py` cannot even parse as JSON,
        forcing `cite --all` to exit 4 (scan_registry -> RegistryIntegrityError
        -> integrity_error(), precedent.py:~777), distinct from the
        'found a live citation' (exit 0/3) path the tests above cover."""
        pdir = self.root / ".harness" / "precedents"
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "{}.json".format(pr_id)).write_text("{ this is not valid json")

    def test_reset_refuses_when_the_citation_scan_cannot_be_trusted(self):
        self.cli("add-task", "--agent", "p", "--id", "T-001", "--title", "a",
                 "--role", "worker", "--engine", "any")
        self._write_unparseable_precedent()

        r = self.cli("reset", "--agent", "operator", "--yes")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("T-001", self.task_ids(), "board must be untouched on refusal")

        events = [e for e in self._events() if e.get("event") == "board_reset_refused_citations"]
        self.assertEqual(len(events), 1, "refusal must log exactly one named event")
        self.assertEqual(events[0].get("citations"), [], "no hits -- the scan itself was the problem")
        self.assertIsNotNone(events[0].get("problem"), "an untrustworthy scan must log a non-null problem")
        self.assertIn("exited 4", events[0]["problem"])
        # trash/ must stay empty -- the refusal must happen before any archive write
        self.assertEqual(list((self.root / ".harness" / "trash").glob("reset-*")), [])

    def test_reset_override_with_note_proceeds_over_an_untrustworthy_scan(self):
        self.cli("add-task", "--agent", "p", "--id", "T-001", "--title", "a",
                 "--role", "worker", "--engine", "any")
        self._write_unparseable_precedent()

        # override flag alone, no --note: still refused
        r0 = self.cli("reset", "--agent", "operator", "--yes", "--override-precedent-citations")
        self.assertNotEqual(r0.returncode, 0, r0.stdout + r0.stderr)
        self.assertIn("T-001", self.task_ids())

        r = self.cli("reset", "--agent", "operator", "--yes",
                      "--override-precedent-citations", "--note",
                      "registry integrity error predates this reset, safe to proceed")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.task_ids(), [])

        overrides = [e for e in self._events() if e.get("event") == "board_reset_citations_overridden"]
        self.assertEqual(len(overrides), 1)
        self.assertIn("exited 4", overrides[0]["problem"])
        self.assertEqual(overrides[0]["reason"],
                         "registry integrity error predates this reset, safe to proceed")
        archived = list((self.root / ".harness" / "trash").glob("reset-*/tasks/T-001.json"))
        self.assertTrue(archived, "override must still archive the task for reversibility")

    def task_ids(self):
        board = json.loads((self.root / ".harness" / "blackboard.json").read_text())
        return list(board["tasks"].keys())

    def test_lease_less_inprogress_gets_a_lease(self):
        # driving a task to in_progress via update (bypassing claim) must still
        # attach a live lease, or expire_claims could never free it.
        self.cli("add-task", "--agent", "p", "--id", "T-001", "--title", "x", "--role", "worker", "--engine", "any")
        self.cli("update", "T-001", "--status", "in_progress", "--agent", "w", "--note", "p")
        self.assertIsNotNone(self.task("T-001").get("claim_expires_at"),
                             "in_progress task must carry a lease")


# ==========================================================================
# T-438: fail-closed on `cite --all` LINE-FORMAT drift.
#
# `_precedent_task_citations` shells out to the real `precedent.py cite
# --all`; this exercises its internal parse loop directly, in-process,
# against a STUB in place of the real `precedent.py`, rather than through
# `reset`/subprocess like the tests above. The seam is the module's own
# `_PRECEDENT_PY` constant (already a module-level global the function reads
# at call time, not a constructor argument) -- patched for the duration of
# one test and restored in `finally`, so the DEFAULT path (every other test
# in this file, and the live board) is untouched. Loaded via
# importlib.util.spec_from_file_location against the real repo's
# blackboard.py, mirroring test_precedent_bridge.py's
# `_import_precedent_module` pattern for the same reason: the function under
# test is read-only (no writes, no board/state access) so importing the
# live file in-process is safe, and avoids re-copying the whole bin/ tree
# just to flip one constant.
# ==========================================================================

import importlib.util

BB_PY = REPO_BIN / "blackboard.py"


def _import_blackboard_module():
    spec = importlib.util.spec_from_file_location("blackboard_under_test_t438", str(BB_PY))
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(BB_PY.parent))  # so blackboard's own `import harness_common` resolves
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(BB_PY.parent))
    return mod


class FormatDriftFailsClosedTests(unittest.TestCase):
    def setUp(self):
        self.bb = _import_blackboard_module()
        self._orig_precedent_py = self.bb._PRECEDENT_PY

    def tearDown(self):
        self.bb._PRECEDENT_PY = self._orig_precedent_py

    def _point_at_stub(self, stub_stdout):
        """Writes a throwaway stub standing in for precedent.py: whatever
        argv `_precedent_task_citations` passes it (cite --all --root ...),
        it ignores and just prints `stub_stdout`, exit 0 -- enough to drive
        the parse loop without a real precedent.py cite --all run."""
        tmp = tempfile.mkdtemp(prefix="t438-stub-")
        stub = Path(tmp) / "precedent.py"
        stub.write_text(
            "import sys\n"
            "sys.stdout.write({!r})\n"
            "sys.exit(0)\n".format(stub_stdout))
        self.bb._PRECEDENT_PY = stub
        return stub

    def test_unrecognized_nonempty_line_is_a_problem_not_silently_skipped(self):
        drifted_line = "this line has no colon-shaped citation structure at all"
        self._point_at_stub(drifted_line + "\n")
        hits, problem = self.bb._precedent_task_citations()
        self.assertEqual(hits, [], "a drifted line must not be mistaken for zero citations")
        self.assertIsNotNone(problem, "an unrecognized nonempty line must fail CLOSED, not open")
        self.assertIn(drifted_line, problem, "the offending line must be named in the message")

    def test_well_formed_lines_are_unaffected_by_the_drift_check(self):
        # same stub seam, but printing output that DOES match the real
        # format -- confirms the new check is additive, not a regression on
        # the happy path the live board already exercises.
        self._point_at_stub("PR-900 cites T-999: OK (dangling but parseable)\n")
        hits, problem = self.bb._precedent_task_citations()
        self.assertEqual(hits, [], "T-999 has no task file, so it is not a live-board hit")
        self.assertIsNone(problem)

    def test_blank_lines_in_otherwise_well_formed_output_are_not_a_problem(self):
        self._point_at_stub("\nPR-900 cites T-999: OK (dangling but parseable)\n\n")
        hits, problem = self.bb._precedent_task_citations()
        self.assertEqual(hits, [])
        self.assertIsNone(problem)


if __name__ == "__main__":
    unittest.main(verbosity=2)
