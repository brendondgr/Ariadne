# Results — EXP-2026-09-019

Status: **complete**. All five steps ran.
Every number here is read from `data/endpoint.json`, `data/endpoint-gemma-4-26B-it.json`
and `data/planner_cost.json`.

## Step 1 — the endpoint

The alias in the plan was wrong, and the identity gate is what caught it.
`local` on the `:4000` relay answers `gemma-4-26B-it`, and did so on both
probes. MiniCPM5-2B is served by the llama.cpp router on `:7070`, where the
gate passes: served id `minicpm-5-2B`.

### Concurrency, `minicpm-5-2B` at `:7070`

Ten calls per rung, an identical 512 generated tokens per call, 32-core host.

| Concurrency | Wall | Aggregate tok/s | Per-stream tok/s | p50 | p95 | load |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 36.962 s | 73.05 | 73.05 | 3.694 s | 3.724 s | 2.79 |
| 2 | 20.272 s | 133.24 | 66.81 | 3.956 s | 4.43 s | 3.31 |
| **4** | 12.838 s | **210.47** | 62.26 | 4.444 s | 4.494 s | 3.27 |
| 8 | 12.708 s | 212.7 | 43.41 | 8.293 s | 8.789 s | 2.9 |
| 12 | 12.891 s | 209.92 | 40.38 | 8.879 s | 12.886 s | 2.61 |
| 16 | 12.857 s | 210.24 | 40.45 | 8.856 s | 12.852 s | 2.58 |

**Chosen concurrency: 4.** Throughput saturates from rung 4
onward; rungs 8 through 16 buy nothing and cost roughly double the latency. No
rung errored and no guard tripped, so the full ladder ran.

### The same ladder on `gemma-4-26B-it`, for contrast

Recorded under protest of the identity gate and kept because it makes the
comparison free (`data/endpoint-gemma-4-26B-it.json`). Single-stream 90.99 tok/s,
knee also at concurrency 4 at 140.03 tok/s aggregate, and rung 8 tripped the p95
guard so rung 12 never ran.

The 2B is **slower single-stream** than the 26B (73.05 vs 90.99 tok/s) and **faster
in aggregate** (210.47 vs 140.03): it parallelises where the larger model does not. Load
never passed 4.4 of 32 cores on either, so the bound is memory bandwidth rather
than CPU.

### Negative result: the context ceiling cannot be probed

Both servers accepted `max_tokens` all the way to the probe cap of 1,048,576
without refusing — no error, no body. They clamp silently. The budget for Steps
3–5 must therefore come from the model card, not from the endpoint. This is the
opposite of the `:9090` behaviour the plan was written against, where the 400s
were the signal.

## Step 2 — the planner costs a great deal

Both arms completed 284/284.

| | `generic_composed` | `generic_planned` |
| --- | ---: | ---: |
| Gold coverage (mean) | 0.8611 | 0.4797 |
| Wall clock, 284 questions, 8 workers | 4.0 s | 17.1 s |

**Paired difference: −0.3814** (sd 0.4413, standard error 0.0262, n = 284),
separable by the `|difference| > 2·SE` rule. Both arms are deterministic, so this
is not run variance, and no model was in either, so it is not grading noise.

On **77 of 284 questions the planner retrieved nothing where the authored plan
retrieved records.** The reverse never happened: zero questions where the
authored plan retrieved nothing and the planner retrieved something. Eight
questions returned nothing on both sides.

### Per tier

| Tier | n | Mean difference |
| --- | ---: | ---: |
| D0 | 36 | −0.3333 |
| D1 | 35 | −0.3157 |
| D2 | 40 | −0.3117 |
| D3 | 44 | −0.4055 |
| D4 | 55 | −0.2981 |
| D5 | 47 | −0.5025 |
| D6 | 27 | −0.5534 |

Every tier loses. The loss concentrates in D5 and D6 — the chained and
cross-catalogue tiers, where a plan has the most structure to get wrong.

### What does not degrade

`scripts/mechanism_check.py` over the treatment arm reports **0 absence
contradictions across 284 answers**. The planner arm retrieves less; it does not
start asserting that things are absent. One mechanism improves rather than
degrades: the name-search slice rises from 0.0443 to 0.4443 coverage, with its
zero-record count falling from 21 to 11.

### What this means for every figure that rests on 0.92

The Generic tier's headline is a ceiling for retrieval and composition **given a
correct plan**, and this is the first measurement of what producing that plan
costs. It is not a small correction. The difference exceeds the 0.02 threshold
the plan set for a judged pass by a factor of nineteen, so the judged read is
warranted; it has not been run yet.

The difference is not attributed to the planner *alone*. `generic_planned` runs
the real pipeline, so the planner's own per-plan limits travel with it — the
observed plans set `max_result_rows: 1000` and `max_traversal_depth: 3` rather
than the lifted bounds the gold-replay path inherits. Separating "the planner
chose a worse decomposition" from "the planner chose tighter limits" is not done
here and is recorded in `ISSUES.md` as I-2.

