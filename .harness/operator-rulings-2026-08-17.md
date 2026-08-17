# Operator rulings, 2026-08-17: W-002 signed, D1 through D6 all YES

The operator signed W-002 and ruled on all six pending decisions in one pass. This file is
the durable record; the decision text they answered is
`decisiones-arnes-ets-2026-08-17.html`, and the positioning it rests on is
`intake-valley-2026-08-17.md`.

## The signature

```
SSH_AUTH_SOCK= ssh-keygen -Y sign -f ~/.ssh/harness_root -n harness-warrant .harness/warrants/W-002.json
```

Verified before anything was applied:

```json
{ "warrant_id": "W-002",
  "signed_by": "SHA256:9Ya45T4LytgZjcPKr0Aj5YrFqWmZT0SNoK3ExeQQnVM",
  "digest": "sha256:14069b6a1acab5ab281d3abe66968728600154904c2e74e95ad67157491b41e3",
  "expired": false }
```

**The digest matches the one in `W-002-BRIEFING.md` byte for byte.** That is the check that
matters: the operator signed the document they were briefed on, not a document that changed
between the briefing and the signature. `signed_by` equals the enrolled anchor.

## D5, ruled first because it gated the rest

**Question.** PR-028 clause 6, verbatim: *"This charter authorizes no cell now."* Does an
operator-signed warrant authorize the first cell, or must a tier-1 record land first?

**Ruling: the signature suffices.** Operator's words: *"La firma basta."*

**Grounds, as the coordinator understands them and subject to correction.** PR-026 clause 1
makes the operator the only tier-1 authority and states they are sovereign, not a market
participant. Clause 6 of PR-028 is a self-limitation of that charter record, and a sovereign
act by the only tier-1 authority is not bound by a lower record's hold on itself. The
coordinator did NOT reach this conclusion on its own and should not be credited with it: it
set out both readings and declined to choose, because its citation record this session
carried four tier-1 errors, two of which read a rule into a record that is not written there.
This ruling is the operator's.

**What it does not decide.** Whether a future warrant, absent a fresh ruling, carries the
same authorization. Nothing here converts one sovereign act into a standing rule.

## D1: W-002 applied

```
colegiados   fedatario, registro, revision
plazas       fedatario/registrar=1  fedatario/relator=1  fedatario/regulador=1
             fedatario/codificador=1  registro/author=2  registro/verifier=3
             revision/verifier=3                                    (11 total)
names        fed-registrar  fed-relator  fed-regulador  fed-codificador
             registro-a  registro-b
             revision-doctrina  revision-ataque  revision-mecanismo   (9 of 11 seats)
```

`reconcile`: enrolled, 19 rows checked, **0 orphans**, W-002 verified, clean.

Two seats left deliberately empty, so the roll can grow to a ceiling the operator already
signed without a new signature. Expiry 2026-11-10, aligned to the T-349 quarterly watch.

**What this does NOT do**, carried verbatim from the payload: *PR-022 clause 4 holds: this
warrant confers a seat and a name, never a weight, a burden, a quorum or a permission.* No
standing figure changed. `roster.py` remains bookkeeping. Identity is still self-asserted and
impersonation is still open (D-17).

## D2: constitutional and operational parameters are separated

Consequences may attach to OPERATIONAL parameters that agents set for themselves.
CONSTITUTIONAL parameters — thresholds, quorum floors, any weighting — remain the operator's
alone. Ruled YES.

This is the route past the PR-022 clause 4 deadlock that does not require lifting PR-026
clause 3. All twelve instruments the blind panel refuted 12-0 in round 4 tried to attach a
consequence to a constitutional parameter.

**Open and not decided here:** this ruling authorizes the SPLIT. It does not itself attach
any consequence to anything. The enacting tier-1 record has to be published, and per PR-015
confirmed by a distinct identity, before any consequence exists. Drafting it is a task, and
the coordinator must not treat "the operator said yes" as the record.

## D3: adopt the identity formats that already shipped

Ruled YES. Three anchoring records per privileged action (intent declared, privilege
granted, privilege exercised), a delegation ceiling where no identity delegates more
privilege than it holds, and credentials that expire and cannot extend themselves. Sourced
to the CSA agentic identity governance framework via `intake-valley-2026-08-17.md`.

`attest.py` already signs acts; it does not yet demand a declared intent BEFORE the act.
That is the gap.

## D4: build the distinguish verb and the PR-029 KPI

Ruled YES. `distinguish` disposes of a novel case by citing the nearest decided one plus the
material difference, as a signed act. The PR-029 KPI measures what repairing a divergence
costs, against the operator's baseline of roughly three months of human effort.

The differentiator is the ratio of novel cases disposed by citation versus by legislation.
Nobody else can report it, because nobody else has the denominator.

## D6: `.harness/trust/` is tracked by git

Ruled YES. `root.pub` and `root.fingerprint` are now tracked; see `.harness/trust/README.md`
for what that buys and what it costs. No private key material is in that directory.

**Stated plainly because the operator should know where the exposure actually is:** this
harness commits and never pushes. A commit is local. The permanent public association of
this repository with that key happens on PUSH, which has not happened and will not happen
without a separate instruction.

## Still owed by the operator, and independent of every ruling above

```
python3 .harness/bin/warrant.py audit --expect "SHA256:<the fingerprint held off this machine>"
```

Until that runs, the anchor is UNVERIFIED and says so about itself. Tracking `trust/` adds a
second witness; it does not replace the one that lives outside the filesystem.
