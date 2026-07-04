"""mdtoc slugger tournament: candidate-agnostic golden test vectors (T-023).

SHARED CANDIDATE INTERFACE (every slugger candidate — T-024/T-025/T-026 — and the
promoted winner in mdtoc/slugger.py — T-027 — MUST implement exactly this):

    slugify(text: str, seen: dict) -> str

    - Returns a GitHub-style anchor slug for a single Markdown heading's text.
    - `seen` maps base-slug -> count of PRIOR uses of that base slug in the current
      document, and is MUTATED in place by the call to thread dedup state across
      an entire document: the first heading that slugifies to base slug "foo"
      returns "foo" and records seen["foo"] = 1; the next heading that ALSO
      slugifies to base "foo" returns "foo-1" and bumps seen["foo"] = 2; the next
      returns "foo-2"; and so on. Callers reset dedup by starting a document with
      seen = {} (or a fresh dict per document group).

This module is CANDIDATE-AGNOSTIC: it imports no candidate implementation. It only
defines the ground-truth golden vectors and a mechanical scoring helper
(`run_against`) so the T-027 verdict task can score any conforming candidate.

GROUND TRUTH SOURCE (cited per-vector below): GitHub's long-standing heading-anchor
algorithm, historically implemented in html-pipeline's `TocFilter#generate_id` and
reproduced by essentially every community slug generator (e.g. the npm package
`github-slugger`), is:

    1. downcase the heading text
    2. strip every character that is not a Unicode "word" character (letter,
       digit, mark, or underscore), a hyphen, or a literal space
    3. replace each remaining space with a hyphen

Two consequences that are easy to get wrong and are therefore covered explicitly
below: (a) step 2 removes punctuation WITHOUT collapsing the whitespace around it,
so a heading like "Foo & Bar" (space, ampersand, space) loses only the "&" and
keeps both spaces, which step 3 turns into a double hyphen ("foo--bar"); and
(b) Unicode letters (accented Latin, CJK, etc.) are word characters and therefore
survive step 2 untouched (and are case-folded by step 1 only if they have case).
"""

from __future__ import annotations

from typing import Callable, List, Tuple

# ---------------------------------------------------------------------------
# SLUG_VECTORS: (input_text, expected_slug) single-shot cases.
# Each is evaluated with a FRESH, EMPTY `seen` dict (no dedup interaction).
# ---------------------------------------------------------------------------
SLUG_VECTORS: List[Tuple[str, str]] = [
    # -- lowercasing + the core space -> hyphen rule --
    ("Hello World", "hello-world"),  # step 1 downcase, step 3 space->hyphen

    # -- punctuation stripped (comma and exclamation point removed, no residue) --
    ("Hello, World!", "hello-world"),  # step 2 strips "," and "!" (not word/hyphen/space)

    # -- punctuation stripped WITHOUT collapsing surrounding whitespace --
    # "&" sits between two spaces; removing only the "&" leaves both spaces,
    # which become two consecutive hyphens. This is the well-known GitHub
    # "double-dash" anchor quirk for ampersands (and any lone symbol flanked
    # by spaces), and it pins down that step 2 must not collapse whitespace.
    ("Foo & Bar", "foo--bar"),

    # -- Unicode letters retained (accented Latin is a Unicode word char) --
    ("Café con leche", "café-con-leche"),  # 'é' (category Ll) is a word char, kept + lowercased

    # -- Unicode letters retained (CJK has no case, both ideographs/kana kept) --
    ("日本語 テスト", "日本語-テスト"),  # category Lo word chars survive step 2; space -> hyphen

    # -- emoji REMOVED entirely (Unicode category So == symbol, not a word char) --
    # No space touches the emoji here, so removal leaves no hyphen residue,
    # isolating "emoji stripped" from the double-hyphen-via-space case above.
    ("Great✨News Update", "greatnews-update"),

    # -- underscores RETAINED (github-slugger treats '_' as a word char) --
    ("snake_case_Heading", "snake_case_heading"),  # underscores kept; letters still lowercased

    # -- existing hyphens preserved verbatim (hyphen is explicitly allowed) --
    ("Multi-Word-Heading", "multi-word-heading"),

    # -- digits retained; '.' stripped as punctuation, no hyphen inserted for it --
    ("Section 2.1 Overview", "section-21-overview"),

    # -- parentheses stripped as punctuation; interior spacing unaffected --
    ("Foo (Bar) Baz", "foo-bar-baz"),

    # -- slug is fully lowercased regardless of input casing --
    ("MixEd CasE HEADING", "mixed-case-heading"),
]

