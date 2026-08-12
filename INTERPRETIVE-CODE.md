# INTERPRETIVE-CODE.md — The Serenissima Shared Interpretive Code (v1)

Version: v1

> **Summary**: every registry record (`PRECEDENT.md`) is a *disposition* — text. What a
> reading agent extracts from it is a *norm* — meaning. Human interpreters compose the rules
> that bridge disposition to norm ad hoc and privately; that privacy is the deep source of
> interpretive divergence. Agents do not have to accept that cost. This document is the
> interpretive code: a finite, explicit, versioned set of translation rules (how to read a
> ratio), preference rules (how to rank competing readings), and procedure rules (the order in
> which the first two apply, plus the duties that keep the whole thing auditable) — identical
> for every session, every engine, every role. It does not make interpretation determinate:
> indeterminacy here is structural, not an engineering defect this document can remove. What
> it does is make divergence **auditable** — a disagreement between two sessions decomposes
> into exactly one of three distinguishable causes (section 6) instead of one undifferentiated
> fog.

> **STATUS.** This document is constitutional-tier (coordinator decision A3) and amendable
> only through the overruling-grade protocol (section 7) — never by ordinary edit. It is
> **not yet incorporated into `claude.md` or `gemini.md`**: no agent is presently under a
> documented duty to consult it, apply it, or cite it before deciding or before publishing to
> the registry. See section 8.

## 1. Provenance, and how this document cites its own authority

