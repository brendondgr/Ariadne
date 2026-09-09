# RESULTS — EXP-2026-07-010 Independent cross-model grading (pre-fix baseline)

> **Status: `superseded` by [`EXP-2026-07-001`](../EXP-2026-07-001-arm-a-deterministic/).**
> These numbers are historically correct and currently obsolete. They are the
> **"Committed baseline" row** of the 2026-07-26 standing table — the "before"
> that the eight defect fixes were measured against. Do not quote them as
> current performance; do not delete them either.

## 1. Headline

Independent correctness **0.8946** — 91 CORRECT / 27 PARTIAL / 2 INCORRECT, with
hallucinations flagged in **11 of 120** answers. The hypothesis held: an
independent judge scored the pipeline materially lower than its own model did.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json).

| Metric | Independent (Sonnet 5) | Self-judged (skynet) |
|---|---|---|
| `correctness` **(primary)** | 0.8946 | — |
| `completeness` | 0.8952 | 0.95 (as evidence sufficiency) |
| `faithfulness` | 0.9558 | 0.9733 |
| `groundedness` | 0.9575 | 0.9342 |

**Verdicts:** 91 CORRECT · 27 PARTIAL · 2 INCORRECT. **Hallucinations:** 11 answers.

Weakest categories: C-ABS 0.17 (n=3), C-CSQ 0.35 (n=2), A-SW 0.45 (n=3),
F-CWE 0.59 (n=5), A-GRP 0.76 (n=4).

## 3. Figures

None.

## 4. Interpretation

Two disagreements with the self-judge, in opposite directions, and both
explicable:

* **Faithfulness lower** (0.956 vs 0.973) — the independent grader caught
  unsupported claims the model missed in its own output. This is the
  self-preference bias the experiment was run to detect.
* **Groundedness higher** (0.958 vs 0.934) — the Sonnet grader was given the
  related-neighbour descriptions that skynet's judge had stripped, so it
  correctly credited grounding the self-judge had penalised.

The weak categories became the work programme. C-ABS at 0.17, C-CSQ at 0.35, and
A-SW at 0.45 are what the eight defect fixes targeted; every one of them reads
1.000 in Arms A and F afterwards.

## 5. Threats to validity

* **Superseded configuration.** This graded the pipeline under the *truncated*
  profile, before eight defects were fixed. Nothing here describes current
  behaviour.
* **Small categories.** C-CSQ has 2 members and A-SCN has 1. A single case moves
  those means by half.
* **Single judge pass, n=1.** No variance recoverable.
* **The catalogue is the same co-authored, non-held-out 120 questions** as every
  other experiment here.

## 6. What surprised us

That the two judges disagreed in *both* directions rather than one. The naive
expectation was that a self-judge simply inflates every score; in fact it
inflated faithfulness and deflated groundedness, the latter purely because of
what its prompt was given to read. Judge input matters as much as judge identity.

## 7. Follow-ups

All four fixes this run motivated shipped in `df700ee` (serializer
properties/facets, an answer-completeness metric, the structured enumeration
claim, and C-ABS role labelling). Remaining, tracked in
[`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Re-run an independent panel against the *current* pipeline for a true
  post-fix faithfulness read. The seven-arm study judged each arm independently,
  but a direct successor to this specific comparison has not been re-run.

## 8. Reproduction

**Not reproducible.** The pipeline configuration it graded no longer exists, and
the judging step ran 120 external Sonnet 5 agents. The artifacts are archived
and hashed in [`data/POINTERS.md`](data/POINTERS.md); treat them as the record.

---

# AMENDMENTS

## AMENDMENT A-1 (2026-09-09) — The per-question verdicts were unpointed; one pointer description was wrong

**What was wrong.** `data/POINTERS.md:9` described
`docs/evaluation/archive/independent-eval.json` (453 bytes) as "Per-question
verdicts". It holds only the aggregate scores. The per-question verdicts this
experiment's every number is computed from are the 120 `*.judgment.json` files
under `docs/evaluation/answers/`, which this record did not point at (they
were hashed only under `EXP-2026-07-009`'s pointer table, where they were in
turn mis-described as that run's judge output).

**What is now correct.** The L9 description is corrected in place, and a row is
added pointing at `docs/evaluation/answers` (1 543 550 bytes, tree hash
`sha256:c0828b08…`, computed 2026-09-09 with
`uv run python -m utils.research_record.hashing`). The B2 audit of 2026-09-09
recomputed correctness 0.8946, completeness 0.8952, faithfulness 0.9558,
groundedness 0.9575, verdicts 91 / 27 / 2 and 11 hallucination answers from
exactly those 120 files; all reproduce.

**Nothing else changes.** `status: superseded` and `superseded_by:
EXP-2026-07-001` stand (the other side of that link is being set in
`EXP-2026-07-001`'s manifest in the same repair pass). Note for readers: the
superseding experiment carries a *lower* ID number — IDs were assigned when the
record was back-filled on 2026-08-06 and do not follow chronology. This
experiment (2026-07-20) precedes the seven-arm study (2026-07-26).
