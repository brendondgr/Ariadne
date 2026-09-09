# RESULTS — EXP-2026-08-009 Does federating beat merging?

**Status: complete.** Run 2026-08-21, commit `79e11b0`. Raw artifacts:
`docs/evaluation/merged-2026-08-21-v2/`.

## 1. Headline

**No.** On two blind question sets, with everything but the number of stores
held constant, merging is not worse than federating in any way this study can
measure.

| | set 1 | set 2 |
|---|---:|---:|
| **one** store, both catalogues (`merged`) | 0.9233 (0.857–0.983) | 0.9367 (0.870–0.990) |
| **two** stores, otherwise identical (`generic_composed`) | 0.9567 (0.910–0.993) | 0.9367 (0.873–0.987) |
| merging minus federating | **−0.0334** | **+0.0000** |

n = 30 per cell, judged correctness, 95% bootstrap interval over questions. Both
arms are byte-reproducible — no language model in either — so neither figure
carries run-to-run variance, and the grader graded all eight cells of this
experiment in one session.

Federating leads on one set by 0.0334 and by nothing at all on the other. The
intervals overlap almost entirely on both. **C-015 as written — *federating
outperforms merging* — is not supported.**

## 2. Secondary readings, same grader, same session

| arm | set 1 | set 2 |
|---|---:|---:|
| `generic` — no templates, LLM narrator | 0.9833 | 1.0000 |
| `deterministic` — templates, deterministic composer | 0.9667 | 0.9667 |

`generic` remains the strongest configuration in the study. It differs from
`merged` in two ways, so it cannot carry C-015; see §5.

## 3. Fabrications

| arm | set 1 | set 2 |
|---|---:|---:|
| `merged` | 2 | 3 |
| `generic_composed` | 3 | 1 |
| `generic` | 0 | 1 |
| `deterministic` | 0 | 0 |

The two deterministic-composer arms fabricate at the same rate whether they sit
over one store or two — 5 answers against 4 across 60 questions each. The defect
is the composer naming software and group identifiers as "used techniques", and
it is unrelated to storage. In the first, confounded pass it looked like a cost
of merging, because the arm it was compared against had a language model writing
its prose.

## 4. The mechanical half

The merged store holds 9138 nodes and 34641 relationships — the exact sum of the
two catalogues — and all eight separation checks pass. `Mitigation`, the one
label both catalogues use, splits 44 / 1170 by marker label with nothing
unmarked and nothing in both. A `MITIGATES` traversal reaches no CAPEC node. The
main ATT&CK store was counted before and after every load and did not move.

Two things had to be decided to get there, both recorded as D-016 and D-017:
the Neo4j loader's relationship-name rule was widened to admit the five names
CAPEC's own XML supplies, and the merged build reconciles two identifier forms
at load that the federated system reconciles in code at query time.

## 5. What this does and does not show

**Shows.** With one store against two and everything else identical, correctness
does not separate on anchored questions over these two catalogues. Whatever
justifies federation here, it is not answer quality.

**Does not show.** That the two are equivalent. n = 30 per set is small and the
intervals are wide; a real effect of a few hundredths would not be visible.

**Does not show.** Anything about the regime where the two designs plausibly
differ most — open-ended, non-anchored questions (Q4), or catalogues whose
identifier spaces collide, which these two do not.

**Does not test** the arguments federation is usually made on: provenance,
licensing, staleness, and not having to re-run a merge when a catalogue updates.
Those are real and are untested here, and they should be stated as the surviving
case for federation rather than implied by a correctness figure that does not
exist.

**One advantage travels with the merged arm and is reported, not hidden.** In one
store the next hop of a cross-catalogue question is reachable without leaving
the engine, so the merged arm takes a join value off a *neighbour's* identifier
where a federated specialist cannot act on one. That is a property of the
architecture. It moved consumer sub-questions skipped for want of a join value
from 7 of 30 to 3 of 30, and the three that remain are the cases whose gold
asserts the skip.

## 6. Threats to validity

Every threat in `PROTOCOL.md` §"Threats to validity" stands. Added by the run:

