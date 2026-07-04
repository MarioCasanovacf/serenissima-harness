# ReContext Evidence Buffer (gemini.md §4B)

Gemini agents: before writing final changes, paste here the EXACT code blocks,
class definitions, schemas or spec lines you extracted during your scan, then
reference these lines while implementing (Scan → Extract → Replay → Reason).

Claude agents may read this file for cross-engine context but write their own
evidence into task notes instead.

Format per entry:

```
## [T-XXX] <what this evidence supports> — <agent> — <ISO timestamp>
Source: <file>:<lines>
<verbatim extract in a fenced block>
```

---
## [T-002] NLAH gemini.md ReContext evidence — gemini-runner — 2026-07-03T19:34:13-06:00
Source: gemini.md:62-67
```
### B. ReContext (Recursive Evidence Replay)
To handle long-context reasoning in massive workspaces without losing focus:
1. **Scan**: Perform a broad scan of the codebase using grep or local indexing.
2. **Extract**: Copy the exact relevant code blocks, class definitions, or API signatures.
3. **Replay**: Write these extracted segments into `.harness/recontext_evidence.md`.
4. **Reason**: When writing the final code changes, reference the exact lines in `recontext_evidence.md` to ensure high-fidelity implementation.
```

## [T-002] Blackboard protocol evidence — gemini-runner — 2026-07-03T19:34:13-06:00
Source: .harness/blackboard.json:6-11
```
  "protocol": {
    "single_source_of_truth": "This file is the shared index of all tasks and the FIRST thing every agent must read before acting (claude.md §2A, gemini.md §2B).",
    "write_rule": "NEVER hand-edit this file. All mutations go through `python3 .harness/bin/blackboard.py <command>`, which serializes writes through a guard flock and enforces the cascade gate (a task is claimable only when all depends_on are done).",
    "read_rule": "Read freely at any time; reading requires no lock.",
    "collision_model": "One guarded mutable index (this file) + one detail file per task in .harness/tasks/ (written only by the claiming agent, via blackboard.py --note) + append-only event logs in .harness/logs/. Source-file edits additionally require a write lock (lock.py / .harness/locks/)."
  },
```

## [T-009] demo: living proof for T-009 — substrate-worker-2 — 2026-07-04T04:28:09Z
Source: .harness/bin/lock.py:98
```
test extract line
```

## [T-009] verifier replay probe — harness-verifier — 2026-07-04T04:41:20Z
Source: .harness/bin/recontext.py:1
```
verifier replay probe
```
