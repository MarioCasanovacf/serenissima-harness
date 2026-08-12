# Coordinator Amendment Memo — Legal-Theory Addendum Intake (Precedent Layer v1)

Author: coordinator (main session, Fable 5). Date: 2026-08-11.
Trigger: operator-supplied addendum at `docs/serenissima-addendum-legal-theory.md`
(source: Sandoval Islas, *Problema* 20, IIJ-UNAM 2026, DOI 10.22201/iij.24487937e.2026.20.20316;
Genoese school: Tarello, Guastini, Chiassoni). The addendum is marked by the operator as
BINDING DESIGN INPUT where tagged DIRECTIVE and states it prevails over prior assumptions.
Under PRECEDENT.md's own ladder that makes its directives TIER-1 (operator) authority.

Discipline note: everything here that amends a previously recorded decision MUST be
published through `precedent.py` as a recorded overruling/amendment with reasoning —
the layer governs its own amendment. No silent divergence.

## A1. VALIDATES D1 (author-declared ratio) and completes it into the hybrid

The addendum (section 3) confirms author-declaration at write time as the primary reference
(institutional fixation, cf. Mexican tesis jurisprudenciales) AND mandates the successor's
corrective path: a successor may argue the declared ratio is apparent/incorrect ONLY by
reinterpreting the source materials that produced the decision, with recorded reasoning, at
sufficient authority level. Correction without sources is invalid.

DECISION: schema v2 adds a MANDATORY `sources` field (the interpretive resources actually
consulted: spec sections, prior PR-IDs, code artifacts at commit, external docs with durable
identifiers such as DOIs). Existing seed records PR-001..PR-004 must be migrated with
sources backfilled from their ORCHESTRATION.md origins. A corrective act that cites no
sources is mechanically rejected.

## A2. AMENDS D4 (binary binding/persuasive becomes graded force) and partially overrules the T-344 N=1 framing

