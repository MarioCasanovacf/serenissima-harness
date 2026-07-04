#!/usr/bin/env python3
"""Claude Code hook (PostToolUse / SessionStart / Stop): appends a compact
record of every session event to .harness/logs/transcript.jsonl.

This implements the Experience Observability pillar mechanically — agents do
not have to remember to log; the harness logs for them on every tool call.

Fail-open by design: this hook must NEVER break a session, so any internal
error exits 0 silently.
"""
import json
import sys

MAX_STR = 400
MAX_DEPTH = 6
MAX_KEYS = 40
MAX_ITEMS = 20


def _truncate(value, depth=0):
    if depth > MAX_DEPTH:
        return "..."
    if isinstance(value, str):
        if len(value) <= MAX_STR:
            return value
        return value[:MAX_STR] + "... [{} chars total]".format(len(value))
    if isinstance(value, dict):
        return {k: _truncate(v, depth + 1) for k, v in list(value.items())[:MAX_KEYS]}
    if isinstance(value, list):
        out = [_truncate(v, depth + 1) for v in value[:MAX_ITEMS]]
        if len(value) > MAX_ITEMS:
            out.append("... [{} items total]".format(len(value)))
        return out
    return value


def main():
    payload = json.load(sys.stdin)
    import harness_common as hc

    record = {
        "ts": hc.now_iso(),
        "agent": hc.agent_id(),
        "event": payload.get("hook_event_name", "unknown"),
        "session_id": payload.get("session_id"),
        "tool_name": payload.get("tool_name"),
        "tool_input": _truncate(payload.get("tool_input")),
        "tool_response": _truncate(payload.get("tool_response")),
    }
    record = {k: v for k, v in record.items() if v is not None}
    hc.append_jsonl(hc.TRANSCRIPT, record)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
