"""mdtoc: a Markdown Table-of-Contents generator (Python 3.9+ stdlib only).

This file is what turns ``projects/mdtoc/mdtoc/`` from a PEP-420 namespace
package into a regular package (T-028). Every other mdtoc module
(``parser.py``, ``inserter.py``, ``slugger.py``) was authored earlier in the
DAG (T-021/T-022/T-027) against the namespace-package form, so this marker
is intentionally the LAST piece wired in -- adding it does not change how any
of those modules import or run.

Public API (re-exported for convenience; each name is owned by its source
module -- see the module docstring there for the authoritative contract):

    mdtoc.parser.parse_headings   -- ATX heading extraction   (T-021)
    mdtoc.inserter.render_toc     -- nested TOC rendering      (T-022)
    mdtoc.inserter.insert_toc     -- idempotent marker splice  (T-022)
    mdtoc.slugger.slugify         -- GitHub-style anchor slugs (T-027, tournament-promoted)
    mdtoc.cli.main                -- `python3 -m mdtoc ...` entry point (T-028)

Run the CLI with:

    python3 -m mdtoc generate FILE [--max-depth N] [--in-place]
    python3 -m mdtoc check FILE

See ``mdtoc.cli`` for the full command contract and ``projects/mdtoc/README.md``
for usage examples.
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
