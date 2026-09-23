"""Regression coverage for the PR #3 and PR #1 fixes that shipped without a test (T-430).

The GitHub sync of 2026-09-22 merged PR #1 (portalock) and PR #3 (invariant hardening)
into the live history. PR #3's own tests (test_lifecycle_invariants.py, test_safe_delete.py
and two cases in test_data_loss_guard.py) pin most of its fixes. The rest had no test at
all, so a verifier could not show that reverting one of them fails anything. Each class
below names the fix it pins. Every test runs in a throwaway tree built in a
TemporaryDirectory; none touches the live board, state or logs.

The last class pins a semantic conflict the merge found rather than a PR #3 fix: PR #1
routed every lock through portalock so the substrate imports on Windows, and a module
added on the other side of the fork (roster.py) still imported fcntl directly.
"""
import ast
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_BIN = REPO_ROOT / ".harness" / "bin"
GUARD = REPO_BIN / "prevent_data_loss.py"


def scratch_tree(test, state=None):
    """A throwaway harness root: a copy of .harness/bin plus an empty board."""
    tmp = tempfile.mkdtemp(prefix="sync-pr3-")
    test.addCleanup(shutil.rmtree, tmp, True)
    root = Path(tmp)
    shutil.copytree(REPO_BIN, root / ".harness" / "bin",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for sub in ("locks", "logs", "tasks"):
        (root / ".harness" / sub).mkdir(parents=True, exist_ok=True)
    (root / ".harness" / "blackboard.json").write_text(json.dumps({
        "schema_version": "0.1.0", "generation": 0, "tasks": {}, "epics": {},
        "updated_at": "2026-09-22T00:00:00Z", "updated_by": "test-init"}))
    if state is not None:
        (root / ".harness" / "state.json").write_text(json.dumps(state))
    return root


def run_tool(root, tool, *args, timeout=60):
    return subprocess.run([sys.executable, str(root / ".harness" / "bin" / tool), *args],
                          capture_output=True, text=True, cwd=str(root), timeout=timeout)


def run_guard(workspace, command):
    payload = {"session_id": "test-session", "cwd": str(workspace),
               "tool_name": "Bash", "tool_input": {"command": command}}
    return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload),
                          text=True, capture_output=True)


class BlockedTaskReleasesStaleClaim(unittest.TestCase):
    """PR #3, blackboard.py: blocked tasks release stale claims (expire_claims)."""

    def test_expired_claim_on_blocked_task_is_released_and_status_kept(self):
        root = scratch_tree(self, state={"limits": {}, "agents": {"reputation": {}}})
        run_tool(root, "blackboard.py", "add-task", "--agent", "p", "--id", "T-001",
                 "--title", "x", "--role", "worker", "--engine", "any")
        self.assertEqual(run_tool(root, "blackboard.py", "claim", "T-001", "--agent", "w",
                                  "--lease", "1").returncode, 0)
        self.assertEqual(run_tool(root, "blackboard.py", "update", "T-001", "--agent", "w",
                                  "--status", "blocked", "--note", "waiting").returncode, 0)
        time.sleep(2)
        run_tool(root, "blackboard.py", "status")  # any command runs expire_claims
        task = json.loads((root / ".harness" / "blackboard.json").read_text())["tasks"]["T-001"]
        self.assertEqual(task["status"], "blocked", "a blocked task keeps its status")
        self.assertIsNone(task["claimed_by"], "a dead holder must not pin a blocked task")
        self.assertIsNone(task["claim_expires_at"])


class GitCheckoutDotIsBlocked(unittest.TestCase):
    """PR #3, prevent_data_loss.py: `git checkout .` discards every local edit."""

    def setUp(self):
        self.workspace = Path(tempfile.mkdtemp(prefix="sync-guard-"))
        self.addCleanup(shutil.rmtree, self.workspace, True)

    def test_checkout_dot_forms_are_blocked(self):
        for command in ("git checkout .", "git checkout ./", "git checkout ./src/app.py",
                        "cd repo && git checkout .", "sudo git checkout ."):
            with self.subTest(command=command):
                result = run_guard(self.workspace, command)
                self.assertEqual(result.returncode, 2, (command, result.stderr))
                self.assertIn("git checkout .", result.stderr)

    def test_unparseable_text_takes_the_fallback_copy_of_the_rule(self):
        # An unbalanced quote cannot be tokenized, so the flat fallback scan decides.
        result = run_guard(self.workspace, "git checkout . 'unterminated")
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_branch_switches_and_mentions_are_allowed(self):
        for command in ("git checkout main", "git checkout -b feature/x.y",
                        "echo \"git checkout .\"", "git status"):
            with self.subTest(command=command):
                result = run_guard(self.workspace, command)
                self.assertEqual(result.returncode, 0, (command, result.stderr))


class PerlUnlinkIsScopedToCallSyntax(unittest.TestCase):
    """PR #3, prevent_data_loss.py: the Perl rule reads call syntax, not the bare word.

    In this repository the guard already parses commands (T-407), so the bare word as an
    argument was allowed before the merge. What the scoping changes here is SOURCE text:
    a code payload or a comment that merely mentions the word.
    """

    def setUp(self):
        self.workspace = Path(tempfile.mkdtemp(prefix="sync-guard-"))
        self.addCleanup(shutil.rmtree, self.workspace, True)

    def test_prose_in_a_comment_or_payload_is_allowed(self):
        for command in ("ls -la  # never unlink anything here",
                        "python3 -c \"print('see the unlink docs')\""):
            with self.subTest(command=command):
                result = run_guard(self.workspace, command)
                self.assertEqual(result.returncode, 0, (command, result.stderr))

    def test_perl_call_forms_are_still_blocked(self):
        for command in ("perl -e 'unlink $f'", "perl -e 'unlink(\"x\")'",
                        "perl -e 'unlink @files'"):
            with self.subTest(command=command):
                self.assertEqual(run_guard(self.workspace, command).returncode, 2, command)


