# T-303 Intake Audit — Generic protected-paths destructive-command guardrail

- **Analyst**: analyst-a (evolution-analyst role)
- **Date**: 2026-07-06 (UTC)
- **Task**: T-303 (thinker/intake). Evaluate promoting Portfolio's PreToolUse[Bash]
  destructive-command hook into the public harness as a *configurable* guardrail
  (`protected_paths` glob in `state.json` + a hook script in `.harness/bin/` wired via
  `.claude/settings.json`).
- **Source idea**: `/Users/mariocasanova10pa/Documents/Portfolio/.claude/settings.json`
  (read read-only, never edited) ships a `PreToolUse[Bash]` hook whose jq+grep pipeline
  denies `(rm|mv|shred|truncate)` and `>`/`>>` redirects that target `notebooks/data/real`
  (verbatim regex: `'(^|[;&|[:space:]])(rm|mv|shred|truncate)[[:space:]][^;|&]*data/real|>>?[[:space:]]*[^[:space:]]*data/real'`).
- **Intake bar**: same falsifiable bar applied to P-027/P-028 in `audit_gen5.md` and
  `state.json evolution.pending_proposals`. Operator reject criteria: too much work, too
  many tokens, too complex, too hard to integrate; a well-argued reject outranks an
  enthusiastic adopt (`audit_gen5.md:9-11`). Active cost crackdown: `state.json.cost_policy`
  (95% usage from subagent-heavy sessions).
- **Verdict**: **SIMPLIFY-AND-ADOPT** — adopt the *generic, default-empty, opt-in mechanism*;
  reject the Portfolio literal and any default-on / broad-glob form. Rationale and the
  honest counter-case (a strict occurrence-only reading yields REJECT) are in §C.

---

## A. Local evidence — has an agent in THIS repo ever destroyed / nearly destroyed a file a protected-paths list would have saved?

**Answer: No protected-path near-miss is recorded, and `data/real` does not exist in this
repo. The one real on-disk deletion was intentional and unprotected. The one genuinely
dangerous command this session (an `rm -rf`) was caught by an *external* operator guard and
is therefore invisible to our own logs — which is itself the load-bearing finding.**

### A.1 The literal target path does not exist here
`find` for a `real/` dir and `grep` for the string `data/real` across the repo return only
the T-303 task text itself:
```
grep -rl "data/real" ... -> .harness/blackboard.json, .harness/tasks/T-303.json   (both = this task's own description)
find ... -name real -> (none)
```
The Portfolio regex is hardcoded to a Portfolio-specific irreplaceable-CSV path
(`notebooks/data/real`, "status pages age out old incidents" — Portfolio settings.json:39).
Porting the literal here protects nothing. Any adoption must be generic.

### A.2 Every rm/mv/shred/truncate in the corpus, categorized (12 transcript hits)
Enumerated from `transcript.jsonl` (2668 lines) via a `(^|[;&|\s])(rm|mv|shred|truncate)\s`
scan. Breakdown:
- **Ephemeral scratch / lock cleanup (harmless, out-of-repo or `.tmp`)**: e.g.
  `transcript.jsonl:673` `rm -f "/private/tmp/.../scratchpad/e2e_sample*.md"`;
  `:421` `lock.py release ...; rm -f .harness/scratch/T-013_realworld.txt`;
  `:1585` `lock.py release scratch_probe_t053.tmp; rm -f scratch_probe_t053.tmp`.
