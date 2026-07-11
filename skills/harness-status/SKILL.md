---
name: harness-status
description: Inspect the Universal Agent Harness board, claimable frontier, review queue, leases, locks, and recent lifecycle events. Use for board status or before planning new work.
---

# Harness status

This workflow is strictly read-only.

From the workspace root, run `python3 .harness/bin/blackboard.py status`, then `python3 .harness/bin/lock.py status`. Read the last 20 lines of `.harness/logs/events.jsonl` when the file exists.

Report the claimable frontier, cascade-gated tasks and their dependencies, work in flight with holder and lease expiry, the review queue, live or expired locks, and recent rejection or contention anomalies. Recommend the appropriate native Codex agent for the next legal action, but do not claim or mutate anything.

