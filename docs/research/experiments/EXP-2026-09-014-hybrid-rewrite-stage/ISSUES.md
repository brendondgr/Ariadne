# ISSUES — EXP-2026-09-014

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

## 2026-09-08 — `default-model-2` is the same weights as `default-model`, and flaps
**Impact:** Step 7's arm **R3** cannot be a model comparison. Run as written it is
a *second three-run repeatability block on the same weights*, which is worth
having but is not what the operator asked for. Awaiting the operator's call
(§2 of the plan anticipated exactly this).
**Cause:** two probes 90 seconds apart, both recorded in
`data/model_identity_2026-09-08.json` (the file holds the second):

| alias | probe 1 (16:06) | probe 2 (16:12) | advertised upstream |
|---|---|---|---|
| `default-model` | qwen38-27B-v2 | qwen38-27B-v2 | qwen38-27B-v2 |
| `default-model-2` | HTTP 502 | qwen38-27B-v2 | qwen38-27B-v2 |
| `default-model-3` | HTTP 502 | HTTP 502 | qwen38-27B-v2 |
| `default-model-4` | HTTP 502 | HTTP 502 | qwen38-27B-v2 |

`default-model-2` came up between the two probes and, when it answered, returned
the same `served_model` **and the same `system_fingerprint`**
(`vllm-0.21.0-bf3a75db`) as `default-model`. All four aliases advertise the same
upstream. So the relay's four `default-model-*` endpoints are replicas of one
deployment, not four models.
**Resolution:** Not resolved — the operator decides whether R3 runs as a
repeatability block, is substituted with a genuinely different endpoint, or is
dropped. Steps 1–6 do not depend on it; R0/R1 need no model and R2 needs only
`default-model`, which was healthy in both probes.
**Paper implication:** Any variance figure from this experiment is
**within-model** variance for one set of weights on one server build. No
cross-model claim may be made from it. The flap also means every arm must
re-probe identity at run time rather than trusting Step 0's record.

## 2026-09-08 — the shipped `reference_arm6.json` no longer reproduces on current `main` (records do; queries and claims do not)
**Impact:** R0 is scored against a **fresh** capture,
`docs/evaluation/variants-2026-08-29/reference_2026-09-08.json`, not against the
2026-08-29 file. `records_exact` comparisons against the published Arm 0–6
figures remain valid; `queries_exact` comparisons against them do not and are
not made.
**Cause:** three shipped changes and one data refresh land between the Arm 6
capture and today. Of 120 cases: **0 differ on `entity_ids`** (the primary
`records` metric), 60 differ on `queries`, 15 on `claims`, 11 on `abstentions`.
Every query diff is Gremlin-side — the emitted traversal lost its
`hasLabel("AttackPattern")` prefix when universal node extraction replaced the
per-template lookups — and every abstention diff is the sub-question *wording*
inside an abstention statement, never whether the case abstained (all 11 still
abstain). The claim diffs are ATT&CK 19 property drift, e.g. T1047 now carries
`x_mitre_remote_support`.
**Resolution:** Re-captured on 2026-09-08 and committed as the R0 reference; the
2026-08-29 file is left untouched as the dated historical record.
**Paper implication:** the "byte-identical retrieval" claim (EXP-2026-09-010) is
about repeated runs of one build, not across builds. Say so where the reference
is cited.

## 2026-09-08 — `--graph verify --dataset attack` failed on a runtime manifest for a store that no longer holds ATT&CK
**Impact:** None on any number; a precondition check only.
**Cause:** ATT&CK was loaded into Gremlin at 17:45Z for a side experiment, and
the CAPEC load at 18:07Z replaced the Gremlin graph. The ATT&CK Gremlin
`load-manifest.json` survived, so `verify` kept checking a backend whose 6374
nodes / 8582 edges are entirely CAPEC (`AttackPattern`, `Weakness`,
`Prerequisite`, …) against ATT&CK's expectations. Neo4j held ATT&CK exactly:
4369 nodes, 27669 edges, every label at its manifest count.
**Resolution:** the stale manifest was retired (kept out-of-tree; the file is
git-ignored local state). Both datasets then verify clean. Nothing was reloaded
and no graph content changed.
**Paper implication:** none.
