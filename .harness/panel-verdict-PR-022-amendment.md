# Third blind panel: verdict on the proposed amendment to PR-022 clause 4

**Convened:** 2026-08-15, by operator directive D4 of ruling round 3 — *"Manda la decisión 4
a un panel ciego. Me interesa saber su opinión."*

**Composition:** four panelists, four lenses, no panelist aware of the others' subject.
Constitutional coherence; adversarial attack; incentive design and monetary economics; the
case for refusal. None was shown the drafter's advocacy (`draft-amendment-PR-022.md` §3) or
its self-refutation (§6); all were instructed by name not to open that file, and all four
confirmed they did not. One disclosed that the filename appeared in unrelated grep output
and that it opened no byte of the content.

**Brief:** session-local and deliberately not tracked, since a panel brief is an input to
one proceeding and not a norm. Naming a path a reader cannot resolve is the TIER-EVIDENCE-A
pathology, so its contents are stated here instead: PR-022's ratio verbatim from the record;
its `revisit_trigger` and `scope_conditions`; the proposed clause 4 verbatim; the single
proposed consequence; eleven mechanically checkable facts each with the command that checks
it; the six records each panelist was told to read for itself; and the three-function
candidate as a marked, explicitly unratified annex, with the circularity posed as an open
question rather than as a conclusion.

---

## VERDICT: REFUSE. Four of four, unanimous, independently reached.

Not one panelist returned RATIFY or RATIFY WITH AMENDMENTS. The fourth, whose assignment
was to build the strongest possible case for refusal and then try to refute it, reached
REFUSE *and* produced the most serious argument against its own verdict — recorded in §4
below because it is load-bearing.

---

## 1. The dispositive finding, reached independently by all four

**PR-023 clause 1, verbatim:**

> (1) Phase B (**verification-burden discounts**, quorum weight, charter contestability)
> is gated on cryptographic identity with an external trust root.

The amendment's only proposed consequence is a **verification-burden discount**. It is the
first item PR-023 names as Phase B, in the same three words. PR-023's `scope_conditions` —
"any proposal attaching consequence, weighting, quorum weight or charter contestability to
standing" — reach it directly, have never been narrowed (`narrowed_scope: null`), and the
appeal that sought exactly that narrowing was REFUSED on 2026-08-15.

The constitutional panel added the fact that settles it: the refused appeal **conceded this
specific case away in its own §5**, writing that "Phase B as PR-023 defined it —
verification-burden discounts, quorum weight, charter contestability — stays gated." The
amendment therefore seeks, through PR-022, more than the refused appeal sought through
PR-023, one day after that appeal failed, without naming PR-023 at all.

The operator's standing instruction is that PR-023 is to be satisfied, not re-argued. An
amendment to a different record that delivers a PR-023-gated outcome is a re-argument
conducted in another courtroom.

**This is the coordinator's error and it is not a drafting slip.** The drafter chose the
verification-burden discount as "the smallest consequence that is still a consequence"
while writing a document whose whole thesis was that PR-023 must be satisfied rather than
appealed. It picked, out of three named items, the one the gate names first.

## 2. The self-contradiction, reached independently by three of four

**PR-022 clause 6, verbatim, and expressly left untouched by the amendment:**

> Phase A is neutral on standing: **no verification or confirmation burden varies by
> standing.** The PR-015 confirmation burden is UNIFORM for every identity in Phase A.

The proposed consequence is a verification burden that varies by standing, stated in clause
6's own vocabulary. Clause 5, also untouched, adds "no consequence may cite these figures".
Both would sit in one ratio alongside amended clause 4.

Two panelists found the sharper version. Clause 6 **quotes clause 4 as its justification**:
"by A.4's own words: no consequence attaches, none." Amend clause 4 and clause 6 continues
to assert, as active tier-1 ratio text, a proposition the record no longer contains. The
amended record would misquote itself in its own ratio — in a layer where PR-019 makes a
publish mechanically refuse over a non-verbatim quotation of someone else's ratio.

There is no reading that saves the "clauses 1, 2, 3, 5 and 6 stand entirely" premise. The
drafter read clause 6, embedded it verbatim in its own §1, and did not notice it forbade
the proposal by name.

## 3. The other collisions, each with an active tier-1 record

- **PR-024 clauses 3 and 4.** Load-bearing citation is NOT COMPUTED and `cited_by` "must
  never be used as a proxy". `reputation.py` obeys, labelling the figure
  ELIGIBLE-UPPER-BOUND. The trigger would key to a number the registry's own tier-1 record
  says is not the number.
