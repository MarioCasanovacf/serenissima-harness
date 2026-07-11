# Smoke Contention Report — T-010

Contention + crash-recovery smoke test exercising every path `audit_gen1` flagged as
untested (§4). Produced by `substrate-worker-1` (T-010). All commands below were run
live against the real `.harness/` runtime — no synthetic/mocked output. Working
directory for every command: `.`.

## Identity attribution note (read this first)

Every command in this report carries `--holder`/`--agent smoke-a` or `smoke-b`
explicitly on the CLI invocation, per protocol (identity flags always win over ambient
identity). However, the ambient session identity for this whole run was
`CLAUDE_HARNESS_AGENT_ID=substrate-worker-1` (per ORCHESTRATION.md / README.md
Identity section, CLIs log **both** the acting agent for the log line's `"agent"` field
*and* the flag-supplied `"holder"`). As a result, every event in `events.jsonl` below
shows `"agent": "substrate-worker-1"` (who ran the process) while the payload's
`holder`/`previous_holder`/`completed_by` fields correctly show `smoke-a` / `smoke-b`
(who the lock/claim/task update was performed *as*). **This is a known, expected split
— not a bug in this run** — and matches the substrate's documented identity model
(flags win for holder attribution; the process's ambient env is a separate "who
executed this CLI call" audit trail). Future readers of `events.jsonl` should not
confuse `"agent"` with `"holder"` when reconstructing who owned a lock/claim.

Baseline before any smoke actions: `events.jsonl` had 169 lines; `lock.py status`
showed only this report's own lock (`.harness/logs/smoke_contention_report.md`,
holder=substrate-worker-1, task=T-010) live.

---

## Path 1 — Busy refusal (two distinct holders, same path)

**Goal:** confirm a second holder is refused with `busy:` and process exit code 1
while the first holder's lock is live.

### Commands + verbatim output

```
$ python3 .harness/bin/lock.py acquire .harness/logs/smoke_scratch.txt --holder smoke-a --task T-010
acquired: .harness__logs__smoke_scratch.txt.lock (holder=smoke-a, ttl=900s)

$ python3 .harness/bin/lock.py acquire .harness/logs/smoke_scratch.txt --holder smoke-b --task T-010
busy: '.harness/logs/smoke_scratch.txt' held by 'smoke-a' (task T-010, acquired 2026-07-04T04:45:12Z, ttl 900s). Pick another task/file or wait for expiry.
EXIT_CODE=1

$ python3 .harness/bin/lock.py release .harness/logs/smoke_scratch.txt --holder smoke-a
released: .harness__logs__smoke_scratch.txt.lock
```

### Result

- `smoke-b`'s acquire attempt printed the exact `busy:` refusal message documented in
  `lock.py --help` and returned process exit code **1** (captured via `$?` immediately
  after the call, printed as `EXIT_CODE=1`).
- No `lock_acquired` event was written for the refused `smoke-b` attempt (refusals are
  not logged as events — only successful acquires/releases are; confirmed by
  cross-checking `events.jsonl` between the two acquire attempts, no line appears for
  the busy call).
- Released cleanly as `smoke-a`. Post-release `lock.py status` showed only the
  report's own lock — zero residue from Path 1.

---

## Path 2 — TTL steal (expired lock swept and reacquired by a different holder)

**Goal:** confirm that after a lock's TTL elapses, a different holder's acquire call
sweeps the expired lock and succeeds, logging `lock_acquired` with
`"stole_expired": true`.

