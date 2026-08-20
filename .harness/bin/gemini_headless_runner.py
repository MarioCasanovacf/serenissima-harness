#!/usr/bin/env python3
"""Run Gemini CLI headlessly while retaining replayable JSONL evidence.

This adapter deliberately does not mutate the harness blackboard.  Claiming,
locking, handoff, and verdicts remain explicit calls to the substrate CLIs.

Hard boundary: a Claude-coordinated session must never invoke this module to
outsource reasoning to another model -- the no-external-LLM rule extends to
local model subprocesses; engines coordinate through the blackboard, not
through each other.
"""

import argparse
import datetime as dt
import json
import math
import os
import queue
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path


TURN_LIMIT_EXIT = 53
WALL_CLOCK_TIMEOUT_EXIT = 124
DEFAULT_TIMEOUT_SECONDS = 300
TERMINATION_GRACE_SECONDS = 2.0
IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/+\-]{0,127}$")
STATE_PATH = Path(__file__).resolve().parents[1] / "state.json"


def utc_now():
    return dt.datetime.now(dt.timezone.utc)


def iso_now():
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_binary(candidate):
    """Return the executable path, or None when the dependency is unavailable."""
    expanded = os.path.expanduser(candidate)
    if os.path.sep in expanded or (os.path.altsep and os.path.altsep in expanded):
        path = Path(expanded)
        if path.is_file() and os.access(str(path), os.X_OK):
            return str(path.resolve())
        return None
    return shutil.which(expanded)


def validate_identity(value, flag):
    if not IDENTITY_RE.fullmatch(value):
        raise ValueError(
            "%s must be 1-128 safe identity characters "
            "(letters, digits, '.', '_', ':', '@', '/', '+', '-')" % flag
        )
    return value


def path_component(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-") or "unknown"


def default_timeout_seconds():
    """Read the shared command bound, with goal_mode.py's fallback."""
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        value = int((state.get("limits") or {}).get("max_seconds_per_command"))
        if value > 0:
            return value
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return DEFAULT_TIMEOUT_SECONDS


def positive_float(value):
    try:
        parsed = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive number")
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return parsed


def compose_prompt(prompt, agent_id, task_id):
    return (
        "[UNIVERSAL HARNESS EXECUTION CONTEXT]\n"
        "Agent identity: %s\n"
        "Task identity: %s\n"
        "Treat the prompt below as the complete assignment. Do not directly edit "
        ".harness/blackboard.json; use harness lifecycle CLIs when instructed.\n"
        "[BEGIN SELF-CONTAINED PROMPT]\n%s\n[END SELF-CONTAINED PROMPT]\n"
        % (agent_id, task_id, prompt)
    )


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".summary-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def new_summary(agent_id, task_id, run_id, argv_display, raw_path, stderr_path, timeout_seconds):
    return {
        "schema_version": 1,
        "runner": "gemini-cli-headless",
        "run_id": run_id,
        "agent_id": agent_id,
        "task_id": task_id,
        "started_at": iso_now(),
        "status": "running",
        "exit_code": None,
        "command": argv_display,
        "raw_jsonl": str(raw_path),
        "stderr_log": str(stderr_path),
        "event_counts": {},
        "invalid_jsonl_lines": 0,
        "wall_clock_timeout_seconds": timeout_seconds,
    }


def observe_event(summary, line):
    try:
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        event = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError):
        summary["invalid_jsonl_lines"] += 1
        return
    if not isinstance(event, dict):
        summary["invalid_jsonl_lines"] += 1
        return
    event_type = event.get("type") or event.get("event") or "unknown"
    event_type = str(event_type)
    counts = summary["event_counts"]
    counts[event_type] = counts.get(event_type, 0) + 1
    if event_type == "init":
        for source, target in (("session_id", "session_id"), ("sessionId", "session_id"), ("model", "model")):
            value = event.get(source)
            if isinstance(value, (str, int, float, bool)):
                summary[target] = value
    elif event_type == "error":
        summary["error_events"] = summary.get("error_events", 0) + 1
    elif event_type == "result":
        summary["result_seen"] = True
        stats = event.get("stats")
        if isinstance(stats, dict):
            summary["stats"] = stats


