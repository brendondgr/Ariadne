# Binding consistency and direction resolution — a portable fix

**Created:** 2026-08-18. **Mode:** direct on `main`, no worktree.
**Addresses:** the `groups` 0.00 / `software` 0.06 blind-holdout categories
(`EXP-2026-08-002` §1 failure mode 1) and the template inner-join defect
(`EXP-2026-08-004` `ISSUES.md`).

## 1. Introduction

The blind holdout lost four questions to a query that cannot match anything.
Asked *"which groups use T1550.002"*, the cascade routes on the word **Group**
([`cypher/builder.py:220`](../../utils/specialists/cypher/builder.py)) and then
binds `$ids` to the task's seed ids regardless of what those ids identify, so
`_group_techniques` emits `WHERE g.attack_id IN ['T1550.002']` — a filter of
*Group* identifiers against a *Technique* identifier. It returns zero rows,
every time, and nothing in the system notices: there is no validator check that
the bound seeds can inhabit the property being filtered, and no `expected_nonempty`
flag on that draft. The development bank only ever asks Group → technique, so
120 questions never touched it.

The narrow repair is to add two reverse-direction branches. This plan does not
do that, because the narrow repair re-authors MITRE knowledge that a different
dataset will not share, and the same defect will arrive again with the first
non-MITRE source. The defect has a portable shape: **routing chose an anchor
label from an entity mention, binding took ids from somewhere else, and no
component owned the question of whether the two agree.** Both halves of that
question are answerable from schema the repository already derives from the
data — `DatasetSchema.triples` gives the legal directions of every edge, and
`build_dataset_schema` computes (then discards) the id→label map that gives each
label's identifier scheme.

So the approach is: **learn id schemes into the schema registry, add one
card-driven consistency check that every builder consults, and let the check
repair the binding by flipping direction when the schema says the reverse edge
exists.** On MITRE that closes `groups` and `software`. On a source nobody has
seen, it degrades honestly — where identifiers are opaque (UUIDs, hostnames) the
check returns `undetermined` and blocks nothing, rather than guessing.

Steps 1–5 are **additive**: they change emitted queries only for task shapes
that today emit a structurally unsatisfiable query or fall through to `describe`.
`freeze/holdout-v1` and every arm figure survive them untouched, and the plan
proves that mechanically rather than asserting it. Step 6 is not additive and is
gated on an operator decision.

## 2. Gaps and unanswered questions

- **Id-scheme learning on opaque identifiers.** A dataset whose ids are UUIDs
  gives every label the same scheme, so label inference from an id is
  impossible. *Assumption*: the checker is three-valued — `consistent`,
  `mismatch`, `undetermined` — and only `mismatch` is actionable. A scheme
  shared by more than one label yields `undetermined`, never a guess. This is
  the same discipline as `AmbiguousAnchor` in the resolver.
- **Repair versus refuse.** When the binding is inconsistent, the system can
  flip the direction (if the schema declares the reverse edge) or fail the draft
  and let the specialist abstain. *Assumption*: repair when the schema licenses
  exactly one repair; fail when it licenses none; treat more than one licensed
  repair as `undetermined` and fail. A failed draft is an honest empty answer
  with the executed query attached — the behaviour the abstention machinery
  already implements — which is strictly better than today's silent zero rows.
- **Learned schemes and the pinned snapshot.** Schemes are derived from
  `data/graphs/*/canonical/nodes.jsonl`, so they inherit the snapshot pin. A
  dataset reload changes them. *Assumption*: acceptable — the registry is
  already built this way and cached per data dir.
- **Whether the template path gets the outer-join fix at all (Step 6).** It
  rewrites query strings the frozen fixture covers, so it costs arm-figure
  comparability against the 2026-07-26 study. **Human intervention is needed to
  answer this question**; Steps 1–5 do not depend on the answer.
- **Which arms are re-run if Step 6 proceeds.** *Assumption pending the above*:
  Arms A and F only — the two the holdout measured and the two quotable in
  October — with B–E and G kept as a labelled generation-1 table.

## 3. Steps

### Step 1 — Learn per-label identifier schemes into the schema registry

- **Locations:** new `utils/specialists/schema/idscheme.py` (`IdScheme`,
  `scheme_of`, `learn_schemes`); `utils/specialists/schema/build.py`
  (`build_dataset_schema` — retain the `id_to_label` map it already computes);
  `utils/specialists/schema/registry.py` (`DatasetSchema.label_id_schemes`,
  `DatasetSchema.labels_for_id`); tests in
  `utils/specialists/schema/tests/test_idscheme.py`.
- **What a scheme is:** the leading literal non-digit prefix plus the shape of
  the remainder (digit runs and separators), longest-prefix-wins on lookup, so
  `TA0001` resolves to Tactic and `T1003` to Technique without either being
  named in code. A scheme observed under more than one label is recorded as
  ambiguous and inferred to no label.
