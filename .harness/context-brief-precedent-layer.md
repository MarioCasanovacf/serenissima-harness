# Context Brief — Precedent Layer / Jurisprudence for Agent Sessions

Author: `context-scout` (retrieval thinker, runs before the planner). Read-only on source;
this brief is the only artifact this agent wrote. Founding source:
`docs/civilizational-roadmap-brief.md` (Serenissima Harness Civilizational Roadmap Brief,
118 lines) — Part II (lines 28-58) is the build target, Part V (90-97) and Part VI (98-106)
are standing design/falsification constraints.

---

## 1. Goal, restated

The brief asks the harness to move from *bureaucracy* (descriptive handoff memos with no
normative force) to *legal order* (records that bind successor agents unless explicitly
overruled). Concretely it wants four prototyped mechanisms layered on top of the existing
task/handoff/note substrate: (a) a schema that marks which parts of a decision are binding
(*ratio*) vs incidental commentary (*dicta*), tagged with a scope, an authority level, and a
stable citation ID; (b) a queryable index of those decisions across "sessions"; (c) an
overruling protocol — who may overturn what, with a mandatory reasoning record, as opposed to
silent divergence; and (d) a conflict-detection pass that flags two active precedents that
contradict each other. The brief explicitly gates this behind a research agenda (stare
decisis mechanics, the ratio-identification problem, overruling doctrines, distinguishing,
civil-law *jurisprudencia constante*, non-judicial precedent, failure modes) and says schema
design may start once research items 1-3 are synthesized (`docs/civilizational-roadmap-brief.md:47-57`).
It explicitly forbids building Part III (political economy / markets) or Part IV
(Westphalian/inter-org diplomacy) yet — "the sequence is load-bearing... do not skip"
(`docs/civilizational-roadmap-brief.md:93`, Part V principle 2) — and sets a standing
falsification/monitoring task independent of the build (Part VI, `docs/civilizational-roadmap-brief.md:98-106`).

---

## 2. Context map (substrate the precedent layer must integrate with)

