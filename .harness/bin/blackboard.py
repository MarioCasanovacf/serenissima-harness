#!/usr/bin/env python3
"""Blackboard CLI — the ONLY sanctioned writer of .harness/blackboard.json.

This tool mechanically encodes the delegation topology (see ORCHESTRATION.md):
  - CASCADE WHERE REAL: a task is claimable only when ALL of its depends_on
    tasks are done. The claim command refuses otherwise — delegation chains
    are enforced by the data, not by agent politeness.
  - PARALLEL WHERE POSSIBLE: independent open tasks can be claimed by
    different agents concurrently; write collisions are prevented by lock.py
    and by serializing all blackboard mutations through a single guard.
  - NO STALLS: claims carry a lease (claim_expires_at). Expired claims are
    auto-released on every command, so a crashed/stuck agent never blocks
    the DAG frontier.
  - PRODUCER != APPROVER: workers hand off to reviewers (status=review);
    only a different agent should mark a task done. This is now MECHANICAL,
    not just cultural: `update --status done` is refused unless (a) a
    handoff record exists (the task was actually reviewed by someone) AND
    (b) the acting --agent differs from handoff.from. AUTHORSHIP governs,
    not current status (P-011) -- a verifier who claimed/in_progress'd the
    review task may verdict done with no extra friction; only the original
    producer of record is blocked. Escape hatch: --override-producer-check
    (requires --note); every refusal and override is logged to events.jsonl
    with the acting agent recorded explicitly. EXCEPTION (P-022): a
    role=='verifier' task (the task itself IS the review/execution step --
    tournament verdicts, epic joins) may go straight to done with NO handoff
    at all, provided --agent differs from the task's created_by; logged as
    event verifier_execute_done. Self-done by the creator is still refused;
    worker/thinker-role tasks are unaffected.

Usage examples:
  python3 .harness/bin/blackboard.py status
  python3 .harness/bin/blackboard.py next --agent substrate-worker --role worker
  python3 .harness/bin/blackboard.py show T-003
  python3 .harness/bin/blackboard.py claim T-003 --agent substrate-worker [--lease 3600]
  python3 .harness/bin/blackboard.py update T-003 --status in_progress --note "plan: ..."
  python3 .harness/bin/blackboard.py update T-003 --artifact .harness/bin/ast_index.py
  python3 .harness/bin/blackboard.py handoff T-003 --to-role verifier --note "tests green: <cmds>"
  python3 .harness/bin/blackboard.py update T-003 --status done --note "verified by replaying cmds"
  # producer!=approver is mechanical: --status done is refused unless a handoff
  # record exists AND --agent != the handoff's from_agent (current status is
  # irrelevant -- P-011). Escape hatch (rare, audited): --override-producer-check
  # --note "why this is safe"
  # P-022: role=='verifier' tasks (the task itself IS the review/execution --
  # tournament verdicts, epic joins) may go straight to done with NO handoff,
  # as long as --agent differs from the task's created_by. Self-done by the
  # creator is still refused. worker/thinker-role tasks are unchanged (handoff
  # still required). Logged explicitly as event verifier_execute_done.
  python3 .harness/bin/blackboard.py add-task --id T-010 --title "..." --role worker \
      --engine any --depends-on T-001,T-003 --priority 2 --description "..."
  # P-021: --note takes raw shell args, so backticks/$()/etc are expanded by
  # YOUR shell before this CLI ever sees them (a live hazard, not a hypothetical
  # one). For any note containing those characters, use --note-file <path>
  # (content read byte-exact) or --note-stdin (byte-exact from stdin) instead --
  # available on both `update` and `handoff`, mutually exclusive with --note.
  printf '%s' 'note with `backticks` and $(danger)' > /tmp/note.txt
  python3 .harness/bin/blackboard.py update T-003 --note-file /tmp/note.txt
  echo 'note with `backticks`' | python3 .harness/bin/blackboard.py update T-003 --note-stdin
  # P-023: 'done'/'failed' are terminal -- nothing above can move a task off
  # them (by design). The only sanctioned way back is `reopen`, which only
  # acts on terminal tasks, MANDATES --note (no note = refused, no silent
  # resurrection), and logs task_reopened (who/why) to events.jsonl:
  python3 .harness/bin/blackboard.py reopen T-090 --agent worker-b \
      --note "re-running the scratch probe under the new goal_mode bound"
"""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

import harness_common as hc

VALID_STATUS = ["open", "claimed", "in_progress", "blocked", "review", "done", "failed"]
VALID_ROLES = ["thinker", "worker", "verifier"]
VALID_ENGINES = ["claude", "gemini", "codex", "any"]

# T-426 / PR-062 (YIELD-AT-NEXT, docket C-002): `next`'s yield exit code.
# Distinct from 0 (recommendation given) and 1 (no claimable task at all --
# the ratio's own words: "neither 0 nor 1, since 1 already means no
# claimable task"). Unused elsewhere in this file's return codes.
PHASE_B_YIELD_EXIT = 2

# T-422: fixed by this file's own location, NEVER by hc.HARNESS -- a test
# fixture redirects hc.HARNESS to a scratch root (it is the --root value
# reputation.py reads data from), but the reputation.py SCRIPT itself always
# lives next to this one, in the real .harness/bin/ directory.
_REPUTATION_PY = Path(__file__).resolve().parent / "reputation.py"


# ---------- shared helpers (call only while holding hc.guarded()) ----------

def load_bb():
    bb = hc.read_json(hc.BLACKBOARD)
    if bb is None:
        sys.exit("fatal: cannot read or parse {}".format(hc.BLACKBOARD))
    return bb


def save_bb(bb, actor):
    bb["updated_at"] = hc.now_iso()
    bb["updated_by"] = actor
    hc.atomic_write_json(hc.BLACKBOARD, bb)


