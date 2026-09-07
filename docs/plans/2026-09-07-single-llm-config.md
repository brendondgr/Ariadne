# Single LLM Configuration — Plan (2026-09-07)

## 1. Introduction

Ariadne currently splits its language-model configuration across **five independent
env groups** — `PLANNER_LLM_*`, `SPECIALIST_LLM_*`, `SYNTHESIS_LLM_*`, `EVAL_LLM_*`
and `CONVERSATION_LLM_*` — each with its own `ENABLED / BASE_URL / MODEL / TIMEOUT_S /
MAX_TOKENS`. The web workbench's Settings modal exposes four of them and *not* the one
the chat pane actually uses (`CONVERSATION_LLM_*`, which silently inherits
`SYNTHESIS_LLM_*`). Two of the four it does show are inert for a chat turn:
`SPECIALIST_LLM_ENABLED` does nothing unless the experiment-only
`SPECIALIST_LLM_QUERY_BUILDER` is on, and `EVAL_LLM_*` only affects the offline judge.
So an analyst who opens Settings, fills in an endpoint and flips toggles has no reliable
way to tell which of them made the model answer — which is the "doesn't function as
intended" symptom. On top of that, **no call site in the codebase sends an API key**:
all ten hand-rolled clients POST to `<base_url>/chat/completions` unauthenticated, so
only a local OpenAI-compatible server can ever be used. There is also no model
discovery in the web app (only in the CLI setup wizard), so the model is a free-text
field you must spell exactly right. Finally, the Settings entry point in the header is
labelled a gear but `GearIcon` is drawn as a circle with eight radiating rays — a
sun/light-bulb, not a cog.

The approach is to introduce **one** configuration group, `ARIADNE_LLM_*`, carrying a
provider kind, base URL, model, API key, timeout, token budget and thinking budget; make
every existing per-agent group *inherit* from it (so the ~20 experiment scripts and the
recorded research runs that pin `SPECIALIST_LLM_TIMEOUT_S` and friends still reproduce
byte-for-byte); add a small provider-abstraction layer under `utils/llm/` modelled on
the `llm-integration` skill so OpenAI, Anthropic, Gemini and any OpenAI-compatible local
server (vLLM / llama.cpp / Ollama / LM Studio / DeepSeek) all work; expose live model
discovery over a new `GET /api/llm/models`; and collapse the Settings modal to a single
LLM section with a provider dropdown, a discovered-model dropdown and a Test-connection
button. The gear gets redrawn as an actual cog.

**One menu, not one endpoint.** The complaint was that configuration is *split across
places*, not that a second model is unwanted — so the inheritance already required for
reproducibility becomes the user-facing feature. The modal has one primary Language
Model section (the instance everything uses), and below it a collapsed **Per-stage
endpoints** disclosure listing the five stages — planner, specialist, synthesis,
conversation, evaluator. Each stage reads `inherit` and shows what it is inheriting;
overriding one reveals its own provider / base URL / model / timeout / budget, each with
its own Refresh and Test. Setting a stage back to `inherit` must *delete* its env keys,
not rewrite them with the default's current value — otherwise the override is frozen in
`.env` the moment it is switched off, which is the exact failure shape the changelog
already records twice. `utils/config.py` today has `set_env_values` and no way to unset,
so that helper is part of the work. Every endpoint field in the modal — primary and
override alike — carries a **Refresh** that lists what the server actually serves and a
**Test** that proves a real completion comes back, because a reachable port is not a
working model: the 2026-09-05 run has ten responses with no `choices` key at all while
vLLM was still loading weights.

