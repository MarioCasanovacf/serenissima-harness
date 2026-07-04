#!/usr/bin/env python3
"""Bounded edit-test-fix loop harness for the Universal Agent Harness (.harness/bin/).

Usage:
  python3 .harness/bin/goal_mode.py run --cmd "<shell command>"
      [--max-iters N] [--timeout S] [--task T-XXX]
  python3 .harness/bin/goal_mode.py reset --task T-XXX
  python3 .harness/bin/goal_mode.py reset --task T-XXX --cmd "<shell command>"

Purpose (ZCode "goal mode" parity item #1, anti-agentic-trap):
  An agent stuck in an edit-test-fix loop calls `run` once per iteration
  instead of invoking its test command directly. The tool MECHANICALLY
  enforces an iteration bound per (task, command) pair so no agent can loop
  forever chasing a failing test: once the bound is reached the command
  itself is refused (exit 3) until a human/verifier calls `reset`.

Semantics:
  - Defaults come from .harness/state.json `limits`: --max-iters defaults to
    limits.max_retries_per_failure, --timeout to limits.max_seconds_per_command
    (both fall back to hardcoded values if state.json is missing/unreadable,
    fail-safe per harness_common conventions).
  - Iteration counters persist across process invocations in
    .harness/logs/goal_mode_state.json, keyed by "<task>:<sha1(cmd)[:12]>" so
    different commands/tasks never share a bound.
  - `run` executes --cmd via `subprocess.run(shell=True, capture_output=True,
    text=True, timeout=...)`. A `subprocess.TimeoutExpired` counts as a
    failed iteration with an explicit TIMEOUT note in the failure digest.
  - Exit 0: command succeeded (returncode == 0). Prints a success line, logs
    `goal_reached` (with iterations_used), and CLEARS the counter for this
    (task, cmd) key so a later re-run of the same command starts fresh.
  - Exit 1: command failed and iterations remain. Increments the counter
    (logging `goal_mode_start` on the very first iteration for this key),
    overwrites .harness/logs/goal_mode_last_failure.md with an actionable
    digest, and prints a one-line hint pointing at that file.
  - Exit 3: the bound is reached (this call would be iteration > max-iters).
    Logs `goal_abandoned` (with iterations_used), writes the digest with an
    ABANDONED banner, and prints an instruction to stop and mark the task
    blocked. The command is NOT re-run once abandoned. Every subsequent
    `run` call with the same (task, cmd) key keeps exiting 3 without
    executing --cmd again, until `reset` is called for that key.
  - `reset --task T-XXX [--cmd "..."]`: clears counters. With --cmd, clears
    only that (task, cmd) key; without --cmd, clears every key for --task.
"""
import argparse
import hashlib
import re
import subprocess
import sys
import time

import harness_common as hc

COUNTER_FILE = hc.LOGS / "goal_mode_state.json"
DIGEST_FILE = hc.LOGS / "goal_mode_last_failure.md"

DEFAULT_MAX_ITERS = 3
DEFAULT_TIMEOUT_SECONDS = 300

NO_TASK = "none"
TAIL_LINES = 40
FILE_MENTION_RE = re.compile(r"[./\w\-]+\.[A-Za-z]{1,5}(?::\d+)?")
MAX_FILE_MENTIONS = 15


