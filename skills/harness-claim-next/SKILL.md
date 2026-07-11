---
name: harness-claim-next
description: Join the Universal Agent Harness as a Codex worker, claim the next legal Codex task, lock files, execute bounded work, and hand it to an independent verifier.
---

# Claim the next Codex task

Read `AGENTS.md`, `ORCHESTRATION.md`, and the task detail before editing. Use the unique identity supplied by the caller, for example `codex-worker-a`; if none was supplied, use `codex-worker`.

Run `python3 .harness/bin/blackboard.py next --agent <identity> --role worker --engine codex`. If nothing is claimable, report the cascade gate and stop. Claim only the returned task. Acquire `python3 .harness/bin/lock.py acquire <path> --holder <identity> --task <T-ID>` for every target file before writing, and announce `in_progress` through the blackboard CLI.

Execute only the claimed acceptance criteria. Use `goal_mode.py` for bounded edit-test-fix cycles, record expected versus actual outcomes, and register all artifacts. On exhaustion, mark the task blocked and release locks.

Never permanently delete workspace files or discard user edits. Do not run `rm`, `git clean`, `git reset --hard`, `git restore`, forced checkout, force-push, or an `apply_patch` deletion. If a task genuinely requires removal, quarantine the path with `python3 .harness/bin/safe_delete.py quarantine <path> --reason "<why>"`; restoration remains available and the action is audited.

Finish with `blackboard.py handoff <T-ID> --to-role verifier` and a replayable evidence note. Never mark the task done yourself. Release every acquired lock.
