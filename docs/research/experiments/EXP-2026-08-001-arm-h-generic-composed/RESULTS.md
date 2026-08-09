# RESULTS — EXP-2026-08-001 Arm H — generic primitives with composition, join projection and anchor resolution

## 1. Headline

**Gold-in-evidence 1.0000 over 120 questions — every gold identifier the
catalogue asks for now reaches the retrieved evidence, in every question.**
Against Arm G's 0.7191: 120/120 fully covered (was 73), 424 gold ids recovered,
**0 questions regressed**.

**This arm has no correctness number and must not be given one.** It was scored
mechanically from the artifacts; no judge ran. See §5.

The hypothesis in `PROTOCOL.md` — that Arm G's gap is a **capability** gap in the
schema-driven layer rather than a **domain-knowledge** gap — is supported on the
retrieval half of the question. Not one MITRE-specific literal was added to
either query builder; every new primitive is driven by the source card, the
derived schema registry, or the declared join-key registry.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), itself computed by
`utils/evaluation/retrieval_coverage.py` over the committed artifacts.

| Metric | Arm G | **Arm H** | Delta |
|---|---|---|---|
| `gold_in_evidence` **(primary)** | 0.7191 | **1.0000** | **+0.2809** |
| `gold_in_evidence_scorable` | 0.6595 | **1.0000** | +0.3405 |
| Questions fully covered | 73 / 120 | **120 / 120** | +47 |
| Gold ids never retrieved | 424 | **0** | −424 |
| Dependent hops skipped for want of seeds | 56 | **7** | −49 |

The seven remaining skipped hops are all `F-NEG`, where the correct behaviour is
to find no mapping and abstain. Arm G scored those correctly too; nothing
regressed there.

| Paired against Arm G | Value |
|---|---|
| Questions compared | 120 |
| Improved | 47 |
| **Regressed** | **0** |
| Gold ids recovered | 424 |
| Gold ids lost | 0 |

| Cost / volume | Arm G | Arm H |
|---|---|---|
| Wall clock (120 questions) | 914.8 s | 1574.1 s |
| Evidence records | 252 | 950 |

Retrieval is **not** what got slower: the heaviest executed query in the run
took 40 ms. The extra wall clock is the LLM narrator working over 3.8× more
evidence.

Per-category coverage is in
[`tables/tab-coverage-by-category.md`](tables/tab-coverage-by-category.md). The
categories that were worst in Arm G are the ones that moved:

| Category | Arm G | Arm H |
|---|---|---|
| `F-CWE` | 0.000 | 1.000 |
| `A-DCA` | 0.100 | 1.000 |
| `F-CTM` | 0.101 | 1.000 |
| `F-FAN` | 0.167 | 1.000 |
| `F-CTT` | 0.253 | 1.000 |

## 3. Figures

None generated. The study's cross-arm figure plots judged correctness, and this
arm has none; adding it would invite exactly the category error §5 warns about.

## 4. Interpretation

Arm G's −0.3568 was read as evidence for C-003 — that accuracy lives in the
hand-written templates. This experiment splits that claim in two.

The **retrieval** half does not survive as stated. Every retrieval failure Arm G
suffered was closable from declarations the repository already had:

* the **join-key registry** already declared `MAPS_TO`, `TaxonomyEntry` and
  `entry_id`; nothing was walking them;
* the **schema registry** already declared every `(rel, direction, neighbour)`
  facet, so `Technique → DetectionStrategy → Analytic` is an ordinary
  breadth-first search;
* the **anchor label** was being guessed from `labels[0]`, the order the planner
  happened to list entities in, rather than resolved.

What remains genuinely template-shaped is **precision**, and it is now the
sharper finding. Two primitives answer correctly but too broadly, and neither
can be narrowed from the schema (see `ISSUES.md`):

* `generic_intersect` returns 29 records for A-MC-01 where gold wants 7 — the
  sub-techniques are also mitigated by M1027 and also under TA0006, and nothing
  in the schema says "techniques" excludes them;
* the hierarchy walk returns descendants alongside ancestors, because nothing in
  the schema says which direction of a self-loop means "up".

That is a much more precise account of what a template buys than "accuracy":
templates encode **which of several schema-valid readings the analyst meant**.
A generic layer can find everything; it cannot know what to leave out.

## 5. Threats to validity

* **No judged correctness.** The primary metric here is retrieval. Judging needs
  120 independent Sonnet 5 agents and was not run. **Do not place Arm H on the
  arm-comparison figure, and do not compare 1.0000 against any arm's
  `correctness`.** Until a judge run exists, the only defensible statement is
  about what reached the evidence.
* **`gold_in_evidence` saturates.** At 1.0 the metric has no headroom and cannot
  distinguish a good answer from an over-broad one — which is precisely where
  the two over-returning primitives would show up. A ceiling result on a
  recall metric is weaker evidence than its face value suggests.
* **Not a clean pre-registration.** Spot checks over 30 of the 120 questions
  preceded the protocol. See `ISSUES.md`.
* **The catalogue is still co-authored and still has no holdout.** This
  experiment does not address C-013 and does not claim to. A generic layer
  reaching full coverage on a question set written alongside the templates says
  nothing about an unseen one.
* **All 120 questions are anchored.** Nothing here measures open-ended questions.
* **Single run, one model, seeds unrecorded.** As with every arm of the study.
  `gold_in_evidence` is deterministic given the plan, but the plan comes from an
  LLM planner, so it is not fully deterministic across runs.
* **It took three runs to get here.** The first full run regressed 8 CAPEC
  hierarchy questions to zero retrieval — the shared Gremlin validator counts
  every traversal step in a query against `max_traversal_depth`, so a wide union
  was rejected before execution. The paired per-question regression check is the
  only reason that was caught rather than absorbed into a rising mean.

## 6. What surprised us

That it went to exactly 1.0. The expectation recorded in `PROTOCOL.md` was
`≥ 0.97` with up to five `incomplete_retrieval` cases surviving. That every
category closed completely is a stronger result than predicted and, for that
reason, a result to be more suspicious of rather than less — §5 says why.

## 7. Follow-ups

* **Judge this arm** under the same protocol as Arms A–G. Until then the
  precision cost of the two over-returning primitives is unmeasured, and it is
  the one number that would make this experiment conclusive.
* **Qualify C-003.** Its current wording attributes the whole −0.3568 to the
  templates. The retrieval component is now shown to be a capability gap. The
  claim should be re-scoped to precision and disambiguation, with this
  experiment as the evidence. Not edited here — a `supported` claim's rewording
  is an operator decision.
* C-012 is untouched. No LLM writes Cypher or Gremlin in this arm either.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm generic --root docs/evaluation/experiments/untruncated-generic-fixed --workers 4
uv run python -m utils.evaluation.retrieval_coverage \
  --root docs/evaluation/experiments/untruncated-generic-fixed --arm generic \
  --reference-root docs/evaluation/experiments/untruncated-generic
```

`data/metrics.json` and `tables/tab-coverage-by-category.md` are both generated
from the artifacts by the second command's library functions; neither holds a
hand-entered number.

The artifact-directory hashes recorded in [`data/POINTERS.md`](data/POINTERS.md)
reproduce with:

```bash
find docs/evaluation/experiments/untruncated-generic-fixed/generic -type f -name '*.json' | sort | xargs cat | sha256sum
```
