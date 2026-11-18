#!/usr/bin/env python3
"""console.py - the harness console: a local web page over the harness's own tools.
Design T-484 sections 2 and 6. Standard library only, Python 3.9.

    python3 .harness/bin/console.py [--port 8765] [--root R] [--open]

It prints the local URL. --root serves a throwaway root for tests and demos.

SAFETY (design section 2)
  - Binds 127.0.0.1 only, and refuses any request whose Host header is not
    127.0.0.1:<port> or localhost:<port> (DNS rebinding).
  - Every POST and PUT must carry X-Console-Token, a random token minted at start and
    written into the served index.html. A POST whose Origin is another site is refused.
    GET is read-only: it writes nothing on disk (this process and its child tools run
    with bytecode writing switched off).
  - Every write goes through the harness's own tools: operator_desk.py, flow_runner.py,
    blackboard.py. Nothing here edits blackboard.json, roster.json, acts or warrants.
  - It never signs and never reads private keys. It serves files from .harness/ui only.
  - Every JSON response passes redact(): the home directory becomes ~, the OS user name
    becomes <user>, system temp paths become <tmp>.
"""
import sys

sys.dont_write_bytecode = True  # a GET must not leave __pycache__ behind

import argparse  # noqa: E402
import getpass  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import secrets  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import webbrowser  # noqa: E402
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402
from pathlib import Path  # noqa: E402
from urllib.parse import parse_qs, unquote, urlparse  # noqa: E402

import flow_runner as fr  # noqa: E402
import operator_desk as od  # noqa: E402

THIS_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORT = 8765
TOKEN_PLACEHOLDER = "__CONSOLE_TOKEN__"
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
                ".svg": "image/svg+xml"}
MAX_BODY = 256 * 1024
EVENT_TAIL = 200
ACTIVITY_EVENTS = 3000
SOCIETY_TTL = 15.0
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
       "form-action 'none'; frame-ancestors 'none'")


# ---------------------------------------------------------------- redaction

def _redaction_pairs():
    pairs = []
    t = tempfile.gettempdir().rstrip("/")
    if t:
        pairs.append((re.compile(re.escape(t) + r"(?:/[^\s\"']*)?"), "<tmp>"))
    # the system temp roots, with or without the private/ prefix macOS adds
    pairs.append((re.compile(r"(?<![\w.-])/(?:private/)?(?:tmp|var/folders)(?:/[^\s\"']*)?"),
                  "<tmp>"))
    home = str(Path.home()).rstrip("/")
    if home and home != "":
        pairs.append((re.compile(re.escape(home)), "~"))
    try:
        user = getpass.getuser()
    except Exception:
        user = ""
    if user and len(user) >= 3 and user.lower() not in od.GENERIC_USERS:
        pairs.append((re.compile(r"(?<![A-Za-z0-9])" + re.escape(user) + r"(?![A-Za-z0-9])"),
                      "<user>"))
    return pairs


REDACTIONS = _redaction_pairs()


