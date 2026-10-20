"""test_rehearsal.py -- T-440/T-442: the rehearsal runs, the live tree stays
untouched, and the throwaway sandbox is gone when the run is done.

Runs `examples/rehearsal/run_rehearsal.py` as a subprocess (never imports it, so this
test exercises exactly the CLI a human operator would run) and checks three things
independently of the script's own self-report:

  1. The live `.harness/` tree (excluding `logs/` and `tasks/T-440.json`, for the same
     reason the script itself excludes them -- this task's own bookkeeping legitimately
     touches both, outside the sandbox) is byte-identical, by sha256, before and after
     the run, and `git status --porcelain` for `.harness/` does not change the set of
     non-excluded paths it reports.
  2. No `harness-rehearsal-*` directory under the OS temp dir is left behind by a
     default (no `--keep`) run: T-442 found 15 such sandboxes accumulated by
     2026-10-19 because the script never removed the one it created with
     `tempfile.mkdtemp`. This compares the set of matching names before and after the
     run rather than asserting "zero exist", so the test is not poisoned by sandboxes
     any other process on the machine happens to be holding.
  3. The script's own scorecard, read back via `--json` (which, per T-442, must work
     without `--keep`): every row is `fired`, `blocked` or `unbuilt`; every `fired`
     row carries non-empty, tool-sourced evidence; every `blocked`/`unbuilt` row names
     a blocker.

This does not re-derive whether each blocked finding's root cause is correctly
diagnosed -- that is this task's own analysis, recorded in the scorecard's prose -- it
checks the MECHANICAL invariants: the live tree's integrity, the sandbox's removal,
and that the scorecard's own shape (fired implies evidence; not-fired implies a named
blocker) holds.
"""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "examples" / "rehearsal" / "run_rehearsal.py"
LIVE_HARNESS = REPO_ROOT / ".harness"

EXCLUDE_DIRS = {"logs"}
EXCLUDE_FILES = {"tasks/T-440.json"}


def sandbox_names():
    """Names of harness-rehearsal-* entries currently under the OS temp dir."""
    return set(p.name for p in pathlib.Path(tempfile.gettempdir())
               .glob("harness-rehearsal-*"))


def sha256_tree(root, exclude_dirs=frozenset(), exclude_files=frozenset()):
    out = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if rel.parts and rel.parts[0] in exclude_dirs:
            continue
        if str(rel) in exclude_files:
            continue
        out[str(rel)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def git_status_porcelain():
    p = subprocess.run(["git", "-C", str(REPO_ROOT), "status", "--porcelain",
                        ".harness"], capture_output=True, text=True, timeout=30)
    # Drop lines under the excluded paths so this test is not sensitive to the
    # live task's own, expected, outside-the-sandbox bookkeeping.
    lines = []
    for line in p.stdout.splitlines():
        path = line[3:].strip()
        if any(path.startswith(".harness/" + d + "/") for d in EXCLUDE_DIRS):
            continue
        if path in {".harness/" + f for f in EXCLUDE_FILES}:
            continue
        lines.append(line)
    return sorted(lines)


class RehearsalTests(unittest.TestCase):
    def test_script_exists_and_is_file(self):
        self.assertTrue(SCRIPT.is_file(), "examples/rehearsal/run_rehearsal.py missing")

    def test_live_tree_untouched_sandbox_removed_and_scorecard_shape(self):
        before_hashes = sha256_tree(LIVE_HARNESS, EXCLUDE_DIRS, EXCLUDE_FILES)
        before_status = git_status_porcelain()
        before_sandboxes = sandbox_names()

        # --json: the scorecard must be obtainable without --keep (T-442).
        proc = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                               capture_output=True, text=True, timeout=600)

        after_hashes = sha256_tree(LIVE_HARNESS, EXCLUDE_DIRS, EXCLUDE_FILES)
        after_status = git_status_porcelain()
        after_sandboxes = sandbox_names()

        self.assertEqual(before_hashes, after_hashes,
                          "run_rehearsal.py changed a file under the live .harness/ "
                          "tree (outside logs/ and tasks/T-440.json)")
        self.assertEqual(before_status, after_status,
                          "run_rehearsal.py changed git's view of the live .harness/ "
                          "tree (outside the excluded paths)")

        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

        leaked = after_sandboxes - before_sandboxes
        self.assertFalse(leaked,
                          "a default (no --keep) run left a sandbox directory "
                          "behind under the OS temp dir: {}".format(leaked))

        m = None
        for line in proc.stdout.splitlines():
            if line.startswith("scorecard-json: "):
                m = line[len("scorecard-json: "):]
        self.assertIsNotNone(m, "run_rehearsal.py --json did not print a "
                                 "scorecard-json line:\n" + proc.stdout)
        data = json.loads(m)

        self.assertTrue(data["live_tree_untouched"], data.get("live_tree_diffs"))

        rows = data["rows"]
        self.assertGreaterEqual(len(rows), 10, "expected >=10 attempted mechanisms")
        seen = set()
        for row in rows:
            self.assertIn(row["outcome"], ("fired", "blocked", "unbuilt"))
            seen.add(row["outcome"])
            if row["outcome"] == "fired":
                self.assertTrue(row.get("evidence"),
                                 "fired row with no evidence: {}".format(row["mechanism"]))
            else:
                self.assertTrue(row.get("blocker"),
                                 "{} row with no blocker: {}".format(
                                     row["outcome"], row["mechanism"]))

        # The story must contain at least one of each outcome -- a scorecard that is
        # all green (or all red) would not be the honest, mixed finding T-440 asked for.
        self.assertIn("fired", seen)
        self.assertIn("blocked", seen)
        self.assertIn("unbuilt", seen)

    def test_keep_flag_retains_the_sandbox_for_inspection(self):
        before_sandboxes = sandbox_names()

        proc = subprocess.run([sys.executable, str(SCRIPT), "--keep"],
                               capture_output=True, text=True, timeout=600)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

        sandbox_line = None
        scorecard_line = None
        for line in proc.stdout.splitlines():
            if line.startswith("sandbox: "):
                sandbox_line = line[len("sandbox: "):].strip()
            elif line.startswith("scorecard written: "):
                scorecard_line = line[len("scorecard written: "):].strip()
        self.assertIsNotNone(sandbox_line,
                              "--keep did not print the sandbox location:\n"
                              + proc.stdout)
        self.assertIsNotNone(scorecard_line,
                              "--keep did not print where scorecard.json was "
                              "written:\n" + proc.stdout)

        sandbox_path = pathlib.Path(sandbox_line)
        self.assertTrue(sandbox_path.is_dir(),
                         "--keep claimed to retain {} but it is gone".format(
                             sandbox_line))
        self.assertTrue(pathlib.Path(scorecard_line).is_file(),
                         "--keep claimed to write {} but it is missing".format(
                             scorecard_line))

        after_sandboxes = sandbox_names()
        self.assertIn(sandbox_path.name, after_sandboxes - before_sandboxes,
                      "the --keep run's own sandbox name was not newly present "
                      "under the OS temp dir")

        # This test, not the script, cleans up its own --keep sandbox -- by the
        # exact path the script just printed, never a computed parent or a glob.
        shutil.rmtree(sandbox_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
