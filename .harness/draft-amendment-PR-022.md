# Draft amendment to PR-022. ARCHIVED, NOT PUBLISHED, DOES NOT PROCEED.

> **DISPOSITION, 2026-08-15.** ARCHIVED by operator ruling — *"Yo creo que hay que
> archivar la enmienda."* — following a unanimous 4-of-4 REFUSE from a blind panel of four
> independent lenses. Full verdict: `.harness/panel-verdict-PR-022-amendment.md`.
>
> The text below is preserved UNCHANGED as the constancy of what was proposed and why it
> failed. Nothing in it is in force. Three of the panel's findings are drafting errors by
> the coordinator and are recorded here so the document is not read as merely unlucky:
>
> 1. **The single proposed consequence — a verification-burden discount — is the FIRST
>    ITEM PR-023 clause 1 names as Phase B**, in the same three words. §5 below chose it as
>    "the smallest consequence that is still a consequence" while §3 argued that PR-023
>    must be satisfied rather than appealed. It is the item the gate names first.
> 2. **PR-022 clause 6, quoted verbatim in §1 below and declared untouched in §2, forbids
>    the proposal by name**: "no verification or confirmation burden varies by standing."
>    The drafter transcribed the prohibition into its own draft and did not see it.
> 3. **Condition (e) miscites PR-026 clause 3.** The verbatim text forbids demotion,
>    suspension or exclusion "by computed standing alone". §4 reports the exclusion arm
>    only and drops the operative qualifier, which is the exact mechanism the discount
>    uses. The clause actually broken is clause 4: the machine flags, an agent decides.
>
> It is NOT repairable by redrafting the six conditions. Five findings are collisions with
> active tier-1 records — PR-022 c6, PR-023 c1, PR-024 c3/c4, PR-025 c1/c3, PR-038 — that
> no redraft touches. Any future attempt is a five-record displacement and must arrive as
> one, with PR-019's verbatim embedding, before a panel holding the whole package.
>
> §6, "Why this draft should be REFUSED, stated by its own drafter", was written before the
> panel and anticipated none of the three errors above. That is the measure of what a
> drafter's self-critique is worth without an adversary.
>
> The live question moved elsewhere and is now on its own docket: can a typed citation be
> made to cost the citer something, and is PR-026 clause 3 the record that has to move?

---

**Status:** ARCHIVED. No record exists and none will issue from this text.
**Operator instruction:** *"Hay que enmendarlo con mucho cuidado."*
**Why it is a draft and not a record:** PR-017 requires the amending record to land before
any code computes a consequence, and PR-015 requires confirmation by a distinct identity.
Both are satisfied by publishing this only after the operator and a second identity have
read it, in that order.

---

## 1. The record being amended, quoted verbatim

Quoted in full because PR-019 forbids displacing a ratio without embedding it.

> **PR-022 — Phase A reputation is bookkeeping: derived on read, zero consequences**
> (1) Reputation is derived, never stored as balances; standing is computed at read time
> from the existing archive, following PR-010's computed-on-read doctrine. (2) No new
> ledger: the reader references existing records rather than duplicating them, because
> stacking layers can subtract performance. (3) The event types are exactly six: rule
> authorship; load-bearing citations received; consolidations achieved; proper overrulings
> issued and sustained; verification verdicts upheld; adjudications not reversed
> (DEFERRED, present and empty, never fabricated). (4) NO CONSEQUENCE ATTACHES. NONE: no
> weighting, no gating, no privileges. (5) The caveat, verbatim, is the canonical string
> every output path of the reader prints: identities are self-asserted (FORCE-IDENTITY-A
> open); Phase A is bookkeeping, not currency; no consequence may cite these figures
> (A.4, A.9). (6) The neutrality clause, verbatim: [...]

## 2. What this draft does NOT touch

Clauses 1, 2, 3 and 6 stand entirely. Computed-on-read stays, the no-new-ledger rule
stays, the six event types stay closed, and the neutrality clause stays.

Clause 5's canonical caveat stays **verbatim and unmodified**, including the words
"identities are self-asserted". That sentence remains TRUE: the identity work of D-16
through D-21 closed minting conditionally and closed impersonation not at all. Anyone
proposing to soften clause 5 on the strength of the warrant layer has misread what the
warrant layer does, and two blind panels are on record refuting exactly that reading.

The amendment reaches clause 4 alone, and reaches it narrowly.

## 3. The case for amending at all

