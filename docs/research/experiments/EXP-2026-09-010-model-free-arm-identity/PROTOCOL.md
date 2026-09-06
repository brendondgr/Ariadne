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
