# ISSUES — EXP-2026-08-007

Everything that would make a reader trust these numbers less, recorded so they
do not have to find it themselves.

---

## 1. The grader is a reconstruction, and it is not independent

**Date:** 2026-08-19

The holdout's original rubric lived in subagent instructions, not in a file.
`utils/evaluation/judge_answers.py` is a *reconstruction* of it, and it runs on
a local model served from the same relay that the pipeline's own LLM seams use.
Two distinct problems: the prompt may not be the prompt, and the grader may
share failure modes with the thing it grades.

**Impact:** every absolute level here carries an unknown offset from the
instrument used in EXP-2026-08-002.

**Resolution:** calibration was made phase one of the run rather than optional.
Rank agreement with the committed Sonnet judgments is r = 0.9275 over 30
answers, mean delta +0.031, verdict agreement 0.70. That justifies the grader
for *differences* and for development work. It does not justify it for a
published absolute figure, and the cross-model panel remains the instrument for
anything quoted outside this repository.

---

## 2. The blind bank is burned, and the headline delta inherits that

**Date:** 2026-08-19

Holdout v1 diagnosed the direction defect and the join defect. Both were then
fixed. `docs/plans/robustness/02-holdout-question-generation.md` predicted this
exact failure mode before it happened: *"a template tweaked because a holdout
question failed converts the experiment into a second development set."*

**Impact:** the +0.1167 paired delta measures a repair against the test that
found what was repaired. It is strong evidence the fix worked and weak evidence
about unseen questions.

**Resolution:** not resolvable within this experiment. Stated in RESULTS §5 as
the largest threat, and the follow-up (a cheaply re-drawable bank) is `Q16`.

---

## 3. Four answers were too large for the grader's default budget

**Date:** 2026-08-19

`H-SW-02`, `A-SW-02`, `A-MC-02` and `F-CTM-05` are enumeration answers with 70
to 170 expected identifiers. The grader's reasoning plus output overran both the
8192-token default and the 16384-token escalation retry, returning a truncated
or empty reply.

**Impact:** the affected phases initially rolled at n = 29, 119 and 118 rather
than 30, 120 and 120.

**Resolution:** all four were re-graded at `--max-tokens 32768` and succeeded.
Neither recovery changed a conclusion — `H-SW-02` came back PARTIAL 0.80 and
`A-SW-02` CORRECT 1.00 — which also confirms the failures were a function of
answer *length*, not answer *quality*, so nothing was biased by dropping them.
The corrected rolls are recomputed from the judgment files and printed in the
run report's §7b with both readings shown.

**Note:** the escalation ladder should start higher for enumeration-heavy cases.
Left as a deliberate change rather than a mid-run patch.

---

## 4. One grading pass was contaminated and had to be recomputed

**Date:** 2026-08-19

`answer_files()` excluded names ending `.judgment.json` but not
`.judgment.run2.json`. The third repeat pass therefore picked up the second
pass's 30 judgment files, graded them as if they were answers, and reported
n = 60 on a bank of 30.

**Impact:** the contaminated mean was 0.7583. Had it stood, it would have
entered this experiment as the grader's run-to-run spread — the exact figure
the repeat passes exist to establish — inflating apparent grader noise from
0.0050 to 0.083 and making the arm comparisons look far shakier than they are.
Nothing raised; the phase looked complete.

**Resolution:** fixed at commit `9f1ff94` with a regression test that walks
three passes over one answer set and asserts the input count never grows. The
30 junk files are quarantined under `_contaminated_run3` rather than deleted.
The pass rolls cleanly at 0.8400 over the 30 real cases.

---

## 5. Seeds unrecorded for the pipeline runs

**Date:** 2026-08-19

`seeds: []` in the manifest. The pipeline arms were run once each with no
recorded seed, consistent with D-010 (every arm is `n_runs: 1`, no statistical
test). The one seed that *is* pinned is the bootstrap's (1729, in
`utils/evaluation/stats.py`), so the reported intervals are reproducible even
though the runs are not.

**Impact:** no pipeline-level variance estimate exists. The grader-level
variance measured here (0.0050) is not a substitute for it and is not presented
as one.

---

## 6. The CAPEC graph was empty at preflight

**Date:** 2026-08-19

Preflight failed: the Gremlin store held 0 nodes against an expected 4769. This
is the second occurrence — the store does not survive a restart.

**Impact:** none on the results. The failure was recorded and the run continued
by design, because every grading phase reads answers from disk and needs no
graph. Only Arm F touches the live graph, and it runs last; CAPEC was reloaded
and verified during the run, well before those phases.

**Note:** the run is therefore recorded as 14 phases with 1 failed. The failed
phase is preflight, not a measurement.

---

## 7. Arm F's catalogue lead is not a lead

**Date:** 2026-08-19

0.9852 against the cascade's 0.9839 is inside the interval and inside anything
the grader can resolve. It is reported in the table because omitting it would
be selective, but it must not be read as Arm F winning on the catalogue.

---

## 8. The relay's upstream model is not pinned

**Date:** 2026-08-19

`skynet` is a routing alias. On the night of the run it resolved to
`qwen38-27B-awq`; it had resolved to something else when the grader was first
smoke-tested, and the relay hot-swaps. The manifest records the observed
upstream, but a future run of the same command may not get the same model.

**Impact:** exact reproduction of these grades is not guaranteed. Calibration
would have to be re-run to establish comparability.