- **The first comparison was confounded and the first pass caught it.** See
  `ISSUES.md` D1. The superseded figures are on disk and are quoted nowhere.
- **Three cases needed a third grading attempt** at 32768 tokens after two empty
  replies. All are 177k–205k-character answers to one question, `H-CHN-01` on
  set 2, in every arm including the LLM-narrator one — so the size is a property
  of the question, not of a composer. Size is not decisive on its own: the
  largest of the four (205k, `merged`) graded first time while smaller ones did
  not.
- **The grader is unvalidated against a human** (Q6), and it moved between the
  two passes on the same saved answers — `generic` on set 2 scored 1.0000 with
  0 fabrications in one pass and 1 fabrication in the other. That is why every
  cell quoted here was graded in a single session.

## 7. Follow-ups

- **Q5 is answered** and should be closed with this result.
- **C-015 needs rewriting**, not re-running. The correctness claim is gone; the
  provenance/licensing/staleness case for federation has never been written down
  as a claim, and it is what is left.
- **The composer's label defect** (§3) is worth a fix on its own: it is the only
  fabrication source in either deterministic arm, and it is one wrong noun.
- **`generic_composed` is now a judged arm** and did not exist before. It is the
  missing cell in the arm table — schema primitives with deterministic
  composition — and EXP-2026-08-001 measured only its retrieval.

---

# AMENDMENTS

## A-1 (2026-08-31) — the reported figures are one pass by an unidentified model, and the order was fixed

**Nothing was re-run.** The saved answers were re-graded: six passes in the
original grading order and two with it reversed.

Two defects in how this experiment's headline was produced, one small and one
not.

### The small one: grading order, and it does not change anything here

`merged_sweep.py:223` graded `(MERGED_ARM, *FEDERATED_ARMS)` — so **`merged` was
graded first and `generic_composed`, the federated control, second, on every
bank in every pass.** `EXP-2026-08-022` then measured what that costs: on
byte-identical answers the condition graded **second** scores about **0.01
lower**, whichever condition it is, proved by a sign flip when the order was
reversed. The bias was therefore loading entirely onto federation, in the one
direction that would make this experiment's conclusion easier to reach.

Measured on this contrast, it is smaller than that:

| bank | forward (merged first, 6 passes) | reversed (federated first, 2 passes) | order effect |
|---|---|---|---|
| 19 | −0.0565 | −0.0608 | **+0.0043** |
| 20 | −0.0491 | −0.0550 | **+0.0059** |

**≈0.005, consistent in direction, and immaterial to any reading here.** Recorded
because it was real and undetected, not because it matters. `merged_sweep` now
counterbalances the order per bank (`utils/evaluation/grading_order.py`) and every
judgment records its position.

### The one that matters: the grader

The reported **−0.0334 / +0.0000** comes from the `.c015` pass — **one pass, by a
model that cannot be identified**, run 2026-08-19..21 inside the window `Q12`
describes. Re-graded by `qwen38-27B-v2`, calibrated at r = 0.9612 against the
committed Sonnet judgments:

| bank | as reported (`.c015`, n=1) | **order-corrected, 8 passes** |
|---|---|---|
| 19 | −0.0334 | **−0.0587** |
| 20 | **+0.0000** | **−0.0520** |

The `.c015` pass is the **least federation-favouring of all eight**, and it is the
one this experiment reported. Both passes grade merged first, so **order cannot
explain the gap — the grader does**, and it is worth roughly 3–10× the order
effect.

### What changes, and what does not

**The conclusion stands.** `EXP-2026-08-009`'s own limits section says n = 30 per
set with bootstrap intervals of roughly ±0.06 over questions, and a 0.05–0.06
contrast sits inside that. Eight grading passes make the *grader* confident and
add **nothing** to the question sample. **C-015 stays refuted and C-022 stays a
claim about cost and constraint rather than accuracy.**

**The specific numbers should not be quoted.** *"Merging is not worse in any way
this study can measure"* rested on `+0.0000` on bank 20, and that exact zero is an
artifact of one pass by an unnamed model. Under a named, calibrated grader
federation leads on **both** banks by ~0.05, consistently, in both grading orders
— still not a demonstrable difference at this n, but not a tie either.

