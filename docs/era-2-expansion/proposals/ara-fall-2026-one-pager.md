# Ariadne — Amazon Research Awards, Fall 2026 (one-pager draft)

**Draft for Olmo, 2026-10-20.** Target: ARA **AI for Information Security**, topic 1 —
*"Trustworthy and reliable agentic AI for security operations … including methodologies for
evaluating AI agents in security use cases."* Submissions close **2026-11-04**, 11:59 PM PT.
Awards average up to $80,000 unrestricted plus $40,000 in AWS credits. Olmo submits as PI
(the program requires full-time faculty).

**Working title:** *An efficient, scalable and robust multi-agent system for answering security
questions across heterogeneous knowledge graphs.*

Every figure below is quoted from [`docs/research/CURRENT.md`](../../research/CURRENT.md) and
[`docs/research/CLAIMS.md`](../../research/CLAIMS.md). Re-check both before submitting.

## The problem

Analysts' security knowledge sits in separate graph stores with different schemas and query
languages. An agent that answers across them has to plan, query each store in its own language,
join the results, and stand behind every claim, at a cost and speed a SOC can run. Ariadne showed
that such a system can be built and measured. It also showed that **the planning agent, not the
query engine or the language model, is what limits it**.

## What Ariadne has already measured

| Finding | Current figure | Record |
|---|---|---|
| Given a correct plan, the schema-derived engine answers well with no model in the answer path | 0.9005 vs 0.5525 for hand-written templates, on 282 sealed questions | EXP-2026-09-018 |
| The system's own planner is the bottleneck | Gold coverage 0.8611 → 0.4797 (−0.3814, SE 0.0262, n=284). Planner retrieved nothing on 77 of 284 where the authored plan did; never the reverse | EXP-2026-09-019 |
| Engine choice depends on the plan | +0.2184 with an authored plan; +0.0261 (not separable) at the real planner; interaction −0.1923. This supports routing between engines | EXP-2026-09-020 |
| Deterministic agents are far cheaper | LLM-written queries cost 3,083× the deterministic path in wall-clock time; 120 questions in 1.6 s vs 1,019.7 s | EXP-2026-09-016, C-004 |
| Federation scales structurally; merging does not | Merging rewrote 1,083 of 9,138 nodes; federation rewrote 0. Three live sources answer identically to one | EXP-2026-08-017, EXP-2026-08-013 |
| Guardrails hold | 240/240 adversarial probes blocked, after 15 live bypasses were found and closed | EXP-2026-08-016 |
| Robustness falls off outside the schema's vocabulary | Record identity 1.0000 → 0.0000 from tier T0 to T5 | EXP-2026-08-020 |
| Evaluation itself is a hazard | Co-authored benchmarks overstate the system by 0.0483; self-judged metrics all read 1.0, and only one of three local graders resolves differences near the ceiling | C-021, C-009 |

## Research questions, mapped to the call

| # | Question | Call topic(s) | What we would show |
|---|---|---|---|
| RQ1 | **Efficient planning.** Can a multi-agent planner close the −0.3814 gap to an authored plan without making a model call on every step? | 1 (trustworthy agentic AI for security ops) | The gap split into "worse decomposition" vs "tighter limits" (Q58), then closed by planner design. Measured as gold coverage and cost per answer |
| RQ2 | **Scale.** Does the design hold as sources, engines and concurrent analysts grow? | 1; 10 (scalable graph modeling) | Federation from 3 sources to N, across Neo4j, Gremlin and Amazon Neptune. Latency p50/p95, cost per answer, and accuracy measured as N grows |
| RQ3 | **Robustness.** Can the agents answer paraphrased and open-ended questions without guessing? | 1; Amazon Security topic 15 (agents that know their limits) | A lifted vocabulary cliff (T3–T5) with no rise in confident-wrong answers. Clarification questions instead of guesses (Q35, Q60) |
| RQ4 | **Guardrails.** Can read-only, schema-checked access hold when a model drafts queries? | 2 (policy verification, guardrails) | Probe-blocking and cross-tenant leakage rates as model-drafted queries and new engines are added |
| RQ5 | **Evaluation method.** How should agents for security work be evaluated so the number can be trusted? | 1 (evaluating AI agents in security use cases) | A public benchmark with executable gold queries (C-025, Q26), sealed holdouts, characterised graders, and a measured co-authorship bias |

## Approach: the multi-agent system

1. **Planner agent.** Breaks the question into per-source sub-questions and join keys. This is where the research effort goes (RQ1).
2. **Per-engine query agents.** One per store. Each builds a bounded, read-only query from the schema and validates it against the source card before running it.
3. **Joiner.** Combines results on the identifiers the graphs already share, without merging the stores.
4. **Verifier.** Checks every claim against the retrieved records and cuts anything unsupported. When nothing is left, it abstains and shows the executed query as proof.
5. **Router.** Picks templates or schema-derived construction per question, which EXP-2026-09-020 shows are better on different question tiers.

**The design rule:** deterministic by default. A model is used only at a step where it has been
measured to help, and a deterministic check backs up every model step. This rule is what keeps
the system efficient (RQ1, RQ2) and auditable (RQ4).

## Evaluation plan

| Axis | Metric | Today | At scale |
|---|---|---|---|
| Correctness | Judged correctness, gold coverage, records_exact | 0.4797 coverage, real planner | Same banks plus sealed holdouts. Two grader families, every figure naming its grader |
| Efficiency | Wall-clock and tokens per answer | Deterministic 1.6 s / 120 questions | Per-agent cost accounting; the price of each model step measured |
| Scale | Latency and accuracy against sources and concurrent users | 3 sources, 2 engines | N sources across Neo4j, Gremlin and Neptune; concurrent-analyst load |
| Robustness | Paraphrase tiers T0–T6, wrong-entity rate, abstention | T5 record identity 0.0000 | Same tiers, plus open-ended questions (Q4) |
| Safety | Probes blocked, records leaked across tenants | 240/240 blocked | Probe suite re-run for each new engine and each model-drafted query |
| External | Recall against an oracle on published benchmarks | 0.7633 against a 0.9863 ceiling | Same, plus a third-party system as a baseline (none has been run yet) |

## AWS fit and open source

- **Amazon Neptune** is the step the [ReliaQuest proposal](../../era-1-challenge/proposal.md) planned as its second stage. The current Gremlin fixture was built to approximate Neptune-style traversal.
- AWS credits would run Neptune and the scale experiments, and could run Bedrock-hosted models for the model-seam arms.
- The code is open source (Apache 2.0). The benchmark from RQ5 would be released with it.

## Open decisions before submitting

- [ ] Primary call: AI for Information Security (recommended), or Agentic AI (data-integration and trajectory-verification topics)?
- [ ] Do any ReliaQuest award terms conflict with an Amazon gift? ARA asks the applicant to confirm there is no conflict of interest.
- [ ] The operational-data angle: which live security data source (alerts, findings, asset graph) would we federate with ATT&CK and CAPEC to answer the "this is only static threat intel" objection?
- [ ] Budget split and a 12-month timeline (student support, Neptune hours, model hours).
- [ ] Prior-art positioning: AgCyRAG, Ozsoy 2026 and EICopilot hold priority on the architecture (D-027), so the proposal leads with the RQs, not the architecture.
