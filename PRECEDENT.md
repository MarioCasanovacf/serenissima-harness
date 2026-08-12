# PRECEDENT.md — The Precedent-Layer Contract (v1)

> **Summary**: a precedent is not a note. `.harness/precedents/PR-NNN.json` (D5) holds records
> that a CLI mints, mutates, and resolves — never a hand-edited file. Four authority tiers key
> bindingness to a mechanically observable fact, never to rank, model tier, or prose (D4). A
> record's `ratio` is author-declared and binds at the record's tier the moment it publishes;
> its `scope_conditions` are author-declared too, but do **not** bind until a distinct-identity
> verifier confirms them — the same producer≠approver discipline this harness already runs on
> tasks (`ORCHESTRATION.md:99`), applied here to a new object. Overruling is the `reopen` verb's
> mandatory-reasoning pattern extended to precedents, not a second resurrection mechanism.
> Conflict detection is an on-demand pass, not a gate. Nothing here is a duty yet.

> **STATUS.** PRECEDENT.md v0 is a prototype contract. It is **not yet incorporated into
> `claude.md` or `gemini.md`** — no agent is under a documented duty to cite it, consult it
> before deciding, or publish to it before handing off. Incorporating such a duty into either
> NLAH would itself be an NLAH mutation: the §5A loop plus the human gate that already covers
> "mutating `claude.md` or `gemini.md`" (`ORCHESTRATION.md:225-229`; `.harness/state.json:20-28`
> `human_gates.require_human_approval_for`, specifically the entry at `.harness/state.json:26`). A worker
> task cannot do that, and this document does not claim to have done it.

This document is the source-of-truth *explanation* for the schema and CLI that
`docs/precedent-research/synthesis-design-requirements.md` (T-339) fixed and
`.harness/bin/precedent.py` (T-340) implements — mirroring the role `ORCHESTRATION.md` plays
for the task/handoff lifecycle, but for the precedent-record lifecycle (coordinator decision
D5). Where this document and the shipped CLI disagree, the CLI's actual `--help` output is
correct and this document has drifted (T-346's adversarial replay exists to catch that). The
v0 revision (T-345) folded in failure modes, anti-evasion detection signals, adjudication-record
detail, and the standing steelman caution against the whole layer — sections 10-13 below,
sourced from `docs/precedent-research/synthesis-refinements.md` (T-344) and reconciled against
the shipped CLI exactly as section 16 records.

**v1 (this revision, T-357) states the doctrine an external legal-theory input fixes and the
coordinator's amendment memo adopts: the hybrid ratio model with its corrective path (section
17), the three operations kept structurally separate (section 18), graded force distinguished
from issuance tier (section 19), validity conditions distinct from scope conditions (section
19.3), the fact-re-description constraint on distinguishing (section 20), and the realist
frame (section 21).** The external input is Mario Armando Sandoval Islas, "Distinciones entre
la interpretación de disposiciones legislativas y la interpretación de precedentes," *Problema.
Anuario de Filosofía y Teoría del Derecho* 20 (IIJ-UNAM, 2026), **DOI
`10.22201/iij.24487937e.2026.20.20316`** — a paper working within the Genoese school of legal
realism (Tarello, Guastini, Chiassoni). This document cites it as `doi:<the-DOI>#<section>`
(the citation grammar's own external-identifier token, section 5.1) plus the coordinator
decision letter (A1-A9, `.harness/coordinator-decisions-addendum.md`) that adopted it — **never
by the local `docs/` path**: `docs/` is gitignored (`.gitignore:33`, verified live), so a path
citation would dangle for every reader who clones this tracked repository. Schema v2 and CLI v2
(the four new fields, the `migrate`/`stale` verbs, graded force) are `.harness/bin/precedent.py`
work this document does not implement or claim shipped — where this document states a v2 CLI
surface, it cites the requirement id in `docs/precedent-research/synthesis-v1-requirements.md`
(T-352) that fixed it, exactly as this paragraph's own discipline requires, and leaves the
shipped-vs-documented reconciliation to the epic's own adversarial replay (T-360), the same
posture section 16 already takes for v0.

**Why this exists, with a worked example rather than a hypothetical one.** The harness already
cites precedent informally, in prose, with no resolver: `ORCHESTRATION.md:58` cites `P-023`
(the `reopen` verb) as settled, and the verb ships in code at `.harness/bin/blackboard.py:470`
— but `P-023` has **no entry at all** in `state.json evolution.accepted_mutations` (verified:
the array at that JSON path runs P-001 through P-030 with P-023, P-027, P-028 absent), a gap
`state.json`'s own `evolution.next_audit_inputs[0]` entry already flags as latent backlog —
quoted, not line-cited, because that array is append-only and this exact quote's line number
moved three times (841 → 846 → 851) over the course of this document's own review cycle, which
is the volatility that entry's own text separately names as a known nit ("gen-5 backlog: P-023
terminal-state --reopen rule (LOW, latent); doc-only nits (volatile line citations...)"). A
prose citation with no resolvable target cannot surface
that kind of drift; a citation grammar that distinguishes resolvable from dangling (section 5)
can. That is the whole layer's job in one sentence.

## 1. Headline rules and the risks each one neutralizes

| Rule | Risk neutralized if the rule were absent |
|---|---|
| `ratio` is required, non-empty, author-declared, and binds at the record's tier on publication — no confirmation step | An empty or hand-waved rationale circulating as "binding," with nothing on record to audit later |
| `scope_conditions` / `declared_width` are author-written but stay at persuasive (tier-4) strength until a **distinct-identity** verifier confirms them, regardless of the record's own tier | Author self-predicted blast radius measures only ~2x random (precision 11.8% / recall 11.1% against a 5.6%/5.4% baseline, vs. ~5x for the author's own benefit-attribution claim) — `papers/agentic_harness_engineering.pdf:9` §4.4.2. Trusting it by default launders an unreliable claim as if it were the reliable one |
| `overrules`/`voids` refuse when the acting record's tier is numerically **greater** (lower authority) than the target's | A lower-authority record silently outranking a higher one |
| `overrules`/`voids` of a tier-4 target refuse outright | Category error: promoting a never-verdicted note by fiat instead of citing, distinguishing, or simply disagreeing with it |
| **`supersedes` carries neither refusal above — no tier check, no tier-4-target refusal.** SDR-17.8 exempts it by design (`.harness/bin/precedent.py:117-121`: "`supersedes` is deliberately excluded: SDR-17.8 never applies a tier check to it") | A tier-4, never-verdicted record can flip a tier-1 record's `status` to `superseded` through an ordinary `publish` call, with no refusal and no `conflicts` finding — reproduced live in section 10.2, which names it as a genuine, unresolved detector-surface gap, not a designed protection this table's silence would otherwise suggest |
| `overrules` of a target with non-empty `cited_by` refuses unless `--acknowledge-reliance` is passed — and the refusal message lists every citing record first, so the acting agent sees the blast radius before it can proceed | The overruling agent breaks every downstream citer without ever being shown the blast radius it is about to create |
| `distinguishes` requires non-empty `distinguishing_facts` **and** a target whose own `scope_conditions` is non-empty | Distinguishing a record that declared no scope at all — there is nothing on record to distinguish *from* |
| Conflict detection (`conflicts`) is an on-demand pass, not a gate | A false-positive gate trains agents to route around the registry, which is fatal to the layer (forum-shopping by abandonment); accepted cost: a pass can be forgotten where a gate cannot (coordinator decision D6, quoted in full in section 9) |
| Precedent disputes route through verifier rotation (F6), never a single arbiter | Coordinator-as-sole-arbiter is exactly the "single agent decides alone" pattern the founding premise forbids (`docs/civilizational-roadmap-brief.md:92`) |

**v1 amends the `supersedes` row above.** Section 16.1's ledger records the amendment in full:
`supersedes` gains the ordering half of tier symmetry (a lower-authority acting record may no
longer flip a higher-authority target's `status`), while keeping no tier-4-target refusal (the
merge outcome, section 12, stays available). The row above states the v0 rule the amendment
changes; it is left as written rather than rewritten in place, because it is exactly the "old
text" half of that ledger entry.

## 2. The record and its lifecycle

One JSON file per record at `.harness/precedents/PR-NNN.json`, mirroring `.harness/tasks/`
(D5). The CLI, never an editor, allocates the id, writes the file, and is the only writer.

### 2.1 Field classes

Every field belongs to exactly one class, and the class is the load-bearing fact:

| Class | Meaning |
|---|---|
| **A** | author-declared, **binds on publication** — trustworthy-class field (ratio, or a mechanically-checked structural fact) |
| **W** | author-**written**, does **not** bind until a distinct-identity verifier confirms it — near-noise-class field (any claim about the rule's reach) |
| **R** | registry-maintained — written only by the CLI as a side effect, or by a distinct-identity verb; never settable by the publishing author |

### 2.2 Selected fields (the ones that carry the contract; the full 26-field table is
`docs/precedent-research/synthesis-design-requirements.md` section 2.1 — this document does
not re-derive it, only the fields that change bindingness or lifecycle state)

| Field | Class | Required? | Binds when |
|---|---|---|---|
| `id` (`PR-NNN`) | R | always, CLI-minted | on write |
| `authority_tier` (1-4) | A | required | on publication (section 3) |
| `tier_evidence` | A | required, ≥ 1 token | on publication |
| `ratio` | A | required, non-empty | on publication |
| `dicta` | A (non-binding by definition) | optional, default `[]` | never — persuasive only |
| `scope_conditions` | W | required non-empty at tiers 1-3, optional at tier 4 | only once `confirmation_status` flips off `unconfirmed` |
| `declared_width` (`narrow`\|`wide`) | W | required | same as `scope_conditions` |
| `confirmation_status` (`unconfirmed`\|`confirmed`\|`narrowed`\|`rejected`) | R | always `unconfirmed` at publication | flips only via `confirm`, never self-flippable by the publishing author |
| `revisit_trigger` | A | required at tiers 1-3, optional at tier 4 | on publication |
| `relations[]` | A | optional, default `[]`, **immutable after publish** | on publication |
| `cites[]` | A | optional, default `[]` | on publication |
| `cited_by[]` | R, append-only | `[]` at publication | write-time side effect on the **cited** record, never manual |
| `status` (`active`\|`overruled`\|`superseded`\|`void_per_incuriam`) | R | default `active` | flips only via `overrules`/`supersedes`/`voids` on a **different** record's publish |
| `published_by`, `published_at` | R | CLI-stamped | on write |

**Immutability.** `relations`, `ratio`, `dicta`, `scope_conditions`, `declared_width`,
`tier_evidence`, `cites`, `subject`, `title`, `issuing_task` are immutable after publication.
The only fields any verb may mutate in place, exhaustively: `status`, `overruled_by`,
`superseded_by`, `voided_by`, `cited_by` (append-only), `confirmation_status`, `confirmed_by`,
`confirmed_at`, `narrowed_scope`, `confirmation_note`. A parent record's text is never edited;
a later record narrows or rejects a scope claim by publishing a new field value on itself, not
by rewriting the record it disagrees with — lineage is append-only.

**Schema v2 (v1 amendment) adds four fields on top of the table above, and this section does
not re-derive their full table either — the complete v2 field table lives at
`docs/precedent-research/synthesis-v1-requirements.md` section 2 (its V1-10), exactly as this
section already defers the full v1 table to `synthesis-design-requirements.md`.** In one line
each, forward-referenced to where this document states their doctrine in full: `sources`
(class A, required ≥ 1 token, immutable — section 17); `validity_conditions` (class W, required
non-empty at tiers 1-3, immutable — section 19.3); `operation` (class A, required, immutable —
section 18); `interpretive_code_version` (class A, required, immutable — cites
`INTERPRETIVE-CODE.md` by name and version only, never by rule id, section 18). All four join
the immutable list above; none joins the mutable list. A `schema_version` field (`R`, `2` on
every new publish) also joins the table, distinguishing a v1-shaped record (schema_version 1,
missing all four) from a v2-shaped one — the v2 CLI loads both without refusal (dual-read), a
CLI-side migration mechanic this document does not implement or claim shipped.

### 2.3 Two independent lifecycles, never one

```
status:              publish
        (nothing) ─────────────▶ active ──┬─ named as an overrules target ──▶ overruled
                                            ├─ named as a supersedes target ──▶ superseded
                                            └─ named as a voids target ───────▶ void_per_incuriam
        (each transition is a side effect of a DIFFERENT record's successful publish, never
         a self-edit — section 7)

confirmation_status:  publish
        (nothing) ─────────────▶ unconfirmed ──confirm──▶ confirmed  ─┐
                                              ──confirm──▶ narrowed   ─┼─ re-reviewable later,
                                              ──confirm──▶ rejected   ─┘  any direction (SDR-25)
```

A record's `status` and its `confirmation_status` move independently. A `rejected` scope does
**not** touch the ratio: the ratio stays binding at tier; only the record's *reach* becomes
undefined and is treated as persuasive-only until a later `confirm` flip or a successor record
restates scope.

## 3. The four authority tiers

Bindingness is a function of *how much adversarial process a decision survived*, not of rank,
model tier, or role seniority — the same "replay, don't trust" invariant the rest of the
harness already runs on (`ORCHESTRATION.md` invariants table). Each tier is keyed to a fact a
CLI can check by reading the log, never to an assertion in the record's own text.

| Tier | Name | Observable fact | `tier_evidence` must contain | Binding force | Overturned by |
|---|---|---|---|---|---|
| 1 | operator | human gate fired / operator directive recorded (`state.json human_gates`) | ≥ 1 `event:` or `T-NNN` token anchoring the record | binding on everyone | only a new tier-1 act |
| 2 | constitutional | NLAH mutation accepted via the §5A loop + human gate (`ORCHESTRATION.md:225-229`) | ≥ 1 `P-NNN` token | binding on all agents | the same §5A path with fresh failure evidence — the registry documents the reversal, the ledger and gate remain the authority |
| 3 | verdicted | producer ≠ approver verdict exists on the issuing task (`ORCHESTRATION.md:99`) | ≥ 1 `T-NNN` token naming the issuing task | binding within confirmed scope | a new verdicted record of equal or higher tier, `relations[].type == overrules`, factor recitation mandatory (section 7) |
| 4 | single-agent | a `DECISION:` note that never passed a verifier; observable by **absence** of any verdict event citing it | ≥ 1 `T-NNN` token naming the note's task | persuasive only, never binding | nobody — overruling a tier-4 record is a category error; the CLI refuses it. The correct move is disagreement or distinguishing, never overruling |