def build_parser():
    parser = argparse.ArgumentParser(
        description="Safe Gemini CLI stream-json adapter with run-specific evidence logs."
    )
    parser.add_argument("--prompt-file", type=Path, help="UTF-8 file containing the complete prompt")
    parser.add_argument("--agent-id", help="unique harness worker identity")
    parser.add_argument("--task-id", help="blackboard task identity (informational only)")
    parser.add_argument(
        "--gemini-bin",
        default=os.environ.get("GEMINI_BIN", "gemini"),
        help="Gemini executable name/path (default: GEMINI_BIN or gemini)",
    )
    parser.add_argument("--model", help="optional Gemini model name")
    parser.add_argument(
        "--timeout-seconds",
        type=positive_float,
        default=None,
        help="positive wall-clock bound (default: limits.max_seconds_per_command)",
    )
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="workspace passed to Gemini")
    parser.add_argument(
        "--logs-root",
        type=Path,
        help="log root (default: <cwd>/.harness/logs/gemini)",
    )
    parser.add_argument("--dry-run", action="store_true", help="validate and print invocation without running")
    parser.add_argument("--discover", action="store_true", help="report whether the configured Gemini binary exists")
    return parser


def discovery_payload(candidate):
    resolved = resolve_binary(candidate)
    return {"candidate": candidate, "available": resolved is not None, "resolved": resolved}


def pump_stdout(stream, messages):
    """Read bytes off the child pipe without blocking the deadline owner."""
    try:
        for line in iter(stream.readline, b""):
            messages.put(line)
    finally:
        stream.close()
        messages.put(None)


# `killpg` on Darwin does not only answer ESRCH for a group that is gone. Measured on
# macOS 25.6 under load (25 timed-out runs, 10 CPU burners): 2 of them came back EPERM,
# "[Errno 1] Operation not permitted", from `killpg` on a group this process created
# moments earlier and is entitled to signal. The run had launched, streamed and timed
# out correctly; only the kill answered oddly.
#
# DEFECT RUNNER-LAUNCH-MISREPORT-A, and the consequence was not cosmetic. PermissionError
# is an OSError, so it escaped this function, unwound past every assignment below, and
# landed in the handler that writes `status: "launch_error"` -- a run that timed out was
# filed as a CLI that never started. Anyone counting timeouts undercounted them and
# anyone counting launch failures counted a launch that had in fact succeeded.
#
# A signal we are not permitted to send is not a failure of the run, so it is absorbed
# here, at the only place that can tell the difference.
UNSIGNALLABLE = (ProcessLookupError, PermissionError)


def record_refusals(summary, refused):
    """Write refused signals into the summary, or say nothing when there were none.

    The field is absent on the ordinary path on purpose. A key that is always present and
    almost always empty gets skimmed; a key that appears only when the kernel refused a
    kill is a fact worth reading, and it is the only signal a consumer has that the run
    timed out but the process group may have outlived it.
    """
    if refused:
        summary["termination_refused"] = refused
    return summary


