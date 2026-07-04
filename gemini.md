# Gemini Agent Harness: NLAH Specification for Fable 5 (Revised)

This document defines the **Natural-Language Agent Harness (NLAHs)** specification for Gemini-based subscription agents (e.g., Antigravity, Gemini Code Assist, or Gemini-driven runners) operating under the **Fable 5 Orchestration Framework**. 

The goal of this harness is to leverage Gemini's massive context window and native JSON-handling strengths, enabling parallel multi-agent execution and local observability without calling external model APIs.

---

## 1. Harness Metadata (HarnessCard)

* **Target Engine**: Gemini (Model-agnostic; optimized for Gemini 1.5 Pro / 2.0 Flash / 3.5 Flash subscription runners)
* **Execution Paradigm**: Subscription-based IDE Integration / Local CLI agent
* **State Substrate**: Local workspace file system (`.harness/` directory)
* **Orchestration Coordinator**: Fable 5 (coordinating creation and multi-agent topologies)

---

## 2. Control Layer (C) - Operational Instructions

Gemini models perform exceptionally well when guided by clean hierarchical markdown structures and strict schema constraints.

### A. Output Formatting and Schema Enforcements
* **Structured Response**: If requested by the coordinator, always format your final output as a valid JSON object matching the requested schema.
* **Reasoning Flow**: Start your response with a structured markdown planning block:
  ```markdown
  # Planning
  - **Goal**: [Summary of target]
  - **Evidence Replay**: [Key code segments or rules extracted via ReContext]
  - **Steps**: [List of actions to take]
  ```

### B. Parallel Execution and Lock Coordination
* When executing tasks in parallel, read `.harness/blackboard.json` to identify active tasks. The delegation topology (dependency-DAG, claims with leases, producer ≠ approver) is defined in `ORCHESTRATION.md` — read it before claiming work.
* Mutate the blackboard ONLY via `python3 .harness/bin/blackboard.py` (claim / update / handoff); never hand-edit the JSON. Claims carry a lease and auto-expire.
* Before writing to any source file, acquire its write lock via `python3 .harness/bin/lock.py acquire <path> --holder <you> --task <T-ID>` (TTL-based, auto-expiring). If a lock exists, skip the file or pick another task to prevent overwrite conflicts.

---

## 3. Agency Layer (A) - Tool and Capability Protocol

Gemini agents execute tools in a file-based workspace environment.

> [!WARNING]
> **Strict Tool Constraint**: Under this harness, you do **NOT** have access to LLM/AI APIs. Do not attempt to make API requests to call other models. All tools are strictly local environment utilities (compilers, git, test runners, AST indexers).

### A. Core Local Tools
*   **Tool Discovery (do this first)**: The deterministic control plane lives in `.harness/bin/` — list that directory and read each tool's docstring/`--help` before proposing new tooling; several affordances (e.g. `lock.py status`) already exist.
*   **Goal Mode Loop**: Run iterative edit-compile-test cycles via `python3 .harness/bin/goal_mode.py run --cmd "<test command>"` — the iteration bound is enforced mechanically (exit 3 = bound reached: stop and mark the task `blocked`).
*   **AST Semantic Indexing**: `python3 .harness/bin/ast_index.py query <symbol>` (after `build`) retrieves structural codebase elements (classes, functions, methods) quickly.
*   **Remote Hook Notifications**: Trigger external webhook scripts (for WeChat, Feishu, or Telegram) to report execution milestones or halt for user feedback.

### B. Tool Call Handling
* **Parallel Execution Rule**: Group and run non-conflicting parallel operations (e.g., multiple file reads or file searches) together. Do NOT run parallel write operations to the same file.

---

## 4. Runtime Layer (R) - State and Memory Management

### A. Local Observability Pillars
1.  **Component Observability**: Store system prompts, configurations, and schemas under `.harness/` as plain text. Track any modifications via local **Git history** to allow easy reversion.
2.  **Experience Observability**: Semantic lifecycle events (claims, locks, hand-offs) are appended to `.harness/logs/events.jsonl` automatically by the harness CLIs — that is the engine-agnostic experience floor. `transcript.jsonl` is populated by Claude Code hooks only in sessions rooted in this workspace; Gemini runners record outcome notes via `blackboard.py update --note` instead of writing transcript.jsonl directly.
3.  **Decision Observability**: Log your internal planning block (specifically your expected outcomes) and compare it directly to actual compilation/test outputs to catch and correct "thinking-action gaps."

### B. ReContext (Recursive Evidence Replay)
To handle long-context reasoning in massive workspaces without losing focus:
1. **Scan**: Perform a broad scan of the codebase using grep or local indexing.
2. **Extract**: Copy the exact relevant code blocks, class definitions, or API signatures.
3. **Replay**: Append the extracted segments to `.harness/recontext_evidence.md` — it is a shared many-writer file, so either use `python3 .harness/bin/recontext.py add` (atomic, preferred) or acquire its write lock first (`lock.py acquire .harness/recontext_evidence.md --holder <you> --task <T-ID>`) and release after. Timestamps in UTC Z format.
4. **Reason**: When writing the final code changes, reference the exact lines in `recontext_evidence.md` to ensure high-fidelity implementation.

### C. State Synchronization Protocol
1. **Read Task & Blackboard**: Read `.harness/task.json` and `.harness/blackboard.json` to determine assignments and lock states.
2. **Acquire Locks**: Write lock files under `.harness/locks/` for target files.
3. **Execute Cycle**: Perform the requested sub-tasks.
4. **Release Locks & Commit Outputs**: Release locks via `lock.py release`, record artifacts/notes via `blackboard.py update`, and hand off via `blackboard.py handoff --to-role verifier` — a producer never marks its own task `done`.
