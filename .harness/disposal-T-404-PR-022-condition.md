# T-404 disposal: PR-022's validity condition did not lapse

**Date:** 2026-08-19 · **Role:** thinker · **Outcome:** the canon requires NO ACT
· **PR-022 clause 4 remains fully in force.**

## The question

PR-022 (authority_tier 1, subject `reputation-phase-a`, status active,
confirmation_status unconfirmed) carries this validity condition, verbatim:

> FORCE-IDENTITY-A is open: no cryptographic identity with an external trust root exists in
> this harness

Since W-002 was signed and applied on 2026-08-17, an enrolled root exists at
`.harness/trust/root.pub`, nine names are bound inside an operator-signed warrant, and
`reconcile` traces 19 roll rows to it with 0 orphans. The words after the colon are false.

When a tier-1 record's validity condition is written as a factual claim, and the fact changes
but the concern the fact stood for does not, does the record lapse?

## First: the canon does not name validity conditions

IC-01 through IC-11 govern the reading of a **ratio**, and IC-05 governs **scope claims**.
Neither names `validity_conditions`. Applying the canon to a validity condition is itself an
interpretive move, and it is recorded here as one rather than presented as the canon speaking
directly. What follows applies IC-01, IC-02 and IC-10 **by analogy**, and says so.

The alternative — treating validity conditions as outside interpretation entirely, decided by
plain truth-value — is the reading that lapses PR-022, and it is addressed in the last section
rather than dismissed.

## IC-01, literal: indeterminate, so it does not decide

IC-01 asks for the literal reading in ordinary technical meaning, against the record's own
text, and permits stopping there only when the literal reading decides **with no residual
indeterminacy**. Two literal readings are grammatically available:

- **head plus gloss.** The condition asserts one thing — `FORCE-IDENTITY-A is open` — and the
  clause after the colon explains what "open" looked like when the record was written. On this
  reading the head is still true, and the condition holds.
- **conjunction.** The condition asserts two things, both required. On this reading the second
  conjunct is false, and the condition fails.

Both are available on the text alone. That is residual indeterminacy, so IC-01 does not
license stopping, and the sequence continues to IC-02.

## IC-02, purposive: determinate, and it comes from the record itself

IC-02 requires a purposive reading against the record's **own recorded materials** — its
`sources`, its `revisit_trigger`, and its issuing task's recorded reasoning — never against
presumed unrecorded intent. PR-022's `revisit_trigger` reads, verbatim:

> Revisit when FORCE-IDENTITY-A is recorded closed, or when any consumer proposes to attach a
> consequence to a Phase A figure

The record names its own test, and the test is **the defect's recorded status**, not the
existence of an artifact. Clause 5's canonical caveat string says the same thing again:
"identities are self-asserted (FORCE-IDENTITY-A open)". Twice, in its own text, the record
ties itself to the defect.

FORCE-IDENTITY-A is not recorded closed. D-17 holds: every agent runs as the same OS user on
one filesystem, every agent can read `.harness/keys/`, and a test in
`.harness/tests/test_attest_intent.py` proves forgery by stealing an agent key and signing
with it. Impersonation is open.

So the purposive reading is determinate: **the condition tracks the defect, and the defect is
open, so the condition holds.** What lapsed is the gloss.

## IC-10: stop here

IC-10 fixes the order and says to stop at the first rule that yields a determinate reading.
IC-02 yielded one, so IC-03 is not reached and the preference rules IC-06 to IC-08 are not
reached either — nothing is competing. IC-09 constrains throughout and points the same way: a
reader who cannot or will not publish a corrective act applies the record as written.

IC-07's narrow-reading preference is **not** invoked. It governs competing readings of a
record's own ratio, and stretching it to cover validity conditions would be
PR-017-OVEREXTENSION-A a second time.

## The disposal

**No act.** No record is published, nothing is amended, and the condition is left exactly as
written. The reasons, in order of weight:

1. The record already encodes the correct test in its `revisit_trigger`. Restating the
   condition in terms of the defect would add nothing PR-022 does not already say twice.
2. A new record would be legislation to fix a reading — the expensive path where a reading
   suffices, and the path D4a exists to make unnecessary.
3. Under PR-015 a new record needs confirmation by a distinct identity before it binds. The
   restraint binds **now**; a corrective record would not bind until confirmed. Acting would
   trade a binding restraint for an unconfirmed one, in the direction of weaker.

## PR-022 clause 4 is in force

> (4) NO CONSEQUENCE ATTACHES. NONE: no weighting, no gating, no privileges.

Unamended, unnarrowed, and binding. Nothing in this disposal touches it. Its
`revisit_trigger` names the other arm — a consumer proposing to attach a consequence to a
Phase A figure — and that arm has not fired either.

**The incentive this disposal runs against, stated plainly:** a coordinator who wanted to
attach a consequence to a Phase A figure has exactly one cheap route, which is to read the
lapse broadly and treat the whole record as expired. That is the reading refused here, and it
is refused by the record's own text rather than by preference.

## D-17, stated because it is the load-bearing fact

Impersonation is open. Every agent runs as the same OS user, on one filesystem, and can read
every other agent's private key. No agent can hold a secret from another. The only unforgeable
boundary in this harness is the operator's key, held off the machine. An enrolled trust root
changed what can be *minted*; it changed nothing about what can be *impersonated*.

That is why FORCE-IDENTITY-A is not recorded closed, and it is the whole reason this disposal
comes out the way it does.

## Where a reader meets this

`python3 .harness/bin/precedent.py conditions` (T-405) lists both of PR-022's validity
conditions and marks each `NOT MECHANICALLY EVALUABLE`, and its output says in its own words
that a condition written as a factual claim can lapse in letter without lapsing in purpose,
naming PR-022 as the live example and this task as the question. The tool reports and declines
to rule; this document is the ruling it declines to make.

## The reading not taken, and what would revive it

If validity conditions are held to be outside interpretation altogether — plain sentences with
plain truth values, no canon — then the second conjunct is false and the condition fails. That
reading is coherent. It is not taken here for the reason above: the record's own
`revisit_trigger` states the test, and a reading that ignores a record's stated test in favour
of a gloss is not more literal, it is less faithful.

Anyone who wants that reading has a route: publish it, at tier 1, with sources, and have it
confirmed by a distinct identity. That is IC-09's asymmetry working as designed. What is not
available is reaching the same result by preference alone.