**The thinking budget is the worst instance of the split and gets one source.** Today it
has three: a global `LLM_THINKING_BUDGET` read in `utils/llm_sampling.py` and sent to
every graded call, a `SYNTHESIS_LLM_THINKING_BUDGET` read only by the composer, and an
implicit `llm_max_tokens // 2` fallback inside `SynthesisConfig.thinking_budget()` that
fires when the second is unset. Nothing anywhere checks the budget against `max_tokens`,
and the project's own record is that a reasoning model given room spends it — 4,134
tokens of answer behind 16,106 characters of preamble, and 42,602 characters when
unbounded. A budget at or above `max_tokens` is therefore not merely useless, it is the
configuration that produces an empty answer, which surfaces as a silent "LLM
unavailable" fallback rather than an error. So the resolved settings carry exactly one
`thinking_budget`, it is **validated to be strictly less than `max_tokens`** at every
layer that can reject it, and a stage that overrides one of the pair overrides both
together — a stage cannot inherit a budget sized for someone else's token cap.

## 2. Gaps & Unanswered Questions

- **Do the per-agent env vars get deleted?** No — and they are now *promoted* to the
  UI's per-stage override rows rather than being hidden hand-edits. They fall back to
  `ARIADNE_LLM_*` when unset. Deleting them would invalidate every arm in
  `docs/research/experiments/` whose PROTOCOL pins them, and the memory note on
  recorded-answer regression requires the deterministic banks to stay byte-identical.
  What makes the menu single is that they live in **one collapsed section of one modal**
  and default to `inherit`, not that they are unreachable.
- **What does "inherit" write to `.env`?** Nothing — it *removes* the key. *Assumption*:
  a new `unset_env_values()` comments the assignment out in place (preserving the line
  and its documentation) and pops it from `os.environ`, so a stage that has ever been
  overridden leaves a readable trace of what it was. Rewriting the key with the default's
  value would silently pin a moving target.
- **What happens when the thinking budget is >= max tokens?** *Assumption*: it is
  refused, not silently repaired. The API rejects the `PUT` with a field error, the modal
  disables Save and says why, and the resolver clamps to `max_tokens - 1` with a logged
  warning as a last resort for a hand-edited `.env` — clamping is the fallback, not the
  primary behaviour, because a value that quietly becomes something else is how this
  codebase has lost runs before.
- **Is a zero thinking budget still allowed?** Yes, and it stays the default. `0` means
  "send no cap", which is what every recorded run that predates the cap did, so leaving
  it at 0 keeps those reproducible. The `< max_tokens` rule applies only to a positive
  value.
- **What replaces `SynthesisConfig.thinking_budget()`'s implicit `max_tokens // 2`?**
  *Assumption*: nothing derives silently any more. The resolved value is whatever the one
  source says; if the operator wants half of max tokens, the UI offers it as a one-click
  suggestion that *writes a real number*. A derived default that changes when an unrelated
  field changes is a second source wearing a disguise.
- **What counts as a passing connection test?** *Assumption*: a real one-token chat
  completion with non-empty content — not a TCP probe and not a `/models` listing. The
  09-05 record shows both of those passing against a server that could not answer. The
  result reports server kind, latency, the model that answered, and the failure reason
  verbatim when it fails.
- **Where does the API key live?** *Assumption*: `ARIADNE_LLM_API_KEY` in the
  git-ignored `.env`, write-only over the API exactly like `NEO4J_PASSWORD` (accepted on
  `PUT`, never returned; `api_key_set: bool` is returned instead).
- **Does one endpoint have to serve every agent?** By default yes, by choice no. Every
  stage inherits the primary instance until it is explicitly overridden in the Per-stage
  endpoints section — so the judge on a second GPU, or a cheap local model for routing
  and a hosted one for the visible answer, is a two-click change instead of a hand-edit.
- **Which stages get an override row?** *Assumption*: the five that have a real read
  site — planner, specialist, synthesis, conversation, evaluator. `SPECIALIST_LLM_*` is
  labelled as experiment-only in the UI, because its `ENABLED` flag is inert unless
  `SPECIALIST_LLM_QUERY_BUILDER` is on and the research record is explicit that the arm
  exists to be measured against, not run.
- **Do we vendor `templates/llmkit/` from the skill?** *Assumption*: no. We take its
  *design* (normalized `Message` / `ChatResponse` / `Usage`, adapters at the boundary,
  `safe_discover` that never raises, split connect/read timeouts) but write a minimal
  `utils/llm/` against the project's existing `requests` idiom, because the ten existing
  clients each parse their own reply shape and a wholesale swap would put the
  reproducibility record at risk for no functional gain.
