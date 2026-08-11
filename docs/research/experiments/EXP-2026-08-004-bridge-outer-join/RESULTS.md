# RESULTS — EXP-2026-08-004 The bridge as an outer join

## 1. Headline

Making the generic cross-source bridge an **outer join** takes blind-holdout
retrieval to **1.0000** — 30/30 fully covered, zero gold ids missing — from
0.8952 before the fix and **0.7688** for the hand-written template cascade.
The development catalogue holds at 1.0000 with **0 regressions**.

Every one of the five residual identifiers `EXP-2026-08-003` left outstanding
was the same defect, and all five are recovered.

**Nothing here is judged.** See §5.

## 2. Results table

From [`data/metrics.json`](data/metrics.json); per-set summary in
[`tables/tab-outer-join.md`](tables/tab-outer-join.md).

| Set | Template cascade | Arm H inner join | **Arm H outer join** |
|---|---|---|---|
| Blind `gold_in_evidence` | 0.7688 | 0.8952 | **1.0000** |
| Blind fully covered | 22/30 | 26/30 | **30/30** |
| Development `gold_in_evidence` | — | 1.0000 | **1.0000** |
| Development fully covered | — | 120/120 | **120/120** |

Paired, blind set: 4 improved, **0 regressed**. Paired, development set: 0
improved, **0 regressed** — it was already saturated, so that run could only
detect harm, which is why it was worth running.

Evidence records rise 950 → 966 on the development set and 51 → 56 on the blind
set: the unmapped anchors now being returned instead of dropped.

## 3. What the fix actually is

`.out(edge)` is an inner join — an anchor with no edge on the far side produces
no row, so it disappears from the evidence entirely. The bridge now projects one
row per anchor with its mappings folded into a possibly-empty list.

The CWE-anchored chain is deliberately **asymmetric**: the first hop stays an
inner join, because only patterns that genuinely exploit the weakness belong in
the answer, and only the second becomes outer. Making both outer would return
patterns unrelated to the weakness; making both inner is what was deleting
`CAPEC-116`.

This is not only a recall fix. *"This pattern has no ATT&CK mapping"* is a real
analyst answer, and an inner join cannot return the record needed to ground it.
Three of the four affected blind questions are `expect_no_correlation` cases the
judge already scored 1.00 or 0.50 on Arm F — the abstention was right, and is
now grounded in a retrieved record rather than in nothing. The dependent hop
still correctly stands down, because an anchor with no mappings contributes no
join values.

## 4. The loss that retrieval cannot reach

`EXP-2026-08-003` found 45% of Arm F's blind loss sitting on questions that
retrieved completely. `utils/evaluation/answer_gap.py` decomposes it:

| Class | Questions | Loss share of total | Ids |
|---|---|---|---|
| `under_enumeration` | 3 | **0.0883** | `H-ABS-01`, `H-CSQ-01`, `H-PRE-01` |
| `judge_nuance` | 19 | 0.0417 | spread thinly |

So "45% is answer shaping" resolves to **one named defect worth 0.0883**,
concentrated in three questions, plus small deductions elsewhere that are
presentation rather than bug. In all three the answer names the anchor and drops
the neighbours the query already returned — 1 of 4, 1 of 2, 1 of 3.

Classes are chosen by the **magnitude** of each observable deficit, not by a
fixed precedence. `H-PRE-01` carries a 0.1 faithfulness deduction alongside a
0.75 enumeration shortfall; a ladder ranking faithfulness first would file it
under the symptom and point the fix list at the wrong thing.

## 5. Threats to validity

* **No arm here is judged.** Every figure is retrieval. `1.0000` may not be
  printed beside Arm A's 0.689 or Arm F's 0.708. The `answer_gap` block reuses
  `EXP-2026-08-002`'s Arm F judgments and describes **Arm F**, not Arm H.
* **`gold_in_evidence` saturates, and is now saturated on both sets.** It has no
  remaining headroom and cannot distinguish a good answer from an over-broad
  one. Arm H's two deliberately over-returning primitives stay invisible to it.
  This metric has done its job and further work needs a judged measurement.
* **An outer join returns strictly more.** Precision was already the known cost
  of this arm; this change adds empty-mapping records to the evidence and can
  only increase what a narrator might over-state.
* **The templates still have the inner-join defect.** `capec_maps_to` and
  `cwe_chain` lose the same ids. Fixing them would break the byte-identical
  isolation test and make every arm figure in the 2026-07-26 study
  non-comparable, so it was deliberately not done — see `ISSUES.md`.
* **n = 30** on the blind set, single run, one model, seeds unrecorded.

## 6. What surprised us

That the development catalogue moved not at all. The same defect existed there —
966 vs 950 records shows unmapped anchors are now returned — but no gold
assertion in that catalogue ever required an anchor with an empty mapping. The
blind author wrote four such questions in thirty. That is the co-authoring
effect visible in miniature: the development set does not ask the question that
exposes the bug.

## 7. Follow-ups

1. **Judge Arm H** on both banks. Retrieval is saturated; every remaining
   question about this arm is a precision question, and precision needs a judge.
2. **Fix `under_enumeration` in the composer** — 3 questions, 0.0883, one defect:
   state the neighbours that were retrieved, not just the anchor.
3. **Decide on the templates.** The same outer-join fix applies to
   `capec_maps_to` and `cwe_chain`; the cost is arm-figure comparability.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin

uv run python -m utils.evaluation.experiment_untruncated --arm generic \
  --bank utils/specialists/tests/golden/holdout_questions.json \
  --root docs/evaluation/experiments/holdout-v1-generic-outer --workers 4
uv run python -m utils.evaluation.experiment_untruncated --arm generic \
  --root docs/evaluation/experiments/untruncated-generic-outer --workers 4

uv run python -m utils.evaluation.retrieval_coverage \
  --root docs/evaluation/experiments/holdout-v1-generic-outer --arm generic \
  --reference-root docs/evaluation/experiments/holdout-v1 --reference-arm gold_loop_llm
uv run python -m utils.evaluation.answer_gap \
  --root docs/evaluation/experiments/holdout-v1 --arm gold_loop_llm \
  --judgment-root docs/evaluation/experiments/holdout-v1 --judgment-arm gold_loop_llm
```
