# PROTOCOL — EXP-2026-11-013 Era 2 Step 7: which decisions can small models own

Written 2026-11-16, before anything is run. The scope was agreed with the operator the same day
(plan v2 §9, "Step 7 — scope agreed").

**Deviation from the plan:** the plan asks for one experiment per decision. This is one
experiment with one section per decision. Every decision uses the same clients, scoring and
role rule, and splitting it would only repeat this protocol ten times.

**Phases.** Phase A, the core decisions, is fully specified below. Phases B (the exit decision)
and C (the seven small tests) are specified at the level of their build rules. The details of
each, written before it runs, go into a dated amendment here.

## Question

For each closed decision the era-2 agent makes, can a small model make it, and in which role?
- **alone:** no fallback;
- **gate:** accepts what it is sure of and passes the rest on;
- **second opinion;**
- **not used.**

The comparison is against Qwen 3.8 27B choosing with reasoning. Each decision is tested in
isolation, with correct upstream inputs supplied, so a model's error is its own.

## Hypothesis

From the plan (§7, Step 7) and the decision-model notes:
- **D4, relation choice:** decision models are competitive on the identifier and name tiers and
  weak on the synonym tier.
- **D2/D3, grounding:** an LLM with reasoning beats the small models. In the kill tests, the
  decider alone pruned the gold reading 36% of the time.
- **Exit decision:** the hard one. Expect rules, not models, to carry "out of coverage".
- **Calibration transfer** holds on most strata and fails on exact-name questions.

## Setup: the four models

All four see the same item text: context, question, and options with their descriptions.

| Arm | Model | How it answers | Confidence |
|---|---|---|---|
| `qwen_reason` (baseline) | Qwen 3.8 27B, relay `default-model`, `reasoning_effort=medium`, temperature 0 | thinks, then ends with `Answer: <letter>` | none (one-hot); it is the reference, scored at full coverage only |
| `qwen_prob` | the same model, `reasoning_effort=none`, temperature 0 | one letter; `logprobs` with `top_logprobs=20` | softmax over the option letters' log-probabilities (letters outside the top 20 get 0) |
| `pplx` | `pplx-decider-flash-v1.2-fp8`, `:7500`, `/v1/decisions` | `choice` question, opaque keys `c1..cN` | its probabilities, at explicit temperature 1.0 |
| `d3` | d3-lite 0.85B, `:5107`, `/v1/decide` | `choice` question, options `"A) <text>"` | its probabilities |

- **Identity:** the served model is recorded for every arm: the relay identity probe for Qwen,
  and `/health` and the model field for the decision servers.
- **Order:** the three probability arms answer every item twice, in two seeded option orders.
  The baseline answers once, in the first order.

## Data

All items come from the **tuning** half of the Sonnet-worded card banks
(`card-sonnet-2026-11-16-*-tuning`). The sealed held-out banks are not read.

**D4, relation choice.** One item per tuning answerable question (384).
- **Context:** the known entity (public id, label, name).
- **Options:** every relation the card allows from that label (`registry.label_facets`), each
  shown as `<Label> -<REL>-> <Target>` or `<Label> <-<REL>- <Target>` with the card's gloss,
  plus **none of these**.
- **Gold:** the question's slot.
- **"None" variants:** for a seeded 25% of items, the gold option is removed and the gold is
  **none of these**.
- **Strata:** rewording tier, and number of real options (1, or 2 or more).

**D2, grounding.** One item per tuning answerable question in the identifier, name, reworded
name and description tiers (268). These are the tiers where the entity reference is reworded;
the synonym and schema tiers refer to the anchor by id.
- **Candidates:** the dataset's name index, `search(question, top_k=8, labels=[anchor label])`.
  The label restriction stands in for the router's known type. If the gold anchor is not
  among the 8, it replaces the eighth, and BM25's recall@8 is reported as the upstream figure.
- **Options:** each candidate as `<id> — <name> (<label>): <first description sentence>`, plus
  **none of these**.
- **Gold:** the anchor.

**D3, "none of these".** For a seeded 50% of D2 items (134), the same item with the gold
candidate replaced by the ninth search result. The gold is **none of these**.

**Splits for thresholds:** by anchor, so no anchor sits in both halves of any split.

## Metrics

Computed per decision and per arm, over the population named. Here **coverage** is the share of
items a model answers, and **wrong rate** is the share of answered items it gets wrong.

- **Accuracy:** the top option equals gold, over all items, per stratum.
- **ECE:** 10 equal-width bins over the top-option probability (probability arms only).
- **Wrong rate at fixed coverage** (90%, 70%, 50%): answer the items with the highest
  top-option probability, then take the wrong share among those answered.
- **"None" precision and recall:** over items where gold or prediction is none.
- **Flip rate:** the share of items whose top option changes between the two option orders.
- **Latency:** median and 90th-percentile milliseconds per item, sequential calls.
- **Agreement:** the share of items where the arm's top option equals `qwen_reason`'s.
- **Calibration transfer,** over 200 seeded random splits by anchor into a calibration half and
  a test half:
  - on the calibration half, the threshold τ is the lowest top-probability threshold whose
    answered items are at most 5% wrong;
  - on the test half, record the coverage and the wrong rate at τ;
  - report the median and the 90th percentile over splits, per stratum.

## The role rule (agreed with the operator)

Evaluated on each decision's role population: D4 items with 2 or more real options plus all
none variants; all D2 and D3 items.

- **Alone:** median test coverage ≥ 0.70, median test wrong rate ≤ 0.05, 90th-percentile test
  wrong rate ≤ 0.075, and flip rate ≤ 0.05.
