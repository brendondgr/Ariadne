# PROTOCOL — EXP-2026-08-002 Blind holdout v1

> **Pre-registered.** Unlike EXP-2026-07-001…011, this protocol was fixed
> *before* the run, in `docs/plans/robustness/02-holdout-question-generation.md`
> (2026-08-05), the execution brief `04-holdout-execution-brief.md`, and the
> implementation plan `05-holdout-execution-plan.md` (2026-08-09). The anchor
> draw was committed to git before a single question existed. This file restates
> those documents; where it differs from them, they win.

## Question

The 120-question golden catalogue was written by the same person, at the same
time, as the query templates that answer it. Its 0.9972 correctness figure
(Arm A) is therefore ambiguous: it could mean the system works, or it could mean
the questions were shaped — consciously or not — by knowing what the system
handles.

**Does the deterministic pipeline's near-ceiling correctness survive on
questions written by an author who could not see the template inventory?**

This is claim **C-013**, which gates **C-001** and, through it, the interpretive
value of every other arm figure.

## Hypothesis

Stated before the run, and deliberately directional rather than exploratory,
because the whole point is that a null result here is informative:

> Blind correctness will be **materially lower** than the development-set
> figure. The interesting quantity is the size of the drop and whether it is
> uniform across categories or concentrated in the categories whose original
> anchors were richest.

No threshold is set here. The decision rule lives in the gate and may not be
renegotiated after seeing the result.

## Setup

Three roles, strictly separated; one agent may not hold two.

| Role | Held by | Context |
|---|---|---|
| Sampler | `utils/specialists/evalset/holdout_protocol.py` | Everything. It is a script. |
| Author | A fresh **Claude Fable 5** subagent at **high reasoning effort**, one spawn per anchor | Anchor id, entity type, catalogue name, one category description, the reference-discipline rule. Nothing else. |
| Compiler | The orchestrator session | Everything, but it never writes question text. |

The Author's restriction is enforced by **prompt construction**, not by
instruction: the prompt contains no repository path, no file name, no template
identifier, no example question, and no second entity.
`test_holdout_protocol.py` asserts that, so it is a checked property.

**Frozen tree.** Both arms ran from a detached worktree at
`freeze/holdout-v1` (`974e85a`), where `git describe --exact-match` reports the
tag. The only files added to that checkout were the holdout bank and the
`--bank`-capable runner; `utils/specialists/` was untouched.

## Data

30 questions, `docs/research/datasets/cards/blind-holdout-30.md`.

Anchors drawn by seed **20260805** (module constant, never to change) from the
live id space of the pinned snapshot — 697 ATT&CK techniques and sub-techniques,
558 CAPEC patterns, 336 bridged CWEs — stratified 12 / 8 / 10 to match the
existing bank's 46/34/40 source proportions, and sampled **uniformly within
stratum**: no weighting by degree, mapping count, fame, or category.

The federated stratum is **over-drawn and partitioned**, never filtered, because
68% of CAPEC patterns carry no ATT&CK mapping and for those the correct system
behaviour is an abstention carrying the executed query:

| Partition | n | Scored on |
|---|---|---|
| Answerable — anchor has ≥1 live ATT&CK mapping | 6 | Answer correctness |
| Abstention-expected — anchor has none | 4 | Abstention behaviour: did it abstain, did the abstention carry the executed query, did it avoid fabricating a mapping |

Gold is **computed, never authored**, by the existing
`utils/specialists/evalset/gold_bank.py`, which parses the raw STIX bundle and
CAPEC XML directly rather than reading the loaded graph — so the answer key
stays independent of both the ingest and the specialists.

**Offline rule.** Neither the Author nor the Compiler had network access. Both
snapshot SHA256s were verified against `data/versions.json` before anything ran.
A question written against live MITRE content would reference a version the
graph was not built from, and the resulting failure would look like a system
failure.

## Metrics

| Metric | What it computes |
|---|---|
| `correctness` | Mean judge correctness. The primary metric. Reported with a **Wilson score interval**, because at n=30 a bare point estimate overclaims. |
| `completeness` | Fraction of gold-required entities the answer surfaces. |
| `faithfulness` | Whether each stated claim follows from the retrieved evidence. |
| `groundedness` | Whether each claim carries a citation to a retrieved record. |
| `fabricated_mapping` | Abstention stratum only: did the answer invent a correlation. The failure that matters most. |

`expected_template` is present on every entry but is **derived** by the Compiler
from the anchor's type and category — the Author could not supply it.
`expected_template_is_derived: true` records this. **Template-routing accuracy
may not be reported from this holdout.**

Grading is by one independent **Sonnet 5** agent per case per arm, cross-model on
purpose, against gold *and* the full retrieved evidence.

## Baselines

The development-set figures for the same two arms, recomputed from the committed
judgment files rather than quoted from prose (EXP-2026-07-001 Arm A, 0.9972;
EXP-2026-07-006 Arm F, 0.9957). Arms A and F only — the brief restricts the
holdout to those two.

## Procedure

```bash
# 0. Preconditions
python3 - <<'PY'   # both snapshot SHA256s against data/versions.json
PY
git -C <freeze-worktree> describe --exact-match       # must print freeze/holdout-v1

# 1. Draw, and commit before authoring
uv run python -m utils.specialists.evalset.holdout_protocol

# 2. Author — 30 fresh Fable 5 high-effort subagents, one per anchor
#    scratchpad/author_holdout.mjs via the Workflow tool

# 3. Compile gold and the bank (holdout_protocol.compile_bank)

# 4. Run both arms from the detached freeze checkout
uv run python -m utils.evaluation.experiment_untruncated \
  --arm deterministic  --bank utils/specialists/tests/golden/holdout_questions.json \
  --root docs/evaluation/experiments/holdout-v1 --workers 4
uv run python -m utils.evaluation.experiment_untruncated \
  --arm gold_loop_llm --bank utils/specialists/tests/golden/holdout_questions.json \
  --root docs/evaluation/experiments/holdout-v1 --workers 4

# 5. Judge — 30 independent Sonnet agents per arm
#    scratchpad/judge_holdout.mjs via the Workflow tool
```

**Between compile and write-up, nothing changes.** No template edit, no planner
edit, no prompt edit, no re-draw. A crash is a deviation to be logged and
re-run; a wrong answer is a result, not a bug. A template tweaked because a
holdout question failed would convert this into a second development set, and
the output would still look like a number — which is what makes it dangerous.

## What would falsify this

If blind correctness landed at the development-set figure with no drop at all,
that would be evidence the catalogue was *not* co-authored in any way that
mattered — and it would also be suspicious enough to warrant checking the blind
for a leak before believing it. If it collapsed, C-001 would have to be
withdrawn and the study reframed around the coverage regime rather than the
accuracy figure.

## Known limitation, stated in advance

An LLM-authored holdout controls **co-authorship bias** — the author had no
knowledge of the template inventory — but does not control for the question
distribution being a model's idea of what an analyst asks. A human-authored set
remains the stronger test; a further 15–20 questions would be a cheap secondary
check.
