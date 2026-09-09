# RESULTS — EXP-2026-08-008 Composer fixes, and the first fresh bank

## 1. Headline

Letting a language model write the queries scores **0.5000** where the template
cascade scores **0.9467** on the same unseen questions — and **0.5739** even
after crediting every failure that was our evidence reader's fault rather than
the model's. C-012, the paper's intended headline and previously supported by
nothing, is now supported. Separately, the morning's two answer-writing fixes
are worth **+0.098** paired on the blind set, and that gain shows that
two-thirds of the co-authorship gap recorded hours earlier in EXP-2026-08-007
was those defects, not the questions.

## 2. Results table

From `data/metrics.json`. One pipeline run per arm (`n_runs: 1`); the only
repeated measurement in this study is of the grader, established at a 0.0050
spread in EXP-2026-08-007, and every difference below is read against it.

### The answer-writing fixes — same 30 questions, same grader, code the only variable

| | correctness |
|---|---|
| before | 0.8367 |
| after | **0.9350** |
| **paired delta** | **+0.0983** (95% CI +0.025 to +0.180) |

10 improved, 2 regressed, 18 unchanged. Fully-correct answers 22 → 27 of 30,
hallucinations 0 → 0. The three questions predicted in advance to move — those
answering "what is this and how does it work?" with STIX bookkeeping — moved
from 0.50 to 0.95 each.

### Four arms, fresh bank (30 questions no arm has seen)

| arm | correctness (95% CI) | C/P/I | answers w/ hallucination | abstentions w/ proof |
|---|---|---|---:|---|
| LLM-assisted (`gold_loop_llm`) | 0.9773 (0.962–0.990) | 30/0/0 | 0 | 4/4 |
| No templates (`generic`) | 0.9700 (0.940–0.992) | 29/1/0 | 2 | 4/4 |
| Template cascade (`deterministic`) | 0.9467 (0.915–0.972) | 29/1/0 | **0** | 4/4 |
| **LLM writes the query** (`llm_query`) | **0.5000** (0.415–0.585) | 11/18/1 | 5 | — |

The top three are indistinguishable. The fourth is not close to them.

### Co-authorship, re-measured on identical questions

| | catalogue (120) | blind (30) | gap |
|---|---|---|---|
| before the fixes | 0.9839 | 0.8367 | **0.1472** |
| after the fixes | 0.9833 | 0.9350 | **0.0483** |

## 3. Figures

None. The numbers feed the standing arm-comparison figure, regenerated from
`metrics.json` when the arm matrix is next rebuilt.

## 4. Interpretation

**C-012 — supported, for the first time.** *"Routing to a fixed library of
validated parameterised templates outperforms letting an LLM plan and generate
the queries."* The margin is 0.9467 against 0.5000 on questions neither had
seen. The baseline was built to be fair rather than a strawman: the model is
given the real schema, the resolved seed identifiers, the constraints the gate
enforces, the harness's output-column convention, and a repair loop that feeds
gate rejections back. It is denied only the templates.

**C-021 — materially corrected, hours after it was written.** It recorded the
co-authorship gap at 0.1472. On identical questions with the composer repaired
the gap is **0.0483**. Two-thirds of what was attributed to the question set was
a defect in how answers were written, which hit naturally-phrased blind
questions harder than catalogue questions phrased in ways that happened to
trigger the working path. The effect is real and roughly a third the size.

**C-001** — the cascade reaches 0.9467 on never-seen questions with zero
fabrications and every abstention carrying its query. That is the strongest
blind result the deterministic path has recorded.

**C-003** — a second independent measurement that the templates do not hold the
*accuracy*: the no-templates arm scored 0.9700 against the cascade's 0.9467.
What separates them is fabrication (2 answers against 0). Q14's rewrite stands.

**C-017** — every arm carried proof on 4 of 4 abstentions here, including the
generic arm that managed 11 of 20 last night. Small n; noted, not concluded.

## 5. Threats to validity

- **The fresh bank is machine-authored.** Phrasing is less varied than a
  human's, and it may therefore be easier. Some of the narrowed co-authorship
  gap could be that — though the *paired* catalogue-vs-blind comparison in §2,
  which uses the same human-authored questions on both sides, is not exposed to
  this and shows the same collapse.
- **7 of the LLM-query arm's 30 questions failed on our evidence reader**, which
  dispatches on the column shapes the templates emit. Reported apart, and the
  headline conclusion is stated against the adjusted 0.5739 as well as the raw
  0.5000 so it does not rest on the ambiguous cases.
- **2 of its 3 gate rejections were empty replies** — the token-truncation mode
  seen twice before in this repository. Part of that bucket may also be ours.
- **The grader is not independent** and runs ~0.03 generous (r = 0.9275 against
  the Sonnet judgments). Fine for comparing arms; not a publication figure.
- **n = 30** per arm on the fresh bank; single run per arm; seeds unrecorded.
- **One catalogue answer failed to grade** (n = 119 of 120), the oversized-answer
  truncation recorded in EXP-2026-08-007 ISSUES §3.

## 6. What surprised us

**The composer fixes were three times larger than predicted.** The hypothesis
said the aggregate would barely move because only a handful of questions were
affected. Ten of thirty moved and the mean rose 0.098. The defect was more
widespread than the three cases that made it visible.

