# RESULTS — EXP-2026-11-010 MiniCPM 4.7 35B against Qwen 3.8 27B on CypherBench

## 1. Headline

**The pre-registered rule says: ask for Qwen back.** MiniCPM 4.7 35B is clearly weaker than
Qwen 3.8 27B at turning graph questions into queries and typed requests. That holds in every
reading:

| MiniCPM reading | typed3 vs Qwen | free Cypher vs Qwen |
|---|---:|---:|
| thinking on, as served | **−0.220** | **−0.110** |
| thinking off | −0.305 | −0.360 |
| thinking on with its misfiled replies recovered (post-hoc) | −0.135 | −0.060 |

Every 95% CI excludes zero. Qwen's saved scores reproduce exactly on today's tree.

A large part of MiniCPM's thinking-on loss is a server and template quirk, not the model's
reasoning. **222 of its 800 replies** (28%) arrived with empty reply text: it answered without
thinking and never closed the think block the template had opened, so the server filed the
answer as reasoning. Recovering those still leaves it short of Qwen.

## 2. Results table

Exact records on 200 CypherBench questions. One run; temperature 0. "Δ" is MiniCPM minus Qwen,
paired, with a 95% CI.

| Arm | Qwen 3.8 (saved; replay identical) | MiniCPM, thinking on | Δ | MiniCPM, thinking off | Δ | MiniCPM, on + recovered (post-hoc) | Δ |
|---|---:|---:|---|---:|---|---:|---|
| free Cypher | 0.860 | 0.750 | −0.110 [−0.165, −0.055] | 0.500 | −0.360 [−0.430, −0.290] | 0.800 | −0.060 [−0.110, −0.010] |
| free Gremlin | 0.635 | 0.075 | −0.560 [−0.630, −0.490] | 0.340 | −0.295 [−0.360, −0.230] | 0.345 | −0.290 [−0.360, −0.220] |
| typed2 → Cypher | 0.945 | 0.590 | −0.355 | 0.620 | −0.325 | 0.820 | −0.125 [−0.180, −0.075] |
| typed3 → Cypher | 0.950 | 0.730 | −0.220 [−0.280, −0.155] | 0.645 | −0.305 [−0.370, −0.240] | 0.815 | −0.135 [−0.185, −0.080] |
| typed3 + repair re-ask | 0.950 | 0.735 | −0.215 | 0.715 | −0.235 | 0.820 | −0.130 |

**Reasoning-only replies, MiniCPM with thinking on** (empty text, the answer filed as
reasoning): 222 of 800 in all. Qwen had 0.

| Arm | Reasoning-only replies |
|---|---:|
| free Cypher | 11 |
| free Gremlin | 131 |
| typed2 | 57 |
| typed3 | 23 |

With thinking off, MiniCPM had none.

**Cost per reply** (median latency, median completion tokens):

| Run | Latency | Completion tokens |
|---|---:|---:|
| MiniCPM, thinking on | 8.7 s | 530 |
| MiniCPM, thinking off | 3.1 s | 83 |
| Qwen 3.8, medium | 8.9 s | 321 |

## 3. Figures

None.

## 4. Interpretation

### The decision

The primary arms are typed3 via Cypher and free Cypher, with thinking on. Both are worse by
more than 0.05, and both CIs sit entirely below zero, so the pre-registered decision is **ask
for Qwen back**. The thinking-off condition gives the same decision.

### How much is the quirk and how much is the model (post-hoc)

- **The mechanism.** The 222 reasoning-only replies were re-requested with thinking on and token
  ids. In 192, the think block was never closed (no token 248069) and the model stopped on its
  own, so the reasoning text *was* the answer, as one inspected case showed: a complete
  Gremlin query. Putting those back and re-scoring gives the last column.
- **What remains is the model.** MiniCPM is still 0.135 behind on typed3 and 0.29 behind on free
  Gremlin. The quirk costs it about 0.05 to 0.09 on most arms and is not the whole story.
- **The re-request was not perfectly deterministic.** 159 of 222 reproduced the same reasoning
  length at temperature 0 under concurrency. The recovered figures are an estimate, not a
  replay.

### Corrections to what I said earlier today

- **The quirk is not confined to one-word answers.** My first probe (4 of 10 one-word prompts;
  0 of 15 normal or tool prompts) was too small. On real query-writing prompts it hit 28% of
  replies, and 66% on Gremlin.
- **The client's re-ask with thinking off is the worse fix for this model.** It replaces a
  misfiled answer with a thinking-off answer, and thinking-off answers are much weaker here
  (free Cypher 0.500, against 0.800 recovered). For MiniCPM, taking the answer from a block the
  token ids prove was never closed would have been more accurate. This matters only if MiniCPM
  stays.

### What it means for era 2

- The loop needs a model that is good at mapping questions onto the schema, which Step 4 found
  is the largest single cause of lost answers. On that skill, Qwen 3.8 27B is measurably better
  than MiniCPM 4.7 35B.
- Qwen also closed its think blocks: 0 reasoning-only replies in 800.

## 5. Threats to validity

- **One benchmark,** and part A is development data for the typed format. Fair for ranking two
  models, not for claims about the format.
- **The Qwen reference ran on 2026-11-14.** The replay shows the evaluation side is identical
  today, and the generation code is byte-identical. The server and its vLLM build may differ,
  since Qwen ran under its own deployment.
- **Temperature 0, one run.** The post-hoc recovery shows MiniCPM's replies are not perfectly
  reproducible under concurrency.
- **MiniCPM ran with its default thinking and Qwen at `reasoning_effort=medium`.** MiniCPM has
  only "on" and "none"; "low" made no difference, so no closer match was available.

## 6. What surprised us

- **The scale of the misfiling:** 28% of replies, and two thirds of Gremlin replies.
- **Thinking off is far worse for MiniCPM than thinking on** on free Cypher (0.50 against
  0.75). MiniCPM needs its thinking; it cannot be switched off to save time.

## 7. Follow-ups

- **The operator's decision:** bring Qwen 3.8 27B back, or keep MiniCPM. If Qwen returns, its
  registry entry is ready apart from its open status. It needs one probe, checking token
  248046 plus a new prompt fingerprint.
- **If MiniCPM stays,** the client should take the answer from a provably unclosed think block
  rather than re-ask with thinking off (§4), and Steps 7–11 should expect lower accuracy.

## 8. Reproduction

```bash
uv run python scripts/minicpm_vs_qwen.py replay
uv run python scripts/minicpm_vs_qwen.py run --condition on
uv run python scripts/minicpm_vs_qwen.py run --condition off
uv run python scripts/minicpm_vs_qwen.py recover        # post-hoc
uv run python scripts/minicpm_vs_qwen.py compare --out docs/research/experiments/EXP-2026-11-010-minicpm-vs-qwen-cypherbench/data
```
