# PROTOCOL — EXP-2026-09-007 Spending the 288-question holdout

> Written 2026-09-05 11:00 EDT, **before any holdout answer from `generic` or
> `llm_query` existed and before any holdout judgment of any kind existed**.
> Sealed state verified the same morning by `scripts/holdout_seal.py`:
> bank `sha256:ad99afb1…`, 284 dev / 288 holdout, holdout questions
> `sha256:812ab787…`, **9,357 dev judgments seen and 0 holdout judgments**,
> `deterministic` the only arm to have answered any of it.

## Question

Six system defects and three measurement defects were found and fixed using the
**dev** half of this bank. Every headline in the paper — `generic` 0.6569,
`deterministic` 0.4946, `llm_query` 0.3781 — is measured on the 284 questions
that were used to find those defects.

**Are those figures a property of the system, or of the 284 questions?**

## What this holdout does and does not control for

Stated first, because overclaiming it is the most likely way this experiment
becomes misleading.

The 572 questions in `bank.json` were generated **by one generator in one pass**
(`claude-opus-5`, subagent path, seed 20260901) and split 284/288 by that seed.
The holdout is therefore a **random split of the same bank**, not an
independently authored set.

- **It does control for tuning to specific questions.** Nothing in the six
  repairs was allowed to see these 288. If the repairs were fitted to the dev
  items, the holdout will say so.
- **It does not control for co-authorship bias.** Both halves share an author, a
  vocabulary and a shape distribution. C-021's 0.0483 is measured elsewhere, on
  the August blind banks, and this experiment neither replaces nor strengthens
  it. **Do not report this holdout as evidence of generalisation to
  independently authored questions.** It is evidence of generalisation to
  *unseen questions of the same kind*, which is a narrower and still useful
  thing.

## Hypothesis

**H1 — ordering preserved.** `generic` > `deterministic` > `llm_query` on the
holdout, with every pairwise gap larger than the grader's own spread
(0.0036–0.0249 within family). This is the claim-bearing prediction.

**H2 — levels move little.** Each arm's holdout correctness lands **within 0.08**
of its dev value, and `deterministic` specifically drops **less than 0.05**. The
reasoning: the repairs were schema-level (a property-shape rule, a binding
ceiling, an identity overwrite, an anchor-resolution rule, two dispatch guards),
not question-level, so they should carry.

**H3 — the multi-hop reversal reproduces.** On D6 the template arm *leads* the
schema-assembled arm on dev (0.3548 against 0.0717). If that is real it appears
again here; if it was a dev artifact it will not.

**H4 — recall does not collapse.** Model-free `gold_in_evidence` on the holdout
is **no more than 0.05 below** its dev counterpart. Note the one prior
holdout-versus-dev comparison we have runs the *other* way: pre-repair
deterministic recall was **0.4683 on holdout against 0.4350 on dev**, holdout
*higher* by 0.0333. There is no evidence the holdout half is harder, and a naive
"the holdout will be worse" expectation is not supported by anything measured.

**H5 — abstention discipline holds.** Zero fabricated mappings on
`deterministic` and `generic`, matching every prior bank.

## Setup

Same code, same live stores, same configuration as the dev measurement.
**Any difference here would make the holdout test a different system than the
paper describes**, which is the one way to waste it.

- Stores asserted before the run: Neo4j **4,369 nodes / 27,669 edges**, Gremlin
  **6,374 vertices / 8,582 edges**.
- `deterministic` and `generic` take **no model in the answering path** and are
  byte-reproducible.
- `llm_query` runs the **settled configuration**: budget 32,768,
  `SPECIALIST_LLM_TIMEOUT_S=4096`, 16 concurrency, `ORCH_MAX_HOPS=5`,
  **no thinking cap**. The 512-token `LLM_THINKING_BUDGET` lever is wired but
  has never been verified against a live endpoint; it is deliberately **not
  used**, and is recorded as an untested lever rather than quietly enabled. The
  holdout must test the configuration the paper describes.
- **The scorer is frozen.** Two known scoring faults — abstention boilerplate
  crediting refusals, and the scorer recognising the source's identifier
  vocabulary rather than the graph's (worth 0.185 on the subset measured) —
  both *raise* scores and both stay unfixed here. Changing the scorer between
  the dev measurement and the holdout would destroy the only comparison this
  experiment exists to make. They are declared limitations, not oversights.

