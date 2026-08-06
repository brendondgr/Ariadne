# Research Decisions

ADR-style, dated, **append-only**. One entry per research decision: metric
choices, baseline selection, dataset exclusions, scope cuts, framing.

Reviewers ask "why did you use X?". This is where the honest answer already
lives, written at the time rather than reconstructed under pressure.

Add entries with [`templates/DECISION.md`](templates/DECISION.md). Never edit an
existing entry — supersede it with a new one that names the entry it replaces.

---

## D-001 — Primary metric is judge-scored correctness, not the four `goals.md` metrics

**Date:** 2026-07-26
**Context:** The project's stated end-to-end metrics — cross-source answer
accuracy, mapping recall, provenance correctness, analyst inspectability — all
read 1.0 while an independent panel scored the same answers at 0.8946
correctness with hallucinations in 11 of 120.
**Options:** (a) keep the four `goals.md` metrics as primary, since they are
deterministic and reproducible; (b) adopt judge-scored correctness as primary and
demote the four to secondary; (c) report both as co-primary.
**Decision:** (b). Judge-scored correctness is primary; the four `goals.md`
metrics are reported as secondary and explicitly labelled as what they are.
**Consequences:** The primary metric is now non-reproducible — it depends on an
LLM judge whose verdicts are not stable across runs. That cost is accepted
because three of the four alternatives are self-consistency checks that a
confidently wrong pipeline passes. Every reported correctness figure must name
its judge run. See C-009.

## D-002 — Evaluation is cross-model by construction

**Date:** 2026-07-26
**Context:** The first end-to-end evaluation had `skynet` grading answers
`skynet` wrote. Independent grading found faithfulness 0.956 against a
self-reported 0.973 — the self-preference bias the concern predicted.
**Options:** (a) keep self-judging, it is cheap and local; (b) grade with a
different model; (c) human annotation.
**Decision:** (b). One independent Sonnet 5 agent per answer, given the gold
assertions *and* the full retrieved evidence. 840 agents across the seven study
runs, plus 120 for the Arm G control.
**Consequences:** Expensive, and it introduces a dependency on a commercial model
in the evaluation path. It also means self-judged numbers already in the
repository cannot be compared with post-decision numbers. (c) remains
unaddressed — there is still no human-versus-judge agreement statistic, which a
reviewer will ask for. Tracked as Q6.

## D-003 — Both inter-arm deltas are reported treated-minus-reference

**Date:** 2026-08-04
**Context:** The study reports two effects — disabling templates, and swapping in
LLM planning — and they were being quoted with inconsistent signs and, in one
plan document, with the letters reversed ("F − G delta (−0.357)"; F − G is
*positive*).
**Options:** (a) report each delta in whatever direction reads naturally;
(b) fix a single convention.
**Decision:** (b). Treated minus reference, always, so both effects are negative
and directly comparable: templates **G − F = −0.3568**, planning
**B − C = −0.1185**.
**Consequences:** Some prose elsewhere in the repository still carries the old
labels and is now wrong on its face. Those documents are dated records and are
not edited in place; this entry is the correction of record.

## D-004 — Arm G is a generic-primitives control, not a free-form-generation baseline

**Date:** 2026-07-26
**Context:** Arm G disables every hand-written intent template, leaving only
schema-driven primitives. It is tempting to describe this as "the LLM writes the
queries instead", which would make it the baseline the paper's headline claim
needs.
**Options:** (a) describe Arm G as a text-to-query baseline; (b) describe it
precisely as a generic-primitives control and state that the free-form baseline
does not exist.
**Decision:** (b). **No LLM writes Cypher or Gremlin in any arm of this study.**
**Consequences:** The paper's intended headline claim (C-012) has *no* supporting
experiment, and the ledger says so. This is the single most consequential honesty
decision in the record: (a) would have made the paper look finished and would not
have survived a reviewer reading the harness.

## D-005 — No baseline system was implemented, and this is recorded rather than worked around

**Date:** 2026-08-03
**Context:** Not one alternative system has ever been implemented or run. Every
comparison in the record is Ariadne against Ariadne.
**Options:** (a) frame inter-arm contrasts as though they were baselines;
(b) build a baseline before publishing anything; (c) record the absence
explicitly and treat the two missing baselines as named backlog items.
**Decision:** (c) now, (b) before any archival submission. The two required
baselines are the free-form text-to-Cypher/Gremlin system (C-012) and the
merged-single-graph system (C-015).
**Consequences:** `baselines_compared` is empty in all eleven back-filled
manifests, and it is empty *truthfully*. No result in this repository may be
described as beating anything external.

