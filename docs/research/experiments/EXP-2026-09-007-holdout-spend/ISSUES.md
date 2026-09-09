# ISSUES — EXP-2026-09-007

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

## 2026-09-09 — I-8: the dev `llm_query` baseline (0.3781) was measured outside any experiment
**Impact:** `dev_qwen_llm_query`, `dev_gemma_llm_query`, and the two dev C-012 contrasts (0.1147 / 0.0696) rest on a re-run EXP-2026-09-005 never made (its I-5: "`llm_query` … not re-run").
**Cause:** the dev arm was re-answered at the settled 32,768 budget on 2026-09-05 into `docs/evaluation/experiments/llm-query-split-2026-09-05/llm_query/answers` and rolled up in `docs/evaluation/composition/bank/two-grader-judged.json` (`e83ed62`), a file no experiment folder pointed at until A-2 moved its numbers here.
**Resolution:** both are now pointed from `data/POINTERS.md` (A-5 §4). The qwen pass there covers 281 + 281 judgments over 283 cases (3 + 3 `.error.txt`), which is why `dev_qwen_llm_query` has n = 283.
**Paper implication:** the dev row of the templates-versus-generation table cites this experiment, not EXP-2026-09-005, for `llm_query`.

## 2026-09-09 — I-7: the `llm_query` arm's builder model was not probed
**Impact:** the arm's answer artifacts record `run_meta.planner`/`synthesis` and no served model; only the graders are named from a response envelope.
**Cause:** `experiment_untruncated` does not write the builder's `response.model`; the grader path does.
**Resolution:** `llm.model` records the builder as `relay/qwen38-27B-v2@2026-09-05` on the strength of `docs/evaluation/README.md` ("2026-08-31 — current: qwen38-27B-v2") and the manifest's own `compute.hardware` line, not a probe. Not resolved beyond that.
**Paper implication:** say "the relay's model on 2026-09-05" for the arm; say `qwen38-27B-v2` by name only for the graders.

## 2026-09-09 — I-6: seeds and lockfile
**Impact:** none on the figures. `seeds: []` is accurate: the split is `sha256(spec_id)` parity, the two model-free arms take no random draw, and the graders and `llm_query` ran at temperature 0 with no seed parameter exposed by the relay; the bootstrap seed (1729) is in `statistical_test`.
**Resolution:** `environment.lockfile` pointed at `env/requirements.lock`, never written; set to `null` (A-5). Dependencies are `uv.lock` at `2ed6de9`.

## 2026-09-09 — I-5: `date_completed` preceded half the judgments
**Impact:** the manifest said 2026-09-05; gemma position-2 sidecars are dated 2026-09-06 00:30–01:30 and the final roll-up was committed 2026-09-06 03:28 (`81f12cb`).
**Resolution:** `date_completed` → 2026-09-06 (A-5 §4).

## 2026-09-09 — I-4: four manifest values were wrong for two days, and the body stayed stale through two corrections
**Impact:** A-1 (2026-09-07) corrected `llm_query_holdout` 0.4031 → 0.4039, `deterministic_minus_llm_query_holdout` 0.0831 → 0.0822, `generic_minus_llm_query_holdout` 0.2515 → 0.2507, `second_family_generic_minus_deterministic` 0.2053 → 0.2143. A-4 corrected two cells of RESULTS §1 and left lines 5–6, 13, 18–19, 30, 64–74 and 82–85 stale; `max_arm_deviation_from_dev` stayed 0.0250 in the manifest until 2026-09-09. H5 was declared held ("Five for five") with no recorded measurement, and the judge flag, once read, is not zero on `generic` (A-5 §3).
**Cause:** values copied from `data/judged-final.json`, an intermediate roll-up that declared its own `not_measured`; corrections applied to one file at a time.
**Resolution:** withdrawn values recorded in `metrics.withdrawn`; A-5 tabulates every stale line; H5 figures recorded as metrics.
**Paper implication:** quote only manifest values; the paper's "fourth decimal" characterisation of the disagreement was already corrected by A-1.

## 2026-09-09 — I-3: gemma position 2 was first recorded `not_run`
**Impact:** `data/judge-state-gemma.json` (15:03) records `deterministic.gemp2` and `generic.gemp2` as `not_run` ("27 min left before 15:30; skipped for ALL arms so the comparison stays symmetric"), and `judged-final.json` / `judged-gemma-p1.json` were rolled up on that basis. The gemma endpoint came back that night and position 2 was graded for all three arms (`deterministic` 00:30–00:49, `generic` 00:50–01:12, `llm_query` 01:12–01:30 on 2026-09-06), along with gemma position 1 for `llm_query` (00:03–00:30).
**Cause:** the shared gemma window closed at 16:00 on 2026-09-05 and reopened later.
**Resolution:** the state file was not updated; the sidecars are authoritative and `judged-two-family-final.json` (committed `81f12cb`) is the complete instrument. The position-1-only figures are withdrawn (A-1, A-5 §2).
**Paper implication:** the gemma half is two-position, like the qwen half.

## 2026-09-09 — I-2: two qwen position-2 judge failures and five retried calls, all cleared
**Impact:** none on the figures; every cell has 288 cases × 2 positions.
**Cause:** `judge-state-qwen2.json` records `llm_query.qwp2` as `partial` (286 written) with `D2-PeerOf-CAPEC-80-1a5732::formal` failing on missing judgment fields (`ValueError`) and `D3-log_source-DC0032-735d0c::formal` on `HTTP Error 502` after three attempts. The `llm_query` directory holds 3 `.judgment.qw.error.txt` (18:30–18:59) and 2 `.judgment.qwp2.error.txt` (19:15–19:54) from those and earlier transient failures.
**Resolution:** all were retried and every case carries a `.qw` and `.qwp2` judgment (288 each, verified 2026-09-09); the `.error.txt` files are left in place as the trace and are counted in the pointer row.

## 2026-09-09 — I-1: `dirty: true` — the tree moved throughout the run
**Impact:** no single commit reproduces the folder. `code.commit` is `2ed6de9` (10:56:07, this folder's pre-registration; A-5 corrected it from `514ddda`, which is EXP-2026-09-006's). The arms ran 11:27–16:27 and judging ran to 2026-09-06 01:30; during that window `8bab0d8` (15:03, the qwen roll-up), `2bddfd9` (21:41) and `bba225c` (22:02) landed, and the two-family roll-up was committed at `81f12cb` (2026-09-06 03:28).
**Cause:** the results were written up in stages while later passes were still grading.
**Resolution:** not resolved; recorded. The model-free arms are byte-reproducible from any of these trees; the judged figures depend on the sidecars, which are pinned by tree hash in `data/POINTERS.md`.
**Paper implication:** none.
