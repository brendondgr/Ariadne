# RESULTS — EXP-2026-11-022 Era 2 Step 9 Phases G–H: does showing the operators to the planner help, without harm?

## 1. Headline

**Exposure helps on the probe, by a wide margin.** With `ARIADNE_ALGEBRA_CORE` on, the typed
planner answers 87, 90 and 81 of the 99 core probe items exactly (Qwen T-lazy, Qwen T-full,
Gemma T-lazy-G). With it off, it answers 0.

**It is not shown to be harmless.**
- The stop rule fired on both core sittings, because Gemma's exact variant answers fell 354 → 338
  and 354 → 335.
- The two further fix rounds that Amendment 2 allows each failed their proving bar.

So both switches stay off by default. The final confidence bar was never computed: off-B and
core+ext were not sat. Step 9 closes on the engine result (EXP-2026-11-021: zero Cypher/Gremlin
disagreements) and this measured exposure result.

## 2. Results table

From `data/metrics.json` (`data/close_metrics.py`). One run per sitting (`n_runs: 1`). Variants
n = 699, dev n = 284, probe core n = 99, probe extended n = 16.

| Sitting (tree) | Arm | Variants exact | Variants CW | Dev kept | Dev lost | Dev CW | Probe core exact | Probe ext exact |
|---|---|---|---|---|---|---|---|---|
| off-A (f7b908ab) | T-lazy | 328 | 54 | 262 | 22 | 0 | 0 | 0 |
| | T-full | 346 | 52 | 269 | 15 | 0 | 0 | 0 |
| | T-lazy-G | 354 | 30 | 253 | 31 | 0 | 0 | 0 |
| core-1 (f7b908ab, superseded) | T-lazy | 331 | 46 | 262 | 22 | 0 | 84 | 0 |
| | T-full | 341 | 39 | 267 | 17 | 0 | 86 | 2 |
| | T-lazy-G | 338 | 31 | 251 | 33 | 0 | 80 | 4 |
| core-2 (840f20da, superseded) | T-lazy | 324 | 54 | 265 | 19 | 0 | 87 | 1 |
| | T-full | 343 | 47 | 268 | 16 | 0 | 90 | 0 |
| | T-lazy-G | 335 | 30 | 253 | 31 | 1 | 81 | 5 |

**Provisional confidence bar, core-2 against off-A alone.** This is a paired 95% bootstrap: 2,000
resamples, seed 20261118. Amendment 3's margins decide.

| Arm | Variants exact Δ [CI] | Variants CW Δ [CI] | Dev lost Δ [CI] | Dev CW Δ [CI] | Probe core Δ [CI] | Confident |
|---|---|---|---|---|---|---|
| T-lazy | −0.0057 [−0.0241, 0.014] | 0.0 [−0.0191, 0.0199] | −3 [−7, 0] | 0 [0, 0] | 0.8788 [0.8081, 0.9394] | yes |
| T-full | −0.0043 [−0.023, 0.0141] | −0.0072 [−0.0199, 0.0058] | 1 [0, 3] | 0 [0, 0] | 0.9091 [0.8485, 0.9596] | yes |
| T-lazy-G | −0.0272 [−0.0519, −0.0015] | 0.0 [−0.017, 0.0158] | 0 [−8, 7] | 1 [0, 3] | 0.8182 [0.7374, 0.8889] | **no** (variants exact) |

**Proving sets.** Each set holds the items the previous core sitting lost, the 60 controls and the
probe tune half. Each runs core and core+ext on all three arms; scores are in `fix{4,5,6}-small/score.json`.

| Round | Bar | Result |
|---|---|---|
| 4 (Amendment 1) | Gemma operator losses well below 17; no control lost to an operator; probe within 5 | passed (Gemma 4 of 14 on the lost items) |
| 5 (Amendment 4) | + no teaching refusal final | failed: 1 final refusal (empty repair reply), 1 control lost (two-label union narrowed) |
| 6 (Amendment 5) | same, controls restricted to those off-A answered right | failed: 3 controls lost (1 entity churn, 2 kept describes adding parents and tactics) |

## 3. Figures

None.

## 4. Interpretation

- **The operators answer the questions they were built for.** On the probe, off answers none and
  core answers 0.82–0.91 of the core items. The prediction was ≥ 0.5 for Qwen.
- **The harm sits in one model.** Both Qwen arms are inside every Amendment 3 margin on today's
  banks. Gemma loses about 3 points of exact variant answers in each core sitting. The loss is
  concentrated on questions that describe an entity (T4/T5), where Gemma reaches for a scan.
- **Each fix round removed the defect it targeted:**
  - text scans (round 4);
  - last-turn refusals (round 5);
  - narrowed seeds (round 6).

  Each time, the re-run met another plan shape the algebra path handles worse than today's
  path. The cap on rounds was pre-registered for exactly this. The switches stay off.
- **Step 10 does not depend on the operators.** Grounding, synonyms and the fast path build on
  today's typed planner, which is unchanged with the switches off: the hash test passes and the
  recorded steps compile byte-identically.
- No claim in `../../CLAIMS.md` moves. The era-2 operator claim waits on Q65.

## 5. Threats to validity

- **No off-B, no final bar.** The confidence intervals compare against off-A alone. Off-run
  churn (Gemma 350 in EXP-2026-11-018, 354 in off-A) is not in them.
- **The proving sets are re-runs of items selected for loss.** Recovery is partly regression to
  the mean, and new losses are partly churn. The control clause counts single items, so one
  churned control can fail a round (F-CTT-01 T3 in round 6).
- **Amendment 5 narrowed the control clause after a round-5 observation.** It counts only controls
  off-A answered right. This was written before round 6 ran, and it did not change round 6's verdict.
- **Fix rounds 4–6 exceed Stage 1's original three.** The operator authorised them (Amendment 1)
  and capped them (Amendment 2).
- **One model per family.** Gemma and Qwen differ, and other planners may differ again.

## 6. What surprised us

- **Two-label seeds.** A typed seed was stricter than the untyped path it replaced. Today's
  cross-graph step matches seed ids with no label. The algebra's `FromStep` added
  `(v:Technique)` and silently dropped every sub-technique. Of the 11 times a step was narrowed to
  one label of a two-label producer, 10 lost their item.
- **An empty repair reply makes the first turn's refusal final.** That case was not in the
  round-5 design.
- **Gemma's harm reproduced across two core sittings** (338 and 335 against off runs of 350 and
  354). Eleven items are exact in both off runs and lost in both core runs; three go the other
  way.

## 7. Follow-ups

- [Q65](../../OPEN_QUESTIONS.md): Gemma loses about 3 points of exact variant answers when it sees
  the operators. A switch-on default needs a fix for describe-an-entity questions, and a final bar
  with both off runs.
- [Q66](../../OPEN_QUESTIONS.md): a union that reads through describe steps keeps them, so their
  facet blocks add parents and tactics. Find every such plan shape with a model-free replay
  before any new sitting.

## 8. Reproduction

```bash
# Stage 3 sittings (off-A, core); each writes under docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h/
bash docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data/phase_h.sh off-A
bash docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data/phase_h.sh core
# proving sets (round N in 4, 5, 6), then their scores
bash docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data/fix6_prove.sh
uv run python docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data/fix6_score.py
# this folder's metrics
uv run python docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data/close_metrics.py
```

Before any sitting: the full pytest, then `uv run main.py --dataset attack --graph neo4j && uv run
main.py --dataset capec --graph gremlin`, and no pytest between the reload and the runs.
