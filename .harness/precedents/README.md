# `.harness/precedents/` — the precedent registry (D5)

One JSON file per record, `PR-NNN.json`, mirroring `.harness/tasks/`. This
directory holds ONLY live, published records — never test fixtures. This
file exists purely so git tracks the (otherwise-empty) directory and to
point elsewhere; it does not restate the schema.

- **Schema, CLI surface, exit codes**: `docs/precedent-research/synthesis-design-requirements.md`
  (T-339) is the fixed source; `.harness/bin/precedent.py --help` and each
  subcommand's `--help` reflect what actually shipped.
- **Doctrine, tier ladder, failure modes**: `PRECEDENT.md` (T-341/T-345),
  once written — cites `ORCHESTRATION.md` and this schema by name rather
  than restating either.
- **Mutate records only via** `python3 .harness/bin/precedent.py publish|confirm`
  (guarded, atomic writes) — never hand-edit a `PR-NNN.json` file, for the
  same reason `blackboard.json` is never hand-edited (`.harness/README.md:14-15`).
- **Registry-root override**: `--root <dir>` or `PRECEDENT_ROOT` env
  (flag wins) redirects every subcommand elsewhere — used by tests and by
  any future parallel registry so nothing test-only ever lands here.

No live record has been published into this directory by T-340 (forward-only
schema build; seeding is T-343's job).
