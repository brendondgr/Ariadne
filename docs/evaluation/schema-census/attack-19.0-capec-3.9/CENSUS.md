# Schema census

ATT&CK v19.0 + CAPEC v3.9, read from the pinned raw snapshot. Regenerate with `uv run python -m utils.specialists.evalset.schema_census`.

## The number this was built to produce

The banks draw from **16 hand-written question categories**. The sources support **34 distinct edge types** across **25 node types**.

Those categories reach **12 of 34** edge types — **35.3%** of the shapes, covering **66.6%** of the 34,954 edge instances.

On the property side it is narrower still: **16 of 83** node properties (**19.3%**), because only the `lookup` category reads a property at all and it reads the description.

| | count |
|---|---:|
| node types | 25 |
| nodes | 10,170 |
| edge types | 34 |
| edge instances | 34,954 |
| cross source edge types | 1 |
| enumerable properties | 46 |
| facet properties | 12 |
| forward askable edge types | 32 |
| reverse askable edge types | 31 |
| dangling cross source references | 10 |

## Edge types

`fwd` / `rev` are median and p90 fan-out. *Askable* in a direction means
p90 answers stay under 50. It is reported, never used to exclude: Q29
measured judged score against gold width and found no effect.

| triple | n | fwd med/p90 | rev med/p90 | origin | asked? |
|---|---:|---:|---:|---|---|
| `Software -[uses]-> Technique` | 11,213 | 11/27 | 5/53 | relationship-object | yes |
| `Group -[uses]-> Technique` | 4,546 | 19/63 | 3/26 | relationship-object | yes |
| `Analytic -[log_source]-> DataComponent` | 4,170 | 2/4 | 7/109 | nested-ref | **never** |
| `DetectionStrategy -[x_mitre_analytic_refs]-> Analytic` | 1,745 | 2/5 | 1/1 | embedded-ref | **never** |
| `Mitigation -[mitigates]-> Technique` | 1,448 | 19.5/79 | 2/5 | relationship-object | yes |
| `AttackPattern -[EXPLOITS_WEAKNESS]-> Weakness` | 1,211 | 1/7 | 2/9 | xml-element | yes |
| `AttackPattern -[HAS_MITIGATION]-> CapecMitigation` | 1,170 | 2/6 | 1/1 | xml-element | **never** |
| `Campaign -[uses]-> Technique` | 1,146 | 18/34 | 2/9 | relationship-object | **never** |
| `Group -[uses]-> Software` | 1,144 | 5/17 | 1/3 | relationship-object | **never** |
| `Technique -[kill_chain_phase]-> Tactic` | 872 | 1/2 | 49/113 | embedded-ref | yes |
| `AttackPattern -[HAS_EXECUTION_STEP]-> ExecutionStep` | 815 | 3/4 | 1/1 | xml-element | yes |
| `AttackPattern -[HAS_CONSEQUENCE]-> Consequence` | 812 | 2/4 | 1/1 | xml-element | yes |
| `AttackPattern -[HAS_PREREQUISITE]-> Prerequisite` | 746 | 1/3 | 1/1 | xml-element | **never** |
| `DetectionStrategy -[detects]-> Technique` | 697 | 1/1 | 1/1 | relationship-object | yes |
| `AttackPattern -[ChildOf]-> AttackPattern` | 532 | 1/1 | 3/7 | xml-element | yes |
| `Technique -[subtechnique-of]-> Technique` | 475 | 1/1 | 4/8 | relationship-object | yes |
| `AttackPattern -[REQUIRES_SKILL]-> Skill` | 402 | 1/2 | 1/1 | xml-element | yes |
| `AttackPattern -[HAS_EXAMPLE]-> Example` | 387 | 1/2 | 1/1 | xml-element | **never** |
| `AttackPattern -[REQUIRES_RESOURCE]-> Resource` | 289 | 1/1 | 1/1 | xml-element | **never** |
| `AttackPattern -[MAPS_TO[ATTACK]]-> Technique` | 271 | 1/3 | 1/2 | xml-element/cross-source | yes |
| `Category -[HAS_MEMBER]-> AttackPattern` | 190 | 6/17 | 3/4 | xml-element | **never** |
| `Campaign -[uses]-> Software` | 172 | 2/8 | 1/2 | relationship-object | **never** |
| `AttackPattern -[CanPrecede]-> AttackPattern` | 162 | 1/5 | 1/6 | xml-element | **never** |
| `AttackPattern -[HAS_INDICATOR]-> Indicator` | 96 | 1/3 | 1/1 | xml-element | **never** |
| `View -[HAS_MEMBER]-> AttackPattern` | 46 | 46/46 | 1/1 | xml-element | **never** |
| `AttackPattern -[MAPS_TO[OWASP Attacks]]-> TaxonomyEntry:OWASP Attacks` | 39 | 1/1 | 1/1 | xml-element | **never** |
| `AttackPattern -[MAPS_TO[WASC]]-> TaxonomyEntry:WASC` | 37 | 1/1 | 1/1 | xml-element | **never** |
| `AttackPattern -[HAS_ALTERNATE_TERM]-> AlternateTerm` | 27 | 1/3 | 1/1 | xml-element | **never** |
| `Campaign -[attributed-to]-> Group` | 26 | 1/1 | 1/2 | relationship-object | **never** |
| `View -[HAS_MEMBER]-> Category` | 21 | 6/9 | 1/1 | xml-element | **never** |
| `AttackPattern -[PeerOf]-> AttackPattern` | 19 | 1/3 | 1/1 | xml-element | **never** |
| `Matrix -[tactic_refs]-> Tactic` | 15 | 15/15 | 1/1 | embedded-ref | **never** |
| `AttackPattern -[CanFollow]-> AttackPattern` | 10 | 1/2 | 1/1 | xml-element | **never** |
| `AttackPattern -[CanAlsoBe]-> AttackPattern` | 3 | 1/1 | 1/1 | xml-element | **never** |