## Step 3 — the 2B narrator, full 284

| Measure | Value | Gate |
| --- | ---: | --- |
| Answers | 284 | — |
| Fallback rate (over ANSWERS) | **0.0282** | <= 0.14 ✓ |
| New unsupported verdicts | **0** | 0 ✓ |
| Claims byte-identical to the control | **284/284** | ✓ |
| Wall clock per answer, 4 workers | 80.988 s (median 43.678 s) | vs 0.042 s |

Every one of the 8 fallbacks was `LLM narrator unavailable` — a
transport failure reaching the endpoint, not the model refusing. At four
concurrent generations of this length some connections do not survive, which is
a reliability signal at this concurrency rather than a property of the model.

**The narrator does not touch the facts.** Across 284 answers: zero changes to
`entity_ids`, zero to `citations`, zero to `verdict`, and zero new unsupported
verdicts.

The first pass of this comparison read 273 of 284, and that was an artefact of
the tree moving mid-run rather than anything the narrator did: a concurrent
session committed `1f507002` at 17:30:38, adding `DETECTS` to the composer's
`_REL_NOUNS`, and the two arms straddled it. Regenerating the narrator cell on
one tree gives **284 of 284**. Recorded as I-8; the superseded figures are kept
there as its evidence.

What the seam costs is time: roughly three orders of magnitude, not a tax.

## Step 4 — the 2B specialist seam is not viable

The plan's rule is that above a 25% rejection rate this seam is not viable at
this model size and the step records that rather than widening. Counted over
drafts submitted to the gate — not over questions, see I-9 — it is far past that
line, and the full 284-question pass was not run.

| | 4096-token budget | 16384-token budget |
| --- | ---: | ---: |
| Drafts reaching the gate | 17 | 16 |
| Rejected as empty | 11 | 8 |
| Rejection rate | 0.6471 | 0.5 |
| Cleared the gate, then failed at the database | 6/6 | 8/8 |
| **Drafts that worked** | **0/17** | **0/16** |
| Questions returning no records | 9/9 | 9/9 |
| Control, same questions | 0/9 | 0/9 |

Quadrupling the budget is not the missing ingredient. It bought a change of
failure mode and not of outcome: fewer drafts truncated into nothing, and
correspondingly more malformed drafts reaching the database and erroring there.
The prompts are ~870 tokens, so the empty drafts are the model failing to close
a query rather than running out of room.

Two findings here are **not** about model size and are recorded as such in I-9.
No rejection named `allowed_edge_patterns`, so the allowlist gate the plan
expected to be the defence never fired — the drafts were empty rather than
wrong, and empty passes that check. And the drafts that were not empty executed
against live graph engines rather than being refused before them.

## Step 5 — the two questions crossed

Gold coverage, 284 development questions, every cell paired per question.

| | no model | 2B narrator |
| --- | ---: | ---: |
| **authored plan** | 0.8611 | 0.8611 |
| **real planner** | 0.4797 | 0.4824 |

**The plan effect**, down the columns — what letting the planner run costs:

| Model column | Paired difference | SE | Separable |
| --- | ---: | ---: | --- |
| no model | **-0.3814** | 0.0262 | True |
| 2B narrator | **-0.3787** | 0.0262 | True |

**The model effect**, across the rows — what adding the 2B narrator costs:

| Plan row | Paired difference | SE | Separable |
| --- | ---: | ---: | --- |
| authored plan | +0.0000 | 0.0 | False |
| real planner | +0.0026 | 0.0026 | False |

**Interaction: +0.0027.** The two variables do not
interact. The plan costs the same whether or not a small model is narrating, and
the model costs nothing either way. This was the cell nobody had run and the
reason the 2x2 existed: had the effects compounded, the corners would have been
misleading. They do not.

The model-effect row is a control as much as a result. Gold coverage is a
retrieval measure, and the narrator must not be able to move it. That it is
+0.0000 with an authored plan — exactly zero, with zero
spread — is the independent confirmation of Step 3's claim from a different
direction.

### Step 2's headline, re-derived against the corrected control

Step 2 compared `generic_planned` against `generic_composed`, and I-8 later
established that those two load different composer caps. The no-model column
above is the same comparison against `generic_narrator_off`, which does not:
**-0.3814** against Step 2's published -0.3814. The confound
did not touch the figure, which is what a retrieval metric should do — the
composer cap changes claim text, not what was retrieved — but it is checked
rather than asserted.

### Single-user latency, one worker

The wall-clock column in the cells above is measured at concurrency 4, which is
throughput under load. This is what one analyst waits, on the tier-balanced
nine-question slice.

| Cell | Mean | Median | n |
| --- | ---: | ---: | ---: |
| authored plan, no model | 0.07 s | 0.01 s | 9 |
| authored plan, 2B | 20.802 s | 17.744 s | 9 |
| real planner, no model | 0.119 s | 0.06 s | 9 |
| real planner, 2B | 9.752 s | 6.904 s | 9 |

