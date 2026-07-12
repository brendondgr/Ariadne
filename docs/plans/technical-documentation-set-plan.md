# Technical Documentation Set Plan (Wk 14–15, docs-only)

## 1. Introduction

This plan delivers the documentation half of the Wk 14–15 roadmap row in
`docs/goals.md`: four documents that make Ariadne usable by a third party — a
formal **source card format spec**, the **agent interface contracts** (the four
integration-frozen seams), the consolidated **query safety constraints** story,
and the **openCypher/GQL migration guide** (proposal Deliverable #6). The
bug-fix/hardening half of the row and the golden-eval LLM run are explicitly
out of scope for this session.

Approach: work in a separate worktree (concurrent sessions move `main`), fan
out research/drafting via an agent workflow (Haiku for repository
fact-extraction, Sonnet for drafting), then every factual claim in each draft
is verified against the actual code and its contract tests before it lands.
Each doc is validated by running the test suites that pin the contracts it
describes, plus a new lightweight docs-consistency test. Every step ends in a
local commit with a changelog entry (no push, per standing directive); the
worktree merges to `main` at the end.

## 2. Gaps & Assumptions

- **Source card spec location**: `docs/source_cards.md` already exists as a
  partial format doc. *Assumption*: extend it in place into the full spec
  (including "what a new source's card must contain") rather than duplicate.
- **New doc filenames**: `docs/agent-interfaces.md`, `docs/query-safety.md`,
  `docs/migration-guide.md` (kebab-case convention).
- **goals.md checkbox**: the Wk 14–15 row also covers bug fixes/hardening not
  done here. *Assumption*: leave unchecked; record docs progress in
  `structure.md` + changelog.
- **Migration-guide findings**: coupling discovered beyond the four swap
  points is recorded honestly in the guide and changelog as a hardening
  backlog item; no code changes in this session.

## 3. Steps

Each step ends: *validate, then commit locally as "Technical Documentation Set
(N/8): …" with a `docs/changelog.jsonl` entry. Never push.*

1. **Worktree setup + plan on record.** Worktree reset onto local `main`,
   `data/*` + `.env` symlinked; this file committed.
   *Validation*: hermetic test collection succeeds in the worktree.
2. **Fact-gathering + drafting workflow.** Pipeline over the four docs: Haiku
   fact-extraction (registry writer, `card_enrichment.py`, `contracts.py`,
   `schema.py`, `evidence.py`, validators, gate, connectors, `federation.py`,
   synthesis contracts, seam tests) → Sonnet draft to scratchpad.
   *Validation*: drafts cite real paths; nothing lands in the repo. No commit.
3. **Source card format spec** (`docs/source_cards.md`). Verify draft against
   the card writer + enrichment code, land.
   *Validation*: `utils/kg_builder/tests/test_registry_contracts.py` + planner
   card tests green; every documented field exists in code.
4. **Agent interfaces** (`docs/agent-interfaces.md`). Field-by-field against
   `Plan`/`SpecialistTask`/`EvidenceRecord`/`FederatedEvidence`/
   `SynthesizedAnswer`.
   *Validation*: `utils/specialists/tests/test_seams.py` + contract tests
   green; doc fields match the dataclasses.
5. **Query safety constraints** (`docs/query-safety.md`). Organized by
   enforcement point (card → pre-run gate → connector/DB role → evidence
   contract).
   *Validation*: both validator suites + hermetic `test_score_safety.py`
   green; each documented enforcement cites its code location.
6. **Migration guide** (`docs/migration-guide.md`). Dry-run the
   four-swap-point walkthrough against the real Gremlin specialist layout;
   full checklist (card, swap points, federation wiring, eval-harness
   validation); record any fifth-coupling findings.
   *Validation*: every referenced module/function exists; steps map to real
   extension points.
7. **Docs-consistency test**
   (`utils/specialists/tests/test_docs_contracts.py`): repo paths referenced
   in the four docs exist; documented interface field names match the actual
   dataclasses.
   *Validation*: new test green within the hermetic specialist suite.
8. **Cross-linking + structure.md + merge.** Update `structure.md` (docs
   table, Finding Things Fast, Not Yet in Repo), cross-link the four docs.
   *Validation*: relevant hermetic suites green; merge worktree → `main`,
   resolve drift, re-verify on `main`.

## 4. Deliverables

| Deliverable | Description | Location |
| --- | --- | --- |
| Source card format spec | Full card contract incl. new-source requirements | `docs/source_cards.md` |
| Agent interfaces doc | The four frozen seams as public contracts | `docs/agent-interfaces.md` |
| Query safety doc | Safety model by enforcement point | `docs/query-safety.md` |
| Migration guide | openCypher/GQL four-swap-point walkthrough (Deliverable #6) | `docs/migration-guide.md` |
| Docs-consistency test | Referenced paths + documented fields verified against code | `utils/specialists/tests/test_docs_contracts.py` |
| Plan + changelog entries | This plan, one changelog line per step | `docs/plans/`, `docs/changelog.jsonl` |
