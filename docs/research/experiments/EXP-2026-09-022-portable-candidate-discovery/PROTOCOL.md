# PROTOCOL — EXP-2026-09-022

## Question
Can portable search over cards and canonical graph records surface the intended
entity when the question lacks a name or identifier? Does attached graph text
help beyond record text? This is a discovery diagnostic, not an answer run.

## Hypothesis
Exploratory — no prior quantitative hypothesis. Source-independent exact search
should remove lookup-order restrictions; separate lexical views may improve
candidate coverage, while graph context may add noise. Keep negative results.

## Setup
CPU-only, no model, no live database writes. Read cards and canonical records.
Index all card-valid nodes with canonical identity and searchable text, including
attached nodes that the old name index excludes. All arms use the same corpus.
Identity is source plus canonical ID; public identifiers are scorer aliases,
never globally unique keys. Card identity properties supply identifier values.
Do not use bank, tier, gold anchor, gold label, or gold question in retrieval.

## Data
Use the existing variants and slot_gold files in variants-2026-08-29. This bank
has been exposed in prior work; it is diagnostic, not a new holdout. Record all
file hashes. Gold public IDs are mapped to canonical IDs only by the scorer.
Explicitly report anchors absent from the corpus and cases without anchor gold.
T6 invented anchors do not inherit their parent question's real anchor gold.

## Metrics
Per tier: mean fraction of gold anchor identities present among top k candidates,
k in {1,5,10,20}; fraction of cases with all anchors at k; corpus anchor coverage;
source-independent exact candidate coverage and ambiguity. No-anchor cases have
null recall and are excluded with their count reported. T6 reports candidate
presence only: a suggestion is not an accepted answer or a false-answer rate.
Latency describes this local in-memory prototype, not deployed graph latency.
No answer recall, records_exact, or judged correctness is measured here.

## Baselines
- pooled: name repeated three times plus the same declared string properties.
- fields: independent name and property BM25 rankings, equal reciprocal-rank
  fusion (constant 60), each view contributes its top 100 candidates.
- graph: fields plus a one-hop neighbor-name/property ranking, equal fusion.
Exact ID/name matches are prepended separately in every arm. Preserve multiple
exact matches; no automatic acceptance or source-name tie break. The candidate
budget is global across sources. Exclude schema-word-only name matches.
BM25 k1=1.5, b=0.75; reuse the existing generic lexical tokenizer. Graph text is
capped at 32 neighbors per node, sorted by canonical ID, 512 characters per
neighbor; keep direction and provenance. Text extraction omits non-string values
and undeclared properties. No hand-written cyber synonyms or label filters.

## Procedure
1. Commit this protocol before implementation and measurement.
2. Implement and test the retrieval core and scoring harness; commit code.
3. Run `uv run python scripts/prototype_candidate_discovery.py` once, persist
   predictions and metrics, and report every arm without retuning.
4. Generate results tables, record limitations, validate research/docs, commit.

## What would falsify this
There is no ship hypothesis. A field or graph arm that fails to improve candidate
recall over pooled search supplies no evidence to adopt it. High top-k recall
with weak top-1 retrieval supports a reranking experiment, not automatic entity
binding. A non-cyber fixture needing dataset-specific code falsifies the portable
interface claim. No result on this exposed bank establishes unseen-domain QA.
