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
