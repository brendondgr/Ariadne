# Identity-Schema Transfer — Implementation Plan

**Date:** 2026-08-21
**Mode:** B (no worktree; work directly on `main`)
**Target experiment ID:** EXP-2026-08-011 (slug `identity-schema-transfer`)

---

## 1. Introduction

Every correctness figure this project has published was measured on MITRE ATT&CK
and CAPEC — the two schemas the code was developed against. The one artifact that
speaks to whether any of it transfers to a different schema is
[`EXP-2026-07-011`](../research/experiments/EXP-2026-07-011-portability-audit/),
which supports C-010 and whose own threats-to-validity section states the
limitation plainly: *"This is an audit, not a measurement. No non-MITRE dataset
was ever loaded. The portability verdict is a code reading, and code readings
miss coupling that only shows up at run time."* C-010 is currently marked
`supported` on the strength of that reading.

ReliaQuest has now supplied the catalog of their production customer graph — 72
node types, 21 edge labels, 60 typed `(source, edge, target)` triples, 779 node
attributes and 118 edge attributes spanning Active Directory, Entra, Okta, AWS
and GCP. It contains no customer records, only schema, which is precisely the
input Ariadne claims to need. This plan turns C-010 from a code reading into a
measurement: teach the registry to accept a *declared* schema rather than one
derived by scanning instances, generate a synthetic tenant that obeys that
catalog, derive gold from the generator's own blueprint, and run the existing
blind-holdout machinery against a schema no part of this codebase has ever seen.
The deliberate secondary benefit is that the blind metric is currently saturated
(C-014: *"the metric is saturated on both banks and can no longer detect
anything"*) — an unseen domain unsaturates it.

The plan is sequenced so that the entire deterministic spine (steps 1–6, 8)
runs with **no language model at all**, and every LLM-dependent step (7, 9) is
isolated, checkpointed and resumable. That is a direct response to the shared
`skynet` server being under contention: the headline retrieval number is
obtainable without waiting on it.

---

## 2. Gaps & Unanswered Questions

- **The delivered edge catalog is truncated.** `customer_xref.sql.rtf` uses an
  inner `join customer_attribute_catalog`, so any edge type carrying no
  attributes was dropped from the export. The evidence is structural: there is no
  `USER -MEMBER_OF-> GROUP` triple, and 48 of the 60 triples have `GROUP` as
  source — an AD graph in which no user belongs to any group. **Human
  intervention is needed to answer this question:** ReliaQuest should re-run as
  `select distinct source_node_type, edge_label, target_node_type from
  customer_edge_catalog` (and the node equivalent) and re-send. *Assumption until
  they do:* build against the 60 declared triples as the authoritative set, and
  carry the handful of edges an AD graph cannot function without in a separate,
  explicitly-marked `inferred` block that is never merged into the declared set
  and is reported as a threat to validity. If a corrected catalog arrives
  mid-plan, step 2 is re-run and steps 3+ inherit it.

- **Backend for the identity source.** *Assumption:* Neo4j, loaded on an isolated
  port, mirroring the isolation pattern EXP-2026-08-009 used for the merged store
  (separate `ARIADNE_DATA_DIR`, separate `NEO4J_URI`). Cypher is the specialist
  with the wider template surface, and the point of this experiment is the
  schema, not the engine.

- **Tenant scale.** *Assumption:* ~1,200 nodes / ~4,000 edges — the same order of
  magnitude as the ATT&CK store's 4,369 nodes, so retrieval breadth is
  comparable and any difference in score is not a size effect.

- **Does the identity source join the routed source set?** *Assumption:* **No.**
  It stays isolated exactly as `merged` did. `load_source_cards()` globs
  `source_cards/*.json` and `discover_datasets()` walks `graphs/`, so an identity
  card in the ordinary place silently becomes a third routable source and a
  fourth dataset in the schema registry — which would change arms that are
  already measured. Isolation is by directory because a directory cannot be left
  switched on by accident.

- **Are synthetic instances acceptable evidence?** For the claim actually under
  test — *can the system navigate a schema it has never seen* — yes: a synthetic
  `WRITE_DACL` edge exercises the identical code path as a real one, and the
  measurement is of query construction and evidence reading, not of detection
  quality. This must be stated in RESULTS threats-to-validity rather than
  assumed. Not blocking.

- **Whether id schemes are learnable on this domain** is not a gap to close
  before running — it is one of the things being measured. `idscheme.py` caps at
  `MAX_SCHEMES = 24` and records opaque properties as *open*; identity data mixes
  structured identifiers (ARNs, SIDs) with opaque ones (GUIDs, UPNs). Whatever it
  reports is a finding.

- **The ATT&CK crosswalk** (`DC_SYNC` ↔ T1003.006 and similar) would make a
  genuine no-shared-key federation test, but it needs a hand-built mapping table
  that is itself a third source. *Assumption:* **out of scope here**, recorded in
  `OPEN_QUESTIONS.md` as a follow-on. Folding it in would confound schema
  transfer with crosswalk quality.

- **Interaction with EXP-2026-08-010.** That experiment (`status: planned`,
  started today) varies *question authorship* on a familiar schema; this one
  varies *the schema*. They are complementary and must not be run into the same
  conclusions. Noted in both PROTOCOLs.

---

## 3. Hierarchical Step-by-Step Instructions

> **Deviation from `planner.md`, stated once:** that reference says to push to
> GitHub at each step. This repository's `global-project-rules` rule 1 and the
> operator's standing directive both forbid pushing. Every step below therefore
> ends at **commit**, never push.

### Step 1: Pre-register the experiment

- **Locations**: `make new-experiment SLUG=identity-schema-transfer` →
  `docs/research/experiments/EXP-2026-08-011-identity-schema-transfer/`
  (`manifest.yaml`, `PROTOCOL.md`, `RESULTS.md`, `figures/`);
  `docs/research/OPEN_QUESTIONS.md` (new question for the crosswalk follow-on).
- **Rationale**: EXP-2026-08-009 established the house pattern of committing the
  protocol before any number exists, and it is the only defence against the trap
  `make_bank.py` documents — a test set silently becoming a development set.
  Hypotheses, arms, the grader and its budget are fixed here while it is still
  cheap to be honest. `supports_claims` names C-010 (the claim this converts from
  audit to measurement) and C-014 (the saturated metric this unsaturates).
- **Action**: Undergo the verification/tests/validation process for this phase —
  `make validate-research` must pass with the new folder present. Once validated,
  commit stating: `Identity-Schema Transfer (1/9) Complete: pre-registered
  EXP-2026-08-011 with hypotheses fixed before any data exists.`

### Step 2: Ingest the catalog into a declared-schema artifact

- **Locations**: new `utils/kg_builder/catalog/` — `reader.py` (parse
  `node_attributes.csv` / `relationship_attributes.csv`), `declared.py` (the
  normalized artifact + its dataclasses), `tests/test_reader.py`. Output written
  under `data-identity/catalog/declared.json`.
- **Rationale**: The two CSVs are the raw delivery; everything downstream should
  read one normalized artifact rather than re-parsing CSV in three places. The
  reader must record what it *cannot* see — the inner-join truncation — as an
  explicit field rather than silently presenting 60 triples as complete. It also
  carries something the existing scan path has never had: declared value types
  (`STRING` / `BOOLEAN` / `INTEGER` / `LIST_STRING`). Preserve catalog noise
  verbatim, including the real `ENTRA_LICENCE` / `ENTRA_LICENSE` spelling
  collision — it is a free disambiguation test case and cleaning it would be
  fabricating a tidier schema than the customer has.
- **Action**: Undergo the verification/tests/validation process for this phase —
  unit tests pin 72 node types, 21 edge labels, 60 triples, 779 node attributes,
  118 edge attributes, and assert the truncation flag is set. Once validated,
  commit stating: `Identity-Schema Transfer (2/9) Complete: ReliaQuest catalog
  parsed into a declared-schema artifact that records its own truncation.`

### Step 3: Teach the registry to accept a declared schema

- **Locations**: `utils/specialists/schema/build.py` — new
  `build_declared_schema()` beside the existing `build_dataset_schema()`;
  `utils/specialists/schema/registry.py` — `DatasetSchema` gains a provenance
  field distinguishing *observed* from *declared* facets;
  `utils/specialists/schema/tests/test_declared.py`;
  `utils/specialists/tests/test_identity_isolation.py`.
- **Rationale**: This is the load-bearing change and the one that makes the
  system expandable in the sense the funder means — onboarding a source becomes a
  catalog import, not an ingestion project. It is additive: a new function beside
  the old one, never a modification of the scan path, so no measured arm can
  shift. The semantic distinction matters and must be recorded rather than
  glossed: a `PlausibleFacet` derived by scanning means *some node actually has
  this edge*; a declared one means *the catalog permits this edge*. Honest-zero
  claims rest on that difference. Id schemes stay unlearned here — there is no
  data yet — which is the correct `undetermined` behaviour and not a bug to work
  around.
- **Action**: Undergo the verification/tests/validation process for this phase —
  new tests pass, and the isolation test pins that `load_source_cards('data')`
  still returns exactly `{attack, capec}` and `discover_datasets('data')` still
  does not contain `identity`. Full `utils/specialists` suite green under
  `ORCH_MAX_HOPS=5`. Once validated, commit stating: `Identity-Schema Transfer
  (3/9) Complete: DatasetSchema can be built from a declared catalog, isolated
  from every measured arm.`

### Step 4: Generate a synthetic tenant and its blueprint

- **Locations**: new `utils/kg_builder/synthetic/` — `generator.py` (seeded
  emitter), `spec.py` (the blueprint written alongside), `paths.py` (planted
  attack chains), `tests/test_generator.py`. Output: canonical
  `nodes.jsonl` / `relationships.jsonl` under `data-identity/graphs/identity/canonical/`
  plus `spec.json`.
- **Rationale**: Nothing runs without instances. The generator must emit *only*
  edges the declared catalog permits, so conformance is structural rather than
  reviewed. Attack chains are planted deliberately (e.g. `USER → MEMBER_OF →
  GROUP → GENERIC_ALL → USER → DC_SYNC → DOMAIN`) so questions have non-trivial
  multi-hop answers, and the eight same-label-both-ends triples — `GROUP -OWNS->
  GROUP`, `DOMAIN -TRUSTED_BY-> DOMAIN` and the rest — are populated on purpose
  because they are the hardest direction case and MITRE has essentially none of
  them. Identifier shapes are mixed by design (GUIDs, SIDs, UPNs, ARNs) so step 8
  measures scheme learnability rather than assuming it. Seeded and deterministic
  so the graph is reproducible from the seed alone.
- **Action**: Undergo the verification/tests/validation process for this phase —
  a conformance test asserts every emitted edge matches a declared triple and
  every property key matches a declared attribute; a determinism test asserts the
  same seed yields byte-identical output; node/edge counts land in the assumed
  band. Once validated, commit stating: `Identity-Schema Transfer (4/9) Complete:
  seeded synthetic tenant conforming to the declared catalog, with its blueprint.`

### Step 5: Source card, overlay, and isolated load

- **Locations**: `data-identity/source_cards/identity.json` (derived parts) and
  `data-identity/source_cards/overlays/identity.overlay.json` (hand-authored
  connection / safety / provenance / `entity_descriptions`, following the
  existing `attack.overlay.json` shape); `utils/graph_loader/config.py` and
  `utils/specialists/__init__.py` gain an `identity` branch; a separation script
  at `scripts/identity_separation.py`.
- **Rationale**: The card is what the planner and specialists actually read. The
  derived half comes from step 2's artifact; the half no catalog can supply —
  what a `DC_SYNC` edge *means* to an analyst — is hand-authored in an overlay,
  exactly as ATT&CK and CAPEC already do. `entity_descriptions` carry real weight
  here: with 72 labels including five different flavours of "group", the
  deterministic planner's label matching is the thing under stress in T4, and
  glosses are its only disambiguation signal. Loading goes to an isolated Neo4j
  port so the ATT&CK store is provably untouched — EXP-2026-08-009 needed 8/8
  separation checks and this needs the same.
- **Action**: Undergo the verification/tests/validation process for this phase —
  separation script passes, load counts match the generator's manifest exactly,
  and the ATT&CK store's node count is unchanged at 4,369. Once validated, commit
  stating: `Identity-Schema Transfer (5/9) Complete: identity card built and
  loaded into an isolated store, separation verified.`

### Step 6: Derive gold from the blueprint

- **Locations**: new `utils/specialists/evalset/identity_gold.py`;
  `utils/specialists/tests/golden/identity_gold_bank.json`;
  `utils/specialists/evalset/tests/test_identity_gold.py`.
- **Rationale**: This mirrors the independence property that makes the existing
  golden suite double as an ingestion check — [`gold_bank.py`](../../utils/specialists/evalset/gold_bank.py)
  parses the raw STIX bundle deliberately *not* through `kg_builder`, so gold and
  answers agree only if the build was faithful. Here gold is computed from
  `spec.json`, never by querying the loaded graph. If the load dropped an edge,
  gold and the system disagree and the discrepancy is visible instead of silently
  cancelling out. Without this the whole experiment is circular.
- **Action**: Undergo the verification/tests/validation process for this phase —
  a cross-check confirms spec-derived gold and a direct graph read agree on a
  sampled subset, with any disagreement failing loudly. Once validated, commit
  stating: `Identity-Schema Transfer (6/9) Complete: gold derived from the
  blueprint independently of the loaded graph.`

### Step 7: Draw and author the question bank — **LLM-gated**

- **Locations**: `utils/specialists/evalset/make_bank.py` and
  `holdout_protocol.py` invoked against the identity dataset; new
  `utils/specialists/evalset/identity_bank.py` for dataset-specific wiring;
  output to `docs/evaluation/identity-2026-08-<dd>/`.
- **Rationale**: The sampler/author/compiler separation already exists and is the
  protocol — reuse it wholesale rather than re-implementing, so the drawn bank
  inherits the fairness properties already argued for. The author sees four
  fields of one anchor and nothing else, which is what keeps co-authorship bias
  (measured at 0.147, corrected to 0.0483) from creeping back in. **This is the
  first step that needs `skynet`**, and it is the cheap half: ~30 short authoring
  calls, not a judging pass. It must checkpoint per question and resume from
  partial output, because the server is under contention and a mid-bank failure
  should cost one question, not the bank.
- **Action**: Undergo the verification/tests/validation process for this phase —
  the compiled bank has gold for every question, anchors are disjoint from any
  prior bank, and a resume-from-partial test passes without duplicating a
  question. Once validated, commit stating: `Identity-Schema Transfer (7/9)
  Complete: blind question bank drawn and authored against the identity schema.`

### Step 8: Run the arms and score retrieval — **no LLM**

- **Locations**: `utils/evaluation/experiment_untruncated.py` gains an `identity`
  registration at the same sites `merged` uses; scoring via the existing
  deterministic gold-in-evidence path (`utils/specialists/evalset/score_execution.py`);
  results to `docs/evaluation/identity-2026-08-<dd>/`.
- **Rationale**: This produces the headline number, and it produces it with **no
  language model in the loop**, so it is byte-reproducible and unblocked by
  server contention. Two arms, the same pair EXP-2026-08-009 used so the
  comparison is already calibrated: the schema-derived generic primitives, and
  the deterministic template cascade — which on this domain is expected to fail
  broadly, because 19 of its 25 templates are MITRE-specific by C-010's own
  count. That contrast *is* the portability measurement. Deterministic retrieval
  scoring also means the T2 (id-scheme), T3 (direction) and T6 (abstention)
  readings all land here rather than waiting on the judge.
- **Action**: Undergo the verification/tests/validation process for this phase —
  the run is re-run once and confirmed byte-identical excluding clock readings,
  per-category retrieval is broken out with the same-label-both-ends triples
  isolated, and the id-scheme report records how many properties learned as
  *open*. Once validated, commit stating: `Identity-Schema Transfer (8/9)
  Complete: both arms run against the identity schema, retrieval scored
  deterministically.`

### Step 9: Judge, record, and close the loop — **LLM-gated, resumable**

- **Locations**: judging via the existing golden-eval judge stage;
  `docs/research/experiments/EXP-2026-08-011-identity-schema-transfer/`
  (`RESULTS.md`, `data/metrics.json`, `data/POINTERS.md`, `figures/`,
  `ISSUES.md`); `docs/research/CLAIMS.md` (C-010, C-014);
  `docs/research/OPEN_QUESTIONS.md`; `docs/changelog.jsonl`.
- **Rationale**: Correctness needs the judge, and judging is the expensive half —
  EXP-2026-08-009 needed three grading attempts at 32,768 tokens on its largest
  answers. It runs last, can run overnight, and must resume from persisted
  judgments so contention costs a cell rather than the pass. Note the sidecar
  discipline that has bitten before: suffixed judgment files sitting beside their
  inputs get re-consumed on a later pass unless every variant is excluded. The
  record steps are not optional bookkeeping — a number that exists only in a chat
  log does not exist, and every figure must regenerate from `metrics.json`.
  C-010 gets its status re-examined against a runtime measurement rather than a
  code reading, whichever way the number falls.
- **Action**: Undergo the verification/tests/validation process for this phase —
  `make validate-research` passes, every reported metric appears in
  `metrics.json`, figures regenerate from a command, and `supports_claims`
  round-trips against `CLAIMS.md`. Once validated, commit stating:
  `Identity-Schema Transfer (9/9) Complete: EXP-2026-08-011 reported; C-010
  re-examined against a measurement instead of an audit.`

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Experiment record | Pre-registered protocol, results, metrics, figures, issues | `docs/research/experiments/EXP-2026-08-011-identity-schema-transfer/` |
| Catalog reader | Parses the two ReliaQuest CSVs into a normalized declared-schema artifact, recording its own truncation | `utils/kg_builder/catalog/reader.py`, `declared.py` |
| **Catalog reader tests** | Pin 72 node types / 21 edge labels / 60 triples / 779 + 118 attributes; assert truncation flag; assert `ENTRA_LICENCE`+`ENTRA_LICENSE` both survive | `utils/kg_builder/catalog/tests/test_reader.py` |
| Declared-schema builder | `build_declared_schema()` beside the existing scan-based builder; observed-vs-declared facet provenance | `utils/specialists/schema/build.py`, `registry.py` |
| **Declared-schema tests** | Build a `DatasetSchema` from a small fixture catalog; assert id schemes report `undetermined`, not a false match | `utils/specialists/schema/tests/test_declared.py` |
| **Isolation tests** | Pin that `load_source_cards('data')` == `{attack, capec}` and `discover_datasets('data')` excludes `identity` | `utils/specialists/tests/test_identity_isolation.py` |
| Synthetic tenant generator | Seeded, deterministic emitter of a catalog-conformant tenant with planted attack paths and mixed id shapes | `utils/kg_builder/synthetic/generator.py`, `spec.py`, `paths.py` |
| **Generator tests** | Conformance (every edge matches a declared triple), determinism (same seed → byte-identical), count bands, planted-path presence | `utils/kg_builder/synthetic/tests/test_generator.py` |
| Identity source card + overlay | Derived schema half plus hand-authored connection / safety / provenance / entity descriptions | `data-identity/source_cards/identity.json`, `overlays/identity.overlay.json` |
| Separation script | Proves the ATT&CK and CAPEC stores are untouched by the identity load | `scripts/identity_separation.py` |
| Spec-derived gold bank | Gold computed from the generator blueprint, never by querying the loaded graph | `utils/specialists/evalset/identity_gold.py` |
| **Gold cross-check tests** | Spec-derived gold agrees with a direct graph read on a sampled subset; disagreement fails loudly | `utils/specialists/evalset/tests/test_identity_gold.py` |
| Question bank wiring | Draws, authors and compiles a blind bank against the identity dataset; checkpointed and resumable | `utils/specialists/evalset/identity_bank.py` |
| Arm registration | `identity` registered at the same sites `merged` uses, isolated by data dir and store URI | `utils/evaluation/experiment_untruncated.py` |
| Run + judgment artifacts | Per-question answers, judgments, metrics, referenced by relative path + SHA-256 | `docs/evaluation/identity-2026-08-<dd>/` |
| Ledger updates | C-010 and C-014 re-examined; crosswalk follow-on filed | `docs/research/CLAIMS.md`, `OPEN_QUESTIONS.md` |
| Changelog entries | One per step, nine total | `docs/changelog.jsonl` |

---

## 5. What this plan does not do

- It does not build the ATT&CK ↔ identity-edge crosswalk, and therefore does not
  attempt a no-shared-key federation claim. Filed as a follow-on.
- It does not touch the Black Basta RAG kit. That corpus is a baseline exhibit
  for a different argument and shares no entities with anything here.
- It does not promote the identity source into the routed source set. Doing so
  would alter arms that are already measured.
- It does not claim anything about detection quality. The measurement is schema
  navigation — query construction, direction resolution, evidence reading and
  abstention — on instances that are synthetic by necessity and labelled as such.
