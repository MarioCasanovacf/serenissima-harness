# Bench-Sync Decision — three diverging copies of the bench

**Task**: T-301 · **Author**: thinker-a (thinker role — recommendation only, zero source changes) · **Date**: 2026-07-06

**Question**: The 5-agent bench + `harness-status` skill + the 4 hook wirings are COPIED into
two sibling deployments (`~/Documents/Portfolio`, `~/Documents/Curriculums`) with no sync
mechanism (fleet inventory `docs/flota-de-agentes.md`, "Duplicaciones y pendientes" #1). As the
bench mutates (gen 5+), how do we keep the copies coherent — (a) re-transplant via
`migrate_project.py` per generation bump, (b) deliberate divergence, or (c) a sync manifest?

---

## 1. Measured divergence (evidence, not assumption)

Shared units compared across the three projects = **7**: the 5 bench agents
(`orchestration-planner`, `substrate-worker`, `harness-verifier`, `evolution-analyst`,
`research-librarian`), the `harness-status` SKILL, and the hook wirings block of
`.claude/settings.json`. All sibling reads were **read-only**.

| Shared unit | Harness ↔ Portfolio | Harness ↔ Curriculums | Portfolio ↔ Curriculums |
|---|---|---|---|
| `orchestration-planner.md` | 1 line differs | 1 line differs | **identical** |
| `substrate-worker.md` | identical | identical | identical |
| `harness-verifier.md` | identical | identical | identical |
| `evolution-analyst.md` | identical | identical | identical |
| `research-librarian.md` | 2 lines differ | 2 lines differ | **identical** |
| `harness-status/SKILL.md` | 1 line differs | 1 line differs | **identical** |
| hook wirings (`settings.json`) | 4 core identical; **Portfolio adds 2** | **fully identical** | Portfolio has 2 extra |

**Total real divergence in the bench text: 3 files, ~4 lines — all cosmetic/wording.** The
two siblings are in lockstep with each other on every bench/skill file; they were transplanted
from one snapshot and neither has drifted independently.

### What the ~4 lines actually are (this is the crux)

The drift is **bidirectional and mostly intentional**, not "siblings lag the parent":

1. **Siblings hold text the parent LACKS** (legitimate localization):
   - `SKILL.md` description: siblings add a Spanish trigger phrase `qué está pasando`
     alongside the English triggers. A skill-discovery improvement for a Spanish operator.
   - `orchestration-planner.md` L49: siblings route the Gemini bridge to a
     project-local path (`prompts para Gemini/`) vs the parent's `.gemini/commands/claim-next`.
     A per-project path, correct for those repos.
2. **Parent holds text the siblings LACK** (a later gen refinement):
   - `research-librarian.md` L16-17: the parent annotated `fetched_docs/*.md` as
     `(operator-local, untracked)`. A doc-hygiene edit the siblings predate.

So a blind re-transplant of the parent over the children would **destroy** the Spanish trigger
and the project-local Gemini path. This is decisive against option (a) as literally framed.

### The one substantive functional divergence — and it flows the WRONG way

Portfolio's `settings.json` adds **2 hooks the parent does not have** (confirmed the 4 core
wirings — `log_event.py` on SessionStart/PostToolUse/Stop, `check_lock.py` on PreToolUse — are
byte-identical across all three):
- a `NotebookEdit` PostToolUse reminder to re-execute the notebook, and
- a `Bash` PreToolUse **guard that denies `rm/mv/shred/truncate`/redirects against
  `notebooks/data/real/`** (irreplaceable capture CSVs).