# ---------------------------------------------------------------------------
# DEDUP_SEQUENCES: duplicate-heading dedup threaded through ONE shared `seen`
# dict per sequence (simulates one document's headings processed in order).
# ---------------------------------------------------------------------------
DEDUP_SEQUENCES = [
    {
        # Repeated identical heading: numeric suffix starts at -1 and increments.
        "inputs": ["Setup", "Setup", "Setup"],
        "expected": ["setup", "setup-1", "setup-2"],
    },
    {
        # Unrelated slugs do not share or perturb each other's dedup counters;
        # only a later repeat of the SAME base slug ("Foo" again) bumps.
        "inputs": ["Foo", "Bar", "Foo"],
        "expected": ["foo", "bar", "foo-1"],
    },
    {
        # Dedup keys off the produced (already-lowercased) slug, so headings
        # that differ only by case still collide and dedupe against each other.
        "inputs": ["Config", "CONFIG", "config"],
        "expected": ["config", "config-1", "config-2"],
    },
    {
        # Counter keeps incrementing across many repeats, document-wide.
        "inputs": ["Overview", "Overview", "Overview", "Overview"],
        "expected": ["overview", "overview-1", "overview-2", "overview-3"],
    },
]


def run_against(
    slugify_callable: Callable[[str, dict], str]
) -> Tuple[int, int, List[Tuple[str, str, str]]]:
    """Score `slugify_callable` against every golden vector in this module.

    `slugify_callable` must conform to the shared interface documented at the
    top of this module: `slugify(text: str, seen: dict) -> str`.

    Evaluates every entry of SLUG_VECTORS with a fresh, empty `seen` dict (no
    cross-case dedup interaction), then evaluates every entry of
    DEDUP_SEQUENCES with ONE shared `seen` dict per sequence (threaded across
    that sequence's inputs, in order, to exercise document-wide dedup).

    Imports NO candidate module: the caller supplies the callable.

    Returns:
        (passed, total, failures) where `failures` is a list of
        (case_description, expected, got) for every mismatch.
    """
    passed = 0
    total = 0
    failures: List[Tuple[str, str, str]] = []

    for input_text, expected in SLUG_VECTORS:
        total += 1
        seen: dict = {}
        got = slugify_callable(input_text, seen)
        case = f"SLUG_VECTORS: slugify({input_text!r}, {{}})"
        if got == expected:
            passed += 1
        else:
            failures.append((case, expected, got))

    for seq_index, seq in enumerate(DEDUP_SEQUENCES):
        seen = {}
        inputs = seq["inputs"]
        expected_list = seq["expected"]
        for i, (input_text, expected) in enumerate(zip(inputs, expected_list)):
            total += 1
            got = slugify_callable(input_text, seen)
            case = (
                f"DEDUP_SEQUENCES[{seq_index}][{i}]: "
                f"slugify({input_text!r}, seen) after prior inputs {inputs[:i]!r}"
            )
            if got == expected:
                passed += 1
            else:
                failures.append((case, expected, got))

    return passed, total, failures


def _self_check() -> None:
    """Structural self-test: no candidate is imported, so this only validates
    the shape of the golden data itself (not any slugify implementation)."""
    assert len(SLUG_VECTORS) > 0, "SLUG_VECTORS must not be empty"
    assert len(DEDUP_SEQUENCES) > 0, "DEDUP_SEQUENCES must not be empty"
    for input_text, expected_slug in SLUG_VECTORS:
        assert isinstance(input_text, str) and isinstance(expected_slug, str)
    dedup_case_count = 0
    for seq in DEDUP_SEQUENCES:
        assert len(seq["inputs"]) == len(seq["expected"]), (
            "DEDUP_SEQUENCES inputs/expected length mismatch: %r" % (seq,)
        )
        dedup_case_count += len(seq["inputs"])

    total_vectors = len(SLUG_VECTORS) + dedup_case_count
    print("mdtoc slugger golden vectors (T-023) -- self-check OK")
    print(f"  SLUG_VECTORS (single-shot):      {len(SLUG_VECTORS)}")
    print(f"  DEDUP_SEQUENCES (sequences):     {len(DEDUP_SEQUENCES)}")
    print(f"  DEDUP_SEQUENCES (total cases):   {dedup_case_count}")
    print(f"  TOTAL golden cases (for a candidate's run_against score): {total_vectors}")


if __name__ == "__main__":
    _self_check()
