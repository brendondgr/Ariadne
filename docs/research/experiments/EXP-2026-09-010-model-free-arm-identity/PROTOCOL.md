# PROTOCOL — EXP-2026-09-010 — do the model-free arms actually repeat?

**Written 2026-09-06, before any run.** Pre-registered. Append AMENDMENTS; do not
edit after data exists.

---

## The question

Thirty-six of forty-two experiments in this record are `n_runs: 1`. For the two
arms that carry the paper's primary result — `deterministic` and `generic` — we
have justified that by asserting the arms are model-free on the query path and
therefore deterministic.

**That justification has never been measured.** It is an assumption, and it is
load-bearing: it is the entire reason we feel entitled to run those arms once and
publish the number.

This experiment converts the assumption into a measurement, or kills it.

## Why this rather than three noisy repeats

If the arms are byte-identical across runs, that is a **strictly stronger**
statement than a mean ± SD over three draws. "Zero run-to-run variance, verified
over 284 questions" needs no interval and no further replication. If they are
*not* identical, we have found a source of variance the paper currently assumes
away, and every single-draw figure from these arms needs re-examining.

Either outcome is worth more than the ~3,400 additional judgments that
replicating all arms under both graders would cost.

---

## Design

**Arms.** `deterministic` and `generic`. Not `llm_query` — that arm has a model
in the query path, is expected to vary, and is measured separately by
`EXP-2026-09-009`.

**Population.** The expansion-bank dev half, n=284, sha256
`a4ca6702029cae77…` — the same file and the same population as
`EXP-2026-09-002`, `EXP-2026-09-005` and `EXP-2026-09-009`, so a failure here
bears directly on those recorded figures.

**Procedure.** Run each arm **twice**, fresh, back to back, under identical
configuration and against stores asserted at their pinned counts. Compare the two
captures per question.

**Comparison.** Exact structural equality of the answer artifact, after removing
exactly one key path:

```
logic_flow.results.[].traces.[].detail.timing_ms
```

That path was identified empirically by walking all 100 key paths of a real
artifact and testing for wall-clock-derived names — not guessed. **No other key
is excluded.** If a second volatile key exists, this experiment must discover it
by failing, and the discovery is reported rather than absorbed into the
exclusion list.

**Configuration**, matching the recorded runs: `ORCH_MAX_HOPS=5`, workers 32, no
composer LLM. No grading — this experiment produces no judged number and needs
no grader.

---

## Pre-registered hypotheses

**H1 — `deterministic` is byte-identical.** All 284 answers match across the two
runs, modulo `timing_ms`.
*Falsified by:* one or more differing answers.

**H2 — `generic` is byte-identical.** Same, 284/284.
*Falsified by:* one or more differing answers.

**H3 — any difference is confined to key paths that carry no scored content.**
If H1 or H2 fails, the differing paths do not intersect the fields the scorer
reads (`answer`, retrieved record identifiers, claims).
*Falsified by:* a difference in a scored field.

## What each outcome means, decided now

| Outcome | Consequence |
|---|---|
| H1 and H2 hold | Record `n_runs: 1` as **sufficient by construction** for these arms. The paper states verified zero run-to-run variance and cites this experiment. No further replication of these arms is owed. |
| H1 or H2 fails, H3 holds | Non-scored jitter. Report the paths; the published figures stand; the paper says "identical in every scored field." |
| H3 fails | **The primary result rests on an unmeasured source of variance.** `C-023`'s figures become single draws of a varying process, the paper's limitation 5 widens to cover the main arms, and replication under both graders becomes required rather than optional. |

The third row is the outcome that costs us the most, and it is recorded here,
before the data exists, that we will report it.

---

## Guards

- Both stores asserted at pinned counts before either run (Neo4j 4,369/27,669;
  Gremlin 6,374/8,582). Gremlin was found empty at 0/0 earlier today; a run
  against half a graph would compare two equally wrong captures and call them
  identical.
- An arm writing fewer than 284 answers in either run is recorded `not_run`.
- The two runs of an arm happen back to back, with no reload between them, so
  that a store change cannot be mistaken for arm non-determinism.

## What this does not do

- It does not test the `llm_query` arm.
- It does not test across a store reload, a process restart, or a different
  machine. It tests repeat-run identity under one process lifetime, which is the
  weakest form of the claim and the one actually relied on.
- It says nothing about whether the answers are *correct* — only whether they are
  *the same*.

---

# AMENDMENTS

## A-1 (2026-09-06, after the `deterministic` pair, before `generic` finished)

**A second volatile key exists, and the run found it by failing — as designed.**

`deterministic` came back **2/284 identical** under the pre-registered exclusion
list. The sole differing key path across all 282 non-identical answers is:

```
run_meta.wall_s
```

It is wall-clock seconds for the run (e.g. `3.737` vs `1.720`). The two fields
beside it in the same object, `planner: "gold-replay"` and
`synthesis: "deterministic"`, are identical on every answer, and no other path in
the artifact differs anywhere.

**What this means, stated in the order it should be read:**

1. **H1 as literally worded is falsified.** Identity under the pre-registered
   exclusion list is 0.0070, not 1.0.
