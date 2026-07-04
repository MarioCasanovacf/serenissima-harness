# `.harness/` — Runtime Substrate (Generation 0)

The local, file-based **Runtime layer (R)** of the CAR decomposition. No databases,
no external APIs: plain files + deterministic stdlib-only CLIs. Every agent
(Claude, Gemini, human) coordinates through this directory.

Read [ORCHESTRATION.md](../ORCHESTRATION.md) first for the delegation topology;
this file is the substrate reference.

## Directory map

```
.harness/
 ├── active_role            Current persona for a solo Claude runner (thinker|worker|verifier).
 │                          Default: thinker (safest — no source changes).
 ├── blackboard.json        Shared task index + DAG topology. NEVER hand-edit;
 │                          mutate only via bin/blackboard.py (guarded, atomic).
 ├── state.json             Execution limits, human gates, agent capability
 │                          contracts, reputation counters, evolution queue.
 ├── task.json              Mirror of the current task for single-runner sessions.
 ├── plan.md                WHY/ordering (Thinkers). The blackboard is WHO/WHAT-NOW.
 ├── recontext_evidence.md  Gemini ReContext evidence replay buffer (gemini.md §4B).
 ├── tasks/                 One detail file per task (T-XXX.json): description,
 │                          acceptance_criteria, notes[]. Written only by the
 │                          claiming agent (via blackboard.py update --note).
 ├── locks/                 Write locks: <rel__path>.lock (TTL JSON payloads)
 │                          + .guard (flock target serializing state mutations).
 ├── logs/
 │    ├── transcript.jsonl  Tool calls via the PostToolUse hook — fires ONLY in
 │    │                     sessions rooted in this workspace (see pillar table).
 │    └── events.jsonl      Semantic events: claims, hand-offs, locks, expiries
 │                          (written by the CLIs).
 └── bin/                   The deterministic control plane (python3 >= 3.9, stdlib-only):
      ├── blackboard.py     status | next | show | claim | update | handoff | add-task
      ├── lock.py           acquire | release | status | sweep
      ├── session.py        register <name> [--ttl 7200] | unregister <name> | list — session-holder registry (P-002 fix, see §Identity)
      ├── ast_index.py      build | query <symbol> [--contains] — AST symbol map (.harness/index/symbols.json)
      ├── log_event.py      hook: transcript logger (fail-open)
      ├── check_lock.py     hook: blocks edits to files write-locked by another agent, unless the holder is a registered session holder (fail-open)
      └── harness_common.py shared helpers (guarded mutation, atomic writes, TTL logic, session_holders())
```

## Core protocols

### Task lifecycle (enforced by `blackboard.py`)
`open → claimed → in_progress → review → done` (or `blocked` / `failed` / back to `open`).

1. `blackboard.py next --agent <you> [--role r] [--engine e]` — dispatcher suggests work.
2. `blackboard.py claim <T-ID> --agent <you>` — **refused if any `depends_on` is not `done`**
   (the cascade gate) or if already claimed (collision prevention). Claims carry a lease;
   expired leases auto-release on every command (anti-stall).
3. `lock.py acquire <path> --holder <you> --task <T-ID>` for **every** file you will edit.
4. `blackboard.py update <T-ID> --status in_progress --note "<one-line plan>"`.
5. Work. Record artifacts (`update --artifact <path>`) and honest notes: state what you
   *expected* vs what *actually happened* (Decision Observability).
6. `blackboard.py handoff <T-ID> --to-role verifier --note "<replayable evidence>"` —
   a producer **never** marks its own task `done`.
7. Verifier claims the review task, replays the evidence adversarially, then
   `update <T-ID> --status done` (accept) or `--status open --note "REJECTED: ..."` (send back).
   `failed` is reserved for abandoned/impossible tasks.
8. `lock.py release <path> --holder <you>` for everything you locked.

### Identity
Cross-session/cross-engine runners: `export CLAUDE_HARNESS_AGENT_ID=<name>` (or pass
`--agent`/`--holder` explicitly, which always wins). In-session bench subagents use their
bench name. Default identity is `main`.

**Session holders (P-002 fix):** an in-session subagent whose identity is overridden
per-call (`--agent`/`--holder`) used to self-block on its own live locks, because
`check_lock.py` only ever compared a lock's `holder` against the *ambient*
`CLAUDE_HARNESS_AGENT_ID`. A coordinator now declares which agent names are coordinated
within THIS session via `session.py register <name> [--ttl 7200]` /
`unregister <name>` / `list` (TTL entries in `.harness/session_holders.json`,
`harness_common.session_holders()` reads live ones). `check_lock.py` allows a write when
`holder == me` **or** `holder in session_holders()`. Registration is an explicit
coordinator act — `blackboard.py claim` and `lock.py acquire` never auto-register a
holder — so **registered = this session's coordinated agents ONLY**;
cross-session/cross-engine holders (another terminal, Gemini/Antigravity, a different
machine) are never auto-registered and their locks keep blocking exactly as before.

**events.jsonl attribution (flags-win model):** the `agent` field records the ambient
session identity that RAN the CLI; `holder` / `previous_holder` / `completed_by` carry
the flag-supplied identity. When a coordinator or verifier operates on behalf of other
holders, `agent` ≠ `holder` **by design** — read `holder` for ownership, `agent` for
who executed the command.

### Locks
- One lock file per workspace file; name = relative path with `/` → `__`, plus `.lock`.
- TTL (default 900 s from `state.json`) — a crashed holder never stalls the swarm;
  re-acquiring your own lock refreshes it (heartbeat).
- Claude Code sessions get **mechanical** enforcement via the PreToolUse hook
  (`check_lock.py`); other engines (Gemini/Antigravity, humans) must call `lock.py`
  voluntarily — the contract is engine-agnostic, the hook is Claude-side sugar.

### Observability pillars → concrete files
| Pillar (AHE) | Implementation here |
|---|---|
| Component | Everything under `.harness/` + NLAHs are explicit files, tracked by **git**; harness changes = commits (rollback = revert). |
| Experience | `logs/events.jsonl` (semantic lifecycle events, written by the CLIs — the engine-agnostic floor) + `logs/transcript.jsonl` (hook-fed tool calls, ONLY in Claude Code sessions rooted in this workspace; coordination sessions rooted elsewhere do not populate it). |
| Decision | Task notes record *expected vs actual*; verifier verdicts expose thinking–action gaps; `<thinking>` blocks stay in-session (subscription CLIs don't expose them to hooks — the notes are the durable proxy). |

### Governance (harness evolution, claude.md §5)
`claude.md` / `gemini.md` are **never** edited casually. Mutations flow:
`logs → audit (T-006-style) → state.json evolution.pending_proposals → human approval
(state.json human_gates) → gated apply + re-verification (T-007-style) → generation bump
+ git commit`.

### Never nest `guarded()`
A second `guarded()` inside the first deadlocks (flock on a second handle). All
CLI code paths take the guard exactly once.
