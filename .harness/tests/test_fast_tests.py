"""T-480: fast_tests.py --changed, --base, low priority and the half-the-cores slot cap.

Every selection test runs in a throwaway git repo built here (a tiny .harness/bin,
.harness/tests and examples tree, one initial commit), never in the live tree. The CLI
tests copy fast_tests.py and portalock.py into that repo's .harness/bin, so the copy
resolves its own REPO to the throwaway and the live tests are never collected.
"""
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
BIN = ROOT / ".harness" / "bin"
sys.path.insert(0, str(BIN))
_spec = importlib.util.spec_from_file_location("fast_tests_under_test", BIN / "fast_tests.py")
ft = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ft)

HEADER = ("import pathlib, sys\n"
          "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'bin'))\n")

FILES = {
    ".harness/bin/alpha.py": "X = 1\n",
    ".harness/bin/beta.py": "Y = 2\n",
    ".harness/bin/gamma.py": "Z = 3\n",
    ".harness/bin/orphan.py": "W = 4\n",
    "examples/demo/runner.py": "R = 5\n",
    "README.md": "readme\n",
    ".harness/tests/test_alpha.py": HEADER + "import alpha\n\n\ndef test_ok():\n    assert alpha.X == 1\n",
    ".harness/tests/test_beta.py": HEADER + "from beta import Y\n\n\ndef test_ok():\n    assert Y == 2\n",
    # names gamma.py in its text but imports nothing
    ".harness/tests/test_named.py": "# exercises .harness/bin/gamma.py through its CLI\n\n\ndef test_ok():\n    assert True\n",
    # a test whose own name holds 'orphan' must not count as naming orphan.py
    ".harness/tests/test_unrelated.py": "def test_ok():\n    assert True\n",
    ".harness/tests/test_runner_user.py": "# calls examples/demo/runner.py\n\n\ndef test_ok():\n    assert True\n",
}


def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                        "-c", "commit.gpgsign=false"] + list(args),
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


