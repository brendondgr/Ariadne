# ISSUES — EXP-2026-08-021

## I-1 — `calibrate()` would have destroyed the artifacts behind the recorded r = 0.9275

**Impact:** none, because it was caught first. Recorded because the next person
to run a calibration will hit it.

**Cause:** `judge_answers.calibrate()` hardcodes `suffix=".local"` **and**
`force=True`, so it overwrites any existing `.judgment.local.json`. Those files
were the Ornith-era calibration behind `EXP-2026-08-007`'s r = 0.9275 — the only
evidence about how far that instrument could be trusted.

**Resolution:** copied to `.judgment.local.pre-qwen38.json` before running. The
backup suffix contains `.judgment`, so `answer_files()` excludes it and it cannot
be re-consumed as an answer — the contamination mode that module's own docstring
warns about.

**Paper implication:** none. **Repo implication:** `calibrate()` should refuse to
overwrite without an explicit flag, or should suffix by date. Not fixed here.

## I-2 — An existing `.cross` pass is not cross-model, and its `llm_query` mean is inflated by dropout

**Impact:** nothing in this experiment uses it. It is recorded because it is
quotable-looking and wrong in two ways at once.

Found while locating the reference pass. On `bank20260819/llm_query` the
`.judgment.cross.json` pass reads **0.7407 (n=27)** against the base pass's
**0.5000 (n=30)**.

1. **It is not cross-model.** Every judgment in it records `"model": "skynet"` —
   the local relay, same as the base pass. The suffix name suggests otherwise.
2. **Its three missing cases are three of the arm's worst answers.** `H-CHN-02`,
   `H-CHN-03` and `H-CTM-04` failed with `ValueError: no JSON object in reply: ''`
   and score **0.30, 0.20, 0.35** in the base pass. Imputing them back gives
   ≈ 0.695, so roughly a fifth of the 0.24 gap is dropout, not disagreement.

**Paper implication:** a grading pass that fails on its hardest cases reports a
flattering mean, and the failure mode is silent. This is the same shape as
`EXP-2026-08-019`'s fallback contamination (r = +0.62 between failure rate and
measured quality) on a different mechanism. **`grader_sensitivity.py` therefore
pairs on case id and reports dropout separately rather than absorbing it.**

## I-3 — My own comparison script reported an ordering flip that was a tie

**Impact:** a wrong intermediate reading, corrected before it reached a
conclusion. Recorded because it is exactly the class of defect this experiment
exists to catch.

On `bank20260820` the reference pass scores `merged` and `generic_composed` at
**exactly 0.9367**. Sorting by mean and comparing the two sorted lists reported
`arm_order_preserved: False` — but there was no ordering to preserve, and the
"flip" was the sort's tie-break.

**Resolution:** the script now detects ties in the reference, excludes tied arms
from the ordering test, and prints the tie explicitly. Both banks pass H1 once
ties are handled.

**Paper implication:** an ordering test is only meaningful over pairs the
reference actually ranked. Stated in the results rather than silently handled.

## I-4 — The reference grader is unidentified, so the offset between passes cannot be attributed

**Impact:** bounds what this experiment can conclude, and it is the reason it
exists.

The candidate grader is `qwen38-27B-v2`, probed and recorded. The reference
passes were run 2026-08-19..21, inside the window where the alias's serving model
is **not determinable** (`Q12`). So the measured offsets are real and their
*cause* is not recoverable.

They also do not run in one direction:

| reference pass | cells | offset (candidate − reference) |
|---|---|---|
| base `.judgment.json` | the four `EXP-2026-08-008` arms | **+0.023 to +0.057** (candidate more generous) |
| `.judgment.c015.json` | the `EXP-2026-08-009` pair | **−0.007 to −0.038** (candidate stricter) |

Both reference passes fall in the same undetermined window but were run in
different sessions, so the disagreement between them cannot be separated from the
disagreement with the candidate.

**Paper implication:** report the offsets as measured and **do not explain them**.
The honest sentence is that a grader offset of ±0.05 exists between passes and
its source is unrecoverable — which is the cost `D-028` was written to stop
accruing, observed rather than argued.

## I-5 — The candidate pass supports a six-arm comparison the reference cannot

Not a defect; a property worth recording before someone builds the wrong table.