## Never asked

22 edge types have never carried a question:

- `Analytic -[log_source]-> DataComponent`
- `AttackPattern -[CanAlsoBe]-> AttackPattern`
- `AttackPattern -[CanFollow]-> AttackPattern`
- `AttackPattern -[CanPrecede]-> AttackPattern`
- `AttackPattern -[HAS_ALTERNATE_TERM]-> AlternateTerm`
- `AttackPattern -[HAS_EXAMPLE]-> Example`
- `AttackPattern -[HAS_INDICATOR]-> Indicator`
- `AttackPattern -[HAS_MITIGATION]-> CapecMitigation`
- `AttackPattern -[HAS_PREREQUISITE]-> Prerequisite`
- `AttackPattern -[MAPS_TO[OWASP Attacks]]-> TaxonomyEntry:OWASP Attacks`
- `AttackPattern -[MAPS_TO[WASC]]-> TaxonomyEntry:WASC`
- `AttackPattern -[PeerOf]-> AttackPattern`
- `AttackPattern -[REQUIRES_RESOURCE]-> Resource`
- `Campaign -[attributed-to]-> Group`
- `Campaign -[uses]-> Software`
- `Campaign -[uses]-> Technique`
- `Category -[HAS_MEMBER]-> AttackPattern`
- `DetectionStrategy -[x_mitre_analytic_refs]-> Analytic`
- `Group -[uses]-> Software`
- `Matrix -[tactic_refs]-> Tactic`
- `View -[HAS_MEMBER]-> AttackPattern`
- `View -[HAS_MEMBER]-> Category`

## Facet properties

Properties whose values are shared across enough nodes to carry a filter —
the raw material for constrained questions, of which the banks have none.
Identifiers and bundle metadata are excluded; date properties are listed
after, because they carry range filters rather than equality filters.

| node type | property | distinct | coverage | values |
|---|---|---:|---:|---|
| Analytic | `x_mitre_platforms` | 11 | 100% | Containers, ESXi, IaaS, Identity Provider, Linux, Network Devices, … (+5) |
| Software | `x_mitre_platforms` | 14 | 95% | Android, Containers, ESXi, Engineering Workstation, Field Controller/RTU/PLC/IED, IaaS, … (+8) |
| Technique | `x_mitre_impact_type` | 2 | 5% | Availability, Integrity |
| Technique | `x_mitre_is_subtechnique` | 2 | 100% | False, True |
| Technique | `x_mitre_platforms` | 11 | 100% | Containers, ESXi, IaaS, Identity Provider, Linux, Network Devices, … (+5) |
| AttackPattern | `Abstraction` | 3 | 100% | Detailed, Meta, Standard |
| AttackPattern | `Likelihood_Of_Attack` | 3 | 62% | High, Low, Medium |
| AttackPattern | `Status` | 3 | 100% | Draft, Stable, Usable |
| AttackPattern | `Typical_Severity` | 5 | 87% | High, Low, Medium, Very High, Very Low |
| Category | `Status` | 3 | 100% | Deprecated, Draft, Stable |
| View | `Status` | 2 | 100% | Draft, Stable |
| View | `Type` | 3 | 100% | Explicit, Graph, Implicit |

Date properties (range filters): `Campaign.first_seen`, `Campaign.last_seen`

## Dangling cross-source references

CAPEC declares 10 ATT&CK technique ids that the pinned Enterprise bundle has no live object for. They are the cross-source join's failure surface and must not carry a federated question:

> `T1513`, `T1562.001`, `T1562.002`, `T1562.003`, `T1562.004`, `T1562.006`, `T1562.007`, `T1562.008`, `T1562.009`, `T1574.002`

## Node types

| source | label | count | referenced only | text properties |
|---|---|---:|---|---|
| attack | Analytic | 1,758 | — | `description` |
| attack | Campaign | 56 | — | `description` |
| attack | DataComponent | 106 | — | `description` |
| attack | DetectionStrategy | 697 | — | — |
| attack | Group | 174 | — | `description` |
| attack | Matrix | 1 | — | `description` |
| attack | Mitigation | 44 | — | `description` |
| attack | Software | 821 | — | `description` |
| attack | Tactic | 15 | — | `description` |
| attack | Technique | 697 | — | `description` |
| capec | AlternateTerm | 27 | — | — |
| capec | AttackPattern | 558 | — | `Description`, `Extended_Description` |
| capec | CapecMitigation | 1,170 | — | `text` |
| capec | Category | 78 | — | — |
| capec | Consequence | 812 | — | — |
| capec | Example | 387 | — | `text` |
| capec | ExecutionStep | 815 | — | `text` |
| capec | Indicator | 96 | — | `text` |
| capec | Prerequisite | 746 | — | `text` |
| capec | Resource | 289 | — | `text` |
| capec | Skill | 402 | — | `text` |
| capec | TaxonomyEntry:OWASP Attacks | 39 | yes | — |
| capec | TaxonomyEntry:WASC | 33 | yes | — |
| capec | View | 13 | — | — |
| capec | Weakness | 336 | yes | — |
