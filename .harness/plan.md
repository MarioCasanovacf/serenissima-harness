# Harness Build Plan (maintained by Thinkers; workers execute, verifiers gate)

> Owner: orchestration-planner / fable-5-coordinator.
> Rule: this file states WHY and IN WHAT ORDER; the blackboard states WHO and WHAT NOW.
> Lock this file (`lock.py acquire .harness/plan.md --holder <you>`) before rewriting it.

## Generation 0 — Substrate (DONE, this session)
Physical runtime substrate per claude.md §4 / gemini.md §4: guarded blackboard,
TTL write locks, JSONL observability (hook-fed), deterministic CLIs, agent bench,
Gemini prompt bridge, git baseline.

## Generation 0 → 1 — Frontier (parallel where independent)
- **T-002** Gemini contract test (bridge file: `prompts para Gemini/1.md`) — proves NLAH portability, feeds friction notes to the audit.
- **T-003** AST semantic indexer v0 — ZCode parity item #3.
- **T-004** Goal-mode runner v0 — ZCode parity item #1.
- **T-005** Remote messenger hook v0 — ZCode parity item #2 (human-gated activation).

## Generation 1 — Evolution loop (cascade: real dependency on evidence)
- **T-006** Audit trajectories from logs (claude.md §5A steps 1–2) — needs T-002/T-003/T-004 evidence to exist.
- **T-007** Gated mutation of claude.md/gemini.md (§5A steps 3–4) — needs T-006 verdicts; bumps `harness_generation`; git commit "generation 1".

## Standing design rules
1. Default to parallel: only add a `depends_on` edge when a task literally consumes another task's artifact.
2. Every worker chain terminates in a verifier join (producer ≠ approver).
3. Task size ≤ `state.json limits.max_steps_per_task`; otherwise decompose further.
4. High-uncertainty nodes may use tournament mode: N parallel candidates, one verifier verdict (Co-Scientist pattern).
