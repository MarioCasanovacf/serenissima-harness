# USAGE.md — Operating the Universal Agent Harness

You've never seen this repo. You have a goal and want real work done, not to develop the
harness itself. This is the only doc you need to get from zero to a finished task. For the
*design rationale* behind any rule here, see [ORCHESTRATION.md](ORCHESTRATION.md) (topology)
and [.harness/README.md](.harness/README.md) (substrate reference) — this doc never
contradicts either.

## 1. The mental model, in one paragraph

Work lives as tasks on a shared **blackboard** (`.harness/blackboard.json`), wired into a
**dependency DAG**: a task is claimable only when every task it `depends_on` is `done` (the
*cascade gate* — enforced by data, not politeness), and everything else on the unblocked
frontier can be worked **in parallel** by different agents/engines/terminals at once, with
collisions prevented by **claims** (task ownership, time-boxed by a lease) and **write locks**
(file ownership, TTL-based, in `.harness/locks/`) — both auto-expire, so a crashed or looping
agent returns its work to the pool instead of freezing everyone else. The one hard social rule
riding on top of the mechanics: **producer ≠ approver** — whoever does the work hands off to a
different role for verdict, never marks its own task `done`. Depth: [ORCHESTRATION.md](ORCHESTRATION.md) §1-3.

## 2. Posing a goal: turn intent into tasks

Two ways to get a goal onto the board:
- **Small/simple**: write the tasks yourself with `blackboard.py add-task`, wiring real
  `--depends-on` edges only where a task literally consumes another task's artifact (no
  edge = independent = parallelizable).
- **Multi-step/uncertain**: delegate decomposition to the `orchestration-planner` bench agent
  (thinker role) — it designs the DAG, writes `.harness/plan.md`, and publishes the tasks for
  you. This is what happened for the real `mdtoc` project below (T-020 planned T-021..T-029).

**Worked mini-example** (verified live on this board — inspect it yourself with
`python3 .harness/bin/blackboard.py show T-091` / `show T-092`; re-running the exact commands
below will now fail with "already exists" since these IDs are taken — pick fresh `T-0NN` ids
for your own goal):

```bash
python3 .harness/bin/blackboard.py add-task --agent <you> \
  --id T-091 --title "producer task" --role worker --engine any --priority 9 \
  --epic my-goal --description "what T-091 actually produces"

python3 .harness/bin/blackboard.py add-task --agent <you> \
  --id T-092 --title "dependent task" --role verifier --engine any --priority 9 \
  --epic my-goal --depends-on T-091 --description "consumes T-091's artifact"
```

`add-task` refuses unknown `--depends-on` ids and refuses to redefine an existing `--id`, so
edges are always real by construction. `blackboard.py status` now shows T-091 as
`claimable now` and T-092 as `gated (cascade): T-092 waits for T-091` — exactly the DAG you asked for.

## 3. Dispatching and working a task

| Step | Command |
|---|---|
| Find work | `python3 .harness/bin/blackboard.py next --agent <you> --role worker` |
| Claim (cascade-gated) | `python3 .harness/bin/blackboard.py claim <T-ID> --agent <you>` |
| Lock **every** file you'll touch | `python3 .harness/bin/lock.py acquire <path> --holder <you> --task <T-ID>` |
| Announce | `blackboard.py update <T-ID> --status in_progress --note "plan: ..."` |
| Work, then record | `blackboard.py update <T-ID> --artifact <path>` / `--note "expected X, got Y"` |
| Hand off (never self-approve) | `blackboard.py handoff <T-ID> --to-role verifier --note "<replayable evidence>"` |
| Release locks | `python3 .harness/bin/lock.py release <path> --holder <you>` |

Continuing the worked example above, the exact sequence that closed out T-091 (all verified live):

```bash
python3 .harness/bin/blackboard.py claim T-091 --agent substrate-worker-2
python3 .harness/bin/lock.py acquire SCRATCH-usage-example.md --holder substrate-worker-2 --task T-091
python3 .harness/bin/blackboard.py update T-091 --status in_progress --agent substrate-worker-2 --note "plan: ..."
python3 .harness/bin/blackboard.py update T-091 --agent substrate-worker-2 --artifact SCRATCH-usage-example.md
python3 .harness/bin/blackboard.py handoff T-091 --to-role verifier --agent substrate-worker-2 --note "..."
python3 .harness/bin/lock.py release SCRATCH-usage-example.md --holder substrate-worker-2
```

Trying `claim T-092 --agent substrate-worker-2` at this point still refuses:
`refused (cascade gate): T-092 depends on unfinished task(s): T-091.` — because handing off
puts a task in `review`, not `done`; only a verifier's `update --status done` clears the gate.

**Running agents — in-session vs. a second terminal:**
- *In-session fan-out*: a coordinator session spawns bench agents (`.claude/agents/*.md`,
  e.g. `substrate-worker`) as subagents over the frontier; Claude Code sessions get **mechanical**
  lock enforcement via the PreToolUse hook (`check_lock.py`) — an Edit/Write to a file another
  agent holds is blocked automatically.