def _limits_defaults():
    """Read (max_iters, timeout_seconds) defaults from state.json limits,
    falling back to hardcoded values if the file is missing/malformed."""
    state = hc.read_json(hc.STATE) or {}
    limits = state.get("limits") or {}
    try:
        max_iters = int(limits.get("max_retries_per_failure", DEFAULT_MAX_ITERS))
    except (TypeError, ValueError):
        max_iters = DEFAULT_MAX_ITERS
    try:
        timeout_seconds = int(limits.get("max_seconds_per_command", DEFAULT_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        timeout_seconds = DEFAULT_TIMEOUT_SECONDS
    return max_iters, timeout_seconds


def _key_for(task, cmd):
    task = task or NO_TASK
    digest = hashlib.sha1(cmd.encode("utf-8")).hexdigest()[:12]
    return "{}:{}".format(task, digest)


def _read_counters():
    return hc.read_json(COUNTER_FILE, default={}) or {}


def _tail(text, n=TAIL_LINES):
    if not text:
        return ""
    lines = text.splitlines()
    return "\n".join(lines[-n:])


def _find_file_mentions(*texts):
    found = []
    seen = set()
    for text in texts:
        if not text:
            continue
        for match in FILE_MENTION_RE.finditer(text):
            candidate = match.group(0)
            if candidate not in seen:
                seen.add(candidate)
                found.append(candidate)
            if len(found) >= MAX_FILE_MENTIONS:
                break
        if len(found) >= MAX_FILE_MENTIONS:
            break
    return found


def _write_digest(cmd, task, iteration, max_iters, exit_desc, duration_seconds, stdout, stderr, abandoned):
    task_label = task or NO_TASK
    banner = "ABANDONED — BOUND REACHED, DO NOT RE-RUN" if abandoned else "FAILURE"
    mentions = _find_file_mentions(stdout, stderr)
    mentions_block = "\n".join("- `{}`".format(m) for m in mentions) if mentions else "(none detected)"
    body = """# goal_mode: {banner}

- **command**: `{cmd}`
- **task**: {task}
- **iteration**: {iteration}/{max_iters}
- **exit**: {exit_desc}
- **duration**: {duration:.2f}s
- **timestamp**: {ts}

## stdout (last {tail_n} lines)
```
{stdout_tail}
```

## stderr (last {tail_n} lines)
```
{stderr_tail}
```

## files mentioned in output
{mentions_block}

## next step
{next_step}
""".format(
        banner=banner,
        cmd=cmd,
        task=task_label,
        iteration=iteration,
        max_iters=max_iters,
        exit_desc=exit_desc,
        duration=duration_seconds,
        ts=hc.now_iso(),
        tail_n=TAIL_LINES,
        stdout_tail=_tail(stdout) or "(empty)",
        stderr_tail=_tail(stderr) or "(empty)",
        mentions_block=mentions_block,
        next_step=(
            "Bound reached for this (task, command) pair. STOP iterating; do not re-run "
            "--cmd as-is. Mark the task blocked (`blackboard.py update {task} --status "
            "blocked --note \"goal_mode bound reached: {cmd}\"`) or, once the human/verifier "
            "confirms a real fix was made, call `goal_mode.py reset --task {task} --cmd "
            "\"{cmd}\"` before retrying.".format(task=task_label, cmd=cmd)
            if abandoned
            else "Read the stderr/stdout tails above, fix the named file(s), then re-run the "
            "identical --cmd (same task) to consume the next iteration."
        ),
    )
    DIGEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DIGEST_FILE, "w", encoding="utf-8") as f:
        f.write(body)


def cmd_run(args):
    max_iters = args.max_iters
    timeout_seconds = args.timeout
    key = _key_for(args.task, args.cmd)
    task_label = args.task or NO_TASK

    with hc.guarded():
        counters = _read_counters()
        record = counters.get(key)
        if record is None:
            record = {
                "task": task_label,
                "cmd": args.cmd,
                "iterations": 0,
                "max_iters": max_iters,
                "started_at": hc.now_iso(),
            }
        # An explicit --max-iters on this call refreshes the recorded bound
        # (lets an agent tighten/loosen the bound between invocations).
        record["max_iters"] = max_iters
        already_abandoned = record["iterations"] >= record["max_iters"]
        counters[key] = record
        hc.atomic_write_json(COUNTER_FILE, counters)

    if already_abandoned:
        _write_digest(
            args.cmd, args.task, record["iterations"], record["max_iters"],
            exit_desc="BOUND ALREADY REACHED (not re-run)", duration_seconds=0.0,
            stdout="", stderr="", abandoned=True,
        )
        hc.log_event(
            "goal_abandoned", task=task_label, cmd=args.cmd,
            iterations_used=record["iterations"], max_iters=record["max_iters"],
            note="run() called again after bound was already reached",
        )
        print(
            "ABANDONED: {}/{} iterations already used for this command/task. "
            "Command was NOT re-run. Stop and mark the task blocked, or "
            "`goal_mode.py reset --task {} --cmd \"{}\"` if a real fix was made. "
            "See {}".format(
                record["iterations"], record["max_iters"], task_label, args.cmd, DIGEST_FILE
            )
        )
        return 3

    iteration = record["iterations"] + 1
    if iteration == 1:
        hc.log_event(
            "goal_mode_start", task=task_label, cmd=args.cmd,
            max_iters=record["max_iters"], timeout_seconds=timeout_seconds,
        )

    started = time.monotonic()
    timed_out = False
    stdout, stderr = "", ""
    returncode = None
    try:
        proc = subprocess.run(
            args.cmd, shell=True, capture_output=True, text=True, timeout=timeout_seconds,
        )
        returncode = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + "\n[goal_mode] TIMEOUT after {}s".format(timeout_seconds)
    duration = time.monotonic() - started

    if returncode == 0 and not timed_out:
        with hc.guarded():
            counters = _read_counters()
            counters.pop(key, None)
            hc.atomic_write_json(COUNTER_FILE, counters)
        hc.log_event(
            "goal_reached", task=task_label, cmd=args.cmd,
            iterations_used=iteration, max_iters=record["max_iters"], duration_seconds=duration,
        )
        print(
            "GOAL REACHED: '{}' succeeded on iteration {}/{} ({:.2f}s).".format(
                args.cmd, iteration, record["max_iters"], duration
            )
        )
        return 0

    exit_desc = "TIMEOUT" if timed_out else "exit {}".format(returncode)
    bound_now_reached = iteration >= record["max_iters"]

    with hc.guarded():
        counters = _read_counters()
        current = counters.get(key, record)
        current["iterations"] = iteration
        counters[key] = current
        hc.atomic_write_json(COUNTER_FILE, counters)

    _write_digest(
        args.cmd, args.task, iteration, record["max_iters"],
        exit_desc=exit_desc, duration_seconds=duration,
        stdout=stdout, stderr=stderr, abandoned=bound_now_reached,
    )

    if bound_now_reached:
        hc.log_event(
            "goal_abandoned", task=task_label, cmd=args.cmd,
            iterations_used=iteration, max_iters=record["max_iters"], duration_seconds=duration,
        )
        print(
            "ABANDONED: '{}' failed on iteration {}/{} ({}). Bound reached — STOP, do not "
            "retry this command. Mark the task blocked, or `goal_mode.py reset --task {} "
            "--cmd \"{}\"` once a real fix is confirmed. Digest: {}".format(
                args.cmd, iteration, record["max_iters"], exit_desc, task_label, args.cmd, DIGEST_FILE
            )
        )
        return 3

    print(
        "iteration {}/{} failed ({}) — read {}, fix, re-run".format(
            iteration, record["max_iters"], exit_desc, DIGEST_FILE
        )
    )
    return 1


def cmd_reset(args):
    task_label = args.task
    cleared = []
    with hc.guarded():
        counters = _read_counters()
        if args.cmd:
            key = _key_for(task_label, args.cmd)
            if key in counters:
                cleared.append(key)
                counters.pop(key)
        else:
            for key in list(counters.keys()):
                if key.split(":", 1)[0] == task_label:
                    cleared.append(key)
                    counters.pop(key)
        hc.atomic_write_json(COUNTER_FILE, counters)
    hc.log_event("goal_mode_reset", task=task_label, cmd=args.cmd, cleared_keys=cleared)
    if cleared:
        print("reset: cleared {} counter(s) for task {}: {}".format(len(cleared), task_label, cleared))
    else:
        print("noop: no counters found for task {} (cmd={})".format(task_label, args.cmd or "*"))
    return 0


def main(argv):
    max_iters_default, timeout_default = _limits_defaults()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run --cmd once, bounded by a persistent per-(task,cmd) counter")
    p_run.add_argument("--cmd", required=True, help="shell command to run (passed to subprocess with shell=True)")
    p_run.add_argument("--max-iters", type=int, default=max_iters_default, dest="max_iters")
    p_run.add_argument("--timeout", type=int, default=timeout_default)
    p_run.add_argument("--task", default=None, help="task id (e.g. T-004); omit for ad-hoc/no-task runs")
    p_run.set_defaults(func=cmd_run)

    p_reset = sub.add_parser("reset", help="clear persistent iteration counter(s) for a task")
    p_reset.add_argument("--task", required=True)
    p_reset.add_argument("--cmd", default=None, help="clear only this command's counter; omit to clear all for --task")
    p_reset.set_defaults(func=cmd_reset)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
