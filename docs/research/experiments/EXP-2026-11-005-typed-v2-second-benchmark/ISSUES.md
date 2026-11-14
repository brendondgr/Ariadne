# ISSUES — EXP-2026-11-005

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

## 2026-11-14 — Protocol deviation: Qwen's part B runs at `reasoning_effort=medium`
**Impact:**
- Qwen's part-B figures come from `reasoning_effort=medium`. Every other Qwen figure in this experiment, in EXP-2026-11-003 and in EXP-2026-11-004 used the server default, `xhigh`. So Qwen's part A and part B are not comparable in absolute terms.
- Within part B, every Qwen arm (free and typed, every shot count, repair) uses `medium`, so the pre-registered comparisons stay paired.
- Gemma is unchanged: no setting is sent for it.
**Cause:**
- At `xhigh`, many Qwen part-B calls thought until they hit the 8,192-token cap. These reached about 300 s each, and many timed out during the outage.
- The server lists its supported levels as "xhigh (default), medium, and low"; `none` disables thinking.
- On 8 prompts that overflowed at `xhigh`, `medium` finished all 8 (median about 1,100 tokens). `low` overflowed on one and was not shorter. Probe scripts: `probe_think.py` and `probe_levels.py`, session scratchpad (not kept).
- Turning thinking off answered a trivial arithmetic check wrongly, so `none` was not used.
**Resolution:**
- The user chose to lower Qwen's thinking level. `medium` was chosen by the probe above.
- The 493 Qwen part-B generations already made at `xhigh` were moved to `cache/B-generate.qwen-xhigh-archive.jsonl`, and all 2,340 Qwen part-B calls were regenerated at `medium`.
- The runner sends per-model extras from `KILLTESTS_REASONING_EFFORT`, and each generation records the level it used. The run header records it per resume.
- From this resume on, concurrency is 16 per model, not 64, because 64 drew HTTP 429s. Requests are at temperature 0; concurrency does not change outputs.
**Paper implication:** report Qwen's part B with its reasoning level, and do not set it beside Qwen's part A or T1 figures as like for like. The finding that a reasoning model's default thinking level exhausts a fixed budget on unfamiliar schemas, in every arm, is itself worth a sentence.

## 2026-11-14 — Format v2 accepts edge references in `any_of` but not in `optional`; both models generalised them
**Impact:** every invalid 3-shot request in part A comes from this: 6 of 6 for Gemma and 5 of 6 for Qwen. Qwen's sixth is unparseable. Accuracy on the optional-relationship category (n = 15) fell from 0.667 to 0.333 (Gemma) and 0.800 to 0.333 (Qwen). With some name noise, this is why Qwen's part A fell from 0.955 to 0.905 and missed expectation A1.
**Cause:** v2 added a second way to write an edge, a reference by `var`, in one place only. The models wrote the edge in `edges` and referred to it from `optional`, or wrote `optional: ["r1"]`. The validator rejects both, as specified.
**Resolution:** not changed; the format is frozen for this experiment. Candidate v3: accept edge references in `optional` too, with the same semantics as `any_of`, i.e. one way to refer to an edge everywhere. Untested.
**Paper implication:** a design rule worth stating. A form grammar that accepts a construct in one place and rejects it in another gets generalised by the model. The repair arm (one turn showing the validator's message) recovers most of this: 0.945 and 0.930.

## 2026-11-14 — Relay outage during part B; failed calls retried
**Impact:** the first part-B pass (2026-11-14 01:19–08:14) lost generations to relay errors. About 100 of 390 per arm failed for Gemma and about 320 of 390 for Qwen: timeouts, HTTP 502 and 429, refused and reset connections. Every repair call failed as well. Part B's first scores (e.g. free Cypher 0.256 and 0.077) are therefore invalid and are not reported. Part A (01:09–01:19) had no errors.
**Cause:** upstream model endpoints failed. The relay itself restarted at about 08:10, and both endpoints reported `health: failed` afterwards.
**Resolution:**
- `scripts/killtests_exp005_resume.sh` waits until both aliases answer, then re-identifies each model by tokenizer token id and records the mapping in `run_header.json` (`identities_initial`, `resumes`).
- It then deletes part B's derived stage files. The execute cache is deleted too, because it records generation errors as rows.
- It reruns part B. Only successful generations are cached, so only the failed calls are retried, from the same frozen code, prompts and settings.
- Passes repeat until no generation error remains.
**Paper implication:** none if the final pass has zero generation errors; the count is recorded in RESULTS.md. Generations from before and after the outage come from the same weights, identified by token id each time.

## 2026-11-14 — `analysis.py` and the resume script were written after the tag
**Impact:** none on the measurement. `analysis.py` reads the stage outputs and computes the pre-registered rule and the exploratory taxonomy. The resume script only re-invokes the frozen runner. Both are committed (f276e998).
**Resolution:** recorded here.
**Paper implication:** none.