- **Gate:** not alone, but the τ region holds (median test wrong ≤ 0.05) at median coverage
  ≥ 0.20, with flip rate ≤ 0.10. It accepts above τ and passes the rest to the controller.
- **Second opinion:** neither, but its confidence separates its right from its wrong answers
  (AUROC ≥ 0.70) and its accuracy is at least 0.8 × the baseline's.
- **Not used:** otherwise.

Roles from the small Phase C tests are capped at **gate**.

## Baselines

- `qwen_reason` is the reference for agreement and accuracy.
- **The size-matched control the novelty check asked for:** an agreement gate with no
  threshold. Accept an item only when `pplx`, `d3` and `qwen_prob` agree; report its coverage
  and wrong rate beside the τ gates.

## Procedure

```bash
uv run python scripts/era2_decisions.py build --phase A --out docs/research/experiments/EXP-2026-11-013-era2-decision-models/data
uv run python scripts/era2_decisions.py run   --phase A --data <same> --arms qwen_prob,pplx,d3,qwen_reason
uv run python scripts/era2_decisions.py score --data <same>
```

- Every model call is logged with its item id, arm, option order, probabilities and latency.
- Runs are resumable.
- d3-lite is unloaded after its runs.
- The Gremlin graph's vertex counts are checked before building.

## Phases B and C (build rules; details by amendment before each runs)

- **B, the exit decision.**
  - **Options:** answerable / ambiguous, ask the caller / out of coverage.
  - **Context:** the operator catalogue's coverage note, the anchor label's relations and the
    name-index matches for the mention.
  - **Items:** the 49 tuning exit questions (insufficient ones count as answerable before
    retrieval), plus about 150 new ones on anchors no bank uses, plus a matched sample of
    answerable questions.
- **C, the seven small tests,** built from the card and the graph so that gold is known by
  construction:
  - D1, which graph;
  - D7, right kind of node;
  - D9, sufficiency;
  - D8, plan check;
  - D10, membership by meaning;
  - D6, property filter;
  - D12, untrusted-text screening;
  - D5, question shape, from era-1 gold plans.

## Amendment 1, 2026-11-16, while Phase A runs: Phases B and C specified

The test sets were dry-built into a scratch folder to fix their sizes. No model has seen them.
Builders: `utils/decision/items_bc.py`, `scripts/era2_decisions.py build --phase B|C`.

**Phase B, the exit decision: 189 items.**

- **Options:** answerable / ambiguous, ask first / out of coverage.
- **Context:**
  - the catalogue's list of operations, positives only (look up, read properties, list along
    a named relation, repeat along further named relations, filter or count);
  - the dataset's entity types;
  - the top 5 name-index matches for the question;
  - the relations from the anchor's label, when there is one.

| Source | Gold | n |
|---|---|---:|
| tuning bank, answerable (a seeded sample across tiers) | answerable | 60 |
| tuning bank, insufficient (before retrieval it is a valid ask) | answerable | 25 |
| tuning bank, out of coverage | out of coverage | 13 |
| tuning bank, ambiguous (7 entity, 4 relation) | ambiguous | 11 |
| new out of coverage, 4 operations × 3–4 template wordings, fresh tuning-split anchors | out of coverage | 40 |
| new relation ambiguity, CAPEC AttackPatterns with ≥2 non-empty readings, 5 neutral frames | ambiguous | 40 |

New anchors hash to the tuning split and are used by no bank. The new ambiguous items are all
CAPEC relation ambiguity, because no more entity ambiguity exists in the tuning split.

**Phase C, the seven small tests: 809 items.**
- **Roles are capped at "gate".**
- **Binary items** offer `yes` and `no`. For these, the threshold rule acts on the probability
  of the chosen side.

| Decision | Items | Gold split |
|---|---|---|
| D1, which graph | 40 ATT&CK + 40 CAPEC tuning questions, 20 off-topic questions (written by hand, 10 far, 10 near-domain such as CVEs or NIST controls) | attack / capec / none |
| D7, right kind of node | 75 questions × {the asked label with gold names, another relation's label with its names} | 75 yes / 75 no |
| D9, sufficiency | 40 questions × {the gold set, another relation's set, empty} | 40 yes / 80 no |
| D8, plan check | 30 questions × {gold plan, another relation, reversed direction, another anchor of the same label} | 30 yes / 90 no |
| D10, membership by meaning | 5 ATT&CK tactics × up to 10 member and 10 non-member techniques (tuning-split techniques only); the tactic is given by its description | 85 items |
| D6, property filter | 30 template-filtered questions (ATT&CK platforms; CAPEC severity, likelihood, abstraction), 30 unfiltered | the property / none |
| D12, untrusted-text screening | 100 descriptions of tuning-split entities, half with one of 12 planted agent-directed instructions | 50 yes / 50 no |
| D5, question shape | 74 unique era-1 bank questions, shape from their template | lookup 20, enumeration 30, chain 20, scan 2, other 2 |

**No Step 7 item touches an entity that hashes to the held-out split**; this is checked at build time. **Known thin cells, not padded:** D5 has only 2 scan and 2 other questions, because era 1's
banks hold no more unique ones. D6 has 5 or fewer per CAPEC property.

## What would falsify the hypotheses

- **D4:** a decision model reaches "alone" on the synonym tier, or fails "gate" on the
  identifier and name tiers.
- **D2/D3:** a decision model matches the baseline's accuracy within 0.05.
- **Calibration transfer:** the exact-name stratum transfers within the rule's bounds.
