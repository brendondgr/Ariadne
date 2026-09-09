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

---

# AMENDMENTS

## A-1 (2026-08-23) — Q15 answered: the abstention-proof gap is two mechanisms, one of them the grader

**Nothing was re-run.** This reads the committed judgment and answer artifacts
under `docs/evaluation/experiments/outerjoin-dev/deterministic/answers/` and
`docs/evaluation/experiments/untruncated-generic-outer/generic/answers/`.

Q15 asked which of three defects explains Arm H carrying the executed query on
only 11 of 20 catalogue abstentions against the cascade's 20 of 21: was the query
never executed, executed and lost, or executed and not attached? **It is none of
the three.** The nine unproved abstentions split into two mechanisms.

### Mechanism 1 — a missing abstention, not a missing proof (6 of 9)

On `F-NEG-01` … `F-NEG-06` the cascade emits **two** abstentions and Arm H emits
**one**. For `F-NEG-01` the cascade says:

| source | statement | query |
|---|---|---|
| `capec` | the executed query ran cleanly and returned CAPEC-116 with no linked records | *present* |
| `attack` | the sub-question it depends on (q1) produced no seed identifiers, so no query was executed | *empty, correctly* |

Arm H emits only the second. The proof is not lost or unattached — **the
source-side abstention is never produced at all**, so the answer never declares
that the ATT&CK mapping is absent with the query that proves it.

The cause is upstream of proof attachment, in `_empty_ok_results`
(`utils/synthesis/verifier.py`), which selects the results that must carry an
abstention: *nothing found, or nothing joined*. The template path's narrow
`capec_maps_to` query returns the anchor with an empty taxonomy fold, which is
"nothing joined". The generic path returns the anchor **plus its real
neighbours** — the WASC taxonomy entry on CAPEC-66, for instance — which is
neither empty nor unjoined at that call site, so the branch is never reached.
**The over-returning that costs the generic arm precision is the same property
that costs it its abstention.** That is one defect with two prices, and it is
the sharpest thing this amendment records.

### Mechanism 2 — grader noise on byte-identical inputs (4 cases)

`F-PART-01`, `F-PART-02`, `A-AST-01` and `A-AST-02` have **byte-identical
abstention objects in both arms** — same source, same statement, same empty
query — and the grader assigned different `abstention_carries_query` values
anyway. Three favour the cascade, one favours Arm H, so the net effect is **+2
to the cascade** from noise alone. `abstention_carries_query` is an LLM-assigned
field, not a computed one, which is how identical inputs can diverge.

### Corrected reading

Scoring the four noise cases identically, whichever convention is chosen:

| convention | cascade | Arm H | gap |
|---|---|---|---|
| strict (an empty query is not proof) | 17/21 = **0.810** | 10/20 = **0.500** | 0.310 |
| lenient (explaining why no query ran is proof) | 21/21 = **1.000** | 14/20 = **0.700** | 0.300 |
| **as originally reported** | 20/21 = 0.952 | 11/20 = 0.550 | 0.402 |

**The gap is real, it is about 0.30 rather than 0.40, and all of it is
Mechanism 1.** The headline pair "95% against 55%" overstates the separation by
roughly a quarter and should not be quoted further; quote a convention and its
pair. One case is neither mechanism: `C-MAP-NEG-01`, where the cascade abstains
with proof and Arm H does not abstain at all — a coverage difference rather than
a proof one, and it is excluded from both rows above.

### What this changes

- **C-017** may still claim enforced abstention-with-proof is materially stronger
  on the default path, but at ~0.30 and with the mechanism named.
- **C-003** is refuted and superseded by **C-023**; this amendment supplies the
  corrected abstention figures C-023 quotes. The direction is unharmed and the
  size is reduced.
- The defect is **fixable and localised** to one predicate. It is deliberately
  *not* fixed here: a fix moves recorded numbers and needs its own experiment
  plus a recorded-answer regression diff.
- A grader that disagrees with itself on identical input is a threat to validity
  wherever a judged binary field carries a claim. The 0.0050 correctness spread
  recorded in §2 does not bound this, because it was measured on correctness.

## AMENDMENT A-2 (2026-09-09) — Pointers re-hashed, the "before" pointer re-pointed, the grader model marked unknown, C-021 cross-referenced

