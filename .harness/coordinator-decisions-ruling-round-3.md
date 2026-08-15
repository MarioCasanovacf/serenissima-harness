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
