"""mdtoc slugger candidate C -- GitHub-slugger SPEC-PORT (T-026).

APPROACH: this candidate ports the *documented* GitHub heading-anchor
algorithm as a small, explicit RULE TABLE, distinct from candidate A's
single dynamic regex substitution and candidate B's ad-hoc unicodedata
category membership check. The upstream algorithm (as historically
implemented by GitHub's html-pipeline `TocFilter#generate_id`, and
reproduced by the npm package `github-slugger`; cited verbatim in
projects/mdtoc/candidates/vectors.py's module docstring) is:

    1. downcase the heading text
    2. strip every character that is not a Unicode "word" character
       (letter, digit, mark, or underscore), a hyphen, or a literal space
    3. replace each remaining space with a hyphen (no collapsing)

then documents thread a per-document `seen` dict to dedupe repeated slugs
with a numeric suffix.

Each pipeline stage below is a separate, named function; step 2's character
classification is expressed as an explicit RULE TABLE (`_KEEP_MAJOR_CATEGORIES`
/ `_KEEP_LITERAL_CHARS`, consulted by `_is_kept_char`) with one comment per
rule citing the upstream rationale and, where one exists, the golden vector
in vectors.py that pins it. This keeps every keep/remove decision traceable
to a documented rule instead of being buried in one opaque regex or a bare
`if category in {...}` check.

-----------------------------------------------------------------------
DOCUMENTED DIVERGENCES FROM THE UPSTREAM SPEC (vectors.py is ground truth;
see the task brief for T-026 and vectors.py's own module docstring):
-----------------------------------------------------------------------

1. EMOJI (e.g. U+2728 "Sparkles" - "✨"): the *documented* algorithm
   above says step 2 removes any character that is not a word/hyphen/space,
   and U+2728 is Unicode general category "So" (Symbol, other) -- not a
   word character -- so the documented algorithm removes it. This candidate
   follows the documented algorithm (and vectors.py: "Great✨News Update"
   -> "greatnews-update").
   However, the *actual, shipped* github-slugger implementation does NOT
   use a live Unicode-category test at all: its `regex.js` is a large,
   hand-generated blocklist of specific punctuation/symbol code points, and
   that blocklist has known gaps for emoji added to Unicode after the
   blocklist was generated (U+2728 SPARKLES is one such gap). Real
   github-slugger therefore emits "great✨news-update" (emoji retained)
   for this input -- diverging from both the documented algorithm and from
   vectors.py. This candidate intentionally does NOT reproduce that
   blocklist gap: it implements the documented category-based rule so it
   agrees with vectors.py's ground truth, and calls the discrepancy out
   here rather than silently picking one behavior.

2. DEDUP COLLISION HANDLING: vectors.py's module docstring pins the dedup
   contract explicitly as "seen maps base-slug -> count of PRIOR uses of
   that base slug" -- i.e. a NAIVE base-slug counter, with no re-checking
   of the literal (suffixed) output string. This candidate implements
   exactly that naive contract (see `slugify` below).
   The actual github-slugger implementation does something subtly richer:
   after computing `base + "-" + occurrence`, it also registers that exact
   *produced* string as its own key in the occurrences map (see upstream
   `slugger.prototype.slug`, which does `self.occurrences[slug] = 0` for
   the final, possibly-suffixed slug, not just the base). This guards
   against a document that contains both "Foo" (twice) and a literal
   heading "Foo 1": naive base-counting would emit "foo", "foo-1" (for the
   second "Foo") and ALSO "foo-1" (for the literal "Foo 1"), a genuine
   output collision; real github-slugger's extra bookkeeping would detect
   that "foo-1" is already taken and bump again. None of vectors.py's
   DEDUP_SEQUENCES exercise this collision case, and the module docstring's
   contract explicitly calls for the naive base->count mapping, so this
   candidate implements the naive version to conform to vectors.py rather
   than the richer (but unspecified-by-contract) upstream recursion.

Conforms to the candidate-agnostic interface documented in vectors.py:

    slugify(text: str, seen: dict) -> str

Python 3.9+, stdlib only (unicodedata). No import of the mdtoc package or
of the other tournament candidates.
"""

from __future__ import annotations

import unicodedata

# ---------------------------------------------------------------------------
# STEP 2 RULE TABLE
#
# The documented algorithm keeps a character iff it is a Unicode "word"
# character (letter, digit, mark, or underscore), a literal hyphen, or a
# literal space. Unicode general categories split naturally into "major
# classes" (the first letter of the two-letter category code, e.g. "Lu" ->
# major class "L"). We express "word character" as membership in one of
# three major classes, plus two characters ('_' and ' ') and one more
# ('-') that must be special-cased because their own general category
# would otherwise place them in the fallthrough (removed) bucket.
# ---------------------------------------------------------------------------

# RULE L -- major class "L" (Lu, Ll, Lt, Lm, Lo): Unicode letters.
#   Cited: html-pipeline / github-slugger's "word character" includes any
#   Unicode letter, not just ASCII a-z. Vectors: "Café con leche" ->
#   "café-con-leche" (Ll 'é' kept + lowercased); "日本語 テスト" ->
#   "日本語-テスト" (Lo ideographs/kana kept, no case to fold).
#
# RULE N -- major class "N" (Nd, Nl, No): digits and other numerals.
#   Cited: "word character" includes digits. Vector: "Section 2.1
#   Overview" -> "section-21-overview" (Nd '2' and '1' kept; the '.'
#   between them is Po punctuation and falls through to removal below).
#
# RULE M -- major class "M" (Mn, Mc, Me): combining marks.
#   Cited: "word character" includes marks (this matters for text using
#   decomposed combining diacritics rather than precomposed letters; no
#   golden vector currently exercises this, but it is part of the
#   documented rule and is ported for spec fidelity).
_KEEP_MAJOR_CATEGORIES = frozenset({"L", "N", "M"})

