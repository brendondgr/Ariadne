# The operator algebra: what each retrieval operation means

**Status:** written 2026-11-20 (Era 2, Step 9, Phase B), before any compiler code. This document
is the oracle: the tests in `utils/specialists/algebra/tests/test_semantics.py` check the
compilers against it, and the differential test checks Cypher against Gremlin. When a compiler
and this text disagree, the compiler is wrong. A change here is a dated amendment (§ 9), never a
silent edit.

**Why it is written first.** Cypher and Gremlin agree on the easy cases and part ways on missing
values, duplicates, ties and paths. Neither engine's default is "right": each rule below picks one
meaning and both compilers implement it. The kill-test compilers (EXP-2026-11-006) agreed 100%
once the meaning was fixed this way.

**What decided the scope.** The question-shape census (EXP-2026-11-020):
- today's operations already cover 0.98 of Ariadne's own banks;
- `verify` is 0.44 of AttackQA;
- no source asks for aggregates, ranks, grouping, time or paths, except Step 6's out-of-coverage
  set.

All eight operators are built anyway (operator's decision, 2026-11-20). Mind the Query's three
gaps are not built, since each covers 0% of external retrieval questions.

---

## 1. The graph the algebra sees

The algebra works on the **card**: the graph's schema as Ariadne describes it, not the engine's
raw storage. The compilers translate.

| Thing | What the card says | How the backends store it |
|---|---|---|
| Node | one **card label** and one stored id | Neo4j: several labels (`Technique`, `AttackObject`, `STIXObject`); Gremlin: one vertex label |
| Stored id | the `id` property, unique in the graph | both: property `id` (Gremlin: `has('id', …)`, not `T.id`) |
| Public identifier | the card's id scheme: `attack_id` for ATT&CK, `CAPEC-<n>` for CAPEC | Neo4j: `attack_id`; Gremlin CAPEC: `capec:<kind>:<n>` in `id` |
| Relationship | a card name, a direction, and the labels it joins | Neo4j: the card name; Gremlin: the SCREAMING_SNAKE form (`gremlin_edge_label`) |
| Property type | `str`, `int`, `float`, `bool`, `list[str]`, `date` (ISO-8601 text) | the same in both; dates are strings, lists are list values |

**Anchors arrive resolved.** Grounding (names to ids, `resolve_entity`, the written-id guard) runs
before the algebra and hands it stored ids. The algebra never matches by name.

---

## 2. Rules every operator follows

Each rule has an id, which the tests cite (§ 8).

- **S1 — identity and deduplication.**
  - A node result is a **set of nodes, keyed by stored id**. A node reached by several paths
    appears once.
  - Counts count distinct stored ids.
  - Results report the public identifier and the name beside the stored id.
- **S2 — label mode.**
  - A node matches label `L` only when its **card label** is `L`.
  - Neo4j's extra labels (`AttackObject`, `STIXObject`) are not card labels and are never
    matched or returned.
  - A step that names no target label keeps every card label the relationship reaches.
- **S3 — relationships.**
  - A relationship is named by its card name and walked in the card's direction (`out` or `in`).
  - Each compiler translates the name to its backend's spelling.
  - A relationship the card does not list between two labels is refused before compiling.
- **S4 — filters: present and satisfying.**
  - A filter keeps an item only when the property is **present** and satisfies the condition.
  - A missing property never matches, not even `<>` or `not_contains`. "Lacks the property" is
    its own test, `missing` (§ 3, `O7d`).
  - Several filters on one item are joined by AND. OR is `union` (`O7c`).
- **S5 — comparison by type.**
  - `int` and `float` compare as numbers.
  - `str` compares exactly and is case-sensitive. It orders by code point (`<`, `>`, `<=`,
    `>=`; amendment 2). `starts_with`, `ends_with` and `contains_text` are case-sensitive
    substring tests.
  - `number_text` (a number stored as text) compares, sorts and aggregates as the number it
    spells. A value that does not parse as a number counts as missing (amendment 2).
  - `bool` allows only `=` and `<>`.
  - `list[str]` allows `contains` and `not_contains` (one element), and `size` with a comparison.
- **S6 — dates.**
  - Stored as ISO-8601 text.
  - Comparisons use the first ten characters (`YYYY-MM-DD`) as text, which orders correctly for
    ISO dates.
  - `year` compares the first four characters as an integer.
  - A value that is not ISO-shaped does not match any date condition.
- **S7 — limits.**
  - **The row cap bounds the rows shown, never an aggregate's inputs or a count.** Totals are
    exact.
  - Every result carries its exact total and `complete: true|false` (Step 5's envelope). A
    capped list says how many rows it left out.
  - Path search has a depth cap (§ 3, `O8`). Hitting the cap marks the result `partial`.
- **S8 — ties and order.**
  - Ranked results return **every item tied with the last one kept**. A top-3 with a tie at
    third returns 4 or more, and says so.
  - Every list has a deterministic order: the operator's own key, then stored id ascending.
    Unranked sets order by stored id.
  - **A missing or `null` key sorts last in either order** (amendment 2). It is reached by a
    top-`k` only when fewer than `k` items have a value.
- **S9 — empty groups.** A group-by returns **every member** of the grouped label that passes the
  member filter:
  - a member with nothing to aggregate has count 0;
  - its sum is 0;
  - its avg, min, max and median are missing (`null`).
- **S10 — paths.**
  - Paths are **acyclic**: no node repeats.
  - Reach returns nodes, not paths.
  - Shortest path returns **every** path of the minimum length, each as an alternating list of
    stored ids and relationship names.
- **S11 — numbers.**
  - Integer results are exact.
  - `sum` and `avg` over floats compare across backends within a **relative tolerance of
    1e-9**, fixed in advance. This is the only tolerance anywhere.
  - Median of an even count is the mean of the two middle values.
- **S12 — nothing found is an answer.**
  - An empty set is a valid result with total 0.
  - An anchor id that matches no node gives `anchor_not_found`, which is different from an
    empty result.

---

## 3. The operators

Notation:
- `A` is a set of anchor ids.
- `L`, `M` are card labels.
- `R` is a relationship with a direction.
- `W(A, hops)` is the set of nodes a walk reaches from `A`.

Every operator's input node set comes from one of three places:
- a walk from anchors (`W`);
- a scan of a label;
- an earlier step's result (`from_step`).

That is what lets plans chain.

### Today's operations (the base, unchanged in meaning)

| Operation | Inputs | Output | Meaning |
|---|---|---|---|
| `describe` | `A` | nodes with all properties | each anchor node (S12 for missing ids) |
| `expand` | `A`, hops (each `R` and an optional target label), depth | node set, with every intermediate | every node at the end of a matching walk, plus the nodes it passes through; one repeated hop may run 1..depth times |
| `count` | as `expand` | integer | distinct nodes at the walk's end (S1) |
| `scan` | `L` | node set | every node of `L` (S7 bounds the rows shown) |
| `common` | `A` (two or more, of different kinds) | node set | nodes adjacent to every anchor |
| `eqfilter` | property, value | — | S4 with `=`, on the last hop's label |

A `TypedStep` (`utils/specialists/signals.py`) is written in these terms and keeps compiling
exactly as before (Phase D's byte-identical check).

### O1 — `filter`

- **Inputs:** a node set and one or more conditions `(property, op, value)`. `op` is one of:
  `=`, `<>`, `<`, `>`, `<=`, `>=`, `contains`, `not_contains`, `starts_with`, `ends_with`,
  `contains_text`, `size <op> n`, `present`.
- **Output:** the subset that satisfies all conditions.
- **Meaning:** S4, S5, S6. `present` keeps nodes that have the property.
- **Edge cases:**
  - a property of the wrong type for the op is refused at validation;
  - a missing property never matches (S4).

### O2 — `aggregate`

- **Inputs:** a node set and a function:
  - `count` (distinct nodes);
  - `count_values` (distinct present values of a property);
  - or `sum`, `avg`, `min`, `max`, `median` of a numeric or date property.
- **Output:** one value, or `null` when nothing is present (except `count` and `sum`, which are 0).
- **Meaning:**
  - over distinct nodes (S1), so a node reached twice counts once;
  - missing values are skipped;
  - `min` and `max` of a date return the date text.
- **Limits:** the row cap never applies to the inputs (S7).

### O3 — `rank`

- **Inputs:** a node set, a key, an order (`asc` or `desc`), and `k`. The key is either:
  - a property;
  - or the count of a walk from each node.
- **Output:** up to `k` nodes plus every node tied with the k-th (S8), each with its key value.
- **Meaning:**
  - nodes without the property are left out of a property ranking, and the result says how many;
  - a count key of 0 is a real value and is ranked.

### O4 — `verify`

- **Inputs:** two anchor ids `a` and `b`, and optionally a relationship `R` (else any card
  relationship between their labels, in either direction).
- **Output:**
  - `exists` (true or false);
  - the **witness**: each matching relationship's name, direction and properties;
  - the **proof**: the compiled query text and its parameters, exactly as run.
- **Meaning:**
  - true when at least one matching relationship joins `a` and `b`;
  - false with an empty witness otherwise;
  - `anchor_not_found` when either id matches no node (S12).
- **Edge case:** the census showed AttackQA's verify questions want the relationship's text. The
  live graph's relationships carry only `id` today, so the witness holds `id` alone. The
  operator does not invent text.

### O5 — `typescan`

- **Inputs:** a label `L` and optional `O1` conditions.
- **Output:** the matching nodes, the exact total, and a sample of up to the row cap.
- **Meaning:** `scan` with filters, and with an exact total even when the sample is capped (S7).

### O6 — `groupby`

- **Inputs:**
  - a group label `L` (with optional member conditions);
  - a walk from each member (hops), with optional conditions on the walk's end nodes
    (`end_conds`, amendment 2);
  - an aggregate (`count`, `sum`, `avg`, `min`, `max`, `median` over the walk's end nodes or one
    of their properties);
  - optionally `having (op, value)`, and a rank (`O3`) over the groups.
- **Output:** one row per member: its id, name and value.
- **Meaning:**
  - every member is kept, with S9 values when its walk is empty;
  - `having` is applied after S9, so `count = 0` can be selected;
  - an aggregate over the groups (for example "median techniques per group") is `O2` applied to
    this result's values, and includes the zeros.

### O7 — edge filters, time, union and absence

- **O7a `edgefilter`:**
  - a condition on a relationship's own properties, inside a walk. Same rules as `O1`.
  - **Today no ATT&CK or CAPEC relationship carries a property other than `id`**, so this is
    tested on the fixture graph only.
- **O7b `time`:**
  - date conditions per S6, on a node or relationship property: `before`, `after`, `between`,
    `year =`.
  - On ATT&CK the dated properties are `created` and `modified`, one release, no history.
  - "Changed over time" questions remain unanswerable.
- **O7c `union`:**
  - two or more patterns from the same subject label; the union of their results, by stored id
    (S1).
  - Several anchors of one pattern are `expand`, not `union`.
- **O7d `absence`:**
  - members of `L` with **no** relationship `R` to any node of `M` (optionally `M` with
    conditions);
  - or members lacking a property (`missing`).
  - A member with a relationship to an `M` that fails the conditions counts as lacking it.

### O8 — `path`

- **`reach`:**
  - **Inputs:** anchors `A`, a set of relationships with directions, a depth cap `d` (default 6,
    at most 10; amendment 1).
  - **Output:** every node reachable in 1 to `d` steps along acyclic paths (S10). The anchors
    themselves are never in the result, since an acyclic path cannot return to its start.
- **`shortest`:**
  - **Inputs:** two anchors `a` and `b`, an optional relationship set (default: every card
    relationship, either direction), and a depth cap.
  - **Output:** every acyclic path of the minimum length between them, or `none within d`.
- **Limits:**
  - `d` is a hard cap;
  - hitting it with frontier left is `partial` (S7);
  - the number of returned paths is capped at the row cap, and the total is exact when it can be
    computed within the time limit, else `partial`.

---

## 4. What is not in the algebra

- **Mind the Query's gaps** (several aggregates per row, grouping by a property's value, columns
  from two variables): 0% in the census, not built.
- **Text search across descriptions, similarity, extraction from supplied text:** outside
  retrieval (census codes `X.*`). Text search belongs to Step 10's grounding.
- **Writes of any kind.** Every compiled query is read-only.

## 5. Per-operator limits, in one place

| Operator | Bounded by the row cap | Never bounded | Other cap |
|---|---|---|---|
| expand, scan, typescan, union, absence, filter | rows shown | total | — |
| count, aggregate | — | inputs and result | — |
| rank | — | inputs | `k` plus ties |
| groupby | groups shown | each group's value, the group total | — |
| verify | witness rows shown | `exists` | — |
| path | paths and nodes shown | — | depth `d`, time limit |

## 6. Compiling: one compiler per backend

- `utils/specialists/cypher/compile.py` and `utils/specialists/gremlin/compile.py` take the
  internal form (`utils/specialists/algebra/`).
- Values are passed as parameters, never spliced into the query text.
- Gremlin text matching uses wildcard sanitizing, never `re.escape`, because Groovy rejects
  `'\ '`.
- **Ported from the kill-test compilers** (`utils/killtests/typed/`), with three changes this
  document requires:
  - `top` with `limit` returns ties (S8); v3 cut at `LIMIT`;
  - literals become parameters;
  - labels are matched by card label only (S2).

## 7. How agreement is tested

- **`test_semantics.py`** runs each operator on a fixture graph built to contain every hard case:
  - ties at the cut;
  - empty groups;
  - missing and present-but-failing properties;
  - two paths to one node;
  - equal-length shortest paths;
  - dated edges;
  - a Neo4j node with extra labels.

  It compares each result with a hand-computed answer.
- **`test_differential.py`** loads ATT&CK and CAPEC into both backends of the verification pair
  (ports 5480 and 6480). It compares Cypher with Gremlin on every operator instance the card
  allows, plus 3,000 seeded random compositions, by stored id, with S11's tolerance.

## 8. Rules to tests

Each rule names the tests that check it. Phase E adds a test that fails if a named test is
missing.

| Rule | Tests (in `test_semantics.py`) |
|---|---|
| S1 | `test_two_paths_one_node_counted_once`, `test_count_is_distinct` |
| S2 | `test_extra_neo4j_labels_never_match`, `test_untargeted_hop_keeps_card_labels` |
| S3 | `test_direction_in_and_out`, `test_unknown_relationship_refused` |
| S4 | `test_missing_never_matches_not_equal`, `test_missing_never_matches_not_contains`, `test_filters_are_and` |
| S5 | `test_text_ops_case_sensitive`, `test_bool_only_equality`, `test_list_contains_and_size` |
| S6 | `test_date_compare_on_iso_prefix`, `test_year_part`, `test_non_iso_date_never_matches` |
| S7 | `test_cap_bounds_rows_not_count`, `test_aggregate_inputs_uncapped`, `test_total_and_complete_flag` |
| S8 | `test_rank_returns_ties_at_cut`, `test_deterministic_order` |
| S9 | `test_groupby_keeps_empty_groups`, `test_empty_group_values`, `test_having_can_select_zero` |
| S10 | `test_reach_is_acyclic`, `test_all_shortest_paths_returned`, `test_depth_cap_marks_partial` |
| S11 | `test_median_even_count`, `test_float_sum_tolerance` |
| S12 | `test_empty_is_an_answer`, `test_anchor_not_found_distinct` |

## 9. Amendments

1. **2026-11-20, Phase C: the path depth cap.** The text said the path cap is "default 6, at
   most the card's cap". But both cards cap walks at 3 (`max_traversal_depth`), so a path could
   never reach its own default. Paths now have their own cap: default 6, at most 10. The card's
   traversal cap still bounds `expand` and every walk. Found while writing the validator; no
   code had used the old text.
2. **2026-11-20, Phase C: four gaps found while converting the kill-test v3 requests.**
   - **Strings order by code point.** The text allowed only `=` and `<>` on strings, while
     ranking and `min`/`max` already ordered them.
   - **`number_text` has a meaning:** the number it spells, else missing. S1–S12 never said.
   - **A missing or null key sorts last in either order** (S8). It matters for `rank` and for a
     ranked `groupby`, whose empty groups have `null` avg, min, max and median.
   - **`groupby` takes `end_conds`:** conditions on the walk's end nodes. For example, "per
     group, how many of its techniques run on Linux".
   - **`Values` returns one value per node that has the property**, and reports how many nodes
     lacked it. Nothing returns a null row.

   No compiler existed yet. The v3 compilers differ on the last three, and those requests are
   flagged by `from_v3.semantic_differences`.
