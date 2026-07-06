#!/usr/bin/env python3
"""Claude Code hook (PreToolUse on Bash).

Denies a Bash command ONLY when it looks destructive (remove/move/shred/
truncate verb, or a shell redirect `>`/`>>`) AND its resolved target path
matches one of the operator-configured globs in `state.json protected_paths`.

This is P-029 (audit_t303_protected_paths.md mutation section), a generic,
default-empty, opt-in guardrail: with `protected_paths: []` (the shipped
default) this hook is a strict no-op that returns fast without touching the
command at all. It exists to close an observability gap: an OUTER guard
(e.g. an operator's machine-level command guard) can silently deny a
destructive command with zero trace in this harness's own logs, because a
PreToolUse deny suppresses the PostToolUse hook that fills
transcript.jsonl. This hook makes an INNER deny observable by logging a
`protected_path_blocked` event to events.jsonl on every block.

Scope: Bash tool calls only (other tools are out of scope for this hook;
Edit/Write/etc. go through check_lock.py). Matching is heuristic (regex
extraction of verb arguments and redirect targets, not a full shell
parser) — intentionally conservative in what it recognizes as destructive
(rm|mv|shred|truncate + redirects) so it stays predictable, matching the
class of commands audited in audit_t303_protected_paths.md §A.2.

Fail-open: on any internal error, or when protected_paths is empty/absent,
or when no target matches, the command is allowed (exit 0). Blocking
protocol: exit code 2 with the reason on stderr, same convention as
check_lock.py, so Claude Code feeds the reason back to the model.
"""
import fnmatch
import json
import re
import shlex
import sys
from pathlib import Path

DESTRUCTIVE_VERB_RE = re.compile(
    r"(?:^|[;&|]|\s)(?:\S*/)?(rm|mv|shred|truncate)\s+([^;&|\n]+)"
)
REDIRECT_RE = re.compile(r">>?\s*([^\s;&|]+)")


def _extract_targets(command):
    """Best-effort extraction of candidate target paths from a Bash command
    string: arguments to a destructive verb (skipping flags), plus the
    target of any `>`/`>>` redirect. Heuristic, not a full shell parser —
    mirrors the scope of the Portfolio source pattern this generalizes.
    Uses shlex so quoted paths containing spaces stay one token; falls back
    to a naive whitespace split if shlex chokes on unbalanced quoting."""
    targets = []
    for m in DESTRUCTIVE_VERB_RE.finditer(command):
        args_str = m.group(2)
        try:
            toks = shlex.split(args_str)
        except ValueError:
            toks = args_str.split()
        for tok in toks:
            if not tok or tok.startswith("-"):
                continue
            targets.append(tok)
    for m in REDIRECT_RE.finditer(command):
        tok = m.group(1).strip("'\"")
        if tok:
            targets.append(tok)
    return targets


def _target_matches(target, protected_globs, root):
    """Return (matched: bool, glob: str|None). Tries the target both as
    given and resolved+made-relative-to the workspace root, so globs in
    state.json (written relative to the repo root) match absolute-looking
    command arguments too.

    A glob of the form `<prefix>/**` is meant to protect an entire
    directory tree, including the directory itself: `rm -rf dir` (no
    trailing segment) deletes everything the glob was written to protect,
    but `fnmatch("dir", "dir/**")` is False under plain fnmatch semantics
    (the pattern requires at least one path segment after the slash). So
    in addition to the raw fnmatch, also match the bare prefix and the
    prefix-with-trailing-slash directly. Candidates are normalized by
    stripping a trailing slash first so `dir/` and `dir` behave alike."""
    raw_candidates = [target]
    try:
        p = Path(target)
        if not p.is_absolute():
            p = root / p
        resolved = p.resolve()
        try:
            raw_candidates.append(str(resolved.relative_to(root)))
        except ValueError:
            raw_candidates.append(str(resolved))
    except Exception:
        pass
    candidates = [c.rstrip("/") or c for c in raw_candidates]
    for glob in protected_globs:
        for cand in candidates:
            if fnmatch.fnmatch(cand, glob):
                return True, glob
            if glob.endswith("/**") and cand == glob[: -len("/**")]:
                return True, glob
    return False, None


def main():
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return 0

    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command")
    if not command:
        return 0

    import harness_common as hc

    state = hc.read_json(hc.STATE, default={}) or {}
    protected = state.get("protected_paths") or []
    if not protected:
        return 0

    targets = _extract_targets(command)
    if not targets:
        return 0

    for target in targets:
        matched, glob = _target_matches(target, protected, hc.ROOT)
        if matched:
            hc.log_event(
                "protected_path_blocked",
                command=command[:400],
                target=target,
                glob=glob,
            )
            sys.stderr.write(
                "HARNESS PROTECTED PATH: command targets '{target}', which matches "
                "protected glob '{glob}' (state.json protected_paths). Denied. "
                "Destructive commands (rm/mv/shred/truncate, or redirects) against "
                "protected paths are blocked; edit state.json protected_paths if this "
                "block is a false positive.\n".format(target=target, glob=glob)
            )
            return 2
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        code = 0
    sys.exit(code)
