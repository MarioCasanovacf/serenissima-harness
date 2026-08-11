# Precedent Layer Grounding Report — Research Corpus Survey

Author: research-librarian (read-only corpus grounding). Preserved verbatim by the
coordinator as epic input. Method note: primary sources read page-by-page;
`papers/harness_engineering_preprints.pdf` is corrupted at file level (only its abstract in
`fetched_docs/` was usable); `trinity.pdf`/`conductor.pdf` surveyed but off-topic for
precedent mechanics (see section 5f).

---

## 1. Session handoff, memory conventions, context resets — trajectory over time

ESTABLISHED — the industry vocabulary the brief describes (memory files, handoff docs) is real and documented in the corpus, and is trending toward more formal, typed structure, not toward raw volume:

- `papers/natural_language_agent_harnesses.pdf:9` (section 6 Related Work): "Files such as prompts, AGENTS.md, CLAUDE.md, and AgentSkills-related skill bundles show that operational knowledge can be packaged as reusable text and attached to agent runs... NLAHs operate at the run-level harness-policy layer, specifying roles, call boundaries, state carriers, evidence gates, recovery rules, and stopping criteria." This is a documented progression: ad hoc prompt text, then reusable memory-file conventions (AGENTS.md/CLAUDE.md), then formal policy documents with explicit evidence gates and stopping criteria.
- `papers/natural_language_agent_harnesses.pdf:4` (section 3.2, "Make state and evidence explicit"): "Long-horizon agents fail when useful intermediate information is lost or when a final answer is produced without auditable evidence. A readable NLAH should therefore specify where state is stored, which artifacts must be reopened by later agents, what evidence supports a claim, and which files or logs close the run."
- `agentic-harness-engineering-reference/agents/code_agent_simple/LongTermMEMORY.md:1-3` (real reference-repo artifact): "Persistent knowledge that should be retained across sessions. Store important facts about the user, project conventions, architectural decisions, and recurring patterns here." Paired with `ShortTermMEMORY.md:1-3`: "Temporary context relevant to the current task or session... This memory may be cleared between sessions." A concrete, dated (2026) instance of the two-tier memory convention the brief's Part I describes — explicitly typed (persistent/architectural vs ephemeral/task-scoped), more structured than an undifferentiated handoff memo.

IMPORTANT NUANCE (ESTABLISHED, cuts against a naive "richer = bigger" reading of Part VI):

- `papers/natural_language_agent_harnesses.pdf:6` (Table 2): externalizing harness policy into an NLAH SHRINKS the static artifact even as it becomes more formally structured — Live-SWE: 60.10k tokens / 68 files (code) to 2.90k tokens / 3 files (NLAH); MHTBA: 10.50k/3 to 0.80k/1; SeeAct: 47.50k/5 to 1.40k/1. The paper's framing (p.6): "NLAHs expose the reusable harness policy in fewer static materials." So "getting richer/more constitution-like" does not mean "getting longer" — it means gaining structural fields (roles, evidence gates, stopping criteria) while raw token footprint can fall. This matters for Part VI's falsification metric, which as worded ("thinner vs richer") risks conflating file size with institutional formality. The corpus suggests these can move in opposite directions simultaneously.

ESTABLISHED — a documented failure mode directly relevant to the precedent layer's citation/handoff plumbing:

- `papers/natural_language_agent_harnesses.pdf:8` (section 5.2): "The main mechanism weakness is handoff. NLAH Orchestration Reliability is lower than Prompt on both Live-SWE and MHTBA, and Information Handoff Recall drops from the direct-context Prompt setting to 0.322 and 0.553 under parent-child execution. This weakness is consistent with the cost profile in RQ1: the prototype runtime already materializes harness mechanisms, but loses information across boundaries that ordinary prompting does not create." Formalizing a handoff boundary INTRODUCED information loss a flat single-context prompt did not have. See section 5 below for the fuller discussion.