The addendum (section 5): force is a graded spectrum, not binary; reiteration raises force
(jurisprudencia constante; Llewellyn's accumulating citations); a never-recited ratio may
decay to persuasive.

DECISION: separate two concepts the v0 schema fused:
- `authority_tier` (1-4) remains the ISSUANCE authority: how much adversarial process the
  decision survived at birth. Unchanged. This preserves T-344's core: a single verdicted
  decision binds at issuance; no N>1 threshold is required to bind.
- NEW `force` level: a graded value computed from issuance tier plus recorded consistent
  applications (via the citation index: `cite`/`confirm` events), with decay toward
  persuasive for records never cited within a stated window. Decay flags for
  reconsideration; it never auto-expires a record (addendum section 6 logic applies).

OVERRULED (partially), with reasoning, to be published as a formal record: T-344's demotion
of repeated confirmation to a non-binding reiterated flag. Reiteration is now a first-class
force-raising mechanism. T-344's argument (any N>1 threshold is a de facto ban on binding)
is preserved against a different error: it argued against requiring N>1 for ANY bindingness,
which the addendum also does not require. What changes is the ceiling, not the floor.

## A3. NEW PRIMITIVE: the shared interpretive code (addendum section 4)

DECISION: create `INTERPRETIVE-CODE.md` at repo root, sibling of PRECEDENT.md:
translation rules (how to read a ratio: literal, then purposive, then systematic), preference
rules (ranking competing readings), procedure rules (order of application), each rule with a
stable ID (IC-NN) and the document carrying an explicit version (v1). Every interpretive act
recorded in the registry cites the code version used. The code is CONSTITUTIONAL-TIER
material: amendable only through the overruling-grade protocol (tier-2 path).
Purpose per the addendum: indeterminacy stays structural, but divergence becomes auditable
(different disposition, different code version, or different application - three
distinguishable failure modes).

## A4. Three operations, structurally separate (addendum section 2)

DECISION: schema v2 records interpretive acts as TYPED operations, never a single blob:
- `determination` (realist terminology adopted: a recorded CHOICE of what binds, with
  reasoning, contestable) - at publish time by the author.
- `reinterpretation`: `declarative` (fixing an indeterminate ratio for a new case) or
  `corrective` (`restrictive` | `extensive`) - the corrective kind requires the A1 sources
  discipline and sufficient tier.
- `valuation`: metatextual force changes (declaring a passage obiter, error-in-pronouncement,
  context-change weakening) - each a first-class recorded act, never silent (addendum
  section 5 last bullet).
Conflict detection and the overruling protocol must branch on operation type.

## A5. Validity conditions vs scope conditions (addendum section 6)

DECISION: schema v2 adds `validity_conditions` - the facts about the ENVIRONMENT the ratio
presupposes (file paths, tool versions, board mechanics, repo state) - distinct from
`scope_conditions` (the class of cases the ratio applies to). A periodic pass (extending the
conflicts machinery or a sibling `stale` check) flags records whose validity conditions no
longer hold as RECONSIDERATION CANDIDATES; never auto-expiry.

## A6. Anti-evasion sharpened: constrain fact re-description (addendum section 7)

DECISION: the distinguishing protocol in PRECEDENT.md must require every distinguishing move
to state (a) WHICH material facts differ and (b) WHY the difference is material - because
distinguishing operates literally by re-describing facts, constraining rule citation alone
does not constrain evasion. Where computable, the S-signal list gains a check on
fact-re-description discipline.

## A7. Realist cautions adopted as standing rules

- No mechanism may presuppose recoverable collective intent (the "will" of a council is not
  a discoverable fact); mechanisms record DECLARED reasoning only.
- PRECEDENT.md gains the conceptual frame: records are dispositions, not norms; precedents
  are second-degree documents; certainty is an institutional achievement of disciplined,
  auditable interpretation - which is this layer's value proposition.

## A8. Research remainders (addendum section 8)

Two small research tasks remain from the original agenda: (1) horizontal precedent among
peer lineages (item 1 remainder), (2) reasoning-burden calibration for overruling (item 3
remainder). Same discipline as the first nine: web research, named primary sources, tagged
claims, implications section.

## Scope of the amendment epic

Deliverables: schema v2 + CLI v2 (sources, validity_conditions, graded force with
reiteration and decay, typed operations, interpretive-code version citation) with migration
of PR-001..PR-004; INTERPRETIVE-CODE.md v1; PRECEDENT.md v1 update; the formal tier-1
records publishing the addendum's directives and the recorded partial overruling of A2;
the two research remainders. Producer/approver discipline, verifier rotation, and the
extends-not-duplicates contract all unchanged.

OPEN-QUESTION: the addendum's DOI is the durable external identifier for sources citing it;
the local addendum file lives under docs/ (operator-local, gitignored) - tracked registry
records must therefore cite the DOI plus section, never the local path alone.

## A9. Coordinator answers to the planner's U3 blindspot interview (all six, recorded)

1. DECISION: CONFIRM the anchor-grammar extension. The A2 overruling targets the T-344
   recorded decision by task-anchored citation (task ID plus document section), not by
   republishing it as a PR record born to be overruled. The registry may cite the board's
   native recorded decisions; D3 already anchors citations to task IDs. Registry noise is
   the cost we refuse.
2. DECISION: CONFIRM in-place migration of PR-001..PR-004 as a once-only, tier-1-authorized,
   recorded exception to immutability. Rationale: supersede-with-new-records would break
   citation stability for a pure format change - PR-IDs must keep resolving identically.
   The migration act itself is logged with the operator directive as its authority.
3. DECISION: CONFIRM force computed on read, never stored. Force is a function of the
   citation index, which changes with every cite; storing it would mutate published records
   continuously, violating immutability. Computed-on-read also makes the force formula
   itself amendable without touching records.
4. DECISION: decay is measured on the ACTIVITY CLOCK - intervening published records and
   citation events - never wall-clock. Unit: a record with zero citations after N subsequent
   registry publications flags as decay-candidate; T-352 calibrates N against the registry's
   real citation velocity and records the calibration reasoning. Wall-clock measures
   burstiness of operator sessions, not neglect by the polity.
5. DECISION: CONFIRM. Research and synthesis outputs stay operator-local under docs/
   (gitignored by design); tracked artifacts (INTERPRETIVE-CODE.md, PRECEDENT.md, registry
   records) cite the addendum by DOI plus section.
6. DECISION: CONFIRM scope unchanged: no claude.md/gemini.md/ORCHESTRATION.md/state.json
   writes, no P-023 backfill (still operator-gated), no P-number retrofit in this epic.
