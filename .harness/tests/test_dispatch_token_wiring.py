"""T-454: `blackboard.py claim` and `lock.py acquire` wire dispatch_token.py in as an
optional, additive check. This suite pins the acceptance criteria end to end, driving
the real CLIs by subprocess over a throwaway tree the same way
test_sync_pr3_coverage.py and test_blackboard_redact.py already do -- nothing here
touches the live board, locks, trust store or dispatch_tokens/ directory.

The two cases the criteria name, pinned concretely:
  1. An epic with NO operator-signed requirement: claim/acquire behave exactly as
     before, with or without a --token-file.
  2. An epic WITH a signed requirement (`"required": true` inside that epic's own
     signed token set -- T-454's design choice, no second signed record): claim/acquire
     refuse without a verifying token, and a mismatch between a presented token and the
     acting agent/task/role is refused even though a token WAS presented.

Nonce decisions pinned here too: `claim` consumes a token's nonce (single claim per
(agent, task, role)); `lock.py acquire` does not, so refreshing a held lock under the
same still-valid token keeps working.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_BIN = REPO_ROOT / ".harness" / "bin"


def scratch_tree(test, tasks):
    tmp = tempfile.mkdtemp(prefix="t454-wiring-")
    test.addCleanup(shutil.rmtree, tmp, True)
    root = Path(tmp)
    shutil.copytree(REPO_BIN, root / ".harness" / "bin",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for sub in ("locks", "logs", "tasks"):
        (root / ".harness" / sub).mkdir(parents=True, exist_ok=True)
    bb = {
        "schema_version": "0.1.0", "generation": 0, "tasks": tasks, "epics": {},
        "updated_at": "2026-10-21T00:00:00Z", "updated_by": "test-init",
    }
    (root / ".harness" / "blackboard.json").write_text(json.dumps(bb))
    for tid in tasks:
        (root / ".harness" / "tasks" / "{}.json".format(tid)).write_text(
            json.dumps({"id": tid}))
    return root


def task(epic, role="worker", status="open"):
    return {"epic": epic, "title": "t", "status": status, "role": role, "engine": "any",
            "depends_on": [], "claimed_by": None, "claim_expires_at": None,
            "priority": 1, "detail_file": "x", "artifacts": [], "handoff": None,
            "created_at": "2026-10-21T00:00:00Z", "created_by": "test"}


def run(root, tool, *args, timeout=60):
    return subprocess.run([sys.executable, str(root / ".harness" / "bin" / tool), *args],
                          capture_output=True, text=True, cwd=str(root), timeout=timeout)


def keygen(path):
    subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "root@operator",
                    "-f", str(path), "-q"], check=True, capture_output=True)
    return Path(str(path) + ".pub")


def sign(payload_path, key_path, namespace="harness-dispatch-token"):
    r = subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key_path), "-n", namespace,
                        str(payload_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return Path(str(payload_path) + ".sig")


def enroll(root):
    keys = root / "keys"
    keys.mkdir(exist_ok=True)
    root_key = keys / "root"
    root_pub = keygen(root_key)
    r = run(root, "warrant.py", "init", "--root-pub", str(root_pub))
    assert r.returncode == 0, r.stderr
    return root_key


def mint_required_set(root, root_key, epic, dispatch):
    r = run(root, "dispatch_token.py", "draft", "--epic", epic,
           "--dispatch", dispatch, "--required")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    path = Path(out["path"])
    sign(path, root_key)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {"token_set_id": payload["token_set_id"], **payload["tokens"][0]}


class NoRequirementIsUnchanged(unittest.TestCase):
    """Case 1 of the acceptance criteria: no signed requirement, nothing changes."""

    def test_claim_succeeds_with_no_token_and_no_requirement(self):
        root = scratch_tree(self, {"T-1": task("e-free")})
        r = run(root, "blackboard.py", "claim", "T-1", "--agent", "worker-a")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_lock_acquire_succeeds_with_no_token_and_no_requirement(self):
        root = scratch_tree(self, {"T-1": task("e-free")})
        r = run(root, "lock.py", "acquire", "some/file.py", "--holder", "worker-a",
               "--task", "T-1")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_lock_acquire_with_no_task_at_all_is_unaffected(self):
        root = scratch_tree(self, {})
        r = run(root, "lock.py", "acquire", "untracked/file.py", "--holder", "worker-a")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_an_unsigned_required_draft_still_does_not_require_a_token(self):
        root = scratch_tree(self, {"T-1": task("e-1")})
        root_key = enroll(root)
        r = run(root, "dispatch_token.py", "draft", "--epic", "e-1",
               "--dispatch", "worker-a:T-1:worker", "--required")
        self.assertEqual(r.returncode, 0)
        # never signed -- claim must still succeed with no token
        r = run(root, "blackboard.py", "claim", "T-1", "--agent", "worker-a")
        self.assertEqual(r.returncode, 0, r.stderr)


class RequirementIsEnforced(unittest.TestCase):
    """Case 2: a signed `required: true` set for the epic."""

    def test_claim_refuses_without_a_token_once_required(self):
        root = scratch_tree(self, {"T-1": task("e-req")})
        root_key = enroll(root)
        mint_required_set(root, root_key, "e-req", "worker-b:T-1:worker")
        r = run(root, "blackboard.py", "claim", "T-1", "--agent", "worker-b")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("dispatch token required", r.stdout + r.stderr)

    def test_claim_succeeds_with_the_correct_token(self):
        root = scratch_tree(self, {"T-1": task("e-req")})
        root_key = enroll(root)
        tok = mint_required_set(root, root_key, "e-req", "worker-b:T-1:worker")
        tf = root / "tok.json"
        tf.write_text(json.dumps(tok))
        r = run(root, "blackboard.py", "claim", "T-1", "--agent", "worker-b",
               "--token-file", str(tf))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_claim_refuses_a_token_presented_by_the_wrong_agent(self):
        root = scratch_tree(self, {"T-1": task("e-req")})
        root_key = enroll(root)
        tok = mint_required_set(root, root_key, "e-req", "worker-b:T-1:worker")
        tf = root / "tok.json"
        tf.write_text(json.dumps(tok))
        r = run(root, "blackboard.py", "claim", "T-1", "--agent", "worker-mallory",
               "--token-file", str(tf))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("IDENTITY MISMATCH", r.stdout + r.stderr)

    def test_claim_nonce_is_single_use(self):
        root = scratch_tree(self, {"T-1": task("e-req", status="review")})
        root_key = enroll(root)
        tok = mint_required_set(root, root_key, "e-req", "worker-b:T-1:worker")
        tf = root / "tok.json"
        tf.write_text(json.dumps(tok))
        r1 = run(root, "blackboard.py", "claim", "T-1", "--agent", "worker-b",
                "--token-file", str(tf))
        self.assertEqual(r1.returncode, 0, r1.stderr)
        # put it back to a claimable state and try to reuse the SAME presented token
        r2 = run(root, "blackboard.py", "update", "T-1", "--agent", "worker-b",
                "--status", "review", "--note", "t454 nonce-reuse fixture")
        self.assertEqual(r2.returncode, 0, r2.stderr)
        r3 = run(root, "blackboard.py", "claim", "T-1", "--agent", "worker-b",
                "--token-file", str(tf))
        self.assertNotEqual(r3.returncode, 0)
        self.assertIn("already used", r3.stdout + r3.stderr)

    def test_lock_acquire_refuses_without_a_token_once_required(self):
        root = scratch_tree(self, {"T-1": task("e-req")})
        root_key = enroll(root)
        mint_required_set(root, root_key, "e-req", "worker-b:T-1:worker")
        r = run(root, "lock.py", "acquire", "some/file.py", "--holder", "worker-b",
               "--task", "T-1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("dispatch token required", r.stdout + r.stderr)

    def test_lock_acquire_succeeds_and_refreshes_with_the_same_token(self):
        """lock.py acquire does NOT consume nonces: presenting the same valid token a
        second time (the ordinary heartbeat refresh of a lock you already hold) must
        keep succeeding, unlike claim's single-use nonce above."""
        root = scratch_tree(self, {"T-1": task("e-req")})
        root_key = enroll(root)
        tok = mint_required_set(root, root_key, "e-req", "worker-b:T-1:worker")
        tf = root / "tok.json"
        tf.write_text(json.dumps(tok))
        r1 = run(root, "lock.py", "acquire", "some/file.py", "--holder", "worker-b",
                "--task", "T-1", "--token-file", str(tf))
        self.assertEqual(r1.returncode, 0, r1.stderr)
        r2 = run(root, "lock.py", "acquire", "some/file.py", "--holder", "worker-b",
                "--task", "T-1", "--token-file", str(tf))
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn("refreshed", r2.stdout)

    def test_lock_acquire_refuses_a_mismatched_token(self):
        root = scratch_tree(self, {"T-1": task("e-req")})
        root_key = enroll(root)
        tok = mint_required_set(root, root_key, "e-req", "worker-b:T-1:worker")
        tf = root / "tok.json"
        tf.write_text(json.dumps(tok))
        r = run(root, "lock.py", "acquire", "some/file.py", "--holder", "worker-mallory",
               "--task", "T-1", "--token-file", str(tf))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("IDENTITY MISMATCH", r.stdout + r.stderr)

    def test_a_different_epic_is_unaffected_by_this_one_being_required(self):
        root = scratch_tree(self, {"T-1": task("e-req"), "T-2": task("e-free")})
        root_key = enroll(root)
        mint_required_set(root, root_key, "e-req", "worker-b:T-1:worker")
        r = run(root, "blackboard.py", "claim", "T-2", "--agent", "worker-c")
        self.assertEqual(r.returncode, 0, r.stderr)


class LiveTreeIsolation(unittest.TestCase):
    def test_nothing_in_this_suite_touches_the_live_dispatch_tokens_dir_or_trust_store(self):
        live_dt = REPO_ROOT / ".harness" / "dispatch_tokens"
        live_trust = REPO_ROOT / ".harness" / "trust"
        before_dt = live_dt.exists()
        before_trust = (set(p.name for p in live_trust.iterdir())
                        if live_trust.exists() else None)
        root = scratch_tree(self, {"T-1": task("e-req")})
        root_key = enroll(root)
        mint_required_set(root, root_key, "e-req", "worker-b:T-1:worker")
        self.assertEqual(live_dt.exists(), before_dt)
        after_trust = (set(p.name for p in live_trust.iterdir())
                      if live_trust.exists() else None)
        self.assertEqual(after_trust, before_trust)


if __name__ == "__main__":
    unittest.main(verbosity=2)