**Deviation from the literal task-detail wording (documented, not silent):** the
task's `detail_file` (`T-010.json`) describes this step as `--ttl 1`, wait 2s. The
coordinator's dispatch for this run explicitly overrode that to **`--ttl 3`, sleep
4s**, citing a known substrate finding **G6** (recorded in `state.json
.evolution.next_audit_inputs`): *"harness_common ISO_FMT truncates sub-second
precision — short TTLs (--ttl 1) race truncation; deterministic only at >=3s (T-008
verify anomaly)"*. I followed the dispatch/G6 guidance (ttl=3, sleep=4) rather than the
task-detail's ttl=1 wording, since a 1s TTL is documented as racy given the substrate's
whole-second ISO-8601 timestamp truncation. This is the correct, deterministic way to
exercise this path; the acceptance criteria ("gains >=1 lock_acquired with
stole_expired:true") are satisfied identically either way.

### Commands + verbatim output

```
$ date -u +%Y-%m-%dT%H:%M:%SZ
2026-07-04T04:45:22Z
$ python3 .harness/bin/lock.py acquire .harness/logs/smoke_scratch.txt --holder smoke-a --task T-010 --ttl 3
acquired: .harness__logs__smoke_scratch.txt.lock (holder=smoke-a, ttl=3s)

$ sleep 4

$ date -u +%Y-%m-%dT%H:%M:%SZ
2026-07-04T04:45:31Z
$ python3 .harness/bin/lock.py acquire .harness/logs/smoke_scratch.txt --holder smoke-b --task T-010
acquired (expired lock swept): .harness__logs__smoke_scratch.txt.lock (holder=smoke-b, ttl=900s)
```

### events.jsonl evidence (verbatim, in order)

```
{"ts": "2026-07-04T04:45:22Z", "event": "lock_acquired", "agent": "substrate-worker-1", "path": ".harness/logs/smoke_scratch.txt", "holder": "smoke-a", "task": "T-010", "ttl_seconds": 3, "stole_expired": false, "refreshed": false}
{"ts": "2026-07-04T04:45:31Z", "event": "lock_acquired", "agent": "substrate-worker-1", "path": ".harness/logs/smoke_scratch.txt", "holder": "smoke-b", "task": "T-010", "ttl_seconds": 900, "stole_expired": true, "refreshed": false}
```

### Cleanup

```
$ python3 .harness/bin/lock.py release .harness/logs/smoke_scratch.txt --holder smoke-b
released: .harness__logs__smoke_scratch.txt.lock
```

### Result

- CLI printed the exact `"acquired (expired lock swept)"` phrasing.
- `events.jsonl` gained a `lock_acquired` event with `"holder": "smoke-b"` and
  **`"stole_expired": true"`** — acceptance criterion #1 satisfied.
- 9 real elapsed seconds (04:45:22Z acquire → 04:45:31Z steal, includes the acquire
  call itself plus `sleep 4`) confirmed the lock was genuinely expired (ttl=3s) before
  the steal, not a race.
- Released cleanly as `smoke-b`. Post-release, zero residue from Path 2.

---

## Path 3 — Lease expiry (auto-release to `open` on any subsequent `blackboard.py` call)

**Goal:** confirm a claimed task's lease auto-expires and is released back to `open`
by the next `blackboard.py` command (here, `status`), logging `claim_expired`.

**Deviation from literal task-detail wording:** same G6 rationale as Path 2 — used
`--lease 3` + `sleep 4` instead of the task-detail's `--lease 1` + wait 2s, per the
coordinator's explicit instruction. This produces a deterministic, non-racy result.

### Commands + verbatim output

#### 3a. Create the scratch task T-090

```
$ python3 .harness/bin/blackboard.py add-task --id T-090 --title "SCRATCH smoke artifact (T-010)" --role worker --engine any --priority 9 --epic E-03 --description "disposable lifecycle probe created and terminated by T-010" --agent substrate-worker-1
added T-090 (role worker, engine any, depends_on: none). Fill acceptance_criteria in .harness/tasks/T-090.json
```

#### 3b. Claim with a 3-second lease

```
$ date -u +%Y-%m-%dT%H:%M:%SZ
2026-07-04T04:45:47Z
$ python3 .harness/bin/blackboard.py claim T-090 --lease 3 --agent smoke-a
claimed T-090 for smoke-a (lease 3s, expires 2026-07-04T04:45:50Z).
next steps: acquire locks (lock.py acquire <path> --holder smoke-a --task T-090), then `blackboard.py update T-090 --status in_progress --note "<plan>"`
```

#### 3c. Sleep past the lease, then run `status` (any blackboard.py call triggers the sweep)

```
$ sleep 4

$ date -u +%Y-%m-%dT%H:%M:%SZ
2026-07-04T04:45:55Z
$ python3 .harness/bin/blackboard.py status
note: lease on T-090 (held by smoke-a) expired -> task released to open
Universal Agent Harness — blackboard (generation 1)
updated_at: 2026-07-04T04:45:56Z   by: lease-expiry
counts: done=9, in_progress=1, open=2

ID     STATUS       ROLE     ENGINE  CLAIMED_BY         DEPENDS_ON       TITLE
...
T-090  open         worker   any     -                  -                SCRATCH smoke artifact (T-010)
...
claimable now: T-005, T-090
```

### events.jsonl evidence (verbatim)

```
{"ts": "2026-07-04T04:45:42Z", "event": "task_added", "agent": "substrate-worker-1", "task": "T-090", "by": "substrate-worker-1", "depends_on": []}
{"ts": "2026-07-04T04:45:47Z", "event": "task_claimed", "agent": "substrate-worker-1", "task": "T-090", "holder": "smoke-a", "lease_seconds": 3, "previous_status": "open"}
{"ts": "2026-07-04T04:45:56Z", "event": "claim_expired", "agent": "substrate-worker-1", "task": "T-090", "previous_holder": "smoke-a"}
```

### Result

- The `status` call's stdout led with the exact auto-release printout: `"note: lease
  on T-090 (held by smoke-a) expired -> task released to open"`, and the board header
  itself changed to `by: lease-expiry` (a self-attributing sweep, not a manual actor).
- `events.jsonl` gained a **`claim_expired`** event with `"previous_holder":
  "smoke-a"` — acceptance criterion #1 (second half) satisfied.
- T-090 confirmed `status: open`, `claimed_by: null` in the board index after the
  sweep — no stale claim residue.

---

## Path 4 — Blocked path (claim → blocked → unblock to open)

**Goal:** exercise the `blocked` status transition and confirm a task can be moved
back to `open` afterward (unblock), on the now-open T-090.

### Commands + verbatim output

```
$ python3 .harness/bin/blackboard.py claim T-090 --agent smoke-a
claimed T-090 for smoke-a (lease 3600s, expires 2026-07-04T05:46:06Z).
next steps: acquire locks (lock.py acquire <path> --holder smoke-a --task T-090), then `blackboard.py update T-090 --status in_progress --note "<plan>"`

$ python3 .harness/bin/blackboard.py update T-090 --status blocked --note "smoke: simulating a hard blocker" --agent smoke-a
updated T-090: status=blocked; note appended to .harness/tasks/T-090.json

$ python3 .harness/bin/blackboard.py update T-090 --status open --agent smoke-a
updated T-090: status=open
```

### events.jsonl evidence (verbatim)

```
{"ts": "2026-07-04T04:46:06Z", "event": "task_claimed", "agent": "substrate-worker-1", "task": "T-090", "holder": "smoke-a", "lease_seconds": 3600, "previous_status": "open"}
{"ts": "2026-07-04T04:46:06Z", "event": "task_updated", "agent": "substrate-worker-1", "task": "T-090", "status": "blocked", "artifact": null, "has_note": true}
{"ts": "2026-07-04T04:46:06Z", "event": "task_updated", "agent": "substrate-worker-1", "task": "T-090", "status": "open", "artifact": null, "has_note": false}
```

### Post-transition detail-file verification

`.harness/tasks/T-090.json` `notes[]` gained `{"ts": "2026-07-04T04:46:06Z", "agent":
"smoke-a", "note": "smoke: simulating a hard blocker"}`; board index confirmed
`status: "open"`, `claimed_by: null` after the unblock call — acceptance criterion #3
(first half, "blocked ... exercised on T-090") satisfied.

---

## Path 5 — Failed path (terminal state + reputation bump)

**Goal:** claim T-090 again, mark it `failed`, and confirm `state.json`'s reputation
counters gain `tasks_failed: 1` for the holder (`smoke-a`).

### Baseline (before this path)

`smoke-a` had **no reputation entry at all** in `state.json` prior to this call
(`python3 -c "..."` lookup returned the literal string `"ABSENT"`), which makes the
post-call `tasks_failed: 1` unambiguous — there is no pre-existing count it could be
conflated with.

### Commands + verbatim output

```
$ python3 .harness/bin/blackboard.py claim T-090 --agent smoke-a
claimed T-090 for smoke-a (lease 3600s, expires 2026-07-04T05:46:18Z).
next steps: acquire locks (lock.py acquire <path> --holder smoke-a --task T-090), then `blackboard.py update T-090 --status in_progress --note "<plan>"`

$ python3 .harness/bin/blackboard.py update T-090 --status failed --note "smoke artifact terminal state (T-010) — intentional" --agent smoke-a
updated T-090: status=failed; note appended to .harness/tasks/T-090.json
```

### state.json reputation evidence (verbatim, after the call)

```json
"smoke-a": {
  "tasks_done": 0,
  "tasks_failed": 1,
  "last_outcome_at": "2026-07-04T04:46:18Z"
}
```

### events.jsonl evidence (verbatim)

```
{"ts": "2026-07-04T04:46:18Z", "event": "task_claimed", "agent": "substrate-worker-1", "task": "T-090", "holder": "smoke-a", "lease_seconds": 3600, "previous_status": "open"}
{"ts": "2026-07-04T04:46:18Z", "event": "task_updated", "agent": "substrate-worker-1", "task": "T-090", "status": "failed", "artifact": null, "has_note": true}
```

### T-090 final board-index state (verbatim)

```json
"T-090": {
  "epic": "E-03",
  "title": "SCRATCH smoke artifact (T-010)",
  "status": "failed",
  "role": "worker",
  "engine": "any",
  "depends_on": [],
  "claimed_by": null,
  "claim_expires_at": null,
  "priority": 9,
  "detail_file": ".harness/tasks/T-090.json",
  "artifacts": [],
  "handoff": null,
  "created_at": "2026-07-04T04:45:42Z",
  "created_by": "substrate-worker-1",
  "completed_at": "2026-07-04T04:46:18Z",
  "completed_by": "smoke-a"
}
```

### Result

- `blackboard.py update --status failed` bumped `smoke-a`'s reputation counter from
  no-entry to `tasks_failed: 1` (`tasks_done: 0`) — acceptance criterion #3 (second
  half, "reputation tasks_failed bumped for its holder") satisfied.
