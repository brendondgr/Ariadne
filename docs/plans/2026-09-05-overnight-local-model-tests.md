# Overnight local-model tests — what is worth GPU time next

*2026-09-05, written after Steps 4 and 7 closed. Target is now a **full
conference paper or JMLR**, not a demo, so the standard is a reviewer trying to
break the instrument. Servers are restarting; this is not launched yet.*

## 1. Introduction

Today produced one finding that changes how every remaining judged measurement
should be run: **`gemma4-31B-mtp` returned exactly 1.0 on all 150 `composerfix`
answers and is saturated in 6 of 12 August bank cells.** A saturated grader
reports a gap of zero whatever is true, and three separate near-misses traced to
it — including a tie-break that was one commit from being published as four
arm-order reversals.

So the highest-value overnight work is **not another arm run**. It is finding out
which of the locally-available models can actually resolve differences near the
ceiling, and then spending the good ones on the two measurements still open.

Everything below is judging or calibration. **No pipeline runs, no graph writes,
no bank regeneration** — except Phase D, which is explicitly flagged.

## 2. Gaps & Unanswered Questions

- **Which local models are usable as graders?** Unknown, and today shows the
  answer is not "all of them". *Assumption*: measurable directly — run every
  alias over one frozen answer set and report spread, ceiling fraction and
  rank correlation. **This has never been done and it is cheap.**
- **Is C-012's family-sensitivity real?** On dev it is significant under qwen
  (+0.1147 [+0.0653, +0.1645]) and not under gemma (+0.0696 [−0.0024, +0.1450]).
  gemma never reached `llm_query`'s holdout answers. *Assumption*: 288 judgments
  settles it, and it is the single most informative measurement left.
- **Does C-021 rest on one grader by necessity or by accident?** gemma cannot
  measure it at all. *Assumption*: if calibration finds any second model with
  resolution near 1.0, C-021 gets a genuine second opinion for the first time.
- **Does the thinking cap change the third arm?** `LLM_THINKING_BUDGET=512` is
  wired and **has never been verified against a live endpoint**. *Assumption*:
  worth one bounded probe, not a full arm re-run, and it is the only phase here
  that generates rather than grades.
- **How much grader variance does the holdout carry?** One session per position.
  *Assumption*: repeat sessions bound it; low value unless a margin is close.

## 3. Phases, in priority order

Each phase is independently useful and independently skippable. A phase that
cannot complete is recorded `not_run`, never averaged partially.

#### Phase A — Grader calibration suite — ~45 min, HIGHEST VALUE
- **What**: every healthy alias on every endpoint grades the **same frozen 60
  answers**, chosen to span the score range (20 near-ceiling from
  `composerfix-dev`, 20 mid from `post-repair` `deterministic`, 20 low from
  `llm_query`).
- **Report per model**: mean, sd, fraction at exactly 1.0, number of distinct
  values emitted, Spearman correlation against the qwen reference, and a
  **saturated / usable** verdict.
- **Why first**: it decides who runs Phases B and C, and it turns today's
  accidental discovery into a stated method. **Probe every alias for its served
  model first — an alias is not a model (`D-028`), and `default-model-2` served
  two different families within six hours today.**
- **Deliverable**: `docs/research/experiments/<new>/data/grader-calibration.json`
  plus a one-line rule: *never grade a near-ceiling contrast with a model whose
  ceiling fraction on this suite exceeds X.*

#### Phase B — gemma on `llm_query`'s holdout answers — ~40 min, HIGH VALUE
- **What**: 288 judgments, suffix `.gem`, position 1, to match the other two arms
  already graded that way.
- **Why**: completes the holdout's second-family picture and directly tests
  whether C-012's family-sensitivity reproduces on unseen questions. C-012 is
  currently *positive in all four measurements it has and significant in three*.
- **Guard**: refuse to run if the served model is not gemma — `default-model-2`
  now serves qwen (the runner already enforces this).

#### Phase C — C-021 under a third opinion — ~50 min, HIGH VALUE IF PHASE A FINDS ONE
- **What**: the 150 `composerfix` answers under whichever model Phase A marks
  usable near the ceiling, suffixes `.c3` / `.c3p2`.
- **Why**: C-021 is the paper's methodological headline and rests on **one**
  named grader, because the only second family available saturates on it. A
  third opinion either corroborates +0.0322 or is the most interesting negative
  in the record.
- **Skip if**: Phase A finds nothing with resolution near 1.0. Record that as the
  result — *"no locally available model can adjudicate this contrast"* is itself
  publishable and is the honest reason the claim rests on one grader.

#### Phase D — Thinking-cap probe — ~90 min, MEDIUM, THE ONLY GENERATING PHASE
- **What**: `LLM_THINKING_BUDGET=512` against **30 questions only**, matched to
  30 from the settled run. Record `finish_reason`, completion tokens, reasoning
  tokens, wall time, and whether a query was built.
- **Why**: the cap is wired and unverified. A bounded probe answers "does it do
  anything at all" for a fraction of a full arm re-run.
- **Explicitly not**: a re-measurement of `llm_query`. If the probe shows an
  effect, that becomes a pre-registered experiment of its own — it does **not**
  silently replace 0.4031.

#### Phase E — Holdout grader variance — ~2 h, LOW, ONLY IF TIME
- **What**: two more qwen sessions over the holdout's three arms, position 1.
- **Why**: bounds grader variance on the holdout the way `EXP-2026-08-021` did
  for the banks. Low value because every holdout margin is far from zero —
  the smallest is +0.0831 [+0.0366, +0.1320].

## 4. Operating rules, all learned today

1. **Probe the served model before every phase and refuse on mismatch.** An
   alias served two different families within six hours today.
2. **Never treat process exit as success.** Count artefacts on disk. A chain that
   read exit-as-success drove 288 cases into a dead endpoint and wrote 656 error
   sidecars.
3. **A grading position is all-or-nothing across arms**, except position 1, which
   always attempts — it is the measurement, not the correction.
4. **One state file per process.** Two processes sharing one clobber each other.
5. **Disjoint cells, or one process.** Two writers on one judgment file can
   interleave into truncated JSON.
6. **Report saturation with every margin.** Where one side is at the ceiling the
   margin is a directional bound, not an estimate — and which bound depends on
   which side.
7. **A partial cell is not a result.**

## 5. Risks

| risk | mitigation |
|---|---|
| Every local model saturates near the ceiling | That is Phase A's result, not its failure. It explains why C-021 rests on one grader and belongs in the limitations section. |
| Phase D shows the cap helps | Do **not** fold it into the headline. It becomes a pre-registered experiment; the published figure ran the settled configuration. |
| An alias silently changes model mid-run | Guard in rule 1, plus `served_model` recorded on every judgment. Note that `judge.model` records the *environment* default and is not evidence (`I-6`). |
| Phase B contradicts C-012 on the holdout | **That is the finding.** C-012 becomes "positive in five measurements, significant in three of five", and the paper says so. |
