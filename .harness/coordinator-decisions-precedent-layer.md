# Coordinator Decision Memo — Precedent Layer Epic

Author: coordinator (main session, Fable 5). Date: 2026-08-10.
Input: `docs/civilizational-roadmap-brief.md` (founding brief, Part II build target) and
`.harness/context-brief-precedent-layer.md` (context-scout, §6 ranked open questions).
Status: these are epic-scoped coordinator decisions, all reversible and additive. They are
presented to the operator for ratification at the epic join; any of them may be overturned
there with recorded reasoning — which is, fittingly, the mechanism this epic builds.

All decisions below use the U2 note taxonomy so the next evolution audit can grep them.

---

## D1. Granularity: what earns precedent status

DECISION: Precedent status is an explicit act of publication, never automatic promotion.
`DECISION:` notes on tasks remain the raw material; the registry holds only records
deliberately published to it (by an author at handoff, or by a verifier at verdict).
Rationale: the brief's mechanism 1 states "Not every recorded decision binds." Auto-promoting
every note floods the registry, invites the ossification failure mode (research item 7), and
makes conflict detection noisy to the point of being ignored.

TRADEOFF: some binding-worthy decisions will go unpublished (under-capture) in exchange for
a registry where every entry was meant to be there (precision over recall). The evolution
audit can chase under-capture; nothing can un-noise a polluted registry.

Provisional sub-decision, subject to research item 2 (the ratio identification problem):
the *author declares the ratio at write time* (structural resolution), because agent
societies lack a standing interpretive court and structural declaration is mechanically
checkable. The research phase may overturn this with evidence; if it does, the overruling
is recorded per this epic's own protocol.

## D2. Retrofit of existing P-numbers

DECISION: forward-only as the rule, plus a seed migration of 3-5 exemplar precedents to
validate the schema against reality rather than against imagination. Seed candidates:
P-023 (reopen verb — chosen because the scout found it MISSING from
`state.json accepted_mutations` while applied in code: the live integrity gap this layer
exists to catch), P-025 (test-discovery precision), P-026 (verbatim promotion), and F6
(verifier rotation). Full retrofit of all ~30 P-numbers becomes a follow-on task, gated on
the schema surviving adversarial verification.

## D3. What "session" means for citation

DECISION: citations anchor to identifiers that are already durable and engine-agnostic:
task IDs (T-xxx), agent identity, harness generation, and `events.jsonl` timestamps.
Precedent records receive their own stable IDs (PR-NNN) issued by the registry CLI at
publication; PR-NNN is the citable unit across sessions. The brief's "session 40 citable in
session 200" is satisfied by PR-IDs without inventing session infrastructure.
The Claude hook `session_id` is explicitly rejected as an anchor: ephemeral, single-engine.

## D4. Authority levels (binding vs persuasive, mechanically grounded)

DECISION: authority maps to the existing ontology as four descending tiers, each defined by
a mechanically observable fact — consistent with the "replay, don't trust" invariant:

| Tier | Name | Observable fact | Binding force |
|---|---|---|---|
| 1 | operator | human gate fired / operator directive recorded | Binding on everyone; only the operator overturns |
| 2 | constitutional | NLAH mutation accepted via the §5A loop + human gate | Binding on all agents; overruling requires the same §5A path |
| 3 | verdicted | producer != approver verdict exists on the issuing task | Binding within declared scope; overruling requires a new verdicted decision citing it |
| 4 | single-agent | a DECISION: note that never passed a verifier | Persuasive only, never binding |

This gives the brief's binding/persuasive distinction teeth without inventing new authority:
bindingness is a function of *how much adversarial process a decision survived*, which the
substrate already records.

## D5. Placement

DECISION: core substrate, not a `projects/` sandbox — the layer integrates directly with
handoff mechanics (scout §2, placement inference confirmed). Registry: `.harness/precedents/`
(one JSON per precedent, mirroring `.harness/tasks/`). CLI: `.harness/bin/precedent.py`
(stdlib-only, Python 3.9-compatible, atomic guarded writes via `harness_common`). Contract
doc: `PRECEDENT.md` at repo root, mirroring `ORCHESTRATION.md`'s role. Tests:
`.harness/tests/test_precedent.py` under the `unittest discover` convention
(`python3 -m unittest discover -s .harness/tests -p 'test_*.py'`).

## D6. Conflict detection: pass, not gate

DECISION: on-demand CLI pass (`precedent.py conflicts`), modeled on `lock.py sweep` /
`blackboard.py expire-claims` — engine parity is the invariant; hooks are Claude-side sugar.
TRADEOFF: a pass can be forgotten where a gate cannot; accepted for v0 because a
false-positive gate trains agents to route around the registry, which is fatal to the layer
(forum shopping, research item 7). Promotion to a gate is a candidate follow-on once the
pass demonstrates precision on real precedents.

## D7. The legal-research corpus problem

DECISION: the scout is right that the local corpus has zero legal sources and the local
bench has no web access — but the coordinator session does (WebSearch/WebFetch are local
environment tools; the no-external-LLM rule concerns model APIs, not retrieval). The
research fan-out therefore runs with web-capable research agents; every output lands in
`docs/precedent-research/` with source citations and every claim tagged
ESTABLISHED / ANALOGY / SPECULATION per Part V principle 5. The bench remains web-free.

## D8. Scope boundary held

DECISION: Part III (political economy) produces exactly one research artifact — a survey
identifying which precedent-layer primitives the future market layer presupposes — and no
code. Part IV is untouched. Part VI's standing monitoring duty becomes a standing
blackboard task with quarterly cadence recorded in its description.

OPEN-QUESTION: D1 granularity, D2 seed selection, and D4 tier boundaries are coordinator
judgment, not operator-ratified; the epic join must present all three to the operator with
this memo as the citation.