def expire_claims(bb):
    """Release claims whose lease has expired. Returns [(task_id, holder)]."""
    released = []
    for tid, t in bb.get("tasks", {}).items():
        if t.get("status") in ("claimed", "in_progress"):
            exp = hc.parse_iso(t.get("claim_expires_at") or "")
            if exp is not None and exp < hc.now_utc():
                released.append((tid, t.get("claimed_by")))
                t["status"] = "open"
                t["claimed_by"] = None
                t["claim_expires_at"] = None
    return released


def unconfirmed_records_for(task_id):
    """Active precedent records issued by this task that no distinct identity has
    confirmed yet.

    PR-015 requires a confirming identity; `precedent.py confirm` already refuses
    the publishing author mechanically (SDR-24.1). Measured 2026-08-16 before this
    function existed: 0 successful confirmations across 59 records, against 16
    distinct `precedent_confirm_refused` events -- 5 of them the author rule firing
    correctly and 11 usage errors. Nothing was broken. The verb was never wired to
    a step that runs, so the floor was never exercised.

    FAIL-OPEN BY CONSTRUCTION. A missing directory, an unreadable file or a
    malformed record all yield [], so a registry problem can never wedge the DAG.
    Only a record that is present, parseable, active and unconfirmed is returned.
    """
    out = []
    try:
        pdir = hc.HARNESS / "precedents"
        if not pdir.is_dir():
            return out
        for path in sorted(pdir.glob("PR-*.json")):
            try:
                rec = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue
            if rec.get("issuing_task") != task_id:
                continue
            if rec.get("status") != "active":
                continue
            if rec.get("confirmation_status") == "confirmed":
                continue
            out.append(rec.get("id") or path.stem)
    except Exception:
        return []
    return out


def deps_unmet(bb, t):
    return [d for d in t.get("depends_on", []) if bb["tasks"].get(d, {}).get("status") != "done"]


def is_claimable(bb, t):
    """Open with all dependencies done, or handed off for review."""
    if t.get("status") == "review":
        return True
    return t.get("status") == "open" and not deps_unmet(bb, t)


def bump_reputation_locked(agent, outcome):
    """Update state.json reputation counters. Caller must hold the guard."""
    state = hc.read_json(hc.STATE)
    if state is None:
        return
    rep = state.setdefault("agents", {}).setdefault("reputation", {})
    entry = rep.setdefault(agent, {"tasks_done": 0, "tasks_failed": 0})
    key = "tasks_done" if outcome == "done" else "tasks_failed"
    entry[key] = entry.get(key, 0) + 1
    entry["last_outcome_at"] = hc.now_iso()
    hc.atomic_write_json(hc.STATE, state)


def default_lease():
    state = hc.read_json(hc.STATE) or {}
    try:
        return int(state.get("limits", {}).get("claim_lease_seconds_default", 3600))
    except (TypeError, ValueError):
        return 3600


def detail_path(task_id):
    return hc.TASKS / "{}.json".format(task_id)


def append_note(task_id, agent, note):
    detail = hc.read_json(detail_path(task_id)) or {
        "id": task_id,
        "title": "",
        "description": "",
        "acceptance_criteria": [],
        "context_files": [],
        "notes": [],
    }
    detail.setdefault("notes", []).append({"ts": hc.now_iso(), "agent": agent, "note": note})
    hc.atomic_write_json(detail_path(task_id), detail)


def resolve_note(args):
    """P-021: resolve the effective note text from --note / --note-file / --note-stdin.

    argparse's mutually-exclusive group (set up in main()) already refuses more
    than one of these being passed together, so no re-check is needed here.
    --note-file and --note-stdin are read as raw bytes and decoded utf-8 with
    NO stripping/rstrip -- byte-exact -- specifically so hazardous shell
    metacharacters (backticks, $(), etc.) survive intact instead of being
    expanded by the invoking shell (the P-021 hazard --note is inherently
    exposed to).
    """
    note_file = getattr(args, "note_file", None)
    note_stdin = getattr(args, "note_stdin", False)
    if note_file:
        try:
            with open(note_file, "rb") as f:
                return f.read().decode("utf-8")
        except OSError as e:
            sys.exit("refused: cannot read --note-file {}: {}".format(note_file, e))
    if note_stdin:
        return sys.stdin.buffer.read().decode("utf-8")
    return args.note


def report_expirations(released):
    for tid, holder in released:
        hc.log_event("claim_expired", task=tid, previous_holder=holder)
        print("note: lease on {} (held by {}) expired -> task released to open".format(tid, holder))


# ------------------- T-422: Phase B claim-order CONSUMER -------------------
#
# gen-8 consumer scaffold (docket C-002). PR-061 (RAT-01) authorizes
# reputation.py's `dispatch` as the one consequence verb reputation.py
# exposes, gated by an operator-signed, activated constitutional file; PR-060
# clause 6 splits parameters into CONSTITUTIONAL (the operator's alone --
# decay rate, weights) versus OPERATIONAL (claim priority ordering -- the one
# thing a consumer may act on). Everything below builds the READ side: it
# asks dispatch what it would recommend and prints the answer as an ADVISORY
# line, in `cmd_status` (unconditionally) and in `cmd_next` (unconditionally,
# on every path -- byte-identical to before this task).
#
# T-426 / PR-062 (YIELD-AT-NEXT, docket C-002 disposition) ATTACHES the one
# consequence C-002 authorized, and no other: on `cmd_next`'s success path
# ONLY (never `status`, never `claim`), when the SAME dispatch read that
# produced the advisory line also shows the requesting agent is OUTRANKED
# (PR-062 clause 4: another live candidate's Phase B `total_score` is
# STRICTLY GREATER, zero margin) by another live candidate, the dispatcher's
# RECOMMENDATION yields: `cmd_next` prints one additional line, logs one
# named event (`phase_b_yield`, carrying task/agent/outranked_by) to this
# board's OWN event log, and returns `PHASE_B_YIELD_EXIT` instead of 0. The
# 'next:' and 'claim it:' lines stay byte-identical under a yield (see
# `cmd_next` below) and `cmd_claim` is untouched -- claim stays first-come.
# See `phase_b_yield_check`'s docstring for the outranked-by rule and the
# documented (not hidden) rename bypass.

