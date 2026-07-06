# Step 8 — End-to-End Integration & Pipeline Wiring Plan

## 1. Introduction

This plan delivers the Wk 10–11 roadmap row (`docs/goals.md`): connect planner → specialist
agents → synthesis into one proven pipeline, test the full credential-theft flow, and resolve
inter-agent format mismatches. Scouting confirmed the chain already *runs* — `utils/specialists/cli.py::run_query_command`
and `api/services/query.py::stream_query_events` both do plan → specialists → federation →
synthesize, and the web workbench already streams the same pipeline live over `POST /api/query`
SSE. What is missing is not wiring but *proof and hardening*: the four inter-agent seams have no
contract tests, the `partial`/status/exit-code logic is duplicated (and can drift) between the CLI
and the API, there is no single `run_pipeline` orchestrator, no snapshot-derived gold for the
proposal's flagship credential-theft query, no per-stage latency capture, and no integration test
layer distinct from the single-source golden suites.

The approach follows the source plan (`4.end-to-end-integration-plan.md`) adjusted to reality:
the P0 source-card work is already largely satisfied by the committed `card_enrichment.py`
ENRICHMENT layer (safety limits 1000 rows / depth 3 / 5000 ms match the specialist env defaults),
so P0 reduces to *proving* the limits flow card→plan→task and surfacing them in `--plan` output.
The central A-vs-B decision (parallel+join vs dependent sequencing) is settled empirically in the
credential-theft golden-flow step, with dependent sequencing built only if the parallel
architecture fails the snapshot-derived gold. Front end and back end are both exercised: the API
gains one `run_pipeline` entry point plus per-stage latency, and the web workbench surfaces the
new fields with the full vitest/lint/production-build/live-smoke gates. Model drafts,
deterministic code grades — integration adds no new intelligence.

---

## 2. Gaps & Unanswered Questions

- **Defining the "credential theft" CAPEC set.** The gold must be computed from the pinned
  snapshot (CAPEC 3.9 / ATT&CK v19), never hand-keyed. *Assumption:* select CAPEC patterns whose
  name/description matches a small, committed anchor list of credential-theft terms (e.g.
  "credential", "password", "authentication bypass" family), computed deterministically by a gold
  script over `data/raw`, with the selection rule recorded next to the gold. The anchor list is
  reviewable; the resulting IDs are derived.
- **A vs. B architecture.** Decided empirically in Step 4 (Phase 2 gate) — not pre-committed.
- **Dependency encoding (only if B).** *Assumption:* join-derived ordering — the source that
  *produces* the canonical join key runs first — preferred over a new `depends_on` field, per the
  source plan's stated preference, to avoid new plan surface area.
- **Seed-set bound (only if B).** *Assumption:* cap injected `seed_ids` at the consumer task's
  `max_result_rows`; truncation recorded as an honest note on the result, never silent.
- **Total-pipeline timeout.** *Assumption:* new `PIPELINE_TIMEOUT_S` env (default 120 s) enforced
  in `run_pipeline`, above the per-query 5 s bound.
- **Overlay files vs ENRICHMENT.** Overlays on disk are gitignored dead code; the committed
  enrichment layer is authoritative. *Assumption:* verify + document this rather than resurrect
  overlays. No human input needed.
- **UI scope.** Full rendering of tables/figures/diagrams stays out of scope (later roadmap row);
  the front end here surfaces per-stage latency and any new pipeline fields, and proves the live
  E2E flow in the workbench.

---

## 3. Hierarchical Step-by-Step Instructions

> Session directive: **commit only, never push** (user override of the global-rules push wording).
> Each step ends with a `docs/changelog.jsonl` entry + `git commit` on the worktree branch.

### Step 1: Predecessor proof — card limits flow + `--plan` visibility + seam freeze
- **Locations:** `utils/planner/cli.py` (`run_plan_command` summary), `utils/planner/cards.py`
  (`SourceCardView.limits`), `utils/planner/card_enrichment.py` (read-only verify),
  `docs/specialist_agents.md` (seam-freeze note), new test in `utils/planner/tests/`.
