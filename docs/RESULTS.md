# Ariadne — Research Results

This page holds the research detail that used to sit in the top-level
[README](../README.md). The README covers what Ariadne is, how it works, and how to run it;
this page covers what was measured, how to reproduce it, and where the work stands.

> **Quote figures from [`research/CURRENT.md`](research/CURRENT.md), not from this page.**
> This page is a hand-written summary of the record in [`research/`](research/README.md);
> `make check-docs` fails the commit if it quotes a figure the record has retracted.

**Contents** — [Research Record](#research-record) · [What Actually Runs](#what-actually-runs) · [Results](#results) · [Reproducing the Results](#reproducing-the-results) · [What the templates buy](#what-the-templates-buy) · [Status](#status)

## Research Record

This is a research repository. All experiments, results, figures, and findings
live in [`docs/research/`](research/). Nothing that will appear in a paper
is recorded anywhere else. Before running an experiment, read
[`docs/research/AGENT_INSTRUCTIONS.md`](research/AGENT_INSTRUCTIONS.md).

## What Actually Runs

Ariadne is **deterministic by default, with LLM seams that are opt-in and individually backstopped**. This is a design decision the project's own evaluation supports (see [Results](#results)), and the table below names each seam and its default in the detail the [architecture diagram](assets/architecture.svg) only labels:

| Stage | Default behavior | LLM seam |
|---|---|---|
| **Planning** | Deterministic drafter: intent classified by a closed regex taxonomy, sources and entities matched against schema labels from the source cards, plan checked by a deterministic self-eval gate ([`utils/planner/`](../utils/planner/)) | `ARIADNE_LLM_ENABLED` (default `false`) swaps in an LLM drafter, always backstopped by the deterministic one; `--plan-llm` / `--query-llm` enable it per invocation |
| **Question rewriting** | **A model may canonicalise the question before planning — but only when the question cites no identifier, and it may never choose the entity.** `ARIADNE_REWRITE` + `ARIADNE_REWRITE_MODEL` + `ARIADNE_REWRITE_ONLY_WITHOUT_ID` + `ARIADNE_REWRITE_REQUIRE_RESOLVED_ANCHOR`, shipped on 2026-09-15 ([`D-034`](research/DECISIONS.md), [`D-035`](research/DECISIONS.md)). The stage fills a fixed intent form; the model only ever picks an index out of a candidate list it cannot add to ([`utils/planner/canonical.py`](../utils/planner/canonical.py), [`rewrite_llm.py`](../utils/planner/rewrite_llm.py)). **Since 2026-09-16 four deterministic mechanisms sit around it** ([`D-037`](research/DECISIONS.md), plan [`2026-09-15-open-question-correctness`](plans/2026-09-15-open-question-correctness.md)): a one-word entity name binds only when the question writes it as a name, so "stolen credentials" no longer anchors on the sub-technique named *Credentials* (`ARIADNE_EXACT_NAME_DISTINCT`, [`EXP-2026-09-023`](research/experiments/EXP-2026-09-023-anchor-hygiene-and-q59/)); a relation template with no anchor abstains instead of scanning the catalogue (`ARIADNE_UNANCHORED_RELATION_ABSTAINS`); an entity's name is looked up across every source **before** a dataset is chosen, with the router as the tie-break (`ARIADNE_ANCHOR_BEFORE_ROUTING`, Q59); and the bound form is executed as a plan rather than rendered to English and parsed again (`ARIADNE_FORM_EXECUTE`, [`EXP-2026-09-025`](research/experiments/EXP-2026-09-025-direct-form-execution/)). Measured together against the 2026-09-15 tree on the exposed bank: questions that name an entity without its identifier go **0.3267 → 0.3762** `records_exact` and 0.6223 → 0.7042 recall, every catalogue dump on every tier is gone, wrong-entity falls at T3 and T6 answers nothing wrong; questions that keep the identifier are **byte-identical**. On the sealed, entity-held-out bank the same tier goes 0.6500 → 0.7000. Paraphrased and description-only questions still answer nothing by default: the reranked, disclosed acceptance that would answer them was measured at a wrong-entity rate of 0.35 on the exposed bank and is kept off ([`D-038`](research/DECISIONS.md), [`EXP-2026-09-028`](research/experiments/EXP-2026-09-028-disclosed-anchor-acceptance/)) | The model rung is the seam; `ARIADNE_REWRITE_MODEL=0` keeps the deterministic fill alone, and `ARIADNE_REWRITE=0` restores the pre-2026-09-15 behaviour byte-for-byte. Every 2026-09-16 mechanism is one flag, default off in code |
| **Query construction** | **Deterministic on every shipped path.** An if-cascade over **29 distinct query-template identifiers** (20 in the Cypher builder, 14 in the Gremlin builder, 5 shared), of which **20 are exercised by the 120-question bank**; `ambiguous-name` and `unanchored` are refusal outcomes rather than queries. Derived on 2026-09-09 and recorded in [`EXP-2026-07-011`](research/experiments/EXP-2026-07-011-portability-audit/) A-1. Each is validated against the source card before execution ([`utils/specialists/cypher/builder.py`](../utils/specialists/cypher/builder.py), [`gremlin/builder.py`](../utils/specialists/gremlin/builder.py)). Counts derived mechanically by [`docs/plans/robustness/_overnight/derive_templates.py`](plans/robustness/_overnight/derive_templates.py), not read off prose | **Off by default, and it exists only as a baseline.** `SPECIALIST_LLM_QUERY_BUILDER` (default `false`) hands a model the schema and lets it write the Cypher or Gremlin itself ([`utils/specialists/llm_builder.py`](../utils/specialists/llm_builder.py)). It was built to be measured against, not to be run: it scores **0.5000** where the template cascade scores **0.9467** on the same unseen questions |
| **Retrieval loop** | `assess → re-plan → specialists`, capped at `ORCH_MAX_HOPS` — **code default 5, and the committed `.env` now ships `5` as well.** It pinned `1` until 2026-09-14, which made the loop inert on a default local run while every recorded figure was produced at `5` — so the committed default described no measured configuration ([`EXP-2026-09-020`](research/experiments/EXP-2026-09-020-plan-source-crossed/)). Deterministic sufficiency judge over join closure ([`utils/orchestration/`](../utils/orchestration/)) | `ORCH_ASSESS_MODE=llm` selects a "what's missing" critic, but nothing injects one today ([`utils/orchestration/main.py`](../utils/orchestration/main.py) builds the assess node with no `critic=`), so the mode degrades to the deterministic judge and records the fallback; `ORCH_CHASE_FACETS` (default off) extends the frontier to un-fetched facets |
| **Synthesis** | **Claims are composed deterministically on every shipped path** and every one is checked against the retrieved evidence by an unconditional verifier — uncited or ungrounded claims are cut, honest empties become abstentions carrying the executed query as proof ([`utils/synthesis/`](../utils/synthesis/)) | `ARIADNE_LLM_ENABLED` (default `false`) lets an LLM rewrite the **narrative prose** over the already-verified claims; it cannot add a claim. In the workbench this is the **"Plain prose" toggle**, per question and off by default, and it is deliberately *separate* from the drafter toggle: `drafter: "llm"` sets the planner, specialist and synthesis seams together, so asking for readable prose through it also hands query construction to a model. The answer records `narrative_source` so a reader can see which wrote the sentence. This seam is the one measured not to change a fact — 284/284 claims byte-identical to the model-free control, zero changes to identifiers, citations or verdicts, +0.0000 retrieval coverage ([`EXP-2026-09-019`](research/experiments/EXP-2026-09-019-small-model-generic/) Step 3) — at roughly 1,340× the deterministic composer's wall time. `SYNTHESIS_LLM_CLAIMS` (default `false`) lets a model *propose* claims — kept as an instrument, never as a default, because it is 67× slower and loses 0.1367 of grounding. It is the only configuration in which the verifier's gates have anything to cut |

Every LLM-off path is byte-reproducible, which is what makes the committed evaluation reports citable.

## Results

> **Quote from [`docs/research/CURRENT.md`](research/CURRENT.md), not from this section.**
> The record holds every experiment ([`INDEX.md`](research/INDEX.md)), the
> claims ledger with statuses ([`CLAIMS.md`](research/CLAIMS.md)), and every
> figure the record has withdrawn together with its replacement. This section is a
> hand-written summary; `make check-docs` fails the commit if it quotes a figure
> the record has retracted.

**Three controlled comparisons, none of which a system that generates its queries with a language model could make cleanly.** All judged figures below name their grader; question sets are the 284-question development half and the 288-question sealed holdout of a bank built to cover every question shape the sources support.

| Comparison | Current figure | Record |
|---|---|---|
| **Hand-written templates vs schema-derived construction** (the primary result) | The template-free path wins, and after the 2026-09 repair it wins by more: **0.9005 vs 0.5525** on 282 questions sealed before use and never graded before (gap **0.3480**, `qwen38-27B-v2`, both counterbalanced positions, zero fabricated mappings on either arm). A second 288-question bank reproduces it at 0.8987 vs 0.5443 — within 0.003 on disjoint sets. The earlier pre-repair reading of this comparison was 0.6569 vs 0.4946. The template path is only 0.01 s/answer faster. **This comparison holds the retrieval plan fixed**, and [`EXP-2026-09-020`](research/experiments/EXP-2026-09-020-plan-source-crossed/) shows it does not transfer to the planner the workbench actually runs — see the row below | [`EXP-2026-09-018`](research/experiments/EXP-2026-09-018-correctness-repair/), [`EXP-2026-09-005`](research/experiments/EXP-2026-09-005-post-repair-arm-comparison/), [`EXP-2026-09-007`](research/experiments/EXP-2026-09-007-holdout-spend/) |
| **Templates vs a language model writing the queries** | Templates ahead: **+0.1147** [+0.0653, +0.1645] on the development half and **+0.0822** [+0.0362, +0.1308] on the holdout under one grader family; positive but not significant under the second (+0.0696 [−0.0024, +0.1450]; +0.0643 [−0.0080, +0.1333]). The model-written arm is stable across seeds (sd 0.0089) | [`EXP-2026-09-007`](research/experiments/EXP-2026-09-007-holdout-spend/), [`EXP-2026-09-006`](research/experiments/EXP-2026-09-006-cross-family-august-regrade/), [`EXP-2026-09-009`](research/experiments/EXP-2026-09-009-llm-query-seeded-repeats/) |
| **Federating two stores vs merging both catalogues into one** | No demonstrable accuracy difference: merged minus federated **−0.0587** and **−0.0520** over eight named grading passes, inside the ±0.06 sampling floor at n=30, and the same under a second grader family. The case for federation is structural: merging required rewriting **1,083 of 9,138 nodes**; federation rewrote none, and a third live source loaded unmodified beside both catalogues | [`EXP-2026-08-009`](research/experiments/EXP-2026-08-009-merged-graph-counterfactual/), [`EXP-2026-08-017`](research/experiments/EXP-2026-08-017-federation-isolation/), [`EXP-2026-08-013`](research/experiments/EXP-2026-08-013-tri-source-federation/) |
| **A model narrating the answer vs no model at all** | No measurable gain, and a large cost. On the sealed set **0.8991 with an LLM narrator against 0.9005 with every seam off** — inside grader noise. The narrator is measurably *faithful*: across 284 answers its claims are byte-identical to the model-free control 284/284, with zero changes to identifiers, citations or verdicts and **+0.0000** on retrieval coverage. What it costs is time — **66.82 s/answer against 0.05 s**, roughly 1,340× | [`EXP-2026-09-018`](research/experiments/EXP-2026-09-018-correctness-repair/), [`EXP-2026-09-019`](research/experiments/EXP-2026-09-019-small-model-generic/) |
| **Which engine wins where the workbench actually stands** | The deployment question, and the one the row above bounds. Crossing engine × plan source on 284 questions: given an authored plan, primitives lead templates by **+0.2184** (separable); at the real planner that falls to **+0.0261 and is not separable**, with primitives returning nothing on 85 questions against templates' 55. **Interaction −0.1923** — unlike the model seam, these factors interact. The effect changes sign by tier (templates win easy −0.1586 and adversarial −0.1389; primitives win hard +0.0659 and medium +0.1127), so the evidence supports **routing between the two engines, not replacing one** | [`EXP-2026-09-020`](research/experiments/EXP-2026-09-020-plan-source-crossed/) |
| **An authored retrieval plan vs the system planning for itself** | The one comparison the headline figures do *not* win. Both 0.90 arms replay a human-authored plan; letting the planner produce the decomposition costs **−0.3814** gold coverage (paired, n=284, SE 0.0262). On **77 of 284 questions the planner retrieved nothing where the authored plan retrieved records, and the reverse never happened once.** Worst on chained and cross-catalogue questions (−0.50, −0.55) | [`EXP-2026-09-019`](research/experiments/EXP-2026-09-019-small-model-generic/) |

What the design costs is measured too, and recorded rather than summarized here: co-authorship
bias between questions written with and without sight of the templates, the vocabulary cliff under
paraphrase, 240/240 blocked on the safety gate after 15 live bypasses were found and closed, and
which local graders can resolve a 0.03 difference at all. Against two published external
benchmarks, scored against an oracle graph read rather than against 1.0, the cascade reaches
recall 0.7633 against a ceiling of 0.9863.

**The limit that matters most, stated plainly: every headline figure above replays a retrieval
plan derived from the answer key.** A bank entry is generated from a `spec`, and that one object
produces three things — the question text, the plan, and the expected answer
([`spec_bank.py`](../utils/specialists/evalset/spec_bank.py) transcribes each plan leg
straight from `spec.steps`). So replaying it hands the system the traversal that *defines* the
correct answer. 0.9005 therefore measures something real and separable — **given a correct
traversal, does the engine execute it and state the results faithfully** — and it is what makes the
arm comparisons valid, since every arm receives the same plan. It is **not** a figure for answering
a question, and nothing here may present it as one. The figure for that is the system finding its
own path: **0.4797**. Closing the gap is the project's critical path, not a footnote to it.

Four further limits carry across all of it: every question is anchored, so open-ended asks are
unmeasured; the development catalogue was co-authored with the system; no published external
system has been run as a baseline; and the judge is a model, so every figure names its grader.
[`CURRENT.md`](research/CURRENT.md) holds each of these with its experiment.

### Earlier measurements

A seven-arm study over a 120-question catalogue was run in July and is kept as history in
[`docs/evaluation/2026-07-26/`](evaluation/2026-07-26/README.md). It was graded by a model
that no longer serves the endpoint, on questions co-authored with the templates, and its headline
finding has since been refuted by the comparisons above. Two of its findings still stand and drove
the defaults: LLM planning is where the loss concentrates, and binding the narrator to the verified
claims rather than to raw evidence makes readable prose nearly free.

## Reproducing the Results

The full artifact description — hardware, software, data pins, per-experiment commands, and the
blockers — is [`docs/research/paper/ARTIFACT_APPENDIX.md`](research/paper/ARTIFACT_APPENDIX.md).
The short version is below. Every command was read from that appendix and the CLI parsers, and
each experiment directory under [`docs/research/experiments/`](research/experiments/) carries
its own `manifest.yaml` with the figures and the artifacts they were computed from.

**1. Prepare the data and both live stores.** Verify the fixtures are non-empty before going on:
an empty CAPEC fixture returns "no records" rather than failing, which silently invalidates every
CAPEC and federated result.

```bash
uv sync
uv run main.py --docker start
uv run main.py --download                 # checksum-verified; pins land in data/versions.json
uv run main.py --build attack && uv run main.py --build capec
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
```

**2. Run what reproduces exactly.** These paths call no model and are byte-reproducible. Arm A
completes in about 1.6 s on a commodity machine; the component and end-to-end deterministic
metrics reproduce to the digit.

```bash
uv run main.py --component-eval           # EXP-2026-07-008
uv run main.py --e2e-eval                 # EXP-2026-07-009, without a judge
ORCH_MAX_HOPS=5 uv run python -m utils.evaluation.experiment_untruncated \
  --arm deterministic --root docs/evaluation/experiments/untruncated-fixed --workers 4
```

Arms are selected with `--arm {deterministic,gold_llm,llm,llm_loop,gold_loop_llm,generic}`, and the
per-arm environment overlays are in `untruncated_env()` in
[`utils/evaluation/experiment_untruncated.py`](../utils/evaluation/experiment_untruncated.py). Set
`ORCH_MAX_HOPS` explicitly for any arm that measures the retrieval loop: `.env.example` ships `5`,
but a local `.env` copied before 2026-09-14 pins `1`, which makes the loop inert.

**3. What cannot be reproduced from this repository.** Every judged correctness figure depends on
independent grader agents — 120 per arm, 840 across the July study — so re-running the judging
needs an equivalent judge and will not return identical numbers. The **judgments themselves are
committed** under [`docs/evaluation/experiments/`](evaluation/experiments/) and hashed in each
experiment's `data/POINTERS.md`, so the aggregation is reproducible from the artifacts even where
the grading is not. There is also **no archival DOI**: a clone of this repository is currently the
only way to obtain the code.

**4. Check the record itself.**

```bash
make check-record                         # validator, index freshness, and the stale-quote scan
```

## What the templates buy

**Templates over free generation.** The specialists compile hand-written, card-validated templates instead of letting a model write Cypher or Gremlin. Query validity and safety adherence hold by construction, and a model given the same schema scores 0.5000 against the cascade's 0.9467.

⚠️ **But what the templates buy is not what this section used to claim.** A schema-derived generic path, with every hand-written template disabled, judges *level* with the cascade on ATT&CK and CAPEC and beats it by roughly 0.61 on a schema nobody wrote templates for. The templates hold **precision and provable abstention on the schema they were written for** — which of several schema-valid readings the analyst meant — and that advantage reverses off it. The claim that the templates hold the accuracy (`C-003`) is **refuted** in the project's own ledger and superseded by `C-023`.

## Status

The data layer, the federated planning agent, both query specialists, the verifying synthesis agent, and the end-to-end pipeline integration are complete: one LangGraph `StateGraph` orchestrator ([`utils/orchestration/`](../utils/orchestration/), shared by the CLI and the API through `run_pipeline`/`iter_pipeline`) runs plan → dependency-sequenced specialists → assess → verified synthesis with per-stage latency. An analyst web workbench sits on top — chat, graph explorer, and evaluation dashboard.

Component-level evaluation (`--component-eval`) and end-to-end evaluation (`--e2e-eval`) are complete and committed, as is the controlled seven-arm study that produced the July table above. The Wk 14–15 technical documentation set is delivered: source card format ([`docs/source_cards.md`](source_cards.md)), agent interface contracts ([`docs/agent-interfaces.md`](agent-interfaces.md)), the query safety model ([`docs/query-safety.md`](query-safety.md)), and the openCypher/GQL migration guide ([`docs/migration-guide.md`](migration-guide.md), proposal Deliverable #6).

Since then the project has run **38 further experiments** (complete; the record holds 52 in all, six of them superseded) — blind holdouts, both baselines, external validation against two published benchmarks, a third live source with a declared cross-graph bridge, a 240-probe safety audit, and a 699-run paraphrase-robustness study. The record is [`docs/research/INDEX.md`](research/INDEX.md); the current outside assessment is [`docs/research/audit-2026-08-31.md`](research/audit-2026-08-31.md).

The two most recent close in September 2026 and change what the project recommends. [`EXP-2026-09-018`](research/experiments/EXP-2026-09-018-correctness-repair/) repaired five composer defects and measured the result against a concurrent control, a freshly sealed question set, and a regression bank: the schema-derived path reaches **0.9005** with no model anywhere in the answer path, against **0.5525** for hand-written templates, at 0.01 s/answer more. [`EXP-2026-09-019`](research/experiments/EXP-2026-09-019-small-model-generic/) crossed two questions nobody had crossed: a 2B narrator preserves every fact (284/284 claims byte-identical, +0.0000 coverage) but costs ~1,340× in wall time and cannot draft queries at all (0 working drafts of 17), while **letting the planner produce its own decomposition costs −0.3814**. [`EXP-2026-09-020`](research/experiments/EXP-2026-09-020-plan-source-crossed/) then crossed engine against plan source and found the decisive limit on all of it: **at the planner `app.py` actually runs, the engine advantage is +0.0261 and not separable from zero**, and the two factors interact at −0.1923. The primitive path remains what makes the system open-ended — templates cannot take an unanticipated question at all — but it is not a drop-in replacement, and the planner is the largest term in every cell. A four-page reader's summary of all three is [`docs/research/reports/2026-09-14-templates-primitives-and-the-planner.pdf`](research/reports/2026-09-14-templates-primitives-and-the-planner.pdf).

**Known open work**, in priority order, is [`docs/research/OPEN_QUESTIONS.md`](research/OPEN_QUESTIONS.md). The item that now leads the list is the planner gap: every headline figure replays an authored plan, so closing the −0.3814 — or separating how much of it is a worse decomposition from how much is the tighter per-plan bounds the self-planning arm inherits — is what turns a ceiling into an end-to-end result. Behind it: explaining why this project's failure distribution runs opposite to the only comparable published one (Q24), re-grading the headline comparisons with a cross-model panel, deciding whether the question banks emit executable gold queries (Q26), and the contamination control that has never been run.