def live_candidates(bb, agent):
    """T-422's definition of 'live candidates' for the Phase B claim-order
    ADVISORY: identities holding an UNEXPIRED claim in blackboard.json
    (status 'claimed' or 'in_progress', and claim_expires_at either unset or
    still in the future -- an already-expired claim is stale data that
    `expire_claims()` releases separately and is never a live candidate)
    PLUS the requesting --agent, deduplicated, first-seen order preserved.

    This is bookkeeping for what to ask reputation.py to SCORE, nothing
    more -- it does not decide who may claim anything, and it is not a
    quorum, standing, or eligibility computation of any kind."""
    now = hc.now_utc()
    seen = []
    for t in bb.get("tasks", {}).values():
        if t.get("status") not in ("claimed", "in_progress"):
            continue
        holder = t.get("claimed_by")
        if not holder:
            continue
        exp = hc.parse_iso(t.get("claim_expires_at") or "")
        if exp is not None and exp < now:
            continue
        if holder not in seen:
            seen.append(holder)
    if agent and agent not in seen:
        seen.append(agent)
    return seen


def _phase_b_reason_from_stderr(stderr, returncode):
    """Builds the one-line refusal reason named by the spec. On every refusal
    path, `reputation.py dispatch` prints line 2 of stderr as
    '  constitutional file: <STATE> -- <detail>' (the `_phase_b_activation`
    status token); this strips the label and surfaces '<STATE> -- <detail>'
    verbatim. Falls back to naming the exit code when stderr doesn't have
    that shape -- e.g. exit 4 (REGISTRY INTEGRITY ERROR) prints exactly one
    stderr line, no 'constitutional file:' line at all."""
    lines = (stderr or "").splitlines()
    marker = "constitutional file: "
    if len(lines) >= 2:
        idx = lines[1].find(marker)
        if idx != -1:
            return lines[1][idx + len(marker):].strip()
    return "dispatch exited {}".format(returncode)


def _phase_b_dispatch_plan(candidates):
    """The ONE subprocess call onto reputation.py's `dispatch` verb (T-422,
    extended by T-426 to also hand back per-candidate scores from that SAME
    read -- PR-062 clause 4 requires the outranked-by check run "from one
    read and with no second dispatch run"). `phase_b_claim_order` (the
    order-only view) and `phase_b_yield_check` (the T-426 consequence) both
    read from whatever ONE call to this function already produced; neither
    calls `dispatch` again.

    Contract (unchanged from T-422's `phase_b_claim_order`, restated here):
      - Runs `<python> reputation.py dispatch --json --root <hc.HARNESS>
        --candidates <csv>` as a SUBPROCESS (sys.executable running the
        script at `_REPUTATION_PY`). Never imports reputation.py, never
        calls any of its functions -- public or private -- in-process.
      - NEVER passes --half-life-days: that is a CONSTITUTIONAL parameter
        under PR-060 and `dispatch` itself refuses it on the CLI; this seam
        does not attempt it either.
      - Returns `(plan, reason)`. `plan` is dispatch's own parsed `--json`
        payload (a dict carrying `recommended_claim_order` and `candidates`
        -- the latter a list of `{"identity": ..., "total_score": ...}`
        sorted `(-total_score, identity)`, the same sort `dispatch` itself
        performs) and ONLY when the subprocess exits 0, stdout parses as
        JSON, and that JSON carries a non-empty `recommended_claim_order`
        list. Every other outcome -- exit 1 (gate closed: NOT_PRESENT /
        UNSIGNED / BAD_SIGNATURE / WRONG_NAMESPACE / UNVERIFIABLE /
        VERIFIED_OFF / UNREADABLE), exit 4 (REGISTRY INTEGRITY ERROR), any
        other nonzero code, a missing/empty stdout, or stdout that fails to
        parse -- returns `(None, reason)` instead.
      - `reason` is built from dispatch's own stderr (see
        `_phase_b_reason_from_stderr`) or, on success, is the fixed string
        'VERIFIED, activation on' (the only state `dispatch` can exit 0
        under -- `_phase_b_activation` returns a payload only when the
        signature verifies AND activation is 'on').
      - NEVER RAISES: subprocess errors/timeouts, an unreadable script,
        malformed JSON, and any other unexpected condition are all caught
        and folded into `(None, reason)`.
      - NEVER WRITES: this function performs no file I/O of its own, and
        `dispatch` itself is read-only (T-421's `ZeroWritesAcrossPhaseB`).
    """
    if not candidates:
        return None, "no live candidates"
    try:
        proc = subprocess.run(
            [sys.executable, str(_REPUTATION_PY), "dispatch", "--json",
             "--root", str(hc.HARNESS), "--candidates", ",".join(candidates)],
            capture_output=True, text=True, timeout=30)
    except Exception as e:  # subprocess.SubprocessError, OSError, ... -- never raise
        return None, "reputation.py dispatch could not run: {}".format(e)

    try:
        if proc.returncode != 0:
            return None, _phase_b_reason_from_stderr(proc.stderr, proc.returncode)
        if not proc.stdout or not proc.stdout.strip():
            return None, "dispatch exited 0 with no stdout"
        plan = json.loads(proc.stdout)
        order = plan.get("recommended_claim_order") if isinstance(plan, dict) else None
        if not isinstance(order, list) or not order:
            return None, "dispatch JSON carried no recommended_claim_order"
        return plan, "VERIFIED, activation on"
    except Exception as e:  # malformed JSON, ... -- never raise
        return None, "dispatch output could not be parsed: {}".format(e)


