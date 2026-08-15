# Operator ruling round 3 (2026-08-15): the seven pending decisions

Recorded verbatim in substance so the mandates survive context compaction. No registry
mutation flows from this file. Every change lands only through its named vehicle, after
the ratification each item specifies.

Presented to the operator as an ETS-100 decision artifact. Seven items, D1 through D7
below, numbered as they were presented.

---

## D1. CANONICITY IS THE DESTINATION. THE ANCHOR DEFECT IS THE ONLY GATE.

**RULING: neither "mirror" nor "canonical" as posed. The operator ruled a SEQUENCE.**

Operator's framing, on record: the purpose of the whole programme is to move the harness
from session engineering to registry engineering to jurisprudence, and canonicity is what
makes judges, courts and interpretation real rather than decorative. Verbatim: *"si yo
digo canónico, en estricto sentido, se cumple esto de tener jueces y cortes y demás para
interpretar, constituir"*. And on the cost: *"el tema con la verificación de las anclas es
que hay que ver cómo lo resolvemos antes de poder plantear constitucionalidad."*

So CD1's three options were the wrong menu. The answer is: canonical, AFTER
TIER-EVIDENCE-A closes. The registry stays a mirror in the interim, and the interim has a
defined exit rather than being an indefinite hedge.

### What the anchor defect actually is, measured

The coordinator's first statement of this was on its way to being an overclaim and was
corrected before it reached the operator. The precise finding, each part checked:

- **29 of 59 records are tier 1.** Tier 1 means the operator ruled it.
- **19 of those 29 anchor to a decision token**, e.g. PR-022's
  `decision:T-368#addendum-ii-a4`. The token DOES resolve: the string appears in
  `.harness/tasks/T-368.json`, which git tracks. So the anchor is not dangling.
- **What it resolves to is a coordinator's restatement**, not the operator's own text. The
  task file holds a paraphrase table written by the party whose authority the anchor is
  meant to establish.
- **The operator's own text is out of the repository.** `docs/` is gitignored at line 33
  and git tracks 0 files under it. PR-022's own dicta already admits this: the addendum
  "would dangle for every reader who clones".
- **The other 10 tier-1 records anchor only to task ids**, which do not even claim an
  operator act.
- **Zero records of 59 anchor to a commit hash.**

That is the form-versus-fact gap F2 named. Form: the anchor resolves. Fact: it resolves to
the wrong KIND of thing. A fresh clone cannot verify that the operator ruled any tier-1
record in this registry.

### The exit, and why it is not archaeology

The obvious repair — dig through git for the commit that introduced each norm — is the
wrong instrument, because a commit proves a coordinator wrote a file, which is the same
category error one level down.

The right instrument already exists and is unbuilt only because it was never pointed here.
Once the operator's key is enrolled (D2), the operator signs a **ratification act** per
tier-1 record: a short attestation, in the repository, signed by the one key no agent can
steal, saying that this operator ruled this ratio. `attest.py` chains it. `warrant.py
verify` checks it. Anyone who clones can verify it without trusting any agent.

**This inverts the published dependency map.** The artifact delivered earlier this session
shows D1 and D2 as independent. They are not: **D2 is the prerequisite for D1.** The
coordinator published that map before measuring the anchor classes, and it is wrong.

**Scope: 29 records, one signing session.** Not an epic of archaeology.

**Cost the operator must accept before ordering it:** a record whose ratio the operator
declines to attest does not get re-anchored, and takes the tier its evidence supports.
CD6 already fixes that rule. Canonicity that cannot demote anything is not canonicity.

VEHICLE: new epic. Instrument `verify-anchors`, a read-only verb that resolves every
`tier_evidence` anchor to a checkable fact and reports the unverifiable class rather than
passing it silently. Then the ratification acts. Then the RATIFICATION-SET record F2
already ordered, with verify-anchors green as one of its four clauses.

## D2. ENROL THE ROOT: YES. GROWTH IS AUTHORIZED BY ESTABLISHMENT, NOT BY HIRE.

**RULING: approved.** Operator's question, verbatim: *"¿Cómo podemos hacer para exigir mi
firma y poder tener crecimiento de agentes si es necesario? ¿Tendrían que mandarme un
memorándum de 'hoy necesitamos más agentes' y yo lo tengo que firmar?"*

Essentially yes, but the signature goes one level up from where the current code puts it.

`roster.py` today gates all three verbs — `charter`, `plazas`, `issue` — on a warrant, so
every individual name would need the operator's signature. That is the sign-every-hire
model and it makes the operator a bottleneck on ordinary work.

