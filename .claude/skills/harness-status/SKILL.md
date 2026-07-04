---
name: harness-status
description: Print the live Universal Agent Harness status - blackboard task DAG, claimable frontier, cascade gates, active write-locks and recent events. Use when the user asks what the harness is doing, qué está pasando, board status, or before planning new work.
---

# Harness Status

Run these from the workspace root (all read-only):

1. `python3 .harness/bin/blackboard.py status`
2. `python3 .harness/bin/lock.py status`
3. `tail -n 20 .harness/logs/events.jsonl` (skip silently if the file does not exist yet)

Then synthesize for the user, in their language:

- **Frontier**: which tasks are claimable RIGHT NOW (deps satisfied, unclaimed) and which
  are gated by the cascade (list the blocking task ids).
- **In flight**: claimed/in_progress tasks, by whom, and lease expiry; flag anything the
  lease-expiry sweep just released (possible stalled agent).
- **Review queue**: tasks waiting for a verifier (producer ≠ approver rule).
- **Locks**: live vs expired write locks; recommend `lock.py sweep` if expired ones linger.
- **Anomalies**: repeated `busy:` refusals, REJECTED notes, or claim churn in the last
  events — these feed the evolution audit.

Close by pointing to `ORCHESTRATION.md` for the topology rules and, if the frontier is
non-empty, suggest the concrete next delegation (which bench agent should claim what).