def redact(obj):
    """Every string inside obj with home, user name and temp paths replaced."""
    if isinstance(obj, str):
        for rx, rep in REDACTIONS:
            obj = rx.sub(rep, obj)
        return obj
    if isinstance(obj, dict):
        return {redact(k) if isinstance(k, str) else k: redact(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    return obj


# ---------------------------------------------------------------- readers (no writes)

def _harness(root):
    return Path(root) / ".harness"


def _read_json(path):
    return od._read_json(path)


def board(root):
    data = _read_json(_harness(root) / "blackboard.json") or {}
    tasks = data.get("tasks") if isinstance(data.get("tasks"), dict) else {}
    out, counts = [], {}
    for tid, t in tasks.items():
        if not isinstance(t, dict):
            continue
        status = t.get("status")
        counts[status] = counts.get(status, 0) + 1
        row = {"id": tid, "title": t.get("title"), "status": status, "role": t.get("role"),
               "epic": t.get("epic"), "claimed_by": t.get("claimed_by"),
               "claim_expires_at": t.get("claim_expires_at"),
               "depends_on": t.get("depends_on") or [], "priority": t.get("priority")}
        h = t.get("handoff")
        if isinstance(h, dict):
            row["handoff"] = {"from": h.get("from"), "to_role": h.get("to_role"),
                              "note": str(h.get("note") or "")[:600]}
        if status not in ("done",):
            row["last_note"] = _last_note(root, tid)
        out.append(row)
    out.sort(key=lambda r: _task_num(r["id"]))
    return {"tasks": out, "counts": counts, "updated_at": data.get("updated_at"),
            "updated_by": data.get("updated_by")}


def _task_num(tid):
    m = re.match(r"T-(\d+)", tid or "")
    return int(m.group(1)) if m else 0


def _last_note(root, tid):
    detail = _read_json(_harness(root) / "tasks" / (tid + ".json"))
    notes = (detail or {}).get("notes") if isinstance(detail, dict) else None
    if isinstance(notes, list) and notes:
        n = notes[-1]
        if isinstance(n, dict):
            return {"ts": n.get("ts"), "agent": n.get("agent"),
                    "text": str(n.get("note") or n.get("text") or "")[:600]}
        return {"text": str(n)[:600]}
    return None


def locks(root):
    out = []
    d = _harness(root) / "locks"
    if d.is_dir():
        for p in sorted(d.glob("*.lock")):
            payload = _read_json(p) or {}
            out.append({"path": payload.get("path") or unquote(p.name[:-5]),
                        "holder": payload.get("holder"), "task": payload.get("task"),
                        "acquired_at": payload.get("acquired_at"),
                        "ttl_seconds": payload.get("ttl_seconds"),
                        "expired": od.hc.lock_is_expired(payload)})
    return out


def events_file(root):
    return _harness(root) / "logs" / "events.jsonl"


def read_events(root, since=-1, cap=500):
    """Events after byte offset `since`. since < 0 means the last EVENT_TAIL lines.
    Returns {"next": offset, "events": [...]}."""
    p = events_file(root)
    try:
        size = p.stat().st_size
    except OSError:
        return {"next": 0, "events": []}
    if since is None or since < 0 or since > size:
        start = max(0, size - 400 * EVENT_TAIL)
        tail = True
    else:
        start, tail = since, False
    with open(str(p), "rb") as fh:
        fh.seek(start)
        data = fh.read(size - start)
    lines = data.split(b"\n")
    if tail and start > 0:
        lines = lines[1:]  # the first piece may be a partial line
    if lines and lines[-1] != b"":
        consumed = size - len(lines[-1])
        lines = lines[:-1]
    else:
        consumed = size
    evs = []
    for raw in lines:
        try:
            e = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            continue
        if isinstance(e, dict):
            evs.append(e)
    if tail:
        evs = evs[-EVENT_TAIL:]
    return {"next": consumed, "events": evs[-cap:]}


def actor(e):
    """Whose act an event records: the holder, the handing-off agent or the step's agent
    when the event names one, else the ambient agent that logged it."""
    for k in ("holder", "from_agent", "step_agent"):
        v = e.get(k)
        if isinstance(v, str) and v:
            return v
    return e.get("agent")


def activity(root):
    """One entry per agent name for the tooltips: what that agent is doing right now."""
    agents = {}

    def entry(name):
        return agents.setdefault(name, {"name": name, "task": None, "role": None,
                                        "step": None, "since": None, "last_action": None,
                                        "last_note": None, "tests_run": None, "locks": [],
                                        "source": []})
    b = _read_json(_harness(root) / "blackboard.json") or {}
    for tid, t in (b.get("tasks") or {}).items():
        if isinstance(t, dict) and t.get("claimed_by") and t.get("status") in (
                "claimed", "in_progress", "blocked"):
            a = entry(t["claimed_by"])
            a.update(task=tid, role=t.get("role"), step=t.get("status"))
            a["last_note"] = _last_note(root, tid)
            if "board" not in a["source"]:
                a["source"].append("board")
    for run in fr.list_runs(root):
        if run.get("status") != "running":
            continue
        full = _read_json(fr.runs_dir(root) / run["id"] / "run.json") or {}
        for s in full.get("steps") or []:
            if s.get("status") == "running":
                a = entry(s.get("agent"))
                a.update(task=s.get("track"), role=s.get("role"), since=s.get("started"),
                         step="{} {}".format(s.get("role"), s.get("round")))
                a["run"] = run["id"]
                if "run" not in a["source"]:
                    a["source"].append("run")
    for lk in locks(root):
        if lk["holder"] and not lk["expired"]:
            a = entry(lk["holder"])
            a["locks"].append(lk["path"])
            if "locks" not in a["source"]:
                a["source"].append("locks")
    recent = read_events(root, -1, cap=ACTIVITY_EVENTS)["events"]
    for e in recent:
        name = actor(e)
        if not name:
            continue
        if name not in agents and e.get("event") not in ("task_claimed", "lock_acquired",
                                                         "flow_step_started", "tests_run"):
            continue
        a = entry(name)
        if e.get("event") == "tests_run":
            a["tests_run"] = {k: e.get(k) for k in ("ts", "file_count", "counts", "seconds",
                                                    "ok", "changed")}
        a["last_action"] = {k: e.get(k) for k in ("ts", "event", "task", "path", "status",
                                                  "to_role", "id", "state", "role")
                            if e.get(k) is not None}
        if "events" not in a["source"]:
            a["source"].append("events")
    out = sorted(agents.values(), key=lambda a: (a["task"] is None, a["name"] or ""))
    return {"agents": out}


# ---------------------------------------------------------------- society (cached)

_SOCIETY = {"at": 0.0, "root": None, "data": None}
_SOCIETY_LOCK = threading.Lock()


def _tool_json(root, argv):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("CLAUDE_HARNESS_AGENT_ID", None)
    try:
        cp = subprocess.run([sys.executable] + argv, cwd=str(root), env=env, timeout=60,
                            universal_newlines=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    if cp.returncode != 0:
        return None, (cp.stderr or cp.stdout).strip()[-300:]
    try:
        return json.loads(cp.stdout), None
    except ValueError:
        return cp.stdout.strip(), None


def society(root):
    with _SOCIETY_LOCK:
        if _SOCIETY["root"] == str(root) and time.time() - _SOCIETY["at"] < SOCIETY_TTL:
            return _SOCIETY["data"]
    bin_dir = ".harness/bin/"
    out = {"problems": []}
    roster, err = _tool_json(root, [bin_dir + "roster.py", "roster", "--json"])
    if err:
        out["problems"].append("roster: " + err)
    out["roster"] = roster if isinstance(roster, dict) else {}
    forks, err = _tool_json(root, [bin_dir + "attest.py", "forks"])
    if err:
        out["problems"].append("forks: " + err)
    out["forks"] = forks if isinstance(forks, list) else []
    cases, err = _tool_json(root, [bin_dir + "precedent.py", "case", "list", "--json"])
    if err:
        out["problems"].append("cases: " + err)
    out["cases"] = []
    for c in cases if isinstance(cases, list) else []:
        words, _ = _tool_json(root, [bin_dir + "precedent.py", "case", "show", str(c.get("id"))])
        c = dict(c)
        c["in_words"] = words if isinstance(words, str) else None
        out["cases"].append(c)
    precs, err = _tool_json(root, [bin_dir + "precedent.py", "list", "--json"])
    if err:
        out["problems"].append("precedents: " + err)
    out["precedents"] = [{k: p.get(k) for k in ("id", "title", "authority_tier", "status",
                                                "subject", "force", "confirmation_status")}
                         for p in (precs if isinstance(precs, list) else [])]
    warrants = []
    wd = _harness(root) / "warrants"
    for p in sorted(wd.glob("W-*.json")) if wd.is_dir() else []:
        w = _read_json(p) or {}
        warrants.append({"id": w.get("warrant_id") or p.stem, "epic": w.get("epic"),
                         "issued_at": w.get("issued_at"),
                         "signature_file": (p.parent / (p.name + ".sig")).is_file()})
    out["warrants"] = warrants
    acts = []
    ad = _harness(root) / "acts"
    for d in sorted(x for x in ad.iterdir() if x.is_dir()) if ad.is_dir() else []:
        files = sorted(d.glob("[0-9]*.json"))
        kinds = {}
        last = None
        for f in files:
            a = _read_json(f) or {}
            k = a.get("kind") or "?"
            kinds[k] = kinds.get(k, 0) + 1
            last = a
        acts.append({"name": d.name, "count": len(files), "kinds": kinds,
                     "last_kind": (last or {}).get("kind"), "last_ts": (last or {}).get("ts"),
                     "retractions": kinds.get("retraction", 0) + kinds.get("retract", 0),
                     "contracts": kinds.get("commit", 0)})
    out["acts"] = acts
    with _SOCIETY_LOCK:
        _SOCIETY.update(at=time.time(), root=str(root), data=out)
    return out


# ---------------------------------------------------------------- operator view

def operator_view(root):
    cards, problems = od.decisions(root, "all")
    b = board(root)
    review = [t for t in b["tasks"] if t["status"] == "review"]
    gates = [r for r in fr.list_runs(root) if r.get("status") == "awaiting_operator"]
    for g in gates:
        full = _read_json(fr.runs_dir(root) / g["id"] / "run.json") or {}
        g["gate"] = full.get("gate")
        g["tracks"] = full.get("tracks")
    signatures = []
    wd = _harness(root) / "warrants"
    for p in sorted(wd.glob("W-*.json")) if wd.is_dir() else []:
        if not (p.parent / (p.name + ".sig")).is_file():
            signatures.append(signature_card(p))
    try:
        tracked, untracked = od.pending_change_set(root)
        stat = od._stat_text(root, untracked)
        branch = od._branch(root)
    except Exception as e:  # not a git checkout, or git missing
        tracked, untracked, stat, branch = [], [], "git: {}".format(type(e).__name__), None
    return {"decisions": cards, "decision_problems": problems, "review": review,
            "gates": gates, "signatures": signatures, "branch": branch,
            "pending": {"tracked": len(tracked), "untracked": len(untracked), "stat": stat}}


def signature_card(path):
    """The operator's commands for an unsigned warrant, as text to copy. The console
    runs neither: signing happens on the operator's terminal, with the operator's key."""
    try:
        import warrant as wr
        env, key, ns = wr.SIGN_ENV, wr.ROOT_KEY, wr.NAMESPACE
    except Exception:
        env, key, ns = "SSH_AUTH_SOCK= ", "<operator key>", "harness-warrant"
    rel = ".harness/warrants/" + path.name
    return {"what": "warrant " + path.stem,
            "commands": ["{}ssh-keygen -Y sign -f {} -n {} {}".format(env, key, ns, rel),
                         "python3 .harness/bin/warrant.py apply --warrant " + path.stem],
            "note": "unsigned draft"}


def run_detail(root, run_id):
    run = fr.read_run(root, run_id)
    run = dict(run)
    run.pop("pid", None)
    last = {}
    for e in read_events(root, -1, cap=ACTIVITY_EVENTS)["events"]:
        name = actor(e)
        if name:
            last[name] = {k: e.get(k) for k in ("ts", "event", "task", "path", "status")
                          if e.get(k) is not None}
    for s in run.get("steps") or []:
        s["last_action"] = last.get(s.get("agent"))
    return run


def waves_chart(root):
    """Minutes per wave: the measured baseline shipped with the page, then every run."""
    base = _read_json(_harness(root) / "ui" / "waves-measured.json") or {}
    rows = list(base.get("waves") or [])
    for r in reversed(fr.list_runs(root)):
        if r.get("mode") != "agents" or not r.get("started") or not r.get("ended"):
            continue
        a, b = od.hc.parse_iso(r["started"]), od.hc.parse_iso(r["ended"])
        if a and b:
            rows.append({"label": r["id"], "label_es": r["id"],
                         "minutes": round((b - a).total_seconds() / 60, 1),
                         "kind": "run", "status": r.get("status")})
    return {"waves": rows, "source": base.get("source"),
            "target_minutes": base.get("target_minutes")}


# ---------------------------------------------------------------- writes (token)

def next_task_id(root):
    data = _read_json(_harness(root) / "blackboard.json") or {}
    nums = [_task_num(t) for t in (data.get("tasks") or {})]
    return "T-{:03d}".format((max(nums) if nums else 0) + 1)


def add_task(root, body):
    title = str(body.get("title") or "").strip()
    if not title:
        raise od.Refused("a task needs a title")
    tid = str(body.get("id") or "").strip() or next_task_id(root)
    if not od.TASK_ID.match(tid):
        raise od.Refused("not a task id: {!r}".format(tid))
    role = str(body.get("role") or "worker")
    if role not in ("worker", "verifier", "thinker"):
        raise od.Refused("role must be worker, verifier or thinker")
    desc = str(body.get("description") or "")
    epic = str(body.get("epic") or "")
    deps = body.get("depends_on") or []
    if isinstance(deps, str):
        deps = [d.strip() for d in deps.split(",") if d.strip()]
    if not all(isinstance(d, str) and od.TASK_ID.match(d) for d in deps):
        raise od.Refused("depends_on must be task ids")
    hits = od.scan_text(" ".join([title, desc, epic]), "task")
    if hits:
        raise od.Refused("the task would publish a leak ({})".format(od._format_hits(hits)))
    argv = [sys.executable, str(_harness(root) / "bin" / "blackboard.py"), "add-task",
            "--agent", od.OPERATOR, "--id", tid, "--title", title, "--role", role]
    if desc:
        argv += ["--description", desc]
    if epic:
        argv += ["--epic", epic]
    for d in deps:
        argv += ["--depends-on", d]
    env = dict(os.environ)
    env["CLAUDE_HARNESS_AGENT_ID"] = od.OPERATOR
    cp = subprocess.run(argv, cwd=str(root), env=env, universal_newlines=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if cp.returncode != 0:
        raise od.Refused("blackboard refused: " + (cp.stderr or cp.stdout).strip()[-300:])
    return {"id": tid, "output": cp.stdout.strip()}


def git_commit(root, body):
    message = str(body.get("message") or "").strip()
    if not message:
        raise od.Refused("a commit needs a message")
    fd, path = tempfile.mkstemp(prefix="console-commit-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(message + "\n")
        stat = []
        result = od.commit(root, path, dry_run=bool(body.get("dry_run")),
                           stat_out=stat.append)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return {"stat": stat[0] if stat else None, "result": result}


def git_push(root, body):
    stat = []
    result = od.push(root, dry_run=bool(body.get("dry_run")), stat_out=stat.append)
    return {"stat": stat[0] if stat else None, "result": result}


# ---------------------------------------------------------------- HTTP

class BadRequest(Exception):
    pass


ROUTE_ID = r"([A-Za-z0-9][A-Za-z0-9._-]{0,127})"
POST_ROUTES = [
    (re.compile(r"^/api/tasks$"), lambda root, b: add_task(root, b)),
    (re.compile(r"^/api/tasks/(T-\d{3,})/verdict$"),
     lambda root, b, t: od.verdict(root, t, str(b.get("outcome")), str(b.get("note") or ""))),
    (re.compile(r"^/api/decisions/(D-\d{3,})/rule$"),
     lambda root, b, d: od.rule(root, d, str(b.get("choice")), str(b.get("note") or ""),
                                via="console")),
    (re.compile(r"^/api/flows/([a-z0-9][a-z0-9-]{0,63})/validate$"),
     lambda root, b, n: {"problems": fr.validate(root, b.get("recipe"), n)}),
    (re.compile(r"^/api/flows/([a-z0-9][a-z0-9-]{0,63})/launch$"),
     lambda root, b, n: fr.launch(root, n, str(b.get("mode")), by=od.OPERATOR)),
    (re.compile(r"^/api/runs/" + ROUTE_ID + r"/gate$"),
     lambda root, b, r: fr.gate(root, r, str(b.get("decision")), str(b.get("note") or ""),
                                via="console")),
    (re.compile(r"^/api/runs/" + ROUTE_ID + r"/stop$"), lambda root, b, r: fr.stop(root, r)),
    (re.compile(r"^/api/git/commit$"), lambda root, b: git_commit(root, b)),
    (re.compile(r"^/api/git/push$"), lambda root, b: git_push(root, b)),
]
PUT_ROUTES = [
    (re.compile(r"^/api/flows/([a-z0-9][a-z0-9-]{0,63})$"),
     lambda root, b, n: fr.save_recipe(root, n, b.get("recipe"))),
]


def get_route(root, path, query):
    if path == "/api/board":
        return board(root)
    if path == "/api/locks":
        return {"locks": locks(root)}
    if path == "/api/events":
        try:
            since = int((query.get("since") or ["-1"])[0])
        except ValueError:
            raise BadRequest("since must be a whole number")
        return read_events(root, since)
    if path == "/api/activity":
        return activity(root)
    if path == "/api/society":
        return society(root)
    if path == "/api/decisions":
        cards, problems = od.decisions(root, "all")
        return {"decisions": cards, "problems": problems}
    if path == "/api/operator":
        return operator_view(root)
    if path == "/api/flows":
        return {"flows": fr.list_flows(root)}
    m = re.match(r"^/api/flows/([a-z0-9][a-z0-9-]{0,63})$", path)
    if m:
        recipe = fr.load_recipe(root, m.group(1))
        return {"recipe": recipe, "problems": fr.validate(root, recipe, m.group(1))}
    if path == "/api/runs":
        return {"runs": fr.list_runs(root)}
    m = re.match(r"^/api/runs/" + ROUTE_ID + "$", path)
    if m:
        return run_detail(root, m.group(1))
    if path == "/api/charts/waves":
        return waves_chart(root)
    if path == "/api/close-report":
        report, err = _tool_json(root, [".harness/bin/close_checks.py", "--json", "epic-close"])
        return {"report": report if isinstance(report, dict) else None, "problem": err}
    return None


def watched_state(root):
    """(mtime, size) of everything a `changed` ping reports on. Read-only stat calls."""
    h = _harness(root)
    out = {}
    for name, paths in (("board", [h / "blackboard.json"]),
                        ("runs", list((h / "runs").glob("*/run.json"))),
                        ("decisions", list((h / "decisions").glob("D-*.json")) +
                         list((h / "rulings").glob("R-*.json"))),
                        ("flows", list((h / "flows").glob("*.json"))),
                        ("locks", list((h / "locks").glob("*.lock")))):
        sig = []
        for p in sorted(paths):
            try:
                st = p.stat()
                sig.append((p.name, st.st_mtime_ns, st.st_size))
            except OSError:
                pass
        out[name] = tuple(sig)
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "HarnessConsole/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quiet: the event log is the record
        pass

    # ---- checks
    def _host_ok(self):
        port = self.server.server_address[1]
        return self.headers.get("Host") in ("127.0.0.1:{}".format(port),
                                            "localhost:{}".format(port))

    def _origin_ok(self):
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        port = self.server.server_address[1]
        return origin in ("http://127.0.0.1:{}".format(port),
                          "http://localhost:{}".format(port))

    def _token_ok(self):
        given = self.headers.get("X-Console-Token") or ""
        return secrets.compare_digest(given, self.server.token)

    # ---- replies
    def _headers(self, code, ctype, length):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()

    def _json(self, code, obj):
        data = json.dumps(redact(obj), ensure_ascii=False).encode("utf-8")
        self._headers(code, "application/json; charset=utf-8", len(data))
        self.wfile.write(data)

    def _error(self, code, reason, kind="error"):
        self._json(code, {"error": kind, "reason": reason})

    # ---- GET
    def do_GET(self):
        if not self._host_ok():
            return self._error(403, "Host header must be 127.0.0.1 or localhost", "forbidden")
        url = urlparse(self.path)
        path = unquote(url.path)
        root = self.server.root
        try:
            if path in ("/", "/index.html"):
                return self._index()
            if path.startswith("/ui/"):
                return self._static(path[len("/ui/"):])
            if path == "/api/stream":
                return self._stream()
            obj = get_route(root, path, parse_qs(url.query))
            if obj is None:
                return self._error(404, "no such route", "not_found")
            return self._json(200, obj)
        except od.Refused as e:
            return self._error(404, str(e), "refused")
        except BadRequest as e:
            return self._error(400, str(e), "bad_request")
        except (BrokenPipeError, ConnectionResetError):
            return None
        except Exception as e:
            return self._error(500, type(e).__name__)

    def _index(self):
        p = self.server.ui_dir / "index.html"
        try:
            html = p.read_text(encoding="utf-8")
        except OSError:
            return self._error(404, "the page is missing", "not_found")
        data = html.replace(TOKEN_PLACEHOLDER, self.server.token).encode("utf-8")
        self._headers(200, STATIC_TYPES[".html"], len(data))
        self.wfile.write(data)

    def _static(self, rel):
        ui = self.server.ui_dir.resolve()
        if not rel or rel.startswith("/") or "\\" in rel or "\0" in rel:
            return self._error(404, "no such file", "not_found")
        target = (ui / rel).resolve()
        try:
            target.relative_to(ui)
        except ValueError:
            return self._error(404, "no such file", "not_found")
        ext = target.suffix.lower()
        if ext not in STATIC_TYPES or not target.is_file():
            return self._error(404, "no such file", "not_found")
        data = target.read_bytes()
        if ext == ".html":
            data = data.replace(TOKEN_PLACEHOLDER.encode(), b"")
        self._headers(200, STATIC_TYPES[ext], len(data))
        self.wfile.write(data)

    def _stream(self):
        """Server-Sent Events: new event-log lines as `events`, and a `changed` ping
        naming what moved (board, runs, decisions, flows, locks). Polled once a second."""
        root = self.server.root
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        offset = read_events(root, -1, cap=0)["next"]
        state = watched_state(root)
        last_beat = time.monotonic()
        try:
            self.wfile.write(b"retry: 2000\n\n")
            self.wfile.flush()
            while not self.server.stopping.is_set():
                time.sleep(self.server.poll)
                got = read_events(root, offset)
                offset = got["next"]
                if got["events"]:
                    self._send("events", {"events": got["events"]})
                now = watched_state(root)
                moved = sorted(k for k in now if now[k] != state.get(k))
                state = now
                if moved:
                    self._send("changed", {"what": moved})
                if time.monotonic() - last_beat > 15:
                    self.wfile.write(b": beat\n\n")
                    self.wfile.flush()
                    last_beat = time.monotonic()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return None

    def _send(self, kind, obj):
        data = json.dumps(redact(obj), ensure_ascii=False)
        self.wfile.write("event: {}\ndata: {}\n\n".format(kind, data).encode("utf-8"))
        self.wfile.flush()

    # ---- POST / PUT
    def do_POST(self):
        self._write(POST_ROUTES)

    def do_PUT(self):
        self._write(PUT_ROUTES)

    def _write(self, routes):
        if not self._host_ok():
            return self._error(403, "Host header must be 127.0.0.1 or localhost", "forbidden")
        if not self._origin_ok():
            return self._error(403, "cross-site request", "forbidden")
        if not self._token_ok():
            return self._error(403, "missing or wrong X-Console-Token", "forbidden")
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if ctype != "application/json":
            return self._error(415, "send application/json", "bad_request")
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            return self._error(400, "bad Content-Length", "bad_request")
        if length < 0 or length > MAX_BODY:
            return self._error(413, "body too large", "bad_request")
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except ValueError:
            return self._error(400, "body is not JSON", "bad_request")
        if not isinstance(body, dict):
            return self._error(400, "body must be a JSON object", "bad_request")
        path = unquote(urlparse(self.path).path)
        for rx, fn in routes:
            m = rx.match(path)
            if m:
                try:
                    with self.server.write_lock:
                        out = fn(self.server.root, body, *m.groups())
                    return self._json(200, {"ok": True, "result": out})
                except od.Refused as e:
                    return self._error(409, str(e), "refused")
                except Exception as e:
                    return self._error(500, type(e).__name__)
        return self._error(404, "no such route", "not_found")


class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, root, port=DEFAULT_PORT, poll=1.0, token=None):
        self.root = Path(root).resolve()
        self.ui_dir = _harness(self.root) / "ui"
        if not self.ui_dir.is_dir():  # a throwaway root without a page serves this one
            self.ui_dir = _harness(THIS_ROOT) / "ui"
        self.token = token or secrets.token_urlsafe(24)
        self.poll = poll
        self.stopping = threading.Event()
        self.write_lock = threading.Lock()
        super().__init__(("127.0.0.1", port), Handler)

    def shutdown(self):
        self.stopping.set()
        super().shutdown()


def main(argv=None):
    ap = argparse.ArgumentParser(description="the harness console, on 127.0.0.1 only")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--root", default=None, help="repository root (default: this checkout)")
    ap.add_argument("--open", action="store_true", help="open the page in the browser")
    a = ap.parse_args(argv)
    root = od.resolve_root(a.root) if a.root else THIS_ROOT
    try:
        srv = ConsoleServer(root, a.port)
    except OSError as e:
        print("console: cannot listen on 127.0.0.1:{} ({})".format(a.port, e), file=sys.stderr)
        return 1
    url = "http://127.0.0.1:{}/".format(srv.server_address[1])
    print("harness console: {}  (Ctrl-C stops it)".format(url), flush=True)
    if a.open:
        webbrowser.open(url)
    try:
        srv.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        srv.stopping.set()
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
