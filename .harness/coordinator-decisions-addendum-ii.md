# Coordinator Intake Memo — Addendum II (Reputation, Political Economy, Westphalia)

Author: coordinator (main session). Date: 2026-08-12.
Source: `docs/serenissima-addendum-ii-reputation-westphalia.md` (operator-supplied, tier-1
where marked DIRECTIVE; merges and supersedes the never-received separate Addendum II/III
texts and v1 of the unified document — only this unified v2 is on file; no registry impact
from the superseded versions, which never entered this environment).
Procedure: this intake follows PR-017 (R-B): reasoned with the operator, instance delimited
below, records published before any text or code lands.

Decisions use the U2 taxonomy. Delimitations are the load-bearing part of this memo.

## AB1. Delimitation of buildable scope

DECISION: three scopes, mechanically distinct:
- BUILD NOW (Part A, Phase A only): the reputation bookkeeping reader and the A.3
  displacement-bridge enforcement in the overruling path. Both are "operable today" by the
  addendum's own ordering.
- RESEARCH ONLY (Part B + A.6.3): the Schumpeter/Mokyr validation memo and the load-bearing
  citation operationalization. Zero build authorization for the market layer stands.
- RECORDS ONLY, FUTURE-BINDING (Part C): territorial law, sovereign cell charter, and the
  Westphalia KPI bind FUTURE construction. No cell, no domain registry, no charter is built
  now. The directives enter the registry so future epics are born bound.
- PARKED (explicit): Brussels-effect / conformance-acquis. No record beyond the parking
  notice inside the Part C record's dicta; building "standardization gravity" is refused
  until the operator's stated precondition holds.

## AB2. Phase A reputation: mapping event types to existing data (no new ledger)

DECISION: `reputation.py` is a READ-ONLY derivation over existing stores, mirroring
PR-010's computed-on-read doctrine. Event-type mapping, delimited:
- rule authorship -> `published_by` on PR records;
- load-bearing citations received -> v1 heuristic from the A.6.3 research task, marked
  PROVISIONAL with a decay clock (revisit trigger) in its enacting record;
- consolidations achieved -> the force computation's existing C-threshold data (PR-015
  qualified: only distinct-identity confirmed applications count);
- proper overrulings issued and sustained -> `overrules` relations whose superseding record
  survived verification and has been cited at least once (A.3.2: credit accrues on
  sustained, never on published);
- verification verdicts upheld -> verdicts in blackboard/task records and events.jsonl
  (producer-distinct done verdicts not later reopened);
- adjudications not reversed -> DEFERRED until the appellate verb exists; the reader ships
  with the field present and empty, never fabricated.
TRADEOFF: events.jsonl carries the measured synthetic-token contamination (~430 events);
the reader therefore prefers registry and task records over raw event counts, and every
figure it emits names its source store.

## AB3. Phase A displays the sybil caveat on every output

DECISION: every `reputation.py` output carries a fixed caveat line: identities are
self-asserted (FORCE-IDENTITY-A open); Phase A is bookkeeping, not currency; no consequence
may cite these figures (A.4, A.9). A consumer that wires a consequence to Phase A output
violates a tier-1 record, not a style guide.

## AB4. Phase A neutrality on trust burden

DECISION: A.6.2's standing-scaled verification burden is PHASE B material. In Phase A the
PR-015 confirmation burden stays UNIFORM for all identities. Delimited explicitly because
A.6.2's wording could be read as operable now; it is not, by A.4's "no consequence. None."

## AB5. The displacement bridge lands in the overruling path

DECISION: precedent.py's overrule path gains the A.3.1 enforcement: publishing with
--overrules requires embedding the overruled record's ratio verbatim with its authorship
(record id, published_by, issuing task) inside the superseding record; refusal otherwise.
PR-009 is the worked precedent being generalized. This is a protocol change: its enacting
record publishes BEFORE the code lands (PR-017 procedure).

## AB6. Silent divergence becomes the named reputational crime

DECISION: recorded as doctrine now (it already is protocol law); its reputational PRICE is
Phase B material. Phase A only counts and displays; it does not fine.

## AB7. T-349 amendment

DECISION: T-349 (quarterly watch) gains by note: (a) the A.8 reputation indicator
(load-bearing vs name-drop convergence; standing concentration without verified work -
either failing means Phase B does not ship regardless of the identity gate), and (b) the
C.5 Westphalia KPI as a standing definition with the operator baseline on record (~3 months
human reconciliation effort), measurable only once two domain registries exist.

## AB8. Anchoring and naming

DECISION: this addendum has no DOI; records anchor via task-anchored decision tokens
(decision:T-NNN#addendum-ii-<section>) per the established grammar, with the local file
under docs/ (operator-local) named in dicta, never as the sole anchor. No sibling-project
names in tracked artifacts, as always.

## AB9. Tensions surfaced to the operator (the reasoning step, on record)

OPEN-QUESTION (1): A.3.4 pays consolidation credit to the AUTHOR, while PR-015 counts only
distinct-identity confirmations. An author who recruits confirmers buys their own
consolidation credit - the citation-cartel vector applied to confirmations. Phase A
mitigation: the reader displays WHO confirmed alongside every consolidation figure, so the
pattern is visible while it is still free to attempt (A.4's stated purpose). Priced in
Phase B.
OPEN-QUESTION (2): A.2 makes standing portable across cells while C.4.5 pays cells for
outcomes. When cells can hire, portable standing plus outcome pay recreates the free-agent
market. Likely intended (the RoL architecture); flagged so the Part B validation memo
checks Mokyr for how the RoL priced mobile stars, and whether rent extraction followed.

## AB10. Current registry is the founding domain

DECISION: until cells exist, `.harness/precedents/` is delimited as the registry of the
FOUNDING DOMAIN (the harness itself). C.3's territorial rule is satisfied degenerately by
a single territory; the Part C record states this so no future epic mistakes the current
registry for a personal-law patrimony of any lineage.
