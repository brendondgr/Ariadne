# PROTOCOL — EXP-2026-08-011 Identity-schema transfer

> Written before anything is built. No number in this experiment exists yet.
> Implementation plan: [`docs/plans/2026-08-21-identity-schema-transfer.md`](../../../plans/2026-08-21-identity-schema-transfer.md).

## Question

C-010 says the system's dataset-specific surface is bounded and countable — that
the schema-agnostic machinery transfers to a source that is not MITRE, and only a
known number of templates need re-authoring. It is marked `supported`, but its
evidence is [EXP-2026-07-011](../EXP-2026-07-011-portability-audit/), an audit
whose own threats section says: *"This is an audit, not a measurement. No
non-MITRE dataset was ever loaded. The portability verdict is a code reading, and
code readings miss coupling that only shows up at run time."*

So: **when a schema this codebase has never seen is loaded and queried, does the
schema-agnostic path actually work — and does the gap between it and the
template path match the surface the audit counted?**

Both halves can come out either way. The generic path could fail on coupling the
AST parse could not see. The template path could score higher than predicted
because some templates are less MITRE-shaped than their names suggest.

## Hypothesis

**H1 — the generic path transfers.** The schema-derived primitives arm reaches
gold-in-evidence retrieval within **0.10** of its MITRE blind figure. On the
fresh bank of EXP-2026-08-008 that arm scored 0.9700 judged with retrieval
saturated at 30/30, so H1 predicts identity retrieval **≥ 0.90**. The reasoning
is C-010's own: `describe`/`expand` read labels, facets and directions from the
card they are handed, and the card is now built from a declared catalog instead
of a scan.

**H2 — the template path does not transfer, and the gap measures the surface.**
The deterministic template cascade scores **< 0.40** retrieval on the identity
schema. 19 of its 25 distinct templates are MITRE-specific by the audit's AST
count; `group_techniques` and its siblings name ATT&CK labels that do not exist
here. This is the load-bearing prediction: **the arm gap is the dataset-specific
surface, measured at run time rather than counted by parsing source.** If H1 and
H2 both hold, C-010 survives contact with a real foreign schema and gains a
measurement to stand on.

**H3 — direction resolution degrades specifically on same-label-both-ends
edges.** Retrieval on the eight triples whose source and target labels are equal
(`GROUP -OWNS-> GROUP`, `GROUP -WRITE_DACL-> GROUP`, `DOMAIN -TRUSTED_BY->
DOMAIN`, and five more) falls **at least 0.20 below** retrieval on
heterogeneous-label triples in the same run.

This is a predicted *defect*, stated now, and it follows from the data model
rather than from pessimism. A `PlausibleFacet` is `(rel_type, direction,
neighbour_label)`. When both endpoints carry the same label, `(OWNS, out,
GROUP)` and `(OWNS, in, GROUP)` differ only in the direction field — the
neighbour label carries no disambiguating signal. On MITRE, direction is
recoverable from label asymmetry almost everywhere (a Technique cannot *use* a
Group), which is why this failure mode has never been exercised. ATT&CK has
essentially no homogeneous-label edges; this schema has eight, and they are
exactly the privilege-escalation edges an analyst would ask about.

**H4 — identifier schemes go open, and the honesty property holds.** More than
**50%** of identity node properties learn as *open* (no scheme; admits
everything), because GUIDs, UPNs and free-text names dominate and `idscheme.py`
caps at `MAX_SCHEMES = 24`. Consequently the binding guard cannot fire on those
properties and the protection it bought on MITRE (part of the 0.7688 → 0.8952
blind rise in EXP-2026-08-005) is unavailable here. The companion prediction is
the one that matters for the design claim: **zero false mismatches.** A property
that learned nothing must return `undetermined`, never a wrong `mismatch`. H4 is
half a limitation and half a test of a stated safety property.

## Setup

System under test: the Ariadne pipeline at the commit recorded in
`manifest.yaml`, **with no language model in the loop** for the primary metric.
Planning is the deterministic drafter, query construction is deterministic by
construction, synthesis is the deterministic composer. The primary result is
therefore byte-reproducible and re-runnable without the shared inference server.

Two arms, the same pair EXP-2026-08-009 compared so the reading is already
calibrated against a known instrument:

| Arm | What it is | Held constant |
|---|---|---|
| `generic` | Schema-derived `describe`/`expand` primitives, templates disabled | plan, questions, gold, composer, grader |
| `deterministic` | The 25-template if-cascade | same |

The identity source is **isolated by directory and store URI**
(`ARIADNE_DATA_DIR=data-identity`, its own Neo4j port), never registered in
`data/source_cards/` or `data/graphs/`. `load_source_cards()` globs and
`discover_datasets()` walks; either would silently add a source to arms that are
already measured. A separation script asserts the ATT&CK and CAPEC stores are
untouched, as EXP-2026-08-009 required 8/8.

## Data

**Schema — real.** ReliaQuest's production graph catalog, delivered
2026-08-21 as two CSV exports of `customer_vertex_catalog`,
`customer_edge_catalog` and `customer_attribute_catalog`: 72 node types, 21 edge
labels, 60 typed `(source, edge, target)` triples, 779 node attributes and 118
edge attributes across Active Directory, Entra, Okta, AWS and GCP. It contains
**zero customer records**. Dataset card:
[`../../datasets/cards/reliaquest-identity-catalog.md`](../../datasets/cards/reliaquest-identity-catalog.md).

