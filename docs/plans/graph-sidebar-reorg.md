# Plan: Graph Explorer Sidebar Reorganization

## 1. Introduction

The graph explorer currently crams three things into one left sidebar: a "Graph"
legend (node labels + counts), the Filters (node-type + relationship-type
checkboxes, which *also* show counts), and the selected-element Inspection panel.
The legend duplicates information already visible in the filters, and putting
inspection details in the same narrow column as the filters makes the panel busy
and cramped.

This plan reorganizes the explorer into a clean two-sidebar layout: the **left
sidebar becomes filters-only** (legend removed as redundant), and a **new right
sidebar appears only when a node or edge is clicked**, showing that element's
details with a close control. This is one cohesive layout change scoped to
`web/components/graph/`; it touches no data, API, or graph-rendering logic.

## 2. Gaps & Unanswered Questions

- **Redundant legend** — *Resolved (user):* remove the "Graph" legend section from
  the left sidebar entirely; the filter rows already show each label with its
  count and color swatch.
- **Where do details go** — *Resolved (user):* a right sidebar that appears on
  node/edge click and shows the details there.
- **Dismissing the right sidebar** — *Assumption:* the right sidebar shows a close
  (×) button that clears the selection; clicking a different element replaces its
  contents. When nothing is selected the right sidebar is not rendered (the canvas
  reclaims the width), so there is no permanent empty panel.
- **Empty/placeholder state** — *Assumption:* since the right sidebar only appears
  on selection, the "Select a node or edge…" placeholder is no longer needed as a
  persistent element; the ElementInspector's placeholder branch stays as a
  harmless fallback but won't normally render.
- **Mobile** — *Assumption:* desktop-first, consistent with the existing explorer;
  the right sidebar uses the same fixed-width aside pattern as the left. No new
  mobile drawer work in this change.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Filters-only left sidebar + new right details sidebar

- **Locations:**
  - `web/components/graph/GraphSidebar.tsx` — remove the "Graph" legend section
    and the "Inspection" section (and the `ElementInspector` import + `selected`
    prop). Keep the Filters section; let it grow to fill the column height and
    scroll (drop the `max-h-[240px]` cap). `labelColor` stays (filter swatches).
  - `web/components/graph/GraphDetailsSidebar.tsx` (new) — a right-side `aside`
    (mirrors the left sidebar's width/styling, left-edge shadow) that renders only
    when `selected` is non-null: a header ("Node" / "Edge") + a close (×) button
    wired to `onClose`, and the existing `ElementInspector`.
  - `web/components/graph/GraphExplorer.tsx` — drop the `selected` prop passed to
    `GraphSidebar`; render `<GraphDetailsSidebar selected={selected} onClose={...}/>`
    to the right of the canvas region; add an `onClose` handler that clears the
    selection (`updateFilters({ selected: null })`). Reset selection on dataset
    change already happens via the per-dataset filter map.
  - `web/components/graph/ElementInspector.tsx` — unchanged (reused as-is); its
    placeholder branch remains as a fallback.
- **Rationale:** These edits are interdependent — moving inspection out of the left
  column must coincide with the new right sidebar so no functionality is lost, so
  they land as one atomic change. Removing the legend de-duplicates the counts the
  filters already show.
- **Action:** Undergo the verification/tests/validation process for this phase —
  `cd web && npm run build && npm run lint && npm test`, then a live in-browser
  check (start API + prod preview): the left sidebar shows only Filters, no legend;
  clicking a node/edge opens the right sidebar with its properties; the × closes
  it; switching datasets clears it. Once validated, commit to GitHub stating:
  Graph Sidebar Reorg (1/2) Complete: Left sidebar is filters-only; a right details
  sidebar now shows clicked node/edge properties.

### Step 2: Docs, regression, merge

- **Locations:**
  - `docs/structure.md` — update the `components/graph/` description to note the
    filters-only left sidebar and the new `GraphDetailsSidebar` (right, on-select).
  - `docs/changelog.jsonl` — entry per step.
  - Merge `feature/graph-sidebar-reorg` into `main`.
- **Rationale:** Canonical docs must reflect the new two-sidebar layout; a full
  regression + merge lands the change.
- **Action:** Undergo the verification/tests/validation process for this phase —
  full regression (`uv run python -m pytest api/tests/`, `cd web && npm test &&
  npm run lint && npm run build`). Once validated, commit to GitHub stating:
  Graph Sidebar Reorg (2/2) Complete: Documented the two-sidebar layout, passed
  regression, merged to main. (Per session directive: commit only, do not push.)

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Filters-only left sidebar | Legend + inspection removed; filters fill height | `web/components/graph/GraphSidebar.tsx` |
| Right details sidebar | Appears on selection; header + close + inspector | `web/components/graph/GraphDetailsSidebar.tsx` |
| Explorer wiring | Renders right sidebar, clears selection on close | `web/components/graph/GraphExplorer.tsx` |
| Graph transform tests | Existing `lib/graph.ts` tests still green (no logic change) | `web/lib/__tests__/graph.test.ts` |
| Docs | Two-sidebar layout described | `docs/structure.md`, `docs/changelog.jsonl` |
