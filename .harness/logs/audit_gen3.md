# Generation-3 Evolution Audit (T-035)

- **Auditor**: evolution-analyst (Opus, thinker) — claude.md §5A steps 1-2.
- **Generation audited**: 2 as shipped (P-005…P-008 applied via T-013/T-014/T-015; P-009
  guardrail applied via T-031) PLUS the full `state.json evolution.next_audit_inputs`
  backlog (18 items, `.harness/state.json:343-360`) PLUS a fresh trajectory sweep of the
  T-031..T-034 traffic (guardrail rollout + attack matrix, migration script hardening,
  de-Fable NLAH mutation).
- **Written**: 2026-07-05 (UTC).
- **Rule** (unchanged from gen-1/gen-2): every claim quotes a concrete `events.jsonl:<line>`,
  source `<file>:<line>`, or `state.json:<line>`. A proposal without quoted evidence is
  invalid and is deleted. This audit **REGISTERS proposals only**; applying them is a
  separate worker→verifier cycle (claude.md §5A.3-4).
- **Standing human decisions honored, not re-litigated** (per T-035 contract): (1) **U1-U4
  are PRE-APPROVED** — converted to concrete falsifiable task specs below, not debated;
  (2) **active_role removal is PRE-APPROVED** (operator 2026-07-05) — spec'd as ONE minimal
  gated diff (P-017, §5.8); (3) **de-Fable is handled in T-034** (currently `review`) — NOT
  duplicated here; §7 records the file-ownership dependency my ORCHESTRATION.md/claude.md/
  README.md proposals inherit from it.

---

## 0. HUMAN GATE REQUIRED

**EXACTLY ONE gated item this generation: P-017 (active_role removal).** It edits `claude.md`
(§2B line 34, §4 tree line 66) and `README.md` (tree line 14), tripping the `state.json
human_gates` entry *"mutating claude.md or gemini.md"* (`state.json:human_gates`). It is
**PRE-APPROVED by the operator on 2026-07-05** ("avienta a agentes a hacer los 18 insumos" +
the standing active_role decision) — flagged prominently in §5.8 under **HUMAN GATE:
pre-approved 2026-07-05**. All other accepted proposals (P-010…P-016) are code-level or
touch agent-definition / ORCHESTRATION / plan / project files, none of which is `claude.md`
or `gemini.md`, so none trips the gate.

> **Note on gemini.md**: `grep -rni active_role` returns hits ONLY in `claude.md:34`,
> `claude.md:66`, and `.harness/README.md:14` — **gemini.md contains no active_role
> reference**, so the gated bundle does not need to touch it. No other stray claude.md /
> gemini.md wording fix surfaced in the sweep, so the gated bundle is genuinely minimal:
> claude.md + README.md active_role only.

---

## 1. Corpus summary (snapshot at audit-time T)

| Source | Count at snapshot T | Note |
|---|---|---|
| `.harness/logs/events.jsonl` | **644 lines** (`wc -l`) | grows live — counts are a monotone lower bound at T (~2026-07-05T03:0xZ). Append-only: cited line N never moves. |
| `.harness/logs/transcript.jsonl` | **1071 lines** | Experience pillar; grows live under this audit's own tool calls. |
| `.harness/state.json` | `evolution.next_audit_inputs` = 18 items (`state.json:343-360`); `human_gates` = 4; `limits` (max_parallel_workers=3, max_steps_per_task=50, max_seconds_per_command=300) | the 18-item backlog is the primary scope. |
| Task detail files | T-031, T-032, T-033, T-034 notes/handoffs | guardrail + migration + de-Fable trajectories with verifier verdicts. |
| Source under audit | `.harness/bin/blackboard.py`, `.claude/agents/orchestration-planner.md`, `.harness/plan.md`, `projects/mdtoc/*` | targets of the accepted proposals. |

Event-kind histogram (whole file, 644 lines): `task_updated 171`, `lock_acquired 107`,
`lock_released 102`, `task_claimed 74`, `task_handoff 40`, `task_added 33`,
`session_holder_registered 23`, `session_holder_unregistered 17`, `goal_mode_start 16`,
**`producer_check_refused 15`**, `goal_reached 9`, `goal_mode_reset 9`, `goal_abandoned 4`,
`recontext_added 4`, **`producer_check_overridden 4`**, `index_built 3`, `notify_dry_run 3`,
**`lock_busy 3`**, `notify_config_initialized 2`, `reputation_corrected 1`,
`proposals_registered 1`, `generation_bumped 1`, `claim_expired 1`, `announcement_added 1`.

---

