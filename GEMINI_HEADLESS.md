# Gemini CLI headless adapter

`gemini_headless_runner.py` is the non-interactive bridge between a self-contained harness
assignment and Gemini CLI. It does not claim tasks, acquire locks, hand off work, issue
verdicts, or edit `.harness/blackboard.json`; those lifecycle operations remain explicit calls
to the shared substrate.

The current [Gemini documentation](https://geminicli.com/docs/) announces that unpaid and Google
One users transition to Antigravity CLI. The adapter therefore does not hard-code distribution assumptions: use
`--gemini-bin <path>` or `GEMINI_BIN=<path>` for the executable available in the operator's
channel. Its stream contract must be rechecked against that installed binary before unattended
production use.

The implementation follows Gemini CLI's official headless contract: `--output-format
stream-json` emits newline-delimited `init`, `message`, `tool_use`, `tool_result`, `error`, and
`result` events. Exit code `53` means that the turn limit was exceeded. The runner therefore
preserves code 53 and records the run as `blocked`; all other child exit codes are also
preserved. See the official [headless mode reference](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/headless.md)
and [CLI reference](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/cli-reference.md).

Run dependency discovery without a prompt:

```sh
python3 .harness/bin/gemini_headless_runner.py --discover
```

Inspect an invocation without requiring Gemini CLI or writing logs:

```sh
python3 .harness/bin/gemini_headless_runner.py \
  --prompt-file .harness/tasks/TASK-001/prompt.md \
  --agent-id gemini-worker-1 \
  --task-id TASK-001 \
  --dry-run
```

Execute it by removing `--dry-run`. The wrapper invokes an argument vector with `shell=False`,
never adds `--yolo` or `--approval-mode=yolo`, streams Gemini's JSONL unchanged to stdout, and
stores `events.jsonl`, `stderr.log`, and `summary.json` beneath a unique directory at
`.harness/logs/gemini/<task>/<run>/`. Configure the executable with `--gemini-bin` or
`GEMINI_BIN`; use `--model` only when the task requires a particular model.