- **PR-025 clauses 1 and 3.** Adversarial work must pay more than authorship, and
  pre-registration exists "so the constituency that benefits from cheap authorship credit
  cannot write the exchange rate later". The proposed consequence is the first exchange
  rate ever written, pays authorship, pays adversarial work nothing, and inverts the
  pre-registered ordering.
- **PR-026 clause 3, miscited by condition (e).** The verbatim text is "No automatic
  demotion, suspension or exclusion of any identity **by computed standing alone**."
  Condition (e) reported the exclusion arm only, dropped demotion and suspension, and
  dropped the operative qualifier — which is the exact mechanism the discount uses. Two
  panelists further found that the clause actually broken is **clause 4**: "the machine
  flags, an agent decides, the record shows why." A discount applied automatically on a
  computed figure is the machine deciding. **This is the coordinator's fourth miscitation
  of a tier-1 record in this session, and the first where the miscited clause was cited to
  prove the proposal was safe.**
- **PR-038 and the baseline.** "Reduced by at most one reviewer, never below two"
  presupposes a burden of three. The recorded baseline is ONE distinct verifier. So the
  clause is either inert, or it silently raises everyone else's floor to two — a burden
  varying by standing in the punitive direction, violating clause 6 twice.
- **PR-007 and SDR-01.** `ratio` is immutable; PR-007's exception is structurally consumed
  (0 v1 records remain). No verb in `precedent.py` edits a ratio. "Replace clause 4" is not
  an operation this layer can perform.

## 4. What the panel found in the TOOLS, which is worse than what it found in the draft

### 4.1 `audit --expect` read the operator's fingerprint and threw it away. REPAIRED.

Two panelists ran it. On an un-enrolled harness, `warrant.py audit --expect SHA256:<any
string at all>` returned exit 0, no ALARM, no UNVERIFIED, and no
`anchor_matches_operator` — because the un-enrolled early return sat ABOVE the block that
compares `expect`.

Three distinct states produced identical silence: un-enrolled, forged-root-without-expect,
and genuine-root-with-matching-expect. Only the third is the state a caller means.

This is the mechanism the coordinator described to the operator as the one genuinely
external check in the whole design, and the one condition (b) of the amendment rests on.
Condition (b) — "`warrant.py audit --expect` returning no ALARM" — was satisfied, today, on
a harness with no gate installed at all.

The previous repair round fixed `audit` to look at the roll. It left the branch that fires
before `audit` looks at anything. **Defect AUDIT-EXPECT-DISCARDED.**

REPAIRED: supplying `--expect` is an ASSERTION by the operator that the harness is
anchored. A false assertion is now an ALARM and exit 3. Un-enrolled without `--expect`
stays exit 0 and is marked NOT ASSESSED — silence when nobody claimed anything, alarm when
someone claimed and the claim is false. Three regression tests pin all three states,
including one that checks the alarm reaches the shell rather than only the JSON.

### 4.2 `reconcile` reported zero orphans by virtue of examining zero rows. REPAIRED.

Same shape, and its own docstring names the attack it enabled: "an agent that moves
`trust/root.pub` aside, mints freely and moves it back". Moving it aside is sufficient. A
panelist reproduced it end to end: built an enrolled sandbox, minted an unwarranted name,
confirmed `reconcile` caught it correctly with exit 3 and a precise ALARM — **that guard
holds and is recorded as holding** — then deleted `trust/` and watched the same illegitimate
row read as clean.

`trust/` is untracked by git, so its deletion leaves no trace in `git status` either.

**Defect RECONCILE-SILENT-UNENROLLED.** REPAIRED: the un-enrolled branch now counts the
unbacked rows and returns `clean: null`, NOT ASSESSED, never True and never False. Exit
stays 0 to preserve the no-flag-day property; the loud verb is `audit --expect`.

### 4.3 Condition (a) names a relationship that does not exist in code. NOT REPAIRED.

`reconcile` walks `roster.json`. Every standing figure is computed from
`precedents/PR-*.json:published_by`. **There is no join.** Verified by AST: `precedent.py`
imports argparse, json, os, re, sys, pathlib and harness_common, and neither `roster` nor
`warrant`. Records are not "issued under warrants" in any sense the code supports. A
panelist dropped 30 fabricated records into a sandbox archive and `reconcile` returned
`orphans: [], exit 0`. A regression test now fails the day someone wires the join silently.

### 4.4 The trigger predicate has no domain. NOT REPAIRED.

Live `roster.json`: `{"colegiados": {}, "plazas": {}, "names": {}}`. Zero of 59 precedent
records carry a `colegiado` field. "A different colegiado" is undefined for every record in
the registry, and the only available reinterpretation is "a different `published_by`
string" — an environment variable.

