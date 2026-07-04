"""Unit tests for mdtoc.parser (T-021).

The mdtoc package has no __init__.py yet (that marker file is created only
by T-028), so it is currently a PEP-420 namespace package. Rather than rely
on implicit namespace-package discovery working under every unittest runner
invocation, this file explicitly inserts projects/mdtoc/ onto sys.path (its
parent directory), matching the shared convention documented in every mdtoc
task: `python3 -m unittest discover -s projects/mdtoc/tests -t projects/mdtoc`.
"""
import os
import sys
import unittest

_MDTOC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _MDTOC_ROOT not in sys.path:
    sys.path.insert(0, _MDTOC_ROOT)

from mdtoc.parser import Heading, parse_headings  # noqa: E402


class TestAtxLevels(unittest.TestCase):
    """All 6 ATX heading levels are recognized with the correct level."""

    def test_all_six_levels(self):
        text = "\n".join(
            [
                "# H1",
                "## H2",
                "### H3",
                "#### H4",
                "##### H5",
                "###### H6",
            ]
        )
        result = parse_headings(text)
        self.assertEqual(
            result,
            [
                Heading(level=1, text="H1", line=1),
                Heading(level=2, text="H2", line=2),
                Heading(level=3, text="H3", line=3),
                Heading(level=4, text="H4", line=4),
                Heading(level=5, text="H5", line=5),
                Heading(level=6, text="H6", line=6),
            ],
        )


class TestIndentation(unittest.TestCase):
    """Up to 3 leading spaces are still recognized as headings."""

    def test_zero_to_three_leading_spaces(self):
        text = "\n".join(
            [
                "# Zero",
                " # One",
                "  # Two",
                "   # Three",
            ]
        )
        result = parse_headings(text)
        self.assertEqual(
            result,
            [
                Heading(level=1, text="Zero", line=1),
                Heading(level=1, text="One", line=2),
                Heading(level=1, text="Two", line=3),
                Heading(level=1, text="Three", line=4),
            ],
        )

    def test_four_leading_spaces_is_not_a_heading(self):
        # 4+ leading spaces is an indented code block in Markdown, not ATX.
        result = parse_headings("    # Not a heading")
        self.assertEqual(result, [])


class TestNonHeadingCases(unittest.TestCase):
    """The two explicit non-heading rules from the acceptance criteria."""

    def test_no_space_after_hashes_is_not_a_heading(self):
        result = parse_headings("#nospace")
        self.assertEqual(result, [])

    def test_seven_hashes_is_not_a_heading(self):
        result = parse_headings("####### x")
        self.assertEqual(result, [])

    def test_mixed_with_real_headings(self):
        text = "\n".join(["#nospace", "# Real", "####### x"])
        result = parse_headings(text)
        self.assertEqual(result, [Heading(level=1, text="Real", line=2)])


class TestTextExtraction(unittest.TestCase):
    """Surrounding whitespace and a trailing ATX closing run are stripped."""

    def test_trailing_closing_hashes_stripped(self):
        result = parse_headings("## Heading ##")
        self.assertEqual(result, [Heading(level=2, text="Heading", line=1)])

    def test_extra_whitespace_stripped(self):
        result = parse_headings("#   Spaced Out   ")
        self.assertEqual(result, [Heading(level=1, text="Spaced Out", line=1)])

    def test_closing_hashes_without_preceding_space_are_literal(self):
        # No whitespace before the trailing '#' run -> not a closing
        # sequence, so it is kept as part of the literal text.
        result = parse_headings("# Heading##")
        self.assertEqual(result, [Heading(level=1, text="Heading##", line=1)])

    def test_empty_heading_text(self):
        result = parse_headings("# ")
        self.assertEqual(result, [Heading(level=1, text="", line=1)])


class TestCodeFenceExclusion(unittest.TestCase):
    """Headings inside fenced code blocks are ignored, for both fence chars."""

    def test_backtick_fence_excludes_headings(self):
        text = "\n".join(
            [
                "# Before",
                "```",
                "# not a heading",
                "```",
                "# After",
            ]
        )
        result = parse_headings(text)
        self.assertEqual(
            result,
            [
                Heading(level=1, text="Before", line=1),
                Heading(level=1, text="After", line=5),
            ],
        )

    def test_tilde_fence_excludes_headings(self):
        text = "\n".join(
            [
                "# Before",
                "~~~",
                "# not a heading",
                "~~~",
                "# After",
            ]
        )
        result = parse_headings(text)
        self.assertEqual(
            result,
            [
                Heading(level=1, text="Before", line=1),
                Heading(level=1, text="After", line=5),
            ],
        )

    def test_fence_with_info_string_excludes_headings(self):
        text = "\n".join(
            [
                "# Before",
                "```python",
                "# not a heading (a python comment)",
                "```",
                "# After",
            ]
        )
        result = parse_headings(text)
        self.assertEqual(
            result,
            [
                Heading(level=1, text="Before", line=1),
                Heading(level=1, text="After", line=5),
            ],
        )

    def test_fence_closes_only_on_equal_or_longer_run(self):
        # A shorter run of the fence char inside the block does NOT close
        # it; the block only closes on a run >= the opener's length.
        text = "\n".join(
            [
                "````",
                "```",
                "# still not a heading",
                "````",
                "# After",
            ]
        )
        result = parse_headings(text)
        self.assertEqual(result, [Heading(level=1, text="After", line=5)])

    def test_mismatched_fence_chars_do_not_close(self):
        # A tilde run does not close a backtick fence, and vice versa.
        text = "\n".join(
            [
                "```",
                "~~~",
                "# not a heading",
                "```",
                "# After",
            ]
        )
        result = parse_headings(text)
        self.assertEqual(result, [Heading(level=1, text="After", line=5)])


class TestHtmlCommentExclusion(unittest.TestCase):
    """Headings inside HTML comments are ignored, including multi-line ones."""

    def test_multiline_comment_excludes_heading(self):
        text = "\n".join(
            [
                "# Before",
                "<!--",
                "# not a heading",
                "still commented",
                "-->",
                "# After",
            ]
        )
        result = parse_headings(text)
        self.assertEqual(
            result,
            [
                Heading(level=1, text="Before", line=1),
                Heading(level=1, text="After", line=6),
            ],
        )

    def test_single_line_comment_excludes_heading(self):
        text = "\n".join(
            [
                "<!-- # not a heading -->",
                "# After",
            ]
        )
        result = parse_headings(text)
        self.assertEqual(result, [Heading(level=1, text="After", line=2)])


class TestLineNumbers(unittest.TestCase):
    """1-based line numbers are correct even with interleaved noise."""

    def test_line_numbers_with_mixed_content(self):
        text = "\n".join(
            [
                "intro text",
                "",
                "# First",
                "some body text",
                "```",
                "# skipped",
                "```",
                "",
                "## Second",
            ]
        )
        result = parse_headings(text)
        self.assertEqual(
            result,
            [
                Heading(level=1, text="First", line=3),
                Heading(level=2, text="Second", line=9),
            ],
        )


if __name__ == "__main__":
    unittest.main()
