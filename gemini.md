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
* When executing tasks in parallel, read `.harness/blackboard.json` to identify active tasks.
* Before writing to any source file, check `.harness/locks/` to ensure no other agent has acquired a lock on the target file. If a lock exists, skip the file or wait to prevent overwrite conflicts.

---

## 3. Agency Layer (A) - Tool and Capability Protocol

Gemini agents execute tools in a file-based workspace environment.

> [!WARNING]
> **Strict Tool Constraint**: Under this harness, you do **NOT** have access to LLM/AI APIs. Do not attempt to make API requests to call other models. All tools are strictly local environment utilities (compilers, git, test runners, AST indexers).

### A. Core Local Tools
*   **Goal Mode Loop**: Run iterative edit-compile-test cycles. Fix syntax and logical errors autonomously until all tests pass.
*   **AST Semantic Indexing**: Query local indices to retrieve structural codebase elements (classes, types, imports) quickly.
*   **Remote Hook Notifications**: Trigger external webhook scripts (for WeChat, Feishu, or Telegram) to report execution milestones or halt for user feedback.

### B. Tool Call Handling
* **Parallel Execution Rule**: Group and run non-conflicting parallel operations (e.g., multiple file reads or file searches) together. Do NOT run parallel write operations to the same file.

---

## 4. Runtime Layer (R) - State and Memory Management

### A. Local Observability Pillars
1.  **Component Observability**: Store system prompts, configurations, and schemas under `.harness/` as plain text. Track any modifications via local **Git history** to allow easy reversion.
2.  **Experience Observability**: Write execution logs, inputs, outputs, and tool outcomes directly to `.harness/logs/transcript.jsonl` in structured JSONL format.
3.  **Decision Observability**: Log your internal planning block (specifically your expected outcomes) and compare it directly to actual compilation/test outputs to catch and correct "thinking-action gaps."

### B. ReContext (Recursive Evidence Replay)
To handle long-context reasoning in massive workspaces without losing focus:
1. **Scan**: Perform a broad scan of the codebase using grep or local indexing.
2. **Extract**: Copy the exact relevant code blocks, class definitions, or API signatures.
3. **Replay**: Write these extracted segments into `.harness/recontext_evidence.md`.
4. **Reason**: When writing the final code changes, reference the exact lines in `recontext_evidence.md` to ensure high-fidelity implementation.

### C. State Synchronization Protocol
1. **Read Task & Blackboard**: Read `.harness/task.json` and `.harness/blackboard.json` to determine assignments and lock states.
2. **Acquire Locks**: Write lock files under `.harness/locks/` for target files.
3. **Execute Cycle**: Perform the requested sub-tasks.
4. **Release Locks & Commit Outputs**: Remove lock files, update `.harness/blackboard.json` and `.harness/state.json`, and signal completion.
