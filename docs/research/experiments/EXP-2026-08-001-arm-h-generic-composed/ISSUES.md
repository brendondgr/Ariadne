# ISSUES — EXP-2026-08-001

## 2026-08-09 — Not a clean pre-registration

**Impact:** `PROTOCOL.md` was written while the full run was in flight, and its
quantitative predictions rest on spot checks over 30 of the 120 questions that
had already been run (committed in `925f2a3` and `b6c4f12`). The direction of
the effect was therefore known before the protocol was written.

**Cause:** The fixes were developed question-by-question against live smoke runs,
which is the right way to develop them and the wrong way to pre-register them.

**Resolution:** Not resolvable for this run. The predictions are still
falsifiable on the other 90 questions and on the regression count, which is the
part no spot check established. Reported as a limitation rather than presented
as a pre-registered result.

## 2026-08-09 — Retrieval only; no judged correctness

**Impact:** This experiment reports **no correctness number**. Judged
correctness requires 120 independent Sonnet 5 agents via the Workflow tool — an
operator-authorised, billed step that was not run.

**Cause:** Deliberate scope. The change under test is a retrieval change, and
gold-in-evidence measures it directly and deterministically.

**Paper implication:** Arm H may **not** be placed on the arm-comparison figure
or in any correctness table until it is judged under the same protocol as Arms
A–G. Quoting `gold_in_evidence` beside another arm's `correctness` would be a
category error. `metrics.primary` is `gold_in_evidence`, not `correctness`, and
must stay that way until a judge run exists.

## 2026-08-09 — Two primitives deliberately over-return

**Impact:** Two of the new primitives answer more broadly than the gold expects,
which will cost precision under a judge even though recall is complete.

| Case | Behaviour | Gold |
|---|---|---|
| `A-MC-*` | `generic_intersect` returns techniques *and* sub-techniques adjacent to both anchors — 29 records for A-MC-01. | `max_records: 7` (top-level only) |
| `C-ABS-*` | A self-referential edge is walked in **both** declared directions, so descendants come back alongside ancestors. | ancestors only |

**Cause:** In both cases the schema does not carry the distinction. Nothing in
the registry says a `SubTechnique` is not wanted when a question says
"techniques", and nothing says which direction of `ChildOf` means "up". That
distinction is exactly what a hand-written template encodes.

**Resolution:** Left as-is, deliberately. Filtering either one to match the gold
would be tuning a generic primitive against a catalogue co-authored with the
templates it is being compared to — the co-authoring threat this study already
names as its largest. Recall-complete and over-broad is the honest generic
answer; it is recorded here so a reader is not surprised by the precision cost.

**Follow-up:** This is a real, reportable finding in its own right — it bounds
what a schema-driven layer can do without domain knowledge, and it is the
sharpest evidence in the study for what the templates actually buy.

## 2026-08-09 — The bridge reuses shared normalization

**Impact:** `_generic_bridge` emits the row shapes the existing `maps_to` and
`cwe_chain` normalizers already handle, and those paths contain MITRE-specific
id handling (`taxonomy_name == "ATTACK"`, the `T` prefix).

**Cause:** The ablation's variable is `SPECIALIST_GENERIC_ONLY`, which disables
**query templates** — question shapes. The normalizer was never part of it: Arm G
used `_normalize_describe` and `_normalize_neighbors` freely.

**Resolution:** Consistent with the ablation as defined, but recorded because
"no MITRE literal enters the *builder*" is the precise claim, and it is narrower
than "no MITRE knowledge anywhere in the path". A reader comparing this against
a true zero-knowledge baseline needs to know that.

## 2026-08-09 — Changes live under a frozen path

**Impact:** All builder changes are under `utils/specialists/`, which
`freeze/holdout-v1` declares immutable until the blind holdout reports (still
open — see `OPEN_QUESTIONS.md`).

**Resolution:** Every change is confined to code reachable only when
`SPECIALIST_GENERIC_ONLY` is set. This is enforced by
`utils/specialists/tests/test_generic_only_isolation.py`, which replays ten task
shapes covering every branch of the default cascade and asserts the emitted
template, query string and params are **byte-identical** to the tag's output.
The expected values were captured from `git archive freeze/holdout-v1`, not
regenerated from the working tree. A companion test asserts the flag still
changes routing, so the suite cannot pass by the flag becoming a no-op.

Arms A–F and the holdout tree are therefore unaffected. `git diff
freeze/holdout-v1 -- utils/specialists/` is non-empty and that is expected; the
test, not the diff, is the operative check.

## 2026-08-09 — Single run, no seeds, one model

**Impact:** `n_runs: 1`, seeds unrecorded, one served model (`skynet` = Gemma 4
31B, quantisation and context window unrecorded). Same limitation as every arm
of the 2026-07-26 study.

**Note:** `gold_in_evidence` is deterministic *given the plan*, but the plan
comes from an LLM planner, so the metric is not fully deterministic across runs.
It is far more stable than a judged score, and much less so than a metric on a
replayed gold plan. Treat single-run deltas of a few gold ids as noise; the
deltas this experiment reports are an order of magnitude larger.
