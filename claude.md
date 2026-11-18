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
*   **Tests, Fast**: `python3 .harness/bin/fast_tests.py [files...] [--changed [--base REF]]` runs the suite as balanced pytest batches, at low priority and on at most half the cores machine-wide (`HARNESS_TEST_SLOTS` overrides). `--changed` picks the tests that import or name what the working tree changed. **Wave rule (measured 2026-11-17: a wave fell from 28-35 min to 8):** an agent runs only the tests its change touches and never the full suite; the coordinator runs the full suite once per wave, before committing. Four agents running the full suite at once saturate the machine and each run takes 2 to 4 min instead of 1. `--changed` does not yet follow indirect imports, so a change to a shared module such as `harness_common.py` needs its dependents named by hand.
*   **AST Semantic Indexing**: `python3 .harness/bin/ast_index.py query <symbol>` (after `build`) finds function, class, and method definitions without reading entire files.
*   **Remote Hook Notifications**: Trigger script webhooks (integrating with WeChat, Feishu, or Telegram) to report long-running task completions or request human validation.
*   **Issued Names and Plazas**: `python3 .harness/bin/roster.py [--root R] {charter|plazas|issue|roster|eligible}` records agent names against seats published *before* the work exists: a colegiado declares what it is paid for, and `issue` refuses when no declared seat is free. It is BOOKKEEPING, not a gate, and its integrity claim runs against accident only — duplicate names, over-filled plazas, concurrent lost writes, and typos that would mint a parallel seat (`judge` vs `judge ` vs `Judge`). It does NOT bound an adversary: `--by` is self-asserted, so every authorization check inside it is a string comparison the attacker controls both sides of. PR-023 clause 4 governs and is unamended — an appeal seeking to narrow it was refused on 2026-08-15 (`.harness/appeal-PR-023.md`). `eligible` is a REPORT, never a gate: recusal is not computed from colegiado membership until an amending record lands (PR-017). Regression coverage in `.harness/tests/test_roster.py`, whose race tests carry their measured detection rate against a guard-neutered build.
*   **The Identity Gate**: `python3 .harness/bin/warrant.py [--root R] {init|draft|verify|apply|reconcile|audit --expect SHA256:...|anchor}` supplies the prerequisite PR-023 names, rather than arguing with it. A name, a plaza and a charter exist ONLY inside a warrant signed by the operator's key; `draft` emits an UNSIGNED payload and prints the command the operator runs, and a test asserts no code path in the module can sign one. Once `.harness/trust/root.pub` is enrolled, `roster.py` refuses every unwarranted mutation; before that it behaves exactly as before, so there is no flag day. **Minting is closed CONDITIONALLY** — conditional on `reconcile` coming back clean and on the anchor being checked against a fingerprint held outside the machine. Do not shorten that to "minting is closed": two blind panels refuted exactly that sentence, the second by naming three paths that minted names while `audit` printed clean. **Impersonation is NOT closed**, and a test proves the limit by stealing an agent key and forging with it: every agent runs as the same OS user on one filesystem, so no agent can hold a secret from another (D-17). **`audit` without `--expect` is a self-consistency check, not an audit**: `trust/` is writable by every agent — its public material (`root.pub`, `root.fingerprint`, and the constitutional payload+sig) IS git-tracked, private keys are never tracked (T-428 correction: the prior text here claimed `trust/` was untracked, which two blind panels' worth of scrutiny should have caught and did not — `git ls-files .harness/trust` shows otherwise). Being tracked does not make it protected: nothing stops an agent from overwriting the working-tree copy before the next commit, and `audit` reads whatever is on disk right now, so every check inside the module is still consistent with whatever an attacker wrote there. Pass the fingerprint you hold out of band or the report marks itself UNVERIFIED, and exits 5 (`EXIT_AUDIT_UNVERIFIED`, T-450), so an unverified audit can no longer pass for a verified one in a script. The out-of-band copy is a git tag the operator signs; the exact command is in `audit --help` and `.harness/OPERATOR-ENROLMENT.md`, and no agent runs it. `reconcile` requires every roll row to trace to a verified warrant, which is the detector for the paths no in-process check can stop. Two blind panels have refuted this module's compliance claim; read `.harness/coordinator-decisions-ruling-round-2.md` D-16..D-21 before relying on it.
*   **Signed Acts and Fork Detection**: `python3 .harness/bin/attest.py [--root R] {sign|verify|forks|chain|contest|retract}` chains every act to that name's previous act, so two acts sharing one predecessor is a FORK. A fork is evidence of DIVERGENCE and nothing stronger: one party signing twice from one predecessor is indistinguishable from two, and a forger who uses the shipped `sign` verb appends at the tip and leaves no fork at all. Both limits are measured and pinned by tests. A fork freezes nothing (AF-5) and attaches no consequence (PR-022 clause 4); `contest` files a claim as a signed act on the ACCUSER's own chain, so a false accusation is permanently attributable to whoever filed it (AF-3). Design rule enforced throughout: credit follows the signature, so forging as A credits A and forgery can only destroy, never enrich. `retract --name --key --seq --reason` (T-448) files an unprivileged retraction on the name's own chain, citing the target act by digest: the retracted act stays on disk and every tool that reports it reports the retraction with it. One retraction per target, and a retraction cannot itself be retracted.
*   **Contracts and Suits (decision 3, built in part)**: `attest.py commit` files a self-signed, unprivileged act fixing one operational parameter from PR-060 clause 1's list (task, order, budget, deadline, engine, iteration bound) to a value, before the work begins. `attest.py file-claim` compares that committed value with the observed one, which it reads itself from the one harness record that observes the parameter (`PARAMETER_READERS`: deadline, iteration bound, budget, engine, each tied to the commit act's own task; T-472). The claimant supplies no value, and a parameter with no reader (task, order) is refused as unreplayable. When the values agree it refuses and writes nothing anywhere; when they disagree it files one `contest` on the CLAIMANT's own chain, so it inherits every privileged guard `contest` has. The raw `contest` verb still writes without that check (the BYPASS residual in `design-T-436-contracts.md`, pinned open by a test). `answer` and `appeal` are unprivileged acts for the respondent and the losing party. In the case register, `precedent.py case open` accepts an optional suit block (claimant, respondent, contract, damages claimed), `case notice` publishes the respondent's board task, `case claim`, `case answer` and `case appeal` link each party's own signed act into the suit (T-474), `case show` reports the suit's state in words, and `case verdict` disposes a suit only through a signed `verdict` act by a name issued in the `judge` colegiado. The judge seat exists only as the UNSIGNED draft `.harness/warrants/W-003.json` (placeholder name and key, see `.harness/judge-seat-draft-T468.md`) until the operator signs a real one. The three numbers of decision 3 (objection window, pursue-or-lapse window, damages cap) are NOT ratified: no tool computes a deadline, a lapse or an amount, and each place one would appear says so.
*   **Dispatch Tokens (identity, option 5)**: `python3 .harness/bin/dispatch_token.py [--root R] {draft|verify}` carries the operator's authorization of one agent for one task and role: `(agent_name, task_id, role, issued_at, expiry, nonce)`. Grain is one signature per epic (operator ruling of 2026-10-21): `draft --epic E --dispatch AGENT:TASK:ROLE[:TTL]` writes an UNSIGNED set and prints the operator's command; `verify` accepts only a set that verifies against `trust/root.pub` and the anchor, never against a key the file names. `--required` lives inside the signed set, so no unsigned file can switch the requirement on or off; once such a set is signed, `blackboard.py claim --token-file` and `lock.py acquire --token-file` refuse that epic's work without a verifying token, and `claim` spends the nonce (single use). An epic with no signed set behaves exactly as before. A token proves the operator authorized that agent for that task and role; it does not prove each act under it is the act the operator meant, and impersonation inside a token's window stays open (D-17). The file is not `token.py` because that name shadows the standard library.
*   **Revocation by Operator Order (option 6a)**: `python3 .harness/bin/revoke.py [--root R] {draft|apply|verify|list|check}` mirrors `warrant.py`: `draft` writes an UNSIGNED `.harness/revocations/REV-NNN.json` and prints the operator's command; a revocation counts only if it verifies against the enrolled root. From its time on, `dispatch_token.py verify` refuses every token for that name, expired or not, and `roster.py` shows the name as revoked (a report; nothing else is gated). No agent can revoke another.
*   **Epic-Close Checks (option 6b)**: `python3 .harness/bin/close_checks.py [--root R] [--json] {epic-close|imp6}` prints one read-only report of `attest.py forks`, `warrant.py reconcile` and IMP-6 (an act with no matching `act_signed` event, counted with `event_stats.py`'s dedup predicate). The coordinator runs it at every epic close. It always exits 0 and attaches no consequence (IMP-7, PR-022 clause 4): it reports, a ruling decides.
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