- T-090 is now in its expected terminal state: `status: "failed"`, `claimed_by:
  null` (terminal statuses clear the live claim), `completed_by: "smoke-a"`. This is
  the correct final resting state for the scratch task — no further cleanup of T-090
  is needed or expected.

---

## Residue check (final)

Run after all five paths, before releasing the report lock or handing off.

### `lock.py status`

```
$ python3 .harness/bin/lock.py status --agent substrate-worker-1
PATH                                         HOLDER               TASK     ACQUIRED_AT            STATE
.harness/logs/smoke_contention_report.md     substrate-worker-1   T-010    2026-07-04T04:45:01Z   live
```

**Only** this report's own lock (mine, for this task, still legitimately held while
writing this file) is live. Zero smoke-a/smoke-b lock residue.

### `blackboard.py status`

```
$ python3 .harness/bin/blackboard.py status
Universal Agent Harness — blackboard (generation 1)
updated_at: 2026-07-04T04:46:18Z   by: smoke-a
counts: done=9, failed=1, in_progress=1, open=1

ID     STATUS       ROLE     ENGINE  CLAIMED_BY         DEPENDS_ON       TITLE
T-000  done  ...
...
T-005  open         worker   any     -                  -                Remote messenger hook v0 ...
...
T-010  in_progress  worker   claude  substrate-worker-  T-008            Contention + crash-recovery smoke test (untested
T-090  failed       worker   any     -                  -                SCRATCH smoke artifact (T-010)

claimable now: T-005
```

