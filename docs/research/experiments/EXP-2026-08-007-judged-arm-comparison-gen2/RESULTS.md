# RESULTS — EXP-2026-08-007 Judged arm comparison, generation 2

## 1. Headline

The repair is real on **answers**, not just coverage: paired over the same 30
blind questions and the same grader, correctness rises **0.7200 → 0.8367,
+0.1167**, 95% CI +0.0333 to +0.2167, excluding zero. The arm ordering is the
part worth arguing about — the cascade and Arm H are **indistinguishable** on
correctness, while Arm F leads by +0.079 blind and by nothing at all on the
catalogue, buying that lead with hallucinations in 4 of 30 blind answers where
the deterministic arms produced none.

## 2. Results table

Every figure below is computed in `data/metrics.json`. **`n_runs: 1`** for the
pipeline — each arm answered each bank once, and no arm-level std exists. The
only repeated measurement is of the *grader*, three passes over one fixed
answer set, and that is reported as its own row rather than smuggled in as a
pipeline error bar.

### The question the repair was built to answer

| | correctness |
|---|---|
| before (holdout-v1, pre-fix answers) | 0.7200 |
| after (repaired cascade) | 0.8367 |
| **paired delta** | **+0.1167** (95% CI +0.0333 – +0.2167) |

10 improved, 3 regressed, 17 unchanged; worst single-case movement −0.15.

### Arms

| arm | bank | n | correctness (95% CI) | C/P/I | faithfulness | answers w/ hallucination | abstained / carried query |
|---|---|---:|---|---|---:|---:|---|
| Cascade | blind | 30 | 0.8367 (0.752 – 0.915) | 22/8/0 | 0.980 | **0** | 3 / 3 |
| Arm H | blind | 30 | 0.8483 (0.778 – 0.915) | 21/9/0 | 0.952 | 1 | 4 / 2 |
| Arm F | blind | 30 | **0.9157** (0.856 – 0.963) | 25/5/0 | 0.960 | 4 | 4 / 4 |
| Cascade | catalogue | 120 | 0.9839 (0.977 – 0.990) | 119/1/0 | 0.988 | 3 | 21 / 20 |
| Arm H | catalogue | 120 | 0.9692 (0.955 – 0.980) | 115/5/0 | 0.975 | 9 | 20 / 11 |
| Arm F | catalogue | 120 | 0.9852 (0.979 – 0.990) | 117/3/0 | 0.978 | **19** | 21 / 20 |

### The grader, and the noise floor

| | value |
|---|---|
| calibration vs committed Sonnet judgments (n=30) | Pearson r **0.9275** |
| mean delta (local − Sonnet) | +0.031 |
| verdict agreement | 0.70 |
| three passes over one fixed answer set | 0.8367 / 0.8417 / 0.8400 |
| **grader spread** | **0.0050** (sd 0.0021) |

### Co-authorship, priced

| | correctness |
|---|---|
| cascade, 120-question catalogue | 0.9839 |
| cascade, 30 blind questions | 0.8367 |
| **gap** | **0.1472** |

## 3. Figures

None. This experiment produces no figure of its own; its numbers feed the
standing arm-comparison figure, which is regenerated from `metrics.json` when
the full arm matrix is next re-measured (see §7). Adding a figure here that
duplicates one table would be decoration, not evidence.

## 4. Interpretation

**C-001** (deterministic pipeline near-ceiling with zero hallucinations) —
strengthened where it was weakest and narrowed where it overreached. The blind
figure moves 0.689 → 0.8367 under a comparable grader, so the claim is no
longer carrying a two-thirds-of-ceiling blind number. Zero hallucinations held
across 30 blind answers and the claim's "zero hallucinations" half is now
evidenced blind rather than only on the catalogue. Still `partial`: the blind
bank is burned, and 3 of 120 catalogue answers did contain fabrications.