def phase_b_claim_order(candidates):
    """Read-only consumer seam onto reputation.py's `dispatch` verb (T-422).

    Cites PR-061 (RAT-01, the ruling that authorizes `dispatch` at all) and
    PR-060 clause 6 (the constitutional/operational parameter split): this
    helper reads dispatch's recommended operational ordering and hands it
    back for a caller to PRINT. NO CONSEQUENCE BINDS HERE -- it is a thin
    `(order, reason)` view over `_phase_b_dispatch_plan`, used by
    `phase_b_advisory_line` (the `status` advisory and, unconditionally, the
    `next` advisory). Attaching the one consequence PR-062 authorizes is
    `phase_b_yield_check`'s job, called separately by `cmd_next` against the
    SAME plan on its own success path -- not this function's concern.

    Returns `(order, reason)`: `order` is `_phase_b_dispatch_plan`'s plan's
    `recommended_claim_order` on success, else `None`; `reason` is that
    call's own second return value, verbatim.
    """
    plan, reason = _phase_b_dispatch_plan(candidates)
    if plan is None:
        return None, reason
    return plan.get("recommended_claim_order"), reason


def _phase_b_advisory_text(order, reason):
    """Shared by `phase_b_advisory_line` and `cmd_next`'s success path (T-426
    -- the latter builds `order`/`reason` from the single dispatch plan it
    already read for the yield check, rather than calling
    `phase_b_claim_order` a second time) so both print the byte-identical
    line for the same (order, reason)."""
    if order:
        return "phase-b claim order: {} ({})".format(", ".join(order), reason)
    return "phase-b claim order not applied: {}".format(reason)


def phase_b_advisory_line(bb, agent):
    """The ONE advisory line `cmd_status` prints (T-422 spec item 4):
    'phase-b claim order: a, b, c (VERIFIED, activation on)' when
    `phase_b_claim_order` returns an order, else 'phase-b claim order not
    applied: <reason>'. Pure function of (bb, agent) plus one read-only
    subprocess call -- never mutates `bb`. `cmd_next`'s success path builds
    the identical text itself from its own single dispatch read instead of
    calling this (see `_phase_b_advisory_text`) so T-426's yield check never
    triggers a second `dispatch` subprocess."""
    order, reason = phase_b_claim_order(live_candidates(bb, agent))
    return _phase_b_advisory_text(order, reason)


def phase_b_yield_check(plan, agent):
    """T-426 / PR-062 (YIELD-AT-NEXT, docket C-002): decides whether
    `cmd_next`'s recommendation for `agent` YIELDS to a live candidate with a
    strictly greater Phase B score, from the SAME dispatch `plan` already
    read for the advisory line (`_phase_b_dispatch_plan`'s first return
    value) -- this function never runs a subprocess itself and never
    triggers a second `dispatch` call.

    Returns the outranking identity's name (truthy) when a yield fires, or
    `None` when it does not: gate closed / dispatch refused (`plan` is
    `None` or carries no `candidates`), `agent` is alone or unranked (its
    identity is absent from `plan['candidates']` -- score unknown to
    dispatch), tied for the top score, or already at the top.

    'Outranked' (PR-062 clause 4): STRICTLY GREATER Phase B `total_score`,
    ZERO MARGIN -- a margin would be a threshold, and PR-060 clause 1 makes
    any threshold constitutional, unsettable by any agent under clause 3.
    `plan['candidates']` is already sorted `(-total_score, identity)` (the
    same sort `recommended_claim_order` is derived from), so its first entry
    already carries the maximum score in the set: if that entry's identity
    is not `agent`, its score is compared to `agent`'s own score in that
    same list. A lower list POSITION never yields by itself (ties break
    lexicographically on the identity string, an attribute PR-060 clause 5
    forbids keying on) -- with 82 of 147 live identities at 0.0 that would
    make position-based yielding the common case, not the edge; ties and
    unranked identities never yield (PR-062's common floor).

    RENAME BYPASS (PR-062 clause 5, documented here rather than hidden):
    identity stays self-asserted (PR-023 clause 4 unamended); a requester
    that runs `next --agent <top identity>` is never outranked, because ties
    never yield and the rename inherits that identity's score. The payoff is
    nil -- `claim` stays first-come, entirely untouched by this function --
    and the deviation is legible without a verdict: a `phase_b_yield` row
    followed within seconds by `task_claimed` from the same agent, or a top
    identity claiming tasks its genuine holder never touched.
    """
    if not plan:
        return None
    scored = plan.get("candidates")
    if not isinstance(scored, list) or not scored:
        return None
    requester_score = None
    for c in scored:
        if isinstance(c, dict) and c.get("identity") == agent:
            requester_score = c.get("total_score")
            break
    if requester_score is None:
        return None
    top = scored[0]
    if not isinstance(top, dict) or top.get("identity") == agent:
        return None
    top_score = top.get("total_score")
    if isinstance(top_score, (int, float)) and top_score > requester_score:
        return top.get("identity")
    return None


# ------------------------------- commands ---------------------------------

