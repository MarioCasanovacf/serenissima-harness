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

``python3 -m mdtoc check FILE``
    Recomputes the TOC (at the default ``--max-depth`` of 3) and compares it
    against what is currently between the markers. Exits 0 if the file is
    already fresh (regenerating would be a no-op), exits 1 if it is stale or
    if the markers are missing entirely.

Both commands read/write files with ``newline=""`` so line endings already
present in the file are preserved verbatim rather than translated by
Python's universal-newlines layer -- this is what makes two consecutive
``generate --in-place`` runs byte-for-byte idempotent.
"""
import argparse
import sys

from mdtoc.inserter import insert_toc, render_toc
from mdtoc.parser import parse_headings
from mdtoc.slugger import slugify

DEFAULT_MAX_DEPTH = 3


def _read_text(path):
    """Read `path` as text, preserving original line endings verbatim."""
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _write_text(path, text):
    """Write `text` to `path` verbatim (no newline translation)."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


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

    toc = _render(text, args.max_depth)
    updated = insert_toc(text, toc)

    if updated is None:
        # No markers to splice into: print just the rendered TOC.
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

    toc = _render(text, DEFAULT_MAX_DEPTH)
    updated = insert_toc(text, toc)

    if updated is None:
        print(
            "mdtoc: error: no {} / {} markers found in {!r}".format(
                "<!-- toc -->", "<!-- tocstop -->", args.file
            ),
            file=sys.stderr,
        )
        return 1

    if updated == text:
        print("{}: TOC is up to date".format(args.file))
        return 0

    print(
        "{}: TOC is stale (run `python3 -m mdtoc generate --in-place {}` to update)".format(
            args.file, args.file
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
    check.set_defaults(func=_cmd_check)

    return parser


def main(argv=None):
    """Parse `argv` (defaults to `sys.argv[1:]`) and dispatch. Returns an int exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover - exercised via mdtoc.__main__
    sys.exit(main())
