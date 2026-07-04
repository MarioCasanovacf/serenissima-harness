#!/usr/bin/env python3
"""Write-lock manager for the Universal Agent Harness (.harness/locks/).

Usage:
  python3 .harness/bin/lock.py acquire <path> --holder <agent> [--task T-XXX] [--ttl 900]
  python3 .harness/bin/lock.py release <path> --holder <agent> [--force]
  python3 .harness/bin/lock.py status [--agent <name>]
  python3 .harness/bin/lock.py sweep [--agent <name>]

Rules:
  - One lock file per workspace file: <rel__path>.lock with a JSON payload
    {path, holder, task_id, acquired_at, ttl_seconds}.
  - Locks auto-expire after ttl_seconds. `sweep` (or any later acquire)
    clears expired locks, so a crashed agent can never stall the swarm.
  - Re-acquiring your own live lock refreshes it (heartbeat pattern).
  - The PreToolUse hook (check_lock.py) enforces these locks mechanically
    for Claude Code sessions; other engines must call this CLI voluntarily.

G4 fix: `status` and `sweep` now ACCEPT (but ignore) a --agent flag. Neither
subcommand needs an actor identity -- status is a read-only report and sweep
only removes locks that are already expired regardless of who holds them --
so this is a harmless documented alias, not a behavior change: it exists
purely so the pass-identity-everywhere discipline (every harness CLI call
carries --agent/--holder) never errors out on these two read-only/janitor
subcommands. Bare `status`/`sweep` (no --agent) are byte-for-byte unchanged.
"""
import argparse
import sys

import harness_common as hc


def acquire(args):
    name = hc.lock_name_for(args.path)
    if name is None:
        print("refused: '{}' is outside the workspace root {}".format(args.path, hc.ROOT))
        return 1
    lock_path = hc.LOCKS / name
    payload = {
        "path": args.path,
        "holder": args.holder,
        "task_id": args.task,
        "acquired_at": hc.now_iso(),
        "ttl_seconds": args.ttl,
    }
    with hc.guarded():
        existing = hc.read_json(lock_path)
        live = existing and not hc.lock_is_expired(existing)
        if live and existing.get("holder") != args.holder:
            print(
                "busy: '{}' held by '{}' (task {}, acquired {}, ttl {}s). "
                "Pick another task/file or wait for expiry.".format(
                    args.path,
                    existing.get("holder"),
                    existing.get("task_id", "?"),
                    existing.get("acquired_at"),
                    existing.get("ttl_seconds"),
                )
            )
            return 1
        stole_expired = bool(existing and not live and existing.get("holder") != args.holder)
        refreshed = bool(live and existing.get("holder") == args.holder)
        hc.atomic_write_json(lock_path, payload)
    hc.log_event(
        "lock_acquired",
        path=args.path,
        holder=args.holder,
        task=args.task,
        ttl_seconds=args.ttl,
        stole_expired=stole_expired,
        refreshed=refreshed,
    )
    verb = "refreshed" if refreshed else ("acquired (expired lock swept)" if stole_expired else "acquired")
    print("{}: {} (holder={}, ttl={}s)".format(verb, name, args.holder, args.ttl))
    return 0


def release(args):
    name = hc.lock_name_for(args.path)
    if name is None:
        print("refused: '{}' is outside the workspace root".format(args.path))
        return 1
    lock_path = hc.LOCKS / name
    with hc.guarded():
        existing = hc.read_json(lock_path)
        if existing is None:
            print("noop: no lock on '{}'".format(args.path))
            return 0
        if existing.get("holder") != args.holder and not args.force:
            print(
                "refused: lock on '{}' is held by '{}', not '{}'. Use --force only "
                "with coordinator authority.".format(args.path, existing.get("holder"), args.holder)
            )
            return 1
        lock_path.unlink(missing_ok=True)
    hc.log_event(
        "lock_released",
        path=args.path,
        holder=args.holder,
        forced=bool(args.force and existing.get("holder") != args.holder),
    )
    print("released: {}".format(name))
    return 0


def status(args):
    # args.agent is accepted-but-unused (G4 harmless alias -- see module docstring).
    del args
    hc.LOCKS.mkdir(parents=True, exist_ok=True)
    locks = sorted(hc.LOCKS.glob("*.lock"))
    if not locks:
        print("no active lock files")
        return 0
    print("{:<44} {:<20} {:<8} {:<22} {}".format("PATH", "HOLDER", "TASK", "ACQUIRED_AT", "STATE"))
    for lp in locks:
        data = hc.read_json(lp) or {}
        state = "EXPIRED" if hc.lock_is_expired(data) else "live"
        print(
            "{:<44} {:<20} {:<8} {:<22} {}".format(
                str(data.get("path", lp.name))[:43],
                str(data.get("holder", "?"))[:19],
                str(data.get("task_id") or "-")[:7],
                str(data.get("acquired_at", "?")),
                state,
            )
        )
    return 0


def sweep(args):
    # args.agent is accepted-but-unused (G4 harmless alias -- see module docstring).
    del args
    hc.LOCKS.mkdir(parents=True, exist_ok=True)
    removed = []
    with hc.guarded():
        for lp in sorted(hc.LOCKS.glob("*.lock")):
            data = hc.read_json(lp)
            if hc.lock_is_expired(data):
                lp.unlink(missing_ok=True)
                removed.append(lp.name)
    for name in removed:
        hc.log_event("lock_swept", lock_file=name)
    print("swept {} expired lock(s)".format(len(removed)))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_acq = sub.add_parser("acquire", help="acquire or refresh a write lock")
    p_acq.add_argument("path")
    p_acq.add_argument("--holder", default=hc.agent_id())
    p_acq.add_argument("--task", default=None)
    p_acq.add_argument("--ttl", type=int, default=900)
    p_acq.set_defaults(func=acquire)

    p_rel = sub.add_parser("release", help="release a write lock you hold")
    p_rel.add_argument("path")
    p_rel.add_argument("--holder", default=hc.agent_id())
    p_rel.add_argument("--force", action="store_true")
    p_rel.set_defaults(func=release)

    p_st = sub.add_parser("status", help="list lock files and their liveness")
    p_st.add_argument("--agent", default=None, help="accepted-but-unused alias (G4); no behavior change")
    p_st.set_defaults(func=status)

    p_sw = sub.add_parser("sweep", help="remove expired lock files")
    p_sw.add_argument("--agent", default=None, help="accepted-but-unused alias (G4); no behavior change")
    p_sw.set_defaults(func=sweep)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
