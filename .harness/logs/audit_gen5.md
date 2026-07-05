# Gen-5 Intake Audit — Shepherd (checkpoint/revert) & Opik/Ollie (auto-regression)

- **Analyst**: evolution-analyst
- **Date**: 2026-07-05
- **Scope**: two externally-sourced Gen-5 intake candidates, evaluated *evidence-first*
  against local trajectories (`transcript.jsonl`, `events.jsonl`, `goal_mode_state.json`,
  `goal_mode_last_failure.md`) and the current control plane (`goal_mode.py`, `blackboard.py`,
  `CLAUDE.md §5A`, `state.json`).
- **Operator bar**: Gen-4 is in production; the entry bar is high. Explicit reject criteria
  from the operator: *too much work, too many tokens, too complex to implement, too hard to
  integrate*. A well-argued DESCARTAR outranks an enthusiastic ADOPTAR.
- **Verdict summary**: **Candidate 1 (Shepherd) — DESCARTAR.** **Candidate 2 (Opik) — DESCARTAR**
  (mechanism already exists as convention; the LLM half is disqualified by §3).

---

## 0. Evidence base — do these failure modes actually occur here?

### 0.1 goal_mode abandonment / contaminated-state (Shepherd's target problem)

`goal_abandoned` fired **4 times total** in the entire event log, and **every one is a
synthetic smoke test**, not real project work:

```
events.jsonl:41  goal_abandoned  agent=substrate-worker-2  task=DEMO  cmd="python3 -c 'import sys; sys.exit(1)'"
events.jsonl:42  goal_abandoned  agent=substrate-worker-2  task=DEMO  ... note="run() called again after bound was already reached"
events.jsonl:66  goal_abandoned  agent=harness-verifier    task=VER1  cmd="python3 -c 'import sys; sys.exit(1)'"
events.jsonl:67  goal_abandoned  agent=harness-verifier    task=VER1  ... note="run() called again after bound was already reached"
```

Grep for any *real* abandonment: `grep goal_abandoned | grep -vE 'DEMO|VER1'` → **NONE**.
The two distinct abandoned commands are both `python3 -c 'import sys; sys.exit(1)'` — a command
that **touches zero files**. So even in the only cases we ever abandoned, there was **no
working tree to contaminate**.

Meanwhile every *real* goal_mode run reached its goal quickly:

```
events.jsonl:295 goal_reached T-022 mdtoc unittest        iterations_used=2/3
events.jsonl:297 goal_reached T-021 mdtoc unittest        iterations_used=2/3
events.jsonl:332 goal_reached T-024 slugger_a             iterations_used=1/3
events.jsonl:458 goal_reached T-028 mdtoc unittest        iterations_used=1/3
events.jsonl:931 goal_reached T-044 cronsplain node test  iterations_used=1/3
events.jsonl:978 goal_reached T-045 cronsplain node test  iterations_used=1/3
```

The single real captured failure digest (`goal_mode_last_failure.md`) is T-021, `exit 1`,
`iteration 1/3` — an `ImportError: Start directory is not importable` (wrong test-discovery
path), fixed and reached at iteration 2 (`events.jsonl:297`). Normal fix loop, no contamination.

**`goal_mode_state.json` is `{}`** — no counter is even mid-flight; nothing is stuck.

**`goal_mode.py` confirmed to never touch git or the working tree.** `cmd_run` only spawns the
`--cmd` subprocess and writes counters/digest; `cmd_reset` (goal_mode.py:296-317) clears counters
only. So the *capability* Shepherd proposes is genuinely absent — but **the problem it would fix
has never manifested in a real trajectory** (0 real abandonments, 0 contaminated states).

### 0.2 Recurring / regressed failures (Opik's target problem)

Grep for a regression signature (a test that failed, was fixed, then failed again): the
transcript iteration grep and the per-command event history show **no command that went
fail → fixed → fail-again**. T-045's `node --test tests/*.js` appears twice (`events.jsonl:978`
and `:981`) — both `goal_reached iterations_used=1`, i.e. a re-run of an already-passing command,
**not** a regression re-failure.

Critically, the *permanent-regression-test pattern Opik describes already exists here* as
convention:

