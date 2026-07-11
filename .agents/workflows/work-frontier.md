---
description: Execute the currently claimable Gemini frontier with unique workers, explicit locks, bounded loops, and handoffs
---

Read the board and the parallel limit. When Antigravity can create separate conversations or
Agent Manager tasks, assign each independent frontier item a unique identity such as
`gemini-worker-a`, `gemini-worker-b`, and `gemini-worker-c`. Each context must independently
claim its own returned task, acquire all file locks, run bounded goal mode, register evidence,
and hand off to role `verifier`. Never exceed the harness limit or let two workers share an
identity.

If parallel contexts are unavailable, process the frontier sequentially in this conversation,
using a fresh unique worker identity for each task. Do not issue verdicts here. Release all
locks and leave completed production work in `review` for a separate verifier context.