- *Second terminal / another engine*: `export CLAUDE_HARNESS_AGENT_ID=<name>` before running any
  harness CLI, or just pass `--agent`/`--holder` explicitly on every call (flags always win over
  the env var). That session follows the same CLI protocol above; there is no hook to save it
  from itself, so lock discipline is voluntary but load-bearing.

## 4. Reading the board

`python3 .harness/bin/blackboard.py status` prints: task counts by status, a table
(`ID STATUS ROLE ENGINE CLAIMED_BY DEPENDS_ON TITLE`), the claimable frontier, and every
cascade gate currently blocking an open task. Lifecycle:

```
open ──claim──▶ claimed ──update──▶ in_progress ──handoff──▶ review ──verdict──▶ done
```

`review` means a producer finished and is waiting on a *different* agent to verdict; `done`
means a verifier already replayed the evidence and accepted it — never treat `review` as
finished. A cascade-gate refusal (`refused (cascade gate): ... depends on unfinished task(s)`)
is not a bug to route around — pick another unblocked task instead (`blackboard.py next`).

For a one-shot synthesized view (frontier, in-flight leases, review queue, lock liveness,
anomalies), ask for it in a Claude Code session and the `harness-status` skill
(`.claude/skills/harness-status/SKILL.md`) runs `blackboard.py status` + `lock.py status` +
`tail .harness/logs/events.jsonl` for you and narrates the result.

## 5. THE GOLDEN RULES — do not skip

> 1. **Identity & registration**: an in-session subagent whose identity is overridden per-call
>    (`--agent`/`--holder`) must be registered by the **coordinator** —
>    `session.py register <name>` — or it self-blocks on its own live locks. Registration is a
>    deliberate coordinator act only: **cross-session/cross-engine holders (another terminal,
>    Gemini, a different machine) are never registered**, and stay mechanically lock-enforced.
> 2. **Lock before every edit, release after.** One lock per file, TTL-bounded; re-acquiring
>    your own lock refreshes it.
> 3. **Producer never marks its own task `done`.** Workers only `handoff`; a different agent verdicts.
> 4. **Human gates — these ALWAYS require explicit human approval, verbatim from `state.json`:**
>    - git push or any network publication of workspace content
>    - deleting files outside .harness/ scratch areas
>    - activating or sending remote webhook notifications (T-005) for the first time
>    - mutating claude.md or gemini.md (harness generation bump via the §5A verification gate)
> 5. **Never hand-edit `blackboard.json`** (or `state.json`) — mutate only through the CLIs
>    (`blackboard.py`, `lock.py`, `session.py`), which serialize writes under a single guard.
> 6. **Respect `state.json` limits**: 50 steps/task, 300s/command, 3 retries per failure, 900s
>    default lock TTL, 3600s default claim lease, 3 max parallel workers.

The cost of skipping rule 3 is not hypothetical: while verifying this doc's worked example, a
`blackboard.py update` call that accidentally omitted `--agent` used the default identity and
set the scratch task straight to `done` — a live self-approval slip, caught and reverted
immediately (see `T-091.json` notes). It cost one bogus `+1` to a reputation counter in
`state.json` that no CLI can cleanly retract; that's the actual blast radius of this rule, and
exactly why it exists.

## 6. Where the evidence lives

- `.harness/logs/events.jsonl` — semantic lifecycle events (claim/lock/handoff/expiry), written
  by the CLIs themselves. This is the **engine-agnostic floor**: every engine gets it for free.
- `.harness/logs/transcript.jsonl` — every tool call, hook-fed. **It only fills in Claude Code
  sessions whose root is this repo** — a coordination session opened elsewhere never populates
  it. Don't rely on it for cross-engine or cross-session attribution; use `events.jsonl`.
- Read `agent` vs. `holder` in `events.jsonl` carefully: `agent` is whoever *ran* the CLI in
  this ambient session, `holder`/`from_agent` is whoever the flags say *owns* the action — they
  differ by design whenever one session acts on another's behalf (e.g. a just-verified real
  line: `{"event":"task_handoff","agent":"main","from_agent":"substrate-worker-2",...}`).
- `.harness/tasks/T-XXX.json` — one detail file per task; `notes[]` record expected-vs-actual
  (decision observability) and are the durable proxy for reasoning that never leaves a session.
- `.harness/logs/audit_gen*.md` — the evolution audits (see §7).
- **Worked reality**: the `mdtoc` epic (T-020..T-029, `projects/mdtoc/`) is a real external
  project built entirely through this protocol — planner decomposition, a disjoint-ownership
  parallel frontier, a tournament node (3 candidate sluggers + one verifier verdict), and a
  final join. Read any `T-02X.json` handoff note for a real replayable evidence string. As of
  this writing T-028 is still `in_progress` (claimed by another worker) — do not touch
  `projects/mdtoc/` files; only read them.

## 7. Evolution, in two lines

Frictions you hit while working (a missing convention, a CLI gap, a rough edge) belong in
`state.json evolution.next_audit_inputs`; an `evolution-analyst` audit later turns accepted
patterns from there into `state.json evolution.pending_proposals`, which only become a new
harness generation after human approval and re-verification (`claude.md` §5A).
