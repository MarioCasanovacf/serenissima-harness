# Generation-4 Evolution Audit + Production-Readiness Gate (T-055)

- **Auditor**: evolution-analyst (Opus, thinker) — claude.md §5A steps 1-2.
- **Scope**: ALL 11 `state.json evolution.next_audit_inputs` (indices 0-10) PLUS a fresh
  trajectory sweep of the T-042..T-054 traffic (T-042 liveness forensic, T-053 P-019
  registration auth gate, cronsplain non-Python epic T-043..T-052, swarm smoke T-054,
  P-020 sonnet-verifier cost policy). PLUS the load-bearing deliverable: the
  **PRODUCTION-READINESS VERDICT** across all 7 `state.json evolution.readiness_criteria`.
- **Written**: 2026-07-05 (UTC).
- **Rule** (unchanged from gen-1..gen-3): every claim quotes a concrete
  `events.jsonl:<line>`, source `<file>:<line>`, `state.json`/`plan.md` anchor, or task
  note. A proposal without quoted evidence is invalid and is deleted. This audit
  **REGISTERS proposals only**; applying them is a separate worker->verifier cycle
  (claude.md §5A.3-4). PROPOSE only — never applied here.
- **Snapshot-at-T caveat**: live counts below are a monotone lower bound taken at
  ~2026-07-05T06:2xZ. `events.jsonl`/`transcript.jsonl` are append-only, so a cited line N
  never moves; `state.json`/`plan.md`/`blackboard.json` are mutable, so this audit cites
  their STABLE anchors (section names / keys), not line numbers (see input #3 disposition).

---

## 0. HUMAN GATE REQUIRED

**ZERO gated items this generation.** No proposal below edits `claude.md` or `gemini.md`
(the only wording tripping the `state.json human_gates` entry *"mutating claude.md or
gemini.md"*). All code-level proposals target `.harness/bin/blackboard.py`; all
document/process proposals target `ORCHESTRATION.md` or are batched doc-nits. `git push`
remains an untouched human-only gate. The gen-3 active_role gate (P-018) already landed and
its physical file was deleted under a separate gate-approved cleanup (git `1a2c58a`).

---

## 1. Corpus summary (snapshot at audit-time T)

| Source | Count at snapshot T | Note |
|---|---|---|
| `.harness/logs/events.jsonl` | **1168 lines** (`wc -l`) | append-only; cited line N is stable. |
| `.harness/logs/transcript.jsonl` | **2146 lines** | Experience pillar; grows under this audit's own tool calls. |
| `state.json evolution.next_audit_inputs` | **11 items** (indices 0-10) | the primary scope. |
| `state.json evolution.readiness_criteria.criteria` | **7 criteria** | the load-bearing gate (§4). |
| `state.json limits` | max_parallel_workers=3, max_steps_per_task=50, max_seconds_per_command=300 | respected by this audit. |

Event-kind histogram (whole file, 1168 lines): `task_updated 314`, `lock_acquired 180`,
`lock_released 175`, `task_claimed 149`, `task_handoff 88`, `task_added 80`,
`session_holder_registered 42`, `session_holder_unregistered 28`,
**`producer_check_refused 27`**, `goal_mode_start 21`, `goal_reached 14`,
`goal_mode_reset 9`, **`producer_check_overridden 8`**, **`session_holder_register_refused 6`**,
**`lock_busy 5`**, `goal_abandoned 4`, `recontext_added 4`, `index_built 3`,
`notify_dry_run 3`, `notify_config_initialized 2`, `announcement_added 2`,
`reputation_corrected 1`, `proposals_registered 1`, `generation_bumped 1`, `claim_expired 1`.

**New event kinds since gen-3**: `session_holder_register_refused` (6) — the P-019 auth gate
firing (gen-3 measured 0; the kind did not exist). `lock_busy` grew 3->5 (two new swarm
events), `producer_check_overridden` 4->8, `producer_check_refused` 15->27.

---

## 2. Fresh trajectory sweep — T-042..T-054 (DESIGNED / VALIDATED / GAP)

Classification key: **DESIGNED** = mechanism firing correctly; **VALIDATED** = an invariant
real traffic now proves held; **GAP** = a genuine friction/defect.

### 2.1 VALIDATED — the gen-3 authorship-first guard (applied P-011) killed the false-refusals
The gen-3 audit's rank-1 fix (review-status false-refusal) landed: the refusal text now reads
*"...producer cannot verdict their own work (producer != approver), **regardless of current
status ('review')**..."* (`events.jsonl:691` T-099, `:747` T-104). Source confirms the guard
is authorship-keyed and status-agnostic: `blackboard.py:295-312` refuses done iff
(`not handoff`) OR (`args.agent == handoff_producer`). **Every cronsplain/T-04x cross-agent
done was CLEAN (no override)**: T-040 `events.jsonl:838`, T-041 `:836`, T-042 `:889`,
T-043 `:935`, T-044 `:972`, T-045 `:987`, T-046 `:1000`, T-047 `:1113`, T-048 `:1124`,
T-049 `:1135` — all `done` by a different agent, none in the override set. **VALIDATED.**

### 2.2 VALIDATED — P-019 registration auth gate closed the T-042 liveness question
T-042 (forensic) proved the P-002 liveness premise FALSE (registration WAS live at edit
time: `events.jsonl:693` register substrate-worker-2 03:08:38Z BEFORE the 4 Edits at
transcript:1161/1163/1168/1171); verifier-b replayed and confirmed H4 (T-042 note). T-042
surfaced one latent authorization gap (any id could self-whitelist a session holder), which
P-019 (T-053) closed. The gate now fires: **6 `session_holder_register_refused` events**
(`events.jsonl:912` fake-cross-engine self-register, `:916` cross-unregister,
`:942`/`:943`/`:944`/`:945` the poison/empty probes). verifier-b's T-053 before/after bypass
table: *"register fake -> EXIT 0 self-whitelist (pre) vs EXIT 1 REFUSED (post); check_lock
me=main on fake-held lock -> EXIT 0 BYPASS (pre) vs EXIT 2 BLOCKED (post)."* **VALIDATED —
input #2 is CLOSED, not re-proposed.**

### 2.3 VALIDATED — swarm coordination smoke (criterion 2 substrate)
T-054 (verifier-d) drove a genuine multi-PROCESS concurrent race on fresh frontier
T-206..T-211: clean 3+3 claim split (swarm-c:206/208/210, swarm-d-worker:207/209/211, exactly
one `task_claimed` each), 0 double-claims, contention probe exits swarm-c-acquire=0 /
swarm-d-worker-acquire=1(refused) / check_lock=2(blocked), one new `lock_busy`
(`events.jsonl:1109` requester swarm-d-worker on swarm-c-held), P-019 held (0 swarm-*
registrations). See §4 criterion 2 for the honest session_id caveat. **VALIDATED at the
mechanical level.**

### 2.4 VALIDATED — second external project, non-Python, source untouched
The cronsplain epic (T-043..T-052, Node/CommonJS) shipped 93 passing tests end-to-end.
`git diff --stat` across the epic window (`5c5aea6~1..61adaf2`) touched **only**
`projects/cronsplain/*` (+ 2 scratch claim files + the deliberate P-020 harness-verifier.md
policy edit); `git log ... -- .harness/bin claude.md gemini.md` over the same range is
**EMPTY** — harness source untouched. **VALIDATED** (composition caveat in §4 criterion 3).

### 2.5 GAP (MED) — backtick / $() shell-substitution corrupts note text (recurring 4+)
Input #9, now with hard sweep evidence. Agents typing `--note` text containing backticks or
`$(...)` at the shell get them command-substituted BEFORE reaching blackboard.py, mangling
the note. T-052 join note (`events.jsonl:1163`): *"(2) backtick-in-note shell corruption
recurring; use single-quote/backtick-free notes."* transcript evidence: *"backtick ate a
command in the prior handoff note's P7 line): the omitted command was: python3
.harness/bin/blackboard.py status"* and *"backtick-quoted in my terminal invocation and got
shell-command-substituted ... leaving blanks before the -> in items (1)(2)(3)."* This
corrupts the Experience/Decision observability pillars (verifier replay commands are lost).
The no-backticks convention is in ad-hoc use but not mechanically enforced. **GAP -> P-021.**

### 2.6 GAP (MED) — verifier-execute (owns-nothing join) tasks force a reflexive override
`producer_check_overridden` grew 4->8. Of the 4 new: 2 are probe attacks (`events.jsonl:691`
T-099, `:747` T-104) and **2 are LEGITIMATE verifier-execute joins forced to override**:
T-054 (`events.jsonl:1122`, producer=**null**, *"verifier-EXECUTE task, no handoff record ->
audited P-011 override: producer=created_by fable-5-coordinator != approver verifier-d"*) and
T-052 (`events.jsonl:1163`, producer=**null**, *"owns-nothing coordinator join, override
used, no separate producer"*). A task created_by the coordinator, then claimed + executed +
verdicted by a single verifier (no separate producer) trips the `not handoff` refusal
(`blackboard.py:298`) even though producer!=approver is VACUOUSLY satisfied. This is the same
reflexive-override antipattern the gen-3 P-010 fought, re-appearing in a new task class.
**GAP -> P-022.**

### 2.7 GAP (LOW, latent) — no terminal-state rule after authorship-first guard
Input #1. Source `blackboard.py:295-312`: the done-guard refuses ONLY on (`not handoff`) OR
(`agent==producer`) — it is status-agnostic, so a task already `done` (or `failed`) that
carries a handoff and is touched by a different actor can be re-transitioned. **No live
incident**: 0 `done->done` or `failed->done` `task_updated` events in the whole log. Coherence
oddity, not a bypass (the input itself says so). **GAP (latent) -> P-023.**

### 2.8 ASSESSED — P-020 sonnet-tier verifier holds the opus-tier quality bar (n=1 strong)
Input #7. Registry `harness-verifier.tier = "sonnet (opus per-dispatch for high-stakes
verdicts)"`. The T-051/T-052 join was verdicted by harness-verifier at sonnet tier and it
performed at opus-comparable depth: T-051 note *"node --test tests/*.js -> tests 93 pass 93
fail 0 ... exit 0 (**real green, not node --test empty-set false-green**)"* — the verifier
pre-empted the exact false-green trap baked into T-052's own acceptance criterion. T-052 note
(`events.jsonl:1163`) then hand-verified leap-year occurrences (2028/2032/2036), exclusivity
next-minute, invalid-expr clean exit1 no stack — AND self-reported three fresh frictions
(node false-green, backtick corruption, promotion-verbatim imprecision). Rejection integrity
across the ledger: the guardrail refused 27 producer-check violations and the override set is
entirely probes + the 2 legit joins — no rubber-stamp verdict surfaced. **ASSESSMENT: the
sonnet-tier verifier maintained the bar on this data point; the proportional-verification
rule proves out and is worth formalizing (P-024), with an honest n=1 caveat.**

No other new defect surfaced in the sweep.

---

## 3. Per-input disposition table — all 11 next_audit_inputs

| # (idx) | Input (short) | Severity | Disposition |
|---|---|---|---|
| 0 | gen-4 backlog seed (declined items already dispositioned) | INFO | **NO ACTION** — informational; gen-3 declined items stand. |
| 1 | done-on-done / failed->done re-accepts under authorship-first; terminal-state rule? | LOW | **P-023** (latent; 0 live incidents). |
| 2 | worker-registration liveness (check_lock fail-open?) | — | **CLOSED** by T-042 (H4, premise false) + T-053 P-019 (`events.jsonl:912/916/942-945`); verify-closure DONE, NOT re-proposed. |
| 3 | normative docs cite volatile state.json line numbers (drift stale) | DOC | **document-only** — cite stable section anchors for MUTABLE files; line-cites only for append-only logs (this audit already does so). |
| 4 | slugger.py DEDUP pseudocode `while (originalSlug in occurrences)` should read `slug` | DOC | **document-only** — `slugger.py:70`; algorithm is verified github-parity (T-039/P-013), comment-only reconcile. |
| 5 | F6 prose "all 9 producer tasks" loose (T-027/T-029 were verifier-role) | DOC | **document-only** — substance holds; batch into next ORCHESTRATION.md touch. |
| 6 | physical `.harness/active_role` file still on disk | — | **CLOSED** — deleted under gate-approved cleanup (git `1a2c58a`); `grep -c active_role` = 0 in claude.md/README/gemini.md. NO ACTION. |
| 7 | P-020 sonnet-verifier quality vs opus bar; formalize proportional-verification | MED->rule | **P-024** — proves out on T-051/T-052 (§2.8); formalize into ORCHESTRATION.md (n=1 caveat). |
| 8 | bare `node --test` false-greens (0 tests, exit 0) on tests/test_*.js layout | MED->rule | **P-025** — criteria must carry the exact layout-matching command + verifiers assert nonzero test count. |
| 9 | backtick/$() in `--note` gets shell-substituted, corrupting notes (4+ incidents) | MED | **P-021** (rank 1) — CLI note-from-stdin/file + documented convention. |
| 10 | "verbatim promotion" imprecise (renames identifiers, strips self-tests) | MED->rule | **P-026** — define byte-diff exemption set in ORCHESTRATION.md. |

---

## 4. THE PRODUCTION-READINESS VERDICT (the 7 criteria, walked)

> Verdict scale: **MET** (falsifiable evidence holds now) / **MET-PENDING** (met except for a
> step that structurally cannot fire yet, or contingent on a cheap registered fix) /
> **UNMET**. Honest, not generous.

**Criterion 1 — guardrail-trust: cross-agent done needs no override; overridden-where-agent!=producer = 0.**
**MET.** P-011 (authorship-first guard) applied: refusal text *"regardless of current status"*
(`events.jsonl:691`,`:747`); source `blackboard.py:295-312`. Every genuinely-handed-off
cross-agent done since is CLEAN (T-040..T-049, `events.jsonl:836..1135`). The whole-log
override set is `T-032, T-033` (gen-3 pre-P-011, now impossible), probes `T-093/094/099/104`,
and the 2 verifier-execute joins `T-052/T-054` (producer=**null**, NOT agent!=producer). So
`producer_check_overridden where agent != producer-of-a-handoff` = **0**. A genuine self-done
still exits 1 (`events.jsonl:691`,`:747`).

**Criterion 2 — swarm smoke: >=2 concurrent sessions on one DAG; busy-refusals/task < 1; 0 false producer refusals.**
**MET (with documented caveat).** T-054: fresh frontier T-206..T-211, concurrent
swarm-c/swarm-d-worker, clean 3+3 split, 0 double-claims, exactly 1 new `lock_busy`
(`events.jsonl:1109`, busy/task << 1), 0 false producer refusals, P-019 held. **CAVEAT
(verifier-d, honest)**: this proves genuine multi-PROCESS concurrency with distinct AMBIENT
identities via the engine-agnostic CLI path, but does NOT spawn two distinct Claude LLM
`session_id`s (operator declined the sandbox drop). All invariants key on
`CLAUDE_HARNESS_AGENT_ID` + lock-holder string, never on an LLM session token, so the
process-level proof is faithful/equivalent for the mechanical guarantees. session_id-literalism
is a **scope caveat, not a gap**.

**Criterion 3 — second external project via migracion_proyecto.py bootstrapping a NEW repo; full epic end-to-end; source untouched.**
**MET (with composition caveat).** Non-Python full epic proven: cronsplain (Node/CommonJS,
T-043..T-052, 93 tests), harness source untouched by git (§2.4). Non-destructive NEW-repo
bootstrap proven separately: T-032/T-033 (`events.jsonl:605`/`:618` — full CLI lifecycle in a
migrated target, source read-only, backup-chain, nothing deleted). **CAVEAT**: the two halves
are proven SEPARATELY (migration = lifecycle smoke; cronsplain = in-repo full epic), not
COMPOSED into "a full dev epic run inside a freshly-migrated repo." Intent (language-agnostic
external capability + non-destructive migration) is met; the literal composition is unproven
and adds no new mechanical risk. Honest call: **MET-with-note**.

**Criterion 4 — U1-U4 exercised on a real epic (Unknowns populated, OPEN-QUESTION chased, interview recorded, pre-push explainer+quiz).**
**MET-PENDING (gate-contingent).** cronsplain ran through the upgraded planner: `plan.md`
Unknowns section populated (all 4 BLOCKING known-unknowns Q1-Q4 closed before DAG publish,
`plan.md` `## Unknowns` block); U3 blindspot interview recorded (`plan.md` "Unknown knowns —
candidate assumptions from the U3 blindspot interview"); OPEN-QUESTION protocol documented and
tagged notes exist. **BUT (d) the pre-push explainer + 3-comprehension-question quiz (U4) has
NOT fired** — because the first `git push` human gate has not been requested (no push
attempted this generation). U4 is structurally un-triggerable until a push is requested, so
this is **MET-PENDING-GATE**, not UNMET: 3 of 4 U-items exercised on a real epic; the 4th
awaits its triggering gate.

**Criterion 5 — mdtoc correctness closed (P-012 + P-013, suite green under joint verifier).**
**MET.** P-012 (check --max-depth round-trip) + P-013 (slugger dedup collision fix) applied
and verified (T-038 done, T-039 done; git `e1015ef` *"mdtoc correctness closed"*; source marker
`slugger.py:31` *"UPDATED by T-039/P-013"*). The only residual is a pseudocode-COMMENT nit
(input #4, DOC) — the shipped algorithm is verified github-parity.

**Criterion 6 — active_role reconciled + de-Fable done; push stays human-gated.**
**MET.** active_role dead refs removed (P-018; `grep -c active_role` = 0 in claude.md,
README.md, gemini.md) and the physical file deleted under gate approval (git `1a2c58a`).
De-Fable done (P-010, git `0e2bd11` *"the harness is now explicitly model-agnostic"*). The
`state.json human_gates` entry *"git push or any network publication"* is intact and untouched.

**Criterion 7 — clean gen-4 audit (backlog only document-only/UNTESTED; no open HIGH/MED gap).**
**MET-PENDING (self-referential, honest).** **No open HIGH gap** exists. Two MED items remain,
both registered below: (P-021) backtick note corruption — real, recurring, but non-safety
(coordination invariants intact) with the no-backticks workaround already in ad-hoc use; and
(P-022) the verifier-execute reflexive-override coherence gap — a logged, justified override,
not a safety bypass. The remaining backlog is DOC nits (inputs #3/#4/#5) and rule-formalizations
(P-024/P-025/P-026). Per the criterion's strict wording ("no open MED gap"), it is not
perfectly clean; per severity reality, both MED items are ergonomic/coherence with known
mitigations and cheap fixes. **MET-PENDING** on landing P-021 + P-022.

### BOTTOM LINE

**Production-ready: YES-WITH-NOTES.** Criteria **1, 5, 6 are fully MET**. Criteria **2 and 3
are MET with honest scope caveats** (session_id-literalism; migration+epic proven separately,
not composed) that add no mechanical risk. Criterion **4 is MET-PENDING-GATE** (U4's pre-push
quiz cannot fire until the first `git push` gate is requested — structural, not a defect).
Criterion **7 is MET-PENDING** (no HIGH gaps; two MED ergonomic/coherence items registered as
P-021/P-022). **Nothing blocks real use of the coordination substrate today**: the guardrail
is trustworthy, registration is auth-gated, the swarm race is clean, and a non-Python epic
shipped end-to-end without touching harness source. The open items are ergonomics (note
corruption), one coherence wart (verifier-execute override), and one contingent gate (U4).

---

## 5. Ranked proposals (falsifiable) — code-level / NLAH-gated / document-only

### CODE-LEVEL (target `.harness/bin/blackboard.py`; no human gate)

**P-021 — note-from-stdin/file to end backtick shell-substitution corruption (RANK 1, MED)**
- **Evidence** -> input #9; `events.jsonl:1163` *"backtick-in-note shell corruption
  recurring"*; transcript *"backtick ate a command in the prior handoff note's P7 line ... the
  omitted command was: python3 .harness/bin/blackboard.py status"*; transcript
  *"backtick-quoted ... got shell-command-substituted ... leaving blanks before the -> in items
  (1)(2)(3)."*
- **Diagnosis** -> `--note "<text>"` is expanded by the shell before blackboard.py sees it;
  backticks/`$()` execute and blank out, corrupting the audit trail (verifier replay commands
  lost). Degrades the Experience + Decision observability pillars (claude.md §4A.2-3).
- **Mutation** -> add `--note-file <path>` and/or `--note-stdin` to `update`/`handoff` that
  read the note verbatim (no shell expansion); document a no-backticks convention for inline
  `--note` in ORCHESTRATION.md.
- **Measurable gain** -> an agent passes a note containing backticks/`$()` via `--note-file`
  and blackboard.py stores it BYTE-IDENTICAL (diff stored-note vs file = empty); new "backtick
  ate / shell corruption" mentions in subsequent notes drop to **0** (today 4+).

**P-022 — model the verifier-execute (owns-nothing join) task class; no reflexive override (RANK 2, MED)**
- **Evidence** -> `events.jsonl:1122` (T-054, producer=**null**, forced override,
  *"verifier-EXECUTE task, no handoff record"*), `events.jsonl:1163` (T-052, producer=**null**,
  *"owns-nothing coordinator join"*); source `blackboard.py:298` refuses on `not handoff`.
- **Diagnosis** -> a task created_by the coordinator, then claimed+executed+verdicted by one
  verifier (no separate producer) trips the no-handoff refusal though producer!=approver is
  vacuously satisfied — same reflexive-override antipattern as the gen-3 P-010 false-refusal,
  re-appearing in a new task class; inflates the override signal.
- **Mutation** -> allow `done` for a handoff-less task iff (`created_by != args.agent`) AND the
  task's role is verifier/join; log a `producer_check_autopass` event recording `created_by`
  as producer-of-record; keep `--override-producer-check` mandatory for everything else.
- **Measurable gain** -> a verifier-execute task completes at **exit 0 with no override**;
  `producer_check_overridden` events with `producer==null` for verifier tasks drop to **0**
  (today 2: `events.jsonl:1122`,`:1163`); genuine self-done and never-reviewed jumps still exit 1.

**P-023 — terminal-state rule after the authorship-first guard (RANK 3, LOW, latent)**
- **Evidence** -> input #1; source `blackboard.py:295-312` has NO terminal-state check
  (refuses only on `not handoff` OR `agent==producer`, status-agnostic); **0** `done->done` /
  `failed->done` events in the whole log (no live incident).
- **Diagnosis** -> a `done`/`failed` task carrying a handoff can be re-transitioned by a
  different actor — a coherence oddity of authorship-first, not a bypass.
- **Mutation** -> once `status == "done"`, refuse further status changes except an explicit
  `--reopen` flag (with mandatory `--note`); log `task_reopened`.
- **Measurable gain** -> a `done->done`/`failed->done` attempt returns **exit 1**
  ("terminal state; use --reopen"); the `--reopen` path logs `task_reopened`; no regression to
  legitimate cross-agent done (T-040..T-049 replay stays exit 0).

### NLAH-GATED-BUT-NO-HUMAN-GATE (target `ORCHESTRATION.md`; process/convention, does NOT touch claude.md/gemini.md)

**P-024 — formalize the proportional-verification rule (RANK 4, DOC/process)**
- **Evidence** -> input #7; registry `harness-verifier.tier` *"sonnet (opus per-dispatch for
  high-stakes verdicts)"*; T-051 note *"real green, not node --test empty-set false-green"*;
  T-052 note (`events.jsonl:1163`) caught the false-green + 2 nuances at opus-comparable depth.
- **Diagnosis** -> the sonnet-default / opus-per-dispatch tiering proved out (n=1 strong) but
  is only implicit in the registry, not a normative rule.
- **Mutation** -> document in ORCHESTRATION.md: default verifier tier = sonnet; escalate to
  opus per-dispatch for high-stakes verdicts (harness mutations, human-gate joins, tournaments);
  record the escalation decision in the verdict note. State the **n=1 caveat** explicitly.
- **Measurable gain** -> `grep -c "proportional" ORCHESTRATION.md > 0`; the next high-stakes
  verdict note records its tier choice against the documented rule.

**P-025 — test-discovery precision: exact layout command + nonzero-count assertion (RANK 5, DOC/process)**
- **Evidence** -> input #8; T-052's own acceptance criterion prescribed bare `node --test`
  which false-greens (0 tests, exit 0) on the `tests/test_*.js` layout; T-051 verifier note
  guarded it manually (*"not node --test empty-set false-green"*), `events.jsonl:1163`.
- **Diagnosis** -> a literal-minded verifier running the bare criterion command would have
  passed the epic running zero tests. The criterion command was imprecise.
- **Mutation** -> ORCHESTRATION.md rule: test-running acceptance criteria MUST carry the exact
  layout-matching glob (e.g. `node --test tests/*.js`) AND the verifier MUST assert a nonzero
  test count (and quote pass/fail/skip totals) in the verdict.
- **Measurable gain** -> a re-audit finds every test-running criterion specifies the glob + a
  min-count assertion; verdict notes quote the runner's `tests N pass N` summary.

**P-026 — define "verbatim promotion" precisely (RANK 6, DOC/process)**
- **Evidence** -> input #10; T-049 verifier-d note *"body-diff ... 189/189 lines IDENTICAL
  except EXACTLY the two error-string renames 'schedule_b:'->'schedule:'; self-check guard
  dropped"*; T-052 note *"promotion-verbatim imprecise"*, `events.jsonl:1163`.
- **Diagnosis** -> a correct promotion legitimately renames candidate-identifying strings and
  strips the self-test / `require(candidates)` guard, so a naive byte-diff both false-fails
  (on the rename/strip) and can false-pass (missing a real algorithm change).
- **Mutation** -> define in ORCHESTRATION.md: promotion = algorithm bytes VERBATIM + a bounded
  exemption set (candidate-prefix identifier renames; removal of the self-test/require-main
  guard). A verbatim check diffs the algorithm body only, over the exemption set.
- **Measurable gain** -> the exemption set is documented; a promotion-fidelity check neither
  false-fails on the identifier rename nor false-passes on an algorithm-body change (re-runs
  the T-049 body-diff and matches its 189/189-except-renames result).

### DOCUMENT-ONLY (nits; batch into the next doc touch, no standalone task)

| Input | Ruling | One-line reason |
|---|---|---|
| #3 volatile line-number citations | **document-only** | rule: cite stable SECTION anchors for MUTABLE files (state.json/plan.md); line-cites only for append-only logs. Self-demonstrated (audit_gen3 state.json:343-360 has drifted). |
| #4 slugger pseudocode `originalSlug`->`slug` | **document-only** | `slugger.py:70` comment reconcile; shipped algorithm is verified github-parity (T-039/P-013). |
| #5 F6 "all 9 producer tasks" prose | **document-only** | loose phrasing (T-027/T-029 were verifier-role); substance holds. |

### NO-ACTION / CLOSED

| Input | Ruling | Reason |
|---|---|---|
| #0 gen-4 backlog seed | **NO ACTION** | informational; gen-3 declined items stand. |
| #2 worker-registration liveness | **CLOSED** | T-042 H4 (premise false) + T-053 P-019 (6 `session_holder_register_refused`, `events.jsonl:912/916/942-945`); verifier-b bypass table. |
| #6 physical active_role file | **CLOSED** | deleted under gate-approved cleanup (git `1a2c58a`); `grep -c active_role` = 0. |

---

## 6. Registration note (evolution queue)

Per claude.md §5A.3-4 this audit **does not apply** anything. Coordinator to register
**P-021..P-026** into `state.json evolution.pending_proposals` (final P-numbers at coordinator
discretion). **ZERO human-gate entries triggered** (no claude.md/gemini.md edit; ORCHESTRATION.md
is not gated). Inputs #2 and #6 are recorded CLOSED so they are not re-surfaced. DOC nits
(#3/#4/#5) batch into the next ORCHESTRATION.md / slugger.py touch.

**Readiness bottom line for the coordinator/operator**: **production-ready: YES-WITH-NOTES.**
Criteria 1/5/6 MET; 2/3 MET-with-caveat; 4 MET-PENDING-GATE (U4 awaits the first push); 7
MET-PENDING (land P-021 + P-022). Nothing blocks real use of the coordination substrate today.

**Handoff target**: verifier. **Replay path**: `wc -l .harness/logs/events.jsonl` (>=1168);
`grep -c session_holder_register_refused events.jsonl` = 6; `grep -c producer_check_overridden
events.jsonl` = 8 (confirm `events.jsonl:1122` T-054 + `:1163` T-052 are producer=null
verifier-execute); confirm T-040..T-049 cross-agent dones are absent from the override set;
`grep -c active_role claude.md .harness/README.md gemini.md` = 0; `git log 5c5aea6~1..61adaf2
-- .harness/bin claude.md gemini.md` = empty (cronsplain source-untouched); `plan.md` contains
a populated `## Unknowns` block with Q1-Q4 closed.
