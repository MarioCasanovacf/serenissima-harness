#!/usr/bin/env python3
"""ReContext evidence CLI for the Universal Agent Harness (gemini.md §4B, G4/G5).

Makes the Scan -> Extract -> Replay -> Reason discipline mechanical instead of
manual: `add` atomically appends one evidence entry to
.harness/recontext_evidence.md under a write lock (so concurrent agents never
interleave partial writes), and `list` gives a cheap grep-level index of what
is already on file.

Usage:
  python3 .harness/bin/recontext.py add --task T-XXX --source "<file>:<lines>" \
      --label "<what this evidence supports>" [--text "<verbatim extract>"] \
      [--agent <name>]
    If --text is omitted, the extract is read verbatim from stdin (EOF/Ctrl-D
    to finish), e.g.: `echo "..." | python3 .harness/bin/recontext.py add ...`.
  python3 .harness/bin/recontext.py list [--task T-XXX]
    Prints one line per entry header (`## [T-XXX] <label> — <agent> — <ts>`),
    grep-level parsing of the Markdown file -- no separate index is kept.

Locking mechanics (mirrors lock.py's acquire/release exactly, scoped to the
single fixed target .harness/recontext_evidence.md so `add` never needs a
--path argument): a lock file appears under .harness/locks/ for the duration
of the append and is removed afterwards; a live lock held by a DIFFERENT
agent refuses the append (same busy/expiry semantics as lock.py). `add` logs
lock_acquired / lock_released events (identical shape to lock.py) plus a
final recontext_added event.

G5 fix: every entry `add` writes uses hc.now_iso() -- an UTC 'Z'-suffixed
timestamp -- never a local-offset ISO string. (Older entries in the file
predate this tool and may still show a local offset like '-06:00'; this tool
only ever appends, it never rewrites history, so those are left as-is.)

Notes:
  - stdlib-only, python3 >= 3.9 (no `match` statements, no 3.10+ syntax).
  - Header template (must match the file's own documented header exactly):
      ## [T-XXX] <label> — <agent> — <UTC Z timestamp>
      Source: <file>:<lines>
      ```
      <verbatim extract>
      ```
"""
import argparse
import sys

import harness_common as hc

EVIDENCE_PATH = hc.HARNESS / "recontext_evidence.md"


# --------------------------- lock mechanics (mirrors lock.py) --------------

def _acquire_evidence_lock(holder, task):
    """Acquire (or refresh) the write lock on EVIDENCE_PATH. Returns True on
    success, False if busy (held live by a different agent)."""
    name = hc.lock_name_for(EVIDENCE_PATH)
    lock_path = hc.LOCKS / name
    payload = {
        "path": str(EVIDENCE_PATH),
        "holder": holder,
        "task_id": task,
        "acquired_at": hc.now_iso(),
        "ttl_seconds": 900,
    }
    with hc.guarded():
        existing = hc.read_json(lock_path)
        live = existing and not hc.lock_is_expired(existing)
        if live and existing.get("holder") != holder:
            print(
                "busy: '{}' held by '{}' (task {}, acquired {}, ttl {}s). "
                "Retry once released/expired.".format(
                    EVIDENCE_PATH,
                    existing.get("holder"),
                    existing.get("task_id", "?"),
                    existing.get("acquired_at"),
                    existing.get("ttl_seconds"),
                )
            )
            return False
        stole_expired = bool(existing and not live and existing.get("holder") != holder)
        refreshed = bool(live and existing.get("holder") == holder)
        hc.atomic_write_json(lock_path, payload)
    hc.log_event(
        "lock_acquired",
        path=str(EVIDENCE_PATH),
        holder=holder,
        task=task,
        ttl_seconds=payload["ttl_seconds"],
        stole_expired=stole_expired,
        refreshed=refreshed,
    )
    return True


def _release_evidence_lock(holder):
    """Release the write lock on EVIDENCE_PATH if held by `holder`."""
    name = hc.lock_name_for(EVIDENCE_PATH)
    lock_path = hc.LOCKS / name
    with hc.guarded():
        existing = hc.read_json(lock_path)
        if existing is None:
            return
        if existing.get("holder") != holder:
            return
        lock_path.unlink(missing_ok=True)
    hc.log_event("lock_released", path=str(EVIDENCE_PATH), holder=holder, forced=False)


# --------------------------------- commands ---------------------------------

def cmd_add(args):
    if args.text is not None:
        text = args.text
    else:
        text = sys.stdin.read()
    text = text.rstrip("\n")
    if not text.strip():
        print("refused: empty extract (pass --text or pipe non-empty content via stdin)")
        return 1

    ts = hc.now_iso()
    entry = (
        "\n## [{task}] {label} — {agent} — {ts}\n"
        "Source: {source}\n"
        "```\n{text}\n```\n"
    ).format(task=args.task, label=args.label, agent=args.agent, ts=ts, source=args.source, text=text)

    if not _acquire_evidence_lock(args.agent, args.task):
        return 1
    try:
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(EVIDENCE_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
    finally:
        _release_evidence_lock(args.agent)

    hc.log_event("recontext_added", task=args.task, source=args.source, agent=args.agent, label=args.label)
    print("appended: [{}] {} — {} — {} -> {}".format(args.task, args.label, args.agent, ts, EVIDENCE_PATH))
    return 0


def cmd_list(args):
    if not EVIDENCE_PATH.exists():
        print("no evidence file yet at {}".format(EVIDENCE_PATH))
        return 1
    needle = "[{}]".format(args.task) if args.task else None
    count = 0
    with open(EVIDENCE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.startswith("## ["):
                continue
            if needle and needle not in line:
                continue
            print(line[3:])  # drop the leading "## " markdown marker
            count += 1
    if count == 0:
        print("no entries" + (" for {}".format(args.task) if args.task else ""))
        return 1
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="append one evidence entry, under lock")
    p_add.add_argument("--task", required=True)
    p_add.add_argument("--source", required=True, help="<file>:<lines>")
    p_add.add_argument("--label", required=True, help="what this evidence supports")
    p_add.add_argument("--text", default=None, help="verbatim extract (else read from stdin)")
    p_add.add_argument("--agent", default=hc.agent_id())
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="print entry headers (grep-level)")
    p_list.add_argument("--task", default=None)
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
