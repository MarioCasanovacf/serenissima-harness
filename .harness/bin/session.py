#!/usr/bin/env python3
"""Session-holder registry for the Universal Agent Harness (.harness/session_holders.json).

Fixes P-002 (audit_gen1 Proposal A): check_lock.py only ever compared a lock's
holder against the AMBIENT CLAUDE_HARNESS_AGENT_ID, so an in-session subagent
whose identity is overridden per-call (--agent/--holder) self-blocked on its
own live locks. This registry lets a COORDINATOR explicitly declare which
agent names are "coordinated within this session" — check_lock.py then also
allows a write when the lock holder is one of those names (see
harness_common.session_holders()).

Usage:
  python3 .harness/bin/session.py register <name> [--ttl 7200] [--by <agent>]
  python3 .harness/bin/session.py unregister <name>
  python3 .harness/bin/session.py list

Rules:
  - Data file: .harness/session_holders.json -> {"holders": {"<name>": {
      "registered_at": iso, "expires_at": iso, "by": agent}}}.
  - All mutations go through hc.guarded() + hc.atomic_write_json (same
    serialization discipline as lock.py / blackboard.py).
  - Entries auto-expire (TTL, default 7200s); expired entries are pruned
    whenever the file is next written (register/unregister), and are always
    filtered out at read time regardless of what is still on disk (see
    harness_common.session_holders() and the `list` command below).
  - Registration is a deliberate, explicit coordinator act. Nothing else in
    this harness (blackboard.py claim, lock.py acquire, ...) may auto-register
    a holder here -- cross-engine/cross-session agents must stay mechanically
    lock-enforced unless a coordinator explicitly opts them in.
"""
import argparse
import sys

import harness_common as hc


def _read_holders():
    """Return the raw {"holders": {...}} dict, defaulting to an empty registry."""
    data = hc.read_json(hc.SESSION_HOLDERS, default=None)
    if not isinstance(data, dict) or not isinstance(data.get("holders"), dict):
        return {"holders": {}}
    return data


def _live_holders(data):
    """Filter a raw holders dict down to entries whose expires_at is in the future."""
    live = {}
    now = hc.now_utc()
    for name, entry in data.get("holders", {}).items():
        if not isinstance(entry, dict):
            continue
        expires_at = hc.parse_iso(entry.get("expires_at", ""))
        if expires_at is not None and expires_at > now:
            live[name] = entry
    return live


def register(args):
    entry = {
        "registered_at": hc.now_iso(),
        "expires_at": hc.iso_in(args.ttl),
        "by": args.by,
    }
    with hc.guarded():
        data = _read_holders()
        data["holders"] = _live_holders(data)  # prune expired entries on write
        data["holders"][args.name] = entry
        hc.atomic_write_json(hc.SESSION_HOLDERS, data)
    hc.log_event(
        "session_holder_registered",
        holder=args.name,
        ttl_seconds=args.ttl,
        expires_at=entry["expires_at"],
        by=args.by,
    )
    print(
        "registered: '{}' (by={}, expires_at={}, ttl={}s)".format(
            args.name, args.by, entry["expires_at"], args.ttl
        )
    )
    return 0


def unregister(args):
    with hc.guarded():
        data = _read_holders()
        live = _live_holders(data)  # prune expired entries on write
        existed = args.name in live
        live.pop(args.name, None)
        data["holders"] = live
        hc.atomic_write_json(hc.SESSION_HOLDERS, data)
    hc.log_event("session_holder_unregistered", holder=args.name, existed=existed)
    print(("unregistered: '{}'" if existed else "noop: '{}' was not a live holder").format(args.name))
    return 0


def list_holders(_args):
    data = _read_holders()
    live = _live_holders(data)  # read-only filter; does not rewrite the file
    if not live:
        print("no live session holders")
        return 0
    print("{:<24} {:<22} {:<22} {}".format("NAME", "REGISTERED_AT", "EXPIRES_AT", "BY"))
    for name in sorted(live):
        entry = live[name]
        print(
            "{:<24} {:<22} {:<22} {}".format(
                name[:23],
                str(entry.get("registered_at", "?")),
                str(entry.get("expires_at", "?")),
                str(entry.get("by", "?")),
            )
        )
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_reg = sub.add_parser("register", help="register a name as a session-coordinated holder (TTL entry)")
    p_reg.add_argument("name")
    p_reg.add_argument("--ttl", type=int, default=7200)
    p_reg.add_argument("--by", default=hc.agent_id())
    p_reg.set_defaults(func=register)

    p_unreg = sub.add_parser("unregister", help="remove a name from the session-holder registry")
    p_unreg.add_argument("name")
    p_unreg.set_defaults(func=unregister)

    p_list = sub.add_parser("list", help="list live (unexpired) session holders")
    p_list.set_defaults(func=list_holders)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
