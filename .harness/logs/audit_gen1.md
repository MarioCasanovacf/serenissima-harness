# Generation-1 Evolution Audit (T-006)

- **Auditor**: evolution-analyst (Opus, thinker) — claude.md §5A steps 1-2
- **Generation audited**: 0 (bootstrap + first build wave, T-000 → T-006)
- **Written**: 2026-07-04 (UTC)
- **Rule**: every claim below quotes a concrete log/source line. A proposal without quoted
  evidence is invalid. This audit REGISTERS proposals only; mutating claude.md/gemini.md is
  T-007, human-gated (state.json human_gates).
- **Replay**: each quoted line is grep-able in the cited file at the cited line number.

---

## 1. Corpus summary (line counts)

| Source | Lines / count | Content |
|---|---|---|
| `.harness/logs/events.jsonl` | **77** (`wc -l`) | full semantic history: 6 claims, 6 handoffs, 14 lock acquire/release, 1 reputation correction, goal-mode runs, 5 done verdicts |
| `.harness/logs/transcript.jsonl` | **1** (`wc -l`) | a single synthetic `test-session` bootstrap probe (see §2, gap G1) |
| `.harness/logs/gemini_contract_report.md` | 65 | cross-engine producer report + 3 frictions (F1/F2/F3) |
| `.harness/logs/goal_mode_last_failure.md` | 26 | last goal-mode digest (VER3 TIMEOUT) |
| Task notes | T-000, T-002, T-003, T-004, T-006 detail files | plans, hand-offs, verdicts |
| `.harness/state.json` | limits, human_gates, reputation (4 agents), evolution.pending_proposals (P-001) |

Distinct agents in events.jsonl: `main`, `gemini-runner`, `harness-verifier`,
`substrate-worker-1`, `substrate-worker-2`, `evolution-analyst` (6).

---

## 2. Taxonomy (with quoted evidence)

Classification key: **DESIGNED-REFUSAL** = a mechanism behaving correctly (not a failure);
**GAP** = a genuine friction/defect; **VALIDATED** = an invariant the traffic proves held;
**UNTESTED** = a designed path no real traffic exercised (an audit finding in its own right).

### 2.1 Designed refusals / bounds firing correctly (NOT failures)

| Item | Count | Evidence | Verdict |
|---|---|---|---|
| Cascade gate present | 1 (structural) | board: `gated (cascade): T-007 waits for T-006`; blackboard.py `claim` is "refused if any depends_on is not done" (README.md:48) | DESIGNED — but see UNTESTED: no real early-claim refusal was ever logged |
| Goal-mode bound fires | 4 `goal_abandoned` | events.jsonl:41-42 `"goal_abandoned" ... "iterations_used": 2, "max_iters": 2`; :42 `"note": "run() called again after bound was already reached"`; verifier repro :66-67 (VER1) | DESIGNED — anti-agentic-trap bound (state.json:15 `max_retries_per_failure: 3`) working; NOT a failure |
| Producer never self-approves | 4/4 tasks | T-002 handoff by `gemini-runner` (events.jsonl:15), verdict by `harness-verifier` (:22); same split T-000/T-003/T-004 | DESIGNED — producer≠approver held everywhere |

### 2.2 Genuine gaps (frictions / defects)

