# Research Record

Everything in Ariadne that will ever appear in a paper lives here: experiments,
results, claims, decisions, figures, and the open questions. A finding recorded
anywhere else — a commit message, a chat log, a notebook cell, an issue comment —
**does not exist**.

The unit of record is the **experiment**, not the file. An experiment is a
directory with a fixed contract, identified by a permanent ID of the form
`EXP-YYYY-MM-NNN-<slug>`. That ID is the only handle used in code, figures,
commit messages, and paper drafts. Every number in the paper traces back to one.

The contract every agent and human must follow is
[`AGENT_INSTRUCTIONS.md`](AGENT_INSTRUCTIONS.md). Read it before running
anything.

## What is where

| Path | What it holds |
|---|---|
| [`CURRENT.md`](CURRENT.md) | **Read first.** Auto-generated: every withdrawn figure with its replacement, every superseded experiment with its successor, one current headline per experiment. `make index` regenerates it; the validator fails on a stale copy. |
| [`INDEX.md`](INDEX.md) | Auto-generated table of every experiment. **Never hand-edit** — `make index` regenerates it and the validator fails on a stale copy. |
| [`CLAIMS.md`](CLAIMS.md) | The paper's spine: one short row per claim — current figure, evidence, status. The highest-value file in this directory. |
| [`CLAIMS-HISTORY.md`](CLAIMS-HISTORY.md) | Every earlier version of every claim row, verbatim, append-only. How each claim got to where it is. |
| [`DECISIONS.md`](DECISIONS.md) | Dated, append-only ADR log. Why recall@10 and not MRR, why this baseline, why that exclusion. |
| [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) | Unresolved threads, known weaknesses, reviewer bait. Becomes future work. |
| [`OPEN_QUESTIONS-ANSWERED.md`](OPEN_QUESTIONS-ANSWERED.md) | Questions that have been answered, moved here verbatim with the date and the experiment or decision that answered them. |
| [`RELATED_WORK.md`](RELATED_WORK.md) | Running bibliography with a how-it-differs line each, plus the scoop watch. |
| [`experiments/`](experiments/) | One directory per experiment. Append-only once complete. |
| [`figures/`](figures/) | Publication-ready figures **only**, promoted from experiments, with their generators in `figures/sources/`. |
| [`tables/`](tables/) | Publication-ready generated tables (`.md` / `.tex`). |
| [`datasets/`](datasets/) | Provenance, licence, and version for every dataset, one card each. |
| [`paper/`](paper/) | Outline, venue targets and deadlines, artifact appendix, venue checklists. |
| [`templates/`](templates/) | Copied wholesale by the scaffolder. Do not fill these in place. |
| [`history/`](history/) | Dated records of one-time work (the August retrofit's migration sections). Never edited. |
| [`audit-2026-08-03.md`](audit-2026-08-03.md) | External research audit, 3 August 2026. A dated snapshot — never updated in place. |
| [`audit-2026-08-31.md`](audit-2026-08-31.md) | External research audit, 31 August 2026. Re-audits the same repository and states, for every 3 August finding, whether it still holds. Also a dated snapshot. |

## Adding an experiment

```bash
make new-experiment SLUG=my-experiment
```

This allocates the next ID, copies `templates/experiment/`, and pre-fills the
date, git commit, branch, and dirty-tree status. Then:

1. Fill **`PROTOCOL.md` before running anything.** A protocol written after the
   numbers are in is not a protocol.
2. Run via the recorded entrypoint so the manifest captures provenance.
3. Fill `RESULTS.md`, regenerate figures, and run `make validate-research`.
4. Commit the experiment folder in the same commit as any code change it
   depends on.

```bash
make validate-research   # schema, linkage, figure, pointer, hash and link checks
make index               # regenerate INDEX.md and CURRENT.md
make check-docs          # no prose document quotes a withdrawn or superseded figure
make check-record        # all of the above plus the tests — what the pre-commit hook enforces
make figures             # regenerate every promoted figure
```

## The rules that are not negotiable

- **Failures stay.** A failed or abandoned experiment is set to `status: failed`
  or `superseded`, gets a `RESULTS.md` saying what broke, and is never deleted.
  Use [`templates/negative_result.md`](templates/negative_result.md).
- **Completed experiments are append-only.** Corrections go in a new experiment
  or an appended `AMENDMENTS` section — never a silent edit. A manifest value
  that an amendment retracts moves to `metrics.withdrawn` with the figure that
  replaces it; it is never deleted. An experiment whose headline a later one
  replaces gets `superseded_by`, and the successor gets `supersedes` — both, or
  neither.
- **Quote from `CURRENT.md`.** Prose anywhere in the repository that quotes a
  withdrawn or superseded figure as current fails `make check-docs`, which the
  pre-commit hook runs.
- **Figures are generated.** Every figure has a script beside it that rebuilds it
  from `data/metrics.json`. No hardcoded numbers in a plotting script, ever.
- **Nothing large lives here.** Raw run output stays in `docs/evaluation/` or
  outside the repository; the experiment records a path plus a hash in
  `data/POINTERS.md`. This directory must stay cloneable in seconds.
- **Do not fabricate manifest fields.** A back-filled experiment with three
  known fields is more useful than one with ten invented ones. Unknown is a
  valid value; a guess is not.
