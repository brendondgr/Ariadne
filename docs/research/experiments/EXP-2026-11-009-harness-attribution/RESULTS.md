# RESULTS — EXP-2026-11-009 Era 2 Step 4: where the planned path loses an answer, and whose fault it is

## 1. Headline

- **The deterministic planner's loss is decomposition, not limits (Q58).** The authored plan
  run under the planner's tighter limits loses **−0.001** coverage (SE 0.001). The planner's
  decomposition loses **−0.3342** (SE 0.026). All three arms are model-free and ran back to back
  on today's tree, with zero model-port connections.

- **Both planners lose mainly by choosing the wrong relation.** That is 59 of the deterministic
  planner's 77 empty answers. For the LLM planner it is 68 of 105 under the pre-registered
  rules, or 42 of 105 after the post-hoc correction described in §4.

- **RQ5 (did the model or the harness lose the LLM planner's answers?): the pre-registered
  figure says the model, but it is a lower bound on the harness share, and every correction
  lands in "mixed".**

  | Reading | Harness share of the 105 losses | Band |
  |---|---:|---|
  | pre-registered rules (primary) | **0.16** | "mostly model" |
  | blind second annotator, 20-question sample | 0.30 | "mixed" |
  | correcting the one rule the traces show is wrong (post-hoc) | 0.41 | "mixed" |

  Two biases push the primary figure down; both are in §4.

- **The correction to the era-2 plan.** EXP-2026-09-019's "+0.0000 model effect" was a narrator
  swap, not a planner swap, and says nothing about the harness question. This experiment is the
  first to measure that question.

## 2. Results table

From `data/metrics.json`, `data/attribution.json`, `data/agreement.json` and
`data/codings.jsonl`. One deterministic pass; n_runs = 1.

### Causes, first in pipeline order

The cause columns use the pre-registered rules. The last row is the post-hoc builder-walk
reading, from `attribution.json` (`posthoc_builder_walk`).

| Planner | Lost | relation | shape | english_reread | direction | decomposition | source | other | Downstream share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| deterministic (rules) | 77 | 59 | 7 | 1 | 0 | 1 | 0 | 9 | 0.013 |
| LLM (Gemma 4 26B) | 105 | 68 | 12 | 14 | 3 | 0 | 1 | 7 | **0.162** |
| LLM, post-hoc builder walk | 105 | 42 | 12 | 40 | 3 | 0 | 1 | 7 | 0.410 |

**Counting every applicable flag, not only the first:**
- **Deterministic:** relation 60, english_reread 19, decomposition 17, shape 7, direction 2.
- **LLM:** relation 70, english_reread 38, shape 13, decomposition 6, direction 3.

**The 38 questions both planners lost:** 31 got the same cause. The pairs were:

| Deterministic → LLM | Count |
|---|---:|
| relation → relation | 21 |
| relation → english_reread | 5 |
| shape → shape | 5 |
| other → other | 4 |

### The three reruns (today's tree, model-free, guarded at the socket)

| Arm | Coverage | Δ | SE |
|---|---:|---:|---:|
| authored plan, lifted limits | 0.8526 | | |
| authored plan, the planner's limits (1,000 rows, depth 3) | 0.8516 | limits effect **−0.0010** | 0.0010 |
| deterministic planner | 0.5173 | decomposition effect **−0.3342** | 0.0260 |

- **Drift against September:** the authored arm moved −0.0085 and the planner +0.0376. The lost
  set is the same 77 questions with identical causes, so the planner's gain is on questions it
  already answered.
- **Model-port connections:** 0 across all three arms.
- **Stage timing** (deterministic planner, today):

  | Stage | Median | p95 |
  |---|---:|---:|
  | planning | 61 ms | 158 ms |
  | each specialist | 35 ms | 91 ms |
  | whole question | 418 ms | 772 ms |

### The second annotator (Claude Sonnet 5.5, blind, random 20 per planner)

| | Exact agreement | κ | Stage agreement |
|---|---:|---:|---:|
| deterministic | 0.75 | 0.58 | 0.75 |
| LLM | 0.90 | 0.83 | 0.90 |
| all | **0.825** | **0.71** | 0.825 |

There are 7 disagreements. In 6 the annotator coded `direction` where the coder said
`other`, `relation` or `decomposition`. In the 7th the annotator said `other` where the coder
said `relation`.

## 3. Figures

None.

## 4. Interpretation

### Expectations against outcomes

| | Expected | Outcome |
|---|---|---|
| G1 one cause per lost question | 182 / 182 | **met** |
| G2 model-port connections | 0 | **0: met** |
| E1 LLM downstream share | ≥ 0.25 ("mixed or better") | **missed under the primary reading (0.162, "mostly model")**; met by the annotator's sample (0.30) and by the post-hoc correction (0.41) |
| E2 plan-stage causes the majority of the deterministic 77 | majority | **met: 67 / 77** |
| E3 limits effect | ≤ 0.02 | **met: −0.001** |
| E4 drift | within 0.01 | **half met:** authored −0.0085, planner +0.0376 |
| E5 D5/D6 dominated by decomposition | | **missed:** D5 is 15/15 `relation`, D6 is 6/6 |
| E6 agreement | ≥ 0.75 exact, κ ≥ 0.6 | **met overall** (0.825, 0.71); the deterministic subset's κ is 0.58 |

### Why the primary figure understates the harness

Both biases are visible in the saved traces.

1. **The builder's fixed walk.** For 26 of the LLM losses, the model's plan named every
   authored relation and set a small depth, often 1 for a one-hop question. The harness's query
   builder then emitted a fixed `repeat(...).times(3)` walk, and the gate rejected the
   builder's own query for exceeding the plan's depth. Pre-registered rule 5 read every depth
   rejection as an over-long chain made of the plan's own elements. These rejections did not
   come from the plan. The annotator, applying the rule as written, agreed with the coder on
   these cases, so its agreement does not decide this point.
2. **Direction.** The annotator found 6 direction errors in 40 sampled questions that the coder
   missed: builders traversing `out()` where the authored plan went `in()`. Those 6 are 4 in
   the deterministic sample and 2 in the LLM sample. The cause is that the authored traces'
   `relationships` fields do not always list the relations their queries use, so the coder's
   orientation check had nothing to compare. All are downstream (harness) errors.

### What this answers

- **Q58 is closed.** Limits cost nothing measurable. The planner's loss is its decomposition.
- **RQ5 is "mixed", not "mostly harness".** The single largest cause, for both planners, is
  choosing the wrong relation for what the question asks:
  - wrong relations such as `NEXT_STEP` for "can follow", `IN_VIEW` versus `MEMBER_OF`, and
    `REQUIRES_SKILL` for "prerequisites";
  - attribute questions planned as traversals.

  That is a grounding problem: mapping the question's words onto the schema. The harness then
  loses a further share (the plan provisionally said "mostly"), probably 0.3 to 0.4, through:
  - seed ids re-read from English and dropped;
  - a builder walk that ignores the plan's depth;
  - schema the resolver changed or added;
  - wrong traversal direction.
- **What this decides in plan v2 (Step 4, "What the result decides").** Neither branch applies
  cleanly, so both parts of the fix stay:
  - **The harness half** goes away by design in the v2 loop. Tools take ids and handles as typed
    arguments (no English re-read); the compiler, not a template, sets the depth; direction
    comes from the schema.
  - **The grounding half** is Step 10's job (`find_schema`, synonyms), together with Step 7's
    relation-choice decision (D4). It is the largest single cause, so Steps 7 and 10 matter
    more than the plan assumed. Step 11's expected gain should be set from this table, not from
    "mostly harness".

## 5. Threats to validity

- **The LLM-planner arm is saved, from 2026-09-14 and an older tree.** Its model (Gemma 4
  26B) is no longer served. Today's deterministic planner has moved +0.0376 since then, but its
  lost set is unchanged.
- **Coverage is retrieval, not judged correctness.** "Lost" means zero records.
- **The coder relies on recorded traces.** Where the authored trace's `relationships` field is
  incomplete, `relation` and `direction` are undercounted. The 9 and 7 `other` codes are mostly
  such cases, which the annotator coded `direction` or left `other`.
- **One annotator and 40 questions.** The deterministic subset's κ of 0.58 is below the bar.
- **The plan stage is not purely the model's.** The LLM's choices are shaped by the harness's
  prompt and card: its plan format has no seed field, and it sees glosses, not examples. So
  even the plan-stage share is not "the model alone".

## 6. What surprised us

- **The premise.** The plan's harness-versus-model evidence (EXP-2026-09-019) never contained a
  model planner.
- **The gate rejecting its own builder.** The fixed 3-step walk against a plan's depth-1 limit
  explains a quarter of the LLM planner's losses (26 of 105). The model chose a sensible depth,
  and the harness's template would not honour it.
- **Limits are irrelevant.** Q58 had been open since September as a plausible half of the
  loss. It is 0.1 percentage point.
- **The two planners fail on the same questions for the same reason** (31 of the 38 they share).
  That points at the schema-mapping problem, which no planner style escapes.

## 7. Follow-ups

- **Step 10:** relation grounding with synonyms is now the measured largest cause.
- **Step 7:** relation choice (D4) moves up.
- **Step 11:** the loop's tools must take ids as typed arguments, let the compiler set depth,
  and take direction from the schema. Each is a measured cause here.
- **Step 11's expectation** is to be restated from this table before its protocol is written.
- Q57 and Q58 are amended in `OPEN_QUESTIONS.md`.

## 8. Reproduction

```bash
uv run python scripts/harness_attribution.py rerun   --root docs/evaluation/experiments/harness-attribution-2026-11-15
uv run python scripts/harness_attribution.py code    --out docs/research/experiments/EXP-2026-11-009-harness-attribution/data --rerun-root docs/evaluation/experiments/harness-attribution-2026-11-15
uv run python scripts/harness_attribution.py packets --out docs/research/experiments/EXP-2026-11-009-harness-attribution/data
# the second annotator codes data/packets/ blind, writing data/annotator2.json
uv run python scripts/harness_attribution.py agree   --out docs/research/experiments/EXP-2026-11-009-harness-attribution/data
```

## Amendment A-1 (2026-11-16): the model half on Qwen 3.8 27B

Gemma is retired as a basis (operator). The LLM-planner arm was rerun on Qwen 3.8 27B at
`reasoning_effort=medium`, back to back with both model-free arms, at the same commit, with 32
workers. Data: `data/attribution-qwen.json` and `data/codings-qwen.jsonl`.

| | Saved, Gemma 4 26B (retired) | Qwen 3.8 27B (today) |
|---|---:|---:|
| LLM-planner coverage | 0.4858 | **0.5811** |
| … minus the authored plan (0.8526 today) | −0.3754 | **−0.2715** (SE 0.025) |
| … minus the deterministic planner (0.5173 today) | +0.006 | **+0.064** (SE 0.030) |
| questions lost (authored retrieves, the planner does not) | 105 | **71** |
| wrong relation, first cause | 68 | 44 |
| shape (attribute lookup planned as a traversal) | 12 | 8 |
| english_reread (downstream) | 14 | 12 |
| **downstream share, pre-registered rules** | 0.162 | **0.169** |
| downstream share, builder-walk reading (named in advance for A-1) | 0.410 | **0.437** |

- **The finding replicates on the open model.** The primary reading falls in the same band
  ("mostly model", 0.169). The builder-walk reading, named in advance this time, falls in
  "mixed" (0.437). Read together, as the main result was, RQ5 is **mixed**, and wrong relation
  choice is the largest single cause.
- **Qwen plans better than Gemma 26B did,** and better than the rules: +0.064, about two
  standard errors. Of its 71 losses, 26 are also lost by the deterministic planner.
- **Run checks:** zero model-port connections in the two guarded arms. Qwen's identity was
  verified before and after (token id plus default-rendering fingerprint). The model-free arms
  reproduce yesterday's reruns exactly (0.8526 and 0.5173).
- **The first A-1 attempt was void**, because the CAPEC Gremlin graph was empty (ISSUES).
