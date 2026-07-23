#!/usr/bin/env python3
"""Pre-tool hook that blocks commands capable of destroying workspace data.

This is a deliberately conservative backstop for coding agents.  It does not
try to prove intent: when an executable command matches a known destructive
shape, the command is refused with exit status 2.  Use ``safe_delete.py`` to
move unwanted paths into the reversible ``.harness/trash`` quarantine.

The threat model follows GPT-5.3-Codex System Card section 4.1: seemingly
benign requests such as "clean the folder" or "reset the branch" can conceal
rm -rf, git clean -xfd, git reset --hard, and force-push data loss.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

import portalock


BLOCK_MESSAGE = (
    "HARNESS DATA-LOSS GUARD: blocked {rule}. This operation can irreversibly "
    "delete data or discard edits. Preserve user changes; use "
    "`python3 .harness/bin/safe_delete.py quarantine <path>` for reversible "
    "removal, or ask the user to perform an explicitly reviewed destructive "
    "operation outside the agent session."
)


# Ordered from specific to general so the emitted reason is useful.
COMMAND_RULES = (
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
    ("PowerShell Remove-Item", re.compile(r"(?i)\bRemove-Item\b|(?:^|[;|]\s*)ri\b")),
    ("Windows delete command", re.compile(r"(?i)(?:^|[;&|()]\s*)(?:del|erase)(?:\s|$)")),
    ("Python filesystem deletion", re.compile(r"(?i)\b(?:shutil\.rmtree|os\.(?:remove|unlink|rmdir|removedirs)|(?:pathlib\.)?Path\([^\n]*?\)\.(?:unlink|rmdir))\s*\(")),
    ("Python subprocess deletion", re.compile(r"(?is)\b(?:subprocess\.)?(?:run|call|check_call|check_output|Popen)\s*\(\s*(?:\[|\()[^\n;]*?['\"](?:rm|unlink|rmdir|shred|truncate)['\"]")),
    ("Python shell deletion", re.compile(r"(?is)\bos\.(?:system|popen)\s*\(\s*['\"][^'\"\n]*(?:rm|unlink|rmdir|shred|truncate)\b")),
    ("JavaScript filesystem deletion", re.compile(r"(?i)\b(?:fs\.)?(?:rmSync|rmdirSync|unlinkSync)\s*\(|\b(?:fs\.)?promises\.(?:rm|rmdir|unlink)\s*\(|\bDeno\.remove\s*\(")),
    ("compiled-language filesystem deletion", re.compile(r"(?i)\b(?:os\.RemoveAll|os\.Remove|Files\.deleteIfExists|Files\.delete|fs::remove_file|fs::remove_dir_all|fs::remove_dir)\s*\(")),
    ("Ruby filesystem deletion", re.compile(r"(?i)\b(?:File\.(?:delete|unlink)|FileUtils\.(?:rm|rm_f|rm_r|rm_rf|remove|remove_dir|remove_entry))\s*\(?")),
    ("Perl unlink", re.compile(r"(?i)\bunlink\b")),
)

PATCH_DELETE = re.compile(r"(?m)^\s*\*\*\* Delete File:\s*\S+")


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        # Restrict inspection to fields that can carry executable input.  This
        # avoids blocking a harmless tool merely because its metadata quotes a
        # dangerous command.
        for key in ("cmd", "command", "patch", "input", "script", "code"):
            if key in value:
                yield from _strings(value[key])
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def classify(payload: Any) -> Optional[Tuple[str, str]]:
    """Return ``(rule, matching_text)`` when a hook payload is destructive."""
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input", payload.get("input", {}))
    tool_name = str(payload.get("tool_name") or payload.get("tool") or "")
    for text in _strings(tool_input):
        if PATCH_DELETE.search(text):
            return "apply_patch Delete File", text
        for rule, pattern in COMMAND_RULES:
            if pattern.search(text):
                return rule, text
    # Some hook implementations pass apply_patch text as the direct input.
    if isinstance(tool_input, str) and "patch" in tool_name.lower() and PATCH_DELETE.search(tool_input):
        return "apply_patch Delete File", tool_input
    return None


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
            portalock.lock_ex(handle)
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            portalock.unlock(handle)
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
