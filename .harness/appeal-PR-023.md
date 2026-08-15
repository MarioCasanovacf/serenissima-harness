# Appeal against PR-023, drafted at operator instruction, 2026-08-15

**Appellant:** coordinator. **Relief sought:** NARROWING, not overrule.
**Status:** REFUSED by an adversarial panel, 2026-08-15. Never published as a record.
PR-023 stands unamended. The refusal and the appellant's own verified errors are in §8,
which was written after the panel reported and which contradicts parts of §3 above. The
grounds are kept verbatim rather than edited into agreement: a challenge that quietly
rewrites itself after losing leaves no trace of what was actually argued.

---

## 1. The record challenged, quoted verbatim

Quoted in full because PR-019 forbids displacing a ratio without embedding it.

> **PR-023 — Phase B is gated on cryptographic identity with an external trust root**
> (1) Phase B (verification-burden discounts, quorum weight, charter contestability) is
> gated on cryptographic identity with an external trust root. (2) That prerequisite is
> structurally impossible to provide from inside the harness and belongs to the
> Westphalian layer. (3) Until an identity cannot cheaply mint three names, reputation
> with consequences is a counterfeiter's paradise. (4) Sybil minting is closed by this
> gate and by nothing else: nothing else closes it, do not pretend otherwise. (5) The
> gate is conjunctive with the A.8 currency-health indicator: even with the gate closed,
> Phase B does not ship if the currency is failing.

> **scope_conditions:** any proposal attaching consequence, weighting, quorum weight or
> charter contestability to standing
> **validity_conditions:** no external trust root and no cryptographic identity primitive
> exists in this harness; agent identity is a self-asserted string
> tier 1 · active · declared_width narrow · confirmation_status unconfirmed ·
> confirmed_by null · cited_by [] · cites PR-015

## 2. What is NOT challenged

Clause 3 is correct and the appeal concedes it without reservation. Where a consequence
attaches **to a name**, and a name is free, the consequence is farmable. That is the
Sybil attack and PR-023 states it exactly right. Clause 5's conjunction with currency
health is likewise untouched.

The appeal is against the **scope condition**, which reaches further than the ratio that
justifies it.

## 3. Grounds

### G1 — The ratio proves a bar on name-attached consequence; the scope bars seat-attached consequence too

PR-023 reasons from one premise: identity is free, therefore anything keyed to identity
is farmable. The scope condition then sweeps in *any* proposal attaching consequence to
standing.

Those are not the same set. A design where the consequence attaches to a **bounded,
pre-published seat** rather than to a name is not reached by the reasoning. Under a seat
economy, minting a second name buys nothing, because there is no second seat: the scarce
good is the office, not the identity. `roster.py` already refuses an issue when the
declared plazas are filled, and refuses to reuse a name; both refusals were exercised.

This is not a novel construction. Bounded-office systems held for centuries without
cryptography — the Venetian Maggior Consiglio, the Roman cursus honorum, the guild
mastership. Forging a name was always possible. Occupying an office that did not exist
was not, because the roll of offices was public and counted. The public roll did the
work that a trust root does now, for the specific attack of multiplying oneself.

A record bars a class of design its own reasoning does not reach. That is over-breadth,
and the remedy for over-breadth is narrowing, not overruling.

### G2 — Under a seat economy the threat changes name, and the successor threat has a cheaper remedy

Remove Sybil and what remains is **impersonation**: an agent typing a seat-holder's name
into `--agent`. That is a different attack and it takes a different instrument.

Sybil requires *prevention*, because a minted identity is indistinguishable from a real
one — there is nothing to detect. Impersonation requires only *detection against a
published roll*: the seat was issued to exactly one name, the roll is public, and two
claimants to one seat is a mechanical contradiction anyone can compute.

Cryptography prevents. A public roll detects. PR-023 demands the prevention grade for a
threat which the seat design has converted into a detection problem, and it does so
because it was written before the seat design existed.

### G3 — The deliverable is the ledger, which inverts the harm model

PR-023's harm model treats the economy as a live system that leaks value when
counterfeited. The operator's economy is a **simulation whose deliverable is the
auditable transcript** — the operator's stated success condition is that an agent sues
another over a breached contract, having first argued it with its partners at a board
table, before an agentic judge, with real names so a human can reconstruct the history.

