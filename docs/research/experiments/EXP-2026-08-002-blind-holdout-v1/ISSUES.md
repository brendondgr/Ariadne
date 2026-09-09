# ISSUES — EXP-2026-08-002 Blind holdout v1

Everything that went wrong, was left open, or would need doing differently.

## 1. `H-SW-01` is malformed and was kept

The §5 `software` category reads "The techniques a piece of software
implements", which presupposes a **Software** anchor. The ATT&CK stratum's
population is techniques and sub-techniques, so the Author was handed
`T1555.005 (Password Managers)` with that description and wrote *"What
techniques does T1555.005 (Password Managers) implement?"* — a question with no
coherent answer.

It was **not repaired.** Editing an authored question after seeing the anchor
would convert a blind question into a co-authored one, which is the exact failure
mode the experiment exists to avoid. Every figure is reported twice, with and
without it (0.689 / 0.709 for Arm A).

The protocol defect is in the category scheme, not in the sampler: `groups`
offers both directions ("the techniques a named group uses, **or the groups
using a technique**") and produced two well-formed questions; `software` offers
only one. A future draw should either phrase every category
direction-agnostically or draw the anchor from the population the description
presupposes.

## 2. The Compiler omitted `join_key` on the CAPEC `mapping` category

Fixed mid-run and logged as a deviation; see RESULTS.md. Worth recording *why*
it was not caught earlier: `test_holdout_bank.py` deliberately does **not**
assert that entries route to their `expected_template`, because that field is
derived and asserting on it would turn a derived value into ground truth. That
was the right call for the reason given, and it is also why a routing regression
had no test to trip. A test that asserts the holdout's *task shape* matches the
committed bank's task shape for the same category — entities, join_key, limits,
but not the resulting template — would have caught it without smuggling in a
scoring signal.

## 3. Three judgment files were never written

Three grading agents returned a well-formed verdict as structured output but did
not write the `.judgment.json` file the prompt asked for. The verdicts were
recovered verbatim from the workflow journal rather than re-graded — re-grading
would have introduced a second, differently-sampled judgment for those cases
only. If the judge harness is reused, it should verify the file exists rather
than trusting the instruction.

## 4. The manifests reflect the deviation re-run, not the full run

`docs/evaluation/experiments/holdout-v1/*/manifest.json` were overwritten by the
two-case re-run, so their `wall_s` and case list cover 2 questions, not 30. The
full-run figures (Arm A 1.0 s, Arm F 554.0 s, 30/30 each, 0 errors) come from the
run logs and are recorded in RESULTS.md. A `--only` re-run should write a
separate manifest rather than clobbering.

## 5. Contention during the Arm F run

A concurrent session was running Arm G against the same LLM relay and the same
graphs for part of Arm F's 554 s. Queries are read-only so correctness is
unaffected, but **the wall-clock figure for Arm F is an upper bound, not a clean
measurement**, and should not be compared with the 533.4 s recorded for Arm F on
the development set as though both were measured under the same load. One Arm F
case (`H-LKP-01`) records a 120 s LLM read timeout and fell back to the
deterministic composer.

## 6. Unresolved: the gate cannot be decided sharply at n=30

Arm A lands at 0.689 against a 0.70 threshold, with a 95% CI of 0.550 – 0.817
that spans three of the gate's four bands. The rule was applied as written and
not renegotiated, but the thresholds were evidently set without n=30's interval
width in view. Any future gate on a set this size should be stated as a decision
on the interval, not on the point.

## 7. Not measured

- Non-anchored questions. Every holdout question names an entity, as every
  catalogue question does. C-014's other half — the open-ended regime — remains
  unmeasured.
- Human-authored questions. See the standing limitation.
- Run-to-run variance. n_runs = 1.

## 8. (2026-09-09) The judge harness script is not in the repository, and the Arm A output directory has grown

`llm.prompt_files` lists `scratchpad/judge_holdout.mjs`; no such path exists in
the repository, so the judging harness that drove the 60 Sonnet 5 agents is
not recoverable from git. The verdicts it produced are (the `*.judgment.json`
files and `results.json`, now hashed in `data/POINTERS.md`).

Separately, `docs/evaluation/experiments/holdout-v1/deterministic/answers/`
has held 60 additional grader sidecars (`*.judgment.local.json`,
`*.judgment.local.pre-qwen38.json`) since 2026-08-31, written by
`EXP-2026-08-021`. They are not this experiment's and must be excluded from any
recomputation of its numbers; `utils.evaluation.retrieval_coverage` currently
counts them as answer artifacts and reports n = 90 for that arm, which is a
scorer hygiene defect rather than a record error. See RESULTS A-2.