class LockFileNamesAreInjective(unittest.TestCase):
    """PR #3, harness_common.py: `a/b` and a file named `a__b` no longer share a lock."""

    def test_distinct_paths_get_distinct_lock_names(self):
        root = scratch_tree(self)
        probe = ("import harness_common as hc, json; print(json.dumps(["
                 "hc.lock_name_for('a/b'), hc.lock_name_for('a__b'), "
                 "hc.lock_name_for('pkg/mod.py'), hc.lock_name_for('100%/x')]))")
        out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                             cwd=str(root / ".harness" / "bin"))
        self.assertEqual(out.returncode, 0, out.stderr)
        slash, underscores, readable, percent = json.loads(out.stdout)
        self.assertNotEqual(slash, underscores)
        self.assertEqual(readable, "pkg%2Fmod.py.lock")
        self.assertEqual(percent, "100%25%2Fx.lock")


class LimitsComeFromStateJson(unittest.TestCase):
    """PR #3, harness_common.limit + lock.py: the lock TTL default honors state.json."""

    STATE = {"limits": {"lock_ttl_seconds_default": 123,
                        "claim_lease_seconds_default": "not-a-number"},
             "agents": {"reputation": {}}}

    def test_limit_reads_state_and_falls_back_on_missing_or_malformed(self):
        root = scratch_tree(self, state=self.STATE)
        probe = ("import harness_common as hc, json; print(json.dumps(["
                 "hc.limit('lock_ttl_seconds_default', 900), "
                 "hc.limit('claim_lease_seconds_default', 3600), "
                 "hc.limit('no_such_key', 7)]))")
        out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                             cwd=str(root / ".harness" / "bin"))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout), [123, 3600, 7])

    def test_lock_acquire_default_ttl_is_the_state_json_value(self):
        root = scratch_tree(self, state=self.STATE)
        (root / "work.txt").write_text("x")
        result = run_tool(root, "lock.py", "acquire", "work.txt", "--holder", "w")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads((root / ".harness" / "locks" / "work.txt.lock").read_text())
        self.assertEqual(payload["ttl_seconds"], 123)


class GoalModeTimeoutWithOutputAdvancesTheBound(unittest.TestCase):
    """PR #3, goal_mode.py: a command that prints and then hangs used to crash with a
    TypeError before the iteration counter was bumped, so the anti-runaway bound never
    advanced on exactly the case it exists for."""

    def test_spew_then_hang_counts_one_iteration(self):
        root = scratch_tree(self, state={"limits": {}, "agents": {"reputation": {}}})
        result = run_tool(root, "goal_mode.py", "run", "--cmd", "printf spew; exec sleep 3",
                          "--timeout", "1", "--max-iters", "3", timeout=30)
        self.assertNotIn("Traceback", result.stderr, result.stderr)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        counters = json.loads((root / ".harness" / "logs" / "goal_mode_state.json").read_text())
        self.assertEqual([r["iterations"] for r in counters.values()], [1])


class NotifyNonObjectConfigDoesNotCrash(unittest.TestCase):
    """PR #3, notify.py: valid JSON that is not an object is an unusable config, not a crash."""

    def test_list_config_reports_instead_of_raising(self):
        root = scratch_tree(self)
        (root / ".harness" / "notify_config.json").write_text("[1, 2]")
        result = run_tool(root, "notify.py", "status")
        self.assertNotIn("Traceback", result.stderr, result.stderr)
        self.assertIn("not an object", result.stdout)


class MigrateProjectFixes(unittest.TestCase):
    """PR #3, migrate_project.py: the spec is found under either casing, and the target's
    .gitignore gets the secrets file and the trash archive."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(REPO_BIN))
        try:
            spec = importlib.util.spec_from_file_location(
                "migrate_project_under_test", REPO_BIN / "migrate_project.py")
            cls.mp = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.mp)
        finally:
            sys.path.pop(0)

    def test_gitignore_entries_cover_secrets_and_trash(self):
        self.assertIn(".harness/notify_config.json", self.mp.GITIGNORE_ENTRIES)
        self.assertIn(".harness/trash/", self.mp.GITIGNORE_ENTRIES)

    def test_lowercase_spec_is_found(self):
        tmp = Path(tempfile.mkdtemp(prefix="sync-migrate-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "claude.md").write_text("spec")
        found = self.mp._first_existing(tmp, "CLAUDE.md", "claude.md")
        self.assertTrue(found.exists())
        self.assertEqual(found.name.lower(), "claude.md")


class OnlyPortalockTouchesFcntl(unittest.TestCase):
    """PR #1 x our side: every lock goes through portalock, or the module will not import
    on Windows. roster.py (added on our side of the fork, imported by warrant.py and
    attest.py, and through them by reputation.py) was the one module still importing fcntl
    when the histories were merged."""

    def test_no_control_plane_module_but_portalock_imports_fcntl(self):
        offenders = []
        for path in sorted(REPO_BIN.glob("*.py")):
            if path.name == "portalock.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                if "fcntl" in names:
                    offenders.append(path.name)
        self.assertEqual(offenders, [], "import portalock instead of fcntl")


if __name__ == "__main__":
    unittest.main(verbosity=2)