2. **H1's intent holds.** After excluding both clock-derived keys, identity is
   **284/284**. No content field varies.
3. **H3 holds.** `run_meta.wall_s` is not a scored field; the scorer never reads
   it.

**The defect is in the method, not in the arm.** The pre-registered exclusion
list was built by walking the key paths of **one** artifact — and an `llm_query`
artifact at that, from a different experiment — and regex-matching names against
`time|elapsed|_ms|stamp|duration|latency|seconds`. `wall_s` matches none of those
patterns, and `run_meta` does not appear in the `llm_query` artifact shape that
was sampled. Two independent mistakes, either of which alone would have caused
the miss.

**The correct method is the one this run performed**: do not predict which keys
are volatile, run twice and observe which ones move. The empirical diff is the
instrument; the name-matching pass should have been used only to *label* what the
diff found, never to decide what to exclude in advance.

**What is deliberately not done.** `run_meta.wall_s` is **not** being added to
`VOLATILE` and the run is **not** being repeated to obtain a clean pass. The
protocol says a second volatile key must be discovered by failing and reported
rather than absorbed, and that is what this amendment is. `RESULTS.md` will
report the raw figure (2/284), the sole differing path, and the content-identity
figure (284/284) together, in that order.

**Consequence for the record, unchanged by the above:** the assumption that lets
`deterministic` run once — that it is deterministic in everything the scorer
reads — is now measured rather than asserted, and it holds.

## A-2 (2026-09-06, after the `generic` pair — the premise was false)

**`generic` is not a model-free arm, and this protocol should never have said it
was.** The run is **invalid for `generic`** and must be repeated. What follows is
why, because the reason is worth more than the run.

### What the numbers said, and what they actually meant

`generic` returned **0/284** identical under the pre-registered exclusions and
**224/284** once both clock keys are removed. The 60 differing answers break down
as `answer.fallback_reason` (60), `answer.narrative` (58), and
`deterministic_scores.coverage.{coverage,found,missing}` (4).

The coverage differences looked like the expensive outcome — retrieval varying
run to run on the arm that carries the paper's primary result. They are not.
**All 4 coverage-differing answers are inside the 60 narrator-failed answers**,
and the differing `fallback_reason` values name the cause directly:

```
LLM narrator unavailable (request failed: HTTPConnectionPool(
    host='localhost', port=4000): Read timed out …)
```

Run B lost the narrator endpoint on 60 of 284 answers. Where the narrator
failed, a fallback text was composed that lists fewer values of a multi-valued
property, and the coverage scorer — which reads the composed answer — scored it
lower. Every difference in this arm is downstream of one external failure.

### The premise failure

The artifacts state the configuration plainly, and disagree with this protocol:

| arm | `run_meta.synthesis` |
|---|---|
| `deterministic` | `deterministic` |
| `generic` | **`llm (claim-grounded)`** |

`utils/evaluation/experiment_untruncated.py` sets `SYNTHESIS_LLM_ENABLED=true`
for `generic`; only the *query path* is model-free. This protocol asserted both
arms were model-free and never checked, when a single artifact would have said
otherwise.

### The consequence, which is larger than this experiment

`scripts/holdout_run.py` drives the same harness with the same arm. **The
holdout's `generic` figure — 0.6546, and the +0.1684 gap that is the paper's
primary result — was produced by answers a language model composed.**

- The paper's claim that **no language model writes a query** is untouched. It
  remains true, and the artifacts show it.
- But `generic` is **not** deterministic by construction, so the justification
  for running it once does **not** transfer from `deterministic` to it. Its
  published figures carry a run-to-run variance that has never been measured.
- The paper's §3 sentence "the shipped default composes deterministically" is
  true of the shipped default and **misleading about the evaluated
  configuration**. It must be corrected.
- Limitation 5 (`n_runs: 1`) must name `generic` explicitly, as the arm carrying
  the primary result.

### Guard defects this exposes

1. **Pre-flight probed the wrong endpoint.** It asserted three aliases on
   `:9090` and never touched `:4000`, which is where `generic` narrates. The
   arm's own dependency was unguarded.
2. **There is no in-run liveness check.** A dependency that dies mid-run
   produces a complete, well-formed, silently degraded capture. Nothing failed
   loudly; `rc` was 0 and 284 answers were written.
3. **`fallback_reason` is the tell and nothing reads it.** A run whose
   `fallback_reason` is non-null on 21% of answers is not a clean run, and the
   harness should refuse to record it as one.

### What happens next

- `deterministic`'s result **stands** — it is genuinely narrator-free
  (`synthesis: deterministic`) and is 284/284 content-identical.
- `generic` is recorded **`not_run`**, not "differs". Reporting an infrastructure
  failure as arm non-determinism would have been a false alarm on the paper's
  primary result, and it was one inspection away from being written down.
- The repeat must (a) probe and pin `:4000` in pre-flight, (b) abort if
  `fallback_reason` is non-null anywhere, and (c) report `generic`'s **real**
  narration variance, which is now a genuine open question rather than an
  assumption.