The rules below implement coordinator decision **A3** ("NEW PRIMITIVE: the shared interpretive
code"), issued against an operator-supplied legal-theory addendum:

> Mario Armando Sandoval Islas, "Distinciones entre la interpretación de disposiciones
> legislativas y la interpretación de precedentes," *Problema. Anuario de Filosofía y Teoría
> del Derecho* (20), IIJ-UNAM, 2026. DOI `10.22201/iij.24487937e.2026.20.20316`. The paper
> works within the Genoese school of legal realism (Tarello, Guastini, Chiassoni).

This document's short form for that source is **"the addendum."** The addendum's local file
lives under `docs/`, which is gitignored (`.gitignore:33`) and therefore dangles for any reader
who clones this repository without the operator's local corpus — so every citation to it below
uses the DOI plus a section number, in the same `doi:` token grammar the registry itself
resolves external identifiers with: **`addendum §N` means
`doi:10.22201/iij.24487937e.2026.20.20316#N`**, never a local path. The addendum's own
instruction line, quoted once here because it is this whole document's mandate: *"Treat it as
binding design input where marked DIRECTIVE, and as research context otherwise. Where this
addendum conflicts with prior assumptions in the roadmap, this addendum prevails."* Its section
4 is marked DIRECTIVE; that section is this document's direct authority.

Coordinator decisions are cited below by their bare label (`A1`–`A9`) only. The memo that
records them is, like the addendum's local copy, not a tracked artifact of this repository — so
for the identical dangling-path reason, no citation below points at it by path. `PRECEDENT.md`
and `ORCHESTRATION.md` are cited by document name and section heading, never by line number: a
line-numbered citation into a document that is still being revised is exactly the kind of
citation that goes stale first (a prior revision of this layer was caught doing exactly that).
This document does not restate any rule that already lives in `PRECEDENT.md` or
`ORCHESTRATION.md` — it cites them. The measured basis for that discipline: stacking a layer
that re-performs verification another layer already does regressed the harness's own corpus
system by 2.3 percentage points — the only regression among four single-component swaps tested
(`papers/agentic_harness_engineering.pdf`, Table 3, RQ3a). Extending a layer, not duplicating
it, is the cheaper and the tested design.

Per-rule citations in section 4 below reference only sources durable under those same rules:
the addendum (by DOI and section), coordinator decisions (by bare label), and `PRECEDENT.md`
(by section heading). The rules' normative content is fixed content, owed in full to this
document by the epic's own build order; the citations attached to each rule are this
document's own choice of durable authority for that content, not a restatement of the rule
itself.

## 2. Why a shared, explicit code replaces private judgment

Interpretation is the operation that leads from a disposition (the text) to a norm (the
meaning produced by reading it). The recorded outcome of interpreting — a precedent record — is
itself a document that can be reinterpreted: precedents are **second-degree documents**,
products of a prior interpretation of other materials (addendum §1). There is no single
correct meaning of a disposition in the abstract: a meaning is always relative to (a) an
interpretive code — the translation, preference, and procedure rules a reader applies — and
(b) the interpretive resources fed into those rules. Different codes over the same disposition
yield different, equally defensible readings (addendum §1). Indeterminacy of this kind is
structural: vagueness, ambiguity, unforeseen application contexts, competing methods, and
competing background theories all produce it, and no amount of better drafting removes it
(addendum §1).

Human interpreters compose their interpretive code ad hoc and privately — each reader's literal/
purposive/systematic mix, their ranking of competing readings, their sense of which rule applies
first, lives in that reader's head and changes reader to reader. That privacy is the deep source
of interpretive divergence among human interpreters (addendum §4). Agents publishing to and
reading from this repository's registry need not pay that cost: the code can be written down
once, explicitly, and applied identically by every session. That is the whole of what this
document is for.

## 3. The three rule classes

Per coordinator decision A3 and addendum §4, this code has exactly three rule classes:

- **translation** — how to read a ratio: which method (literal, purposive, systematic) applies,
  in what order, against what materials.
- **preference** — how to rank competing readings against one another, when more than one
  survives translation.
- **procedure** — the order in which translation and preference rules apply, and the duties
  (citation, amendment) that make the whole code auditable rather than merely aspirational.

## 4. The rules — IC-01 through IC-13

Every rule the addendum's shared-interpretive-code primitive and coordinator decision A3
require is listed below, exhaustively: no rule is added beyond this list, and none of these
thirteen is omitted.

| ID | Class | Normative content |
|---|---|---|
| IC-01 | translation | Read a ratio's words literally first — in their ordinary technical meaning, against the record's own text — and if the literal reading decides the question with no residual indeterminacy, stop there (addendum §4's fixed order: literal, then purposive, then systematic; coordinator decision A3). |
| IC-02 | translation | When the literal reading is indeterminate — vague, ambiguous, or silent on the application context — read the ratio purposively against the record's own recorded materials (its `sources`, its `revisit_trigger`, and its issuing task's recorded reasoning), never against presumed unrecorded intent (addendum §7: the "will" of a multi-agent council is not a discoverable fact — a purposive reading works from what was recorded, not from what is imagined). |
| IC-03 | translation | When literal and purposive readings remain indeterminate or conflict, read systematically: against the record's own `relations`, the other active records sharing its `subject`, and the tier ladder, preferring whichever reading leaves the fewest active records in contradiction (addendum §1's systematic method; coordinator decision A3). |
| IC-04 | translation | The record's text is a disposition; what binds is the norm the reading produces. A reader applying a ratio states which rule — IC-01, IC-02, or IC-03 — produced the reading it is applying (addendum §1: disposition vs. norm; precedents as second-degree documents). |
| IC-05 | translation | Read scope claims at their confirmation state: an unconfirmed `scope_conditions` / `declared_width` carries persuasive strength regardless of the record's authority tier, and is never read as though it were already confirmed (`PRECEDENT.md`, section 6, "Distinguishing and scope conditions: declared until confirmed"). |
| IC-06 | preference | Between competing readings supported by different records, the reading supported by the higher computed force prevails; at equal force the conflict routes to the adjudication protocol, never to silent private choice (coordinator decision A2 on graded force; `PRECEDENT.md`, section 12, "Adjudication: no single agent decides alone"). |
| IC-07 | preference | Between competing readings of one record's own ratio, at equal support, prefer the narrower reading; a wider reading is a reach claim and stays at persuasive strength until confirmed — the same asymmetry that already governs `scope_conditions` (`PRECEDENT.md`, section 6). |
| IC-08 | preference | A reading recorded in a later, active record that expressly `follows` or `reinterprets` a target — an acknowledged lineage — is preferred over a fresh, unrecorded reading of the original (coordinator decision A4 on typed operations; addendum §5's reiteration through acknowledged, recorded applications). |
| IC-09 | preference | Reading a record's declared ratio as merely apparent is never available by preference alone: it requires the recorded corrective operation, with sources, at sufficient authority; a reader who cannot or will not publish that act applies the declared ratio as written (addendum §3; coordinator decision A1). |
| IC-10 | procedure | Order of application: IC-01, then IC-02, then IC-03, stopping at the first rule that yields a determinate reading; any readings still competing after that rank by IC-06, then IC-07, then IC-08; IC-09 constrains the whole sequence throughout (addendum §4: "procedure rules (the order of application)"; coordinator decision A3). |
| IC-11 | procedure | The citation duty: every interpretive act recorded in the registry carries an `interpretive_code_version` field naming the code version it applied. A record that cites a version other than the one currently in force is not thereby invalid: consult this file's version history for the text of the version it cites, and treat the mismatch as diagnostic evidence of possible divergence (section 6), never as a defect in the citing record (addendum §4: "Every interpretive act cites the code version used"; coordinator decision A3). |
| IC-12 | procedure | Divergence diagnosis precedes dispute: before treating a disagreement between two sessions as a substantive conflict, establish which of three failure modes produced it — a different disposition was read, a different code version was cited, or the same code version was applied differently — and route only the third to adjudication as a genuine interpretive conflict (addendum §4's three distinguishable failure modes; coordinator decision A3). |
| IC-13 | procedure | Amendment route: this code is constitutional-tier and amendable only through the overruling-grade protocol — a published registry record, at tier 1 or tier 2, that names the IC-NN rules it changes and the version it bumps to. No ordinary edit to this file is a valid amendment, regardless of who makes it (addendum §4: "amendable only through the overruling-grade protocol"; coordinator decision A3). |

## 5. The citation duty, and the version string

IC-11 above is a rule this document enforces on every reader, not a description of good
practice: **every interpretive act recorded in the registry must carry an
`interpretive_code_version` field naming the code version applied.** This is not optional
colour on the surrounding prose — it is the mechanism that makes section 6's diagnosis possible
at all. A registry record with no version citation, or a version citation this document cannot
resolve, is exactly the "one fog" this whole primitive exists to split apart; a version
citation that resolves is the raw material section 6's diagnosis consumes.

**When a reader encounters a record whose cited version no longer matches this file's current
`Version:` line:** the record is not thereby invalid, and its ratio is not thereby unreadable.
The reader consults this file's git history for the version the record cites, reads the record
under that version's rules, and records the version mismatch itself as diagnostic data — a
candidate instance of the second failure mode in section 6 — never as a defect in the record
being read. Divergence is auditable precisely because the superseded version's text is not
discarded; git history preserves every version this file has ever carried.

**Machine-readable form.** This document declares its own version on exactly one line, placed
before the first `##` section heading, matching the pattern `Version: v` followed by digits —
for this release, the line at the top of this file reads `Version: v1`. A tool reads the
version as the first (and only) match of that pattern over the file; no markdown parsing is
required. Every registry record's `interpretive_code_version` field cites a value of this same
form (`v1`, `v2`, …), and that field is how a record ties itself to a specific, resolvable
revision of this document.

## 6. The diagnostic payoff, stated plainly

This is the addendum's own claim for why the shared code is worth building, quoted because it
is the standard this document is held to: two sessions that disagree either **read different
dispositions**, **used different code versions**, or **applied the same code differently** —
"three distinguishable failure modes instead of one fog" (addendum §4). Concretely:

1. **Different dispositions read** — the two sessions consulted different source text (a
   different record, a different revision of a spec, a different snapshot of the repository).
   Nothing about this document resolves that disagreement; it is not an interpretive-code
   question at all.
2. **Different code versions cited** — the two sessions' `interpretive_code_version` fields
   differ. The fix is mechanical: resolve both versions' text (section 5) and check whether the
   disagreement survives once both readers apply the same version.
3. **The same code version applied differently** — both sessions cite the same version, read
   the same disposition, and still disagree. Only this case is a genuine interpretive conflict
   under this code, and only this case routes to the adjudication protocol (`PRECEDENT.md`,
   section 12).

Splitting the fog into these three does not resolve any of them by itself — case 3 is still a
real disagreement after the split, and case 1 may still require its own adjudication over which
disposition governs. What the split buys is scope: a disagreement is no longer investigated as
one undifferentiated failure of "the interpretation," it is investigated as one specific,
narrower question with its own, smaller evidence set.

## 7. Amendment route

This code is constitutional-tier material (coordinator decision A3; addendum §4: "The code
itself is amendable only through the overruling-grade protocol"). The only valid amendment
route is: a published registry record, at authority tier 1 or tier 2, that names every IC-NN
rule the amendment changes and states the version number this file bumps to as a result. A
hand-edit of this file with no such record — however small, however well-reasoned in a commit
message or a task note — is not an amendment; it is a forgery of a constitutional artifact, and
a reader who finds this file's content changed with no corresponding tier-1/2 record citing the
change should treat the file's current text as unauthoritative until that record is produced
(IC-13). This mirrors, for this document, the same discipline `ORCHESTRATION.md` states for
`claude.md` and `gemini.md`: a constitutional artifact is mutable only through its own gated
loop, never by ordinary edit (`ORCHESTRATION.md`, section 6, "Governance: evolving the harness
itself").

## 8. What this document does NOT do

So that no downstream reader assumes a gap is closed by implication:

- **It does not eliminate indeterminacy.** Indeterminacy is structural (section 2; addendum
  §1). This document making divergence auditable is not the same claim as this document making
  interpretation determinate, and it does not make that claim anywhere above. A revision of
  this file that promised determinacy would misstate its own theory.
- **No agent is presently obliged to consult, apply, or cite this code.** This document exists
  and states rules; it does not, by existing, place any session under a duty to read it before
  deciding, to apply it before publishing to the registry, or to populate
  `interpretive_code_version` correctly rather than carelessly. It states what the rules are,
  not that anyone is currently bound to follow them.
- **Incorporating such a duty is out of scope for this epic.** Writing a consult-and-cite
  obligation into `claude.md` or `gemini.md` would itself be an NLAH mutation, and this
  document does not perform one: that requires the harness's own §5A loop plus the human gate
  that already covers mutating either NLAH (`ORCHESTRATION.md`, section 6, "Governance:
  evolving the harness itself"; `ORCHESTRATION.md:225-229`). No worker task, this one included,
  can substitute for that gate, and this document does not claim to have done so.
- **It does not validate a registry record's cited version against its own current text.**
  Whether a given `interpretive_code_version` value resolves to a version of this file that
  ever existed is a question for the tooling that reads the registry, not for this document —
  this file only fixes what the version string means and where it is declared (section 5).
- **It does not resolve which of the three failure modes in section 6 produced any particular
  disagreement.** It states the taxonomy; applying it to a live disagreement is the reader's or
  the adjudicating verifier's act, not a mechanical output of this file.
