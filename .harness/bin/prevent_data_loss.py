#!/usr/bin/env python3
"""Pre-tool hook that blocks commands capable of destroying workspace data.

This is a deliberately conservative backstop for coding agents.  It does not
try to prove intent: when an executable command matches a known destructive
shape, the command is refused with exit status 2.  Use ``safe_delete.py`` to
move unwanted paths into the reversible ``.harness/trash`` quarantine.

The threat model follows GPT-5.3-Codex System Card section 4.1: seemingly
benign requests such as "clean the folder" or "reset the branch" can conceal
rm -rf, git clean -xfd, git reset --hard, and force-push data loss.

THE DECISION IS MADE ON THE PARSED COMMAND, NEVER ON THE RAW STRING (T-407)
==========================================================================
The guard used to run twenty-two regular expressions over the command text as
one flat string.  That is GUARD-MENTION-C, this project's most repeated defect:
a substring scan cannot tell a mention from a call.  It was reproduced four
times on 2026-08-17 and once more while this repair was being written:

  1. an ``attest.py sign --body "<prose describing a removal>"`` payload;
  2. this defect's own bug report, whose text names the commands it is about;
  3. a handoff note listing the filesystem-mutating method names that an AST
     test FORBIDS a module from calling -- so the guard blocked a document
     describing a prohibition on the very operation it guards against;
  4. the test corpus written to repair the guard, which by construction is a
     list of every destructive command string the guard knows.

All five share one shape: PROSE DESCRIBING A REMOVAL THAT WAS NOT BEING
PERFORMED, and three of them were audit trails this harness wants written.

So the command is now parsed.  The text is split into four populations and each
is treated according to what it is:

  COMMANDS   simple commands as (executable, argv) token lists, split on shell
             operators.  The shell rules read tokens, so ``rm`` in argument
             position is an argument and ``rm`` in executable position is rm.
  CODE       payloads an executable's own calling convention declares to be
             code: ``sh -c``, ``python3 -c``, ``perl -e``, ``node -e``,
             ``powershell -Command``.  Scanned with the language rules, and a
             shell payload is parsed as a command line in its own right.
  COMMENTS   text after an unquoted ``#``.  Scanned with the language rules,
             because the guard blocked ``go run x.go  # os.RemoveAll(p)`` before
             this change and that block is kept rather than quietly dropped.
  DATA       quoted arguments to executables with no code convention, and
             heredoc bodies.  NEVER INSPECTED.  This is the whole repair.

WHAT THIS GIVES UP, STATED RATHER THAN LEFT TO BE DISCOVERED
-----------------------------------------------------------
A quoted argument to an executable this module does not know is data, so
``somerunner "rm -rf /"`` is allowed where it was blocked before.  That is not
a side effect of the repair; it IS the repair, because it is the same shape as
the ``--body`` payload above and no parser can tell one from the other without
knowing the callee's convention.  The mitigation is the wrapper and code-flag
tables below: an executable whose convention IS known keeps its payload
inspected, and the tables are the place to add one.

Parsing that fails falls back to the old flat scan over the whole string.  An
unparseable command is not a safe command, and the fallback is the strictest
behavior available, not the most permissive.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple


BLOCK_MESSAGE = (
    "HARNESS DATA-LOSS GUARD: blocked {rule}. This operation can irreversibly "
    "delete data or discard edits. Preserve user changes; use "
    "`python3 .harness/bin/safe_delete.py quarantine <path>` for reversible "
    "removal, or ask the user to perform an explicitly reviewed destructive "
    "operation outside the agent session."
)


# --------------------------------------------------------------------------- rules

# Executables that delete.  Matched on the BASENAME of the executable token, so
# `/bin/rm`, `\rm` and `rm` are one rule and `--body "rm -rf x"` is none of them.
DELETING_EXECUTABLES = {
    "rm": "recursive or direct rm",
    "unlink": "direct filesystem deletion",
    "rmdir": "direct filesystem deletion",
    "shred": "direct filesystem deletion",
    "truncate": "direct filesystem deletion",
    "del": "Windows delete command",
    "erase": "Windows delete command",
    "remove-item": "PowerShell Remove-Item",
    "ri": "PowerShell Remove-Item",
}

# `rm --help` is documentation, not deletion.  Kept from the previous rule set.
HARMLESS_ONLY_FLAGS = {"--help", "--version", "-h"}

# Executables that run another command given in their own arguments.  The
# remainder is re-parsed as a command, which is how `sudo rm`, `env rm`,
# `xargs rm` and `nohup rm` stay blocked without scanning raw text.
SHELL_WRAPPERS = {
    "sudo", "command", "env", "nice", "nohup", "time", "timeout", "busybox",
    "stdbuf", "setsid", "ionice", "xargs", "doas",
}

# Flags whose value the executable itself declares to be code.  A payload here
# is inspected; a payload anywhere else is data.  The value says how to read it.
CODE_FLAGS = {
    "sh": ("-c", "shell"), "bash": ("-c", "shell"), "zsh": ("-c", "shell"),
    "dash": ("-c", "shell"), "ksh": ("-c", "shell"), "ash": ("-c", "shell"),
    "python": ("-c", "source"), "python2": ("-c", "source"),
    "python3": ("-c", "source"), "py": ("-c", "source"),
    "perl": ("-e", "source"), "ruby": ("-e", "source"),
    "node": ("-e", "source"), "deno": ("-e", "source"), "bun": ("-e", "source"),
    "powershell": ("-command", "source"), "pwsh": ("-command", "source"),
}
# Additional spellings accepted for the same flag, per executable family.
CODE_FLAG_ALIASES = {
    "perl": {"-e", "-E"}, "node": {"-e", "--eval", "-p", "--print"},
    "deno": {"-e", "--eval"}, "bun": {"-e", "--eval"},
    "powershell": {"-command", "-c", "/c"}, "pwsh": {"-command", "-c", "/c"},
    "python": {"-c"}, "python2": {"-c"}, "python3": {"-c"}, "py": {"-c"},
    "ruby": {"-e"},
}

GIT_RULES = (
    ("git clean", lambda argv: "clean" in argv),
    ("git reset --hard", lambda argv: "reset" in argv and "--hard" in argv),
    ("git force push", lambda argv: "push" in argv and any(
        a in ("--force", "--force-with-lease", "--force-if-includes")
        or (a.startswith("-") and not a.startswith("--") and "f" in a[1:])
        for a in argv)),
    ("git checkout discarding edits", lambda argv: "checkout" in argv and any(
        a in ("--", "--ours", "--theirs")
        or (a.startswith("-") and not a.startswith("--") and "f" in a[1:])
        for a in argv)),
    ("git restore discarding edits", lambda argv: "restore" in argv and not any(
        a in HARMLESS_ONLY_FLAGS for a in argv)),
    ("git switch discarding edits",
     lambda argv: "switch" in argv and "--discard-changes" in argv),
    ("git rm (use --cached for index-only removal)",
     lambda argv: "rm" in argv and "--cached" not in argv),
)

# Language-level deletion, unchanged from the previous rule set.  These are the
# rules that read SOURCE, and they now run only over source: code payloads,
# comments, and tool fields that carry a file's contents rather than a command.
SOURCE_RULES = (
    ("Python filesystem deletion", re.compile(r"(?i)\b(?:shutil\.rmtree|os\.(?:remove|unlink|rmdir|removedirs)|(?:pathlib\.)?Path\([^\n]*?\)\.(?:unlink|rmdir))\s*\(")),
    ("Python subprocess deletion", re.compile(r"(?is)\b(?:subprocess\.)?(?:run|call|check_call|check_output|Popen)\s*\(\s*(?:\[|\()[^\n;]*?['\"](?:rm|unlink|rmdir|shred|truncate)['\"]")),
    ("Python shell deletion", re.compile(r"(?is)\bos\.(?:system|popen)\s*\(\s*['\"][^'\"\n]*(?:rm|unlink|rmdir|shred|truncate)\b")),
    ("JavaScript filesystem deletion", re.compile(r"(?i)\b(?:fs\.)?(?:rmSync|rmdirSync|unlinkSync)\s*\(|\b(?:fs\.)?promises\.(?:rm|rmdir|unlink)\s*\(|\bDeno\.remove\s*\(")),
    ("compiled-language filesystem deletion", re.compile(r"(?i)\b(?:os\.RemoveAll|os\.Remove|Files\.deleteIfExists|Files\.delete|fs::remove_file|fs::remove_dir_all|fs::remove_dir)\s*\(")),
    ("Ruby filesystem deletion", re.compile(r"(?i)\b(?:File\.(?:delete|unlink)|FileUtils\.(?:rm|rm_f|rm_r|rm_rf|remove|remove_dir|remove_entry))\s*\(?")),
    ("PowerShell Remove-Item", re.compile(r"(?i)\bRemove-Item\b|(?:^|[;|]\s*)ri\b")),
    ("Windows delete command", re.compile(r"(?i)(?:^|[;&|()]\s*)(?:del|erase)(?:\s|$)")),
    ("Perl unlink", re.compile(r"(?i)\bunlink\b")),
)

# The flat scan, kept VERBATIM as the fallback for text that will not parse.
FALLBACK_RULES = (
    ("git clean", re.compile(r"(?i)(?:^|[;&|()]\s*)(?:sudo\s+)?git\b[^\n;&|]*?\bclean(?:\s|$)")),
    ("git reset --hard", re.compile(r"(?i)(?:^|[;&|()]\s*)(?:sudo\s+)?git\b[^\n;&|]*?\breset\b[^\n;&|]*--hard\b")),
    ("git force push", re.compile(r"(?i)(?:^|[;&|()]\s*)(?:sudo\s+)?git\b[^\n;&|]*?\bpush\b[^\n;&|]*(?:--force(?:-with-lease|-if-includes)?\b|(?:^|\s)-[^\s]*f[^\s]*(?:\s|$))")),
    ("git checkout discarding edits", re.compile(r"(?i)(?:^|[;&|()]\s*)(?:sudo\s+)?git\b[^\n;&|]*?\bcheckout\b[^\n;&|]*(?:\s--\s|--(?:ours|theirs)\b|(?:^|\s)-[^\s]*f[^\s]*(?:\s|$))")),
    ("git restore discarding edits", re.compile(r"(?i)(?:^|[;&|()]\s*)(?:sudo\s+)?git\b[^\n;&|]*?\brestore(?:\s|$)(?![^\n;&|]*(?:--help|-h)(?:\s|$))")),
    ("git switch discarding edits", re.compile(r"(?i)(?:^|[;&|()]\s*)(?:sudo\s+)?git\b[^\n;&|]*?\bswitch\b[^\n;&|]*--discard-changes\b")),
    ("git rm (use --cached for index-only removal)", re.compile(r"(?i)(?:^|[;&|()]\s*)(?:sudo\s+)?git\b(?=[^\n;&|]*\brm\b)(?![^\n;&|]*--cached\b)[^\n;&|]*\brm\b")),
    ("find -delete", re.compile(r"(?i)(?:^|[;&|()]\s*)find\b[^\n;&|]*(?:^|\s)-delete(?:\s|$)")),
    ("find -exec/-execdir rm", re.compile(r"(?i)(?:^|[;&|()]\s*)find\b[^\n;&|]*?-exec(?:dir)?\b[^\n;&|]*?\\?\brm(?:\s|$)")),
    ("wrapped filesystem deletion", re.compile(r"(?i)(?:^|[;&|()]\s*)(?:(?:/usr/bin/)?env|nice|nohup)\b[^\n;&|]*?\b(?:rm|unlink|rmdir|shred|truncate)(?:\s|$)")),
    ("recursive or direct rm", re.compile(r"(?i)(?:^|[;&|()'\"]\s*|\bbusybox\s+)(?:sudo\s+)?(?:command\s+)?(?:/[\w.+-]+)*/?\\?rm(?:\s|$)(?!\s*(?:--help|--version)(?:\s|$))")),
    ("xargs rm", re.compile(r"(?i)\bxargs\b[^\n;&|]*\brm(?:\s|$)")),
    ("direct filesystem deletion", re.compile(r"(?i)(?:^|[;&|()]\s*)(?:sudo\s+)?(?:unlink|rmdir|shred|truncate)(?:\s|$)(?!\s*(?:--help|--version)(?:\s|$))")),
) + SOURCE_RULES

PATCH_DELETE = re.compile(r"(?m)^\s*\*\*\* Delete File:\s*\S+")

# Fields that carry a command line, versus fields that carry a file's contents.
COMMAND_FIELDS = ("cmd", "command")
SOURCE_FIELDS = ("patch", "script", "code")
AMBIGUOUS_FIELDS = ("input",)

OPERATORS = {";", "&&", "||", "|", "&", "(", ")", "{", "}", "\n", ";;"}
REDIRECTIONS = {"<", ">", ">>", "<<", "<<<", "2>", "2>>", "&>", "&>>", ">|"}

HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


# --------------------------------------------------------------------------- parse

def split_comments(text: str) -> Tuple[str, List[str]]:
    """Separate unquoted ``#`` comments from the command text.

    Done by hand rather than with shlex's own commenters because both halves are
    wanted: the command text to parse, and the comment text to scan as source.
    A ``#`` inside quotes is not a comment, which is why quote state is tracked.
    """
    out, comments = [], []
    quote = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            out.append(ch)
        elif ch == "#" and (not out or out[-1] in (" ", "\t", "\n", ";", "&", "|")):
            end = text.find("\n", i)
            end = len(text) if end == -1 else end
            comments.append(text[i:end])
            out.append("\n" if end < len(text) else "")
            i = end + 1
            continue
        else:
            out.append(ch)
        i += 1
    return "".join(out), comments


def strip_heredocs(text: str) -> Tuple[str, List[str]]:
    """Remove heredoc bodies, returning them as data.

    A heredoc body is the single most common way an agent writes prose that
    names a destructive command -- a bug report, a handoff note, a test corpus.
    It is input to the command, never a command, and is never inspected.
    """
    bodies: List[str] = []
    lines = text.split("\n")
    out: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        markers = [m.group(2) for m in HEREDOC.finditer(line)]
        i += 1
        for marker in markers:
            body: List[str] = []
            while i < len(lines) and lines[i].strip() != marker:
                body.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1  # the terminator line itself
            bodies.append("\n".join(body))
    return "\n".join(out), bodies


def tokenize(text: str) -> Optional[List[str]]:
    """Shell tokens, or None when the text will not parse.

    None sends the caller to the flat fallback scan.  An unparseable command is
    not a safe command.
    """
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return None


def simple_commands(tokens: Sequence[str]) -> List[List[str]]:
    """Split a token stream into simple commands, dropping redirections and
    leading ``VAR=value`` assignments."""
    commands: List[List[str]] = []
    current: List[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token in OPERATORS or all(c in ";&|" for c in token):
            if current:
                commands.append(current)
            current = []
            continue
        if token in REDIRECTIONS or re.fullmatch(r"\d*(?:>>?|<)", token):
            skip_next = True
            continue
        if not current and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token):
            continue
        current.append(token)
    if current:
        commands.append(current)
    return commands


def basename(executable: str) -> str:
    name = executable.replace("\\", "/").rstrip("/").split("/")[-1]
    return name.lower()


# --------------------------------------------------------------------------- decide

def _code_flag_names(exe: str) -> set:
    aliases = set(CODE_FLAG_ALIASES.get(exe, ()))
    entry = CODE_FLAGS.get(exe)
    if entry:
        aliases.add(entry[0])
    return {a.lower() for a in aliases}


def scan_source(text: str) -> Optional[Tuple[str, str]]:
    for rule, pattern in SOURCE_RULES:
        if pattern.search(text):
            return rule, text
    return None


def inspect_command(argv: Sequence[str], depth: int = 0) -> Optional[Tuple[str, str]]:
    """Decide on one simple command, following wrappers and code payloads.

    ``depth`` bounds wrapper recursion.  ``sudo env nice nohup ... rm`` is a real
    shape and the bound is generous, but a bound there must be: the token list is
    attacker-supplied and this runs inside a hook on every tool call.
    """
    if not argv or depth > 8:
        return None
    exe = basename(argv[0])
    rest = list(argv[1:])
    display = " ".join(argv)

    if exe in DELETING_EXECUTABLES:
        if rest and all(a.lower() in HARMLESS_ONLY_FLAGS for a in rest):
            return None
        return DELETING_EXECUTABLES[exe], display

    if exe == "git":
        for rule, matches in GIT_RULES:
            if matches(rest):
                return rule, display

    if exe == "find":
        if "-delete" in rest:
            return "find -delete", display
        for i, token in enumerate(rest):
            if token in ("-exec", "-execdir"):
                inner: List[str] = []
                for token2 in rest[i + 1:]:
                    if token2 in (";", "+", "\\;"):
                        break
                    inner.append(token2)
                found = inspect_command(inner, depth + 1)
                if found:
                    return "find -exec/-execdir " + found[0], display

    code_flags = _code_flag_names(exe)
    if code_flags:
        kind = (CODE_FLAGS.get(exe) or ("", "source"))[1]
        for i, token in enumerate(rest):
            if token.lower() in code_flags and i + 1 < len(rest):
                payload = rest[i + 1]
                if kind == "shell":
                    found = inspect_text(payload, depth + 1)
                    if found:
                        return found
                else:
                    found = scan_source(payload)
                    if found:
                        return found

    if exe in SHELL_WRAPPERS:
        inner = [a for a in rest]
        # `env FOO=bar rm -rf x` and `xargs -0 rm -rf x`: skip the wrapper's own
        # assignments and flags, then treat what remains as a command.
        while inner and (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", inner[0])
                         or inner[0].startswith("-")
                         or (exe == "timeout" and re.fullmatch(r"[\d.]+[smhd]?", inner[0]))):
            inner.pop(0)
        found = inspect_command(inner, depth + 1)
        if found:
            return found

    return None


def inspect_text(text: str, depth: int = 0) -> Optional[Tuple[str, str]]:
    """Decide on a whole command line: parse it, or fall back to the flat scan."""
    if depth > 8:
        return None
    stripped, _heredoc_bodies = strip_heredocs(text)
    command_text, comments = split_comments(stripped)

    for comment in comments:
        found = scan_source(comment)
        if found:
            return found[0], text

    tokens = tokenize(command_text)
    if tokens is None:
        for rule, pattern in FALLBACK_RULES:
            if pattern.search(text):
                return rule, text
        return None

    commands = simple_commands(tokens)
    for argv in commands:
        found = inspect_command(argv, depth)
        if found:
            return found

    # A HEREDOC BODY IS DATA ONLY UNTIL AN INTERPRETER IS ON THE RECEIVING END.
    # `cat > notes.md <<EOF` feeds prose to a file; `bash <<EOF` and `python3 - <<EOF`
    # feed a program to a program. Stripping the body unconditionally would have opened
    # exactly the hole this guard exists to close, so the receiving executable decides.
    if _heredoc_bodies:
        convention = None
        for argv in commands:
            exe = basename(argv[0]) if argv else ""
            if exe in SHELL_WRAPPERS and len(argv) > 1:
                exe = basename(argv[1])
            entry = CODE_FLAGS.get(exe)
            if entry and entry[1] == "shell":
                convention = "shell"
                break
            if entry:
                convention = convention or "source"
        for body in _heredoc_bodies:
            if convention == "shell":
                found = inspect_text(body, depth + 1)
            elif convention == "source":
                found = scan_source(body)
            else:
                found = None
            if found:
                return found[0], text
    return None


def _fields(value: Any, keys: Sequence[str]) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key in keys:
            if key in value:
                yield from _fields(value[key], keys)
    elif isinstance(value, list):
        for item in value:
            yield from _fields(item, keys)


def classify(payload: Any) -> Optional[Tuple[str, str]]:
    """Return ``(rule, matching_text)`` when a hook payload is destructive."""
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input", payload.get("input", {}))
    tool_name = str(payload.get("tool_name") or payload.get("tool") or "")

    for text in _fields(tool_input, COMMAND_FIELDS + SOURCE_FIELDS + AMBIGUOUS_FIELDS):
        if PATCH_DELETE.search(text):
            return "apply_patch Delete File", text

    # A field carrying a file's contents is source, not a command line.  Scanning
    # it as a command would ask a parser to tokenize a Python module.
    for text in _fields(tool_input, SOURCE_FIELDS):
        found = scan_source(text)
        if found:
            return found

    for text in _fields(tool_input, COMMAND_FIELDS + AMBIGUOUS_FIELDS):
        found = inspect_text(text)
        if found:
            return found

    # Some hook implementations pass apply_patch text as the direct input.
    if isinstance(tool_input, str) and "patch" in tool_name.lower() and PATCH_DELETE.search(tool_input):
        return "apply_patch Delete File", tool_input
    return None


# --------------------------------------------------------------------------- hook

def _workspace(payload: dict) -> Path:
    candidates = (
        payload.get("cwd"),
        (payload.get("tool_input") or {}).get("cwd") if isinstance(payload.get("tool_input"), dict) else None,
        os.environ.get("CODEX_WORKSPACE_ROOT"),
        os.environ.get("CODEX_PROJECT_DIR"),
    )
    for candidate in candidates:
        if candidate:
            return Path(str(candidate)).expanduser().absolute()
    return Path(__file__).resolve().parents[2]


def _log_block(payload: dict, rule: str, text: str) -> None:
    """Append a compact structured event; logging failure never permits action."""
    try:
        path = _workspace(payload) / ".harness" / "logs" / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": "data_loss_action_blocked",
            "agent": os.environ.get("CLAUDE_HARNESS_AGENT_ID", "codex"),
            "session_id": payload.get("session_id"),
            "tool_name": payload.get("tool_name") or payload.get("tool"),
            "rule": rule,
            "command_preview": text[:500],
        }
        record = {key: value for key, value in record.items() if value is not None}
        with path.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            fcntl.flock(handle, fcntl.LOCK_UN)
    except Exception:
        pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # An unreadable payload contains no recognized action.  The important
        # fail-closed property is below: after recognition, no logging or
        # formatting failure can turn a block into an allow.
        return 0

    match = classify(payload)
    if match is None:
        return 0
    rule, text = match
    _log_block(payload, rule, text)
    sys.stderr.write(BLOCK_MESSAGE.format(rule=rule) + "\n")
    return 2


if __name__ == "__main__":
    try:
        result = main()
    except Exception as exc:
        # A recognized action must not become executable because auxiliary hook
        # work failed.  Unexpected top-level failures are therefore blocking.
        sys.stderr.write("HARNESS DATA-LOSS GUARD: hook failure; command refused: {}\n".format(exc))
        result = 2
    sys.exit(result)
