# ISSUES — EXP-2026-11-004

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

## 2026-11-14 — The primary metric is the smaller of the two models' gains
**Impact:** `typed_3shot_gremlin_minus_free_gremlin_3shot_min` is 0.15 (Gemma); Qwen's is 0.30. The PROTOCOL states the primary per model; the manifest needs one value, so it carries the minimum.
**Cause:** the manifest schema holds one primary value.
**Resolution:** both per-model values are in `metrics.values`.
**Paper implication:** quote per model.

## 2026-11-14 — Relay aliases serve the reverse of the stated assignment
**Impact:** none on the figures; identities are recorded by tokenizer in `run_header.json`.
**Cause:** `default-model` serves Gemma (last token 106) and `default-model-2` serves Qwen (248046); each backend's envelope reports the other alias's name.
**Resolution:** models are named by tokenizer family, never by alias or envelope.
**Paper implication:** name models by weights; sizes are as stated by the operator, not verified.

## 2026-11-14 — Compiler defects found and fixed before the run
**Impact:** none on the run (all fixes precede tag `killtests-typed-run`).
**Cause:** in pre-run verification, Gremlin `match()` in TinkerPop 3.8.0 (a) could not solve patterns with two start points, (b) dropped labels internal to a pattern traversal, and (c) returned nothing or raised `ClassCastException` on cyclic patterns with edge labels. Cypher relationship uniqueness and Neo4j's null ordering also had to be reproduced.
**Resolution:** the Gremlin compiler walks the pattern from one node instead of using `match()`; uniqueness and Cypher's null ordering are compiled explicitly. Verified: gold 1.000 / 0.9986, differential 0.9997.
**Paper implication:** the verification table in PROTOCOL.md is the compiler's correctness evidence; the `match()` failure is worth a footnote, since free-written Gremlin can hit it too.

## 2026-11-14 — `analysis.py` was written during the run
**Impact:** none; it only reads the run's outputs and computes the pre-registered rule and the ceiling. It is committed after the tag.
**Resolution:** recorded here.
**Paper implication:** none.