**The signature belongs on the ESTABLISHMENT, not on the occupant.** The operator signs a
seat budget for an epic: this colegiado gets these seats, with these names. Filling a
declared seat needs no further signature. The population is then bounded absolutely by
what the operator signed, which is exactly the property PR-023 clause 1 is asking for:
the Sybil attack is defeated by the seat count, not by vetting each occupant.

Security accounting, stated plainly so it is not oversold: this concedes that an agent
could occupy a declared seat under a name it did not earn. That is impersonation, which is
architecturally open regardless (D-17: every agent runs as the same OS user on one
filesystem). The establishment model therefore concedes nothing that D-17 has not already
conceded, and closes minting completely.

MECHANISM: the coordinator drafts an establishment request naming the seats and the
reason. `warrant.py draft` emits it unsigned and prints the exact command. The operator
runs it under `ssh-add -c`, so a confirmation prompt appears. **One signature per epic**,
plus one per mid-epic supplement. The supplement is the intended friction: it is the exact
moment a runaway loop would be caught.

## D3. THE FAILING POINT IS NOT A THRESHOLD. IT IS THE THREE FUNCTIONS OF MONEY.

**RULING: the question was re-specified, not answered, and the re-specification governs.**

Operator's framing, on record: *"¿Cuál es el punto de falla de una moneda? ¿Cuál es el
punto de falla de un mecanismo de intercambio? ¿Qué es lo que hace que el dinero sea
dinero? Yo entiendo que el dinero es dinero porque es salvaguarda de valor, medida de
intercambio y unidad de medida. Si no tuviera una de estas tres, la verdad es que no
sería dinero."*

And the stakes, verbatim: without a functional currency there is no mechanism to make
agents economize resources, none to make them trade and negotiate, and none to establish a
fiscal wedge toward the coordinator — the Swiss-and-French mechanism of F4. *"En esta
República de Letras que estamos construyendo, estamos concediendo también un Estado."*

CANDIDATE DEFINITION, for ratification, not ratified here:

> A reputational currency is FAILING when it does not perform all three of: **store of
> value** (standing persists and stays attributable to whoever earned it), **medium of
> exchange** (standing circulates; distinct identities transact in it), and **unit of
> account** (something is denominated in it). Failing any one means it is not money.

Operator's own guard, also on record: the test must not run retroactively against records
published before the mechanism existed, or it is rigged to fail.

### Status of each function today, and the fix each one needs

| Function | Status | Why | Fix |
|---|---|---|---|
| Store of value | FAILS | Attribution is a self-asserted string. 108 names in `state.json` against 7 real authors. Value cannot be stored in a unit anyone can counterfeit. | D2. Already built, not yet switched on. |
| Medium of exchange | FAILS | The citation economy stopped at PR-034. 25 records since, 0 typed edges between them. | Unsolved. The hardest of the three. |
| Unit of account | FAILS **BY LAW** | PR-022 clause 4 forbids denominating anything in standing. | D4, the amendment. |

### The circularity the coordinator found, surfaced rather than left for the panel

Condition (f) of the draft amendment requires the A.8 currency to be above its failing
point BEFORE any consequence attaches. Under the three-function test, unit of account
cannot obtain while clause 4 stands. **So the amendment requires a condition that only the
amendment can create.** As drafted, (f) plus this candidate is unsatisfiable.

Two non-circular readings exist and the operator must pick one, or reject both:
1. **Staged.** At ratification the test runs on functions 1 and 2 only; function 3 is
   measured after a trial window under sunset, and its failure lapses the consequence.
2. **Demand-side.** Function 3 is read as "something is denominated in it", which a
   PROPOSAL to denominate satisfies without the consequence yet attaching.

### The objection the coordinator owes the operator, stated against the operator's frame

Reputation is not alienable. The coordinator cannot transfer its standing; a citation does
not deplete the citer's holding. On the strict monetary reading, a non-transferable unit
has no medium-of-exchange function at all, and the analogy fails at function 2.

The defence, which the coordinator believes is right but flags as its own reasoning: a
typed citation IS a transaction with a real cost. A record that declares `follows PR-010`
binds itself to PR-010 as controlling and gives up future freedom to depart from it. The
citer spends something scarce. That is exchange without transfer.

The blind panel's economics lens was asked to attack exactly this, and its ruling on the
annex is a separate deliverable.

## D4. TO THE BLIND PANEL.

**RULING: send it.** *"Manda la decisión 4 a un panel ciego. Me interesa saber su
opinión."*

