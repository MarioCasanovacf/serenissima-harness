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

# The exact phrase run_rehearsal.py appends to every row that depends on the
# sandbox's own throwaway root (decision 9, T-444 acceptance criterion 3).
ROOT_DEPENDENCY_PHRASE = "rehearsal's own throwaway root"


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


class DecisionNineMechanismsFireTests(unittest.TestCase):
    """T-444 (operator ruling, decision 9, .harness/operator-rulings-2026-10-21.md):
    the rehearsal mints its own throwaway root, and that unblocks exactly 4 of the
    8 rows T-440 found BLOCKED by one shared root cause (no key matching any
    warrant) -- the fedatario signature, the delegation ceiling, the fork/contest,
    and `distinguish`'s by_citation disposal -- while the 8 rows that already
    fired under the old, carried-over trust keep firing.

    This pins the SHAPE (outcome, and that root-dependent rows say so) rather than
    re-deriving each row's own tool-level correctness, which lives in the
    scorecard's own evidence string and in the tool's own test suite
    (test_warrant.py, test_precedent_*.py, etc).
    """

    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                               capture_output=True, text=True, timeout=600)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        line = next((l for l in proc.stdout.splitlines()
                     if l.startswith("scorecard-json: ")), None)
        assert line is not None, proc.stdout
        cls.scorecard = json.loads(line[len("scorecard-json: "):])

    def _row(self, substring):
        matches = [r for r in self.scorecard["rows"] if substring in r["mechanism"]]
        self.assertEqual(len(matches), 1,
                          "expected exactly one row matching {!r}, found {}".format(
                              substring, len(matches)))
        return matches[0]

    def test_live_tree_stays_untouched(self):
        self.assertTrue(self.scorecard["live_tree_untouched"],
                         self.scorecard.get("live_tree_diffs"))

    def test_the_sandbox_has_its_own_fingerprint(self):
        fp = self.scorecard.get("sandbox_root_fingerprint") or ""
        self.assertTrue(fp.startswith("SHA256:"), fp)

    def test_the_by_citation_disposal_now_fires(self):
        # T-445 round 2: `by_citation_raw` counts signed `distinguish` ACTS off the
        # attest chain, not the case record's own disposal field -- a regression
        # inside `dispose_case()` could leave the act/counter path untouched while
        # the case itself stayed open. Assert BOTH: the counter moved (the act was
        # signed) AND the case record itself (read back independently via `case
        # show --json`, which this row's own evidence now carries) says disposed
        # by the `distinguish` verb -- not just that some act existed.
        row = self._row("a case disposed by `distinguish`")
        self.assertEqual(row["outcome"], "fired", row)
        self.assertIn("by_citation_raw=1", row["evidence"])
        self.assertIn("case_status=disposed", row["evidence"])
        self.assertIn("disposal_verb=distinguish", row["evidence"])
        self.assertIn(ROOT_DEPENDENCY_PHRASE, row["mechanism"])

    def test_the_fedatario_signature_now_verifies(self):
        row = self._row("signed by a fedatario seat holder")
        self.assertEqual(row["outcome"], "fired", row)
        self.assertIn("signature_failures=[]", row["evidence"])
        self.assertIn(ROOT_DEPENDENCY_PHRASE, row["mechanism"])

    def test_the_delegation_ceiling_now_fires(self):
        row = self._row("delegation with a ceiling")
        self.assertEqual(row["outcome"], "fired", row)
        self.assertIn("DELEGATION CEILING", row["evidence"])
        self.assertIn(ROOT_DEPENDENCY_PHRASE, row["mechanism"])

    def test_the_fork_is_detected_and_contested(self):
        row = self._row("fork under one name")
        self.assertEqual(row["outcome"], "fired", row)
        self.assertIn("CONTESTED", row["evidence"])
        self.assertIn("SIMULATED FORGER", row["mechanism"])
        self.assertIn(ROOT_DEPENDENCY_PHRASE, row["mechanism"])

    def test_phase_b_yield_still_fires_and_now_says_it_depends_on_the_root(self):
        row = self._row("phase B yield")
        self.assertEqual(row["outcome"], "fired", row)
        self.assertIn(ROOT_DEPENDENCY_PHRASE, row["mechanism"])

    def test_the_eight_previously_firing_rows_are_still_fired(self):
        previously_fired_substrings = [
            "producer-not-approver refusal",
            "handoff and a distinct verifier's verdict",
            "a case opened and deliberated",
            "a precedent published disposing the case",
            "a confirmation by a distinct author",
            "a case disposed by publish --follows",
            "phase B yield",
            "currency.py and event_stats.py",
        ]
        for substr in previously_fired_substrings:
            row = self._row(substr)
            self.assertEqual(row["outcome"], "fired", substr)

    def test_westphalia_stays_blocked_and_contracts_stays_unbuilt(self):
        west = self._row("westphalia_kpi.py attempted")
        self.assertEqual(west["outcome"], "blocked")
        self.assertIn("PR-029 clause 6", west["blocker"])
        contracts = self._row("contracts and breach")
        self.assertEqual(contracts["outcome"], "unbuilt")

    def test_total_outcome_counts(self):
        """4 newly-fired + 8 previously-fired = 12; westphalia blocked; contracts
        unbuilt. Of 14 total rows."""
        outcomes = [r["outcome"] for r in self.scorecard["rows"]]
        self.assertEqual(len(outcomes), 14)
        self.assertEqual(outcomes.count("fired"), 12)
        self.assertEqual(outcomes.count("blocked"), 1)
        self.assertEqual(outcomes.count("unbuilt"), 1)


