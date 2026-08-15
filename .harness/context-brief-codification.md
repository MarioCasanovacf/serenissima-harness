# Context Brief: THE CONSTITUTIONAL CODIFICATION

Author: context-scout. Date: 2026-08-13 (repo `currentDate`; note the harness's own clock last
touched `.harness/blackboard.json` 2026-08-14T04:44:03Z — a session-clock/file-mtime skew worth
flagging to whoever plans off this brief, not resolved here).
Mandate: operator ruling 9, 2026-08-13 — *"Sí, y no lo limitaría a 30-P. Hay que ser más
ambiciosos, es una constitución."* Retrofit the full normative corpus (not merely the ~30
P-numbers) into `.harness/precedents/`, PR-NNN records, schema v2.
Scope of this document: retrieval + interrogation only. No source edited, no task claimed, no
DAG designed. Written for `orchestration-planner` to consume.

---

## 0. Goal restated

The operator wants every standing rule that currently binds agents — wherever it lives — pulled
into the precedent registry as PR-NNN records, at the correct authority tier, so the registry
stops being "the precedent layer plus 34 test-schema records" and becomes the actual
constitution: one system of record for what binds, at what strength, with what evidence. The
operator explicitly rejects scoping this to the ~30 P-numbers alone (that boundary was this
project's own prior self-imposed limit, not the operator's) and explicitly invokes the word
"constitution," which this repo already uses as a term of art (`INTERPRETIVE-CODE.md:18`
"constitutional-tier"; `PRECEDENT.md` tier 2 "constitutional"). Before any task graph exists,
this brief inventories what there is to codify, maps where codifying it could go wrong, and
separates what the operator actually decided from what remains for the planner to ask about.

**Load-bearing prior fact, found during retrieval, that reframes the whole mandate**: this is
not a green-field codification. A prior epic already ran exactly this question at small scale
and left a written, reasoned boundary and a named unblocking condition for exactly the expansion
the operator is now ordering. See §2.0 below — read it before anything else in this brief.

---

## 1. Census of the normative corpus

### 1.0 What "the registry" already contains (baseline, not the target)

