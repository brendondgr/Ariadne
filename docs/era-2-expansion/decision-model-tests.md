# Decision models — what to test at each step (2026-10-26)

**Status: a list of tests to choose from later. Nothing here is scheduled.**

A **decision model** answers a closed question about an input (yes/no, one of several
options, or a score) with a probability for every answer and no generated text. The first one
available is d3-lite (GAIFA `decide` mod: 0.85B, Apache-2.0). On 2026-10-26 it took about
80 ms per call for two questions, against 0.30–0.41 s for the local LLM picking from a list
([probe](../research/reports/2026-10-26-agentic-loop/probe/RESULTS.md)). **Speed is measured;
accuracy and calibration on Ariadne's questions are not.** That is what these tests are for.

The aim is to learn, step by step, where a decision model can run a step on its own, where it
is good enough only as a signal to escalate, and where it should not be used.

## Candidate steps

Each row is one closed question the loop asks. The options always come from the card or from
the previous tool's output, so every test carries over to any graph without code changes.

| # | Step | The question to the decision model | Options come from | Ground truth from | Compare against |
|---|---|---|---|---|---|
| D1 | **Source routing** | Which of the online graphs does this question need? | The online cards' one-line descriptions, plus "several" and "none" | Gold source per question in the banks | The current planner's routing; LLM pick |
| D2 | **Entity grounding** | Does *this mention* refer to *this candidate* (id, label, name, description)? Asked once per candidate | Candidates from the name, alias and description index | Gold anchor id per question; the named, paraphrased and description tiers | Generative LLM pick (35% wrong); deterministic exact-name match |
| D3 | **"None of these"** | Derived from D2: every candidate below threshold | — | Questions about entities absent from the graph (the false-premise pilot: 4 of 30 answered with up to 558 cited records, `EXP-2026-08-020`) | LLM pick with a NONE option |
| D4 | **Relation choice** | Which relation from this anchor answers the question? | Relations valid from the anchor's label, each with its gloss and direction, plus NONE | Gold plan per question | Keyword rules in the builders; LLM menu pick; LLM tool call |
| D5 | **Question shape** | Is this a lookup, enumeration, count, chain, intersection, comparison, aggregate, or other? | A fixed, graph-independent list | Gold template or plan shape in the banks | `utils/planner/intent.py` (MITRE-specific rules) |
| D6 | **Property filter** | Does the question restrict a property of the target? Which one? | The target label's properties in the card, plus "no filter" | Questions with filters (a located defect: filters never reach the query) | LLM tool call |
| D7 | **Answer type** | Is the node type of this answer the type the question asks for? | The card's labels | Gold answer label; catches answers that stop one hop short | Nothing today |
| D8 | **Plan check** | Does this typed plan answer this question? | The plan rendered in words from the card's glosses | Gold plan vs perturbed plans (wrong relation, wrong direction, wrong anchor) | Nothing today: the claim verifier cannot catch a wrong binding |
| D9 | **Sufficiency** | Do these records answer the question? | The envelope's totals, facets and sample | Gold coverage of the retrieved set | The model's own "done" |
| D10 | **Membership by meaning** | Does this member satisfy the question's judgment ("concerns cloud identity")? Asked once per member of a large set | Each member's name and description | Constructed sets where membership is known from structure (for example, techniques under one tactic), with the structural cue hidden | LLM over a sample; embedding filter |
| D11 | **Ask or guess** | Derived from D2/D4: is the spread of probabilities wide enough to ask the user? | — | Simulated caller that knows the gold anchor | Never ask; LLM decides when to ask |
| D12 | **Untrusted text screening** | Does this node description contain instructions aimed at an agent? | — | Descriptions with planted instructions in a Synapse-extracted graph | No screening |

## How each test is measured

The same measurements apply to every row, so the steps can be compared:

- **Accuracy** of the top answer, by wording tier where the bank has tiers.
- **Calibration:** do answers given p = 0.8 turn out right about 80% of the time? Report the
  calibration error and a reliability plot.
- **Wrong answers at fixed coverage:** if the model may answer only when it is confident,
  how many does it get wrong at 90%, 70% and 50% coverage? This is the number that decides
  the threshold.
- **"None" precision and recall** (D2–D4, D6).
- **Order and wording stability:** shuffle the options and reword the glosses. How much does
  the answer move?
- **Latency:** single call, and batched throughput on the vLLM server.
- **Agreement across models:** the same question to several decision models, and to the LLM
  scored by the probability of each option label, so generative and decision models are
  compared on the same footing.

## Models and serving

- **Decision models:** d3-lite first, then any other that vLLM can serve, on a separate
  vLLM server so calls run concurrently and in batches.
- **LLM baselines:** run across several models, not one, starting with `minicpmv47-35b`.
  Record the served model on every call (`scripts/model_identity.py`), never the alias.

## When a decision model may run a step on its own (to agree before testing)

A proposal for the rule, not a result. A decision model runs a step without a fallback only if,
on a held-out bank:

- its wrong rate is at most the agreed limit at the agreed coverage (for example ≤ 5% wrong at
  ≥ 70% coverage);
- it is calibrated well enough that the threshold carries over from the tuning half to the
  held-out half;
- shuffling the options does not change the answer more than an agreed amount.

Below that bar it is used only as a signal to escalate to the controller. A step where it does
worse than the LLM pick is dropped.

## Questions to settle in discussion first

- Which steps matter most? D2, D4 and D8 target the largest measured losses.
- Which held-out banks to reserve for setting thresholds, so the tuning half and the test half
  never mix. (The 2026-08-31 lesson: a threshold that scored 12-right-0-wrong on the tuning half
  scored 17-right-8-wrong on the frozen half.)
- Which decision models to include besides d3-lite, once the vLLM server is up.

## Round two changed the roles (2026-10-26)

The decision-model report ([`5-decision-models.md`](../research/reports/2026-10-26-agentic-loop-round-2/5-decision-models.md))
found that a small model scoring candidates one at a time is a poor *final* judge of the entity:
a reranker's top pick scored 27 against 77–83 for an LLM choosing with reasoning (LELA, ZESHEL,
normalized accuracy). Revised roles, from
[`ASSESSMENT.md`](../research/reports/2026-10-26-agentic-loop-round-2/ASSESSMENT.md) §4.3:

- **D2 entity grounding:** a second opinion, never the final judge.
- **D3 "none":** combined with structural signals (no candidate has the required relation).
- **D4 relation choice:** a strong candidate; on a near-tie, run both relations.
- **D5 question shape, D8 plan check:** advisory only.
- **D10 membership by meaning:** the best fit.

The test order, the roster of model types and sizes, and the rule for assigning each step a role
are in the [era-2 roadmap](../plans/2026-10-26-era-2-roadmap.md), Phase 1. Only off-the-shelf
open-source models are tested; none is trained for Ariadne.