- **Rationale:** Integration under wrong or absent safety limits is not faithful. The limits are
  already authored in the committed enrichment layer and match the specialist env defaults
  (1000/3/5000 vs `SPECIALIST_MAX_RESULT_ROWS=1000`, `SPECIALIST_QUERY_TIMEOUT_MS=5000`); what is
  missing is the "done when" proof: `--plan` must show both sources routed with limits populated
  from the cards, not fallback zeros, and a test must pin card-limits == specialist env defaults
  so a future mismatch fails loudly. The four boundary contracts (`Plan → SpecialistTask`,
  `Specialist → SpecialistResult`, `results → FederatedEvidence`,
  `FederatedEvidence → SynthesizedAnswer`) are declared integration-frozen in the docs.
- **Action:** Undergo the verification/tests/validation process for this phase (planner test suite
  incl. gate corpus; live `uv run main.py --plan` on the credential-theft question shows per-source
  limits). Once validated, commit stating: *E2E Integration (1/8) Complete: proved card→plan limit
  flow, surfaced limits in --plan output, froze the four integration seams.*

### Step 2: Seam audit — contract tests + one shared status helper
- **Locations:** new `utils/specialists/tests/test_seams.py`; new shared helper (e.g.
  `utils/specialists/status.py`) extracting the duplicated `partial`/status/exit-code rule;
  callers `utils/specialists/cli.py::run_query_command`, `utils/specialists/federation.py`
  (`run_plan` partial aggregation), `api/services/query.py` (`_status_and_exit`, evidence
  bundling).
- **Rationale:** Integration failures live at the seams. Four hermetic contract tests (LLM off,
  fake connectors): (1) `SpecialistTask.from_sub_question` drops no field the specialist relies on;
  (2) every `EvidenceRecord` carries non-null `Provenance` and Gremlin results never leak
  non-ATTACK join values; (3) `partial` is computed by one function used by CLI, federation, and
  API so they cannot drift; (4) `synthesize()` output only renders claims resolving to retrieved
  records, empties become abstentions with query proof. The `partial` rule currently exists in
  three places verbatim — that is a latent drift bug.
- **Action:** Undergo the verification/tests/validation process for this phase (new seam tests +
  full `utils/specialists`, `utils/synthesis`, `api/tests` hermetic suites). Once validated, commit
  stating: *E2E Integration (2/8) Complete: four seam contract tests green and CLI/API/federation
  share one partial/status computation.*

### Step 3: Credential-theft gold — snapshot-derived expected result
- **Locations:** `utils/specialists/evalset/gold_bank.py` (reuse `attack_mappings` CAPEC→T-IDs and
  `technique_mitigations`), new gold derivation (e.g. `utils/specialists/evalset/federated_gold.py`
  + committed JSON artifact), tests in `utils/specialists/evalset/tests/` pinning the census.
- **Rationale:** Phase 2's decision gate needs a hand-checkable gold: (a) credential-theft CAPEC
  patterns and their ATTACK-taxonomy `MAPS_TO` T-IDs, (b) each T-ID's `MITIGATES` mitigations,
  (c) the expected cross-source correlation set (T-IDs on both sides). Both underlying maps
  already exist in the gold bank — this step composes them under the committed anchor-term
  selection rule and pins counts with anchor tests, matching the Step 5/7 discipline (gold
  computed from `data/raw`, regeneration-matches-committed).
- **Action:** Undergo the verification/tests/validation process for this phase (evalset suite green;
  gold regenerates byte-identical). Once validated, commit stating: *E2E Integration (3/8)
  Complete: snapshot-derived credential-theft gold (CAPEC set, T-ID mappings, mitigations,
  expected overlap) committed with anchor tests.*

### Step 4: The decision gate — run Option A live, grade against gold, record verdict
- **Locations:** live run via `uv run main.py --query` (and/or a capture script in
  `utils/specialists/evalset/`); verdict recorded in `docs/changelog.jsonl`; captured
  `FederatedEvidence`/`SynthesizedAnswer` snapshots to the evalset dir if useful.