**The honest restatement:** *no difference is demonstrable at n = 30 under any
grader tested; the point estimate favours federation by about 0.05 and the
question sample cannot resolve it.* Closing that needs more questions, not more
grading — the one thing eight passes proved conclusively.

## AMENDMENT A-2 (2026-09-09) — The withdrawn headline moved out of `values`; pointers and provenance filled

Written during the 2026-09-09 record audit. This records in the manifest what
A-1 already said in prose; it adds no new measurement.

**1. Withdrawn values (manifest `metrics`).** A-1 retracted the reported
figures but they were still the manifest's current values. Moved from
`metrics.values` to `metrics.withdrawn`, `withdrawn_on: 2026-08-31`, reason
"one grading pass by an unidentified model; the exact zero was an artifact (A-1)":

| key | old (withdrawn) | replaced_by |
|---|---|---|
| `merged_minus_federated_bank20260819` | −0.0334 | `EXP-2026-09-006:c022_margin_bank19_qwen` |
| `merged_minus_federated_bank20260820` | 0.0000 | `EXP-2026-09-006:c022_margin_bank20_qwen` |
| `merged_minus_federated_mean` | −0.0167 | none |

Added to `values` from A-1's "order-corrected, 8 passes" column (merged −
federated): `merged_minus_federated_bank20260819_8pass_order_corrected` =
**−0.0587** (n 30) and `merged_minus_federated_bank20260820_8pass_order_corrected`
= **−0.0520** (n 30). `metrics.primary`: `merged_minus_federated_mean` →
`merged_minus_federated_bank20260819_8pass_order_corrected`. The four per-arm
cell means (0.9233 / 0.9367 / 0.9567 / 0.9367) stay in `values` as the `.c015`
cells they are, labelled by comment. The same additions are mirrored in
`data/metrics.json` under `manifest_metrics` and `amendment_a1`.

How the eight-pass figures were established (recomputed 2026-09-09 from the
sidecars): forward six passes = `.c015` + `.qwen38`, `r2`–`r5` → −0.0565 /
−0.0491 (bank 20 paired; −0.0480 unpaired because `r3`/`r4` have n = 29);
reversed two passes `.c022rev1`/`.c022rev2` → −0.0608 / −0.0550; the
order-corrected figure is the mean of the forward and reversed means. Note that
the six forward passes therefore **include** the `.c015` pass A-1 is correcting
for; without it the seven-pass figures are −0.0610 / −0.0571 (ISSUES D4).

**2. The quotable cross-grader readings of this contrast** are not in this
experiment: EXP-2026-08-021 (+0.0625 / +0.0567 on banks 19 / 20, five
`qwen38-27B-v2` sessions, reported with the **generic − merged** sign) and
EXP-2026-09-006 (+0.0608 / +0.0581 qwen; +0.0500 / +0.0400 gemma, saturated).
Both are added to `related`; this experiment is refined by them, not
superseded — its conclusion (no demonstrable difference at n = 30; the point
estimate favours federation by ~0.05) stands.

**3. Provenance fields corrected in place** (ISSUES D5): `code.commit`
`79e11b0` → `79e11b0ed11e6566cd0ce8f931db3aaed73dbd45`; `llm.model`
`"relay/skynet"` → `"relay/unknown@2026-08-21"`; `llm.nondeterminism_note`
template text → a statement of the one-pass design and the A-1 regrades;
`related` + EXP-2026-08-011 (I-13 dependency), EXP-2026-08-021,
EXP-2026-08-022 (the order-effect measurement A-1 cites), EXP-2026-09-006.

**4. `data/POINTERS.md`** was the blank scaffold; it now names and hashes the
three `merged-2026-08-21-v2/` files and the eight `answers/` directories, with
the sidecars later passes added to each. All eight `.c015` cells (means, CIs,
verdicts, faithfulness, hallucinating-answer counts, abstentions) reproduce
exactly from those directories.
