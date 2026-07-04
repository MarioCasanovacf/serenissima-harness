#!/usr/bin/env python3
"""Claude Code hook (PreToolUse on Edit|Write|MultiEdit|NotebookEdit).

Blocks a write ONLY when a live (unexpired) lock on the target file is held
by a DIFFERENT agent — this is the mechanical guarantee behind the
multi-agent write-lock protocol (parallel safety across sessions/engines).

A write is also allowed when the lock's holder is registered (via
bin/session.py) as a session holder: an agent name the COORDINATOR has
explicitly declared to be coordinated within THIS session (fixes P-002 —
in-session subagents with per-call identity overrides used to self-block on
their own locks, because this hook only ever compared against the ambient
CLAUDE_HARNESS_AGENT_ID). Registered holders = agents coordinated within
THIS session ONLY; cross-session/cross-engine holders are NEVER
auto-registered (blackboard.py claim does not register anyone), so their
locks still block mechanically exactly as before.

Fail-open: on any internal error, or when no live foreign/unregistered lock
exists, the write is allowed (exit 0). Blocking protocol: exit code 2 with
the reason on stderr, which Claude Code feeds back to the model so it can
pick another task or wait for expiry.
"""
import json
import sys


def main():
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not target:
        return 0

    import harness_common as hc

    _, lock = hc.read_lock(target)
    if not lock or hc.lock_is_expired(lock):
        return 0

    me = hc.agent_id()
    holder = lock.get("holder", "?")
    if holder == me or holder in hc.session_holders():
        return 0

    sys.stderr.write(
        "HARNESS LOCK: '{target}' is write-locked by agent '{holder}' "
        "(task {task}, acquired {ts}, ttl {ttl}s). Do not edit it now. "
        "Pick another claimable task (`python3 .harness/bin/blackboard.py next "
        "--agent {me}`) or wait for release/expiry.\n".format(
            target=target,
            holder=holder,
            task=lock.get("task_id", "?"),
            ts=lock.get("acquired_at", "?"),
            ttl=lock.get("ttl_seconds", "?"),
            me=me,
        )
    )
    return 2


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        code = 0
    sys.exit(code)