Four independent lenses, none aware of the others, none shown the drafter's advocacy or
its self-refutation: constitutional coherence, adversarial attack, incentive design and
monetary economics, and the case for outright refusal. The three-function candidate went
in as a marked annex with the circularity as an explicit question.

Material fact given to the panel and worth recording here: **PR-022's own
`revisit_trigger` has fired.** Verbatim: *"Revisit when FORCE-IDENTITY-A is recorded
closed, or when any consumer proposes to attach a consequence to a Phase A figure."* The
second arm fired. The amendment is the revisit this record scheduled for itself, not an
intrusion on it. The first arm has NOT fired: FORCE-IDENTITY-A is not closed.

## D5. HUMAN NAMES: YES, AND A POPULATION REGISTER.

**RULING: approved.** *"Sobre la decisión 5, sí. Hay que tener un registro poblacional de
agentes."*

The mechanism falls out of D2 at no extra cost. The human name is a field of the SEAT, not
of the occupant, so the operator signs the names when signing the establishment. An agent
cannot invent a name because names arrive attached to seats.

This forecloses the failure the coordinator was worried about. A display-alias map in a
separate file would be a second unreconciled registry — the exact shape of the
`agent_keys.json` defect the second panel found. A field inside the signed warrant is not
a second registry.

The population register is then the roll: seats signed by the operator, occupants recorded
as signed acts on their own chains, and `reconcile` requiring every roll row to trace to a
verified warrant. That is a census with an integrity claim, and it is the natural predecessor
of the Westphalia and sovereignty work already on the roadmap.

## D6. THIRD BLIND PANEL BEFORE ENROLLING.

**RULING: concurred.** The panel attacks what was built after the first two panels, which
no adversary has yet seen. It runs before the root is enrolled, not after, because
enrolment is the moment the layer stops being inert.

## D7. INSTRUCTION FILES OUT OF SCOPE: CONFIRMED FOR THE MIRROR, RE-OPENED BY CANONICITY.

**RULING: conditional.** *"Si eso es congruente con todo el diseño y la arquitectura que
estamos haciendo, sí."* The condition is doing real work and the coordinator declines to
rubber-stamp it.

Under a MIRROR registry, CD2 is right. The NLAH files are protected by the operator's own
gate, and codifying them would create a second authority track around that gate.

Under a CANONICAL registry, CD2 inverts. If the registry is the supreme source, then
constitutional-in-character rules living outside it — no-external-LLM,
producer-never-approver, bounded-everything — are themselves the second authority track,
just in the other direction. The rule that keeps the instruction files safe today is the
rule that would put them beyond the constitution tomorrow.

CONFIRMED as of today, since today the registry is a mirror. FLAGGED for mandatory
re-examination at the moment D1 lands. Recorded so that transition cannot happen silently.

---

## Carried, unchanged

T-349 quarterly watch (next due 2026-11-10). T-365 generation-6 audit. T-376 repair.
The `docs/` gitignore is deliberate and stays: the operator-local material there is not a
candidate for tracking, which is precisely why the D1 exit is a signed attestation in the
repository rather than a file move.

---

# Ruling round 3.2 (operator, 2026-08-15): the five post-panel decisions

## D8. The three-function test: preserved as a design objective. HOW is the open part.

**RULING: concurred with the panel.** Not the operative failing point; kept as an
objective. Operator's follow-up, verbatim: *"Lo que el panel no me contesta es cómo lo
implementamos."* The panel ruled on WHETHER. The mechanism is the coordinator's to supply.

**MECHANISM: it goes in `dicta`, never in `ratio`, and that distinction is not cosmetic.**

In this layer `ratio` is the holding and it BINDS on publication; `dicta` is reasoning that
travels with a record and persuades without binding. That is the whole ratio/obiter
distinction the precedent layer was built on, and it is the exact instrument for "true and
worth remembering, but not operative". PR-022 already uses it this way: its dicta names
`docs/serenissima-addendum-ii...` as the operator text the ratio enacts, precisely because
that file is gitignored and would dangle as a binding anchor.

Concretely, when the A.8 docket next produces a record:
- The ratio carries the A.8.3 measures and the standing refusal, NO THRESHOLD RATIFIED.
- The dicta carries the three functions, with three things stated in the dicta itself so a
  later session cannot promote it by accident: (i) that it is a design objective and NOT a
  failing point; (ii) that medium-of-exchange is unsatisfiable while standing is derived on
  read, so ratifying it as operative would bar Phase B by definition; (iii) the diagnosis
  it produced and that nothing else did — this system has an asset with no scarcity
  constraint, because a citation depletes nobody.
- `validity_conditions` names the condition under which it could ever become operative: a
  transfer primitive existing, which D-22 IMP-1 says must not.