- **Rationale:** this is the one piece of MITRE knowledge that is currently
  hardcoded and is derivable from data. Everything downstream reads from here,
  so a new dataset gets the same machinery for free. No builder changes, so the
  freeze cannot be affected.
- **Portability test:** the test fixture includes a synthetic non-MITRE dataset
  (OCSF-shaped: `Device`, `User`, `Process`, `Finding`, with `dev-…`, `usr-…`
  ids and one opaque-UUID label) proving the learner is not tuned to ATT&CK and
  that the opaque label yields `undetermined`.
- **Action:** run `uv run python -m pytest utils/specialists/schema/tests/`
  and the full specialist suite. Once validated, commit stating:
  *Binding portability (1/7) Complete: Learn per-label id schemes from the
  canonical snapshot into the schema registry.*

### Step 2 — Audit the cascade for binding inconsistencies (read-only)

- **Locations:** new `utils/specialists/audit/binding_audit.py`
  (`audit_bindings`, `BindingFinding`); new
  `utils/specialists/tests/test_binding_audit.py`.
- **What it does:** enumerates the cross-product of seed-id kind × entity scope
  × dataset, drives each combination through `CypherQueryBuilder.build` and
  `GremlinQueryBuilder.build`, and reports every draft whose filtered anchor
  property cannot admit the bound seeds, using Step 1's schemes. Read-only: it
  builds query strings, executes nothing, changes nothing.
- **Rationale:** this converts "the holdout found two" into a complete
  inventory. Fixing the two the blind set happened to surface is exactly the
  co-authoring error the holdout exists to expose. The audit is also the
  regression guard: once fixed, the finding count is asserted at zero.
- **Action:** run the audit, record the inventory in the plan's companion notes
  and in the Step 7 experiment. Once validated, commit stating:
  *Binding portability (2/7) Complete: Add a read-only binding audit that
  enumerates every routing branch and reports unsatisfiable bindings.*

### Step 3 — A schema-driven consistency check in validation

- **Locations:** new `utils/specialists/binding.py`
  (`check_binding`, `BindingVerdict`); `utils/specialists/validation.py`
  (`BaseValidator.validate` — add the binding reason alongside the existing
  structural, read-only, schema and cap reasons);
  `utils/specialists/tests/test_binding_check.py`.
- **Rationale:** the guard is what makes this durable. Today an impossible query
  is indistinguishable from a true empty result; after this, it is a named
  validation failure that the specialist can act on. This is the piece that
  protects a dataset nobody has seen yet, and it is the same failure surface the
  abstention design already relies on.
- **Constraint:** `undetermined` must never fail a draft. The check fires only
  on a positive mismatch.
- **Action:** run the full specialist suite including
  `test_generic_only_isolation.py`, which must pass **with
  `frozen_default_queries.json` unmodified**. Once validated, commit stating:
  *Binding portability (3/7) Complete: Fail a draft whose bound seeds cannot
  inhabit the property it filters, three-valued and schema-driven.*

### Step 4 — Repair by direction, from the declared triples

- **Locations:** new `utils/specialists/direction.py` (`repair_direction`,
  reading `DatasetSchema.label_facets` / `facet_exists`);
  `utils/specialists/cypher/builder.py` (`_group_techniques`,
  `_software_techniques` — bind by resolved anchor rather than by entity
  mention); `utils/specialists/gremlin/builder.py` (the equivalent seeded
  templates); `utils/specialists/tests/test_direction_repair.py`.
- **Rationale:** `facet_exists(anchor, rel, direction)` already answers "does
  this edge run this way in this dataset" from derived triples. A template that
  asks the resolver which end its seeds sit on, and the registry which direction
  is legal, stops encoding the direction the development bank happened to ask.
  The generic branch reached 1.0000 on the blind set by doing exactly this;
  Step 4 gives the template path the same source of truth rather than a second
  hand-written copy of it.
- **Additivity requirement:** the repair fires only where Step 3 reports a
  mismatch — i.e. only where the emitted query was unsatisfiable. No shape that
  currently produces a satisfiable query may change.
- **Action:** run the full specialist suite; `test_generic_only_isolation.py`
  green with the fixture unmodified; the Step 2 audit reports zero findings.
  Once validated, commit stating: *Binding portability (4/7) Complete: Resolve
  seeded template direction from the declared schema, closing the reverse-
  direction gap.*

### Step 5 — Prove additivity and measure both banks

- **Locations:** `utils/evaluation/experiment_untruncated.py`,
  `utils/evaluation/retrieval_coverage.py` (both used as-is);
  outputs under `docs/evaluation/experiments/`.