**C-003** (the templates are where the accuracy lives) — this is the claim the
experiment damages, and it should be said plainly. Arm H disables the templates
entirely and judged **level with the cascade** (0.8483 vs 0.8367, a difference
2.3× the grader's own spread, with almost totally overlapping intervals). The
3.0× ratio in the original claim came from Arm G, an earlier and weaker generic
arm. On this evidence the templates are not where the *correctness* lives. What
they demonstrably still hold is **provable abstention** (§ below) — which is a
narrower and more defensible claim than the one currently written.

**C-013** (near-ceiling is an artifact of co-authored questions) — already
`refuted`, meaning the artifact hypothesis won. This adds the price tag:
**0.1472**, measured same-system, same-grader, same night.

**C-014** (the coverage cliff is measurable) — the retrieval half was closed by
EXP-2026-08-006 and saturated. This supplies the judged half for the first
time, so the cliff is now priced in correctness rather than coverage.

**C-017** (abstention carrying query proof, `unsupported`) — can move to
`partial`. It previously rested on self-consistency checks. There is now a
measured rate: the cascade carried proof on **20 of 21** catalogue abstentions
(95%) and 3 of 3 blind; Arm H on **11 of 20** (55%) and 2 of 4. The claim's
"without reducing answer coverage" half remains untested, and `wrongful_abstention`
appears on 2–3 questions per arm — the system declining when it held the
evidence — which cuts against the claim from the other side.

**C-021** (new) — a blind/co-authored gap of 0.1472 measured under one grader.

**Q2** (grader variance unrecorded; `statistical_test: null` in every manifest)
— answered. 0.0050 across three passes on deterministic answers.

## 5. Threats to validity

- **The blind bank is not blind any more.** It diagnosed the direction and join
  defects, and both were fixed in response. Every blind figure here is a
  diagnostic, not a measurement of generalisation. This is the single largest
  threat and it applies to the headline delta as much as anything else.
- **The grader is not independent.** A local model grading answers from a
  pipeline whose own LLM seams run on the same relay shares failure modes with
  it. Calibration (r = 0.9275) is the only evidence about how far that matters,
  and it is measured on 30 answers of one arm.
- **The grader runs ~0.03 generous** against the Sonnet reference. Absolute
  levels carry that offset; differences largely do not.
- **Verdict agreement is 0.70** while rank correlation is 0.93. Case-level
  verdicts are not stable enough to quote individually — a point confirmed
  directly, since two passes over identical answers disagreed on one
  hallucination and on the abstention count.
- **Cost is not measured and the comparison is not cost-fair.** Arm F calls an
  LLM per question; the cascade does not. No cost claim may be drawn from here.
- **n = 30** blind, one pipeline run per arm, seeds unrecorded.
- **Arm F's catalogue lead is inside the interval** (0.9852 vs 0.9839), so
  "Arm F beats the cascade on the catalogue" is not a supportable reading.
- **The `answer_gap` shares are fractions of the whole run's deficit** and do
  not sum to 1; and its classifier is a magnitude-argmax, so a question with a
  small groundedness dock and nothing else lands in `ungrounded` regardless of
  how small.

## 6. What surprised us

**Three things, one of which changes the plan.**

*Arm F's advantage is not general — it is entirely a coverage effect.* Blind it
leads by +0.079; on the catalogue it leads by 0.0013, i.e. nothing, while
hallucinating in 19 of 120 answers against the cascade's 3. The LLM loop earns
its keep exactly where the templates stop covering the question and is pure
downside inside that coverage. A catalogue-only evaluation would have called it
a regression; a blind-only evaluation would have called it a clear win.

*The templates hold provable abstention, not accuracy.* Arm H matching on
correctness while its abstention-proof rate falls to 55% was not predicted, and
it reproduced independently on both banks. The property the project leads with
is the one most at risk on the portable path — the opposite of the assumption
built into C-003.

*Where the remaining loss sits is not where we expected.* With retrieval at
30/30 on both arms, the largest bucket is `ungrounded` (0.095, 11 questions)
rather than `under_enumeration` (0.063, 3 questions). Under-enumeration is 2.4×
more severe per affected question but touches a fifth as many. This reorders the
composer work, and the plan was changed on the strength of it.

## 7. Follow-ups

1. **Rewrite C-003 to claim provable abstention rather than accuracy.** The
   present wording is not supported by Arm H's judged result. → `Q14`
2. **Fix the composer's grounding defect before its enumeration defect.**
   Ordering follows from §6, not from prior intuition. → `Q15`
3. **Make a fresh, fairly-drawn question bank cheap to produce.** Every figure
   here is bounded by having exactly one burned blind bank and one flattering
   catalogue. Gold is already computed mechanically; only the question sentence
   is authored, and even that came from a scripted prompt. → `Q16`
4. **Re-grade with the cross-model panel before anything is quoted externally.**
   Calibration justifies this grader for development, not for publication.
5. **Investigate Arm H's abstention-proof gap.** 55% vs 95%, reproduced on both
   banks, in the property the pitch rests on.

## 8. Reproduction

```bash
# CAPEC's Gremlin store does not survive a restart — reload before any pipeline phase
uv run main.py --dataset capec --graph gremlin && uv run main.py --dataset capec --graph verify

# the full chain: calibrate, judge both deterministic arms on both banks,
# three grader passes, answer-gap, then Arm F generation 2
nohup uv run python scripts/overnight_sweep.py --workers 12 > logs/overnight.log 2>&1 &

# report and metrics
uv run python -c "import sys; sys.path.insert(0,'.'); \
from pathlib import Path; from scripts.overnight_report import write_report; \
write_report(Path('docs/evaluation/overnight-2026-08-19'))"
```

Four oversized enumeration cases need a larger grader budget and are recovered
separately — see `ISSUES.md` §3:

```bash
uv run python -m utils.evaluation.judge_answers \
  --root docs/evaluation/experiments/<root> --arm <arm> --workers 2 --max-tokens 32768
```
