"""Tests for mdtoc.inserter (T-022).

Run via:
    python3 -m unittest discover -s projects/mdtoc/tests -t projects/mdtoc

``mdtoc`` has no ``__init__.py`` yet (created only by T-028), so we rely on
PEP-420 namespace packages: we insert ``projects/mdtoc`` onto ``sys.path``
before importing ``mdtoc.inserter``. We never import ``mdtoc.parser`` or any
real slugger here -- headings are represented by a local ``namedtuple`` stub
and ``slugify`` is a local stub callable, per the dependency-injection design
that keeps ``inserter.py`` decoupled from both the parser and the slugger
tournament.
"""

import os
import sys
import unittest
from collections import namedtuple

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)  # projects/mdtoc
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mdtoc.inserter import (  # noqa: E402  (import after sys.path fixup)
    render_toc,
    insert_toc,
    TOC_START_MARKER,
    TOC_STOP_MARKER,
)


# Minimal duck-typed heading stand-in: render_toc only needs .level/.text,
# and deliberately does NOT import mdtoc.parser.Heading.
Heading = namedtuple("Heading", ["level", "text", "line"])


def make_heading(level, text, line=0):
    return Heading(level=level, text=text, line=line)


def simple_slugify(text, seen):
    """The exact stub suggested by the acceptance criteria: no dedup."""
    return text.lower().replace(" ", "-")


def dedup_slugify(text, seen):
    """A slightly richer stub that USES the shared `seen` dict to prove
    render_toc threads a single dict through the whole document (so
    duplicate heading text dedupes consistently, e.g. 'foo', 'foo-1')."""
    base = text.lower().replace(" ", "-")
    count = seen.get(base, 0)
    seen[base] = count + 1
    if count == 0:
        return base
    return "{}-{}".format(base, count)


class RenderTocNestingTests(unittest.TestCase):
    def test_nesting_and_indentation(self):
        headings = [
            make_heading(1, "Intro"),
            make_heading(2, "Background"),
            make_heading(3, "Details"),
            make_heading(2, "Usage"),
        ]
        toc = render_toc(headings, simple_slugify, max_depth=3)
        expected = "\n".join([
            "- [Intro](#intro)",
            "  - [Background](#background)",
            "    - [Details](#details)",
            "  - [Usage](#usage)",
        ])
        self.assertEqual(toc, expected)

    def test_shallowest_included_level_sets_base_indent(self):
        # No level-1 heading present -> level 2 is the shallowest included
        # level and therefore gets ZERO indent; level 3 gets one indent step.
        headings = [
            make_heading(2, "Top"),
            make_heading(3, "Child"),
        ]
        toc = render_toc(headings, simple_slugify, max_depth=3)
        expected = "\n".join([
            "- [Top](#top)",
            "  - [Child](#child)",
        ])
        self.assertEqual(toc, expected)

    def test_render_toc_default_max_depth_is_3(self):
        headings = [
            make_heading(1, "A"),
            make_heading(4, "TooDeep"),
        ]
        toc = render_toc(headings, simple_slugify)  # default max_depth=3
        self.assertEqual(toc, "- [A](#a)")


class RenderTocMaxDepthTests(unittest.TestCase):
    def test_headings_deeper_than_max_depth_are_omitted(self):
        headings = [
            make_heading(1, "One"),
            make_heading(2, "Two"),
            make_heading(4, "FourDeep"),
            make_heading(5, "FiveDeep"),
        ]
        toc = render_toc(headings, simple_slugify, max_depth=3)
        self.assertNotIn("FourDeep", toc)
        self.assertNotIn("FiveDeep", toc)
        expected = "\n".join([
            "- [One](#one)",
            "  - [Two](#two)",
        ])
        self.assertEqual(toc, expected)

    def test_omitted_deep_heading_does_not_affect_indentation(self):
        # A level-1 heading is omitted by a strict max_depth of 0-effective
        # scenario is impossible (levels start at 1), so instead prove: an
        # excluded DEEPER heading interleaved between included ones does not
        # change the shallowest-level computation or indentation of the
        # included siblings.
        headings = [
            make_heading(2, "Alpha"),
            make_heading(5, "ExcludedDeep"),
            make_heading(2, "Beta"),
        ]
        toc = render_toc(headings, simple_slugify, max_depth=3)
        expected = "\n".join([
            "- [Alpha](#alpha)",
            "- [Beta](#beta)",
        ])
        self.assertEqual(toc, expected)

    def test_all_headings_deeper_than_max_depth_yields_empty_string(self):
        headings = [make_heading(4, "Deep"), make_heading(5, "Deeper")]
        toc = render_toc(headings, simple_slugify, max_depth=3)
        self.assertEqual(toc, "")

    def test_no_headings_yields_empty_string(self):
        self.assertEqual(render_toc([], simple_slugify, max_depth=3), "")


