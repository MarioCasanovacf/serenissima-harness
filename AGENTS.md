# AGENTS.md — Directory of Agents, Skills, Hooks & Loops

This file is the machine-readable directory of every reusable capability that ships with
the Universal Agent Harness: who the resident agents are, which skills exist, which hooks
enforce the rules, and which loops drive repeated work. AI coding agents (Claude Code,
Gemini/Antigravity, Cursor, or any CLI-capable engine) should read this before deciding
how to route a task.

The behavioral contracts live elsewhere and take precedence: `claude.md` / `gemini.md`
(per-engine constitutions) and `ORCHESTRATION.md` (the cross-engine topology contract).
This file is the index, not the law.

---

## Agents — the bench

Definitions in [`.claude/agents/`](.claude/agents/). Each is a role on the blackboard,
not a personality: the board (`.harness/blackboard.json`) decides who may do what.

| Agent | Mandate | Hard limits |
|---|---|---|
| [`orchestration-planner`](.claude/agents/orchestration-planner.md) | Decompose a goal into blackboard tasks with a real dependency-DAG; maintain `.harness/plan.md` | Never edits source code |
| [`substrate-worker`](.claude/agents/substrate-worker.md) | Execute open tasks end-to-end: claim, lock, implement, test in a bounded goal-mode loop, hand off with replayable evidence | Never marks its own work `done` |
| [`harness-verifier`](.claude/agents/harness-verifier.md) | Adversarially replay worker evidence on tasks in `review`; verdict `done` or reopen; sweep stale locks/leases | Read-and-run only; never fixes code itself |
| [`evolution-analyst`](.claude/agents/evolution-analyst.md) | Parse `.harness/logs` trajectories, build a failure taxonomy, write falsifiable mutation proposals (§5A audits) | Proposes only; never applies mutations |
| [`research-librarian`](.claude/agents/research-librarian.md) | Answer questions about the research corpus (papers, fetched docs, reference repos) with exact file/page citations | Read-only |
| [`context-scout`](.claude/agents/context-scout.md) | Before planning: map the context a request touches into a cited brief (`.harness/briefs/`) and grill the request — explicit vs assumed, ranked clarifying questions (feeds U3) | Never edits source, never designs the DAG, never guesses human-only answers |

**Intent → agent routing:**

- New epic or ambiguous request, before any planning → `context-scout` (brief first)
- New goal, no tasks on the board yet → `orchestration-planner`
- Open tasks on the claimable frontier → `substrate-worker` (one per parallel slot)
- Any task sitting in `review` → `harness-verifier` (must differ from the producer)
- "Why did X fail?", "what should the next generation change?" → `evolution-analyst`
- "What does paper/repo Y say?" → `research-librarian`

## Skills

Definitions in [`.claude/skills/`](.claude/skills/).

| Skill | Trigger | What it does |
|---|---|---|
| [`harness-status`](.claude/skills/harness-status/SKILL.md) | "board status", "what is the harness doing" | Prints the live board: task DAG, claimable frontier, cascade gates, active write-locks, recent events |

## Codex-native adapter

Codex reads this `AGENTS.md` as the durable repository contract. Its native bench lives in
`.codex/agents/` and mirrors all six harness mandates with Codex project-agent TOML files:
`orchestration_planner`, `substrate_worker`, `harness_verifier`, `evolution_analyst`, and
`research_librarian`, plus the pre-planning `context_scout`. These are engine adapters for the
same blackboard roles, not a second source of task truth.

Reusable Codex workflows live in `.agents/skills/`. `harness-status` is observational,
`harness-claim-next` runs the legal claim→lock→work→handoff lifecycle, and
`harness-orchestrate` coordinates a whole frontier through native Codex subagents. The last
skill explicitly requests delegation, so Codex may fan out independent tasks while respecting
both `.harness/state.json limits.max_parallel_workers` and `.codex/config.toml agents.max_threads`.
Every worker instance receives a distinct harness identity; every verdict comes from an identity
different from the producer.

The repository is also a Codex plugin through `.codex-plugin/plugin.json`. Plugin installation
exposes the reusable skills; opening the repository additionally activates the project-scoped
agent profiles and config. Hooks remain optional engine adapters: absence of a Codex hook never
waives the explicit `lock.py acquire` protocol or the blackboard's mechanical lifecycle gates.

Codex data-loss safety is defense in depth. [`.codex/rules/data-loss.rules`](.codex/rules/data-loss.rules)
forbids the canonical destructive command families before sandbox escalation; the project and
plugin `PreToolUse` configurations call `.harness/bin/prevent_data_loss.py` to catch additional
shell, language-runtime, Git-discard, and patch-deletion forms. Intentional cleanup must use
`.harness/bin/safe_delete.py quarantine`, which moves paths into `.harness/trash` with an audited
manifest and supports non-overwriting restoration. The CLI intentionally exposes no purge verb.

## Hooks

