# Step 7b — Render the Verified Synthesis Answer in the Web Workbench

## 1. Introduction

Steps 6–7 made the API's `answer` SSE event carry a new `synthesis` payload: the verified answer (claims with citations and per-claim verdicts, `rendered_claims` safe to show as fact, enforced abstentions with the executed query as proof — or the Step 7 boundary form where no query was executed because the source doesn't model the asked-about entity), plus the verification roll-up (supported/unsupported counts, unsupported-claim rate, repaired abstentions) and composer provenance (deterministic vs LLM, fallback reason). The field was added additively, so the Next.js workbench under `web/` still renders only the legacy `headline`/`sections`/`cross_source`/`unsupported` surface — none of the new trust-bearing information (the whole point of Step 6: the answer that proves itself) is visible to the analyst.

This plan wires `answer.synthesis` through the web app end to end: TypeScript contract types mirroring `SynthesizedAnswer.to_dict()` exactly, a pure adapter in `web/lib/adapt.ts` (the established seam where server payloads become UI types), a verified-answer block in `AnswerCard` following the Woven Dusk idiom already in the file (mono uppercase section labels, shadow-as-border, teal/amber accents, provenance chips), and updated seeded fixtures so both demo turns — the WMI positive and the CAPEC-557 honest-empty — showcase the new surface without a live backend. Validation follows the repo's mandatory webfront gates: Vitest contract tests, `npm run lint`, `npm run build`, plus a live end-to-end smoke through `app.py`'s two processes.

## 2. Gaps & Unanswered Questions

- **Where should synthesis render?** *Assumption*: inside `AnswerCard` as a distinct "Verified answer" region between the prose paragraphs and the join-candidates footer — it is the assistant turn's trust surface, not inspector detail. The raw payload stays available via the existing Raw JSON tab (`rawAnswer` already retains the whole `ServerAnswer` verbatim, which now includes `synthesis`).
- **How much of the payload to show?** *Assumption*: all analyst-meaningful parts — verification pill (`N/M claims verified · X% unsupported · R repair(s)`), rendered claims with citation chips (reusing `ProvenanceChip` targets like the existing section chips), abstentions with their statement and query proof in mono (or the boundary wording with an explicit "no query executed" proof line), flagged/cut claims with verdict reasons styled as warnings, notes, and the composer/fallback line when the LLM path degraded. Nothing hidden: honesty is the demo.
- **Old conversations without `synthesis`?** The field is optional server-side history may lack it. *Assumption*: `synthesis?: ServerSynthesis | null` — the block renders nothing when absent, keeping old fixtures/replays valid.
- **Seeded fixtures.** The two demo turns were captured before Step 6. *Assumption*: extend both with faithful synthesis payloads (WMI: two supported cited claims + correlation; CAPEC-557: zero claims, one abstention carrying the exact executed Gremlin query) built to the same shapes `to_dict()` emits, so `buildRun` exercises the real adapter path.
- **Screenshot-level verification.** `app.py` starts both processes; the plan verifies live by streaming a real query through the Next proxy and asserting the synthesis payload arrives, plus the mandatory `npm run build`. A browser screenshot is a bonus if the preview tooling cooperates; it is not a gate.

## 3. Hierarchical Step-by-Step Instructions

#### Step 1: Contract types + adapter
- **Locations**: `web/lib/types.ts` (new `SynthesisCitation`, `SynthesisVerdict`, `SynthesisClaim`, `SynthesisAbstention`, `SynthesisVerification`, `ServerSynthesis`; `ServerAnswer.synthesis?`), `web/lib/adapt.ts` (new `buildSynthesis()` producing a UI-ready `SynthesisView`; `AnswerContent` gains `synthesis`), `web/lib/__tests__/adapt.test.ts`.
- **Rationale**: The adapter layer is the app's single seam between server payloads and UI types; typing the payload exactly as `SynthesizedAnswer.to_dict()` emits it keeps the Raw JSON tab truthful and the renderer simple. Tests cover: supported claims map to citation chips, abstention query-proof vs boundary (empty query) forms, flagged claims carry verdict reasons, absent `synthesis` yields a null view.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, commit changes to git (no push) stating: Web Synthesis Rendering (1/4) Complete: synthesis contract types and adapter with tests.

#### Step 2: AnswerCard verified-answer block
- **Locations**: `web/components/center/AnswerCard.tsx` (new `SynthesisBlock` subcomponents), reusing `ProvenanceChip`, `SHADOW`, Woven Dusk tokens.
- **Rationale**: The analyst-facing surface: verification pill (teal when `ok`, amber when repairs/cuts occurred), rendered claims with inline citation chips, abstention rows with the honest statement and the executed-query proof in Geist Mono (boundary abstentions show "no query executed — source boundary" instead of inventing one), cut claims visibly flagged with reasons, composer fallback note. Follows the file's existing idiom (mono uppercase labels, `boxShadow` borders) so the block reads native.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, commit changes to git (no push) stating: Web Synthesis Rendering (2/4) Complete: verified-answer block in AnswerCard.

#### Step 3: Seeded fixtures + fixture tests
- **Locations**: `web/lib/fixtures.ts` (synthesis payloads for `wmiCapecRun` and `deprecatedCapecRun`), `web/lib/__tests__/fixtures.test.ts`.
- **Rationale**: The seeded conversation is the zero-backend demo; both turns must showcase the new surface — the positive turn with verified cited claims, the abstention turn proving the honest-empty with its executed query. Fixture tests pin that both runs adapt into non-null synthesis views with the expected claim/abstention counts.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, commit changes to git (no push) stating: Web Synthesis Rendering (3/4) Complete: seeded demo turns carry verified synthesis.

#### Step 4: Full validation, docs, merge
- **Locations**: `cd web && npm test && npm run lint && npm run build` (mandatory per global rules), `uv run python -m pytest api/ -q`, live smoke via `python app.py` (stream a query through the Next proxy, assert `answer.synthesis` arrives and the page renders), `docs/structure.md` (web row mention), `docs/changelog.jsonl`, merge worktree → `main`, regression re-run on main.
- **Rationale**: Webfront changes ship only with a green production build; the live smoke proves the launcher's two processes still compose and the new payload crosses the proxy. Docs record that the workbench now renders the verified answer.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, commit changes to git (no push) stating: Web Synthesis Rendering (4/4) Complete: build green, live smoke passed, merged to main.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Synthesis contract types | Exact TS mirror of `SynthesizedAnswer.to_dict()` on the `answer` event | `web/lib/types.ts` |
| Synthesis adapter | Pure `buildSynthesis()` → UI view (claims, abstentions, verification, flags) | `web/lib/adapt.ts` |
| Verified-answer block | Woven Dusk rendering: verification pill, cited claims, abstention + query proof, cut-claim flags | `web/components/center/AnswerCard.tsx` |
| Seeded synthesis fixtures | Both demo turns carry faithful synthesis payloads | `web/lib/fixtures.ts` |
| Adapter/fixture tests | Vitest contract tests incl. boundary abstention form | `web/lib/__tests__/adapt.test.ts`, `web/lib/__tests__/fixtures.test.ts` |
| Green gates | `npm test`, `npm run lint`, `npm run build`, api pytest, live `app.py` smoke | `web/`, `api/` |
| Docs | Structure note + changelog entries per phase | `docs/structure.md`, `docs/changelog.jsonl` |
