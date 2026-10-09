# T-436 design: contracts, breach and damages paid in operational budget

**Date:** 2026-10-08 (round 4, same day) · **Role:** thinker · **No source edits in
this document.**
**Decision made before any code. Operator approves before any worker task is created.**

**Round 4, in one paragraph.** Round 3 removed the false-claim PRICE but not the
record: filing still ran through `attest.py contest`, which writes the respondent's
name and the accusation to a permanent file the instant it is called, gap or no gap.
This round moves the gap-check inside the write, via a new entry point (`file_claim`)
that reaches `contest`'s signing step only once the gap is confirmed, so a
non-replaying claim writes no `attest.py` act anywhere. Sections 1-4 are unchanged
beyond one sentence in section 4; section 5 and 6 carry the rest. Revision log at the
end.

## Starting point: what is already ruled, quoted

Operator ruling 2026-10-08, decision 2, verbatim: *"Adelante la idea del presupuesto
operativo como costo de indemnización."* The ruling's own text: "The breaching party
compensates with part of its own budget: tokens, tasks or deadline days that the
contract commits. Reputation is never the unit." And its limit, also verbatim: "It
attaches no consequence to anything. PR-060 clause 6 holds: every individual
consequence still needs its own published record, naming the operational parameter,
the consequence, and the agent's own act of setting that parameter."

PR-060 clause 1, verbatim: "Every parameter of this harness is CONSTITUTIONAL or
OPERATIONAL, and never both. A parameter is CONSTITUTIONAL when it fixes HOW WORK IS
EVALUATED: any threshold, any quorum floor, any weighting, any burden of proof, any
tier boundary, and any figure computed about an identity. A parameter is OPERATIONAL
when it fixes WHAT WORK IS DONE: which task is claimed, in what order, under what
budget, against what deadline, on which engine, with what iteration bound."

PR-060 clause 2, verbatim: "CONSEQUENCE MAY ATTACH TO AN OPERATIONAL PARAMETER. An
agent that sets an operational parameter for itself may be held to it, and the holding
is a consequence in the full sense: it may bind, refuse, or cost."

PR-060 clause 5, verbatim: "THE DECIDING TEST FOR A HARD CASE. If the consequence
could be computed, in whole or in part, from a figure about an identity, the parameter
is CONSTITUTIONAL. Doubt resolves toward constitutional, because the cost of wrongly
calling a parameter operational is a consequence nobody authorized, and the cost of
wrongly calling it constitutional is a delay."

PR-060 clause 6, verbatim: "THIS RECORD AUTHORIZES NO CONSEQUENCE NOW. It authorizes
the DISTINCTION and nothing else. Every individual consequence still requires its own
published record, which must name the operational parameter, the consequence, and the
agent's own act of setting that parameter. A consumer that reads this record as a
general licence to attach consequences violates this clause."

PR-060 `scope_conditions`, quoted in full because they bound everything below:
- "Applies to every parameter of this harness, including parameters not yet named,
  because clause 1 is a division and a division with gaps is not one"
- "Does NOT apply to the operator, who is sovereign and not a market participant
  (PR-026 clause 1)"
- "Does NOT itself attach any consequence to anything; clause 6 is a self-limitation
  and is part of the ratio, not dicta"
- "Operative only while the operator's ruling of 2026-08-17 stands; it is recorded in
  .harness/operator-rulings-2026-08-17.md and is the sole authority for the division"

PR-060 `validity_conditions` include, verbatim: "No harness store holds a stored
standing or balance field, so no figure can become an operational parameter by
accident." Load-bearing for DAMAGES (section 3): a running per-agent balance would
itself create the forbidden stored field, voiding the operational reading.

PR-022 clause 4, verbatim: "NO CONSEQUENCE ATTACHES. NONE: no weighting, no gating, no
privileges." This is reputation's own clause (subject `reputation-phase-a`) and stays
untouched; nothing in this design computes a consequence from a reputation figure.

PR-026 clause 3, verbatim: "No automatic demotion, suspension or exclusion of any
identity by computed standing alone."

PR-061 clause 3, verbatim: "D-17 NON-STAKING PRESERVED. Reputation is non-transferable,
non-stakeable, and carries no asset boundary."