Clause 4 exists because standing keyed to a free identity is farmable. That reasoning was
correct when written and is still correct for any consequence keyed to a NAME.

What has changed is narrow and should be stated narrowly: a name now exists only inside a
warrant the operator signed, so the population of names is no longer free to expand.
Sybil minting -- the specific attack clause 4 defends against -- is closed conditionally.

What has NOT changed, and what any amendment must survive:

- **Impersonation is open**, demonstrated by a test that steals a key and forges with it.
- **The closure is conditional** on `warrant.py reconcile` returning clean AND the anchor
  being checked against a fingerprint held off the machine. Neither is automatic.
- **The A.8 conjunction has no threshold.** PR-023 clause 5 says Phase B does not ship if
  the currency is failing, and `currency.py` now computes the measures but refuses to
  name a failing point, because nobody has ratified one.
- **PR-015's confirmation floor has never been exercised.** Zero of 59 records carry a
  `confirmed_by`. The layer's own distinct-identity check is, empirically, ceremonial.

That last finding is the strongest argument for caution and the drafter puts it first
rather than burying it. A registry that has never once had a second identity confirm
anything is not obviously ready to start paying people.

## 4. The amendment proposed

Replace clause 4 with:

> (4) NO CONSEQUENCE ATTACHES BY DEFAULT. A consequence may attach to a figure in clause
> 3 only where ALL of the following hold, each verifiable by command:
>   (a) the figure is computed from records issued under warrants that `warrant.py
>       reconcile` reports free of orphans;
>   (b) the harness anchor matches the fingerprint the operator holds off the machine,
>       evidenced by `warrant.py audit --expect` returning no ALARM;
>   (c) the consequence is REVERSIBLE and its reversal is itself a recorded act;
>   (d) the consequence is bounded by a sunset stated in the enacting record, after which
>       it lapses unless re-enacted;
>   (e) the consequence does not exclude any party from participation, which PR-026
>       clause 3 forbids independently and which this clause does not license;
>   (f) an A.8 failing point has been ratified by the operator and `currency.py` reports
>       the currency above it.
> Absent any one of (a) through (f), NO CONSEQUENCE ATTACHES. NONE.

## 5. The first consequence the drafter would propose under it, and only this one

**A verification-burden discount, capped, reversible, sunset at one epic.** A name whose
records have been built on by a different colegiado carries a verification burden reduced
by at most one reviewer, never below two.

Chosen because it is the smallest consequence that is still a consequence, because its
failure mode is visible (bad work shipping with one less reviewer, which the verifier
queue records), and because it cannot exclude anyone -- it lightens a burden, it never
raises one. Quorum weight and charter contestability, the other two Phase B items PR-023
names, stay gated and are NOT proposed here.

## 6. Why this draft should be REFUSED, stated by its own drafter

The strongest arguments against, put as well as the drafter can put them:

**The conditions are self-reported.** (a) and (b) are commands run inside the harness,
by agents, on a filesystem those agents control. A party that wants the consequence can
arrange for reconcile to come back clean. The only genuinely external check in the list
is the operator comparing a fingerprint, and if that is the load-bearing element then the
amendment is really "consequences attach when the operator says so", which is a shorter
and more honest record than this one.

**Condition (f) is a blank the operator has not filled.** Ratifying an A.8 failing point
is a substantive judgment about currency health, and this draft quietly assumes it will
be made. It might not be, or it might be made badly, and clause 4 currently protects
against both by refusing the whole question.

**The drafter has been wrong three times in this session** about what its own mechanisms
guarantee, twice caught by blind panels and once by miscitation of a tier-1 record. That
is a reason to discount its assessment that the conditions are sufficient, and the
operator should weigh it accordingly.

**Nothing is broken today.** Clause 4 has no victims. The economy the operator wants does
not exist yet, so there is no live cost to waiting, and PR-022's caution has so far cost
this project nothing while its absence would have cost it a counterfeit currency.

## 7. Procedure, if the operator wants it to proceed

1. The operator ratifies or rejects an A.8 failing point. Without it, condition (f) is
   unfillable and the amendment is inert on its own terms.
2. This draft goes to an adversarial panel that has not seen the drafter's defence, on
   the F7 and D-12 precedent.
3. If it survives, the record is published by an identity that is NOT the coordinator,
   and confirmed by a third under PR-015 -- which would also be the first confirmation
   ever recorded in this registry, and is worth doing for that reason alone.
4. Only then does any code read the amended clause. PR-017 governs and is not waivable
   by the drafter.