## Data

`docs/evaluation/composition/bank/bank-holdout.json`, 288 questions, cut from
`bank.json` and hashed (`812ab787…`) so the run can prove it answered the
questions sealed on 2026-09-05.

`deterministic` answered these 288 once before, on 2026-09-02, **model-free
only**, and the recall figure was published. That look was deliberate and is on
the record. It is not a violation of the seal, because the seal is about
*judgment*, and no holdout answer has ever been judged.

## Metrics

- **`correctness_by_arm`** — mean judged correctness, per arm, per grader
  family. Both grading positions averaged per case *before* averaging across
  cases, so an arm that lost a judgment in one pass is not scored on fewer
  questions than the others.
- **`dev_minus_holdout`** — per arm, paired at the bank level, with a percentile
  bootstrap (`utils/evaluation/stats.py::bootstrap_ci`, 2,000 resamples, seed
  1729). **This is the number the experiment exists to produce.**
- **`gold_in_evidence`** — model-free recall, reported **beside** judged
  correctness and never merged with it. Reweighted per shape by
  `meta.reweighting.census_instances`; pooled recall on this bank is a draw
  artifact, because the bank deliberately over-samples rare shapes.
- **`d6_margin`** — `deterministic − generic` on the multi-hop tier.
- **`fabricated_mappings`**, **`abstentions_with_proof`** — counts, per arm.
- **`arm_order_reversals`** between the two grader families, as in
  `EXP-2026-09-006`.

## Baselines

The dev half of the same bank, `EXP-2026-09-005`: `generic` **0.6569**,
`deterministic` **0.4946**, `llm_query` **0.3781** (0.3703 conditional on a
query being built). Same grader, same protocol, same two counterbalanced passes.

## Procedure

```bash
# 1. Seal, hash, and cut the holdout. Must print SEALED.
uv run python scripts/holdout_seal.py --write-bank

# 2. Gate: EXP-2026-09-006 must report zero arm-ordering reversals first.
#    A grader-family reversal means the instrument is in question, and the
#    holdout is not spent while the instrument is in question.

# 3. The two model-free arms — minutes, no model in the loop.
uv run python -m utils.evaluation.experiment_untruncated --arm deterministic \
    --bank docs/evaluation/composition/bank/bank-holdout.json --root <root>
uv run python -m utils.evaluation.experiment_untruncated --arm generic ...

# 4. llm_query — the settled configuration, one GPU, ~5 h.
# 5. Judge: 3 arms x 2 positions x 2 grader families = 3,456 judgments.
# 6. Roll up against the predictions above, including where they were wrong.
```

## What would falsify this

**H1 fails** if the arm ordering differs from dev. The paper's central
comparison would then be a property of the 284 questions it was measured on,
and every headline would have to be restated on the holdout instead.

**H2 fails** if any arm moves more than 0.08, or `deterministic` more than 0.05.
That would mean the six repairs were fitted to the dev items rather than to the
schema, and the honest report would be the holdout figure with the dev figure
labelled optimistic.

**H3 fails** if the D6 template lead does not reproduce. Then the most
interesting non-uniformity in the record is a 284-question artifact and must be
dropped rather than explained.

**H4 fails** if recall falls more than 0.05. Given the pre-repair comparison ran
the other way, that would suggest the repairs themselves are dev-specific.

**A predicted number that misses is reported as a miss.** This project has twice
predicted 47 and 23 repairs and delivered 2 and 14; saying so in the record is
what makes the rest of it worth reading.

## Stop conditions

- `scripts/holdout_seal.py` does not print `SEALED` → **do not run anything**.
- `EXP-2026-09-006` reports any arm-ordering reversal → **hold**, investigate,
  and write that up first.
- A store count does not match → **hold**; a holdout answered against a
  different graph is not comparable to the dev measurement and cannot be redone.
- Any arm completes fewer than 288 answers → that arm is recorded `not_run`.
  **A partially answered holdout is not a result**, and unlike every other run
  in this project it cannot simply be repeated.
