# Component-Level Evaluation

ATT&CK 19.0 · CAPEC 3.9 · full report (live EX + latency)

Deterministic scoring against snapshot-derived gold — no LLM judge. The model drafts, deterministic code grades; every number here is reproducible.

> **Read the ceiling honestly.** Ariadne's specialists do not free-generate queries — a deterministic builder fills read-only templates — so query validity sits at the ceiling by construction and EX misses point at routing/seed/ingest issues, not malformed queries. That is a design strength, stated plainly.

## Planner

Drafter scored: **deterministic** (deterministic, reproducible).

| Metric | Overall | Dev | Holdout |
|---|---|---|---|
| Source precision | 0.887 | 0.87 | 0.938 |
| Source recall | 1.0 | 1.0 | 1.0 |
| Unnecessary source calls | 7 | 6 | 1 |
| Sub-question quality | 0.835 | 0.812 | 0.904 |
| — routing accuracy | 0.774 | 0.739 | 0.875 |
| — dependency accuracy | 0.774 | 0.739 | 0.875 |
| Schema adherence | 1.0 | 1.0 | 1.0 |
| Honesty (unsupported/partial) | 1.0 | 1.0 | 1.0 |

Corpus: 31 cases (curated 7, generated 24). Curated-anchor pass rate 1.0.

## Specialists

### attack

**Query validity (VA)** — share of drafted queries clearing the gate:

- first-pass: 1.000 [0.89–1.00] (k=30/30)
- post-retry: 1.000 [0.89–1.00] (k=30/30)
- boundary (no query drafted): 2

**Execution accuracy (EX)** — result set vs snapshot gold:

- exact-set-match: 1.000 [0.89–1.00] (k=32/32)
- precision / recall / F1: 1.0 / 1.0 / 1.0
- error taxonomy: none

**Safety adherence** — bounded-execution audit + adversarial probes:

- accepted-query adherence: 1.0 (30 audited, breaches 0)
- adversarial probe block rate: 1.0 (10 probes, leaks 0)

**Latency** — p50/p95/p99 (ms), warm steady-state:

- total: p50 1.046 · p95 1.746 · p99 4.761 · gap 3.715
- by stage (p50): gate 0.04, execute 0.9, assess 0.002, normalize 0.015
- cold p50 1.179 vs warm p50 1.046

### capec

**Query validity (VA)** — share of drafted queries clearing the gate:

- first-pass: 1.000 [0.85–1.00] (k=21/21)
- post-retry: 1.000 [0.85–1.00] (k=21/21)
- boundary (no query drafted): 0

**Execution accuracy (EX)** — result set vs snapshot gold:

- exact-set-match: 1.000 [0.85–1.00] (k=21/21)
- precision / recall / F1: 1.0 / 1.0 / 1.0
- error taxonomy: none

**Safety adherence** — bounded-execution audit + adversarial probes:

- accepted-query adherence: 1.0 (21 audited, breaches 0)
- adversarial probe block rate: 1.0 (7 probes, leaks 0)

**Latency** — p50/p95/p99 (ms), warm steady-state:

- total: p50 2.468 · p95 5.395 · p99 6.77 · gap 4.302
- by stage (p50): gate 0.048, execute 1.8, assess 0.002, normalize 0.022
- cold p50 2.515 vs warm p50 2.468

## What this diagnoses (-> Wk 14-15)

- Planner over-routes: source precision 0.887 (7 unnecessary source calls) — mitigation/mapping questions are sent to both sources. Tighten routing.
- Planner cannot route bare id lookups (e.g. 'what is T1059.001?') — they were excluded from the generated corpus as unroutable. Add a lookup intent.
- attack latency p50=1.046ms p99=4.761ms (gap 3.715ms), execute-dominated.
- capec latency p50=2.468ms p99=6.77ms (gap 4.302ms), execute-dominated.
- Safety: an adversarial probe surfaced (and this milestone fixed) a single-quoted unknown-label bypass in the Gremlin gate; keep probing as the gate evolves.
