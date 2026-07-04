#!/usr/bin/env python3
"""AST semantic indexer v0 for the Universal Agent Harness (ZCode parity #3).

Walks the workspace for *.py files, parses each with the stdlib `ast` module,
and emits a symbol -> [{file, line, kind, parent}] map so agents can jump
straight to a definition instead of reading whole files.

Usage examples:
  python3 .harness/bin/ast_index.py build
  python3 .harness/bin/ast_index.py query cmd_claim
  python3 .harness/bin/ast_index.py query lock --contains

Notes:
  - stdlib-only, python3 >= 3.9 (no `match` statements, no 3.10+ syntax).
  - Skips the three external reference-repo clones, .git, __pycache__,
    node_modules, .venv, venv, and .harness/logs + .harness/index (the
    index's own output directory must never be walked into itself).
  - Files that fail to parse (SyntaxError/UnicodeError) are recorded under
    files_skipped and the build continues; a bad file never aborts a build.
  - Top-level functions/classes get kind "function"/"class" with
    parent: null. Functions defined directly inside a class body get
    kind "method" with parent: <class name>.
"""
import argparse
import ast
import os
import sys
import time
from pathlib import Path

import harness_common as hc

INDEX_DIR = hc.HARNESS / "index"
SYMBOLS_PATH = INDEX_DIR / "symbols.json"

SKIP_DIR_NAMES = {
    "harness-optimization-reference",
    "coffee-bench-reference",
    "agentic-harness-engineering-reference",
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
}
# Paths (relative to ROOT, posix-style) pruned in addition to the bare dir names above.
SKIP_REL_PATHS = {
    ".harness/logs",
    ".harness/index",
}


def _rel_posix(path):
    return path.relative_to(hc.ROOT).as_posix()


def _should_prune(dirpath, dirname):
    if dirname in SKIP_DIR_NAMES:
        return True
    rel = _rel_posix(dirpath / dirname)
    return rel in SKIP_REL_PATHS


def _iter_py_files():
    for dirpath_str, dirnames, filenames in os.walk(str(hc.ROOT)):
        dirpath = Path(dirpath_str)
        dirnames[:] = [d for d in dirnames if not _should_prune(dirpath, d)]
        for name in filenames:
            if name.endswith(".py"):
                yield dirpath / name


def _node_line(node):
    # lineno is 1-based in the ast module; guard for nodes without it (shouldn't
    # happen for Function/AsyncFunction/ClassDef, but stay defensive).
    return getattr(node, "lineno", None)


def cmd_build(_args):
    start = time.monotonic()
    files_indexed = []
    files_skipped = []
    symbols = {}
    seen_method_ids = set()

    for path in _iter_py_files():
        rel_path = _rel_posix(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=rel_path)
        except (SyntaxError, UnicodeError, OSError) as exc:
            files_skipped.append({"file": rel_path, "error": "{}: {}".format(type(exc).__name__, exc)})
            continue

        files_indexed.append(rel_path)

        # Pass 1: classes + their direct-body methods. Track each method
        # node's id() so pass 2 (below) never re-emits it as a bare function.
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                symbols.setdefault(node.name, []).append(
                    {"file": rel_path, "line": _node_line(node), "kind": "class", "parent": None}
                )
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.setdefault(child.name, []).append(
                            {"file": rel_path, "line": _node_line(child), "kind": "method", "parent": node.name}
                        )
                        seen_method_ids.add(id(child))

        # Pass 2: everything else (top-level defs and defs nested inside
        # other functions) is indexed as a plain "function" with no parent.
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and id(node) not in seen_method_ids:
                symbols.setdefault(node.name, []).append(
                    {"file": rel_path, "line": _node_line(node), "kind": "function", "parent": None}
                )

    symbol_count = sum(len(v) for v in symbols.values())
    duration_ms = int((time.monotonic() - start) * 1000)

    payload = {
        "built_at": hc.now_iso(),
        "root": str(hc.ROOT),
        "files_indexed": len(files_indexed),
        "files_skipped": files_skipped,
        "symbol_count": symbol_count,
        "symbols": symbols,
    }
    hc.atomic_write_json(SYMBOLS_PATH, payload)
    hc.log_event(
        "index_built",
        files_indexed=len(files_indexed),
        symbol_count=symbol_count,
        duration_ms=duration_ms,
    )
    print(
        "built: {} files indexed, {} skipped, {} symbols, {}ms -> {}".format(
            len(files_indexed), len(files_skipped), symbol_count, duration_ms, SYMBOLS_PATH
        )
    )
    return 0


def cmd_query(args):
    data = hc.read_json(SYMBOLS_PATH)
    if data is None:
        print("error: {} not found. run build first (python3 .harness/bin/ast_index.py build).".format(SYMBOLS_PATH))
        return 2

    symbols = data.get("symbols", {})
    hits = []
    if args.contains:
        needle = args.symbol.lower()
        for name, locations in symbols.items():
            if needle in name.lower():
                for loc in locations:
                    hits.append((name, loc))
    else:
        for loc in symbols.get(args.symbol, []):
            hits.append((args.symbol, loc))

    if not hits:
        print("no hits for '{}'".format(args.symbol))
        return 1

    for name, loc in hits:
        parent = loc.get("parent") or "-"
        print(
            "{}  {}  {}:{}  ({})".format(
                name, loc.get("kind"), loc.get("file"), loc.get("line"), parent
            )
        )
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="walk the workspace and (re)build the symbol index")
    p_build.set_defaults(func=cmd_build)

    p_query = sub.add_parser("query", help="look up a symbol's location(s)")
    p_query.add_argument("symbol")
    p_query.add_argument(
        "--contains", action="store_true", help="case-insensitive substring match instead of exact name"
    )
    p_query.set_defaults(func=cmd_query)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
