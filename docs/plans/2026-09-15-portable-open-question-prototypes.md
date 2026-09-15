# Portable question answering: discovery before commitment

## 1. Introduction

The target is an analyst who does not know a catalogue's vocabulary. Improve
entity discovery, intent interpretation, and evidence completeness independently,
using source cards and graph records as the portable interface. A ranked search
hit is a hypothesis; only executed graph evidence can support an answer.

This session delivers a design and an offline, executable discovery experiment.
It does not change workbench defaults. Findings belong in
`EXP-2026-09-022-portable-candidate-discovery`; this plan contains no results.

## 2. Gaps & unanswered questions

- **Future domains:** assume unrelated domains as well as new cyber sources.
  No technique names, identifier regexes, or benchmark-derived synonyms in the
  new retrieval core. A small non-cyber fixture checks that contract.
- **Deployment shape:** start from canonical graph exports already available.
  A live backend can implement the same search interface later. Source cards
  describe schema; record-level descriptions must come from graph data.
- **Semantic retrieval:** first measure a model-free lexical baseline. Optional
  embeddings or a bounded language-model reranker are later ablations, not
  prerequisites for adding a source. The current architecture has no vector
  store, and this prototype preserves that property.
- **Accuracy bar:** retain exact answer completeness, report record precision
  and recall beside it, and add independent judgments for open-ended answers.
  Candidate recall is a different metric and cannot satisfy an answer bar.
- **Ambiguity:** preserve multiple candidates and their source identities.
  Choosing when to ask a user rather than answer needs calibration on ambiguous,
  answerable, and unanswerable requests. No uncalibrated score becomes confidence.

## 3. Hierarchical steps for this session

### Step 1 — Record the design and experiment before running

- **Locations:** this plan; `docs/research/experiments/EXP-2026-09-022-portable-candidate-discovery/`.
- **Rationale:** compare competing mechanisms, including failures, without
  adjusting thresholds after inspecting results.
- **Validation:** `make validate-research`, `make check-docs`.
- **Action:** validate, then commit locally as Portable discovery (1/3).
  Push only if the operator explicitly requests it (global-project-rules).

### Step 2 — Implement portable discovery and its diagnostic harness

- **Locations:** `utils/planner/discovery_candidates.py`,
  `utils/planner/tests/test_discovery_candidates.py`,
  `scripts/prototype_candidate_discovery.py`.
- **Rationale:** exact IDs/names across sources address lookup ordering; separate
  name/property searches test T4/T5 discovery; one-hop graph context tests whether
  descriptions on attached nodes help find their parent entity.
- Candidate identity is `(dataset, canonical record id)`. Cards declare valid
  labels/properties, identity keys, and edge patterns. Return matched fields and
  graph context as inspectable retrieval reasons; never collapse candidates into
  answer records or merge cross-source identities by spelling.
- Compare pooled lexical search, separate fields with rank fusion, and graph
  context with rank fusion on the same corpus. Keep exact matching separate.
- **Validation:** focused unit tests for source collisions, unknown labels,
  missing text, alias discovery, graph direction, and unrelated-domain transfer.
- **Action:** validate, then commit locally as Portable discovery (2/3).

### Step 3 — Measure and write the research recommendation

- **Locations:** experiment `data/metrics.json`, `manifest.yaml`, `RESULTS.md`,
  `DESIGN.md`; raw predictions under `docs/evaluation/experiments/`.
- **Rationale:** locate headroom before paying for semantic search or reranking.
  Use question text alone for retrieval; gold anchors are scorer-only data.
- Report each tier separately, candidate recall at multiple budgets, missing
  gold anchors, exact-match ambiguity, and negative-control candidate presence.
  Explicitly distinguish a replay diagnostic from independent generalization.
- **Validation:** focused tests, `make index`, `make validate-research`,
  `make check-docs`, `git diff --check`.
- **Action:** validate, then commit locally as Portable discovery (3/3).

## 4. Deliverables

| Deliverable | Location |
|---|---|
| Portable discovery prototype | `utils/planner/discovery_candidates.py` |
| Reproducible diagnostic runner | `scripts/prototype_candidate_discovery.py` |
| Small cross-domain contract tests | `utils/planner/tests/test_discovery_candidates.py` |
| Measured ablations and limitations | Experiment `RESULTS.md` and `data/metrics.json` |
| Prioritized architecture and future experiments | Experiment `DESIGN.md` |