| ID | Item | Quoted evidence | Verdict |
|---|---|---|---|
| **G1** | transcript.jsonl empty of real traffic | `wc -l transcript.jsonl` = **1**; that line is `{"ts":"2026-07-04T01:25:01Z","agent":"main","event":"PostToolUse","session_id":"test-session","tool_name":"Bash","tool_input":{"command":"echo hola"}...}` (transcript.jsonl:1). README promises "transcript.jsonl EVERY tool call, auto-appended by the ... PostToolUse hook" (README.md:29-30) and "hook-fed, every tool call" (README.md:79); gemini.md:59 repeats it; ORCHESTRATION.md:69 names the failure mode as "Unobservable trajectories (no evolution evidence)" | GAP — Experience pillar empty; see Proposal B |
| **G2** | check_lock.py self-blocks per-call identity overrides | T-004.json:23 (worker note): "check_lock.py PreToolUse hook resolves agent identity from the session's ambient env, NOT per-Bash-call exports -- confirmed by piping a synthetic PreToolUse payload ... it read holder=substrate-worker-2 (my real lock) vs me=main (hook's default) and returned exit 2, which would have blocked my own Edit/Write on files I legitimately held-locked". Root cause in source: check_lock.py:30-32 `me = hc.agent_id(); holder = lock.get("holder"...); if holder == me: return 0`; harness_common.py:51-55 `agent_id` reads ONLY `os.environ.get("CLAUDE_HARNESS_AGENT_ID", default)`. Coordinator independently confirms in T-006.json (SELF-BLOCKED, exit 2) | GAP — see Proposal A |
| **G3** | recontext_evidence.md is an unlocked shared append-target | recontext_evidence.md:1-9 defines it as the single shared buffer ("Gemini agents ... paste here the EXACT code blocks"); gemini.md:62-67 step 3 = "Write these extracted segments into `.harness/recontext_evidence.md`" with NO lock step; `grep -c recontext_evidence events.jsonl` = **0** → gemini-runner acquired zero locks on it while writing (T-002); state.json:18 `max_parallel_workers: 3`; the collision_model itself (recontext_evidence.md:33-38, quoting blackboard.json) says "Source-file edits additionally require a write lock" yet this shared mutable file is exempt | GAP — coordinator fact-check "F3 VALID: collision gap" (T-006.json); see Proposal C |
| **G4** | lock.py `status`/`sweep` reject `--agent` | reproduced: `lock.py status --agent evolution-analyst` → `error: unrecognized arguments: --agent evolution-analyst`, exit 2 (same for `sweep`). lock.py defines no `--agent` on those subparsers (lock.py:152-156). Mismatches the pass-identity-everywhere habit; the harness prompt itself flags it as a "Known quirk" | GAP (low severity) — CLI-consistency; a doc/coordinator-level expectation gap, no logged failure |
| **G5** | cross-engine timestamp format inconsistency | recontext_evidence.md:19 & :30 headers use LOCAL offset `2026-07-03T19:34:13-06:00`, while every substrate CLI emits UTC `Z` (harness_common.py:29 `ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"`, :36-37) | GAP (minor) — cosmetic ordering hazard; noted, not in top-3 |

### 2.3 Decision gaps (expected-vs-actual; §5A.2)

| Case | Expected (note) | Actual (verdict) | Assessment |
|---|---|---|---|
| Gemini F1 | Gemini proposed "Implementar un subcomando `list` o `status` en `lock.py`" (gemini_contract_report.md:48) as a MISSING feature | It already exists: lock.py:98-117 (`def status`) | THINKING–ACTION GAP (discoverability): producer expected absence, feature was present. Coordinator: "F1 PARTIALLY VALID ... ALREADY EXISTS (lock.py:98-117); real signal = CLI discoverability gap" (T-006.json) |
| worker-1 self-catch | (coordinator note, T-006.json) "worker-1 self-caught dead code + non-idiomatic imports in its first draft BEFORE validation" | delivered clean; verifier VERIFIED with independent repro (T-003.json:28) | HEALTHY — decision-observability worked; expected==actual after self-correction. No mutation warranted |
| Every-task expectation match | T-000/T-002/T-003/T-004 producer hand-off notes all state expected replayable evidence | all 4 verifier notes = VERIFIED (no REJECTED verdicts in corpus: `grep -ic rejected events.jsonl` = 0) | VALIDATED — zero expected-success→got-rejection cases this generation |

Decision-gap count: **1 material** (F1 discoverability) + 1 healthy self-correction + 0 rejected verdicts.

### 2.4 Validated invariants (audit is honest in both directions)

- **Producer ≠ approver** on all 4 verified tasks (§2.1).
- **Reputation credits the producer, not the verdict-time claimant**: events.jsonl:8
  `"reputation_corrected" ... "moved_from": "harness-verifier", "moved_to": "substrate-worker",
  "reason": "bootstrap bug fix: credit producer, not verdict-time claimant"`; state.json:106-127
  shows all 4 producers at `tasks_done: 1, tasks_failed: 0`.
- **guarded() serialized a real race**: coordinator note (T-006.json) — "guarded() flock
  deterministically serialized an accidental parallel double-dispatch of goal_mode runs";
  mechanism in harness_common.py:80-92 (single flock on `.guard`).
- **Zero lock residue across 5 completed tasks**: every `lock_acquired` has a matching
  `lock_released` (events.jsonl:12↔16, 25↔38, 28↔57, 29↔58, 32↔33, 9↔10, 18↔19, 20↔21);
  all 4 T-00x verdict notes report "lock.py status clean / no active locks"
  (T-002.json:30, T-003.json:23, T-004.json:28).

### 2.5 UNTESTED designed paths (invariants no real traffic exercised)

These are audit findings: mechanisms that exist in code but have **zero** confirming traffic.
Counts computed against events.jsonl.