**And it ate a headline finding recorded the same morning.** C-021's 0.1472 gap
was measured before the fixes; two-thirds of it was the fixes' fault. A figure
written into the ledger at 09:00 was two-thirds wrong by 20:00. The lesson is
not that the ledger was careless but that a bias measurement taken over a
defective pipeline measures the defect too.

**The LLM-query gap is far larger than expected.** The working assumption was
that a model with the schema in front of it would be roughly competitive and
lose on edge cases. It loses by half, and not mainly on syntax — most of its
queries pass the safety gate and execute.

## 7. Follow-ups

1. **Decide whether the evidence reader should accept non-template column
   shapes.** It would make the C-012 comparison unambiguous. Reporting the split
   is the alternative and is what this experiment does. → `Q18`
2. **Re-run the LLM-query arm with a larger token budget**, since two of its
   three gate rejections were empty replies rather than bad queries.
3. **CAPEC execution steps have descriptions the system does not surface** —
   the same class of defect as the two fixed here, one level down. Found while
   diagnosing H-EXE-01.
4. **Re-grade with the cross-model panel** before anything here is quoted
   outside the repository.

## 8. Reproduction

```bash
uv run main.py --dataset capec --graph gremlin     # the Gremlin store does not survive a restart
uv run python scripts/measure_arms.py --workers 12

# the catalogue re-run behind the corrected co-authorship figure
uv run python -m utils.evaluation.experiment_untruncated --arm deterministic \
  --root docs/evaluation/experiments/composerfix-dev
uv run python -m utils.evaluation.judge_answers \
  --root docs/evaluation/experiments/composerfix-dev --arm deterministic --workers 12
```

---

# AMENDMENTS

## AMENDMENT A-1 (2026-09-09) — Pointers re-hashed, the model marked unknown, the C-021 figure placed, refinements linked

Written during the 2026-09-09 record audit. **No figure in §1–§8 changes**: all
eight manifest values, the four fresh-bank roll-ups, `catalogue_after_fix`, the
paired composer-fix delta (before 0.8367, after 0.9350, +0.0983, CI
0.025–0.180, 10/2/18), the co-authorship figures 0.0483 / 0.0366 and the
reader-adjusted 0.5739 were recomputed from the sidecars on 2026-09-09 and
reproduce exactly.

**1. `data/POINTERS.md` judgment-set rows.** Old: six set digests over
`*.judgment.json` (`ab6126f1…`, `7a03a818…`, `c744c418…`, `668b5bb1…`,
`8ff28c96…`, `ee50b56d…`), which still verify but which the validator flagged
because it tree-hashes the directory. New: tree hashes as of 2026-09-09
(`e034f420…`, `0219150f…`, `d88e7df4…`, `4034e679…`, `86490c6e…`,
`d15b78a1…`) with each row naming the sidecars later experiments added. The
answer files and this run's `.judgment.json` files are unchanged. ISSUES §7.

**2. Manifest `llm.model`:** `"relay/skynet (grader and query writer); relay/local
for bank authoring"` → `"relay/unknown@2026-08-19"`. The served model behind
both aliases on 2026-08-19 is not recorded anywhere in the artifacts
(sidecars carry only `"skynet"`) and the repository's model history marks the
window undetermined. Roles, for the record: the relay `skynet` alias graded
every answer and wrote the `llm_query` arm's queries; the `local` alias
authored the fresh bank (ISSUES §3). ISSUES §8.

**3. Manifest `llm.nondeterminism_note`:** was the unedited template sentence
("results are reported as mean ± std over n_runs") for a study with n_runs = 1.
Now states that each arm ran once and that grader variance is bounded by
EXP-2026-08-007's three-pass spread 0.0050, not measured here.

**4. C-021.** §4 says C-021's 0.1472 (EXP-2026-08-007) is "materially
corrected" to **0.0483** by this experiment. To be precise about what that
means for the record: 0.1472 remains valid as EXP-2026-08-007's
pre-composer-fix measurement and is not withdrawn there; **0.0483 is the figure
CLAIMS quotes for C-021**, from `coauthorship_gap_after_fix` here. This is a
refinement, not a supersession — EXP-2026-08-007 is added to `related` here and
carries the reciprocal note in its A-2.

**5. Later refinements.** EXP-2026-09-005 (post-repair arm comparison) and
EXP-2026-09-007 (holdout spend) re-measure the arm ordering this experiment
first established on a fresh bank; both are added to `related`. Neither
overturns a figure here.

Manifest fields changed by this amendment: `llm.model`, `llm.nondeterminism_note`,
`related` (+ EXP-2026-08-007, EXP-2026-09-005, EXP-2026-09-007). No metric value
changed.

## AMENDMENT A-2 (2026-09-09) — the primary metric now names a recorded key

`metrics.primary` was `llm_query_vs_templates_fresh_bank`, a label for the comparison rather than a key in
`metrics.values`, so `INDEX.md` and `CURRENT.md` rendered the headline as "not
recorded". It now names `fresh_llm_query` — the query-writing arm's 0.5000 against the
cascade's `fresh_deterministic` 0.9467 on the same 30 questions. No value changed.
