# T-452 design: suits between parties, an agentic judge, appeal to the operator

**Date:** 2026-10-21 · **Role:** thinker · **No source edits in this document.**
**Builds on `.harness/design-T-436-contracts.md` (round 4, ratified by the operator's
ruling of 2026-10-08 and named again in the ruling of 2026-10-21, decision 3). Design
only; the worker task list at the end is not boarded.**

## 0. What decision 3 ratified, quoted

`.harness/operator-rulings-2026-10-21.md`, Decision 3, verbatim: "The case register
accepts suits: claimant, respondent, contract, damages claimed. The respondent receives
notice and may answer before judgment. An agentic judge decides, distinct from both
parties. The operator is the final appeal." And its limit: "A judge seat exists only
inside a warrant the operator signs. The design comes first and builds on what T-436
left: claims replayed at filing, and an objection that halts. Construction waits on the
identity tokens." And what remains owed: "Three numbers from T-436: the objection
window, the pursue-or-lapse window, and the damages cap. The judge design proposes
values with reasons; the operator ratifies them."

The 2026-10-08 ruling fixes the unit before any of this: "Adelante la idea del
presupuesto operativo como costo de indemnización... The breaching party compensates
with part of its own budget: tokens, tasks or deadline days that the contract commits.
Reputation is never the unit." Nothing here proposes a different unit.

## 1. The suit, as an extension of the case register

`precedent.py case open` today (`.harness/bin/precedent.py:981-1012`) writes exactly
`{id, question, task, opened_by, ts, status, disposal}`. The rule this reuses is T-412's,
restated by T-436, quoted: "This is the same rule T-412 fixed for the case register:
registration must precede disposal" (`.harness/design-T-436-contracts.md:106`) — and
T-412's own words for the mechanism itself: "The mechanism is a precondition, not an
inference" — and "A CLI verb, not a required field on task creation... `case open` is
called by the agent that is about to reach for the layer, at the moment it reaches." A
suit reuses this verb exactly, with one addition: an optional `--suit` block of four
fields, written into the case record as `rec["suit"] = {claimant, respondent, contract,
damages_claimed}`, so a suit-case and an ordinary case stay one schema (T-412's point:
inventing a second denominator is the mistake T-412 exists to prevent). `contract`
points at the T-436 §1 commit act that set the breached parameter — a `blackboard.py
claim` record, a `goal_mode.py` iteration bound, or the self-filed `attest.py sign`
act T-436 §1 specifies for budget/deadline/engine. `damages_claimed` is the claimant's
own allegation, in operational-budget units (tokens, tasks, or deadline days — never
reputation, per the 2026-10-08 ruling) — and it is **informational only**. T-436's
round 1 and round 2 were both rejected for exactly the failure of letting the
claimant's own number set the price (round 1: "the claimant could allege an
arbitrarily small gap for an arbitrarily small price"; round 2: "the claimant still
chose which commitment to name"). `damages_claimed` is not reintroducing that: section
4 below bounds the actual consequence by the mechanical gap and the operator's cap,
never by this field.