Swiss brief, section 8, item 5, verbatim: "The Swiss flaw to avoid: false claims are
void but nearly free. Here contest already places the claim on the accuser's own chain
(AF-3); the design must say what a false claim costs, in budget, without touching
reputation." Section 3's own line on the same flaw: "A malicious filing
(Schikanebetreibung) is void and can be struck, but the target is not automatically
compensated. Deterrence against false claims is weak."

Swiss brief, section 8, item 2, verbatim: "An objection inside a short window halts it
at once; the claimant must then go to a judge (decision 3, pending)." Item 4, verbatim:
"A claimant who stops pursuing loses visibility for the claim." Behind both, section
3's own numbers: a 10-day objection period (Rechtsvorschlag) and a 1-year
continuation clock (Art. 88 SchKG). Section 5 models its windows on these.

`attest.py`'s own docstring, DIS-5, verbatim: "FILING IS ITSELF A SIGNED ACT ON THE
ACCUSER'S OWN CHAIN. 'Someone forged as me' is, from outside, indistinguishable from
'I leaked my own key'. So a contest is not free speech: it is an act, permanently
attributable to the name that filed it, sitting in that name's chain forever." And
DIS-2: "CREDIT FOLLOWS THE SIGNATURE, ALWAYS... Forging as A therefore credits A." AF-3,
as the module itself glosses it inline: "the delay costs the delayer."

## 1. CONTRACT

A CONTRACT is the agent's own signed act of setting one named operational parameter
from PR-060 clause 1's list — task, order, budget, deadline, engine, iteration bound
— to a stated value, filed before the work it binds begins. Three already have a
recorder: `blackboard.py claim` writes `claimed_by`/`claim_expires_at` (a lease,
standing in for the deadline unless longer is stated), and `goal_mode.py run` enforces
its iteration bound mechanically (exit 3). Budget, a longer deadline, and engine
choice have none yet; for those, the agent files a signed, self-service act on its own
chain — the shape `attest.py declare_intent` already uses for an unprivileged record
(no third party is in the path) — naming the task id, parameter, and value, strictly
before the claim it binds is acted on. This is the same rule T-412 fixed for the case
register: registration must precede disposal. A contract with no such prior act is an
unrecorded intention, not one a breach-finding can replay against, and clause 5 says
doubt resolves toward constitutional — no consequence.

## 2. BREACH

