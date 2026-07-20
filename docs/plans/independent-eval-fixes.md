# Plan — Independent-Eval Fixes

## 1. Introduction

The independent cross-model evaluation (`docs/evaluation/independent-eval-analysis.md`)
surfaced four actionable items: one **judging-harness artifact** that depressed the
measured faithfulness/groundedness, one **measurement blind spot**, and two genuine
pipeline defects (**under-enumeration** and **C-ABS hierarchy role labeling**). This
plan implements all four, in an order chosen so each later step can be measured by an
earlier one: fix the serializer first (honest baseline), add the coverage metric
second (a cheap deterministic yardstick), then fix under-enumeration (measured by that
yardstick), and finally the narrow C-ABS bug.

The work happens in a dedicated git worktree branched off local `main`, with a commit
+ `docs/changelog.jsonl` entry per step and no push (per the standing project directive
that overrides the global "commit AND push" rule). Every step is validated by its unit
suite before commit. On completion the worktree merges to `main` and is deleted.

## 2. Gaps & Unanswered Questions

- **Enumeration surface** — *Resolved by user*: surface the full id set via a
  **structured enumeration claim** (`kind="enumeration"`) rather than cramming ids into
  the short-prose narrative. The narrator stays 2–5 sentences and references the
  structured list; completeness lives in the trust surface.
- **What counts as an "enumerative" question** — *Assumption*: add an
  `is_enumerative_request` intent helper (which/what/list/all + a plural relationship
  noun), mirroring `is_definitional_request`. The composer emits the enumeration claim
  only for single-anchor results whose question is enumerative and whose record carries
  a `related`/`join_values` set larger than the existing citation sample.
- **Coverage-metric target** — *Assumption*: the new metric scores gold
  `must_include_related` + `must_include_ids` ids **surfaced in the answer** (claim
  `entity_ids` ∪ enumeration ids ∪ narrative text), distinct from `mapping_recall`
  which already measures retrieval into the pool. This is what makes under-enumeration
  visible deterministically.
- **C-ABS abstraction source** — *Assumption*: derive the standard/meta label from edge
  **role order** (parent = standard, grandparent = meta) and carry the ancestor's own
  `Abstraction` property when present, so the label is both positional and grounded.
- **Live re-run of the 120-agent panel** — Out of scope for this plan's automated
  validation (it needs the live stack + Sonnet fleet, and is user-triggered/billed). The
  plan leaves the serializer correct so the panel *can* be re-run; the re-run itself is
  a separate user action.

## 3. Hierarchical Step-by-Step Instructions

### Step 0: Worktree setup
- **Locations**: new worktree `.claude/worktrees/independent-eval-fixes` off local `main`;
  symlink the gitignored `.env` and `data/` from the primary checkout.
- **Rationale**: Isolate the change set; the pipeline needs the live `.env`/`data`
  symlinks to run any live-touching validation, and merges must start from local `main`.
- **Action**: Create the worktree, reset onto local `main`, symlink `.env` + `data/`.
  No commit (setup only).

### Step 1: Fix the judging serializer (Bucket A)
- **Locations**: `utils/evaluation/generate_e2e.py` — `_record_dict` (and constants
  `_MAX_RECORDS_PER_RESULT`, `_MAX_RELATED_PER_RECORD`). Mirror the narrator's own
  context builder in `utils/synthesis/llm_composer.py` (`_record_context`,
  `_related_entry`, `_MAX_FACETS_PER_RECORD`).