- **Rationale:** The central design decision must be made on evidence. Grade three things:
  (a) did the parallel ATT&CK sub-question return mitigations for the T-IDs CAPEC actually
  surfaced, or a broader/narrower set; (b) does the synthesis correlation set equal the expected
  overlap; (c) were any expected technique→mitigation pairs silently dropped by the differently
  scoped parallel query. Decision rule: faithful → keep parallel, mark Step 5 not-needed, record
  why; over-/under-fetch or dropped pairs → build dependent sequencing in Step 5.
- **Action:** Undergo the verification/tests/validation process for this phase (live run captured,
  grading script output committed alongside the written A-vs-B verdict). Once validated, commit
  stating: *E2E Integration (4/8) Complete: credential-theft flow graded against snapshot gold;
  A-vs-B verdict recorded with evidence.*

### Step 5: Dependent sub-question sequencing *(conditional — only if Step 4 says B)*
- **Locations:** `utils/planner/gate.py` (+ join-derived ordering validation: acyclic, both
  endpoints exist), `utils/planner/drafter.py` (consumer sub-question drafted seed-driven),
  `utils/specialists/federation.py::SpecialistRouter.run_plan` (topological pass: run producer,
  harvest T-prefixed `join_values`, inject into consumer `seed_ids` — the field already exists —
  bounded by the consumer's `max_result_rows` with honest truncation notes), guardrails (zero
  producer join values → consumer skipped → honest abstention via the existing empty-source path;
  total-pipeline timeout).
- **Rationale:** Only built if parallel demonstrably fails the gold. Sequencing changes *what the
  consumer is asked*, never who composes: federation still hands off evidence, synthesis still
  owns the join and prose. Independent sub-questions keep the existing path unchanged.
- **Action:** Undergo the verification/tests/validation process for this phase (sequenced
  credential-theft run reproduces the gold overlap and per-technique mitigations; hermetic
  sequencing tests; independent plans unchanged). Once validated, commit stating: *E2E Integration
  (5/8) Complete: join-derived dependent sequencing with bounded seed injection reproduces the
  credential-theft gold.* (If skipped, record the skip + reason in the changelog instead.)

### Step 6: One `run_pipeline` orchestrator + degradation semantics + latency hooks
- **Locations:** new `utils/specialists/pipeline.py` (or similar) exposing
  `run_pipeline(question, *, use_llm, ...)` returning plan, evidence, answer, status, exit code,
  and per-stage timings; rewire `utils/specialists/cli.py::run_query_command` and
  `api/services/query.py::stream_query_events` (API keeps SSE by wrapping the same steps via
  stage callbacks/iterator); degradation tests (ATT&CK-down, CAPEC-down, both-up-one-empty,
  unsupported-part-present) in `utils/specialists/tests/`; provenance end-to-end assertion;
  `PIPELINE_TIMEOUT_S`.
- **Rationale:** CLI and API currently re-implement plan→run→bundle→synthesize; one orchestrator
  makes divergence impossible and gives the Wk 11–13 evaluation its per-stage wall-clock hooks
  (plan, each specialist, synthesis) without re-instrumentation. Every rendered claim's citation
  must resolve back through `FederatedEvidence` to a `Provenance` block with the executed query
  and timestamp. With `SPECIALIST_LLM_ENABLED=false` and `SYNTHESIS_LLM_ENABLED=false` the
  pipeline must be reproducible (same input → same answer).
- **Action:** Undergo the verification/tests/validation process for this phase (all hermetic
  suites + api contract tests green; determinism double-run check; live CLI smoke). Once
  validated, commit stating: *E2E Integration (6/8) Complete: single run_pipeline orchestrator
  shared by CLI and API with degradation tests, provenance threading, and per-stage latency.*

### Step 7: Integration test layer + federated golden set + live acceptance
- **Locations:** new `utils/specialists/tests/test_integration_pipeline.py` (mocked specialists →
  orchestrator routes/bundles/synthesizes/status correct, hermetic); new live acceptance test
  (`@pytest.mark.live`-style, skips when stack down) asserting the credential-theft answer's
  supported-claim set and correlation set match the Step 3 gold, unsupported rate 0 %, provenance
  complete; a small federated golden set (~5–8 genuinely cross-source questions) in
  `utils/specialists/evalset/` with gold computed from the pinned snapshot; wired into
  `uv run pytest`.
