# Step 6 — Synthesis Agent with Claim Verification & Abstention

## 1. Introduction

This plan builds the synthesis agent — the final layer of the Ariadne pipeline — and makes its
answer *prove itself*. The agent composes the analyst-facing answer from `FederatedEvidence`
(the specialists' `EvidenceRecord`s, grounded summaries, and join index), then runs a
**deterministic verification pass**: every claim in the draft is checked, citation by citation,
against the actual evidence records that were retrieved. A claim whose cited records do not
support it is cut from the prose and retained as *flagged* in the verification report. This is
the guard against the Step 5 "97% problem" — the query ran, rows came back, but do they support
the sentence the agent wrote?

Paired with verification is **principled abstention**: when a specialist returned `ok=True` with
zero records, the correct output is "the sources don't establish this" — with the executed query
(already persisted on `SpecialistResult.query` / `Provenance.query`) shown as proof — never a
plausible-sounding invention. The design mirrors the planner's proven layering: an LLM composer
behind `SYNTHESIS_LLM_*` env flags with a deterministic composer as the always-on fallback, and a
verifier that is *always deterministic* — the guard must not itself trust the model. Step 5's
golden banks (including the five honest-empty negatives) become the synthesis evalset, measuring
the goals.md synthesis metrics directly: faithfulness, groundedness, unsupported-claim rate.

## 2. Gaps & Unanswered Questions

- **Package location**: synthesis is its own agent per `docs/purpose.md`. *Assumption*: new
  sibling package `utils/synthesis/` mirroring `utils/planner/` layout (contracts, composer,
  llm_composer, factory, verifier, config, tests).
- **No LLM endpoint in `.env`**: `PLANNER_LLM_ENABLED` is unset, so LLM paths are untestable
  live here. *Assumption*: same hybrid pattern as the planner — deterministic composer is the
  default and fully tested; the LLM composer is exercised hermetically (stubbed HTTP) and falls
  back on `ComposerUnavailable`. All suites green with LLM disabled.
- **Cut vs. flag for unsupported claims**: Step 6 text says "cut or flagged". *Assumption*: cut
  from the rendered prose, retained in the verification report with verdict `unsupported` and
  the reason — auditable, never silently shown.
- **What counts as "supported"**: *Assumption*: a claim is supported when (a) every citation
  resolves to a real retrieved record, and (b) every entity ID named in the claim appears in the
  id-pool (primary_id ∪ join_values ∪ related ids, backend-normalized as in
  `golden_runner.id_pool`) of its cited records; cross-source correlation claims must
  additionally be backed by the computed `join_index`. Free-prose claims with no entity IDs and
  no citations are treated as unsupported (composer is required to cite).
- **API answer schema**: the UI consumes the deterministic answer JSON today. *Assumption*:
  extend additively (new `claims`, `verification`, `abstentions` fields; keep `headline`,
  `sections`, `cross_source`) so `web/` keeps rendering without changes; the web UI upgrade is
  out of scope for Step 6.

## 3. Hierarchical Step-by-Step Instructions

#### Step 1: Contracts + deterministic composer

- **Locations**: new `utils/synthesis/__init__.py`, `utils/synthesis/contracts.py`
  (`Citation`, `Claim`, `ClaimVerdict`, `Abstention`, `SynthesizedAnswer` with
  `to_dict`/`from_dict`), `utils/synthesis/config.py` (`SynthesisConfig`, `SYNTHESIS_LLM_*` env
  vars mirroring `utils/planner/config.py`), `utils/synthesis/composer.py`
  (`DeterministicComposer` producing structured claims-with-citations from
  `FederatedEvidence` — lifting/replacing the logic in `api/services/query.py:79-121`),
  `utils/synthesis/tests/test_contracts.py`, `test_composer.py`.
- **Rationale**: the claim/citation structure is the substrate everything else checks against;
  the deterministic composer must exist first so the verifier and the API seam have a
  guaranteed-available producer. Every claim it emits carries explicit citations
  (`source`, `primary_id`, `record_id`) so verification is mechanical.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated,
  commit stating: Step 6 Synthesis (1/6) Complete: synthesis contracts + deterministic
  claims-with-citations composer.

#### Step 2: Deterministic claim verifier + abstention

- **Locations**: `utils/synthesis/verifier.py` (`verify_answer(answer, evidence) ->
  VerificationReport`; citation-resolution check, id-pool grounding check reusing/normalizing via
  a shared helper extracted from `utils/specialists/tests/golden_runner.py` into
  `utils/synthesis/grounding.py`, join-claim check against `join_index`, zero-record guard),
  abstention construction (per empty-but-ok `SpecialistResult`: statement + the executed
  `result.query`), `utils/synthesis/tests/test_verifier.py`, `test_abstention.py`.
- **Rationale**: the verifier is the actual Step 6 deliverable — deterministic, so it cannot be
  sweet-talked by the model it audits. Adversarial hermetic tests are mandatory: inject
  fabricated claims (nonexistent ID, wrong-record citation, claim against a zero-record source)
  and assert each is cut and flagged; assert honest-empty produces the abstention sentence with
  the query attached, not silence.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated,
  commit stating: Step 6 Synthesis (2/6) Complete: deterministic claim verifier + abstention
  with executed-query proof.

#### Step 3: LLM composer + hybrid factory

- **Locations**: `utils/synthesis/llm_composer.py` (`OpenAICompatibleComposer`, temperature 0,
  JSON-claims output contract, `ComposerUnavailable`), `utils/synthesis/factory.py`
  (`HybridComposer`: LLM → deterministic fallback, fallback reason recorded on the answer),
  `utils/synthesis/tests/test_llm_composer.py` (stubbed HTTP; malformed-JSON, timeout,
  fabrication-then-verifier-cut paths).
- **Rationale**: mirrors the proven `HybridDrafter` pattern (`utils/planner/drafter_factory.py`);
  the LLM never gets to bypass the verifier — its output flows through the same
  `verify_answer` pass, which is exactly the chain Step 6 describes.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated,
  commit stating: Step 6 Synthesis (3/6) Complete: LLM composer behind env flags with hybrid
  fallback, all output verifier-gated.

#### Step 4: Wire into the API answer seam + CLI

- **Locations**: `api/services/query.py` (`stream_query_events` answer stage: build
  `SynthesizedAnswer` via the hybrid composer + verifier; extend the answer JSON additively with
  `claims`, `verification`, `abstentions`), `utils/specialists/cli.py` (or `utils/synthesis/cli.py`)
  for a `main.py --query`-path synthesis printout, `api/tests/` contract tests updated/added.
- **Rationale**: `query.py:17-18` marks this exact seam for the synthesis agent. With LLM
  disabled the deterministic composer reproduces today's semantics, so existing API contract
  tests must stay green; new fields are additive so the web UI is unaffected.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated,
  commit stating: Step 6 Synthesis (4/6) Complete: synthesis agent wired into the API answer
  seam with additive schema.

#### Step 5: Synthesis golden evalset (live)

- **Locations**: `utils/synthesis/tests/test_golden_synthesis.py` (live-marked, reachability
  skips as in `utils/specialists/tests/test_golden_attack.py`): parameterize over the Step 5
  banks (`utils/specialists/tests/golden/{attack,capec}_questions.json`), run live specialist →
  synthesis → assert every rendered claim has verdict `supported`, unsupported-claim rate == 0,
  and every `expect_empty` question yields an abstention containing the executed query and no
  invented IDs; metrics summary (faithfulness/groundedness/unsupported rate per goals.md).
- **Rationale**: this is the acceptance gate — the same 45 verified questions now measure the
  synthesis layer; the negatives are purpose-built abstention probes.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated,
  commit stating: Step 6 Synthesis (5/6) Complete: synthesis golden suite green live —
  0 unsupported claims, abstention on all negatives.

#### Step 6: Docs, changelog, full regression, merge

- **Locations**: `docs/structure.md` (synthesis package + verification/abstention semantics,
  remove "Not Yet in Repo" synthesis entry), `docs/goals.md` (check off Wk 10 synthesis row),
  `docs/changelog.jsonl`, full regression (`utils/` + `api/` + golden suites), merge worktree
  into local `main` (commit-only session: **not pushed**).
- **Rationale**: canonical docs are the contract other agents read; nothing merges below 100%
  green per global rules.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated,
  commit stating: Step 6 Synthesis (6/6) Complete: docs + full regression + merge to main.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Synthesis contracts | Claim/Citation/Abstention/SynthesizedAnswer dataclasses + config | `utils/synthesis/contracts.py`, `config.py` |
| Deterministic composer | Claims-with-citations from FederatedEvidence (always available) | `utils/synthesis/composer.py` |
| Claim verifier | Deterministic citation-resolution + id-pool grounding + join checks; cut/flag | `utils/synthesis/verifier.py`, `grounding.py` |
| Abstention | "Sources don't establish this" + executed query proof on empty-but-ok results | `utils/synthesis/verifier.py` |
| LLM composer + hybrid | OpenAI-compatible composer behind `SYNTHESIS_LLM_*`, deterministic fallback | `utils/synthesis/llm_composer.py`, `factory.py` |
| API integration | Synthesis at the answer seam, additive JSON schema | `api/services/query.py` |
| Hermetic unit tests | Contracts, composer, adversarial verifier (fabrication cut), abstention, stubbed LLM | `utils/synthesis/tests/test_*.py` |
| Synthesis golden suite | Live: 45 bank questions → 0 unsupported claims, abstention on negatives | `utils/synthesis/tests/test_golden_synthesis.py` |
| Docs + changelog | structure.md, goals.md checkbox, per-step changelog entries | `docs/` |
