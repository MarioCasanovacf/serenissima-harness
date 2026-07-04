"""mdtoc slug generation -- GitHub-style heading-anchor slugs.

TOURNAMENT-PROMOTED (T-027). This module is the verbatim promotion of tournament
candidate B -- projects/mdtoc/candidates/slugger_b.py (T-025), the unicodedata
category-based implementation -- selected as the winner of the mdtoc slugger
tournament (ORCHESTRATION.md section 5). Candidates were produced under
T-024 (A) / T-025 (B) / T-026 (C) against the shared candidate-agnostic golden
vectors in projects/mdtoc/candidates/vectors.py (T-023).

CONTENDERS:
    A = regex-core                                     (slugger_a.py, T-024)
    B = unicodedata category-based                     (slugger_b.py, T-025)  <-- PROMOTED
    C = github-slugger spec-port + cited rule table    (slugger_c.py, T-026)

SCORE SUMMARY (full table + rationale recorded in the T-027 notes):
  * Golden vectors (vectors.run_against): A 24/24, B 24/24, C 24/24 -- a tie;
    the golden set intentionally does not discriminate the survivors.
  * Decisive axis = fidelity on plausible real-world inputs the golden set
    leaves unpinned (weighted above clarity/brevity per the T-027 brief):
      - NFD combining marks ("cafe"+U+0301, i.e. decomposed "cafe-acute"):
        B and C KEEP the mark (GitHub treats marks as word chars); A strips it
        (Python re \\w excludes category Mn). B, C faithful; A not.
      - Whitespace beyond U+0020 (tab, ideographic space U+3000): B hyphenates
        them via str.isspace() (matching GitHub's whitespace handling); A and C
        (literal-U+0020-only) drop them. B faithful; A, C not.
    B is the ONLY candidate faithful to GitHub on BOTH axes, so B wins.
  * Dedup-collision probe (['Foo','Foo','Foo-1']): all three agree with the
    pinned naive base->count contract (-> ['foo','foo-1','foo-1'], a genuine
    output collision that the contract mandates); non-discriminating.
  * Ranking: 1st B; 2nd C (best documentation / cited rule table, but drops
    tab & U+3000 whitespace); 3rd A (most compact, but silently strips NFD
    combining marks -- a real-data hazard for decomposed input).

The slugify() implementation, its helper functions, and their inline comments
below are copied VERBATIM (functionally) from slugger_b.py. Only this module
docstring is new; candidate B's __main__ self-check block (which imported the
candidates-local vectors.py, NOT part of the mdtoc package, and would raise
ImportError if this file were run standalone) has been dropped. Regression
coverage -- the full golden suite plus the decisive tie-breaker behaviors --
lives in projects/mdtoc/tests/test_slugger.py.

INTERFACE CONTRACT (authoritative statement in vectors.py):

    slugify(text: str, seen: dict) -> str

`seen` maps base-slug -> count of PRIOR uses of that base slug within the current
document and is mutated in place to thread dedup state: the first heading whose
base slug is "foo" returns "foo" and sets seen["foo"] = 1; the next heading with
the same base returns "foo-1" and sets seen["foo"] = 2; and so on. Callers reset
dedup with a fresh `seen = {}` per document.

Python 3.9+, stdlib only (unicodedata).
"""

from __future__ import annotations

import unicodedata

# Categories that are always Unicode "word" characters alongside letters
# (L*) and numbers (N*): the three combining-mark categories.
_WORD_MARK_CATEGORIES = frozenset({"Mn", "Mc", "Me"})

# Literal characters kept verbatim regardless of their Unicode category
# (underscore is a word char per \w; hyphen is explicitly preserved by
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
