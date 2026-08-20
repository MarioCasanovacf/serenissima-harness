# T-412 design: the case register that `disposition-ratio` needs a denominator from

**Date:** 2026-08-19 · **Role:** thinker · **No source edits in this document.**

## The gap

`precedent.py disposition-ratio` (T-402) correctly reports **NO DENOMINATOR RATIFIED**. It has
the numerator split — dispositions by citation versus by legislation — and no register of
**cases presented**. A case raised and never disposed of (abandoned, routed around, answered in
prose without either verb) is invisible.

T-402's own note names the wrong fix: building the register by inferring cases from
dispositions makes the denominator a function of the numerator, and the ratio reads 1.0
forever. So the design has to show, mechanically, how registration **precedes** disposal.

## 1. What counts as a case arising

**Not every task.** Most work in this harness is implementation, and counting it would make
the denominator a measure of activity rather than of adjudication.

**A case arises when an agent needs the precedent layer to decide what to do.** Operationally,
one of three things is about to happen:

| shape | example |
|---|---|
| the agent will **apply** an existing record to facts it was not written against | "does PR-023 clause 4 cover a delegated name?" |
| the agent will **distinguish** — the nearest record does not reach these facts | T-402's own worked example |
| the agent will **legislate** — no record reaches, and one must be published | any `publish`, whatever its `operation` type |

What is deliberately excluded: reading a record to learn how the system works; citing a record
in a commit message or a handoff note as background; any task whose question is "how do I build
this" rather than "what does the layer say".

The line is **a decision that would change if the layer said something else.** That test is
prose and unavoidably so — but it is applied once, at registration, by the agent that is about
to act, not retroactively by a counter inspecting artifacts.

## 2. How registration precedes disposal, mechanically