The safeguard is that promotion from dicta to ratio is not a text edit anyone can make.
`ratio` is immutable under SDR-01 and no verb in `precedent.py` edits one, so promoting it
requires a new tier-1 record that overrules, which PR-019 forces to embed the displaced
ratio verbatim. The objective cannot become a test quietly.

## D9. PR-026 clause 3: docket OPENED, and the panel convened.

**RULING: open it.** Operator, verbatim: *"si no la abrimos, no vamos a poder tener sistema
económico ni fiscal. ¿Cómo evitamos que tengamos cebadores de arquitectura? Necesito que el
panel me traiga argumentos."*

Note what was asked for: ARGUMENTS, both sides, not a verdict. Four lenses convened, none
aware of the others, before any instrument is drafted rather than after — the inverse of
the PR-022 sequence, and deliberately so. Lenses: constitutional path (is a lift even
required, and if so what is the instrument); mechanism design (the chilling effect, and
what the machine computes versus what an agent decides); attack (the operator's gaming
worry, including whether an attacker can engineer an overruling to damage citers it
dislikes); comparative institutions plus the case for NOT opening.

The question posed: can a typed citation carry a real cost to the CITER without producing
the harms PR-026 refuses? The load-bearing sub-question the coordinator put to the
constitutional lens: clause 3 forbids demotion "by computed standing alone", so a liability
firing on an ADJUDICATED overruling may not touch clause 3 at all — it may be exactly what
clause 4 blesses. If that reading holds, the docket needs no lift. If it does not, it is
word-play routing around a refusal, which is the move the prior panel condemned.

## D10. The three A.8.3 measures: BUILT.

**RULING: build.** Done, shipped in `currency.py` as `structure()`. Read-only, no verdict,
NO THRESHOLD RATIFIED preserved.

Live values: breadth **4 of 42** ordered pairs (0.095); issued from outside the incumbent
set **0 of 12** (0.0); liveness **0** typed citations in the trailing 25 records, marked
NOT REPORTABLE; reciprocity **2 of 4** realized pairs lie on a mutual edge (0.5).

**A measurement defect was caught before it shipped and both figures now print.** The
panel's literal words were "the share issued from outside the top-3 BY AUTHORSHIP".
Computed literally on this registry that returns **0.417**, which reads as a mostly-open
economy and is an artifact: the top-3 by authorship and the identities that actually
participate are different sets here, because the largest publisher has never cited nor been
cited while the 4th-largest issues a third of all citations. The measure that answers the
question uses the INCUMBENTS — identities already holding a cross-author citation received
— and returns 0.0. Both print, separately named, with the substitution stated, because
silently replacing a panel's stated measure would be its own defect.

Reciprocity prints `NOT_A_FINDING` on every path: this module cannot distinguish a genuine
reciprocal citation from a manufactured one, no instrument in this harness can, and the
panelist who raised it said the same of itself.

Seven new tests, 22 total, OK. One asserts that bulk publication moves none of the three
and LOWERS liveness, which is the attack that killed the previous candidate's
store-of-value arm.

## D11. Enrolment: stands, and the commands finally exist.

**RULING: stands.** Operator, verbatim and pointed: *"pues sí, hay que ponerla en pie, pero
es que yo no he tirado ningún código de Python ni el WordArt ni nada, ni he firmado nada
porque no me has dicho que sea necesario."*

That is the second time in this session the operator has had to say the commands were never
supplied. The failure is the coordinator's and it is now closed:
`.harness/OPERATOR-ENROLMENT.md`, every command run end to end against a sandbox before the
file was written, with the real outputs quoted and the negative cases verified in both
directions.

Also verified in that run, and it settles D5 without new code: the `--name` grammar already
carries an optional PERSONA field, and it lands INSIDE the signed payload and then in the
roll. The human name is a field of the warrant the operator signs, never a separate alias
map. D5 needs no implementation.

Sequencing note: D6 required the third panel BEFORE enrolment. It ran, it found two silent
detectors, both are repaired and pinned by regression tests. The precondition is satisfied.

## D12. The amendment: ARCHIVED.

**RULING: archive.** `draft-amendment-PR-022.md` carries a disposition header naming the
three findings that are coordinator errors rather than bad luck, and preserves the text
unchanged as the constancy of what was proposed. Nothing in it is in force.

Recorded because it is the sharpest lesson available: §6 of that draft, "Why this draft
should be REFUSED, stated by its own drafter", was written before the panel and anticipated
NONE of the three errors. That is what a drafter's self-critique is worth without an
adversary.