def cmd_status(args):
    with hc.guarded():
        bb = load_bb()
        released = expire_claims(bb)
        if released:
            save_bb(bb, "lease-expiry")
    report_expirations(released)

    tasks = bb.get("tasks", {})
    counts = {}
    for t in tasks.values():
        counts[t.get("status", "?")] = counts.get(t.get("status", "?"), 0) + 1
    print("Universal Agent Harness — blackboard (generation {})".format(bb.get("generation", "?")))
    print("updated_at: {}   by: {}".format(bb.get("updated_at"), bb.get("updated_by")))
    print("counts: " + ", ".join("{}={}".format(k, v) for k, v in sorted(counts.items())))
    print()
    print("{:<6} {:<12} {:<8} {:<7} {:<18} {:<16} {}".format(
        "ID", "STATUS", "ROLE", "ENGINE", "CLAIMED_BY", "DEPENDS_ON", "TITLE"))
    for tid in sorted(tasks):
        t = tasks[tid]
        print("{:<6} {:<12} {:<8} {:<7} {:<18} {:<16} {}".format(
            tid,
            t.get("status", "?"),
            t.get("role", "?"),
            t.get("engine", "any"),
            str(t.get("claimed_by") or "-")[:17],
            ",".join(t.get("depends_on", [])) or "-",
            str(t.get("title", ""))[:48],
        ))
    claimable = [tid for tid in sorted(tasks) if is_claimable(bb, tasks[tid])]
    blocked = {tid: deps_unmet(bb, tasks[tid]) for tid in sorted(tasks)
               if tasks[tid].get("status") == "open" and deps_unmet(bb, tasks[tid])}
    print()
    print("claimable now: {}".format(", ".join(claimable) or "none"))
    for tid, unmet in blocked.items():
        print("gated (cascade): {} waits for {}".format(tid, ", ".join(unmet)))
    for ann in bb.get("announcements", [])[-2:]:
        print("announcement [{}]: {}".format(ann.get("ts", "?"), ann.get("message", "")))
    print(phase_b_advisory_line(bb, args.agent))
    return 0


def cmd_next(args):
    with hc.guarded():
        bb = load_bb()
        released = expire_claims(bb)
        if released:
            save_bb(bb, "lease-expiry")
    report_expirations(released)

    tasks = bb.get("tasks", {})
    cands = []
    for tid in sorted(tasks):
        t = tasks[tid]
        if not is_claimable(bb, t):
            continue
        if t.get("status") == "open":
            if args.role and t.get("role") != args.role:
                continue
            if args.engine and t.get("engine", "any") not in (args.engine, "any"):
                continue
        elif t.get("status") == "review":
            # review tasks go to verifiers regardless of the producer role
            if args.role and args.role != "verifier":
                continue
        cands.append((t.get("priority", 5), tid, t))
    if not cands:
        print("no claimable task for role={} engine={}. Run `blackboard.py status` "
              "to see cascade gates.".format(args.role or "any", args.engine or "any"))
        print(phase_b_advisory_line(bb, args.agent))
        return 1
    cands.sort(key=lambda c: (c[0], c[1]))
    prio, tid, t = cands[0]
    print("next: {} [{}] (priority {}, role {}, engine {}) — {}".format(
        tid, t.get("status"), prio, t.get("role"), t.get("engine", "any"), t.get("title")))
    print("claim it: python3 .harness/bin/blackboard.py claim {} --agent {}".format(tid, args.agent))
    if len(cands) > 1:
        print("also claimable: " + ", ".join(c[1] for c in cands[1:]))

    # T-426 / PR-062 (YIELD-AT-NEXT): ONE dispatch read serves both the
    # advisory line (unchanged text/placement) and the yield check below --
    # never two `dispatch` subprocess calls for one `next` invocation.
    plan, reason = _phase_b_dispatch_plan(live_candidates(bb, args.agent))
    order = plan.get("recommended_claim_order") if plan else None
    print(_phase_b_advisory_text(order, reason))

    outranked_by = phase_b_yield_check(plan, args.agent)
    if outranked_by:
        hc.log_event("phase_b_yield", task=tid, agent=args.agent, outranked_by=outranked_by)
        print("yield: {} is outranked by live candidate '{}' on Phase B score "
              "(PR-062 YIELD-AT-NEXT) -- the recommendation above stands unchanged and "
              "`claim` stays first-come; this exit code ({}) marks the yield only.".format(
                  args.agent, outranked_by, PHASE_B_YIELD_EXIT))
        return PHASE_B_YIELD_EXIT
    return 0


def cmd_show(args):
    bb = load_bb()
    t = bb.get("tasks", {}).get(args.task_id)
    if t is None:
        sys.exit("unknown task {}".format(args.task_id))
    print(json.dumps({args.task_id: t}, indent=2, ensure_ascii=False))
    detail = hc.read_json(detail_path(args.task_id))
    if detail:
        print("--- detail file ({}) ---".format(detail_path(args.task_id)))
        print(json.dumps(detail, indent=2, ensure_ascii=False))
    return 0


def cmd_claim(args):
    with hc.guarded():
        bb = load_bb()
        released = expire_claims(bb)
        t = bb.get("tasks", {}).get(args.task_id)
        if t is None:
            sys.exit("unknown task {}".format(args.task_id))
        unmet = deps_unmet(bb, t)
        if t.get("status") == "open" and unmet:
            sys.exit(
                "refused (cascade gate): {} depends on unfinished task(s): {}. "
                "Delegation is dependency-gated — claim an unblocked task instead: "
                "`python3 .harness/bin/blackboard.py next --agent {}`".format(
                    args.task_id, ", ".join(unmet), args.agent))
        if t.get("status") not in ("open", "review"):
            extra = " (claimed_by={})".format(t.get("claimed_by")) if t.get("claimed_by") else ""
            sys.exit("refused: {} is '{}'{} — not claimable.".format(args.task_id, t.get("status"), extra))
        lease = args.lease if args.lease is not None else default_lease()
        previous_status = t.get("status")
        t["status"] = "claimed"
        t["claimed_by"] = args.agent
        t["claim_expires_at"] = hc.iso_in(lease)
        save_bb(bb, args.agent)
    report_expirations(released)
    hc.log_event("task_claimed", task=args.task_id, holder=args.agent,
                 lease_seconds=lease, previous_status=previous_status)
    print("claimed {} for {} (lease {}s, expires {}).".format(
        args.task_id, args.agent, lease, t["claim_expires_at"]))
    print("next steps: acquire locks (lock.py acquire <path> --holder {a} --task {t}), "
          "then `blackboard.py update {t} --status in_progress --note \"<plan>\"`".format(
              a=args.agent, t=args.task_id))
    return 0


