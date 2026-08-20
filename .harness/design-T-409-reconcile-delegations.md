# T-409 design: reconcile names the delegated credentials it does not evaluate

**Date:** 2026-08-19 · **Role:** thinker · **No source edits in this document.**
**Chosen option: (a).** Reconcile mentions the existence of delegated credentials without
evaluating them.

## The finding

DELEGATION-OUTSIDE-RECONCILE-A, raised by the verifier `revision-ataque` on 2026-08-17 while
accepting T-401. Its strongest objection, and it was not grounds for rejection.

`reconcile` answers one question: **every row of the roll traces to a verified warrant.**
Delegated identities are not on the roll. So `reconcile` comes back clean while a delegated
credential can sign. The documented mitigation is that `delegations` is the complementary
report and that both verbs must be run.

**That is a documentation convention, not a mechanism.** Nothing obliges an auditor to run
both. Nothing tells someone who ran only `reconcile` that their answer is partial.

## The hard constraint

`reconcile`'s guarantee is stated in terms of **names with warrants**. Widening that word is
forbidden. Widening it would break the claim "minting is closed" while appearing to
strengthen it — the guarantee would then cover a population it cannot actually verify, and the
sentence an auditor relies on would become false in the one direction that matters.

Every option below is judged against that constraint first.

## The three options

### (b) A single verb that calls both — rejected

It removes the silence but at a cost the constraint forbids. A combined verb produces one
verdict over two populations with two different guarantees, and the moment there is one
verdict there is pressure to state one guarantee. Either the combined sentence is weaker than
`reconcile`'s (so running it is worse than running `reconcile` alone) or it is stated broadly
enough to cover delegations (which is the silent widening). It also leaves the two verbs in
place, so an auditor can still run `reconcile` alone and get the same partial answer — the
convention problem is not solved, only given a third exit.

### (c) Leave it — rejected

The convention is doing real work today and the harness is not unsafe. But the failure mode is
specific and cheap to hit: an auditor runs `reconcile`, reads CLEAN, and reports that the
identity layer reconciles. Nothing they did was wrong. The tool told them so. A guarantee whose
scope is only discoverable by reading a different tool's documentation is a guarantee that will
eventually be over-reported, and this harness already has four tier-1 miscitations on file
from a single day.

### (a) Reconcile names what it does not evaluate — chosen

`reconcile` keeps its guarantee **word for word**. It gains a count and a sentence:

```
reconcile: 19 roll row(s), 19 traced to a verified warrant, 0 orphan(s)
  DELEGATED CREDENTIALS OUTSIDE THIS GUARANTEE: 3 raw / 3 distinct
  This verb answers ONE question -- every roll row traces to a verified warrant -- and
  delegated identities are not on the roll. It did NOT evaluate the 3 credential(s) above and
  says nothing about them. Run `attest.py delegations` for that population.
```

What this buys, precisely:

- the guarantee is unchanged, so "minting is closed conditionally" survives untouched;
- the silence is gone: a clean `reconcile` now states its own boundary in the same breath;
- the number is a **count, not a verdict** — `reconcile` does not check whether a delegated
  credential is valid, expired, or within its ceiling, and its own output says so;
- an auditor who ignores the sentence is now ignoring a printed sentence rather than failing
  to know about a second tool.

## What it deliberately does not do

- **No exit code change.** Delegated credentials existing is not a failure, and `reconcile`'s
  exit code stays a function of orphan roll rows alone. A count that moved the exit code would
  be an evaluation wearing a count's clothes.
- **No evaluation.** Not expiry, not ceiling, not chain depth. Every one of those is
  `delegations`' job and duplicating any of them starts the second-registry defect that
  `roster.py`'s cache already cost this project once.
- **No claim that running both is sufficient.** Two verbs covering two populations is still not
  a proof that the populations are exhaustive. D-17 remains: any agent can read any key, so
  neither report bounds an adversary.

## Cost of being wrong in each direction

If the count is too **low** (a delegated credential exists that this count misses), an auditor
under-estimates the unevaluated population — the dangerous direction, and it is the reason the
count must be derived from the same grant-act walk `delegations` uses rather than from a
separate cache that can drift.

If the count is too **high** (a credential counted that cannot actually sign, e.g. expired),
the auditor is pointed at `delegations` for a population smaller than advertised. Cheap, and it
errs toward looking.

So: **derive the count from the same source `delegations` reads, and do not filter it.** An
unfiltered count is the conservative one here, and filtering would require the evaluation this
verb is refusing to do.

## Handoff to a worker task

1. `reconcile` gains `delegated_outside_guarantee_raw` / `_distinct`, computed by calling the
   existing delegation walk in `attest.py` and counting — no new traversal, no new store.
2. The renderer prints the count and the boundary sentence on every run, clean or not.
   Printing it only when non-zero would make the boundary invisible in exactly the case an
   auditor is most likely to over-report: a clean run in a harness with no delegations yet.
3. `--json` carries both counts and the boundary sentence as a string field, per the pattern
   `currency.py` and `westphalia_kpi.py` already use for non-verdict prose.
4. Tests: the guarantee sentence is unchanged (pin it verbatim); the count matches
   `delegations`' population exactly; the exit code does not move when the count is non-zero;
   and a negative control where a delegated credential exists and `reconcile` still says CLEAN
   about the roll — because that is the true and unchanged answer, and the test exists to
   prove the fix did not quietly widen it.
