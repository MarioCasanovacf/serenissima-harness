"""Unit tests for mdtoc.cli (T-028).

Run via:
    python3 -m unittest discover -s projects/mdtoc/tests -t projects/mdtoc

These tests invoke ``cli.main()`` in-process (no subprocess) on temporary
copies of ``tests/fixtures/sample.md``, so the checked-in fixture is never
mutated by the test suite itself. End-to-end coverage of the real
``python3 -m mdtoc ...`` invocation (subprocess, exercising ``__main__.py``)
lives in ``test_integration.py``.
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)  # projects/mdtoc
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mdtoc import cli  # noqa: E402  (import after sys.path fixup)

FIXTURE = os.path.join(_TESTS_DIR, "fixtures", "sample.md")

TOC_START = "<!-- toc -->"
TOC_STOP = "<!-- tocstop -->"


def _between_markers(text):
    """Return the substring strictly between the TOC markers, or None.

    T-038: the start marker may now carry a ``max-depth=N`` parameter
    (``<!-- toc max-depth=2 -->``), so this locates it with the same regex
    ``cli.py`` itself uses (``cli._MARKER_START_RE``) rather than a bare
    literal search, while still falling back correctly for the legacy
    parameterless ``<!-- toc -->`` form.
    """
    match = cli._MARKER_START_RE.search(text)
    if match is None:
        return None
    start = match.end()
    stop = text.find(TOC_STOP, start)
    if stop == -1:
        return None
    return text[start:stop]


class CliTestCase(unittest.TestCase):
    """Base class: copies the fixture into a fresh temp dir per test."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="mdtoc-cli-test-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.target = os.path.join(self.tmpdir, "sample.md")
        shutil.copyfile(FIXTURE, self.target)

    def read_target(self):
        with open(self.target, "r", encoding="utf-8", newline="") as fh:
            return fh.read()

    def write_target(self, text):
        with open(self.target, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)


class TestGenerateInPlace(CliTestCase):
    def test_inserts_toc_between_markers(self):
        rc = cli.main(["generate", self.target, "--in-place"])
        self.assertEqual(rc, 0)
        updated = self.read_target()
        toc = _between_markers(updated)
        self.assertIsNotNone(toc)
        self.assertIn("[Sample Document](#sample-document)", toc)
        self.assertIn("[Introduction](#introduction)", toc)
        self.assertIn("[Nested Section](#nested-section)", toc)

    def test_in_place_leaves_markers_and_surrounding_text_untouched(self):
        original = self.read_target()
        cli.main(["generate", self.target, "--in-place"])
        updated = self.read_target()
        # Everything before the start marker and after the stop marker is
        # unchanged.
        start = original.find(TOC_START)
        stop = original.find(TOC_STOP) + len(TOC_STOP)
        self.assertEqual(updated[:start], original[:start])
        self.assertTrue(updated.endswith(original[stop:]))

    def test_duplicate_headings_get_deduped_anchors(self):
        cli.main(["generate", self.target, "--in-place"])
        toc = _between_markers(self.read_target())
        self.assertIn("(#café)", toc)
        self.assertIn("(#café-1)", toc)

    def test_fence_and_comment_hash_lines_never_appear_in_toc(self):
        cli.main(["generate", self.target, "--in-place"])
        toc = _between_markers(self.read_target())
        self.assertNotIn("looks like a heading", toc)
        self.assertNotIn("Not A Real Heading", toc)


class TestGenerateStdoutMode(CliTestCase):
    def test_without_in_place_prints_full_document_and_leaves_file_untouched(self):
        original = self.read_target()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli.main(["generate", self.target])
        self.assertEqual(rc, 0)
        # File on disk is untouched.
        self.assertEqual(self.read_target(), original)
        # Stdout carries the full updated document.
        printed = buf.getvalue()
        toc = _between_markers(printed)
        self.assertIsNotNone(toc)
        self.assertIn("[Introduction](#introduction)", toc)

    def test_without_markers_prints_only_the_rendered_toc(self):
        no_markers_path = os.path.join(self.tmpdir, "no_markers.md")
        with open(no_markers_path, "w", encoding="utf-8") as fh:
            fh.write("# Title\n\n## Section One\n\n## Section Two\n")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli.main(["generate", no_markers_path])
        self.assertEqual(rc, 0)

        printed = buf.getvalue()
        # No markers were present, so the file is untouched and only the
        # bare TOC (no surrounding document text) was printed.
        with open(no_markers_path, "r", encoding="utf-8") as fh:
            self.assertEqual(
                fh.read(), "# Title\n\n## Section One\n\n## Section Two\n"
            )
        self.assertIn("[Title](#title)", printed)
        self.assertIn("[Section One](#section-one)", printed)
        self.assertNotIn("# Title", printed)  # only TOC bullets, not the doc


class TestMaxDepthTruncation(CliTestCase):
    def test_default_max_depth_includes_level_three(self):
        cli.main(["generate", self.target, "--in-place"])
        toc = _between_markers(self.read_target())
        self.assertIn("[Nested Section](#nested-section)", toc)
        self.assertNotIn("Too Deep", toc)  # level 4, excluded even at default

    def test_max_depth_two_excludes_level_three(self):
        cli.main(["generate", self.target, "--in-place", "--max-depth", "2"])
        toc = _between_markers(self.read_target())
        self.assertNotIn("Nested Section", toc)
        self.assertIn("[Café](#café)", toc)

    def test_max_depth_one_only_top_level(self):
        cli.main(["generate", self.target, "--in-place", "--max-depth", "1"])
        toc = _between_markers(self.read_target())
        self.assertEqual(toc.strip(), "- [Sample Document](#sample-document)")