def terminate_process_group(process):
    """Terminate, then force-kill, the isolated child process group and reap it.

    Returns the signals that were refused WHILE THE LEADER WAS STILL ALIVE, in order.
    Absorbing a refusal is not the same as pretending it did not happen: a refusal that
    lands on a live leader means the group may outlive the run, and the caller writes it
    down rather than reporting an unqualified clean timeout. An empty list is the ordinary
    case.

    TWO KINDS OF ERROR ARE DELIBERATELY NOT REFUSALS, and both were learned by measurement
    rather than reasoned about:

    ESRCH -- the group is already gone. This is the NORMAL outcome of the second signal,
    because SIGTERM usually did the job. Filing it would put the field on nearly every
    timed-out run, where it would say nothing.

    EPERM ON A LEADER THAT HAS ALREADY EXITED -- Darwin answers `killpg` on an emptied
    group with EPERM, not ESRCH. Observed under load with `child_exit_code: -15` in the
    same summary: SIGTERM had worked, the leader was reaped, and the follow-up SIGKILL
    still came back "Operation not permitted". Recording that as a refusal claims the
    group may have survived when the leader's own exit status proves it did not.

    What is left is the case that carries information: the kernel refused a signal to a
    group whose leader is still running.
    """
    refused = []

    def signal_group(sig, name):
        if os.name != "posix":
            return
        alive_before = process.poll() is None
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            if alive_before:
                refused.append({"signal": name, "error": str(exc)})

    if os.name == "posix":
        signal_group(signal.SIGTERM, "SIGTERM")
    elif process.poll() is None:
        process.terminate()

    try:
        process.wait(timeout=TERMINATION_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass

    # The leader may have exited while descendants retained its stdout pipe, so
    # target the group even when process.poll() is no longer None.
    if os.name == "posix":
        signal_group(signal.SIGKILL, "SIGKILL")
    elif process.poll() is None:
        process.kill()

    try:
        process.wait(timeout=TERMINATION_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    return refused


def main(argv=None):
    args = build_parser().parse_args(argv)
    timeout_seconds = args.timeout_seconds
    if timeout_seconds is None:
        timeout_seconds = default_timeout_seconds()
    dependency = discovery_payload(args.gemini_bin)
    if args.discover and args.prompt_file is None:
        print(json.dumps(dependency, sort_keys=True))
        return 0 if dependency["available"] else 1

    missing = [
        flag
        for flag, value in (
            ("--prompt-file", args.prompt_file),
            ("--agent-id", args.agent_id),
            ("--task-id", args.task_id),
        )
        if value is None
    ]
    if missing:
        print("required for a run: %s" % ", ".join(missing), file=sys.stderr)
        return 42

    try:
        agent_id = validate_identity(args.agent_id, "--agent-id")
        task_id = validate_identity(args.task_id, "--task-id")
        cwd = args.cwd.resolve(strict=True)
        if not cwd.is_dir():
            raise ValueError("--cwd is not a directory: %s" % cwd)
        prompt_path = args.prompt_file.resolve(strict=True)
        if not prompt_path.is_file():
            raise ValueError("--prompt-file is not a regular file: %s" % prompt_path)
        prompt = prompt_path.read_text(encoding="utf-8")
        if not prompt.strip():
            raise ValueError("--prompt-file must not be empty")
    except (OSError, UnicodeError, ValueError) as exc:
        print("input error: %s" % exc, file=sys.stderr)
        return 42

    effective_bin = dependency["resolved"] or args.gemini_bin
    command = [effective_bin, "--prompt", compose_prompt(prompt, agent_id, task_id), "--output-format", "stream-json"]
    if args.model:
        command.extend(["--model", args.model])

    # Never display or persist the prompt in runner metadata.
    display = list(command)
    display[2] = "<prompt from %s>" % prompt_path
    plan = {
        "dependency": dependency,
        "cwd": str(cwd),
        "command": display,
        "uses_shell": False,
        "yolo": False,
        "wall_clock_timeout_seconds": timeout_seconds,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if not dependency["available"]:
        print("Gemini CLI executable not found: %s" % args.gemini_bin, file=sys.stderr)
        return 127

    logs_root = args.logs_root
    if logs_root is None:
        logs_root = cwd / ".harness" / "logs" / "gemini"
    elif not logs_root.is_absolute():
        logs_root = cwd / logs_root
    run_id = "%s-%s" % (utc_now().strftime("%Y%m%dT%H%M%SZ"), uuid.uuid4().hex[:10])
    run_dir = logs_root / path_component(task_id) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    raw_path = run_dir / "events.jsonl"
    stderr_path = run_dir / "stderr.log"
    summary_path = run_dir / "summary.json"
    summary = new_summary(
        agent_id, task_id, run_id, display, raw_path, stderr_path, timeout_seconds
    )

    started = time.monotonic()
    timed_out = False
    launched = False
    try:
        with raw_path.open("wb") as raw_log, stderr_path.open("wb") as stderr_log:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=stderr_log,
                shell=False,
                start_new_session=(os.name == "posix"),
            )
            launched = True
            assert process.stdout is not None
            messages = queue.Queue()
            reader = threading.Thread(
                target=pump_stdout, args=(process.stdout, messages), daemon=True
            )
            reader.start()
            deadline = started + timeout_seconds
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    raw_line = messages.get(timeout=min(0.1, remaining))
                except queue.Empty:
                    continue
                if raw_line is None:
                    break
                raw_log.write(raw_line)
                raw_log.flush()
                sys.stdout.buffer.write(raw_line)
                sys.stdout.buffer.flush()
                observe_event(summary, raw_line)
            if timed_out:
                record_refusals(summary, terminate_process_group(process))
            else:
                # EOF implies the child has closed stdout; this bounded wait is
                # still covered by the same deadline for unusual CLI behavior.
                remaining = max(0.0, deadline - time.monotonic())
                try:
                    process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    record_refusals(summary, terminate_process_group(process))
            reader.join(timeout=TERMINATION_GRACE_SECONDS)
            # Preserve any complete events the reader queued just before group
            # termination; a timeout must not silently discard available evidence.
            while True:
                try:
                    raw_line = messages.get_nowait()
                except queue.Empty:
                    break
                if raw_line is None:
                    continue
                raw_log.write(raw_line)
                raw_log.flush()
                sys.stdout.buffer.write(raw_line)
                sys.stdout.buffer.flush()
                observe_event(summary, raw_line)
            exit_code = process.returncode
    except OSError as exc:
        # A LAUNCH ERROR IS AN ERROR OF THE LAUNCH. Anything raised after `Popen` returned
        # is an error of the runner's own bookkeeping -- a full disk, a closed stdout, a
        # signal refused -- and reporting it as a CLI that never started is a lie about
        # where the fault lies. The two cases now carry different status strings and
        # different fields; the exit code stays 127 for both, because no record ratifies
        # a second failure code and inventing one here would be this module deciding it.
        if launched:
            summary.update(
                status="runner_error",
                exit_code=127,
                finished_at=iso_now(),
                runner_error=str(exc),
                child_launched=True,
            )
            note = "Gemini CLI launched but the runner failed; summary: %s"
        else:
            summary.update(
                status="launch_error",
                exit_code=127,
                finished_at=iso_now(),
                launch_error=str(exc),
                child_launched=False,
            )
            note = "Gemini CLI launch failed; summary: %s"
        atomic_json(summary_path, summary)
        print(note % summary_path, file=sys.stderr)
        return 127

    elapsed_seconds = round(time.monotonic() - started, 3)
    if timed_out:
        status = "blocked"
        summary["blocked_reason"] = "wall_clock_timeout"
        summary["child_exit_code"] = exit_code
        exit_code = WALL_CLOCK_TIMEOUT_EXIT
    elif exit_code == 0:
        status = "succeeded"
    elif exit_code == TURN_LIMIT_EXIT:
        status = "blocked"
        summary["blocked_reason"] = "turn_limit_exceeded"
    else:
        status = "failed"
    summary.update(
        status=status,
        exit_code=exit_code,
        finished_at=iso_now(),
        elapsed_seconds=elapsed_seconds,
    )
    atomic_json(summary_path, summary)
    print("Gemini headless run %s; summary: %s" % (status, summary_path), file=sys.stderr)
    return exit_code if exit_code >= 0 else 128 + abs(exit_code)


if __name__ == "__main__":
    sys.exit(main())
