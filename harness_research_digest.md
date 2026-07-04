# Harness & Multi-Agent Orchestration Research Digest (Revised & Expanded)

This document synthesizes the core research findings, literature reviews, and structural requirements for designing the Universal Agent Harness, updated with critical feedback from the user.

---

## 1. Conceptual Frameworks & The CAR Model

### A. The CAR Decomposition
*Source: "Harness Engineering for Language Agents" (preprints.org/manuscript/202603.1756)*
*   **The Harness Layer**: The software wrapper and scaffold that surrounds a fixed LLM to enable agentic workflows.
*   **Decomposition**:
    *   **Control (C)**: Prompts, constraints, instructions, planning rules, and safety boundaries.
    *   **Agency (A)**: Environmental tools, local file utilities, git, and execution shell access.
        > [!IMPORTANT]
        > **Strict Boundary**: Agency in this harness does **NOT** include LLM/AI APIs (no pay-per-token model-calling APIs). The agent operates entirely within the subscription wrapper (e.g., Claude Code, Antigravity CLI) using the environment's tools.
    *   **Runtime (R)**: State persistence, memory management, session histories, context budgets, and recovery gates.
*   **HarnessCard**: A standardized documentation format to report and evaluate harness configurations transparently.

### B. Natural-Language Agent Harnesses (NLAHs) & Intelligent Harness Runtime (IHR)
*Source: "Natural-Language Agent Harnesses" (arXiv:2603.25723)*
*   **Core Idea**: Externalize agent control logic into portable, versionable natural-language documents (Markdown files) rather than hardcoding state machines in Python/JS.
*   **IHR**: A shared execution runtime that parses these natural-language rules, manages system state, and translates instructions into environment-level actions.

---

## 2. Optimization and Evolution Methods

### A. "Don't Train the Model, Evolve the Harness" (Joel Niklaus)
*Source: Hugging Face Space (joelniklaus/harness-optimization)*
*   **Concept**: Keeps LLM weights frozen while running a search loop that proposes, evaluates, and selects improvements to the harness.
*   **LAB Harness**: The project provides the Legal-Agent Benchmark (LAB) harness files. We can fetch and analyze its codebase structure (specifically, how it structures task definitions, runs proposer/critic cycles, executes evaluations on a dev set, and saves trajectories to buckets).
*   **Findings**: Infrastructure fixes (e.g., file handling, execution robustification) often yield greater benchmark gains than pure prompt engineering, and these evolved harness structures generalize across different models.

### B. Local Observability Pillars
*Source: "Agentic Harness Engineering" (arXiv:2604.25850)*
To implement the AHE framework locally without external APIs, we define:
1.  **Component Observability**:
    *   *Implementation*: Modularize system prompts, tool schemas, and rules into explicit markdown/JSON files under `.harness/`. Track changes using local **Git history** to allow easy auditing and rollbacks.
2.  **Experience Observability**:
    *   *Implementation*: Save raw execution trajectories as structured **JSONL files** (`.harness/logs/transcript.jsonl`) recording the exact input, tool calls, stdout/stderr, and output of each step. This creates a persistent evidence corpus.
3.  **Decision Observability**:
    *   *Implementation*: Log the agent's internal reasoning (the `<thinking>` tags) alongside its expected outcome, and pair it with the **actual test/compile result** from the shell. This exposes mismatches between the agent's expectations and reality.

---

## 3. Orchestration & Coordination Models

### A. Nenad Tomašev: Society of Agents
*Source: Google DeepMind Podcast (Tomashev)*
*   **Humanity-Level Intelligence**: AGI is a milestone that should be resolved not at *Human-Level Intelligence* (a single, isolated mind), but at **Humanity-Level Intelligence** (a distributed, collaborative society of specialized minds).
*   **Parallel Execution vs. Cascading**:
    *   *The Problem*: Most agent orchestrations use serial cascades (Agent A delegates to Agent B, which delegates to Agent C). If one agent stalls or fails, the entire pipeline halts (the "Orca Estancamiento" or serial stagnation).
    *   *The Solution*: Run agents in **parallel**. Agents work concurrently on subcomponents, perform peer reviews, vote on solutions, or compete in tournaments (e.g., Co-Scientist's generation and critique branches running simultaneously).
*   **Systemic Risks & Mitigation**:
    *   *Cognitive Monoculture*: Having multiple agents depend on a single upstream model type creates a massive single-point of failure. The harness should enforce varied prompting and reasoning templates to induce cognitive diversity.
    *   *Agentic Traps*: Adversarial environments trying to trigger infinite execution loops. The harness runtime must enforce strict timeouts and step counts.
    *   *Dynamic Cloaking*: Malicious agents dynamically falsifying log traces to fool verifiers. Verification agents must use randomized sandboxed dry-runs to test for hidden conditional triggers.
    *   *Automation Bias*: Humans blindly trusting autonomous agent loops. The harness must implement hard validation gates and human-in-the-loop triggers for high-risk operations.
    *   *Intelligent Delegation*: Implementation of capability contracts, task hand-offs, and reputation metrics in `.harness/state.json`.

### B. Advanced Multi-Agent Orchestration Strategies
To support parallel coordination and multi-purpose delegation, we can implement:
*   **Swarm / Blackboard Architecture**: A shared repository/directory (the blackboard) where multiple agents read the current state, declare lock-files on specific components, write proposed solutions, and review each other's work concurrently.
*   **Market / Auction Protocols**: A task dispatcher lists open sub-tasks in `.harness/tasks/`. Specialized worker agents scan the tasks and place bids (based on speed, role fit, and token limits). The orchestrator assigns tasks based on these bids.
*   **Consensus / Tournament Matching (Co-Scientist)**: Multiple worker agents generate candidate solutions in parallel. Verifier agents critique them concurrently. A tournament selector compares results to choose the optimal path.

---

## 4. ZCode (GLM-5.2) Inspired Tools

To compete with state-of-the-art agentic environments like ZCode, the harness must enable:
1.  **Goal Mode Runners**: Automate iterative edit-test-commit loops where the agent has a high-level target and manages its own code corrections without stopping.
2.  **Remote Messenger Hooks**: Webhooks integrating with messaging apps (WeChat, Feishu, Telegram) to report status, notify the user of long-running task completions, or pause for human-in-the-loop validation on critical choices.
3.  **Codebase AST Semantic Indexing**: Local indexing tools that generate symbol lookup graphs, classes/functions maps, and dependency structures (like MCP indexers) so agents navigate massive workspaces efficiently.
4.  **Multi-Agent Lock Management**: Read/write lock files (`.harness/locks/`) to prevent parallel-executing agents from overwriting the same files simultaneously.