# RULE _ -- literal underscore, U+005F.
#   Cited: github-slugger's word-char definition explicitly includes '_'
#   even though its own Unicode general category is "Pc" (Connector
#   Punctuation), which would otherwise be removed by the fallthrough
#   rule. Vector: "snake_case_Heading" -> "snake_case_heading".
#
# RULE - -- literal hyphen, U+002D.
#   Cited: pre-existing hyphens are explicitly allowed through step 2
#   unchanged -- they are not treated as punctuation to strip, and step 3
#   later produces MORE hyphens from spaces, so hyphens must survive
#   step 2 verbatim. Vector: "Multi-Word-Heading" -> "multi-word-heading".
#
# RULE ' ' -- literal space, U+0020.
#   Cited: spaces are explicitly allowed through step 2 -- they are
#   converted to hyphens in step 3, and critically are NOT collapsed in
#   step 2, so a punctuation character flanked by two spaces removes only
#   itself and leaves both spaces intact. Vector: "Foo & Bar" -> "foo--bar"
#   ('&' is Po, removed by the fallthrough rule; both flanking spaces
#   survive and each becomes its own hyphen in step 3).
_KEEP_LITERAL_CHARS = frozenset({"_", "-", " "})

# FALLTHROUGH -- every other general category (P* punctuation, S* symbols
#   including emoji's "So" bucket, Z* separators other than literal space,
#   C* controls/format characters) is REMOVED. Vectors: "Hello, World!" ->
#   "hello-world" (Po ',' and Po '!' removed, no residue); "Foo (Bar) Baz"
#   -> "foo-bar-baz" (Ps '(' and Pe ')' removed); "Great✨News Update" ->
#   "greatnews-update" (So '✨' removed -- see divergence note #1 above).


def _is_kept_char(ch: str) -> bool:
    """STEP 2 classifier: True iff `ch` survives punctuation/emoji removal.

    Consults the RULE TABLE above: first the small set of literal
    exceptions (underscore, hyphen, space), then the Unicode general
    category major class (letter / number / mark). Anything else falls
    through to False (removed).
    """
    if ch in _KEEP_LITERAL_CHARS:
        return True
    return unicodedata.category(ch)[0] in _KEEP_MAJOR_CATEGORIES


def _downcase(text: str) -> str:
    """STEP 1: downcase the heading text.

    Cited: html-pipeline / github-slugger lowercase the whole heading
    before anything else. Vector: "MixEd CasE HEADING" ->
    "mixed-case-heading".
    """
    return text.lower()


def _strip_non_word_chars(lowered: str) -> str:
    """STEP 2: keep only word characters, hyphens, and spaces (RULE TABLE
    above); strip everything else. Deliberately does NOT collapse or
    otherwise normalize whitespace left behind by a stripped character --
    see RULE ' ' above and the "Foo & Bar" -> "foo--bar" vector.
    """
    return "".join(ch for ch in lowered if _is_kept_char(ch))


def _hyphenate_spaces(stripped: str) -> str:
    """STEP 3: replace each remaining literal space with a hyphen,
    one-for-one. A run of N consecutive spaces (surviving from step 2's
    no-collapsing rule) becomes a run of N consecutive hyphens.
    """
    return stripped.replace(" ", "-")


def _base_slug(text: str) -> str:
    """Run the full three-step pipeline (steps 1-3) with no dedup applied."""
    return _hyphenate_spaces(_strip_non_word_chars(_downcase(text)))


def slugify(text: str, seen: dict) -> str:
    """GitHub-style anchor slug for one Markdown heading, per the interface
    contract documented in projects/mdtoc/candidates/vectors.py.

    Pipeline: `_base_slug` (steps 1-3: downcase -> strip non-word/hyphen/
    space chars via the RULE TABLE above -> hyphenate spaces), then a
    NAIVE base-slug -> prior-use-count dedup pass (see divergence note #2
    in the module docstring: this intentionally does not re-check the
    literal suffixed output the way real github-slugger does, matching
    vectors.py's pinned "seen maps base-slug -> count of PRIOR uses"
    contract).

    `seen` is mutated in place: the first heading producing base slug
    "foo" returns "foo" and sets seen["foo"] = 1; the next heading that
    also produces base "foo" returns "foo-1" and sets seen["foo"] = 2;
    and so on.
    """
    base = _base_slug(text)
    prior_uses = seen.get(base, 0)
    slug = base if prior_uses == 0 else f"{base}-{prior_uses}"
    seen[base] = prior_uses + 1
    return slug


def _self_check() -> None:
    """Run this candidate against vectors.py's golden vectors when executed
    directly (`python3 slugger_c.py`). Not part of the shared interface;
    a convenience for local iteration alongside `goal_mode.py`.
    """
    import vectors

    passed, total, failures = vectors.run_against(slugify)
    print(f"slugger_c self-check: {passed}/{total} passed")
    for case, expected, got in failures:
        print(f"  FAIL {case}: expected {expected!r}, got {got!r}")


if __name__ == "__main__":
    _self_check()
