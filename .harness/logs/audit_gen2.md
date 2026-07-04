# Generation-2 Evolution Audit (T-012)

- **Auditor**: evolution-analyst (Opus, thinker) — claude.md §5A steps 1-2
- **Generation audited**: 1 (T-007 gated mutation → T-011 hook-liveness; the generation-1
  substrate as shipped, plus the four `state.json evolution.next_audit_inputs` carry-overs
  G6 / G7 / G8 / P-003-residual).
- **Written**: 2026-07-04 (UTC). **Rev 2**: P-008 re-diagnosed after harness-verifier REJECTED
  the first hand-off on P-008 only (P-005/P-006/P-007 + taxonomy replayed clean and are
  unchanged); stale live-log counts refreshed with a snapshot caveat.
- **Rule**: every claim below quotes a concrete log/source line or a reproducible one-liner.
  A proposal without quoted evidence is invalid. This audit **REGISTERS proposals only**;
  applying them is a separate worker/verifier cycle (claude.md §5A.3-4).
- **Replay**: each quoted line is grep-able at its cited file:line; each repro is a
  `python3 -c` against read-only imports (no `bin/` file was modified, no live task mutated).

---

## 0. HUMAN GATE REQUIRED

**NONE this generation.** Every gen-2 proposal (P-005 … P-008) is **code-level** — it touches
only `.harness/bin/*.py`, `.harness/README.md`, and one scratch task file (`T-010.json`).
**No proposal edits `claude.md` or `gemini.md`**, so none trips the `state.json human_gates`
item *"mutating claude.md or gemini.md"* (state.json:26). TTL/lock/artifact **semantics are
unchanged** — the fixes correct precision, observability, log hygiene, and CLI ergonomics, not
the contracts the NLAHs describe. This contrasts with generation-1, whose Proposals B/C carried
NLAH wording changes bundled into the human-gated T-007 apply. Gen-2 needs no human gate.

---

## 1. Corpus summary (line counts)

| Source | Lines / count | Content |
|---|---|---|
| `.harness/logs/events.jsonl` | **225 at audit-time snapshot T** (`wc -l`; grows live — see note) | full semantic history: 26 task_claimed, 49 task_updated, 41 lock_acquired, 38 lock_released, 11 task_handoff, 11 session_holder_registered, 9 goal_mode_start, 4 goal_abandoned, 2 goal_reached, 2 recontext_added, **2 stole_expired:true**, **1 claim_expired**, 1 reputation_corrected, 1 proposals_registered, 1 generation_bumped (histogram computed at the 225-line snapshot) |
| `.harness/logs/transcript.jsonl` | **74 real at snapshot T** (session `15636cc2…`; grows live) + **1 synthetic** (`test-session`) | Experience pillar NOW populated with real PostToolUse traffic (see §4, P-003 closure). Live-growing during this very audit session. |
| Task detail files | T-008 / T-010 / T-011 notes | contention + hook-liveness trajectories with verifier verdicts |
| `.harness/bin/{harness_common,lock,recontext,blackboard,notify}.py` | source under audit for G6/G7/G8 | |
| `.harness/state.json` | limits, human_gates, reputation (7 agents), evolution.accepted_mutations (P-001..P-004 applied), next_audit_inputs (G6/G7/G8/P-003-residual) | |

> **Snapshot note (live logs)**: both JSONL logs are appended to continuously as agents act —
> including this audit's own session. The counts above are a monotone **lower bound at audit
> time T (~2026-07-04T06:2x)**, not a fixed total: `events.jsonl` measured 225 → **286** and
> `transcript.jsonl` 74 → **182** between the first hand-off and this Rev-2 revision. Every
> cited `events.jsonl:<line>` stays stable — the file is append-only, so line N never moves.

