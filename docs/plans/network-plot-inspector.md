# Plan — Network Plot Inspector (chat answer card)

## 1. Introduction

The per-answer **Network Plot** tab in the chat answer card renders a compact
CAPEC → ATT&CK → mitigation subgraph, but it is hard to read: nodes are labelled
only by their raw identifier (e.g. `CAPEC-66`, `T1047`), clicking a node does
nothing visible, and clicking an edge silently deselects. Analysts can see *that*
there are attack patterns and techniques but get no name, description, or
provenance for the thing they clicked.

This plan makes the plot inspectable **inside the same plot area**: clicking a
node or an edge opens a detail panel (reusing the existing, already-themed
`ElementInspector`) that shows the entity's proper name, type, and properties
(description, provenance, join values). It also enriches the subgraph nodes with
the real names/descriptions already present in the turn's federated evidence, so
both the hover label and the panel show human-readable titles instead of bare
IDs. No new graph engine, no backend change — the enrichment reuses data the turn
already carries.

## 2. Gaps & Unanswered Questions

- **Enrichment source**: node names/descriptions are not on the synthesis view.
  *Assumption*: derive an `id → {name, label, properties}` lookup from
  `run.federated.results[].records[]` (rich: name + properties) plus
  `join_index[*]` entries (name-only fallback for join endpoints). This is
  already in `WorkbenchRun` — no backend/fixture change.
- **Panel placement in a narrow card**: the plot box is only ~240px tall inside a
  chat bubble. *Assumption*: render the inspector as an absolutely-positioned
  overlay panel on the right edge of the plot box (scrollable, with a close
  button), rather than shrinking the canvas with a flex column. Keeps the canvas
  full-bleed and works on narrow widths.
- **Edge names**: the link inspector shows `sourceId → targetId`. *Assumption*:
  keep IDs there (matches the Graph Explorer); node enrichment already gives the
  readable names when the endpoints themselves are clicked.
- **Deselect affordance**: *Assumption*: clicking empty canvas background clears
  the selection (new optional `onBackgroundClick` on `GraphCanvas`); the panel
  also has an explicit close button.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Enrich subgraph nodes with real names/descriptions
- **Locations**: `web/lib/synthesisGraph.ts` — new pure helper
  `buildEntityDetails(federated)` returning `Map<string, EntityDetail>`; extend
  `synthesisToGraphPayload(synthesis, joinPairs, details?)` to stamp
  `node.name` / `node.properties` from the lookup (falling back to the id when
  absent). `web/lib/types.ts` if a small `EntityDetail` type is needed.
- **Rationale**: the panel and hover label are only as good as the node data;
  the names already exist in the federated evidence, so this is a projection, not
  new data. Keeping it in the one payload-building seam means the renderer,
  legend, and meta helper are untouched.
- **Action**: Add unit tests in `web/lib/__tests__/synthesisGraph.test.ts`
  (lookup build, name/description stamped, id fallback when no match, existing
  callers still pass with the optional arg). Run `cd web && npm test`. Once
  validated, commit stating: Network Plot Inspector (1/3) Complete: subgraph
  nodes carry real names/descriptions from the turn's federated evidence.

### Step 2: Let the shared canvas report background clicks
- **Locations**: `web/components/graph/GraphCanvas.tsx` — add optional
  `onBackgroundClick?: () => void` prop wired to ForceGraph2D's
  `onBackgroundClick`. No behaviour change when the prop is omitted (Graph
  Explorer unaffected).
- **Rationale**: a click-outside-to-deselect affordance for the overlay panel,
  without touching the Explorer surface.
- **Action**: `cd web && npm run lint` + `npm test` stay green. Commit with
  Step 3 (small, coupled change) or state: Network Plot Inspector (2/3)
  Complete: GraphCanvas can report background clicks for deselect.

### Step 3: Inspect panel + edge selection in the plot area
- **Locations**: `web/components/center/AnswerNetworkPlot.tsx` — replace the
  `selectedId` string state with `SelectedElement` state; wire `onSelectNode` /
  `onSelectLink` / `onBackgroundClick`; render an overlay `aside` inside the
  existing relative plot box hosting `ElementInspector`
  (`web/components/graph/ElementInspector.tsx`) with a close button
  (`CloseIcon`); derive `selectedId` for the highlight ring; update the caption
  to hint clickability; accept + thread an `entityDetails` prop.
  `web/components/center/AnswerCard.tsx` — build the details lookup from
  `run.federated` and pass it to `<NetworkPlotBody>`.
- **Rationale**: this is the actual user-facing fix — click a node/edge, get its
  name and details in the same plot area, and edges become selectable.
- **Action**: `cd web && npm run lint && npm test && npm run build`; verify in
  the browser preview (open a turn's Network Plot tab, click a node → panel shows
  the proper name + description; click an edge → edge panel; background click and
  close button clear it). Append a `docs/changelog.jsonl` entry. Commit stating:
  Network Plot Inspector (3/3) Complete: clicking nodes/edges opens a named,
  descriptive detail panel inside the chat network plot.

## 4. Deliverables Table

| Deliverable | Description | Location |
| --- | --- | --- |
| Node enrichment + lookup | Stamp real names/descriptions onto subgraph nodes | `web/lib/synthesisGraph.ts` |
| Enrichment unit tests | Lookup build, stamping, id fallback, back-compat | `web/lib/__tests__/synthesisGraph.test.ts` |
| Background-click hook | Optional deselect affordance on the shared canvas | `web/components/graph/GraphCanvas.tsx` |
| Inspect panel + edge select | Overlay `ElementInspector`, node+edge selection | `web/components/center/AnswerNetworkPlot.tsx` |
| Details wiring | Build id→details from federated evidence, pass down | `web/components/center/AnswerCard.tsx` |
| Changelog entry | Record the feature | `docs/changelog.jsonl` |