- **Rationale:** Integration tests prove plumbing correctness and reproducibility — distinct from
  the Wk 12–13 scored evaluation. The existing 53 golden are single-source; cross-source
  regressions currently have zero coverage.
- **Action:** Undergo the verification/tests/validation process for this phase (hermetic
  integration tests green; live acceptance green against Neo4j+Gremlin; federated golden set green
  live). Once validated, commit stating: *E2E Integration (7/8) Complete: hermetic integration
  layer, live credential-theft acceptance test, and federated golden set all green.*

### Step 8: Front-end surfacing + docs + full regression + merge
- **Locations:** web: `web/lib/types.ts`, `web/lib/adapt.ts`, run views (surface per-stage latency
  from the new pipeline timings; sequenced-federation indicator if Step 5 built; keep Raw JSON
  truthful), vitest in `web/lib/__tests__/`; docs: `docs/structure.md`,
  `docs/specialist_agents.md` (run_pipeline entry point, parallel-vs-sequenced behavior, frozen
  seams, test layer), `docs/goals.md` Wk 10–11 checkbox, README status; full regression
  (`uv run pytest` across `utils/` + `api/`, `cd web && npm test && npm run lint && npm run build`);
  live smoke through `python app.py` running the credential-theft question in the workbench;
  merge worktree into local `main` (no push).
- **Rationale:** The user's directive is front end + back end testable end-to-end: the workbench
  must demonstrably run the flagship flow live against the real stack, and webfront changes only
  ship with a green production build per global rules. Docs must describe the integration shape
  before it lands; merge only at 100 % green.
- **Action:** Undergo the verification/tests/validation process for this phase (full regression +
  build + live app smoke). Once validated, commit stating: *E2E Integration (8/8) Complete: web
  surfaces pipeline latency and the live credential-theft flow, docs and roadmap updated, full
  regression green, merged to main.*

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| `--plan` limits visibility | Per-source safety limits printed in plan summary, proving card→plan flow | `utils/planner/cli.py` |
| Card/env limits agreement test | Pins enrichment safety limits == specialist env defaults | `utils/planner/tests/` |
| Seam contract tests | Four hermetic tests over the frozen inter-agent seams | `utils/specialists/tests/test_seams.py` |
| Shared status helper | One `partial`/status/exit-code computation for CLI, federation, API | `utils/specialists/status.py` (new) |
| Credential-theft gold | Snapshot-derived CAPEC set, T-ID mappings, mitigations, expected overlap + anchor tests | `utils/specialists/evalset/federated_gold.py` + committed JSON |
| A-vs-B verdict | Evidence-backed decision on parallel vs sequenced federation | `docs/changelog.jsonl` (+ grading capture in evalset) |
| Dependent sequencing (conditional) | Topological producer→consumer pass with bounded `seed_ids` injection | `utils/specialists/federation.py`, `utils/planner/gate.py` |
| `run_pipeline` orchestrator | Single entry point with stage callbacks, timings, total timeout | `utils/specialists/pipeline.py` (new), rewired `cli.py`, `api/services/query.py` |
| Degradation tests | ATT&CK-down / CAPEC-down / one-empty / unsupported-part, exit codes asserted | `utils/specialists/tests/` |
| Integration test layer | Mocked-specialist pipeline tests + live credential-theft acceptance test | `utils/specialists/tests/test_integration_pipeline.py` |
| Federated golden set | ~5–8 cross-source questions with snapshot gold, green live | `utils/specialists/evalset/` |
| Web latency/pipeline surfacing | Per-stage timings (+ sequencing indicator if built) in the workbench | `web/lib/types.ts`, `web/lib/adapt.ts`, components |
| Docs + roadmap | Integration shape documented; Wk 10–11 checked off | `docs/structure.md`, `docs/specialist_agents.md`, `docs/goals.md` |
