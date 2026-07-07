# Plan: Analyst-Facing Claim Table + Per-Answer Network Plot (Deliverable #4)

## 1. Introduction

Deliverable #4 (the "synthesis and reporting agent" output promised in
`docs/purpose.md`, `docs/proposal/proposal.md`, and `docs/goals.md`) says every
answer should return a *table* and a *compact CAPEC–ATT&CK–mitigation network
plot* alongside the verified claims. Today the synthesis layer produces the
auditable substance — `Claim` objects with `citations`, `entity_ids`, `kind`,
and per-claim `verdict`, all already serialized by
`SynthesizedAnswer.to_dict()` (`utils/synthesis/contracts.py`) and streamed to
the UI under `answer.synthesis` — but the workbench renders only prose. The
table and network plot are the missing *presentation* on top of substance that
already exists.

This plan delivers both in two waves. **Option A** builds the table and the
network plot entirely in the web frontend by inferring edge structure from the
data already in the payload (`joinPairs` for CAPEC↔ATT&CK, same-claim proximity
for technique→mitigation). **Option B** then upgrades the plot to be
provenance-*exact* by having the synthesis composer emit explicit typed edges,
so the topology is proven rather than inferred. A→B is incremental, not rework:
everything except the single `deriveEdges` step is shared, and the A phase
pre-pays B's integration cost by plumbing `entity_ids` through the adapter and
isolating edge-derivation behind one function. The existing whole-graph renderer
(`react-force-graph-2d` + the pure `toForceGraphData` transform in
`web/lib/graph.ts` + `GraphCanvas`) is reused as-is by shaping the per-answer
subgraph as a `GraphPayload`.

## 2. Gaps & Unanswered Questions

- **Edge direction in Option A** — a multi-hop `correlation` claim's `chips` are
  a flat list, so inferred edges can occasionally draw a triangle where a chain
  is meant. *Assumption:* acceptable for A because the plot is explicitly
  labelled "derived"; B makes it exact. We must NOT present A's topology as
  ground truth (auditability is the product's whole point).
- **Which claims feed the plot** — *Assumption:* only verified-supported claims
  (`rendered_claims` / `synthesis.claims` after the verifier) become nodes/edges;
  cut ("flagged") claims never appear in the plot. Abstentions are absence, not
  edges — surfaced as a caption count, not nodes.
- **Node typing** — entity type (CAPEC pattern / ATT&CK technique / mitigation)
  is inferred from the citation `source` plus the id prefix (`CAPEC-`, `T####`,
  `M####`). *Assumption:* prefix + source is sufficient; no new backend field
  needed for A. B may add an explicit node role but is not required to.
- **Where Option B edges are built** — the deterministic composer already joins
  on shared identifiers to emit `correlation` claims; that join site is where
  explicit edges are cheapest to emit. *Assumption:* locate it in
  `utils/synthesis/composer.py` during Phase 3; the LLM composer
  (`llm_composer.py`) must produce the same `edges` shape or fall back.
- **Verifier interaction (B)** — edges whose endpoints reference a cut claim
  must be pruned so the plot never shows unverified topology. *Assumption:*
  prune in the verifier pass (or when building the plot) to supported endpoints.
- **Agent Workflow usage** — the task suggests workflows for multi-step work
  *where steps don't depend on one another*. Here the steps are tightly
  sequential (types → adapter → derive → component → wire-in, then backend →
  frontend), and each needs iterative `npm run build` / `pytest` feedback in the
  main loop. *Decision:* implement in-loop; delegate only the read-only
  repository confirmations to Haiku `Explore` subagents where they save time.
  This is a deliberate, stated deviation, not an oversight.

## 3. Hierarchical Step-by-Step Instructions

### Step 0: Worktree & branch setup

- **Locations**: new git worktree `analyst-tables-network-plot` branched from
  local `main`; symlinks per `[[ariadne-worktree-setup]]` — `data/raw`,
  `data/graphs`, `data/processed`, `data/source_cards/{attack,capec}.json`,
  `data/source_cards/overlays`, `.env` from the main checkout.
- **Rationale**: worktrees branch from `origin/main` (behind local `main`); reset
  onto local `main` and symlink gitignored data so backend tests don't silently
  skip. Never `git add -A` in the worktree — only explicit files — to avoid
  symlink/deletion noise in history.
- **Action**: Undergo the verification/tests/validation process for this phase
  (confirm `git status` clean, `uv run python -m pytest utils/synthesis/tests -q`
  collects, `cd web && npm test` runs). No commit — setup only.

### Step 1: Option A — Claim table

- **Locations**: new `web/components/center/ClaimTable.tsx` (renders one row per
  `synthesis.claims` entry: kind badge, entity ids, source(s), claim text +
  provenance chips; optional struck-through `flagged` rows and an abstention
  caption). Wire into `web/components/center/AnswerCard.tsx` (render below
  `SynthesisBlock`, gated on `run.answer.synthesis`). Reuse `ProvenanceChip`,
  Woven Dusk tokens, `SHADOW` from `web/lib/ui`. Add
  `web/lib/__tests__/claimTable.test.ts` if pure helpers are extracted; otherwise
  cover via existing adapter/fixture contract tests.
- **Rationale**: the table needs zero new data — `SynthesisClaimView` already
  carries `text`, `kind`, `chips`. Pure presentation, isolated to `web/`.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`cd web && npm test && npm run lint && npm run build`). Once validated, commit
  to GitHub (no push) stating: Analyst Tables & Network Plot (1/6) Complete:
  added per-answer claim table rendering verified claims from `answer.synthesis`.