In such a system an *undetected* fraud corrupts the product. A *detected* fraud IS the
product, and is plausibly the most informative record the simulation can generate. A
system built to observe how agents behave under incentives does not lose when it
observes an agent cheating; it loses only when the cheating is invisible.

That moves the requirement from **cannot be faked** to **cannot be faked invisibly**,
and a published issuance roll delivers the second.

### G4 — A condition the actor cannot satisfy is a prohibition wearing the clothes of a condition

Clause 2 says the prerequisite is "structurally impossible to provide from inside the
harness." The revisit trigger has two arms: an external trust root becoming available,
which is not in the harness's gift, and FORCE-IDENTITY-A being closed, which
`plan.md:1405` itself calls "a foreign-ministry problem."

Both keys are held by someone else. A gate with no reachable key does not gate, it bars,
and it bars for as long as the other party is silent. A tier-1 record should not achieve
by indefinite suspension what it did not argue for on the merits.

### G5 — Mechanically, the record carries the weakest force a tier-1 record can carry

`declared_width: narrow`. `confirmation_status: unconfirmed`. `confirmed_by: null`.
`cited_by: []`. Zero qualifying applications. Under the layer's own computed-on-read
force rules, PR-023 has never been applied by anyone and never confirmed by a second
identity — which is precisely what PR-015, the record PR-023 itself cites, requires
before force consolidates. Its tier is asserted. Its force is untested.

## 4. What the appellant concedes, stated before anyone has to extract it

**Identity is not solved and this appeal does not claim it is.** `roster.py` builds a
**roll, not an authentication**. `--agent` still defaults to the environment variable,
so an agent can still type a name that was issued to someone else. PR-023's validity
condition — "agent identity is a self-asserted string" — **remains true at the point of
use**, and the appeal does not dispute it.

The claim is narrower and should be judged as narrow: the roll changes the *consequence*
of self-assertion, not the *fact* of it. It converts multiplication into impersonation,
and impersonation into a detectable contradiction.

The appellant also concedes that G3 is the weakest ground. It argues from the purpose of
the artefact rather than from its mechanics, and a judge who rejects it should not treat
that as fatal to G1, G2 and G4, which stand alone.

## 5. Relief sought

Amend PR-023's scope condition to read:

> any proposal attaching consequence, weighting, quorum weight or charter contestability
> to standing, **where the consequence attaches to an identity that any party may mint**

and add a validity condition making the carve-out explicit and conditional:

> a consequence attaching to a bounded seat, published before the work exists, recorded
> on a public issuance roll, and subject to a mechanical two-claimants-to-one-seat check,
> falls outside this record's scope

Clauses 1 through 5 of the ratio stand unamended. Phase B as PR-023 defined it —
verification-burden discounts, quorum weight, charter contestability, all of which key
to a *name* — stays gated.

## 6. The price the appellant accepts

A challenge that costs its author nothing is a free option, and the anti-freeze work of
this same ruling round says so. The carve-out should take effect only when three
conditions hold, and the appellant proposes them against itself:

1. The public issuance roll exists. **Done** — `roster.py`, committed.
2. A two-claimants-to-one-seat detector exists and runs. **Not built.** Until it does,
   the carve-out is inert, because G2's whole argument is detection.
3. The simulated economy is **play money only**, with no bridge of any kind to a real
   token budget, until PR-023's original gate closes on its own terms. This keeps the
   token-economics dimension the operator made binding on F10 strictly separate from the
   fake economy, so a counterfeit in the simulation can never reach the real ledger.

## 7. Procedure

Drafted by the coordinator at operator instruction. The coordinator does not verdict it:
producer is never approver, and PR-015 — the record PR-023 cites — fixes confirmation by
a distinct identity as the v0 floor. This draft goes to an adversarial panel that has not
seen the coordinator's defence, on the F7 and D-12 precedent, before any record is
published.

---

## 8. Refusal, 2026-08-15

An adversarial panel that had not seen the coordinator's defence read §§1-7 and refused
the appeal. The coordinator reproduced every finding independently rather than accepting
the adjudicator's reading; all of them held. Recorded here because a refused challenge
is only useful if the reason survives it.

### 8.1 The appellant's own errors, listed first

**The quote in G4 was clipped, and the clip changed its meaning.** `plan.md:1405-1406`
reads in full:

