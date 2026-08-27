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
| 2026-08-26 | [Novelty audit — what this architecture can actually claim](2026-08-26-novelty-audit/novelty-audit-report.pdf) | external agent, brief in [PROMPT.md](2026-08-26-novelty-audit/PROMPT.md) | Final | One claim killed outright by a paper published four weeks earlier, two mechanisms scooped, five narrowed, one clear — and the citation the whole novelty argument rested on does not say what we thought it said |

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
