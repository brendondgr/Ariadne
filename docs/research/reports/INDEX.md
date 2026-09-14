# Reports

Synthesis reports. Distinct from [`../experiments/`](../experiments/), which
records single runs: a report here reads across many of them and says what they
add up to. Reports are dated snapshots and are never edited in place once they
leave `Draft` — a later report supersedes an earlier one and says so.

The last column is the one that gets used. Someone scanning this file is asking
"has anyone looked at X", and a one-line finding answers that where a title does
not.

| Date | Report | Author | Status | One-line finding |
|---|---|---|---|---|
| 2026-08-20 | [Templates beat LLM-written graph queries two to one](2026-08-20-ariadne-project-briefing/report.pdf) | brendondgr | Draft | Templates win the query-writing comparison ~2:1 on two disjoint sets; the near-ceiling catalogue figure and the templates-hold-the-accuracy claim did not survive blind testing |
| 2026-08-31 | [Overnight run — steps 1–6 of the honest-ambiguity plan](2026-08-31-overnight-run.md) | claude | Final | Three defects fixed and exact-name matching shipped (+3 right for +1 wrong); fuzzy matching held back because a threshold that scored 12-right-0-wrong on the tuning half scored 17-right-8-wrong on the frozen half |
| 2026-09-02 | [Overnight — the expansion bank, judged](2026-09-02-overnight-report.md) ([pdf](2026-09-02-overnight-report.pdf)) | claude | Final | 572 questions covering every shape the sources support; the assembled path beats the hand-written library and the query-writing arm on the 284-question dev half |
| 2026-09-04 | [Overnight — two tracks, two graders](2026-09-04-overnight-report.md) ([pdf](2026-09-04-overnight-report.pdf)) | claude | Final (stub) | Second grader family agrees on the arm ordering; the gemma pass on the query-writing arm did not run before the deadline |
| 2026-09-05 | [What happened, in plain language (3–5 Sept)](2026-09-05-full-report.md) ([pdf](2026-09-05-full-report.pdf)) | claude | Final | The hand-written library was broken six ways; repaired, the assembled path still leads by 0.1623 under one grader and 0.2531 under another |
| 2026-09-06 | [Overnight — which graders can see near the ceiling](2026-09-06-overnight-report.md) ([pdf](2026-09-06-overnight-report.pdf)) | claude | Final | Of three local graders one resolves a 0.03 difference near 1.0; one emits a single value there and one inverts mid/low |
| 2026-09-07 | [Overnight — seeded generic repeats and the paper-number check](2026-09-07-overnight.md) ([pdf](2026-09-07-overnight.pdf); [state](2026-09-07-overnight.state.json), [paper numbers](2026-09-07-paper-numbers.json), [recompute audit](2026-09-07-recompute-audit.json)) | claude | Final | Three further seeds graded; the driver finished early and nothing ran between 04:00 and 09:57 |
| 2026-09-14 | [Retiring the template engine](2026-09-14-retiring-the-template-engine.pdf) ([html source](2026-09-14-retiring-the-template-engine.html)) | claude | Final | On 282 sealed, never-seen questions the open-ended engine scores 0.9005 against the template engine's 0.5525 with no model anywhere in the answer path, and the template engine is 0.01s/answer faster — dominated on every measured dimension; the 2B narrator preserves 284/284 answers' facts exactly but costs ~1,340x, and the caveat is that both 0.90 arms replay an authored plan the system's own planner cannot match (-0.381) |
| 2026-08-26 | [Novelty audit — what this architecture can actually claim](2026-08-26-novelty-audit/novelty-audit-report.pdf) | external agent, brief in [PROMPT.md](2026-08-26-novelty-audit/PROMPT.md) | Final | One claim killed outright by a paper published four weeks earlier, two mechanisms scooped, five narrowed, one clear — and the citation the whole novelty argument rested on does not say what we thought it said |

**The September overnight reports** (2026-09-02 … 09-07) were written by
`scripts/morning_report.py`, `scripts/plain_report.py` and the
`scripts/overnight_2026_09_0*.py` drivers, which read every figure from files
on disk at render time; they moved here from a second, unindexed docs/reports/
directory on 2026-09-09.

**Not every report is built here.** The 2026-08-26 novelty audit is an external
literature audit — no number in it comes from `data/collect.py` and it cites no
experiment of ours. It is filed as a report because it reads across the whole
project and says what the *literature* adds up to. Its
[`POINTERS.md`](2026-08-26-novelty-audit/POINTERS.md) records what was
independently re-verified and what was not.

## Building one

The template and its rules live outside this repository, in the
`research-report` skill. Each report directory carries everything needed to
rebuild it:

```bash
cd docs/research/reports/<date>-<slug>
python3 data/collect.py        # pull every figure out of the experiments
python3 figures/make_figures.py
python3 tables/make_tables.py
latexmk -pdf report.tex
```

`data/collect.py` is the provenance boundary. No number is typed into a section,
a figure, or a table — everything is read from the experiments' own
`data/metrics.json` files, and a missing key raises rather than defaulting.