### 2.1 The blackboard / task substrate
- `.harness/blackboard.json` is the sole shared task index; **only** `bin/blackboard.py`
  writes it, serialized by `flock` (`.harness/README.md:14-15`, `ORCHESTRATION.md:96`).
  A task record's schema (verified live, `.harness/tasks/T-329.json` example): `epic, title,
  status, role, engine, depends_on[], claimed_by, claim_expires_at, priority, detail_file,
  artifacts[], handoff{to_role, from, note, ts}, created_at, created_by`. `VALID_STATUS`
  is `open|claimed|in_progress|blocked|review|done|failed` and `VALID_ROLES` is
  `thinker|worker|verifier` (`.harness/bin/blackboard.py:73-75`).
- Per-task detail files (`.harness/tasks/T-XXX.json`) carry free-text `notes[]`: each entry is
  `{ts, agent, note}` — plain prose, no structured ratio/dicta/scope/authority fields
  (`.harness/tasks/T-329.json:7-23`). Notes are written only via
  `blackboard.py update --note/--note-file/--note-stdin` (`.harness/bin/blackboard.py:51-57`,
  P-021 — raw `--note` is shell-expanded, so backticks/`$()` require the file/stdin form).
- Lifecycle: `open → claimed → in_progress → review → done` (or `blocked`/`failed`/back to
  `open`), enforced mechanically — cascade gate refuses `claim` while `depends_on` are unmet
  (`ORCHESTRATION.md:38-56`, `.harness/bin/blackboard.py:107-115`). `done`/`failed` are
  **terminal**; the only sanctioned way back is `blackboard.py reopen`, which (1) only acts on
  terminal tasks, (2) makes `--note` mandatory (no note = refused, no silent resurrection),
  (3) logs `task_reopened` to `events.jsonl`, (4) resets to `open`
  (`ORCHESTRATION.md:58-67`, `.harness/bin/blackboard.py:470-517`, code comment "P-023:
  terminal-state resurrection, done properly instead of by hand-editing JSON"). **This is the
  single closest existing analog to Part II mechanism 4 (overturning without chaos)** —
  already mandatory-reasoning-gated and event-logged, but scoped to *tasks*, not to
  harness-level decisions/precedents.
- Producer ≠ approver is mechanical, not cultural: `update --status done` is refused unless a
  handoff record exists and the acting agent differs from the handoff's `from` (authorship,
  not current status — P-011); `--override-producer-check` is a logged escape hatch
  (`.harness/bin/blackboard.py:14-28`). A `role=='verifier'` task may go straight to `done`
  with no handoff if `--agent` differs from `created_by` (P-022, `verifier_execute_done`
  event) — self-done by the creator is still refused (`blackboard.py:26-28`).

### 2.2 Shared helpers, locking, identity
- `.harness/bin/harness_common.py`: `guarded()` (flock on `.harness/locks/.guard`, never
  nest), `atomic_write_json` (tempfile + `os.replace`), `append_jsonl` (flock'd append),
  `log_event(kind, **fields)` → `.harness/logs/events.jsonl`, `session_holders()` (fail-safe,
  returns `{}` on any error) (`harness_common.py:81-178`).
- `.harness/bin/lock.py`: one lock file per workspace path (`<rel__path>.lock`, TTL JSON,
  default 900s from `state.json limits`), re-acquire-refreshes (heartbeat),
  `check_lock.py` enforces mechanically only inside Claude Code sessions — other engines must
  call the CLI voluntarily (`.harness/README.md:117-126`, `ORCHESTRATION.md:193-196`).
- `.harness/bin/session.py`: `register|unregister|list` for in-session identity overrides.
  **The only mechanically-enforced authority tier in the entire substrate today**: `register`/
  `unregister` refuse (exit 1) unless the *ambient* identity is in the "coordinator set" —
  `{'main'} ∪ {name : state.json agents.registry[name].role == 'coordinator'}`, read live off
  disk, fail-closed to `{'main'}` on a missing/malformed registry (`.harness/README.md:80-99`,
  `.harness/bin/session.py:31-49,94-119`). Nothing else in the harness has a ranked-authority
  concept. (This agent used exactly this mechanism, legitimately, to register its own
  `context-scout` identity as a session holder before writing this brief — ambient identity in
  this session is the default `main`, which is trivially in the coordinator set.)
- `.harness/bin/recontext.py`: append-only Markdown evidence log
  (`.harness/recontext_evidence.md`), one fixed target file, lock-protected append, each entry
  headed `## [T-XXX] <label> — <agent> — <UTC ts>` with `Source: <file>:<lines>` and a verbatim
  extract; `list` does grep-level parsing, no separate index kept
  (`.harness/bin/recontext.py:1-41`). **This is the closest existing pattern for a lightweight,
  citation-carrying, append-only registry with a CLI wrapper** — but it indexes *corpus
  evidence* for ReContext discipline, not *decisions/precedents*, and has no binding/scope/
  authority fields either.
- `.harness/bin/log_event.py`: the Claude Code `PostToolUse`/`SessionStart`/`Stop` hook that
  fills `transcript.jsonl`; fail-open by design (`log_event.py:1-59`). **This is the only place
  in the codebase a `session_id` field appears** (`payload.get("session_id")`, line 45) — it is
  Claude-Code-hook-only, ephemeral, never written to the engine-agnostic `events.jsonl`, and
  never durable/citable across engines. `prevent_data_loss.py:118` and
  `gemini_headless_runner.py:153` are the only other two `session_id` occurrences in the whole
  `.harness/bin/` tree.
- `.harness/logs/events.jsonl` (2035 lines, verified count) is the engine-agnostic semantic
  event floor — `task_claimed/task_updated/lock_acquired/task_handoff/task_reopened/
  producer_check_refused/session_holder_registered/...` (30 distinct event kinds counted live).
  This is the closest thing to an append-only "court record," but it is a flat, unindexed log
  — no query CLI exists over it beyond `grep` (unlike `blackboard.py show` / `ast_index.py
  query` for other substrates).

