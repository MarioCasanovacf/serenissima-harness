---
name: harness-orchestrate
description: Coordinate a goal through the Universal Agent Harness with native Codex subagents. Use when the user asks to plan, dispatch, run, finish, or babysit a multi-task harness goal.
---

# Orchestrate with the Codex bench

Read `AGENTS.md`, `ORCHESTRATION.md`, `.harness/README.md`, and the live board first. This skill explicitly authorizes delegation to native Codex subagents when work is independent and the harness limits permit it.

If the goal has no board tasks, delegate decomposition to `orchestration_planner`. Do not publish a DAG with unresolved blocking unknowns. Once tasks exist, dispatch only the claimable frontier to separate `substrate_worker` instances, assigning unique harness identities such as `codex-worker-a`, `codex-worker-b`, and `codex-worker-c`. Never exceed the lower of `.harness/state.json limits.max_parallel_workers` and `.codex/config.toml agents.max_threads` after reserving the coordinator slot.

Workers must claim through the CLI and lock files before edits. When work reaches review, delegate it to `harness_verifier` with an identity distinct from the producer. Do not treat a subagent summary as a verdict; the verifier must replay the commands. Route corpus research to `research_librarian` and trajectory audits to `evolution_analyst`.

At joins, re-read the board rather than relying on stale subagent summaries. Continue until the requested outcome is complete or a genuine human decision is required. Respect human gates for publication, destructive operations, notifications, and engine-constitution mutations.