The `data/real` guard is a genuine, exportable guardrail — the fleet doc itself flags it as a
**gen-5/6 intake candidate the public harness lacks** ("Duplicaciones y pendientes" #2). The
valuable divergence is in the *child*, needing to flow *back up* to the parent — the exact
motion neither (a) nor (b) provides.

---

## 2. `migrate_project.py` is an INSTALL tool, not a SYNC tool (decisive for option a)

Read of `.harness/bin/migrate_project.py` (lines 162-240, `_copy_guarded_file` /
`_copy_guarded_dir`) shows the `.claude/settings.json`, `.claude/agents/`, and
`.claude/skills/harness-status` copies are **per-file guarded**:

- **Without `--force`**: any pre-existing target file → `[SKIP-EXISTS]`, "left intact
  (target-owned; diff manually … if you want to reconcile)". Re-running over an
  already-migrated Portfolio/Curriculums propagates **nothing** — it is a no-op on the bench.
- **With `--force`**: it `[BACKUP]`s the whole file (rename to `.bak-<n>`) then overwrites
  it wholesale. There is **no field-level merge** — the entire `settings.json` is replaced.

**Field evidence this already bit us**: Portfolio holds `.claude/settings.json.bak-1`
(dated 2026-07-04) — a prior `--force` migration ran there. That backup already contained
Portfolio's custom-hook lines, and the current `settings.json` (2026-07-05) has them again —
i.e. the migration **clobbered a customized settings file and the operator had to manually
re-establish the custom hooks afterward.** That is the destructive-recovery cycle option (a)
would repeat on every generation bump.

Conclusion: option (a) is either a **no-op** (no `--force`) or **destructive** (`--force`
clobbers sibling localizations and Portfolio's 2 hooks). `migrate_project.py`'s own safety
docstring says to "diff manually if you want to reconcile" — it was designed for the *first*
install, not for ongoing sync.

---

## 3. Options and trade-offs

### (a) Re-transplant via `migrate_project.py` per generation bump — REJECTED
- **Pro**: zero new tooling; the tool exists.
- **Con**: as shown in §2 it is a no-op without `--force` and destructive with it (whole-file
  overwrite, no merge). It would erase the siblings' intentional localizations (Spanish
  trigger, project Gemini path) and Portfolio's 2 custom hooks — and the `settings.json.bak-1`
  scar proves this recovery cycle already happened once. It also has **no reverse channel**
  for Portfolio's `data/real` guardrail to reach the parent.

### (b) Deliberate divergence — no sync mechanism at all
- **Pro**: honest about today's reality — the ~4 lines of drift are cosmetic + intentional;
  zero maintenance cost; nothing to build.
- **Con**: forward-looking failure. As the bench evolves gen 5+, a *substantive* protocol fix
  in (say) `orchestration-planner.md` would silently fail to reach the siblings, and there is
  **no mechanism to distinguish benign localization drift from a missed critical fix** — the
  operator can't see divergence without manually diffing three trees. The good Portfolio
  guardrail also never flows back. Divergence is benign now but compounds invisibly.

### (c) Sync manifest + read-only drift checker — RECOMMENDED
A small declarative manifest (e.g. `.harness/bench_manifest.json` or a section appended to the
operator-local fleet doc) that classifies every shared file region as one of:
- **CORE — keep verbatim** (the bench files meant to be identical: worker, verifier,
  evolution-analyst, plus the shared body of the others and the 4 hook wirings), vs.
- **PROJECT-LOCAL — do NOT touch** (an explicit allowlist: the `SKILL.md` Spanish trigger,
  `planner.md` L49 Gemini path, Portfolio's `NotebookEdit` + `data/real` hooks).

Paired with a **read-only** `bench_sync.py check` (stdlib only, local — fits the harness
tooling contract) that diffs the three copies and reports drift **only in CORE regions**,
exiting nonzero on real drift. Propagation stays **manual and reviewed** through the normal
loop (thinker plans → worker applies → verifier verdicts; producer ≠ approver) — the checker
never auto-applies and never clobbers.
- **Pro**: the only option that (1) separates intentional localization from stale drift, so
  the operator sees *signal* not noise; (2) turns divergence into an **evolution-audit input**
  (§5A loop / `evolution-analyst`) instead of silent state; (3) surfaces the reverse-flow
  candidate (Portfolio's `data/real` guard → parent gen-5/6 intake, already named in the
  fleet doc); (4) is non-destructive by construction — it reports, humans/loop decide.
- **Con**: needs a small new tool + a manifest to maintain. Mitigated by keeping it minimal
  (read-only checker, declarative allowlist) and by the fact that the allowlist is tiny today
  (4 line-regions + 2 hooks).

---

## 4. Recommendation

**Adopt option (c), in its lightest form: a declarative bench manifest + a read-only
`bench_sync.py check` drift reporter — NO auto-apply, NO `--force` re-transplant.**

Rationale grounded in the evidence:
1. Option (a) is disqualified by the tool itself: `migrate_project.py` skips existing files
   (no-op) or whole-file-clobbers with `--force`, and the Portfolio `settings.json.bak-1`
   proves the clobber-and-manually-recover cycle already happened.
2. Option (b) is right about *today* (drift is 4 cosmetic/intentional lines) but wrong for the
   *trajectory* — the bench WILL mutate at gen 5+, and (b) gives the operator no way to tell a
   benign localization from a missed critical fix, and no reverse channel for the one
   genuinely valuable divergence (Portfolio's `data/real` guard).
3. Option (c) folds in (b)'s only real insight — that some divergence is *intentional* — by
   making it an explicit allowlist, so the checker reports *signal* only, and it plugs sync
   into the existing producer≠approver evolution loop instead of a destructive one-shot copy.

**Sequencing note for whoever acts on this**: the manifest's first payload is not to
"re-sync" anything (there is nothing stale worth pushing today) — it is to (i) record the 4
line-regions + 2 hooks as PROJECT-LOCAL so no future `--force` ever clobbers them again, and
(ii) route Portfolio's `data/real` Bash guard up to the parent as a gen-5/6 intake candidate
with its own evidence, per fleet-doc pending #2.

**Scope guardrail**: this is a recommendation only. Building `bench_sync.py`, writing the
manifest, and the reverse-flow intake are separate WORKER/THINKER tasks to be published on the
board after this recommendation is verdicted — not part of T-301.

---

## 5. Replayable evidence (exact commands run)

Agent bench diffs (loop over the 5 bench files; `diff` exit 0 = identical):
```
H=.claude/agents; P=/Users/mariocasanova10pa/Documents/Portfolio/.claude/agents; C=/Users/mariocasanova10pa/Documents/Curriculums/.claude/agents
for a in orchestration-planner substrate-worker harness-verifier evolution-analyst research-librarian; do
  diff "$H/$a.md" "$P/$a.md"; diff "$H/$a.md" "$C/$a.md"; done
```

Skill diff + sibling-vs-sibling cross-check:
```
diff .claude/skills/harness-status/SKILL.md /Users/mariocasanova10pa/Documents/Portfolio/.claude/skills/harness-status/SKILL.md
diff .claude/skills/harness-status/SKILL.md /Users/mariocasanova10pa/Documents/Curriculums/.claude/skills/harness-status/SKILL.md
diff /Users/mariocasanova10pa/Documents/Portfolio/.claude/agents/orchestration-planner.md /Users/mariocasanova10pa/Documents/Curriculums/.claude/agents/orchestration-planner.md
```

Hook-wiring diffs (normalized JSON of the `hooks` block):
```
diff <(python3 -c "import json;print(json.dumps(json.load(open('.claude/settings.json')).get('hooks'),indent=2,sort_keys=True))") \
     <(python3 -c "import json;print(json.dumps(json.load(open('/Users/mariocasanova10pa/Documents/Portfolio/.claude/settings.json')).get('hooks'),indent=2,sort_keys=True))")
# repeat with the Curriculums path
```

`migrate_project.py` guard behavior — read `.harness/bin/migrate_project.py` lines 162-240
(`_copy_guarded_file`: SKIP-EXISTS without `--force`, backup+overwrite with `--force`).

Portfolio clobber scar:
```
ls -la /Users/mariocasanova10pa/Documents/Portfolio/.claude/settings.json.bak-1   # dated 2026-07-04
grep -c "data/real\|NotebookEdit" /Users/mariocasanova10pa/Documents/Portfolio/.claude/settings.json.bak-1  # backup already had custom hooks
```
