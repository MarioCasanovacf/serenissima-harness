# Onboarding example board

Four tasks, one for each state a new operator needs to see before running agents:

| Task  | State   | What it shows |
|-------|---------|---------------|
| T-001 | done    | a finished task with its evidence (`show T-001`) |
| T-002 | review  | handed off, waiting for a *different* agent's verdict (producer is never approver) |
| T-003 | open    | claimable right now |
| T-004 | open    | gated: not claimable until T-003 is done (the cascade gate) |

It arrived with PR #3, where it was the board a fresh clone shipped with. The sync of
2026-09-22 moved it here (operator ruling D1).

**This is not the live board.** `.harness/blackboard.json` and `.harness/tasks/` hold this
repository's own working history. The precedent registry, the signed acts in
`.harness/acts/` and `reputation.py` all cite that history by task id. The example's ids
T-001..T-004 are also live ids. The live tasks stay in `.harness/tasks/`, and this
directory is the only place the example exists.

## Explore it without touching the live board

Run this from the repository root. It builds a throwaway copy of the harness in a temp
directory and loads the example there:

```sh
SANDBOX="$(mktemp -d)"
mkdir -p "$SANDBOX/.harness/tasks" "$SANDBOX/.harness/logs" "$SANDBOX/.harness/locks"
cp -R .harness/bin "$SANDBOX/.harness/bin"
cp examples/onboarding/blackboard.json "$SANDBOX/.harness/blackboard.json"
cp examples/onboarding/tasks/*.json "$SANDBOX/.harness/tasks/"

python3 "$SANDBOX/.harness/bin/blackboard.py" status
python3 "$SANDBOX/.harness/bin/blackboard.py" show T-001
python3 "$SANDBOX/.harness/bin/blackboard.py" claim T-004 --agent you   # refused: T-003 is not done
python3 "$SANDBOX/.harness/bin/blackboard.py" claim T-003 --agent you   # succeeds
```

Every tool finds the harness root from its own location on disk. The copy in `$SANDBOX`
therefore reads and writes only inside `$SANDBOX`. The directory is disposable.

In the sandbox, `status` ends with `phase-b claim order not applied: dispatch exited 1`.
This is expected. Phase B claim ordering needs this repository's operator-signed
constitutional file, and the sandbox does not copy it. The board works the same without
Phase B ordering.

## Start your own project clean

This section is for an adopter who cloned the harness to run their own project. Never
run it on this repository's live board. A reset archives every task file that the
precedent citations resolve against, and `precedent.py cite --all` would report all of
them as dangling until the archive is restored.

```sh
python3 .harness/bin/blackboard.py reset --agent you --yes
```

`reset` refuses without `--yes`. It moves the board, the task files and `state.json` to
`.harness/trash/reset-<timestamp>-<id>/` before clearing anything, so the reset can be
undone. It keeps the configuration in `state.json` (limits, human gates, the evolution
ledger) and clears only the reputation earned on the old tasks. From the empty board,
publish your own work with `add-task`.

To practise on the example first, copy it onto the empty board **before any agent starts**:

```sh
cp examples/onboarding/blackboard.json .harness/blackboard.json
cp examples/onboarding/tasks/*.json .harness/tasks/
```

The operator makes this one whole-file copy onto a board that `reset` just emptied. It is
not an agent edit. After it, every change goes through `blackboard.py`, which is the only
sanctioned writer of the board.

To install the harness into a *different* project, use
`python3 .harness/bin/migrate_project.py <target-dir> --dry-run`, then run it again
without `--dry-run`. The target gets an empty board and no task history. Copy the example
into the target's `.harness/` the same way if you want it there.