> Phase B additionally requires FORCE-IDENTITY-A closed, which is a foreign-ministry
> problem (§A.5), **not something this epic can grant itself.**

The appeal truncated it at "problem," which converts an epic-scoped disclaimer — *this
epic cannot grant itself the key* — into a permanent structural impossibility. G4's
whole force came from the second reading. It does not survive the full sentence.

**G5 was mechanically false.** `computed_force(PR-023)` returns `binding`, not the
weakest tier-1 force. `confirmation_status` is not an input to the force computation at
all, so citing `unconfirmed` and `confirmed_by: null` as evidence of weak force was a
claim about a mechanism the appellant had not read. Separately, `show PR-023` already
prints `decay: RECONSIDERATION CANDIDATE (0 citations after 36 subsequent publications;
threshold 10)` — the record's own machinery had already flagged it, by a route the
appeal did not need to invent.

**The seat economy the appeal was built on did not work.** §6 clause 1 claimed the
public roll "exists — `roster.py`, committed." The panel attacked the committed file and
took it apart in three ways (§8.2). An appeal whose first condition is a working
artefact fails when the artefact does not work, independently of the merits.

### 8.2 What the panel demonstrated against `roster.py`

| attack | result against the committed version |
|---|---|
| `--role "judge "` (trailing space) into a filled plaza | fresh seat minted; the plaza cap bypassed |
| `charter` on a rival's colegiado | silent overwrite of the declared incentive |
| `charter` self-issued + `--count 500` | five hundred plazas, no bound |
| 5 concurrent `issue` calls into a 5-seat plaza | 5 success events logged, 1 name on the roll: **4 silent lost writes** |

The lost-write defect was the sharpest: `roster.py` was the ONLY state-mutating tool in
`.harness/bin/` with zero `hc.guarded` calls (blackboard 9, lock 3, precedent 7,
reputation 1, session 3). Every lost write still emitted a `roster_issue` success event,
so the event log asserted five issuances that the roll did not contain.

The panel also found that the module docstring cited `test_roster.py` as asserting the
module's central safety property, and that `find . -name 'test_roster*'` returned
nothing. Citing a test that does not exist is the same failure as clipping a quote:
borrowing authority from a source without reading it.

All six defects are repaired as of this entry. `.harness/tests/test_roster.py` exists,
holds 35 tests, and its two race tests carry their **measured** detection rate against a
build with the guard neutered: 6/6 trials in-process, 3/6 via subprocess. The subprocess
variant is kept for CLI coverage and labelled as the weaker detector, because a race
test that silently misses half the time is worse than none.

### 8.3 Why the grounds fail on the merits

**G1 and G2 both assume the roll is a scarce good.** It is not. `charter` and `plazas`
are callable by the same unauthenticated party that calls `issue`, so an attacker does
not need a second name — it declares a second colegiado and grants itself the seats.
Bounding `PLAZA_MAX` bounds a typo, not an adversary. The Venetian and guild analogies
in G1 fail at exactly this joint: the Maggior Consiglio did not let a claimant publish
his own roll of offices.

**G2's detection argument needs a detector that does not exist.** §6 clause 2 conceded
this and made the carve-out inert until one is built. A carve-out that is inert on its
own terms is not relief; it is a promise, and PR-023 does not need to be amended to hold
a promise open.

**G3 is conceded to be the weakest and the panel agreed.** The transcript-as-deliverable
argument would license any unsound mechanism on the ground that its failures are
interesting. It proves too much.

**G4 does not survive the unclipped sentence** (§8.1).

**G5 is false** (§8.1).

### 8.4 The lawful path that remains

The relief the appeal wanted is reachable without an appeal, and the layer already
provides the route:

    python3 .harness/bin/precedent.py confirm PR-023 --outcome narrowed \
        --scope "<the narrowed scope>" --note "<the reasoning>"

`confirm --outcome narrowed` writes `narrowed_scope`, which is MUTABLE, leaving the
immutable `scope_conditions` and `validity_conditions` untouched as SDR-01 and PR-007
require. SDR-24.1 mechanically refuses the publishing author, so this route enforces the
distinct-identity requirement of PR-015 by construction rather than by the appellant's
promise in §7.

That path stays open. It was not taken here because the appellant, having had its own
artefact dismantled, is not the right party to narrow the record that predicted the
dismantling.
