"""mdtoc CLI (T-028): argparse ``generate`` / ``check`` commands.

Wires the three independently-developed mdtoc modules into one pipeline,
without modifying any of them:

    mdtoc.parser.parse_headings(text)               (T-021)
        -> mdtoc.inserter.render_toc(headings, mdtoc.slugger.slugify, max_depth)
                                                       (T-022 render, T-027 slug)
        -> mdtoc.inserter.insert_toc(text, toc)      (T-022)

``mdtoc.slugger.slugify`` is passed into ``render_toc`` as the injected
callable that ``inserter.py`` expects (signature ``slugify(text, seen)``);
this module is the only place in the package that imports all three at once.

Commands
--------
``python3 -m mdtoc generate FILE [--max-depth N] [--in-place]``
    Default ``--max-depth`` is 3. If the TOC markers (``<!-- toc -->`` /
    ``<!-- tocstop -->``) are present in FILE, the TOC between them is
    (re)inserted idempotently: with ``--in-place`` the file is rewritten on
    disk, otherwise the full updated document is printed to stdout and the
    file is left untouched. If the markers are ABSENT, there is nothing to
    splice into, so just the rendered TOC body is printed to stdout
    (``--in-place`` has no effect in that case, and a warning is emitted on
    stderr if it was passed).

    The depth used is always recorded on the start marker itself, as an
    HTML-comment parameter (T-038/P-012): ``<!-- toc max-depth=N -->``. This
    is written EXPLICITLY every time, including at the default depth of 3
    (``<!-- toc max-depth=3 -->``), rather than left parameterless -- see
    ``_marker_with_depth`` for the rationale. This is what lets ``check``
    (below) recompute at the depth the file was actually generated with,
    instead of hardcoding a depth and reporting false-stale.

``python3 -m mdtoc check FILE [--max-depth N]``
    Recomputes the TOC and compares it against what is currently between the
    markers. The depth used, in priority order, is: (1) ``--max-depth`` if
    given explicitly on the command line, (2) the ``max-depth=N`` parameter
    already recorded on the file's start marker, (3) the legacy default of 3
    if the marker carries no parameter at all (pre-T-038 files / fixtures
    that still use the bare ``<!-- toc -->`` marker). Exits 0 if the file is
    already fresh (regenerating at that same resolved depth would be a
    no-op), exits 1 if it is stale or if the markers are missing entirely.

Both commands read/write files with ``newline=""`` so line endings already
present in the file are preserved verbatim rather than translated by
Python's universal-newlines layer -- this is what makes two consecutive
``generate --in-place`` runs (with the same ``--max-depth``) byte-for-byte
idempotent, including the recorded ``max-depth=N`` marker parameter.
"""
import argparse
import re
import sys

from mdtoc.inserter import TOC_START_MARKER, insert_toc, render_toc
from mdtoc.parser import parse_headings
from mdtoc.slugger import slugify

DEFAULT_MAX_DEPTH = 3

# Matches the TOC start marker with an OPTIONAL "max-depth=N" parameter:
#   <!-- toc -->                  (legacy / parameterless -> group("depth") is None)
#   <!-- toc max-depth=2 -->      (T-038 parameterized form)
# `TOC_START_MARKER` ("<!-- toc -->") is imported from inserter.py rather
# than re-declared, so the literal stays a single source of truth even
# though inserter.py itself is not ours to modify.
_MARKER_START_RE = re.compile(
    r"<!-- toc(?: max-depth=(?P<depth>\d+))? -->"
)


