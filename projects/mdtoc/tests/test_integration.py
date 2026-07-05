"""End-to-end integration test for mdtoc (T-028).

Run via:
    python3 -m unittest discover -s projects/mdtoc/tests -t projects/mdtoc

Unlike test_cli.py (which calls ``cli.main()`` in-process), this test shells
out to the REAL entry point exactly as a user would invoke it:

    python3 -m mdtoc generate FILE [--max-depth N] [--in-place]
    python3 -m mdtoc check FILE

via ``subprocess``, with the working directory set to ``projects/mdtoc``
(the ``mdtoc`` package's parent directory) so that Python's ``-m`` machinery
puts it on ``sys.path`` -- the same "run from the package's parent
directory" convention documented in ``projects/mdtoc/README.md``. This
exercises ``mdtoc/__main__.py`` and ``mdtoc/__init__.py`` for real, not just
``mdtoc.cli`` in isolation.

All commands run against a throwaway copy of ``tests/fixtures/sample.md``;
the checked-in fixture itself is never mutated.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)  # projects/mdtoc (mdtoc's parent dir)
FIXTURE = os.path.join(_TESTS_DIR, "fixtures", "sample.md")

TOC_START = "<!-- toc -->"
TOC_STOP = "<!-- tocstop -->"

# T-038/P-012: the real `generate` now writes the start marker with a
# `max-depth=N` parameter (`<!-- toc max-depth=2 -->`), so locating it here
# needs the same tolerant pattern `mdtoc.cli` uses internally (this test
# shells out to the real CLI rather than importing it, so the pattern is
# duplicated rather than shared -- kept in sync manually, same as the two
# marker literals above already were).
_MARKER_START_RE = re.compile(r"<!-- toc(?: max-depth=(?:\d+))? -->")


def _between_markers(text):
    match = _MARKER_START_RE.search(text)
    if match is None:
        return None
    start = match.end()
    stop = text.find(TOC_STOP, start)
    if stop == -1:
        return None
    return text[start:stop]


def _run_mdtoc(*args):
    """Invoke `python3 -m mdtoc <args>` for real, cwd=projects/mdtoc."""
    result = subprocess.run(
        [sys.executable, "-m", "mdtoc"] + list(args),
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result


class TestEndToEndIdempotencyAndFidelity(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="mdtoc-integration-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.target = os.path.join(self.tmpdir, "sample.md")
        shutil.copyfile(FIXTURE, self.target)

    def _read_bytes(self):
        with open(self.target, "rb") as fh:
            return fh.read()

    def test_generate_in_place_twice_is_byte_identical(self):
        first = _run_mdtoc("generate", self.target, "--in-place")
        self.assertEqual(first.returncode, 0, msg=first.stderr)
        after_first = self._read_bytes()

        second = _run_mdtoc("generate", self.target, "--in-place")
        self.assertEqual(second.returncode, 0, msg=second.stderr)
        after_second = self._read_bytes()

        self.assertEqual(
            after_first,
            after_second,
            "running `generate --in-place` twice must be byte-identical (idempotent)",
        )

    def test_fenced_and_comment_hash_lines_never_appear_in_toc(self):
        result = _run_mdtoc("generate", self.target, "--in-place")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        with open(self.target, "r", encoding="utf-8") as fh:
            text = fh.read()
        toc = _between_markers(text)
        self.assertIsNotNone(toc)
        self.assertNotIn("looks like a heading", toc)
        self.assertNotIn("Not A Real Heading", toc)
        self.assertNotIn("def foo", toc)

    def test_duplicate_headings_get_dash1_dash2_anchors(self):
        # Add a THIRD occurrence of "Café" to exercise -1 then -2.
        with open(self.target, "r", encoding="utf-8") as fh:
            text = fh.read()
        text = text.replace(
            "## Conclusion", "## Café\n\nA third duplicate.\n\n## Conclusion"
        )
        with open(self.target, "w", encoding="utf-8") as fh:
            fh.write(text)

        result = _run_mdtoc("generate", self.target, "--in-place")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        with open(self.target, "r", encoding="utf-8") as fh:
            toc = _between_markers(fh.read())
        self.assertIn("(#café)", toc)
        self.assertIn("(#café-1)", toc)
        self.assertIn("(#café-2)", toc)

    def test_check_returns_zero_after_generate(self):
        gen = _run_mdtoc("generate", self.target, "--in-place")
        self.assertEqual(gen.returncode, 0, msg=gen.stderr)

        check = _run_mdtoc("check", self.target)
        self.assertEqual(check.returncode, 0, msg=check.stderr)

    def test_check_returns_one_before_generate_and_after_tamper(self):
        # Fixture markers are empty before the first generate: nonexistent
        # markers case doesn't apply here (markers ARE present, just with no
        # TOC body yet), so a fresh check must report stale (regenerating
        # would change the file, since the TOC body would go from empty to
        # populated).
        check_before = _run_mdtoc("check", self.target)
        self.assertEqual(check_before.returncode, 1)

        gen = _run_mdtoc("generate", self.target, "--in-place")
        self.assertEqual(gen.returncode, 0, msg=gen.stderr)

        with open(self.target, "r", encoding="utf-8") as fh:
            text = fh.read()
        tampered = text.replace(
            "[Conclusion](#conclusion)", "[Conclusion](#conclusion-stale)"
        )
        with open(self.target, "w", encoding="utf-8") as fh:
            fh.write(tampered)

        check_after_tamper = _run_mdtoc("check", self.target)
        self.assertEqual(check_after_tamper.returncode, 1)

    def test_generate_stdout_mode_matches_in_place_mode(self):
        stdout_run = _run_mdtoc("generate", self.target)
        self.assertEqual(stdout_run.returncode, 0, msg=stdout_run.stderr)

        _run_mdtoc("generate", self.target, "--in-place")
        with open(self.target, "r", encoding="utf-8", newline="") as fh:
            in_place_content = fh.read()

        self.assertEqual(stdout_run.stdout, in_place_content)


if __name__ == "__main__":
    unittest.main()