**Instances — synthetic, by necessity.** ReliaQuest cannot supply customer data;
that is why they supplied a catalog. A seeded generator emits a tenant that obeys
the declared catalog structurally — every edge matches a declared triple, every
property key a declared attribute — with attack chains planted deliberately and
identifier shapes deliberately mixed. Target scale ~1,200 nodes / ~4,000 edges,
the same order as the ATT&CK store's 4,369, so retrieval breadth is comparable
and no difference is a size effect.

**Questions.** 30, drawn and authored by the committed sampler/author/compiler
separation in `utils/specialists/evalset/`, the same protocol as the blind
holdout: the author sees four fields of one anchor and nothing else. Gold is
computed from the generator's blueprint (`spec.json`), never by querying the
loaded graph — mirroring why `gold_bank.py` parses raw STIX deliberately *not*
through `kg_builder`. Without that independence the experiment is circular: a
dropped edge would cancel out on both sides instead of showing up.

### The truncation, and why it is permanent

The delivered export uses `join customer_attribute_catalog` — an inner join — so
**every edge type carrying no attributes was dropped before the file was
written.** The evidence is structural, not inferred: there is no `USER
-MEMBER_OF-> GROUP` triple, and 48 of the 60 triples have `GROUP` as source. That
is an Active Directory graph in which no user belongs to any group.

The operator has confirmed (2026-08-21) that no corrected export will be
supplied. This is therefore a **permanent limitation of the experiment, not a
temporary one**, and it is handled as follows:

* The 60 declared triples are the authoritative set and are never modified.
* The small number of edges an AD graph cannot function without are carried in a
  separate `inferred` block, marked as such in the artifact and in the source
  card, and reported in RESULTS. They are the experimenter's construction, not
  ReliaQuest's schema.
* Any per-triple result is reported split by declared-vs-inferred so no reader
  can mistake one for the other.

The honest consequence: this experiment measures transfer to a schema that is
*real but partially observed*, and the inferred edges are a confound on any
question that traverses them. H3's homogeneous-label finding is unaffected — all
eight of those triples are declared, none inferred.

## Metrics

**Primary — gold-in-evidence retrieval rate.** For each question, the fraction
of gold records (blueprint-derived) that appear in the evidence the arm
retrieved. Population: 30 questions × 2 arms. Deterministic, no judge. Success is
not a threshold but the arm difference: H1 and H2 name bands.

**Secondary — judged correctness.** LLM-graded on the persisted answers, the same
grader and budget as EXP-2026-08-009 (32,768 tokens, re-attempt on empty reply).
Reported with a 95% interval. Runs last and can run overnight.

**Diagnostics, all deterministic:**

| Metric | Computes | Bears on |
|---|---|---|
| `direction_homo` / `direction_hetero` | retrieval split by whether the traversed triple's endpoint labels are equal | H3 |
| `scheme_open_rate` | share of node properties learning as *open* | H4 |
| `false_mismatch_count` | properties reporting `mismatch` where the blueprint says the value is valid — must be 0 | H4 |
| `abstention_with_proof` | share of declining answers carrying the executed query | C-017 |
| `fabrication_count` | claims not traceable to a retrieved record | C-001 |
| `declared_vs_inferred` | retrieval split by whether the path used an inferred edge | the truncation confound |

## Baselines

The two arms are each other's baseline: same questions, same gold, same
composer, same grader in one session, so the template inventory is the only
variable. That is the fair comparison and it is internal to this run.

The MITRE blind figures (EXP-2026-08-008: `generic` 0.9700, cascade 0.9467) are
quoted as a **reference band, not a paired comparison** — different questions,
different schema, different session. They set H1's and H2's thresholds and must
never be differenced against this run's numbers as if paired.

## Procedure

```bash
# 2  catalog -> declared artifact
uv run python -m utils.kg_builder.catalog --out data-identity/catalog/declared.json

# 4  synthetic tenant + blueprint (seeded)
uv run python -m utils.kg_builder.synthetic --seed 20260821 --out data-identity

# 5  card, load, separation
uv run python -m utils.kg_builder.catalog card --out data-identity/source_cards/identity.json
ARIADNE_DATA_DIR=data-identity uv run main.py --dataset identity --graph neo4j
uv run python scripts/identity_separation.py

# 6  gold from the blueprint
uv run python -m utils.specialists.evalset.identity_gold

# 7  draw + author the bank            [needs skynet; checkpointed]
uv run python -m utils.specialists.evalset.identity_bank --seed 20260821

# 8  run both arms, score retrieval    [no LLM]
uv run python scripts/identity_sweep.py --out docs/evaluation/identity-2026-08-21

# 9  judge                             [needs skynet; resumable]
uv run python scripts/identity_sweep.py --stage judge --out docs/evaluation/identity-2026-08-21
```

## What would falsify this

* **H1 falsified** if the generic arm retrieves below 0.90. That would mean the
  audit missed run-time coupling, and C-010 would have to move off `supported` —
  the interesting outcome, and the one worth the most.
* **H2 falsified** if the template cascade scores at or above 0.40. That would
  mean the templates are less MITRE-bound than the AST count implies, and the
  "19 of 25" figure overstates the re-authoring cost.
* **H3 falsified** if homogeneous-label retrieval lands within 0.20 of
  heterogeneous. Direction resolution would then be doing more than the facet
  record alone can explain, and that mechanism needs finding.
* **H4 falsified** on either half: fewer than 50% open properties (identity data
  is more structured than assumed), or — the serious one — **any false
  mismatch**, which would refute the stated honesty property of `idscheme.py`
  and is a defect to fix before anything else in this experiment is reported.

**If every hypothesis holds, the experiment is still only worth what its
instances are worth.** Synthetic data can demonstrate that schema navigation
works; it cannot demonstrate that the answers would be operationally useful on a
real tenant. That limit is stated here, in advance, so it is not discovered in
review.
