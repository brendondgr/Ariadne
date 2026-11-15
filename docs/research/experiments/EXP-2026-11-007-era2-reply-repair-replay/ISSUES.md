# ISSUES — EXP-2026-11-007

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

<!-- Entry template — newest first:

## YYYY-MM-DD — <one-line summary>
**Impact:** what this changes about the reported numbers (e.g. "seed 3 excluded; n=4 not 5 for this cell").
**Cause:** the mechanism, if known.
**Resolution:** what was done. "Not resolved" is a valid answer.
**Paper implication:** what must be stated in the paper because of this.

-->

## 2026-11-15 — Closing truncated JSON was unsafe for replies cut off at the token cap; fixed after the pre-registered run
**Impact:** The pre-registered policy rescued 16 replies, all of them capped. Every one had lost its tail: 15 of 16 have no `answer`, and values are chopped (`"France 201"`, `"SCORED_"`). Under the fixed, cap-aware policy the count is 0. Both runs are reported. Neither changes any kill verdict, because the closed requests are incomplete and would not have scored.
**Cause:** `close_json` came from GAIFA, where it repairs vLLM's streaming Gemma parser dropping the closing `"}` of a call that was complete. A reply that stops at `max_tokens` is genuinely incomplete, and closing it manufactures a plausible object.
**Resolution:**
- `parse_arguments(..., cut_off=True)` and `extract_json_object(..., cut_off=True)` refuse to close. They return `bad_arguments` with an `args_bad` event that names the cap.
- `toolcalls.finalize` passes `cut_off` for the last call of a reply whose `finish_reason` is `length`.
- Regression tests use one real capped reply from EXP-2026-11-006 part C.
**Paper implication:** A harness that closes truncated JSON must condition on why it was truncated. State this when describing the repair layer.

## 2026-11-15 — The matrix has two distinct models, not three
**Impact:** The plan asks for "a two-question slice across three models". Only two distinct LLM weights are reachable locally (Gemma 4 31B and Qwen 3.8 27B). The third registry entry, `gemma4-31b-remote` (:4000 `skynet`), serves the same Gemma weights (token 106). So the matrix shows the mechanics across three endpoints, but only two models.
**Cause:** What the relays currently serve.
**Resolution:** Recorded. A third model (a frontier API model, or another local one) is an operator decision; the v2 plan already lists it as open.
**Paper implication:** None yet.

## 2026-11-15 — The tree was dirty during development runs
**Impact:** None on the reported data. The first replay and the first matrix ran on an uncommitted tree while the code was written.
**Resolution:** Every number in RESULTS.md comes from a rerun at the commit recorded in `code.commit`, on a clean tree.
