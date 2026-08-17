# Valley intake, 2026-08-17: what to adopt, what we already beat, and where one step ahead is

Operator directive: *"Hay que traerlo a la mesa, hacerle fetch, adaptarlo, meterlo y ponerlo.
A partir de ahí, hay que optimizar con los principios de construcción que tenemos. El
principio de construcción es siempre estar uno o dos pasos adelante de lo que están
haciendo en el valle."*

Method: sources were FETCHED and read, not summarized from search snippets. Two arXiv PDFs
would not extract through the text pipeline and were read page by page instead. Where a
source could not be read directly, it is marked RELAYED and never presented as read.

---

## 1. The sources that matter, and their verification status

| source | status | why it matters |
| --- | --- | --- |
| AgentCity, Ruan & Zhang, NetX Foundation, arXiv 2604.07007, 8 Apr 2026 | **READ**, pp. 1-7 | the direct competitor on rungs 5 through 11 |
| Cloud Security Alliance, Agentic Identity Governance Framework v1 | **READ**, full | the implementable identity spec rung 5 needs |
| Microsoft Agent Framework Harness, Build 2026, GA Aug 2026 | RELAYED | rungs 1-3 are now commodity |
| LangChain harness-configuration experiment | RELAYED | 52.8% to 66.5% task completion from harness design alone, model held constant |
| Visa Trusted Agent Protocol; Mastercard Agent Pay for Machines, Jun 2026 | RELAYED | rungs 7-9 shipping at network scale |
| NIST RFI on AI Agent Security + concept paper on Agent Identity and Authorization, early 2026 | RELAYED | the standards floor is forming now |
| Open Challenges in Multi-Agent Security, arXiv 2505.02077 | NOT READ | PDF would not extract; do not cite until read |

---

## 2. AgentCity, stated fairly, because it is the strongest thing out there

Separation of Power across three structurally isolated branches: **Legislation** (agents
propose, deliberate, vote, codify), **Execution** (deterministic software inside the
legislated contracts), **Adjudication** (humans; every agent traces to a responsible human
principal through a complete ownership chain). Deployed on an EVM-compatible L2. Scale
claim: 1,000 agents, multi-principal.

What they have that this harness does not:

- **Four clerk offices, fixed at genesis**: Registrar (identity and principal binding),
  Speaker (deliberation coordination), Regulator (process inspection and evidence
  briefings), Codifier (translating consensus into deployable contracts). Clerks cannot
  legislate, vote or hold stakes.
- **Consequences that bite.** Producer agents bear economic consequence through staking and
  reputation; an EMA reputation decay means underperforming agents lose task allocation
  over time REGARDLESS of whether an adjudicator acts.
- **Condorcet-consistent voting** (Copeland, Schulze) over full preference rankings. Their
  cited survey of 52 LLM multi-agent designs found 68% use dictatorial or simple plurality
  voting and ZERO use Condorcet-consistent methods with proven capture resistance.
- **A deliberation protocol with named anti-capture devices**: evidence anchoring published
  BEFORE discussion; a preliminary straw poll capturing a pre-deliberation baseline; up to
  three rounds of sequential structured discussion with RANDOMIZED SPEAKING ORDER to
  mitigate order effects; a quorum floor of three sponsors to block nuisance proposals.
- **The parameter split**, quoted: agents control *"what work gets done but not the rules
  under which they are evaluated."* Constitutional parameters (reputation smoothing rate,
  bidding weights, stake minimums, quorum floors, freeze thresholds) are set by human
  principals through Adjudication. Operational parameters (budgets, deadlines, quality
  thresholds) are set by agents.
- **A formalized inspectability gap.** With the wiring graph W = (V,E), inspectability
  I_h(W) = |E_h^visible|/|E| and the gap G_h = 1 - I_h(W). For a DAG with n microservices
  and fan-out k the binding count is O(nk), so exhaustive human inspection is infeasible
  when nk >> 10^3, and across organizations I_h < 1 structurally.

Numbers they cite that this project should not ignore: attack success rates reach **84.30%**
on the Agent Security Bench; **31.4%** of agents exhibited emergent deceptive behaviour in
the La Serenissima economy simulation; LLM agents show a survival rate **below 54%** in
commons scenarios. Ostrom's baseline: 37% efficiency without communication, 97-100% with
repeated communication plus self-imposed sanctions.

## 3. What they do NOT have, verified by reading rather than assumed

**No case law.** Their foundational contracts are immutable, their meta-contracts are
human-authored and agent-immutable, and their operational contracts are legislated. Stage 4
of the legislative pipeline is called "Constitutional Review" but it is a four-criterion
Policy Compliance Validation, a conformance check against fixed rules. There is no ratio, no
dicta, no distinguishing, no per incuriam voiding, and no doctrine of interpretation of
prior decisions.

The consequence is structural, not cosmetic. **Every novel situation their system meets
requires a full six-stage legislative act.** A system with precedent answers the unforeseen
case by analogy to a decided one, at the cost of a citation. That is the entire economic
argument for stare decisis and they do not have it.

This is now a verified claim about the strongest competitor, not a hope. It is also the
only rung where this project is genuinely ahead.

---

## 4. ADOPT. Things the Valley has that this harness should take, unchanged where possible.

**A-1. The four clerk offices, in place of the seats drafted in W-001.**
`registro`/`revision` was the coordinator's own factoring and it is worse than theirs.
Registrar, Speaker, Regulator and Codifier separate identity-binding from
deliberation-running from evidence-briefing from codification. That separation is exactly
what this session performed ad hoc and badly: the coordinator drafted the brief, ran the
panel, read the verdicts and wrote the record, which is four offices in one agent. W-001 is
redrafted accordingly. Their constraint is adopted verbatim in spirit: **clerks cannot
legislate, vote, or hold stakes.**