### Step 2: Option A — plumb `entity_ids` + edge-derivation seam

- **Locations**: `web/lib/types.ts` (`SynthesisClaimView` gains `entityIds:
  string[]`); `web/lib/adapt.ts` (stop dropping `entity_ids` at the claim
  projection ~line 337 — carry it into `SynthesisClaimView`). New
  `web/lib/synthesisGraph.ts` exposing `deriveEdges(claims, joinPairs, explicit?)`
  and `synthesisToGraphPayload(synthesis, joinPairs): GraphPayload` — nodes from
  citation ids (type by prefix/source), edges from `deriveEdges` in **inference
  mode** (joinPairs → CAPEC↔ATT&CK edges; same-claim `M####`↔`T####` →
  mitigation edges). Update `web/lib/fixtures.ts` + `web/lib/__tests__/adapt.test.ts`
  to assert `entityIds` flows.
- **Rationale**: carrying `entity_ids` now (even before B uses them) means B is a
  composer change + one `deriveEdges` rewrite, with no adapter re-plumbing. The
  `GraphPayload` shape lets us reuse `toForceGraphData` unchanged.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`cd web && npm test && npm run lint && npm run build`; new
  `web/lib/__tests__/synthesisGraph.test.ts` green). Once validated, commit (no
  push) stating: Analyst Tables & Network Plot (2/6) Complete: plumbed entity_ids
  and added the synthesisGraph adapter with inferred edges behind a deriveEdges
  seam.

### Step 3: Option A — network plot component

- **Locations**: new `web/components/center/AnswerNetworkPlot.tsx` — calls
  `synthesisToGraphPayload`, pipes through `toForceGraphData` (`web/lib/graph.ts`),
  renders via existing `GraphCanvas` (`web/components/graph/GraphCanvas.tsx`)
  sized as a compact inline panel; caption labels it "derived" and shows the
  abstention count. Wire into `AnswerCard.tsx` beneath the claim table, gated on a
  non-empty subgraph. Handle the empty/degenerate case (0–1 nodes → hide plot).
- **Rationale**: reusing `GraphCanvas`/`toForceGraphData` means the plot inherits
  the workbench's force-graph styling and per-node color logic with no new render
  engine. The compact plot is the CAPEC–ATT&CK–mitigation subgraph the docs
  promise.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`cd web && npm test && npm run lint && npm run build`; visual check via
  preview tools that the plot renders for a federated fixture run). Once
  validated, commit (no push) stating: Analyst Tables & Network Plot (3/6)
  Complete: added compact per-answer CAPEC–ATT&CK–mitigation network plot reusing
  the force-graph renderer.

### Step 4: Option B — composer emits explicit typed edges

- **Locations**: `utils/synthesis/contracts.py` — new frozen `SynthesisEdge`
  dataclass (`source_id`, `target_id`, `rel`, e.g. `mapsTo` / `mitigatedBy`) with
  `to_dict`/`from_dict`; `SynthesizedAnswer` gains `edges: list[SynthesisEdge]`
  and serializes it in `to_dict()`. `utils/synthesis/composer.py` (deterministic)
  emits edges at the join site that already produces `correlation` claims.
  `utils/synthesis/llm_composer.py` produces the same `edges` shape or falls back
  to the deterministic edges. `utils/synthesis/verifier.py` prunes edges whose
  endpoints reference cut claims. Extend `utils/synthesis/tests/` (composer +
  verifier + contract round-trip) and confirm `api/tests/test_query.py`
  `answer.synthesis` still validates (to_dict passthrough at
  `api/services/query.py:216`).