**The "Overturned by" column above binds `overrules` and `voids` only.** `supersedes` — the
third status-flipping relation in section 2.3's lifecycle diagram — carries no tier check
whatsoever; SDR-17.8 deliberately never applies one to it (section 1's headline table names the
live consequence). Nothing in this table protects a tier-1, tier-2, or tier-3 record's `status`
from a `supersedes` call originating at any tier, including tier 4. Section 10.2 documents this
as a genuine, unresolved detector-surface gap, not a designed protection this table's silence
would otherwise imply. **v1 amends this**: section 16.1's ledger records `supersedes` gaining
the ordering half of tier symmetry — the ONLY change; the tier-4-target refusal stays absent by
design, per the same ledger entry.

**Per-field bindingness, not record-as-a-whole.** The tier above governs the record's `ratio`
immediately on publication, but its scope claims sit at persuasive strength until confirmed
(section 6) — bindingness moves one field at a time, never as a unit.

**Tier-3 overruling needs equal adversarial weight, not more.** A single verdicted pair can
undo what a single verdicted pair established; v0 does not add a wider-quorum ("en banc")
requirement, because the harness has no multi-verifier quorum primitive and inventing one for
this alone would be a new verification layer. This is a recorded open design alternative for
the operator, not a resolved question — see section 8.

## 4. Ratio and dicta: structural fields, not a note prefix

`ratio` and `dicta` are dedicated, required-or-optional JSON fields on the record, not free
text buried inside a note.

- **`ratio`** — a non-empty string. Author-declared, and it **binds** at the record's tier the
  moment the record publishes. No confirmation step exists for it, because it is the
  trustworthy-class self-declaration (section 6).
- **`dicta`** — an optional list of strings, default `[]`. Explicitly and permanently
  **non-binding**: persuasive commentary attached to the record, never elevated by any verb.

**This extends the existing note taxonomy; it does not replace or duplicate it.** The U2 note
taxonomy (`ORCHESTRATION.md:69-77`) already gives task notes four prefixes — `DECISION:`,
`DEVIATION:`, `TRADEOFF:`, `OPEN-QUESTION:` — so evolution audits can `grep` them instead of
re-reading prose. That taxonomy is, and remains, **a convention**: it is SHOULD not MUST, no
CLI validates the split, it has **no binding force**, **no scope field**, and **no authority
level**. A `DECISION:`-prefixed note is raw material a `ratio` may later be drawn from; the
ratio/dicta split becomes structural — a schema field with a class, an authority tier, and a
binding effect — only on the specific subset of decisions someone deliberately publishes to
the registry. There is no new tagging scheme for ordinary task notes, and this document does
not propose one.

## 5. Citation: the PR-NNN format

**The citable unit is `PR-NNN`**, minted by the registry CLI at publication, never
self-assigned. `PR-NNN` resolves across sessions by design — the brief's "session 40 citable
in session 200" is satisfied by durable PR-IDs, not by inventing session infrastructure.

### 5.1 Token grammar — what a citation string in `cites`, `tier_evidence`, or
`relations[].controlling_authority` may be, exhaustively

| Token | Regex | Resolves against |
|---|---|---|
| `PR-NNN` | `^PR-\d{3,}$` | a record file in the registry root |
| `T-NNN` | `^T-\d{3,}$` | `.harness/tasks/T-NNN.json` exists |
| `P-NNN` | `^P-\d{3}$` | an entry with that `id` in `state.json evolution.accepted_mutations` or `evolution.pending_proposals` (read-only) |
| `gen:N` | `^gen:\d+$` | `N <= state.json harness_generation` (read-only) |
| `agent:name` | `^agent:[A-Za-z0-9_.-]+$` | `state.json agents.registry` or `agents.reputation` key (read-only) |
| `event:TS` | `^event:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$` | a line in `.harness/logs/events.jsonl` with that `ts` |
| `path:lines` | `^[^\s:]+\.[A-Za-z0-9]+:\d+(-\d+)?$` | the file exists relative to repo root |

**The Claude hook `session_id` is explicitly rejected as a citation anchor** — ephemeral,
single-engine, and never written to the engine-agnostic `.harness/logs/events.jsonl`. The
grammar above has no token for it, by design; the resolver must not grow one.

### 5.2 What a citation may anchor to, and what happens when it dangles

- `relations[].target` **must** resolve — an unresolvable relation target is a **refusal**
  (`exit 1`): a relation pointing at nothing is meaningless.
- `cites` and `tier_evidence` entries are resolved too, but an unresolvable one is only a
  **warning** plus a `dangling_reference` event — publication proceeds. This is deliberate,
  not laxity: a registry that refused to publish evidence of its own gaps could never record
  the exact defect this layer exists to catch (the P-023 example in the intro). The on-demand
  `conflicts` pass (section 9; shipped — `.harness/bin/precedent.py conflicts`) is what sweeps
  the whole registry for dangling references after the fact.

### 5.3 How to cite a precedent inside an ordinary task note

There is no new field and no CLI-enforced format for this. Citing a `PR-NNN` inside a task
note works exactly the way the harness already cites `P`-numbers and `T`-ids in prose today —
write the token where it belongs, typically inside a `DECISION:`/`TRADEOFF:`/`OPEN-QUESTION:`
note (section 4). `ORCHESTRATION.md` itself does this at least five times already: `P-023` at
line 58, `P-025` at lines 82-90, `F6` at lines 119-126, `P-024` at lines 128-134, `P-026` at
lines 211-218. A `PR-NNN` token typed into a task note is prose the humans and agents reading
that note can follow to `precedent.py show PR-NNN`; it is not data the resolver in section 5.1
reads mechanically — that resolver only walks a *record's own* `cites`/`tier_evidence`/
`relations[]` fields. No parallel citation-tracking mechanism for notes is proposed here.

## 6. Distinguishing and scope conditions: declared until confirmed

**The governing fact, measured, not assumed.** An agent's self-declared *ratio* (why a change
helps) measured roughly 5x above random (precision 33.7% / recall 51.4%); the same agent's
self-predicted *scope of harm* (what it will break) measured only roughly 2x above random
(precision 11.8% / recall 11.1% against baselines of 5.6%/5.4%) — `papers/
agentic_harness_engineering.pdf:9` §4.4.2, "Regression blindness." Consequence adopted
throughout this schema: an agent's stated reason for a decision is roughly trustworthy; the
same agent's claim about how far that decision reaches is the least reliable text in the
record.

**The mechanical consequence.** A record whose `confirmation_status == "unconfirmed"` and
`confirmed_by == null` has **non-binding** `scope_conditions` and `declared_width` regardless
of its `authority_tier`: an unconfirmed scope claim carries tier-4 (persuasive) strength even
on a tier-1 record, until a distinct-identity `confirm` moves that specific claim toward its
record's tier strength. `show` and `list` must render this state explicitly (for example,
`scope: UNCONFIRMED (does not bind)`) — this is a mechanical field state the CLI prints, never
a prose convention a reader has to infer.

**What `rejected` means.** Rejecting a scope claim does not reject the ratio underneath it:
the ratio remains binding at tier; the record's *reach* becomes undefined and is treated as
persuasive-only until a later `confirm` flip or a successor record restates scope. A verifier
can narrow a wide claim without wholesale rejecting the record, and can later re-review a
`confirmed`/`narrowed`/`rejected` outcome — width is not a one-shot classification fixed
forever at first review.

**Scope binds roles and objects, never a specific agent identity string.** A valid
`scope_conditions` entry names roles (thinker/worker/verifier/coordinator), paths, task
classes, tiers, or conditions on them. An entry that binds a specific reassignable identity
(for example, "worker-research-1 must...") is invalid: horizontal precedent binds the office,
not the person, or it breaks the moment that identity is retired. This is a protocol rule the
confirming verifier checks by reading the text — it is not, and cannot be, a parser check.

**Distinguishing, structurally.** A `relations[].type == distinguishes` element requires
non-empty `distinguishing_facts` **and** a target whose own `scope_conditions` is non-empty —
distinguishing against a record that declared no scope at all is structurally invalid; there
is nothing on record to distinguish from. If the distinguishing record's own tier number is
*greater* (lower authority) than the target's, the relation is still **accepted**, but stamped
`below_target_tier: true` at publish time: the claim is persuasive-only for its own author and
binds no one else.

