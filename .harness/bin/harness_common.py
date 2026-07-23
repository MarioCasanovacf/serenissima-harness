"""Shared helpers for the Universal Agent Harness runtime substrate.

All tools under .harness/bin/ are stdlib-only (python3 >= 3.9) and fail-safe:
they must never corrupt shared state. Invariants:
  - Shared JSON files are mutated only through read-modify-write cycles
    serialized by the `guarded()` context manager (an exclusive lock on
    .harness/locks/.guard, via portalock -- POSIX fcntl / Windows msvcrt).
  - NEVER nest `guarded()` blocks (locking a second file handle would deadlock).
  - All JSON writes are atomic (tempfile in the same directory + os.replace).
  - JSONL appends take an exclusive lock on the log file for the write.
"""
import datetime as _dt
import json
import os
import tempfile
from pathlib import Path

import portalock

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / ".harness"
LOCKS = HARNESS / "locks"
LOGS = HARNESS / "logs"
TASKS = HARNESS / "tasks"
BLACKBOARD = HARNESS / "blackboard.json"
STATE = HARNESS / "state.json"
SESSION_HOLDERS = HARNESS / "session_holders.json"
TRANSCRIPT = LOGS / "transcript.jsonl"
EVENTS = LOGS / "events.jsonl"
GUARD = LOCKS / ".guard"

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def now_utc():
    return _dt.datetime.now(_dt.timezone.utc)


def now_iso():
    return now_utc().strftime(ISO_FMT)


def iso_in(seconds):
    return (now_utc() + _dt.timedelta(seconds=seconds)).strftime(ISO_FMT)


def parse_iso(ts):
    try:
        return _dt.datetime.strptime(ts, ISO_FMT).replace(tzinfo=_dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def agent_id(default="main"):
    """Identity of the current agent. Multi-session runners (other terminals,
    Gemini/Antigravity) must export CLAUDE_HARNESS_AGENT_ID or pass explicit
    --agent/--holder flags; in-session subagents pass their bench name."""
    return os.environ.get("CLAUDE_HARNESS_AGENT_ID", default)


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def atomic_write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class guarded:
    """Serialize read-modify-write cycles on shared state via a single flock."""

    def __enter__(self):
        GUARD.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(GUARD, "a+")
        portalock.lock_ex(self._fh)
        return self

    def __exit__(self, *exc):
        portalock.unlock(self._fh)
        self._fh.close()
        return False


def append_jsonl(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        portalock.lock_ex(f)
        f.write(line + "\n")
        portalock.unlock(f)


def log_event(kind, **fields):
    """Semantic blackboard/lock events -> .harness/logs/events.jsonl."""
    record = {"ts": now_iso(), "event": kind, "agent": agent_id()}
    record.update(fields)
    append_jsonl(EVENTS, record)


def lock_name_for(path):
    """Map a workspace path to its lock file name (relative path, sep -> '__').
    Returns None for paths outside the workspace root (those are never locked
    here; writes outside the root are forbidden by the Control layer anyway)."""
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    try:
        p = p.resolve()
        rel = p.relative_to(ROOT)
    except (OSError, ValueError):
        return None
    return str(rel).replace(os.sep, "__") + ".lock"


def read_lock(path):
    """Return (lock_path, payload_or_None) for a workspace path."""
    name = lock_name_for(path)
    if name is None:
        return None, None
    lock_path = LOCKS / name
    return lock_path, read_json(lock_path)


def lock_is_expired(payload):
    if not payload:
        return True
    acquired = parse_iso(payload.get("acquired_at", ""))
    if acquired is None:
        return True
    try:
        ttl = float(payload.get("ttl_seconds", 900))
    except (TypeError, ValueError):
        ttl = 900
    return (now_utc().replace(microsecond=0) - acquired).total_seconds() > ttl


def session_holders():
    """Names registered (via bin/session.py) as agents coordinated within THIS
    session, filtered to LIVE (unexpired) entries only. check_lock.py treats a
    lock holder in this set the same as `holder == me` (fixes P-002: in-session
    subagents with per-call identity overrides no longer self-block on their
    own locks). Registration is an explicit coordinator act -- nothing else in
    this harness auto-registers a holder here, so cross-session/cross-engine
    locks stay mechanically enforced.

    Must never raise: any malformed data or I/O error yields an empty set, so
    callers (notably the fail-open check_lock.py hook) stay fail-safe."""
    try:
        data = read_json(SESSION_HOLDERS, default=None)
        if not isinstance(data, dict):
            return set()
        holders = data.get("holders")
        if not isinstance(holders, dict):
            return set()
        now = now_utc()
        live = set()
        for name, entry in holders.items():
            if not isinstance(entry, dict):
                continue
            expires_at = parse_iso(entry.get("expires_at", ""))
            if expires_at is not None and expires_at > now:
                live.add(name)
        return live
    except Exception:
        return set()
