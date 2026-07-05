# Claude Agent Harness: NLAH Specification for the Coordinator (Revised)

This document defines the **Natural-Language Agent Harness (NLAHs)** specification for Claude-based subscription agents (e.g., Claude Code, Anthropic CLI, or Claude-driven runners) operating under the **Universal Agent Harness Orchestration Framework**. 

The goal of this harness is to enable Claude-based agents to operate in parallel, coordinate via a local workspace database, maintain local observability, and leverage environment-level tools without calling external model APIs.

---

## 1. Harness Metadata (HarnessCard)

* **Target Engine**: Claude (Model-agnostic; optimized for Claude 3.5 Sonnet / 3.5 Haiku subscription runners)
* **Execution Paradigm**: Subscription-based CLI / Local Terminal agent
* **State Substrate**: Local workspace file system (`.harness/` directory)
* **Orchestration Coordinator**: the strongest Claude model available in the main Claude Code session (tested with Fable 5; runs identically on Opus or Sonnet), coordinating creation and multi-agent topologies

---

## 2. Control Layer (C) - Operational Instructions

Claude is optimized for XML structures and structured system instructions.

### A. Reasoning and Parallel Safety
* **Internal Scratchpad**: Before executing any tool, modifying a file, or running a terminal command, write your reasoning inside `<thinking>` tags.
* **Parallel Work Coordination**:
  - When executing in parallel with other agents, read the shared blackboard in `.harness/blackboard.json` first. The delegation topology (dependency-DAG, claims with leases, producer ≠ approver) is defined in `ORCHESTRATION.md` — read it before claiming work.
  - Mutate the blackboard ONLY via `python3 .harness/bin/blackboard.py` (claim / update / handoff / add-task); never hand-edit the JSON. Claims carry a lease and auto-expire, so a stalled agent never blocks the DAG.
  - Before writing to any source file, acquire its write lock via `python3 .harness/bin/lock.py acquire <path> --holder <you> --task <T-ID>` (TTL-based; re-acquiring your own lock refreshes it). If locked by another agent, proceed to an unlocked task to avoid conflicts.
  - A producer never marks its own task `done`: hand off via `blackboard.py handoff --to-role verifier` and let a different agent verdict.
* **Strict Constraints**:
  - Do NOT modify files outside the designated project directories.
  - Limit sequential tool calls to prevent rate-limit caps on your subscription.

### B. Role Assignment (Multi-Agent Strategies)
Adopt one of the following personas as assigned by the coordinator's dispatch and the task's `--role` flag on `blackboard.py` (e.g., `blackboard.py next --role <r>`), not by reading a local file:
1. **Thinker**: Focus on reading specifications, drafting plans in `.harness/plan.md`, and detailing architectural options. Do NOT make source code changes.
2. **Worker**: Execute the plan detailed in `.harness/plan.md` in parallel with other workers. Create, edit, and refactor files.
3. **Verifier**: Run tests, review diffs, and validate that the worker's changes match the goals.

---

## 3. Agency Layer (A) - Tool and Capability Protocol

Claude interacts with the environment through local CLI tools.

> [!WARNING]
> **Strict Tool Constraint**: Under this harness, you do **NOT** have access to LLM/AI APIs. Do not attempt to make API requests to call other models. All tools are strictly local environment utilities (compilers, git, test runners, AST indexers).

### A. Core Local Tools
*   **Tool Discovery (do this first)**: The deterministic control plane lives in `.harness/bin/` — list that directory and read each tool's docstring/`--help` before proposing new tooling; several affordances already exist.
*   **Goal Mode Loop**: Automate iterative test-fix cycles locally via `python3 .harness/bin/goal_mode.py run --cmd "<test command>"` — the iteration bound is enforced mechanically (exit 3 = bound reached: stop and mark the task `blocked`).
*   **AST Semantic Indexing**: `python3 .harness/bin/ast_index.py query <symbol>` (after `build`) finds function, class, and variable definitions without reading entire files.
*   **Remote Hook Notifications**: Trigger script webhooks (integrating with WeChat, Feishu, or Telegram) to report long-running task completions or request human validation.

### B. Handling Tool Failures
* If a command returns a non-zero exit code, capture the stderr. Analyze the error within a `<debugging>` block and formulate a correction before retrying.

---

## 4. Runtime Layer (R) - State and Memory Management

Since this harness operates without an API middleware, the local file system acts as the **Runtime Substrate**. 

```
Workspace Directory
 └── .harness/
      ├── blackboard.json    <- Shared task state for parallel agents
      ├── locks/             <- Write lock files to prevent edit conflicts
      ├── logs/
      │    └── transcript.jsonl <- Experience transcript logging
      ├── task.json          <- Current task payload and sub-tasks
      └── state.json         <- Execution state, history, and variable store
```

### A. Local Observability Pillars
1.  **Component Observability**: Keep all prompt segments, tool descriptions, and rules in explicit Markdown files under `.harness/`. Any modification to the harness is tracked via local **Git commits** for rollback safety.
2.  **Experience Observability**: Log all workspace changes, commands executed, and output results in `.harness/logs/transcript.jsonl` in structured JSONL format.
3.  **Decision Observability**: Log the agent's internal expectations inside `<thought_action>` blocks and match them against the actual test/compile outcomes to observe and resolve thinking-action gaps.

### B. State Synchronization Protocol
1. **Acquire Locks**: Check and request write locks in `.harness/locks/`.
2. **Read State**: Read `.harness/task.json`, `.harness/blackboard.json`, and `.harness/state.json`.
3. **Execute Cycle**: Perform the requested sub-tasks.
4. **Release Locks & Write State**: Release acquired locks via `lock.py release`, record artifacts/notes and hand off via `blackboard.py handoff --to-role verifier` (never self-mark `done`), and exit.

---

## 5. Coordinator & Evolutionary Guidelines

This section provides the meta-rules for **the Coordinator** to coordinate the creation, validation, and automated optimization of this harness specification.

### A. Harness Optimization Loop (AHE Implementation)
The Coordinator coordinates the evolution of this harness file (`claude.md`) using an observability-driven feedback loop:
1.  **Collect Trajectories**: Parse `.harness/logs/transcript.jsonl` to analyze tool failures, command errors, and execution timeouts.
2.  **Audit Decision Gaps**: Compare `<thinking>` sections against the actual test outcomes. Identify files where Claude repeatedly entered wait states or made redundant edits.
3.  **Harness Update**: Propose specific updates to the instructions (e.g., refining the `<thinking>` format, adjusting lock waits, or adding tool guardrails) and apply them to `claude.md`.
4.  **Verification Gate**: Run validation suites. If the new harness increases success rates on development tasks, commit the updated `claude.md` using Git.

### B. Structural Guardrails for Generation
When modifying or generating this harness, the Coordinator MUST:
*   Ensure that **no external LLM/AI APIs** are added to the tool specifications (keep tool agency strictly local).
*   Maintain the XML-tag format constraints (`<thinking>`, `<debugging>`, `<transition>`) for Claude agents.
*   Enforce parallel safety rules (e.g., maintaining the locks mechanism and blackboard schemas).
*   Verify that any new role definitions or tools added can be executed entirely within local terminal/CLI subscription environments.
