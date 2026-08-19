# Overnight sweep — judged arm comparison

**Started** 2026-08-19T03:53:37+00:00 · **finished** 2026-08-19T06:02:39+00:00
**Tree** `9da80faea1ac` · **workers** 12 · **wall** 129 min

> ⚠ **1 of 14 phases failed.** They are listed in §7 with their errors. Every figure below comes only from phases that completed.

## 1. How much to trust these numbers

The local judge re-graded the 30 blind answers that already carry committed **Sonnet 5** judgments from `EXP-2026-08-002`. That is the only evidence that this runner's rubric and model reproduce the instrument the holdout was measured with.

| | value |
|---|---|
| cases compared | 30 |
| Sonnet mean correctness | 0.689 |
| local mean correctness | 0.72 |
| mean delta (local − Sonnet) | 0.031 |
| mean absolute delta | 0.103 |
| verdict agreement | 0.7 |
| Pearson r | 0.9275 |

**Read:** the two judges rank the same answers the same way and sit close in level. Treat the comparisons below as meaningful, and the absolute values as carrying the offset above.

## 1b. Did the repair actually work?

The same **30 blind questions**, graded by the **same judge on the same night**, before and after the binding/direction/outer-join work. Pairing case by case removes the grader from the comparison entirely — the only thing that differs between the two columns is the code.

| | correctness |
|---|---|
| before (holdout-v1, pre-fix) | 0.7200 |
| after (repaired cascade) | 0.8367 |
| **paired delta** | **+0.1167** (95% CI +0.0333 – +0.2167) |

**10 improved, 3 regressed, 17 unchanged.** Worst single-case movement -0.15.

The interval excludes zero, so the improvement is not an artefact of which questions happened to be sampled.

## 2. The comparison this was for

Both arms retrieve identically — `gold_in_evidence` 1.0000, 30/30 covered — so any difference here is answer quality, not what was fetched. Arm H had never been judged before tonight.

| arm | n | correctness (95% CI) | C/P/I | faithfulness | completeness | answers w/ hallucination |
|---|---:|---|---|---:|---:|---:|
| Cascade (templates, repaired) | 30 | **0.8367** (0.752 – 0.915) | 22/8/0 | 0.980 | 0.911 | 0 |
| Arm H (schema-driven) | 30 | **0.8483** (0.778 – 0.915) | 21/9/0 | 0.952 | 0.911 | 1 |

**Delta (Arm H − cascade): +0.0116.** Whether that is real is §3's question.

Abstention behaviour, which is the property the pitch rests on:

| arm | abstained | abstention carried the query | fabricated a mapping |
|---|---:|---:|---:|
| Cascade | 3 | 3 | **0** |
| Arm H | 4 | 2 | **0** |


## 3. Is any of that above noise?

The cascade's pipeline is fully deterministic, so re-judging the *same* answers isolates grader variance exactly — for this arm, all variance is judge variance. That is a partial answer to open question Q2, which currently has `statistical_test: null` in every manifest.

| pass | mean correctness |
|---|---|
| E1 | 0.8367 |
| E2a | 0.8417 |
| E2b | 0.8400 |

**Spread across 3 passes: 0.0050** (sd 0.0021).

The **arm** delta in §2 is 0.0116 against a grader spread of 0.0050 — a ratio of 2.3×.

That is **not a separation**. Clearing the grader's noise floor is the weakest possible bar — it says the two arms were not measured identically, not that either is better. Their confidence intervals in §2 overlap almost entirely, and at n = 30 the honest reading is that **the cascade and Arm H are indistinguishable on correctness**. The differences worth acting on are in §5's abstention rates and the hallucination counts, not here.

For contrast, the **repair** delta in §1b is 0.1167 against the same 0.0050 spread — 23× — and its paired interval excludes zero. That one is a real effect; the arm comparison is not.

## 4. Where the remaining loss sits

**cascade** — see `answer-gap-*.json` in this directory.

Retrieval was complete on 30/30 questions, so every point below is lost *after* the evidence was in hand. Total loss **0.1633**.

| reason | questions | loss share | per affected question |
|---|---:|---:|---:|
| `ungrounded` | 11 | 0.0950 | 0.0086 |
| `under_enumeration` | 3 | 0.0633 | 0.0211 |
| `wrongful_abstention` | 2 | 0.0050 | 0.0025 |
| `judge_nuance` | 14 | 0.0000 | 0.0000 |

_`judge_nuance` is scored loss the gap analysis could not attribute to a named defect; a large question count there with near-zero share means the answers were docked fractionally, not broken._

**Arm H** — see `answer-gap-*.json` in this directory.

Retrieval was complete on 30/30 questions, so every point below is lost *after* the evidence was in hand. Total loss **0.1517**.

| reason | questions | loss share | per affected question |
|---|---:|---:|---:|
| `under_enumeration` | 3 | 0.0617 | 0.0206 |
| `ungrounded` | 8 | 0.0583 | 0.0073 |
| `unfaithful` | 6 | 0.0150 | 0.0025 |
| `judge_nuance` | 10 | 0.0100 | 0.0010 |
| `wrongful_abstention` | 3 | 0.0067 | 0.0022 |

_`judge_nuance` is scored loss the gap analysis could not attribute to a named defect; a large question count there with near-zero share means the answers were docked fractionally, not broken._

## 5. The 120-question catalogue

