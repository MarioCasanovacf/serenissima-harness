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
      "registered_at": iso, "expires_at": iso, "by": agent, "task": task_id}}}.
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

Mechanical authorization (P-019, closes the T-042 self-whitelist gap):
  - register/unregister now REFUSE (exit 1) unless the AMBIENT identity --
    hc.agent_id(), i.e. CLAUDE_HARNESS_AGENT_ID / the session default 'main',
    NEVER the --by flag or the <name> being registered -- is in the
    "coordinator set": {'main'} union every name in state.json's
    agents.registry whose role == 'coordinator' (read LIVE off disk on every
    call, no hardcoded names beyond 'main'; a missing/malformed registry
    falls back to {'main'} alone -- fail-closed, never fail-open, see
    _coordinator_set()). A refusal logs 'session_holder_register_refused'
    (agent=<ambient>, action, name, by) and prints the ambient identity and
    the rule to stderr before exiting 1.
  - WHY THIS GATES ON AMBIENT, NOT --by: T-042's forensic investigation found
    that ANY caller could self-whitelist itself (e.g. `CLAUDE_HARNESS_AGENT_ID
    =substrate-worker-2 session.py register substrate-worker-2 --by
    substrate-worker-2`), silently defeating check_lock.py's lock-blocking
    invariant for genuinely cross-session/cross-engine agents. Gating on
    ambient identity preserves the one legitimate pattern this registry
    exists for (T-037): an in-session bench worker whose per-call identity is
    OVERRIDDEN (--agent/--holder) still runs inside the coordinator's real
    terminal session, so its ambient CLAUDE_HARNESS_AGENT_ID is unset/'main'
    -- that self-registration keeps returning exit 0 unchanged. A genuine
    cross-session runner that follows protocol (exports its OWN
    CLAUDE_HARNESS_AGENT_ID per .harness/README.md #Identity, e.g. a second
    terminal or a different engine) now gets refused, because its ambient
    identity is neither 'main' nor a registered coordinator.
  - HONEST THREAT MODEL: this guards the SANCTIONED session.py CLI path
    against ACCIDENTAL protocol violations only -- a well-behaved cross-
    session runner that exports its own identity and calls this CLI. It does
    NOT and cannot prevent a malicious/adversarial actor from hand-editing
    .harness/session_holders.json directly (no CLI, no ambient-identity check
    to trip): that bypass is OUTSIDE this trust model, the same boundary the
    fail-open PreToolUse hook (check_lock.py) already accepts for direct
    file-write bypasses. Nothing here is a security control against a hostile
    process with filesystem access -- it is a mechanical guardrail against a
    cooperating agent following the wrong (or no) protocol.
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


def _coordinator_set():
    """Ambient identities allowed to register/unregister session holders
    (P-019). Always includes 'main' -- the default ambient identity for
    in-session bench workers (harness_common.agent_id) -- so the T-037
    in-session whitelisting flow keeps working unchanged. Also includes every
    name in state.json's agents.registry whose role == 'coordinator', read
    LIVE off disk on every call (no hardcoded names beyond 'main').

    Must never raise or silently WIDEN the set: any missing/malformed
    state.json or registry shape falls back to {'main'} alone -- fail-closed,
    mirroring the fail-safe discipline of harness_common.session_holders()
    (which fails to an empty set on error; here 'empty' would over-restrict
    to 'main', which is the safe direction for an authorization gate)."""
    coordinators = {"main"}
    try:
        state = hc.read_json(hc.STATE, default=None) or {}
        registry = state.get("agents", {}).get("registry", {})
        if isinstance(registry, dict):
            for name, entry in registry.items():
                if isinstance(entry, dict) and entry.get("role") == "coordinator":
                    coordinators.add(name)
    except Exception:
        # state.json missing/malformed or agents.registry not a dict: fall
        # back to {'main'} only (see docstring -- fail-closed).
        pass
    return coordinators


def _authorize_or_exit(action, name, by=None):
    """Refuse (exit 1) unless the AMBIENT identity (hc.agent_id() -- NEVER
    --by/--holder, which is caller-supplied and therefore untrustworthy) is
    in _coordinator_set(). Logs 'session_holder_register_refused' on refusal
    and names the ambient identity + the rule on stderr before exiting."""
    ambient = hc.agent_id()
    coordinators = _coordinator_set()
    if ambient in coordinators:
        return
    hc.log_event(
        "session_holder_register_refused",
        agent=ambient,
        action=action,
        name=name,
        by=by,
    )
    sys.exit(
        "REFUSED: ambient identity '{ambient}' is not a coordinator (coordinator set = "
        "{coordinators}); session-holder {action} is a coordinator-only act. This guards "
        "the sanctioned session.py CLI against ACCIDENTAL protocol violations -- a "
        "cross-session/cross-engine runner that follows protocol (exports its own "
        "CLAUDE_HARNESS_AGENT_ID per .harness/README.md #Identity) is refused here BY "
        "DESIGN; direct edits to session_holders.json are outside this trust model (same "
        "boundary as the fail-open check_lock.py hook).".format(
            ambient=ambient, coordinators=sorted(coordinators), action=action
        )
    )


def register(args):
    _authorize_or_exit("register", args.name, by=args.by)
    entry = {
        "registered_at": hc.now_iso(),
        "expires_at": hc.iso_in(args.ttl),
        "by": args.by,
        "task": args.task,
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
        task=args.task,
    )
    print(
        "registered: '{}' (by={}, expires_at={}, ttl={}s, task={})".format(
            args.name, args.by, entry["expires_at"], args.ttl, args.task
        )
    )
    return 0


def unregister(args):
    _authorize_or_exit("unregister", args.name)
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
    p_reg.add_argument("--task", default=None, help="blackboard task id this registration is attributed to (OQ2 attribution fix)")
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