class Repo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = pathlib.Path(self._tmp.name)
        for rel, text in FILES.items():
            self.put(rel, text)
        git(self.repo, "init", "-q")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")

    def put(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def selected(self, base="HEAD"):
        changed = ft.git_changed(self.repo, base)
        picked, ignored = ft.select_changed(self.repo, changed)
        return {t.name: r for t, r in picked.items()}, ignored


class SelectionTests(Repo):
    def test_a_changed_bin_module_selects_the_test_that_imports_it_and_not_an_unrelated_one(self):
        self.put(".harness/bin/alpha.py", "X = 1\n# edited\n")
        picked, ignored = self.selected()
        self.assertEqual(set(picked), {"test_alpha.py"})
        self.assertIn("imports changed module .harness/bin/alpha.py", picked["test_alpha.py"])
        self.assertEqual(ignored, [])

    def test_from_import_form_is_seen_too(self):
        self.put(".harness/bin/beta.py", "Y = 2\n# edited\n")
        picked, _ = self.selected()
        self.assertEqual(set(picked), {"test_beta.py"})

    def test_a_changed_test_file_selects_itself(self):
        self.put(".harness/tests/test_unrelated.py", "def test_ok():\n    assert 1 == 1\n")
        picked, _ = self.selected()
        self.assertEqual(set(picked), {"test_unrelated.py"})
        self.assertEqual(picked["test_unrelated.py"], ["changed itself"])

    def test_an_untracked_new_test_file_is_selected(self):
        self.put(".harness/tests/test_fresh.py", "def test_ok():\n    assert True\n")
        picked, _ = self.selected()
        self.assertEqual(set(picked), {"test_fresh.py"})

    def test_a_module_named_only_by_file_name_in_the_test_source_selects_that_test(self):
        self.put(".harness/bin/gamma.py", "Z = 3\n# edited\n")
        picked, _ = self.selected()
        self.assertEqual(set(picked), {"test_named.py"})
        self.assertIn("names changed file gamma.py", picked["test_named.py"])

    def test_a_file_name_inside_a_longer_name_does_not_count(self):
        # test_alpha.py contains the text 'alpha.py' only as the tail of its own name in
        # nobody's source; build the case directly: a test that names 'xalpha.py'
        self.put(".harness/tests/test_decoy.py", "# touches xalpha.py and alpha.pyc\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "decoy")
        self.put(".harness/bin/alpha.py", "X = 1\n# edited\n")
        picked, _ = self.selected()
        self.assertEqual(set(picked), {"test_alpha.py"})

    def test_an_examples_module_is_scanned_like_a_bin_module(self):
        self.put("examples/demo/runner.py", "R = 5\n# edited\n")
        picked, _ = self.selected()
        self.assertEqual(set(picked), {"test_runner_user.py"})

    def test_an_unreferenced_change_selects_nothing_and_is_listed(self):
        self.put(".harness/bin/orphan.py", "W = 4\n# edited\n")
        self.put("README.md", "readme\nmore\n")
        picked, ignored = self.selected()
        self.assertEqual(picked, {})
        self.assertEqual(sorted(ignored), [".harness/bin/orphan.py", "README.md"])

    def test_no_change_at_all_selects_nothing(self):
        picked, ignored = self.selected()
        self.assertEqual((picked, ignored), ({}, []))

    def test_base_diffs_against_another_commit(self):
        self.put(".harness/bin/alpha.py", "X = 1\n# edited\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "edit alpha")
        picked, _ = self.selected()  # clean tree against HEAD
        self.assertEqual(picked, {})
        picked, _ = self.selected(base="HEAD~1")
        self.assertEqual(set(picked), {"test_alpha.py"})

    def test_a_bad_base_raises_instead_of_selecting_everything(self):
        with self.assertRaises(RuntimeError):
            ft.git_changed(self.repo, "no-such-ref")


class CliTests(Repo):
    """The real command line, from a copy of the runner inside the throwaway repo."""

    def setUp(self):
        super().setUp()
        dest = self.repo / ".harness" / "bin"
        for name in ("fast_tests.py", "portalock.py"):
            shutil.copy(BIN / name, dest / name)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "runner")

    def run_cli(self, *args, env=None):
        e = dict(os.environ)
        e.pop(ft.SLOTS_ENV, None)
        # A private temp dir, so the copy's machine-wide slot files are its own and a
        # busy neighbour on the real slot files can neither slow nor flake these tests.
        slots_tmp = self.repo.parent / (self.repo.name + "-slots")
        slots_tmp.mkdir(exist_ok=True)
        self.addCleanup(shutil.rmtree, str(slots_tmp), True)
        e["TMPDIR"] = str(slots_tmp)
        e.update(env or {})
        return subprocess.run([sys.executable, str(self.repo / ".harness" / "bin" / "fast_tests.py")]
                              + list(args), cwd=str(self.repo), capture_output=True, text=True,
                              env=e, timeout=300)

    def test_plan_prints_the_selection_with_reasons(self):
        self.put(".harness/bin/alpha.py", "X = 1\n# edited\n")
        p = self.run_cli("--changed", "--plan")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("test_alpha.py  (imports changed module .harness/bin/alpha.py)", p.stdout)
        self.assertIn("1 test files selected", p.stdout)
        self.assertNotIn("test_beta.py", p.stdout)
        self.assertIn("test_alpha.py", p.stdout.split("selected", 1)[1])

    def test_an_unreferenced_change_says_so_and_never_runs_the_suite(self):
        self.put(".harness/bin/orphan.py", "W = 4\n# edited\n")
        p = self.run_cli("--changed")
        self.assertEqual(p.returncode, 5, p.stdout + p.stderr)
        self.assertIn("0 test files selected", p.stdout)
        self.assertIn("no test references .harness/bin/orphan.py", p.stdout)
        self.assertIn("nothing ran", p.stdout)
        self.assertNotIn("passed", p.stdout)

    def test_changed_runs_only_the_selected_file(self):
        self.put(".harness/tests/test_beta.py", HEADER + "from beta import Y\n\n\n"
                 "def test_ok():\n    assert Y == 2\n\n\ndef test_two():\n    assert Y\n")
        p = self.run_cli("--changed")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("2 passed", p.stdout)
        self.assertIn("(1 files in", p.stdout)

    def test_base_flag_on_the_command_line(self):
        self.put(".harness/bin/alpha.py", "X = 1\n# edited\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "edit alpha")
        p = self.run_cli("--changed", "--base", "HEAD~1", "--plan")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("against HEAD~1", p.stdout)
        self.assertIn("test_alpha.py", p.stdout)

    def test_a_bad_base_fails_loudly(self):
        p = self.run_cli("--changed", "--base", "no-such-ref")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("cannot read the diff", p.stdout)

    def test_changed_with_named_files_is_refused(self):
        p = self.run_cli("--changed", "test_alpha.py")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("cannot be combined", p.stderr)

    def test_jobs_above_the_cap_is_clamped_and_said(self):
        self.put(".harness/bin/alpha.py", "X = 1\n# edited\n")
        p = self.run_cli("--changed", "-j", "9", "--pytest-arg=-q", env={ft.SLOTS_ENV: "2"})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("-j 9 is above the slot cap of 2", p.stdout)
        self.assertIn("2 workers", p.stdout)


class SlotCapTests(unittest.TestCase):
    def test_default_is_half_the_cores(self):
        with mock.patch.dict(os.environ):
            os.environ.pop(ft.SLOTS_ENV, None)
            with mock.patch.object(os, "cpu_count", return_value=10):
                self.assertEqual(ft.slot_cap(), 5)
            with mock.patch.object(os, "cpu_count", return_value=1):
                self.assertEqual(ft.slot_cap(), 1)
            with mock.patch.object(os, "cpu_count", return_value=None):
                self.assertEqual(ft.slot_cap(), 1)

    def test_the_env_var_overrides_the_default(self):
        with mock.patch.dict(os.environ, {ft.SLOTS_ENV: "3"}):
            with mock.patch.object(os, "cpu_count", return_value=64):
                self.assertEqual(ft.slot_cap(), 3)

    def test_a_bad_env_value_is_said_and_ignored(self):
        for bad in ("zero", "0", "-2"):
            with mock.patch.dict(os.environ, {ft.SLOTS_ENV: bad}), \
                    mock.patch.object(os, "cpu_count", return_value=10), \
                    mock.patch("sys.stderr") as err:
                self.assertEqual(ft.slot_cap(), 5)
                self.assertTrue(err.write.called, bad)

    def test_jobs_cannot_exceed_the_cap(self):
        with mock.patch.dict(os.environ, {ft.SLOTS_ENV: "2"}):
            self.assertEqual(ft.effective_jobs(8), 2)
            self.assertEqual(ft.effective_jobs(1), 1)
            self.assertEqual(ft.effective_jobs(0), 1)
            self.assertLessEqual(ft.default_jobs(), 2)

    def test_slot_files_never_exceed_the_cap(self):
        with mock.patch.dict(os.environ, {ft.SLOTS_ENV: "2"}), \
                tempfile.TemporaryDirectory() as d, \
                mock.patch.object(ft, "SLOT_DIR", pathlib.Path(d)):
            ft._slot_next[0] = 0
            seen = []
            import threading

            def work():
                ft._slot_ids.__dict__.clear()
                with ft.Slot():
                    seen.append(ft._slot_ids.i)

            for _ in range(6):
                t = threading.Thread(target=work)
                t.start()
                t.join()
            self.assertEqual(set(seen), {0, 1})
            self.assertEqual(sorted(p.name for p in pathlib.Path(d).iterdir()), ["slot-0", "slot-1"])


class NiceTests(unittest.TestCase):
    def probe(self, level):
        """Niceness after apply_nice(level), and a child's, in a fresh process."""
        code = ("import os, subprocess, sys\n"
                "sys.path.insert(0, %r)\n"
                "import fast_tests as ft\n"
                "got = ft.apply_nice(%d)\n"
                "child = subprocess.run([sys.executable, '-c', 'import os; print(os.nice(0))'],"
                " capture_output=True, text=True).stdout.strip()\n"
                "print(got, child)\n" % (str(BIN), level))
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        return [int(x) for x in p.stdout.split()]

    @unittest.skipUnless(hasattr(os, "nice"), "no os.nice on this platform")
    def test_children_inherit_the_requested_niceness(self):
        got, child = self.probe(10)
        self.assertGreaterEqual(got, 10)
        self.assertEqual(child, got)

    @unittest.skipUnless(hasattr(os, "nice"), "no os.nice on this platform")
    def test_the_level_is_clamped_and_never_lowered(self):
        got, child = self.probe(99)
        self.assertEqual((got, child), (19, 19))

    def test_the_default_is_ten_and_the_flag_exists(self):
        self.assertEqual(ft.DEFAULT_NICE, 10)
        p = subprocess.run([sys.executable, str(BIN / "fast_tests.py"), "--help"],
                           capture_output=True, text=True, timeout=60)
        self.assertIn("--nice", p.stdout)
        self.assertIn("--changed", p.stdout)
        self.assertIn("--base", p.stdout)


class DocstringTests(unittest.TestCase):
    def test_module_docstring_documents_nice_and_the_slot_cap(self):
        doc = ft.__doc__
        for needle in ("--changed", "--base", "nice 10", "--nice", "HARNESS_TEST_SLOTS",
                       "half the cores"):
            self.assertIn(needle, doc)


if __name__ == "__main__":
    unittest.main()
