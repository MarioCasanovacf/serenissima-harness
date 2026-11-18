#!/usr/bin/env python3
"""operator_desk.py - what waits on the operator: decisions, rulings, verdicts, wave gates,
commit and push. Design T-484 sections 3 and 5. Standard library only, Python 3.9.

    operator_desk.py [--root R] decisions [--json] [--status open|ruled|all]
    operator_desk.py [--root R] rule <D-id> --choice C [--note N]
    operator_desk.py [--root R] verdict <T-id> (--done | --open) [--note N]
    operator_desk.py [--root R] gate <run-id> (--approve | --reject) [--note N]
    operator_desk.py [--root R] commit --message-file F [--dry-run]
    operator_desk.py [--root R] push [--remote NAME] [--dry-run]

R is the repository root (the directory that holds .harness). Default: the root this
file lives in. Exit codes: 0 done, 2 refused (a rule said no, nothing was changed),
1 error.

WHAT EACH VERB WRITES
  rule     one NEW file .harness/rulings/R-NNN.json (created with link(2), so it can never
           replace a ruling that exists) and then flips the card's status to `ruled`. The
           dated records (operator-rulings-*.md, coordinator-decisions-*) are never opened.
  verdict  runs `blackboard.py update` as the agent `operator`, only on a task in `review`,
           and refuses when `operator` is that task's producer (handoff.from). Nothing
           here touches blackboard.json.
  gate     record_gate_decision(): the one function that writes a wave gate's decision into
           .harness/runs/<run-id>/run.json. flow_runner.py calls the same function from
           its own `gate` verb, so the two entry points cannot drift.
  commit   leak scan, then the diff stat, then `git add -A` (the .gitignore is honoured)
           and `git commit -F -` of the exact message bytes that were scanned.
  push     leak scan of every commit that would leave the machine, then the stat, then
           `git push <remote> refs/heads/<branch>:refs/heads/<branch>` for the CURRENT
           branch only. Never main or master, never a force flag, never `+` in the refspec,
           never --tags, --mirror or --all. A diverged remote is refused by git itself.

THE LEAK SCAN. LEAK_PATTERNS is the single list of patterns; tests pin it. It looks at
added lines only (an old line that was already public is not this commit's doing), at
the full text of new untracked files, at the commit message and at file paths. Patterns
for absolute home and temp paths, key blocks, tokens and emoji are generic. The OS user
name and home directory of the machine running the scan are added at run time
(runtime_literals), and the operator can add terms that must never ship, such as the
names of sibling projects, through the environment variable HARNESS_LEAK_TERMS
(comma-separated) or --extra-term; those terms are never written in this repository.
"""
import argparse
import contextlib
import getpass
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import harness_common as hc
import portalock

THIS_ROOT = Path(__file__).resolve().parents[2]

OPERATOR = "operator"
PROTECTED_BRANCHES = ("main", "master")
LEAK_TERMS_ENV = "HARNESS_LEAK_TERMS"
# Account names that are ordinary words; matching them would flag prose, not a person.
GENERIC_USERS = frozenset(["root", "user", "admin", "runner", "ubuntu", "debian", "docker",
                           "build", "test", "tester", "agent", "guest", "vagrant", "node"])
MAX_SCAN_BYTES = 5 * 1024 * 1024

DECISION_ID = re.compile(r"^D-\d{3,}$")
RULING_ID = re.compile(r"^R-\d{3,}$")
TASK_ID = re.compile(r"^T-\d{3,}$")
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
REMOTE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
BRANCH_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")