- **What runs:** reload the live fixtures first
  (`uv run main.py --dataset attack --graph neo4j`, `--dataset capec --graph
  gremlin`), then the paired judge-free retrieval scorer on the 120-question
  development catalogue (must report **0 improved, 0 regressed** — that is
  arm-figure comparability demonstrated, not assumed) and on the 30-question
  blind holdout for the template cascade (0.7688 is the number to beat).
- **Rationale:** the cheap judge-free instrument first, because it catches a
  regression in seconds; and the development run is the one that can only detect
  harm, which is precisely why it must run.
- **Honesty constraint:** any blind figure produced here is a **diagnostic, not
  a headline**. Holdout v1 diagnosed these defects, so a post-fix v1 number is
  co-authored with its own test. The headline blind number must come from
  holdout v2.
- **Action:** record every number in the Step 7 experiment's `metrics.json`
  before quoting it anywhere. Once validated, commit stating: *Binding
  portability (5/7) Complete: Development catalogue shows no regression; blind
  retrieval measured for the repaired cascade.*

### Step 6 — Port the outer join to the templates (gated on §2's open question)

- **Locations:** `utils/specialists/gremlin/builder.py` (`_capec_maps_to`,
  `_cwe_chain`); `utils/specialists/gremlin/normalizer.py` (the folded-shape
  branch already added for the generic bridge); new tag `freeze/arm-baseline-2`;
  `utils/specialists/tests/fixtures/frozen_default_queries_v2.json` captured via
  `git archive` from the new tag; `test_generic_only_isolation.py` extended to
  replay both generations.
- **Rationale:** the same defect and the same fix as `EXP-2026-08-004`, which
  already proved it on the generic path (blind 0.8952 → 1.0000, dev 1.0000 with
  0 regressions). Keeping both fixture generations means the record shows which
  figures belong to which tree, instead of overwriting the evidence that the
  older figures were comparable.
- **Blocked by:** the operator decision in §2. Do not start this step before it.
- **Action:** re-run Arms A and F on both banks per the decision. Once
  validated, commit stating: *Binding portability (6/7) Complete: Outer-join the
  template bridges under a new comparability baseline.*

### Step 7 — Record the experiment

- **Locations:** `make new-experiment SLUG=binding-direction-portability`, then
  `manifest.yaml`, `data/metrics.json`, `RESULTS.md`, `ISSUES.md`;
  `docs/research/CLAIMS.md` (C-001, C-003, C-014),
  `docs/research/OPEN_QUESTIONS.md` (Q1's residue).
- **Rationale:** a number that exists only in a chat log does not exist. The
  audit inventory, the additivity proof, and both retrieval runs are findings and
  belong in the record; so does the fact that the blind figure here is a
  diagnostic.
- **Action:** `make validate-research` must pass. Once validated, commit
  stating: *Binding portability (7/7) Complete: Record the experiment, the
  inventory and the additivity proof, and reconcile the ledgers.*

> **Note on the planner template's push wording:** this repository commits at
> every step and **does not push** — pushing is the operator's call
> (`docs/skills/global-project-rules/SKILL.md` rule 1). Every step above ends at
> a commit.

## 4. Deliverables

| Deliverable | Description | Location |
| --- | --- | --- |
| Id-scheme learner | Derives per-label identifier schemes from the canonical snapshot; ambiguity is recorded, not guessed | `utils/specialists/schema/idscheme.py` |
| Registry extension | `label_id_schemes` / `labels_for_id` on `DatasetSchema` | `utils/specialists/schema/registry.py`, `schema/build.py` |
| Binding checker | Three-valued check that bound seeds can inhabit the filtered property | `utils/specialists/binding.py` |
| Direction repair | Chooses edge direction from declared triples instead of from a hand-written template | `utils/specialists/direction.py` |
| Validator guard | Binding mismatch becomes a named validation failure | `utils/specialists/validation.py` |
| Binding audit tool | Read-only enumeration of every routing branch, reporting unsatisfiable bindings | `utils/specialists/audit/binding_audit.py` |
| Id-scheme tests | Includes a synthetic non-MITRE (OCSF-shaped) dataset and an opaque-id label | `utils/specialists/schema/tests/test_idscheme.py` |
| Binding audit tests | Asserts the inventory, then asserts zero findings after Step 4 | `utils/specialists/tests/test_binding_audit.py` |
| Binding check tests | Consistent / mismatch / undetermined, on both datasets and the synthetic one | `utils/specialists/tests/test_binding_check.py` |
| Direction repair tests | Reverse-direction shapes, plus proof that forward shapes are byte-identical | `utils/specialists/tests/test_direction_repair.py` |
| Retrieval runs | Paired dev-catalogue non-regression and blind-bank measurement | `docs/evaluation/experiments/` |
| Experiment record | Manifest, metrics, results, issues, ledger reconciliation | `docs/research/experiments/EXP-2026-08-005-…/` |
