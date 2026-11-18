"""test_rehearsal.py -- T-440/T-442: the rehearsal runs, the live tree stays
untouched, and the throwaway sandbox is gone when the run is done.

Runs `examples/rehearsal/run_rehearsal.py` as a subprocess (never imports it, so this
test exercises exactly the CLI a human operator would run) and checks three things
independently of the script's own self-report:

  1. The protected live material (`PROTECTED_LIVE_PATHS` below: trust, keys,
     constitutional, warrants, roster, acts, revocations, dispatch tokens) is
     byte-identical, by sha256, before and after the run, and `git status --porcelain`
     for those paths does not change. The rest of the live tree is NOT compared
     here: another process's legitimate edit there must not fail this test (T-478).
     That the rehearsal itself writes nothing to the live tree, protected or not, is
     pinned by the script's own scorecard (`live_tree_untouched`, backed by its write
     guard) on the real run, and by `LiveTreeCheckTests` below, which plants each kind
     of write in a throwaway copy and shows the check catching it, and shows a
     concurrent edit not tripping it (decision 9: "a test pins that the live tree
     does not change").
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
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "examples" / "rehearsal" / "run_rehearsal.py"
LIVE_HARNESS = REPO_ROOT / ".harness"

# Kept independent of the script's own constant on purpose; a test below asserts the
# two agree, so neither can drift without this file noticing.
PROTECTED_LIVE_PATHS = ("trust", "keys", "constitutional", "warrants", "roster.json",
                        "acts", "revocations", "dispatch_tokens")

# The exact phrase run_rehearsal.py appends to every row that depends on the
# sandbox's own throwaway root (decision 9, T-444 acceptance criterion 3).
ROOT_DEPENDENCY_PHRASE = "rehearsal's own throwaway root"


def sandbox_names(tag=None):
    """Names of this run's sandbox entries under the OS temp dir.

    T-482: with a `tag` (the per-run unique value passed to the script as
    REHEARSAL_RUN_TAG) only `harness-rehearsal-<tag>-*` matches, so a sandbox a
    concurrent foreign run has open at the same moment is never counted. With no
    tag it is the historical every-rehearsal-looking-directory glob, kept only so
    the test of the check itself can show the difference."""
    pattern = "harness-rehearsal-{}-*".format(tag) if tag else "harness-rehearsal-*"
    return set(p.name for p in pathlib.Path(tempfile.gettempdir()).glob(pattern))


def new_run_tag():
    """A tag unique to one test's subprocess run (letters and digits only)."""
    return "t{}x{}".format(os.getpid(), time.monotonic_ns())


def tagged_env(tag):
    env = dict(os.environ)
    env["REHEARSAL_RUN_TAG"] = tag
    return env


def sha256_protected(root):
    out = {}
    for name in PROTECTED_LIVE_PATHS:
        top = root / name
        if not (top.exists() or top.is_symlink()):
            continue
        for p in [top] + (sorted(top.rglob("*")) if top.is_dir() else []):
            rel = str(p.relative_to(root))
            if p.is_dir():
                out[rel + "/"] = "dir"
            elif p.is_file():
                out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def git_status_porcelain():
    p = subprocess.run(["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--"]
                       + [".harness/" + n for n in PROTECTED_LIVE_PATHS],
                       capture_output=True, text=True, timeout=30)
    return sorted(p.stdout.splitlines())