- **Golden vector files** are the project's permanent regression suite:
  `projects/mdtoc/candidates/vectors.py`, `projects/cronsplain/candidates/vectors.js`. A
  discovered bug is *already* lifted into a vector — see `audit_gen3.md:235,240` ("lift
  slugger_c's cited … as a regression vector … the new regression vector passes").
- **Verifier replay** re-runs the full suite on epic-join tasks (T-029 "replay full suite +
  end-to-end", T-052 "cronsplain epic FINAL JOIN: replay full node --test suite").
- **Harness-guardrail regressions** are covered by the SCRATCH probe family — 40+ disposable
  probe tasks (T-090..T-121, T-200..T-211) that re-attack producer!=approver, the done-guard,
  ambient-slip, re-handoff, etc. (`producer_check_refused=32`, `producer_check_overridden=8`
  in `events.jsonl` are these probes firing).
- **§5A is the audit loop itself**, which this document is an instance of.

So the "each cycle the harness gets harder to break" outcome is *already produced* by
vectors + verifier replay + probe family + the audit loop. And the Ollie-as-LLM-agent half is
disqualified up front by `CLAUDE.md §3` (no external LLM/AI APIs).

### 0.3 The overriding cost constraint

`state.json.cost_policy._source`: *"operator directive 2026-07-05 ('Soluciona esto' — 95%
usage from subagent-heavy sessions, 79% from 8h+ sessions)"*. The operator is in an active
token crackdown. Any candidate that adds recurring per-cycle work is fighting a live directive.

---

## Candidate 1 — Shepherd: git-as-checkpoint / revert-to-last-good-tree

### Proposal (falsifiable form)
Landed version (not process forking — we do not control the Claude Code runtime): have
`goal_mode.py` `git commit` the working tree on every verified checkpoint (exit 0), and on
abandon (exit 3) / `reset` offer `git checkout` of the tracked tree back to that last-good
commit, instead of leaving partial edits in place.

- **Target file/section**: `.harness/bin/goal_mode.py` (`cmd_run` success branch 242-256,
  abandon branch 274-286; `cmd_reset` 296-317); a new `--checkpoint` flag; doc note in
  `CLAUDE.md §3A Goal Mode Loop`.
- **Motivating log lines**: `events.jsonl:41,42,66,67` (the only 4 abandonments — all synthetic,
  zero-file commands); `goal_mode_last_failure.md` (only real failure, fixed at iter 2 with no
  contamination); `goal_mode_state.json = {}` (nothing stuck).
- **Expected measurable gain (falsifiable)**: "after abandon, working tree returns to last
  verified commit; contaminated-retry incidents → 0." **This gain is unmeasurable-because-already-zero:
  contaminated-retry incidents in real trajectories are already 0/55 done tasks.** A proposal
  whose target metric is already at its floor cannot demonstrate improvement — this is the
  falsification.

### Implementation cost
| Dimension | Rating | Justification |
|---|---|---|
| Lines/files to touch | **medio** | ~40-70 lines in `goal_mode.py`: git-porcelain guard, commit on exit 0, checkout on abandon/reset, a `--checkpoint` opt-in, plus dirty-index/untracked-file handling and `CLAUDE.md §3A` wording. |
| Integration complexity | **alto** | Collides with the git-as-rollback substrate (`CLAUDE.md §4A.1`, human_gate on git publication): auto-commits pollute the same history used for harness rollback, and a blind `git checkout` can nuke a *parallel* worker's unrelated edits — goal_mode has no lock on the tree, so it does not know which paths are "its" changes. Interacts badly with the locks/blackboard model that assumes multiple agents share one working copy. |
| Recurring token cost | **bajo-medio** | Runs only inside `goal_mode` calls, not every agent cycle — but adds git subprocess churn to every checkpoint and larger, noisier git history against a live token/hygiene crackdown (`cost_policy._source`). |
| Risk to Gen-4 | **alto if default / bajo if opt-in** | Auto-commit + auto-checkout *changes existing semantics* of goal_mode and of the shared tree during parallel work; safe only as strictly opt-in `--checkpoint`, which then almost no one would invoke for a non-problem. |

### Verdict: **DESCARTAR**
Evidence → the problem (abandon-then-retry-on-contaminated-tree) has occurred **zero times** in
real work; all 4 abandonments are synthetic zero-file commands (`events.jsonl:41,42,66,67`), and
`goal_mode_state.json={}`. Diagnosis → this is a solution to a theoretical problem; its target
metric is already at floor, so it is structurally unfalsifiable-as-improvement. The auto-checkout
mechanism also *creates* a new risk (clobbering a parallel worker's edits) that is worse than the
problem it removes. Mutation → none. Expected gain → none realizable. **Revisit trigger (cheap,
falsifiable):** if a future generation logs `>0` *non-synthetic* `goal_abandoned` events where the
abandoned command edited files, re-open this candidate then — not before.

---

## Candidate 2 — Opik/Ollie: resolved failure → permanent regression test

### Proposal (falsifiable form)
Mechanical pattern only (Ollie-as-LLM is disqualified by `CLAUDE.md §3`): when a failure recorded
in `transcript.jsonl` / `goal_mode` is later resolved, auto-append its minimal repro to a
regression file that `goal_mode`/the verifier re-runs, so `§5A` stops depending on the Coordinator
manually parsing logs.

- **Target file/section**: new `.harness/regressions/` runner + capture hook in `goal_mode.py`
  (`goal_reached` branch 242-256) or a new `blackboard.py` verb; `CLAUDE.md §5A.1`;
  `ORCHESTRATION.md` (regression-note taxonomy).
- **Motivating log lines**: **there are none for the "recurring bug" premise** — zero
  fail→fixed→fail-again signatures in the log; T-045's double `goal_reached` (`events.jsonl:978,981`)
  is a passing re-run, not a regression. Per the constraint "a proposal without quoted log lines is
  invalid," the *recurrence* premise is unsupported by local evidence.
- **Counter-evidence that the pattern already exists**: `vectors.py`/`vectors.js` golden files
  (permanent regression suite), verifier replay (T-029, T-052), the SCRATCH probe family
  (T-090..T-121, T-200..T-211; `producer_check_refused=32`), and this audit loop itself
  (`audit_gen3.md:235,240` already lifted a bug into a regression vector).
- **Expected measurable gain (falsifiable)**: "fixed bugs never recur." Already true (0 recurrences),
  so unmeasurable-as-improvement — same falsification as Candidate 1.

### Implementation cost
| Dimension | Rating | Justification |
|---|---|---|
| Lines/files to touch | **alto** | A new regression runner + capture path, a de-dup/canonicalization scheme for repros, a new `blackboard.py`/`goal_mode.py` verb, and edits to `CLAUDE.md §5A` + `ORCHESTRATION.md`. Meaningfully more than the vector-file convention already in use. |
| Integration complexity | **alto** | No single failure chokepoint exists: `goal_mode` captured only synthetic + a handful of *passing* real runs, and transcript hooks only fire in in-repo sessions (P-003, `state.json`). Auto-capture must interact with claims/leases (who owns a captured regression?) and the producer!=approver rule (a captured test must still be verifier-gated). |
| Recurring token cost | **medio-alto** | To be automatic it adds a capture+match step to failure/resolve cycles and a growing regression suite that verifier replay must run every epic-join — directly against the active `cost_policy` crackdown (95% usage, `cost_policy._source`). |
| Risk to Gen-4 | **medio** | Additive if opt-in, but an auto-appending suite that silently grows and gates future verdicts changes verifier semantics and can wedge the DAG on a bad auto-captured case. |

### Verdict: **DESCARTAR**
Evidence → zero recurring-bug signatures in the log, and the "harder to break each cycle" outcome
is *already delivered* by golden vectors + verifier replay + the SCRATCH probe family + the §5A
audit loop (`audit_gen3.md:235,240`). Diagnosis → the valuable half of Opik is already implemented
as convention; the only genuinely new sliver (fully-automatic capture) has no clean chokepoint,
adds recurring tokens against a live crackdown, and solves a problem with no local occurrences. The
LLM half is disqualified by §3. Mutation → none. **Cheapest survivable fragment (if the operator
insists on *something*):** a one-line `ORCHESTRATION.md` note making the existing convention explicit
— "a verifier resolving a *real* (non-synthetic) bug appends its minimal repro to the relevant
`vectors.*` golden file before closing" — doc-only, ~0 recurring tokens, no new mechanism. Even this
is optional given the pattern is already followed.

---

## Bottom line
Both candidates are technically sound in their origin projects but fail *this harness's* intake
bar on the same two grounds: (1) the failure modes they fix have **not occurred** in our
trajectories (0 real abandonments, 0 contaminated states, 0 bug recurrences — §0.1/§0.2), and
(2) their landed forms add integration risk and recurring cost against an **active operator token
crackdown** (§0.3). For Opik, the useful mechanical core already exists as convention. Recommend
**DESCARTAR both**, registering only the cheap revisit-triggers above so the decision is
re-openable on evidence rather than re-litigated on theory.
