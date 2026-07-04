"""mdtoc slugger tournament candidate B (T-025): unicodedata category-based slugify.

Implements the SHARED CANDIDATE INTERFACE defined in
`projects/mdtoc/candidates/vectors.py` (that module is the authoritative
contract; if anything below appears to disagree with an external spec,
vectors.py wins):

    slugify(text: str, seen: dict) -> str

APPROACH (deliberately distinct from a single regex or a ported JS
implementation): walk the downcased input ONE CHARACTER AT A TIME and
classify each character with `unicodedata.category()`, deciding
keep / drop / hyphen purely from that category (plus two literal
passthrough characters, `_` and `-`, and Python's own `str.isspace()`
for whitespace detection). No regular expressions are used for the core
filtering pass.

Classification rules (mirrors GitHub's historical anchor algorithm: strip
everything that is not a Unicode "word" character, a hyphen, or a literal
space; then turn each remaining space into a hyphen):

    1. `text.lower()`                         -- downcase (step 1)
    2. for each character `ch` in the lowered text, in order:
         - `ch.isspace()`                     -> emit '-'   (becomes step 3;
                                                  done in the same pass so
                                                  surrounding whitespace is
                                                  never collapsed away)
         - `ch in ('_', '-')`                 -> emit `ch`  (explicit
                                                  word-char / hyphen keep)
         - `unicodedata.category(ch)` starts
           with 'L' (Lu/Ll/Lt/Lm/Lo, i.e. any
           Unicode letter) or 'N' (Nd/Nl/No,
           i.e. any Unicode number)           -> emit `ch`
         - `unicodedata.category(ch)` is one
           of 'Mn'/'Mc'/'Me' (combining marks
           are Unicode "word" characters too,
           per the \\w definition this
           algorithm reproduces)               -> emit `ch`
         - otherwise (punctuation, symbols,
           separators that are not whitespace,
           control chars, ...)                 -> drop it (emit nothing;
                                                  critically, this does NOT
                                                  emit a hyphen, so adjacent
                                                  whitespace is unaffected --
                                                  see the "Foo & Bar" ->
                                                  "foo--bar" double-hyphen
                                                  golden vector)
    3. join the emitted pieces with no separator -> the base slug

Dedup: `seen` maps base-slug -> count of PRIOR uses within the current
document and is mutated in place (see vectors.py docstring for the exact
contract). The first heading that produces base slug "foo" returns "foo"
and sets seen["foo"] = 1; the next heading with the same base returns
"foo-1" and bumps seen["foo"] = 2; and so on.

Stdlib only (`unicodedata`). Does not import the mdtoc package, vectors.py,
or either sibling candidate.
"""

from __future__ import annotations

import unicodedata

# Categories that are always Unicode "word" characters alongside letters
# (L*) and numbers (N*): the three combining-mark categories.
_WORD_MARK_CATEGORIES = frozenset({"Mn", "Mc", "Me"})

# Literal characters kept verbatim regardless of their Unicode category
# (underscore is a word char per \\w; hyphen is explicitly preserved by
# the GitHub anchor algorithm).
_LITERAL_KEEP = frozenset({"_", "-"})


def _is_word_or_hyphen_char(ch: str) -> bool:
    """True if `ch` should survive the strip pass (step 2 of the algorithm):
    a Unicode letter, a Unicode number, a combining mark, an underscore, or
    a literal hyphen."""
    if ch in _LITERAL_KEEP:
        return True
    category = unicodedata.category(ch)
    if category[0] in ("L", "N"):
        return True
    return category in _WORD_MARK_CATEGORIES


def _slug_base(text: str) -> str:
    """Steps 1-3 of the GitHub anchor algorithm, character-by-character,
    using unicodedata.category() for classification (no regex)."""
    lowered = text.lower()
    pieces = []
    for ch in lowered:
        if ch.isspace():
            # Step 3: each whitespace char becomes exactly one hyphen.
            # Emitted in the same pass (rather than a separate substitution
            # step) so whitespace surrounding a dropped punctuation char is
            # never collapsed -- e.g. "Foo & Bar" -> "foo--bar".
            pieces.append("-")
        elif _is_word_or_hyphen_char(ch):
            # Step 2: keep Unicode word characters and literal hyphens.
            pieces.append(ch)
        # else: step 2 continued -- drop the character entirely (no
        # replacement emitted; this is what prevents punctuation removal
        # from introducing a spurious hyphen).
    return "".join(pieces)


def slugify(text: str, seen: dict) -> str:
    """Return a GitHub-style anchor slug for `text`, deduped against `seen`.

    `seen` is mutated in place per the contract in vectors.py: it maps a
    base slug to the count of prior uses of that base slug. The Nth
    occurrence (N >= 2) of a given base slug returns "base-(N-1)".
    """
    base = _slug_base(text)
    prior_uses = seen.get(base, 0)
    if prior_uses == 0:
        seen[base] = 1
        return base
    seen[base] = prior_uses + 1
    return f"{base}-{prior_uses}"


if __name__ == "__main__":
    import sys

    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    import vectors  # noqa: E402  (candidate-agnostic golden vectors, T-023)

    passed, total, failures = vectors.run_against(slugify)
    print(f"slugger_b self-check: {passed}/{total}")
    for case, expected, got in failures:
        print(f"  FAIL {case}: expected {expected!r}, got {got!r}")