## 2. Fresh trajectory sweep — T-031..T-034 (looking for NEW failure modes)

Classification key: **DESIGNED** = mechanism firing correctly (not a failure);
**VALIDATED** = an invariant real traffic now proves held; **GAP** = a genuine friction/defect.

### 2.1 P-009 guardrail — DESIGNED refusals firing correctly

The gen-3 guardrail rollout (T-031) plus its attack matrix (scratch tasks T-093..T-098)
produced **15 `producer_check_refused` events**, every one a correct refusal of a self-done
or premature-done attempt:

- `events.jsonl:514-515` — `T-093 prev=in_progress agent=probe-x / probe-y` refused (self-done from in_progress).
- `events.jsonl:517` — `T-093 prev=review agent=probe-x producer=probe-x` refused (producer==approver).
- `events.jsonl:530` — `T-031 prev=review agent=substrate-worker-1 producer=substrate-worker-1` refused (the producer of the guardrail itself blocked from verdicting its own work).
- `events.jsonl:547` — `T-094 prev=done agent=probe-w producer=probe-x` refused (done-on-done idempotence guard — see §5.9 no-action ruling).
- `events.jsonl:568` — `T-097 prev=review agent=agent-X producer=agent-X` refused.

**Verdict: DESIGNED — the guardrail is mechanically sound.** T-031 was itself verdicted by a
**rotated reviewer** (`events.jsonl:585` `T-031 status=done agent=verifier-b`), practicing F6.

### 2.2 Escape hatch — DESIGNED, exercised 4×

`producer_check_overridden` fired 4 times: **2 are probe attacks** (`events.jsonl:523/539`,
`agent=probe-x`, notes "emergency override test") and **2 are the legitimate verifier uses**
diagnosed in §5.1 below (`events.jsonl:605` verifier-c/T-032, `events.jsonl:618`
verifier-c/T-033). The `--override-producer-check` + mandatory `--note` mechanism works.

### 2.3 VALIDATED — gen-2 fixes proven live this generation

| gen-2 fix | gen-3 evidence | Verdict |
|---|---|---|
| P-006 `lock_busy` logging | **3 `lock_busy` events** now exist: `events.jsonl:377` (holder=substrate-worker-2), `:407` (holder=vrf-holderX), `:421` (holder=combo-a). Gen-2 measured 0. | VALIDATED — contention is now observable; the §5A loop can compute busy-per-task. |
| P-009 F7 for status changes | `task_updated status=done` events now carry an explicit acting `agent`: `events.jsonl:585` (`agent=verifier-b`), `:606` / `:619` (`agent=verifier-c`) — NOT a uniform ambient session id. | VALIDATED — verdict auditing is now direct, closing F7 for status changes (see §5.9). |
| P-007 artifact-append | `task_updated` artifact is now a **list**: `events.jsonl:433` `['projects/mdtoc/mdtoc/slugger.py','projects/mdtoc/tests/test_slugger.py']`; multi-file done events at `:465/:634`. | VALIDATED — multi-artifact single-call works (see §5.9 shape-change no-action). |

### 2.4 VALIDATED — migration overwrite hole opened AND closed within the sweep window

The T-032 verifier note (`events.jsonl:605`) surfaced a real defect: *"pre-existing target
.claude/settings.json / ORCHESTRATION.md / USAGE.md SILENTLY OVERWRITTEN … no backup/warn."*
T-033 was the hardening task; its verifier note (`events.jsonl:618`) records *"THE HOLE FROM
T-032 IS CLOSED … WITHOUT --force -> all 5 collisions [SKIP-EXISTS], shasum -c ALL OK …
BACKUP CHAIN … NOTHING deleted."* **Verdict: VALIDATED — closed in T-033; no new proposal.**

### 2.5 The ONE genuine NEW gap the sweep confirms — P-009 review-status friction

This is input #18 (`state.json:360`) now backed by hard log evidence — see §5.1. **No other
new defect surfaced.** The de-Fable mutation (T-034) shows a clean rewording-only lifecycle
(`events.jsonl:627/633/634/635`, handed to verifier at `:635`); its inputs are consistent
with my proposals (§7 handles the ORCHESTRATION.md/claude.md/README.md ownership overlap).

---

## 3. Reproduction of the P-009 friction (read-only source inspection)

Root cause is two lines in `blackboard.py`:

1. **`cmd_claim` overwrites `review`** — `blackboard.py:242` allows claiming a `review` task,
   then unconditionally sets `t["status"] = "claimed"`. So the moment a verifier claims (or
   sets `in_progress` on) a task to track it, the `review` marker is destroyed.