- **Anthropic / Gemini graded-call parity is unmeasured.** Sampling (`temperature: 0`,
  `seed`) does not translate cleanly to those APIs. *Assumption*: adapters map what maps
  and drop the rest with a logged warning; any *graded* run on a non-OpenAI provider must
  be recorded as its own experiment before a number from it is cited. Flagged, not
  resolved here.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Redraw the gear icon and unblock the entry point
- **Locations**: `web/components/ui/icons.tsx` (`GearIcon`); `web/components/header/HeaderBar.tsx` (title/aria copy).
- **Rationale**: The smallest, fully independent defect. The current path is a circle
  with eight radiating strokes, which reads as a light bulb or a brightness control; a
  cog needs a toothed outer path plus the hub circle. Doing it first means the rest of
  the work is verified through a control that already looks like settings.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`cd web && npm run lint && npm run build`, visual check in the browser pane). Once
  validated, commit stating: Single LLM Config (1/7) Complete: Redrew GearIcon as a real
  cog so the Settings entry point stops reading as a light bulb.

### Step 2: The unified config resolver
- **Locations**: new `utils/llm/config.py` (`LLMSettings`, `LLMProvider` enum,
  `resolve(stage)`, `overridden_keys(stage)`, `env_with_fallback()`); `utils/config.py`
  (new `unset_env_values()` beside `set_env_values`); new `utils/llm/tests/test_config.py`,
  extend `utils/tests/test_config.py`.
- **Rationale**: Everything downstream needs one resolved object. This step defines the
  `ARIADNE_LLM_*` names, the provider kinds, and the two-level lookup
  (`<STAGE>_LLM_X` → `ARIADNE_LLM_X` → hard-coded default) *before* any consumer is
  touched, so the fallback semantics are pinned by tests rather than by five copies of
  `env_str`. `resolve()` must also report **which** fields were overridden and which were
  inherited — the UI needs that to render a stage row as `inherit` versus `custom`, and
  the API needs it to answer what a stage is actually using. `unset_env_values()` is what
  makes "set this stage back to inherit" possible at all; it comments the assignment out
  in place rather than deleting the line, and pops the key from `os.environ` so the
  running API stops seeing it without a restart. `LLMSettings` also owns the **single**
  `thinking_budget` and the `budget < max_tokens` invariant: a `validate()` that returns
  field errors for the API and the UI to render, plus a last-resort clamp with a logged
  warning for a hand-edited `.env`. `max_tokens` and `thinking_budget` are treated as one
  unit for override purposes — overriding either on a stage carries both — so a stage can
  never inherit a budget sized against a different token cap. Tests must assert that with
  no `ARIADNE_LLM_*` and no per-stage vars set, every per-agent config resolves to exactly
  today's values; that set-then-unset returns a stage to inheriting; that a budget >=
  max_tokens is reported invalid; and that a budget of 0 stays valid and means "no cap".
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run python -m pytest utils/llm/tests/ utils/tests/`). Once validated, commit
  stating: Single LLM Config (2/7) Complete: Added the ARIADNE_LLM_* resolver with
  per-stage override tracking and an unset_env_values helper so inherit really clears.

### Step 3: The provider abstraction layer
- **Locations**: new `utils/llm/__init__.py`, `utils/llm/types.py` (`Message`,
  `ChatResult`, `Usage`, `ModelInfo`, `LLMUnavailable`), `utils/llm/client.py`
  (`chat()`, `discover_models()`, `probe()`), `utils/llm/adapters/openai_compat.py`,
  `adapters/anthropic.py`, `adapters/gemini.py`; new `utils/llm/tests/test_adapters.py`,
  `utils/llm/tests/test_discovery.py`.
- **Rationale**: This is where the `llm-integration` skill's content lands — the four
  backends disagree on message shape (Anthropic hoists `system` out of `messages`,
  Gemini uses `contents`/`parts` and `generationConfig`), on auth header
  (`Authorization: Bearer` vs `x-api-key` + `anthropic-version` vs `x-goog-api-key`), on
  token fields (`max_tokens` vs `max_output_tokens`), and on how usage is reported.
  Normalizing once here is what stops `if provider == "anthropic"` from spreading into
  ten call sites. `discover_models()` must never raise into a UI path — it returns a
  result object carrying either models or a human-readable reason — and connect timeout
  must be separate from read timeout so an off GPU box fails in ~2s while a legitimate
  three-minute local generation still completes. `probe()` is the connection test's
  engine and is deliberately stronger than a reachability check: it issues a real minimal
  completion and returns server kind, latency, the model that answered and a verbatim
  failure reason, because the project has already been burned by a server whose port was
  open and whose ten replies carried no `choices` key at all.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run python -m pytest utils/llm/tests/` with mocked transports covering each
  backend's real response shape — no network). Once validated, commit stating: Single LLM
  Config (3/7) Complete: Added utils/llm provider layer with OpenAI-compatible,
  Anthropic and Gemini adapters plus never-raising model discovery.