class RehearsalTests(unittest.TestCase):
    def test_script_exists_and_is_file(self):
        self.assertTrue(SCRIPT.is_file(), "examples/rehearsal/run_rehearsal.py missing")

    def test_live_tree_untouched_sandbox_removed_and_scorecard_shape(self):
        before_hashes = sha256_protected(LIVE_HARNESS)
        before_status = git_status_porcelain()
        tag = new_run_tag()
        before_sandboxes = sandbox_names(tag)

        # --json: the scorecard must be obtainable without --keep (T-442).
        proc = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                               capture_output=True, text=True, timeout=600,
                               env=tagged_env(tag))

        after_hashes = sha256_protected(LIVE_HARNESS)
        after_status = git_status_porcelain()
        after_sandboxes = sandbox_names(tag)

        self.assertEqual(before_hashes, after_hashes,
                          "run_rehearsal.py changed protected material under the "
                          "live .harness/ tree")
        self.assertEqual(before_status, after_status,
                          "run_rehearsal.py changed git's view of the protected "
                          "paths of the live .harness/ tree")

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
        self.assertEqual(set(data["live_tree_protected_paths"]),
                         set(PROTECTED_LIVE_PATHS))

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

    def test_leak_check_counts_only_this_runs_sandboxes(self):
        """T-482: a sandbox a concurrent FOREIGN run creates during the check must
        not fail it; a sandbox THIS run leaks must. Both are simulated with bare
        directories so no second rehearsal has to run."""
        tag = new_run_tag()
        tmp = pathlib.Path(tempfile.gettempdir())
        before = sandbox_names(tag)
        foreign = pathlib.Path(tempfile.mkdtemp(prefix="harness-rehearsal-"))
        self.addCleanup(shutil.rmtree, foreign, ignore_errors=True)
        other = pathlib.Path(tempfile.mkdtemp(
            prefix="harness-rehearsal-{}zz-".format(tag)))
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        # Foreign sandboxes (untagged, or another run's tag) are invisible.
        self.assertEqual(sandbox_names(tag) - before, set(),
                         "a foreign run's sandbox was counted as this run's")
        # The old glob would have counted the foreign one: the check is what changed.
        self.assertIn(foreign.name, sandbox_names())
        # A sandbox this run leaks (its own tag) is still caught.
        leaked = pathlib.Path(tempfile.mkdtemp(
            prefix="harness-rehearsal-{}-".format(tag), dir=str(tmp)))
        self.addCleanup(shutil.rmtree, leaked, ignore_errors=True)
        self.assertEqual(sandbox_names(tag) - before, {leaked.name},
                         "a sandbox this run leaked was not counted")

    def test_run_tag_names_the_sandbox_and_is_sanitized(self):
        """The script itself honours the tag: its sandbox carries it, and glob or
        path characters in a tag are stripped, never passed through."""
        tag = new_run_tag()
        proc = subprocess.run([sys.executable, str(SCRIPT), "--keep"],
                               capture_output=True, text=True, timeout=600,
                               env=tagged_env(tag + "/../*"))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        line = next((l for l in proc.stdout.splitlines() if l.startswith("sandbox: ")), None)
        self.assertIsNotNone(line, proc.stdout)
        path = pathlib.Path(line[len("sandbox: "):].strip())
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        self.assertTrue(path.name.startswith("harness-rehearsal-{}-".format(tag)), path.name)
        self.assertNotIn("*", path.name)

    def test_keep_flag_retains_the_sandbox_for_inspection(self):
        tag = new_run_tag()
        before_sandboxes = sandbox_names(tag)

        proc = subprocess.run([sys.executable, str(SCRIPT), "--keep"],
                               capture_output=True, text=True, timeout=600,
                               env=tagged_env(tag))
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

        after_sandboxes = sandbox_names(tag)
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


