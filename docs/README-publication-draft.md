# Universal Agent Harness

**A file-based coordination substrate that lets multiple AI agents work a real codebase in parallel — without stepping on each other, without approving their own work, and with an auditable evidence trail for every decision.**

No databases. No external APIs. No framework lock-in. Plain files + nine stdlib-only Python CLIs + a set of rules that are *programs, not promises*.

> Built for Claude Code, but engine-agnostic by design: any agent (or human) that can run a CLI can join the swarm. The enforcement hooks are Claude-side sugar; the contract is universal.

---

## Why this exists

Two failure modes plague multi-agent coding:

- **Unmanaged parallelism**: agents duplicate work, overwrite each other, and nobody delegates.
- **The giant cascade**: one long delegation chain where every hop loses context and one stalled link halts everything.

The resolution: **delegation is a property of the task graph, not the org chart.** Work is a dependency-DAG on a shared blackboard. The cascade exists exactly where an artifact dependency is real (the CLI *refuses* premature claims), and everything else runs in parallel under TTL write-locks and leased claims — so nothing can stall forever, and nothing collides.

## The rules (mechanically enforced)

| Rule | Mechanism |
|---|---|
| No claiming blocked tasks | `blackboard.py claim` refuses unmet `depends_on` (cascade gate) |
| No editing files someone else holds | TTL write-locks + a PreToolUse hook that blocks the edit before it happens |
| No agent stalls the swarm | Claims carry leases, locks carry TTLs — everything auto-expires back to the pool |
| **No one approves their own work** | `--status done` is refused unless the task went through review AND the actor differs from the producer of record |
| No self-whitelisting | Session-holder registration is coordinator-gated by ambient identity |
| No unsupervised escalation | Human gates: `git push`, deletions, first webhook, and mutating the agent constitutions ALWAYS require explicit human approval |
| No silent evolution | The harness mutates itself only through an audit loop: logs → evidence-cited proposals → adversarial verification → gated apply → generation bump (git = rollback) |

## What's in the box

```
.harness/               The runtime substrate
 ├── blackboard.json    Task DAG (only blackboard.py may write it)
 ├── bin/               9 stdlib-only CLIs: blackboard, lock, session,
 │                      goal_mode, ast_index, notify, recontext, log hooks,
 │                      and migracion_proyecto.py (one-command transplant)
 ├── locks/  logs/      TTL locks · append-only evidence (events + transcript)
 └── state.json         Limits, human gates, agent registry, evolution memory
.claude/agents/         The bench: planner / worker / verifier / evolution-analyst
.claude/settings.json   Hooks: mechanical lock enforcement + flight recorder
ORCHESTRATION.md        The topology contract (DAG, lifecycle, invariants, patterns)
USAGE.md                Operator guide — start here
projects/               Proof of work: two real projects built BY the harness
```

## Proof it works (dogfood record)

This harness **built itself, evolved itself four generations, and shipped two real projects** under its own rules — every task producer≠approver, every verdict adversarially replayed:

- **mdtoc** (Python): a Markdown TOC generator — including the harness's first *tournament*: 3 independent slugger implementations with deliberately different methods, judged on real-input fidelity, promoted verbatim.
- **cronsplain** (Node.js, zero deps): a cron-expression explainer + next-occurrence engine — planned with a formal Unknowns pass (4-quadrant blindspot interview *before* the DAG published), second tournament (brute-force vs field-cascade candidates, 450-input cross-diff), 93 tests.
- **Four generations of self-audits** with falsifiable proposals — including catching its own auditors: one audit was *rejected* for a wrong evidence count and had to re-diagnose; a verifier once caught the coordinator's own math error.
- **A swarm smoke**: two concurrent OS processes racing one board — zero double-claims, cross-identity locks held.

The full evidence trail (task files, verdicts, event logs, audits) ships in the repo. Nothing here is claimed that a `grep` can't confirm.

## Quickstart

```bash
# 1. Get it into your project (one command, never overwrites your files):
python3 .harness/bin/migracion_proyecto.py /path/to/your/repo --dry-run   # preview
python3 .harness/bin/migracion_proyecto.py /path/to/your/repo             # transplant

# 2. Open Claude Code IN your repo (hooks live where the session is rooted) and say:
#    "Read ORCHESTRATION.md and USAGE.md. My goal: <describe it>.
#     Planner: decompose it onto the board and dispatch."

# 3. Watch the board:
python3 .harness/bin/blackboard.py status
```

Requirements: Python ≥3.9 (stdlib only), git, and any Claude Code plan (tested with Fable 5; runs identically on Opus or Sonnet — the coordinator is a role, not a model).

## Design lineage

Standing on: the blackboard-architecture tradition; Anthropic's multi-agent research patterns; and Thariq Shihipar's *unknowns* framework (known/unknown × knowns/unknowns), whose pre-flight blindspot pass is now a mandatory planner step here. Frictions become audit inputs; audits become generations. The tool that coordinates the work is itself work the tool coordinated.

## License & contributions

[OPERATOR TO DECIDE: license]. Issues and PRs welcome — but read `ORCHESTRATION.md` first; this repo eats its own dogfood, and proposals against the harness follow the §5A evolution loop like everything else.
