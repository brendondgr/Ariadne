# RESULTS — EXP-2026-08-003 Arm H against the blind holdout

## 1. Headline

On the 30 blind questions, the schema-driven primitives retrieve
**gold_in_evidence 0.8952** against the template cascade's **0.7688** — 26/30
fully covered against 22/30, **4 questions improved, 0 regressed**.

The gain is exactly where predicted and nowhere else: **`H-GRP` 0.000 → 1.000**
and **`H-SW` 0.103 → 1.000**. All fourteen other categories are unchanged to
three decimals. Those two are precisely the categories `EXP-2026-08-002`
diagnosed as structurally unserved, where Arm F scored **0.000** and **0.050**
judged.

**Arm H has no judged correctness on this bank.** Everything below about
correctness is Arm A/F's, quoted for diagnosis. See §5.

## 2. Results table

| Metric (30 blind questions) | Arm A | Arm F | **Arm H** |
|---|---|---|---|
| `gold_in_evidence` | 0.7688 | 0.7688 | **0.8952** |
| Fully covered | 22/30 | 22/30 | **26/30** |
| Gold ids never retrieved | 192 | 192 | **5** |
| Dependent hops skipped | 3 | 3 | 3 |
| Judged correctness | 0.689 | 0.708 | **not run** |

Arm A and Arm F retrieve **identically** — the facet-chasing loop fetched more
records (54 vs 43) and not one additional gold id. On the development catalogue
the loop was part of the best arm; on blind questions it adds volume, not reach.

The 192 → 5 figure is dominated by one question (`H-SW-02` alone requires 170
gold ids), which is why the per-question mean, not the id count, is the headline.

Per-category in
[`tables/tab-blind-holdout-by-category.md`](tables/tab-blind-holdout-by-category.md).

## 3. Where the blind loss actually lives

Splitting Arm F's judged loss by whether retrieval had already succeeded:

| | Questions | Share of Arm F's total loss |
|---|---|---|
| Loss where retrieval was **incomplete** | 8 | **55%** (0.1617 of 0.2917) |
| Loss where retrieval was **complete** | 22 | **45%** (0.1300 of 0.2917) |

So roughly **half** the blind-set deficit is not a retrieval problem at all, and
no amount of better query construction will touch it. `H-ABS` (0.100 judged),
`H-PRE` (0.100), `H-CSQ` (0.150) and `H-LKP` (0.617) all retrieve **completely**
on every arm and still score badly. That is a composition and answer-shaping
deficit, and it is the honest ceiling on this line of work.

**Upper bound on what Arm H can be worth here.** The four questions it newly
covers currently carry 0.1300 of judged loss. If all four became perfect, Arm F's
0.708 would rise to at most **0.838**. That is an arithmetic ceiling under the
assumption that complete retrieval yields a perfect answer, which §5 says is
optimistic. It is **not** a prediction of a measured score.

## 4. What still fails, and why it is one defect

Four questions remain not fully covered. Every missing identifier — all five —
has the same cause: **`_generic_bridge` is an inner join**, so an anchor with no
join target is dropped from the evidence entirely.

| Case | Missing | What is actually true |
|---|---|---|
| `H-CHN-01` | `CAPEC-116` | CWE-1243 is exploited by CAPEC-116 **and** CAPEC-545. CAPEC-116 has zero ATT&CK mappings, so the join drops it. A real miss. |
| `H-CHN-02` | `CAPEC-456`, `CAPEC-679` | `expect_no_correlation: true` — correctly no mapping, but the patterns vanish from the evidence too. |
| `H-CTM-01` | `CAPEC-603` | Exists, zero `MAPS_TO` edges. Anchor lost. Arm F judged **1.00** — the abstention is right, the grounding is thin. |
| `H-CTM-02` | `CAPEC-40` | Same. Arm F judged **1.00**. |

Three of the four are *correct abstentions* that the judge already rewarded; the
retrieval metric penalises them because the gold asks for the anchor record
(`min_records: 1`) and an honest "no mapping exists".

This matters beyond the metric. "This pattern has **no** ATT&CK mapping" is a
real analyst answer, and grounding it requires the pattern to be in the evidence.
An inner join cannot express a negative result. The fix is an optional match on
the anchor side, and it is **not** Arm H-specific — `capec_maps_to` and
`cwe_chain` have the same shape, which is why Arm A and Arm F lose these ids too.

## 5. Threats to validity

* **Arm H is unjudged on this bank.** 0.8952 is retrieval. It may not be placed
  beside 0.689/0.708, and the ≤0.838 bound in §3 is arithmetic, not measurement.
* **Complete retrieval does not imply a correct answer.** §3 shows 22 questions
  retrieving completely and still losing 0.13. Assuming the four newly-covered
  questions become perfect is the optimistic end of the range.
* **n = 30.** `EXP-2026-08-002` reports 95% CIs of roughly ±0.13 on judged
  correctness at this size. A four-question improvement is well inside the noise
  of a judged comparison — which is part of why this experiment measures
  retrieval, where the quantity is a set-membership test rather than a score.
* **`gold_in_evidence` cannot see over-return.** Arm H's two deliberately
  over-broad primitives (`EXP-2026-08-001` `ISSUES.md`) are invisible here and
  would cost precision under a judge. `H-ABS` and `H-PRE` — the hierarchy
  questions where Arm H returns both directions — already score 0.100 judged on
  the template arms, so that category is weak for everyone.
* **Single run, one model, seeds unrecorded.** As with every arm in the study.
* **The bank is LLM-authored**, which controls for template-coupling but not for
  a language model's idea of a plausible question. `EXP-2026-08-002` records this.

## 6. What surprised us

That the gain was *exactly* the two diagnosed categories and nothing else — a
diffuse improvement would have suggested a metric artifact. And that Arm A and
Arm F retrieve identically: the iterative loop, which earned its place on the
development catalogue, contributes nothing to reach on blind questions.

## 7. Follow-ups

1. **Make the bridge an outer join.** One change, fixes all five residual ids,
   and lets a negative result be grounded in the anchor record. Applies to the
   hand-written templates too.
2. **Judge Arm H on this bank** — 30 agents, the same protocol as
   `EXP-2026-08-002`. It is the only way to turn the ≤0.838 bound into a number,
   and the only way to price the over-return.
3. **The 45%.** Half the blind deficit is answer-shaping on questions that
   retrieved perfectly. That is now the largest addressable gap in the system and
   nothing in this line of work touches it.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm generic --bank utils/specialists/tests/golden/holdout_questions.json \
  --root docs/evaluation/experiments/holdout-v1-generic --workers 4
uv run python -m utils.evaluation.retrieval_coverage \
  --root docs/evaluation/experiments/holdout-v1-generic --arm generic \
  --reference-root docs/evaluation/experiments/holdout-v1 --reference-arm gold_loop_llm
```

The Gremlin fixture must be loaded before the run. It was empty at the start of
this session and every CAPEC and federated question would have returned nothing;
see `ISSUES.md`.
