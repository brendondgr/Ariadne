# Overnight, two tracks — settle the query arm while a second family re-grades

*Written 2026-09-04 00:40 EDT. **Supersedes
`2026-09-04-overnight-arm-settlement.md`**, which was written before two facts
were known: `gemma4-31B-MTP` on `:9091` accepts **32-way concurrency**, and it
is separate hardware from the qwen relay. That earlier plan sub-sampled the
cross-family check and ran everything in one line. Neither is necessary. The
holdout decision it argued is unchanged and is restated in §2.*

---

## 1. Introduction

The night has a hard edge: `:9091` shuts down at **09:00**, and at the time of
writing there are 8.6 hours left. It also has two independent machines — the
qwen relay and the gemma endpoint — so the work splits into two tracks that
share nothing but the answer files one of them reads.

Track A settles the query-writing arm, whose 0.3712 is a token-budget artifact
and whose only real support is a single 30-question run from August. Track B
re-grades everything the repair produced with a **different model family**, at
full n and order-counterbalanced, so the 0.1623 gap stops being a property of one
grader. Track B is the one with the expiry, so it starts first and does not wait
on Track A.

---

## 2. Gaps & Unanswered Questions

- **The holdout is still not spent, and the reasoning has not changed.** It
  answers C-023, it can be spent once, and `llm_query` is the arm that is not
  settled. Tonight settles it; a later night can then spend the holdout on
  **three** arms. Spending it now buys a two-arm number and forecloses the
  three-arm one forever. *The run asserts the seal by hash and by case id.*
- **Are the two endpoints really independent?** Everything about running them
  concurrently rests on this. *Assumption*: yes — `:9090` presents as an SSH
  tunnel and `:9091` is local — but yesterday relay contention silently
  corrupted a timing measurement, so **preflight measures it** rather than
  assuming: three judgments on each endpoint alone, then three on both at once.
  If throughput drops materially, the tracks serialise and Track B keeps
  priority.
- **How fast is gemma?** Unknown. From the qwen run, one answer costs about 146
  model-seconds; at 32 workers the full 1,136-judgment cross-family pass is
  **1.4 h if gemma matches qwen and 3.6 h at 2.5× slower**. *Assumption*:
  measure it on three judgments and size the phase from the measurement, not
  from this arithmetic.
- **Should gemma also grade the re-run arm?** Yes if Track A finishes in time —
  that turns the cross-family check into a full three-way. *Assumption*: it is a
  bonus phase, taken only if `:9091` has an hour left after the main pass.
- **Do the two graders use the same budget?** They must, or the comparison
  confounds grader with budget. *Assumption*: both at 32,768. If gemma cannot
  sustain that, **cut the sample, not the budget** — EXP-2026-08-021 found 7–8%
  of the largest answers fail to grade at smaller budgets and the failures land
  on the thorough ones.
- **What if `:9091` is not ready?** *Assumption*: preflight waits up to 20
  minutes, then records Track B as `not_run` and gives the whole night to
  Track A. It never blocks indefinitely.

---

## 3. Hierarchical Step-by-Step Instructions

### Track B — gemma, `:9091`, 32 workers. Starts first; expires 09:00.

#### Step 1: Preflight both endpoints, and measure whether they interfere

- **Locations**: `scripts/model_identity.py`, `utils/research_record/hashing`,
  new `scripts/overnight_two_track.py`; state in
  `docs/evaluation/composition/bank/overnight-2026-09-04-state.json`.
- **Rationale**: probe what each endpoint actually serves — the alias `skynet`
  has served three models, and `:9091`'s identity must be recorded not assumed.
  Hash the bank, assert both graph stores hold their expected counts, assert the
  holdout untouched. Then time three judgments on each endpoint alone and three
  with both busy: that number decides whether the tracks overlap, and it is the
  measurement whose absence spoiled yesterday's budget probe.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Overnight Two-Track (1/6) Complete: both
  endpoints identified, interference measured, holdout seal asserted.*

#### Step 2: Cross-family re-grade at full n, order-counterbalanced

- **Locations**: `utils.evaluation.judge_answers` over
  `docs/evaluation/experiments/post-repair-2026-09-03/{deterministic,generic}`,
  suffix `.gemma` and `.gemma2`, positions 1 and 2, 32 workers, 32,768 tokens.
- **Rationale**: 568 answers × 2 passes. The existing judgments are untouched
  because the suffix differs, so the two graders can be compared per case rather
  than only in aggregate. Two passes because the ~0.01 order effect applies to
  any grader and a single pass would confound it with the family change. The
  question is narrow and coarse — **does the ordering survive** — and at full n
  it is answered with an interval rather than an anecdote.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Overnight Two-Track (2/6) Complete: 1,136
  cross-family judgments over both post-repair arms.*

