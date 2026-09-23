# Write locks

One `.lock` file per workspace file an agent is editing. Managed exclusively by
`python3 .harness/bin/lock.py` (acquire / release / status / sweep) — do not create
or delete lock files by hand.

- Name: relative path with `%` escaped as `%25`, then `/` as `%2F`, e.g.
  `src%2Fmain.py.lock`. Before the 2026-09-22 sync the separator was `__`, which let
  `a/b` and a file named `a__b` share one lock. A lock taken under an old `__` name is
  invisible to `acquire` and `check_lock.py` under the new scheme until its TTL runs
  out and `sweep` clears it.
- Payload: `{path, holder, task_id, acquired_at, ttl_seconds}`.
- Liveness: expired locks (past TTL) are dead — any acquire or `sweep` clears them.
- `.guard` is the flock target that serializes blackboard/state mutations; it is
  permanent and holds no data.

Claude Code sessions enforce these locks mechanically via the PreToolUse hook
(`.harness/bin/check_lock.py`). Other engines must check voluntarily per their NLAH.