### Step 4: Route the existing clients through the layer
- **Locations**: `utils/planner/config.py`, `utils/planner/llm_drafter.py`,
  `utils/planner/intent_llm.py`; `utils/specialists/config.py`,
  `utils/specialists/llm_builder.py`; `utils/synthesis/config.py`,
  `utils/synthesis/llm_composer.py`, `utils/synthesis/narrator.py`;
  `utils/evaluation/llm_judge/config.py`, `utils/evaluation/llm_judge/llm_judge.py`,
  `utils/evaluation/harness/correctness_judge.py`, `utils/evaluation/judge_answers.py`;
  `utils/conversation/config.py`, `utils/conversation/llm.py`; and critically
  `utils/llm_sampling.py` (`sampling_params` stops reading `LLM_THINKING_BUDGET` itself
  and takes the resolved settings from its caller) plus
  `utils/synthesis/config.py::thinking_budget` (the implicit `max_tokens // 2` derivation
  is deleted).
- **Rationale**: Each `from_env()` switches to the Step-2 resolver so it inherits
  `ARIADNE_LLM_*`; each client's `requests.post(... /chat/completions)` is replaced by a
  call into `utils.llm.client.chat()`, which for the `openai-compatible` provider issues
  the identical request it does today plus an `Authorization` header when a key is set.
  Prompt construction and reply parsing are deliberately left alone — the graded output
  path must not move. The three thinking-budget sources collapse into the one resolved
  value here: `sampling_params()` is handed the settings instead of reading its own env
  var, and the composer's implicit half-of-max-tokens derivation goes away. That last one
  is a **behaviour change for anyone who set `SYNTHESIS_LLM_MAX_TOKENS` and not the
  budget**, so `.env.example` and the changelog must name it, and the recorded-answer
  regression is the check that the deterministic path is untouched. This is the step that
  makes the single menu actually *reach* every agent, and it is also the riskiest, so the
  recorded-answer regression from the project memory runs here.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run python -m pytest utils/ api/`, plus the deterministic recorded-answer
  regression over both banks diffed excluding clock keys — it must be byte-identical).
  Once validated, commit stating: Single LLM Config (4/7) Complete: Every agent's LLM
  config and transport now resolves through utils/llm with per-agent overrides intact.

### Step 5: Collapse the API contract to one LLM group
- **Locations**: `api/models.py` (`LLMGroup` → provider-aware `LLMSettingsModel` with an
  `inherits: list[str]` field, `LLMConfig` becomes `{default, stages: dict[str, ...]}`,
  `ConfigUpdateRequest.llm` + `ConfigUpdateRequest.llm_stages`, `api_key` write-only +
  `api_key_set`, and an explicit `inherit: list[str]` on a stage update meaning "unset
  these"); `api/services/config.py` (`_LLM_ENV_KEYS` becomes the primary
  `ARIADNE_LLM_*` map plus the per-stage maps; `read_config` reports resolved value *and*
  whether it was inherited; `apply_update` routes cleared fields to `unset_env_values`);
  new `api/services/llm_models.py` (`list_models`, `test_endpoint` — both accept an
  ad-hoc endpoint from the request body so the modal can Refresh/Test a URL the operator
  has typed but not yet saved); `GET /api/llm/models` and `POST /api/llm/test` routes in
  `api/main.py`; `api/services/health.py` (`llm_health` reads the unified settings instead
  of `SynthesisConfig`); `api/tests/test_config.py`, new `api/tests/test_llm_models.py`.
- **Rationale**: The UI can only *be* one menu if the contract behind it is one group with
  optional per-stage deltas. Discovery and the connection test have to be server-side
  because the browser cannot reach a private endpoint or hold the API key, and they must
  accept unsaved form values — a Refresh that only works after Save is the same
  spelling-test problem in a new place. `inherit` as an explicit list rather than a null
  field is what stops "field omitted from a partial update" and "operator cleared this
  field" from being the same wire value. The API key follows the existing
  `neo4j_password` precedent exactly — accepted on `PUT`, never echoed. The
  `thinking_budget < max_tokens` invariant is enforced as a Pydantic model validator on
  the primary and on each stage, so an invalid pair is a 422 with a named field rather
  than a value the server quietly rewrites.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run python -m pytest api/tests/`, including a round-trip test that overriding a
  stage then setting it back to inherit leaves `.env` with the key unset and the stage
  resolving to the primary). Once validated, commit stating: Single LLM Config (5/7)
  Complete: /api/config exposes one provider-aware LLM group plus per-stage overrides,
  with /api/llm/models discovery and /api/llm/test against unsaved values.

