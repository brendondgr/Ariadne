# RESULTS — EXP-2026-11-007 Era 2 Step 2: the reply-repair layer replayed over every saved kill-test reply

## 1. Headline

Both gates pass over all 15,748 saved replies:
- **H1:** zero silent repairs;
- **H2:** zero changed readings against the kill tests' parser.

**The pre-registered policy rescued 16 typed replies, and none were real.** All 16 had been
cut off at the token cap, and closing their JSON produced requests that were missing their
tail. The fixed policy never closes a capped reply, and it rescues 0. So the kill tests lost
nothing to parsing, and no verdict changes.

The live matrix ran both local models (three endpoints) through a two-question tool loop,
and every check passed. A registry entry pointed at the wrong model was refused before any
call.

## 2. Results table

From `data/replay.json` (cap-aware, the shipped policy) and `data/replay-preregistered.json`
(close-always, the pre-registered policy). One deterministic pass over saved replies; n_runs = 1.

| | pre-registered (close-always) | shipped (cap-aware) |
|---|---|---|
| replies | 15,748 | 15,748 |
| capped (`finish_reason = length`) | 1,067 | 1,067 |
| typed replies the old parser read | 7,579 | 7,579 |
| typed replies the new layer read | 7,595 | 7,579 |
| rescued | 16 (all capped) | 0 |
| changed readings (H2) | 0 | 0 |
| silent repairs (H1) | 0 | 0 |
| typed replies still invalid | 532 | 548 |

Where the 16 rescues came from (pre-registered policy):

| Cache | Model | Arm | Rescued |
|---|---|---|---|
| exp006 C-generate | Gemma | typed2-3shot | 10 |
| exp006 C-generate | Gemma | typed3-3shot | 3 |
| exp006 C-repair | Gemma | typed3-3shot-repair | 1 |
| exp006 B-generate | Gemma | typed2-3shot | 1 |
| exp005 B-generate | Gemma | typed2-0shot | 1 |

**What the rescued objects contain.** 15 of 16 have no `answer` field. The 16th has
`"answer": {"kind": "aggregate", "fn": ""}`, an empty function. Values are chopped
mid-string: `"France 201"`, `"SCORED_"`, an edge `"to": ""`. None is a request the model
finished.

**The live matrix.** `data/matrix-live-3-entries.jsonl`: test `toolcall-roundtrip`, 2
questions, 3 registry entries.

| Model (served by) | Questions | Called on turn 1 | Calls known | Arguments readable | Finished | Cited a given handle | Answer right | Repairs |
|---|---|---|---|---|---|---|---|---|
| gemma4-31b (106) | 2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0 |
| qwen38-27b (248046) | 2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0 |
| gemma4-31b-remote (106) | 2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0 |

**The swap check.** `data/matrix-live-swap-refused.jsonl`: a registry with `gemma4-31b`
pointed at alias `default-model-2`. It was refused before any test call: "expected end-of-turn
id 106 (gemma), got 248046".

## 3. Figures

None.

## 4. Interpretation

Expectations against outcomes:

| | Expected | Outcome |
|---|---|---|
| H1 silent repairs | 0 | **0: pass** |
| H2 changed readings | 0 | **0: pass** |
| E1 Gemma's capped part-C replies stay invalid | 0 of 161 typed3-3shot recovered | **Missed under the pre-registered policy (3 of 161 "recovered", all incomplete). Met under the shipped policy (0).** |
| E2 at most 2% rescued per cache | at most 2% | Met: the maximum is 13 of 900 (1.4%), in exp006 C-generate Gemma, pre-registered policy |
| E3 no verdict can change | bound below margin | Met: the largest bound is 13/450 = 0.029 against the 0.129 to 0.222 the part-C H2 verdicts missed by. And no rescued object is a complete request. |

- **For the kill tests:** the typed format did not lose on parsing. The 532 to 548 invalid
  typed replies are capped or empty replies (Gemma, mostly part C), which is a token-budget
  and thinking-length effect, not a parser effect. That supports the plan's choice of a
  generous cap plus a runaway check, not more repairs.
- **For the agent layer:** the repair ladder is safe to ship once closing is conditioned on
  why the text was truncated.
- **For RQ5 (harness vs model):** this is weak evidence. The parsing harness was not where
  the kill tests lost.

## 5. Threats to validity

- **Saved replies are the last 6,000 characters of the content.** A longer reply is cut at
  its start, which could only hide a leading fence. No reply in the caches is that long and
  well formed, so the effect is nil here. It still bounds what a replay of other runs could
  recover.
- **The kill tests asked for free-text JSON, not native tool calls.** The leaked-call repairs
  (Gemma markers, Hermes, Python-style) were never exercised by real replies here. Their
  evidence is the synthetic fixtures, plus the live matrix, where both models used native
  calls and needed no repair. Real leaks will show up in the Step 11 loop's logs.
- **The matrix is two questions on canned tool results.** It tests the format round trip,
  not retrieval.

## 6. What surprised us

- **Closing truncated JSON is the dangerous repair.** In GAIFA it fixes a parser artefact;
  applied to a capped reply it fabricates a request. The fix is one flag, but without the
  replay it would have shipped. A loop would then have executed half-requests and logged them
  as repaired.
- **A tool-call reply does not end on the end-of-turn token.** Gemma's ended on token 50. So
  identity has to be a separate plain probe, not read off each row.
- **The relay now serves only two distinct models.** The `:4000` `skynet` alias serves the
  same Gemma.

## 7. Follow-ups

- Step 3 records `model_call` events with the identity from the registry probe, not from the
  envelope.
- Step 11 reports leaked-call repairs observed in real loop runs; the expectation is few
  with native tool calls.
- A third model for the matrix and the study is an open operator decision (v2 plan §5).

## 8. Reproduction

```bash
uv run python scripts/era2_repair_replay.py --out docs/research/experiments/EXP-2026-11-007-era2-reply-repair-replay/data
uv run python scripts/era2_repair_replay.py --no-cap-aware --out docs/research/experiments/EXP-2026-11-007-era2-reply-repair-replay/data
uv run python scripts/matrix_run.py --models gemma4-31b,qwen38-27b,gemma4-31b-remote --questions 2
```