### Track A — qwen, `:4000`, 16 workers. No hard expiry.

#### Step 3: What an honest query-writing arm costs

- **Locations**: `scripts/builder_budget_probe.py` →
  `docs/evaluation/composition/bank/budget-cost.json`.
- **Rationale**: four real failing cases at 8192 / 16384 / 32768, 900 s ceiling,
  recording wall-clock, completion tokens and relay timeout rate. Yesterday's
  attempt was abandoned because a judging run shared the relay; tonight the
  judging is on other hardware, which is what makes this measurable at all. The
  output picks Step 4's budget: **the smallest at which a real query returns**.
  If none does, Step 4 does not run and that is the finding.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Overnight Two-Track (3/6) Complete: the
  per-budget cost of the query-writing arm, measured without contention.*

#### Step 4: The fair re-run C-012 has been waiting for

- **Locations**: `experiment_untruncated --arm llm_query --bank bank-dev.json
  --llm-max-tokens <from Step 3> --workers 8`, into
  `docs/evaluation/experiments/llm-query-fair-2026-09-04`.
- **Rationale**: the claim's support is one 30-question run; the only larger
  measurement is confounded by the import-time budget freeze fixed in `a1e20f6`.
  284 questions, plan held constant, query generation the only variable. **Hard
  cap 2.5 h** — a partly answered arm is not a measurement, and an overrun is
  recorded as `not_run` so Step 5 and Step 6 still have their hours.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Overnight Two-Track (4/6) Complete: the
  query-writing arm re-run at a budget that lets it answer.*

#### Step 5: Judge the re-run arm on the same instrument as the other two

- **Locations**: `judge_answers` positions 1 and 2 over Step 4's answers, grader
  `skynet`, 16 workers, 32,768 tokens. Then, **if `:9091` has an hour left**,
  the same answers under gemma for a three-arm cross-family picture.
- **Rationale**: same grader and protocol as the post-repair arms, or the
  three-way is not like-for-like. Skipped outright if Step 4 did not complete —
  half an arm graded is worse than none, because it looks like a number.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Overnight Two-Track (5/6) Complete: the
  re-run arm judged under the same protocol as the other two.*

#### Step 6: Roll up, record, and name what did not run

- **Locations**: `make new-experiment`, `scripts/score_bank.py`,
  `docs/reports/2026-09-04-overnight-report.md`, `docs/research/CLAIMS.md`.
- **Rationale**: every number cites an `EXP-` id or it does not exist. Report
  per-arm judged correctness under **both** graders with denominators, the
  per-grader ordering, and the cost table. C-012 is amended only if Steps 4 and
  5 both completed. A mandatory "what did not run" section, as the last overnight
  plan required, and an explicit restatement that the holdout is still sealed.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Overnight Two-Track (6/6) Complete: results
  recorded under two graders, with the phases that did not run named.*

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Two-track orchestrator | Independent tracks, per-phase caps, state file, resumable; Track B abandoned cleanly if `:9091` never comes up. | `scripts/overnight_two_track.py` |
| Orchestrator tests | Dry-run lists both tracks; a done phase is skipped on restart; a capped phase records `not_run`, not a partial figure; a dead `:9091` skips Track B without blocking. | `scripts/tests/test_overnight_two_track.py` |
| Preflight record | Both model identities, interference measurement, store counts, bank hash, holdout seal. | `docs/evaluation/composition/bank/overnight-2026-09-04-state.json` |
| Cross-family judgments | 1,136 `.gemma`/`.gemma2` judgments beside the existing ones. | `docs/evaluation/experiments/post-repair-2026-09-03/*/answers/` |
| Budget cost table | Wall-clock, completion tokens, timeout rate at three budgets, uncontended. | `docs/evaluation/composition/bank/budget-cost.json` |
| Fair re-run answers | 284 `llm_query` answers at an adequate budget. | `docs/evaluation/experiments/llm-query-fair-2026-09-04/` |
| Two-grader rollup | Judged correctness per arm per grader, with denominators and per-pass means. | `docs/evaluation/composition/bank/two-grader-judged.json` |
| Experiment record | Manifest, results, issues, hashed pointers; names every phase that did not run. | `docs/research/experiments/` |
| Morning summary | Jargon-free, rendered from artifacts, mandatory "what did not run". | `docs/reports/2026-09-04-overnight-report.md` |