**The `confirm` verb's lifecycle.** `confirm PR-NNN --outcome {confirmed,narrowed,rejected}
(--note <s> | --note-file <f>)` — long text arrives via `--note-file`; there is no
`--note-stdin` form on `confirm` (`synthesis-design-requirements.md` section 5.6, line 461;
SDR-16 names exactly five fields that get `-file`/`-stdin` pairs — `--ratio-file`,
`--ratio-stdin`, `--scope-file`, `--distinguishing-facts-file`, `--factor-note-file` — and
`confirm`'s note is not among them). Refusals:

| Refusal | Reason |
|---|---|
| `--agent` equals the record's `published_by` | The publishing author never flips their own record's confirmation, in any direction, ever — reuses the authorship-governs logic of the existing producer≠approver check (`.harness/bin/blackboard.py:14-28`), not a new gate |
| record `status != "active"` | Confirming a dead record's scope is meaningless |
| `--outcome narrowed` with no scope restatement | The reviewer restates the scope **independently**, in `narrowed_scope`; the author's own `scope_conditions` text is never edited |
| missing `--note` | Mandatory reasoning — the same pattern `reopen` already enforces (section 7) |

Allowed transitions: from `unconfirmed` to any of the three outcomes, and between
`confirmed`/`narrowed`/`rejected` on later re-review. Every flip stamps `confirmed_by`,
`confirmed_at`, `confirmation_note` (and `narrowed_scope` when narrowed) and logs one
`precedent_scope_reviewed` event carrying the outcome and the prior state.

## 7. Overruling: who may overturn what, and the required reasoning record

Overruling extends the `reopen` verb's mandatory-reasoning pattern onto a new object; it does
not create a second task-resurrection mechanism, and `reopen` itself is untouched by this
layer. `reopen` (1) only acts on a task currently `done`/`failed`, (2) mandates `--note`
explaining why, (3) logs a `task_reopened` event to `events.jsonl`, and (4) resets the task to
`open` (`ORCHESTRATION.md:58-67`, `.harness/bin/blackboard.py:470-517`). The same three
properties — narrow precondition, mandatory reasoning, event log — reappear below, applied to
a precedent record instead of a task.

**Who may overturn what.** From the tier table in section 3: only an equal-or-higher-tier
record may overrule or void a target, and a tier-4 target can never be overruled at all
(section 1's headline-rules table gives the risk each refusal neutralizes). The acting
record's own tier is established the normal way — it must itself clear formation at that tier
(for a tier-3 overrule, a fresh producer≠approver verdict on its own issuing task).

**This tier check binds `overrules` and `voids` only — not `supersedes`.** SDR-17.8 exempts
`supersedes` from every rule in this paragraph: no tier ordering, no tier-4-target refusal, no
factor/reliance requirement beyond the `status == active` precondition every relation type
shares in the table below. A tier-4 record may `supersedes` a tier-1 record's `status` through
an ordinary `publish` call today; section 10.2 names this as a genuine, unresolved
detector-surface gap, not an intended protection. **v1 amends this** — section 16.1's ledger
entry adds the ordering half of tier symmetry to `supersedes`, leaving the tier-4-target
non-refusal untouched.

**The required reasoning record, exhaustively.**

| Requirement | When it applies |
|---|---|
| A named target's `status` must currently be `active` | always, for `overrules`/`supersedes`/`voids` — nothing to overrule twice |
| `--factor <name>` from a fixed five-name enum (`reasoning_error`, `unworkability`, `doctrinal_change`, `factual_change`, `reliance`) plus `--factor-note-file` | `overrules` where the target's tier is 3 — mandatory; optional where a human gate substitutes at tiers 1-2 |
| `--acknowledge-reliance` | `overrules` where the target's `cited_by` is non-empty — the refusal message lists every citing `PR-ID` first, so the acting agent sees the blast radius before proceeding |
| `--controlling-authority <token>` naming a resolvable citation | `voids` — *per incuriam* is specifically the claim that a controlling authority was never before the deciding process; the voiding record must name it |

**Effects of a successful overruling publish**, inside one atomic guarded write (never
nested — `.harness/bin/harness_common.py:7`): the target's `status` flips to `overruled` /
`superseded` / `void_per_incuriam` and the matching `overruled_by`/`superseded_by`/`voided_by`
back-reference is set; every record named in `cites` or `relations[].target` gets the new
record's id appended to its own `cited_by`. After the guard releases, one `precedent_published`
event is logged, plus `precedent_overruled` / `precedent_superseded` / `precedent_voided` per
status flip, into the **same** `.harness/logs/events.jsonl` used everywhere else in the
harness — mirroring `task_reopened`'s shape, not a new log file.

**The scope-breadth check for a tier-3 overrule (the overruling record's declared scope must
be at least as broad as the target's) is a protocol rule the confirming verifier checks, never
a structural parser check.** Scope text is exactly the least reliable text in the record
(section 6); a mechanical width comparison over free text would be false rigor.

## 8. Standing open design question forwarded, not resolved here

Section 3 already states v0's decision (equal adversarial weight suffices to overrule a
tier-3 record — no wider quorum). The harness has no multi-verifier quorum primitive today,
and this document does not invent one. Whether tier-3 overruling should require a wider
quorum than establishing it is presented to the operator as a named open alternative
elsewhere in this epic, not settled by this contract.

## 9. Conflict detection: an on-demand pass, not a gate

DECISION (coordinator decision D6): conflict detection is an on-demand CLI pass
(`precedent.py conflicts`), modeled on `lock.py sweep` / `blackboard.py expire-claims` —
engine parity is the invariant; hooks are Claude-side sugar only. TRADEOFF, stated as decided:
**a pass can be forgotten where a gate cannot; accepted for v0 because a false-positive gate
trains agents to route around the registry, which is fatal to the layer.** Promotion to a
gate is a candidate follow-on, gated on the pass first demonstrating precision on real
precedents — it is not built by default just because a gate would close the "forgotten" risk.

`conflicts` **is implemented** (T-342, landed after this document's earlier draft, into the
same `.harness/bin/precedent.py` this document describes throughout). Its shipped surface,
verified against the live `--help`:

`conflicts [-h] [--json] [--root ROOT]` — no flags beyond the two every read verb already
carries; `--root` overrides the registry root the same way it does for `show`/`list`/`cite`
(SDR-13).

**Read-only, same contract as `cite`.** It never mutates the registry and logs no event —
`.harness/bin/precedent.py:937-956` states the reasoning: making `conflicts` the one read verb
with a side effect would be an asymmetry a future engine-parity audit would have to explain,
and SDR-23 already established that `cite` "never writes anything, including events" on the
same grounds.

**Exit codes reuse SDR-15's table verbatim; no new codes were minted for this verb:** `0`
clean (zero findings across the scanned registry), `3` findings (one or more conflicts
reported), `2` usage error (argparse-native), `4` registry integrity error (an unparseable
record hit mid-scan).

**Five detectors run on every sweep, unconditionally** (`.harness/bin/precedent.py:979-1125`):
(1) two ACTIVE records sharing a `subject` with diverging `ratio` text and no relations/cites
link acknowledging each other; (2) an ACTIVE record citing or following a target whose
`status` is `overruled`; (3) an `overrules`/`voids` relation recorded by a numerically higher
(lower-authority) tier against a numerically lower (higher-authority) target — the
illegitimacy D4 forbids, checked against every record regardless of status; (4) two ACTIVE
records at the SAME tier with overlapping `scope_conditions` and diverging `ratio`, same
acknowledged-pair exclusion as (1); (5) dangling citations registry-wide, any status — reusing
the identical resolution core `cite --all` already runs (SDR-23/C-2) rather than
reimplementing it, and the mechanism section 5.2 forward-references as what eventually catches
a P-023-shaped gap.

**v1 doctrine: detector 3 widens to also scan `supersedes` relations for the same
tier-violating shape**, per section 16.1's ledger entry and section 10.2's carried-defect-(ii)
note — this is doctrine this document states for `.harness/bin/precedent.py` (T-353) to build
against, not a claim that the five-detector count above has already become six; the count
above describes the shipped surface as last verified live (section 16), and the epic's own
adversarial replay (T-360) is what confirms whether the widened detector 3 actually ships as
detector 3 (a widened check) rather than a new detector 6 — either shape satisfies the doctrine.

This document states that shipped surface and stops there, by design: the detectors' own
semantic judgment calls — what a verifier does with a given finding, whether a detector's
mechanical proxy for "contradiction" is doing its job in an edge case not covered above — are
not re-derived here. They live at the cited lines in `.harness/bin/precedent.py` itself. The
fuller failure-mode treatment — which of these five detectors maps to which named failure mode,
what each one's own false-positive risk is, and what is still DEFERRED beyond them — is section
10 below; adjudication of an actual finding is section 12.

## 10. Failure modes: detection signals and verdicts

Four failure modes are named because real precedent systems have each, by name, and because
`docs/precedent-research/07-failure-modes.md` (research item 7) traces each to a detection
design. `docs/precedent-research/synthesis-refinements.md` (T-344) consolidates that design
with item 4's anti-evasion signals into one numbered list, S-01 through S-15. This section
gives every one of the four failure modes an explicit verdict — **DETECTED BY V0** (the signal
runs today, verified against the live CLI below) or **DEFERRED** (it does not, and the reason
and the missing piece are named) — because a failure mode listed with no detection status is a
defect. Every signal is a read-only query over `events.jsonl` plus the registry; none proposes
a second logging substrate (the non-additive-duplication constraint, `papers/
agentic_harness_engineering.pdf:8` Table 3 RQ3a — stacking a redundant verification layer has
already regressed this class of system once, section 12 below restates why that matters for
adjudication specifically).

**A reconciliation finding stated up front, because it corrects the synthesis's own language.**
T-344 verdicts several signals "the v0 conflicts pass can compute this," meaning *computable
within v0's stdlib-plus-registry constraints if built* — not *already running*. Read against the
actually shipped `.harness/bin/precedent.py`, verified live (section 16 records the commands),
exactly **five** detector functions exist in `conflicts` — `detect_subject_ratio_conflicts`
(1, `subject-ratio-contradiction`), `detect_overruled_cited_as_binding` (2,
`cites-overruled-as-binding-support`), `detect_illegitimate_overrule_tier` (3,
`illegitimate-overrule-lower-tier`), `detect_scope_overlap_conflicts` (4,
`same-tier-scope-overlap`), `detect_dangling_citations` (5, `dangling-citation`) — plus one
mandatory-but-non-blocking scan inside `cmd_publish` (SDR-18, the S-09 citation-completeness
check, confirmed shipped below). **No sixth detector, and no citation-graph/cluster query, exists
in the running code.** So below, "DETECTED BY V0" means one of these six checks; a signal T-344
called "v0 can compute" that is not one of these six is verdicted DEFERRED here, on the honest
present-tense reading, with a note that it remains buildable without new substrate whenever
someone builds it. This is a DEVIATION from T-344's forward-looking phrasing, not from any of
its facts, and it is the document that changes to match the code (never the reverse).

### 10.1 Ossification and the dead-hand problem

Common-law systems that treat precedent as absolutely, permanently binding ossify —
*London Tramways Co Ltd v London County Council* [1898] AC 375 is the dead-hand problem in its
purest form, a court that cannot correct its own errors even when it recognizes them. The named
fix real systems converged on is a deliberate, conditioned escape valve, not an ad hoc one: the
1966 *Practice Statement (Judicial Precedent)* let the House of Lords depart from its own past
decisions "when it appears right to do so," while naming the costs that constrain when (settled
reliance, criminal-law certainty) — departure is possible, but gated on a stated reason.
Landes & Posner's economic account names the underlying mechanism: precedent is "a capital stock
which yields a flow of information services which depreciates over time" — ossification is not
"precedent existing," it is precedent's information value depreciating faster than the system
revisits it.

**Signal S-12 (ossification: cited-but-never-revisited), class B/C split, verdict SPLIT.** PR-N
cited >= 5 times with zero distinguish/overrule attempts over a window (one
`harness_generation` bump or 50 closed tasks) while its `revisit_trigger` condition has been
satisfied without a revisit occurring.
- **The structural half — DETECTED BY V0.** Every binding-tier (D4 tier 1-3) record carries
  `revisit_trigger` at publication, refused if empty: `publish --tier 1` (or 2, or 3) with no
  `--revisit-trigger` refuses `revisit_trigger must be non-empty at tiers 1-3 (SDR-17.4)`,
  reproduced live for this revision (section 16). Tier 4 is genuinely optional — a tier-4 record
  publishes clean with `revisit_trigger: null`, also reproduced live. This closes the one
  concrete gap the research flagged: v0 had no escape valve on the *precedent record* grain at
  all (task-level `reopen` and NLAH-level human gates are one grain too coarse or too high); the
  field exists and is enforced exactly where it needs to be.
- **The counter half — DEFERRED.** The citations-without-revisit *count* is v0-computable once
  `cites[]` exists (it does) but is **not** one of the six checks named above — no detector
  reads a citation count against an unmet `revisit_trigger`. What it would take: a seventh
  detector, informational-only (class C), reading `cited_by` length against overrule/distinguish
  attempts in the same window — no new event kind, pure query.
- **The semantic half — DEFERRED, permanently by design.** `revisit_trigger` is free text; whether
  its condition has actually been met is a judgment call, not a parser check. What it would take:
  either a constrained, greppable trigger grammar, or a standing verifier review of open triggers
  at each §5A audit. The turns-per-task companion signal (elevated turns on tasks citing >=2
  binding precedents in scope) is separately DEFERRED — it needs a transcript-metrics join that
  does not exist as a query today.
- **False-positive risk.** The stable-correct rule ("lock before writing any file") shows high
  citation with no unmet trigger — that is expected health, not ossification. Citation count
  alone, without the unmet-trigger component, is never evidence.

### 10.2 Fragmentation and circuit splits

U.S. Supreme Court Rule 10 names an inter-circuit conflict on an "important matter" as a
first-class, if discretionary, ground for the one court with power to resolve it to intervene;
28 U.S.C. §1407 consolidates fact-identical disputes across districts without erasing the
originating courts' authority. Both mechanisms presuppose a court of last resort exists to hear
the conflict. The historical instance the harness must not repeat glosses over — because the
brief's own "likely closer to our topology" framing needs the qualification — is the **lex
mercatoria**: locally-consistent, mutually-divergent merchant custom **with no reconciliation
function at all** (Kadens; Baker, per `docs/precedent-research/06-administrative-mercantile-
precedent.md` §9). That is worse than a circuit split, not a milder version of one — there was
no Rule 10 for it. **`precedent.py conflicts` must catch inter-lineage divergence (two lineages'
binding records contradicting), not only intra-registry duplicate-ID collisions** — this is the
scope note the fragmentation lesson writes into the pass, R-7 in T-344.

**Signal S-08 (circuit-split candidate pairs), class B, verdict DETECTED BY V0.** >= 2 records
at tier 3 or higher with overlapping declared scope, divergent ratio, no shared ancestor, and no
adjudication record between them; urgency escalates with the higher tier of the pair (a
tier-4-vs-tier-4 disagreement is noise, not a split — section 10.4 below is where that pair type
actually belongs). This is, concretely, detectors 1 and 4 as shipped: detector 1
(`subject-ratio-contradiction`) keys the same divergence off `subject` rather than scope-text
overlap; detector 4 (`same-tier-scope-overlap`) is the literal scope-overlap shape. Reproduced
live for this revision (section 16): two tier-3 records sharing a subject and overlapping
`role:worker` scope, with different ratio text and no relations/cites link, fire **both**
detectors in the same sweep — `conflicts` exits 3 with 2 findings, and `--json` carries
`{"detector": 1, "name": "subject-ratio-contradiction", ...}` and `{"detector": 4, "name":
"same-tier-scope-overlap", ...}` verbatim. Resolution is never automatic — every flagged pair
routes to section 12's adjudication protocol.
- **False-positive risk.** MEDIUM — disjoint scopes that look similar in short summary text; the
  detector diffs the `scope_conditions` set, never `ratio`/`summary` prose alone (confirmed live:
  detector 4 intersects the `scope_conditions` sets, case-sensitively).
- **Genuine detector-surface gaps, named rather than hidden, found by this epic's own adversarial
  replay (T-347) and carried here because they bound how much to trust a clean sweep:** detector
  4 is subject-agnostic — two same-tier records on unrelated topics that merely share a generic
  scope literal like `role:worker` still collide, a real precision cost at registry scale because
  scope conditions are free-text tags, not a controlled vocabulary; and detector 2
  (`cites-overruled-as-binding-support`) checks only `status == "overruled"`, not `superseded` —
  an active record can `follows`/cite a target that was legitimately superseded and still read as
  relying on live law with zero findings. Both are real gaps in the shipped detectors, not a
  doc/code mismatch this document can paper over — they belong to `.harness/bin/precedent.py`
  (T-340/T-342's file), not to this document to fix.
- **A third gap from the same replay, T-347's Case C: `supersedes` carries no tier check at
  all.** SDR-17.8's tier-symmetry rule and detector 3 both scope themselves to `overrules`/
  `voids` only — the module's own docstring states it outright: "`supersedes` is deliberately
  excluded: SDR-17.8 never applies a tier check to it" (`.harness/bin/precedent.py:117-121`). A
  tier-4, never-verdicted record can therefore `supersedes` a tier-1 record through an ordinary
  `publish` call: the target's `status` flips to `superseded` with `superseded_by` set, exit 0,
  and `conflicts` reports zero findings. Reproduced live for this revision: publish a tier-1
  record, `--supersedes` it from a fresh tier-4 record, then run `conflicts` —
  `conflicts: 0 findings across 2 record(s)`, no refusal anywhere in the path. This is a
  strictly stronger instance of the illegitimate-tier-inversion failure detector 3 exists to
  catch, since it needs no cites/relations tampering at all, only the one status-flipping verb
  detector 3 never inspects — sections 1, 3, and 7 above now name the exemption directly rather
  than leaving `supersedes` looking covered by the same protection `overrules`/`voids` carry.
  This belongs to `.harness/bin/precedent.py` (T-340/T-342's file) to fix, not to this document —
  named here for the same reason the two gaps above are.
  **v1 status: this gap is "carried defect (ii)" and is now IN SCOPE, fixed by doctrine in this
  revision — section 16.1's ledger records the exact amendment (`supersedes` gains the ordering
  half of tier symmetry, not the tier-4-target refusal) and its authority (T-347's finding,
  verdicted at T-352). The CLI-side fix remains `.harness/bin/precedent.py`'s own work
  (`docs/precedent-research/synthesis-v1-requirements.md` V1-03/V1-49 fix the exact scope for
  that file to build against); this document states the doctrine the fix must satisfy and does
  not claim the fix has shipped — the epic's own adversarial replay (T-360) reconciles the two.**
- **A fourth gap from the same replay, T-347's Case G: the citation resolver never reads
  `dicta`.** `_record_citation_tokens` (`.harness/bin/precedent.py:786-794`) walks `cites`,
  `tier_evidence`, and `relations[].target`/`controlling_authority` only — never `ratio`,
  `dicta`, or `title` text. A `PR-NNN`/`T-NNN`-shaped token written solely into a record's own
  `dicta` is therefore invisible to both `cite --record` and every `conflicts` detector, for the
  identical reason section 5.3 already gives for note prose: no verb parses free text for
  citation-shaped tokens, and `dicta` is exactly that — persuasive prose the schema deliberately
  never binds (section 4). Reproduced live for this revision: publishing a record whose `dicta`
  names two unresolvable tokens in prose only produces `cite --record` output reporting the one
  *structured* `tier_evidence` token as OK and saying nothing about either dangling prose
  reference, while `conflicts` finds nothing. This belongs to `.harness/bin/precedent.py`
  (T-340/T-342's file) to fix, not to this document — named here for the same reason the two
  gaps above are.

### 10.3 Forum shopping

*Piper Aircraft Co. v. Reyno*, 454 U.S. 235 (1981) forecloses choosing a venue for its more
favorable law absent an essentially-no-remedy alternative; §1407 and Rule 10 are both
structural and non-optional, because forum shopping is definitionally strategic behavior by an
actor who benefits from evading the check, and a check the evader can decline to run is exactly
the shape real anti-forum-shopping doctrine does not use (07 §3.4). This is the finding that
cuts against coordinator decision D6 (on-demand pass, not a gate), and the reconciliation below
resolves it rather than leaving it open.

**Citation shopping — signal S-09 (citation-completeness at publish), class B mandatory-but-
non-blocking, verdict DETECTED BY V0, SHIPPED.** Verified live in `cmd_publish`
(`.harness/bin/precedent.py:619-705`, SDR-18): at publication, the CLI computes the set of
active tier 1-3 records sharing the new record's `subject` and absent from its `cites[]`/
`relations[]`; if any exist, it logs a `citation_gap` event and prints, character for character,
`warning: citation-completeness gap -- active tier 1-3 record(s) sharing subject '<subject>'
not cited: <ids>` — then **publishes anyway**. Reproduced live for this revision (section 16):
publishing a second tier-3 record on a subject an existing tier-3 record already occupies, with
no `--cites`/`--follows` naming it, prints exactly that warning and exits 0. **This resolves the
D6 tension rather than restating it as open**: 07 §3.4 is right that every real anti-forum-
shopping mechanism found is structural and non-optional, and D6 is right that a false-positive
hard gate trains agents to route around the registry (forum shopping via abandonment) — the
shipped design takes the property that matters (the actor cannot decline to run the check,
because it runs inside the verb it must call anyway) while refusing the property D6 feared (a
block on a false positive). This EXTENDS D6; it does not overrule it — the registry-wide
on-demand sweep (section 9) stays exactly as decided. The **residual tension that remains open
for the operator**: 07 §3.4's stronger recommendation — a true hard refusal at tier-3
publication, not merely a warning — is not built, and promotion from warning to refusal is a
named follow-on gated on the check first demonstrating precision on real records (same shape as
section 9's pass-to-gate promotion path).
- **False-positive risk.** The novel-scope trap: "zero citations" is only shopping when a
  matching precedent existed and was reachable; scope matching is itself a text proxy (the same
  reliability asymmetry as section 6 — a record's `ratio` is roughly trustworthy self-declared
  text, its scope claims are the least reliable text in the record).

**Registry/engine shopping — no signal, resolved structurally.** Once D5's single
`.harness/precedents/` store ships — verified: `--root`/`PRECEDENT_ROOT` both name one shared
root, and no per-engine registry variant exists — there is no second registry to shop between.
This was only ever a transitional risk, during the pre-schema period when per-engine informal
notes were the only record; it demands nothing beyond D5 itself.

**Tier shopping — signal S-10 (republish-after-rejection), class D, verdict DEFERRED.** A
near-duplicate decision republished at tier 4 within one `harness_generation` of a REJECTED or
unresolved tier-3 attempt on the same substance. DEFERRED because no verdict-outcome code exists
on rejection events today, and near-duplicate matching over free prose is noisy without one.
**Interim protocol rule, since v0 has no automated check:** a verifier receiving a tier-3
publication should check for recent refusals/rejections on the same substance before verdicting
— a human-judgment stopgap, named as such, not a mechanism. **Signal S-11 (verifier-override
rate on self-declared distinguishes), class D, verdict DEFERRED** for the identical missing-datum
reason; once a rejection-outcome field exists, `override_rate(agent) = downgrades /
self_declared_distinguishes` is a trivial counter mirroring the existing `agents.reputation`
shape (`.harness/bin/blackboard.py:118-128`), flagged at `> 0.4` with `>= 5` declared.

### 10.4 Precedent inflation and citation clusters

Landes & Posner's depreciation model supplies the mechanism (citing is cheap; verifying a cited
precedent's `ratio` actually supports the citing decision is costly, so citation volume can grow
faster than verified information content); Fowler & Jeon's citation-network method shows raw
citation *count* diverges from citation-derived *authority* during periods of doctrinal drift —
count is not, by itself, a reliable signal of binding weight. The "citation cartel" label itself
is SPECULATION (07 §4.1 tags it as such): no source retrieved studies self-citation rings among
peer decision-makers in the case-law sense; the construction is this research's own extension of
two established citation-economics claims onto a precedent registry.

**Signal S-13 (precedent-inflation / citation-cluster query), class C, verdict DEFERRED — not
shipped, though buildable without new substrate.** Connected components of the `cites[]` graph
restricted to tier-4 nodes, >= 3 members, zero in-edges from tier 1-3 records, zero
verifier-engagement events over a window. As stated in this section's opening reconciliation:
no graph-traversal detector exists among the five shipped detectors or inside `publish` — this
is a named, scoped-out sixth-detector candidate for a future revision of `precedent.py`, recorded
here as an open build item rather than implied by anything above. If built, it ships
informational-only per its own SPECULATION label: a cluster finding flags where verification
never happened, it is not a conflict between binding records and needs no adjudicator.
- **Companion counters, same verdict (v0-computable, not shipped):** S-05 (distinguish-density
  per precedent — `distinguish_rate = distinguishes / all citations`, report `> 0.7` with
  `n >= 3`) is downgraded per Re (2014): a raw-frequency signal flags the healthiest, most
  load-bearing precedents as the most suspect, because narrowing is ordinary, healthy practice —
  **if ever built, this MUST ship informational-only**, never a hard flag by default. S-06
  (scope-erosion proxy — `N >= 4` consecutive `distinguishes` with zero intervening `follows`)
  has the same shape: the mechanical proxy is computable, but per the same reliability asymmetry
  as section 6, the scope text being compared is the least reliable field in the record, so the
  erosion *verdict* is adjudicator-only by construction — a triggered counter routes to section
  12's adjudication, it never auto-concludes evasion.
- **False-positive risk.** A small, genuinely related task cluster citing a shared decision that
  is later verified is not a cartel — the discriminator is absence of any tier 1-3 anchor or
  verifier engagement *over time*, not mutual citation per se.

### 10.5 Consolidated verdict table

| Failure mode | Governing signal(s) | Verdict | Where it lives if shipped |
|---|---|---|---|
| Ossification | S-12 | SPLIT — structural field: DETECTED BY V0; count/trigger-semantics: DEFERRED | `publish`'s tier 1-3 `revisit_trigger` refusal |
| Circuit splits / fragmentation | S-08 | DETECTED BY V0 | `conflicts` detectors 1 and 4 |
| Forum shopping — citation shopping | S-09 | DETECTED BY V0, shipped | `publish`'s citation-completeness scan |
| Forum shopping — registry/engine shopping | none | resolved structurally (D5) | n/a |
| Forum shopping — tier shopping | S-10, S-11 | DEFERRED (missing verdict-outcome code) | not built |
| Precedent inflation / citation clusters | S-13 (+ S-05, S-06 companions) | DEFERRED (v0-computable, not shipped) | not built |

## 11. Anti-evasion norms for distinguishing

Every anti-evasion norm surveyed in the research presupposes a single hierarchy the
distinguishing party stays embedded in and answerable to. *Rodriguez de Quijas v.
Shearson/American Express, Inc.*, 490 U.S. 477, 484 (1989): "If a precedent of this Court has
direct application in a case, yet appears to rest on reasons rejected in some other line of
decisions, the Court of Appeals should follow the case which directly controls, leaving to this
Court the prerogative of overruling its own decisions." This is not a rule against distinguishing
on genuinely different facts — it is a rule against a lower tier treating a precedent as
obsolete *because the lower tier thinks it should be overruled*, which is precisely the failure
mode where "distinguishing" becomes a euphemism for a lower tier doing what only the issuing tier
may do. *Broome v Cassell & Co Ltd* [1972] AC 1027 (HL), rebuking a Court of Appeal that had
directed trial judges to disregard binding precedent as decided *per incuriam*: "in the
hierarchical system of courts which exists in this country, it is necessary for each lower tier
... to accept loyally the decisions of the higher tiers." The generalizable norm this supplies is
not "distinguishing is forbidden" — it is that *whatever device* a lower tier uses to avoid a
binding decision (per incuriam, distinguishing, "this reasoning is outdated") is disciplined the
same way: only the same-or-higher authority tier gets to say the precedent no longer controls.

**Protocol rule, named by this document per Rodriguez de Quijas/Broome v Cassell (signal S-03's
semantic half): a citing record that argues a target's *reasoning* is outdated — rather than
pointing to material facts outside its declared scope — is an attempted overruling wearing
distinguishing's clothes, and MUST be routed through the overruling protocol (section 7) at the
target's own tier, never processed as an ordinary distinguish.** Section 7's tier-symmetry
refusal already enforces the numeric half of this mechanically; this paragraph names the evasion
shape D4's tiers state only generically, so no reader has to infer it.

Duncan Hosie's "Factual Revisionism" (78 Stan. L. Rev. Online 184 (2026)) names the mechanism
most relevant to a text-level anti-evasion detector: courts (or a single opinion) can change
settled law by manipulating the *factual predicate* a rule is applied to, rather than the rule
itself, while professing fidelity to the record. Hosie's four-part anatomy — **substitution** (a
new factual characterization supplants the earlier finding without ever declaring it clearly
erroneous), **rhetorical naturalization** (the substitution is repeated with confident,
non-hedged language until it reads as settled truth), **evasion** (the opinion does not engage
with the record it contradicts), and **nominal acceptance** (the opinion claims to defer to
earlier findings while doing the opposite) — is the vocabulary this document borrows for signal
S-07 below, because "distinguishing" and "factual revisionism" use the identical surface move
(recharacterizing facts) for opposite purposes (legitimate narrowing versus quiet reversal), and
the literature's own point is that a diff of the *words* cannot, by itself, tell which one
happened.

**Five items are mechanically checkable — an agent or a CLI pass can flag these without legal
judgment:**

1. **Formal-completeness check (S-01), verdict DETECTED BY V0, shipped.** A `distinguishes`
   relation requires non-empty `distinguishing_facts` and a target whose own `scope_conditions`
   is non-empty — section 6 already documents this refusal; there is nothing on record to
   distinguish *from* otherwise.
2. **Authority-symmetry check (S-02), verdict DETECTED BY V0, shipped.** A lower-tier distinguish
   is accepted but stamped `below_target_tier: true` — persuasive only for its own author,
   binding no one else (section 6).
3. **Interested-party check, verdict PARTIAL.** Whether the distinguishing agent is also the
   party whose own prior performance the precedent would otherwise bind is, structurally, the
   same conflict-of-interest shape as producer≠approver (`.harness/bin/blackboard.py:14-28`).
   **DETECTED BY V0 for scope *confirmation*** — the `confirm` verb refuses a self-flip (section
   6). **Not yet checked for `distinguishes`/`overrules` publication itself** — nothing in the
   shipped CLI stops the same agent identity that authored PR-A from later publishing PR-B that
   distinguishes or overrules PR-A. Named here as an open gap, not claimed as covered.
4. **Grounding-in-record check — signal S-07 (fact-restatement fidelity diff), class B, verdict
   PARTIAL v0, not shipped.** A distinguish claim's facts must be traceable to a record that
   predates the distinguish claim itself, not asserted for the first time in the act of
   distinguishing. The check (a stdlib `difflib` comparison between a citation-time restatement
   and its earlier, contemporaneous record) is computable today once both text fields exist —
   but it is not implemented in the shipped `publish`/`conflicts` surface, verified: neither
   command runs a text-fidelity diff. **The tool, once built, produces an exhibit for the
   verifier — it never produces a verdict.** Honest late elaboration is textually
   indistinguishable from revisionism to a diff; that discrimination is item 7 below, permanently.
5. **Distinguisher-identity concentration check (S-04), class B, verdict v0-computable, not
   shipped.** Every `distinguishes` relation published against a single target PR-X carries the
   citing agent's identity; `max_share = max_agent_count / total_distinguishes` against that
   target, flag when `max_share > 0.6` and `total >= 3`. Output routes to section 12's
   F6-style rotation review, never to auto-invalidation — one agent legitimately owning a topic
   area is common, so the false-positive risk is LOW-MEDIUM, not zero. Identical in shape to the
   existing `agents.reputation` counters (`.harness/bin/blackboard.py:118-128`) — a read-only
   aggregation over agent identity already on record, no new counter store. **Not implemented in
   the shipped `publish`/`conflicts` surface, verified: no sixth detector computes this**
   (section 10's opening reconciliation — exactly five detector functions exist, none is this
   one).

**Two items are not mechanically checkable — this document names, rather than hides, where only
a human or an adjudicator agent can tell the difference:**

6. **Materiality.** Whether the factual difference asserted is *material* in the doctrinal sense
   — whether it is the kind of difference that, given the target's own underlying ratio and not
   just its literal facts, ought to change the outcome. No source surveyed offers a formula for
   this, and this document does not invent one. It is a verifier/adjudicator judgment, full stop.
7. **Aggregate erosion and revisionism.** Whether a *chain* of individually-plausible narrow
   distinguishes has, in aggregate, carved away so much of a precedent's scope that nothing
   recognizable is left to bind future cases (S-06's mechanical trigger flags the pattern; per
   section 6's reliability asymmetry, the scope text a trigger compares is the least reliable
   field in the record, so the *erosion verdict* routes to section 12's adjudication, never an
   auto-conclusion) — and, symmetrically, whether a text-restatement diff (S-07, once built) shows
   honest late elaboration or Hosie-style revisionism. Neither is resolvable by a script; both
   route to a verifier or an adjudicator, by design, permanently.

**The practical consequence, stated plainly:** items 1-5 belong in this schema and the on-demand
`conflicts` pass, where three of the five already run; items 6-7 belong to a verifier or
adjudicator role and cannot be delegated to a script — which is consistent with D4's existing
tier design (an unconfirmed, single-agent distinguish claim is persuasive only), not a gap the
schema needs to newly close.

## 12. Adjudication: no single agent decides alone

The founding premise applies to precedent disputes exactly as it applies everywhere else in this
harness: **no single agent decides alone** (roadmap Part V principle 1,
`docs/civilizational-roadmap-brief.md:92`). Concretely, this means precedent conflicts do not get
a new standing "adjudicator" role or a coordinator-as-arbiter shortcut — they inherit the same
discipline that already governs every other epic join and guardrail change: **verifier rotation
(F6, `ORCHESTRATION.md:119-126`)**. The scout's own finding that motivated this epic states the
failure mode by name: absent this inheritance, "the coordinator is the de facto single arbiter"
for cross-lineage precedent conflicts — exactly the forbidden pattern
(`.harness/context-brief-precedent-layer.md` §3 row 6). **The one single actor who MAY settle a
conflict solo is the operator (tier 1), because tier 1 is definitionally the human gate** — no
other identity, including the coordinator, gets that exception.

**How F6 applies to a precedent conflict, concretely.** When section 10's S-08 (detectors 1/4) or
an S-09 `citation_gap` review surfaces a conflict between PR-A and PR-B:

1. A verifier-role adjudication task is created on the blackboard.
2. The claiming identity **must differ from the producing agent AND the verdicting verifier of
   both PR-A and PR-B** — computed mechanically from the records' identity fields
   (`published_by`) plus `events.jsonl`'s verdict trail, the same authorship-not-status logic the
   harness already runs on task verdicts (P-011, `.harness/bin/blackboard.py:14-28`) — and must
   satisfy F6 across the epic (not be the sole approver of the epic's other verdicts).
3. **Escalation follows the tier of the higher record:**
   - tier 1 involved → the operator decides;
   - tier 2 involved → the §5A loop with its human gate;
   - tier 3 vs. tier 3 → a new tier-3 verdicted decision citing both, per the overruling protocol
     (section 7) if one record is to prevail, or a successor publication (item 5 below) if both
     contributed;
   - tier 4 vs. tier 4 → **no adjudication at all — both remain persuasive.** Adjudicating every
     tier-4 disagreement would manufacture the process-over-action failure the standing caution
     (section 13) warns about; Rule 10's own selectivity ("important matter," not every
     disagreement) maps onto tier here.

**A conflict whose citing record argues the target's reasoning is outdated is not an ordinary
distinguish dispute** — section 11's named routing rule applies: it goes through the overruling
protocol at the target's own tier, not through this adjudication path as if it were a factual
disagreement.

**What an adjudication record must contain, at minimum** (it is itself a publishable precedent
record, subject to the same schema and checks):

1. the conflicting PR-IDs and each one's authority tier at the time of adjudication;
2. the scope overlap **as independently restated by the adjudicator** — never as either party's
   self-declared scope text, because self-declared blast-radius text is the least reliable half
   of any record (section 6);
3. the adjudicator identity plus the mechanical evidence of non-production — the event/record
   citations showing it produced and verdicted neither record (replay, don't trust —
   `ORCHESTRATION.md:100`);
4. the ruling as a `relation` outcome: which record prevails (`follows`), a distinguish with its
   facts, an overruling with its reasoning burden (section 7), or a merged successor (below);
4a. **the adjudication's own `operation` field (schema v2, section 18) tags `determination`, not
   a corrective reinterpretation or a valuation** — an adjudicator picks a winner between two
   readings each defensible at publication, a forward-looking choice, not a claim that the
   losing record's reasoning was defective from birth. An adjudicator who genuinely believes the
   losing record's reasoning was wrong is not adjudicating a peer conflict at all; the act must
   instead be typed and routed as `reinterpretation`/`corrective` or `overrules` at the losing
   record's own tier (section 18's closing paragraph; section 11's Rodriguez de Quijas/Broome v
   Cassell routing rule, applied to the same line);
5. the adjudication's own `ratio` and `scope_conditions`, contemporaneous at publication (section
   4's Chenery-shaped rule, applied here at a different grain);
6. append-only relation entries linking both parent records — parent texts are never edited
   (section 2.1's immutability discipline);
7. the logged event, through the existing `log_event()` call — no new log file.

**Merge as an adjudication outcome, recorded now; a first-class merge verb, gated on the
operator.** Section 3's tier ladder and the `overrules`/`voids` mechanism model one timeline
correcting itself; a genuine fork produces two simultaneously legitimate branches, and
`conflicts` detects contradiction without reconciling it. v0 handles this **without a contract
change**: an adjudicator MAY resolve a conflict by publishing an ordinary successor record that
cites both parents and states what each contributed — `relations` type `supersedes` plus `cites`,
already supported, already stated in section 11's predecessor discussion — so rank-and-discard is
not the only outcome the schema allows. A first-class `precedent.py merge` verb, however, changes
the registry's contract and **must be presented at the epic join's operator gate**, not slipped
in by a worker; whether the layer ever actually exercises the merge outcome, or only ever
rank-and-discards, is exactly what section 13's CAUTION-3 signal tracks.

## 13. Standing caution: the Graeber-Wengrow steelman

This section carries the mandated steelman (roadmap Part VII,
`docs/civilizational-roadmap-brief.md:117`: "assign at least one research agent to steelman this
critique against the roadmap") in its own strength, not as a weakened disclaimer softened for
comfort. It is sourced from `docs/precedent-research/08-graeber-wengrow-steelman.md` (research
item 8) and from `synthesis-refinements.md`'s R-13 through R-16.

**The strongest case against building this layer at all.**

1. Roadmap Part VI states the founding assumption flatly: institutions exist *because* actors are
   cognitively limited and mortal. Agents that fork, merge, and regenerate full context cheaply —
   the exact capability Part V principle 4 names — may not carry that scarcity into this actor
   class at all, or only partially and temporarily. If so, building permanent binding law is
   solving a problem this substrate does not structurally have.
2. The reversible alternative is not hypothetical — it is the status quo already running in this
   repo: free-text `DECISION:`/`TRADEOFF:`/`OPEN-QUESTION:` notes, persuasive-only, no citation
   IDs, no ratio/dicta split, no conflict detector, no `PRECEDENT.md`. It costs nothing to keep.
   Graeber and Wengrow's own preferred political arrangement — consciously kept reversible rather
   than crystallized — is exactly this, made concrete: **keep decisions as disposable memos and
   rebuild consensus per session, and treat churn as the price of adaptability.**
3. The corpus itself measured that stacking one more institutional/verification layer on an
   already-working substrate can *regress* performance — "+ system_prompt only" was the sole
   regression among four single-component swaps tested, -2.3 percentage points
   (`papers/agentic_harness_engineering.pdf:8` Table 3, RQ3a) — and that accumulated,
   path-dependent optimization plateaus rather than compounding forever (a documented ~83% pooled
   local ceiling in a related harness-optimization benchmark). Both are concrete, harness-native
   reasons, not just historical analogy, to doubt that "add binding jurisprudence" is a free win.
4. A live, published, non-institutional coordination paradigm already exists: `papers/
   trinity.pdf` describes an evolved LLM coordinator achieving real-time multi-agent role routing
   with no precedent registry, no ratio/dicta schema, no citation index at all.
5. The cheapest fallback this argument implies, stated plainly, not softened: **do not build
   `precedent.py` or `.harness/precedents/`.** Keep the note taxonomy exactly as it is; let
   `events.jsonl` carry the historical record for anyone who wants to re-derive consensus; accept
   that some good decisions will be silently re-litigated every few sessions, as the price of
   never having to build, maintain, or adjudicate a jurisprudence system a cheap-forking actor
   class may not need.

**Why the epic proceeds anyway — stated explicitly, not left as an unaddressed datapoint.**
Trinity solves real-time role routing *within* a session; it does not solve durable, auditable,
cross-session precedent — a lineage that forks and remerges within one session's lifetime is a
different problem from a decision that must still bind a session that opens six weeks later with
zero shared memory. Trinity does not falsify the founding premise; it demonstrates a different,
narrower coordination problem has a non-institutional solution. The plateau finding argues for
building *reversibility mechanisms inside the layer* (the `revisit_trigger` field, section 10.1;
merge-not-only-discard, section 12; tier 4's permanence, below) — it is evidence against
over-institutionalizing, not evidence against institutionalizing at all. **The anti-build null
hypothesis itself is presented to the operator at the epic join, not settled here and not
buried**: tier 1 is the correct authority to decide whether this layer should exist, and that
decision cannot be delegated to a worker task revising a contract document.

**Concrete design consequences already adopted because of this steelman, not decoration:**

- **`revisit_trigger` on every binding-tier record, not only rejected proposals** — shipped,
  verified in section 10.1: `publish` refuses an empty `revisit_trigger` at tiers 1-3.
- **Merge as a publication outcome now; a first-class `merge` verb gated on the operator** —
  section 12, so linear rank-and-discard is not the only outcome the schema allows even though
  the overruling ladder itself models one timeline correcting itself, not two branches
  reconciling.
- **Tier 4 is a legitimate *permanent* mode of operation — the registry's "summer" — not merely a
  waystation on a promotion pipeline toward tier 1.** A tier-4 note that never gets promoted is
  not a failure of the layer; persuasive-only, never-verdicted precedent is exactly what D4's
  ladder calls it. This is a framing obligation on this document, not a mechanism: adopting a
  full seasonal design (scheduled de-formalization) is not recommended now — the falsification
  signals below exist to tell whether the substrate actually behaves seasonally before any
  mechanism is built for that.
- **The lineage-namespace promotion of `PRECEDENT_ROOT`** from a test-isolation flag (its only
  live use today, verified: `--root`/`PRECEDENT_ROOT` exist solely to keep tests and seeds off the
  live registry) **to a named parallel-lineage mode is a candidate follow-on for the operator
  gate, not a v0 requirement** — it presupposes fork-governance concepts this epic's own scope
  boundary (coordinator decision D8) puts out of reach.

**Falsifiable standing-caution signals, named in the form the standing quarterly task (T-349)
tracks. None requires new instrumentation — each is a pure consumer of `events.jsonl` or T-349's
own existing log.**

- **CAUTION-1 — cadence-aware structural-richness series.** Observable: T-349's existing
  quarterly structural-field count per surveyed convention. Once >= 3 quarterly points exist,
  classify the series monotonic-thickening / monotonic-thinning / **oscillating on a repeatable
  period**. Thickening supports state-formation; thinning supports the prosthesis reading (roadmap
  Part VI as written); oscillation supports a *third* reading Part VI's text does not name — the
  seasonal-alternation steelman above — so a **single** thinning observation must never be scored
  as the prosthesis reading winning.
- **CAUTION-2 — reopen-drama ratio.** Observable: `task_reopened` events plus their mandatory
  notes. Per quarter, the fraction of reopen notes citing a failure/incident versus routine,
  low-drama re-scoping. Rare and dramatic supports the Weberian reading (overruling as
  constitutional crisis); steady and undramatic supports the alien-coordination reading
  (overruling as a cheap, seasonal act).
- **CAUTION-3 — merge-versus-discard ratio.** Observable: tournament and (once live) adjudication
  verdicts. Per quarter, count verdicts that merge losing-branch insight into the promoted record
  (section 12's merge outcome) versus pure rank-and-discard. If the layer ships and never once
  merges, the schema imported the linear-succession assumption unexamined — evidence against the
  layer's *design*, not against its existence.
- **CAUTION-4 — ex-ante versus ex-post citation timing.** Observable: `DECISION:` note timestamps
  citing precedent versus `task_claimed` timestamps on parallel/forked task slots. Per quarter,
  classify citations on forked work as before-fork (precedent consulted to bind the choice) or
  after-verdict (precedent cited to rationalize a winner already picked by running both). Ex-ante
  supports state-formation; predominantly ex-post supports alien-coordination — the fork made
  consultation unnecessary.

## 14. What v0 does NOT do (kept current as its v1 equivalent)

So no downstream reader invents any of the following by assuming it is implied. The first eight
bullets are T-341's; the remainder are what T-344's research explicitly deferred, carried here so
this list stays the single place a reader checks before assuming a gap is closed. Every bullet
below was re-checked against this revision, not merely carried forward by inertia: none of them
was closed by the schema-v2/CLI-v2 doctrine sections 17-21 add, and section 14.1 below states
the schema-v2-specific items this same doctrine explicitly keeps out of scope.

- **No full retrofit of the ~30 existing P-numbers.** Forward-only, plus a small seed
  migration of exemplar precedents to validate the schema against real history rather than
  imagination; a full retrofit is a follow-on gated on the schema surviving adversarial
  verification.
- **No gate-mode conflict detection.** The registry-wide sweep is an on-demand pass (section
  9); the only check that runs unconditionally is inside `publish` itself, and it is
  mandatory-but-non-blocking, never a refusal.
- **No `state.json` write, by anyone in this layer.** Including backfilling the `P-023` gap
  described in the intro. The P-number ledger is a tier-2 constitutional record, mutated only
  through the §5A loop with human approval (`ORCHESTRATION.md:225-229`); a worker unilaterally
  writing it would be forging the constitutional ledger.
- **No session infrastructure of any kind.** `PR-NNN` is the citable unit across "sessions";
  the Claude hook `session_id` is rejected outright (section 5.1) and no substitute session
  concept is introduced.
- **Nothing from Part III (political economy) or Part IV (Westphalian/inter-org layer)** of
  the founding roadmap. This layer is Part II only.
- **No first-class `merge` verb.** An adjudicator may resolve a conflict today by publishing an
  ordinary successor record that cites both parents (`relations` type `supersedes` plus `cites`)
  — that outcome is already supported (section 12). A first-class merge verb would change the
  registry's contract and is not built here; it is a named candidate for a future operator-gated
  decision.
- **No automated judgment of genuineness.** This schema mechanizes *structural* compliance — a
  ratio field is non-empty, a scope is declared, a citation resolves. Whether a ratio is
  genuine, a scope honest, a citation apt, or a distinguish evasive stays a verifier-role
  judgment, permanently, by design (section 11 items 6-7). It is not a future automation target
  this document is quietly building toward.
- **No new duty in `claude.md` or `gemini.md`, still true in v1.** Restated from the header,
  and re-checked, not merely carried forward, for this revision: no agent is yet obliged to
  consult or cite the registry — or `INTERPRETIVE-CODE.md` — before deciding, and schema v2's
  new fields (`sources`, `validity_conditions`, `operation`, `interpretive_code_version`,
  section 17-19) change what a record must contain if published, not whether publishing or
  consulting is required of anyone. **Making either a duty would itself be an NLAH mutation** —
  the §5A loop plus the human gate that already covers "mutating `claude.md` or `gemini.md`"
  (`ORCHESTRATION.md:225-229`; the STATUS note at this document's own head) — and a worker task
  revising this contract cannot do that and does not claim to have done it.
- **No sixth conflict detector.** No citation-graph/cluster query (S-13), distinguish-density
  counter (S-05), scope-erosion counter (S-06), or distinguisher-identity-concentration counter
  (S-04, section 11 item 5) runs today — verified live, exactly five detector functions exist in
  `conflicts` (section 10, opening reconciliation). All four are v0-computable in principle;
  none is built. Not implied by section 10's discussion of them.
- **No tier-shopping or verifier-override-rate detector (S-10, S-11).** DEFERRED on a missing
  verdict-outcome code that does not exist on rejection events today (section 10.3); the interim
  is a human-judgment stopgap for the verifier, not a mechanism.
- **No ossification counter.** The `revisit_trigger` field is required and enforced at tiers
  1-3 (section 10.1); no detector yet reads a citation count against it, and deciding whether a
  free-text trigger's condition has been satisfied is not automated.
- **No fact-restatement fidelity tool (S-07).** The stdlib diff this would take is computable
  once both text fields exist; it is not implemented in the shipped CLI (section 11 item 4).
- **No interested-party check on `distinguishes`/`overrules` publication itself** (section 11
  item 3) — only on scope *confirmation*, which the `confirm` verb already refuses for a self-flip.
- **No fork-lineage or distinguish-then-fork-abandonment detector (signal S-14 in T-344).**
  Fork/branch identity over the task graph does not exist (`blackboard.json` is flat); building
  one is out of this epic's own scope boundary (coordinator decision D8), closer to market-layer
  plumbing. This is a **named open risk for the operator**, not a defect: appellate-style
  discipline has no purchase on a branch that never returns to the hierarchy, and only the
  operator or a future fork-governance mechanism can close that gap.
- **No temporal-clustering-after-cost-imposition detector (signal S-15 in T-344).** Needs event
  kinds (`precedent_cited`/`precedent_distinguished`) that do not exist yet, plus more event
  volume than the harness currently generates for statistical power; deferred for both reasons.
- **No wider quorum for tier-3 overruling.** Section 8's decision stands: equal adversarial
  weight suffices; a wider ("en banc") requirement is a named open alternative for the operator,
  not built.

### 14.1 What v1's schema-v2 doctrine additionally does not do

Named flat, per `docs/precedent-research/synthesis-v1-requirements.md`'s own out-of-scope
statement (its V1-54), so this stays the one list a reader checks before assuming any of the
following was quietly adopted alongside sections 17-21:

- **No NLAH mutation, no `state.json` write, no `ORCHESTRATION.md` edit, no full P-number
  retrofit** — all four restated from the bullets above and from v0's own list; schema v2 does
  not touch any of them.
- **No hook, no hard gate.** Conflict detection stays an on-demand pass (section 9, coordinator
  decision D6); the validity-conditions/decay pass (section 19.2) is the same class — read-only,
  on-demand, never a publish-time block beyond the mandatory-but-non-blocking checks already
  named.
- **Nothing from roadmap Parts III/IV.** Unchanged from v0's own boundary.
- **The Kimble external-fix-channel force input is NOT adopted.** An author-declared
  classification that would raise a record's own protection at issuance, with no confirming
  check, is a candidate amendment to the force computation (section 19.1) — not built in v1;
  forwarded to the epic join as a named candidate, not silently dropped.
- **Force-scaled factor-note specificity is NOT adopted.** No mechanical grader for "how
  specific must a factor note be, given the target's force" exists; forwarded to the epic join
  alongside the Kimble question, for the same reason section 11 items 6-7 leave materiality to a
  verifier rather than a script.
- **The conflicts-obligation question is named, not resolved** (section 21's closing paragraph
  already states it in full: whether any agent is yet obliged to run `conflicts` once a finding
  is discoverable). **The interested-party check's gap on `distinguishes`/`overrules`
  publication is unchanged** (section 11 item 3; section 21's closing paragraph names it again
  for continuity) — both forwarded to the epic join, neither settled by this revision.
- **Detector 2's `superseded` blind spot and detector 4's subject-agnostic scope collisions**
  (section 10.2's other named gaps, distinct from the `supersedes` tier-check fix section 16.1
  records) **are real, known, and NOT fixed by this epic** — only the two carried defects named
  in section 16.1 were in scope; these two remain forwarded to the epic join exactly as v0 left
  them.
- **No `merge` verb, no en-banc quorum, no lineage namespaces, no session infrastructure, no
  semantic-genuineness automation.** All five stand unchanged from v0's own list above; schema
  v2 introduces no new primitive in any of these five directions.

## 15. What this document extends, and does not restate

Rationale, measured: stacking a redundant verification layer on top of an existing one has
already regressed this class of system once — "+ system_prompt only" was the sole regression
among four single-component swaps, because "components interact non-additively... stacking
them spends turns on redundant re-checks" (`papers/agentic_harness_engineering.pdf:8` Table 3
RQ3a, p.9). Every mechanism in this document therefore names the existing record it extends,
below, and this document does not restate the cited rule's own text — read it at the cited
location.

| This document's mechanism | Extends (file:line) | What is NOT restated here |
|---|---|---|
| ratio/dicta structural split (section 4) | U2 note taxonomy, `ORCHESTRATION.md:69-77` | the four note prefixes and their meanings — stated once, at that location |
| overruling protocol (section 7) | the `reopen` verb, `ORCHESTRATION.md:58-67` and `.harness/bin/blackboard.py:470-517` | `reopen`'s own precondition/note/event/reset logic — this document only states the pattern it borrows |
| `confirm`'s self-flip refusal (section 6) | producer≠approver, `ORCHESTRATION.md:99` and `.harness/bin/blackboard.py:14-28` | the authorship-governs mechanics of P-011 itself |
| adjudication (section 12) | verifier rotation F6, `ORCHESTRATION.md:119-126`, and roadmap Part V principle 1, `docs/civilizational-roadmap-brief.md:92` | F6's own rotation rule and its worked counter-example; the founding premise's own text |
| the `P-NNN` citation token (section 5.1) | the P-number ledger, `state.json evolution.accepted_mutations` | the ledger's own schema or entries — a `P-NNN` token only points at it, and this layer never writes it |
| `cited_by` back-reference (section 7) | `agents.reputation`'s counter-update shape, `.harness/bin/blackboard.py:118-128` | that function's own logic — `cited_by` is a new, analogous, but distinct write-time side effect |
| every event kind this layer adds | the existing 30+-kind floor in `.harness/logs/events.jsonl`, written via `harness_common.log_event` (`.harness/bin/harness_common.py:106-110`) | the existing event schema or the guard/atomic-write mechanics it wraps |
| failure-mode detection signals (section 10) | the registry's existing `cites[]`/`revisit_trigger` fields plus `events.jsonl`'s floor — no new logging substrate for any of S-01 through S-15 | each signal's own formula and threshold — stated once, in `docs/precedent-research/synthesis-refinements.md`, not re-derived per row here |
| anti-evasion norms (section 11) | Rodriguez de Quijas/Broome v Cassell generalized (`docs/precedent-research/04-distinguishing-anti-evasion.md` §3) onto D4's overruling path (section 7); the interested-party check onto producer≠approver (P-011) | the cases' own holdings and reasoning — cited, not reproduced |
| standing caution (section 13) | roadmap Part V principle 4 ("watch for alien coordination") and the Part VII Graeber-Wengrow mandate, `docs/civilizational-roadmap-brief.md:117` | the book's and the corpus papers' own arguments — cited via `docs/precedent-research/08-graeber-wengrow-steelman.md`, not reproduced in full |

**This document's own verification is not exempt from the harness's general rules, and this
document does not restate those rules either.** It is a control-plane/contract-tier document,
so it gets full adversarial replay under proportional verification, not a brief README-tier
skim (P-024, `ORCHESTRATION.md:128-134`). Any acceptance command a verifier runs against this
document's claims — including the CLI's own test suite — must be the exact, layout-matching
command and must report a nonzero executed-test count before being trusted; exit 0 alone is
not evidence (P-025, `ORCHESTRATION.md:82-90`). This document does not self-verify: it hands
off to a distinct verifier exactly as any task does (`ORCHESTRATION.md:99`).

## 16. Reconciliation ledger for this revision

Every CLI behavior sections 10-13 rely on was run against the live `.harness/bin/precedent.py`
by this revision's author, not paraphrased from an earlier draft or from a prior verifier's note
— this is the replay this document's own rule (section 15's closing paragraph) demands of itself.
Commands and their exact observed output:

1. `python3 --version` → `Python 3.9.6` (the bare interpreter every engine on this bench runs).
2. `python3 .harness/bin/precedent.py --help` → subcommand list exactly
   `{publish,show,list,cite,confirm,conflicts}` — confirms section 14's "no `merge` verb" claim
   mechanically, not by assertion.
3. `python3 .harness/bin/precedent.py conflicts --help` → `conflicts [-h] [--json] [--root ROOT]`
   — unchanged, character for character, from section 9's own prior quote; zero drift.
4. `python3 .harness/bin/precedent.py conflicts` against the live registry → `CONFLICT
   detector=5 [dangling-citation] records=PR-001: PR-001 cites token 'P-023' which does not
   resolve` / `1 conflict finding(s) across 4 record(s)`, exit 3 — unchanged from T-346/T-347's
   prior runs; the layer still catches the P-023 gap it was built for.
5. `grep -n "^def detect_\|^def cmd_" .harness/bin/precedent.py` → exactly five `detect_*`
   functions (`detect_subject_ratio_conflicts`, `detect_overruled_cited_as_binding`,
   `detect_illegitimate_overrule_tier`, `detect_scope_overlap_conflicts`,
   `detect_dangling_citations`) and six `cmd_*` functions (`cmd_publish`, `cmd_show`, `cmd_list`,
   `cmd_cite`, `cmd_confirm`, `cmd_conflicts`) — grounds section 10's opening reconciliation
   finding ("no sixth detector exists") in a direct read of the file, not an inference.
6. `grep -n "citation_gap\|citation-completeness" .harness/bin/precedent.py` plus a direct read
   of `.harness/bin/precedent.py:619-705` (`cmd_publish`) → confirms the S-09 citation-completeness
   scan is real, shipped code (`# SDR-18: S-09 citation-completeness scan (mandatory,
   non-blocking)`), not a future requirement — grounds section 10.3's "DETECTED BY V0, SHIPPED"
   verdict in the source, not in a description of it.
7. `publish --tier 1 ... ` with no `--revisit-trigger`, against a throwaway `--root` →
   `refused: revisit_trigger must be non-empty at tiers 1-3 (SDR-17.4)`, exit 1. The same call
   at `--tier 4` with no `--revisit-trigger` and no `--scope` → `published PR-001`, exit 0, and
   `show` prints `"revisit_trigger": null`, `"scope_conditions": []` — both reproduced live for
   section 10.1's structural-half verdict, in a fresh throwaway registry, not reused from a prior
   verifier's fixtures.
8. Two tier-3 `publish` calls into one throwaway `--root`, same `subject`, overlapping
   `--scope "role:worker"`, divergent `--ratio`, no `--cites`/`--follows` between them → the
   second call prints `warning: citation-completeness gap -- active tier 1-3 record(s) sharing
   subject 'shared-subject' not cited: PR-001` (S-09 firing) and still exits 0 (publishes
   anyway); `conflicts --root <same>` then exits 3 with **two** findings —
   `detector=1 [subject-ratio-contradiction]` and `detector=4 [same-tier-scope-overlap]` — and
   `conflicts --root <same> --json` carries `"detector": 1, "name":
   "subject-ratio-contradiction"` and `"detector": 4, "name": "same-tier-scope-overlap"`
   verbatim. This single self-built scenario grounds section 10.2's S-08 verdict, section 10.3's
   S-09 verdict, and the exact detector `name` strings quoted throughout sections 10-11 — all
   from one fresh, throwaway registry this revision constructed itself, not from an inherited
   fixture.
9. `python3 -m unittest discover -s .harness/tests -p "test_precedent*.py" -v` → **`Ran 100
   tests in 5.131s`**, `OK` — run once before any edit in this revision and once after all edits
   above, both times identical: `Ran 100 tests in 5.131s`, 0 failures, 0 errors. Then
   `python3 -m py_compile .harness/bin/precedent.py` → exit 0. This revision changed
   `PRECEDENT.md` only; `.harness/bin/precedent.py`, every `test_precedent*.py` file, and the
   registry were not touched, and the identical test count before and after is the mechanical
   proof of that.
10. **Repair pass (verifier-build-c's rejection of the sections-10-13 draft): two `publish`
    calls into a fresh throwaway `--root`** — a tier-1 record (`--tier 1 ... --revisit-trigger
    never`), then a tier-4 record naming `--supersedes PR-001` — both `published PR-00N`, exit 0;
    a direct read of the first record afterward shows `"status": "superseded"`,
    `"superseded_by": "PR-002"`; `conflicts --root <same>` → `conflicts: 0 findings across 2
    record(s)`, exit 0. Grounds section 10.2's new Case C finding (the `supersedes` tier-bypass)
    and sections 1/3/7's new tier-symmetry-exception notes, in a registry this repair
    constructed itself, not inherited from the rejected draft.
11. **Repair pass: one `publish` call into a second fresh throwaway `--root`, tier 4, `--dicta`
    naming two unresolvable tokens in prose only** (no `--cites`/`--follows`) → `published
    PR-001`, exit 0; `cite --root <same> --record PR-001` → reports only the structured
    `tier_evidence` token, `PR-001 cites T-345: OK`, and nothing about either prose-only
    reference; `conflicts --root <same>` → `conflicts: 0 findings across 1 record(s)`, exit 0.
    Grounds section 10.2's new Case G finding (the `dicta`-blind resolver).

**No DEVIATION was found between this revision's new claims and the shipped CLI.** The three
DEVIATIONs this revision fixes are pre-existing documentary drift T-346 already found and
recorded as needs-repair against `PRECEDENT.md` (not against `precedent.py`, which is out of
this task's ownership): the stale `state.json:426` line citation in the intro (now a stable JSON
path, matching the fix its own neighbouring sentence already models); five path citations missing
their `.harness/` directory prefix, which the citation grammar's own resolver (section 5.1) would
otherwise flag `DANGLING`; and section 1's headline-rules row implying `--acknowledge-reliance`
takes an argument it does not (`store_true`; the refusal message, not the flag, lists the
citing records — section 7 already said this correctly, only the summary row disagreed with it).
None of the three changes a refusal, an exit code, a schema field, or a lifecycle transition.

### 16.1 v1 amendment ledger (T-357) — extends this same ledger, does not invent a second one

**The two carried defects named for this task, verified rather than assumed repaired.** The
board criterion for this task names two specific pre-existing defects as this task's to fix:
a stale line cite at the old `PRECEDENT.md:36` and five path citations missing their
`.harness/` prefix. Both were checked live against the current text before any v1 edit:
`grep -n -i "P-023" PRECEDENT.md` plus a direct read of the intro paragraph shows the
`state.json` reference already resolved to a JSON-path quote with no line number (the repair
the paragraph immediately above this one already records, from this same section's prior
revision); `grep -n '\`[a-zA-Z_./-]*\.py:[0-9]' PRECEDENT.md` shows every `precedent.py`/
`blackboard.py`/`harness_common.py` citation in the document already carries its `.harness/`
prefix — zero matches lacking it. **Verdict: both carried defects were already repaired by the
revision recorded immediately above (the prior task's own "Repair pass" items); this task found
nothing further to fix at either named location and makes no additional edit there.** Recorded
here, not silently assumed, per this task's own reasoning-record discipline.

**Every v0 rule this revision changes — old text, new text, and the authority for the change.**
Cited `V1-NN` ids are `docs/precedent-research/synthesis-v1-requirements.md` (T-352)
requirement ids, consumed as this task's own contract per that document's task-routing map
(its section 14); `doi:` tokens are `10.22201/iij.24487937e.2026.20.20316` plus section,
never the local path (intro, this document). DECISION, disclosed: the authority column below
cites A9.2/A9.5 where the true operative authority is one of the memo's six recorded
blindspot-interview answers rather than A1-A7 directly — the board criterion's own phrasing
("the coordinator decision by letter A1-A7") names the range that carries the substantive
doctrine, but `.harness/coordinator-decisions-addendum.md` runs A1 through A9, and citing the
letter that is actually load-bearing is more accurate than omitting it or misattributing it to
a nearby A1-A7 entry that did not decide the point.

| Rule amended | Old text (quoted) | New text | Authority | Classification |
|---|---|---|---|---|
| SDR-01, immutability (section 2.1) | "`relations`, `ratio`, `dicta`, `scope_conditions`, `declared_width`, `tier_evidence`, `cites`, `subject`, `title`, `issuing_task` are immutable after publication. The only fields any verb may mutate in place, exhaustively: `status`, `overruled_by`, `superseded_by`, `voided_by`, `cited_by` (append-only), `confirmation_status`, `confirmed_by`, `confirmed_at`, `narrowed_scope`, `confirmation_note`." | The immutable list gains `sources`, `validity_conditions`, `operation`, `interpretive_code_version`, and `schema_version`; the mutable list is unchanged; one narrow exception — the once-only schema migration may add exactly those four fields and flip `schema_version` 1→2 on a v1 record, altering no existing field's value (section 19). | `doi:...#3` via A1; migration authority A9.2 | reinterpretation-corrective-restrictive (V1-01) |
| SDR-10, citation grammar (section 5.1) | Seven exhaustive kinds: `PR-NNN`, `T-NNN`, `P-NNN`, `gen:N`, `agent:name`, `event:TS`, `path:lines`. | The grammar gains `doi:<DOI>[#fragment]` (external durable identifier, UNCHECKED by design — no network fetch exists in this harness's tool agency, and a DOI is durable precisely because it outlives local state) and `decision:T-NNN#anchor` (task-anchored recorded decision; the `T-NNN` half resolves against `.harness/tasks/`, the anchor is unchecked) — nine kinds, exhaustive. `session_id`'s rejection stands untouched. | `doi:...#3` via A1; A9.1; A9.5 | reinterpretation-corrective-extensive (V1-02) |
| SDR-17.8, tier symmetry excludes `supersedes` (sections 1, 3, 7, 10.2) | "`supersedes` carries neither refusal above — no tier check, no tier-4-target refusal," reproduced live from the shipped module's own documented DECISION: "`supersedes` is deliberately excluded: SDR-17.8 never applies a tier check to it." | `supersedes` gains the ORDERING half of tier symmetry — an acting record whose tier number is greater (lower authority) than the target's is a refusal. It does **not** gain the tier-4-target refusal: superseding replaces content rather than overturning force, and the merge outcome (section 12's "Merge as an adjudication outcome" paragraph) stays available to an equal-or-higher successor. | Not addendum-grounded — T-347 Case C's live-reproduced finding (section 10.2), verdicted at T-352; published as a registry record (the epic's own T-358 batch, `decision:T-339#SDR-17.8` anchored) | reinterpretation-corrective-restrictive (V1-03) |
| The reiterated flag, `docs/precedent-research/synthesis-refinements.md` R-2 (T-344) — never itself restated as a structural rule in this contract's v0 text | "Repeated confirmation becomes a separate, non-binding `reiterated` flag on tier-4 records — not a replacement of tier 3 and not a new binding tier … The flag changes nothing about bindingness." | Reiteration is a first-class, computed-on-read force-raising mechanism at every tier (section 19.1). R-1's floor (N=1 binds at tier 3, no threshold for ANY bindingness) and D1's rule (no reiteration ever promotes a tier-4 record to binding) are both explicitly preserved — what changes is the ceiling, not the floor. | `doi:...#5` via A2 (partial overruling, targeting `decision:T-344#R-2`) | determination at tier 1 (V1-05) |
| SDR-19.5 / SDR-26, single event sink (section 7's "into the **same** `.harness/logs/events.jsonl`") | "log ONE `precedent_published` event … into the EXISTING `events.jsonl` — no new log file, ever"; "a second log file is precisely the redundant re-verification layer C-2 warns against." | Unchanged for the live default root. When the root is **overridden** (`--root`/`PRECEDENT_ROOT` — every test and throwaway registry), events append to a sidecar `<root>/events.jsonl` inside that overridden root instead; the live substrate never gains a second log file. | Not addendum-grounded — T-346's measured test-event pollution of the live log, verdicted at T-352; not published as a registry record (amends build/test mechanics, not a norm of agent conduct — disclosed planner judgment, recorded here per that same judgment) | reinterpretation-corrective-restrictive (V1-06) |
| Relation type enum (T-344 field floor, exercised throughout sections 2.3, 7, 9-12 as `follows`\|`distinguishes`\|`overrules`\|`supersedes`\|`voids`) | Five relation types, no carrier for a reinterpretation or a valuation act. | The enum gains `reinterprets` and `revalues` — the relation carriers for the reinterpretation and valuation operations (section 18). Both reuse the existing relation machinery whole (target resolution, `cited_by` side effect, `below_target_tier` stamping); neither ever flips the target's `status`. | `doi:...#2` via A4 | determination — a new primitive on directive, not a re-reading of the old enum (V1-07) |

**Confirmed UNCHANGED, for citation completeness (not amendments, so no old/new pair applies):**
SDR-23 (`cite` stays read-only, logs no event — the force formula reads only data publication
and confirmation already write, so no cite event is ever needed); SDR-15 (the exit-code
contract is reused verbatim by every v2 verb, including the new `migrate`/`stale`); SDR-07
(equal adversarial weight still suffices for a tier-3 overrule — section 8's open question
stands, re-confirmed against fresh sources); and every SDR/S/R item not named above, en bloc.

## 17. THE HYBRID RATIO MODEL

**The question this section answers, stated as the external legal-theory input poses it: does
the author of a decision declare its own ratio, or does a later reader extract it?** Real
systems run both, and the answer this layer adopts is the hybrid the source names
(`doi:10.22201/iij.24487937e.2026.20.20316#3`, coordinator decision A1):

- **The author session declares its ratio at write time** — a structured field, general and
  abstract, with `scope_conditions` — as the record's **primary reference**. This is
  **institutional fixation**: the same move the source's own worked analogue makes (Mexican
  *tesis jurisprudenciales* — an organ fixes, in a separate document, what a decision's ratio
  is). Declaring narrows the interpretive range for every later reader; it does not settle the
  question permanently, because —
- **The successor retains the corrective path.** A successor may argue the declared ratio was
  merely *apparent* and the real ratio differs — but **only** by reinterpreting the **source
  materials that produced the decision**, with recorded reasoning, at sufficient authority
  level. This is the `reinterpretation` operation's `corrective-restrictive`/
  `corrective-extensive` subtype (section 18); it is never available by preference alone, and
  it is never available against a target whose tier is 4 (a persuasive, never-verdicted note's
  declared ratio is contested by disagreement or distinguishing, the same category-error
  boundary section 3's tier ladder already draws for overruling).
- **Correction without sources is mere disagreement, and is INVALID.** Second-degree documents
  — and every precedent record is one, section 21 — without their first-degree sources make
  founded overruling impossible: a corrective act that cites nothing beyond its own say-so is
  indistinguishable from a lower tier simply preferring a different outcome, which is exactly
  the evasion the tier ladder (section 3) and the anti-evasion norms (section 11, section 20)
  exist to close off.

**The mechanical consequence: every precedent record carries a mandatory `sources` field.**
`sources` (schema field #27, `docs/precedent-research/synthesis-v1-requirements.md` V1-11) is
the interpretive resources actually consulted in producing the decision — distinct from
`cites` (the general anchor list; overlap is legitimate and expected). It is required,
non-empty, on **every** publish, every tier, every operation type — not only corrective acts —
because a record's own reasoning should always be traceable to what it read. A publish whose
operation is a corrective reinterpretation, or which carries an `overrules`/`voids` relation,
and whose `sources` is empty is a **mechanical refusal**: this is A1's "correction without
sources is mechanically rejected" rule, and `docs/precedent-research/synthesis-v1-requirements.md`
V1-20 fixes its exact scope and refusal message for the CLI T-353 builds — this document states
the doctrine the CLI enforces; it does not claim the enforcement already ships, and where it
does, the shipped `--help` text is authoritative over any transcript this document could quote
(the same posture section 16 already takes toward v0's CLI).

**What counts as a source, and the delta discipline.** Any token the citation grammar accepts
(section 5.1, extended by section 16.1's V1-02 row): spec sections, prior `PR-NNN` records,
`T-NNN` tasks, `P-NNN` mutations, external docs by `doi:`, and the board's own recorded
decisions by `decision:T-NNN#anchor`. A corrective reinterpretation whose sources add nothing
the target's own `sources`/`cites` did not already consult is not refused — the addendum's own
caveat is that correction must rest on something not before the earlier decision — but it is
**warned**, non-blocking, per the same mandatory-but-non-blocking discipline SDR-18's
citation-completeness scan already uses (section 10.3): the tool produces the exhibit, the
reviewing verifier weighs it, never the reverse.

## 18. THE THREE OPERATIONS

**Any precedent-layer schema must keep three operations structurally separate**
(`doi:10.22201/iij.24487937e.2026.20.20316#2`, coordinator decision A4): a single "precedent"
blob conflating them makes disagreement unadjudicable, because a disagreement about *which
reading controls* and a disagreement about *how much force it carries* are different disputes
with different remedies, and a record that does not distinguish the two forces every reader to
guess which one is actually being contested.

1. **`determination`** — the recorded choice of what binds, at publish time, by the author.
   **Terminological caution, adopted explicitly:** this document says "determination," never
   "identification." Identifying a ratio implies it pre-exists and is merely recognized (the
   cognitivist thesis); determining implies the interpreter *chooses* it (the realist thesis).
   This layer adopts the realist reading precisely because a recorded choice must carry
   reasoning and be contestable — an "identified" fact does not need reasons; a "determined"
   choice does, and this schema is built to demand exactly that. Every ordinary publish that
   is not a reinterpretation or a valuation writes `operation.type = determination`; the field
   is always present — a record may never carry an untyped operation.
2. **`reinterpretation`** — what a ratio *means*, not what binds. Two subtypes:
   - `declarative`: fixing an indeterminate ratio for a new case. Applying a ratio to a new
     case this way is itself a consistent application — it feeds the qualifying-applications
     counter (section 19.1), it never zeroes it.
   - `corrective` (`restrictive` | `extensive`): arguing the previously declared ratio was
     merely apparent and the real ratio differs — the corrective path section 17 names, gated
     on sources, tier symmetry, and (per section 17) a refusal against a tier-4 target.
3. **`valuation`** — ascribing the ratio's institutional force. **This is metatextual: it
   changes force, not meaning.** Three named subtypes, all first-class recorded acts, never
   silent divergence: declaring a passage `obiter` rather than ratio (reclassifies a passage;
   the whole record's computed force is untouched — section 19.1); `error-in-pronouncement`
   (arguing the ratio was pronounced in error — requires the `reasoning_error` factor, the
   same mandatory-reasoning discipline section 7's overruling table already runs); and
   `context-change` (arguing the environment the ratio presupposed has changed — this is the
   recorded act a `validity_conditions` failure or a decay flag, section 19, *invites*, not
   the flag itself). `error-in-pronouncement` and `context-change` are the two subtypes with a
   whole-record force effect (section 19.1); `obiter` has none — it reclassifies one passage,
   and weighing that stays the reader's/verifier's job, exactly as `dicta` already is
   permanently persuasive-only (section 4).

**Operations never mix outside a fixed matrix.** A `determination` never carries a
`reinterprets`/`revalues` relation (that would be an untyped-blob evasion wearing a typed
label); a `reinterpretation` or `valuation` carries **exactly one** `reinterprets`/`revalues`
relation naming its target — never zero, never more than one. A record MAY combine a
corrective reinterpretation with an `overrules` relation on the same publish (the target is
both re-read and overturned in one act, the Morelle-shaped move section 11 already names by
citation); it may never combine a `determination` with either new relation type. This full
matrix — which relation each operation/subtype requires, which extra flags, which refusals —
is fixed in `docs/precedent-research/synthesis-v1-requirements.md` V1-14; this document states
the doctrine the matrix encodes and does not re-derive the matrix's own cells.

**Neither `reinterprets` nor `revalues` ever flips a target's `status`, and neither ever
requires `--acknowledge-reliance`.** They overturn nothing — the valuation force effect is
computed on read (section 19.1), never by a status transition. This is the structural line
that keeps section 2.3's two independent lifecycles independent of a third: `status` moves
only on `overrules`/`supersedes`/`voids`; `confirmation_status` moves only on `confirm`; force
moves on neither, it is a pure read-time computation over whichever operations and relations
already published.

**Adjudication tags its own operation, and the tag is a substantive choice, not a formality.**
An adjudication record (section 12) tags `operation.type = determination` — a forward-looking
choice of which of two live readings controls now, never a claim that the losing reading was
defective from birth. The distinction matters because it is exactly the line section 11's
Rodriguez de Quijas/Broome v Cassell routing rule already draws: an adjudicator who instead
means "the losing record's reasoning was wrong" is not adjudicating a peer conflict, they are
overruling, and the act must be typed and routed as `reinterpretation`/`corrective` or
`overrules` at the losing record's own tier, never smuggled through as a plain determination.
An adjudicator who genuinely picked a winner between two readings that were each defensible at
publication — the ordinary case — tags `determination` and nothing more is required.

## 19. GRADED FORCE, DECAY, AND VALIDITY CONDITIONS

### 19.1 Graded force, distinguished from `authority_tier`

**`authority_tier` is unchanged and remains the ISSUANCE authority** — how much adversarial
process a decision survived at birth (section 3). **A single verdicted decision still binds at
issuance; no reiteration count is required for bindingness, at any tier.** This floor does not
move.

**`force` is a new, separate, computed-on-read value — never stored** (coordinator decision
A2: "storing it would mutate published records continuously, violating immutability;
computed-on-read also makes the force formula itself amendable without touching records"). It
is a graded spectrum, total order high to low: `settled` > `binding` > `reiterated` >
`persuasive` > `none`. `none` is a dead record (`status != active` — its history stays
citable, it carries no force). `binding`/`persuasive` are exactly D4's old binary, now the
*default* level within each authority band rather than the whole story. `settled` (tier 1-3)
and `reiterated` (tier 4) are the new bands **reiteration adds on top of issuance**: force is
graded, not binary, and **reiteration raises force** (*jurisprudencia constante*; also
observed de facto in common law via accumulating citations) — this is the addendum's section 5
doctrine, adopted by coordinator decision A2.

**What reiteration changes is the ceiling, not the floor.** A tier 1-3 record with at least
three qualifying, non-contrary applications by a distinct-identity author computes `settled`
(above plain `binding`); a tier-4 record with the same count computes `reiterated` (above
plain `persuasive`) — but no amount of reiteration ever moves a tier-4 note into binding:
publication at a verdicted tier stays the only route to bindingness (D4 is untouched). A
contrary or interrupting application — an equal-or-higher-tier `distinguishes`, or a corrective
`reinterprets` — **zeroes** the counter; it never merely skips an increment, the same discipline
Mexico's *cinco sentencias no interrumpidas* rule enforces. This partially overrules, with
reasoning, `docs/precedent-research/synthesis-refinements.md`'s R-2 framing of a "reiterated"
flag as non-binding decoration — section 16.1's ledger records the amendment and its authority
in full; T-344's original argument (no N>1 threshold should be required for ANY bindingness) is
expressly preserved, because the addendum's doctrine does not require one either.

**A weakening valuation (`error-in-pronouncement` or `context-change`, section 18) renders a
tier 1-3 record's force `persuasive` instead of `binding`/`settled`** — but only when recorded
at equal-or-higher authority than the target (the same tier-symmetric discipline that protects
every other force-affecting act in this document); a below-target-tier valuation is recorded
and rendered, but has no effect on the target's computed force, the identical persuasive-only
stamp section 6's below-target-tier distinguish already carries.

### 19.2 Decay: the activity clock, flagging only

**"The ratio was created long ago and the context has changed" is a recognized
force-weakening technique this layer must be able to name mechanically, not only rhetorically**
(the addendum's own context-drift caution, section 6 DIRECTIVE, coordinator decision A5). In
this harness the changing context is the codebase/spec state, and the clock that measures
staleness is the **registry's own activity**, never wall-clock and never the raw event log:
this bench has published a twenty-task epic and several records inside a single day, so a
wall-clock window would measure the burstiness of operator sessions, not neglect by the
polity; the event log is, independently, the substrate the v1 amendment ledger's events-sink
fix (section 16.1) exists to unpollute, so it is disqualified as a clock input on its own
measured evidence. The clock is instead **the count of later-published records in the same
registry root** — a pure, unpollutable, test-isolated observable.

**A decay candidate is FLAGGED, never auto-expired and never silently demoted.** An active
tier 1-3 record with no citations at all, once enough later records have published without
ever citing it, becomes a **reconsideration candidate** — nothing about its `status` changes,
and its computed force is **not** lowered by the flag itself. The force drop to `persuasive`
happens only through a **recorded** `valuation`/`context-change` act (section 18, section
19.1) that the flag *invites* — never as a side effect of the flag being raised. This is the
harmonization this document adopts between two binding inputs that would otherwise conflict:
coordinator decision A2 says decay "flags for reconsideration; it never auto-expires a record";
coordinator decision A4 says every metatextual weakening is "a first-class recorded act, never
silent." A mechanism that silently computed a lower force for an uncited record would itself
be the silent weakening A4 forbids, so the machine only ever flags, and a recorded act does the
weakening — at every tier uniformly, since nothing below a record's own tier could record an
effective weakening against it regardless (tier symmetry, section 19.1). Tier-4 records are
never decay-flagged: tier 4 is a legitimate *permanent* mode of operation (section 13's
steelman already names this — "the registry's summer"), and flagging every never-cited note
would flood the pass with exactly the noise a selective mechanism exists to refuse.

**This periodic pass is a sibling read-only verb, not a sixth `conflicts` detector** — the same
on-demand, never-a-gate discipline section 9 already runs, extended to a different finding
class: `conflicts` detects record-vs-record contradiction and routes to adjudication (section
12); this pass detects record-vs-ENVIRONMENT drift and routes to reconsideration. Its exact
surface, exit codes, and finding-line format are fixed in
`docs/precedent-research/synthesis-v1-requirements.md` V1-34 for `.harness/bin/precedent.py`
(T-354) to build against; this document names the doctrine the verb enforces and does not
claim the verb already ships.

### 19.3 Validity conditions versus scope conditions

**Every binding-tier record already declares two different kinds of condition, and v0 named
only one of them.** `scope_conditions` (section 6, unchanged) is the class of CASES a ratio
applies to — roles, task classes, paths-as-jurisdiction, tiers. `validity_conditions` (schema
field #28, new) is the facts about the ENVIRONMENT a ratio presupposes — file paths, tool
versions, board mechanics, repo state (the addendum's own enumeration, section 6 DIRECTIVE,
coordinator decision A5, verbatim).

**The one-sentence discriminating test an author or a reader applies to any candidate string:**
if the string is true or false about the repository *today*, independent of any case being
decided, it is a validity condition; if the string can only be evaluated against a candidate
case — "does this rule govern that act?" — it is a scope condition. ("`blackboard.py` defines a
`reopen` verb acting only on done/failed tasks" is true or false today, independent of any
case: validity. "role:worker invoking `reopen` on a done task" is evaluable only against an
act: scope.) `validity_conditions` is required, non-empty, at tiers 1-3, exactly parallel to
`scope_conditions`'s own tier split (section 6); optional, default empty, at tier 4.

**The periodic pass (section 19.2's sibling verb) flags records whose `validity_conditions` no
longer hold as RECONSIDERATION CANDIDATES — never auto-expiry, at any tier, ever.** This is the
same discipline decay already runs (section 19.2), applied to a different failure signal:
where decay measures neglect (nobody has cited a record), a validity-condition failure measures
drift (the environment the ratio presupposed has changed out from under it) — both route to
the same recorded response, a deliberate `valuation`/`context-change` publish, an overruling,
or a documented decision to leave the record standing; neither ever flips `status` on its own.

## 20. THE FACT-RE-DESCRIPTION CONSTRAINT

**This section extends section 11's anti-evasion norms; it does not restate or duplicate
them.** Section 11 already requires a `distinguishes` relation to carry non-empty
`distinguishing_facts` (signal S-01, "formal-completeness," DETECTED BY V0) — but *non-empty*
constrains only whether a distinguishing move says anything about facts at all, not whether
what it says is doing legitimate work. The addendum's own diagnosis of why that gap matters
(`doi:10.22201/iij.24487937e.2026.20.20316#7`, coordinator decision A6) is the reason this
constraint exists as its own named section rather than a footnote to S-01:

**"Following precedent" is never mechanical, because material facts can be re-described.**
Internal and external distinguishing both operate literally by changing the description of
facts — that is what distinguishing *is*. Anti-evasion design must therefore constrain the act
of *fact re-description itself*, not merely the presence of a rule citation: a lower tier that
wants to evade a binding ratio can always find *some* factual difference to point to (any two
decisions differ in some respect), so requiring a citation of facts without requiring that the
citation be *material* leaves the evasion fully open — the same failure mode section 11 already
names via Duncan Hosie's "Factual Revisionism" vocabulary (substitution, rhetorical
naturalization, evasion, nominal acceptance): a diff of the *words* cannot, by itself, tell
legitimate narrowing from quiet reversal.

**The constraint this section adds, on top of S-01's non-empty check: every distinguishing move
must state (a) WHICH material facts differ from the target's own facts, and (b) WHY that
difference is material — i.e., why it is the kind of difference that, given the target's own
underlying ratio, ought to change the outcome.** This is a protocol rule a verifier checks by
reading the text, not a structural parser check — materiality is, per section 11 item 6, a
verifier/adjudicator judgment the schema does not automate and does not claim to. What the
schema *can* and does check mechanically remains exactly S-01's non-empty precondition and
S-02's authority-symmetry stamp (section 11); what this section adds is the standing
**reading** a verifier applies to that text once it exists: a `distinguishing_facts` entry that
names a difference without saying why it matters, or that argues the target's *reasoning* was
wrong rather than that the *facts* differ, fails this constraint and, per section 11's own
routing rule, the second failure mode routes through the overruling protocol (section 7) at
the target's tier — it is not an ordinary distinguish at all, however it is labeled.

**Where computable, the S-signal list gains a check on fact-re-description discipline** — this
is the addendum's own instruction (coordinator decision A6, last sentence), and this document
does not invent a new mechanical grader beyond what section 11 already names as buildable: S-07
(the fact-restatement fidelity diff, verdict PARTIAL v0, not shipped) is the existing candidate
whose purpose this constraint sharpens — it would flag a distinguish whose "material facts"
were never asserted before the act of distinguishing itself, the textual symptom of a
fact-re-description move manufactured for the occasion rather than found in the record. This
section does not change that signal's shipped status; it names why the signal matters more
precisely than section 11's own text did before this revision.

## 21. THE REALIST FRAME

**Records are dispositions, not norms — the norm is what a successor extracts.** A disposition
is the text; a norm is the meaning interpretation produces from it (the addendum's core
postulate, `doi:10.22201/iij.24487937e.2026.20.20316#1`, section 1). Every handoff, precedent
file, and task note in this harness is a disposition; the norm any later session applies is
what that session's own interpretation extracts from it — writing a clearer disposition reduces
but never eliminates the gap, because indeterminacy is structural (vagueness, ambiguity,
unforeseen application contexts, competing methods, competing background theories). This is
why `ratio` is a recorded **determination** and not a recognized fact (section 18's
terminological caution) — a determination is exactly a session's interpretive act on a
disposition, made explicit and contestable.

**Precedents are second-degree documents.** The recorded outcome of interpreting is itself a
document that can be reinterpreted: a precedent record is a *product* of a prior interpretation
of other materials (specs, prior precedents, code, task history), never a first-degree
disposition in its own right. This is exactly why section 17's corrective path requires
`sources` — a second-degree document without its first-degree sources on record makes founded
overruling impossible, because there is nothing beneath it for a corrective act to
reinterpret. Legislation-like inputs (specs, requirements documents) are first-degree; every
`PR-NNN` record is second-degree, and this document — a contract *about* second-degree records
— inherits the same status one level up: it is itself reinterpretable, per its own section 16
ledger's discipline, and does not claim otherwise.

**No mechanism in this layer may presuppose recoverable collective intent.** The "will" of a
multi-agent council, an epic, or a coordinator's dispatch is not a discoverable fact — appeals
to it are normative moves dressed as descriptions, not descriptions. This is why every
interpretive act this schema mechanizes records **declared** reasoning only: a `ratio`, a
`factor`, a `valuation-note`, a `distinguishing_facts` entry are all first-person, contestable
statements of what an agent or session concluded and why — never a claim about what "the
harness really meant." A future mechanism proposal that presupposes recoverable collective
intent — for example, inferring a lineage's "true purpose" from its aggregate history rather
than from what any single session actually recorded — would violate this frame on its face, and
this document names that as a standing design constraint, not merely a caution (coordinator
decision A7; `doi:10.22201/iij.24487937e.2026.20.20316#7`).

**Legal certainty is not a property texts have; it is an institutional achievement.** "Citizens
know the norms that bind them" — the universal-guarantee framing the addendum's source
critiques — is not something a well-written disposition delivers on its own, given structural
indeterminacy. It is produced, when it is produced at all, by a *disciplined, auditable
interpretive process*: a fixed, versioned interpretive code (`INTERPRETIVE-CODE.md`, cited by
name and version only — this document does not enumerate its rules, which are that document's
own artifact); a citation grammar that distinguishes resolvable references from dangling ones
(section 5); a tier ladder keyed to observable adversarial process, not to rank (section 3); and
a reconciliation ledger that records every amendment's old text, new text, and authority
(section 16, extended by 16.1). **This is exactly this layer's value proposition, stated
plainly and not softened: not that agents will always agree, but that when they disagree, the
disagreement is auditable.** Section 13's steelman already asks whether a cheap-forking actor
class needs this at all; this frame is the answer to a narrower question the steelman leaves
open — *if* the layer exists, what discipline makes its certainty real rather than performed —
and the answer is process, not text.

**What this frame forecloses for future mechanism design, named so nobody has to rediscover it
by building the wrong thing first:** no signal, detector, or adjudication step in this document
or any future revision of it may compute a verdict from an inferred "true intent" behind a
decision, a lineage, or an epic; every such mechanism must instead read what was actually
recorded — `ratio`, `sources`, `factors`, notes — and treat the absence of a recorded reason as
exactly what it is, an absence, never a fact to be inferred around. Two open questions this
frame raises but does not resolve — forwarded, not silently dropped, the same posture section 8
already models for the tier-3 quorum question: **whether any agent is yet obliged to run
`conflicts` once a finding is discoverable** (the Mexican mandatory-once-denounced model versus
this layer's current silent-discretionary default — `docs/precedent-research/
10-horizontal-peer-precedent.md` §4, forwarded to the epic join, T-362); and **the interested-
party check's own gap on `distinguishes`/`overrules` publication** (section 11 item 3 already
names this; it remains open in v1, forwarded to the same join). Both are named here, not
resolved, because resolving either would itself be a mechanism-design decision this worker task
does not have standing to make.
