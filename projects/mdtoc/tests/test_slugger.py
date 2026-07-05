"""Unit tests for the tournament-promoted mdtoc.slugger (T-027).

mdtoc has no __init__.py yet (created only by T-028), so it is a PEP-420
namespace package. Following the shared mdtoc test convention, this file
explicitly inserts projects/mdtoc/ onto sys.path so `from mdtoc.slugger import
slugify` resolves, and additionally inserts projects/mdtoc/candidates/ so the
candidate-agnostic golden-vector module (`vectors`, T-023) is importable to
score the PROMOTED implementation with the exact same suite the tournament used.

Coverage:
  1. FULL GOLDEN SUITE via vectors.run_against(slugify) against the promoted
     mdtoc.slugger -- asserts the recorded 24/24 pass rate with zero failures.
  2. TIE-BREAKER PINS that were decisive in the T-027 verdict, so a future
     regression (e.g. someone "simplifying" the winner back toward a losing
     candidate's behavior) surfaces immediately:
       (a) winner B's WHITESPACE handling: tab and ideographic space U+3000
           become hyphens (str.isspace()), unlike losing candidates A/C which
           drop non-U+0020 whitespace;
       (b) winner B's COMBINING-MARK handling: an NFD "cafe"+U+0301 keeps the
           mark, unlike losing candidate A which strips it.
  3. DEDUP-COLLISION contract (T-039/P-013, see mdtoc/slugger.py's DEDUP RULE
     TABLE): github-slugger-style produced-slug registration is pinned so
     ['Foo','Foo','Foo-1'] no longer collides (-> ['foo','foo-1','foo-1-1']),
     plus a stress regression over a longer chain of colliding bases.
     NOTE: this INVERTS a prior pin in this file that asserted the naive
     base->count contract's collision (['foo','foo-1','foo-1']) as correct;
     see TestDedupCollisionContract below for the full rationale.
Run: python3 -m unittest discover -s projects/mdtoc/tests -t projects/mdtoc
"""
import os
import sys
import unicodedata
import unittest

_MDTOC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _MDTOC_ROOT not in sys.path:
    sys.path.insert(0, _MDTOC_ROOT)

_CANDIDATES_DIR = os.path.join(_MDTOC_ROOT, "candidates")
if _CANDIDATES_DIR not in sys.path:
    sys.path.insert(0, _CANDIDATES_DIR)

import vectors  # noqa: E402  (candidate-agnostic golden vectors, T-023)
from mdtoc.slugger import slugify  # noqa: E402  (the PROMOTED winner, T-027)


class TestPromotedSluggerGoldenVectors(unittest.TestCase):
    """The promoted slugger must pass the full golden suite the tournament used."""

    def test_full_golden_suite_passes_24_of_24(self):
        passed, total, failures = vectors.run_against(slugify)
        self.assertEqual(total, 24, "golden suite size drifted from the 24 cases T-027 scored")
        self.assertEqual(
            failures,
            [],
            "promoted mdtoc.slugger regressed on golden vectors: %r" % (failures,),
        )
        self.assertEqual(
            (passed, total),
            (24, 24),
            "promoted mdtoc.slugger must score 24/24 (was %d/%d)" % (passed, total),
        )


class TestDedupCollisionContract(unittest.TestCase):
    """Pins the COLLISION-SAFE github-slugger-style dedup contract.

    DECISION (T-039/P-013, inverting a prior pin in this file): this class
    used to assert the NAIVE base->count contract's output -- ['Foo','Foo',
    'Foo-1'] -> ['foo','foo-1','foo-1'] -- as a CORRECT, tournament-agreed
    behavior. It was not correct; it was a known, verified (3x) real anchor
    collision (F4 in the generation-3 audit, P-013): 'Foo-1' is a plausible
    literal heading, and colliding with the auto-numbered second 'Foo' means
    two different headings resolve to the same in-page anchor.

    EXPECTED (before T-039): naive base->count dedup -> ['foo','foo-1','foo-1']
    (collision; len(set(out)) == 2 != len(out) == 3).
    ACTUAL (after T-039): mdtoc/slugger.py now also registers each PRODUCED
    slug into `seen` (github-slugger's `slugger.prototype.slug` occurrence
    re-registration -- see the DEDUP RULE TABLE in slugger.py's docstring),
    so the third call's base 'foo-1' is recognized as already taken (by the
    second call's produced-slug registration) and is bumped again ->
    ['foo','foo-1','foo-1-1'] (unique; len(set(out)) == len(out) == 3).

    This test now pins the NEW collision-safe outcome. Every OTHER
    tournament-decisive pin in this file (whitespace, combining marks) is
    untouched by T-039 and is preserved verbatim below.
    """

    def test_foo_foo_foo1_no_longer_collides(self):
        seen = {}
        out = [slugify(x, seen) for x in ["Foo", "Foo", "Foo-1"]]
        self.assertEqual(out, ["foo", "foo-1", "foo-1-1"])
        self.assertEqual(len(set(out)), len(out), "produced anchors must be unique")

    def test_stress_list_of_colliding_bases_all_unique(self):
        # A longer chain where each produced slug is itself reused as a
        # LATER heading's literal base slug, exercising RULE 2's re-
        # registration repeatedly (not just once, as in the 3-item case
        # above). If produced slugs were not registered, "Item-1" (the 4th
        # input) would collide with the 2nd input's produced "item-1", and
        # "Item-2" (the 6th input) would collide with the 3rd input's
        # produced "item-2".
        inputs = ["Item", "Item", "Item", "Item-1", "Item-1", "Item-2"]
        seen = {}
        out = [slugify(x, seen) for x in inputs]
        self.assertEqual(len(set(out)), len(out), "stress list produced a duplicate anchor: %r" % (out,))
        self.assertEqual(
            out,
            ["item", "item-1", "item-2", "item-1-1", "item-1-2", "item-2-1"],
        )


class TestWinnerWhitespaceBehavior(unittest.TestCase):
    """Winner B hyphenates ALL Unicode whitespace via str.isspace().

    This is the decisive divergence from losing candidates A and C, which only
    treat the literal U+0020 space and DROP tab / ideographic space. The T-021
    parser can emit tabs inside heading text, and GitHub treats tabs as
    whitespace, so the winning behavior is a hyphen -- pinned here so it is not
    silently regressed back to literal-space-only handling.
    """

    def test_tab_becomes_hyphen(self):
        self.assertEqual(slugify("Tab\there", {}), "tab-here")

    def test_ideographic_space_u3000_becomes_hyphen(self):
        self.assertEqual(slugify("a　b", {}), "a-b")


class TestWinnerCombiningMarkBehavior(unittest.TestCase):
    """Winner B keeps Unicode combining marks (categories Mn/Mc/Me).

    Decisive divergence from losing candidate A, whose regex \\w strips category
    Mn. Decomposed (NFD) input -- e.g. 'cafe'+U+0301 rather than precomposed
    U+00E9 -- is plausible from real files, and GitHub keeps the mark, so the
    promoted winner must too. Pinned so a future edit cannot silently strip it.
    """

    def test_nfd_combining_acute_is_kept(self):
        nfd = "café"  # decomposed 'cafe' + COMBINING ACUTE ACCENT
        self.assertTrue(unicodedata.is_normalized("NFD", nfd), "probe input must be NFD")
        result = slugify(nfd, {})
        self.assertIn("́", result, "combining acute mark must survive step 2")
        self.assertNotEqual(result, "cafe", "winner must NOT strip the combining mark")
        self.assertEqual(result, "café")


if __name__ == "__main__":
    unittest.main()