Distinct agents that RAN a CLI in events.jsonl (`agent` field, at snapshot T):
`substrate-worker-1` (57), `main` (54), `harness-verifier` (54), `substrate-worker-2` (48),
`gemini-runner` (6), `evolution-analyst` (6) — **6 agents**. (Per README §Identity, `agent` =
who ran the CLI, `holder`/`previous_holder`/`completed_by` = the flag-supplied owner; flags-win.
The `agent`≠`holder` splits below are **by design**, not misattribution.)

---

## 2. Taxonomy (with quoted evidence)

Classification key: **DESIGNED** = mechanism behaving correctly (not a failure);
**VALIDATED** = an invariant real traffic now proves held (incl. gen-1 UNTESTED paths that
this generation exercised); **GAP** = a genuine friction/defect; **UNTESTED** = a designed
path still with zero confirming traffic (an audit finding in its own right).

### 2.1 Designed refusals / bounds firing correctly (NOT failures)

| Item | Count | Evidence | Verdict |
|---|---|---|---|
| Goal-mode bound fires | 4 `goal_abandoned` | events histogram: 9 `goal_mode_start` vs 4 `goal_abandoned` + 2 `goal_reached` | DESIGNED — anti-agentic-trap bound (state.json:15) still working |
| PreToolUse foreign-lock block | 1 (T-011) | T-011.json verdict: `foreign holder ghost-verify -> exit 2 + 'HARNESS LOCK'; after release -> exit 0` | DESIGNED — mechanical lock enforcement proven live |
| Producer ≠ approver | all verified tasks | T-011 producer `fable-5-coordinator`, verdict by `harness-verifier` (T-011.json:2026-07-04T06:20:55Z) | DESIGNED — held |

### 2.2 VALIDATED — gen-1 UNTESTED paths now exercised (audit honest in both directions)

