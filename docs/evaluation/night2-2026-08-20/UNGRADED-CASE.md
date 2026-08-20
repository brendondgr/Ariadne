# One case in bank 2 has no grade, and the reason is not what I first said

`bank20260820 / gold_loop_llm / H-CTM-01` is ungraded. That arm reads **n=29**,
not 30, and its 0.9645 is a mean over 29 questions.

## What was tried

| grader budget | outcome | wall |
|---|---|---:|
| 8192 | empty reply | — |
| 16384 (the automatic retry) | empty reply | — |
| 32768 (by hand, afterwards) | HTTP 502 from the relay | 2231s |

## What it is not

**Not an oversized answer.** That was the first diagnosis and it is wrong. The
judge prompt for this case is 26,248 characters — *identical in length* to a
case that graded without incident, because the prompt is assembled to a fixed
budget. The answer itself is 3,868 characters, well inside the ordinary range.
Nothing about this input is large.

**Not the same question as bank 1's `H-CTM-01`.** Also wrong when first stated.
The two banks reuse the same case-id scheme over different anchors:

| bank | id | anchor |
|---|---|---|
| bank-2026-08-19 | H-CTM-01 | CAPEC-572 |
| bank-2026-08-20 | H-CTM-01 | CAPEC-442 |

So the cross-grader disagreement on bank 1's `H-CTM-01` (ours 0.95, independent
0.50) and this ungraded case are two unrelated questions that happen to share a
label. They are not two signals pointing at one bad question.

## What that id collision costs

Case ids are not unique across banks. Every roll-up so far scopes by directory
so nothing is currently wrong, but this is one careless join away from the
judgment-contamination class of bug already fixed once this month — and it just
produced a false diagnosis in a report, which is the cheap version of the same
failure. Worth making bank ids carry their bank.

## Standing

Cause unknown. One case in thirty, on one arm, and the arm it affects is one of
the three the repeat runs showed are not separable anyway — so it changes no
conclusion. Recorded rather than retried: three attempts have already cost 40
minutes of relay time.
