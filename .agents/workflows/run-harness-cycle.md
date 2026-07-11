---
description: Coordinate planning, Gemini frontier execution, and independent review until a harness goal reaches a real terminal outcome
---

Read `gemini.md` and the live board. If the goal is absent, execute `plan-and-fill-board`.
Then execute `work-frontier` over only the legal frontier. At each join, re-read the board
rather than trusting summaries. Dispatch every review item to a fresh Antigravity conversation
or Agent Manager task running `review-queue`, with a verifier identity different from its
producer. Resume reopened work with a new worker context.

Continue until the requested goal is done or a genuine human gate is reached. If Antigravity
cannot create independent contexts automatically, pause only at the producer/verifier boundary
and give the operator the exact `/review-queue` instruction to open in a new conversation.
Never simulate independence by changing personas in one context.