### Step 6: Rebuild the Settings modal as one LLM menu
- **Locations**: `web/lib/types.ts` (`ApiConfig`, `ApiConfigUpdate`, new `ApiLLMSettings`,
  `ApiLLMStage`, `ApiModelList`, `ApiLlmTestResult`); `web/lib/api.ts` (`getLlmModels`,
  `testLlm`); `web/components/settings/SettingsPanel.tsx` (delete the four-agent
  `AGENTS`/`LLMSection` loop; one primary section plus the disclosure);
  new `web/components/settings/EndpointFields.tsx` (the shared provider / base URL /
  model / key / timeout / budget block, reused by the primary and by every override so
  the two cannot drift), new `web/components/settings/ModelPicker.tsx` (dropdown fed by
  discovery, **Refresh** button, free-text fallback, three distinct empty states), new
  `web/components/settings/TestConnection.tsx` (**Test** button + verdict line),
  new `web/components/settings/StageOverrides.tsx` (the collapsed per-stage list with
  inherit/custom toggles); `web/components/header/InfraStatusBar.tsx` (pill reads the
  unified group); new `web/lib/__tests__/llmSettings.test.ts`.
- **Rationale**: This is the deliverable the operator asked for. The primary section is
  provider select, base URL, model *picker* rather than a spelling test, API key,
  timeout, max tokens, thinking budget and one enable toggle. Refresh and Test hang off
  `EndpointFields`, so a stage override gets them for free and there is exactly one
  implementation of "ask this URL what it serves". The override list stays collapsed by
  default and each row renders `inherit — <primary model> @ <primary host>` until it is
  switched to custom, which is what keeps the menu single at a glance while still
  exposing the second endpoint. Discovery must be debounced and cancellable (stale-result
  handling keyed to the latest request) so typing a URL does not freeze the modal. Max
  tokens and thinking budget sit side by side in `EndpointFields` with the budget's max
  bound to the token value, live validation on the pair, Save disabled while it is
  violated, and a "half of max" shortcut that writes a real number rather than a
  derivation. An
  unreachable endpoint renders as an ordinary empty state with the reason, never an error
  banner — someone's GPU box being off is a normal condition, not a fault. Switching a
  row back to inherit sends the `inherit` list from Step 5 rather than the primary's
  values. Graph connection and orchestration fieldsets stay as they are.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`cd web && npm run lint && npm test && npm run build`, then drive the modal in the
  browser pane against a live API: Refresh lists real models, Test passes and fails
  legibly, an override round-trips to inherit). Once validated, commit stating: Single
  LLM Config (6/7) Complete: Settings is one LLM menu — provider select, Refresh-backed
  model picker, Test button, and collapsed per-stage endpoint overrides.

