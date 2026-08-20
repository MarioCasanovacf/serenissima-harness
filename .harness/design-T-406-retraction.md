# T-406 design: retraction is necessarily reflexive

**Date:** 2026-08-19 · **Role:** thinker · **No source edits in this document.**
**Decision made before any code, as the task requires.**

## The case that forced this

On 2026-08-17, during T-400, the coordinator smoke-tested the D3a intent path against the live
registry and signed, as `revision-doctrina`, an act with `kind=verdict` and `ref=T-376`. **No
verdict on T-376 was rendered.** The ref was chosen carelessly. A signed, verified, fully
anchored act now sits on a real name's chain asserting a verdict that does not exist, and
`trace()` reports it COMPLETE — which it truthfully is, because every anchoring record it
checks really is present.

Removal was attempted and correctly refused twice: `prevent_data_loss.py` blocked it, and
`safe_delete.py` refused `.harness/acts/` as a control-plane path. **Those refusals are right
and must not be relaxed.** An agent that can erase the evidentiary record has no evidentiary
record. A direct filesystem call that would have bypassed both was available and deliberately
not used.

## The decision: a chained self-act, and the alternative is a category error

The task framed the choice as (a) a chained act that `verify` and `trace` consult, versus
(b) an adjudication only a DISTINCT name can make, aligning with PR-015's confirmation floor
and producer ≠ approver. Option (b) was described as "stronger and slower".

**It is not stronger. It is a different verb, and this harness already has it.**

You cannot retract someone else's statement. A retraction is a speaker disowning their own
assertion; the thing a second party does to an assertion they believe false is **contest**,
and `attest.py contest` exists, files the claim as a signed act on the accuser's own chain,
and makes a false accusation permanently attributable to whoever filed it (AF-3). Building a
second-party "retraction" would duplicate `contest` under a name that misdescribes it — and
misdescribes it in the dangerous direction, because "retracted" reads as *the author withdrew
this* when it would mean *someone else disputes this*.

So:

| verb | who | what it asserts |
|---|---|---|
| `retract` (to build) | the signer, on their own chain | I disown this act of mine |
| `contest` (exists) | any other name, on their own chain | I say this act of theirs is false |

Both are append-only. Both attach no consequence. Neither removes anything.

The consequence of choosing reflexive: a retraction is available **immediately**, without
waiting for a second party. That is the right failure direction here. During any gap where a
known-false act stands undisowned, `trace` reports it COMPLETE — the evidentiary layer should
be able to record "the author disowns this" the moment it is known, not when someone else gets
around to it. Slower is not safer when the thing being delayed is the correction.

## The three weaknesses of the seq-2 filing workaround

The only correction available today was to sign a `kind=filing` act recording that seq 1 is
void. The task named three weaknesses. Two are fixed by design; one is accepted, with reasons.

### 1. It sits after the act it corrects and nothing links them — FIXED

The retraction body carries `retracts: <digest of the target act>`, the same digest field
shape `intent` already uses, so consumption-style backward resolution already has a precedent
in this module (PR-010: computed on read, no side ledger).

Resolution is **backward**: when any tool reports act N, it walks that name's chain for an act
whose `retracts` equals N's digest. No index, no cache, no second registry — the roster cache
defect is exactly the mistake not to repeat here.

Refusals the verb needs, each for a reason already learned in this module:

- the target must be **on the retractor's own chain** — you cannot disown another name's act;
- the target must **exist and verify** — retracting a digest that names nothing is noise;
- **one retraction per target** — a second is a no-op refusal, not a silent duplicate, the same
  shape as `grant`'s second-grant refusal in T-401;
- **a retraction cannot be retracted.** Un-disowning is not a speech act the chain can
  represent honestly, and allowing it opens a flip-flop with no terminal state. A signer who
  changes their mind signs a NEW act saying so; the retraction stays.

### 2. It carries no more authority than the act it corrects — ACCEPTED, and here is why

Same key, same name. Under D-17 a forger who holds the key can file a false verdict **and** a
false retraction of a true one. This is not fixable inside the harness and a design that
claimed to fix it would be claiming a boundary that does not exist.

What makes it survivable is DIS-2, which already governs every act in this module: **credit
follows the signature, always.** A forged retraction signed as A is credited to A. Forging can
destroy the forger's target's record; it can never enrich the forger. The asymmetry is the
whole defence, and it is the same one that makes `sign` and `contest` tolerable.

**Stated as the task requires: a forger can file a false retraction of a true act, and this
design does not prevent that.**

### 3. verify_name and trace do not know the concept exists — FIXED

Both consult retractions when reporting the retracted act:

- `trace` rows gain `retracted` (bool) and `retracted_by` (seq of the retracting act).
  `complete` keeps its current meaning — it is about the anchoring walk, and a retracted act
  can still have a complete walk — so a retracted row reads `complete: true, retracted: true`,
  which is the truth: properly signed, properly anchored, and disowned. Collapsing the two
  would destroy information.
- counts gain `retracted_raw` / `retracted_distinct`, raw and distinct per
  TELEMETRY-PROVENANCE-A.
- `verify_name` reports the retraction alongside the signature verdict and does **not** call a
  retracted act invalid. The signature is still valid; that is a fact about the key. What
  changed is what the signer stands behind.

## The acceptance case

`revision-doctrina` seq 1, `kind=verdict ref=T-376`. After the change, a reader of seq 1 alone
must learn it is void.

**The limit, named rather than glossed:** a reader who `cat`s `.harness/acts/revision-doctrina/001.json`
directly still sees a verdict. The file is immutable and must stay immutable — that is the
whole property being protected. What the design guarantees is that **every tool that reports
seq 1 reports the retraction with it**: `trace`, `verify`, `chain`, and the renderers. A reader
who bypasses the tools bypasses the resolution, exactly as a reader who bypasses `warrant.py`
bypasses warrant verification.

## PR-022 clause 4 applies throughout

> (4) NO CONSEQUENCE ATTACHES. NONE: no weighting, no gating, no privileges.

A retraction attaches no consequence to any name. It does not reduce standing, it does not
gate a privilege, it does not feed a figure any consumer may cite. It changes one thing: what
the reporting tools say about one act. **Pin it with a test** that asserts no counter, weight
or gate anywhere in the harness reads the retraction fields — the same shape as the AST guard
in `westphalia_kpi.py`, and per T-410 the test should validate the reported output rather than
only the source's identifier names.

## What must not happen

The record stays append-only. Nothing in this design removes or rewrites an act. **If the
implementation starts wanting to remove, that is the signal it went wrong** — and the guards
that refused removal on 2026-08-17 stay exactly as strict as they are today.

## Handoff to a worker task

Implementable without further invention:

1. `RETRACT_KIND = "retract"`, unprivileged (it requires no intent — an intent to disown one's
   own error would be a regress with no anchor, and `INTENT_KIND` is already absent from
   `PRIVILEGED_KINDS` for the same reason).
2. `retract(root, name, key_path, target_seq, reason)` → signs an act whose body carries
   `retracts` (digest), `retracts_seq`, and a non-empty `reason` (refused if blank, the same
   refusal `declare_intent` applies to `--declares`: a retraction that says nothing is a
   checkbox).
3. `retractions(root, name)` → digest → retracting act, computed on read.
4. `trace` and `verify_name` consult it; `chain` renders it inline.
5. Tests: the four refusals; backward resolution; the D-17 limit pinned by a stolen-key
   forgery of a retraction; clause 4 pinned by an output-shape guard; and the live acceptance
   case replayed on a fixture chain, not on the live registry.
