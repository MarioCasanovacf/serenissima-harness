# Write locks

One `.lock` file per workspace file an agent is editing. Managed exclusively by
`python3 .harness/bin/lock.py` (acquire / release / status / sweep) — do not create
or delete lock files by hand.

- Name: relative path with `/` replaced by `__`, e.g. `src__main.py.lock`.
- Payload: `{path, holder, task_id, acquired_at, ttl_seconds}`.
- Liveness: expired locks (past TTL) are dead — any acquire or `sweep` clears them.
- `.guard` is the flock target that serializes blackboard/state mutations; it is
  permanent and holds no data.

Claude Code sessions enforce these locks mechanically via the PreToolUse hook
(`.harness/bin/check_lock.py`). Other engines must check voluntarily per their NLAH.