- `T-090` sits in `failed` — its expected, intentional terminal state from Path 5 (not
  stale: `claimed_by: null`, no dangling claim/lease).
- `T-010` sits `in_progress`, claimed by `substrate-worker-1` — that is *this task*,
  legitimately still open pending this report + handoff.
- No other task shows a claimed/stale entry. `T-005` (pre-existing, unrelated open
  task) is unaffected.

### Physical scratch file check

```
$ ls -la .harness/logs/smoke_scratch.txt
ls: .harness/logs/smoke_scratch.txt: No such file or directory
```

The physical file `smoke_scratch.txt` was **never created** — as anticipated, `lock.py
acquire`/`release` operate purely on lock-file metadata under `.harness/locks/` and do
not require (or create) the target path to exist on disk. No cleanup of a physical
file was necessary.

### Verdict

**Zero lock/claim residue** beyond the expected/legitimate: this report's own live
lock (released immediately after this file is finalized, per protocol) and T-090's
intentional terminal `failed` state.

---

## Acceptance criteria checklist (from `.harness/tasks/T-010.json`)

1. "events.jsonl gains >=1 lock_acquired with stole_expired:true (TTL steal) and >=1
   claim_expired (lease auto-release)" — **satisfied**: see Path 2 (`stole_expired:
   true` for holder=smoke-b) and Path 3 (`claim_expired`, previous_holder=smoke-a).
2. "busy refusal between two distinct holders demonstrated with captured exit 1
   output" — **satisfied**: see Path 1 (`busy:` message + `EXIT_CODE=1`).
3. "blocked and failed paths exercised on scratch task T-090; reputation
   tasks_failed bumped for its holder" — **satisfied**: see Path 4 (blocked → open)
   and Path 5 (failed, `smoke-a` reputation `tasks_failed: 1`).
4. ".harness/logs/smoke_contention_report.md contains every command with observed
   output; zero lock/claim residue at the end" — **satisfied**: this file, plus the
   Residue check section above.

## Friction notes (for the next audit)

- **G6 confirmed in practice**: the task-detail file (`T-090.json`... actually
  `T-010.json`) literally specifies `--ttl 1` / `--lease 1` with a 2s wait, which the
  coordinator's dispatch overrode to `--ttl 3` / `--lease 3` with a 4s wait, citing
  G6. I followed the dispatch. Recommendation: update the task-detail description
  itself (not just the audit's `next_audit_inputs` note) so a worker reading only
  `T-010.json` (without a coordinator dispatch annotating the correction) does not
  attempt the racy `--ttl 1` path and get a flaky/non-deterministic result.
- **Identity attribution split confirmed in practice** (see the note at the top of
  this report): every `events.jsonl` line for the smoke-a/smoke-b actions logs
  `"agent": "substrate-worker-1"` (the ambient session identity that ran the CLI
  process) while `holder`/`previous_holder`/`completed_by` correctly carry
  `smoke-a`/`smoke-b`. This is expected given the harness's documented identity model
  but is worth calling out explicitly in `README.md`'s Identity section (or wherever
  `events.jsonl`'s schema is documented) so a future log-reader doesn't misattribute
  who a lock/claim belonged to by looking only at the `agent` field.
- No other new friction surfaced; all five paths behaved exactly as the substrate's
  own `--help` text and README describe.