2. **`cmd_update` done-guard keys on CURRENT status, not on authorship** —
   `blackboard.py:288` `if previous_status != "review":` → hard refuse. This branch fires
   **before** the `actor != handoff_producer` check at `:296`, so a legitimate cross-agent
   verifier is refused purely because the status is no longer `review` — even though the
   handoff exists and `actor != handoff.from`.

Trajectory proof (both legitimate, both forced to `--override-producer-check`):

- **T-032**: handoff `events.jsonl:599`; verifier-c set in_progress `:603`; done attempt
  refused `events.jsonl:604` (`prev=in_progress agent=verifier-c producer=substrate-worker-2`);
  forced override `events.jsonl:605` (note: *"override used only because I set in_progress
  under my own id for tracking"*). **actor (verifier-c) ≠ producer (substrate-worker-2)** —
  a false refusal.
- **T-033**: handoff `events.jsonl:614`; verifier-c re-claimed `:616` (review→claimed);
  done attempt refused `events.jsonl:617` (`prev=claimed producer=main`); forced override
  `events.jsonl:618`. Again **actor ≠ producer** — a false refusal.

---

## 4. Coverage matrix — all 18 next_audit_inputs, dispositioned

| # | Input (state.json line) | Disposition |
|---|---|---|
| 1 | mdtoc friction: `tests/__init__.py` unowned bootstrap (`:343`) | **P-013** (merged with #5) |
| 2 | Nit: TTL bracket `(ttl,ttl+1]` vs README `[ttl,ttl+1)` (`:344`) | **document-only** — optional 1-char bundle into P-017's README edit (§5.9) |
| 3 | Shape change: `task_updated` artifact list vs string (`:345`) | **NO ACTION** — parsers already handle both (§5.9) |
| 4 | Race: verifier probe-claim on T-027 (`:346`) | **P-014-adjacent** — subsumed by the F3 dedup at #7; ruling in §5.9 (document convention, decline flag) |
| 5 | F1: `tests/__init__.py` unowned bootstrap (`:347`) | **P-013** (dup of #1) |
| 6 | F2+F8: mdtoc `check` hardcodes DEFAULT_MAX_DEPTH, no `--max-depth`, no depth record → false-stale (`:348`) | **P-011** |
| 7 | F3: double-claim race, `claim != safe read` (`:349`) | **NO ACTION as code** — document a probe convention; decline the `--dry-run` flag (§5.9) |
| 8 | F4: slugger dedup contract collision vs github-slugger recursion (`:350`) | **P-012** |
| 9 | F5: slugger_c rule-table doc uplift for promoted slugger_b (`:351`) | **bundled into P-012** (cosmetic sub-item) |
| 10 | F6: verdict monoculture, verifier rotation (`:352`) | **P-016** (already practiced ad-hoc: verifier-b/verifier-c; codify) |
| 11 | F7: task_updated done events carry no actor field (`:353`) | **NO ACTION** — CLOSED by P-009 (§2.3, §5.9) |
| 12 | P-009 follow-ups i/ii/iii (`:354`) | **NO ACTION** — (i) intended, (ii) closed, (iii) unproven (§5.9) |
| 13 | U1: planner Unknowns section (`:355`) | **P-014** (pre-approved) |
| 14 | U2: note taxonomy DECISION/DEVIATION/TRADEOFF/OPEN-QUESTION (`:356`) | **P-016** convention (pre-approved); optional `--note-kind` flag deferred (§5.9) |
| 15 | U3: blindspot-pass interview (`:357`) | **P-015** (pre-approved) |
| 16 | U4: explainer + 3 comprehension questions before heavyweight gates (`:358`) | **P-016** (pre-approved) |
| 17 | NLAH-GATED: active_role stale reference (`:359`) | **P-017** — HUMAN GATE pre-approved (§5.8) |
| 18 | P-009 friction, review-status lockout (`:360`) | **P-010** (rank 1) |

---

## 5. Proposals (falsifiable, ranked)

Ranking rationale: **P-010** is the only item that actively **erodes a shipped safety
mechanism** (agents learn to reflexively pass `--override-producer-check`, hollowing out the
guardrail) AND is proven twice in live logs. **P-011/P-012** are correctness defects in the
shipped external project (mdtoc). **P-013…P-016** are process/observability uplifts (U1-U4
pre-approved). **P-017** is the gated active_role removal.

### 5.1 P-010 — Fix the P-009 review-status false-refusal (RANK 1, severity HIGH) [code-level]

- **Evidence** → `blackboard.py:242` (claim overwrites review→claimed), `:288`
  (`if previous_status != "review":` refuses before the authorship check at `:296`);
  live: `events.jsonl:604`+`605` (T-032, verifier-c≠producer, forced override),
  `events.jsonl:617`+`618` (T-033, same). Input `state.json:360`.
- **Diagnosis** → The done-guard authorizes on **current status** instead of **authorship**.
  A verifier who claims or sets `in_progress` on a review task to track it destroys the
  `review` marker (`:242`) and is then refused (`:288`) even though a handoff exists and
  `actor != handoff.from`. The correct-in-principle escape hatch was used for a false
  positive **twice in two consecutive tasks** — the exact "retry storm / reflexive override"
  antipattern the §5A loop is meant to catch.
- **Mutation (mechanism)** → Reorder the guard to key on authorship, not status: **refuse
  done iff (no handoff has ever occurred) OR (`args.agent == handoff.from`)**, regardless of
  current status. Concretely: replace the `previous_status != "review"` gate at `:288` with
  a check that a `handoff` object exists on the task (`t.get("handoff")` is not None, i.e.
  it went through review at least once) and fall through to the existing `:296`
  `agent == handoff_producer` refusal. Preserve the "never went to review at all → refuse"
  behavior (a task that was only ever open/claimed/in_progress still cannot jump to done).
  Alternatively/additionally, make `cmd_claim` preserve `review` for verifier-role claims;
  the authorship-based guard is the primary fix and is sufficient alone.
- **Target** → `.harness/bin/blackboard.py` (`cmd_update` guard ~`:285-315`; optionally
  `cmd_claim` ~`:242`). **Code-level, no human gate.**
- **Measurable gain** → after the fix, a scripted "worker handoff → different-agent claim →
  different-agent done" completes at **exit 0 with NO `--override-producer-check`** (today it
  requires the override, `events.jsonl:604/617`); the count of `producer_check_overridden`
  events where `agent != producer` drops to **0** (today 2: `:605`,`:618`); a genuine
  self-done (`agent == handoff.from`) and a never-reviewed jump-to-done still return exit 1.

### 5.2 P-011 — mdtoc `check` respects generation depth (F2+F8) (RANK 2, severity MED-HIGH) [code-level]

- **Evidence** → input `state.json:348`: *"check hardcodes DEFAULT_MAX_DEPTH=3, no
  --max-depth flag, and generate persists no depth record -> structural false-stale when
  generated at non-default depth."* Artifact provenance: `events.jsonl:465`
  (`projects/mdtoc/mdtoc/cli.py` shipped via T-028).
- **Diagnosis** → `generate` at a non-default depth writes a TOC that `check` then re-derives
  at depth 3 and declares stale — a false failure with no user recourse (no flag, no stored
  record). This is a correctness bug in the first shipped external project.
- **Mutation (mechanism)** → (a) add `--max-depth N` to both `generate` and `check`; (b)
  persist the depth used by `generate` (an HTML comment marker adjacent to the TOC markers,
  e.g. `<!-- mdtoc:maxdepth=N -->`, OR a frontmatter key) so `check` reads it back and
  compares at the same depth; (c) `check` with no flag and no stored record keeps today's
  depth-3 default (backward compatible).
- **Target** → `projects/mdtoc/mdtoc/cli.py` (+ its `__main__`/argparse if separate, same
  package dir). **Code-level, no human gate.**
- **Measurable gain** → `generate --max-depth 2` then `check` (no flag) returns **exit 0**
  (today exit 1 = false-stale); a golden test `generate --max-depth 4; check --max-depth 4`
  round-trips clean; `check` on an unmarked legacy file still behaves as today.

### 5.3 P-012 — mdtoc slugger dedup contract matches github-slugger recursion (F4 + F5) (RANK 3, severity MED) [code-level]

- **Evidence** → input `state.json:350`: *"naive base->count dedup contract mandates output
  collision ['foo','foo-1','foo-1'] vs real github-slugger recursion - contract revision +
  new golden vectors is a real gen-3 item"*; `state.json:351` (F5 doc uplift). Artifact:
  `events.jsonl:433` (`slugger.py`+`test_slugger.py` shipped via T-023..T-027).
- **Diagnosis** → The current base→count dedup can emit duplicate slugs (a real collision) on
  inputs whose base already ends in a counter suffix; github-slugger instead recurses until
  the candidate is unique. The tournament golden vectors (T-027) codified the buggy contract,
  so the "gold" is wrong.
- **Mutation (mechanism)** → adopt recursive dedup (increment-and-recheck until the slug is
  not in the seen-set); revise the golden vector fixtures to the github-slugger-correct
  outputs; add the specific collision case `['foo','foo-1','foo-1']` → `['foo','foo-1','foo-1-1']`
  (or the true github-slugger result) as a regression vector. **F5**: lift slugger_c's cited
  rule-table docstring style into the promoted slugger.
- **Target** → `projects/mdtoc/mdtoc/slugger.py`, `projects/mdtoc/tests/test_slugger.py`
  (+ any golden-vector fixture file in that tests dir). **Code-level, no human gate.**
- **Measurable gain** → for any input list, `len(set(slugs)) == len(slugs)` holds (today it
  can fail — a duplicate slug breaks anchor links); the new regression vector passes; the
  full mdtoc suite (T-029 replay) stays green after cli.py's P-011 change (joint verifier).

### 5.4 P-013 — Planner enumerates shared bootstrap files as owned artifacts (F1) (RANK 4, severity MED) [code-level]

- **Evidence** → input `state.json:343` & `:347`: *"tests/__init__.py needed by py3.9
  unittest discover was unowned by the T-020 plan; two workers hit it, worker-2 created it
  as disclosed shared bootstrap."* Planner file lacks any bootstrap/shared-file rule:
  `grep -ni "bootstrap|__init__|shared.*file" .claude/agents/orchestration-planner.md` = 0.
- **Diagnosis** → The DAG lets two parallel workers race an unowned infra file (test package
  marker, conftest-like scaffolding). The planner's "Decomposition rules"
  (`orchestration-planner.md:21-33`) never require enumerating shared bootstrap files, so
  they fall between tasks.
- **Mutation (mechanism)** → add a Decomposition rule: *"Enumerate shared bootstrap/infra
  files (test package markers like `__init__.py`, conftest, build scaffolding) and assign
  each to exactly ONE task as an owned artifact — or a dedicated bootstrap task that others
  depend on. No infra file may be unowned across parallel siblings."*
- **Target** → `.claude/agents/orchestration-planner.md` (Decomposition rules §21-33).
  **Code-level (agent def, NOT claude.md/gemini.md), no human gate.**
- **Measurable gain** → a re-plan of an mdtoc-shaped epic lists `tests/__init__.py` (or
  equivalent) with an explicit owner; a two-worker replay produces **0** "created shared
  bootstrap as disclosed deviation" hand-off notes (today 1, T-021/T-022 window).

### 5.5 P-014 — Planner Unknowns section per epic (U1, PRE-APPROVED) (RANK 5, severity MED) [code-level]

- **Evidence** → input `state.json:355` (operator pre-approved). `plan.md` (122 lines) and
  `orchestration-planner.md` currently carry no Unknowns quadrant: `grep -ni unknown` on both
  = 0. This is a pre-approved implementation item, not a debate.
- **Diagnosis** → Epics are dispatched without a structured surface for known-unknowns; F1
  (P-013) and F4 (P-012) are both examples of unknowns that only surfaced mid-execution.
- **Mutation (mechanism)** → (a) add to `orchestration-planner.md` a mandatory step:
  *"Before publishing the DAG, populate an Unknowns section in `plan.md` using the 4
  quadrants (known-knowns / known-unknowns / unknown-knowns / unknown-unknowns). Every
  BLOCKING known-unknown must be resolved with the human OR converted to a spike task that
  the dependent DAG node `depends_on`, BEFORE the DAG is published."* (b) add an `## Unknowns
  (4 quadrants)` template block to `plan.md`.
- **Target** → `.claude/agents/orchestration-planner.md`, `.harness/plan.md`. **Code-level,
  no human gate.**
- **Measurable gain** → the next epic's `plan.md` contains a populated Unknowns section;
  `grep -c "known-unknown" .harness/plan.md > 0`; every blocking known-unknown maps to a
  spike task id or a recorded human decision before the first worker task is claimable.

### 5.6 P-015 — Pre-dispatch blindspot interview (U3, PRE-APPROVED) (RANK 6, severity LOW-MED) [code-level]

- **Evidence** → input `state.json:357` (operator pre-approved). No blindspot/interview step
  exists: `grep -ni "blindspot|AskUserQuestion|interview" .claude/agents/orchestration-planner.md ORCHESTRATION.md` = 0.
- **Diagnosis** → Unknown-knowns (things the human knows but never stated) never get
  surfaced; the planner proceeds on unstated assumptions.
- **Mutation (mechanism)** → add a planner protocol step: *"Before dispatching a NEW epic,
  run a blindspot pass: present the human with 3-5 concrete assumptions you are about to bake
  into the DAG and ask them to confirm/correct (use AskUserQuestion). Record the answers in
  plan.md's Unknowns section."*
- **Target** → `.claude/agents/orchestration-planner.md` (Protocol §15-19). **Code-level, no
  human gate.**
- **Measurable gain** → the next epic's `plan.md` records ≥1 assumption confirmed/corrected
  by the human before DAG publication; a downstream "wrong-assumption" rework hand-off note
  count of 0 for that epic.

### 5.7 P-016 — ORCHESTRATION conventions: U4 gate-explainer + U2 note-taxonomy + F6 verifier rotation (RANK 7, severity MED) [code-level; SEQUENCE AFTER T-034]

- **Evidence** → **U4** `state.json:358` (pre-approved): *"before heavyweight human gates
  (first git push), the epic join must produce an explainer + 3 comprehension questions …
  aligns with operator rule 'no publicar lo que no se entiende'."* **U2** `state.json:356`:
  note taxonomy DECISION/DEVIATION/TRADEOFF/OPEN-QUESTION. **F6** `state.json:352` +
  live-proof it's already practiced ad-hoc (`events.jsonl:585` verifier-b, `:606`/`:619`
  verifier-c rotated in).
- **Diagnosis** → Three convention gaps land in the same doc. F6 rotation is happening but
  uncodified (risk it lapses under load); U4 gate-comprehension is an unwritten operator
  rule; U2 has no documented vocabulary so audits can't `grep` OPEN-QUESTIONs.
- **Mutation (mechanism)** → in `ORCHESTRATION.md`: (a) **U4** — add a rule that before any
  heavyweight human gate (first `git push`), the epic-join verifier must produce an explainer
  + exactly 3 comprehension questions for the operator; (b) **U2** — document the note
  taxonomy `DECISION | DEVIATION | TRADEOFF | OPEN-QUESTION` as the required prefix
  convention for hand-off/task notes; (c) **F6** — codify verifier rotation: *"no single
  agent may verdict >N consecutive tasks in an epic; epic joins require a reviewer distinct
  from every producer in the epic."*
- **Target** → `ORCHESTRATION.md`. **Code-level, no human gate. MUST sequence AFTER T-034
  is verified done** (T-034 owns ORCHESTRATION.md — §7).
- **Measurable gain** → `grep -c "OPEN-QUESTION" ORCHESTRATION.md > 0` (taxonomy documented);
  a subsequent epic's notes are prefixed with a taxonomy tag so `grep -c "OPEN-QUESTION:"`
  over its notes is computable and chaseable; the next first-push gate is preceded by an
  explainer artifact + 3 questions; no epic has a single agent as sole approver of all its
  producer tasks (F6).

### 5.8 P-017 — Remove the stale `active_role` NLAH reference (RANK 8) [**HUMAN GATE: pre-approved 2026-07-05**]

- **Evidence** → `claude.md:34` (*"Depending on the instruction written in
  `.harness/active_role`, adopt one of the following personas…"*) and `claude.md:66` (runtime
  tree entry `active_role`); `.harness/README.md:14` (tree entry). Confirmed **no code reads
  it**: verifier-c's T-032 note (`events.jsonl:605`): *"active_role: grep found NO CLI/hook
  reads it; target fully functional without it."* Input `state.json:359`.
- **Diagnosis** → An NLAH instruction ("read `.harness/active_role`") with no backing
  CLI/hook and not seeded by the migration script — a thinking-action gap baked into the spec
  (agents are told to consult a file that never exists). The role model is now expressed via
  the `.claude/agents/*.md` sub-agent definitions, not a single-runner marker file.
- **Mutation (mechanism)** → MINIMAL diff: (a) `claude.md:34` — replace the active_role
  instruction with the current reality: personas are assigned by the sub-agent definition
  (`.claude/agents/*.md`) / the coordinator's dispatch, not by reading a marker file; (b)
  `claude.md:66` — remove the `active_role` line from the runtime-substrate tree; (c)
  `README.md:14` — same tree-line removal. **Do NOT touch roles, rules, gates, limits, or the
  XML-tag conventions** — this is a stale-reference removal, not a redesign. Optionally fold
  the cosmetic input #2 fix here (`README.md` TTL bracket `[ttl,ttl+1)` → `(ttl,ttl+1]`) since
  this task already owns README.md — a 1-character edit (§5.9).
- **Target** → `claude.md` (§2B line 34, §4 tree line 66), `.harness/README.md` (tree line 14).
  **HUMAN GATE — pre-approved by operator 2026-07-05.** gemini.md NOT touched (no active_role
  reference). **MUST sequence AFTER T-034 is verified done** (T-034 owns claude.md + README.md
  — §7).
- **Measurable gain** → `grep -c active_role claude.md` = **0** (today 2); `grep -c
  active_role README.md` = **0** (today 1); the four `state.json human_gates` entries remain
  verbatim; markdown still renders (no broken headers); no change to any role/rule/gate/limit
  line (diff review shows only the active_role lines removed/reworded).

### 5.9 Declined / no-action / document-only (with reasons)

| Item | Ruling | One-line reason |
|---|---|---|
| #2 Nit TTL bracket `(ttl,ttl+1]` vs `[ttl,ttl+1)` | **document-only** (optional 1-char bundle into P-017's README edit) | measure-zero cosmetic; prose is already correct, not worth a standalone task. |
| #3 artifact list-vs-string shape | **NO ACTION** | consumers already handle both — this audit's own parser read `events.jsonl:14` (str) and `:433` (list) without breakage; no observed parser failure. |
| #7 F3 `--dry-run` claim flag | **decline the flag; document convention** | adding a claim mutation mode is scope creep; the existing `deps_unmet`/cascade gate (`blackboard.py:236`) already refuses ineligible claims — the fix is a *convention* (use permanently-gated scratch tasks for refusal probes, e.g. T-093..T-098) which is already the observed practice, not a new CLI surface. |
| #11 F7 actor field | **NO ACTION — CLOSED** | `task_updated status=done` now carries explicit acting `agent` (`events.jsonl:585/606/619`); verdict auditing is direct, not reconstruction-dependent. |
| #12(i) done-on-done idempotence loss | **NO ACTION — intended** | `events.jsonl:547` shows `T-094 prev=done` correctly refused; re-marking done is a coherent no-op-refusal, not a defect. |
| #12(ii) F7 for non-task_updated events | **NO ACTION** | remaining events carry `agent`+`holder`/`requester` fields (e.g. `lock_busy` `events.jsonl:377`), so the actor is already recoverable; no verdict-relevant event is opaque. |
| #12(iii) lifetime-authorship mode | **decline** | producer-of-record semantics are working (P-009 applied_note, `state.json:333`); no evidence it is "too lax." Revisit only with a counterexample. |
| #9 F5 slugger doc uplift | **accepted as sub-item of P-012** | pure doc polish co-located in slugger.py; not worth a standalone task. |

---

## 6. Worker partition — STRICTLY disjoint file ownership, ≤3 workers/wave

Every file appears in **exactly one** task. Two tasks (GE, GF) inherit a dependency on
**T-034** because they edit files T-034 owns (§7).

| Wave | Task | Proposals | Files it (and ONLY it) may write | Depends on |
|---|---|---|---|---|
| **1** | **GA** | P-010 | `.harness/bin/blackboard.py` | — |
| **1** | **GB** | P-013 + P-014 + P-015 | `.claude/agents/orchestration-planner.md`, `.harness/plan.md` | — |
| **1** | **GC** | P-011 | `projects/mdtoc/mdtoc/cli.py` (+ its argparse/`__main__` in same pkg) | — |
| **2** | **GD** | P-012 (+F5) | `projects/mdtoc/mdtoc/slugger.py`, `projects/mdtoc/tests/test_slugger.py` (+ golden fixtures in that tests dir) | GC (mdtoc coherence: one joint suite replay) |
| **3** | **GE** | P-016 (U4+U2+F6) | `ORCHESTRATION.md` | **T-034 done** |
| **3** | **GF** | P-017 (+opt #2) | `claude.md`, `.harness/README.md` | **T-034 done** + **HUMAN GATE (pre-approved)** |

**Disjointness check** (each file → one task only): blackboard.py→GA;
orchestration-planner.md→GB; plan.md→GB; mdtoc/cli.py→GC; mdtoc/slugger.py→GD;
tests/test_slugger.py→GD; ORCHESTRATION.md→GE; claude.md→GF; README.md→GF. **No file in two
tasks.** No shared helper is split (contrast gen-2's P-008 helper decision) — P-010 is one
function body in blackboard.py; P-011/P-012 touch different mdtoc files.

**Wave rationale**: Wave 1 = 3 parallel workers on fully independent files. GD is Wave 2 (not
a file conflict — GC/GD files are disjoint — but a *contract* coupling: P-012 changes slug
output that cli.py renders, so let GC land first and have a single verifier replay the whole
mdtoc suite once). GE/GF are Wave 3 because both edit files still owned by the in-review
T-034 (§7); they are mutually disjoint (ORCHESTRATION.md vs claude.md+README.md) so run in
parallel once T-034 verifies. GF additionally awaits the (already pre-approved) human gate.

---

## 7. Consistency with T-034 (de-Fable, in review) — NOT duplicated

T-034 (`review`) owns `claude.md, gemini.md, ORCHESTRATION.md, README.md,
docs/harness-explainer.html` (`blackboard.py show T-034` artifacts; handoff `events.jsonl:635`).
My proposals **do not duplicate** any de-Fable rewording. Three of my target files overlap
T-034's ownership: **ORCHESTRATION.md (GE), claude.md + README.md (GF)**. Therefore GE and GF
**must be scheduled AFTER T-034 is verified done** — sequential ownership, never concurrent.
T-034's inputs are consistent with mine: it renames the coordinator model-agnostically and
explicitly excludes `.harness/tasks/*`, `.harness/logs/*`, `plan.md`, `state.json`,
`blackboard.json` (T-034 detail), none of which my Wave-1/2 tasks contend for. GB's
`.harness/plan.md` and `.claude/agents/*` are outside T-034's scope — no conflict.

---

## 8. Production-readiness criteria (answering "after these 18, are we production-ready?")

Falsifiable join criteria — the operator may use this harness on real projects when ALL hold:

1. **Guardrail trust restored (P-010 landed)**: a scripted "worker handoff → different-agent
   claim → different-agent done" completes at **exit 0 with no `--override-producer-check`**;
   over a fresh multi-task run, `producer_check_overridden` events where `agent != producer`
   = **0** (today 2). A genuine self-done and a never-reviewed jump-to-done still exit 1.

2. **Multi-session swarm smoke**: **≥2 concurrent real Claude Code sessions** (≥2 distinct
   `session_id`s appending to `transcript.jsonl` in the same window) claim/lock/handoff/verdict
   on one shared DAG with **0 unresolved contention** (busy refusals per task < 1, computed
   from `lock_busy` events — now measurable per §2.3) and **0 producer≠approver false
   refusals**.

3. **Second external project bootstrapped**: `migracion_proyecto.py` seeds a NEW repo (not
   mdtoc — ideally non-Python to prove language-agnosticism); a full epic runs end-to-end
   there; the TARGET's `events.jsonl` records the lifecycle while the source repo stays
   untouched (the T-033-hardened no-overwrite / backup-chain guarantees hold, `events.jsonl:618`).

4. **U1-U4 in force on a real epic**: at least one epic dispatched THROUGH the upgraded
   planner where (a) `plan.md` has a populated Unknowns section (`grep -c known-unknown > 0`),
   (b) ≥1 `OPEN-QUESTION`-tagged note was logged and chased to closure, (c) a pre-dispatch
   blindspot interview is recorded, (d) the first-push gate was preceded by an explainer + 3
   comprehension questions.

5. **mdtoc correctness closed**: P-011 + P-012 landed — `check` round-trips at any
   `--max-depth`, and `len(set(slugs)) == len(slugs)` holds for every input (no duplicate
   anchors); full mdtoc suite green under a joint verifier replay.

6. **active_role reconciled + de-Fable done**: T-034 verified done; `grep -c active_role
   claude.md README.md` = 0; the four human gates remain verbatim; `git push` remains a
   human-only gate.

7. **Clean gen-4 audit**: the next `next_audit_inputs` backlog contains only document-only /
   UNTESTED items — no open HIGH/MED gap — confirming the loop has converged.

Until criteria 1-3 hold, the honest answer is **"not yet — the guardrail false-refusal
(P-010) must land first, and the swarm/second-project smokes are unrun."** The 18 inputs are
dispositioned, but production readiness is defined by these join tests passing, not by the
backlog being emptied.

---

## 9. Registration note (evolution queue)

Per claude.md §5A.3-4 this audit **does not apply** anything. Coordinator to register
**P-010…P-017** into `state.json evolution.pending_proposals` (final P-numbers at coordinator
discretion) and spawn worker tasks per the §6 partition. **Exactly ONE human-gate entry is
triggered — P-017 (active_role, `claude.md`+`README.md`) — and it is PRE-APPROVED (operator
2026-07-05).** Declined/no-action items (§5.9) are recorded so they are not re-surfaced as
gen-4 inputs unless new evidence appears. GE/GF carry a hard dependency on T-034 being
verified done (§7).

**Handoff target**: verifier. **Replay path**: grep every cited `events.jsonl:<line>` and
source `<file>:<line>`; re-confirm `grep -c lock_busy events.jsonl` = 3, the 15
`producer_check_refused` / 4 `producer_check_overridden` counts, and that `events.jsonl:604`
+`617` show `agent != producer` (the two false refusals motivating P-010); confirm
`grep -c active_role claude.md` = 2 and `= 0` in gemini.md.