34 published records, `.harness/precedents/PR-001.json`..`PR-034.json` (`python3
.harness/bin/precedent.py list`, run live). All are `confirmation_status: unconfirmed` (no
record's `scope_conditions` has been confirmed by a distinct-identity verifier yet —
`PRECEDENT.md:191-193` — so every one of the 34 binds on `ratio` but its declared scope is still
only persuasive strength, `PRECEDENT.md §6`). Tier distribution: 4 at tier 3 (PR-001, PR-004,
PR-012, PR-013), 2 at tier 2 (PR-002, PR-003), 28 at tier 1. `precedent.py conflicts` reports
exactly **one** live finding today: detector 5 (dangling citation), PR-001 citing the token
`P-023`, which resolves nowhere (`python3 .harness/bin/precedent.py conflicts` → exit 3, "1
conflict finding(s) across 34 record(s)", run live). That one finding is old, known, and
deliberately left alarming — see §2.3.

Four of the 34 already ARE the codification the operator is now asking for, at small scale, done
by a prior epic (T-340..T-349): **PR-001** = P-023 (terminal-state reopen, `ORCHESTRATION.md:58`),
**PR-002** = P-025 (test-discovery precision, `ORCHESTRATION.md:82-90`), **PR-003** = P-026
(verbatim promotion, `ORCHESTRATION.md:211-218`), **PR-004** = F6 (verifier rotation,
`ORCHESTRATION.md:119-126`). These four were the explicit "seed migration" `.harness/
coordinator-decisions-precedent-layer.md:35-41` (decision D2) authorized — not a random sample,
a chosen exemplar set. The new epic's job is essentially "D2's follow-on," at a much larger
declared scope (§2.0).

### 1.1 P-numbers — `state.json evolution.accepted_mutations` (27 entries) + `pending_proposals` (2)

Read live (`python3 -c "..." .harness/state.json`). Full ledger, 27 accepted IDs: P-001..P-022,
P-024, P-025, P-026, P-029, P-030 (`.harness/state.json:586`, array start). **P-023, P-027,
P-028 are the numbering gaps** the mandate names — but they are NOT the same kind of gap, and
conflating them is a scope-inflating mistake the census corrects:

| ID | State in `state.json` | What it actually is | D4 tier if codified |
|---|---|---|---|
| P-023 | **Absent everywhere** — no `accepted_mutations` entry, no `pending_proposals` entry | Applied in code (`blackboard.py:470`) and in prose (`ORCHESTRATION.md:58`) but never entered the ledger at all. Genuine gap. | Currently tier 3 (PR-001, verdicted on T-302) — NOT yet tier 2, because tier 2 requires the §5A-loop ledger entry this gap is missing (`PRECEDENT.md:174-178`) |
| P-027 | `pending_proposals`, `status: "rejected-no-adoption"` (`.harness/state.json:552`) | Gen-5 intake candidate (Shepherd checkpoint/revert pattern), evaluated and **declined** by evolution-analyst, verdict DESCARTAR (`.harness/logs/audit_gen5.md:12`) | None — a rejected proposal produces no binding ratio. At most a tier-4-shaped "considered and declined" record, and a low-priority one |
| P-028 | `pending_proposals`, `status: "rejected-no-adoption"` (`.harness/state.json:552`) | Gen-5 intake candidate (Opik/Ollie auto-regression pattern) — declined, same audit, same verdict, LLM half additionally disqualified by the no-external-LLM rule (`audit_gen5.md:12-14`, `.harness/logs/audit_gen5.md §3`) | Same as P-027 |

**Only P-023 is a ledger gap in the sense the operator's framing implies.** P-027/P-028 are a
*complete and correct* historical record already — they were considered and rejected, and
`state.json` says so. Treating all three as equivalent "gaps to backfill" would be a scope error
a planner should not carry forward. This correction is itself evidence for §3's grill.

**P-023's own escalation trail — read this before touching it.** PR-001's own `dicta`
(`.harness/precedents/PR-001.json`) already documents the gap in full, including the exact
resolution path (5A loop + human gate, no unilateral backfill), and forwarded it as an
`OPEN-QUESTION` at the T-348 epic join. It has now been escalated **three separate times** across
three epics and left open every time: T-348 → T-362 → T-365 (operator ruling ESCA-01,
2026-08-12, quoted in `.harness/tasks/T-365.json`: *"documentese y respetese... el camino
constitucional se respeta: no hay backfill unilateral, nunca"*). The most recent join memo names
this explicitly: *"Tercer epic con la misma alarma sonando"* ("third epic with the same alarm
sounding") — `docs/precedent-research/ratification-memo-addendum-ii.md:438`. **T-365 currently
owns the P-023 backfill path.** This codification epic must not touch `state.json
evolution.accepted_mutations`, must not attempt the P-023 backfill itself, and must not silence
`conflicts`' PR-001 finding — all three are named, repeated, standing prohibitions
(`PRECEDENT.md:984-986`, PR-001's own dicta, ESCA-01).

**The other 24 P-numbers** (P-001..P-022 minus P-023, plus P-024..P-026, P-029, P-030 minus the
4 already seeded as PR-001..004) split into two classes on inspection of the `summary`/`target`
fields (`.harness/state.json:586-1020`, read live, all 27 rows):

- **Standing process/behavioral rules still binding agents today**, with a `target` that is a
  contract doc (`ORCHESTRATION.md`, `claude.md`, `gemini.md`, an agent-definition `.md`) rather
  than only code: P-001 (NLAH cross-references), P-003 (hook scoping, restated `AGENTS.md:86`),
  P-009 (mechanical producer≠approver, code-level but IS the invariant), P-010 (de-Fable
  wording), P-014/P-015/P-016/P-017 (U1/U3/U2/U4 — see §1.2), P-018 (dead-reference removal,
  human-gated), P-019 (session authorization), P-020 (verifier cost tier), P-024 (proportional
  verification), P-029 (protected-paths guardrail), P-030 (frontier budget). These have
  extractable, relatively **clean** ratios — several already read as prose rules in
  `ORCHESTRATION.md` almost verbatim.
- **Point bug-fixes with no separable standing rule beyond "the code was wrong, now it's
  right"**: P-002, P-005, P-006, P-007, P-008, P-011, P-012, P-013, P-021, P-022 — all
  `gate: "code-level"`, all `target` a single `.py` file, all diagnosing one specific defect
  (e.g. P-005 "`lock_is_expired` floors one side, not both"; P-007 "argparse `store` silently
  drops repeated `--artifact` flags"). These have **entangled** ratios: the normative content
  (what must an agent do?) is inseparable from the historical bug it fixed, and forcing a
  "ratio" out of it risks manufacturing a rule that never existed as a rule — it existed as a
  patch. Codifying these as PR records is possible but low-value unless the census also states
  what generalizable rule, if any, each licenses (e.g. P-005/P-006/P-008's shared theme —
  "the observability layer must not silently lose events" — could ratio into one record rather
  than three).

### 1.2 F-rules and U-rules — NOT a single canonical home

The mandate's framing ("F1 single-owner, F6 verifier rotation... U2 note taxonomy, U3 blindspot
interview, U4 pre-gate ritual") treats these as a peer set. The census finds **three different
homes**, which is itself the first codification hazard:

| Label | Origin (the actual first-class home) | Restated in | Ever became a standing ORCHESTRATION.md rule? | Codified in registry? |
|---|---|---|---|---|
| F1 (single-owner bootstrap files) | `.harness/logs/audit_gen3.md:148` (finding, cites `state.json:347`) | `.harness/plan.md:137,215,517,533,680-681` (planner convention, repeatedly) | **No** — never generalized past the one fix it produced (P-013, mdtoc-specific) | No |
| F6 (verifier rotation) | `.harness/logs/audit_gen3.md:153` | `ORCHESTRATION.md:119-126` (P-016) | Yes | **Yes — PR-004** |
| U1 (Unknowns section) | `.harness/logs/audit_gen3.md:157` (as part of P-014/015/016 bundle) | `.claude/agents/orchestration-planner.md:36` step 6, ONLY | No — lives only in the planner's own agent-definition file, never in ORCHESTRATION.md | No |
| U2 (note taxonomy) | `.harness/logs/audit_gen3.md:157` | `ORCHESTRATION.md:69-77` (P-017) | Yes | No |
| U3 (blindspot interview) | `.harness/logs/audit_gen3.md:158` | `.claude/agents/orchestration-planner.md:27` step 5; `AGENTS.md:27`, `.claude/agents/context-scout.md:34` (as a downstream feed) | No — same as U1, agent-file only | No |
| U4 (pre-gate ritual/explainer) | `.harness/logs/audit_gen3.md:159` | `ORCHESTRATION.md:105-109` (P-016) | Yes | No |

**The F/U labels are not a standing taxonomy at all** — they are `audit_gen3.md`'s own internal
finding numbers (`state.json evolution.next_audit_inputs`, an array of 6 free-text strings,
`.harness/state.json` — read live, entries 0-5), carried into prose by convention because
`ORCHESTRATION.md` and `plan.md` cite them for traceability. **A citation-drift finding on top of
this**: `ORCHESTRATION.md:80` and `audit_gen3.md`'s own findings cite `state.json:352/356/358`
for F6/U2/U4 — those exact line numbers, checked live against the current 1093-line
`state.json`, no longer point at that content (the file has grown substantially across four
generations); this is the exact "volatile line citations" nit `state.json`'s own gen-5 backlog
entry names (`.harness/state.json evolution.next_audit_inputs[0]`: *"doc-only nits (volatile
line citations, ... F6 prose)"*). Any PR record minted for F6/U2/U4 that cites a `state.json:NNN`
line anchor will go stale the same way — `PRECEDENT.md`'s own citation grammar has a `path:lines`
token for exactly this reason but also warns line-numbered citations into a still-revising
document are "exactly the kind of citation that goes stale first" (`INTERPRETIVE-CODE.md:48-50`,
about `PRECEDENT.md`/`ORCHESTRATION.md` specifically, same logic applies to `state.json`).

### 1.3 Invariants table — `ORCHESTRATION.md` §3, lines 92-103

8 rows, one per invariant: single guarded index, cascade gate, leases+TTLs, producer≠approver,
replay-don't-trust, human gates, bounded everything, hook-fed logging. None of these 8 is
currently a PR record. Each maps cleanly to a D4 tier-2 candidate (constitutional — each was
either bootstrap-seeded generation 0 or accepted via the §5A loop), but several are compound:
"producer ≠ approver" alone is *also* separately stated in `claude.md` (this file, §2A, §4B),
`gemini.md:75`, `AGENTS.md:56` (`substrate-worker` hard limit), `.harness/README.md:56`, and
`PRECEDENT.md`'s own D4 tier-3 definition (`.harness/coordinator-decisions-precedent-layer.md:61`)
— **six independent homes for one rule**, the single worst double/triple/hextuple-homing
instance found in this census (detailed in §2.1).

### 1.4 Topology patterns and engine-routing rules — `ORCHESTRATION.md` §5, §4

Three named topology patterns (fan-out/join, tournament/consensus, market-lite dispatch,
`ORCHESTRATION.md:204-221`) plus the engine-routing rules (`:168-202`: claude for judgment,
gemini for long-context/math via the prompt-bridge or native adapter, codex as a native
adapter, hard no-outsourcing-reasoning boundary between engines). None codified. Ratios read
fairly clean — each pattern is already a self-contained paragraph — but the engine-routing
section is long (35 lines) and entangled with operational detail (bridge folder naming
convention, `.gemini/settings.json` bounds) that is implementation detail, not a binding norm on
an agent's behavior; a codifier would need to separate the two.

### 1.5 `claude.md`/`gemini.md` constitutional-character constraints

Both files (`/Users/.../CLAUDE.md`, `/Users/.../gemini.md`, repo root) carry norms that are
constitutional in character but embedded in per-engine operational prose, never extracted as
standalone rules:
- No-external-LLM/API rule — stated independently in `CLAUDE.md` §3 ("STRICT TOOL CONSTRAINT"),
  `gemini.md` §3 (identical warning box), `ORCHESTRATION.md:180-183` (extended to local model
  subprocesses too, "the no-external-LLM rule extends to local model subprocesses"), and
  `AGENTS.md` nowhere directly but implied by the Codex section. **Triple-homed**, and
  `ORCHESTRATION.md`'s version is *wider* than either NLAH's (subprocess extension) — a genuine
  scope divergence between homes, not just duplication (§2.1).
- Human gates — `CLAUDE.md` doesn't enumerate them itself; it points at `state.json human_gates`
  implicitly via the runtime-layer section. The actual enumeration lives ONLY in
  `state.json human_gates.require_human_approval_for` (4 items, `.harness/state.json:20`),
  restated narratively in `ORCHESTRATION.md:101` (invariants table row) and `AGENTS.md`
  (implicitly, via the hooks table). **Not one of these 4 gate items has ever been a PR
  record.**
- Bounded-everything (`state.json limits`, `.harness/state.json:11`: `max_steps_per_task`,
  `max_seconds_per_command`, `max_retries_per_failure`, `lock_ttl_seconds_default`,
  `claim_lease_seconds_default`, `max_parallel_workers`) — six numeric constants, referenced by
  `ORCHESTRATION.md:102` as a single invariant row but never individually codified. A codifier
  choosing "one PR record per invariant row" vs "one PR record per constant" is a real,
  consequential design choice with no existing precedent to follow (none of PR-001..034 codifies
  a bare numeric limit).
- Role definitions (thinker/worker/verifier, `CLAUDE.md` §2B) — restated in `ORCHESTRATION.md:113-114`
  and again per-agent in `AGENTS.md:20-28`'s table (mandate/hard-limits columns). Triple-homed.
- §5A governance loop itself (`CLAUDE.md` §5, `ORCHESTRATION.md:223-229`) — this is the loop that
  *would perform* any future codification of `claude.md`/`gemini.md` text; codifying it into the
  registry that the loop's own human-gate mechanism does not currently cover (see §3, question 3)
  is close to self-reference and worth flagging rather than treating as routine.

### 1.6 `state.json` structures with normative force

| Structure | Location | Normative content | Codified? |
|---|---|---|---|
| `human_gates.require_human_approval_for` | `.harness/state.json:20` | 4 items: push/publish, deletion outside scratch, first webhook activation, NLAH mutation | No |
| `limits.*` | `.harness/state.json:11` | 6 numeric bounds (anti-agentic-trap) | No |
| `cost_policy.frontier_budget` + `.rules` (7 numbered rules) | `.harness/state.json:1021` | Frontier-tier token-share band, coordinator-delegation duty, verifier-tier default, proportional verification, spawn consolidation, session hygiene, model-floor-by-verifiability | Rule 1 and rule 4 partially restated as prose in `ORCHESTRATION.md:128-145` (P-024, P-030) — the OTHER five rules (2, 3, 5, 6, 7) exist ONLY in `state.json cost_policy.rules`, never in `ORCHESTRATION.md` or any NLAH, and never in the registry |
| `protected_paths` | `.harness/state.json:1051` | Currently `[".harness/precedents", ".harness/precedents/*"]` — i.e., **the registry itself is the one path class already protected against destructive Bash commands** (`guard_paths.py:1-25`, P-029) | N/A (mechanism, not a rule to codify — but ironic/relevant: codifying MORE material into the one directory already under this specific guard) |
| `evolution.accepted_mutations`/`pending_proposals` | `.harness/state.json:586,552` | The P-number ledger itself — see §1.1 | 4 of 27 (§1.0) |
| `agents.registry`/`agents.reputation` | `.harness/state.json` (`agents` top key) | Capability contracts, tier assignments per agent — cited as a `token` type in `PRECEDENT.md`'s own citation grammar (`agent:name`, `PRECEDENT.md:238`) | No |

### 1.7 Double-homed norms in AGENTS.md / PRECEDENT.md / INTERPRETIVE-CODE.md (the mandate's item g)

- `AGENTS.md` restates, rather than merely indexes: producer≠approver (`:56` substrate-worker
  hard limit, `:34` intent-routing table), hook scoping/P-003 (`:86`), the §5A loop as "the
  evolution loop" (`:96-99` loops table) — `AGENTS.md:9-11` itself claims to be "the index, not
  the law," but the table format duplicates prose that already exists in `ORCHESTRATION.md`
  and `CLAUDE.md`. Low risk (declared non-canonical by its own header) but still double-homed
  text that could drift.
- `PRECEDENT.md` restates D4 (`§3`, lines 167-199) from `.harness/coordinator-decisions-
  precedent-layer.md` (`D4`, lines 52-66) — acknowledged restatement, not hidden: `PRECEDENT.md`
  is the "doctrine" successor document, the coordinator-decisions memo is the original ratified
  decision. Two texts, both live, is exactly the double-homing shape the mandate's item (g)
  warns about, even though the intent (memo → doctrine promotion) is legitimate.
- `INTERPRETIVE-CODE.md` explicitly does NOT restate `PRECEDENT.md`/`ORCHESTRATION.md` content
  (`:51-56`, citing the 2.3-point regression finding from `agentic_harness_engineering.pdf` Table
  3 as the reason) — this is the one file in the corpus that names double-homing as a measured,
  costed defect and designs around it. **Any codification plan should read this file's own
  citation discipline as the model to imitate**, not merely as one more document to retrofit.
- `.harness/README.md:56` also independently restates producer≠approver — a fourth/fifth home
  for that one rule (see §2.1 tally).

---

## 2. Codification hazards

### 2.0 The governing prior decision — read first

`.harness/coordinator-decisions-precedent-layer.md` decision **D2** (lines 33-41) already
answered a narrower version of exactly this question, in writing, ratified at the prior epic's
join: *"forward-only as the rule, plus a seed migration of 3-5 exemplar precedents... **Full
retrofit of all ~30 P-numbers becomes a follow-on task, gated on the schema surviving
adversarial verification.**"* `PRECEDENT.md` restates this as a live boundary not just once but
**twice across two schema revisions** — v0 (`PRECEDENT.md:977-979`, "No full retrofit... a full
retrofit is a follow-on gated on the schema surviving adversarial verification") and v1
(`PRECEDENT.md:1047`, section 14.1, explicitly re-checked and left standing: *"No NLAH mutation,
no `state.json` write, no `ORCHESTRATION.md` edit, no full P-number retrofit — all four restated
from the bullets above and from v0's own list; schema v2 does not touch any of them"*).

**This means the operator's new ruling is not a fresh idea — it is pulling the trigger on a
gate this project itself set up and has left closed through two full schema generations (v0,
v1/addendum, v2/addendum II).** The gate condition was "the schema surviving adversarial
verification." Evidence the condition may now be met: 339 tests passing across
`test_precedent*.py` + `test_reputation*.py` (`.harness/tasks/T-365.json` notes quoting a T-375
replay), two full addendum cycles each with an operator ratification memo
(`docs/precedent-research/ratification-memo.md`, `ratification-memo-addendum-ii.md`), and 34
live records surviving `conflicts`/`cite --all` sweeps with only the one known, intentional
finding (§1.0). **Whether that evidence is sufficient to declare the D2 gate satisfied is a
planner/operator judgment, not a scout's to make** — but the planner should open with this
framing rather than treating the epic as scope-free: D2's boundary was reversible and
foreseen its own reversal condition; the honest move is to name the gate and assess it, not
silently supersede it.

**D2's scope was explicitly named "coordinator judgment, not operator-ratified"**
(`.harness/coordinator-decisions-precedent-layer.md:103-105`, D2's own OPEN-QUESTION), which is
exactly why the operator ratifying an expansion of it now is procedurally clean — this is the
operator doing the thing D2 itself said only the operator could do.

### 2.1 Double/triple/hextuple-homing tally (worst offenders)

| Norm | Homes found | Count |
|---|---|---|
| Producer ≠ approver | `CLAUDE.md` §2A/§4B, `gemini.md:75`, `ORCHESTRATION.md:99,113-117`, `AGENTS.md:34,56`, `.harness/README.md:56`, `PRECEDENT.md` D4 tier-3 restatement | 6 |
| No-external-LLM/API | `CLAUDE.md` §3, `gemini.md` §3, `ORCHESTRATION.md:180-183` (WIDER scope — extends to subprocesses) | 3, with a real scope divergence between them |
| F6 (verifier rotation) | `audit_gen3.md:153` (origin), `ORCHESTRATION.md:119-126` (P-016), `PR-004.json` (registry) | 3 |
| U2/U4 | `audit_gen3.md` (origin), `ORCHESTRATION.md` (P-016/P-017) | 2 each, not yet 3 (no PR record) |
| Roles (thinker/worker/verifier) | `CLAUDE.md` §2B, `ORCHESTRATION.md:113-114`, `AGENTS.md` table | 3 |
| §5A governance loop | `CLAUDE.md` §5, `ORCHESTRATION.md:223-229`, `AGENTS.md:96-99` | 3 |

**Codifying a norm that already has 3-6 live homes raises the question of which home becomes
the canonical citation target inside the new PR record's `sources`/`cites` fields** — if the
record cites all of them, and one drifts (as F6's `state.json:352` line-anchor already has,
§1.2), the record inherits a stale citation the day it publishes. This is the single most
concrete mechanical risk this census surfaces.

### 2.2 Ratio-cleanliness distribution

Roughly (this census's own read, not a mechanical count): **~14 of the 27 accepted P-numbers**
have clean, one-paragraph-extractable ratios (the standing-rule class, §1.1); **~10** are
entangled bug-fix records whose "ratio" would have to be manufactured rather than extracted; the
invariants table, topology patterns, and F6/U2/U4 read cleanly; the `cost_policy` rules and
`limits`/`human_gates` numeric/list structures are clean as *facts* but would need a genuine
ratio-authoring act to become anything more than a restated list (no adversarial process ever
produced a "ratio" for "max_steps_per_task = 50" — it is a configured constant, not a decision
with reasoning attached, which is exactly the D1 distinction `.harness/coordinator-decisions-
precedent-layer.md:14-21` draws: "not every recorded decision binds," and by extension, not
every configured constant is a decision at all).

### 2.3 The AD2-39 prohibition — direct precedent against "close every gap" completionism

Quoted in full (`docs/precedent-research/synthesis-addendum-ii-spec.md:589-597`):

> **AD2-39. The `conflicts` pass gains NO detector for non-compliant historical overrules.**
> Ruled explicitly. Not merely because D6 makes `conflicts` a pass rather than a gate (a pass
> may gain detectors), but on the substance: the only non-compliant historical overrule in the
> registry is PR-009, which AD2-40 GRANDFATHERS, so a detector's entire possible population is a
> set a tier-1 record has already dispositioned, and it would report the same finding on every
> sweep forever. That is the false-positive shape `PRECEDENT.md` §9's own accepted tradeoff
> names as fatal ("a false-positive gate trains agents to route around the registry").
> Prospectively the publish-time refusal makes non-compliance impossible to create, so the
> detector has no future population either. **The five shipped detectors stay five. T-370 must
> not add a sixth.**

**Why this matters for THIS epic, not just for `precedent.py`**: AD2-39's reasoning generalizes
past its literal subject (a sixth conflict detector). The same shape applies to full-corpus
codification: retrofitting *every* historical norm, including ones already correctly resolved
(P-027/P-028's DESCARTAR verdicts, §1.1; PR-009's own grandfathered status, `PRECEDENT.md:1731`,
AD2-40) risks manufacturing new "findings" against material that was already, correctly,
disposed of — the exact false-positive-completionism shape AD2-39 forecloses for one narrow
mechanism. A planner should ask, for each census item, "does codifying this change any live
agent's behavior, or does it just re-litigate something already settled" before minting a
record — not codify by inertia because the item exists.

### 2.4 Tier-evidence honesty for pre-registry material

Every one of the ~50+ items this census found predates the registry (T-340, 2026-08-10/11) by
weeks to over a month (P-001 applied 2026-07-04). `PRECEDENT.md`'s own tier-evidence
requirements (`:174-178`) demand, per tier: tier 1 needs `≥1 event: or T-NNN token`; tier 2 needs
`≥1 P-NNN token`; tier 3 needs `≥1 T-NNN token naming the issuing task`; tier 4 needs `≥1 T-NNN
token naming the note's task`. The honest anchors available for this corpus are exactly the ones
`PRECEDENT.md §5.1`'s citation grammar already enumerates: `T-NNN` (every mutation names an
issuing task or is traceable to one via `applied_note`), `P-NNN` (self-evident for the P-number
class), `event:TS` (`events.jsonl` predates the registry too — 12,736+ lines as of the addendum
II epic, `.harness/blackboard.json:4184` quoting a T-368 note), and `gen:N` (`harness_generation`
is currently 4, `.harness/state.json:3`). **What is NOT honestly available**: a `published_by`
author identity for anything pre-registry in the sense PR records expect (the `agent:name` token
resolves against `agents.registry`/`agents.reputation`, which was itself only backfilled
starting with the reputation-layer work) — this is structurally the same problem AD2-34/AD2-41
already solved once for PR-009 (a `decision:T-NNN#anchor` target has no registry `ratio` and no
`published_by`, `PRECEDENT.md:274-277`, AD2-34) and the same GRANDFATHER-not-RETROFIT answer
(§2.3, AD2-40) is the precedent a planner should reach for by default rather than re-deriving
from scratch for 50 more items.

### 2.5 Conflicts with existing PR records

Beyond the one live `conflicts` finding (PR-001/P-023, already covered), the census found no
NEW conflicts a codification act would introduce mechanically — but two soft tensions worth a
planner's attention:
- PR-004 (F6, tier 3, verdicted T-031/T-032/T-033) and a hypothetical future PR record for "F1"
  (single-owner) would be adjacent audit-finding siblings from the same `audit_gen3.md` source
  with very different codification maturity (one fully generalized and shipped, one never
  generalized past its single fix) — publishing them asymmetrically (F6 already a record, F1
  freshly minted at full generality) risks implying F1 has the same standing as F6 when the
  evidentiary trail does not support that (§1.2).
- PR-030/PR-031 are `void_per_incuriam` duplicates of the same subject (`westphalia-kpi`),
  voided by PR-032/PR-033 — a live example, already in the registry, of exactly the duplicate-
  publication risk a rushed full-corpus codification pass would recreate at scale if the same
  norm gets minted twice by two different agents working the census in parallel. **F1 single-
  owner discipline (the file-ownership sense, not the registry sense) applies to this epic's own
  execution**: the census-to-records mapping should have exactly one owner per norm-to-PR
  assignment before any worker starts publishing, or PR-030/031's failure mode repeats.

---

## 3. Grilling the mandate

### Explicit (operator said this)

1. Not limited to the ~30 P-numbers — "ambitious."
2. It is a constitution, not a precedent registry footnote — the word choice matters and the
   repo already has vocabulary for it (`constitutional-tier`, D4 tier 2 "constitutional").
3. This runs before the planner (context-scout's own protocol, not the operator's words, but
   consistent with how this mandate was dispatched).

### Assumed (not stated, and each one changes the plan's shape)

- That "full normative corpus" means everything this census found (~50+ items across 7
  categories) rather than a narrower "everything with a clean ratio" subset (§2.2).
- That the registry becomes canonical and the prose documents become commentary — the operator
  did not say this; "constitution" is consistent with either reading (a written constitution
  that IS the prose, vs. a case-law registry that INTERPRETS unchanged prose).
- That this is one epic rather than phased by category (P-numbers, then invariants, then
  state.json structures, etc.) — nothing in the ruling specifies pacing.
- That gemini.md enters scope on the same terms as claude.md — the operator's example ("no lo
  limitaría a 30-P") named P-numbers specifically; gemini.md wasn't mentioned either way.
- That the NLAH files themselves (`claude.md`/`gemini.md`) become registry-governed material —
  this is the highest-consequence assumption, because it intersects the one human_gates item
  that already exists for exactly these two files (`.harness/state.json:20`, "mutating claude.md
  or gemini.md"). If codification writes NEW registry records that themselves alter what
  claude.md/gemini.md say, that is arguably an NLAH mutation requiring the same gate — but if
  codification only records EXISTING claude.md/gemini.md text as a citation target (never
  editing the files), it plainly does not.

### Ranked open questions

1. **[HUMAN-ONLY — highest cost of guessing wrong] Does codification make the registry
   canonical, demoting `ORCHESTRATION.md`/`claude.md`/`gemini.md` to commentary, or does the
   prose remain canonical and the registry become a cited mirror?** No repo evidence answers
   this — `PRECEDENT.md`'s own existing doctrine (`.harness/coordinator-decisions-precedent-
   layer.md:70-71`) treats `PRECEDENT.md` as parallel to `ORCHESTRATION.md`, not superior to it,
   but that was decided for the *precedent-layer contract itself*, not for the general question
   of whether case law now outranks the constitution's text. Best-evidence default if forced to
   guess: **mirror, not supersede** — `INTERPRETIVE-CODE.md:19-22` explicitly states its own
   rules are "not yet incorporated into `claude.md` or `gemini.md`: no agent is presently under a
   documented duty to consult it" even though it is itself constitutional-tier, which is the
   closest existing precedent for "constitutional-tier material that does not yet displace the
   original text as the operative source."

2. **[HUMAN-ONLY] One epic or phased?** No default recommended — genuinely open; the census's
   own category boundaries (§1.1-1.7, 7 distinct categories with different maturity/risk
   profiles) are a natural phase boundary if the operator wants one, but nothing compels it.

3. **[HUMAN-ONLY, but flag the D2 gate framing either way — see §2.0] Is the D2 "schema
   surviving adversarial verification" gate satisfied?** Repo-answerable in part: the evidence
   exists (§2.0's citation list) but the judgment call ("is that enough") is exactly the kind of
   call D2 reserved as "coordinator judgment, not operator-ratified" — i.e., this may actually be
   answerable by the coordinator/planner without going back to the operator, since D2 pre-
   authorized that judgment call to be made downstream. Flag, don't silently assume either way.

4. **[HUMAN-ONLY, highest structural stakes] Do the NLAH files (`claude.md`/`gemini.md`)
   themselves become registry-governed?** See "Assumed" above. Best-evidence default: **no, not
   in this epic** — `PRECEDENT.md §14`/`§14.1` (both revisions) explicitly and repeatedly name
   "no NLAH mutation" as an out-of-scope boundary for the precedent layer generally, and nothing
   in the operator's ruling mentions the NLAH files. If the operator wants NLAH files brought in,
   that should be a named, explicit widening of this specific boundary, not an inferred
   consequence of "be ambitious."

5. **[Repo-answerable, default supplied] Does gemini.md content enter?** Given `ORCHESTRATION.md`
   is explicitly the cross-engine document and both NLAHs already share the same producer≠approver/
   no-external-LLM norms with only prose-level differences (§2.1), the clean default is: **yes,
   on the same terms as claude.md**, since most of gemini.md's constitutional-character content
   (§1.5) is the SAME norm as claude.md's, not a distinct one — codifying only claude.md's copy
   would immediately create a new double-homing gap between the two NLAHs' now-divergent
   treatment.

6. **[Repo-answerable] What about P-027/P-028?** Answered by this census, not open: they are
   NOT ledger gaps (§1.1). If the planner wants them in the registry at all, the honest record
   is a DESCARTAR/rejected-proposal record (tier 4 at most, informational), never a "backfill" —
   using the word "backfill" for P-027/P-028 the way it correctly applies to P-023 would
   misdescribe what happened.

7. **[Repo-answerable, procedural] Who runs this — coordinator, or a fresh planner dispatch, and
   does the existing precedent-layer worker/verifier rotation cast (the identities that produced
   PR-001..034) get reused or does F6 require fresh rotation?** F6 (`ORCHESTRATION.md:119-126`)
   requires a reviewer distinct from every PRODUCER in *this* epic specifically — reusing an
   identity that verified a DIFFERENT prior epic's records is fine; reusing one that both
   produces and verifies inside this new epic is the exact monoculture F6 forecloses. No
   operator input needed; this is a planner-level dispatch design question this brief flags so
   it isn't missed under time pressure.

---

## Files/paths referenced (absolute)

- `<workspace>/ORCHESTRATION.md`
- `<workspace>/CLAUDE.md`
- `<workspace>/gemini.md`
- `<workspace>/AGENTS.md`
- `<workspace>/PRECEDENT.md`
- `<workspace>/INTERPRETIVE-CODE.md`
- `<workspace>/.harness/state.json`
- `<workspace>/.harness/precedents/` (PR-001..PR-034,
  `README.md`)
- `<workspace>/.harness/coordinator-decisions-precedent-layer.md`
- `<workspace>/.harness/logs/audit_gen3.md`
- `<workspace>/.harness/logs/audit_gen5.md`
- `<workspace>/.harness/tasks/T-365.json`
- `<workspace>/docs/precedent-research/synthesis-addendum-ii-spec.md`
- `<workspace>/docs/precedent-research/ratification-memo-addendum-ii.md`
- `<workspace>/.claude/agents/orchestration-planner.md`
- `<workspace>/.harness/bin/precedent.py`
- `<workspace>/.harness/bin/guard_paths.py`