- **Rationale**: the composer already knows the exact join structure it asserted;
  emitting `edges` there makes the topology provenance-exact and identical to what
  the verifier checked — no frontend guessing.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run python -m pytest utils/synthesis/tests api/tests -q`; full
  `uv run python -m pytest utils/ api/` green). Once validated, commit (no push)
  stating: Analyst Tables & Network Plot (4/6) Complete: synthesis composer now
  emits explicit typed provenance edges, verifier-pruned and serialized in the
  payload.

### Step 5: Option B — frontend consumes explicit edges

- **Locations**: `web/lib/types.ts` — mirror `SynthesisEdge` in the payload type
  and add `edges` to the `SynthesisView` projection. `web/lib/adapt.ts` — project
  explicit `edges` when present. `web/lib/synthesisGraph.ts` — `deriveEdges`
  switches to **explicit mode** when the payload carries edges (falls back to
  inference otherwise); `AnswerNetworkPlot` caption relabels "provenance-exact"
  when explicit edges are used. Update `web/lib/fixtures.ts` +
  `web/lib/__tests__/synthesisGraph.test.ts` to cover both modes.
- **Rationale**: the only change from A is the source of edges; the component,
  nodes, table, and renderer are untouched — the seam designed in Step 2 pays off.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`cd web && npm test && npm run lint && npm run build`; preview check that a
  federated run now shows exact edges). Once validated, commit (no push) stating:
  Analyst Tables & Network Plot (5/6) Complete: frontend renders provenance-exact
  edges from the payload, inference retained as fallback.

### Step 6: Docs, changelog, merge to main

- **Locations**: `docs/structure.md` "Not Yet in Repo" (remove the now-delivered
  tables/figures/network diagrams line, or narrow it to remaining figure types);
  `docs/goals.md` Wk-10 row note ("tables/figures/diagrams remain UI work" →
  delivered). `docs/changelog.jsonl` — an entry per shipped step (per rule #4).
  Merge the worktree into local `main` per `[[ariadne-concurrent-sessions]]`:
  re-check `git log` (main may have moved), merge, resolve, and re-run the full
  regression; the evalset derived artifacts are untouched by pure UI + a
  passthrough backend field, but confirm no freshness/census test regressed.
- **Rationale**: docs must stop advertising the deliverable as unbuilt; the merge
  discipline keeps main's derived-artifact suites green.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`cd web && npm run build`; `uv run python -m pytest utils/ api/` green on the
  merged `main`). Once validated, commit (no push) stating: Analyst Tables &
  Network Plot (6/6) Complete: docs updated, branch merged to main, full
  regression green.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Claim table component | Per-answer table of verified claims (kind, ids, source, chips) | `web/components/center/ClaimTable.tsx` |
| Synthesis→graph adapter | `deriveEdges` + `synthesisToGraphPayload`; inference then explicit modes | `web/lib/synthesisGraph.ts` |
| Network plot component | Compact CAPEC–ATT&CK–mitigation force-graph reusing `GraphCanvas` | `web/components/center/AnswerNetworkPlot.tsx` |
| AnswerCard wiring | Render table + plot under `SynthesisBlock` | `web/components/center/AnswerCard.tsx` |
| entity_ids plumbing | Carry `entity_ids` into `SynthesisClaimView` | `web/lib/types.ts`, `web/lib/adapt.ts` |
| Explicit edge contract | `SynthesisEdge` + `edges` on `SynthesizedAnswer` | `utils/synthesis/contracts.py` |
| Composer edge emission | Deterministic + LLM composers emit typed edges; verifier prunes | `utils/synthesis/composer.py`, `llm_composer.py`, `verifier.py` |
| Adapter unit tests | Cover inferred + explicit edge derivation, node typing, empty graph | `web/lib/__tests__/synthesisGraph.test.ts` |
| Backend synthesis tests | Edge emission, verifier pruning, to_dict round-trip | `utils/synthesis/tests/` |
| Fixture/adapter contract updates | `entityIds` + `edges` flow through the fixture path | `web/lib/fixtures.ts`, `web/lib/__tests__/adapt.test.ts` |
| Docs + changelog | Update structure.md / goals.md; per-step changelog entries | `docs/structure.md`, `docs/goals.md`, `docs/changelog.jsonl` |
