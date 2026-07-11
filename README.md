# Universal Agent Harness Workspace

This workspace contains the foundational specifications, research digests, reference implementations, and research papers to build the **Universal Agent Harness**, coordinated by the strongest Claude model available in the main session (tested with Fable 5; runs identically on Opus or Sonnet).

---

## Workspace Structure

### 1. Harness Specifications (NLAHs)
*   **[claude.md](claude.md)**: Natural-Language Agent Harness for Claude models. Includes Section 5 detailing guidelines for the Coordinator to coordinate the creation, validation, and evolution of the harness.
*   **[gemini.md](gemini.md)**: Natural-Language Agent Harness for Gemini models, utilizing ReContext (Evidence Replay) and long-context optimizations.

### 2. Research & Literature
*   **[harness_research_digest.md](harness_research_digest.md)**: Synthesized findings from core papers on CAR framework, NLAHs, parallel orchestration, Humanity-Level intelligence, local observability, and ZCode tools.
*   **[papers/](papers/)**: Downloaded PDF copies of core research papers:
    *   `code_as_agent_harness.pdf` (arXiv:2605.18747)
    *   `recontext.pdf` (arXiv:2607.02509)
    *   `natural_language_agent_harnesses.pdf` (arXiv:2603.25723)
    *   `trinity.pdf` (arXiv:2512.04695)
    *   `conductor.pdf` (arXiv:2512.04388)
    *   `agentic_harness_engineering.pdf` (arXiv:2604.25850)
    *   `sakana_fugu_tech_report.pdf` (arXiv:2606.21228)
    *   `coffee_bench.pdf` (arXiv:2606.16613)
    *   `distributional_agi_safety.pdf` (arXiv:2512.16856)
    *   `intelligent_ai_delegation.pdf` (arXiv:2602.11865)
    *   `virtual_agent_economies.pdf` (arXiv:2509.10147)
*   `fetched_docs/` (operator-local, not tracked): synthesized web content and podcast summaries that ground the research-librarian agent.

### 3. Reference Repositories
We have fetched and cloned the reference source code repositories for key frameworks:
*   **[harness-optimization-reference/](harness-optimization-reference/)**: Joel Niklaus's *"Don't Train the Model, Evolve the Harness"* framework and the Legal-Agent Benchmark (LAB) codebase.
*   **[coffee-bench-reference/](coffee-bench-reference/)**: Sakana AI's CoffeeBench B2B economic simulation environment.
*   **[agentic-harness-engineering-reference/](agentic-harness-engineering-reference/)**: The Agentic Harness Engineering (AHE) framework, including `evolve.py` and the paper PDF.

### 4. Runtime Substrate & Orchestration (Generation 0 — bootstrapped 2026-07-03)
*   **[AGENTS.md](AGENTS.md)**: The capability directory — every resident agent, skill, hook, and loop that ships with the harness, with intent-to-resource routing and the extension patterns proven in sibling deployments. Engines should read this before deciding how to route a task.
*   **[ORCHESTRATION.md](ORCHESTRATION.md)**: The delegation topology contract — dependency-DAG delegation (cascade where a real artifact dependency exists, parallel everywhere else), claims with leases, TTL write locks, producer ≠ approver, engine routing, and the seeded task DAG.
*   **[.harness/](.harness/)**: The Runtime layer (R): guarded `blackboard.json`, `state.json` (limits, capability contracts, human gates, evolution queue), `tasks/` detail files, `locks/`, `logs/` (JSONL observability), and the deterministic control plane in `bin/` (`blackboard.py`, `lock.py`, hook scripts). See `.harness/README.md`.
*   **[.claude/](.claude/)**: Claude Code integration — the agent bench (orchestration-planner, substrate-worker, harness-verifier, evolution-analyst, research-librarian), observability + lock-enforcement hooks in `settings.json`, and the `harness-status` skill.
*   **[.gemini/](.gemini/)** and **[.agents/workflows/](.agents/workflows/)**: The deeper Gemini adapter — bounded native role agents, namespaced `/harness:*` commands with non-preview fallbacks, shared context loading, and Antigravity workflows that preserve independent producer/verifier contexts.
*   **[GEMINI_ADAPTER.md](GEMINI_ADAPTER.md)**: The precedence-safe scope note that enables Gemini/Antigravity-native coordination without mutating the human-gated `gemini.md`, and keeps external webhooks/telemetry opt-in.
*   **[GEMINI_HEADLESS.md](GEMINI_HEADLESS.md)**: The unattended Gemini CLI bridge. It executes self-contained assignments with `stream-json`, preserves exit codes and raw JSONL evidence, uses distinct harness identities, and never bypasses approvals or silently mutates the board.
*   **[GEMINI_DEEPMIND_INTEGRATION_RESEARCH.md](GEMINI_DEEPMIND_INTEGRATION_RESEARCH.md)**: Current primary-source architecture research for a deeper Gemini implementation across interactive CLI, native subagents, shared skills, headless JSONL workers, Antigravity workflows, extensions, policies, and future Managed Agents.
*   **[.codex/](.codex/)**: Native Codex project integration — bounded multi-agent configuration plus planner, worker, verifier, evolution, and research profiles that speak the same blackboard lifecycle.
*   **[.agents/skills/](.agents/skills/)**: Repo-scoped Codex workflows for board status, direct Codex claims, and full-frontier orchestration. The same workflow format is also a future interoperability surface for Gemini CLI and Antigravity.
*   **[.codex-plugin/](.codex-plugin/)** and **[skills/](skills/)**: Installable Codex plugin manifest and packaged copies of the reusable workflows, guarded by a synchronization test against `.agents/skills/`.
*   **[DATA_LOSS_SAFETY.md](DATA_LOSS_SAFETY.md)**: Codex-specific defense in depth against project deletion and discarded edits: native command rules, a project/plugin pre-tool guard, and reversible audited quarantine instead of permanent deletion.

---

## Instructions for the Coordinator

The Coordinator should begin by reading `README.md` and `harness_research_digest.md` to acquire the necessary context. 
It should then parse Section 5 of `claude.md` to run the harness generation and evolutionary optimization loop.

**Generation 0 exists.** Before planning any new work: run `python3 .harness/bin/blackboard.py status`, read `ORCHESTRATION.md`, and dispatch the claimable frontier to the bench instead of working serially. Mutations to `claude.md`/`gemini.md` go exclusively through the evolution queue in `.harness/state.json` (human-gated, per §5A).
