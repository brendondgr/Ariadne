# Plan: Chat / Graphs View Split + Graph Visualization

## 1. Introduction

This plan adds a second top-level view to the Ariadne analyst workbench. Today the app is a single conversational surface (chat thread + inspector). We are introducing a **Chat ⇄ Graphs** toggle in the header so an analyst can switch between the existing federated-query chat and a new **Graphs** view dedicated to exploring the loaded knowledge graphs — the MITRE ATT&CK graph (Neo4j) and the CAPEC graph (Gremlin) — as an interactive node/edge visualization.

The approach: (1) a new read-only backend endpoint that serves the *canonical* graph files already on disk (`data/graphs/<ds>/canonical/nodes.jsonl` + `relationships.jsonl`) as one nodes+edges JSON payload; (2) a typed web data layer for it; (3) a header restructure (drop the "Analyst Workbench" tag, add a view toggle, move the Neo4j/Gremlin status pills to the right by the Run Pipeline button); (4) a `GraphExplorer` view built on **react-force-graph-2d** (canvas) that renders every node and edge for the selected dataset, with a secondary dataset switcher (ATT&CK ↔ CAPEC), a sidebar for navigation/filtering, and a click-to-inspect properties panel. Data is served from the canonical files (authoritative, no running DB required). Execution uses an agent workflow: Opus for planning (this doc), Haiku for repository search, Sonnet for implementation.

Datasets in scope (from the canonical manifests): **ATT&CK** — 2,611 nodes, 21,739 relationships (18,221 `USES`); **CAPEC** — 4,888 nodes, 6,917 relationships.

---

## 2. Gaps & Unanswered Questions

- **Data source** — *Resolved (user):* canonical files on disk via a new `/api/graph/{dataset}` endpoint. No live DB dependency.
- **Render scale / library** — *Resolved (user):* `react-force-graph-2d` (canvas/WebGL-accelerated), render **all** nodes and edges by default. Because ATT&CK has ~21.7k edges, the sidebar provides a relationship-type filter and a node-label filter to thin the view; default is everything visible. *Assumption:* a "cap for first paint" is **not** used — we honor "every node and edge," and lean on canvas + a one-time payload fetch. If the ATT&CK graph is visibly unusable in-browser we will add an opt-in "hide USES" default (noted, not implemented up front).
- **Payload size** — ATT&CK relationships file is ~10 MB raw JSONL. *Assumption:* the endpoint returns a trimmed per-element shape (id, label(s), name, and a compact `properties` map for nodes; id, source, target, type for edges) so the response is far smaller than the raw files; full per-record properties are already available and are included for nodes (needed for inspection) but **descriptions/external_references are truncated/omitted** in the list payload to keep it light, with a note that full detail is what the click panel shows. *Assumption:* include full node `properties` but drop the giant `external_references`/`description` blobs from the wire only if payload proves too large; start by including everything and measure during Step 1 validation.
- **Execution model** — *Resolved (user):* agent workflow (Opus plan / Haiku search / Sonnet implement).
- **Routing** — *Assumption:* the Chat/Graphs switch is **client state** in `WorkbenchContext` (no new Next route), matching the existing single-page, context-driven shell. No URL change.
- **Selectors ("textures")** — *Assumption:* the "Neo4j and Gremlin selectors" refers to the `InfraStatusBar` live status pills currently rendered on the **left** of the header; we move them to the **right**, grouped next to Run Pipeline.
- **Mobile** — *Assumption:* the Graphs view is desktop-first; on small screens the sidebar collapses into a drawer (reuse the existing drawer pattern) and the canvas fills the remaining space. Full mobile polish follows `accessibility-mobile`/`ada-compliance` but is not the primary target.

---

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Backend — canonical graph endpoint
- **Locations:**
  - New `api/services/graph.py` — `load_canonical_graph(dataset)` reads `data/graphs/<dataset>/canonical/nodes.jsonl` + `relationships.jsonl` + `manifest.json`, returns a `GraphPayload` (dataset, backend label, counts, `nodes[]`, `edges[]`). Reuse path resolution from `utils/graph_loader/config.py` / manifest conventions rather than hardcoding.
  - `api/models.py` — add `GraphNodeModel`, `GraphEdgeModel`, `GraphPayloadResponse` (and a `GraphDataset = Literal["attack","capec"]`).
  - `api/main.py` — add `GET /api/graph/{dataset}` returning `GraphPayloadResponse`; 404 on unknown/absent dataset (canonical files missing → clear error).
