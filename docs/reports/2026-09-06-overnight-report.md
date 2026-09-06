# Overnight run — 6 September 2026

*Generated Saturday 05 September, 23:52. Every number below is read from the files on disk at render time, so a phase that did not run cannot appear here as though it did.*

## What ran

| track | phase | outcome | time |
|---|---|---|---:|
| gemma31 | A-calibration | **running** | — |
| qwen | A-calibration | **running** | — |
| gemma26 | A-calibration | **running** | — |

## The main question: which graders can see near the ceiling?

A grader with no spread reports a difference of zero whatever is true. Yesterday that nearly published four arm-order reversals that did not exist. This measures it directly: the same 60 answers, spanning the score range, graded by every model.

| model | ceiling band | mid band | low band | usable near ceiling? |
|---|---|---|---|---|
| gemma31 | — | — | — | *did not run* |
| qwen | — | — | — | *did not run* |
| gemma26 | — | — | — | *did not run* |

*"distinct" is how many different scores the model gave across 20 answers. A model that gave the same score to all 20 cannot tell them apart, and any comparison built on it is empty.*

## Does a third grader agree that writing your own exam flatters you?

**Not measured.** did not run

That is a result rather than a gap: if no available model can tell these answers apart, the claim rests on one grader for a reason we can state, and it belongs in the paper's limitations.

## What this night does not settle

- Nothing here re-measures the system. No questions were re-answered except the 30-question probe; every other number is a re-grading of answers that already existed.
- A grader that agrees is not proof of correctness. All of this tests whether conclusions survive a change of judge, not whether the judge is right.
- Two known scoring faults remain deliberately unfixed, because fixing them mid-comparison would break the comparison. Both would raise scores.