class TestCheck(CliTestCase):
    def test_returns_zero_when_fresh(self):
        cli.main(["generate", self.target, "--in-place"])
        rc = cli.main(["check", self.target])
        self.assertEqual(rc, 0)

    def test_returns_one_after_tampering(self):
        cli.main(["generate", self.target, "--in-place"])
        tampered = self.read_target().replace(
            "[Introduction](#introduction)", "[Introduction](#introduction-tampered)"
        )
        self.write_target(tampered)
        rc = cli.main(["check", self.target])
        self.assertEqual(rc, 1)

    def test_returns_one_when_markers_absent(self):
        no_markers_path = os.path.join(self.tmpdir, "no_markers.md")
        with open(no_markers_path, "w", encoding="utf-8") as fh:
            fh.write("# Title\n\n## Section\n")
        rc = cli.main(["check", no_markers_path])
        self.assertEqual(rc, 1)


class TestMarkerMaxDepthParameter(CliTestCase):
    """T-038/P-012: generate records the depth in the marker; check honors
    it (with a legacy fallback to 3 and an explicit --max-depth override).
    """

    def test_generate_records_max_depth_in_marker(self):
        cli.main(["generate", self.target, "--in-place", "--max-depth", "2"])
        updated = self.read_target()
        self.assertIn("<!-- toc max-depth=2 -->", updated)

    def test_generate_records_default_depth_explicitly_too(self):
        # DECISION: even the default (3) is written explicitly, never left
        # parameterless, so freshly-generated files are unambiguous.
        cli.main(["generate", self.target, "--in-place"])
        updated = self.read_target()
        self.assertIn("<!-- toc max-depth=3 -->", updated)

    def test_round_trip_generate_then_check_at_each_depth(self):
        # This is the exact scenario that used to false-stale: `generate
        # --max-depth 2 --in-place` followed by `check` (which used to
        # hardcode depth 3) must now exit 0 at every depth.
        for depth in (1, 2, 3, 4):
            with self.subTest(depth=depth):
                rc_gen = cli.main(
                    ["generate", self.target, "--in-place", "--max-depth", str(depth)]
                )
                self.assertEqual(rc_gen, 0)
                rc_check = cli.main(["check", self.target])
                self.assertEqual(rc_check, 0)

    def test_generate_twice_same_depth_is_byte_identical(self):
        cli.main(["generate", self.target, "--in-place", "--max-depth", "2"])
        first = self.read_target()
        cli.main(["generate", self.target, "--in-place", "--max-depth", "2"])
        second = self.read_target()
        self.assertEqual(first, second)

    def test_regenerating_over_an_existing_parameterized_marker_still_finds_it(self):
        # Second generate call must still locate the markers even though
        # the first call already rewrote the start marker to carry a param
        # (insert_toc itself only ever searches for the bare literal).
        cli.main(["generate", self.target, "--in-place", "--max-depth", "2"])
        rc = cli.main(["generate", self.target, "--in-place", "--max-depth", "4"])
        self.assertEqual(rc, 0)
        updated = self.read_target()
        self.assertIn("<!-- toc max-depth=4 -->", updated)
        toc = _between_markers(updated)
        self.assertIn("Nested Section", toc)  # level 3, included at depth 4

    def test_legacy_parameterless_marker_defaults_to_three(self):
        # Simulate a pre-T-038 file: content matches a depth-3 render, but
        # the marker itself carries no max-depth parameter at all.
        cli.main(["generate", self.target, "--in-place", "--max-depth", "3"])
        legacy = self.read_target().replace(
            "<!-- toc max-depth=3 -->", "<!-- toc -->"
        )
        self.write_target(legacy)
        rc = cli.main(["check", self.target])
        self.assertEqual(rc, 0)

    def test_legacy_parameterless_marker_with_non_default_content_is_stale(self):
        # Content was generated at depth 2, but the marker is stripped back
        # to the bare (parameterless) legacy form -- check must fall back
        # to the legacy default of 3, which disagrees with the depth-2
        # content, so it correctly reports stale rather than false-fresh.
        cli.main(["generate", self.target, "--in-place", "--max-depth", "2"])
        legacy = self.read_target().replace(
            "<!-- toc max-depth=2 -->", "<!-- toc -->"
        )
        self.write_target(legacy)
        rc = cli.main(["check", self.target])
        self.assertEqual(rc, 1)

    def test_check_max_depth_override_wins_over_marker(self):
        cli.main(["generate", self.target, "--in-place", "--max-depth", "3"])
        # The marker says max-depth=3; overriding to 2 must recompute at 2
        # and therefore disagree with the depth-3 content on disk.
        rc_override = cli.main(["check", self.target, "--max-depth", "2"])
        self.assertEqual(rc_override, 1)
        # Overriding back to the marker's own depth is fresh again.
        rc_matching = cli.main(["check", self.target, "--max-depth", "3"])
        self.assertEqual(rc_matching, 0)

    def test_check_help_documents_max_depth_override(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit):
                cli.main(["check", "--help"])
        self.assertIn("--max-depth", buf.getvalue())


class TestArgparseHelp(unittest.TestCase):
    """--help must work cleanly (exit code 0) for the program and both subcommands."""

    def _help_exit_code(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(argv)
        return ctx.exception.code, buf.getvalue()

    def test_top_level_help(self):
        code, out = self._help_exit_code(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("generate", out)
        self.assertIn("check", out)

    def test_generate_help(self):
        code, out = self._help_exit_code(["generate", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("--max-depth", out)
        self.assertIn("--in-place", out)

    def test_check_help(self):
        code, out = self._help_exit_code(["check", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("FILE", out)

    def test_missing_command_is_a_usage_error(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            with self.assertRaises(SystemExit) as ctx:
                cli.main([])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