def cmd_update(args):
    note = resolve_note(args)
    if args.status and args.status not in VALID_STATUS:
        sys.exit("invalid --status '{}'. Valid: {}".format(args.status, ", ".join(VALID_STATUS)))
    if not (args.status or note or args.artifact):
        sys.exit("nothing to update: pass --status, --note (or --note-file/--note-stdin) and/or --artifact")
    if args.override_producer_check and not note:
        sys.exit("refused: --override-producer-check requires --note (or --note-file/--note-stdin) "
                  "explaining why (the reason is recorded to events.jsonl for audit)")
    if getattr(args, "allow_unconfirmed", False) and not note:
        sys.exit("refused: --allow-unconfirmed requires --note (or --note-file/--note-stdin) "
                  "explaining why a record ships without its confirming identity "
                  "(the reason is recorded to events.jsonl for audit)")
    with hc.guarded():
        bb = load_bb()
        released = expire_claims(bb)
        t = bb.get("tasks", {}).get(args.task_id)
        if t is None:
            sys.exit("unknown task {}".format(args.task_id))
        claimant = t.get("claimed_by")
        previous_status = t.get("status")
        override_used = False
        verifier_execute_used = False
        unconfirmed_allowed = None
        if args.status == "done":
            # MECHANICAL producer != approver guardrail -- AUTHORSHIP-FIRST (P-011).
            # Originally this gated on previous_status == 'review' BEFORE checking
            # authorship, which false-refused legitimate cross-agent verifiers who
            # had claimed the review task and moved it to claimed/in_progress
            # themselves (ev604/605, ev617/618) -- forcing honest actors into the
            # override path. Current status no longer matters: what matters is (a)
            # a handoff record exists at all (the task was actually reviewed by
            # someone), and (b) the acting agent differs from that handoff's
            # producer. A verifier who claimed/in_progress'd the review task may
            # verdict done with zero friction; only the original producer of
            # record is blocked.
            handoff = t.get("handoff")
            handoff_producer = handoff.get("from") if handoff else None
            refusal = None
            if not handoff:
                # P-022: a role=='verifier' task IS the review/execution step
                # itself (tournament verdicts, epic joins -- T-049/T-052/T-054/
                # T-092 precedent) -- there is no separate reviewer to hand off
                # to. Previously these had NO clean path and were forced through
                # --override-producer-check every time (audited: T-052, T-054
                # both overrode). Model it properly instead: allow done with NO
                # handoff when the task's role is 'verifier' AND the acting
                # agent differs from the task's created_by (someone other than
                # whoever authored the task executed/verdicted it). Self-done by
                # the creator is still refused below -- worker/thinker-role
                # tasks are completely unaffected, handoff is still required.
                if t.get("role") == "verifier" and args.agent != t.get("created_by"):
                    verifier_execute_used = True
                else:
                    refusal = (
                        "refused: {tid} cannot go to 'done' -- no handoff record exists (current "
                        "status '{prev}'). Mechanical guardrail (producer != approver): a task must "
                        "be handed off for review first -- `blackboard.py handoff {tid} --to-role "
                        "verifier --note \"...\"` -- before it can be marked done. Pass "
                        "--override-producer-check together with --note to force it."
                    ).format(tid=args.task_id, prev=previous_status)
            elif args.agent == handoff_producer:
                refusal = (
                    "refused: {tid} was handed off by '{producer}' -- the producer cannot "
                    "verdict their own work (producer != approver), regardless of current status "
                    "('{prev}'). A different agent must mark it done, or pass "
                    "--override-producer-check together with --note explaining why."
                ).format(tid=args.task_id, producer=handoff_producer, prev=previous_status)
            if refusal:
                if args.override_producer_check:
                    override_used = True
                    hc.log_event("producer_check_overridden", task=args.task_id, agent=args.agent,
                                 previous_status=previous_status, producer=handoff_producer,
                                 refused_reason=refusal, note=note)
                    print("WARNING: producer-check override used on {} by {}: {}".format(
                        args.task_id, args.agent, refusal))
                else:
                    hc.log_event("producer_check_refused", task=args.task_id, agent=args.agent,
                                 previous_status=previous_status, producer=handoff_producer,
                                 reason=refusal)
                    sys.exit(refusal)
            # PR-015's confirmation floor, wired to the one step that already
            # establishes a distinct identity. The guard immediately above has
            # just proven that `args.agent` is not the producer, so SDR-24.1 is
            # satisfied by construction and this gate recruits no extra party --
            # it asks the verifier who is already here to say what they verified.
            # The escape hatch mirrors --override-producer-check exactly: audited,
            # note-mandatory, never silent.
            pending = unconfirmed_records_for(args.task_id)
            if pending:
                gate = (
                    "refused: {tid} cannot go to 'done' -- it issued {n} active record(s) that "
                    "no distinct identity has confirmed: {ids}. PR-015 requires a confirming "
                    "identity; PR-038 requires it not be the author, and `precedent.py confirm` "
                    "enforces that itself. Run:\n"
                    "  python3 .harness/bin/precedent.py confirm {first} --agent {agent} "
                    "--outcome confirmed --note \"what you verified\"\n"
                    "(use --outcome narrowed with --scope if you restate the scope, or "
                    "--outcome rejected). Then retry. To close without it, pass "
                    "--allow-unconfirmed together with --note."
                ).format(tid=args.task_id, n=len(pending), ids=", ".join(pending),
                         first=pending[0], agent=args.agent)
                if getattr(args, "allow_unconfirmed", False):
                    unconfirmed_allowed = pending
                    hc.log_event("confirmation_gate_overridden", task=args.task_id,
                                 agent=args.agent, records=pending, note=note)
                    print("WARNING: closing {} with {} unconfirmed record(s): {}".format(
                        args.task_id, len(pending), ", ".join(pending)))
                else:
                    hc.log_event("confirmation_gate_refused", task=args.task_id,
                                 agent=args.agent, records=pending)
                    sys.exit(gate)
        if args.status:
            t["status"] = args.status
            if args.status in ("done", "failed"):
                t["completed_at"] = hc.now_iso()
                t["completed_by"] = args.agent
                t["claimed_by"] = None
                t["claim_expires_at"] = None
                # credit the PRODUCER (who handed the work off), not whoever
                # holds the claim at verdict time (usually the verifier)
                producer = (t.get("handoff") or {}).get("from") or claimant or args.agent
                bump_reputation_locked(producer, args.status)
            elif args.status == "open":
                t["claimed_by"] = None
                t["claim_expires_at"] = None
                t["handoff"] = None
        if args.artifact:
            arts = t.setdefault("artifacts", [])
            for art in args.artifact:
                if art not in arts:
                    arts.append(art)
        save_bb(bb, args.agent)
        if note:
            append_note(args.task_id, args.agent, note)
    report_expirations(released)
    # F7: log the acting agent explicitly on every status change, not just the
    # ambient CLAUDE_HARNESS_AGENT_ID default -- makes producer != approver
    # auditable from events.jsonl alone, without reconstructing from notes.
    hc.log_event("task_updated", task=args.task_id, agent=args.agent, status=args.status,
                 artifact=args.artifact, has_note=bool(note),
                 override_producer_check=override_used if args.status == "done" else None)
    if verifier_execute_used:
        # P-022: explicit, separately-greppable event for the verifier-execute
        # done path (distinct from producer_check_overridden -- this is not an
        # override, it's a sanctioned path with its own authorship guard).
        hc.log_event("verifier_execute_done", task=args.task_id, agent=args.agent,
                     created_by=t.get("created_by"))
    bits = []
    if args.status:
        bits.append("status={}".format(args.status))
    if args.artifact:
        bits.append("artifact+={}".format(", ".join(args.artifact)))
    if note:
        bits.append("note appended to {}".format(detail_path(args.task_id)))
    print("updated {}: {}".format(args.task_id, "; ".join(bits)))
    if args.status == "done":
        with hc.guarded():
            bb = load_bb()
        unlocked = [tid for tid, task in sorted(bb.get("tasks", {}).items())
                    if task.get("status") == "open" and not deps_unmet(bb, task)
                    and args.task_id in task.get("depends_on", [])]
        if unlocked:
            print("cascade unlocked: {} now claimable".format(", ".join(unlocked)))
    return 0


