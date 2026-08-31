# Evaluation — Index

Ariadne carries several evaluation reports written at different times against
different configurations. This file says which is which, so no number gets
quoted out of the run that produced it.

> 🛑 **This directory is the raw-artifact store, not the research record.**
> Since 6 August the record of what was measured and what it means lives in
> [`../research/`](../research/README.md) — 31 experiments, a claims ledger, a
> decisions ledger, and two dated external audits. **Several conclusions below
> have been overturned by experiments recorded there**, in particular the arm
> ordering: the claim that the hand-written templates hold the system's accuracy
> is `refuted` in [`../research/CLAIMS.md`](../research/CLAIMS.md). Read the
> ledger before quoting anything in this directory.

## Historical reports (raw artifacts)

| Report | What it measures | How to regenerate |
|---|---|---|
| [`2026-07-26/README.md`](2026-07-26/README.md) | **The July arm study**, superseded as a description of the system and kept as the record of what was measured. Seven full runs over the 120-question catalogue, each answer graded by an independent Sonnet 5 agent. Deterministic planning + deterministic synthesis (Arm A) scores 0.9972 / 120 CORRECT / zero hallucinations; LLM planning is the largest single regression. Also lists the eight defects found and fixed, and the limitations. | `utils/evaluation/experiment_untruncated.py` per arm, then the judge workflow — see §6 of that file |
| [`2026-07-26/portability.md`](2026-07-26/portability.md) | ⚠️ **Superseded by measurement.** A code-reading audit of which layers are schema-agnostic. It counted 25 distinct template identifiers (the builders now declare 29 literals plus one f-string yielding two more) and it classified the **planner as portable, which `EXP-2026-08-011` showed it is not**. Read that experiment instead. | Audit, not a run |
| [`component-evaluation.md`](component-evaluation.md) / `.json` | Planner (source selection, sub-question quality, schema adherence) and specialists (query validity, execution accuracy vs snapshot gold, safety adherence, latency). Deterministic; no LLM judge. | `uv run main.py --component-eval` |
| [`e2e-evaluation.md`](e2e-evaluation.md) / `.json` | The four `goals.md` end-to-end metrics — cross-source answer accuracy, CAPEC→ATT&CK mapping recall, provenance correctness, analyst inspectability — plus the opt-in LLM judge. | `uv run main.py --e2e-eval [--judge]` |
| [`answers/`](answers/) | The 120 saved end-to-end answers and their judgments backing `e2e-evaluation.md`. | `uv run main.py --e2e-generate` |
| [`experiments/`](experiments/README.md) | Per-question answer + evidence + verdict artifacts for each arm of the 2026-07-26 study. | See that index |

## Superseded

| Report | Status |
|---|---|
| [`archive/independent-eval.md`](archive/independent-eval.md) | The first independent cross-model grading pass — 0.8946 correctness, 91/27/2, 11 answers with hallucinations. This is the **"Committed baseline" row** of the 2026-07-26 table: the "before" the eight defect fixes were applied to. Its numbers are historically correct and currently obsolete. |
| [`archive/independent-eval-analysis.md`](archive/independent-eval-analysis.md) | The failure analysis that produced the four fixes merged in `df700ee`. All four shipped. |

## Not committed

`docs/evaluation/golden/` is git-ignored run output from the decoupled
run → judge → report harness (`uv run main.py --golden-eval`). It grades a
different configuration from everything above — the **agentic** path, where the
LLM plans from raw question text and a local LLM grades correctness — so its
lower pass rate is measuring the LLM-planned arm, not the deterministic one, and
is consistent with the 2026-07-26 finding rather than in tension with it.
Regenerate it rather than citing a stale copy.

## The model behind `skynet`

🛑 **`skynet` is a relay alias, not a model, and it has been repointed at a
different model three times.** A report that says `skynet` is telling you which
*endpoint* answered, not which weights did. Every figure in this repository is
dated evidence about whatever was behind the alias on the day it was produced.

| Era | Served model | Notes |
|---|---|---|
| July 2026 — the seven-arm study | **Gemma 4 31B**, dense, quantisation never recorded | Arms B–G. Operator, 2026-08-04 |
| ~August 2026, exact start **unknown** | **Undetermined.** See below | ⚠️ `EXP-2026-08-007`, `-008` and `-009` fall in this window — the three experiments carrying C-012, C-015 and C-021 |
| 2026-08-24 | **`MIRALABS/Ornith-1.5-35B-A3B-W4A16-SYM`** — MoE (~3B active of 35B), 4-bit weights / 16-bit activations, 96,000-token context, 16-way concurrency at full context | `EXP-2026-08-018`, `-019`. Operator, from the serving side |
| **2026-08-31 — current** | **`qwen38-27B-v2`** | Read from the relay's own response envelope (`response.model`) on 2026-08-31. Quantisation, `max_model_len` and concurrency **not yet confirmed from the serving side** |

**How to find out what is actually serving, rather than asking:**

```bash
uv run python scripts/model_identity.py
```

It reports the upstream model each alias resolves to, by issuing a minimal
completion and reading the `model` field off the response. `/v1/models` is not
enough — the relay reports `skynet -> upstream_model: "auto"` because it
hot-swaps.

**Three consequences, all of which bind:**

1. **Never write `skynet` in a result.** Write model, quantisation and date
   together. `EXP-2026-08-018`'s manifest is the format to copy:
   `relay/Ornith-1.5-35B-A3B-W4A16-SYM@2026-08-24`.
2. **No figure crosses an era boundary.** The July arm table and the August
   judged comparisons were produced by different weights and are not comparable
   as levels. Neither is the *grader*, which runs on the same relay.
3. **The middle row is the expensive one.** Which model graded the
   19–21 August runs is not determinable from the record. Those runs carry three
   live claims. See [`../research/OPEN_QUESTIONS.md`](../research/OPEN_QUESTIONS.md)
   Q12 and the migration plan at
   [`../plans/2026-08-31-model-migration-qwen38.md`](../plans/2026-08-31-model-migration-qwen38.md).

**On the context window specifically**, the repository has given three different
answers, none of them authoritative. They are listed here so the history stays
visible and so none of them gets quoted as settled:

| Figure | Where it appeared | What it actually was |
|---|---|---|
| "unknown from the client side" | [`../research/OPEN_QUESTIONS.md`](../research/OPEN_QUESTIONS.md) Q11 | The honest answer, and still the correct one |
| "~64k" | [`2026-07-26/README.md`](2026-07-26/README.md) (limitations) | An estimate, never verified against the server |
| `48000` | `.env` (`EVAL_LLM_NUM_CTX`, `SKYNET_NUM_CTX`, and two comments) | A **client request**, not a server capability — what the client asks for, which the server may cap lower |

A client-side `num_ctx` request and a served `max_model_len` are different
numbers, and only the second one is the context window. Until someone reads it
off the model server, quote none of the three: say the window is unrecorded and
that two questions (C-SCN-01, F-CWE-05) overflowed it under the un-truncation
profile, which is an observation that does not depend on knowing its size.

## Reading rule

When quoting a figure, name the arm and the run. The single most common error in
this repository's history was mixing two judge runs: a −0.196 planning delta
computed before the defect fixes was quoted beside a post-fix arm table that
gives −0.1185. Both were faithfully recorded; neither was labelled with its run.
