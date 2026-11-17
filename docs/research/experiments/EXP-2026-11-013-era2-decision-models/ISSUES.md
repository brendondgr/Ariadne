# ISSUES — EXP-2026-11-013

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

## 2026-11-17 — Qwen latency is dominated by a ~30 s server-side wait, not by generation
**Impact:** the Qwen rows of the latency table (RESULTS §2.6) measure the shared server, not the model.
- **The probe.** The reasoning arm's sequential median is 30.7 s, with p90 30.9 s. In the full run, 1,504 of 1,883 reasoning calls took 25–35 s.
- **The check.** Two identical reasoning calls made right after the probe each generated about 350 tokens. One took 32.0 s and the other 1.4 s.
- **`qwen_prob`.** Its median is 0.33 s, but its p90 is the same 30.7 s.

**Cause:** not the client. `utils/decision/clients.py` has no fixed 30 s wait; it retries only after a server error or a dropped connection, waiting 1, 2, 4 and then 8 s. Those waits add up to 15 s at most, so they cannot make a 30 s floor. Transport retries are not logged. The wait comes from the relay or server under the operator's concurrent load. It was not investigated further.

**Resolution:** RESULTS reports the probe as measured, together with the paired-call check and the idle token cost (about 350 tokens against 1). The decision-server figures are unaffected.

**Paper implication:** quote the token counts, or re-measure on an idle server, before stating any Qwen latency.

## 2026-11-17 — The tree was dirty during the runs, in the scoring code only
**Impact:** none on any model call.
- **Commits behind the runs.** Phase A ran from 9884d451 and Phases B and C from f68d934c, which has the same run code. The manifest records f68d934c.
- **What was uncommitted.** While the runs went on, `scripts/era2_decisions.py` had edits to `cmd_score` (two of them: dropping single-option items, and skipping arms with no records), a new `cmd_latency`, and the per-stratum anchor split.
- **What was not touched.** `cmd_run`, the clients and the item builders stayed as committed. Every recorded call came from committed code.

**Resolution:** the edits are committed with the results. `dirty: true` is recorded in the manifest.
**Paper implication:** none.

## 2026-11-17 — Per-stratum transfer was split by item, not by anchor; fixed before the first full score
**Impact:** none on any reported number.
- **The defect.** In the pre-registration commit (f68d934c), `score` computed `transfer_by_stratum` with every item as its own group. The protocol says every split is by anchor.
- **When it was fixed.** It was found and fixed before the first scoring of the completed runs. Every per-stratum figure in RESULTS is split by anchor. The whole-population transfer was always split by anchor.

**Cause:** a shortcut in the per-stratum call.
**Resolution:** `strat_groups` in `scripts/era2_decisions.py` groups each stratum's rows by anchor.
**Paper implication:** none.

## 2026-11-16 — Ten D4 "none" items had a single option and are not scored
**Impact:** D4 is scored on 478 items, not 488. Ten "none of these" variants came from entity types with exactly one relation (for example ATT&CK DataComponent, CAPEC Example). With the gold relation removed, "none of these" was the only option, so there was nothing to decide.
**Cause:** `relation_items` made a none variant whatever the number of remaining relations. d3-lite refused these items (a choice needs at least 2 options); the other arms answered them trivially.
**Resolution:** `score` drops every item with fewer than 2 options, for all arms alike. The builder is unchanged, so the pre-registered item file stays as it was.
**Paper implication:** none.

## 2026-11-16 — The Qwen server was shared during the runs; per-call times in the run logs include queueing
**Impact:**
- **Run-log times are not per-call latency.** The runs used 8 concurrent calls per arm, and the relay was serving other work at the same time. Qwen calls took a median 1.3 s with option probabilities, and up to 30 s and more with reasoning, against 0.3 s and 3 s when idle (the smoke test). The `latency` columns of the run records therefore mix model time with queueing.
- **The protocol's latency measure** (single, sequential calls) is taken separately, by `scripts/era2_decisions.py latency`, on 40 seeded items per arm (20 for the reasoning arm). It is reported from `data/latency.json`.

**Cause:** a shared server. The first Phase A process also hit its 50-minute `timeout`. It was resumed: completed calls were kept and nothing was re-asked.

**Resolution:** latency is reported from the sequential probe, with the server load noted. Accuracy and calibration figures are unaffected.

**Paper implication:** quote latency from the sequential probe only.
