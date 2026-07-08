# Plan — Answer-card UX overhaul + real LLM final answer

## Introduction

Four analyst-facing changes to the workbench answer surface (`web/components/center/*`)
and the synthesis/health layers (`utils/synthesis/*`, `api/services/*`):

1. **Collapsible sections** — the stacked answer sections (source findings,
   Verified answer, Claim table, Network plot) become clean disclosures, each
   showing a count when closed. The final answer stays open by default.
2. **Plain-English network plot** — replace the jargon caption ("provenance-exact
   CAPEC→ATT&CK mappings from the federation join index") and drop the
   confusing `⇢ sequenced: q2 seeded with 18 join value(s) from q1` note.
3. **Real LLM final answer** — the synthesis composer emits an actual prose
   answer to the question, grounded in the gathered evidence, used **throughout**
   when the LLM drafter is selected (planner + specialists + synthesis). Add an
   **LLM Live / LLM Dead** health pill beside the Neo4j/Gremlin pills.
4. **Working Copy / Export buttons** — Copy gives clear "Copied ✓" feedback;
   Export actually downloads the evidence JSON with an "Exported ✓" confirmation.

## Decisions (from the user)

- User adds the LLM endpoint to `.env`; when the **LLM drafter** is selected the
  LLM is used across planner, specialists, **and** synthesis.
- Final answer **open** by default; detail sections **collapsed** with counts.
- Add "LLM Live"/"LLM Dead" status pill at the top next to Neo4j & Gremlin.

## Gaps / assumptions

- **Grounding of the prose answer.** The verified claim table stays the trust
  surface; the prose "Final answer" is the composer's narrative (LLM or a
  deterministic summary of the *supported* claims). Assumption: it is acceptable
  to show the narrative provided the verified claims remain visible below it.
- **LLM health probe.** Assume a TCP-reachability probe of the synthesis LLM
  `base_url` host:port is a sufficient live/dead signal (mirrors the graph
  health approach; never raises, fast timeout).
- **Drafter authority.** When drafter = `llm`, synthesis `llm_enabled` is forced
  on (overriding the env default) so "selected" means used everywhere.

## Steps

### Phase 1 — Synthesis prose final answer (backend)
- `utils/synthesis/contracts.py`: add `narrative: str` to `SynthesizedAnswer`
  (+ `to_dict`).
- `utils/synthesis/llm_composer.py`: extend the system prompt to emit
  `final_answer` (a direct prose answer to the request); parse into `narrative`.
- `utils/synthesis/composer.py`: deterministic composer builds a readable
  `narrative` from the headline + supported claim sentences + abstentions.
- `utils/specialists/pipeline.py`: build `synthesis_config` from env with
  `llm_enabled = use_llm` so the drafter toggle governs synthesis too.
- Update/extend `utils/synthesis/tests/*`, `utils/specialists/tests/test_pipeline.py`.
- **Validate:** `uv run python -m pytest utils/synthesis/tests utils/specialists/tests`.
- **Commit** (no push) + changelog entry.

### Phase 2 — LLM Live/Dead health (backend)
- `api/services/health.py`: add `llm_health()` (probe synthesis `base_url`);
  returns backend `llm`, status live/down, reason, model.
- `api/models.py`: add `LlmHealthModel`; add `llm` field to `HealthResponse`.
- `api/main.py`: populate `llm` in `/api/health`.
- Update `api/tests/test_health.py`.
- **Validate:** `uv run python -m pytest api/tests`.
- **Commit** (no push) + changelog entry.

### Phase 3 — Frontend contract (types/adapt/fixtures)
- `web/lib/types.ts`: `SynthesisView.narrative`; `ApiHealth.llm`.
- `web/lib/adapt.ts`: map `narrative`; **remove** the `sequencingNotes` surface
  from the answer footer (keep timings).
- `web/lib/fixtures.ts`: add `narrative` to synthesis fixtures.
- Update `web/lib/__tests__/*`.
- **Validate:** `cd web && npm test`.

### Phase 4 — Frontend UI
- New `web/components/center/CollapsibleSection.tsx` (Woven-Dusk disclosure:
  header label + count badge + chevron; `defaultOpen`).
- `AnswerCard.tsx`: render **Final answer** (narrative) open; wrap Retrieved
  evidence, Verified answer, Claim table, Network plot as collapsed disclosures
  with counts; drop `⇢ sequenced` note; wire Copy/Export feedback.
- `AnswerNetworkPlot.tsx`: plain-English caption + `N nodes · M links` badge.
- `InfraStatusBar.tsx` / `InfraStatusPill.tsx`: render an LLM pill from
  `health.llm`.
- **Validate:** `cd web && npm run lint && npm run build`; preview-verify the
  answer card, LLM pill, Copy/Export.
- **Commit** (no push) + changelog entry.

### Phase 5 — Integrate, verify, merge
- Full suites: `uv run python -m pytest api/tests utils/synthesis/tests utils/specialists/tests`
  and `cd web && npm test && npm run build`.
- Preview-verify end-to-end (collapsibles, LLM pill live/dead, final answer,
  Copy/Export).
- **Commit** (no push) + changelog; merge branch → `main`.

## Deliverables

| # | Area | Files |
|---|------|-------|
| 1 | Prose answer | `utils/synthesis/{contracts,llm_composer,composer}.py`, `utils/specialists/pipeline.py` |
| 2 | LLM health | `api/services/health.py`, `api/models.py`, `api/main.py` |
| 3 | FE contract | `web/lib/{types,adapt,fixtures}.ts` |
| 4 | FE UI | `web/components/center/{CollapsibleSection,AnswerCard,AnswerNetworkPlot}.tsx`, `web/components/header/{InfraStatusBar,InfraStatusPill}.tsx` |
| 5 | Tests | `utils/synthesis/tests/*`, `utils/specialists/tests/*`, `api/tests/test_health.py`, `web/lib/__tests__/*` |

Per-phase: validate, then **commit (do not push)** with a `docs/changelog.jsonl`
entry. Merge to `main` only when everything is green.