Written during the 2026-09-09 record audit. **No figure in §1–§8 or A-1
changes.** All ten manifest values, the six arm roll-ups, the three-pass spread,
the co-authorship gap and the paired delta were recomputed from the artifacts
on 2026-09-09 and reproduce exactly (the paired delta and calibration only from
the `.pre-qwen38` copies — see below).

**1. Judgment-set hashes (POINTERS.md, "Judgment sets" table).** The six rows
carried set digests (`sha256sum` over sorted `*.judgment.json` names +
contents) that the validator cannot check; against the directories' tree hashes
it reported all six as changed. Nothing was added to those directories after
the record was committed (2026-08-19 12:29): the difference is the digest
scheme. Old → new (path, old set digest → new tree hash as of 2026-09-09):

| path | old (set digest, still verifies) | new (tree hash) |
|---|---|---|
| `outerjoin-holdout/deterministic/answers` | `f975b544…4549` | `1af3a518…dbfeb` |
| `holdout-v1-generic-outer/generic/answers` | `711d7857…07d1` | `d97c1d3d…3af6c` |
| `outerjoin-dev/deterministic/answers` | `a931d9a4…c639` | `4370c629…8dcae` |
| `untruncated-generic-outer/generic/answers` | `7fe39982…0e34` | `dc4b659b…fa41c` |
| `gen2-armf-holdout/gold_loop_llm/answers` | `1e2284ae…8aa3` | `84725efd…07704` |
| `gen2-armf-dev/gold_loop_llm/answers` | `582e12ce…dcbb` | `8f182b5c…0f4f` |

**2. The "before" pointer (POINTERS.md "Two caveats", old lines 44–51).** It
said the before side of the paired delta lives in
`docs/evaluation/experiments/holdout-v1/deterministic/answers/*.judgment.local.json`,
"never overwritten". Those files **were** overwritten on 2026-08-31 by
EXP-2026-08-021's regrade; the E0 pass survives as
`*.judgment.local.pre-qwen38.json`. Old value: an un-hashed path that now yields
+0.1267 / r = 0.9612. New value: a tree-hashed row for the directory plus the set
hash of the 30 `.pre-qwen38` files (`sha256:639dbf46…7b36`), which yield the
recorded +0.1167 (CI 0.0333–0.2167), 10/3/17, r = 0.9275 exactly. Established
by recomputation from both file sets during the audit and by the committed
`overnight-2026-08-19/calibration.json` (r 0.9275, local mean 0.72). ISSUES §9.
**+0.1167 and r = 0.9275 are not withdrawn.**

**3. Manifest `llm.model`:** `"relay/skynet@qwen38-27B-awq"` →
`"relay/unknown@2026-08-19"`. The sidecars record only the alias; the
repository's model history (`docs/evaluation/README.md`) classifies the window
as undetermined; the `awq` name rests on ISSUES §8's recollection alone. The
`nondeterminism_note` sentence naming `qwen38-27B-awq` is likewise amended in
place to say so, and `data/metrics.json` `judge.model` now reads
`relay/unknown@2026-08-19 (sidecars record only the alias "skynet"; manifest
previously said qwen38-27B-awq)`. ISSUES §10.

**4. C-021 and EXP-2026-08-008.** §2's co-authorship gap 0.1472 (0.9839 − 0.8367)
is valid as the **pre-composer-fix** measurement. EXP-2026-08-008, run the same
day at commit 514fb9a3, re-measured the same two banks with the composer
repaired and found **0.0483** (0.9833 − 0.9350); 0.0483 is the figure CLAIMS
quotes for C-021. This experiment is refined, not superseded, by
EXP-2026-08-008 (`related` now lists it); its other quotable descendants are
EXP-2026-08-021 (the same blind answers regraded five times by a named model)
and EXP-2026-09-006 (cross-family regrade) — both added to `related`.

**5. A-1's corrected abstention-proof rates** (17/21 = 0.810, 10/20 = 0.500
strict; 21/21 = 1.000, 14/20 = 0.700 lenient; C-MAP-NEG-01 excluded) were in
RESULTS only; they are now in `data/metrics.json` under
`abstention_proof_rate.a1_corrected`.

Manifest fields changed by this amendment: `llm.model`, `llm.nondeterminism_note`
(one sentence), `related` (+ EXP-2026-08-008, EXP-2026-08-021, EXP-2026-09-006).
No metric value changed.
