# PROTOCOL — EXP-2026-11-014 Era 2, after Step 7: what makes the fast decision models usable

Written 2026-11-17, before any model is called. It follows the operator's request to try each
idea on its own and see which helps and how (plan v2 §9, after "Step 7 — decision models
measured"). Step 8 waits on this.

## What was looked at before writing

This is disclosed because it shaped the design. Each item below used data already on disk;
no model was called.

1. **Step 7's saved run records** were re-analysed (EXP-2026-11-013, `data/runs/`):
   - the right answer's rank in each model's probabilities;
   - accuracy after averaging the two option orders;
   - pplx-decider's relation-choice accuracy, split by whether the right option's description
     is shared with another option (0.51 on 203 items) or unique (0.86 on 162).
2. **The rule filter below was dry-run on Step 7's relation items, gold included.**
   - It narrows 312 of the 458 items in the relation role population (erratum 1). These are
     285 items whose gold is a real relation and 27 "none" items.
   - On 188 items whose gold is a real relation, it leaves one option, and that option is
     the gold every time.
   - On 9 "none" items, it leaves one option, which is wrong.

   The rule's own gold-keeping rate is therefore known, and it is not a hypothesis here.

## Question

Step 7 found that the fast models often pick the wrong option. They were asked a forced
choice over options written for a schema, not for them. The question here: can we change
how the question is put, or the job they are given, so that they become usable? Which
change helps, by how much, and where?

Each change is tested **on its own** against Step 7's records as the control. Changes that
help are combined in a later round.

## Design

- **Decisions:**
  - relation choice (D4): 488 items;
  - grounding with "none of these" (D2 and D3): 397 items.

  These are Step 7's Phase A items, unchanged (`items.jsonl`, sha256 `5e5be419…`). The
  sealed held-out banks stay unread. The exit decision and the Phase C tests are not in
  this experiment.
- **Models:**
  - `pplx`: pplx-decider, `:7500`;
  - `d3`: d3-lite, `:5107`, unloaded after use;
  - `qwen_prob`: Qwen 3.8 27B with reasoning off, read by the log-probabilities of the
    option letters.

  The clients and settings are Step 7's.
- **Controller:** `qwen_reason` (Qwen with reasoning medium) is used only where a treatment
  hands it a different menu (the shortlist).
- **Control:** Step 7's records for the same model on the same items. A drift check
  (Procedure) confirms that the decision servers still answer as they did.

### Round 1: five treatments, each alone

| Treatment | What changes | Decisions | Models |
|---|---|---|---|
| **Wording** | Option text only: one plain reading per relation, in place of the arrow and the shared description | D4 | pplx, d3, qwen_prob |
| **Yes/no** | Question shape: one yes/no question per option in place of one forced choice | D4, D2+D3 | pplx, d3; qwen_prob as server time allows (below) |
| **Wording × yes/no** | Both: completes a 2×2 with the control | D4 | as yes/no |
| **Shortlist** | The model's job: cut the menu, then the controller chooses from the shortlist | D4, D2+D3 | shortlist from saved records; controller `qwen_reason` |
| **Rule filter** | The menu: options whose target type the question does not name are removed by rule first | D4 | pplx, d3, qwen_prob |
| **Verifier** | The model's job: approve or reject a pick that is already made | D4, D2+D3 | pplx, d3 checking `qwen_prob`'s saved picks |

### Later rounds, specified by amendment before they run

- **Round 2:**
  - combinations of the treatments that pass their hypotheses;
  - **combiner:** a small logistic layer over a model's probabilities plus signals that do
    not come from a model. These are the name index's top score and score gap, an exact
    name match, and whether the rule filter narrowed the item. It is fitted on each split's
    calibration half.
- **Round 3, fine-tune:** a d3-lite adapter trained on items built from the card. It runs
  only if the operator can fine-tune the decision models; training anchors are kept apart
  from test anchors.

## The treatments in detail

### Wording

- **Readings file.** `data/readings.json` holds one reading for each relation option
  that occurs: 63 in all (36 for ATT&CK, 27 for CAPEC). Each is keyed by dataset, label,
  relation, direction and target.
- **Writer.** A Claude Opus 5.5 subagent at medium effort.
  - **Input:** only the card's node and relation descriptions and the 63 keys.
  - **Not seen:** questions, items, or results.
  - **Why Opus:** Sonnet wrote the questions, so a different writer avoids shared phrasing.
  - **The brief** is saved as `data/readings-brief.md`.
- **Form.** A noun phrase from the known entity's point of view, such as "the
  sub-techniques this software uses":
  - plain words, no schema labels;
  - at most 12 words;
  - distinct from every other reading of the same label.

  The build checks these rules. A reading that breaks one goes back to the writer once,
  with the failed check named.
- **Frozen before the first call.** The file and the brief are hashed in `data/POINTERS.md`.
- **On the item,** the reading replaces the whole option text. "None of these relations" is
  unchanged.
- **Diagnostic, not a hypothesis:** the word overlap between each item's gold reading and
  its question (token Jaccard), so that a gain from copying words can be seen.

### Yes/no

- **One binary question per real option,** with the options `yes` and `no`, as in Step 7's
  Phase C:
  - **D4:** "Following this relation from the known entity: `<option text>`. Does it answer
    the question?"
  - **D2/D3:** "Does the question refer to this `<label>`: `<option text>`?"
- **"None of these" is not asked.** It is the outcome when no option passes.
- **Sending:**
  - **pplx:** an item's questions go in one request.
  - **d3:** one request with a question list.
  - Both are sent twice, in two seeded question orders, which gives the flip rate.
  - **qwen_prob:** one call per option. It has no option order, so its flip rate is 0 by
    construction, and this is reported as such.
- **Rule.** `s_i` is the probability of `yes` for option `i`.
  - The pick is `argmax s_i`.
  - The answer is "none" if `max s_i < θ`.
  - **Confidence** is `max s_i` for a real pick and `1 − max s_i` for "none".
- **Fitting θ:**
  - Within each threshold-transfer split, θ is fitted on the calibration half: the value
    in 0.05–0.95 (step 0.05) with the highest accuracy.
  - The gate threshold τ is then fitted on the confidence, as in Step 7.
  - For the single accuracy figure, θ is cross-fitted over two seeded folds by anchor.
- **Qwen budget.** qwen_prob's yes/no calls (about 9,100) run in a seeded anchor order on
  the shared server.
  - It is reported on the anchors completed, provided that is at least a third of them.
  - With fewer than a third, it is reported as not run.
- **Wording × yes/no** is the same, with the readings as option text.

### Shortlist

- **From saved records.** Using each model's first-order probabilities in Step 7's records,
  real options are kept in order of probability until their summed probability reaches `q`.
  "None of these" is always added, so the controller can still say "none".
- **Fitting q.** Within each split, `q` is fitted on the calibration half: the smallest
  value in 0.50–0.99 (step 0.01) that keeps the gold in the list for ≥ 0.95 of items whose
  gold is a real option. The test half reports gold recall and the mean number of real
  options kept.
- **The controller stage:**
  - **Which shortlister.** Among the models with median test recall ≥ 0.95, the one with
    the smallest median list wins; on a tie, the faster model. One list per item comes
    from `q` cross-fitted over two seeded folds by anchor.
  - **What the controller sees.** The shortlist is shown in the item's first option order,
    not sorted by probability, so the order does not leak the shortlister's preference.
  - **The comparison.** `qwen_reason` answers each item twice, on the shortlisted menu and
    on the full menu. The two calls are made back to back, item by item, on the same day,
    so the comparison is paired on one server state.

### Rule filter

- **The rule.** Each real option has a target label. Its words are the CamelCase split,
  lower-cased, in spaced, hyphenated and joined forms, each with an optional plural `s` or
  `es`.
  - If the question names at least one option's target, but not every option's, only the
    named options and "none" are kept.
  - Otherwise the item is unchanged.
- **New calls only for narrowed items:** 312 items (erratum 1), in both orders, for all three
  models.
  Unchanged items use the control records.
- **Items left with one real option are still asked.** The choice is then between that
  option and "none", which tests "none" directly.

### Verifier

- **Items.** Every first-order pick of `qwen_prob` in Step 7's records that is a real option
  (812 items over D4, D2 and D3).
- **Question.** The item's context and question, then: "Proposed answer: `<option text>`. Is
  it the right one?" The options are `yes` and `no`, in two orders. The option text is
  Step 7's, so the verifier's effect is isolated from the wording.
- **The gate signal** is the verifier's probability of `yes`. It is compared against
  `qwen_prob`'s own top probability on the same picks.
  - On the full D2+D3 population, Step 7 recorded 0.560 coverage at 0.044 wrong.
  - On D4, no gate held.
- **Exploratory:** the smaller of the two confidences, as one combined signal.

## Metrics: one scoreboard for every treatment

These are computed per treatment, model and decision, on Step 7's role populations:
- **D4:** items with two or more real options, plus the "none" variants;
- **D2+D3:** all items.

1. **Accuracy:** the answer equals the gold.
   - Reported for all items, for items whose gold is offered, and for items whose gold is
     "none".
   - **D4 only:** also split by whether the gold's Step 7 description is shared with
     another real option.
2. **"None" recall and precision.**
3. **Threshold transfer:**
   - median coverage, median wrong rate and 90th-percentile wrong rate;
   - over 200 splits by anchor, with seed 20261116;
   - the same splits as Step 7 (`utils/decision/score.transfer`), so differences are paired
     by split.
4. **Flip rate** between the two orders.
5. **Role** by Step 7's rule (alone, gate, second opinion, not used).
6. **End-to-end accuracy and controller calls saved.**
   - In each split's test half, items the gate accepts take the treatment's answer. All
     other items take `qwen_reason`'s Step 7 answer.
   - The median over splits is reported; the share accepted is the share of controller
     calls saved.
   - For the shortlist, end-to-end accuracy is the controller's accuracy on the shortlisted
     menu.
7. **Cost:** calls per item, plus median and 90th-percentile latency from a sequential probe
   of 40 items per model. Qwen latency carries Step 7's caveat about server-side waits.

**Differences from the control** are taken on the same items:
- **accuracy and recall:** with 95% intervals from 2,000 bootstrap resamples over anchors;
- **gate coverage and wrong rate:** as the per-split difference, with the 2.5th and 97.5th
  percentiles over the 200 splits.

**Shortlist only:**
- gold recall and mean list size in test, per shortlisting model;
- the controller's accuracy, "none" recall and generated tokens, on shortlisted against
  full menus.

## Hypotheses and what would falsify them

There are six primary hypotheses, with no correction for multiplicity. Everything else is
exploratory and labelled so in RESULTS.

| | Hypothesis | Falsified if |
|---|---|---|
| **H1** wording | pplx's D4 accuracy rises by ≥ 0.05, and at least two thirds of the gain comes from items whose gold description was shared | the gain's interval includes 0, or the gain on shared items is no larger than on unique ones |
| **H2** yes/no | "None" recall (D3 items plus D4 "none" items) rises by ≥ 0.15 for both pplx and d3, while accuracy on items whose gold is offered falls by ≤ 0.03 | either model's recall gain has an interval that includes 0, or offered accuracy falls by more than 0.03 |
| **H3** 2×2 | pplx or d3 holds a D4 gate (Step 7 rule) in at least one cell | neither does in any cell |
| **H4** shortlist | some fast model keeps the gold at ≥ 0.95 test recall with a median of ≤ 3 real options, on D4 and on D2+D3, and the controller on the shortlist is not worse than on the full menu by more than 0.02 | no model meets the recall and size bound, or the lower end of the controller's accuracy difference is below −0.02 |
| **H5** rule filter | on narrowed items, pplx's and d3's accuracy each rises by ≥ 0.10 over the control on the same items, and "none" recall on the narrowed "none" items does not fall | either gain's interval includes 0, or "none" recall falls |
| **H6** verifier | on D2+D3, a pplx or d3 verifier on `qwen_prob`'s picks gives higher median gate coverage than `qwen_prob`'s own confidence, at ≤ 0.05 median wrong; on D4, it gives a gate where none held | neither part holds |

## Threats, stated in advance

- **Same items, tuning split.**
  - Every treatment is scored on the items Step 7 already used. Round 2 selects treatments
    on those same items.
  - Treatments that pass are leads. Before the agent uses them on held-out banks, their
    thresholds are re-fitted and their effects checked on held-out items.
- **The questions name target types.** The banks came from templates and were then
  re-worded; the operator judged the phrasing expert-like. The rule filter's reach (312 of
  458, erratum 1) depends on that. The rule filter's and the readings' effects may shrink on novice or terse
  wording, which no bank tests (EXP-2026-11-012, operator's read).
- **Readings are written, not given.**
  - The card does not hold per-direction readings today; a model wrote them.
  - Deployed, they become a card field written once per graph. Whether a fixed template
    could replace the writer is a follow-up.
- **Only 65 anchors.**
  - Each test half holds about 32 anchors.
  - qwen_prob's yes/no subset may hold fewer, and its transfer figures will be marked thin.
- **A shared Qwen server.** Latency includes queueing. The shortlist comparison is paired
  back to back for this reason.
- **The control is a day old.** The decision servers are re-checked on a sample before any
  treatment runs (Procedure).

## Calls

| Treatment | pplx requests | d3 requests | Qwen calls |
|---|---:|---:|---:|
| Drift check | 200 | 200 | 0 |
| Wording | 976 | 976 | 976 (qwen_prob) |
| Yes/no | 1,770 | 1,770 | up to about 9,100 (qwen_prob, one token each) |
| Wording × yes/no | 976 | 976 | up to about 6,100 (qwen_prob) |
| Rule filter | 624 | 624 | 624 (qwen_prob) |
| Verifier | 1,624 | 1,624 | 0 |
| Shortlist controller | 0 | 0 | about 1,770 (`qwen_reason`, paired) |

- **The decision servers** are local and unshared; their load takes minutes.
- **On the Qwen server,** at most 8 calls are in flight, the shared server's limit. Its
  share is hours under today's load.
- **Run order:**
  1. the decision-server treatments;
  2. qwen_prob's wording and rule-filter calls;
  3. the shortlist controller;
  4. qwen_prob's yes/no calls, last, as time allows.

## Procedure

```bash
E=docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability
S=docs/research/experiments/EXP-2026-11-013-era2-decision-models
uv run python scripts/era2_usability.py readings --out $E/data          # writer brief + check; frozen before any call
uv run python scripts/era2_usability.py build --control $S/data --out $E/data
uv run python scripts/era2_usability.py drift --control $S/data --data $E/data --arms pplx,d3
uv run python scripts/era2_usability.py run --data $E/data --treatments wording,yesno,wording_yesno,rulefilter,verifier --arms pplx,d3
uv run python scripts/era2_usability.py run --data $E/data --treatments wording,rulefilter --arms qwen_prob
uv run python scripts/era2_usability.py shortlist --control $S/data --data $E/data   # picks the shortlister, then runs qwen_reason paired
uv run python scripts/era2_usability.py run --data $E/data --treatments yesno,wording_yesno --arms qwen_prob
uv run python scripts/era2_usability.py score --control $S/data --data $E/data
```

- **Drift check.** 100 seeded items from each decision (D4 and D2+D3) per decision server,
  first order.
  - If the top option agrees with Step 7's record on ≥ 0.97 of them, Step 7's records are
    the control.
  - Otherwise, that server's control is re-run in full before any treatment, and the
    re-run becomes the control.
- **Logging.** Every call is logged with its item id, treatment, model, order,
  probabilities, latency and model identity.
- **Runs** append to `data/runs/<treatment>/<arm>.jsonl` and resume where they stopped.
- **Before building,** the Gremlin vertex counts are checked.
- **d3-lite** is unloaded after its runs.

## Erratum 1, 2026-11-17, before any model call

- **The rule filter narrows 312 of the 458 items in the relation role population, not 365.**
  The first version gave 365, which is the number of items whose gold is a real relation
  (285 of them are narrowed). The count was re-taken when the builder was written.
- **Changed by this:**
  - the item count in "What was looked at before writing" and in "Rule filter";
  - the reach in "Threats";
  - the call budget: 624 calls per model, not 730.
- **Not changed:** the rule, the hypotheses and the falsifiers.


## Amendment 1, 2026-11-17, before any model call: decision servers only

**Operator, 2026-11-17:** no general language model is called in this experiment; only the
two decision servers are used, pplx-decider on `:7500` and d3-lite on `:5107`. A general
model is not trained for these decisions.

**What changes:**

- **No `qwen_prob` or `qwen_reason` calls.** Every row naming `qwen_prob` as a model is
  dropped, and so is the Qwen column of the call table. The models are `pplx` and `d3`.
- **Shortlist: decision models choose from the shortlist.**
  - Each of `pplx` and `d3` shortlists from its own Step 7 records, with `q` fitted and
    cross-fitted as before.
  - Each shortlist is then put to both `pplx` and `d3` as a new choice item, in two orders.
    That gives four cells (shortlister × chooser) on D4 and D2+D3.
  - **The comparison is the chooser on the shortlist against the same chooser on the full
    menu.** The full menu is the chooser's Step 7 record, kept as the control by the drift
    check.
- **Verifier: the decision models check each other's picks, and their own.**
  - **Picks:** the first-order real picks in Step 7's records of `pplx` and of `d3`.
  - **Verifiers:** `pplx` and `d3`, in two orders.
  - **The gate comparison:** the verifier's probability of `yes` against the picker's own
    top probability, on the same picks.
- **End-to-end accuracy** still sends items that are not accepted to `qwen_reason`'s
  *saved* Step 7 answers. This is a reference figure computed from committed records, with
  no new call. It stands for "the controller", whatever model that turns out to be.

**Hypotheses H4 and H6 are restated; H1, H2, H3 and H5 are unchanged except that `qwen_prob`
is gone.**

| | Hypothesis | Falsified if |
|---|---|---|
| **H4** shortlist | some fast model keeps the gold at ≥ 0.95 test recall with a median of ≤ 3 real options, on D4 and on D2+D3; and in at least one cell, the chooser on the shortlist is not worse than on the full menu by more than 0.02 | no model meets the recall and size bound, or every cell's lower bound on the accuracy difference is below −0.02 |
| **H6** verifier | on D2+D3, a verifier's probability of `yes` gives a picker higher median gate coverage than its own confidence, at ≤ 0.05 median wrong, for at least one picker–verifier pair; on D4, some pair gives a gate where the picker's own confidence gives none | neither part holds |

**Calls, revised** (pplx and d3 each):

| Treatment | Requests per server |
|---|---:|
| Drift check | 200 |
| Wording | 976 |
| Yes/no | 1,770 |
| Wording × yes/no | 976 |
| Rule filter | 624 |
| Shortlist, chooser | 3,540 |
| Verifier | about 3,200 |

**Server state at the time of writing.** `:7500` is an SSH tunnel whose far end resets the
connection. The pplx runs wait until the server is back, and the drift check runs first
when it is.

**Counts from the builder** (`data/build.json`), before any call:
- **The relation role population is 464 items:** 458 with two or more real options, plus 6
  "none" items that keep one real option. Erratum 1's "312 of the 458" should read "312 of
  the 464".
- **Grounding:** 397 items.
- **Rule filter:** 312 narrowed items, of which 197 are left with one real option.
- **Verifier:** 739 pplx picks and 746 d3 picks.
- **Shortlist:** 1,722 items.
- **Fitted `q`:** pplx 0.96 on D4 and 0.82 on D2+D3; d3 0.78 and 0.57. Both folds agree.


## Amendment 2, 2026-11-17, before any round-2 call: round 2

**Operator, 2026-11-17:** run round 2 before Step 8. Decision servers only, as in
amendment 1.

### What was looked at before writing

All of round 1 (RESULTS, committed in a5828e0a):
- **Wording is the one change that helps.**
- **The only gate a fast model misses on flips alone** is d3 with wording on D4: coverage
  0.2198 at 0.049 wrong, flip 0.1336.
- **On D2+D3, both models' Step 7 controls are second opinions with flips just over the
  bound:** pplx is at 0.2015 coverage, 0.0494 wrong and 0.1234 flip; d3 at 0.262, 0.0485 and
  0.1108.
- **pplx's wording shortlist and the two-model average have not been computed.** Both are
  computable from saved records, and neither will be computed before this amendment is
  committed.

### Round-2 treatments

| Treatment | What changes | Decisions | Models | New calls |
|---|---|---|---|---|
| **Order averaging** (Q64) | the pick and its confidence come from the mean of the probabilities over two option orders | D4 with wording; D2+D3 control | pplx, d3 | two more orders per item (below) |
| **Two-model average** | the mean of pplx's and d3's probabilities, per option order | D4 with wording; D2+D3 control | pplx + d3 | none |
| **Both** | the mean over both models and both orders | as above | pplx + d3 | none beyond order averaging |
| **Wording shortlist** | pplx shortlists from its *wording* records, then a model chooses from the list with the readings as option text | D4 | shortlister pplx; choosers pplx and d3 | two orders per item |

**Why the pre-registered combiner is replaced.** It was a logistic layer over model
probabilities plus name-index signals. The saved items carry no index scores (D2 has only a
BM25-hit flag), and re-querying the index is not a decision-server call. A combiner over
model probabilities alone is the two-model average. The index-signal combiner moves to a
later amendment, if it is wanted.

**Order averaging, in detail.**
- **Two new orders per item** (orders 2 and 3). They are seeded the way Step 7 seeds its
  orders (`f"{seed}|{id}|{i}"`, for i = 2 and 3), with "none" kept last. Order 3 is rotated
  if it equals order 2.
- **Accuracy, AUROC and the gate** are computed on the mean of orders 0 and 1.
- **Flip** is whether the top pick of mean(orders 0, 1) differs from the top pick of
  mean(orders 2, 3). This is the same question as round 1's flip, asked of the averaged pick.
- **A limitation.** An item with two real options has only two orderings, so its averaged
  pick sees the same pair twice. Its flip then measures server nondeterminism only. RESULTS
  will report the share of such items.

**The wording shortlist, in detail.**
- **Same rule as round 1's shortlist:** order-0 probabilities, with `q` cross-fitted over two
  anchor folds to keep 0.95 of gold answers.
- **Built from** `runs/wording/pplx.jsonl` in place of Step 7's records.
- **Each list item keeps the readings as option text**, and is asked in two orders.
- **The comparison** is the chooser on the list against the same chooser on the full
  wording menu (round 1's wording record).

### Hypotheses

| | Hypothesis | Falsified if |
|---|---|---|
| **H7a** order averaging, D4 | with wording, pplx or d3 averaged over two orders holds a D4 gate by Step 7's rule: median coverage ≥ 0.20, median wrong ≤ 0.05, flip ≤ 0.10 | neither model holds a gate |
| **H7b** order averaging, D2+D3 | pplx or d3 averaged over two orders holds a D2+D3 gate by the same rule | neither does |
| **H8** two-model average | on D4 with wording, the two-model average's accuracy exceeds pplx-with-wording's by ≥ 0.02, with the paired interval above 0 | the gain is below 0.02 or the interval includes 0 |
| **H9** wording shortlist | pplx's wording shortlist keeps the gold at ≥ 0.95 test recall with a median of ≤ 3 real options; and pplx choosing from it is not worse than pplx with wording on the full menu by more than 0.02 (lower bound ≥ −0.02) | the recall or size bound fails, or the lower bound is below −0.02 |

**The scoreboard is round 1's:**
- accuracy and its paired difference, over anchors;
- "none" recall;
- gate coverage and wrong rate over the same 200 anchor splits;
- end-to-end accuracy with Qwen's saved answers as the fallback;
- agreement with that fallback on gated items;
- flip;
- role.

**The comparisons:**
- order averaging, against the single-order version of the same treatment (wording, or the
  Step 7 control);
- the two-model average, against pplx with wording;
- "both", against the better of the two.

### Calls (pplx and d3 each)

| Treatment | Requests per server |
|---|---:|
| Orders 2 and 3 on the wording items | 928 |
| Orders 2 and 3 on the D2+D3 control items | 794 |
| Wording shortlist, as chooser | about 928 |

Drift needs no new check: both servers were checked earlier on 2026-11-17. If a server has
restarted, the drift check is re-run first.
