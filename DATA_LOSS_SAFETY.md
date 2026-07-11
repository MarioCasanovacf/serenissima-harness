# Data-loss safety for Codex

OpenAI's GPT-5.3-Codex System Card section 4.1 identifies deletion and corruption
as high-impact failure modes for autonomous coding agents. It specifically calls
out apparently simple requests such as cleaning a folder or resetting a branch
that can become `rm -rf`, `git clean -xfd`, `git reset --hard`, or force pushes.

This harness adds a project and plugin `PreToolUse` guard for executable commands
and patches. Recognized destructive actions exit with status 2 before execution
and append a `data_loss_action_blocked` record to `.harness/logs/events.jsonl`
when the log is writable. The guard also covers Git operations that discard local
edits, direct filesystem deletion tools, common deletion one-liners, and
`apply_patch` file deletion.

Where this is actually wired today: `.codex/hooks.json` (project-scoped, for Codex
CLI opened in this repository), `hooks/hooks.json` referenced by the
`.codex-plugin/plugin.json` manifest's `hooks` key (installed-plugin path), and —
since 2026-07-11, by explicit operator opt-in — `.claude/settings.json`
(`PreToolUse` → `Bash`, alongside the scoped `guard_paths.py`), so direct Claude
Code sessions in this repo are covered too. Note the behavioral consequence of
that opt-in: `prevent_data_loss.py` blocks every `rm` invocation unconditionally,
so intentional cleanup inside agent sessions must go through
`safe_delete.py quarantine`. The hook command uses `$CLAUDE_PROJECT_DIR`, so the
same `settings.json` block is portable to any repo that carries
`.harness/bin/prevent_data_loss.py` (adopters via `migrate_project.py` get both
pieces automatically; existing adopters can copy the two bin files and add the
hook block by hand without touching their board state).

The guard is a backstop for recognizable tool input, not a proof that arbitrary
code is harmless. Encoded, generated, or otherwise indirect deletion can evade
static command matching. Keep Codex workspace sandboxing and approval policy
enabled as additional enforcement layers, and review elevated commands before
allowing them.

For intentional cleanup, use the reversible path:

```sh
python3 .harness/bin/safe_delete.py quarantine path/to/item --reason "generated output cleanup"
python3 .harness/bin/safe_delete.py list
python3 .harness/bin/safe_delete.py restore ENTRY_ID
```

Quarantined content stays under `.harness/trash` with a manifest recording the
actor, reason, and original relative path. Quarantine and restoration also emit
structured audit events. Restore refuses to overwrite a new user-created path. The CLI has
no purge operation, and it refuses the workspace root, paths outside the
workspace, and harness control-plane files.

Source: [GPT-5.3-Codex System Card, section 4.1](https://deploymentsafety.openai.com/gpt-5-3-codex/safeguards#4-model-specific-risk-mitigations).

Full test coverage requires Python 3.11+ (`tomllib`); under 3.9 two Codex
TOML-validation tests silently skip.