# The stub replaces `run_story` in a THROWAWAY COPY of the script, so each scenario
# exercises the live-tree check end to end (real sandbox, real guard, real
# subprocesses) in about ten seconds instead of the full story's.
STUB_STORY = """
def _stub_story(bindir, harness_dir, keys_dir, root, sc):
    import time
    scenario = os.environ["STUB_SCENARIO"]
    hs = pathlib.Path(os.environ["STUB_HANDSHAKE"])
    live = LIVE_HARNESS
    if scenario == "concurrent":
        (hs / "ready").write_text("1")
        deadline = time.time() + 120
        while not (hs / "edited").exists() and time.time() < deadline:
            time.sleep(0.05)
    elif scenario == "child_writes_unprotected":
        run([PY, "-c", "import sys; open(sys.argv[1], 'w').write('x')",
             str(live / "tasks" / "planted-by-rehearsal.json")])
    elif scenario == "child_appends_existing":
        run([PY, "-c", "import sys; open(sys.argv[1], 'a').write(' ')",
             str(live / "plan.md")])
    elif scenario == "own_process_writes":
        (live / "planted-by-rehearsal.txt").write_text("x")
    elif scenario == "child_writes_protected":
        run([PY, "-c", "import sys; open(sys.argv[1], 'w').write('x')",
             str(live / "trust" / "planted-by-rehearsal.txt")])
    elif scenario == "shell_writes_protected":
        run(["sh", "-c", 'echo x >> "$1"', "sh",
             str(live / "warrants" / "planted-by-rehearsal.txt")])
    elif scenario == "shell_writes_unprotected":
        run(["sh", "-c", 'echo x >> "$1"', "sh",
             str(live / "tasks" / "planted-by-rehearsal.json")])
"""


def make_throwaway_repo(base):
    """examples/rehearsal/run_rehearsal.py plus a copy of the live .harness/ (minus
    private keys, logs, locks, tests and bytecode), with the script's story swapped
    for `_stub_story`. Its REPO_ROOT is the copy, so its 'live tree' is the copy."""
    base = pathlib.Path(base)
    shutil.copytree(LIVE_HARNESS, base / ".harness",
                    ignore=shutil.ignore_patterns("keys", "logs", "locks", "tests",
                                                  "__pycache__"))
    script_dir = base / "examples" / "rehearsal"
    script_dir.mkdir(parents=True)
    text = SCRIPT.read_text(encoding="utf-8")
    call = "            run_story(bindir, harness_dir, keys_dir, root, sc)\n"
    guard = 'if __name__ == "__main__":\n'
    assert text.count(call) == 1 and text.count(guard) == 1
    text = text.replace(
        call, "            _stub_story(bindir, harness_dir, keys_dir, root, sc)\n")
    text = text.replace(guard, STUB_STORY + "\n\n" + guard)
    script = script_dir / "run_rehearsal.py"
    script.write_text(text, encoding="utf-8")
    return base, script


def remove_if_present(path):
    if path.exists():
        path.unlink()