def cmd_handoff(args):
    note = resolve_note(args)
    if args.to_role not in VALID_ROLES:
        sys.exit("invalid --to-role '{}'. Valid: {}".format(args.to_role, ", ".join(VALID_ROLES)))
    with hc.guarded():
        bb = load_bb()
        released = expire_claims(bb)
        t = bb.get("tasks", {}).get(args.task_id)
        if t is None:
            sys.exit("unknown task {}".format(args.task_id))
        t["status"] = "review"
        t["handoff"] = {"to_role": args.to_role, "from": args.agent,
                        "note": note, "ts": hc.now_iso()}
        t["claimed_by"] = None
        t["claim_expires_at"] = None
        save_bb(bb, args.agent)
        if note:
            append_note(args.task_id, args.agent, "HANDOFF -> {}: {}".format(args.to_role, note))
    report_expirations(released)
    hc.log_event("task_handoff", task=args.task_id, from_agent=args.agent, to_role=args.to_role)
    print("handed off {} to role '{}'. A {} must now claim it and verdict done/open.".format(
        args.task_id, args.to_role, args.to_role))
    return 0


def cmd_reopen(args):
    """P-023: terminal-state resurrection, done properly instead of by hand-editing JSON.

    'done' and 'failed' are terminal today -- nothing in this CLI can move a task
    off them, so the only way back was hand-editing blackboard.json, which the
    harness explicitly forbids (claude.md Agency layer, ORCHESTRATION.md
    invariant table: blackboard.py is the ONLY sanctioned writer). This verb
    provides a narrow, audited escape hatch instead:
      (1) only acts on tasks whose status is currently 'done' or 'failed'
          (open/claimed/in_progress/blocked/review are refused -- reopen is not
          a generic status-setter, use `update` for those);
      (2) --note is MANDATORY -- no note is a silent resurrection and is
          refused outright, before any state is touched;
      (3) logs a `task_reopened` event to events.jsonl recording who (--agent)
          and why (the note), plus the previous terminal status;
      (4) resets the task to 'open', clearing claim/handoff/completion state
          the same way `update --status open` already does, so the task
          re-enters the claimable frontier cleanly (cascade gate re-evaluates
          depends_on normally on the next claim attempt).
    """
    note = resolve_note(args)
    if not note:
        sys.exit("refused: reopen requires --note (or --note-file/--note-stdin) explaining "
                  "why this terminal task is being resurrected -- no note means no reopen "
                  "(P-023: refuses silent resurrection)")
    with hc.guarded():
        bb = load_bb()
        released = expire_claims(bb)
        t = bb.get("tasks", {}).get(args.task_id)
        if t is None:
            sys.exit("unknown task {}".format(args.task_id))
        previous_status = t.get("status")
        if previous_status not in ("done", "failed"):
            sys.exit(
                "refused: {tid} is '{prev}', not terminal -- reopen only acts on 'done' or "
                "'failed' tasks (use `update {tid} --status ...` for non-terminal transitions)."
                .format(tid=args.task_id, prev=previous_status))
        t["status"] = "open"
        t["claimed_by"] = None
        t["claim_expires_at"] = None
        t["handoff"] = None
        t["completed_at"] = None
        t["completed_by"] = None
        save_bb(bb, args.agent)
        append_note(args.task_id, args.agent, "REOPEN (was {}): {}".format(previous_status, note))
    report_expirations(released)
    hc.log_event("task_reopened", task=args.task_id, agent=args.agent,
                 previous_status=previous_status, note=note)
    print("reopened {} (was '{}') -> 'open' by {}. Reason logged to events.jsonl and {}.".format(
        args.task_id, previous_status, args.agent, detail_path(args.task_id)))
    return 0