| Path | Evidence of non-exercise | Risk |
|---|---|---|
| Lock TTL steal | `grep -c '"stole_expired": true'` = **0** (every acquire has `"stole_expired": false`) | crash-recovery steal never proven end-to-end |
| Lease expiry auto-release | no expired-lease/auto-release event; all claims completed inside the 3600s lease | anti-stall reclaim unproven |
| Lock `busy:` refusal | `grep -Eic 'busy|refused'` = **0** | contention path (lock.py:41-52) never triggered |
| Cascade-gate refusal at claim time | no refused-claim event; T-007 was never claimed early | the gate is structurally present but never fired |
| `blocked` status path | `grep -c '"status": "blocked"'` = **0** | lifecycle branch unexercised |
| `failed` status path | `grep -c '"status": "failed"'` = **0** (all 5 tasks → done) | abandonment path unexercised |
| `--force` release / `sweep` removal | `grep -c '"forced": true'` = 0; `grep -c lock_swept` = 0 | coordinator override + expiry sweep unexercised |
| Tournament / n-way parallel same-file contention | only 2 workers ran truly parallel (T-003+T-004) and on DIFFERENT files | parallel-write conflict resolution unproven |

Recommendation: seed a future generation with a deliberate contention + crash-recovery smoke
task (claim-and-abandon → lease expiry; acquire-and-crash → TTL steal; two writers, one file →
`busy:`) so these invariants stop being assumed.

---

## 3. TOP-3 mutation proposals (falsifiable, ranked by evidence strength)

> Ranking rationale: **A** is the only gap with a reproduced `exit 2` that forced a *live
> behavioral workaround* which itself defeats a core guarantee. **B** is a demonstrably empty
> pillar (1 vs 77 lines) that undermines the audit engine, trivially falsifiable, but the harm
> is missing-data rather than a wrong action. **C** is a coordinator-confirmed collision hole
> that is real but still latent (parallelism was not exercised this generation).

All three are substrate/NLAH changes to be registered in `state.json evolution.pending_proposals`
by the coordinator; wording changes to `gemini.md` are additionally human-gated (T-007 class).

### Proposal A — check_lock.py should resolve identity per session, not only from ambient env  (RANK 1)