All twelve candidate cells were graded in **one session with one instrument**. The
reference figures are split across two sessions — base for four arms, `.c015` for
the merged/federated pair — and `EXP-2026-08-009`'s protocol explicitly graded its
eight cells together *"so the grader cancels out of every comparison"*, warning
against comparing arms graded in different sessions.

**So a six-arm ordering table may be built on the candidate side and must not be
built on the reference side.** Every reference-versus-candidate comparison in
`RESULTS.md` is therefore within-arm and paired, never across arms.

## I-6 — One 178 KB answer drops intermittently, and the dropout guard fired on my own data

**Impact:** `bank20260820/gold_loop_llm/H-CHN-01` is graded in pass 1 and errors
in r2 with `no JSON object in reply` on a *truncated* reply — the JSON begins
correctly and stops mid-object. Both attempts truncate, including the automatic
retry at double `max_tokens`.

**Cause:** answer size, not grader instability. The answer is **178 KB**, and this
is a documented pathology rather than a new one — `EXP-2026-08-009` recorded that
*"three cases needed a third grading attempt at 32768 tokens after two empty
replies. All are 177k–205k-character answers to one question, `H-CHN-01` on set
2, in every arm including the LLM-narrator one — so the size is a property of the
question, not of a composer."*

**Resolution: excluded, deliberately, rather than recovered at a larger budget.**

`EXP-2026-08-009`'s precedent was to re-grade oversized cases at
`--max-tokens 32768` and record the deviation. **That precedent is right for an
experiment that needs the case's score and wrong for this one.** This experiment
measures grader *spread*; a case graded at 8192 in some passes and 32768 in
others would differ partly because the budget differed, inflating exactly the
quantity being measured. Uniform settings matter more here than one case, so the
case leaves the statistic and the settings stay fixed.

`grader_repeats.py` restricts every cell to the cases graded by **all** passes,
so this happens automatically: the cell reports n=29 rather than a 30-case mean
that silently rests on a different case set per pass.

**The symmetry is worth recording.** That guard exists because I-2 caught an
earlier `.cross` pass inflating its `llm_query` mean by dropping its three worst
answers. It has now fired on my own data. A dropout guard that only ever
disciplines someone else's numbers is not a guard.

**Paper implication:** report `n` per cell, not just the mean, and never compare
two passes over different case sets. Also: this bounds the judged evaluation more
generally — **a 178 KB answer cannot be reliably graded by this instrument at
all**, in any pass, and no amount of repetition fixes that.

## I-7 — A greedy regex loses judgments the model actually produced

**Impact:** `bank20260819/merged/H-CHN-03` fails in r3 with
`JSONDecodeError: Extra data: line 255 column 5 (char 7829)`. Passes 1 and r2
graded it fine, so it is intermittent. **This is a distinct failure mode from
I-6 and the distinction matters.**

**Cause:** `_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)` is **greedy**. When a
reply carries more than one JSON object — a reasoning model emitting a draft and
then a final verdict — the match spans from the *first* `{` to the *last* `}`,
producing `{...}<prose>{...}`. `json.loads` parses the first object, finds more
after it, and raises. Char 7829 is where the first, perfectly good object ended.

**Why the distinction from I-6 matters.** I-6 is truncation: a 178 KB answer whose
reply genuinely never finished, so there was no judgment to have. **I-7 is a
judgment the model produced and we threw away.** One is a property of the answer
under test; the other is a bug in the instrument. Reporting both as "dropout"
would conflate a limit of the evidence with a limit of our code.

**Resolution: recorded, not fixed, and deliberately so.** Changing the extractor
between passes would make the passes non-comparable, which is the whole
discipline this experiment runs on. It is excluded by the common-set rule like
any other drop.

**The fix, for after the repeats land:** use `json.JSONDecoder().raw_decode` from
the first `{`, which stops at the end of the first complete object, or make the
match non-greedy with balanced-brace scanning. Either recovers this case. Until
then the retry path cannot help — it re-posts the same prompt at double the
budget and gets the same two-object reply, so both attempts fail for a reason
that has nothing to do with the budget.

**Paper implication:** none for the arms. **Instrument implication:** the judged
figures across this whole record carry an unmeasured, intermittent loss rate from
a parser that is stricter than it needs to be, and it lands preferentially on long
answers — which are not a random sample of answers.

## I-8 — Three symptoms, one population: the grader fails on its largest answers, and the loss is systematic