### 4.5 The farm costs ten JSON files, and it certifies itself through the guard shipped today.

A panelist measured it. One fabricated record flipped the top-1 holder from
`has_verified_work: False` to `True`. Ten files with three invented author strings, arranged
in a ring, drove registry-wide `share_without_verified_work` from **0.492 to 0.000** —
every identity, real and fabricated, now qualifying.

The part that indicts today's work: thirty such records moved A.8.1 `share_typed` from
0.286 to 0.583 and flipped `currency.py`'s DIRECTION from `NOT REPORTABLE` to **`converging:
typed citations are gaining on bare name-drops`**, because `min_window_edges` rose from 6 to
32 and cleared the `MIN_WINDOW_EDGES = 20` guard added earlier the same day. **The anti-noise
guard certifies the fabricated trend as reportable.**

And the structural consequence: the single action that manufactures eligibility is the same
action that manufactures the health reading licensing eligibility to exist. **Condition (f)
is not a check on the farm. Condition (f) is downstream of it.**

### 4.6 Two further open items the panel surfaced

- `.harness/logs/events.jsonl` is **untracked by git** and feeds
  `verification_verdicts_upheld`. `event_stats.py` measures 3.89x overall replay and 47x on
  some types. A raising attack is deleting lines from an untracked file.
- `epic` is free text, self-asserted at task creation, with no recorded boundary definition.
  Condition (d)'s sunset is a clock the beneficiary sets.

---

## 5. The annex: the three-function money test would bar Phase B permanently

**Three of four panelists reached this independently, and it is the most consequential
finding in the session.**

The candidate says failing any one of the three functions means the currency is failing.
PR-023 clause 5 is conjunctive: even with the gate closed, Phase B does not ship if the
currency is failing.

**Medium of exchange is unsatisfiable by architecture, not by immaturity.** PR-022 clause 1
and PR-010 make standing derived, never stored, computed on read. Nothing is held, so
nothing can move. D-22 IMP-1 states there is "no transfer verb anywhere in the system" and
makes that ABSENCE the anti-forgery guarantee: "a mechanism can have a bug and an absent
feature cannot." Verified: `reputation.py`'s PUBLIC_API has no transfer, assign, delegate or
grant; the only way to move a figure is to rewrite `published_by`, which is forgery.

Therefore: **ratifying this candidate makes the currency permanently failing, which makes
Phase B permanently unshippable, by definition rather than by evidence.** A test that
returns the same answer in every reachable world is not a test. And the only way to pass it
would be to build a transfer verb — the exact thing whose absence protects the design.

That would be a far larger constitutional act than the amendment it was meant to serve: an
indefinite bar on an entire programme, arriving as the definition of a measurement term, in
an annex, with no record. **It is the precise opposite of the operator's stated intent.**

**Unit of account fails by law and by CI.** Nothing is denominated in standing because
clause 4 forbids it — and `test_reputation.py:726` asserts no exported callable takes a
parameter named threshold, gate, weight, burden or permission. The absence is upheld by a
passing test suite, so (f)'s unit-of-account arm is falsified by CI rather than by
measurement.

**On the circularity the coordinator surfaced before the panel: confirmed, and both exits
are bad.** The economics panelist supplied the one repair with real pedigree — *monnaie de
compte*, the medieval unit of account. The livre tournois and Hamburg's mark banco
denominated prices and debts for centuries while no coin of that denomination existed;
Einaudi's imaginary money. A posted price IS a denomination. So publishing a price schedule
satisfies unit-of-account before any consequence attaches, and the circle dissolves.

But the cost is exact: **(f) then becomes satisfiable by writing one sentence.** Strict
reading, permanent deadlock. Loose reading, satisfied by fiat. **Under neither does (f)
constrain anything**, and a condition that does no work in a six-part conjunction is not a
safeguard, it is a line that makes the list look longer.

**The reframe that is worth more than the test.** The economics panelist argued that
reputation is not money but an **endorsement** — the aval on a bill of exchange. An endorser
is *contingently liable*: if the drawer defaults, the endorser pays, and that liability is
what makes the endorsement informative. A typed `follows` in this registry carries no
contingent liability at all: PR-024 clause 6, "Phase A flags, it never fines"; PR-026 clause
3 forbids automatic demotion outright.

So a citation is a costless, liability-free endorsement, and an endorsement with no downside
carries no information however many are issued. **The bottleneck is not PR-022 clause 4. It
is PR-026 clause 3, which no panel has been asked about, and which no amendment to PR-022
can reach.**

**What the panel would accept instead of the three functions** — three supply-side measures,
none circular, none requiring alienability, all computable today at zero consequence, none
satisfiable by bulk publication or by a one-sentence denomination:

1. **BREADTH** — distinct ordered author-pairs carrying a typed citation, and the share
   issued from outside the top-3 by authorship. Today: **4 realized pairs of 42 possible
   (9.5%)**, and **0%** from outside the founding three.
2. **LIVENESS with a denominator** — typed citations issued per record published over a
   trailing window, reusing the existing MIN_WINDOW_EDGES discipline so a thin window
   reports NOT REPORTABLE. Today over the trailing 25 records: **0/25**.
3. **RECIPROCITY CEILING** — share of cross-author typed edges lying on a mutual pair.
   Today: 1 of 4 realized pairs is mutual. Reported as a measure, never a verdict.

## 6. The distribution finding, recorded with its own disclaimer attached

The economics panelist computed set equality: all 12 typed citations in the registry were
issued by exactly three identities, and all 7 credential-conferring receipts are held by
exactly those same three. Applying the proposed consequence to today's registry, three of
seven identities qualify, holding 30 of 59 records.

The largest publisher, `worker-cod-p1` with 18 records and 30.5% of the registry, does NOT
qualify. So the discount does not track size; it tracks membership in the founding session.
PR-035 through PR-059 — 25 consecutive records by the three newest identities, 42% of the
registry — carry zero typed relations, and at the current rate none of them can ever earn
the credential.

The panelist recorded, and the coordinator repeats because it is the honest frame: **no
allegation of intent is made or implied.** A founding cohort citing each other while
building a layer is the ordinary and innocent explanation. PR-025 clause 3 exists precisely
so that good faith is not the load-bearing element. The structure is the finding.

The same panelist stated the corollary against its own position: the live registry contains
one mutual pair, and **no instrument in this harness can distinguish a genuine reciprocal
citation from a manufactured one.** Neither could the panelist. Neither can the coordinator.
That is the case for measure 3 above.

## 7. The strongest argument against the unanimous verdict, preserved

The refusal panelist was required to refute its own case and produced arguments the
coordinator will not bury:

1. **The revisit trigger has fired and the verdict does not refuse the reconsideration.**
   PR-022 instructs a revisit when any consumer proposes to attach a consequence. One has.
   REFUSE rejects *this amendment*, not the reconsideration the record ordered itself.
2. **PR-022 is a reconsideration candidate by the layer's own machinery.** `precedent.py show
   PR-022` prints `RECONSIDERATION CANDIDATE (0 citations after 37 subsequent publications;
   threshold 10)` — nearly four times the threshold. A refusal that treats it as settled law
   treats as settled a record the machinery has already flagged. This is the same argument
   that dismantled the appellant's G5, aimed the other way.
3. **PR-021 clause 2, tier 1, verbatim:** making the cheap path expensive "is the entire
   point of a currency." Twenty-five records with zero typed citations is what "nobody pays
   the cost of consulting the registry" looks like from outside. Refusal preserves a layer
   its own constitution calls pointless.
4. **The no-victims evidence is weak and the panelist said so unprompted.** `citation_gap`
   has 11 firings, ten of them test fixtures. Nothing in the harness records a citation an
   agent declined to make. Absence of victim records is substantially absence of
   measurement.
5. **The confound.** PR-035 through PR-059 are a bulk codification batch of the operating
   manual, published in sittings of under a minute, codifying substrate rules with no
   jurisprudential ancestor to cite. Whether this layer would generate typed citations under
   conditions where citing was the natural act **has never been observed.** That is not
   evidence the economy is healthy; it is evidence there is no baseline. Enacting the first
   exchange rate against no baseline is what PR-025 clause 3 was written to prevent.

Point 5 is the coordinator's own D3 uncertainty returning with better evidence, and it
resolves nothing: the operator's question — is the post-PR-034 drought disease or form —
remains unanswered, and the panel establishes that no instrument in the harness can answer
it today.

## 8. Disposition

The draft does not proceed. It is not repairable by redrafting the six conditions: five of
the findings are collisions with active tier-1 records that no redraft touches. Any future
attempt is a five-record displacement and must arrive as one, with PR-019's verbatim
embedding, before a panel that has the whole package in front of it.

The three-function candidate is NOT ratified as the A.8 failing point. Recommended
disposition: preserve it as a **design objective in dicta**, explicitly not as the operative
failing point, so a later session cannot mistake an unratified metaphor for a ratified test.

`currency.py` continues to print NO THRESHOLD RATIFIED. On this record that refusal is now
the best-supported position in the session.

**Carried forward as the real question, which nobody has been asked:** can a typed citation
be made to cost the citer something, and is PR-026 clause 3 the record that has to move for
that to be possible?
