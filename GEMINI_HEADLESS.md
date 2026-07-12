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

Every execution also has a real wall-clock bound, including periods when Gemini emits no
stdout. By default `--timeout-seconds` reads the shared
`.harness/state.json limits.max_seconds_per_command` value (currently 300 seconds), with the
same 300-second fallback as `goal_mode.py`; an operator may supply another positive value.
When the bound expires, the runner terminates and reaps Gemini's isolated process group,
returns deterministic exit code `124`, and records `status: blocked`, `blocked_reason:
wall_clock_timeout`, `elapsed_seconds`, and `wall_clock_timeout_seconds` in `summary.json`.
This wall-clock result is distinct from Gemini's own turn-limit exit code `53`.

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
Use `--timeout-seconds N` to override the shared command bound for a particular run; `N` must
be greater than zero.

## Real approval probe

The non-`--yolo` approval behavior is **not yet established** in this environment. On
2026-07-12, task T-314 installed the official stable npm distribution
`@google/gemini-cli` 0.50.0 under `/private/tmp` (Node 24.15.0, npm 11.12.1) and invoked
this runner with a 30-second wall-clock bound. The self-contained prompt required
`run_shell_command` to execute the harmless command `pwd`; the invocation contained
neither `--yolo` nor any approval-mode override.

Gemini exited before producing a `tool_use` event: exit code 41 after 0.826 seconds,
with no JSONL events, because no authentication method was configured. A safe follow-up
confirmed that `GEMINI_API_KEY`, `GOOGLE_GENAI_USE_VERTEXAI`, and
`GOOGLE_GENAI_USE_GCA` were absent, the Gemini settings selected no auth type, and no
preinstalled Gemini, Antigravity, or `gcloud` executable was available. The replayable
runner summary is
`.harness/logs/gemini/T-314/20260712T013044Z-d0bfe186d6/summary.json`; its stderr records
the authentication requirement without containing credentials.

Therefore this probe demonstrates a fast authentication failure, not auto-deny, approval
waiting, or timeout behavior. Do not infer any of those outcomes from it. Before claiming
unattended readiness, repeat the same bounded probe in an authenticated environment and
record whether the real tool request is denied, approved, or remains pending until the
runner returns exit 124.