class LiveTreeCheckTests(unittest.TestCase):
    """T-478: the live-tree check is strict where it matters and immune to other
    processes' edits, shown against a throwaway copy of the repository."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="rehearsal-livecheck-")
        cls.base, cls.script = make_throwaway_repo(cls._tmp)
        cls.live = cls.base / ".harness"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def _start(self, scenario, handshake):
        env = dict(os.environ, STUB_SCENARIO=scenario, STUB_HANDSHAKE=str(handshake))
        return subprocess.Popen([sys.executable, str(self.script), "--json"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=env)

    def _finish(self, proc):
        out, err = proc.communicate(timeout=300)
        line = next((l for l in out.splitlines() if l.startswith("scorecard-json: ")),
                    None)
        self.assertIsNotNone(line, out + err)
        return proc.returncode, json.loads(line[len("scorecard-json: "):]), out + err

    def _run(self, scenario):
        with tempfile.TemporaryDirectory() as hs:
            return self._finish(self._start(scenario, hs))

    def _assert_fails(self, scenario, needle, cleanup=()):
        for path in cleanup:
            self.addCleanup(remove_if_present, path)
        rc, card, log = self._run(scenario)
        self.assertEqual(rc, 1, log)
        self.assertFalse(card["live_tree_untouched"])
        self.assertTrue(any(needle in d for d in card["live_tree_diffs"]),
                        card["live_tree_diffs"])
        return card

    def test_the_protected_set_matches_the_scripts(self):
        spec = importlib.util.spec_from_file_location("run_rehearsal_under_test", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(tuple(mod.PROTECTED_LIVE_PATHS), PROTECTED_LIVE_PATHS)

    def test_a_clean_run_passes(self):
        rc, card, log = self._run("clean")
        self.assertEqual(rc, 0, log)
        self.assertTrue(card["live_tree_untouched"], card["live_tree_diffs"])

    def test_a_concurrent_edit_outside_the_protected_set_does_not_fail(self):
        plan = self.live / "plan.md"
        original = plan.read_bytes()
        new_file = self.live / "tasks" / "T-concurrent-edit.json"
        self.addCleanup(remove_if_present, new_file)
        self.addCleanup(plan.write_bytes, original)
        with tempfile.TemporaryDirectory() as hs:
            hs = pathlib.Path(hs)
            proc = self._start("concurrent", hs)
            deadline = time.time() + 120
            while not (hs / "ready").exists():
                self.assertIsNone(proc.poll(), "the run ended before its handshake")
                self.assertLess(time.time(), deadline, "the run never became ready")
                time.sleep(0.05)
            # Another process's legitimate edits, made while the rehearsal is running
            # (after its first snapshot, before its second).
            plan.write_bytes(original + b"\nedited by another agent\n")
            new_file.write_text("{}")
            (hs / "edited").write_text("1")
            rc, card, log = self._finish(proc)
        self.assertEqual(rc, 0, log)
        self.assertTrue(card["live_tree_untouched"], card["live_tree_diffs"])
        self.assertNotEqual(plan.read_bytes(), original,
                            "the simulated edit did not land")

    def test_a_write_by_a_rehearsal_subprocess_to_the_live_tree_fails(self):
        self._assert_fails(
            "child_writes_unprotected",
            "live write by the rehearsal (open): tasks/planted-by-rehearsal.json",
            [self.live / "tasks" / "planted-by-rehearsal.json"])

    def test_an_append_by_a_rehearsal_subprocess_to_an_existing_live_file_fails(self):
        plan = self.live / "plan.md"
        self.addCleanup(plan.write_bytes, plan.read_bytes())
        self._assert_fails("child_appends_existing",
                           "live write by the rehearsal (open): plan.md")

    def test_a_write_by_the_rehearsal_process_itself_to_the_live_tree_fails(self):
        self._assert_fails(
            "own_process_writes",
            "live write by the rehearsal (open): planted-by-rehearsal.txt",
            [self.live / "planted-by-rehearsal.txt"])

    def test_a_write_to_a_protected_path_fails_on_both_arms(self):
        card = self._assert_fails(
            "child_writes_protected",
            "protected path changed/added/removed: trust/planted-by-rehearsal.txt",
            [self.live / "trust" / "planted-by-rehearsal.txt"])
        self.assertTrue(any("live write by the rehearsal" in d
                            for d in card["live_tree_diffs"]), card["live_tree_diffs"])

    def test_a_write_to_a_protected_path_the_guard_cannot_see_still_fails(self):
        # A non-Python process is invisible to the write guard; the byte-strict hash
        # arm is what catches it.
        self._assert_fails(
            "shell_writes_protected",
            "protected path changed/added/removed: warrants/planted-by-rehearsal.txt",
            [self.live / "warrants" / "planted-by-rehearsal.txt"])

    def test_the_stated_limit_a_non_python_write_outside_the_protected_set_is_not_seen(self):
        # Pins the limit the script's docstring states, so a change that closes it
        # (or widens it) has to say so here.
        planted = self.live / "tasks" / "planted-by-rehearsal.json"
        self.addCleanup(remove_if_present, planted)
        rc, card, log = self._run("shell_writes_unprotected")
        self.assertEqual(rc, 0, log)
        self.assertTrue(planted.exists(), "the planted write did not happen")


if __name__ == "__main__":
    unittest.main()
