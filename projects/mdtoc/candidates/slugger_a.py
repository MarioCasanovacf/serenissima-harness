"""mdtoc slugger candidate A (T-024): REGEX-based GitHub-style slugify.

Tournament context: this is ONE of three independently-implemented candidates
(A = this file / regex, B = unicodedata category-based, C = github-slugger
spec port) competing under T-024/T-025/T-026. T-027 scores all three against
the shared golden vectors in `vectors.py` and promotes exactly one winner into
mdtoc/slugger.py. This module owns EXACTLY projects/mdtoc/candidates/slugger_a.py
and touches nothing else; it imports no candidate module and no mdtoc package
code, per the disjoint-ownership convention shared by all mdtoc tasks.

INTERFACE CONTRACT (see vectors.py's module docstring for the authoritative
statement; this file's behavior is derived directly from it and vectors.py
wins over any external spec if they ever disagree):

    slugify(text: str, seen: dict) -> str

    - Returns a GitHub-style anchor slug for a single Markdown heading's text.
    - `seen` maps base-slug -> count of PRIOR uses of that base slug in the
      current document and is MUTATED in place: the first heading whose base
      slug is "foo" returns "foo" and sets seen["foo"] = 1; the next heading
      with the same base returns "foo-1" and sets seen["foo"] = 2; the next
      returns "foo-2"; and so on. Callers reset dedup with a fresh `seen = {}`
      per document.

APPROACH -- REGEX-BASED:
    1. Downcase the heading text (str.lower(); Python's lower() is Unicode-aware
       so accented Latin, etc. case-fold correctly, and CJK/other caseless
       scripts pass through unchanged).
    2. Strip every character that is not a Unicode "word" character (letter,
       digit, or underscore -- Python's `re` module's `\\w` is Unicode-aware
       by default for `str` patterns, matching category L*, Nd, and `_`), a
       literal hyphen, or a literal space, using ONE compiled regex
       (`_STRIP_RE = re.compile(r"[^\\w \\-]")`) and `_STRIP_RE.sub("", text)`.
       This deliberately does NOT collapse surrounding whitespace when a
       punctuation character is removed, which reproduces GitHub's documented
       double-hyphen quirk for symbols flanked by spaces (e.g. "Foo & Bar" ->
       "foo--bar": the "&" is deleted but both spaces around it survive step 2
       untouched).
    3. Replace each remaining space character with a hyphen via a second
       compiled regex (`_SPACE_RE = re.compile(" ")`) and `_SPACE_RE.sub("-",
       text)`, one-for-one (no collapsing), preserving the double-hyphen
       artifact from step 2.
    4. Dedup: look up the base slug produced by steps 1-3 in `seen`. If it is
       new, record `seen[base] = 1` and return `base`. If it has been seen
       `n` times before (`seen[base] == n`), return `f"{base}-{n}"` and bump
       `seen[base] = n + 1`. This is the naive base -> running-count scheme
       that vectors.py's DEDUP_SEQUENCES pins down exactly (no attempt to
       avoid accidental collisions with a heading that is itself literally
       "foo-1"; that refinement is out of scope for this candidate and for
       the golden vectors).

Stdlib only: this module imports only `re` from the standard library. It does
not import `unicodedata`, the `mdtoc` package, or either sibling candidate.
"""

from __future__ import annotations

import re

# Compiled once at module import time (re-used across all slugify() calls).
#
# `\w` in Python's `re` module is Unicode-aware by default for `str` patterns
# (no re.ASCII flag is set here), so it matches Unicode letters (any case),
# decimal digits, and the underscore -- exactly the "word character" set
# vectors.py's ground-truth description calls for, plus the underscore that
# GitHub's algorithm also retains. Anything NOT in {word char, space, hyphen}
# is deleted.
_STRIP_RE = re.compile(r"[^\w \-]", re.UNICODE)

# Literal space -> hyphen, one character at a time (no whitespace collapsing).
_SPACE_RE = re.compile(" ")


def _base_slug(text: str) -> str:
    """Steps 1-3 of the algorithm: downcase, strip, space->hyphen."""
    lowered = text.lower()
    stripped = _STRIP_RE.sub("", lowered)
    return _SPACE_RE.sub("-", stripped)


def slugify(text: str, seen: dict) -> str:
    """Return the GitHub-style anchor slug for `text`, deduped via `seen`.

    `seen` is mutated in place: maps base-slug -> count of prior uses. See the
    module docstring / vectors.py for the exact dedup contract.
    """
    base = _base_slug(text)

    prior_count = seen.get(base, 0)
    if prior_count == 0:
        seen[base] = 1
        return base

    seen[base] = prior_count + 1
    return f"{base}-{prior_count}"
