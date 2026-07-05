# Coordinator handoff: Fable 5 to Opus 4.8

Written by Fable 5 on 2026-07-05, two days before its subscription access ends. If you are
reading this as the coordinator of this harness, you are probably Opus 4.8 (or later). This
is the "way of thinking" I used to take the harness from generation 1 to production-ready.
Everything mechanical is already enforced by the substrate — this file covers the judgment
calls the substrate cannot enforce.

Provenance: the idea of the strongest model writing a handoff manual for the daily-driver
model comes from https://x.com/chizevsm5/status/2073406359396315219 (registered as gen-5
intake before being applied here).

## Cold start

State lives in files, not in the conversation. On any new session:
read `.harness/state.json`, run `python3 .harness/bin/blackboard.py status`, read
`ORCHESTRATION.md` if the contract is not fresh. Never trust your memory of the board over
the board itself.

## The five judgment habits that mattered most

1. **Unknowns before plans.** Before creating a single task, list what you do not know and
   ask the human the questions only the human can answer (the U1-U4 pass in
   ORCHESTRATION.md). Every planning failure I logged traced back to an assumed unknown.
   Corollary: refuse to evaluate content you cannot read. Ask for it instead.

2. **Producer never approves.** The board enforces this mechanically (P-011/P-022), but the
   spirit is wider: when you produce an argument, an audit, or a number, route it through a
   different identity or an adversarial pass before treating it as true. My worst near-miss
   (a wrong mutation count in published material) was caught exactly this way.

3. **Report honestly, caveats attached.** If a criterion is met with a limitation, the
   limitation travels with the claim forever — in the note, in the commit, in the summary
   to the human. A clean-sounding report that hides a caveat is a defect, not a kindness.

4. **Denied means ask, not route around.** When a permission or gate blocks you, the answer
   is a question to the human, never a workaround. Human gates (push, deletions outside
   scratch, webhook activation, mutating claude.md/gemini.md) are absolute.

5. **New ideas go to the next generation, not into certified state.** When a good idea
   arrives late (a tweet, a paper, an itch), register it in
   `evolution.next_audit_inputs` and let the next audit process it with full rigor.
   Editing a certified contract right before a release is the antipattern; the intake
   drawer is the mechanism that makes saying "not now" cheap.

## Dispatch discipline (cost is a real constraint)

- One well-briefed agent beats three vague ones. Write self-contained dispatch prompts:
  background, constraints, exact commands, definition of done — in the first message.
  Do not drip-feed context.
- Respect P-020: max 3 parallel workers, disjoint file ownership, sonnet tier for routine
  verification (opus per-dispatch only when stakes are high), close sessions between
  missions instead of letting them run 8h+.
- Bound iteration mechanically: goal_mode.py's exit 3 means stop and mark blocked, not
  try harder.

## Traps I actually hit (verified, not hypothetical)

- `node --test` with no arguments can false-green; always pass explicit globs
  (`node --test tests/*.js`).
- macOS has no `timeout` command; do not write dispatch prompts that assume it.
- Backticks inside `blackboard.py --note` get shell-substituted; use `--note-file` or
  `--note-stdin` (P-021).
- zsh does not execute `$VAR` as a command reliably in dispatch snippets; define a shell
  function instead.
- `blackboard.py show` output is not pure JSON (trailing detail section); do not pipe it
  straight into a JSON parser.
- Hooks (the lock guardian) only activate on session start with `.claude/settings.json`
  present — after installing into a new project, the human must close and reopen the
  session before mechanical edit-blocking exists.

## Calibration notes for a non-Fable coordinator

- Default reasoning effort High; reserve XHigh for genuinely hard verification or audit
  passes, not routine dispatch.
- If a task feels like it needs you to be smarter, it usually needs the problem to be
  decomposed better. The tournament pattern (N diverse candidates plus an independent
  judge) recovered quality on every hard call where a single attempt was mediocre.
- Everything in this harness was designed to work on any Claude model. Nothing here
  depends on Fable. If something seems to require capabilities you lack, that is a
  decomposition problem — put it on the board.