### 2.3 `state.json` — the closest thing to a precedent registry today
- `harness_generation` = `4` (bumped only on NLAH mutation via the §5A loop,
  `ORCHESTRATION.md:223-229`) — four bumps total since bootstrap. Far too coarse to serve as
  a "session" counter for individual decisions.
- `limits`: `max_steps_per_task=50, max_seconds_per_command=300, max_retries_per_failure=3,
  lock_ttl_seconds_default=900, claim_lease_seconds_default=3600, max_parallel_workers=3`.
- `human_gates.require_human_approval_for`: git push/network publication, deletions outside
  `.harness/` scratch, first webhook activation, **mutating `claude.md`/`gemini.md`**. This
  last one is the existing "constitutional amendment" gate — the nearest analog to an
  authority-level-4 overruling requirement.
- `agents.registry`: capability contracts per bench agent (`fable-5-coordinator`,
  `orchestration-planner`, `substrate-worker`, `harness-verifier`, `evolution-analyst`,
  `context-scout`, `research-librarian`, `gemini-runner`, plus Codex identities) — each has
  `engine, tier, role, capabilities[]`. **No ranking/authority field exists on any entry.**
  `agents.reputation`: per-agent `{tasks_done, tasks_failed, last_outcome_at}` counters,
  updated by `bump_reputation_locked` on every terminal verdict (`blackboard.py:118-128`).