| gen-1 gap | gen-2 evidence | Verdict |
|---|---|---|
| Lock TTL steal never proven | events.jsonl:173 `"stole_expired": true … holder":"smoke-b" … "task":"T-010"`; events.jsonl:188 `"stole_expired": true … "holder":"ver-b"` (verifier's independent repro) | VALIDATED — crash-recovery steal proven **twice** |
| Lease expiry auto-release never proven | events.jsonl:177 `"event":"claim_expired" … "task":"T-090","previous_holder":"smoke-a"` | VALIDATED — anti-stall reclaim proven |
| `blocked` / `failed` status paths never exercised | T-010.json:26 `T-090 event history = task_claimed->claim_expired->claim->blocked->open->claim->failed`; reputation `smoke-a = {tasks_done:0, tasks_failed:1}` (state.json:137-141) | VALIDATED — lifecycle branches + failure-reputation bump proven |
| transcript.jsonl empty of real traffic (gen-1 G1 / P-003) | 74 real PostToolUse lines, session `15636cc2…` | VALIDATED — see §4 |
| Cross-engine timestamp inconsistency (gen-1 G5) | scan of all 225 events: **0 non-Z timestamps, 0 out-of-order**; recontext.py:28 G5 fix (`now_iso()` UTC-Z on every append) | VALIDATED — substrate CLIs are timestamp-consistent; the only local-offset strings are pre-tool human entries left as history |

### 2.3 Genuine gaps (the four carry-over inputs + one new)

| ID | Item | Quoted evidence | Verdict |
|---|---|---|---|
| **G6** | ISO_FMT truncates sub-second precision → short TTLs expire almost instantly | harness_common.py:30 `ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"`; :38 `now_iso() … strftime(ISO_FMT)` (floors to whole second); :147 `return (now_utc() - acquired).total_seconds() > ttl` (RHS full-precision, LHS floored). Repro (§3, P-005) shows acquire@X.999 with `--ttl 1` → **effective_life 0.001s**. Live proof: BOTH producer and verifier overrode the task-spec's `--ttl 1` → `ttl=3/sleep=4` "per G6" (T-010.json:21, :26) | GAP (HIGH) — see P-005 |
| **G7** | Absolute (user-specific) paths leak into the shared event log at multiple CLI sites; every other lock event is repo-relative | recontext.py:47/:58/:84/:105 hardcode `str(EVIDENCE_PATH)`; notify.py:200 `path=str(CONFIG_PATH)`; lock.py:66/:98 `path=args.path` (verbatim, so a caller-supplied absolute path leaks). **9** absolute-path events at snapshot T (see P-008 breakdown) vs relative form at lock.py→events.jsonl:101/129 | GAP (LOW / log-hygiene) — see P-008 |
| **G8** | `blackboard.py update --artifact` is single-value; repeated flags silently drop all but the last | blackboard.py:407 `p_upd.add_argument("--artifact", default=None)` (no `action="append"`); cmd_update:281-284 appends only `args.artifact`. Repro (§3, P-007): `--artifact A --artifact B` → `args.artifact='B'` (A dropped). Real workaround observed: substrate-worker-2 registered two artifacts via **two separate calls** — events.jsonl:120 (`artifact":".harness/bin/recontext.py"`) then :122 (`artifact":".harness/recontext_evidence.md"`) | GAP (MEDIUM) — silent data loss; see P-007 |
| **N1** | `busy:` lock refusals are UNOBSERVABLE — never logged as events | lock.py:50-60 busy branch prints `"busy:"` then `return 1` with **no `hc.log_event`**; recontext.py:68-78 identical (no log). `grep -in busy events.jsonl` = **0**, yet a busy refusal demonstrably occurred: T-010.json:26 `ver-c acquire then ver-d same path -> 'busy: ... held by ver-c' EXIT_CODE=1`. The contention event left zero trace in the semantic log | GAP (MEDIUM) — breaks the §5A audit loop's own measurability; see P-006 |

### 2.4 Decision gaps (expected-vs-actual; §5A.2)

| Case | Expected (spec/note) | Actual | Assessment |
|---|---|---|---|
| T-010 TTL parameter | task detail prescribed `--ttl 1`/`--lease 1` | producer + verifier BOTH used `ttl=3/sleep=4`, citing G6 (T-010.json:21, :26) | THINKING–ACTION GAP embedded in the **spec**: the substrate cannot execute `ttl=1` deterministically. Verifier explicitly recommends "updating T-010.json description text itself" (:26). Root cause = G6; folded into P-005 |
| T-011 hook liveness | producer expected transcript growth + mechanical block | verifier VERIFIED both via a **different method** (synthetic PreToolUse payload vs producer's live Edit) — T-011.json:06:20:55Z | HEALTHY — cognitive-diversity check worked; expected==actual. No mutation warranted |
| **audit_gen2 Rev-1 P-008 count** | auditor wrote "today 4 historical absolute-path lines" | actual `grep -c '/Users/' events.jsonl` = **9** (verifier repro) | THINKING–ACTION GAP in **this audit**: Rev-1 counted only the 4 recontext hits it grepped for, never the global set. Corrected in Rev-2 (P-008 below); self-disclosed |
| REJECTED verdicts | — | 1 this generation: harness-verifier REJECTED T-012 Rev-1 on P-008 (count + scope wrong). Addressed in Rev-2 | HEALTHY — producer≠approver caught an evidence error before registration |

### 2.5 UNTESTED designed paths still with zero confirming traffic

| Path | Evidence of non-exercise | Risk | Severity |
|---|---|---|---|
| Lock refresh / heartbeat | `grep -c '"refreshed": true' events.jsonl` = **0** (lock.py:62, recontext.py:80 never fired) | re-acquire-your-own-lock heartbeat unproven | LOW (N2) |
| `sweep` janitor removal | `grep -c lock_swept events.jsonl` = **0** (expiry steal happened via `acquire`, not `sweep`) | explicit sweep path unproven, though underlying expiry logic is proven | LOW (N3) |
| `--force` release | `grep -c '"forced": true' events.jsonl` = **0** | coordinator override unexercised | LOW |

Recommendation: fold a heartbeat/refresh + explicit-sweep assertion into the next contention
smoke task so N2/N3 stop being assumed. Not a top proposal (no defect, only missing evidence).

---

## 3. Reproductions (read-only; no bin/ file modified)

**G6 — sub-second truncation race** (`python3 -c` importing harness_common, floor semantics):

```
acquire@12:00:00.999000  stored=2026-07-04T12:00:00Z  trunc_loss=0.999s  ttl=1s -> effective_life=0.001s  <-- RACE
acquire@12:00:00.500000  stored=2026-07-04T12:00:00Z  trunc_loss=0.500s  ttl=1s -> effective_life=0.500s  <-- RACE
acquire@12:00:00.999000  stored=2026-07-04T12:00:00Z  trunc_loss=0.999s  ttl=3s -> effective_life=2.001s
```
Truncation loss is bounded in `[0,1)`, so `effective_life ∈ (ttl-1, ttl]`. **ttl=1 → (0,1]**,
can be ~0.001s (immediate expiry → the lock protects nothing). **ttl≥3 → always >2s** (why
the T-010 agents used ttl=3). The bug is `lock_is_expired` comparing a floored `acquired_at`
against a full-precision `now_utc()`; the LHS lost up to 1s that the RHS did not.

**G8 — repeated `--artifact` silent drop** (`python3 -c` mirroring blackboard.py:407):

```
current (store):        args.artifact = '.harness/logs/B.md'                                -> A.md SILENTLY DROPPED
candidate (append):     args.artifact = ['.harness/logs/A.md', '.harness/logs/B.md']        -> both preserved
```

---

## 4. P-003 residual — VERIFIED CLOSED

- **Traffic**: transcript.jsonl held **74 real PostToolUse lines at snapshot T** (grows live;
  182 by Rev-2) for session `15636cc2-22dd-4ee8-8047-516cb2b65a41` (first record
  `{"event":"SessionStart", … "session_id":"15636cc2…"}` at 2026-07-04T06:12:00Z; tool_names
  Bash/Read/Write/Edit/Agent/TodoWrite/ToolSearch) vs the lone gen-1 synthetic `test-session`
  line. The Experience pillar is populated with real traffic exactly as P-003's measurable
  required.
- **Verdict**: T-011 is **`done`**, verified by a DIFFERENT agent — T-011.json verdict
  (harness-verifier, 2026-07-04T06:20:55Z): *"VERIFIED (replayed, not trusted): (1)
  transcript.jsonl live-fills with real PostToolUse traffic for session 15636cc2 (60 session
  records … grew under my own tool calls = direct liveness proof …). (2) Mechanical block
  replayed … foreign holder ghost-verify -> exit 2 + 'HARNESS LOCK'; after release -> exit 0
  … (3) events.jsonl shows ghost-agent lock_acquired 06:15:10Z / lock_released 06:15:22Z."*
  Blackboard index: `T-011 status=done completed_by=harness-verifier completed_at=2026-07-04T06:20:55Z`.
- **Assessment**: P-003 residual is **genuinely closed** — no dependency outstanding.
  (This audit itself ran in session `15636cc2…` and its own tool calls are among the
  transcript lines, which is further live proof the PostToolUse hook fires in a repo-rooted
  session.)

---

## 5. Proposals (falsifiable, ranked; ALL code-level — see §0)

> Ranking rationale: **P-005** is the only gap with a **correctness/safety** impact (a
> short-TTL lock can expire in ~1ms → contention protection silently vanishes) AND a
> live behavioral deviation forced on two agents. **P-006** breaks the audit engine's own
> measurability (the very metric §5A proposals rely on) and is reproduced by a real busy
> refusal that left no trace. **P-007** is silent data loss on a plausible call pattern but
> has a working manual workaround. **P-008** is log-hygiene / portability only.

### P-005 — Fix sub-second TTL truncation in `lock_is_expired` (RANK 1, severity HIGH)

- **Evidence** → harness_common.py:30/:38/:147 (§2.3 G6); repro (§3) acquire@X.999 `--ttl 1`
  → effective_life 0.001s; live deviation T-010.json:21 & :26 ("used ttl3/sleep4 … NOT the
  task-detail's ttl=1 — 1s TTLs race the substrate ISO sub-second truncation").
- **Diagnosis** → `lock_is_expired` (harness_common.py:147) subtracts a **whole-second-floored**
  `acquired_at` from a **full-precision** `now_utc()`. The floor discards up to 0.999s of
  lifetime that the RHS still counts, so a `--ttl 1` lock can be judged expired ~1ms after it
  was taken — the next acquirer steals it and two writers proceed on one file. This defeats
  lock.py's core guarantee at short TTLs and already made a documented test parameter
  (`ttl=1`) un-runnable.
- **Mutation (mechanism)** → in `lock_is_expired`, floor BOTH sides so truncation cancels:
  `return (now_utc().replace(microsecond=0) - acquired).total_seconds() > ttl`. Effective
  lifetime becomes `[ttl, ttl+1)` — never shorter than requested (safe direction: errs toward
  holding, never toward early release). **No `ISO_FMT` change, no lock.py/recontext.py change**
  — the fix is one function body. Also correct the stale T-010.json description (ttl=1 → ttl≥3
  or a note) and add a one-line TTL-precision caveat to README.
- **Target** → `.harness/bin/harness_common.py` (lock_is_expired), `.harness/tasks/T-010.json`
  (description), `.harness/README.md` (TTL note). **Code-level; no human gate.**
- **Measurable gain** → repro `acquire@X.999 --ttl 1` yields `effective_life ≥ 1.0s` (today
  0.001s); a scripted "acquire --ttl 1 as A; immediately acquire as B" no longer produces
  `stole_expired:true` for B within <1s (today it can); count of hand-off notes overriding the
  documented TTL "per G6" drops to **0** (today 2: T-010.json:21, :26).

### P-006 — Log `lock_busy` events so contention is observable (RANK 2, severity MEDIUM)

- **Evidence** → lock.py:50-60 and recontext.py:68-78 print `busy:` then `return 1`/`False`
  with **no `hc.log_event`**; `grep -in busy events.jsonl` = **0**, yet a busy refusal occurred:
  T-010.json:26 `ver-c acquire then ver-d same path -> 'busy: ... held by ver-c' EXIT_CODE=1`.
- **Diagnosis** → Lock contention — the one signal the §5A loop most needs — is written only to
  a transient stdout and vanishes. The audit engine cannot compute "busy refusals per task,"
  which is precisely the falsifiable metric gen-1's own lock proposals used. Every other lock
  outcome (acquired/released/swept/stolen) is logged; only the refusal is silent.
- **Mutation (mechanism)** → before `return 1` (lock.py) and `return False` (recontext.py) in
  the busy branch, add `hc.log_event("lock_busy", path=<normalized path>, holder=<me>, blocked_by=existing.get("holder"), task=<task>, existing_task=existing.get("task_id"))`. No
  behavior change, additive event only. Document the new event kind in the module docstrings
  (in-file). *(Note: the `path=` value here should use the same normalization P-008 introduces,
  since both proposals land in lock.py/recontext.py — see WB partition.)*
- **Target** → `.harness/bin/lock.py`, `.harness/bin/recontext.py`. **Code-level; no human gate.**
- **Measurable gain** → a two-writer contention repro yields `grep -c lock_busy events.jsonl`
  **> 0** (today 0); "busy refusals per task" becomes a computable metric so future audits can
  assert a target (e.g. `< 1 per task`) instead of noting it is unmeasurable.

### P-007 — `blackboard.py update --artifact` should accept repeats (RANK 3, severity MEDIUM)

- **Evidence** → blackboard.py:407 `p_upd.add_argument("--artifact", default=None)`;
  cmd_update:281-284; repro (§3) shows `--artifact A --artifact B` silently keeps only `B`;
  real workaround = two separate calls (events.jsonl:120, :122).
- **Diagnosis** → Default argparse `store` lets a repeated flag overwrite silently, so an agent
  registering several artifacts in one call loses all but the last **with no error**. Silent
  data loss in the artifact ledger the audit trail depends on; today only avoided by knowing to
  issue N calls.
- **Mutation (mechanism)** → change to `action="append"` (blackboard.py:407) and iterate in
  cmd_update:281-284 (`for a in (args.artifact or []): if a not in arts: arts.append(a)`).
  Keep the log line emitting one `task_updated` per call (or join the list) — additive,
  backward-compatible with single-flag callers. Update the docstring usage example (in-file).
- **Target** → `.harness/bin/blackboard.py`. **Code-level; no human gate.**
- **Measurable gain** → `update T-XXX --artifact A --artifact B` records **both** A and B in
  `tasks[T-XXX].artifacts` (today only B); repro asserts `len(artifacts)==2` for a two-flag call.

### P-008 — Normalize paths to repo-relative at the event-log boundary (RANK 4, severity LOW / log-hygiene)  [RE-DIAGNOSED in Rev-2]

- **Evidence** (corrected in Rev-2) → `grep -c '/Users/' events.jsonl` = **9** at snapshot T
  (Rev-1 wrongly said "4"; the auditor had only counted the recontext hits it grepped for).
  All 9 predate the Rev-1 hand-off (latest `2026-07-04T06:20:14Z` < hand-off `06:25:21Z`), so
  this is a **standing** leak, not drift. Breakdown by source:
  - **recontext.py (4)** — events.jsonl:116/117/160/161, `"path":"/Users/…/.harness/recontext_evidence.md"`, from the hardcoded absolute `EVIDENCE_PATH` (recontext.py:47) logged at recontext.py:58/:84/:105.
  - **notify.py (1)** — events.jsonl:199 `notify_config_initialized … "path":"/Users/…/.harness/notify_config.json"`, from notify.py:200 `hc.log_event("notify_config_initialized", path=str(CONFIG_PATH))`.
  - **lock.py, caller-supplied (4)** — events.jsonl:226/227/228/229 (`agent":"main"`, task T-011), `"path":"/Users/…/.harness/scratch/verify_T-011.txt"`, because lock.py:66/:98 log `path=args.path` **verbatim** — ANY caller passing an absolute `--path`/positional path leaks it.
  Relative counter-examples: lock.py callers that passed relative paths logged relative (events.jsonl:101/129 `".harness/bin/recontext.py"`).
- **Diagnosis** (re-scoped) → This is **not recontext-only** and not merely cosmetic. It is a
  missing **path-normalization step at the log boundary**: three sites feed `log_event(...,
  path=…)` whatever string they hold, so user-specific absolute paths (non-portable across
  machines/checkouts, and noisy for grep/diff) leak into the shared semantic log. The lock.py
  case is the important one — it's driven by *caller* input, so a recontext-only fix (Rev-1's
  proposal) could never deliver "all future lock-event path fields are relative."
- **Mutation (mechanism)** → normalize to repo-relative at each log site. Two options:
  - **(a) inline, per site** — at recontext.py:58/:84/:105, notify.py:200, and lock.py:66/:98,
    log the repo-relative form, e.g. `str(Path(p).resolve().relative_to(hc.ROOT))` with a
    fallback to the original string for legitimately out-of-root paths. Keeps
    `harness_common.py` untouched. **Preferred** — preserves the 3-way disjoint partition.
  - **(b) shared helper** — add `hc.rel_path(p)` to `harness_common.py` and call it at all
    sites (DRY, single source of truth). Cleaner engineering **but** it puts P-008 into
    `harness_common.py`, which is WA's file (P-005), creating overlap — see §6 partition
    implication.
- **Target** → **(a)** `.harness/bin/lock.py`, `.harness/bin/recontext.py`, `.harness/bin/notify.py`.
  **(b)** additionally `.harness/bin/harness_common.py` (overlaps WA). **Code-level; no human gate.**
- **Measurable gain** (achievable, forward-looking) → after the fix, `lock.py acquire
  <ABSOLUTE-path-inside-repo> --holder X` logs a **relative** `path` field; a scripted probe
  that passes an absolute path and greps only the newly-appended event yields
  `grep -c '/Users/' <new-events>` = **0** (today such a call leaks, cf. events.jsonl:226-229).
  Same assertion for a recontext `add` and a notify init. (Historical lines 116-229 are
  append-only and left as-is; the metric is on *new* events, not a retroactive rewrite.)

---

## 6. Minimal parallel worker-task partition (DISJOINT file ownership)

Three tasks, each owning a **disjoint** file set, so up to 3 workers apply them concurrently
with zero lock contention. `harness_common.py` is imported by the other tools, but WA's change
is confined to one function body (no API/signature change), so parallel application is safe.

| Proposed task | Proposals | Files it (and ONLY it) may write |
|---|---|---|
| **WA** | P-005 (G6) | `.harness/bin/harness_common.py`, `.harness/tasks/T-010.json`, `.harness/README.md` |
| **WB** | P-006 (N1) + P-008 (G7, option **a**) | `.harness/bin/lock.py`, `.harness/bin/recontext.py`, **`.harness/bin/notify.py`** |
| **WC** | P-007 (G8) | `.harness/bin/blackboard.py` |

Disjointness check (each file appears in exactly one row): harness_common.py→WA, T-010.json→WA,
README.md→WA, lock.py→WB, recontext.py→WB, notify.py→WB, blackboard.py→WC. **No file in two
tasks.** P-006 and P-008(a) are co-located in WB because both edit `lock.py`+`recontext.py`;
the Rev-2 re-diagnosis adds **`notify.py`** to WB (its config-init log site, events.jsonl:199).
All three remain worker→verifier cycles with **no human gate** (§0).

> **Partition implication of P-008 option (b)**: if the coordinator prefers the shared
> `hc.rel_path()` helper, P-008 would also edit `harness_common.py`, which WA owns (P-005 edits
> the SAME file). That is a real overlap — the partition would then need EITHER (i) merging
> P-005+P-008 into one WA task that owns `harness_common.py` + `lock.py` + `recontext.py` +
> `notify.py` (fewer parallel workers), OR (ii) serializing WA→WB on `harness_common.py`.
> **Recommendation: take option (a)** (inline normalization) to keep the clean 3-way parallel
> split; the DRY helper is a minor code-quality gain not worth collapsing the partition.

---

## 7. Registration note (evolution queue)

Per claude.md §5A.3-4, this audit does **not** apply mutations. Coordinator to register
P-005…P-008 into `state.json evolution.pending_proposals` (assigning final P-numbers) and spawn
worker tasks per the §6 partition. **No `human_gates` entry is triggered** — no `claude.md` /
`gemini.md` edit is proposed this generation (state.json:26). Minor unregistered residues:
N2 (refresh/heartbeat), N3 (explicit `sweep`), `--force` release — all UNTESTED-not-defective;
recommend an assertion in the next contention smoke rather than a mutation.

**Handoff target**: verifier. **Replay path**: grep every quoted line at its cited file:line;
re-run the two `python3 -c` repros in §3 against read-only `harness_common`/`argparse` imports;
for P-008, confirm `grep -c '/Users/' events.jsonl` = 9 and that all 9 timestamps precede the
Rev-1 hand-off (06:25:21Z).
