# Un-truncated Retrieval Experiment — Two Arms, 120 Questions Each

Same 120 golden questions, same order, same two graphs (ATT&CK/Neo4j 4,369 nodes; CAPEC/Gremlin 4,769 nodes). The **common** change to both arms lifts every retrieval, synthesis-evidence and judge-artifact cap so `describe`/`expand` return full neighbourhoods and synthesis receives the whole evidence set. The **independent variable** is the LLM: Arm A runs no LLM at all, Arm B runs LLM planning + LLM synthesis. Each arm was graded case-by-case by 120 independent Sonnet 5 agents (240 total) against the gold assertions *and* the full retrieved evidence.

## Headline

| Metric | Arm A — deterministic | Arm B — LLM-planned | Baseline (truncated) |
|---|---|---|---|
| correctness | **0.9500** | **0.0000** | 0.8946 |
| completeness | **0.9534** | **0.0000** | 0.8952 |
| faithfulness | **0.9979** | **0.0000** | 0.9558 |
| groundedness | **0.9992** | **0.0000** | 0.9575 |
| n graded | 120 | 0 | 120 |

**Verdicts**

| Arm | CORRECT | PARTIAL | INCORRECT | answers w/ hallucinations | total hallucinations |
|---|---|---|---|---|---|
| A — deterministic | 112 | 1 | 7 | 0 | 0 |
| B — LLM-planned | 0 | 0 | 0 | 0 | 0 |
| Baseline (truncated) | 91 | 27 | 2 | 11 | — |

## Deltas

| Metric | B − A | A − baseline | B − baseline |
|---|---|---|---|
| correctness | -0.9500 | +0.0554 | -0.8946 |
| completeness | -0.9534 | +0.0582 | -0.8952 |
| faithfulness | -0.9979 | +0.0421 | -0.9558 |
| groundedness | -0.9992 | +0.0417 | -0.9575 |

| Verdict | B − A | A − baseline | B − baseline |
|---|---|---|---|
| CORRECT | -112 | +21 | -91 |
| PARTIAL | -1 | -26 | -27 |
| INCORRECT | -7 | +5 | -2 |

## Retrieval volume actually pulled

| Arm | evidence records | related neighbours | mean answer coverage (gold ids surfaced) |
|---|---|---|---|
| A — deterministic | 1840 | 839 | 1.0000 (66 scorable) |
| B — LLM-planned | 0 | 0 | 0.0000 (0 scorable) |

## Weakest categories by mean correctness

### Arm A — deterministic

| Category | n | mean correctness | baseline | Δ vs baseline | verdicts |
|---|---|---|---|---|---|
| A-SCN | 1 | 0.10 | 0.85 | -0.75 | {"INCORRECT": 1} |
| C-SCN | 1 | 0.15 | 1.00* | -0.85 | {"INCORRECT": 1} |
| C-LKP | 5 | 0.24 | 0.88 | -0.64 | {"INCORRECT": 5} |
| C-HIE | 3 | 0.90 | 1.00* | -0.10 | {"CORRECT": 2, "PARTIAL": 1} |
| A-DET | 3 | 0.98 | 0.97 | +0.01 | {"CORRECT": 3} |
| F-FAN | 3 | 0.98 | 1.00* | -0.02 | {"CORRECT": 3} |
| F-CTM | 10 | 0.99 | 0.92 | +0.07 | {"CORRECT": 10} |

<sub>*Categories absent from the baseline's weakest table scored 1.00 there.</sub>

### Arm B — LLM-planned

Every category scored a mean correctness of 1.0.

## Every non-CORRECT case

### Arm A — deterministic — 8 of 120

| Case | verdict | corr | compl | faith | ground | hallucinations |
|---|---|---|---|---|---|---|
| A-SCN-01 | INCORRECT | 0.10 | 0.00 | 0.90 | 0.90 | 0 |
| C-SCN-01 | INCORRECT | 0.15 | 0.00 | 1.00 | 1.00 | 0 |
| C-LKP-01 | INCORRECT | 0.20 | 0.25 | 1.00 | 1.00 | 0 |
| C-LKP-02 | INCORRECT | 0.20 | 0.33 | 1.00 | 1.00 | 0 |
| C-LKP-04 | INCORRECT | 0.20 | 0.25 | 1.00 | 1.00 | 0 |
| C-LKP-03 | INCORRECT | 0.30 | 0.25 | 1.00 | 1.00 | 0 |
| C-LKP-05 | INCORRECT | 0.30 | 0.33 | 1.00 | 1.00 | 0 |
| C-HIE-03 | PARTIAL | 0.70 | 1.00 | 0.95 | 1.00 | 0 |

### Arm B — LLM-planned — 0 of 0

None.

## Hallucinations flagged

### Arm A — deterministic — 0

None flagged.

### Arm B — LLM-planned — 0

None flagged.

Per-case verdicts: `<arm>/answers/<id>.judgment.json`; answers + full retrieved evidence: `<arm>/answers/<id>.json`; run configuration: `<arm>/manifest.json`.