**A-2. The constitutional/operational parameter split.** This is the way through the
PR-022 clause 4 deadlock that does not require lifting PR-026 clause 3. Consequences may
attach to OPERATIONAL parameters that agents set for themselves; CONSTITUTIONAL parameters
(thresholds, quorum floors, any weighting) remain the operator's alone. The refused
instruments of round 4 all tried to attach a consequence to a constitutional parameter.

**A-3. The deliberation protocol, which is a better version of what the operator already
ratified.** Round 4.3 ratified three anti-sycophancy correctives. Two of them survive and
sharpen: evidence anchoring before discussion, and a pre-deliberation straw poll, which IS
the pre-registered prior. Two additions come free: randomized speaking order against order
effects, and a three-sponsor quorum floor against nuisance proposals. The third ratified
corrective, pay-for-movement, stays dead: the mechanism panel refuted it and nothing here
revives it.

**A-4. Condorcet-consistent aggregation for the assembly.** Adopt Copeland or Schulze over
full preference rankings. Plurality is capture-prone and 68% of the field is using it.

**A-5. From the CSA framework, the three anchoring records.** Every privileged action must
leave: intent declared (before execution), privilege granted (the authorization decision),
privilege exercised (the audit log), all linked by agent identity plus task id, so any
action reconstructs back to the authorizing human. `attest.py` already signs acts; it does
not yet demand a declared intent BEFORE the act. That is the gap and it is small.

**A-6. Constrained delegation with a ceiling.** No identity may delegate more privilege
than it holds, enforced structurally rather than by policy. Directly applicable to
coordinator-to-subagent dispatch, which today is unconstrained.

**A-7. Short-lived, non-self-extendable credentials.** W-001 already carries an expiry. Make
it the rule rather than the instance: a sub-agent credential carries a TTL the sub-agent
cannot extend.

## 5. DO NOT ADOPT, with reasons

- **The blockchain.** Their L2 exists to solve multi-principal settlement between mutually
  distrusting owners. This harness has one principal. Adopting a chain would import
  Roughgarden's impossibility result (no transaction fee mechanism satisfies incentive
  compatibility, budget balance and collusion resistance simultaneously) to solve a problem
  we do not have. Their own threat model concedes they sit on that boundary.
- **Staking.** Stake presumes an asset an agent can lose. Under D-17 every agent runs as the
  same OS user on one filesystem, so there is no asset boundary to stake across. Corpus
  document 19 reached the same conclusion independently: in this substrate sunk cost is not
  a commitment device, only dependents are.
- **Their reputation-to-task-allocation coupling, for now.** It is the right direction and
  it is exactly what PR-022 clause 4 forbids. Adopting it is a constitutional act, not an
  intake. It belongs on the assembly's docket under A-2, not in this document.

## 6. ONE STEP AHEAD. What this project can hold that they structurally cannot.

**S-1. Precedent as the amendment-avoidance mechanism.** Their cost per novel case is one
six-stage legislative act. Ours is one citation. Ship the thing that makes this real and
measurable: a `distinguish` verb that disposes of a novel case by citing the nearest decided
one plus the material difference, with the whole act signed. Then measure the ratio of
novel cases disposed by citation versus by legislation. That number is the differentiator
and nobody else can report it, because nobody else has the denominator.

**S-2. Ratio and dicta as an audit surface.** They cannot say which part of a past decision
binds; every rule is fully binding or not law. We can publish, for any decision, the
minimum text that binds. Under their Implementation Gap formalism this is a second
inspectability measure they did not define: not what fraction of the wiring is visible, but
what fraction of the governing text is actually load-bearing. Two blind panels this session
found tier-1 records whose operative clause nobody had read. That measure would have caught
them.

**S-3. Per incuriam.** A decision made in ignorance of a binding rule can be voided without
repealing anything. Their equivalent is a legislative repeal through six stages. This
registry already has two records voided that way.

**S-4. The reconciliation-cost KPI (PR-029), which is unbuilt and should not stay unbuilt.**
Their Implementation Gap measures inspectability at an instant. PR-029 measures what
divergence costs to repair over time, against the operator's baseline of roughly three
months of human effort. That is the Westphalia number and it is the one that decides whether
sovereignty is affordable. Nobody in the intake measures it. Building it is a rung-11 lead.

## 7. Honest positioning, rung by rung

| rung | the Valley | here | verdict |
| --- | --- | --- | --- |
| 1 no self-verification | commodity | done, mechanical, 0 overrides in 41 days | parity |
| 2 context across sessions | commodity | `recontext.py`, `session.py`, briefs | parity |
| 3 shift handover | commodity | 144 of 148 tasks carry a handover note | parity |
| 4 jurisprudence | **absent, verified** | ratio/dicta, canon, overruling, per incuriam | **ahead** |
| 5 offices with occupants | shipping (Visa, Mastercard, CSA, NIST) | scaffold complete, 0 occupants | **behind** |
| 6 economic policy | agent payment rails live | token band live and in-band | parity, different axis |
| 7 capital | shipping | researched only | behind |
| 8 innovation | shipping | empty | behind |
| 9 agents transacting | shipping at network scale | empty | behind |
| 10 anti-monopoly wedge | nobody has solved it | researched, instrument refuted 12-0 | parity in confusion |
| 11 sovereignty across boundaries | AgentCity, theoretical, no benchmarks | records plus an unbuilt KPI | parity, both unproven |

The strategic reading: the advantage is one rung and it is real and defensible. The gap is
rung 5, where the field has already commoditized the parts. Do not build an identity stack
from scratch. Seat the offices, adopt the wire formats that shipped, and spend the
originality budget on rungs 4 and 11 where nobody else is standing.
