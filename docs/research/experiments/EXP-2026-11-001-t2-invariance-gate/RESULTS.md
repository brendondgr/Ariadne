# RESULTS — EXP-2026-11-001 Answer-invariance gate (kill test T2)

## 1. Headline

**Killed by the pre-registered rule, on both counts.** On the confirmation bank, the
decider-filtered gate (T2-filtered):
- asks on **0.533** of unambiguous questions, against the 0.40 limit;
- prunes the gold interpretation on **0.358** of them, against the 0.30 limit.

The gate does halve confident wrong answers relative to guessing: 27 against 51 on
confirmation, 81 against 142 on development. But it answers correctly less often than the
guess does: 0.233 against 0.425.

## 2. Results table

From `data/score.json` (`summary`). The populations are the unambiguous T1–T5 variants; T6 and
absent anchors are scored separately. One system run (`n_runs: 1`).

| Bank | Policy | answer | ask | abstain | answer_exact | gold_pruned | confident_wrong | T6 answered | mean interps |
|---|---|---|---|---|---|---|---|---|---|
| confirm (n=120 + 40 T6) | raw (no model) | 0.000 | 1.000 | 0.000 | 0.000 | 0.108 | 0 | 0.000 | 37.9 |
| | **filtered** | 0.367 | **0.533** | 0.100 | 0.233 | **0.358** | 27 | 0.275 | 3.1 |
| | guess-raw | 0.825 | — | 0.175 | 0.192 | — | 108 | 0.800 | 1 |
| | guess-filtered | 0.725 | — | 0.275 | 0.425 | — | 51 | 0.375 | 1 |
| dev (n=327 + 37 neg.) | raw | 0.000 | 1.000 | 0.000 | 0.000 | 0.138 | 0 | 0.000 | 28.0 |
| | filtered | 0.538 | 0.398 | 0.064 | 0.321 | 0.468 | 81 | 0.270 | 2.1 |
| | guess-raw | 0.920 | — | 0.080 | 0.272 | — | 245 | 0.892 | 1 |
| | guess-filtered | 0.801 | — | 0.199 | 0.410 | — | 142 | 0.378 | 1 |

T2-filtered by tier:

| Bank | Tier | n | ask | answer_exact | gold_pruned |
|---|---|---|---|---|---|
| confirm | T3 name | 40 | 0.500 | 0.175 | 0.425 |
| | T4 paraphrase | 40 | 0.525 | 0.300 | 0.325 |
| | T5 description | 40 | 0.575 | 0.225 | 0.325 |
| dev | T1 id | 66 | 0.212 | 0.485 | 0.348 |
| | T2 id fragment | 66 | 0.288 | 0.455 | 0.288 |
| | T3 name | 63 | 0.460 | 0.238 | 0.540 |
| | T4 paraphrase | 66 | 0.485 | 0.197 | 0.652 |
| | T5 description | 66 | 0.545 | 0.227 | 0.515 |

Gold sources (`relation_by`) on dev: 94 slot, 20 relation-only, 159 describe, 54 resolved from
the reference answer at Jaccard ≥ 0.5 (34 of them at 1.00). There are no unresolved items and
no execution errors.

## 3. Figures

None.

## 4. Interpretation

- **The mechanism, as built, fails on usability, not on safety.** Executing every plausible
  interpretation and answering only on agreement does what it is meant to: confident wrong
  answers fall by about half against a single guess. But it asks on more than half of the
  questions, and none of them were ambiguous.
- **The pruning is the weak link, not the execution.** Without a model, the card-valid
  enumeration keeps the gold interpretation 89% of the time (gold_pruned 0.108), at about 38
  interpretations per question. The decision model's anchor and facet pruning takes that to
  about 3 interpretations, and loses the gold on 36% of questions.
- **The losses persist when the question writes the identifier** (dev T1, gold_pruned 0.348).
  So the facet choice (which relation and direction) is failing, not only entity grounding.
- **The ask-rate is inflated by complementary readings.** Many questions are not ambiguous in
  their relation but have two readings that are both partly right (Technique and SubTechnique
  members). The gate counts those as disagreement.

What survives is narrower: "enumerate-and-execute halves confident errors over guessing". Its
cost is an ask-rate too high to ship. Making it shippable needs a better facet chooser.

## 5. Threats to validity

- **Real questions are model-authored variants** (T4/T5 written by a model from a gold
  question). This is not a human question distribution.
- **Gold for 54 dev items comes from the reference answer** (pre-run amendment 3), not the slot
  gold.
- **One decision model, one temperature (1.0).** A different pruning model could move every
  number.
- **The interpretation space is one hop** (anchor × facet). Multi-hop questions are scored
  against their first-hop slot gold.
- **The confirmation bank was already opened** by D-037/D-038. It confirms rather than seals.

## 6. What surprised us

- **Facet pruning fails even with the identifier given.** The decider discards the right
  relation for about a third of questions that name their entity by ID. The tests had pointed
  at entity grounding as the risk, not this.
- **Two defects in the shipped Gremlin `expand`** (see ISSUES.md). Every CAPEC hierarchy facet
  returns nothing in the shipped primitive.
