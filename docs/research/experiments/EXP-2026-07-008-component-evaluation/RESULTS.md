# RESULTS — EXP-2026-07-008 Component-level evaluation

## 1. Headline

Source recall **1.0** and schema adherence **1.0** on the planner corpus; query
validity, execution accuracy, and safety adherence all **1.0** on both
specialists, with a **100% block rate** across 17 adversarial probes. No
hypothesis was registered; this is an instrumentation report.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json).

### Planner (deterministic drafter, 43 cases)

| Metric | Overall | Dev | Holdout |
|---|---|---|---|
| Source precision | 0.919 | 0.906 | 0.955 |
| Source recall **(primary)** | 1.000 | 1.000 | 1.000 |
| Unnecessary source calls | 7 | 6 | 1 |
| Sub-question quality | 0.839 | 0.828 | 0.870 |
| — routing accuracy | 0.837 | 0.812 | 0.909 |
| — dependency accuracy | 0.837 | 0.812 | 0.909 |
| Schema adherence | 1.000 | 1.000 | 1.000 |
| Honesty (unsupported/partial) | 1.000 | 1.000 | 1.000 |

### Specialists

| Metric | attack | capec |
|---|---|---|
| Query validity, first-pass | 1.000 (44/44) | 1.000 (34/34) |
| Execution accuracy, exact-set-match | 1.000 (46/46) | 1.000 (34/34) |
| Precision / recall / F1 | 1.0 / 1.0 / 1.0 | 1.0 / 1.0 / 1.0 |
| Safety adherence (audited, breaches) | 1.0 (44, 0) | 1.0 (34, 0) |
| Adversarial block rate (probes, leaks) | 1.0 (10, 0) | 1.0 (7, 0) |
| Latency p50 / p95 / p99 (ms) | 1.099 / 2.032 / 4.425 | 2.617 / 4.210 / 6.891 |

`n = 1` throughout: the scoring is deterministic, so a repeat run reproduces
these numbers exactly rather than sampling a distribution.

## 3. Figures

None. Every number here is a contract check that reads better as a table.

## 4. Interpretation

The component contracts hold. The two numbers that carry real information are
the ones **below** 1.0:

* **Source precision 0.919** — the planner over-routes. Seven unnecessary source
  calls, concentrated in mitigation and mapping questions that get sent to both
  sources when one would do. Costs latency, not correctness.
* **Sub-question quality 0.839** — routing and dependency accuracy move together
  at 0.837, and both are notably better on holdout (0.909) than dev (0.812).

## 5. Threats to validity

* **The 1.0s are ceilings by construction, not achievements.** The specialists
  do not free-generate queries — a deterministic builder fills read-only
  templates — so query validity *cannot* be below 1.0 short of a builder bug.
  Reporting it as a result would overclaim. The repository's own report says so
  explicitly, and that framing is preserved here.
* **The planner corpus is filtered on the planner's own success.** Bare id
  lookups (`what is T1059.001?`) were excluded as unroutable. Two of the
  reported metrics are therefore 1.0 partly by construction. This is the most
  serious limitation of this experiment and it is unresolved.
* **Execution accuracy is against a snapshot, not ground truth.** It measures
  agreement with the pinned export, so an ingest error present in both would not
  be caught.
* **Latency is warm steady-state on one machine.** Not a benchmark.

## 6. What surprised us

That holdout beat dev on every planner metric that moves. With 43 cases split
across two partitions this is well within noise, but it is the opposite of the
usual direction and worth not over-reading.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Add a lookup intent so bare id questions become routable, then re-score
  without excluding them. Until that happens, source recall 1.0 is partly an
  artifact of what the corpus omits.
* Tighten routing to recover the 7 unnecessary source calls.

## 8. Reproduction

```bash
uv run main.py --docker start
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run main.py --component-eval
```

Fully deterministic: this regenerates
[`docs/evaluation/component-evaluation.md`](../../../evaluation/component-evaluation.md)
and its JSON byte-for-byte, modulo latency figures.

---

## AMENDMENT A-1 (2026-09-09) — Run date corrected to 2026-07-07; provenance recorded; the safety half was re-evidenced by EXP-2026-08-016

Written during the 2026-09-09 record audit (batch b1). Every number in §2 and in `data/metrics.json` reproduces from the 43 per-case planner rows and the per-case specialist lists in `docs/evaluation/component-evaluation.json` (source precision 0.919 / 0.906 / 0.955; recall 1.0; sub-question quality 0.839 / 0.828 / 0.870; unnecessary calls 7 / 6 / 1; 32 dev / 11 holdout; EX 46/46 and 34/34; latency and probe counts as tabled). Nothing in the results tables changes.

**What was wrong, and what is now correct.**

* **Dates** (manifest.yaml:6–7): `date_started` / `date_completed: 2026-07-26` → **2026-07-07**. Established from `git log -- docs/evaluation/component-evaluation.json docs/evaluation/component-evaluation.md`: both files were created in **`61657a9`** (2026-07-07 01:00 −0400, *"feat(evaluation): unified component-evaluation report + --component-eval CLI"*), carried through the merge `e9f92cf` (01:28 −0400), and have **never been modified since** (file mtimes 2026-07-07 01:28). The JSON has no timestamp field (`meta.generated_note` only), so the commit is the only date evidence; it is 19 days earlier than recorded. The 2026-07-26 date was inherited from the seven-arm study when the folder was back-filled on 2026-08-06. INDEX.md:20 repeats the old date and is regenerated by the index build.
* **`code.commit`** (manifest.yaml:22): `unknown` → `61657a9f73b317edd6c659f3cd81ac079e9f7bf8`, the commit that generated both pointed-at files. Because the report is a deterministic regeneration, this is the code that produced the numbers, not merely an upper bound — modulo the caveat that the run commit was not written into the report.
* **`data.n_examples: 43`** counts the planner corpus only. The 46 ATT&CK and 34 CAPEC specialist cases and the 17 adversarial probes (10 + 7) scored in §2 are described in PROTOCOL and RESULTS but not in the manifest's `data` block; a manifest comment now says so. `wall_clock_hours: null` stays: the report records latency percentiles, not the run's wall clock.
* **Refinement — the safety half has been re-evidenced at scale.** §1's *"100% block rate across 17 adversarial probes"* stands as the 2026-07-07 measurement. **EXP-2026-08-016** (2026-08-23) generated **240 probes** by crossing rejection categories with syntactic mutations; the gate as of that date failed **15** of them (`mergeV`/`mergeE`, a Groovy closure, un-depth-checked `repeat`, a literal 4-hop chain, `USE`, backtick/multi-label smuggling), all since closed, after which 240/240 blocked with 0 leaks (`CLAIMS.md` C-008). Quote 240 and the 15 beside it; 17/17 is the small-suite figure this folder measured. `related` gains `EXP-2026-08-016`. No status change: this experiment's planner and execution halves are not replaced.
* **ISSUES 2026-08-06's "re-run before publication" has not happened.** The pointed-at files are unchanged since 2026-07-07, so no re-run under the current protocol has landed. Recorded in ISSUES 2026-09-09.
* **Pointers re-verified.** Both rows of `data/POINTERS.md` were re-hashed on 2026-09-09 with `uv run python -m utils.research_record.hashing`: `component-evaluation.json` → `sha256:d1d7407a…` (92927 bytes) and `component-evaluation.md` → `sha256:f23eb6dc…` (3373 bytes), both unchanged.
* **Figures.** `figures: []` is left as recorded; CLAIMS C-007/C-008 cite `tab-component`, a table, not a figure in this folder.