- `evolution.pending_proposals` / `evolution.accepted_mutations` — **the harness's own de
  facto, informal precedent ledger**, already 30 numbers deep (P-001 through P-030). Verified
  live: `accepted_mutations` holds exactly 27 entries
  (`P-001..P-022, P-024, P-025, P-026, P-029, P-030` — **P-023, P-027, P-028 are missing from
  this array**). Schema per entry (union of all keys observed):
  `id, source, target[], summary, status, gate|verdict, evidence, cost_assessment,
  revisit_trigger, applied_note, applied_at, decided_at, decided_by, kill_triggers,
  measurable_gain, recorded_at, recorded_by, verdict_of_intake`. `rejected-no-adoption`
  entries (P-027, P-028) carry `revisit_trigger` — free text describing the *condition* under
  which the rejection should be revisited (e.g. P-027: "reopen if ≥1 non-synthetic
  goal_abandoned event appears whose command edited files"). **This `revisit_trigger` field is
  the one existing structural precursor to Part II mechanism 5 (Distinguishing / scope
  conditions)** — but it exists only on *rejected* proposals, not on accepted ones, so no
  currently-binding decision records the conditions under which it stops applying.
- `protected_paths` is `[]` (shipped empty, opt-in glob list consumed by
  `.harness/bin/guard_paths.py:117` for a `PreToolUse[Bash]` destructive-command guard,
  fail-open when empty — `.harness/bin/guard_paths.py:6-25`).

### 2.4 The P-number citation pattern already in `ORCHESTRATION.md` (informal precedent)
`ORCHESTRATION.md` cites specific P-numbers inline as load-bearing precedent, in prose, at
least 5 times: `P-023` reopen rule (line 58), `P-025` test-discovery precision with a named
counter-example ("a bare `node --test` returned exit 0 with 0 tests executed... a false-green
a less careful verifier could have rubber-stamped," lines 82-90), `F6` verifier rotation with
both a supporting precedent (T-031's `verifier-b` rotation) and a named counter-example it
forecloses (the mdtoc epic's single-reviewer monoculture, lines 119-126), `P-024` proportional
verification (128-134), `P-026` "verbatim promotion" with a specific byte-diff precedent
(T-049's `schedule.js`, lines 211-218), and `P-030` frontier budget (136-145). Each of these is
exactly the brief's "citation" mechanism (Part II item 3) done by hand, in prose, with no
stable ID resolution, no queryable index, and no ratio/dicta split — the sentence *is* both
ratio and dicta undifferentiated. Individual task notes use the same informal pattern: T-040,
T-037, T-044, T-057 all cite prior P-numbers or specific task IDs as precedent inside free-text
`DECISION:`/handoff notes (verified via grep, not paraphrased — see e.g.
`.harness/tasks/T-044.json` line 27: "TAXONOMY: OPEN-QUESTION (F1-style friction, precedent
mdtoc tests/__init__.py P-013)").

**Concrete integrity gap already present, found while mapping this** (not hypothetical): P-023
(the `reopen` verb) is applied in both code (`blackboard.py:470`) and prose
(`ORCHESTRATION.md:58`) but has **no entry at all** in `evolution.accepted_mutations`, and
`state.json:791` itself flags this as a known latent gap in a gen-5 backlog note: *"gen-5
backlog: P-023 terminal-state --reopen rule (LOW, latent); doc-only nits...".* This is exactly
the class of defect a citation index / conflict-detection pass (Part II deliverables 2 and 4)
is meant to catch — it already exists in the harness's own informal ledger, before any new
layer is built.

### 2.5 Note taxonomy (U2) — the existing (non-binding) ratio/dicta gesture
`ORCHESTRATION.md:69-77` defines four note prefixes so evolution audits can `grep` mechanically
instead of re-reading prose: `DECISION:` (a choice made among valid options), `DEVIATION:`
(work diverged from plan/spec — disclose, don't hide), `TRADEOFF:` (benefit traded for cost),
`OPEN-QUESTION:` (unresolved ambiguity chased to closure by the next audit,
`ORCHESTRATION.md:79-80`). This is real prior art for "mark the operative part of a record" —
but it is a *convention* (SHOULD, not mechanically enforced by any CLI check), it has no
binding/persuasive distinction, no scope field, and no authority level. `DECISION:` notes
today read like *ratio* candidates and `TRADEOFF:`/other prose reads like *dicta*, but nothing
currently forces or checks that split.

### 2.6 Test and delivery conventions to reuse, not reinvent
- Test runner (verified exact invocations from real task acceptance criteria, not inferred):
  `python3 -m unittest discover -s .harness/tests -p 'test_*.py' -v` for the whole substrate
  suite (`.harness/tasks/T-315.json:4`, ran 46 tests OK at last count),
  `-p test_<name>.py` for one file (`.harness/tasks/T-312.json:4,21`; `T-313.json:4`). System
  `python3` here is **3.9.6** (verified: `python3 --version` → `Python 3.9.6`); TOML-parsing
  assertions (`tomllib`, 3.11+) must use `python3.12` (present locally at
  `~/.local/bin/python3.12`) and are `unittest.skipIf(tomllib is None,
  ...)`-guarded in existing tests (`.harness/tests/test_context_scout_parity.py:5-7,24,37`).
  `python3 -m py_compile <new_file.py>` is the existing syntax-gate pattern for new CLIs
  (`.harness/tasks/T-311.json:4`).
- `.harness/bin/*.py` are stdlib-only, `python3 >= 3.9` (`harness_common.py:1-10` module
  docstring) — a precedent-layer CLI must not import `tomllib`/`dataclasses`-with-slots/etc. at
  module scope if it needs to run under the bare `python3` in this environment; gate any 3.10+
  syntax the same way the existing tests gate `tomllib`.
- Prior *external, real-use* epics (`projects/mdtoc/`, `projects/cronsplain/`,
  `projects/<retired-skill>/`) are deliberately scoped **toy/unrelated domains**
  (Markdown TOC generation, cron-expression explanation, a design-taste skill) used to
  exercise the harness's own coordination mechanics against a foreign problem — each has its
  own `README.md`, its own test root, its own `candidates/` tournament directory
  (`projects/mdtoc/`, `projects/cronsplain/` directory listings, verified). **The precedent
  layer is not that kind of deliverable** — Part II's mechanisms integrate directly with the
  harness's own handoff/session mechanics, so the natural home is core substrate
  (`.harness/bin/` + a new `.harness/precedents/` or similar data area), analogous to how
  `blackboard.py`/`lock.py`/`recontext.py` already work, not a `projects/` sandbox. Flagged
  as an assumption below (§4), not asserted as settled.

### 2.7 Research-corpus gap (relevant to the brief's own research agenda)
`papers/` holds 12 PDFs and `fetched_docs/` holds 5 Markdown files — all AI-harness/agent-
engineering material (`agentic_harness_engineering.pdf`, `coffee_bench.pdf`, `conductor.pdf`,
`trinity.pdf`, `intelligent_ai_delegation.pdf`, `recontext.pdf`, `sakana_fugu_tech_report.pdf`,
`natural_language_agent_harnesses.pdf`, `virtual_agent_economies.pdf`,
`distributional_agi_safety.pdf`, `code_as_agent_harness.pdf`,
`harness_engineering_preprints{.pdf,_abstract.md}`; `fetched_docs/`: DeepMind co-scientist,
DeepMind podcast transcript, Gemini-for-Science, zcode features — verified by `ls`). **Zero**
legal/jurisprudence sources exist anywhere in the tracked corpus. `research-librarian`'s
mandate is explicitly "answer questions about the research corpus (papers, fetched docs,
reference repos) with exact file/page citations" (`AGENTS.md` bench table) — it has nothing to
cite for Part II's research agenda items 1-7 (stare decisis mechanics, ratio-identification,
overruling doctrines, distinguishing, civil-law contrast, administrative/mercantile precedent,
failure modes; `docs/civilizational-roadmap-brief.md:49-56`). The brief itself calls this
research "self-contained — agents research this directly from legal literature" and says
"external counsel input, when it arrives, supplements rather than gates"
(`docs/civilizational-roadmap-brief.md:47`), implying reliance on the researching agent's own
general/parametric knowledge of real doctrines (in the same register as Part VII's reading
list, which cites real, well-known works from memory, not from a local corpus). This sits in
tension with Part V principle 5, "No fabricated rigor... distinguish what is established, what
is analogy, and what is speculation" (`docs/civilizational-roadmap-brief.md:96`), since
general-knowledge legal claims cannot get the file+page-citation treatment this harness applies
everywhere else. Flagged as an open question below (§5, item 7) — this agent has no web/LLM
access and cannot resolve it by fetching sources.

---

## 3. Existing precedent-like affordances (build on these, do not duplicate)

| Part II mechanism | Closest existing affordance | Gap vs. what the brief wants |
|---|---|---|
| 1. Binding vs. persuasive | `human_gates` (absolute, 4 categories) vs. everything else (informal); `evolution.pending_proposals` "rejected-no-adoption" verdicts are recorded but non-binding | No graded binding/persuasive spectrum; no per-decision authority level; only a hard binary (gated or not) |
| 2. Ratio vs. dicta | Note taxonomy U2 (`DECISION:`/`DEVIATION:`/`TRADEOFF:`/`OPEN-QUESTION:`, `ORCHESTRATION.md:69-77`) | Convention (SHOULD), not structural/mechanical; no CLI validates the split; free-text notes mix ratio and dicta in one string |
| 3. Citation | Prose P-number citations in `ORCHESTRATION.md` (§2.4 above); `recontext.py`'s `file:lines` evidence citations (evidence-for-corpus-reading, not decisions) | No stable resolvable ID→record lookup (no `blackboard.py show P-023` equivalent); already has at least one integrity gap (P-023, §2.4) |
| 4. Overruling without chaos | `blackboard.py reopen` (mandatory `--note`, logged `task_reopened` event, terminal-state-only) — task-level; `human_gates` NLAH-mutation gate — constitution-level | No overruling verb exists between these two granularities (i.e., for an individual P-number/decision, distinct from a whole task or the whole NLAH text) |
| 5. Distinguishing | `revisit_trigger` field on rejected `evolution.pending_proposals` entries (P-027, P-028) | Only on *rejected* proposals; no accepted/binding decision currently records the conditions under which it stops applying |
| 6. Adjudication | Verifier rotation (F6, `ORCHESTRATION.md:119-126`) requires a reviewer distinct from every producer; the coordinator is the de facto single arbiter of §5A evolution disputes | No designated "appellate" role/function for conflicting precedents across agent lineages; coordinator-as-sole-arbiter is exactly the "single agent decides alone" pattern Part V principle 1 forbids |

---

## 4. Constraints (from CLAUDE.md, ORCHESTRATION.md, cost_policy, protected paths)

- No LLM/AI API calls, no web access, anywhere in this harness's tool agency
  (project `CLAUDE.md` §3 top warning; this agent's own mandate). Any precedent-layer tooling
  must be stdlib-only Python (`>= 3.9`), matching every existing `.harness/bin/*.py`.
- `blackboard.json` may be mutated **only** through `blackboard.py`; hand-editing is forbidden
  (`.harness/README.md:14-15`). Any new precedent registry that piggybacks on the blackboard
  (e.g. new task fields) must go through the same CLI, not a parallel writer.
- `claude.md`/`gemini.md` mutation is a human gate, gated by the §5A loop (`ORCHESTRATION.md
  §6`, `state.json human_gates`). If the precedent layer requires new NLAH sections
  (e.g. "cite precedent before deciding"), that text change itself needs the same
  audit→proposal→human-approval→apply cycle already in force — it cannot be added as a normal
  worker task.
- Frontier budget (P-030): 53-65% raw-token share on `fable`/`opus` per mission window,
  measured by `token_share.py` (`ORCHESTRATION.md:136-145`). Low-verifiability judgment
  (schema/DAG design) stays frontier; high-verifiability execution (code gated by tests, cited
  reading) runs `sonnet` (`ORCHESTRATION.md:147-160`) — this is why `context-scout` (this
  agent) runs `sonnet` and the eventual `orchestration-planner` for this epic should run `opus`.
- Proportional verification (P-024): a precedent-layer schema/CLI is squarely "control-plane/
  contract" tier — full adversarial replay expected, not a brief README-tier check
  (`ORCHESTRATION.md:128-134`).
- Verifier rotation (F6): no single identity may be sole approver across the whole epic
  (`ORCHESTRATION.md:119-126`) — directly relevant since Part II mechanism 6 (adjudication) is
  precisely about avoiding a single arbiter; the epic's own verification process should not
  reproduce the problem it is building infrastructure to solve.
- `protected_paths` is currently `[]` (opt-in only); nothing under a prospective
  `.harness/precedents/` path is pre-protected — if the coordinator wants write-protection on
  the precedent store itself (arguably load-bearing, like `blackboard.json`), that has to be
  configured explicitly via `state.json protected_paths` and `guard_paths.py`
  (`.harness/bin/guard_paths.py:6-25,117-138`), it will not happen automatically.
- Git status at brief time (informational, not a blocker): working tree has uncommitted
  changes to `.harness/blackboard.json`/`.harness/state.json` and new untracked files
  `.harness/tasks/T-318.json`..`T-329.json`, `evaluations/`, `projects/<retired-skill>/`
  from a concurrent/prior epic (<retired-skill> promotion, tasks T-318-T-329, currently
  `review`/`blocked`/`open` per `blackboard.py status`). The precedent-layer epic does not
  depend on or touch these; flagged only so the planner doesn't assume a clean tree.

---

## 5. Explicit vs. assumed

### Explicit (verbatim/near-verbatim from the brief)
- The four "core mechanisms to design and implement": binding/persuasive, ratio/dicta,
  citation, overturning, plus distinguishing and adjudication
  (`docs/civilizational-roadmap-brief.md:34-39`).
- The four "deliverables to prototype": precedent-aware handoff schema, citation index,
  overruling protocol, conflict-detection pass (`docs/civilizational-roadmap-brief.md:41-45`).
- The seven-item research agenda, explicitly self-contained/no-web-gate, with schema design
  allowed to start once items 1-3 are synthesized (`docs/civilizational-roadmap-brief.md:47-57`).
- Do NOT build Part III (political economy) or Part IV (Westphalian layer) yet — research only
  for III, not even that for IV yet (`docs/civilizational-roadmap-brief.md:61-86`, Part V
  principle 2).
- Five design principles (no single agent decides alone; sequence is load-bearing; path
  dependence is the moat; watch for alien coordination/forking-merging; no fabricated rigor)
  (`docs/civilizational-roadmap-brief.md:92-96`).
- Falsification criteria and a standing quarterly monitoring task independent of the build
  (`docs/civilizational-roadmap-brief.md:100-106`).

### Assumed (smuggled in, not stated by the brief — flagged, not resolved)
- **Where it lives**: the brief never says whether this is core substrate (`.harness/`) or an
  external practice project (`projects/`). This brief's context map leans substrate (§2.6) but
  that is this agent's inference, not the brief's instruction.
- **What counts as a "session"** for citation purposes ("a decision made in session 40...
  referenceable... in session 200," `docs/civilizational-roadmap-brief.md:36`). No existing
  identifier matches that granularity (§2.2, §5 item 3 below) — the brief assumes a numbered
  sequential unit that does not currently exist.
- **What counts as a "decision" that earns precedent status** — every `DECISION:`-tagged task
  note (dozens already, informal), every P-numbered harness mutation (30, formally gated), or a
  new intermediate tier (e.g. tournament verdicts, epic-join syntheses)? The brief's own
  examples ("we use event sourcing because X," `docs/civilizational-roadmap-brief.md:35`) read
  like architecture-decision-record granularity, closer to `DECISION:` notes than to P-numbers,
  but this is not stated.
- **How "authority level" maps onto the existing role/engine/tier ontology.** The brief's own
  research Q1 asks this to be researched/derived (`docs/civilizational-roadmap-brief.md:49`),
  but the build-target section (Part II) writes as if the mapping will simply exist by the time
  schema design starts. It doesn't today (§2.2, §3 row 1).
- **Retrofitting the ~30 existing P-numbers** into the new schema is nowhere requested by the
  brief itself — it is a scope question the coordinator's own dispatch introduced ("what is the
  migration story for the ~30 existing P-numbers"). The brief's "Deliverables to **prototype**"
  framing suggests forward-only is in scope; full retrofit is a much larger, separate lift.
- **Hard gate vs. on-demand pass** for conflict detection. The brief says "flags contradictory
  active precedents" (`docs/civilizational-roadmap-brief.md:45`) without saying when it runs.

---

## 6. Open questions, ranked by cost of guessing wrong

1. **[HUMAN-ONLY — highest cost]** What decision-granularity earns precedent status: every
   `DECISION:`-tagged task note, only P-numbered harness-constitution mutations, or a new
   intermediate tier? This single choice determines the index's size, the schema's weight, and
   whether the layer is useful-lightweight or unmaintainably heavy. Repo cannot answer this —
   it is a scoping decision.
2. **[HUMAN-ONLY — high cost]** Does this epic retrofit/backfill the existing P-001..P-030
   ledger (`state.json evolution.accepted_mutations`, 27 entries + the P-023 gap documented in
   §2.4) into the new precedent schema, or is the layer forward-only from this generation on,
   leaving history as informally-cited legacy? Guessing "retrofit" when the operator meant
   "prototype forward" triples the scope of the first epic for no requested benefit; guessing
   "forward-only" when the operator wanted continuity leaves the falsification-criteria
   richer-vs-thinner tracking (Part VI) with a discontinuity at generation 5.
3. **[HUMAN-ONLY — high cost]** What identifier is "session" bound to? None of the candidates
   found in the substrate fit cleanly: `harness_generation` (4 total, too coarse),
   task IDs T-XXX (per-unit-of-work, one task can hold several decisions in its `notes[]`),
   or Claude Code's ephemeral hook `session_id` (Claude-only, never durable, never in
   `events.jsonl`). A new counter would need to be minted; the repo gives no default to fall
   back on.
4. **[HUMAN-ONLY — medium-high cost]** How should "authority level" map onto the existing
   role/engine/tier ontology, given the *only* mechanically-enforced authority distinction
   today is `session.py`'s coordinator set (§2.2)? Options include: extending
   `state.json agents.registry` with a rank field, treating engine/tier as a proxy (frontier >
   cheap), or treating role as a proxy (coordinator > thinker > worker/verifier) — none of
   these is currently encoded, and the brief's own research agenda (Q1) treats this as
   something to be *derived from doctrine*, not looked up.
5. **[PARTIALLY REPO-ANSWERABLE, confirm before locking]** Precedent layer lives under
   `.harness/` (core substrate, this agent's read per §2.6) or `projects/precedent-layer/`
   (external-practice-project pattern like mdtoc/cronsplain)? Repo evidence favors `.harness/`
   (Part II integrates directly with the harness's own handoff/session mechanics, not a foreign
   toy domain) — recommend confirming rather than assuming, since it changes which test
   convention and lock/protected-path treatment applies.
6. **[REPO-ANSWERABLE]** Should the conflict-detection pass be a hard gate or an on-demand/
   periodic check? Repo precedent (`check_lock.py` is explicitly "Claude-side sugar" only,
   `ORCHESTRATION.md:193-196`; the harness must behave identically for Claude/Gemini/Codex/
   human, `ORCHESTRATION.md:9`) favors modeling it after `lock.py sweep` /
   `blackboard.py expire_claims` — opportunistic, run on-demand or on every relevant CLI call,
   not a hook only one engine enforces. Still worth an explicit sign-off since it constrains
   the CLI's design.
7. **[REPO-ANSWERABLE re: what's missing, NOT resolvable by this agent re: what to do]** The
   brief's research agenda (items 1-7) has zero grounding corpus in `papers/`/`fetched_docs/`
   (§2.7) and no web/LLM access exists in this harness to fetch one. `research-librarian`'s
   contract is scoped to the existing (non-legal) corpus. Either the operator supplies legal
   source material first, or the research proceeds on the researching agent's general
   knowledge with explicit established/analogy/speculation tagging (Part V principle 5) — this
   is a policy call this agent cannot make.

---

## 7. Summary for the coordinator (≤10 lines)

Brief: `docs/civilizational-roadmap-brief.md` Part II — precedent-aware handoff schema,
citation index, overruling protocol, conflict-detection pass, gated behind a legal-literature
research agenda with zero local corpus to ground it (`papers/`, `fetched_docs/` — 17 files, all
AI-harness engineering, none legal). Existing prior art to build on, not duplicate: the note
taxonomy (`ORCHESTRATION.md:69-77`), the `reopen` verb's mandatory-reasoning gate
(`blackboard.py:470-517`, P-023), `state.json evolution.{pending_proposals,accepted_mutations}`
as a 30-deep informal precedent ledger (already has one integrity gap: P-023 applied but
unregistered, `state.json:791`), P-number prose citations scattered through
`ORCHESTRATION.md`/task notes, and `recontext.py`'s append-only cited-evidence pattern as the
nearest CLI-wrapper template. Five open questions need a human before the planner locks a
schema: decision granularity, retrofit-vs-forward-only scope for the ~30 P-numbers, what
identifies a "session," how authority level maps onto role/engine/tier, and whether legal
research proceeds on general knowledge or waits for supplied sources. Full brief:
`.harness/context-brief-precedent-layer.md`.
