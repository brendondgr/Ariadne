# POINTERS — EXP-2026-09-010

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

Filled 2026-09-09 (RESULTS.md A-1); hashes are of the paths as they stand on
that date. Neither tree has been written to since 2026-09-07 00:00.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| First pair, both arms | `docs/evaluation/experiments/arm-identity-2026-09-06` | 57915402 | `sha256:34941b6c6010b718b69873e1e0f0d5f634d282a298c6ccd56b9991f5a3016849` | Tree. `{a,b}/{deterministic,generic}/answers/`, 284 answers each plus a run `manifest.json`. The **deterministic** result (2/284 pre-registered, 284/284 content-identical) is computed from `a/deterministic` vs `b/deterministic`. The `generic` pair here is the one PROTOCOL A-2 invalidated (run B lost its narrator on 60 answers) and is kept as evidence, not as a result. No judgment sidecars: this experiment grades nothing. |
| Guarded `generic` re-run | `docs/evaluation/experiments/arm-identity-rerun-2026-09-06` | 14775440 | `sha256:6442cb0bf744ef68c70654e582cd127a57522a3f7c0caf518c65148fcbf68323` | Tree. `a-try1/generic` and `b-try1/generic` (284 answers each) are the two captures behind 276 compared / 133 identical / 0.4819. `a-try2/generic` holds 84 answers from an aborted retry that no reported number reads. |
| Question bank | `docs/evaluation/composition/bank/bank-dev.json` | 573495 | `sha256:a4ca6702029cae7784574b0307b9f76d4718a039f3254f2c0ff708a2fa1a4119` | The 284-question dev half; hash asserted in both pre-flights. |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
