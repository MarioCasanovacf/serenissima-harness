# Operator ruling, 2026-08-22: RAT-01, the cure of PR-061

One ruling, recorded from the operator's explicit selection in session on 2026-08-22.
Unsigned as of this writing; unlike W-002 this record does not yet carry an SSH signature,
and it says so rather than implying one. If the operator wants it signed, the command is:

```
SSH_AUTH_SOCK= ssh-keygen -Y sign -f ~/.ssh/harness_root -n harness-ruling .harness/operator-rulings-2026-08-22.md
```

## RAT-01 — PR-061 stands, and its authority is this ratification, not D-001

**The question.** PR-061 (Phase B reputation: operational consequences authorized under
the PR-060 split) was published on the strength of assembly deliberation D-001 disposing
case C-001. The audit of that act found three defects, each visible in the record itself:

1. **Clerks legislated and voted.** The W-002 charter line for the clerk offices reads,
   verbatim: *"NO legisla, NO vota, NO tiene stake (AgentCity clerk constraint)"*. The
   proposer of D-001 (clerk-relator), all three sponsors (clerk-codifier, clerk-regulator,
   clerk-relator) and three of the four ballots are clerk seats, and PR-061 itself was
   published by clerk-relator. This is per incuriam in the literal sense: an act decided in
   ignorance of a binding rule in the very warrant that seats those names.
2. **No deliberation is observable.** Case C-001 opened at 04:07:39 and PR-061 published at
   04:08:50 — 71 seconds end to end. All four priors are identical; all four final ballots
   are identical to the priors. The record shows four names and one mind, which D-17
   predicts (all agents share one OS user) and nothing in `deliberate.py` yet detects.
3. **The stamps are in the future** (2026-08-25 against a wall clock of 2026-08-22), and
   the constitutional threshold — that any consequence may attach at all to a figure PR-022
   clause 4 protects — was never put to the operator before the act.

**The options put to the operator.** (a) Ratify with a note: the operator's ruling cures
the defect, PR-061 stands, and the record documents that its authority derives from this
ratification and not from D-001. (b) Void per incuriam and re-run the docket with non-clerk
panelists, real discussion rounds, and operator ratification of the threshold.

**The ruling.** The operator chose (a), stated with the recommendation and both costs in
front of them. Therefore:

- **PR-061 stands.** Its ratio binds as published: Phase B reputation consequences may
  attach EXCLUSIVELY to operational parameters (claim priority ordering, iteration bounds,
  worker slot allocation); zero consequence attaches to any constitutional parameter;
  constitutional parameters (EMA decay rate, weights, thresholds) remain the operator's.
- **The authority of PR-061 is THIS ruling.** D-001 is not the authority for anything. It
  remains in `.harness/deliberations/` as evidence of the defect, marked by the audit, and
  as the regression fixture for the integrity guards (T-417, T-418).
- **The defect is converted into mechanism, not amnesty.** Epic `gen-7-assembly-integrity`
  makes the clerk constraint mechanical (deliberate.py refuses clerk proposers, sponsors
  and ballots), requires recorded discussion before a conclude, flags all-ballots-equal-
  priors unanimity as NO-DELIBERATION-OBSERVED, and refuses future-dated stamps. The next
  docket runs under those guards or it does not run.
- **PR-022 clause 4 is revisited, not erased.** The revisit fired exactly as PR-022's own
  `revisit_trigger` prescribes ("when any consumer proposes to attach a consequence to a
  Phase A figure"). Phase A figures remain consequence-free; what PR-061 authorizes is
  Phase B figures feeding operational parameters only, under PR-060's division.

**What this does not do.** It does not authorize activating the Phase B engine. T-420
builds it behind a flag that reads the operator-owned constitutional file; turning the flag
on is a separate operator act, after T-421's adversarial verify comes back clean.
