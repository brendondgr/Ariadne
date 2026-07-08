# Graph Search Toolbar Plan

## 1. Introduction

The Graph Explorer's search currently lives on its own row beneath the dataset
switcher, matches a fixed set of fields (name, id, labels, description, edge
type) with no way to narrow the scope, and shows only exact textual matches —
there is no way to see the neighborhood around a match. The node/edge count
summary sits on a different row (the dataset nav), visually disconnected from
the search that changes what is visible.

This plan consolidates the search into a single toolbar line that also carries
the node/edge counts, adds a **jumps** (hop-depth) control on the left of that
line so an analyst searching e.g. "phishing" can reveal every node within N
hops of the matches, and adds a **field-scope** selector so the search can be
pointed at names/titles, IDs, descriptions, labels, or edge types
independently. All matching/expansion logic stays in the pure, unit-tested
`web/lib/graph.ts`; the React components only hold UI state.

## 2. Gaps & Unanswered Questions

- **"At least two away" wording**: the request reads as neighborhood reach,
  not an exclusion ring. *Assumption*: "N jumps" means show matches **plus
  every node within N hops** of a match (0 = matches only, the current
  behavior). This is the standard graph-explorer semantic.
- **Jump range**: *Assumption*: 0–3 hops. Beyond 3 hops on these datasets the
  neighborhood approaches the whole graph and the control loses meaning.
- **Field scope granularity**: *Assumption*: multi-select over Name, ID,
  Description, Labels, Edge type — default all on (today's behavior). "Title"
  and "name" collapse into one Name field because graph nodes have a single
  `name` display property.
- **Which counts move onto the search line**: *Assumption*: the dataset-total
  counts currently in `GraphSecondaryNav` move to the right end of the search
  line; the floating "visible after filtering" badge on the canvas is
  unchanged.
- **Hop expansion vs. hidden labels/types**: *Assumption*: expansion never
  traverses edges of a hidden type nor reveals nodes of a hidden label —
  sidebar filters stay authoritative.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Pure search-scope + hop-expansion logic

- **Locations**: `web/lib/graph.ts` (`SearchField` type, `nodeMatchesQuery`,
  new `expandByHops`, `ToForceGraphOpts` gains `fields` + `hops`,
  `toForceGraphData`); `web/lib/__tests__/graph.test.ts`.
- **Rationale**: every behavior lands first as a pure, synchronous function so
  it is unit-testable without React. `nodeMatchesQuery` learns to honor a set
  of `SearchField`s ("name" | "id" | "description" | "label"; "type" gates the
  edge-type seeding in `toForceGraphData`). `expandByHops` BFS-expands the
  surviving seed set over non-hidden edges/labels up to N hops.
  `toForceGraphData` composes: seeds → hop expansion → node/link lists.
  Defaults (`fields` = all, `hops` = 0) must reproduce today's output exactly.
- **Validation**: new Vitest cases for field scoping (each field on/off), hop
  expansion (0/1/2 hops, hidden-type edge not traversed, hidden-label node not
  revealed), and default-equivalence; `cd web && npm test` green.
- **Action**: Undergo the verification/tests/validation process for this
  phase. Once validated, commit changes (no push) stating: Graph Search
  Toolbar (1/3) Complete: pure field-scoped matching and N-hop neighborhood
  expansion in lib/graph.ts with unit tests.

### Step 2: Single-line toolbar UI (jumps + scope + search + counts)

- **Locations**: `web/components/graph/GraphSearchBar.tsx` (hops select on the
  far left, field-scope dropdown with checkboxes, existing input/Search
  button, counts summary on the right); `web/components/graph/GraphSecondaryNav.tsx`
  (drop the counts span — tabs only); `web/components/graph/GraphExplorer.tsx`
  (`DatasetFilters` gains `hops` + `fields`, wires new props and passes
  `counts` into the search bar, feeds `fields`/`hops` to `toForceGraphData`).
- **Rationale**: the explorer owns per-dataset filter state, so the new
  controls persist per dataset exactly like the query does today. Moving the
  counts into the search row satisfies the "same line" requirement; the
  secondary nav keeps only the dataset tabs.
- **Validation**: `cd web && npm test`, `npm run lint`, and `npm run build`
  (required for webfront changes) all green.
- **Action**: Undergo the verification/tests/validation process for this
  phase. Once validated, commit changes (no push) stating: Graph Search
  Toolbar (2/3) Complete: one-line graph toolbar — jumps selector, field-scope
  dropdown, search, and node/edge counts.

### Step 3: Live verification + merge

- **Locations**: run `python app.py --port 16600 --api-port 16601` (fallback
  ports per project memory); exercise the Graphs menu; then merge
  `worktree-graph-search-toolbar` into local `main`.
- **Rationale**: prove the toolbar against the real API payload (search
  "phishing" with 0/1/2 jumps, scope narrowed to Description vs Name), then
  land on main only when 100% functional, resolving any concurrent-session
  drift.
- **Validation**: UI renders one toolbar line, jumps expand the neighborhood,
  scopes narrow matches, counts sit on the same line; post-merge `npm test` +
  `npm run build` green on main.
- **Action**: Undergo the verification/tests/validation process for this
  phase. Once validated, commit changes (no push) stating: Graph Search
  Toolbar (3/3) Complete: live-verified the toolbar and merged into main.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Field-scoped matching | `nodeMatchesQuery` honoring a `SearchField` set | `web/lib/graph.ts` |
| Hop expansion | `expandByHops` BFS + `toForceGraphData` `hops`/`fields` opts | `web/lib/graph.ts` |
| Unit tests | Vitest cases: scoping, 0/1/2 hops, filter interaction, default equivalence | `web/lib/__tests__/graph.test.ts` |
| Toolbar UI | Jumps select, scope dropdown, search, counts on one line | `web/components/graph/GraphSearchBar.tsx` |
| Nav cleanup | Counts removed from the dataset nav | `web/components/graph/GraphSecondaryNav.tsx` |
| State wiring | Per-dataset `hops`/`fields` filter state | `web/components/graph/GraphExplorer.tsx` |
| Changelog entries | One per completed step | `docs/changelog.jsonl` |