- **Evidence** → T-004.json:23: "it read holder=substrate-worker-2 (my real lock) vs me=main
  (hook's default) and returned exit 2, which would have blocked my own Edit/Write on files I
  legitimately held-locked ... I wrote/placed both artifacts via Bash (heredoc/cp ...) instead
  of the native Edit/Write tools ... to avoid a hook that structurally cannot see a per-Bash-call
  CLAUDE_HARNESS_AGENT_ID override." Root cause: check_lock.py:31-32 `me = hc.agent_id() ... if
  holder == me: return 0`; harness_common.py:55 `return os.environ.get("CLAUDE_HARNESS_AGENT_ID",
  default)`. Independently confirmed by coordinator (T-006.json AUDIT INPUT / T-004 build).
- **Diagnosis** → An in-session subagent that overrides its identity per CLI call is invisible to
  the PreToolUse hook, so the hook SELF-BLOCKS it from editing files it legitimately holds. The
  worker's only escape was to route writes through `Bash` (outside the `Edit|Write|MultiEdit|
  NotebookEdit` matcher) — which **silently bypasses mechanical lock enforcement entirely**. The
  gap therefore costs twice: honest-worker friction, plus a normalized bypass pattern that defeats
  the guarantee check_lock.py exists to provide.
- **Target** → `.harness/bin/check_lock.py` (identity check) + `.harness/bin/harness_common.py`
  (new helper) + `.harness/README.md` §Identity/§Locks note. Substrate task (T-007-class worker),
  NOT a claude.md/gemini.md semantics mutation.
- **Mutation (mechanism)** → Add `hc.session_holders()` reading a per-session marker file
  (e.g. newline-delimited `.harness/session_holders` written when a subagent is spawned, or an
  allowlist path the hook consults); in check_lock.py replace `if holder == me:` with
  `if holder == me or holder in hc.session_holders():` (still fail-open on read error). This lets
  a session declare the identities it legitimately owns without abandoning ambient-env default.
- **Expected measurable gain** → Piping the exact synthetic PreToolUse payload from T-004
  (holder=substrate-worker-2, ambient me=main, marker lists substrate-worker-2) returns **exit 0
  instead of exit 2**; and the count of "wrote via Bash to dodge the hook" notes in future task
  hand-offs drops to **0** (currently 1: T-004.json:23).

### Proposal B — Make transcript.jsonl actually capture real traffic, or correct the promise  (RANK 2)

- **Evidence** → `wc -l transcript.jsonl` = **1**; sole line = synthetic `"session_id":
  "test-session" ... "command": "echo hola"` (transcript.jsonl:1), while `wc -l events.jsonl` =
  **77** real events spanning 6 agents and the whole T-000→T-006 build. Promise: README.md:29-30
  "transcript.jsonl EVERY tool call, auto-appended by the Claude Code PostToolUse hook"; repeated
  README.md:79 and gemini.md:59; and ORCHESTRATION.md:69 names the exact failure mode this pillar
  should prevent — "Unobservable trajectories (no evolution evidence)."
- **Diagnosis** → The PostToolUse hook (log_event.py) is not firing/wired for real subagent
  sessions; only one synthetic line exists. The AHE **Experience pillar is empty for real
  traffic**, and this **undermines the §5A audit loop itself**: this very audit had no transcript
  to parse and reconstructed the entire trajectory from events.jsonl + task notes. The substrate's
  own failure-mode table (ORCHESTRATION.md:69) describes precisely what happened.
- **Target** → Hook wiring: `.claude/settings*.json` PostToolUse registration + verify
  `.harness/bin/log_event.py` appends to `harness_common.TRANSCRIPT` (harness_common.py:25). IF
  subscription-CLI subagents structurally cannot feed PostToolUse to hooks, then correct the
  promise wording in README.md:29-30/:79, gemini.md:59, ORCHESTRATION.md:69 to "best-effort /
  main-session-only" so future auditors do not assume a complete trajectory exists.
- **Expected measurable gain** → After a fix, a fresh smoke task's tool calls appear in
  transcript.jsonl: line count **> 1 and grows ≥1 line per Bash/Edit** in that task (today it is
  frozen at 1 regardless of activity). If declared unfixable for subagents, the measurable becomes
  doc-consistency: `grep -c "every tool call" {README.md,gemini.md,ORCHESTRATION.md}` in
  promise-context returns **0** (claim aligned to reality).

### Proposal C — recontext_evidence.md needs a lock rule (or an atomic recontext.py CLI)  (RANK 3)

- **Evidence** → recontext_evidence.md:1-9 defines a single shared buffer all Gemini agents append
  to; gemini.md:62-67 step 3 = "Write these extracted segments into
  `.harness/recontext_evidence.md`" with NO lock step; `grep -c recontext_evidence events.jsonl` =
  **0** (gemini-runner locked it zero times in T-002); state.json:18 `max_parallel_workers: 3`.
  The collision_model quoted in recontext_evidence.md:33-38 itself mandates "Source-file edits
  additionally require a write lock" — yet this shared MUTABLE file is exempt while blackboard/
  tasks/events are all serialized via guarded() (harness_common.py:80-92). Coordinator fact-check:
  "F3 VALID ... collision gap" (T-006.json).
- **Diagnosis** → recontext_evidence.md is the substrate's only shared, many-writer, mutable file
  with neither a lock rule nor guarded() serialization. With ≥2 concurrent Gemini writers (allowed
  up to 3), appends race and can interleave/clobber. It has not bitten only because generation-0
  ran a single Gemini agent — a latent, untested-until-parallel corruption.
- **Target** → `gemini.md §4B` step 3 (add: acquire a lock via lock.py before writing) +
  `.harness/recontext_evidence.md` header rule; OPTIONALLY a `.harness/bin/recontext.py add --file
  <path> --lines <range>` that appends atomically under `guarded()` with consistent metadata
  (Gemini's own F3 fix, gemini_contract_report.md:56). gemini.md wording is human-gated (T-007);
  the CLI is a substrate worker task.
- **Expected measurable gain** → After the rule, gemini task traffic shows a `lock_acquired` on
  `recontext_evidence.md` before its writes: `grep -c recontext_evidence events.jsonl` > **0**
  (today 0). With a recontext.py CLI, a two-writer stress test yields **zero interleaved or
  truncated entries** (byte-verifiable: every entry's fenced block remains intact).

---

## 4. Registration note (evolution queue)

Per claude.md §5A.4 and README.md:82-86, this audit does NOT apply mutations. Coordinator to
register A/B/C into `state.json evolution.pending_proposals` (assigning P-numbers) alongside the
existing **P-001** (NLAH cross-references to ORCHESTRATION.md / CLI protocol / TTL-lease / producer
≠approver). Note overlap: Proposal C's gemini.md §4B lock rule and Proposal B's promise-wording fix
touch the same NLAH files as P-001 and should be bundled into the single human-gated T-007 apply.
Mutating claude.md/gemini.md remains a human_gates item (state.json:26).

Handoff target: verifier. Replay path: grep every quoted line at its cited file:line.
