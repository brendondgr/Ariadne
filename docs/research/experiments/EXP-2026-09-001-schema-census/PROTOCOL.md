# PROTOCOL — EXP-2026-09-001 Schema census

> **Honest note on ordering.** The enumeration and this protocol were written in
> the same session, and the protocol was committed after the first run. That is
> defensible *here* and would not be elsewhere: the census has no free
> parameter, no arm, and no outcome it could be tuned toward — it either finds a
> shape in the raw file or it does not. The one part that *could* have been
> fitted is the coverage map (§ Metrics), and the guard against that is stated
> below and enforced by a test.

## Question

How many of the question shapes the pinned ATT&CK and CAPEC sources support has
any Ariadne question bank ever asked about?

Every bank we hold draws from 16 hand-written categories in
`holdout_protocol.py` — `ATTACK_CATEGORIES`, `CAPEC_CATEGORIES`,
`FEDERATED_CATEGORIES`. Those were written from domain memory, not derived from
the data. Nobody has ever counted the denominator.

## Hypothesis

Stated before the run: **the 16 categories cover a minority of the available
edge types, and the shortfall is concentrated in (a) relations involving
Campaign, Analytic and DataComponent, and (b) CAPEC's non-`ChildOf` natures.**

The prediction is falsifiable in both directions: if the sources supported ~16
shapes, the categories were adequate and bank expansion is a volume problem
only, not a coverage problem.

## Setup

A standalone enumerator, `utils/specialists/evalset/schema_census.py`, run
against the pinned raw snapshot. No database, no LLM, no network.

Three properties are load-bearing and are the reason this is an experiment and
not a script:

1. **Raw files only.** It parses the STIX bundle and the CAPEC XML directly,
   not through `utils.kg_builder` and not from a live Neo4j/Gremlin store. A
   census taken through the ingest pipeline could only report what the pipeline
   chose to keep, which would make the coverage number circular.
2. **Architecture-blind above the coverage layer.** Nothing in the enumeration
   knows Ariadne has templates, primitives or a composer.
3. **Load-time exclusion policy mirrored.** ATT&CK revoked/deprecated objects
   and CAPEC `Deprecated`/`Obsolete` patterns are excluded, and relationships
   with a dead endpoint are pruned, so every shape reported is one a question
   could actually be answered from. Exclusions are counted, not silently
   applied.

## Data

ATT&CK Enterprise v19.0 (`sha256:df520ea0…`, 52,680,865 bytes) and CAPEC v3.9
(`sha256:70279a2d…`, 3,849,998 bytes), both pinned in `data/versions.json`.
Full inventory in [`data/POINTERS.md`](data/POINTERS.md).

No sampling. The census is a total enumeration, so selection bias does not
apply.

## Metrics

**Edge type.** A distinct `(subject label, predicate, object label)` triple with
at least one live instance. Reported with instance count, distinct subjects,
distinct objects, and fan-out in **both** directions (n / mean / median / p90 /
max over the nodes that have at least one edge).

**Askable, forward / reverse.** An edge type whose p90 fan-out in that direction
is ≤ 50. Above that a question has no answer small enough to grade. Direction is
separated because reverse-direction asks are where the blind holdout collapsed
(EXP-2026-08-005); an edge can be askable one way and not the other.

**Facet property.** A property that is enumerable (≤ 60 distinct values), whose
distinct/present ratio is ≤ 0.25, and whose name is not an identifier or bundle
metadata. The ratio and the exclusion list both exist because a distinct-count
threshold alone calls `Campaign.name` a filter. Facets are the raw material for
constrained questions; the banks currently contain none.

**Category coverage** — the one architecture-aware measure. `CATEGORY_TRIPLES`
maps each of the 16 authored categories onto the census triples it can produce a
question for. Reported as edge types reached / total, edge instances reached /
total, and node properties reached / total.

> **Guard against fitting.** `CATEGORY_TRIPLES` was transcribed mechanically
> from the category descriptions in `holdout_protocol.py` before any coverage
> number existed, and `test_every_declared_category_triple_exists` asserts that
> every triple named in the map is one the census independently found. A map
> quietly narrowed to flatter the coverage number would have to name triples
> that do not exist, and that test would fail.

## Baselines

None, and none is possible: this is a first measurement of a quantity nothing
else in the repository reports. The comparison that *is* available, and is
enforced, is **agreement with `gold_bank`** — an independent derivation from the
same two files, sharing no code with the census. Node counts and five edge
counts must match exactly.

## Procedure

```
uv run python -m utils.specialists.evalset.schema_census
uv run pytest utils/specialists/evalset/tests/test_schema_census.py -q
```

Outputs `census.json` (machine) and `CENSUS.md` (rendered) under
`docs/evaluation/schema-census/attack-<v>-capec-<v>/`, keyed by source version
so a snapshot bump produces a new census rather than overwriting the old one.

## Threats to validity

- **The census can only find shapes it knows how to look for.** Edges hidden in
  structures nobody parsed would be missed, and a miss inflates coverage. Four
  tests exist specifically to catch this class: all five CAPEC natures present,
  all three taxonomies present, every live STIX relationship type typed, and
  embedded/nested refs treated as edges. One real instance was caught this way
  — see ISSUES I-1.
- **Sub-element nodes are census artifacts, not source entities.** CAPEC
  execution steps, consequences and skills have no ids in the XML; the census
  synthesises them the way the loaded graph does. Their counts are instance
  counts, not distinct entities.
- **Coverage is an upper bound on what was asked.** It measures what the 16
  categories *could* reach, not what any particular 30-question bank did reach.
  A real bank asks fewer shapes than this, never more.
- **ATT&CK and CAPEC only.** The identity graph is generated from a blueprint
  rather than a raw catalogue and is out of scope here.