# (name, regex). Held here and nowhere else; test_operator_desk.py pins the names and
# one positive and one negative sample for each.
LEAK_PATTERNS = (
    ("home-path-macos", re.compile(r"/Users/[A-Za-z0-9._-]+/")),
    ("home-path-linux", re.compile(r"/home/[A-Za-z0-9._-]+/")),
    ("home-path-windows", re.compile(r"[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\")),
    ("temp-path", re.compile(r"(?<![\w<.-])/(?:private/)?(?:tmp|var/folders)/")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("chat-bot-token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")),
    ("api-key", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{36,})\b")),
    ("emoji", re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")),
)

# Paths that must never be part of a commit made from the console.
PRIVATE_PATH_PATTERNS = (
    ("private-material-path", re.compile(r"(^|/)\.harness/keys(/|$)")),
    ("private-material-path", re.compile(r"(^|/)\.harness/notify_config\.json$")),
    ("private-material-path", re.compile(r"(^|/)id_(?:rsa|ed25519|ecdsa|dsa)$")),
    ("private-material-path", re.compile(r"\.pem$")),
    ("private-material-path", re.compile(r"(^|/)\.env(\.|$)")),
)


class Refused(Exception):
    """A rule said no. Nothing was changed."""


# ---------------------------------------------------------------- plumbing

def resolve_root(root=None):
    """Repository root as a Path. Accepts the root itself or its .harness directory."""
    r = Path(root).resolve() if root else THIS_ROOT
    if r.name == ".harness" and not (r / ".harness").is_dir():
        r = r.parent
    return r


def _harness(root):
    return resolve_root(root) / ".harness"


def _now():
    return hc.now_iso()


def _event(root, kind, **fields):
    rec = {"ts": _now(), "event": kind, "agent": OPERATOR}
    rec.update(fields)
    try:
        hc.append_jsonl(_harness(root) / "logs" / "events.jsonl", rec)
    except OSError:
        pass  # observability never blocks the act


@contextlib.contextmanager
def _flock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "a") as fh:
        portalock.lock_ex(fh)
        try:
            yield
        finally:
            portalock.unlock(fh)


def _write_json_exclusive(path, data):
    """Create `path` with `data` atomically, failing with FileExistsError if it exists."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.link(tmp, str(path))  # raises FileExistsError rather than replacing
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _read_json(path):
    try:
        with open(str(path), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _git(root, *args, **kw):
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    cp = subprocess.run(["git", "-C", str(resolve_root(root))] + list(args),
                        input=kw.get("input"), env=env, universal_newlines=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return cp


def _git_ok(root, *args, **kw):
    cp = _git(root, *args, **kw)
    if cp.returncode != 0:
        raise Refused("git {} failed: {}".format(args[0], (cp.stderr or cp.stdout).strip()[:300]))
    return cp.stdout


# ---------------------------------------------------------------- leak scan

def runtime_literals(extra=()):
    """Literals that are leaks on THIS machine: the OS user name and the home directory,
    plus operator-supplied terms. Computed at scan time, never stored in the repository."""
    out = []
    home = os.path.expanduser("~")
    if home and home not in ("~", "/"):
        out.append(("home-directory", home))
    try:
        user = getpass.getuser()
    except Exception:
        user = ""
    if user and len(user) >= 4 and user.lower() not in GENERIC_USERS:
        out.append(("os-username", user))
    terms = [t.strip() for t in os.environ.get(LEAK_TERMS_ENV, "").split(",")]
    terms += [t.strip() for t in (extra or ())]
    for t in terms:
        if len(t) >= 3:
            out.append(("operator-term", t))
    return out


def scan_text(text, where, extra=()):
    """Return [{where, line, rule}] for every leak in `text`. Never echoes the match."""
    hits = []
    literals = runtime_literals(extra)
    word_literals = []
    for name, lit in literals:
        if name == "home-directory":
            word_literals.append((name, re.compile(re.escape(lit))))
        else:
            word_literals.append((name, re.compile(r"(?<![A-Za-z0-9])" + re.escape(lit)
                                                   + r"(?![A-Za-z0-9])", re.I)))
    for i, line in enumerate(text.splitlines(), 1):
        for name, rx in LEAK_PATTERNS:
            if rx.search(line):
                hits.append({"where": where, "line": i, "rule": name})
        for name, rx in word_literals:
            if rx.search(line):
                hits.append({"where": where, "line": i, "rule": name})
    return hits


def scan_path_name(path, extra=()):
    hits = []
    for name, rx in PRIVATE_PATH_PATTERNS:
        if rx.search(path):
            hits.append({"where": path, "line": 0, "rule": name})
    hits += scan_text(path, path, extra)
    return hits


def _added_lines(diff_text):
    """Added lines of a unified diff, with the file each belongs to: [(file, text)]."""
    cur, out = None, []
    for ln in diff_text.splitlines():
        if ln.startswith("+++ "):
            cur = ln[4:]
            cur = cur[2:] if cur.startswith("b/") else cur
        elif ln.startswith("+") and not ln.startswith("+++"):
            out.append((cur or "?", ln[1:]))
    return out


def _scan_added(diff_text, extra=()):
    hits = []
    grouped = {}
    for f, t in _added_lines(diff_text):
        grouped.setdefault(f, []).append(t)
    for f, lines in grouped.items():
        hits += scan_text("\n".join(lines), f, extra)
    return hits


def _format_hits(hits):
    seen, parts = set(), []
    for h in hits:
        key = (h["where"], h["rule"])
        if key in seen:
            continue
        seen.add(key)
        parts.append("{} ({})".format(h["where"], h["rule"]))
    return "; ".join(parts[:12]) + (" ..." if len(parts) > 12 else "")


# ---------------------------------------------------------------- decisions and rulings

def _decisions_dir(root):
    return _harness(root) / "decisions"


def _rulings_dir(root):
    return _harness(root) / "rulings"


def _list_rulings(root):
    out = []
    d = _rulings_dir(root)
    if d.is_dir():
        for p in sorted(d.glob("R-*.json")):
            r = _read_json(p)
            if isinstance(r, dict) and RULING_ID.match(str(r.get("id", ""))):
                out.append(r)
    return out


def _card_problem(card):
    if not isinstance(card, dict):
        return "not a JSON object"
    for k in ("id", "title", "question", "options", "status"):
        if k not in card:
            return "missing key '{}'".format(k)
    if not DECISION_ID.match(str(card["id"])):
        return "bad id"
    if not isinstance(card["options"], list) or not card["options"] \
            or not all(isinstance(o, str) and o for o in card["options"]):
        return "options must be a non-empty list of strings"
    return None


def decisions(root=None, status="all"):
    """Cards in id order, each with `ruling` (the R record, or None). A card file that
    does not parse is listed under 'problems' by the CLI, never silently dropped."""
    rulings = {}
    for r in _list_rulings(root):
        rulings.setdefault(r.get("decision"), r)
    cards, problems = [], []
    d = _decisions_dir(root)
    if d.is_dir():
        for p in sorted(d.glob("D-*.json")):
            card = _read_json(p)
            why = _card_problem(card)
            if why:
                problems.append({"file": p.name, "problem": why})
                continue
            card = dict(card)
            card["ruling"] = rulings.get(card["id"])
            if status in ("all", None) or card.get("status") == status:
                cards.append(card)
    return cards, problems


def _next_ruling_id(root):
    nums = [int(r["id"][2:]) for r in _list_rulings(root)]
    return "R-{:03d}".format((max(nums) if nums else 0) + 1)


def rule(root, decision_id, choice, note="", via="cli"):
    """Rule an open decision. Writes one new R file, then flips the card to `ruled`."""
    root = resolve_root(root)
    if not DECISION_ID.match(str(decision_id)):
        raise Refused("not a decision id: {!r}".format(decision_id))
    if via not in ("cli", "console"):
        raise Refused("via must be cli or console")
    card_path = _decisions_dir(root) / (decision_id + ".json")
    card = _read_json(card_path)
    if card is None:
        raise Refused("no such decision: {}".format(decision_id))
    why = _card_problem(card)
    if why:
        raise Refused("{} is not a valid card: {}".format(decision_id, why))
    existing = [r for r in _list_rulings(root) if r.get("decision") == decision_id]
    if existing:
        if card.get("status") != "ruled":
            _flip_card(card_path, card, existing[0]["id"])  # finish an interrupted ruling
        raise Refused("{} is already ruled by {}".format(decision_id, existing[0]["id"]))
    if card.get("status") != "open":
        raise Refused("{} is '{}', only an open decision can be ruled".format(
            decision_id, card.get("status")))
    if choice not in card["options"]:
        raise Refused("choice {!r} is not one of the options: {}".format(
            choice, ", ".join(card["options"])))
    note = note or ""
    hits = scan_text(note, "note") + scan_text(choice, "choice")
    if hits:
        raise Refused("the note would publish a leak ({}); nothing was written".format(
            _format_hits(hits)))
    for _ in range(50):
        rid = _next_ruling_id(root)
        rec = {"id": rid, "decision": decision_id, "choice": choice, "note": note,
               "ts": _now(), "by": OPERATOR, "via": via}
        try:
            _write_json_exclusive(_rulings_dir(root) / (rid + ".json"), rec)
            break
        except FileExistsError:
            continue  # another ruling took that number; take the next
    else:
        raise Refused("could not allocate a ruling id")
    _flip_card(card_path, card, rid)
    _event(root, "decision_ruled", decision=decision_id, ruling=rid, choice=choice, via=via)
    return rec


def _flip_card(card_path, card, ruling_id):
    new = dict(card)
    new["status"] = "ruled"
    new["ruling"] = ruling_id
    hc.atomic_write_json(card_path, new)


# ---------------------------------------------------------------- operator verdict

def _blackboard_script(root):
    root = resolve_root(root)
    own = root / ".harness" / "bin" / "blackboard.py"
    if own.is_file():
        return own
    sibling = Path(__file__).resolve().parent / "blackboard.py"
    if THIS_ROOT == root and sibling.is_file():
        return sibling
    # A sibling script would act on THIS checkout's board, not on `root`'s.
    raise Refused("no blackboard.py under the given root")


def verdict(root, task_id, outcome, note=""):
    """The operator's verdict on a task in review: outcome 'done' or 'open'."""
    root = resolve_root(root)
    if not TASK_ID.match(str(task_id)):
        raise Refused("not a task id: {!r}".format(task_id))
    if outcome not in ("done", "open"):
        raise Refused("outcome must be done or open")
    note = (note or "").strip()
    if outcome == "open" and not note:
        raise Refused("sending a task back needs a note saying why")
    board = _read_json(_harness(root) / "blackboard.json")
    task = ((board or {}).get("tasks") or {}).get(task_id)
    if task is None:
        raise Refused("unknown task {}".format(task_id))
    if task.get("status") != "review":
        raise Refused("{} is '{}', the operator verdicts only a task in review".format(
            task_id, task.get("status")))
    producer = (task.get("handoff") or {}).get("from")
    if producer == OPERATOR:
        raise Refused("{} was handed off by the operator; the producer cannot verdict "
                      "their own work".format(task_id))
    hits = scan_text(note, "note")
    if hits:
        raise Refused("the note would publish a leak ({}); nothing was changed".format(
            _format_hits(hits)))
    script = _blackboard_script(root)
    cmd = [sys.executable, str(script), "update", task_id, "--status", outcome,
           "--agent", OPERATOR]
    if outcome == "open":
        note = note if note.upper().startswith("REJECTED") else "REJECTED: " + note
    if note:
        cmd += ["--note", note]
    env = dict(os.environ)
    env["CLAUDE_HARNESS_AGENT_ID"] = OPERATOR
    cp = subprocess.run(cmd, cwd=str(root), env=env, universal_newlines=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if cp.returncode != 0:
        raise Refused("blackboard refused: {}".format(
            (cp.stderr or cp.stdout).strip().splitlines()[-1][:300] if (cp.stderr or cp.stdout).strip()
            else "exit {}".format(cp.returncode)))
    after = ((_read_json(_harness(root) / "blackboard.json") or {}).get("tasks") or {}).get(task_id) or {}
    _event(root, "operator_verdict", task=task_id, outcome=outcome, producer=producer)
    return {"task": task_id, "outcome": outcome, "status": after.get("status"),
            "producer": producer, "output": cp.stdout.strip()}


# ---------------------------------------------------------------- wave gate

def run_json_path(root, run_id):
    if not RUN_ID.match(str(run_id)) or run_id in (".", ".."):
        raise Refused("not a run id: {!r}".format(run_id))
    return _harness(root) / "runs" / run_id / "run.json"


def record_gate_decision(root, run_id, decision, note="", by=OPERATOR, via="cli"):
    """Write the operator's decision on a wave gate into run.json (design section 3).

    decision is "approve" or "reject". Allowed only while the run is `awaiting_operator`
    with gate.status `pending`. Sets run.status and gate.status to `approved` or
    `rejected`, and adds gate.decided (ISO time), gate.by, gate.note and gate.via. Every
    other key of run.json, and gate.suite, are kept as they were. The read-modify-write
    runs under an exclusive lock on <run dir>/.run.lock. Returns the updated run dict.
    Raises Refused (nothing written) when a rule says no. flow_runner.py calls this."""
    if decision not in ("approve", "reject"):
        raise Refused("decision must be approve or reject")
    path = run_json_path(root, run_id)
    if not path.is_file():
        raise Refused("no such run: {}".format(run_id))
    note = note or ""
    hits = scan_text(note, "note")
    if hits:
        raise Refused("the note would be stored with a leak ({}); nothing was written".format(
            _format_hits(hits)))
    with _flock(path.parent / ".run.lock"):
        run = _read_json(path)
        if not isinstance(run, dict):
            raise Refused("run.json of {} does not parse".format(run_id))
        gate = run.get("gate")
        if not isinstance(gate, dict):
            raise Refused("{} has no gate".format(run_id))
        if run.get("status") != "awaiting_operator" or gate.get("status") != "pending":
            raise Refused("{} is '{}' with gate '{}'; only a run awaiting the operator "
                          "can be gated".format(run_id, run.get("status"), gate.get("status")))
        final = "approved" if decision == "approve" else "rejected"
        gate["status"] = final
        gate["decided"] = _now()
        gate["by"] = by
        gate["note"] = note
        gate["via"] = via
        run["status"] = final
        run["gate"] = gate
        hc.atomic_write_json(path, run)
    _event(root, "wave_gate_decided", run=run_id, decision=final, via=via)
    return run


# ---------------------------------------------------------------- commit

def _branch(root):
    cp = _git(root, "symbolic-ref", "--short", "-q", "HEAD")
    return cp.stdout.strip() if cp.returncode == 0 else None


def _has_head(root):
    return _git(root, "rev-parse", "--verify", "-q", "HEAD").returncode == 0


def _empty_tree(root):
    return _git_ok(root, "hash-object", "-t", "tree", "--stdin", input="").strip()


def pending_change_set(root):
    """(tracked_changed, untracked) paths of the working tree, ignored files excluded."""
    out = _git_ok(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    tracked, untracked = [], []
    parts = out.split("\0")
    i = 0
    while i < len(parts):
        e = parts[i]
        i += 1
        if len(e) < 4:
            continue
        xy, p = e[:2], e[3:]
        if xy[0] in "RC":
            i += 1  # the original name of a rename follows
        (untracked if xy == "??" else tracked).append(p)
    return tracked, untracked


def _read_scannable(path):
    try:
        size = path.stat().st_size
        if size > MAX_SCAN_BYTES:
            return None, "too large to scan"
        data = path.read_bytes()
    except OSError:
        return None, "unreadable"
    if b"\0" in data[:8192]:
        return "", None  # binary: no text to scan
    return data.decode("utf-8", "replace"), None


def _stat_text(root, untracked):
    base = "HEAD" if _has_head(root) else _empty_tree(root)
    tracked_stat = _git_ok(root, "diff", base, "--stat", "--no-color").rstrip()
    lines = [tracked_stat] if tracked_stat else []
    for p in untracked:
        text, _ = _read_scannable(resolve_root(root) / p)
        n = len(text.splitlines()) if text else 0
        lines.append(" {} | {} (new, untracked)".format(p, n))
    return "\n".join(lines)


def scan_working_tree(root, message="", extra=()):
    """The leak scan commit runs. Returns (hits, stat_text, tracked, untracked)."""
    root = resolve_root(root)
    tracked, untracked = pending_change_set(root)
    hits = []
    for p in tracked + untracked:
        hits += scan_path_name(p, extra)
    base = "HEAD" if _has_head(root) else _empty_tree(root)
    hits += _scan_added(_git_ok(root, "diff", base, "-U0", "--no-color", "--no-ext-diff"), extra)
    for p in untracked:
        text, why = _read_scannable(root / p)
        if why:
            hits.append({"where": p, "line": 0, "rule": "cannot-scan: " + why})
        elif text:
            hits += scan_text(text, p, extra)
    hits += scan_text(message, "commit message", extra)
    return hits, _stat_text(root, untracked), tracked, untracked


def commit(root, message_file, dry_run=False, extra=(), stat_out=None):
    """Scan, show the stat, then commit the whole pending change set."""
    root = resolve_root(root)
    try:
        message = Path(message_file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise Refused("cannot read the message file")
    if not message.strip():
        raise Refused("the commit message is empty")
    tracked, untracked = pending_change_set(root)
    if not tracked and not untracked:
        raise Refused("nothing to commit")
    hits, stat, tracked, untracked = scan_working_tree(root, message, extra)
    if hits:
        _event(root, "operator_commit_refused", rules=sorted({h["rule"] for h in hits}))
        raise Refused("leak scan found {} hit(s), nothing committed: {}".format(
            len(hits), _format_hits(hits)))
    if stat_out:
        stat_out(stat)
    result = {"stat": stat, "files": len(tracked) + len(untracked), "committed": False,
              "branch": _branch(root), "sha": None}
    if dry_run:
        return result
    _git_ok(root, "add", "-A")
    _git_ok(root, "commit", "-F", "-", input=message)
    result["committed"] = True
    result["sha"] = _git_ok(root, "rev-parse", "--short", "HEAD").strip()
    _event(root, "operator_commit", sha=result["sha"], files=result["files"])
    return result


# ---------------------------------------------------------------- push

def build_push_command(remote, branch):
    """The one argv `push` may run. No force, no plus, no tags, no mirror, no all."""
    if not REMOTE_NAME.match(remote or ""):
        raise Refused("not a usable remote name")
    if not BRANCH_NAME.match(branch or "") or ".." in branch or branch.endswith(("/", ".lock")):
        raise Refused("not a usable branch name")
    return ["push", remote, "refs/heads/{0}:refs/heads/{0}".format(branch)]


def _outgoing_range(root, remote, branch):
    """Revision args selecting the commits a push of `branch` would add."""
    tracking = "refs/remotes/{}/{}".format(remote, branch)
    if _git(root, "rev-parse", "--verify", "-q", tracking).returncode == 0:
        return [tracking + "..HEAD"]
    return ["HEAD", "--not", "--remotes={}".format(remote)]


def scan_outgoing(root, remote, branch, extra=()):
    root = resolve_root(root)
    rng = _outgoing_range(root, remote, branch)
    shas = _git_ok(root, "rev-list", "--reverse", *rng).split()
    hits = []
    for sha in shas:
        msg = _git_ok(root, "show", "-s", "--format=%an%n%ae%n%cn%n%ce%n%B", sha)
        hits += [dict(h, where="commit " + sha[:8] + " message") for h in scan_text(msg, "m", extra)]
        diff = _git_ok(root, "show", "--format=", "-U0", "--no-color", "--no-ext-diff", sha)
        hits += [dict(h, where=h["where"] + " @" + sha[:8]) for h in _scan_added(diff, extra)]
        names = _git_ok(root, "show", "--format=", "--name-only", "-z", sha).split("\0")
        for n in names:
            if n:
                hits += [dict(h, where=h["where"] + " @" + sha[:8]) for h in scan_path_name(n, extra)]
    stat = ""
    if shas:
        stat = _git_ok(root, "log", "--stat", "--no-color", "--format=%h %s", "--reverse", *rng).rstrip()
    return hits, stat, shas


def push(root, remote="origin", dry_run=False, extra=(), stat_out=None):
    root = resolve_root(root)
    branch = _branch(root)
    if not branch:
        raise Refused("HEAD is detached; push sends the current branch only")
    if branch in PROTECTED_BRANCHES:
        raise Refused("refusing to push '{}'; the console never pushes it".format(branch))
    cmd = build_push_command(remote, branch)
    if _git(root, "remote", "get-url", remote).returncode != 0:
        raise Refused("no remote named '{}'".format(remote))
    hits, stat, shas = scan_outgoing(root, remote, branch, extra)
    if hits:
        _event(root, "operator_push_refused", rules=sorted({h["rule"] for h in hits}))
        raise Refused("leak scan found {} hit(s) in the commits to push, nothing pushed: {}".format(
            len(hits), _format_hits(hits)))
    if not shas:
        raise Refused("nothing to push: '{}' has no commits the remote lacks".format(branch))
    if stat_out:
        stat_out(stat)
    result = {"branch": branch, "remote": remote, "commits": len(shas), "stat": stat,
              "pushed": False, "output": ""}
    if dry_run:
        return result
    cp = _git(root, *cmd)
    result["output"] = (cp.stdout + cp.stderr).strip()
    if cp.returncode != 0:
        raise Refused("git refused the push: {}".format(result["output"][-300:]))
    result["pushed"] = True
    _event(root, "operator_push", branch=branch, remote=remote, commits=len(shas))
    return result


# ---------------------------------------------------------------- CLI

def _print(obj, as_json):
    if as_json:
        print(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="repository root (default: this checkout)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("decisions", help="list decision cards")
    p.add_argument("--json", action="store_true")
    p.add_argument("--status", default="all", choices=("all", "open", "ruled"))

    p = sub.add_parser("rule", help="rule an open decision")
    p.add_argument("decision")
    p.add_argument("--choice", required=True)
    p.add_argument("--note", default="")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("verdict", help="the operator's verdict on a task in review")
    p.add_argument("task")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--done", action="store_true")
    g.add_argument("--open", action="store_true", dest="reopen")
    p.add_argument("--note", default="")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("gate", help="approve or reject a wave gate")
    p.add_argument("run")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--approve", action="store_true")
    g.add_argument("--reject", action="store_true")
    p.add_argument("--note", default="")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("commit", help="leak scan, then commit the pending change set")
    p.add_argument("--message-file", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--extra-term", action="append", default=[])
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("push", help="leak scan, then push the current branch")
    p.add_argument("--remote", default="origin")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--extra-term", action="append", default=[])
    p.add_argument("--json", action="store_true")

    a = ap.parse_args(argv)
    try:
        if a.cmd == "decisions":
            cards, problems = decisions(a.root, a.status)
            if a.json:
                _print({"decisions": cards, "problems": problems}, True)
            else:
                for c in cards:
                    r = c.get("ruling")
                    tail = ""
                    if isinstance(r, dict):
                        tail = " -> {} ({})".format(r["choice"], r["id"])
                    print("{}  [{}]  {}{}".format(c["id"], c["status"], c["title"], tail))
                for pr in problems:
                    print("problem: {}: {}".format(pr["file"], pr["problem"]))
                if not cards and not problems:
                    print("no decisions")
        elif a.cmd == "rule":
            rec = rule(a.root, a.decision, a.choice, a.note)
            _print(rec, a.json) if a.json else print(
                "{}: {} ruled '{}'".format(rec["id"], rec["decision"], rec["choice"]))
        elif a.cmd == "verdict":
            res = verdict(a.root, a.task, "done" if a.done else "open", a.note)
            _print(res, a.json) if a.json else print(
                "{}: verdict {} (status now {})".format(res["task"], res["outcome"], res["status"]))
        elif a.cmd == "gate":
            run = record_gate_decision(a.root, a.run, "approve" if a.approve else "reject", a.note)
            _print(run, a.json) if a.json else print(
                "{}: gate {}".format(run["id"] if "id" in run else a.run, run["gate"]["status"]))
        elif a.cmd == "commit":
            res = commit(a.root, a.message_file, a.dry_run, a.extra_term,
                         None if a.json else (lambda s: print(s)))
            _print(res, a.json) if a.json else print(
                "committed {}".format(res["sha"]) if res["committed"] else "dry run: scan clean")
        elif a.cmd == "push":
            res = push(a.root, a.remote, a.dry_run, a.extra_term,
                       None if a.json else (lambda s: print(s)))
            _print(res, a.json) if a.json else print(
                "pushed {} to {}".format(res["branch"], res["remote"]) if res["pushed"]
                else "dry run: scan clean, {} commit(s) would go".format(res["commits"]))
    except Refused as e:
        print("refused: {}".format(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