- **Rationale:** The view is a pure function of graph data; serving the already-built canonical files is the authoritative, DB-independent source and keeps the frontend a thin consumer. Doing this first gives a stable JSON contract everything else builds on.
- **Action:** Undergo the verification/tests/validation process for this phase — add `api/tests/test_graph.py` (shape, counts match manifest, unknown-dataset 404) and run `uv run python -m pytest api/tests/`; curl the live endpoint for both datasets and record node/edge counts. Once validated, commit to GitHub stating: Graph Visualization (1/6) Complete: Added GET /api/graph/{dataset} serving the canonical ATT&CK/CAPEC nodes+edges with contract tests.

### Step 2: Web data layer + dependency
- **Locations:**
  - `web/package.json` — add `react-force-graph-2d` (single, clearly-scoped rendering dependency; record in changelog per library-inclusion rules).
  - `web/lib/types.ts` — add `GraphNode`, `GraphEdge`, `GraphPayload`, `GraphDataset` mirroring the API models.
  - `web/lib/api.ts` — add `getGraph(dataset): Promise<GraphPayload>` using the existing same-origin `/api/*` proxy.
- **Rationale:** A typed client + types is the clean seam (mirrors the existing `getHealth`/`getConfig` pattern) so components never touch fetch details, and installing the render lib once keeps the boundary explicit.
- **Action:** Undergo the verification/tests/validation process for this phase — `cd web && npm install`, `npm run build`, `npm run lint`; add a Vitest for `getGraph` URL/shape if feasible. Once validated, commit to GitHub stating: Graph Visualization (2/6) Complete: Added the typed getGraph client, graph view-model types, and the react-force-graph-2d dependency.

### Step 3: View state + header restructure
- **Locations:**
  - `web/components/workbench/WorkbenchContext.tsx` — add `view: "chat" | "graphs"` + `setView`, and graph-view state (`graphDataset: GraphDataset`, `setGraphDataset`, selected element for inspection, sidebar open state).
  - `web/components/header/HeaderBar.tsx` — remove the "Analyst Workbench" tag `<span>`; add a segmented **Chat / Graphs** `ViewToggle`; move `InfraStatusBar` from the left group into the right group next to `RunPipelineButton`.
  - New `web/components/header/ViewToggle.tsx` — accessible two-option segmented control (radiogroup semantics, keyboard operable) bound to `view`.
- **Rationale:** The toggle is app-wide navigation, so it belongs in shared context and the header; removing the tag and regrouping the pills are the requested header changes and are cheapest to do alongside the toggle. Client state (not a route) matches the existing single-page shell.
- **Action:** Undergo the verification/tests/validation process for this phase — `npm run build` + `npm run lint`; manually confirm the toggle flips `view`, pills render on the right, and the tag is gone. Once validated, commit to GitHub stating: Graph Visualization (3/6) Complete: Added the Chat/Graphs view toggle, removed the Analyst Workbench tag, and moved the Neo4j/Gremlin status pills beside Run Pipeline.

### Step 4: Graph Explorer scaffold — dataset switcher, layout, sidebar
- **Locations:**
  - New `web/components/graph/GraphExplorer.tsx` — top-level Graphs view: secondary header (dataset switcher ATT&CK ↔ CAPEC + node/edge count summary + loading/empty/error states), a `GraphSidebar`, and the canvas region. Loads via `getGraph(graphDataset)`.
  - New `web/components/graph/GraphSidebar.tsx` — navigation/inspection sidebar: dataset legend (labels/colors), relationship-type and node-label filter toggles, and a slot for the selected-element inspector.
  - New `web/components/graph/GraphSecondaryNav.tsx` — the dataset-switch nav (mirrors ATT&CK "Neo4j graph / attack dataset" and "CAPEC dataset").
  - `web/components/workbench/Workbench.tsx` — render `GraphExplorer` in the center region when `view === "graphs"`, else the existing `ChatThread`/inspector; hide the chat inspector in graphs mode.