class RenderTocSharedSeenDictTests(unittest.TestCase):
    def test_duplicate_headings_dedupe_consistently_via_shared_seen(self):
        headings = [
            make_heading(1, "Foo"),
            make_heading(2, "Bar"),
            make_heading(1, "Foo"),
        ]
        toc = render_toc(headings, dedup_slugify, max_depth=3)
        expected = "\n".join([
            "- [Foo](#foo)",
            "  - [Bar](#bar)",
            "- [Foo](#foo-1)",
        ])
        self.assertEqual(toc, expected)


class InsertTocMarkerReplacementTests(unittest.TestCase):
    def test_replaces_only_content_between_markers(self):
        text = (
            "# Title\n"
            "\n"
            "Some intro text.\n"
            "\n"
            "{start}\n"
            "OLD STALE TOC LINE\n"
            "{stop}\n"
            "\n"
            "## Body\n"
            "Body content untouched.\n"
        ).format(start=TOC_START_MARKER, stop=TOC_STOP_MARKER)

        toc = "- [Body](#body)"
        result = insert_toc(text, toc)

        self.assertIsNotNone(result)
        self.assertIn("# Title\n\nSome intro text.\n\n", result)
        self.assertIn("\n## Body\nBody content untouched.\n", result)
        self.assertIn(TOC_START_MARKER, result)
        self.assertIn(TOC_STOP_MARKER, result)
        self.assertNotIn("OLD STALE TOC LINE", result)
        self.assertIn(toc, result)
        # Markers preserved, ordered, and content between them is exactly
        # the rendered toc (with the newlines insert_toc supplies).
        expected = (
            "# Title\n"
            "\n"
            "Some intro text.\n"
            "\n"
            "{start}\n"
            "{toc}\n"
            "{stop}\n"
            "\n"
            "## Body\n"
            "Body content untouched.\n"
        ).format(start=TOC_START_MARKER, stop=TOC_STOP_MARKER, toc=toc)
        self.assertEqual(result, expected)

    def test_empty_region_between_markers_gets_toc_inserted(self):
        text = "before\n{start}{stop}\nafter".format(
            start=TOC_START_MARKER, stop=TOC_STOP_MARKER
        )
        result = insert_toc(text, "- [X](#x)")
        self.assertEqual(
            result,
            "before\n{start}\n- [X](#x)\n{stop}\nafter".format(
                start=TOC_START_MARKER, stop=TOC_STOP_MARKER
            ),
        )


class InsertTocMarkersAbsentTests(unittest.TestCase):
    def test_returns_none_when_no_markers_present(self):
        text = "# Title\n\nNo markers here at all.\n"
        self.assertIsNone(insert_toc(text, "- [Title](#title)"))

    def test_returns_none_when_only_start_marker_present(self):
        text = "{start}\nno stop marker below\n".format(start=TOC_START_MARKER)
        self.assertIsNone(insert_toc(text, "- [X](#x)"))

    def test_returns_none_when_only_stop_marker_present(self):
        text = "no start marker above\n{stop}\n".format(stop=TOC_STOP_MARKER)
        self.assertIsNone(insert_toc(text, "- [X](#x)"))

    def test_returns_none_when_stop_marker_precedes_start_marker(self):
        text = "{stop}\nsome text\n{start}\n".format(
            stop=TOC_STOP_MARKER, start=TOC_START_MARKER
        )
        self.assertIsNone(insert_toc(text, "- [X](#x)"))

    def test_absent_markers_leaves_no_partial_mutation(self):
        # Belt-and-suspenders: original text object/content is never mutated
        # and the function purely returns None, doing no other side effect.
        text = "plain text\n"
        original = text
        result = insert_toc(text, "- [X](#x)")
        self.assertIsNone(result)
        self.assertEqual(text, original)


class InsertTocIdempotencyTests(unittest.TestCase):
    def test_insert_toc_is_idempotent(self):
        text = (
            "# Doc\n"
            "{start}\n"
            "{stop}\n"
            "## Section\n"
        ).format(start=TOC_START_MARKER, stop=TOC_STOP_MARKER)
        toc = "- [Section](#section)"

        once = insert_toc(text, toc)
        twice = insert_toc(once, toc)

        self.assertEqual(once, twice)

    def test_insert_toc_idempotent_with_realistic_document(self):
        headings = [
            make_heading(1, "Overview"),
            make_heading(2, "Setup"),
            make_heading(2, "Usage"),
        ]
        toc = render_toc(headings, simple_slugify, max_depth=3)

        text = (
            "# Overview\n"
            "\n"
            "{start}\n"
            "{stop}\n"
            "\n"
            "## Setup\n"
            "Install stuff.\n"
            "\n"
            "## Usage\n"
            "Run stuff.\n"
        ).format(start=TOC_START_MARKER, stop=TOC_STOP_MARKER)

        once = insert_toc(text, toc)
        twice = insert_toc(once, toc)
        thrice = insert_toc(twice, toc)

        self.assertEqual(once, twice)
        self.assertEqual(twice, thrice)


if __name__ == "__main__":
    unittest.main()