Wired in [`.claude/settings.json`](.claude/settings.json); scripts in `.harness/bin/`.
Hooks are the mechanical layer — the reason rules are refusals instead of promises.

| Event | Matcher | Script | Enforces |
|---|---|---|---|
| `SessionStart` | — | `log_event.py` | Experience observability: session start recorded in `transcript.jsonl` |
| `PostToolUse` | `*` | `log_event.py` | Every tool call logged — the flight recorder agents don't have to remember |
| `Stop` | — | `log_event.py` | Session end recorded |
| `PreToolUse` | `Edit\|Write\|MultiEdit\|NotebookEdit` | `check_lock.py` | TTL write-locks: an edit to a file locked by another agent is refused before it lands |

Note: hooks are project-scoped — they fire only in sessions rooted in this repo (P-003).
`events.jsonl` (written by the CLIs themselves) is the engine-agnostic floor when hooks
are absent.

## Loops

The harness has three load-bearing loops. None are scheduled/cron loops — all are
demand-driven; that absence is deliberate (rejected as unneeded in the gen-5 intake).

| Loop | Driver | Bound |
|---|---|---|
| **Goal-mode loop** — edit-test-fix against one command | `python3 .harness/bin/goal_mode.py run --cmd "<test cmd>"` | Mechanically bounded: exit 3 when `max_retries_per_failure` is reached; the command is refused until a `reset`. No agent can loop forever chasing a failing test |
| **Review loop** — claim → work → handoff → verdict | `blackboard.py` lifecycle | Producer ≠ approver enforced at the `done` transition; rejected work returns to `open` |
| **Evolution loop** — logs → proposals → adversarial verification → human gate → generation bump | §5A of `claude.md`, run by `evolution-analyst` + the coordinator | Human-gated; every applied mutation is a git commit (git is the undo button) |

---

## Extension patterns

Patterns proven in sibling deployments of this harness, for anyone forking it. Each is a
shape you can copy, not code you must import:

- **Persona bench** — a domain squad of specialist agents (e.g. a tactical-analysis bench
  with a data engineer, domain analysts, and a mandatory `red-team-auditor` who
  stress-tests the plan). Works well when the domain has many orthogonal lenses; keep the
  adversarial seat — it is the persona-bench equivalent of producer ≠ approver.
- **Reviewer panel** — N reviewer agents with deliberately non-overlapping mandates
  (framing / data provenance / statistical validity / reproducibility) plus a skill that
  runs the full panel and synthesizes flags. The multi-verifier version of the review loop.
- **Ops skill pack** — many small, sharply-scoped skills per operational surface
  (deploy checklist, log queries, cost estimation, security audits), most of them
  read-only/report-only by default, with mutation variants kept separate.
- **Command lifecycle** — user-facing slash commands that walk a human through a workflow
  (setup → apply → expand), each a two-agent drafter/reviewer pair internally.

External references that shaped this directory's structure:
[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) (repo anatomy:
`agents/` + `skills/` + `hooks/` + a root index, multi-engine setup docs) and
[davidondrej/skills](https://github.com/davidondrej/skills) (category-grouped skills,
one `SKILL.md` per folder).

## Gemini-native adapter

Gemini CLI loads the existing `gemini.md`, this directory, `ORCHESTRATION.md`, and the scoped
`GEMINI_ADAPTER.md` interpretation through
`.gemini/settings.json`; this avoids the `GEMINI.md`/`gemini.md` filename collision on
case-insensitive filesystems. Six bounded, tool-isolated project agents live in
`.gemini/agents/`. Namespaced `/harness:*` commands in `.gemini/commands/harness/` provide
status, claim, orchestration, verification, audit, and research entry points, each with an
explicit single-agent fallback where preview subagents are unavailable.

Antigravity discovers the reusable workflows in `.agents/workflows/`, including separate
work-frontier and review-queue contexts so producer ≠ approver survives outside Gemini CLI.
For unattended execution, `.harness/bin/gemini_headless_runner.py` invokes Gemini CLI with
`stream-json`, bounded prompts and distinct identities, preserving raw events and exit codes
without bypassing approvals or mutating the blackboard lifecycle.

## Multi-engine note

Claude Code reads `.claude/` natively, and the repo ships plugin packaging
(`.claude-plugin/`) so it can be installed as a Claude Code plugin straight from GitHub.
Gemini joins through the native CLI agents and commands, the Antigravity workflow pack, or the
headless JSONL runner described above. The numbered operator-local prompt bridge remains a
fallback when the installed Gemini surface does not expose native subagents or workflows.
Any other engine can participate by speaking the CLI contract in `ORCHESTRATION.md` §2;
the board does not care who you are, only whether your claim is legal.

**Codex** reads this file natively, discovers the project agents in `.codex/agents/`, and
discovers the shared workflows in `.agents/skills/`. A Codex coordinator can operate the board
interactively, dispatch native subagents over the legal frontier, or run the same substrate from
`codex exec`; tasks tagged `--engine codex` are reserved for that adapter.
