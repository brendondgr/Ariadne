# ISSUES — EXP-2026-09-010

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

## 2026-09-09 — `code.dirty: true`: the guarded re-run script changed while its attempts were in flight
**Impact:** provenance only.
**Cause:** `code.commit` is `c8ad1a7` (2026-09-06 17:57, EXP-2026-09-009's
pre-registration). `scripts/arm_identity_check.py` landed at `9e79114` (18:03)
before the first pair ran (19:08–19:34). `scripts/generic_identity_rerun.py`
landed at `29341e9` (20:06) and was changed at `8eae915` (22:47, "tell
transient failures from deterministic ones") and `0af888c` (23:21, "exclude
failed answers, don't discard whole captures") — the second guarded capture
`a-try1` started at about 23:21:31 and `b-try1` at 23:41, so the final
captures ran at `0af888c` or with those changes uncommitted.
**Resolution:** `dirty: true` kept; the code that produced the reported generic
figures is `0af888c` ± uncommitted edits, not `c8ad1a7`.
**Paper implication:** none.

## 2026-09-09 — seeds recorded as `[]`
**Impact:** the generic captures cannot be claimed to have used a specific seed
from this record alone.
**Cause:** neither driver records `LLM_SEED`, and the capture manifests record
only the alias (`skynet` for the first pair, `default-model` for the re-run).
EXP-2026-09-011's PROTOCOL states that 1729 is "the configuration every
recorded run used", and RESULTS above says "rerun at the same seed", so the
pipeline default was presumably in effect; it is not verifiable from the
artifacts.
**Resolution:** `seeds: []` kept. The finding (same-seed re-wording of 143/276
answers) does not depend on which seed it was, only on it being the same in
both captures, which the same environment guarantees.
**Paper implication:** none.

## 2026-09-09 — three guard defects, found by the run (PROTOCOL A-1, A-2, A-3)
**Impact:** A-1: `deterministic` reads 2/284 under the pre-registered exclusion
list and 284/284 once `run_meta.wall_s` is also excluded. A-2: the first
`generic` pair is `not_run` (narrator at `:4000` timed out on 60/284 answers of
run B; the harness returned rc 0). A-3: one dev-bank question
(`D4-mitigates-uses-M1047-b63672::indirect`) overflows the narrator's context
by one token in every run and is scored on fallback text in every recorded
`generic` run on this bank.
**Cause:** the volatile-key list was built by name-matching one artifact of a
different arm; pre-flight probed `:9090` and never `:4000`; nothing read
`fallback_reason`.
**Resolution:** all three recorded as amendments in PROTOCOL.md and carried
into the guarded re-run's guards. `wall_s` was deliberately not added to
`VOLATILE`. A-3 is not fixed (raising the limit would change what the arm
computes).
**Paper implication:** limitation 5 must name `generic` as the arm carrying
the primary result; `fallback_reason` deserves to be a reported metric.

## 2026-09-09 — the re-run narrated through `:9090/default-model`, not `.env`'s `:4000/skynet`
**Impact:** a deliberate deviation from the recorded configuration.
**Cause:** the `:4000` route was timing out on 2026-09-06 (it is what
invalidated the first pair). The operator confirmed both routes reach the same
backend; the served model was probed as `qwen38-27B-v2` in pre-flight.
**Resolution:** recorded in RESULTS Limits and here.
**Paper implication:** none, provided the served model is named rather than
the alias.

## 2026-09-09 — `data/identity-analysis.json` is the invalidated first pair, now labelled
See RESULTS A-2. The file gains a `status_2026-09-09` field; the reported
generic figures live in `data/generic-rerun-state.json`.

## 2026-09-09 — `arm-identity-rerun-2026-09-06/a-try2` is an aborted retry
84 answers, no run manifest, not recorded in `generic-rerun-state.json`
(whose two attempts are `a-try1` and `b-try1`). No reported number reads it.
Left on disk and noted in `data/POINTERS.md`.

## 2026-09-09 — the manifest was a scaffold until the record repair
See RESULTS.md A-1 for every field filled on 2026-09-09 (old → new). One
manifest field outside `values` changed: `metrics.primary`
`identity_rate_content` → `identity_rate_deterministic`.