**Filing, reusing T-436 §5 verbatim.** The claimant opens the suit-case first (cheap,
no key, per T-412's "biased toward over-registration"), then calls `file_claim` exactly
as T-436 specifies it: "it reads the respondent's commit act for the committed value,
reads the one named independent source... for the observed value, and only when they
disagree calls `sign_act` with `kind="contest"`... When they agree, it raises and
returns, writing nothing." **Outcome A** (no gap): the suit-case stays open,
undisposed, with no `attest.py` act anywhere — T-436's own words, "There is no on-disk
artifact for a future decision, a human operator, or any other agent to read, because
none was written." An open-and-never-disposed case is not a defect; T-412: "That is not
a defect in the register — it is the measurement." **Outcome B** (the gap replays): the
`contest` act is filed, named by the suit-case, and notice (section 2) issues.

## 2. Notice and the answer

A respondent in this harness is a *name*, not a running process, so notice cannot be
"delivered" to a process — it is published where any later dispatch of that name will
see it, exactly as every other instruction in this harness already is: a board task.
`blackboard.py add-task` has no "addressed to" field (`add-task --help`, verified
live), so notice is addressed by convention, in the title and description: `role
worker`, `engine any`, title `"NOTICE to <respondent>: answer suit C-NNN by
<deadline>"`, `--depends-on` nothing (it must be claimable immediately), artifact
pointing at the suit-case. Any agent can *claim* and *read* this task (claiming is not
answering), but only an **answer act** on the respondent's own chain counts: `attest.py
sign --name <respondent> --key <respondent's key> --kind answer --task <notice task>
--ref C-NNN --body {...}`. `answer` is a new, **unprivileged** kind, the same shape
T-436 §1 already uses for the self-filed commit act — "the shape `attest.py
declare_intent` already uses for an unprivileged record (no third party is in the
path)" — because an answer, like an intent, costs the answerer nothing but its own
signature and needs no prior intent of its own.

**Within the objection window** (number proposed in section 6): any answer disputing
the claim — whether it disputes the OBSERVED-SOURCE fact in T-436's narrow sense, or
disputes the contract's scope, denies the contract, or counter-claims — **halts** the
suit, exactly as T-436's objection does: "It HALTS the claim at once; a HALTED CLAIM
CARRIES NO WEIGHT... Halting decides nothing either way; it routes the dispute to
whichever seat decision 3 names as adjudicator" — which is now the judge (section 3).
T-436's own non-citability rule, from `attest.py`'s DIS-4, carries over unchanged: "A
CONTESTED ACT CARRIES NO WEIGHT UNTIL ADJUDICATED, INCLUDING THE FORGER'S." A halted
suit must be brought to the judge within the pursue-or-lapse window or it LAPSES —
T-436: "the claim LAPSES and stops appearing in any listing this design produces."

**No answer inside the window**, in the narrow case T-436 already closes (a single-task,
single-parameter, mechanically-replayable gap, with the contract and the observed
source both already read by `file_claim`): the claim "stands disposed as filed and
section 3's damages apply" — self-executing, because nothing is left for a judge to
weigh; the gap-check already was the adjudication. **No answer, but the suit is not
reducible to that narrow shape** (the claimant alleges breach of a contract whose scope
or existence is itself contested, or names damages beyond the single parameter
`file_claim` compared): silence does **not** self-execute a debit. PR-026 clause 4,
verbatim: "A written, reasoned, tiered decision remains the only instrument that
changes anyone's status: the machine flags, an agent decides, the record shows why."
An unanswered suit of this second kind still goes to the judge, who signs a default
judgment on the papers filed — the record (section 4) still names the judge's own act
as the thing that attached the consequence, so clause 4 is never worked around by
silence. This is also why PR-026 clause 3 is respected rather than merely cited: "No
automatic demotion, suspension or exclusion of any identity by computed standing
alone" — a debit here is never computed from standing; it is computed from the gap
T-436 §2 already defines, task-local and never aggregated.

## 3. The judge

**Seat, published before filled** — `roster.py charter` and `roster.py plazas`, exactly
as W-002 already does for every other office, and exactly as decision 3 requires: "A
judge seat exists only inside a warrant the operator signs." Concretely: `roster.py
charter --colegiado judge --incentive "<what a judge is paid for: a reasoned verdict,
not a favorable one>"`, then `roster.py plazas --epic <the suit's epic> --colegiado
judge --role verifier --count <N>`, published before any suit in that epic needs one.
`roster.py issue --name <judge-name> --colegiado judge --role verifier --epic <epic>`
fills the seat; role `verifier` because a judge disposes of a producer's dispute the
same way a verifier disposes of a producer's work — ORCHESTRATION.md's own "Producer ≠
approver, always."

**Recusal.** The judge must be distinct from both parties and from anyone who sponsored
or voted in a related `deliberate.py` dossier. There is no gate for this, and the
design does not pretend otherwise: `roster.py eligible` is, in its own words, "REPORT,
never a gate. See module docstring and PR-017" (`.harness/bin/roster.py:366`), and its
`IS_NOT_A_GATE` field reads: "advisory only; F6 is not computed from this field until
an amending record is published (PR-017)." The module docstring states why, verbatim:
"changing what F6 computes from is a constitutional act, and PR-017 requires the
amending record before the text lands." PR-017's own ratio is exactly that amendment
procedure: "a build session that needs a constitutional addendum requests it
explicitly, reasons it with the operator, and only then delimits the instance that
later constructions will reference; the amendment is published as a tier 1 or 2 record
naming the IC rules changed and the version jump before any text edit lands." T-452
does not request that addendum — the recusal check it specifies is therefore the same
class of REPORT `eligible` already is, run by hand at `issue` time by whoever fills the
seat: (a) the candidate's name is not the claimant's or respondent's name; (b) run
`roster.py eligible --record <any precedent record either party published that bears
on this suit's contract>` and confirm the candidate is not `author` and not in
`same_colegiado_would_be_excluded`; (c) if the suit's contract traces to a
`deliberate.py` dossier, read that dossier with `deliberate.py show <id>` and confirm
the candidate neither appears among its sponsors (`sponsor`) nor cast a ballot
(`vote`) — read directly off the dossier record, the same manual-read discipline
`eligible` already uses, not a new mechanism. This is advisory exactly as far as
`eligible` is advisory, and no further: a worker task may later promote it to a gate
only through PR-017's own amendment route, never by this document.

**Warrant payload for the seat, UNSIGNED.** Mirroring `warrant.py draft --help`
exactly (`--colegiado NAME=INCENTIVE`, `--plaza COLEGIADO/ROLE=N`, `--name
NAME:COLEGIADO/ROLE:PUBKEY[:PERSONA]`, `--valid-until`):

```
warrant.py draft --epic gen-10-courts \
  --colegiado judge="a reasoned verdict on a filed suit, paid to distrust both parties" \
  --plaza judge/verifier=1 \
  --name <judge-name>:judge/verifier:<pubkey>:"agentic judge, suits epic gen-10-courts" \
  --valid-until <epic close + margin>
```

This is a **draft**, UNSIGNED — `warrant.py`'s own module docstring, verbatim: "`draft`
produces an UNSIGNED payload and prints the command the operator runs. No code path
here can sign a warrant. That is the point, and `test_warrant.py` asserts it."
Nothing above is signed by this document or by any agent; the operator's `ssh-keygen -Y
sign` step, out of band, is the only thing that mints the seat (D-16/D-17, section 7).

## 4. Judgment

The verdict is `attest.py sign --name <judge> --key <judge's key> --kind verdict --task
<T-ID> --ref C-NNN --body {...}`. `verdict` is already a `PRIVILEGED_KINDS` member
(`attest.py:144`), so two things are already mechanical and need no new code: **intent
first** — `sign_act`'s own guard, verbatim: "D3a: what can be refused without reading
the chain is refused here... `--task` is required for a {kind} act: {kind} is
privileged, and D3a links the exercised privilege to the intent by identity AND task
id"; the judge must `declare-intent --for-kind verdict --task <T-ID> --declares
"judgment on suit C-NNN"` before signing, or the sign refuses with "has N open
intent(s) but none for a 'verdict' act on task..." — and **task-bound**, so a verdict
with no task cannot be filed at all.

**What it may order.** Exactly T-436 §3's shape, no wider: a debit against the
respondent's own allocation for its *next* claimable work — a reduction in iteration
bound, token allocation, or claim priority, bounded by (a) the per-task gap `file_claim`
already measured or, for an unanswered non-mechanical suit, the gap the judge's own
reasoning finds on the papers filed, and (b) the floor/ceiling ratio against the size of
that next task's own allocation (section 6, the third number). T-436 §3, verbatim, on
who receives it: "by default, nobody — forfeited, not transferred, since a tracked
recipient-over-time field is itself the forbidden stored balance," with "one narrow
exception... if the breach delayed a dependent task, that task's next claimant may get a
priority-queue bump." The judge orders nothing a `determination` could not already name
— no reputation figure, which PR-022 clause 4 ("NO CONSEQUENCE ATTACHES. NONE: no
weighting, no gating, no privileges") and PR-061 clause 3 ("Reputation is
non-transferable, non-stakeable, and carries no asset boundary") both bar regardless of
what a judge wants to order.

**The published record, PR-060 clause 6.** Verbatim: "THIS RECORD AUTHORIZES NO
CONSEQUENCE NOW. It authorizes the DISTINCTION and nothing else. Every individual
consequence still requires its own published record, which must name the operational
parameter, the consequence, and the agent's own act of setting that parameter." The
verdict's own body is that record: it names (i) the operational parameter (one of
PR-060 clause 1's six — here, the committed value named in the suit's `contract`
field), (ii) the committed value and the sequence number of the commit act that set it
(T-436 §4's own list), (iii) the observed value and its source artifact, (iv) the
consequence ordered and against which future claim it is charged, and (v), where a
dependent task was harmed, the priority-queue change made to it. Disposing the
suit-case reuses `dispose_case()` (`precedent.py:1051`, already general over `verb`/
`ref`/`by`/`task`) with `verb="verdict"` and `ref` pointing at the judge's signed act —
a worker task adds the CLI surface (`precedent.py case verdict --case C-NNN --judge
<name> --seq <seq> --task <T-ID>`) that calls it after validating the referenced act is
kind `verdict`, signed by an issued `judge` colegiado name, and task-matched;
`validate_case_for_disposal`'s existing refusal of a second disposal of one case
(T-412/S-1) is reused unchanged.

## 5. Appeal to the operator

A party signs an **appeal act** — unprivileged, the same shape as `answer` — naming the
verdict's sequence and case, within a window after judgment (left to the next decision
sheet; not one of the three numbers this document owes, since decision 3's text names
only the objection window, the pursue-or-lapse window, and the damages cap). This is not
a new primitive inside `attest.py`: it reaches the operator the way every decision in
this harness already does — a card on the next decision sheet, the operator answering
in plain words, recorded durably. Both ruling files read for this design are exactly
that record: `.harness/operator-rulings-2026-10-08.md` opens "Nothing was signed, and
nothing needed to be: the ruling attaches no consequence, so no warrant carries it," and
the 2026-10-21 file: "Nothing was signed in ruling: no ruling here attaches a
consequence, so no warrant carries it."

**What stays frozen meanwhile.** The verdict's damages consequence — the debit against
the respondent's *next* claimed task — is not applied while an appeal is open, the same
freeze T-436 already gives a halted claim: "a HALTED CLAIM CARRIES NO WEIGHT... section
3's damages do not attach while halted." The verdict record stands on the chain (it is
not retracted merely by being appealed), but the operational consequence is held until
the appeal window lapses unused or the operator rules.

**What the operator signs.** If the operator upholds, nothing new is signed; the frozen
consequence executes. If the operator overturns, the operator does **not** sign a
retraction directly — `attest.py`'s retract verb is, by design, reflexive only: T-406,
verbatim, "You cannot retract someone else's statement. A retraction is a speaker
disowning their own act... the target must be on the retractor's own chain — you cannot
disown another name's act." This is not hypothetical here: decision 4a of the very
ruling this design reads already does exactly this move for a verdict — "retract the
false verdict of 2026-08-17: `revision-doctrina` seq 1, kind verdict, ref T-376. The act
file stays; every tool that reports it reports the retraction with it" — the retraction
is signed by the original signer, at the operator's instruction, not by the operator.
An overturned verdict here follows the same path: the operator's ruling instructs the
judge to run `attest.py retract --name <judge> --key <judge's key> --seq <seq>
--reason "<operator's ruling, quoted>"`. If the judge is unavailable or does not comply,
the residual is named rather than hidden: the operator's durable ruling is itself the
record that the consequence must never execute, even though the on-chain verdict act is
not formally retracted — structurally the same asymmetry T-406 already accepts for
every retraction, verbatim: "a forger can file a false retraction of a true act, and this
design does not prevent that" (`.harness/design-T-406-retraction.md:88-89`) — restated here,
as this design's own analogy and not a quote from any file, as "an unretracted but
overturned verdict can sit on the chain, and this design does not prevent that either" — in
both cases the
operator's own durable record, read by every tool that reports the act, is the actual
instrument of record, not the chain state alone).

## 6. The three numbers the operator still owes, proposed and unratified

**UNRATIFIED. Proposed here with reasons; the operator ratifies, per decision 3's own
text: "The judge design proposes values with reasons; the operator ratifies them."**
PR-060 clause 1 names "any weighting... any tier boundary" constitutional, and clause 5
resolves doubt toward constitutional — these numbers are exactly that doubt, which is
why T-436 §6 left them open and why they are proposed, not fixed, here.

1. **Objection/answer window: 7200 seconds (2 hours).** Units are wall-clock seconds,
   not calendar days, because the parties "live only while a task runs" — the native
   clock an ephemeral agent can be measured against is the same one `blackboard.py
   claim`'s default lease already uses (3600 s). Two leases gives a respondent's name a
   realistic chance to be re-dispatched and claim the notice task even if its last run
   ended mid-lease, without letting a suit sit open long enough to stall the DAG
   (ORCHESTRATION.md's "nothing stalls" invariant, PR-037).

2. **Pursue-or-lapse window: 1 epic-close cycle, capped at 14 days wall-clock,
   whichever comes first.** This harness already runs its own governance on epic
   grain, not calendar grain: decision 1 of the 2026-10-21 ruling fixes dispatch-token
   signing at "one signing action per epic," and the same ruling names "Routine checks
   at every epic close: `attest.py forks`, `warrant.py reconcile`" as the harness's own
   cadence for catching exactly this class of drift. A halted suit that outlives the
   epic it was filed in is already stale by that cadence; the 14-day wall-clock cap is
   a backstop against an epic that simply never closes, so pendency is still bounded in
   the one unit ("live only while a task runs") this design is asked to use.

3. **Damages cap: 25% ceiling / 5% floor of the respondent's next claimed task's own
   allocation.** This is T-436 §3's own named second bound, verbatim: "a second,
   independent bound sits alongside the per-task gap: the debit is also capped against
   the size of the next task's own allocation it is charged to (a floor/ceiling ratio),
   closing a starvation path the per-task gap alone leaves open... The ratio is a
   number, left to the operator." 25% is proposed because it is large enough to be felt
   (deterrence, per the Swiss brief's own complaint that "deterrence against false
   claims is weak") without being able to zero out a respondent's next task outright,
   which would read as exclusion by computed effect rather than by a reasoned decision
   — the thing PR-026 clause 3 forbids when done "by computed standing alone," and the
   thing a 100% ceiling would resemble even though it is computed from a gap, not from
   standing. The 5% floor exists so a large real gap charged against a small next-task
   allocation does not round away to nothing.

## 7. Identity: what this design assumes until T-446's tokens are wired

T-446 has since landed (`.harness/tasks/T-446.json`, status `done` as of this round;
it was `in_progress` under worker `worker-g10-token` when this design was first
drafted), building `dispatch_token.py`'s `draft`/`verify` only — its own acceptance
criteria: "No wiring into blackboard.py or lock.py (that is T-454)." T-454 itself is
still `open` (`.harness/tasks/T-454.json`), so the assumption below still holds. This
design assumes, until T-454 lands: every name in a suit — claimant,
respondent, judge — is **self-asserted**, exactly as every other name in this harness
is today. PR-023 clause 4, verbatim: "Sybil minting is closed by this gate and by
nothing else: nothing else closes it, do not pretend otherwise" — minting a *name* is
closed; nothing closes *which process asserts it on a given call*. D-17, verbatim:
"Every agent runs as the same OS user on the same filesystem... no agent can hold a
secret another agent cannot read, and therefore no agent can have an unforgeable
identity." Concretely: claiming the notice task, signing an `answer`, and being issued
into the `judge` plaza all rest on `--by`/`--agent`/`--name` strings the caller
supplies, not on anything the court verifies independently. Once T-446's tokens exist
and T-454 wires verification into `claim`/`lock`, a later worker task (not this one)
should extend the same check to: the notice task's claim, the `answer` act, and the
`verdict` act — each presenting a token binding exactly `(agent_name, task_id, role)`
before the signature is accepted, closing the gap this section names rather than
papering over it. Until then, the court's guarantees sit on the same footing as
everything else in this harness: D-20's disincentive package (DIS-1 through DIS-5) and
D-22's impersonation rule set (IMP-1 through IMP-7), neither of which prevents
anything — D-22 IMP-7, verbatim further down from the quoted excerpt: "NOTHING ABOVE
ATTACHES A CONSEQUENCE" — they only make impersonating a party or a judge
"less profitable, more visible, or more expensive to sustain" (D-22's own framing),
via DIS-2 ("Credit follows the signature, always... Forging as A therefore credits
A") and IMP-1 ("Benefit is never reassignable... impersonation is therefore
structurally a DONATION").

## 8. Attacks

**False suits** (a claimant files on a gap that does not exist). Closed procedurally by
reuse of T-436's `file_claim`, not newly: Outcome A writes nothing, so a false suit in
this sense costs the claimant nothing and leaves nothing to adjudicate — T-436's own
residual, unchanged: the BYPASS path (calling `attest.py contest` directly instead of
through `file_claim`) "remains reachable to any agent that chooses it... Closing that
needs a second code change," left to T-436's own worker task, not this one.

**Collusive suits** (claimant and respondent are one principal under D-17, filing
against itself to extract a priority-queue bump for a "dependent task," or to generate
a published record for some other reason). D-17 makes this unpreventable in principle —
one OS user can author both chains — so the residual accepted here is DIS-2/IMP-1's
general one: the "harmed" dependent task's priority bump is the only transferable
benefit T-436 §3 names at all, and it only ever moves to a THIRD task's claimant, never
back to either party of the suit — a collusive pair gains nothing a solo forger
couldn't already attempt by filing a real contest, and the forfeiture default (section
4, "by default, nobody") means the respondent side of a collusive pair pays a real cost
(its next-task allocation shrinks) for no corresponding gain to the claimant side,
which is DIS-2's donation shape applied to two names instead of one. What is **not**
closed: nothing here can tell a genuinely adverse pair of names from a collusive one,
because D-17 does not let it.

**Judge capture** (a respondent or claimant engineers who fills the seat, or recusal is
skipped). Section 3's recusal is advisory, same as `eligible` generally — stated, not
solved. What is accepted as residual: the seat is published (`charter`/`plazas`)
*before* a specific suit exists, per decision 3's own requirement, so a party cannot
retroactively shape a plaza to fit a chosen judge for a suit it has already filed — the
W-002 pattern this reuses ("signed plazas bound HOW MANY seats exist. They do not bound
WHO occupies them," quoted in `.harness/design-T-432-agent-identity.md`) names the same
limit: nothing here stops the *issuer* of the seat from choosing badly, only from
inventing a seat after the fact.

**Suits as harassment** (filing repeatedly, cheaply, to tie up a respondent's notice
window). `file_claim`'s Outcome A already prices a non-replaying filing at exactly
nothing to file but also at nothing recorded — there is no accumulating record a
harassment campaign could point to, which cuts both ways: it is cheap to file and
cheap to refuse. What bounds repetition is AF-3, T-436's own citation: "the delay costs
the delayer" — a claimant who files and lets claims lapse repeatedly pays in its own
wasted filing effort and an unpursued record, never a counted strike against it (PR-026
clause 3/clause 5 forbid building that counter without a tier-1 act lifting the
refusal). This residual is named, not solved, exactly as T-436 §6 already named the
BYPASS and FORGERY residuals without claiming to close them.

## 9. Worker task list (not boarded)

1. `precedent.py`: add the `--suit` fields to `case open` (claimant, respondent,
   contract, damages_claimed); add `case verdict --case --judge --seq --task`, calling
   the existing `dispose_case(verb="verdict", ...)`; refuse if the referenced act is not
   kind `verdict`, not signed by an issued `judge`-colegiado name, or already disposes
   another case. Tests mirror T-412 §5's registration-precedes-disposal discipline.
2. `attest.py`: add unprivileged kinds `answer` and `appeal` (same shape as
   `declare_intent`'s self-service record — no intent required, costs only the
   signer's own signature); neither becomes a `PRIVILEGED_KINDS` member.
3. The notice-task convention: a small helper (or a documented `blackboard.py add-task`
   recipe) that titles a notice task `"NOTICE to <respondent>: answer suit <case> by
   <deadline>"`, `--role worker --engine any`, no `--depends-on`.
4. `roster.py charter`/`plazas` recipe for the `judge` colegiado, as section 3 drafts
   it; the manual recusal check as a short checklist in the worker task's own note, not
   a new tool, per PR-017.
5. Falsifier tests, mirroring T-436's own revision discipline: a false suit via
   `file_claim` writes nothing (replay of T-436's existing test, scoped to a suit-case);
   an unanswered mechanical suit self-executes; an unanswered non-mechanical suit does
   not self-execute and requires a judge act; an answer within the window halts; a
   halted, unpursued suit lapses at the pursue-or-lapse window; a verdict with no prior
   intent refuses (D3a replay); a second `case verdict` on one case refuses (T-412/S-1
   replay); an appeal freezes the debit until the operator rules or the appeal window
   lapses.
6. Explicitly deferred to T-446/T-454: wiring dispatch-token verification into the
   notice claim, the `answer` act, and the `verdict` act. Do not build early — section 7
   names exactly why that would be premature.

Hand off to verifier.
