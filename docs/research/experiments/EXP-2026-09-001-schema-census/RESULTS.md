# RESULTS — EXP-2026-09-001 Schema census

**Status: complete, 2026-09-01.** Deterministic enumeration; no model, no
database, no network. Re-running reproduces the artifact byte-for-byte.

## Headline

**The 16 hand-written question categories reach 12 of the 33 edge types the
sources support — 36.4%.** Twenty-one edge types have never carried a question.

| Measure | Value |
|---|---:|
| Node types | 23 |
| Nodes (after exclusions) | 10,098 |
| Edge types | 33 |
| Edge instances | 34,954 |
| Edge types reached by the 16 categories | 12 (36.4%) |
| Edge instances reached | 23,294 (66.6%) |
| Node properties reached | 23 of 74 (31.1%) |
| Facet properties available | 12 |
| Facet properties used by any bank | **0** |
| Cross-source edge types | **1** |

The instance figure (66.6%) is higher than the shape figure (36.4%) for an
unflattering reason: the categories concentrate on the three highest-volume
edges in the graph — `Software -uses-> Technique` (11,213),
`Group -uses-> Technique` (4,546) and `Mitigation -mitigates-> Technique`
(1,448). Coverage looks broader by instance count than it is by shape.

## The hypothesis held, and understated the result

Predicted before the run: the shortfall would be concentrated in Campaign,
Analytic and DataComponent relations, and in CAPEC's non-`ChildOf` natures. All
five of those appear in the never-asked list. What the prediction missed is
**how much of the graph they add up to**.

Top never-asked edge types by instance count:

| Triple | n | fwd med/p90 | rev med/p90 |
|---|---:|---:|---:|
| `Analytic -[log_source]-> DataComponent` | 4,170 | 2/4 | 7/109 |
| `DetectionStrategy -[x_mitre_analytic_refs]-> Analytic` | 1,745 | 2/5 | 1/1 |
| `AttackPattern -[HAS_MITIGATION]-> CapecMitigation` | 1,170 | 2/6 | 1/1 |
| `Campaign -[uses]-> Technique` | 1,146 | 18/34 | 2/9 |
| `Group -[uses]-> Software` | 1,144 | 5/17 | 1/3 |
| `AttackPattern -[HAS_PREREQUISITE]-> Prerequisite` | 746 | 1/3 | 1/1 |
| `AttackPattern -[HAS_EXAMPLE]-> Example` | 387 | 1/2 | 1/1 |
| `AttackPattern -[REQUIRES_RESOURCE]-> Resource` | 289 | 1/1 | 1/1 |

Three findings fall out of this table.

**F-1 — the detection subgraph is almost entirely untested.** ATT&CK v19
restructured detection into DetectionStrategy → Analytic → DataComponent, and
those two edges alone carry 5,915 instances — 17% of the whole graph. The banks
reach that subgraph through exactly one shape,
`DetectionStrategy -detects-> Technique` (697 instances), because that is the
one the `detection` category was written for. The two-hop and three-hop
detection questions a detection engineer would actually ask have never been
asked once.

**F-2 — CAPEC mitigations are invisible while ATT&CK mitigations are the most
asked shape in the record.** `AttackPattern -HAS_MITIGATION-> CapecMitigation`
carries 1,170 instances, comparable to `Mitigation -mitigates-> Technique`'s
1,448, and no bank has ever touched it. Nobody chose this asymmetry; it is an
artifact of which categories someone thought of.

**F-3 — every one of the 21 never-asked edge types is forward-askable** (p90 ≤
50), and 13 of them carry 50 or more instances. They are absent because no
category was written for them, not because they are unanswerable. This is the
finding that matters for expansion: the missing shapes are *usable*.

## Direction, measured rather than assumed

Fan-out is recorded in both directions because reverse-direction asks are where
the blind holdout collapsed. Two asked shapes turn out to be marginal:

| Triple | fwd p90 | rev p90 | note |
|---|---:|---:|---|
| `Group -[uses]-> Technique` | **63** | 26 | the `groups` category asks *both* directions |
| `Technique -[kill_chain_phase]-> Tactic` | 2 | **113** | forward only, correctly |
| `Software -[uses]-> Technique` | 27 | **53** | reverse is marginal |
| `Mitigation -[mitigates]-> Technique` | **79** | 5 | asked in reverse, correctly |

`ATTACK_CATEGORIES["groups"]` reads *"The techniques a named group uses, or the
groups using a technique"* — it licenses the direction whose p90 answer is 63
items. That is a live risk in banks we already hold, not a hypothetical: a
question drawn on that side has an answer no grader can score well, and it would
show up as a system failure rather than as a question defect. Recorded as I-2.

## Federation rests on 271 edges

**There is exactly one cross-source edge type in the entire census**:
`AttackPattern -[MAPS_TO[ATTACK]]-> Technique`, 271 instances, median fan-out 1.

Every federated question in every bank, every claim about cross-store
correlation, and the whole merged-vs-federated comparison traverse that single
edge type. It is not wrong — it is what the sources declare — but it needs
saying plainly in any write-up, because "federated graph QA" implies a richer
join surface than one taxonomy mapping with 271 rows.

## Twelve facets, zero used

The census finds 12 properties whose values are shared widely enough to carry a
filter — `Technique.x_mitre_platforms` (11 values, 100% coverage),
`AttackPattern.Abstraction` (3), `AttackPattern.Typical_Severity` (5),
`AttackPattern.Likelihood_Of_Attack` (3), `Software.x_mitre_platforms` (14),
and 7 more, plus two date properties on Campaign that carry range filters.

No bank contains a single constrained question. "Which techniques targeting
Linux have no listed mitigation" is answerable from the pinned snapshot today
and has never been asked.

## Agreement with the independent derivation

The census and `gold_bank` parse the same two files by different routes and
share no code. They agree exactly:

| Quantity | census | gold_bank |
|---|---:|---:|
| Live ATT&CK objects | 4,369 | 4,369 |
| Techniques (incl. sub-techniques) | 697 | 222 + 475 |
| CAPEC patterns | 558 | 558 |
| CWEs | 336 | 336 |
| `Mitigation -mitigates-> Technique` | 1,448 | 1,448 |
| `Group -uses-> Technique` | 4,546 | 4,546 |
| `Software -uses-> Technique` | 11,213 | 11,213 |
| `AttackPattern -MAPS_TO[ATTACK]-> Technique` | 271 | 271 |
| `AttackPattern -EXPLOITS_WEAKNESS-> Weakness` | 1,211 | 1,211 |

Enforced by `test_node_counts_match_gold_bank` and
`test_edge_counts_match_gold_bank`. When these diverge, one of the two parsers
has a bug and nothing else in the repository would say so.

## What this does and does not license

**Does.** It sets the denominator for bank expansion, and it names 21 specific
shapes and 12 specific facets to expand into. It replaces "the categories were
written from memory" with a number.

**Does not.** It says nothing about whether Ariadne can *answer* the 21
never-asked shapes. Coverage here is coverage of the question space, not of
system capability, and the two must not be conflated — a shape the banks never
asked may be one the builder handles perfectly or one it cannot express at all.
Establishing which is a separate experiment, and it should be run before any
large generated bank is graded, so that a low score on new shapes can be
attributed to the right cause.

Coverage is also an **upper bound on what was asked**: it measures what the 16
categories *could* reach, not what any 30-question bank did reach. A given bank
asks fewer shapes than this, never more.

## Reproduce

```
uv run python -m utils.specialists.evalset.schema_census
uv run pytest utils/specialists/evalset/tests/test_schema_census.py -q
```
