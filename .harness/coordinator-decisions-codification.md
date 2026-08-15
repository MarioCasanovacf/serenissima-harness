# Coordinator Delimitations — Constitutional Codification Epic

Author: coordinator (main session). Date: 2026-08-13.
Mandate: operator ruling 9 (T-375 notes, 2026-08-13): retrofit is not ~30 P-numbers but the
full constitution — "Hay que ser mas ambiciosos, es una constitucion."
Inputs: .harness/context-brief-codification.md (scout census and hazards) and the D2 gate
this epic now triggers (.harness/coordinator-decisions-precedent-layer.md D2: full retrofit
was the named follow-on, gated on the schema surviving adversarial verification — it has,
twice).

The scout flagged two open questions as HUMAN-ONLY. Both are resolved here with the
conservative, reversible default, and both are RATIFICATION ITEMS at the epic join — the
operator may overturn either with recorded reasoning.

## CD1. Mirror first; canonicity is a separate, later operator decision

DECISION: this epic codifies the constitution into the registry as a CITED MIRROR. The
prose homes (ORCHESTRATION.md, claude.md, gemini.md, state.json) remain canonical. Making
the registry the canonical home — demoting prose to commentary — is a distinct
constitutional act reserved for the operator, presented at the join, never assumed.
Rationale: mirror-to-canonical is an upgrade path; canonical-to-mirror is a retreat under
fire. And canonicity while TIER-EVIDENCE-A stays open would rest the constitution's supreme
source on anchors the CLI cannot verify — sequencing error. CD6 partially repairs the
anchor problem for the new records; canonicity can follow when the operator rules.

## CD2. The NLAH files do not enter scope

DECISION: claude.md and gemini.md norms are OUT of this epic. They are the two files the
existing human_gates entry protects, and their mutation path is the 5A loop plus the
operator's gate. Codifying their content would create a second authority track around that
gate. Their constitutional-in-character rules (no-external-LLM, producer-never-approver,
bounded-everything) enter the registry only WHERE ORCHESTRATION.md or state.json already
states the same norm — anchored to those homes, never to the NLAH text.

## CD3. P-023 stays untouched; T-365 owns it

DECISION: the codification epic must not create, cite-as-resolved, or backfill P-023.
PR-001 already records the gap; the 5A path through T-365 and the operator's gate is the
only exit. Any codification record whose subject overlaps P-023 must carry a validity
condition naming the open gap.

## CD4. P-027 and P-028 are codified as what they are: rejected proposals

DECISION: their records, if minted, are HISTORY records — subject rejected-proposal, ratio
stating the DESCARTAR verdict and its reasoning from audit_gen5, status never active-as-
doctrine. Codifying rejection is jurisprudence (negative precedent has value); recasting
rejection as a gap to fill would falsify the ledger. The scout's correction is adopted
verbatim.

## CD5. Anti-completionism, per AD2-39's generalized warning

DECISION: codify norms with OPERATIVE FORCE TODAY. Settled history (superseded rules,
already-dispositioned findings, PR-009's grandfathered shape) is cited in dicta where
relevant, never re-promulgated as active doctrine. The census target is the scout's
per-item inventory filtered to rows with current binding force; the join reports what was
deliberately left uncodified and why, so the boundary is chosen, not accidental.

## CD6. Anchoring: verifiable facts, not decision tokens

DECISION: every codification record's tier evidence anchors to CLI- or git-verifiable
facts: the commit hash that introduced the norm, the events.jsonl entries that enforced it,
the accepted_mutations ledger entry, the audit file section. This is the partial repair of
TIER-EVIDENCE-A for the new corpus: historical norms have verifiable histories precisely
because the archive is append-only. Records for norms lacking any verifiable anchor state
that honestly and take the tier their evidence supports, not the tier tradition suggests.

## CD7. Three waves, each verified before the next

DECISION: wave 1 — ORCHESTRATION.md section-3 invariants plus the P-numbers present in
accepted_mutations (clean ratios, ledger-anchored). Wave 2 — the audit-born norms (F6, U2,
U4 as ORCHESTRATION rules; F1, U1, U3 codified against their actual homes with their
narrower reach stated — the scout showed they are not a peer set and the records must not
flatten that). Wave 3 — state.json normative structures (human_gates, limits, cost_policy
including the P-030 band with its below-band finding noted, protected_paths). Each wave:
publish, verify cluster (text-against-source, the T-361 pattern), then proceed.

## CD8. Double-homed norms get one registry record citing all homes

DECISION: where a norm lives in two or more prose homes, ONE record cites every home and
names which is primary; ORCHESTRATION.md may gain PR-NNN backlink markers (it is not
NLAH-gated and has been task-edited before); claude.md/gemini.md gain nothing (CD2). The
conflict-detection question for drifted double-homes is design work inside the epic, bounded
by AD2-39: no sixth detector for historical nonconformity; a census check comparing registry
against ledger is a different instrument and is in scope.

RATIFICATION ITEMS AT THE JOIN: CD1 (mirror vs canonical) and CD2 (NLAH exclusion),
explicitly; the rest are execution delimitations reviewable as usual.

## Execution log (ops findings, dated)

2026-08-14: census T-377 froze the ledger (34 -> 59 records planned across three
waves) and handed off, but its verifier died twice, instantly, on provider-side 529
Overloaded errors while every agent inheriting the session model ran normally in a
concurrent workflow. Diagnosis: the four frontier slots in the orchestration script
(census verifier, wave drafters, text verifiers, join verifier) carried an explicit
older-model override and that pool was the one overloaded. Fix: the overrides were
removed so frontier slots inherit the session model; cheap mechanical slots keep
their fast tier. Resumed from cache - the census did not re-run. Finding class for
the 5A loop: model-pin fragility under provider overload; prefer inherit-by-default
in orchestration scripts, pin only downward for mechanical stages.

2026-08-14, wave 1: published PR-035..PR-052 (registry 34 -> 52) and both cluster
verifiers cleared it, but only after the census verifier REJECTED the publish task
for one character. It extracted all 18 publish commands mechanically from the
worker's own handoff note and replayed them in a temp root: 17 reproduced byte-
perfect, and CD-12's quoted command carried a comma where live PR-046 was produced
with a semicolon. The records were legitimate; the transcript was not reproducible,
and the task's own criterion holds that an unreproducible transcript is not
evidence. The cascade then refused the next claim on its own (dependency gate,
exit 1) - the topology enforced itself with no coordinator intervention. Repair was
a one-byte note correction by the original producer, re-verdicted by the same
verifier. Finding class: transcript fidelity is a distinct failure mode from record
correctness, and only mechanical re-execution of quoted commands catches it.

2026-08-14, wave 2: the drafter (T-382) died twice mid-work - first on a model
quota, then on a closed connection - leaving partial artifacts both times. This is
the long-agent fragility class already recorded on T-365. Remedy applied here, same
as the T-366 recovery: split the drafter into two short read-only strands (narrow-
reach rows CD-20/21/23; the P-017 split rows CD-22/24) plus a short writer that
claims the task, composes, dry-runs and hands off. Standing guidance for future
epics: any single agent whose assignment spans more than ~4 derivation-heavy items
should be authored as strands plus writer from the start, not after it dies.