- **Rationale:** Establishing the view shell (switcher + sidebar + states) before wiring the heavy canvas keeps the layout, Woven Dusk styling, and loading/empty/error states correct without fighting render performance. Datasets must be switchable per the requirement.
- **Action:** Undergo the verification/tests/validation process for this phase — `npm run build` + `npm run lint`; confirm switching to Graphs shows the shell, the dataset switcher fetches both datasets (counts shown), and loading/empty/error states render. Once validated, commit to GitHub stating: Graph Visualization (4/6) Complete: Added the Graphs view shell with the ATT&CK/CAPEC dataset switcher, sidebar, and load states.

### Step 5: Canvas rendering + click-to-inspect
- **Locations:**
  - New `web/components/graph/GraphCanvas.tsx` — client-only (`dynamic(..., { ssr:false })`) wrapper around `react-force-graph-2d`; maps `GraphPayload` to the lib's `{nodes, links}`, colors nodes by label (Woven Dusk palette), applies the sidebar filters, and handles `onNodeClick`/`onLinkClick`.
  - New `web/components/graph/ElementInspector.tsx` — renders the clicked node/edge's variables/properties (id, labels/type, name, full `properties` map, source/target for edges) inside the sidebar.
  - `GraphSidebar.tsx` — host the `ElementInspector`; wire filter toggles to canvas.
  - `web/lib/graph.ts` — pure helpers (label→color, payload→force-graph shape, filter application) so they are unit-testable without the canvas.
- **Rationale:** react-force-graph on canvas is the chosen renderer for ~21.7k edges; isolating pure transforms in `lib/graph.ts` keeps rendering testable and matches the app's "pure builders" convention. Click-to-inspect is the core "understand each element" requirement.
- **Action:** Undergo the verification/tests/validation process for this phase — add Vitest for `lib/graph.ts` (color mapping, shape transform, filter); `npm run build` + `npm run lint` + `npm test`; validate live in-browser that both graphs render all nodes/edges, filters work, and clicking a node/edge shows its properties with no console errors. Once validated, commit to GitHub stating: Graph Visualization (5/6) Complete: Rendered the full ATT&CK/CAPEC graphs on canvas with label coloring, filters, and click-to-inspect properties.

### Step 6: Docs, full regression, merge
- **Locations:**
  - `docs/structure.md` — document the Chat/Graphs split, the `GET /api/graph/{dataset}` endpoint, and the `web/components/graph/` surface.
  - `docs/changelog.jsonl` — one entry per step already appended; add the final (6/6) entry.
  - Merge the feature worktree/branch into `main` after everything is green.
- **Rationale:** Canonical docs must reflect the new endpoint and view so future agents don't assume a chat-only UI; a full regression + merge lands the feature.
- **Action:** Undergo the verification/tests/validation process for this phase — full regression: `uv run python -m pytest api/tests/`, `cd web && npm test && npm run lint && npm run build`, plus a live `python app.py` smoke test of both views. Once validated, commit to GitHub stating: Graph Visualization (6/6) Complete: Documented the graph view + endpoint, passed full regression, and merged to main. (Per session directive: commit only, do not push.)

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Canonical graph service | Reads canonical JSONL → nodes+edges payload | `api/services/graph.py` |
| Graph endpoint + models | `GET /api/graph/{dataset}` + response models | `api/main.py`, `api/models.py` |
| Backend contract tests | Shape, manifest-count match, 404 on unknown dataset | `api/tests/test_graph.py` |
| Typed graph client + types | `getGraph()` + `GraphNode/Edge/Payload` | `web/lib/api.ts`, `web/lib/types.ts` |
| Pure graph transforms + tests | color/shape/filter helpers | `web/lib/graph.ts`, `web/lib/__tests__/graph.test.ts` |
| View toggle + header changes | Chat/Graphs switch, tag removed, pills moved right | `web/components/header/ViewToggle.tsx`, `HeaderBar.tsx` |
| View + graph state | `view`, `graphDataset`, selection, sidebar state | `web/components/workbench/WorkbenchContext.tsx` |
| Graph Explorer view | Shell, dataset switcher, sidebar, load states | `web/components/graph/GraphExplorer.tsx`, `GraphSecondaryNav.tsx`, `GraphSidebar.tsx` |
| Canvas + inspector | Full node/edge render + click-to-inspect properties | `web/components/graph/GraphCanvas.tsx`, `ElementInspector.tsx` |
| Render dependency | `react-force-graph-2d` | `web/package.json` |
| Docs | Endpoint + view documentation, changelog entries | `docs/structure.md`, `docs/changelog.jsonl` |
