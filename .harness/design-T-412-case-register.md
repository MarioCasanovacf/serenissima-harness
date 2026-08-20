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
| the agent will **legislate** — no record reaches, and one must be published | any `publish` of an operation that is a disposal |

What is deliberately excluded: reading a record to learn how the system works; citing a record
in a commit message or a handoff note as background; any task whose question is "how do I build
this" rather than "what does the layer say".

The line is **a decision that would change if the layer said something else.** That test is
prose and unavoidably so — but it is applied once, at registration, by the agent that is about
to act, not retroactively by a counter inspecting artifacts.

## 2. How registration precedes disposal, mechanically

The mechanism is a **precondition, not an inference**:

```
precedent.py case open --question "<what is being asked>" --task T-NNN   →  C-NNN
precedent.py distinguish --case C-NNN ...                                (refuses without it)
precedent.py publish --case C-NNN ... --operation <disposal>             (refuses without it)
```

Both disposal verbs refuse a case id that does not already exist in the register. Therefore
every disposal has a registration that is strictly older than it, and the register cannot be a
function of the dispositions: it is their **precondition**.

This is the only structural requirement in the design, and everything else follows from it.

An open case that is never disposed of stays open. That is not a defect in the register — **it
is the measurement**. Cases opened and never disposed are precisely the population
`disposition-ratio` is missing today, and they become countable the moment the register exists.

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
  that left no artifact. The register converts that from "unmeasurable" to "unmeasured, and the
  ratio says so" — which is the same distinction `westphalia_kpi.py` draws between a count of
  zero and a cost of zero.

## What `disposition-ratio` may say once this exists

Three counts, each raw and distinct (TELEMETRY-PROVENANCE-A):

```
cases opened            N raw / N distinct
disposed by citation    A       (distinguish)
disposed by legislation B       (publish, disposal operations)
still open              N - A - B
```

And a sentence that survives the register: **the denominator is cases REGISTERED, not cases
ARISING.** Those are different quantities, the gap between them is unmeasured, and the ratio
must never be reported as though registration were complete. Today the tool says NO DENOMINATOR
RATIFIED; after the register it says what the denominator is and what it still is not.

## Handoff to a worker task

Implementable without further invention:

1. `case open --question --task` → `C-NNN` in `.harness/cases/`; refuses an empty question.
2. `case list` / `case show C-NNN`, read-only, counts raw and distinct.
3. `--case C-NNN` required by `distinguish` and by `publish` when the operation is a disposal;
   both refuse an id with no registered case, and refuse a case already disposed (a second
   disposal of one case is a finding, not a silent overwrite — the T-376 shape).
4. `disposition-ratio` reads the register for its denominator and keeps the
   registered-versus-arising disclaimer verbatim.
5. Tests: registration strictly precedes disposal (assert on the stored timestamps and on the
   refusal); a case opened and never disposed is counted as open; the ratio never reads 1.0
   merely because dispositions equal registrations; the disclaimer string is pinned; and a
   negative control in which a disposal is attempted with an unregistered case id and is
   refused — without it, the precondition could be absent and every other test would still
   pass.
