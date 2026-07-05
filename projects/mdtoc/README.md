# mdtoc

A small, dependency-free Markdown Table-of-Contents generator: parse ATX
headings, render a nested TOC with GitHub-style anchor slugs, and splice it
idempotently between two HTML-comment markers. Python 3.9+, standard library
only (no `pip install` required).

## Package layout

```
projects/mdtoc/
├── mdtoc/
│   ├── __init__.py    # package marker + public API summary   (T-028)
│   ├── __main__.py    # `python3 -m mdtoc ...` entry point     (T-028)
│   ├── cli.py         # argparse generate/check commands       (T-028)
│   ├── parser.py      # ATX heading extraction                 (T-021)
│   ├── inserter.py    # TOC rendering + marker splicing        (T-022)
│   └── slugger.py     # GitHub-style anchor slugs (tournament-promoted) (T-027)
├── tests/
│   ├── test_parser.py
│   ├── test_inserter.py
│   ├── test_slugger.py
│   ├── test_cli.py            # unit tests, call `cli.main()` in-process
│   ├── test_integration.py    # end-to-end, shells out to `python3 -m mdtoc`
│   └── fixtures/sample.md     # exercises fences, comments, dup + unicode headings
└── README.md
```

## Running the CLI

`mdtoc` is a regular package with no third-party dependencies, so there is
nothing to install. Python just needs `mdtoc`'s **parent directory**
(`projects/mdtoc/`) on `sys.path`. Either of the following is equivalent:

**Option A — run with `cwd` set to `projects/mdtoc/`:**

```bash
cd projects/mdtoc
python3 -m mdtoc --help
```

**Option B — run from the repo root with `PYTHONPATH`:**

```bash
PYTHONPATH=projects/mdtoc python3 -m mdtoc --help
```

Every example below uses Option B (repo-root-relative paths); swap in
Option A if you prefer to `cd` into `projects/mdtoc/` first.

### `generate` — build/update the TOC

```
python3 -m mdtoc generate FILE [--max-depth N] [--in-place]
```

- `FILE` is the Markdown file to read.
- `--max-depth N` (default `3`) — only headings at level `<= N` are included.
- `--in-place` — rewrite `FILE` on disk. Without it, the result is printed
  to stdout and `FILE` is left untouched (a dry run / pipeable preview).

The TOC is spliced between two marker comments that must already exist
somewhere in the file:

```markdown
<!-- toc -->
<!-- tocstop -->
```

**If the markers are present**, the content strictly between them is
replaced (idempotently — running `generate` twice in a row with the same
`--max-depth` produces a byte-identical result):

```bash
# Preview to stdout, file untouched:
PYTHONPATH=projects/mdtoc python3 -m mdtoc generate README_with_markers.md

# Write the update back to the file:
PYTHONPATH=projects/mdtoc python3 -m mdtoc generate README_with_markers.md --in-place

# Only include H1/H2 in the TOC:
PYTHONPATH=projects/mdtoc python3 -m mdtoc generate README_with_markers.md --max-depth 2 --in-place
```

**The depth is recorded on the start marker itself** (T-038/P-012), as an
HTML-comment parameter: `generate` always rewrites the start marker to
`<!-- toc max-depth=N -->`, explicitly, even at the default depth of 3
(`<!-- toc max-depth=3 -->`) — never left parameterless. This is what lets
`check` (below) recompute the TOC at the depth the file was *actually*
generated with, instead of assuming a fixed depth and reporting a false
"stale" result for files generated at a non-default `--max-depth`.

**If the markers are absent**, there is nothing to splice into, so just the
rendered TOC body is printed to stdout (handy for copy-pasting into a new
document):

```bash
PYTHONPATH=projects/mdtoc python3 -m mdtoc generate some_doc_without_markers.md
# ->
# - [Title](#title)
#   - [Section One](#section-one)
#   - [Section Two](#section-two)
```

### `check` — verify the TOC is up to date

```
python3 -m mdtoc check FILE [--max-depth N]
```

Recomputes the TOC and compares it against what is currently between the
markers. The depth used to recompute is resolved in this priority order
(T-038/P-012):

1. `--max-depth N` on the command line, if given — always wins.
2. The `max-depth=N` parameter already recorded on the file's own start
   marker (see the `generate` section above), if present.
3. The legacy default of `3`, if the start marker carries no parameter at
   all — this is the fallback for pre-T-038 files (checked-in fixtures or
   real files in the wild that predate this feature and still use the bare
   `<!-- toc -->` marker), so they keep working unmodified.

`check` never rewrites the marker's recorded parameter itself (only
`generate` does that) — it only judges whether the TOC *body* is fresh at
the resolved depth.

- **Exit 0** — the TOC is fresh (regenerating at the resolved depth would be
  a no-op). Useful as a CI / pre-commit gate: `mdtoc check docs/README.md ||
  exit 1`.
- **Exit 1** — the TOC is stale (someone edited headings, or the resolved
  depth disagrees with what's on disk, without regenerating), or the
  markers are missing entirely.

```bash
PYTHONPATH=projects/mdtoc python3 -m mdtoc check README_with_markers.md
echo "exit code: $?"

# Override the depth check recomputes at, regardless of the marker's own
# recorded max-depth or the legacy default:
PYTHONPATH=projects/mdtoc python3 -m mdtoc check README_with_markers.md --max-depth 2
```

### `--help`

Both the top-level program and each subcommand have clean argparse help:

```bash
PYTHONPATH=projects/mdtoc python3 -m mdtoc --help
PYTHONPATH=projects/mdtoc python3 -m mdtoc generate --help
PYTHONPATH=projects/mdtoc python3 -m mdtoc check --help
```

## Worked example

Given `projects/mdtoc/tests/fixtures/sample.md` (which already contains
`<!-- toc -->` / `<!-- tocstop -->` markers, a fenced code block with a
commented-out `#` line, an HTML comment with a `#` line, a duplicated
`## Café` heading, and a `## 你好世界` (CJK) heading):

```bash
cp projects/mdtoc/tests/fixtures/sample.md /tmp/sample.md
PYTHONPATH=projects/mdtoc python3 -m mdtoc generate /tmp/sample.md --in-place
PYTHONPATH=projects/mdtoc python3 -m mdtoc check /tmp/sample.md   # -> exit 0
```

produces a TOC block equivalent to:

```markdown
<!-- toc max-depth=3 -->
- [Sample Document](#sample-document)
  - [Introduction](#introduction)
  - [Café](#café)
  - [Café](#café-1)
  - [你好世界](#你好世界)
    - [Nested Section](#nested-section)
  - [Conclusion](#conclusion)
<!-- tocstop -->
```

Notice the start marker now carries `max-depth=3` explicitly (T-038/P-012)
— that's what `check` reads back to recompute at the right depth.

Notice:
- The `#` lines inside the fenced code block and the HTML comment never
  appear in the TOC (the parser correctly ignores both).
- The second `## Café` heading is deduped to anchor `#café-1` (a third
  duplicate would get `#café-2`, and so on).
- The CJK heading `你好世界` gets a Unicode-preserving anchor rather than
  being stripped or transliterated.
- `#### Too Deep` (level 4) is excluded at the default `--max-depth 3`.

## Running the tests

```bash
python3 -m unittest discover -s projects/mdtoc/tests -t projects/mdtoc -v
```

This runs every mdtoc suite (parser, inserter, slugger, CLI unit tests, and
the subprocess-based end-to-end integration test) in one command, entirely
with the Python 3.9+ standard library.