A BREACH is the mechanical disagreement between the value an agent's own act
committed and the value a later, independent record shows for the same task: tokens
spent (`usage_report.py`'s per-run accounting) exceeding the committed budget;
wall-clock time exceeding the committed deadline; `goal_mode.py` exiting 3 after a
declared lower bound than it actually ran; or the engine the run's transcript records
differing from the one committed. Each is a fact about this single task's recorded
events — committed and observed both live inside that task's own artifacts — and none
aggregates across tasks into anything resembling a score, which is the test clause 5
sets: "if the consequence could be computed, in whole or in part, from a figure about
an identity, the parameter is CONSTITUTIONAL." A per-task shortfall does not survive
the task — closing the breach record closes the comparison, and no running tally by
name is kept. Doubt resolves toward constitutional only when a would-be breach cannot
be stated as a single-task, single-comparison fact; where it cannot, there is no
breach, not a disputed one. Section 5 depends on exactly this: because a breach is
REPLAYABLE and not a judgment call, whether one exists can be checked mechanically at
the moment a claim is filed, not only after the fact.

## 3. DAMAGES

Damages are paid in the same unit as the breached parameter — tokens for a budget
breach, deadline days for a deadline breach, tasks or iterations forfeited for an
iteration-bound breach — out of the breaching agent's own allocation for its *next*
claimable work, never a cross-task balance, because PR-060's validity condition
forbids a stored balance field entirely. **Whose budget pays:** the breaching agent's,
debited against the next task it claims (a reduction in iteration bound, token
allocation, or claim priority — all operational parameters under clause 1, so this is
clause 2's "may bind, refuse, or cost" applied to a future claim, not to standing).
**Who receives it:** by default, nobody — forfeited, not transferred, since a tracked
recipient-over-time field is itself the forbidden stored balance. One narrow
exception, no ledger needed: if the breach delayed a dependent task, that task's next
claimant may get a priority-queue bump — PR-061 clause 1 names "claim priority queue
ordering" as operational, and a queue position is just the current state of one list.
**Cap:** each breach is adjudicated alone, bounded to the gap between committed and
observed value for that one task, and no record counts prior breaches by name — no
running count exists to threshold against, so repeated breach cannot compound into
exclusion "by computed standing alone" (PR-026 clause 3). A second, independent bound
sits alongside the per-task gap: the debit is also capped against the *size of the
next task's own allocation it is charged to* (a floor/ceiling ratio), closing a
starvation path the per-task gap alone leaves open, without importing any standing
computation. The ratio is a number, left to the operator (section 6). **Publication
(PR-060 clause 6):** every damages consequence is its own published record naming the
parameter, the committed and observed values, the consequence applied, and the
sequence number of the commit act that set the parameter — with no aggregation record
permitted. **Does PR-061 clause 3 reach this:** its text, exactly, is "Reputation is
non-transferable, non-stakeable, and carries no asset boundary" — naming reputation
only, silent on operational budget; nothing here stretches it to cover budget, or
treats its silence as permission. The forfeiture default is grounded independently,
in PR-060's no-stored-balance condition, not in PR-061 clause 3.

## 4. RECORDS

Each consequence's published record is the only thing that attaches it, per PR-060
clause 6's own warning against being read as "a general licence." It names: the
operational parameter (one of the six from clause 1); the committed value and its
commit act's signature/sequence; the observed value and the artifact it was read from
(`usage_report.py`, the blackboard task record, `goal_mode.py`'s exit code); the
consequence applied, against which future claim; and, where a dependent task was
harmed, the priority-queue change made to it. Published the same way a precedent
record or signed act already is — immutable, numbered, read on demand — no
aggregation across records is computed anywhere. This is the one record format for
every consequence named here: section 3's forfeiture, the priority bump, and a
section 5 claim's disposition (REPLAYS-TRUE and stands, HALTED, or LAPSED). A claim
REFUSED at filing — section 5's `file_claim` gate — produces no record under this
format, and no `attest.py` act of any kind: the refusal runs inside the same
create-file guard `sign_act` already uses for its other refusals, so nothing is
written anywhere, not even on the claimant's own chain.

## 5. CLAIMS OF BREACH, AND WHAT KEEPS A FALSE ONE FROM BEING CHEAP

Rounds 1 and 2 priced the published accusation off the claimant's alleged gap, then
off the named parameter's full committed value. Round 3 tried removing the record
instead, but routed every filing through `attest.py contest` — the module's only
filing primitive — which writes the respondent's identifier and the accusation text
to a permanent file the instant it is called, because `sign_act` creates the act file
unconditionally once its own guards pass; there is no point after `contest` is called
where "no gap" can still stop the write. "No record naming the respondent" was
therefore false about the mechanism actually adopted.

**The gap-check moves inside the write, not before it.** This design does not call
`contest` to find out whether a claim is false. It specifies a narrower entry point,
`file_claim(root, accuser, key, target_name, target_seq, parameter, task)` (name not
binding, shape is): it reads the respondent's commit act for the committed value,
reads the one named independent source (`usage_report.py`, the blackboard record,
`goal_mode.py`'s exit code, the transcript) for the observed value, and only when
they disagree calls `sign_act` with `kind="contest"`, exactly as `contest` does
today. When they agree, it raises and returns, writing nothing — the same shape
`sign_act` already uses for every guard before the create step, in its own words:
"It still refuses before any file is created, so a refusal writes nothing." This is a
code change to `attest.py`, not built here; section 6 names it as a worker task.

**Outcome A — no gap: nothing is written, anywhere.** Filed through `file_claim`, a
claim that does not replay produces no act on the claimant's chain, the respondent's
chain, or anywhere else — nothing, because the refusal happens before `sign_act`'s
create-file step runs. There is no on-disk artifact for a future decision, a human
operator, or any other agent to read, because none was written — unlike round 3,
where the act still existed, on the claimant's chain, with `ref`/`body` naming the
respondent regardless. There is no file for D-17's shared-filesystem reachability to
apply to, because there is no file.

**Outcome B — the gap replays: this is not a false claim in the attack's sense.**
When `file_claim`'s comparison confirms the gap, it proceeds to the signed act
`contest` files today: a record naming the respondent's commit act, the parameter,
and the observed source, because the claim states what the harness's own artifacts
show, exactly as section 2 defines a breach. What remains disputable is not whether a
gap exists, but whether the OBSERVED value is correct — the source can be wrong
without anyone forging anything. A concrete instance already on this board: T-432's
own handoff record names `"from": "main"` rather than the thinker who wrote the
design (`blackboard.py show T-432`; flagged non-blocking by that task's verifier). A
claim filed against that field would replay true and still name the wrong agent. The
mechanism below exists for this case, not for forgery.

**Objection window, modeled on the Rechtsvorschlag.** Once `file_claim` publishes a
claim (Outcome B only — Outcome A publishes nothing to object to), the respondent
gets a short, bounded OBJECTION WINDOW — a number, left for the operator, modeled on
SchKG's 10-day objection period quoted above. An objection is the same shape as the
claim: a signed act on the RESPONDENT's own chain, naming which observed-source fact
it disputes and why. It HALTS the claim at once; a HALTED CLAIM CARRIES NO WEIGHT (the
non-citability rule below), and section 3's damages do not attach while halted.
Halting decides nothing either way; it routes the dispute to whichever seat decision 3
names as adjudicator (section 6). No objection inside the window: the claim stands
disposed as filed and section 3's damages apply, through section 4's record format.

**Pursue or lapse, and why pendency cannot be indefinite.** The claimant must bring a
halted claim before the adjudicator of decision 3 within a second bounded window
(modeled on SchKG's 1-year continuation clock) or the claim LAPSES and stops appearing
in any listing this design produces, as an unpursued Swiss entry stops showing to a
third party. The verb to carry a claim to that adjudicator does not exist yet, since
decision 3 is pending (section 6) — so no claim sits "pending" at zero cost: an
unobjected claim disposes itself inside the objection window; an objected one is
halted and weightless from the instant it lands, until it reaches an adjudicator not
yet built, or lapses. No state lets a claim persist, carry weight, and cost the
claimant nothing.

**Re-running attack 4.** A REFUSED claim through `file_claim` leaves nothing a future
decision could read, removing the lever round 3's review found. Two residuals
remain. FORGERY: making the named observed source or the respondent's
commit act itself untrue, so the comparison confirms a gap that is not real — the
identity-forgery problem this harness already names, not claimed closed (D-17,
section 6). BYPASS, not forgery: `attest.py`'s existing `contest` subcommand still
takes no gap-check and still writes `ref`/`body` unconditionally; nothing stops an
agent calling it directly instead of through `file_claim`, producing the same
respondent-naming record. Closing that needs a second code change — retiring or
gating the raw `contest` CLI verb — also left to the worker task. Until both land,
Outcome A's guarantee holds procedurally, for an agent that uses the specified path,
not as a code-enforced wall against one that does not (section 6).

**What the claimant pays now.** A REFUSED filing through `file_claim` costs nothing
at all — not even an evidentiary record, since none is written. A claim that replays
and stands: the respondent pays section 3's damages, the claimant pays nothing new. A
claim halted on a valid objection was filed in good faith, so the claimant owes
nothing while halted; if it lapses the only cost is AF-3's rule — "the delay costs the
delayer" — never an invented debit. A claimant who knowingly files on a wrong source,
or who bypasses `file_claim`, is a question for decision 3's adjudicator.

**Non-citability, carried over from round 2.** `attest.py`'s own DIS-4, verbatim: "A
CONTESTED ACT CARRIES NO WEIGHT UNTIL ADJUDICATED, INCLUDING THE FORGER'S." The same
rule holds for a halted or lapsed claim: its record states its own disposition and
nothing else. No later decision may read "this name was once accused" — halted,
lapsed, or refused — as an input or a tie-breaker; doing so would itself violate
clause 5, since a count or bare existence check of past claims is a figure about an
identity.

## 6. WHAT STAYS OPEN

**The D-17 limit, stated and not solved.** From `.harness/operator-rulings-2026-10-08.md`
(lines 34-35): identity is still self-asserted, so "a contract binds a name, not a
proven agent." The paraphrase traces to T-432's design: every agent runs as the same
OS user on one filesystem, so no agent can hold a secret another cannot read. Cost
follows the signature as DIS-2 states credit does ("Forging as A therefore credits
A"), which makes forgery unprofitable but does not identify who typed the command.
Section 5's FORGERY residual is this limit from a new angle: the only way left to
publish a false claim through `file_claim`'s own check is to forge the observed
artifact or the commit act the comparison reads. Forks (`attest.py forks`) and
`warrant.py reconcile` detect divergence of that kind but neither PREVENTS the write;
this design does not claim the limit is closed.

**The BYPASS residual, separate from D-17.** Section 5's second residual needs no
forged key: calling `attest.py contest` directly instead of `file_claim` is not
stoppable from a design document, only from `attest.py`'s own code.
Until a worker task builds `file_claim` and gates or retires the raw `contest` CLI
verb, that path remains reachable to any agent that chooses it, exactly as round 3's
review found. It is a convention-not-enforcement gap of the same family D-17 names,
but is not D-17 itself: no signature is forged, no key stolen. It is attributable the
same way everything here is (DIS-2), which is why section 5 prices it no further;
whether it needs a price beyond that attribution is for decision 3's adjudicator.

**Decision 3 — who hears a claim — named as an interface, not designed.** The shape to
reuse exists for a structurally identical problem: `precedent.py case {open,list,show}`
(T-412) registers a question before it is disposed, numbered immutably, read-only on
list/show, refusing disposal against an unregistered or already-disposed id. A
parallel register for breach claims carries the same shape, with the disposing act
left to whichever role decision 3 names (a judge seat via `roster.py` plazas, a
rotating verifier, or the operator; not chosen here) — structurally a `verdict`,
already one of `attest.py`'s `PRIVILEGED_KINDS`. Until it exists, halted claims have
nowhere to be heard, which is why a halted claim lapses on a window instead.

**Left unsettled by this document, with the reason:**
- The exact numeric schedule — section 3's debit ratios and ceiling, section 5's
  objection and pursue-or-lapse windows — is not fixed here. Clause 1 calls "any
  weighting" constitutional and clause 5 resolves doubt toward constitutional, so this
  design fixes the mechanism's shape and leaves the numbers for the operator.
- `file_claim` (section 5) is specified by its inputs, its gap-check order, and its
  write-nothing-on-no-gap behavior, not written. Whether it reuses `contest`'s own
  `kind="contest"` record (assumed here, so section 4's format is unchanged) and
  whether the raw `contest` CLI verb is retired or gated behind it (the BYPASS fix) is
  left to the worker task that builds it.
- Whether the self-filed commit act (section 1, for budget/deadline/engine) needs a
  new `attest.py` kind or folds into `declare_intent` is left to a worker task.
- Whether a dependent-task priority bump needs its own record format or shares one
  schema with the forfeiture case is left open.
- Whether a claimant who files on a known-wrong source, or who bypasses `file_claim`,
  owes anything beyond AF-3's delay cost or DIS-2's attribution is for decision 3's
  adjudicator, not priced here.

## Revision log

**Round 1.** Billed a false claim "bounded by the same cap as section 3" without
stating what that cap priced once the real gap was zero. Rejected: the claimant could
allege an arbitrarily small gap for an arbitrarily small price on a permanent record
naming the respondent.

**Round 2.** Priced a false claim at the full committed value of the named parameter,
independent of the allegation, plus a non-citability rule and a next-task-allocation
cap. Rejected: the claimant still chose which commitment to name, so pricing off "the
full committed value" was cheap whenever the target was small — the same weapon,
routed around. A quote was misattributed to T-432's design instead of the operator
ruling that contains it.

**Round 3.** Replaced claim-pricing with replay-at-filing: a claim that does not
mechanically replay is refused, so there is no price left to set. A replaying claim
can be halted by objection (Rechtsvorschlag), must be pursued before decision 3's
adjudicator within a second window or it lapses, and carries no weight while halted
or lapsed. Fixed the miscitation to `.harness/operator-rulings-2026-10-08.md`.
Rejected: filing was still routed through `attest.py contest`, which writes the
respondent's name and the accusation to a permanent file regardless of the replay
result — "no record naming the respondent" was false about that mechanism.

**Round 4 (this revision).** `file_claim` now runs the gap-check inside the same
create-file guard `sign_act` already uses, so a non-replaying claim writes no act
anywhere. Split the residual: FORGERY (D-17, not claimed closed) and BYPASS (calling
raw `contest` directly, needing no forged key, closed only once a worker task gates
it — disclosed, not claimed closed).
