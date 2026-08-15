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
*   **Issued Names and Plazas**: `python3 .harness/bin/roster.py [--root R] {charter|plazas|issue|roster|eligible}` records agent names against seats published *before* the work exists: a colegiado declares what it is paid for, and `issue` refuses when no declared seat is free. It is BOOKKEEPING, not a gate, and its integrity claim runs against accident only — duplicate names, over-filled plazas, concurrent lost writes, and typos that would mint a parallel seat (`judge` vs `judge ` vs `Judge`). It does NOT bound an adversary: `--by` is self-asserted, so every authorization check inside it is a string comparison the attacker controls both sides of. PR-023 clause 4 governs and is unamended — an appeal seeking to narrow it was refused on 2026-08-15 (`.harness/appeal-PR-023.md`). `eligible` is a REPORT, never a gate: recusal is not computed from colegiado membership until an amending record lands (PR-017). Regression coverage in `.harness/tests/test_roster.py`, whose race tests carry their measured detection rate against a guard-neutered build.
*   **The Identity Gate**: `python3 .harness/bin/warrant.py [--root R] {init|draft|verify|apply|reconcile|audit --expect SHA256:...|anchor}` supplies the prerequisite PR-023 names, rather than arguing with it. A name, a plaza and a charter exist ONLY inside a warrant signed by the operator's key; `draft` emits an UNSIGNED payload and prints the command the operator runs, and a test asserts no code path in the module can sign one. Once `.harness/trust/root.pub` is enrolled, `roster.py` refuses every unwarranted mutation; before that it behaves exactly as before, so there is no flag day. **Minting is closed CONDITIONALLY** — conditional on `reconcile` coming back clean and on the anchor being checked against a fingerprint held outside the machine. Do not shorten that to "minting is closed": two blind panels refuted exactly that sentence, the second by naming three paths that minted names while `audit` printed clean. **Impersonation is NOT closed**, and a test proves the limit by stealing an agent key and forging with it: every agent runs as the same OS user on one filesystem, so no agent can hold a secret from another (D-17). **`audit` without `--expect` is a self-consistency check, not an audit**: `trust/` is writable by every agent and untracked by git, so every check inside the module is consistent with whatever an attacker wrote there. Pass the fingerprint you hold out of band or the report marks itself UNVERIFIED. `reconcile` requires every roll row to trace to a verified warrant, which is the detector for the paths no in-process check can stop. Two blind panels have refuted this module's compliance claim; read `.harness/coordinator-decisions-ruling-round-2.md` D-16..D-21 before relying on it.
*   **Signed Acts and Fork Detection**: `python3 .harness/bin/attest.py [--root R] {sign|verify|forks|chain|contest}` chains every act to that name's previous act, so two acts sharing one predecessor is a FORK. A fork is evidence of DIVERGENCE and nothing stronger: one party signing twice from one predecessor is indistinguishable from two, and a forger who uses the shipped `sign` verb appends at the tip and leaves no fork at all. Both limits are measured and pinned by tests. A fork freezes nothing (AF-5) and attaches no consequence (PR-022 clause 4); `contest` files a claim as a signed act on the ACCUSER's own chain, so a false accusation is permanently attributable to whoever filed it (AF-3). Design rule enforced throughout: credit follows the signature, so forging as A credits A and forgery can only destroy, never enrich.
*   **Currency Health (A.8)**: `python3 .harness/bin/currency.py [--json]` computes the indicator PR-023 clause 5 conjoins the identity gate with, and which was defined in addendum AB7 but never built — so the second arm of a tier-1 conjunction had no instrument. Two measures: A.8.1 the share of citation edges that are TYPED (`follows`/`reinterprets` in `relations[]`) versus bare `cites` name-drops, with its drift across the publication sequence; A.8.2 top-1/top-3 authorship share alongside the share held by identities with no verified work. It emits **NO pass/fail verdict** and prints NO THRESHOLD RATIFIED instead: clause 5 defines no failing point, and a tool that invents one has decided the conjunction. Read-only, enforced by an AST test rather than a substring scan (see defect GUARD-MENTION-C).
*   **Event-Log Counts**: `python3 .harness/bin/event_stats.py [--json]` reports every count TWICE, raw and distinct, and never one alone — the raw log replays at 3.93x overall and up to 47x on some event types, so a bare count of `precedent_published` overstates publication by more than an order of magnitude (defect TELEMETRY-PROVENANCE-A). The dedup predicate (two events are identical when they agree on every field except `ts`) and the source line count print with every run, including `--json`. It deliberately computes no catch-rate: that figure needs a ratified falsifier first.
*   **Usage Telemetry**: `python3 .harness/bin/usage_report.py [--json]` reduces the runner's transcripts to per-run, per-role and per-model consumption; `token_share.py` answers only the frontier-share question. The harness writes no usage counters of its own — treat both as harvesters, and read the cache split before treating raw tokens as cost. Frozen audit: `.harness/logs/audit_telemetry_2026-08-14.html`.

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