## D-006 — The 120-question catalogue ships each question's `expected_template`

**Date:** 2026-07-26 (recorded 2026-08-06)
**Context:** Questions were authored alongside the templates that answer them,
and each carries the template it expects.
**Options:** (a) author questions independently of the templates; (b) accept the
coupling to get a computable gold set quickly.
**Decision:** (b), taken for build speed.
**Consequences:** Severe, and the reason C-001 is `partial` rather than
`supported`. The catalogue cannot distinguish capability from coverage, and no
number derived from it is a defensible headline until a blind holdout reports.
This decision is the direct cause of open question Q1.

## D-007 — Raw run artifacts stay in `docs/evaluation/`; the record stores pointers plus hashes

**Date:** 2026-08-06
**Context:** The seven-arm study's artifacts are 62 MB across 2,894 JSON files,
with single answer files up to 2.6 MB. The research record must stay cloneable in
seconds and reject anything above ~10 MB.
**Options:** (a) copy artifacts into each experiment folder; (b) adopt DVC or Git
LFS; (c) leave them in place and reference them by relative path plus SHA-256.
**Decision:** (c). Each experiment's `data/POINTERS.md` carries a directory hash
that folds every file's relative path and content digest in sorted order, so a
rename counts as a change.
**Consequences:** The record depends on `docs/evaluation/` not being reorganised;
if it moves, every pointer breaks at once — which the validator will catch, but
only after the fact. (b) was rejected because adopting a new artifact-tracking
tool is an explicit non-goal of this retrofit.

## D-008 — The append-only rule binds completed experiments, not the ledgers

**Date:** 2026-08-06
**Context:** `docs/skills/global-project-rules/SKILL.md` rule 4 forbade editing
anything under `docs/research/` in place. The research record needs `INDEX.md`
regenerated on every commit and four ledgers that are living documents, so the
rule as written deadlocked the design.
**Options:** (a) keep the blanket ban and put the ledgers elsewhere, breaking the
one-canonical-location principle; (b) narrow the rule.
**Decision:** (b). Append-only binds **completed experiment folders** and
`audit-2026-08-03.md`. It does not bind `CLAIMS.md`, `DECISIONS.md`,
`OPEN_QUESTIONS.md`, `RELATED_WORK.md`, generated files, or an in-progress
experiment.
**Consequences:** The rule is now conditional rather than absolute, which is
weaker protection. Enforcement moves to the validator and CI rather than to a
flat prohibition an agent can read in one line.

## D-009 — Back-filled provenance is recorded as `unknown`, never reconstructed

**Date:** 2026-08-06
**Context:** Eleven experiments were back-filled from runs that predate the
record. Per-arm commits, seeds, and lockfiles were never captured.
**Options:** (a) infer plausible values from git history around the run dates;
(b) omit the fields; (c) record `unknown` / empty and explain in `ISSUES.md`.
**Decision:** (c). The manifest schema is deliberately strict about *absent*
fields and permissive about *unknown* values, so this is expressible rather than
a workaround.
**Consequences:** Eleven manifests carry `code.commit: unknown` and empty
`seeds`. That is visibly incomplete, which is the point — a back-filled
experiment with three known fields is more useful than one with ten invented
ones, and a reader can see at a glance which results are re-runnable.

## D-010 — Every arm is `n_runs: 1`, and no delta carries a significance test

**Date:** 2026-08-06
**Context:** Each arm ran once. Seeds were never recorded. The study reports
point estimates.
**Options:** (a) report the deltas with a test computed from per-question
variation; (b) re-run the arms with seeds before recording anything;
(c) record `n_runs: 1`, `std: null`, `statistical_test: null` and treat the
re-run as backlog.
**Decision:** (c). `std` is null rather than 0.0 throughout, to keep "measured as
zero variance" distinct from "one run, variance unknown".
**Consequences:** No inter-arm delta in this study can be given a p-value as
recorded — including the two headline deltas. Re-running seven arms with seeds
is roughly an hour of wall clock plus 840 judge agents, and is a decision for the
operator rather than something to trigger during a retrofit. Tracked as Q2.