Consolidates I-6 and I-7 once the third symptom appeared. **They are not three
bugs. They are one population of inputs meeting three separate weaknesses in the
extraction path.**

| pass | cell | case | symptom | mechanism |
|---|---|---|---|---|
| r2 | `bank20260820/gold_loop_llm` | `H-CHN-01` | `no JSON object in reply` | reply truncated mid-object; the data was never produced |
| r3 | `bank20260819/merged` | `H-CHN-03` | `JSONDecodeError: Extra data` | greedy `\{.*\}` spanned two objects; the data was produced and discarded |
| r3 | `bank20260819/generic_composed` | `H-CHN-03` | `judgment missing [correctness, faithfulness, groundedness, completeness, rationale]` | extraction landed on an object carrying only `verdict` |

**The population is the tail of answer size, and the separation is not subtle:**

| | KB |
|---|---|
| median answer, all 360 | **10.3** |
| p90 | 25.3 |
| the three failures | **79, 85, 178** |
| max in the set | 201 |

Every failure is above p90; two are 8–17× the median.

### Why this is the most transferable thing in the experiment

**Judged evaluation across this whole record silently fails on its largest
answers, and answer size is not randomly distributed across questions.** These
are the `H-CHN` CWE-chain cases — a *question type*, one this project already
knows is its longest (`EXP-2026-08-009`: *"all are 177k–205k-character answers to
one question, `H-CHN-01` on set 2, in every arm"*).

So the loss is **systematic, not random**: a judged mean is computed over a case
set that intermittently excludes the hardest, longest questions, and nothing in
the reported figures shows it, because a case that errors is simply not in the
denominator. That is the same shape as I-2's dropout and as
`EXP-2026-08-019`'s fallback contamination — **a failure mode that improves the
number it contaminates** — arrived at for a third time by a third mechanism.

**None of this was visible at n=1.** Pass 1 graded 360 of 360. The loss rate only
appeared because the passes were repeated, which is a return on repetition
independent of the variance estimate they were run for.

### What to do, and what not to do

- **Not fixed mid-experiment.** Changing the extractor between passes makes the
  passes non-comparable, which is the discipline this experiment rests on.
- **Afterwards:** `json.JSONDecoder().raw_decode` from the first `{` fixes
  symptoms 2 and 3. Symptom 1 needs a larger budget for oversized answers, and
  `EXP-2026-08-009`'s 32768 precedent is the right one *there* — it is only wrong
  inside a spread measurement, where a per-case budget change would inflate the
  quantity being measured.
- **Report `n` per cell everywhere, and report the error count beside it.** The
  denominator is not a constant and has never been treated as one.

### I-8 addendum — the at-risk population, sized

"Four failures in a thousand gradings" is the wrong framing and would understate
this. The failures are not spread over the corpus; they are confined to a small,
identifiable tail.

| population | n of 360 | share |
|---|---|---|
| answers ≥ 50 KB | **17** | 4.7% |
| answers ≥ 25 KB | 37 | 10.3% |
| median answer | — | 10.3 KB |

**Every failure so far is inside the ≥ 50 KB group**, and that group is four case
ids — `H-CHN-01`, `H-CHN-02`, `H-CHN-03`, `H-GRP-01` — i.e. **two question
types**, the CWE chains and one group question, repeated across arms.

Across passes 1–r3 those 17 answers have been attempted roughly 50 times for 4
failures — **on the order of 8% per attempt inside the tail, against 0 of ~950
outside it.** Quote it that way. A corpus-wide rate averages a systematic failure
into invisibility, which is the same error as quoting a judged mean without its
`n`.

### I-8 addendum 2 — a trend to check before the spread is believed

Errors per pass so far: **p1 = 0, r2 = 1, r3 = 3** (r3 incomplete at the time of
writing). That may be chance on tiny counts, and it may be the relay degrading
under a sustained multi-hour load.

**It matters for this experiment specifically.** A spread measured across passes
assumes the passes are exchangeable. If grading quality drifts with server load
rather than varying randomly, the measured sd is inflated by *drift*, and calling
it "grader noise" would be wrong in the same way that calling a fallback-inflated
score "quality" was wrong in `EXP-2026-08-019`.

**Check before reporting any sd:** whether the per-cell means trend monotonically
across p1 → r5. A monotone trend across five passes on many cells is drift; an
unordered scatter is noise. This is cheap — the data is already being collected —
and it must be done before H5 is adjudicated.
