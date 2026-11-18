#!/usr/bin/env python3
"""flow_runner.py - validates, launches and gates flow runs. Design T-484 sections 3 and 4.
Standard library only, Python 3.9.

    flow_runner.py [--root R] list [--json]
    flow_runner.py [--root R] validate <name> [--json]
    flow_runner.py [--root R] launch <name> --mode agents|enqueue [--foreground] [--json]
    flow_runner.py [--root R] status [<run-id>] [--json]
    flow_runner.py [--root R] gate <run-id> (--approve | --reject) [--note N]
    flow_runner.py [--root R] stop <run-id>

A recipe is .harness/flows/<name>.json (design section 3). A run is
.harness/runs/<run-id>/run.json (untracked). Exit codes: 0 done, 2 refused (a rule said
no, nothing was changed), 1 error.

MODES
  enqueue  makes sure every track's tasks exist on the board (blackboard.py add-task, for
           a track that carries a `title`), writes a run record, and does nothing else.
  agents   the same, then a detached process drives every track in parallel: producer,
           then verifier, up to `rounds` rounds. Each step runs the Claude Code CLI in
           print mode with a single JSON final result, as one agent name, with the
           prompt on stdin. The verdict is read back from the board after the step,
           never taken from the agent's text. With `gate: true` the runner then runs
           fast_tests.py once and stops at `awaiting_operator`; the operator's decision
           is written by operator_desk.record_gate_decision, the same function the
           console calls.

WHAT IT NEVER DOES
  It never passes --dangerously-skip-permissions or the bypassPermissions mode: the
  recipe's permission flags come from an allow list, and launch checks the final argument
  list again. It never edits blackboard.json, never signs, and reads nothing an agent
  prints while it works: only the step's final JSON result, after the process exits.
  HARNESS_CLAUDE_BIN names the CLI executable (default `claude`); tests point it at a
  fake that prints a scripted final result.

  It registers no session holders. Each step is its own CLI process whose ambient
  identity (CLAUDE_HARNESS_AGENT_ID) is the agent's name, so the lock hook already
  matches that agent's own locks; registering would only let the coordinator's session
  write through them, and session.py keeps registration a coordinator-only act.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import harness_common as hc
import operator_desk as od

THIS_ROOT = Path(__file__).resolve().parents[2]
RUNNER = "flow_runner"
CLAUDE_BIN_ENV = "HARNESS_CLAUDE_BIN"

FLOW_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
AGENT_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
MODEL_NAME = re.compile(r"^[a-z0-9][a-z0-9.-]{0,63}$")
RESERVED_NAMES = frozenset(["main", "operator", RUNNER])
EFFORTS = ("low", "medium", "high", "xhigh", "max")
TESTS_MODES = ("changed", "named")

RECIPE_KEYS = frozenset(["name", "description", "tests", "gate", "defaults", "tracks"])
DEFAULT_KEYS = frozenset(["model", "effort", "rounds", "permissions", "timeout"])
TRACK_KEYS = DEFAULT_KEYS | frozenset(
    ["task", "verify_task", "producer", "verifier", "verify_first", "brief", "title"])

BUILTIN_DEFAULTS = {
    "model": "sonnet",
    "effort": "high",
    "rounds": 2,
    "timeout": 1800,
    "permissions": ["--permission-mode", "acceptEdits",
                    "--allowedTools", "Bash(python3 .harness/bin/*)"],
}

# Permission flags a recipe may carry. Anything else is refused.
PERMISSION_MODES = ("acceptEdits", "auto", "default", "dontAsk", "manual", "plan")
TOOL_LIST_FLAGS = ("--allowedTools", "--allowed-tools", "--disallowedTools",
                   "--disallowed-tools")
DENIED_FLAGS = ("--dangerously-skip-permissions", "--allow-dangerously-skip-permissions")
DENIED_VALUES = ("bypassPermissions",)

RUN_STATUSES = ("enqueued", "running", "awaiting_operator", "approved", "rejected",
                "finished", "failed", "stopped")

PROTOCOL = """You are {agent}, the {role} of one track of a flow run in the Universal Agent \
Harness, in this repository. Your board task is {own_task}. Pass --agent {agent} to \
blackboard.py and --holder {agent} to lock.py on every call.