def _read_text(path):
    """Read `path` as text, preserving original line endings verbatim."""
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _write_text(path, text):
    """Write `text` to `path` verbatim (no newline translation)."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _marker_with_depth(max_depth):
    """Render the start marker with its max-depth parameter embedded.

    DECISION (T-038/P-012): the parameter is written EXPLICITLY on every
    ``generate``, even at the default depth of 3, rather than only writing
    it when it differs from the default. A parameterless marker is
    ambiguous (does the file predate this feature, or was it generated at
    the default on purpose?), whereas an explicit ``max-depth=3`` is
    self-documenting and makes `check`'s "legacy fallback to 3" path apply
    ONLY to genuinely pre-T-038 files, never to freshly generated ones.
    """
    return "<!-- toc max-depth={} -->".format(max_depth)


def _normalize_start_marker(text):
    """Rewrite the start marker (with or without a max-depth param) back to
    the bare ``TOC_START_MARKER`` literal that ``inserter.insert_toc`` (not
    ours to modify) searches for verbatim, and report the depth that was
    parsed off of it (``None`` if the marker was absent or parameterless).

    Returns
    -------
    (normalized_text, existing_depth, original_marker_text) :
    (str, int | None, str | None)
        ``normalized_text`` is byte-identical to ``text`` everywhere except
        the start-marker span itself, so ``insert_toc`` continues to locate
        the surrounding document text (before/after the markers) untouched.
        ``original_marker_text`` is the exact marker substring as found on
        disk (``None`` if no start marker was present at all) -- callers
        that need to compare against the ORIGINAL bytes (``check``) restore
        this verbatim rather than fabricating a new parameter value.
    """
    match = _MARKER_START_RE.search(text)
    if match is None:
        return text, None, None
    existing_depth = int(match.group("depth")) if match.group("depth") else None
    original_marker_text = match.group(0)
    normalized = text[: match.start()] + TOC_START_MARKER + text[match.end() :]
    return normalized, existing_depth, original_marker_text


def _rewrite_marker_param(text, max_depth):
    """Replace the (bare, post-`insert_toc`) start marker with the
    parameterized form recording `max_depth`. Only the FIRST occurrence is
    replaced -- that is always the start marker, since `TOC_STOP_MARKER`
    ("<!-- tocstop -->") is never a substring match for `TOC_START_MARKER`
    ("<!-- toc -->", note the space before "-->").
    """
    return text.replace(TOC_START_MARKER, _marker_with_depth(max_depth), 1)


def _render(text, max_depth):
    """Run the parser -> slugger -> render_toc pipeline on `text`."""
    headings = parse_headings(text)
    return render_toc(headings, slugify, max_depth=max_depth)


def _cmd_generate(args):
    try:
        text = _read_text(args.file)
    except OSError as exc:
        print("mdtoc: error: {}".format(exc), file=sys.stderr)
        return 2

    # Normalize any existing (bare or already-parameterized) start marker
    # back to the literal `insert_toc` searches for, so re-generating a
    # file that already carries a `max-depth=N` param from a prior run
    # still locates the markers (T-038: `insert_toc` itself is not ours to
    # change, and it only ever looks for the bare marker literal).
    normalized_text, _existing_depth, _original_marker = _normalize_start_marker(text)

    toc = _render(normalized_text, args.max_depth)
    updated = insert_toc(normalized_text, toc)

    if updated is None:
        # No markers to splice into: print just the rendered TOC. There is
        # nowhere to record a max-depth parameter in this mode.
        if args.in_place:
            print(
                "mdtoc: warning: no {} / {} markers found in {!r}; "
                "--in-place has no effect, printing TOC to stdout instead".format(
                    "<!-- toc -->", "<!-- tocstop -->", args.file
                ),
                file=sys.stderr,
            )
        print(toc)
        return 0

    updated = _rewrite_marker_param(updated, args.max_depth)

    if args.in_place:
        try:
            _write_text(args.file, updated)
        except OSError as exc:
            print("mdtoc: error: {}".format(exc), file=sys.stderr)
            return 2
        return 0

    sys.stdout.write(updated)
    return 0


def _cmd_check(args):
    try:
        text = _read_text(args.file)
    except OSError as exc:
        print("mdtoc: error: {}".format(exc), file=sys.stderr)
        return 2

    normalized_text, existing_depth, original_marker = _normalize_start_marker(text)

    # Depth resolution priority (T-038/P-012): explicit --max-depth override
    # > the max-depth recorded on the file's own marker > legacy default 3
    # (bare/parameterless marker, e.g. pre-T-038 files and fixtures).
    if args.max_depth is not None:
        depth = args.max_depth
    elif existing_depth is not None:
        depth = existing_depth
    else:
        depth = DEFAULT_MAX_DEPTH

    toc = _render(normalized_text, depth)
    updated = insert_toc(normalized_text, toc)

    if updated is None:
        print(
            "mdtoc: error: no {} / {} markers found in {!r}".format(
                "<!-- toc -->", "<!-- tocstop -->", args.file
            ),
            file=sys.stderr,
        )
        return 1

    # `check` never PERSISTS a new max-depth parameter (only `generate`
    # does) -- it restores the marker EXACTLY as found on disk (bare or
    # parameterized, whatever `original_marker` was) before comparing, so
    # freshness is judged purely on the TOC body content at the resolved
    # `depth`, never on rewriting the marker's recorded parameter. This is
    # what lets a legacy parameterless marker whose body already matches a
    # depth-3 render report fresh (exit 0) rather than false-stale merely
    # because `check` would otherwise "helpfully" add a parameter that
    # wasn't there before.
    updated = updated.replace(TOC_START_MARKER, original_marker, 1)

    if updated == text:
        print("{}: TOC is up to date (max-depth={})".format(args.file, depth))
        return 0

    print(
        "{}: TOC is stale at max-depth={} (run `python3 -m mdtoc generate "
        "--max-depth {} --in-place {}` to update)".format(
            args.file, depth, depth, args.file
        )
    )
    return 1


def build_parser():
    """Construct the top-level argparse parser (also used for --help)."""
    parser = argparse.ArgumentParser(
        prog="mdtoc",
        description="Generate and verify Markdown Tables of Contents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate",
        help="Generate/update the TOC for a Markdown file.",
        description=(
            "Parse headings in FILE, render a nested TOC, and splice it "
            "between the '<!-- toc -->' / '<!-- tocstop -->' markers. If "
            "the markers are absent, print just the rendered TOC instead."
        ),
    )
    generate.add_argument("file", metavar="FILE", help="Path to the Markdown file.")
    generate.add_argument(
        "--max-depth",
        type=int,
        default=DEFAULT_MAX_DEPTH,
        metavar="N",
        help="Maximum heading level to include in the TOC (default: %(default)s).",
    )
    generate.add_argument(
        "--in-place",
        action="store_true",
        help="Rewrite FILE on disk instead of printing the updated document to stdout.",
    )
    generate.set_defaults(func=_cmd_generate)

    check = subparsers.add_parser(
        "check",
        help="Check whether FILE's TOC is up to date.",
        description=(
            "Recompute the TOC for FILE and compare it against the content "
            "currently between the markers. Exit 0 if fresh, 1 if stale or "
            "if the markers are missing."
        ),
    )
    check.add_argument("file", metavar="FILE", help="Path to the Markdown file.")
    check.add_argument(
        "--max-depth",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Override the max-depth used to recompute the TOC; wins over "
            "the max-depth recorded on the file's own marker (default: use "
            "the marker's max-depth, or {} if the marker carries none).".format(
                DEFAULT_MAX_DEPTH
            )
        ),
    )
    check.set_defaults(func=_cmd_check)

    return parser


def main(argv=None):
    """Parse `argv` (defaults to `sys.argv[1:]`) and dispatch. Returns an int exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover - exercised via mdtoc.__main__
    sys.exit(main())
