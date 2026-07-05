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
  * Dedup-collision probe (['Foo','Foo','Foo-1']): all three agreed at
    tournament time with the then-pinned naive base->count contract
    (-> ['foo','foo-1','foo-1'], a genuine output collision); non-
    discriminating for the T-027 verdict.
    UPDATED by T-039/P-013 (post-tournament hardening, see DEDUP RULE
    TABLE below): the naive contract's output collision was accepted as
    a known flaw, not a feature, so this module now implements
    github-slugger's richer produced-slug registration instead. The
    probe's expected output changed from ['foo','foo-1','foo-1'] to
    ['foo','foo-1','foo-1-1'] (no collision). This does not reopen the
    B-vs-A-vs-C tournament verdict above, which stands on the NFD/
    whitespace axes; it only replaces the naive dedup tail-piece every
    candidate shared.
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

`seen` is mutated in place to thread dedup state across a document; callers
reset dedup with a fresh `seen = {}` per document. Its SHAPE is unchanged by
T-039/P-013 (still a plain str -> int dict, mutated in place by `slugify`) --
only WHAT gets registered into it changed, per the rule table below.

-----------------------------------------------------------------------
DEDUP RULE TABLE (github-slugger produced-slug registration, T-039/P-013)
-----------------------------------------------------------------------
Cited upstream source: the npm package `github-slugger`'s
`slugger.prototype.slug` (its JS `BananaSlug.prototype.slug`), which keeps
a per-document `this.occurrences` map and re-registers into it as follows
(paraphrased from the upstream implementation):

    slug = originalSlug = <computed base slug>
    while (originalSlug in occurrences):
        occurrences[originalSlug] += 1
        slug = originalSlug + '-' + occurrences[originalSlug]
    occurrences[slug] = 0
    return slug

RULE 1 -- BUMP the base slug's own counter on every repeat.
    Cited: upstream keeps one integer counter per distinct BASE string
    (`occurrences[originalSlug]`), incremented each time that same base
    is seen again, and uses the post-increment value as the numeric
    suffix. Vector: ["Setup","Setup","Setup"] -> ["setup","setup-1",
    "setup-2"] (DEDUP_SEQUENCES[0] in vectors.py).

RULE 2 -- RE-REGISTER the FINAL, PRODUCED slug too, not just the base.
    Cited: upstream's last line, `occurrences[slug] = 0`, registers the
    (possibly already-suffixed) string it is about to RETURN as its own
    key -- not merely the original base. This is the fix this module
    adopts under T-039/P-013: previously only the base was registered
    (a "naive base->count" scheme -- see candidates/slugger_c.py's
    divergence note #2, which documents that naive scheme and the exact
    collision it produces). Registering the produced slug closes that
    gap: a LATER heading whose base happens to equal an EARLIER
    PRODUCED slug is detected as already-taken (via RULE 1's bump loop)
    instead of silently colliding.
    Regression vector (T-039/P-013, projects/mdtoc/tests/test_slugger.py):
    ["Foo", "Foo", "Foo-1"] -- naive base-counting (the pre-T-039
    behavior) emits ["foo", "foo-1", "foo-1"], a genuine anchor
    collision (the second "Foo" and the literal "Foo-1" heading both
    produce "foo-1"). With RULE 2 applied, the third call's base
    "foo-1" is found already registered (by the second call's RULE-2
    registration), so it is bumped again to "foo-1-1":
    ["foo", "foo-1", "foo-1-1"] -- unique.

RULE 3 -- the golden vectors in vectors.py (DEDUP_SEQUENCES) contain NO
    produced-slug collisions, so RULE 1 alone fully explains their
    expected outputs; RULE 2 is purely additive and does not change any
    golden-vector result (verified: vectors.run_against stays 24/24
    before and after this change).

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

    Implements the DEDUP RULE TABLE in this module's docstring (T-039/P-013,
    porting github-slugger's `slugger.prototype.slug` occurrence bookkeeping):
    compute the base slug, then while that candidate string is already a key
    in `seen` (RULE 1: base collisions; RULE 2: PRODUCED-slug collisions --
    `seen` holds both), bump the base's counter and retry with the next
    numeric suffix. Once a free candidate is found, register it too (RULE 2)
    before returning it, so a LATER base equal to an EARLIER produced slug
    is caught instead of silently colliding.

    `seen` is mutated in place; its shape is unchanged from before T-039
    (still a plain str -> int dict) -- only what gets registered changed.
    """
    base = _slug_base(text)
    slug = base
    while slug in seen:
        seen[base] = seen.get(base, 0) + 1
        slug = f"{base}-{seen[base]}"
    seen[slug] = 0
    return slug