- **Operator-gate-approved deletion**: `transcript.jsonl:1427` (2026-07-05T04:04:24Z)
  `git rm -q PLACEHOLDER && rm .harness/active_role` — commit message quotes explicit
  operator consent ("Both deletions explicitly approved by the operator 2026-07-05 'Sí a lo
  que propones'"). Intentional; a protected-paths list would have been a false-positive
  obstacle here, not a save.
- **`git rm --cached` (untrack only, non-destructive)**: `transcript.jsonl:2546` `git rm -r
  --cached -q docs/` and `:2592` `git rm -r --cached -q gemini-prompts/ fetched_docs/`.
  Verified non-destructive by the command's own output: "=== docs/ still on disk? ===" then
  `ls docs/` lists the files. Files stayed on disk.
- **Literal string in a test payload, never executed**: `transcript.jsonl:2250` /
  `T-090.json` note contains `$(rm -rf /tmp/nope)` as a byte-exactness probe ("note with
  `backticks`, $(danger command) ... must survive byte-exact"). It is data, not a command.
- **The only real on-disk source deletion**: `transcript.jsonl` 2026-07-05T23:25:51Z
  `cd ".../hf-space"; rm -f app.py requirements.txt; ls -la`. Response shows `README.md` and
  `data/` survived. This deleted two generated deploy files; no recovery panic or re-creation
  scramble follows in the log, so it reads as intentional. It targeted named files, not a
  protected glob, and `hf-space/data/` (the plausible "protected" dir) was left untouched.

**Conclusion for A.2**: 0 of 12 are an accidental destruction of an irreplaceable/protected
file. The class of harm the guardrail exists to prevent has **not occurred** in-repo.

### A.3 The dcg block is INVISIBLE to our logs — the decisive finding
The task states this session had an `rm -rf` blocked by an external hook ("dcg"). Searching
our own logs for it:
```
grep -c 'rm -rf' events.jsonl        -> 0
grep 'rm -rf' transcript.jsonl       -> only the T-090 test-payload string + the grep commands themselves
```
The blocked `rm -rf` left **no trace**. This is mechanically expected: a `PreToolUse` deny
means the command never runs, so `PostToolUse` (the `log_event.py` hook that fills
`transcript.jsonl`) never fires. Two implications, pulling in opposite directions:
1. **Weighs against adoption**: the operator *already* runs an outer command guard at the
   machine/CLI level, and it already caught this session's one dangerous command. An inner
   harness copy is belt-and-suspenders over a control that demonstrably works.
2. **Weighs for adoption (for downstream adopters)**: this repo's OWN
   `.claude/settings.json` `PreToolUse[Bash]` slot is **empty** — it has `check_lock.py` on
   `Edit|Write|MultiEdit|NotebookEdit` and `log_event.py` on `PostToolUse`, but **no Bash
   destructive guard at all** (settings.json:23-33 has no Bash matcher). The dcg guard is
   NOT part of the harness; it is the operator's personal machine config. `migracion_proyecto.py`
   propagates the harness (incl. settings.json) into fresh repos; a downstream adopter gets
   **zero** destructive-command protection and may not run dcg.

### A.4 No destructive-op observability exists in the event taxonomy
Event-kind histogram over `events.jsonl` (1321 lines) has 24 kinds (task_updated 353,
lock_acquired 209, lock_released 202, task_claimed 162, ... producer_check_refused 33,
lock_busy 5, goal_abandoned 4, ...). There is **no** `destructive_blocked` / `file_deleted` /
`protected_path_hit` event. So even the Portfolio-style deny, if adopted, would today produce
a `permissionDecision:deny` that our own logs never record — a blind spot the mechanism
should close (see §B/§C). Note also: `goal_abandoned` non-synthetic count = **0** (all 4 are
DEMO/VER1 smoke tests), consistent with §A: no real disaster has ever happened here.

---

## B. Cost table (per dimension, low/medium/high)

Scope priced: a generic, default-empty, opt-in mechanism = one new
`.harness/bin/guard_paths.py` (~30-40 lines: read `state.json.protected_paths`, read the
candidate Bash command on stdin, emit the `permissionDecision:deny` JSON on match, else
pass, and log a `protected_path_blocked` event so the block is observable) + one
`PreToolUse[Bash]` block in `.claude/settings.json` + a `protected_paths: []` key in
`state.json` + a short `CLAUDE.md §3` note. NOT priced: the Portfolio jq/grep one-liner
literal (rejected).

| Dimension | Rating | One-line justification |
|---|---|---|
| Lines / files to touch | **low-medium** | ~30-40 line hook script + 1 settings.json block + 1 state.json key + a §3 doc note; 4 files, no changes to existing CLI tools. |
| Integration with existing hooks | **medium** | The `PreToolUse[Bash]` slot is currently empty here (settings.json:23-33), so no collision — but it must not shadow/duplicate the outer dcg guard, must be a Python script (not a fragile inline jq/grep, which the Portfolio literal is) to stay engine-portable, and `migracion_proyecto.py` must seed a *safe default-empty* value so a fresh repo never inherits a stale glob. |
| Recurring token cost | **low** | Fires locally as a hook on each Bash call; adds ~0 LLM tokens (the standing `cost_policy` concern is token usage, not hook latency). One extra local process per Bash call is latency-only. |
| Gen-4 risk (false positives / DAG wedge) | **low if default-empty & opt-in / high if default-on or broad-glob** | The harness itself legitimately runs `rm -f /private/tmp/.../scratchpad/*` and `lock.py release ...; rm ...` (transcript.jsonl:673, :421); a broad or default-on glob would deny legitimate scratch cleanup and stall claimants. Default `protected_paths: []` = strict no-op until an operator opts in = zero regression risk. |

---

## C. Verdict — SIMPLIFY-AND-ADOPT

**Evidence → diagnosis → mutation → measurable gain.**

**Evidence.** No protected-path near-miss in-repo (§A.2: 0/12 destructive commands were
accidental protected-file loss; the one real deletion, hf-space `rm -f app.py`, was
intentional and unprotected). The literal target `data/real` does not exist here (§A.1). The
one genuinely dangerous command this session was caught by an *external* dcg guard and is
invisible to our logs (§A.3). This repo's own harness ships with an **empty**
`PreToolUse[Bash]` slot and no destructive guard (§A.3.2), and `migracion_proyecto.py`
propagates that gap to downstream repos that may lack dcg.

**Diagnosis.** This is the one candidate class where zero-occurrence is *not* disqualifying:
a guardrail's value is the rare catastrophic case, not its hit-rate — unlike P-027/P-028,
whose target *metrics* (contaminated-retries, bug recurrences) were already at floor and thus
structurally unfalsifiable-as-improvement. But the Portfolio *literal* fails intake (wrong
path, fragile inline jq/grep, non-portable), and a *default-on / broad-glob* form fails on
false-positive risk against the harness's own legitimate scratch `rm`s (§B, gen-4 risk row)
and adds work the operator's own dcg already covers *for this machine*. The defensible
residue is the **mechanism**, decoupled from the literal, shipped **default-empty** so it
costs nothing until an adopter opts in, and made **observable** (unlike both dcg and the
Portfolio hook) so a future audit can actually measure it.

**Mutation (falsifiable, register-only — I propose, I do not apply).**
- Target files: new `.harness/bin/guard_paths.py`; `.claude/settings.json`
  `PreToolUse[Bash]` block; `state.json` new key `protected_paths: []`; `CLAUDE.md §3A`
  note under Core Local Tools.
- Mechanism: hook reads the candidate Bash command on stdin, expands `protected_paths`
  (globs) from `state.json`; if a destructive verb (`rm|mv|shred|truncate`) or a `>`/`>>`
  redirect targets a match, emit `{"hookSpecificOutput":{...,"permissionDecision":"deny",...}}`
  and log a new `protected_path_blocked` event; otherwise pass through silently. Ship
  `protected_paths: []` (no-op) as the default; `migracion_proyecto.py` seeds the empty list.
- Explicitly rejected sub-parts: the hardcoded `data/real` regex; any non-empty default;
  the inline jq/grep implementation (replace with a portable Python script).

**Expected measurable gain (falsifiable).**
1. With `protected_paths: []`, a full harness regression (the SCRATCH probe family +
   legitimate scratch `rm -f /private/tmp/...`) produces **0** `protected_path_blocked`
   events and **0** newly-denied legitimate commands — i.e. provably a no-op until opt-in.
2. With a test glob (e.g. `["hf-space/data/**"]`), a `rm -rf hf-space/data` is denied and a
   `protected_path_blocked` event is written, while `rm -f /private/tmp/.../scratchpad/x` is
   still allowed — i.e. selective, observable, no false positive on scratch.
3. Net new observability: destructive blocks become greppable (`grep -c protected_path_blocked
   events.jsonl > 0` under test), closing the §A.4 blind spot that both dcg and the Portfolio
   hook leave open (today: 0, and structurally unrecordable).

**Falsifiable KILL / downgrade-to-REJECT triggers** (so this decision is re-litigated on
evidence, not theory):
- Downgrade to REJECT if implementation cannot keep the default a strict no-op — i.e. if the
  regression in gain-1 shows any legitimate scratch `rm` denied with `protected_paths: []`.
- Downgrade to REJECT if the operator confirms the outer dcg guard is (a) always present and
  (b) inherited by every downstream `migracion_proyecto.py` target — which would make the
  inner copy pure redundancy.
- Do NOT ship any non-empty default and do NOT port the `data/real` literal; if a future
  proposal reintroduces either, reject on §A.1 / §B gen-4-risk grounds.

**Honest counter-verdict (recorded for the coordinator/verifier).** Under a strict
occurrence-only reading of the P-027/P-028 bar — "0 local occurrences + an outer guard
already catching the one real case + active cost crackdown" — the equally-defensible verdict
is **REJECT with revisit trigger**: reopen if a downstream `migracion_proyecto.py` adopter
reports a destroyed protected file, or if `>=1` accidental (non-approved) destruction of a
repo-tracked file appears in a future `transcript.jsonl`. I land on SIMPLIFY-AND-ADOPT rather
than REJECT only because (i) the default-empty form is near-zero-cost and near-zero-risk, and
(ii) the harness is a *distributed product* whose own Bash guard slot is empty, so the value
accrues to adopters who lack dcg — but the coordinator should treat REJECT-with-revisit as a
fully acceptable, cheaper alternative if the token/complexity bar is being enforced strictly.

---

## Registration note
This audit REGISTERS a proposal only (proposed id **P-029**). It does not touch
`claude.md`/`gemini.md`, source, or shared JSON by hand. Entering P-029 into
`state.json evolution.pending_proposals` and any later application are separate,
coordinator/human-gated steps (CLAUDE.md §5A.3-4, `state.json human_gates`).
