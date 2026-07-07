# Component-Level Evaluation

ATT&CK 19.0 · CAPEC 3.9 · full report (live EX + latency)

Deterministic scoring against snapshot-derived gold — no LLM judge. The model drafts, deterministic code grades; every number here is reproducible.

> **Read the ceiling honestly.** Ariadne's specialists do not free-generate queries — a deterministic builder fills read-only templates — so query validity sits at the ceiling by construction and EX misses point at routing/seed/ingest issues, not malformed queries. That is a design strength, stated plainly.

## Planner

Drafter scored: **deterministic** (deterministic, reproducible).

| Metric | Overall | Dev | Holdout |
|---|---|---|---|
| Source precision | 0.919 | 0.906 | 0.955 |
| Source recall | 1.0 | 1.0 | 1.0 |
| Unnecessary source calls | 7 | 6 | 1 |
| Sub-question quality | 0.839 | 0.828 | 0.87 |
| — routing accuracy | 0.837 | 0.812 | 0.909 |
| — dependency accuracy | 0.837 | 0.812 | 0.909 |
| Schema adherence | 1.0 | 1.0 | 1.0 |
| Honesty (unsupported/partial) | 1.0 | 1.0 | 1.0 |

Corpus: 43 cases (curated 7, generated 36). Curated-anchor pass rate 1.0.

## Specialists

### attack

**Query validity (VA)** — share of drafted queries clearing the gate:

- first-pass: 1.000 [0.92–1.00] (k=44/44)
- post-retry: 1.000 [0.92–1.00] (k=44/44)
- boundary (no query drafted): 2

**Execution accuracy (EX)** — result set vs snapshot gold:

- exact-set-match: 1.000 [0.92–1.00] (k=46/46)
- precision / recall / F1: 1.0 / 1.0 / 1.0
- error taxonomy: none

**Safety adherence** — bounded-execution audit + adversarial probes:

- accepted-query adherence: 1.0 (44 audited, breaches 0)
- adversarial probe block rate: 1.0 (10 probes, leaks 0)

**Latency** — p50/p95/p99 (ms), warm steady-state:

- total: p50 1.099 · p95 2.032 · p99 4.425 · gap 3.326
- by stage (p50): gate 0.043, execute 0.9, assess 0.002, normalize 0.017
- cold p50 1.43 vs warm p50 1.099

### capec

**Query validity (VA)** — share of drafted queries clearing the gate:

- first-pass: 1.000 [0.90–1.00] (k=34/34)
- post-retry: 1.000 [0.90–1.00] (k=34/34)
- boundary (no query drafted): 0

**Execution accuracy (EX)** — result set vs snapshot gold:

- exact-set-match: 1.000 [0.90–1.00] (k=34/34)
- precision / recall / F1: 1.0 / 1.0 / 1.0
- error taxonomy: none

**Safety adherence** — bounded-execution audit + adversarial probes:

- accepted-query adherence: 1.0 (34 audited, breaches 0)
- adversarial probe block rate: 1.0 (7 probes, leaks 0)

**Latency** — p50/p95/p99 (ms), warm steady-state:

- total: p50 2.617 · p95 4.21 · p99 6.891 · gap 4.274
- by stage (p50): gate 0.065, execute 1.9, assess 0.003, normalize 0.03
- cold p50 2.697 vs warm p50 2.617

## What this diagnoses (-> Wk 14-15)

- Planner over-routes: source precision 0.919 (7 unnecessary source calls) — mitigation/mapping questions are sent to both sources. Tighten routing.
- Planner cannot route bare id lookups (e.g. 'what is T1059.001?') — they were excluded from the generated corpus as unroutable. Add a lookup intent.
- attack latency p50=1.099ms p99=4.425ms (gap 3.326ms), execute-dominated.
- capec latency p50=2.617ms p99=6.891ms (gap 4.274ms), execute-dominated.
- Safety: an adversarial probe surfaced (and this milestone fixed) a single-quoted unknown-label bypass in the Gremlin gate; keep probing as the gate evolves.