def make_scratch_repo(tmp_base):
    """A scratch copy of just enough of the live repo for warrant.py to run --
    `bin/` (code) and `trust/` (the live, PUBLIC, operator-enrolled anchor, if
    any) -- NEVER the working tree. Mirrors `run_rehearsal.py`'s own
    `build_sandbox`, narrowed to what this one check needs."""
    scratch_harness = pathlib.Path(tmp_base) / ".harness"
    shutil.copytree(LIVE_HARNESS / "bin", scratch_harness / "bin",
                     ignore=shutil.ignore_patterns("__pycache__"))
    live_trust = LIVE_HARNESS / "trust"
    if live_trust.exists():
        shutil.copytree(live_trust, scratch_harness / "trust")
    (scratch_harness / "warrants").mkdir(parents=True, exist_ok=True)
    (scratch_harness / "roster.json").write_text(
        json.dumps({"schema_version": 1, "colegiados": {}, "plazas": {}, "names": {}}),
        encoding="utf-8")
    return scratch_harness


class RehearsalRootIsNotTheLiveRootTests(unittest.TestCase):
    """T-444 acceptance criterion 4: a rehearsal warrant, signed under the
    sandbox's own throwaway root, must fail verification anywhere else -- proven
    here by copying one into a SCRATCH copy of the repository (never the working
    tree) and running THAT copy's own warrant.py against it."""

    def test_a_rehearsal_warrant_fails_verification_outside_its_own_sandbox(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--keep"],
                               capture_output=True, text=True, timeout=600)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        sandbox_line = next((l for l in proc.stdout.splitlines()
                              if l.startswith("sandbox: ")), None)
        self.assertIsNotNone(sandbox_line, proc.stdout)
        sandbox_path = pathlib.Path(sandbox_line[len("sandbox: "):].strip())
        self.addCleanup(shutil.rmtree, sandbox_path, ignore_errors=True)

        wfiles = sorted((sandbox_path / ".harness" / "warrants").glob("W-*.json"))
        self.assertTrue(wfiles, "the rehearsal left no signed warrant behind")
        rehearsal_warrant = wfiles[0]
        rehearsal_sig = pathlib.Path(str(rehearsal_warrant) + ".sig")
        self.assertTrue(rehearsal_sig.exists(),
                         "the rehearsal's own warrant carries no signature")

        with tempfile.TemporaryDirectory() as scratch_base:
            scratch_harness = make_scratch_repo(scratch_base)
            # A filename picked to never collide with a live warrant id (W-001,
            # W-002 as of this writing): the bytes are the rehearsal's, unchanged
            # (a signature covers bytes; renaming the file does not touch them).
            target = scratch_harness / "warrants" / "W-900.json"
            target.write_bytes(rehearsal_warrant.read_bytes())
            pathlib.Path(str(target) + ".sig").write_bytes(rehearsal_sig.read_bytes())

            verify = subprocess.run(
                [sys.executable, str(scratch_harness / "bin" / "warrant.py"),
                 "verify", "--warrant", "W-900"],
                capture_output=True, text=True, timeout=30)

            self.assertNotEqual(
                verify.returncode, 0,
                "a warrant signed under the REHEARSAL's root verified under a "
                "DIFFERENT root; decision 9's isolation requirement does not hold")
            msg = (verify.stderr + verify.stdout).lower()
            if (LIVE_HARNESS / "trust" / "root.pub").exists():
                # The live repo is enrolled: the scratch copy inherited the
                # OPERATOR's real anchor, which the rehearsal's signature cannot
                # match.
                self.assertIn("signature does not verify", msg)
            else:
                # The live repo is un-enrolled: there is no anchor at all to
                # verify against, which is refused for a different, equally
                # correct reason.
                self.assertIn("no trust anchor", msg)


if __name__ == "__main__":
    unittest.main()