- **Rationale**: The judge artifact dropped `properties` (kept only `description`) and
  `facets` entirely, and capped records at 40 (below the narrator's 50), so faithful,
  grounded answers were flagged as hallucinations. Adding a bounded `properties` block +
  the `facets` list and lifting the cap to 50 gives the judge the same evidence the
  narrator had. Pure judging-side change — no pipeline behavior impact.
- **Validation**: `uv run python -m pytest utils/evaluation/tests/` green; a targeted
  unit asserts a serialized record carries `properties` (a non-description scalar) and
  `facets`. Spot-regenerate one federated case JSON and confirm `facets`/`properties`
  present.
- **Action**: Once validated, commit stating: Independent-Eval Fixes (1/4) Complete:
  serializer now emits bounded properties + facets and a 50-record cap.

### Step 2: Add the answer-coverage deterministic metric (meta-finding)
- **Locations**: `utils/evaluation/score_e2e.py` — new `score_answer_coverage(entry,
  answer)`, a `coverage` field on `E2ECase` (+ `to_dict`), wired through `evaluate_case`
  and surfaced in `aggregate`/`build_e2e`. Tests in
  `utils/evaluation/tests/test_score_e2e.py`.
- **Rationale**: Today `mapping_recall` measures gold ids in the *retrieved pool* (≈1.0),
  so under-enumeration is invisible to the deterministic scorers — which is why the
  self-judge looked flawless. A metric over gold `must_include_related` +
  `must_include_ids` *surfaced in the answer* exposes the gap and becomes the yardstick
  for Step 3.
- **Validation**: `uv run python -m pytest utils/evaluation/tests/` green; new tests
  cover full coverage (1.0), partial (a sampled subset), and no-gold (None/1.0). Confirm
  the aggregate block includes the new metric without breaking `test_e2e_report`.
- **Action**: Once validated, commit stating: Independent-Eval Fixes (2/4) Complete:
  added answer-coverage metric exposing under-enumeration deterministically.

### Step 3: Fix under-enumeration via a structured enumeration claim (Bucket B)
- **Locations**: `utils/planner/intent.py` — new `is_enumerative_request`;
  `utils/synthesis/contracts.py` — allow `kind="enumeration"` (if kind is validated);
  `utils/synthesis/composer.py` — `DeterministicComposer.compose` emits an enumeration
  `Claim` listing the full `related`/`join_values` id set for enumerative single-anchor
  results, and `_narrative` references it ("all N, listed below"); narrator prompt in
  `utils/synthesis/narrator.py` softened so it defers the full list to the structured
  claim instead of inventing/omitting. Tests in `utils/synthesis/tests/test_composer.py`.
- **Rationale**: Retrieval is perfect but the composer's fact claim samples 3 ids and the
  narrator is instructed to summarize; on "which/what" questions the gold wants the whole
  set. A structured enumeration claim carries the complete, cited id list into the trust
  surface while keeping prose short — the shape the user selected.
- **Validation**: `uv run python -m pytest utils/synthesis/tests/` green; a new test
  feeds a single-anchor result with N>sample related ids to an enumerative question and
  asserts an `enumeration` claim with all N cited ids. Re-run Step 2's coverage metric on
  a fixture to confirm it now reports full coverage where it previously reported a sample.
- **Action**: Once validated, commit stating: Independent-Eval Fixes (3/4) Complete:
  composer emits a full structured enumeration claim for which/what questions.

### Step 4: Fix C-ABS hierarchy role labeling (Bucket C)
- **Locations**: `utils/specialists/gremlin/normalizer.py` —
  `_normalize_hierarchy` (~L540) tags each ancestor `{"id", "role":
  "parent"|"grandparent", "name", "abstraction"}` instead of a bare `{"id"}`;
  composer/narrator wording so the standard vs meta ancestor is labeled, and a guard so
  the narrator never asserts "evidence absent" when `related` is non-empty. Tests in
  `utils/specialists/gremlin/tests/` (or `test_contracts`) and
  `utils/synthesis/tests/test_narrator.py`.
- **Rationale**: The normalizer flattened parent (standard) and grandparent (meta) into
  one unordered `related` list, discarding the role labels, so the narrator could not
  distinguish them and once (C-ABS-01) falsely claimed the ancestors were absent.
  Preserving role + carrying the `Abstraction` property restores the distinction and
  kills the one true hallucination.
- **Validation**: `uv run python -m pytest utils/specialists/gremlin/tests/
  utils/synthesis/tests/` green; a new normalizer test asserts role/name on ancestors; a
  narrator/composer test asserts no "evidence absent" phrasing when `related` is
  populated.
- **Action**: Once validated, commit stating: Independent-Eval Fixes (4/4) Complete:
  hierarchy ancestors carry role labels; narrator labels standard vs meta.

### Step 5: Merge & clean up
- **Locations**: `main` branch; the `independent-eval-fixes` worktree.
- **Rationale**: The project rule merges a fully-functional branch to `main`; worktrees
  must not accumulate.
- **Validation**: Full relevant suites green on the merge commit
  (`utils/evaluation`, `utils/synthesis`, `utils/specialists`); resolve any conflicts
  against concurrent `main` movement (regenerate derived artifacts if needed).
- **Action**: Merge to `main`, commit the merge (no push), then `git worktree remove`
  the worktree and prune.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Serializer fix | `_record_dict` emits bounded `properties` + `facets`, 50-record cap | `utils/evaluation/generate_e2e.py` |
| Serializer tests | Assert `properties`/`facets` present on a serialized record | `utils/evaluation/tests/test_score_e2e.py` (or new `test_generate_e2e.py`) |
| Coverage metric | `score_answer_coverage` + `E2ECase.coverage` + aggregate wiring | `utils/evaluation/score_e2e.py` |
| Coverage tests | Full / partial / no-gold coverage cases | `utils/evaluation/tests/test_score_e2e.py` |
| Enumerative intent | `is_enumerative_request` helper | `utils/planner/intent.py` |
| Enumeration claim | Structured full-id-list claim for which/what questions | `utils/synthesis/composer.py`, `utils/synthesis/contracts.py` |
| Enumeration tests | N>sample related → enumeration claim with all ids | `utils/synthesis/tests/test_composer.py` |
| Hierarchy role fix | Ancestors carry role/name/abstraction; narrator labels + no false-absent | `utils/specialists/gremlin/normalizer.py`, `utils/synthesis/narrator.py` |
| Hierarchy tests | Role on ancestors; no "evidence absent" when related non-empty | `utils/specialists/gremlin/tests/`, `utils/synthesis/tests/test_narrator.py` |
| Changelog entries | One per step (4) | `docs/changelog.jsonl` |
