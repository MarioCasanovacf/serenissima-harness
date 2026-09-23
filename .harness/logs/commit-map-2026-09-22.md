# Commit map, 2026-09-22

On 2026-09-22 the operator ratified removing a personal profile flag from four board files
before publishing (decision D2 of the sync round). Git history was rewritten from `8b3e161`
onward to replace that flag with `personal:operator`. No other bytes changed: the tree diff
between the old and new tip touches exactly those four files, and no signed file is among them.

Rewriting changes commit identifiers. Task notes written before the rewrite cite commits by
their old identifier (for example T-376, T-401, T-405, T-407, T-408, T-411, T-418, T-420 and
`.harness/logs/triage_2026-08-30.md`). Those notes are records and are not edited. Resolve an
old identifier through this table instead.

60 of 66 commits changed identifier; the first 6 predate the flag.

| old | new | date | subject |
| --- | --- | --- | --- |
| `e8b76e2` | `e8b76e2` | 2026-08-11  | Precedent layer v0: jurisprudence for agent sessions (T-330..T-348) |
| `229c798` | `229c798` | 2026-08-11  | Precedent layer v1: Genoese-realist amendment via the layer's own protocol (T-350..T-363) |
| `40eb6f9` | `40eb6f9` | 2026-08-11  | PR-014 fleet-first precedent + v1 test suite completion (T-364) |
| `c9cc10b` | `c9cc10b` | 2026-08-11  | Operator ratification session: R-A/R-B/R-C promulgated, ESCA-01/02 applied |
| `51da1eb` | `51da1eb` | 2026-08-12  | Addendum II: reputation Phase A, displacement bridge, Westphalia records (T-366..T-376) |
| `a94d1e0` | `a94d1e0` | 2026-08-13  | Operator ruling round 2: census ratified, PR-034 maturity axis, AB9-OQ2 amended with audit |
| `8b3e161` | `c27f216` | 2026-08-15  | Metric epic groundwork: anti-freeze design, dossier verification, retired-skill purge |
| `8fbc0a7` | `0e36f6b` | 2026-08-15  | M-2: event-log reader with a declared denominator and a declared provenance filter |
| `d5704c7` | `31a8fe4` | 2026-08-15  | roster.py: issued names and published plazas, and only that half |
| `900ce8e` | `036fd5f` | 2026-08-15  | Repair roster.py after adversarial refusal of the PR-023 appeal |
| `39c749e` | `8896f5e` | 2026-08-15  | Identity gate: operator-signed warrants close Sybil minting (D-16..D-21) |
| `433c12f` | `dc43100` | 2026-08-15  | Document the identity gate in the harness spec |
| `553b995` | `34ed1bb` | 2026-08-15  | Repair the identity gate after a blind panel refuted it |
| `6afd734` | `8cfde5e` | 2026-08-15  | Correct the signing command: -U through ssh-agent, not the private key file |
| `25bacd2` | `dcfc460` | 2026-08-15  | Close the second panel's nine findings; retract a false proposition |
| `c001b68` | `6f45322` | 2026-08-15  | D-22/D-23: the impersonation rule set, written knowing prevention is unavailable |
| `e53207a` | `d5c2d0b` | 2026-08-15  | Build the A.8 currency-health indicator (PR-023 clause 5) |
| `cbd81aa` | `730963a` | 2026-08-15  | Draft the PR-022 clause 4 amendment for operator review; publish nothing |
| `3767a92` | `80fe00f` | 2026-08-15  | currency.py: refuse to name a drift direction on a thin window |
| `e39bf07` | `12aa5c4` | 2026-08-15  | Operator ruling round 3: canonicity sequenced behind the anchor defect (D1-D7) |
| `9c0f90f` | `77cac18` | 2026-08-15  | Third blind panel: REFUSE 4-0, and two detectors repaired that it caught silent |
| `5fa947f` | `48c6af7` | 2026-08-15  | Ruling round 3.2: A.8.3 built, amendment archived, enrolment commands supplied |
| `e317b3d` | `e5724f2` | 2026-08-15  | Fourth blind panel: OPEN NARROWLY 4-0, and the docket's premise is inverted |
| `9216818` | `1405f22` | 2026-08-15  | Correct the prose-reference count in the PR-026 docket verdict: 17, not 19 |
| `c0d1b6f` | `8ead69b` | 2026-08-15  | Ruling round 4: D1 rescoped (A+C build, B rides the legislative channel), D2 ratified, Swi |
| `c843056` | `4a71099` | 2026-08-15  | Ruling 4.1: the assembly is a persuasion market; ratification as the only unforgeable unit |
| `9184c70` | `dc1586b` | 2026-08-16  | Ruling 4.2: denomination in ratifications ratified, correctives ratified, enrolment verifi |
| `ca2a54c` | `74fba9f` | 2026-08-16  | Panel result round 4: 12 of 12 REFUTED, plus four coordinator defects the panel found |
| `bb8b721` | `883a586` | 2026-08-16  | Round 4 remedy: four tracks, two requiring no ratification |
| `85d9415` | `3e719c6` | 2026-08-16  | Track 1: wire PR-015's confirmation floor to the done-guard that already proves distinct i |
| `85931c9` | `da104a3` | 2026-08-16  | Retire the taste-calibration epic by operator ruling; record what the board actually shows |
| `0bbb4f1` | `1ca289b` | 2026-08-16  | Draft W-001: the first seating, unsigned, awaiting the operator's key |
| `8a30b56` | `4b0114a` | 2026-08-16  | Valley intake: adopt four clerk offices, redraft the seating as W-002, name the one rung w |
| `c0cd411` | `8aa7294` | 2026-08-17  | Repair OPERATOR-ENROLMENT: -c cannot prompt on a stock macOS, so signing was impossible |
| `6d3ff9e` | `b762ec6` | 2026-08-17  | Fix the warrant signing command at its source in warrant.py draft |
| `19d9e5b` | `97721e8` | 2026-08-17  | Third repair of the warrant signing command, this time with the failing path reproduced |
| `88c1c97` | `f252a77` | 2026-08-17  | W-002 signed and applied: rung 5 goes from 0 occupants to 9 |
| `c7d5993` | `dc9b7a3` | 2026-08-17  | PR-060 publishes the D2 split; T-376 silent-discard fixed (T-399, T-376) |
| `3b75745` | `d13d42e` | 2026-08-17  | D3a: a privileged act needs a declared intent first, and the trace must reach the root (T- |
| `7243d38` | `6c1f1df` | 2026-08-17  | D3b: delegation ceiling and credentials that expire and cannot extend themselves (T-401) |
| `f18654a` | `515ff44` | 2026-08-17  | D4a: distinguish disposes of a case by citation, not by legislation (T-402) |
| `6ae88c6` | `2d03577` | 2026-08-17  | D4b: the PR-029 KPI, whose correct output today is a refusal (T-403) |
| `5f1b4fb` | `d73b6b7` | 2026-08-19  | Turn accounting in usage_report, and the refusal to compute k from it |
| `6b81e38` | `7069a9c` | 2026-08-19  | Three verifiers rule on the six decisions; one rejects, and the rejection was right |
| `51cf01a` | `5e96ad5` | 2026-08-19  | T-411: the flaky timeout test was hiding a runner defect (RUNNER-LAUNCH-MISREPORT-A) |
| `d1414cc` | `247f700` | 2026-08-19  | T-408 + T-410: an intent that names a target is bound to it; the KPI guard asks the output |
| `ab1246b` | `2c69684` | 2026-08-19  | T-407: the data-loss guard decides on the parsed command, not the raw string |
| `439eed0` | `9aeca09` | 2026-08-19  | T-405: precedent.py conditions -- a measured value per condition, or the literal |
| `cf60f26` | `a58e3af` | 2026-08-19  | T-404, T-406, T-409, T-412: four deferred design questions, answered |
| `88edda7` | `19790b6` | 2026-08-19  | T-407 + T-410: two verifier rejections, both real, both repaired in the mechanism |
| `c640039` | `dadbd73` | 2026-08-19  | T-412: --case on every publish, and a pre-register bucket that is never folded into a shar |
| `a5e27e8` | `7ca91e5` | 2026-08-19  | T-407 + T-410: four more escapes, all found by verifiers, all closed in the mechanism |
| `852c709` | `f66c832` | 2026-08-19  | T-407+T-410 round 3: wrapper arity, shelling out, ANSI-C quoting; formatted figures, stder |
| `f120445` | `a72718a` | 2026-08-21  | T-407 + T-410 round 4: eval/source builtins (a regression, not an escape) and the --json s |
| `9eedc2d` | `2b98aa4` | 2026-08-30  | Gen-7 opens: RAT-01 cures PR-061, the clerk constraint becomes mechanical, and the assembl |
| `2989a4e` | `ed3f16b` | 2026-08-30  | T-420 + T-417 round 2 + triage: the gate is the operator's key, and an audit that cannot f |
| `b8ac2a3` | `82dbd70` | 2026-08-30  | T-418: three deliberation-integrity guards, and the duration floor that is discussion, not |
| `4277c29` | `ae2641a` | 2026-08-30  | T-418 hardening: the stamp scan reads keys too, so 'exhaustive' is true |
| `83e3a84` | `9a19625` | 2026-08-30  | T-420 + T-418 round 2: the escapes the adversarial pass found, closed in the mechanism |
| `1dea277` | `57e60b0` | 2026-08-30  | gen-7 closes: both round-2 verdicts land, the three escapes stay closed |
| `c024644` | `326c10d` | 2026-08-31  | Constitutional draft for Phase B: unsigned by construction, closed until signed |
| `4962e4d` | `ea286bb` | 2026-08-31  | RAT-01 is signed: the ruling's authority now carries the operator's signature |
| `1272f60` | `263a48c` | 2026-08-31  | Phase B activates: the operator's signature lands and the gate opens |
| `df41278` | `9dd24f3` | 2026-09-20  | gen-8 opens: the dispatcher gets its first reader, and the assembly gets its guards |
| `d6ebf5e` | `32efe32` | 2026-09-20  | C-002 disposed by PR-062: the first consumer yields at next, and never at claim |
| `20f8f2c` | `fc9e71a` | 2026-09-20  | gen-8 closes: next yields to a higher score, claim stays first-come, PR-063 names the act |