def cmd_add_task(args):
    if not re.match(r"^T-\d{3}$", args.id):
        sys.exit("invalid --id '{}': expected T-NNN (e.g. T-010)".format(args.id))
    if args.role not in VALID_ROLES:
        sys.exit("invalid --role '{}'. Valid: {}".format(args.role, ", ".join(VALID_ROLES)))
    if args.engine not in VALID_ENGINES:
        sys.exit("invalid --engine '{}'. Valid: {}".format(args.engine, ", ".join(VALID_ENGINES)))
    deps = [d.strip() for d in (args.depends_on or "").split(",") if d.strip()]
    with hc.guarded():
        bb = load_bb()
        if args.id in bb.get("tasks", {}):
            sys.exit("refused: task {} already exists".format(args.id))
        missing = [d for d in deps if d not in bb.get("tasks", {})]
        if missing:
            sys.exit("refused: unknown dependency task(s): {}".format(", ".join(missing)))
        bb["tasks"][args.id] = {
            "epic": args.epic,
            "title": args.title,
            "status": "open",
            "role": args.role,
            "engine": args.engine,
            "depends_on": deps,
            "claimed_by": None,
            "claim_expires_at": None,
            "priority": args.priority,
            "detail_file": str(detail_path(args.id).relative_to(hc.ROOT)),
            "artifacts": [],
            "handoff": None,
            "created_at": hc.now_iso(),
            "created_by": args.agent,
        }
        save_bb(bb, args.agent)
        hc.atomic_write_json(detail_path(args.id), {
            "id": args.id,
            "title": args.title,
            "description": args.description or "",
            "acceptance_criteria": [],
            "context_files": [],
            "notes": [],
        })
    hc.log_event("task_added", task=args.id, by=args.agent, depends_on=deps)
    print("added {} (role {}, engine {}, depends_on: {}). Fill acceptance_criteria in {}".format(
        args.id, args.role, args.engine, ", ".join(deps) or "none", detail_path(args.id)))
    return 0


def add_note_args(parser):
    """P-021: shared --note / --note-file / --note-stdin mutually-exclusive group.

    --note is plain argv text -- your shell expands backticks, $(), etc.
    BEFORE this CLI ever receives them, so a note containing those characters
    is corrupted (or worse, executed) at the shell, not by this tool. Use
    --note-file <path> or --note-stdin for byte-exact content containing
    shell metacharacters.
    """
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--note", default=None,
                     help="inline note text -- AVOID backticks/$()/other shell metacharacters "
                          "here, your shell expands them before this CLI sees them (P-021); "
                          "use --note-file or --note-stdin instead for hazardous content")
    grp.add_argument("--note-file", dest="note_file", default=None,
                     help="read note content byte-exact from a file; safe for backticks/$()")
    grp.add_argument("--note-stdin", dest="note_stdin", action="store_true", default=False,
                     help="read note content byte-exact from stdin; safe for backticks/$()")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--agent", default=hc.agent_id(), help="acting agent id")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", parents=[common],
                   help="board overview: counts, DAG gates, claimable frontier").set_defaults(func=cmd_status)

    p_next = sub.add_parser("next", parents=[common], help="dispatcher: highest-priority claimable task for you")
    p_next.add_argument("--role", choices=VALID_ROLES, default=None)
    p_next.add_argument("--engine", choices=VALID_ENGINES, default=None)
    p_next.set_defaults(func=cmd_next)

    p_show = sub.add_parser("show", parents=[common], help="dump one task (index entry + detail file)")
    p_show.add_argument("task_id")
    p_show.set_defaults(func=cmd_show)

    p_claim = sub.add_parser("claim", parents=[common], help="claim a task (refused if dependencies unmet)")
    p_claim.add_argument("task_id")
    p_claim.add_argument("--lease", type=int, default=None, help="seconds (default from state.json)")
    p_claim.set_defaults(func=cmd_claim)

    p_upd = sub.add_parser("update", parents=[common], help="update status / add note / register artifact")
    p_upd.add_argument("task_id")
    p_upd.add_argument("--status", default=None)
    add_note_args(p_upd)
    p_upd.add_argument("--artifact", action="append", default=None,
                       help="repeatable; each value is appended to the task's artifact list (values already present are skipped)")
    p_upd.add_argument("--override-producer-check", dest="override_producer_check", action="store_true",
                       default=False,
                       help="escape hatch for the mechanical producer!=approver guardrail on "
                            "--status done; requires --note/--note-file/--note-stdin (logged to events.jsonl)")
    p_upd.add_argument("--allow-unconfirmed", dest="allow_unconfirmed", action="store_true",
                       default=False,
                       help="close the task even though it issued active precedent records that "
                            "no distinct identity has confirmed (PR-015); requires "
                            "--note/--note-file/--note-stdin (logged to events.jsonl)")
    p_upd.set_defaults(func=cmd_update)

    p_ho = sub.add_parser("handoff", parents=[common], help="hand the task to another role (producer != approver)")
    p_ho.add_argument("task_id")
    p_ho.add_argument("--to-role", required=True)
    add_note_args(p_ho)
    p_ho.set_defaults(func=cmd_handoff)

    p_reopen = sub.add_parser("reopen", parents=[common],
                              help="P-023: resurrect a terminal ('done'/'failed') task back to 'open' "
                                   "(--note mandatory, logged as task_reopened)")
    p_reopen.add_argument("task_id")
    add_note_args(p_reopen)
    p_reopen.set_defaults(func=cmd_reopen)

    p_add = sub.add_parser("add-task", parents=[common], help="publish a new task on the board")
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--description", default="")
    p_add.add_argument("--role", default="worker")
    p_add.add_argument("--engine", default="any")
    p_add.add_argument("--depends-on", dest="depends_on", default="")
    p_add.add_argument("--priority", type=int, default=5)
    p_add.add_argument("--epic", default="E-01")
    p_add.set_defaults(func=cmd_add_task)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
