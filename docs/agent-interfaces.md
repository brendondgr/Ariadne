# Agent Interface Contracts

Ariadne's pipeline — planner → source-specific specialists → federation →
synthesis — is stitched together at four boundaries. Those boundaries, not
the components' internals, are what an external consumer integrates against:
each is a pure, JSON-serialisable dataclass with a `to_dict()` (and usually
`from_dict()`) pair, frozen since Wk 10–11 and guarded by a dedicated
contract test in `utils/specialists/tests/test_seams.py`. This document describes the wire
shape of each seam, the invariant each seam test enforces, and what a
consumer may safely depend on versus must not assume.

All four contracts are declared integration-frozen in `docs/specialist_agents.md`:

> Changes to these shapes require updating the seam tests deliberately.

That is the change policy for everything below; see [Change policy](#change-policy).

## Overview

```
Plan (planner output)
  │  Seam 1 — Plan → SpecialistTask      (SpecialistTask.from_sub_question)
  ▼
SpecialistTask  ──►  Specialist.run(task)
  │  Seam 2 — Specialist → SpecialistResult   (emit_record / check_contract)
  ▼
SpecialistResult × N (one per sub-question; each carries EvidenceRecord + Provenance)
  │  Seam 3 — results → FederatedEvidence   (bundle_evidence)
  ▼
FederatedEvidence  ──►  synthesize(evidence, config)
  │  Seam 4 — FederatedEvidence → SynthesizedAnswer   (verify_answer)
  ▼
SynthesizedAnswer (claims, citations, verification, edges)  ──►  API / CLI
```

| Seam | Producer | Consumer | Contract type(s) | Guarding test(s) |
|------|----------|----------|-------------------|------------------|
| 1. Plan → SpecialistTask | Planner (`Plan.sub_questions`) | Specialist, via `SpecialistRouter` | `SpecialistTask` | `test_seam_plan_to_task_preserves_every_field` |
| 2. Specialist → SpecialistResult | Specialist (`Specialist.run`) | Federation (`join_index`), Synthesis | `SpecialistResult`, `EvidenceRecord`, `Provenance`, `EvaluatorTrace` | `test_seam_result_requires_complete_provenance`, `test_seam_gremlin_join_values_are_attack_taxonomy_only` |
| 3. results → FederatedEvidence | `SpecialistRouter.run_plan()` (via `bundle_evidence`) | Synthesis, API/CLI | `FederatedEvidence` | `test_seam_partial_rule_single_source_of_truth`, `test_seam_cli_and_api_bundle_through_the_shared_helper` |
| 4. FederatedEvidence → SynthesizedAnswer | `synthesize()` / `verify_answer()` | API response, CLI, web UI | `SynthesizedAnswer`, `Claim`, `Citation`, `Abstention`, `Conflict`, `ClaimVerdict`, `VerificationReport`, `SynthesisEdge` | `test_seam_synthesis_claims_resolve_to_retrieved_records`, `test_seam_synthesis_empty_source_becomes_abstention_with_query_proof` |

All four contracts are pure dataclasses in `utils/specialists/contracts.py`,
`utils/specialists/federation.py`, and `utils/synthesis/contracts.py`. A
separate envelope, `utils/orchestration/state.py` (`PipelineState` /
`PlanningState` / `SynthesisState`), wraps these same shapes for the LangGraph
orchestration but never redefines them — a consumer reading the SSE/API wire
format never sees the envelope, only the `to_dict()` output of the contracts
below.

---

## Seam 1: Plan → SpecialistTask

The planner emits a `Plan` whose `sub_questions` are `SubQuestion` objects.
`SpecialistTask.from_sub_question()` (`utils/specialists/contracts.py`)
adapts one `SubQuestion` into the shape a specialist consumes. The adapter is
duck-typed — it reads `id`, `source`, `text`, `entities`, `limits.to_dict()`,
`join_key`, `rationale` off anything exposing them via `getattr()`, without
importing the planner package.

### Fields

| Field | Type | Required | Serialization notes |
|-------|------|----------|----------------------|
| `sub_question_id` | `str` | Yes | Always present |
| `source` | `str` | Yes | Always present |
| `text` | `str` | Yes | Always present |
| `entities` | `tuple[str, ...]` | No (default `()`) | Serialized as a list; always present, may be empty |
| `limits` | `dict[str, int]` | No (default `{}`) | Normalized to exactly `max_traversal_depth`, `max_result_rows`, `query_timeout_ms` with `int` coercion (missing keys become `0`); always present |
| `join_key` | `str \| None` | No (default `None`) | Always present, including when `None` |
| `seed_ids` | `tuple[str, ...]` | No (default `()`) | Serialized as a list; always present, may be empty |
| `rationale` | `str` | No (default `""`) | Always present |

No field is omitted when empty on this contract — every key is always
present in `to_dict()`.

### Limit accessors

`SpecialistTask` exposes three accessors specialists use instead of reading
`limits` directly, each falling back to a conservative default only when the
card-provided bound is absent or zero:

| Accessor | Fallback default |
|----------|-------------------|
| `max_rows()` | `1000` |
| `max_depth()` | `3` |
| `timeout_ms()` | `5000` |

### Frozen invariants

- Every `SubQuestion` field survives the conversion losslessly, including
  `seed_ids` passed through as-is and `limits` matching
  `sub_question.limits.to_dict()` exactly.
  (`test_seam_plan_to_task_preserves_every_field`)
- The limit accessors read the card-provided bounds when present — they do
  not silently substitute the fallback default over a real, non-zero card
  value. (`test_seam_plan_to_task_preserves_every_field`)

### Consumer guidance

**May rely on:**
- Exact field preservation across `to_dict()` / `from_dict()` round trips.
- Every key listed above is always present, even when the underlying value
  is empty, `None`, or zero.

**Must not assume:**
- That `limits` is populated — use `max_rows()` / `max_depth()` /
  `timeout_ms()` rather than reading the dict directly.
- That `entities` or `seed_ids` is non-empty; both default to `()`.

---

## Seam 2: Specialist → SpecialistResult

A specialist's `run(task)` returns a `SpecialistResult`
(`utils/specialists/contracts.py`) built from zero or more `EvidenceRecord`s,
each carrying a `Provenance`. Records are constructed via `emit_record()` and
graded by the deterministic gate in `check_contract()` / `result_conforms()`
(`utils/specialists/evidence.py`) before the result ships — this is one of
the two non-negotiable deterministic gates in the pipeline (no LLM
involved).

### SpecialistResult fields

| Field | Type | Required | Serialization notes |
|-------|------|----------|----------------------|
| `task` | `SpecialistTask` | Yes | Nested `to_dict()` |
| `query` | `str` | No (default `""`) | Always present |
| `records` | `list[EvidenceRecord]` | No (default `[]`) | Each via `to_dict()`; always present |
| `record_count` | `int` | — (derived) | Not a dataclass field; computed as `len(records)` only in `to_dict()` |
| `summary` | `str` | No (default `""`) | Always present |
| `traces` | `list[EvaluatorTrace]` | No (default `[]`) | Each via `to_dict()`; always present |
| `ok` | `bool` | No (default `False`) | Always present |
| `partial` | `bool` | No (default `False`) | Always present |
| `error` | `str \| None` | No (default `None`) | Always present, including when `None` |
| `join_values` | `list[str]` | — (derived) | Not a dataclass field; the distinct, order-preserving union of every record's `join_values`, computed only in `to_dict()` (via the `join_values()` method) |

### EvidenceRecord fields

`primary_id`, `id_scheme`, `label`, and `name` have no dataclass default —
the constructor requires all four. The deterministic gate (below) is looser:
a record is valid so long as *either* `primary_id` or `name` is non-empty,
not both.

| Field | Type | Required (constructor) | Serialization notes |
|-------|------|--------------------------|----------------------|
| `primary_id` | `str` | Yes (no default) | Join-relevant identifier (e.g. a `T`-number or `CAPEC-N`); always present, may be serialized as `""` |
| `id_scheme` | `str` | Yes (no default) | Naming scheme, e.g. `"attack-id"`; always present |
| `label` | `str` | Yes (no default) | Entity type, e.g. `"Technique"`; always present |
| `name` | `str` | Yes (no default) | Human-readable name; always present |
| `properties` | `dict[str, Any]` | No (default `{}`) | Deep-copied on serialize; always present. From `describe` this carries the node's **whole** property set (no allow-list) |
| `related` | `list[dict[str, Any]]` | No (default `[]`) | Lightweight adjacent-record dicts; always present. Empty on a `describe` record (which carries facet counts, not neighbours) |
| `join_values` | `tuple[str, ...]` | No (default `()`) | Serialized as a list; always present, may be empty |
| `provenance` | `Provenance \| None` | No (default `None`) | Nested `to_dict()` or `null`; always present as a key |
| `facets` | `list[dict[str, Any]]` | No (default `[]`) | The `describe` facet block: adjacent-node counts grouped by relationship/direction/neighbour label, each `{"rel", "direction", "label", "count"}`; empty for template records. Always present as a key |

### Provenance fields

All six fields are required with no default — this is the audit trail
behind one record.

| Field | Type | Notes |
|-------|------|-------|
| `source` | `str` | Human-readable dataset name, e.g. `"MITRE ATT&CK Enterprise"` |
| `dataset` | `str` | Registry dataset key, e.g. `"attack"` |
| `backend` | `str` | `"neo4j"` or `"gremlin"` |
| `query` | `str` | The exact validated query that produced the record |
| `record_id` | `str` | Backend node/edge id |
| `timestamp` | `str` | ISO-8601 capture time |

### EvaluatorTrace fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `step` | `str` | Yes (no default) | See the step vocabulary below |
| `ok` | `bool` | Yes (no default) | Pass/fail at this step |
| `reasons` | `list[str]` | No (default `[]`) | Always present |
| `detail` | `dict[str, Any]` | No (default `{}`) | Always present |

The step vocabulary, verified against every construction site: the six loop
checkpoints `"intake"`, `"resolve"`, `"gate"`, `"execute"`, `"assess"`,
`"normalize"` (`utils/specialists/base.py`), plus two refusal/skip traces
that replace the loop when it never runs — `"boundary"` (schema-boundary
refusal: the task names an entity the card does not model; ok, zero records,
no query executed) and `"dependency"` (federation skipped a consumer whose
producer yielded no join values;
`utils/specialists/federation.py` `dependency_skip_result`), and one
observation trace — `"anchor"` (the question named more than one entity and the
specialist declined to choose; `detail.ambiguous_candidates` carries the
`(id, name)` pairs, which `synthesis/composer.py::abstention_for` renders as
*"did you mean …?"* rather than guessing). The `"gate"`
trace repeats per retry attempt, carrying the attempt number, template name,
validated query, and injected caps in `detail`. Per-step timing (`timing_ms`)
rides `detail` on the gate/execute/assess/normalize traces.

### The deterministic contract gate

`check_record()` (`utils/specialists/evidence.py`) flags a record as a
contract violation if **any** of:

1. `primary_id` and `name` are both empty.
2. `id_scheme` is empty.
3. `label` is empty.
4. `provenance` is `None`.
5. `provenance` is present but any of `source`, `dataset`, `backend`,
   `query`, `record_id`, `timestamp` is falsy.

`check_contract(records)` concatenates violations across a list;
`result_conforms(result)` is `True` iff that list is empty. Nothing in the
type system prevents a specialist from constructing a non-conforming
record — the gate is a runtime check the specialist calls before it ships a
result, not a dataclass-level guarantee.

### ATTACK-only join values (Gremlin)

The Gremlin normalizer (`utils/specialists/gremlin/normalizer.py`) only
populates `EvidenceRecord.join_values` from `MAPS_TO` edges whose
`TaxonomyEntry` sits in the `ATTACK` taxonomy. A CAPEC pattern that maps to
both an ATT&CK technique and a WASC entry surfaces the WASC entry in
`related` — never in `join_values`.

### Frozen invariants

- A record missing `provenance` fails `check_contract`; `result_conforms()`
  returns `False`. (`test_seam_result_requires_complete_provenance`)
- Gremlin `MAPS_TO` results over mixed taxonomies filter `join_values` to
  ATT&CK ids only — every value starts with `"T"`; non-ATTACK taxonomy
  entries (e.g. WASC) survive only in `related`.
  (`test_seam_gremlin_join_values_are_attack_taxonomy_only`)

### Consumer guidance

**May rely on:**
- If `result.ok` is `True`, every record in `result.records` has complete,
  non-null provenance and a non-empty `primary_id` or `name`.
- `join_values` (on both the record and the result) contain only canonical
  ATT&CK taxonomy identifiers — no leakage from other taxonomies.

**Must not assume:**
- That `records` is non-empty — a clean `ok=True` result can have zero
  records (see the Seam 4 abstention behavior).
- That `primary_id` is globally unique across sources.
- That `join_values` is deduplicated in record-level order beyond what the
  underlying edges produced, or globally ordered.

---

## Seam 3: SpecialistResult list → FederatedEvidence

`SpecialistRouter.run_plan()` (`utils/specialists/federation.py`) dispatches
every sub-question to its specialist in dependency order and bundles the
results through `bundle_evidence()` — the **only** place the `partial` flag
is computed. The router, the CLI, and the API all route through this one
helper so their degradation semantics cannot drift.

### Fields

| Field | Type | Required | Serialization notes |
|-------|------|----------|----------------------|
| `request` | `str` | Yes | Always present |
| `results` | `list[SpecialistResult]` | No (default `[]`) | Each via `to_dict()`; always present |
| `unsupported` | `list[dict[str, Any]]` | No (default `[]`) | Copied from `plan.unsupported`; always present |
| `skipped` | `list[dict[str, Any]]` | No (default `[]`) | Reasons for non-execution (e.g. no specialist for a source); always present |
| `partial` | `bool` | No (default `False`) | Always present; in production this is always set explicitly by `bundle_evidence()` — see rule below |
| `sequencing` | `list[dict[str, Any]]` | No (default `[]`) | Dependent-sequencing audit trail; always present, may be empty |
| `join_index` | `dict[str, list[dict[str, str]]]` | — (derived) | Not a dataclass field; computed only in `to_dict()` |
| `cross_source_join_values` | `list[str]` | — (derived) | Not a dataclass field; computed only in `to_dict()` |

`join_index()` maps each join value to a list of `{"source", "primary_id",
"name"}` entries — this is the synthesis spine: a join value carried by two
different sources is a candidate cross-source correlation.
`cross_source_join_values()` returns the sorted list of join values present
under 2+ distinct sources.

### The partial rule (single source of truth)

`bundle_evidence()` sets `partial = True` iff **any** of:

- `plan.partial` is `True`.
- `plan.unsupported` is non-empty.
- `skipped` is non-empty.
- any result has `ok is False` or `partial is True`.

Otherwise `partial = False`. This exact boolean expression exists in exactly
one place in the codebase (`federation.bundle_evidence`) — the CLI and API
never recompute it, they call through the shared helper.

### status_and_exit()

`status_and_exit()` (`utils/specialists/federation.py`) is the one
status/exit-code rule for every pipeline entry point:

| Condition | Status | Exit code |
|-----------|--------|-----------|
| No source cards present | `"no_sources"` | `2` |
| `mode="plan"` and `plan.partial` is `True` | `"partial"` | `1` |
| `mode="query"` and `evidence.partial` is `True` | `"partial"` | `1` |
| Otherwise | `"answered"` | `0` |

### Dependent-sequencing audit trail

Each entry in `sequencing` corresponds to a consumer sub-question that was
seeded from, or skipped because of, a producer's join values. Only
dependent sub-questions get an entry — independent ones do not appear.

| Key | Type | Notes |
|-----|------|-------|
| `consumer` | `str` | Consumer sub-question id |
| `producer` | `str` | Producer sub-question id |
| `seed_count` | `int` | Number of seed ids harvested from the producer |
| `truncated` | `bool` | `True` if seeds were capped by the consumer's row limit |
| `skipped` | `str \| None` | `None` if the consumer ran; a reason string if it was skipped (producer not run, producer failed, or producer returned no join values) |

### Frozen invariants

- The partial rule is the single source of truth and exists only in
  `bundle_evidence()`; a clean bundle (no failures/unsupported/skipped)
  yields `partial=False`, `status="answered"`, exit `0`; any one failure,
  partial result, skip, or unsupported plan part yields `partial=True`,
  `status="partial"`, exit `1`; no source cards yields `status="no_sources"`,
  exit `2`. (`test_seam_partial_rule_single_source_of_truth`)
- Both the CLI and the API bundle through the shared helper — the literal
  partial-rule expression appears nowhere else in the codebase.
  (`test_seam_cli_and_api_bundle_through_the_shared_helper`)

### Consumer guidance

**May rely on:**
- `partial` is computed by one deterministic rule; a consumer holding the
  plan and the results can predict it without re-deriving federation logic.
- `join_index` is complete and unfiltered by synthesis — it reflects every
  join value across every result, not just the ones synthesis later uses.
- `cross_source_join_values` is sorted and deduplicated.

**Must not assume:**
- That `results` is keyed or ordered by join value — it is a flat list
  (group by `result.task.source` via `by_source()` if source grouping is
  needed).
- That `sequencing` has an entry for every sub-question — only dependent
  ones appear.

---

## Seam 4: FederatedEvidence → SynthesizedAnswer

`synthesize(evidence, config)` (`utils/synthesis/factory.py`) composes a
draft `SynthesizedAnswer` from `FederatedEvidence`, then `verify_answer()`
(`utils/synthesis/verifier.py`) grades every claim against the retrieved
records and reconciles cross-source conflicts before the answer is
considered final. `verification` is `None` only on an unverified draft; the
API seam and golden suites only ever render verified answers.

### SynthesizedAnswer — dataclass fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `request` | `str` | Yes | |
| `headline` | `str` | No (default `""`) | |
| `narrative` | `str` | No (default `""`) | LLM-composed or deterministically assembled prose surface |
| `claims` | `list[Claim]` | No (default `[]`) | |
| `abstentions` | `list[Abstention]` | No (default `[]`) | |
| `notes` | `list[str]` | No (default `[]`) | |
| `composer` | `str` | No (default `"deterministic"`) | `"deterministic"` \| `"llm"` |
| `fallback_reason` | `str \| None` | No (default `None`) | Set when the LLM path fell back |
| `verification` | `VerificationReport \| None` | No (default `None`) | `None` on an unverified draft |
| `edges` | `list[SynthesisEdge]` | No (default `[]`) | Provenance-exact relationships for the network plot, derived during verification; empty on an unverified draft |

### SynthesizedAnswer — actual `to_dict()` wire shape

The serialized JSON is **not** a 1:1 mirror of the dataclass fields above —
`to_dict()` augments `claims` with each claim's verdict and adds a
`rendered_claims` key that is not a dataclass field at all:

| Wire key | Derivation |
|----------|------------|
| `request`, `headline`, `narrative`, `abstentions`, `notes`, `composer`, `fallback_reason`, `edges` | Direct field serialization, as above |
| `claims` | Each entry is `claim.to_dict()` **plus a `"verdict"` key**: `verdict.to_dict()` if a verdict exists at that claim's index, else `null` |
| `rendered_claims` | **Not a dataclass field.** The subset of `claims` that are verified *and* supported, each `claim.to_dict()` plus a `"contested"` key when the verdict's `contested` tuple is non-empty (omitted otherwise) |
| `verification` | `verification.to_dict()` or `null` |

A consumer parsing the wire format should read `rendered_claims` for the
prose-safe surface and treat `claims[i].verdict` as the audit trail for the
full claim list (including cut/unsupported claims).

### Claim fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `text` | `str` | Yes | |
| `citations` | `tuple[Citation, ...]` | No (default `()`) | Serialized as a list |
| `entity_ids` | `tuple[str, ...]` | No (default `()`) | Serialized as a list |
| `kind` | `str` | No (default `"fact"`) | `"fact"` (single-source) \| `"correlation"` (cross-source) |
| `sub_question_id` | `str` | No (default `""`) | Originating sub-question, when known |

### Citation fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `source` | `str` | Yes | Registry dataset key, e.g. `"attack"` |
| `primary_id` | `str` | Yes | The cited record's join-relevant id, e.g. `"T1047"` |
| `record_id` | `str` | No (default `""`) | Backend node/edge id from provenance |

### Abstention fields

Emitted when a specialist ran cleanly (`ok=True`) and returned zero
records — the correct answer is the absence itself, proven by the exact
query executed.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `sub_question_id` | `str` | Yes | |
| `source` | `str` | Yes | |
| `statement` | `str` | Yes | e.g. `"the sources don't establish this"` |
| `query` | `str` | Yes | The exact query that was executed (proof of absence) |

### Conflict fields

A cross-source contradiction: two sources both carry a canonical join value
but assert incompatible facts about it. Both underlying records are
genuinely retrieved, so a conflict never cuts a claim — it flags the claim
`contested` instead.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `join_value` | `str` | Yes | |
| `kind` | `str` | Yes | `"name"` (different canonical name) \| `"status"` (deprecated/revoked vs. current) |
| `sources` | `tuple[str, ...]` | No (default `()`) | Serialized as a list |
| `values` | `dict[str, str]` | No (default `{}`) | Maps source → asserted value |
| `authoritative_source` | `str \| None` | No (default `None`) | Scheme owner (ATT&CK for T-ids, CAPEC for CAPEC-ids), or `None` when neither is canonically authoritative — surfaced, never used to silently pick a winner |
| `detail` | `str` | No (default `""`) | |

### ClaimVerdict fields

| Field | Type | Required | Serialization notes |
|-------|------|----------|-----------------------|
| `verdict` | `str` | Yes | `"supported"` \| `"unsupported"`; always present |
| `reasons` | `list[str]` | No (default `[]`) | Always present |
| `contested` | `tuple[str, ...]` | No (default `()`) | Conflicted join values this claim touches; **omitted from `to_dict()` entirely when empty** — a conflict-free claim's verdict JSON is byte-identical to the pre-reconciliation shape |

### VerificationReport

Dataclass fields:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `verdicts` | `list[ClaimVerdict]` | No (default `[]`) | |
| `repaired_abstentions` | `int` | No (default `0`) | Count of abstentions the verifier added because the composer omitted them |
| `conflicts` | `list[Conflict]` | No (default `[]`) | Cross-source contradictions detected during reconciliation |

`to_dict()` additionally serializes the report's derived metrics, which are
always present regardless of the dataclass having no corresponding field:

| Wire key | Derivation |
|----------|------------|
| `claim_count` | `len(verdicts)` |
| `supported_count` | Count of verdicts with `verdict == "supported"` |
| `unsupported_count` | `claim_count - supported_count` |
| `unsupported_claim_rate` | `unsupported_count / claim_count`, or `0.0` if there are no verdicts |
| `repaired_abstentions` | Direct field |
| `ok` | `True` iff `unsupported_count == 0` |
| `conflicts`, `conflict_count` | **Only present when `conflicts` is non-empty** — both are omitted together on a single-source or fully-consistent answer, so the payload stays byte-identical to a pre-reconciliation build |

### SynthesisEdge fields

Provenance-exact relationships for the per-answer network plot, derived
mechanically from the join index during verification and pruned to
endpoints that survive in supported claims.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `source_id` | `str` | Yes | e.g. `"CAPEC-555"` |
| `target_id` | `str` | Yes | e.g. `"T1021"` |
| `rel` | `str` | No (default `"mapsTo"`) | `"mapsTo"` \| `"mitigatedBy"` |

### Accessors

- `rendered_claims()` — claims that are both verified and supported. Returns
  `[]` if `verification is None`.
- `flagged_claims()` — `(claim, verdict)` pairs for unsupported claims, the
  audit trail for what the verifier cut. Returns `[]` if `verification is
  None`.

### Frozen invariants

- Non-empty evidence renders at least one claim; every rendered claim has at
  least one citation; every cited `primary_id` resolves to a record actually
  present in the federated evidence; `unsupported_claim_rate` is `0.0` for a
  fully-supported answer.
  (`test_seam_synthesis_claims_resolve_to_retrieved_records`)
- A specialist result with zero records but `ok=True` produces exactly one
  abstention, and `abstention.query` equals the exact query that was
  executed (never a placeholder).
  (`test_seam_synthesis_empty_source_becomes_abstention_with_query_proof`)

### Consumer guidance

**May rely on:**
- `rendered_claims` (wire) contains only verified, supported claims, each
  with at least one citation, and every citation resolves to a record in the
  corresponding `FederatedEvidence`.
- `conflicts` / `conflict_count` are present iff cross-source contradictions
  were detected; a claim's `contested` field is accurate whenever
  `verification` is present.

**Must not assume:**
- That `claims` (the full list, wire or dataclass) is ordered by importance
  or confidence.
- That `verification` is present — check for `null` before reading any
  verification metric.
- That `edges` is a complete network graph — it contains only
  provenance-exact relationships that survive verification, not every
  relationship in the underlying graphs.

---

## Change policy

These four contracts are declared **integration-frozen** in
`docs/specialist_agents.md`:

> Changes to these shapes require updating the seam tests deliberately.

In practice this means: a new field, a changed default, an altered
omit-when-empty rule, or a changed derivation (e.g. how `partial` or
`join_values` is computed) must land alongside an update to the matching
test in `utils/specialists/tests/test_seams.py`, and — for seam 4 — the
downstream payload-shape assertions in `utils/synthesis/tests/test_verifier.py`
that pin the exact wire format (`test_contested_claim_stays_supported_and_rendered`
proves `verification.conflict_count`, `verification.conflicts[].join_value`,
and `claims[].verdict.contested` serialize as expected;
`test_conflict_free_answer_has_no_conflicts_and_identical_payload` proves
`conflicts`, `conflict_count`, and `contested` are absent from the payload
when there is nothing to report). A silent shape change that does not touch
these tests is a regression, not a feature — the tests exist specifically to
make drift between the router, the CLI, and the API impossible.

## Key files

| Concern | Location |
|---------|----------|
| Seam 1 contract (`SpecialistTask`) | `utils/specialists/contracts.py` |
| Seam 2 contracts (`SpecialistResult`, `EvidenceRecord`, `Provenance`, `EvaluatorTrace`) | `utils/specialists/contracts.py` |
| Deterministic evidence gate (`emit_record`, `check_contract`, `result_conforms`) | `utils/specialists/evidence.py` |
| ATTACK-only join-value filtering (Gremlin) | `utils/specialists/gremlin/normalizer.py` |
| Seam 3 contract (`FederatedEvidence`), partial rule, sequencing, `SpecialistRouter` | `utils/specialists/federation.py` |
| Seam 4 contracts (`SynthesizedAnswer`, `Claim`, `Citation`, `Abstention`, `Conflict`, `ClaimVerdict`, `VerificationReport`, `SynthesisEdge`) | `utils/synthesis/contracts.py` |
| Synthesis compose+verify entry point | `utils/synthesis/factory.py` |
| Verification + reconciliation | `utils/synthesis/verifier.py`, `utils/synthesis/reconcile.py` |
| All four seam contract tests | `utils/specialists/tests/test_seams.py` |
| Integration-frozen declaration | `docs/specialist_agents.md` |
| Related: conflicting-evidence detail | `docs/conflict-detection.md` |
| Orchestration envelope (wraps, never redefines, these contracts) | `utils/orchestration/state.py` |