## What the two questions turned out to answer

**Does the Generic tier need a big model?** For narrating prose, no — and it does
not need a model at all on the evidence here. A 2B narrator is faithful: it
changed no identifier, citation or verdict across 284 answers, and it moves gold
coverage by +0.0000. But it buys nothing measurable either,
at roughly a thousand times the latency, and for drafting queries it is not
usable at all — zero working drafts out of seventeen.

**Does it need a planner?** This is the finding that matters. Letting the planner
produce the decomposition costs **-0.3814** gold coverage,
paired, separable, and stable across both model columns. Every headline figure
this programme has published was produced by replaying an authored plan, so
0.92 has always been a ceiling for retrieval and composition *given a correct
plan*. The system's own planning stage does not reach that ceiling and the gap
is not small.

The honest limit on that number is I-2: `generic_planned` runs the real
pipeline, so the planner's own per-plan limits travel with its decomposition
(`max_result_rows` 1000 and `max_traversal_depth` 3, against the lifted bounds
the gold-replay path inherits). How much of the gap is a worse decomposition
and how much is tighter limits is not separated here and needs a third arm.

Nothing here was judged. The model-free difference clears the plan's 0.02
threshold for a judged pass by a wide margin, so that pass is warranted and has
not been run.

## The judged pass — the 2x2 on the grader's own scale

Run 2026-09-14, `default-model` on `:9090` asserted from the response envelope
to be `qwen38-27B-v2`, 32768 max tokens, every cell graded in **both**
counterbalanced positions. 2,272 judgments, no failed cells. Judge
co-authorship is clean: two cells have no model at all and two were narrated by
`minicpm-5-2B`, so the grader never scores its own prose.

| | no model | 2B narrator |
| --- | ---: | ---: |
| **authored plan** | 0.9225 | 0.9396 |
| **real planner** | 0.593 | 0.6402 |

| Effect | Difference | SE | Separable |
| --- | ---: | ---: | --- |
| Plan, no model | **-0.3294** | 0.0197 | True |
| Plan, 2B narrator | **-0.2994** | 0.0178 | True |
| Model, authored plan | **+0.0171** | 0.0061 | True |
| Model, real planner | **+0.0471** | 0.0107 | True |

**The plan effect survives the change of metric.** Gold coverage put it at
-0.3814; the grader puts it at -0.3294. Two different
instruments, one without a model in it at all, agreeing on the size of the gap.
That is the strongest form the Step 2 result can take, and it is now on the
scale every other figure in this project uses.

Per tier, no-model column: D0 -0.1285,
D1 -0.2150,
D2 -0.3065,
D3 -0.3011,
D4 -0.3788,
D5 -0.4191,
D6 -0.5691 — monotone in tier difficulty,
worst where a plan has the most structure to get wrong.

### The model effect reverses sign when the metric can see prose

Gold coverage measured the narrator at +0.0000 and +0.0026, neither separable.
The grader measures it at +0.0171 and
+0.0471, **both separable**. The difference between the two
instruments is the narrative: coverage counts identifiers, the grader reads the
answer. So the 2B narrator does something measurable, and on this metric it
helps — more so when the plan is worse (+0.0471 against
+0.0171), which is consistent with prose partially
compensating for thinner retrieval.

### What the headline hides

`correctness` is not the only dimension the grader reports, and the others move
the other way.

| Cell | correctness | faithfulness | groundedness | completeness | hallucinations per judgment |
| --- | ---: | ---: | ---: | ---: | ---: |
| authored, no model | 0.9225 | 0.9523 | 0.956 | 0.9715 | 0.1743 |
| authored, 2B | 0.9396 | 0.9355 | 0.9484 | 0.9759 | **0.3609** |
| planner, no model | 0.593 | 0.9354 | 0.895 | 0.497 | 0.2377 |
| planner, 2B | 0.6402 | 0.9258 | 0.8906 | 0.4869 | **0.3134** |

Adding the 2B narrator raises correctness and **lowers faithfulness and
groundedness in both rows**, while roughly **doubling** flagged hallucinations
with an authored plan (0.1743 to
0.3609 per judgment). Fabricated
mappings rise from 1 to
3 with an authored plan and from
0 to
8 with a real one.

This corroborates, from the grader's side, the independent measurement made
directly on the prose: 5 of 284 narratives named an identifier that appears
nowhere in the verified claims — not invented nonsense but real outside
knowledge, `TA2541` and a parent technique `T1027` the evidence never carried.

**The trade is fluency against provenance, and it is not obviously worth
taking.** The system's premise is that every statement traces to the graph. A
narrator that scores better because it writes more confidently, while importing
facts the evidence does not contain, is improving the number this project
measures and damaging the property it exists to guarantee. The cheap remedy is
structural rather than a matter of model size: the grounding check already runs,
it simply runs one step too early. `compose -> verify -> narrate` puts the
narrator *after* the verifier, so its prose is the one output nothing checks.
Recorded as I-10.
