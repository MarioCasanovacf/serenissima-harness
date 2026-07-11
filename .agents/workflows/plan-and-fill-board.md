---
description: Turn a new goal into a dependency DAG on the shared harness blackboard without implementing source code
---

Read `gemini.md`, `ORCHESTRATION.md`, `.harness/README.md`, and the live board. Act only as
`gemini-planner`. Decompose the supplied goal into independently claimable tasks, adding an
edge only for a real artifact dependency. Give every task an exact acceptance command and
engine route. Publish only through `blackboard.py`, locking planning artifacts before writes.
Never implement worker tasks. Report the DAG and immediately claimable frontier.

If native Gemini subagents are available, the coordinator may invoke
`@orchestration-planner`; otherwise this workflow is the full direct fallback.
