# Plan: Graph Explorer Search Bar

## 1. Introduction

Add a search bar at the top of the graph explorer that filters the rendered graph
by matching text against node titles/descriptions and edge titles. The graph
re-filters **1 second after the user stops typing** (debounced) or **immediately
when the user clicks the Search button** (or presses Enter). This is scoped to
`web/components/graph/` plus the pure transform in `web/lib/graph.ts`; no backend
or API change.

## 2. Gaps & Unanswered Questions

- **What text is searched** — *Assumption:* nodes match on `name`, `id`, any
  `label`, and `properties.description`; edges match on `type` (the edge's title).
  The backend strips edge `properties` to keep the payload light, so edge
  descriptions are not available client-side — edge search is by type. Node
  `description` is the server-truncated (280-char) value already in the payload.
- **How search affects the graph** — *Assumption:* filter (not just highlight).
  Visible nodes = nodes matching the query; plus the endpoints of any edge whose
  `type` matches. Visible edges = edges (of a non-hidden type) whose both
  endpoints are visible. Empty query = no search filtering (current behavior).
  Search composes with the existing node-type / relationship-type filters.
- **Debounce vs button** — *Resolved (user):* 1s debounce after the last
  keystroke, or immediate on Search-button click / Enter. A clear (×) button
  resets the query immediately.
- **Per-dataset** — *Assumption:* the query is stored per dataset (like the
  filters) and resets when switching datasets.
- **No-results state** — *Assumption:* reuse/generalize the existing
  "all filtered" canvas message so it also covers an empty search result.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Search transform + debounced search bar + wiring

- **Locations:**
  - `web/lib/graph.ts` — extend `ToForceGraphOpts` with `query?: string`; in
    `toForceGraphData`, when a non-empty query is present, restrict visible nodes
    to text matches (name/id/label/description) plus endpoints of type-matching
    edges, keeping the existing dangling-link drop and hidden-label/type filters.
    Add a small pure `nodeMatchesQuery` helper (exported for tests).
  - `web/lib/__tests__/graph.test.ts` — cases: name match, description match,
    edge-type match pulls in endpoints, empty query = unchanged, query composes
    with hiddenTypes, no-match = empty.
  - `web/components/graph/GraphSearchBar.tsx` (new) — controlled input with a 1s
    debounce timer (`useRef`), a Search button and Enter key for immediate search,
    and a clear (×) button. Calls `onSearch(text)`; local text seeded from the
    committed `value`.
  - `web/components/graph/GraphExplorer.tsx` — add `query` to the per-dataset
    filter state; render `<GraphSearchBar key={graphDataset} value={query}
    onSearch={...} />` at the top (below the secondary nav); thread `query` into
    the `toForceGraphData` memo (+ deps); generalize the empty-result message.
- **Rationale:** Keeping the match logic pure in `lib/graph.ts` makes it unit
  testable and keeps the canvas a pure function of state; the debounce/button live
  in a small dedicated component; all of these are interdependent (the bar is
  useless without the transform), so they land together.
- **Action:** Undergo the verification/tests/validation process for this phase —
  `cd web && npm run build && npm run lint && npm test`, then a live in-browser
  check: typing filters the graph after ~1s (visible-count badge drops), the
  Search button/Enter filter immediately, × clears, and search composes with the
  type filters. Once validated, commit to GitHub stating: Graph Search (1/2)
  Complete: Added a debounced top search bar filtering the graph by node
  title/description and edge type.

### Step 2: Docs, regression, merge

- **Locations:** `docs/structure.md` (note the search bar), `docs/changelog.jsonl`
  (entry per step), merge `feature/graph-search` into `main`.
- **Rationale:** Canonical docs must reflect the new search; regression + merge
  lands the change.
- **Action:** Undergo the verification/tests/validation process for this phase —
  full regression (`uv run python -m pytest api/tests/`, `cd web && npm test &&
  npm run lint && npm run build`). Once validated, commit to GitHub stating: Graph
  Search (2/2) Complete: Documented the search bar, passed regression, merged to
  main. (Per session directive: commit only, do not push.)

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Search transform | `query` filtering in `toForceGraphData` + `nodeMatchesQuery` | `web/lib/graph.ts` |
| Transform tests | Query match/compose/empty cases | `web/lib/__tests__/graph.test.ts` |
| Search bar | Debounced (1s) input + Search button + clear | `web/components/graph/GraphSearchBar.tsx` |
| Explorer wiring | Per-dataset query state + memo + empty state | `web/components/graph/GraphExplorer.tsx` |
| Docs | Search bar described | `docs/structure.md`, `docs/changelog.jsonl` |