### Step 7: Documentation, env template, and end-to-end proof
- **Locations**: `.env.example` (rewrite section 8 around `ARIADNE_LLM_*`, demote the
  per-agent blocks to a documented override appendix); `README.md`;
  `docs/skills/website-architecture/SKILL.md` and `docs/skills/ui-frontend/SKILL.md` if
  the settings contract is described there; `utils/setup_wizard/steps.py` (wizard writes
  the unified group and drops its five-group `LLM_GROUPS` fan-out); `docs/changelog.jsonl`.
- **Rationale**: The complexity the operator hit is as much documentation as code — the
  current `.env.example` spends four blocks explaining which of five endpoints wins.
  Ending with the wizard means CLI setup and web setup write the same keys, which is the
  other half of "only one configuration".
- **Action**: Undergo the verification/tests/validation process for this phase (full
  `uv run python -m pytest utils/ api/`, `cd web && npm run build`, and a real
  `python app.py` boot with a live endpoint configured through the UI, answering one
  question, and one stage pointed at a second endpoint to prove the override path is
  real). Once validated, commit stating: Single LLM Config (7/7) Complete: One documented
  ARIADNE_LLM_* group with optional per-stage overrides across .env, wizard, API and UI,
  proven end to end.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Cog icon | `GearIcon` redrawn as a toothed cog | `web/components/ui/icons.tsx` |
| Unified settings resolver | `ARIADNE_LLM_*` with per-agent override fallback | `utils/llm/config.py` |
| Provider layer | Normalized chat/discovery/probe + 3 adapters | `utils/llm/client.py`, `utils/llm/adapters/` |
| Resolver tests | Pins that unset `ARIADNE_LLM_*` reproduces today's defaults | `utils/llm/tests/test_config.py` |
| Adapter tests | Mocked per-backend response shapes; no network | `utils/llm/tests/test_adapters.py` |
| Discovery tests | Never-raises contract + the three empty states | `utils/llm/tests/test_discovery.py` |
| Unset helper | `unset_env_values()` so "inherit" really clears a key | `utils/config.py` |
| Config API | One `llm` group + per-stage deltas, write-only API key | `api/models.py`, `api/services/config.py` |
| Discovery + test endpoints | `GET /api/llm/models`, `POST /api/llm/test`, both accepting unsaved values | `api/services/llm_models.py`, `api/main.py` |
| API contract tests | Config tests incl. override→inherit round-trip, discovery tests | `api/tests/test_config.py`, `api/tests/test_llm_models.py` |
| Single settings menu | One primary LLM fieldset + collapsed overrides | `web/components/settings/SettingsPanel.tsx` |
| Shared endpoint block | Provider/URL/model/key/timeout fields reused by primary and overrides | `web/components/settings/EndpointFields.tsx` |
| Model picker | Discovery-fed dropdown with **Refresh** + free-text fallback | `web/components/settings/ModelPicker.tsx` |
| Connection test | **Test** button issuing a real completion, verdict line | `web/components/settings/TestConnection.tsx` |
| Per-stage overrides | Collapsed inherit/custom list for the five stages | `web/components/settings/StageOverrides.tsx` |
| Settings unit tests | Inherit/override merge, budget<max validation, stale-discovery handling | `web/lib/__tests__/llmSettings.test.ts` |
| One thinking budget | Three sources collapsed to one resolved, validated value | `utils/llm/config.py`, `utils/llm_sampling.py`, `utils/synthesis/config.py` |
| Env template rewrite | `ARIADNE_LLM_*` primary, per-agent as appendix | `.env.example` |
| Changelog entries | One per step | `docs/changelog.jsonl` |