Protocol for this run:
1. Read the task first: python3 .harness/bin/blackboard.py show {own_task}
{role_steps}
- Tests: {tests_rule}
- Never sleep and never wait for another agent. If something blocks you, set the task \
blocked with a note that says why, and stop.
- Release every lock you took before you finish.
- Producer is never approver: never mark your own work done.

Brief from the recipe:
{brief}
"""

PRODUCER_STEPS = """2. Claim it: python3 .harness/bin/blackboard.py claim {task} --agent {agent}
3. Acquire a lock on every file before you edit it: \
python3 .harness/bin/lock.py acquire <path> --holder {agent} --task {task}
4. Do the work the brief asks for, and nothing outside it.
5. Hand off with replayable evidence: python3 .harness/bin/blackboard.py handoff {task} \
--to-role verifier --agent {agent} --note "<what you changed and the test result>"
"""

VERIFIER_STEPS = """2. Task {task} is in review. Replay the producer's evidence and read the diff.
3. If it meets the acceptance criteria: python3 .harness/bin/blackboard.py update {task} \
--status done --agent {agent} --note "<what you checked>"
4. If it does not: python3 .harness/bin/blackboard.py update {task} --status open \
--agent {agent} --note "REJECTED: <what is wrong>"
5. Record your verdict on your own task {own_task} with a note, and hand it off.
"""

TESTS_RULES = {
    "changed": "run only the tests your change touches "
               "(python3 .harness/bin/fast_tests.py --changed, or name the files); "
               "never the full suite, the runner runs it once at the gate.",
    "named": "run only the test files the brief names, with "
             "python3 .harness/bin/fast_tests.py <files>; never the full suite.",
}


class Refused(od.Refused):
    """A rule said no. Nothing was changed."""


# ---------------------------------------------------------------- plumbing

def resolve_root(root=None):
    return od.resolve_root(root) if root else THIS_ROOT


def _harness(root):
    return resolve_root(root) / ".harness"


def flows_dir(root):
    return _harness(root) / "flows"


def runs_dir(root):
    return _harness(root) / "runs"


def _event(root, kind, **fields):
    rec = {"ts": hc.now_iso(), "event": kind, "agent": RUNNER}
    rec.update(fields)
    try:
        hc.append_jsonl(_harness(root) / "logs" / "events.jsonl", rec)
    except OSError:
        pass  # observability never blocks the run


def _board_tasks(root):
    board = od._read_json(_harness(root) / "blackboard.json") or {}
    tasks = board.get("tasks")
    return tasks if isinstance(tasks, dict) else {}


def _task_status(root, task_id):
    return (_board_tasks(root).get(task_id) or {}).get("status")


def _tool(root, name):
    return [sys.executable, str(_harness(root) / "bin" / name)]


def _run_tool(root, argv, agent):
    env = dict(os.environ)
    env["CLAUDE_HARNESS_AGENT_ID"] = agent
    return subprocess.run(argv, cwd=str(resolve_root(root)), env=env,
                          universal_newlines=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)


# ---------------------------------------------------------------- recipes

def recipe_path(root, name):
    if not FLOW_NAME.match(str(name)):
        raise Refused("not a flow name: {!r} (lowercase letters, digits and -)".format(name))
    return flows_dir(root) / (name + ".json")


def list_flows(root):
    out = []
    d = flows_dir(root)
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            if not FLOW_NAME.match(p.stem):
                continue
            recipe = od._read_json(p)
            problems = validate(root, recipe, p.stem) if recipe is not None else ["does not parse"]
            out.append({"name": p.stem,
                        "description": (recipe or {}).get("description", "")
                        if isinstance(recipe, dict) else "",
                        "tracks": len((recipe or {}).get("tracks") or [])
                        if isinstance(recipe, dict) else 0,
                        "valid": not problems, "problems": problems})
    return out


def load_recipe(root, name):
    path = recipe_path(root, name)
    if not path.is_file():
        raise Refused("no such flow: {}".format(name))
    recipe = od._read_json(path)
    if recipe is None:
        raise Refused("{} does not parse as JSON".format(path.name))
    return recipe


def _check_permissions(flags, where):
    problems = []
    if not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
        return ["{}: permissions must be a list of strings".format(where)]
    i = 0
    while i < len(flags):
        f = flags[i]
        if f in DENIED_FLAGS or any(v in f for v in DENIED_VALUES):
            problems.append("{}: {} is on the deny list".format(where, f))
            i += 1
            continue
        if f == "--permission-mode":
            mode = flags[i + 1] if i + 1 < len(flags) else None
            if mode not in PERMISSION_MODES:
                problems.append("{}: --permission-mode {!r} is not one of {}".format(
                    where, mode, ", ".join(PERMISSION_MODES)))
            i += 2
            continue
        if f in TOOL_LIST_FLAGS:
            j = i + 1
            while j < len(flags) and not flags[j].startswith("-"):
                j += 1
            if j == i + 1:
                problems.append("{}: {} needs at least one tool".format(where, f))
            i = j
            continue
        problems.append("{}: {!r} is not an allowed permission flag".format(where, f))
        i += 1
    return problems


def effective(recipe, track, key):
    """A track's value for one of the default keys: track, then recipe defaults, then
    the built-in default."""
    if key in track:
        return track[key]
    defaults = recipe.get("defaults") or {}
    if key in defaults:
        return defaults[key]
    return BUILTIN_DEFAULTS[key]


def _check_settings(holder, where):
    problems = []
    if "model" in holder and not (isinstance(holder["model"], str)
                                  and MODEL_NAME.match(holder["model"])):
        problems.append("{}: model {!r} is not a model name".format(where, holder["model"]))
    if "effort" in holder and holder["effort"] not in EFFORTS:
        problems.append("{}: effort must be one of {}".format(where, ", ".join(EFFORTS)))
    if "rounds" in holder:
        r = holder["rounds"]
        if not isinstance(r, int) or isinstance(r, bool) or not 1 <= r <= 3:
            problems.append("{}: rounds must be 1, 2 or 3".format(where))
    if "timeout" in holder:
        t = holder["timeout"]
        if not isinstance(t, int) or isinstance(t, bool) or not 60 <= t <= 7200:
            problems.append("{}: timeout must be whole seconds from 60 to 7200".format(where))
    if "permissions" in holder:
        problems += _check_permissions(holder["permissions"], where)
    return problems


def validate(root, recipe, name=None):
    """Every problem with a recipe, in words. An empty list means it may be launched."""
    if not isinstance(recipe, dict):
        return ["the recipe must be a JSON object"]
    problems = []
    unknown = sorted(set(recipe) - RECIPE_KEYS)
    if unknown:
        problems.append("unknown keys: {}".format(", ".join(unknown)))
    if not isinstance(recipe.get("name"), str) or not FLOW_NAME.match(recipe.get("name", "")):
        problems.append("name must be lowercase letters, digits and -")
    elif name is not None and recipe["name"] != name:
        problems.append("name {!r} does not match the file name {!r}".format(recipe["name"], name))
    if not isinstance(recipe.get("description", ""), str):
        problems.append("description must be text")
    if recipe.get("tests", "changed") not in TESTS_MODES:
        problems.append("tests must be changed or named")
    if not isinstance(recipe.get("gate", True), bool):
        problems.append("gate must be true or false")
    defaults = recipe.get("defaults", {})
    if not isinstance(defaults, dict):
        problems.append("defaults must be an object")
    else:
        bad = sorted(set(defaults) - DEFAULT_KEYS)
        if bad:
            problems.append("defaults: unknown keys: {}".format(", ".join(bad)))
        problems += _check_settings(defaults, "defaults")
    tracks = recipe.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        problems.append("tracks must be a non-empty list")
        return problems
    board = _board_tasks(root)
    seen_tasks, seen_names = set(), set()
    for i, t in enumerate(tracks, 1):
        where = "track {}".format(i)
        if not isinstance(t, dict):
            problems.append("{}: must be an object".format(where))
            continue
        bad = sorted(set(t) - TRACK_KEYS)
        if bad:
            problems.append("{}: unknown keys: {}".format(where, ", ".join(bad)))
        task, vtask = t.get("task"), t.get("verify_task")
        for key, tid in (("task", task), ("verify_task", vtask)):
            if not isinstance(tid, str) or not od.TASK_ID.match(tid):
                problems.append("{}: {} must be a task id like T-123".format(where, key))
            elif tid in seen_tasks:
                problems.append("{}: {} appears in more than one track".format(where, tid))
            else:
                seen_tasks.add(tid)
                if tid not in board and not t.get("title"):
                    problems.append("{}: {} is not on the board (give the track a title "
                                    "to create it)".format(where, tid))
        if isinstance(task, str) and task == vtask:
            problems.append("{}: task and verify_task must differ".format(where))
        prod, ver = t.get("producer"), t.get("verifier")
        for key, n in (("producer", prod), ("verifier", ver)):
            if not isinstance(n, str) or not AGENT_NAME.match(n):
                problems.append("{}: {} must be an agent name (lowercase, digits, . _ -)".format(
                    where, key))
            elif n in RESERVED_NAMES:
                problems.append("{}: {} may not be the reserved name {!r}".format(where, key, n))
            elif n in seen_names:
                problems.append("{}: agent {} already works another track".format(where, n))
            else:
                seen_names.add(n)
        if isinstance(prod, str) and prod == ver:
            problems.append("{}: the producer cannot be its own verifier".format(where))
        if not isinstance(t.get("verify_first", False), bool):
            problems.append("{}: verify_first must be true or false".format(where))
        brief = t.get("brief")
        if not isinstance(brief, str) or not brief.strip():
            problems.append("{}: brief must say what to do".format(where))
        elif len(brief) > 4000:
            problems.append("{}: brief is longer than 4000 characters".format(where))
        if "title" in t and (not isinstance(t["title"], str) or not t["title"].strip()):
            problems.append("{}: title must be text".format(where))
        problems += _check_settings(t, where)
    text = json.dumps(recipe, ensure_ascii=False)
    hits = od.scan_text(text, "recipe")
    if hits:
        problems.append("the recipe would publish a leak: {}".format(od._format_hits(hits)))
    return problems


def save_recipe(root, name, recipe):
    """Validate, then write .harness/flows/<name>.json atomically. Refused on any problem."""
    problems = validate(root, recipe, name)
    if problems:
        raise Refused("; ".join(problems))
    path = recipe_path(root, name)
    hc.atomic_write_json(path, recipe)
    _event(root, "flow_saved", flow=name)
    return recipe


# ---------------------------------------------------------------- runs

def run_path(root, run_id):
    return od.run_json_path(root, run_id)


def read_run(root, run_id):
    run = od._read_json(run_path(root, run_id))
    if not isinstance(run, dict):
        raise Refused("no such run: {}".format(run_id))
    return run


def update_run(root, run_id, fn):
    """Read-modify-write run.json under <run dir>/.run.lock, the lock operator_desk takes."""
    path = run_path(root, run_id)
    with od._flock(path.parent / ".run.lock"):
        run = od._read_json(path)
        if not isinstance(run, dict):
            raise Refused("no such run: {}".format(run_id))
        fn(run)
        hc.atomic_write_json(path, run)
        return run


def list_runs(root):
    out = []
    d = runs_dir(root)
    if d.is_dir():
        for p in sorted(d.glob("*/run.json")):
            run = od._read_json(p)
            if isinstance(run, dict):
                out.append({k: run.get(k) for k in
                            ("id", "flow", "mode", "status", "started", "ended")})
    out.sort(key=lambda r: r.get("started") or "", reverse=True)
    return out


def _new_run_dir(root, flow):
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    base = "{}-{}".format(flow, stamp)
    for n in range(1, 100):
        run_id = base if n == 1 else "{}-{}".format(base, n)
        d = runs_dir(root) / run_id
        try:
            d.mkdir(parents=True)
            return run_id, d
        except FileExistsError:
            continue
    raise Refused("could not allocate a run id")


def _ensure_tasks(root, recipe, by):
    """add-task for every track task that is not on the board. Returns the ids created."""
    created = []
    board = _board_tasks(root)
    epic = "flow:" + recipe["name"]
    for t in recipe["tracks"]:
        title = (t.get("title") or "").strip()
        wanted = [(t["task"], ["--title", title, "--role", "worker"]),
                  (t["verify_task"], ["--title", "VERIFY {}: {}".format(t["task"], title),
                                      "--role", "verifier", "--depends-on", t["task"]])]
        for tid, extra in wanted:
            if tid in board:
                continue
            argv = _tool(root, "blackboard.py") + [
                "add-task", "--agent", by, "--id", tid, "--description",
                t["brief"].strip(), "--epic", epic] + extra
            cp = _run_tool(root, argv, by)
            if cp.returncode != 0:
                raise Refused("blackboard refused add-task {}: {}".format(
                    tid, (cp.stderr or cp.stdout).strip()[-300:]))
            created.append(tid)
    return created


def launch(root, name, mode, by=od.OPERATOR, foreground=False):
    """Start a run of flow `name`. Returns the run dict as written."""
    root = resolve_root(root)
    if mode not in ("agents", "enqueue"):
        raise Refused("mode must be agents or enqueue")
    recipe = load_recipe(root, name)
    problems = validate(root, recipe, name)
    if problems:
        raise Refused("the recipe does not validate: " + "; ".join(problems))
    for t in recipe["tracks"]:
        argv = claude_argv(recipe, t)
        if any(f in DENIED_FLAGS for f in argv) or any(
                v in f for f in argv for v in DENIED_VALUES):
            raise Refused("refusing to start an agent that skips permissions")
    created = _ensure_tasks(root, recipe, by)
    run_id, d = _new_run_dir(root, name)
    run = {
        "id": run_id, "flow": name, "mode": mode, "by": by,
        "status": "enqueued" if mode == "enqueue" else "running",
        "started": hc.now_iso(), "ended": hc.now_iso() if mode == "enqueue" else None,
        "created_tasks": created, "recipe": recipe, "pid": None,
        "tracks": [{"task": t["task"], "verify_task": t["verify_task"],
                    "producer": t["producer"], "verifier": t["verifier"],
                    "status": "enqueued" if mode == "enqueue" else "pending",
                    "round": 0} for t in recipe["tracks"]],
        "steps": [],
        "gate": {"status": "pending" if recipe.get("gate", True) else "none", "suite": None},
    }
    if mode == "enqueue":
        run["gate"]["status"] = "none"
    hc.atomic_write_json(d / "run.json", run)
    _event(root, "flow_run_started", run=run_id, flow=name, mode=mode, created=created)
    if mode == "agents":
        if foreground:
            drive(root, run_id)
        else:
            log = open(str(d / "driver.log"), "a")
            proc = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--root", str(root),
                 "_drive", run_id],
                cwd=str(root), stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                start_new_session=True, close_fds=True)
            log.close()
            update_run(root, run_id, lambda r: r.update(pid=proc.pid))
    return read_run(root, run_id)


# ---------------------------------------------------------------- one step

def claude_argv(recipe, track):
    binary = os.environ.get(CLAUDE_BIN_ENV) or "claude"
    return ([binary, "-p", "--output-format", "json",
             "--model", effective(recipe, track, "model"),
             "--effort", effective(recipe, track, "effort")]
            + list(effective(recipe, track, "permissions")))


def build_prompt(recipe, track, role):
    agent = track["producer"] if role == "producer" else track["verifier"]
    own = track["task"] if role == "producer" else track["verify_task"]
    steps = (PRODUCER_STEPS if role == "producer" else VERIFIER_STEPS).format(
        task=track["task"], agent=agent, own_task=own)
    return PROTOCOL.format(agent=agent, role=role, own_task=own, role_steps=steps,
                           tests_rule=TESTS_RULES[recipe.get("tests", "changed")],
                           brief=track["brief"].strip())


def _final_result(stdout):
    """The CLI's single JSON final result: the last line that parses as an object."""
    for line in reversed((stdout or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


def _stopped(root, run_id):
    try:
        return read_run(root, run_id).get("status") == "stopped"
    except Refused:
        return True


def run_step(root, run_id, recipe, track, role, rnd):
    """One agent session. Returns the board status of the track's task afterwards, or
    None when the run was stopped."""
    if _stopped(root, run_id):
        return None
    agent = track["producer"] if role == "producer" else track["verifier"]
    step = {"track": track["task"], "role": role, "round": rnd, "agent": agent,
            "status": "running", "started": hc.now_iso(), "ended": None,
            "verdict": None, "result_file": None}

    def add(run):
        run["steps"].append(step)
        for t in run["tracks"]:
            if t["task"] == track["task"]:
                t["status"], t["round"] = "running", rnd
    run = update_run(root, run_id, add)
    index = len(run["steps"]) - 1
    _event(root, "flow_step_started", run=run_id, task=track["task"], role=role,
           round=rnd, step_agent=agent)
    argv = claude_argv(recipe, track)
    env = dict(os.environ)
    env["CLAUDE_HARNESS_AGENT_ID"] = agent
    t0 = time.monotonic()
    timeout = effective(recipe, track, "timeout")
    try:
        cp = subprocess.run(argv, input=build_prompt(recipe, track, role),
                            cwd=str(resolve_root(root)), env=env, universal_newlines=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        code, out, err, state = cp.returncode, cp.stdout, cp.stderr, "ended"
    except subprocess.TimeoutExpired:
        code, out, err, state = None, "", "", "timeout"
    except OSError as e:
        code, out, err, state = None, "", str(e), "error"
    seconds = round(time.monotonic() - t0, 1)
    final = _final_result(out)
    if state == "ended" and (code != 0 or final is None or final.get("is_error")):
        state = "error"
    rel = "{}-{}-{}.json".format(track["task"], role, rnd)
    keep = {"exit": code, "seconds": seconds, "state": state}
    if final:
        for k in ("is_error", "subtype", "duration_ms", "num_turns", "total_cost_usd"):
            if k in final:
                keep[k] = final[k]
        keep["result"] = str(final.get("result", ""))[:4000]
    elif err:
        keep["stderr_tail"] = err.strip()[-1000:]
    hc.atomic_write_json(runs_dir(root) / run_id / rel, keep)
    board_status = _task_status(root, track["task"])

    def finish(run):
        s = run["steps"][index]
        if run.get("status") == "stopped":
            s["status"] = "stopped"
        else:
            s["status"] = state
        s["ended"] = hc.now_iso()
        s["seconds"] = seconds
        s["result_file"] = rel
        s["verdict"] = board_status
    update_run(root, run_id, finish)
    _event(root, "flow_step_ended", run=run_id, task=track["task"], role=role, round=rnd,
           step_agent=agent, state=state, board_status=board_status, seconds=seconds)
    return None if _stopped(root, run_id) else board_status


def run_track(root, run_id, recipe, track):
    """Producer, then verifier, up to `rounds`. Returns the track's final status."""
    rounds = effective(recipe, track, "rounds")
    outcome = "failed"
    for rnd in range(1, rounds + 1):
        status = _task_status(root, track["task"])
        if status == "done":
            outcome = "done"
            break
        skip_producer = (rnd == 1 and track.get("verify_first")) or status == "review"
        if not skip_producer:
            status = run_step(root, run_id, recipe, track, "producer", rnd)
            if status is None:
                return "stopped"
            if status != "review":
                outcome = "failed: producer left the task '{}'".format(status)
                break
        status = run_step(root, run_id, recipe, track, "verifier", rnd)
        if status is None:
            return "stopped"
        if status == "done":
            outcome = "done"
            break
        if status == "open":
            outcome = "sent back"
            continue
        outcome = "failed: verifier left the task '{}'".format(status)
        break
    return outcome


def _set_track(root, run_id, task, status):
    def fn(run):
        for t in run["tracks"]:
            if t["task"] == task:
                t["status"] = status
    update_run(root, run_id, fn)


SUITE_RE = re.compile(r"(\d+) (passed|failed|skipped|errors?)")


def run_suite(root):
    """fast_tests.py once, over the whole suite. Returns the gate's suite record."""
    script = _harness(root) / "bin" / "fast_tests.py"
    if not script.is_file():
        return {"exit": None, "summary": "no fast_tests.py under this root"}
    t0 = time.monotonic()
    env = dict(os.environ)
    env["CLAUDE_HARNESS_AGENT_ID"] = RUNNER
    cp = subprocess.run([sys.executable, str(script)], cwd=str(resolve_root(root)), env=env,
                        universal_newlines=True, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT)
    lines = [l for l in cp.stdout.strip().splitlines() if l.strip()]
    last = lines[-1] if lines else ""
    counts = {}
    for n, k in SUITE_RE.findall(last):
        counts["errors" if k.startswith("error") else k] = int(n)
    return {"exit": cp.returncode, "summary": _redact(last[:300]), "counts": counts,
            "seconds": round(time.monotonic() - t0, 1)}


def _redact(text):
    home = str(Path.home())
    return text.replace(home, "~") if home and home != "/" else text


def drive(root, run_id):
    """The body of an agents run: every track in parallel, then the gate."""
    root = resolve_root(root)
    run = read_run(root, run_id)
    recipe = run["recipe"]
    results = {}

    def work(track):
        try:
            results[track["task"]] = run_track(root, run_id, recipe, track)
        except Exception as e:  # one broken track never takes the others down
            results[track["task"]] = "failed: {}".format(type(e).__name__)
        _set_track(root, run_id, track["task"], results[track["task"]])

    threads = [threading.Thread(target=work, args=(t,)) for t in recipe["tracks"]]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    if _stopped(root, run_id):
        return read_run(root, run_id)
    ok = all(v == "done" for v in results.values())
    if recipe.get("gate", True):
        suite = run_suite(root)

        def gate(run):
            if run.get("status") == "stopped":
                return
            run["gate"]["suite"] = suite
            run["gate"]["status"] = "pending"
            run["status"] = "awaiting_operator"
            run["ended"] = hc.now_iso()
        run = update_run(root, run_id, gate)
        _event(root, "flow_gate_ready", run=run_id, suite_exit=suite.get("exit"),
               tracks_done=sum(v == "done" for v in results.values()), tracks=len(results))
    else:
        def end(run):
            if run.get("status") != "stopped":
                run["status"] = "finished" if ok else "failed"
                run["ended"] = hc.now_iso()
        run = update_run(root, run_id, end)
    _event(root, "flow_run_ended", run=run_id, status=run.get("status"))
    return run


# ---------------------------------------------------------------- gate and stop

def gate(root, run_id, decision, note="", via="cli"):
    return od.record_gate_decision(root, run_id, decision, note=note, by=od.OPERATOR, via=via)


def _is_our_driver(pid):
    try:
        os.kill(pid, 0)
    except (OSError, TypeError):
        return False
    try:
        cp = subprocess.run(["ps", "-o", "command=", "-p", str(pid)],
                            universal_newlines=True, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
        return "flow_runner.py" in cp.stdout and "_drive" in cp.stdout
    except OSError:
        return False


def stop(root, run_id):
    """Mark the run stopped, then end its driver and every agent it started."""
    root = resolve_root(root)
    state = {}

    def fn(run):
        if run.get("status") not in ("running",):
            raise Refused("{} is '{}', only a running run can be stopped".format(
                run_id, run.get("status")))
        state["pid"] = run.get("pid")
        run["status"] = "stopped"
        run["ended"] = hc.now_iso()
        for s in run["steps"]:
            if s.get("status") == "running":
                s["status"] = "stopped"
                s["ended"] = hc.now_iso()
    run = update_run(root, run_id, fn)
    pid = state.get("pid")
    killed = False
    if isinstance(pid, int) and hasattr(os, "killpg") and _is_our_driver(pid):
        try:
            os.killpg(pid, signal.SIGTERM)
            killed = True
        except OSError:
            pass
    _event(root, "flow_run_stopped", run=run_id, signalled=killed)
    run["signalled"] = killed
    return run


# ---------------------------------------------------------------- CLI

def _print(obj, as_json):
    if as_json:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    elif isinstance(obj, list):
        for row in obj:
            print("  ".join(str(row.get(k, "")) for k in row))
    elif isinstance(obj, dict):
        for k in ("id", "flow", "mode", "status", "started", "ended"):
            if k in obj:
                print("{:8} {}".format(k, obj[k]))
        for t in obj.get("tracks", []):
            print("track    {} -> {}  {} / {}  {}".format(
                t["task"], t["verify_task"], t["producer"], t["verifier"], t["status"]))
        if obj.get("gate"):
            print("gate     {}  {}".format(obj["gate"].get("status"),
                                           (obj["gate"].get("suite") or {}).get("summary", "")))
    else:
        print(obj)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=None, help="repository root (default: this checkout)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="list flow recipes")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("validate", help="check a recipe")
    p.add_argument("name")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("launch", help="start a run")
    p.add_argument("name")
    p.add_argument("--mode", required=True, choices=("agents", "enqueue"))
    p.add_argument("--foreground", action="store_true", help="drive in this process")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("status", help="runs, or one run")
    p.add_argument("run", nargs="?")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("gate", help="approve or reject a run waiting at its gate")
    p.add_argument("run")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--approve", action="store_true")
    g.add_argument("--reject", action="store_true")
    p.add_argument("--note", default="")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("stop", help="stop a running run")
    p.add_argument("run")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("_drive", help=argparse.SUPPRESS)
    p.add_argument("run")
    a = ap.parse_args(argv)
    root = resolve_root(a.root)
    try:
        if a.cmd == "list":
            _print(list_flows(root), a.json)
        elif a.cmd == "validate":
            problems = validate(root, load_recipe(root, a.name), a.name)
            _print({"name": a.name, "valid": not problems, "problems": problems}, True)
            return 0 if not problems else 2
        elif a.cmd == "launch":
            _print(launch(root, a.name, a.mode, foreground=a.foreground), a.json)
        elif a.cmd == "status":
            _print(read_run(root, a.run) if a.run else list_runs(root), a.json)
        elif a.cmd == "gate":
            _print(gate(root, a.run, "approve" if a.approve else "reject", a.note), a.json)
        elif a.cmd == "stop":
            _print(stop(root, a.run), a.json)
        elif a.cmd == "_drive":
            drive(root, a.run)
    except od.Refused as e:
        print("refused: {}".format(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
