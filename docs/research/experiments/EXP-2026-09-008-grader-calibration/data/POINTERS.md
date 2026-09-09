# POINTERS — EXP-2026-09-008

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

Filled 2026-09-09 (RESULTS.md A-1); hashes are of the directories as they stand
on that date. No file under these paths was written after 2026-09-06 03:26.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Calibration set, all three graders | `docs/evaluation/experiments/calibration-2026-09-06` | 1916748 | `sha256:84cfc4a13c1e7fb51c12f87b5574be9a3901171b7d589366cfccc2b4d909d5d4` | Tree. `{ceiling,mid,low}/answers/` hold the 60 frozen answers plus one judgment sidecar per model (`*.judgment.{gemma31,gemma26,qwen}.json`: 60 / 58 / 60 — the two missing `gemma26` mid-band judgments are the `*.gemma26.error.txt` endpoint failures) and `selection.json`. Every phase-A figure in the manifest is computed from these sidecars. |
| Band selection | `docs/evaluation/experiments/calibration-2026-09-06/selection.json` | 9988 | `sha256:6aa7161ff6ba16412a9b7bc738ccd69989db884a35dab6ace7e1d05305570e33` | Which 20 cases form each band and which run directory each answer was copied from; seed 20260906. |
| Thinking-cap probe, capped | `docs/evaluation/experiments/thinkcap-probe-2026-09-06/llm_query` | 198292 | `sha256:772bdf821774e413af7b45269191cc58f02666e721ffaff22571d0ceb31e856d` | Tree. 30 `llm_query` answers generated at `LLM_THINKING_BUDGET=512` plus the run `manifest.json`. The capped column of the thinkcap table (0 retrieved / 28 gate-rejected) is read from these. No judgment sidecars: the probe was never graded. |
| Thinking-cap probe, uncapped comparator | `docs/evaluation/experiments/llm-query-split-2026-09-05/llm_query/answers` | 3108206 | `sha256:9bc9d4c721705de9fcff67ccc21193ed8f16b94cad745462a2beadada0cf0fba` | Tree. The settled uncapped `llm_query` run (284 answers); the probe's uncapped column (3 retrieved / 4 gate-rejected) reads the 30 answer files with the same case ids. The directory also carries `.judgment{,.pass2,.gemma,.gemma2}` sidecars written by other experiments' grading passes; this experiment reads none of them. |

Not pointed here: `docs/evaluation/experiments/holdout-spend-2026-09-05`. Phases
B/B2/B3 of the same overnight driver wrote 288 x 3 gemma judgment sidecars
(`.gem`, `.gemp2`) into it, and `data/state-gemma31.json` / `state-gemma31-b3.json`
record those passes — but they are EXP-2026-09-007's holdout grading, not this
experiment's numbers, and EXP-2026-09-007 points at that directory.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
