# ZCode (zcode.z.ai) Features and Tool Requirements

This document outlines the agentic IDE features, multi-agent coordination tools, and integrations supported by **ZCode**, developed as the official harness for the **GLM-5.2** model by Z.ai.

---

## 1. Overview
ZCode is an agentic development environment designed for long-horizon programming tasks. It serves as a benchmark for local coding harnesses by moving beyond simple chat autocompletions to multi-agent, background-executing workflows.

---

## 2. Core Agentic Toolsets & Requirements

### A. Goal Mode Loop
*   **Self-Correcting Execution**: Allows agents to run iterative edit-test-commit loops locally.
*   **Background Running**: The agent manages background processes (compilers, linters, and unit test suites) and attempts to self-debug errors until it achieves a green test suite.

### B. Remote Bot Control (Messenger Hooks)
*   **Webhooks**: Built-in triggers connecting the local agent running in the IDE to external messaging applications (WeChat, Feishu, Telegram).
*   **Interactions**:
    *   *Status Reporting*: Notifies the user of task completions, execution bottlenecks, or test failures.
    *   *Human-in-the-Loop Gate*: Pauses agent execution to request validation or input on ambiguous code design decisions.

### C. Multi-Agent Collaboration & Permissions
*   **Shared Workspace**: Coordinates multiple concurrent agents working on the same directory tree.
*   **Locks**: Utilizes read/write lock files in the workspace (like `.harness/locks/`) to prevent race conditions or overwrite conflicts between parallel agents.
*   **Blackboard**: Uses shared database files (`blackboard.json`) to synchronize task queues.

### D. Codebase AST Indexing
*   **Semantic Search**: Exposes tools that index code symbols (classes, functions, imports) to build local relationship graphs (compatible with Model Context Protocol - MCP).
*   **Pruned Retrieval**: Prevents token-bloat by letting agents fetch code structures semantically rather than reading raw file trees.