> **Revised 2026-08-19 after a verifier rejection.** The first version of this section gated
> `--case` on `publish` "when the operation is a disposal". There is no such operation.
> `precedent.py`'s real vocabulary is `OPERATION_TYPES = ("determination", "reinterpretation",
> "valuation")`, none of which is named "disposal", so a worker would have had to invent the
> trigger — the one thing the parent task forbids. The claim of universal mechanical closure
> was true for `distinguish` and false for `publish`. What follows is the corrected mechanism.

The mechanism is a **precondition, not an inference**:

```
precedent.py case open --question "<what is being asked>" --task T-NNN   →  C-NNN
precedent.py distinguish --case C-NNN ...     (already required=True; tighten to a case id)
precedent.py publish     --case C-NNN ...     (required on EVERY publish, no exceptions)
```

### `--case` is required on every publish, and no operation type gates it

Not on determinations only, not on some mapping from the three operation types onto a case
taxonomy. **Every publish.** Three reasons, in order of weight:

1. **No trigger has to be invented.** Any gate keyed to operation type would need a mapping
   from `determination` / `reinterpretation` / `valuation` onto "is this a disposal", and that
   mapping exists in no record. Inventing one here would be legislating inside a design note.
2. **Every published record is legislation, and legislation happens because a question arose.**
   A publish with no case behind it means a permanent, immutable record was minted with no
   recorded question. That is not a case the design should quietly permit — it is itself a
   finding, and making it impossible is cheaper than making it countable.
3. **It keeps `disposition_counts` honest without renegotiating its numerator.**
   `by_legislation` today counts every active record unconditionally. If only *some* publishes
   carried a case, the numerator and the denominator would measure different populations, and
   a publish that substantively disposed of a real case while omitting `--case` would be
   invisible to the ratio — the exact failure T-412 exists to close, reappearing on the
   legislative side. Requiring it everywhere makes the two populations identical by
   construction.

With that, every disposal by either verb has a registration strictly older than it, and the
register cannot be a function of the dispositions: it is their **precondition**. That is the
only structural requirement in the design, and everything else follows from it.

An open case that is never disposed of stays open. That is not a defect in the register — **it
is the measurement**. Cases opened and never disposed are precisely the population
`disposition-ratio` is missing today, and they become countable the moment the register exists.

### The transition, which the same objection exposes

58 active records exist today and none of them has a case. They **must not be retro-registered**:
inferring a case from a record that already exists is precisely the inference this design
forbids, and doing it once would make the denominator a function of the numerator for the whole
back catalogue.

So `disposition-ratio` reports **three buckets, never two**:

| bucket | what it counts |
|---|---|
| `by_legislation_pre_register` | active records published before the register's first case |
| `by_legislation_registered` | publishes carrying a case id |
| `by_citation` | `distinguish` acts, which already carry a case |

The cutoff is mechanical and needs no judgment: **the timestamp of C-001**. A record published
before it is pre-register by construction. A record published after it *without* a case cannot
exist, because `publish` refuses. The pre-register bucket is frozen the moment the register
opens — it can only shrink, as those records are superseded — and it is never folded into
either arm, because folding it would report an unmeasured population as a measured one.

`citation_share_of_dispositions` is therefore computed over the registered buckets only, and
the pre-register count is printed beside it every time, so nobody quotes a share whose
denominator silently excluded 58 records.

`distinguish` today takes `--case` as free text. Tightening it to accept a case id is the
smallest possible change and is where the implementation should start.

## 3. Who registers, and what it costs to be wrong

**A CLI verb, not a required field on task creation.** A field on task creation would force the
question at the wrong moment — most tasks are not cases, and a mandatory field on a
non-question is answered carelessly and then counted. `case open` is called by the agent that
is about to reach for the layer, at the moment it reaches.

Storage: `.harness/cases/C-NNN.json`, numbered immutable records like every other store here,
holding the question, the issuing task, the opening agent, the timestamp, and — once disposed
— the disposal reference. Computed on read, no side index (PR-010).

### False negative: a real case that goes unregistered

The denominator is **too small**, so the ratio of cases-disposed reads **high**. The layer looks
like it disposes of everything that arises. This is the dangerous direction: it flatters the
precedent layer with a number produced by the cases it never saw, and it flatters it most
exactly when the layer is being routed around most.

### False positive: routine work miscounted as a case

The denominator is **too big**, so the ratio reads **low**. The layer looks worse than it is.
Cheap, and it provokes investigation rather than complacency.

### Therefore

**The design is biased toward over-registration.** Opening a case is one command with two
required arguments, costs nothing, needs no key, no intent, no confirmation, and blocks
nothing. Closing one is gated. That asymmetry is deliberate and should be stated in the verb's
own help text, so an agent unsure whether something is a case is told: open it.

## What the register does NOT do

- **It emits no verdict and no threshold.** `currency.py` and `westphalia_kpi.py` set this
  precedent twice: emit the figure, refuse the verdict. No record ratifies a healthy
  disposition ratio, and a tool that invents one decides the question it was built to measure.
- **It attaches no consequence** to the agent that opened or failed to open a case. PR-022
  clause 4 governs, and a register that fed a standing figure would be the first consumer to
  break it.
- **It does not close the irreducible hole.** A case answered in prose, by an agent that
  called neither verb, is still invisible. No mechanism inside this harness detects a decision
  that left no artifact. **The neighbouring hole is now closed rather than merely named:** a
  case disposed of by a real, permanent registry artifact that evaded case-tracking. That was
  possible while `--case` was gated on an operation type, and requiring it on every publish is
  what removes it. The register converts that from "unmeasurable" to "unmeasured, and the
  ratio says so" — which is the same distinction `westphalia_kpi.py` draws between a count of
  zero and a cost of zero.

## What `disposition-ratio` may say once this exists

Three counts, each raw and distinct (TELEMETRY-PROVENANCE-A):

```
cases opened                 N raw / N distinct
disposed by citation         A       (distinguish acts)
disposed by legislation      B       (publishes carrying a case id)
still open                   N - A - B
published before the register P      (frozen; NOT part of any share above)
```

And a sentence that survives the register: **the denominator is cases REGISTERED, not cases
ARISING.** Those are different quantities, the gap between them is unmeasured, and the ratio
must never be reported as though registration were complete. Today the tool says NO DENOMINATOR
RATIFIED; after the register it says what the denominator is and what it still is not.

## Handoff to a worker task

Implementable without further invention:

1. `case open --question --task` → `C-NNN` in `.harness/cases/`; refuses an empty question.
2. `case list` / `case show C-NNN`, read-only, counts raw and distinct.
3. `--case C-NNN` required by `distinguish` and by **every** `publish`, with no operation-type
   gate; both refuse an id with no registered case, and refuse a case already disposed (a
   second disposal of one case is a finding, not a silent overwrite — the T-376 shape).
4. `disposition_counts` splits `by_legislation` into `pre_register` and `registered` at the
   timestamp of C-001, computes the share over the registered buckets only, and prints the
   pre-register count beside it on every run. `disposition-ratio` keeps the
   registered-versus-arising disclaimer verbatim.
5. Tests: registration strictly precedes disposal (assert on the stored timestamps and on the
   refusal), **for both verbs, with `publish` given its own test rather than being assumed to
   behave like `distinguish`** — that assumption is what the first version of this design got
   wrong; a case opened and never disposed is counted as open; the pre-register bucket is
   never folded into a share; the ratio never reads 1.0 merely because dispositions equal
   registrations; the disclaimer string is pinned; and a negative control in which a disposal
   is attempted with an unregistered case id and is refused — without it, the precondition
   could be absent and every other test would still pass.