ESTABLISHED — second trajectory data point (Sakana Fugu; page numbers approximate, read from rendered pages):

- `papers/sakana_fugu_tech_report.pdf` section 3.2 ("Fugu-Ultra"): explicit intra-workflow isolation / inter-workflow persistent shared memory split — agents within one workflow are deliberately isolated from each other's full trajectories to prevent "orchestration collapse", while memory IS shared across workflows. Versus the stateless-per-query designs in `trinity.pdf` / `conductor.pdf`, a genuine trend toward more formalized, typed memory-sharing rules.

GAP: `harness_engineering_preprints.pdf` corrupted and unreadable; only its abstract available (CAR decomposition, HarnessCard proposal) — no explicit claim about direction of change over time.

## 2. Precedent-like, constitutional, or self-amending mechanisms already in the corpus

ESTABLISHED — a real, running "ratio decidendi at write time" requirement:

- `agentic-harness-engineering-reference/agents/evolve_agent/evolve_prompt.md:19-25` (Evidence-Driven principle): "Every change must be traceable to specific failure evidence. Do not make changes based on intuition, speculation, or 'best practices' alone. Before making any change, you must have: 1. Failure evidence... 2. Root cause... 3. Targeted fix... 4. Predicted impact." This is exactly the "author declares the ratio at write time" option the brief's Part II research item 2 poses — already implemented, not theoretical.

ESTABLISHED — a literal citation-index / decision-registry pair:

- `agentic-harness-engineering-reference/agents/evolve_agent/evolve_prompt.md:77` names `evolution_history.md` as "Cumulative history of all iterations (READ)"; lines 195-218 give the schema for `change_manifest.json`, written every iteration, with fields `id`, `type: "new|improvement|rollback"`, `description`, `failure_pattern`, `predicted_fixes`, `risk_tasks`, `constraint_level`, `why_this_component`. A working precedent-record schema: `id` is a stable citation ID; `description` + `why_this_component` is the ratio; `predicted_fixes`/`risk_tasks` is a scope-condition declaration (nearest thing to "distinguishing" conditions); `type: rollback` is explicit overruling.

ESTABLISHED — an explicit overruling protocol with a reasoning requirement:

- `agentic-harness-engineering-reference/agents/evolve_agent/evolve_prompt.md:103-104, 172-175`: "If the same failure class persists across 2+ iterations despite fixes at one component level, that level may be the wrong choice. Rollback the ineffective change and re-approach the same failure pattern from a different component level." And: "KEEP — working, leave as-is; IMPROVE — directionally correct, refine; ROLLBACK + PIVOT — not working at this component level." The KEEP/IMPROVE/ROLLBACK triad is structurally binding-continue / persuasive-refine / overrule-with-reasoning.

ESTABLISHED — an adjudication mechanism for conflicting parallel lineages:

- `agentic-harness-engineering-reference/agents/evolve_agent/evolve_prompt.md:147-156`: when parallel agents produce divergent results: "Learn from both: Even the losing variant may have solved tasks the winner did not... Combine insights... Avoid repeating failures." A primitive working answer to Part II item 6 (Adjudication).

ESTABLISHED — paper-level description of the same loop:

- `papers/agentic_harness_engineering.pdf:5` (section 3.3, Algorithm 1): "Attribution runs before distillation, so its verdict lands inside the evidence corpus and binds each prior manifest entry as a contract rather than a rationale."
- `papers/agentic_harness_engineering.pdf:5`: "every edit becomes a falsifiable, file-level contract... the next round's verdict either confirms or reverts it."
- `papers/code_as_agent_harness.pdf:33` (section 3.5.2, "The Evolution Agent"): five-stage loop — observe trajectories, diagnose failure modes, propose candidate revisions, evaluate on held-out tasks/replayed traces with deterministic sensors and regression tests, promote only non-regressing improvements.
- `papers/code_as_agent_harness.pdf:33` (section 3.5.3, "Governed Harness Mutation"): "AHE should not be confused with unconstrained self-modification... Changes that alter permission boundaries, network access, credential handling, deployment behavior, or human-review requirements should require HITL approval before activation." A corpus-stated entrenchment clause: some rule changes cannot be self-authorized regardless of evidence — structurally analogous to a constitutional carve-out (that mapping is ANALOGY, not the paper's framing).

ESTABLISHED — second independent instance, with an explicit "frontier lineage" behaving like binding precedent:

- `harness-optimization-reference/legal_agent_bench/HARNESSES.md:3-5`: "Each candidate copies the current frontier file and adds one mechanism, so wins compound. Promotion is by the blended gate." Every future candidate must build on the current frontier — the promoted lineage functions as binding precedent that successors extend rather than relitigate.
- `harness-optimization-reference/legal_agent_bench/meta_harness.py:201-211, 349-350` (`_history_digest()`): a run-history digest appended to every subsequent iteration's context — a working citation-index mechanism, in code.

LIMITATION flagged by the source itself (feeds Part II failure-modes item):

- `papers/agentic_harness_engineering.pdf:10` (Limitations): "AHE bounds edits to a workspace, attributes every change in a versioned manifest, and rolls back ineffective edits at file granularity, but it does not provide a complete guardrail stack... a controlled research prototype rather than a fully mature autonomous self-improvement system."
- `papers/agentic_harness_engineering.pdf:9` (section 4.4.2, "Regression blindness"): "cross-iteration regression-precision of 11.8% and regression-recall of 11.1% sit only about 2x above their random baselines of 5.6% and 5.4%, so most upcoming regressions go unforeseen. The agent can justify why an edit should help, but it cannot reliably name the tasks the same edit is about to break." Quantified: an agent's self-declared ratio (benefit attribution — precision 33.7%/recall 51.4%, ~5x random) is far more reliable than its self-predicted scope of harm (~2x random). A precedent layer that lets agents self-declare both the ratio and the blast radius should treat the two claims very differently in confidence: self-attribution of benefit is roughly trustworthy, self-attribution of risk is not.

## 3. Virtual agent economies — mechanism design, institutional primitives markets presuppose

ESTABLISHED, direct primary sources for Part III's research mandate:

Contracts / task allocation:
- `papers/intelligent_ai_delegation.pdf:9` (section 4.1, "contract-first decomposition"): "task delegation is contingent upon the outcome having precise verification. If a sub-task's output is too subjective, costly, or complex to verify... the system should recursively decompose it further."
- `papers/intelligent_ai_delegation.pdf:10` (section 4.2): "Successful matching should be formalized into a smart contract... The contract must pair performance requirements with specific formal verification mechanisms... and automated penalties actioned for contract breaches... these contracts must be bidirectional: they should protect the delegatee as rigorously as the delegator."
- `papers/intelligent_ai_delegation.pdf:14`: decentralized-market auction option ("If an agent defaults on a task, and the task is re-auctioned, the defaulting agent may be required to cover the price difference as a penalty") vs centralized registry lookup; Table 1/Figure 1 formalize "Scalable Market Coordination."

Reputation-as-credit:
- `papers/intelligent_ai_delegation.pdf:16` (section 4.6): "We distinguish reputation as the public, verifiable history of an agent's reliability, and trust as the private, context-dependent threshold set by a delegator." Immutable performance ledger proposed; "even a naive implementation could be susceptible to gaming."
- `papers/intelligent_ai_delegation.pdf:17` (Table 3): three reputation models — Immutable Ledger, Web of Trust (DIDs + verifiable credentials), Behavioral Metrics — with stated tradeoffs.
- `papers/distributional_agi_safety.pdf:7` (Table 1, Market Design column): "Reputation and Trust: Reputation-gated access, stake-based trust"; "Transparency: Immutable activity ledgers"; "Identity: Cryptographic IDs linked to legal owners."

Dispute resolution / enforcement — the missing institutional primitive:
- `papers/intelligent_ai_delegation.pdf:20` (section 4.8): "the framework relies on robust dispute resolution mechanisms anchored in smart contracts. These contracts must inherently include an arbitration clause and an escrow bond... optimistic model: the task is assumed successful unless the delegator formally challenges it within a predefined dispute period by posting a matching bond. If a challenge occurs and algorithmic resolution fails, the dispute is handed to decentralized adjudication panels composed of human experts or AI agents." The corpus's most concrete adjudication mechanism; directly answers Part II item 6 and Part III's presupposition question.
- `papers/intelligent_ai_delegation.pdf:23` (section 5.2): "liability firebreaks"; "maintain immutable provenance, ensuring that even if an outcome is unintended, the chain of custody regarding who delegated what to whom remains auditorially transparent."
- `papers/virtual_agent_economies.pdf` (~pp.18-22, best-effort transcription from rendered pages): trusted verifiable record and dispute-resolution as preconditions for accountability; recommends legal/liability frameworks for agent collectives "drawing from jurisprudence on group agency, much like corporate liability." The one place in the corpus where a source, unprompted, uses jurisprudential vocabulary for agent accountability — validation that the brief's framing is not the coordinator's invention.

Reference-repo confirmation of the gap:
- `coffee-bench-reference/coffeebench/environment.py:118-122` (late-payment interest), `:359-374` ("ONCE BANKRUPT, ALWAYS BANKRUPT"): contracts (invoices, `Deal`/`Offer` in `marketplace.py:9`) and automatic enforcement exist; grep finds NO occurrence of "dispute" in `environment.py` or `marketplace.py` — contracts and enforcement without adjudication. A clean corpus-grounded example of exactly the gap the precedent layer must fill before Step Two is buildable.

## 4. Inter-agent / inter-organizational protocols, identity, attestation (Part IV horizon)

- `papers/intelligent_ai_delegation.pdf:16` (section 4.6, transitive accountability via attestation): A monitors B's ability to monitor C, via cryptographically signed reports.
- `papers/intelligent_ai_delegation.pdf:19` (section 4.8): signed non-repudiable completion credentials ("Agent A certifies that Agent B successfully completed Task T on Date D to Specification S") incorporated into a permanent verifiable reputation log.
- `papers/intelligent_ai_delegation.pdf:21` (section 4.9): decentralized identifiers (DIDs) for all agents and humans; signed messages for authenticity, integrity, non-repudiation.
- `papers/distributional_agi_safety.pdf:7` (Table 1): Identity as a market-design layer requirement; "International Coordination: Harmonised global standards" — closest corpus analogue to "treaties," one line in a table, undeveloped.
- `papers/distributional_agi_safety.pdf:8` (section 3.1.3): "recording transaction and decision logs in a cryptographically secured, append-only ledger, where entries are hashed and chained to ensure immutability" — usable technical anchor for the citation index (append-only, hash-chained).

GAP: no surveyed source addresses inter-ORGANIZATIONAL protocols (two firms' fleets as distinct polities, MCP-as-lingua-franca, embassies). Everything found is intra-fleet delegation trust. Part IV has essentially no direct grounding in this corpus: treat as SPECULATION/analogy-only, exactly as the brief already scopes it (HORIZON).

## 5. Contradictions, nuances, and analogy-dressed-as-fact flags

(a) ESTABLISHED contradiction candidate — formalized handoff can CREATE information loss plain prompting does not have: `natural_language_agent_harnesses.pdf:8` (quoted in section 1). The paper's own caveat (p.6): "the current cost profile should be read as an engineering target; it does not show that the representation is unusable" — implementation-specific, possibly not fundamental. Real, measured cost of the exact mechanism (handoff boundaries) the precedent layer also introduces.

(b) ESTABLISHED — "more structure is not automatically better," specifically for branching/search, not for state/evidence discipline: `natural_language_agent_harnesses.pdf:9` (section 5.3): "Extra branching is not the same as better control... More search is not automatically better harness design." Same table shows file-backed state (73.0 to 75.6 SWE, 44.4 to 58.3 OSWorld) and self-evolution (to 78.8 SWE, 52.8 OSWorld) as clear net positives. The corpus draws a specific line: richer state/evidence discipline helps; richer branching topology, under this runtime, does not. The precedent layer (citation, adjudication, conflict detection) is structurally closer to state/evidence discipline — some evidence in the brief's favor, but that inference is ANALOGY, not the paper's claim.

(c) ESTABLISHED — component interactions are non-additive; one more institutional layer can REGRESS performance: `agentic_harness_engineering.pdf:8` (Table 3, RQ3a): "+ system_prompt only" scores -2.3pp aggregate vs baseline, the only regression among four single-component swaps. p.9: "Components interact non-additively... memory, middleware, and the system prompt all push toward the same closure-style verification, so stacking them spends turns on redundant re-checks." Direct design risk for Part II: a precedent layer that duplicates rather than replaces existing verification could hit the same interaction.

(d) ESTABLISHED — accumulated "frontier lineage" harness beats every general-purpose alternative, but plateaus: `harness-optimization-reference/legal_agent_bench/HARNESSES.md:60-76` (Pi: 45.4% vs vanilla LAB 63.4% vs optimized LAB 80.1%); lines 30-31, 135-136: "Pooled isn't strictly monotonic across the lineage... Clear plateau ~83% pooled... converged to a local ceiling." Path dependence built a much better system, and it saturates — a fair qualifier on Part V's "path dependence is the moat."

(e) ESTABLISHED finding, ANALOGY application — deliberation richness without action can hurt: `coffee_bench.pdf` section 5.2 (~pp.10-11): Haiku 4.5 "idle-drift" — coherent reasoning traces, repeated wait_for_next_day(), low net income. The inference that citation/adjudication overhead could induce analogous process-over-action paralysis is inference, not a corpus claim.

(f) A non-institutional coordination paradigm is live: `papers/trinity.pdf` demonstrates a trained coordination head routing Thinker/Worker/Verifier roles with no natural-language decision record, no citations, no declared ratio. It solves a narrower problem (real-time role/model selection, not durable cross-session precedent) so it does not falsify the brief — but the brief nowhere addresses that a non-institutional paradigm is actively published.

## Corpus gaps flagged for the coordinator

1. `harness_engineering_preprints.pdf` corrupted — only the abstract is available.
2. No source addresses inter-organizational (Part IV) protocols — speculation/horizon only.
3. No source documents a civil-law jurisprudencia constante (repeated-confirmation) model for agents — Part II item 5 requires legal literature research the technical corpus cannot substitute.
4. `trinity.pdf`/`conductor.pdf` contribute only the section 5f data point, not precedent mechanics.

## Sources consulted

Papers (verified page ranges): natural_language_agent_harnesses.pdf pp.1-11; agentic_harness_engineering.pdf pp.1-10; code_as_agent_harness.pdf pp.32-33 verified (broader pp.1-66 earlier, lower confidence); intelligent_ai_delegation.pdf pp.1-24; distributional_agi_safety.pdf pp.1-8; virtual_agent_economies.pdf pp.1-22; recontext.pdf pp.1-6; coffee_bench.pdf / conductor.pdf / trinity.pdf / sakana_fugu_tech_report.pdf (rendered pages, approximate page cites); harness_engineering_preprints.pdf UNREADABLE (corrupted).
fetched_docs: all five read in full. Reference repos: evolve_agent/evolve_prompt.md (full), code_agent_simple memory files, evolve.py:1-150, legal_agent_bench/HARNESSES.md (full) + meta_harness.py (grepped), coffeebench environment.py + marketplace.py (grepped).
