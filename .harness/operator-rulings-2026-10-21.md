# Operator rulings, 2026-10-21: identity, suits, the notary, and a rehearsal root

The decision sheet cut on 2026-10-19 (version 10) carried one card per decision. The
operator asked for them in plain words, and the coordinator put five questions, each with
its recommendation. The operator answered: *"Okay, sí a todo."*

This file is the durable record. Nothing was signed in ruling: no ruling here attaches a
consequence, so no warrant carries it. Decisions 5, 7 and 8 of the sheet were not among
the five questions and stay open.

## The push of 75de528 and 30592f9

**Ruling: yes.** Both commits went to `gen-9/identity-2026-09-23` on 2026-10-21. `main`
was not touched.

## Decision 9: the rehearsal may mint its own throwaway root

**Question.** Four mechanisms stopped in the T-440 rehearsal at one cause: the sandbox
held no key recorded in a warrant, because the coordinator barred it from copying seat
keys and from signing warrants. May the rehearsal create its own root key, sign a
rehearsal warrant with it, and re-mint the same nine names with fresh keys?

**Ruling: yes.** Limits, as stated on the card:

- The root key is generated inside the temporary directory the script itself created,
  and dies with it. The operator's root key, `~/.ssh/harness_root`, and the live
  `.harness/keys`, `.harness/trust` and `.harness/constitutional` are never read for
  private material and never written.
- Every scorecard row that depends on it says it was signed under the rehearsal root,
  not the operator's.
- A rehearsal warrant copied into the live tree fails verification, because its root is
  not the enrolled one. A test pins that the live tree does not change.

Precedent for the method: `.harness/tests/test_warrant.py` already generates its own
throwaway root in a temporary directory.

## Decision 1: identity is option 5, signed by the operator's root key, plus option 6

**Ratified.** The design is `.harness/design-T-432-agent-identity.md`.

- **Option 5, dispatch tokens.** Fields `(agent_name, task_id, role, issued_at, expiry,
  nonce)`. Signed with the operator's root key through the same out-of-band gate that
  signs warrants. Not an HMAC: under D-17 a shared MAC key is readable by every agent,
  which would let any agent mint tokens. The verifier of T-433 did not catch that; the
  card made it a condition and the operator ratified the card.
- **Grain: one signing action per epic**, covering that epic's set of tokens. The card's
  ratified text says "1 firma tuya por proyecto, no 1 por tarea". The same card also said
  the grain would come back as a separate decision. The coordinator reads the ratified
  text as settling it at epic grain, and records that reading here so the operator can
  correct it.
- **Option 6, from the Swiss research.** (a) A verb that revokes a name by operator
  order. A revocation is an operator-signed record, never an agent act, so no agent can
  revoke another. From that moment every token for that name is refused, expired or
  not. (b) Routine checks at every epic close: `attest.py forks`, `warrant.py reconcile`,
  and IMP-6 (an act with no matching `act_signed` event is anomalous;
  `coordinator-decisions-ruling-round-2.md`, D-22). IMP-6 is not built yet.

**What it does NOT do.** A token proves that the operator authorized that agent for that
task and role. It does not prove that each act under it is the act the operator meant.
That is the limit already accepted for the W-002 plazas. Impersonation inside a token's
window stays open (D-17). Nothing here attaches a consequence (PR-022 clause 4).

## Decision 3: suits between parties, an agentic judge, appeal to the operator

**Ratified.**

- The case register accepts suits: claimant, respondent, contract, damages claimed.
- The respondent receives notice and may answer before judgment.
- An agentic judge decides, distinct from both parties.
- The operator is the final appeal.

**What it needs.** A judge seat exists only inside a warrant the operator signs. The
design comes first and builds on what T-436 left: claims replayed at filing, and an
objection that halts. Construction waits on the identity tokens.

**Still owed by the operator.** Three numbers from T-436: the objection window, the
pursue-or-lapse window, and the damages cap. The judge design proposes values with
reasons; the operator ratifies them.

**What it does NOT do.** Every individual consequence still needs its own published
record (PR-060 clause 6). Damages are paid in operational budget, never reputation
(ruling of 2026-10-08).

## Decision 4: open the notary in parts, a and b now

**Ratified.**

- **a.** Build the retract verb as designed in `.harness/design-T-406-retraction.md`.
  Then retract the false verdict of 2026-08-17: `revision-doctrina` seq 1, kind verdict,
  ref T-376. The act file stays; every tool that reports it reports the retraction with
  it.
- **b.** `warrant.py audit` without `--expect` ends with a failing exit code, so an
  unverified audit can no longer pass for a verified one.

**The operator's manual step for b.** Sign one git tag carrying the root key's
fingerprint, so `audit` has something held outside the working tree to compare against.
The coordinator hands over the exact command when asked, and never runs it.

**Waiting for identity:** c, a fedatario co-signs each close and each verdict as witness;
d, the operator certifies each epoch's batch of acts.

## Not decided here

- Decisions 5, 7 and 8 of the sheet.
- The three numbers of decision 3.
- Whether a future warrant, absent a fresh ruling, carries the same authorization (the
  residue of D5, 2026-08-17).
