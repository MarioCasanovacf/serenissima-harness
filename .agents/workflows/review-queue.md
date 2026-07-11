---
description: Independently replay and verdict harness tasks in review from a fresh Antigravity context
---

This workflow must run in a conversation or Agent Manager task that did not produce the work.
Use a verifier identity such as `gemini-verifier-a` that differs from every selected task's
producer. Select review tasks through the guarded CLI, replay exact handoff commands, confirm
the intended tests actually ran, and add one independent check proportional to risk.

Set `done` with concrete VERIFIED evidence or return to `open` with a precise REJECTED note.
Never repair source in this context. If this conversation produced any selected task, stop and
open a fresh verification context; changing persona or identity text is insufficient.