| arm | n | correctness (95% CI) | C/P/I | faithfulness | completeness | answers w/ hallucination |
|---|---:|---|---|---:|---:|---:|
| Cascade | 120 | **0.9839** (0.977 – 0.990) | 119/1/0 | 0.988 | 0.998 | 3 |
| Arm H | 120 | **0.9692** (0.955 – 0.980) | 115/5/0 | 0.975 | 0.995 | 9 |

Abstention behaviour at this larger n — the blind set's 3-vs-4 abstentions were too few to read, these are not:

| arm | abstained | carried the query | rate |
|---|---:|---:|---:|
| Cascade | 21 | 20 | 95% |
| Arm H | 20 | 11 | 55% |

Remember what this bank is: 120 questions co-authored with the templates that answer them. It is the wrong instrument for an absolute claim and the right one for an arm-to-arm comparison at larger n.

## 6. Arm F, generation 2

| bank | n | correctness (95% CI) | C/P/I | faithfulness | completeness | answers w/ hallucination |
|---|---:|---|---|---:|---:|---:|
| blind holdout | 30 | **0.9157** (0.856 – 0.963) | 25/5/0 | 0.960 | 0.958 | 4 |
| catalogue | 120 | **0.9852** (0.979 – 0.990) | 117/3/0 | 0.978 | 1.000 | 19 |

This closes the open item in `EXP-2026-08-006`'s ISSUES, which recorded that no arm comparison could be drawn from that experiment because Arm F had not been re-run.

## 7. What ran, and what did not

| phase | what it was | status | wall |
|---|---|---|---:|
| `preflight` | graphs live, model served, answers present | **failed** | 3s |
| `E0` | calibrate the local judge against the committed Sonnet judgments | ok | 1036s |
| `E1` | judge the repaired cascade on the blind holdout | ok | 583s |
| `E3` | judge Arm H on the blind holdout | ok | 589s |
| `E2a` | second judge pass over the cascade's blind answers | ok | 312s |
| `E2b` | third judge pass over the cascade's blind answers | ok | 523s |
| `E4a` | answer_gap on the cascade | ok | 0s |
| `E4b` | answer_gap on Arm H | ok | 0s |
| `E5a` | judge the cascade on the 120-question catalogue | ok | 1099s |
| `E5b` | judge Arm H on the 120-question catalogue | ok | 1248s |
| `E7a` | run Arm F generation 2 on the blind holdout | ok | 345s |
| `E7b` | judge Arm F on the blind holdout | ok | 161s |
| `E7c` | run Arm F generation 2 on the catalogue | ok | 905s |
| `E7d` | judge Arm F on the catalogue | ok | 937s |

**`preflight` failed:** `RuntimeError: uv run main.py --dataset capec --graph… exited 1: ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "/home/bdgr/Agents/Ariadne/utils/graph_loader/main.py", line 68, in run_dataset_verify
    _verify_dataset(dataset, config=config)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/bdgr/Agents/Ariadne/utils/graph_loader/verify.py", line 124, in run_dataset_verify
    raise PreflightError("; ".join(result.errors[:5]))
utils.graph_loader.preflight.PreflightError: node count 0 != expected 4769; edge count 0 != expected 6972; label AttackPattern count 0 != expected 558; label Category count 0 != expected 21; label Consequence count 0 != expected 812
`

## 7b. Figures corrected after the run, and why

A roll-up is frozen when its phase ends. Where the data on disk later became more complete than the roll recorded, the figure below was **recomputed from the judgment files**, never adjusted by hand. Both readings are shown so nothing changes silently between the run log and this report.

| phase | n before → after | correctness before → after | why |
|---|---|---|---|
| `E3` | 29 → 30 | 0.8500 → 0.8483 | H-SW-02 truncated at 8192 and 16384 tokens; re-judged at 32768. n 29 -> 30. |
| `E2b` | 60 → 30 | 0.7583 → 0.8400 | judged 60 files: the pass picked up E2a's 30 judgments as answers. Junk quarantined under _contaminated_run3; rolled over the 30 real cases. |
| `E5b` | 119 → 120 | 0.9690 → 0.9692 | A-SW-02 truncated at 8192 and 16384 tokens; re-judged at 32768. n 119 -> 120. |
| `E7d` | 118 → 120 | 0.9849 → 0.9852 | A-MC-02 and F-CTM-05 truncated at 8192 and 16384 tokens; re-judged at 32768. n 118 -> 120. |

## 8. Caveats that travel with every number above

1. **The blind bank diagnosed the defects this system now repairs.** Holdout v1 found the direction defect and the join defect; both are fixed. A v1 figure measured afterwards is co-authored with its own test. These are diagnostics. The quotable blind number still has to come from a holdout v2.
2. **This judge is not independent.** A local model grading answers from a pipeline whose LLM seams run on that same server shares failure modes with it. §1 is the only evidence about how far that matters; the cross-model panel remains the instrument for anything quoted outside the repository.
3. **n = 30** on the blind set, single pipeline run, seeds unrecorded.
4. **Nothing here was recorded as an experiment yet.** The sweep writes artifacts and this report; folding them into `docs/research/experiments/` is a morning job, because which claims move is a judgement call and not one to automate.

## 9. Waiting for you

- **Fold tonight's results into the research record** — one experiment per question answered, then reconcile `CLAIMS.md`. C-003 is the one to watch: if Arm H judged level with the cascade, "the templates are where the accuracy lives" needs rewriting.
- **The composer under-enumeration fix** — deliberately not attempted unattended. §4 says what it is worth on each arm.
- **Holdout v2** — now the only route to a quotable blind figure.
- **21 commits and 2 freeze tags are still unpushed.**

