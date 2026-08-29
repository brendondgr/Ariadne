# Variant Robustness Harness — Plan

**Date:** 2026-08-29
**Mode:** B — no worktree, direct on `main`.
**Commit policy:** commit at every step. **Never push.** The planner skill's
template says "push to GitHub"; the operator's standing directive and
`global-project-rules` rule 1 both override it. Every step also appends to
`docs/changelog.jsonl`.

---

## 1. Introduction

The deterministic pipeline routes a question by matching its words, case-folded
and exact, against the node labels and relationship types named in each source's
schema card. The only morphology it handles is a trailing `s`. Measured on
2026-08-28: `"mitigations"` routes; `"defend against"`, `"countermeasures"`,
`"remediate"` and the typo `"mitgations"` all match **nothing**. Worse,
`"What mitigates browser extension persistence?"` returns four techniques, none
of which is the right one, and `"What are the mitigations for \"Software
Extensions\"?"` — the literal `name` property of T1176 — returns nothing at all.

This plan builds the instrument that measures that cliff, then closes it in
stages. **The instrument comes first and is the deliverable even if nothing is
fixed**: Sonnet authors tiered paraphrase variants of all 120 golden questions,
every variant runs through the deterministic engine, and each is scored against
what the *original* gold question extracted. Fixes follow in order of increasing
cost and increasing risk to the project's existing claims — deterministic word
handling first, exact-name resolution second, a candidate retrieval index third,
and a gated language-model interpreter only if a measured gap survives all
three. **No step may make the deterministic path non-reproducible**, and every
new seam ships switched off with a measured before-and-after.

---

## 2. Gaps & Unanswered Questions

**Resolved by assumption — proceeding.**

- **How many variants per question.** *Assumption:* one per tier T1–T5 (five),
  plus one negative control per four gold questions. 120 questions → ~600
  variants, ~30 negative controls. Tiers are defined in Step 2; a flat count
  would hide the two distinct failure modes.
- **What "extracts the same things" means.** *Assumption:* the **set of entity
  identifiers in the retrieved records** is the primary metric, per the
  operator's phrasing. Query-string identity and claim-set identity are captured
  in the same pass as secondary metrics. A variant reaching the same records via
  a *different template* is a **success** on the primary metric and is reported
  separately, because outcome and interpretation are different questions.
- **Federated questions have two sources.** *Assumption:* same tiers, and the
  comparison is per-source as well as pooled — a variant that keeps the ATT&CK
  half and loses the CAPEC half is a partial, not a failure.
- **Sonnet is not on the local relay** (`:4000` serves `skynet`, `local`,
  `agent`, and free models only). *Assumption:* variants are authored by Sonnet
  **subagents in the Claude Code session**, which is the stronger design anyway —
  it puts the variant author in a different model family from any interpreter we
  later build on the local model, which is what stops the measurement being
  self-consistency (C-021).
- **Abstention counts as an outcome, not a failure.** A variant that declines to
  answer is scored in its own column. Silence and a wrong answer are not the
  same result and must never be pooled.

**Human intervention is needed to answer these.**

- **Should a language-model interpreter, if built, ever be ON by default?**
  Turning it on changes what C-001 and C-004 claim — the shipped path stops
  being byte-reproducible and stops being 637× cheaper. Recommendation is
  off-by-default and reported as a separate arm, but this is a positioning
  decision, not a technical one. *Human intervention is needed.*
- **Is a variant bank with gold interpretations a public artifact?** It is close
  to the resource C-025 says nobody has, and it inherits Q26's circularity trap:
  gold produced by the system under test. *Human intervention is needed.*

---

## 3. Hierarchical Step-by-Step Instructions

### Step 1 — Reference capture: what does the gold question actually extract?

- **Locations:** new `scripts/variant_harness.py` (capture mode);
  `utils/specialists/evalset/compile_banks.py` (bank loading, reused as-is);
  `utils/orchestration/main.py::iter_pipeline` (called with an injected
  synthesis config, never with `use_llm` alone — see
  `ariadne-harness-gotchas` item 2); output under
  `docs/evaluation/variants-2026-08-29/reference.json`.
- **Rationale:** the whole measurement is a comparison against a reference, so
  the reference has to exist and be proven stable *before* any variant is
  written. Capturing it also forces the three-level metric to be defined in code
  rather than in prose. Recorded answers cannot be reused for this —
  `generate_e2e.py::_answer_dict` serialises only claims that already passed the
  verifier, so the pipeline must be re-run live.
- **Action:** capture query string, retrieved entity-ID set, claim set,
  abstentions and template name for all 120 gold questions.
  **Validation:** run the capture **twice** and assert the two artifacts are
  byte-identical after excluding the clock keys `wall_s` and `timing_ms`. A
  reference that is not reproducible makes every downstream number meaningless,
  and this is the exact trap that made a prior regression report all 300 answers
  changed. Undergo the verification/tests/validation process for this phase.
  Once validated, **commit** (do not push) stating: Variant Robustness (1/8)
  Complete: captured and proved stable the gold-side reference extraction for
  all 120 questions.

### Step 2 — Sonnet authors the tiered variant bank

- **Locations:** new `scripts/author_variants.py` (fan-out driver and schema
  validator); prompt fixture under
  `utils/specialists/tests/fixtures/variant_prompt.md`; output
  `docs/evaluation/variants-2026-08-29/variants.json`.
- **Rationale:** the tiers separate the two problems this plan exists to
  distinguish. **T1** keeps the identifier and swaps a schema word. **T2** keeps
  the identifier and restructures the sentence. **T3** replaces the identifier
  with the entity's exact `name`. **T4** paraphrases that name. **T5** describes
  the entity without naming or numbering it. **T6** is a negative control — a
  plausible question about something genuinely absent from the graph. T1–T2
  stress vocabulary matching; T3–T5 stress entity resolution; T6 stresses
  whether the system knows when to say nothing.
  Each authoring agent receives the gold question, its gold answer, and **the
  source card's label and relationship vocabulary as a list of words to avoid**
  in T4 and T5 — without that, an author reaches for the schema's own term and
  silently produces a T1 labelled T5.
- **Action:** fan out Sonnet subagents across the 120 questions; each returns
  tiered variants with a declared tier and a one-line justification.
  **Validation:** three mechanical gates plus one human gate. (a) Schema
  validation — every variant parses and carries a tier. (b) **Tier honesty
  check** — a T3+ variant containing the identifier is rejected; a T4/T5 variant
  containing an exact schema label or relationship word is rejected. (c)
  Coverage — every gold question has at least one variant per tier attempted,
  with rejections recorded rather than silently dropped. (d) The operator reads
  a random sample of 20 and confirms they are answerable and correctly tiered;
  an external benchmark's own audit put generated items at 65% correct, so an
  unaudited generated bank is not evidence. Undergo the
  verification/tests/validation process for this phase. Once validated,
  **commit** (do not push) stating: Variant Robustness (2/8) Complete: authored,
  gated and sampled the tiered variant bank.

### Step 3 — Baseline: measure the cliff before touching anything

- **Locations:** `scripts/variant_harness.py` (compare mode); new experiment
  folder from `make new-experiment SLUG=variant-robustness-baseline`;
  metrics to that folder's `data/metrics.json`.
- **Rationale:** this is the number every later step is judged against, and it
  must be taken before a line of routing code changes. It is also a publishable
  result on its own — the robustness cliff of a deterministic pipeline,
  measured, which the 2026-08-26 novelty audit found nobody has reported.
  Reporting must be **per tier**; a pooled figure would average the vocabulary
  problem and the entity-resolution problem into one uninterpretable number.
- **Action:** run every variant, score record identity (primary), query identity
  and claim identity (secondary), plus abstention rate and **wrong-entity rate**
  — the case where records come back and none of them are the gold entity, which
  is the failure mode that scares us most because nothing downstream catches it.
  **Validation:** T0 control — the gold questions themselves must score exactly
  1.0000 record identity against Step 1's reference; anything else means the
  harness is broken, not the system. Record every metric in `manifest.yaml` and
  `RESULTS.md`; run `make validate-research`. Undergo the
  verification/tests/validation process for this phase. Once validated,
  **commit** (do not push) stating: Variant Robustness (3/8) Complete: baseline
  measured per tier with the T0 control at 1.0000.

### Step 4 — Deterministic vocabulary layer

- **Locations:** new `utils/planner/lexicon.py` (stemming, bounded edit
  distance, gloss promotion); wired into
  `utils/planner/drafter.py::_concept_indexes` and `::_match_card`; flag in
  `utils/planner/config.py`.
- **Rationale:** three cheap mechanisms that need no model and keep the path
  byte-reproducible. **Stemming** collapses `mitigate/mitigates/mitigating/
  mitigations`, where today only a trailing `s` is handled. **Bounded edit
  distance** (≤1, words of 5+ characters only) catches typos; anything looser
  manufactures false matches. **Gloss promotion** indexes morphological variants
  of the words already sitting unused in each card's `entity_descriptions` —
  `Mitigation`'s gloss literally reads *"A defensive measure…"*, so `defend`
  fails today only because matching is exact-string. None of these names a
  dataset, so all three transfer to a schema nobody has seen.
- **Action:** implement behind a flag, default **off**; measure both states.
  **Validation:** unit tests for each mechanism in
  `utils/planner/tests/test_lexicon.py`, including the false-positive cases that
  bound edit distance. Then the **mandatory recorded-answer regression** over
  both catalogue banks, diffing with clock keys excluded — a routing change that
  moves a catalogue answer is a regression until proven otherwise. Then re-run
  the variant harness and report the per-tier delta. Undergo the
  verification/tests/validation process for this phase. Once validated,
  **commit** (do not push) stating: Variant Robustness (4/8) Complete:
  deterministic vocabulary layer with per-tier deltas and a clean regression.

### Step 5 — Fix exact-name resolution

- **Locations:** `utils/specialists/resolve/__init__.py::_extract_name_terms`
  and `_acceptable_name`; the name-lookup path in
  `utils/specialists/cypher/builder.py`; `utils/planner/drafter.py` rescue path.
  Also closes **Q27** — `cards.py::expected_probe_labels` is a liveness helper
  and must stop being used as a semantic type declaration.
- **Rationale:** `"Software Extensions"` is the literal `name` property of
  T1176 and returns nothing today, quoted or bare. That is a defect, not a
  missing feature, and it is the control for everything in Step 6: no fuzzy
  matcher can be evaluated on top of an exact matcher that does not work. Q27
  belongs here because it is the same rescue path — that path currently declares
  `Analytic` as the type of every entity it rescues, because that is
  alphabetically first in the card.
- **Action:** make exact and quoted `name` matching resolve to the anchor;
  replace the probe-label guess with the learned identifier scheme
  (`utils/specialists/schema/idscheme.py`), falling back to an **empty** label
  rather than a guessed one.
  **Validation:** unit tests covering exact name, quoted name, and a name that
  is a substring of several others. Recorded-answer regression over both banks.
  Re-run the harness and report T3 movement specifically. Undergo the
  verification/tests/validation process for this phase. Once validated,
  **commit** (do not push) stating: Variant Robustness (5/8) Complete: exact
  name resolution works and Q27's mislabelling is closed.

### Step 6 — Candidate retrieval over names and descriptions

- **Locations:** new `utils/specialists/schema/namesearch.py` (index build +
  ranked lookup); index built from
  `data/graphs/<dataset>/canonical/nodes.jsonl` (9,138 nodes across the two
  catalogues, each carrying `name` and a `description`); consumed by the
  resolver from Step 5.
- **Rationale:** T4 and T5 need ranked candidates, not exact matches.
  `"browser extension persistence"` should surface T1176, whose description
  opens *"Adversaries may abuse software extensions to establish persistent
  access…"*. A keyword-ranking index over name+description is roughly 150 lines,
  needs **no new dependency** — the project has no embedding, vector or
  fuzzy-match library and this plan does not add one — is deterministic, is
  built from the same checksummed snapshot the identifier schemes are learned
  from, and transfers to any source whose nodes have names.
- **Action:** build the index offline as a build artifact; return ranked
  candidates with scores; the resolver accepts a candidate only above a
  threshold **and** only when it is unambiguous by a margin, abstaining
  otherwise.
  **Validation:** an index-level test asserting the gold entity ranks in the top
  *k* for a fixture set of paraphrases. Then the harness: report T4/T5 movement
  **and the wrong-entity rate**, which is the metric that matters here — a
  retriever that always answers has traded silence for confident error, which is
  worse. Recorded-answer regression over both banks. Undergo the
  verification/tests/validation process for this phase. Once validated,
  **commit** (do not push) stating: Variant Robustness (6/8) Complete: candidate
  retrieval with per-tier movement and the wrong-entity rate reported.

### Step 7 — Gated language-model interpreter *(conditional)*

- **Locations:** new `utils/planner/interpreter.py`; flag in
  `utils/planner/config.py`; sampling via `utils/llm_sampling.py`; gate reusing
  the closed-vocabulary check from `utils/planner/gate.py`.
- **Rationale:** **run this step only if Steps 4–6 leave a measured gap**, and
  only within the constraint that keeps the project's thesis intact: the
  interpreter **renames and selects; it never plans**. It may emit a schema term
  only if that term appears in the card, and it may select an entity only from
  the ranked candidate list Step 6 produces — it never emits a free-form
  identifier. That is what separates it from the LLM planner, which decides what
  to look up and costs ~12 points of correctness. Output is cached by question
  hash so evaluation re-runs are free and reproducible. Reasoning budget must be
  ≥2048 tokens or the local model truncates to empty and reads as a dead server.
- **Action:** implement, default **off**, gated, cached.
  **Validation:** a gate test proving an invented label and an invented
  identifier are both rejected. Then the harness, run **three times**, reporting
  mean and spread — a single run of a model seam is exactly the n=1 problem Q2
  exists to fix. Confirm with the flag off that the pipeline is byte-identical
  to Step 6. Undergo the verification/tests/validation process for this phase.
  Once validated, **commit** (do not push) stating: Variant Robustness (7/8)
  Complete: gated interpreter measured over three runs against a byte-identical
  off state.

### Step 8 — Write up and update the research record

- **Locations:** the experiment folder from Step 3, extended with per-step arms;
  `docs/research/CLAIMS.md`; `docs/research/OPEN_QUESTIONS.md` (Q27 closed, Q4
  updated); `docs/research/DECISIONS.md` (a decision record for the
  interpreter's constraint boundary); `docs/changelog.jsonl`.
- **Rationale:** a number that exists only in a chat log does not exist. This
  work touches C-001 (a robustness limit on the deterministic path), C-010 (the
  vocabulary layer is schema-agnostic and is evidence either way), C-021 (the
  variant bank is the first question set here *not* written in the schema's
  vocabulary), and C-025 (the bank is close to the missing resource). Q4 — open
  since the beginning and still unmeasured — gets its first partial answer,
  because T5 variants are the closest thing to non-anchored questions the
  project has ever run.
- **Action:** file every arm's metrics; state plainly which tiers did not move.
  **Validation:** `make validate-research` passes; every claim referenced from
  the experiment's `supports_claims` exists in `CLAIMS.md`; no metric appears in
  prose that is absent from `data/metrics.json`. Undergo the
  verification/tests/validation process for this phase. Once validated,
  **commit** (do not push) stating: Variant Robustness (8/8) Complete: results
  filed and the affected claims and open questions updated.

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Variant harness | Capture the gold reference; run variants; score record / query / claim identity, abstention and wrong-entity rate per tier | `scripts/variant_harness.py` |
| Variant authoring driver | Sonnet subagent fan-out, schema validation, tier-honesty gating | `scripts/author_variants.py` |
| Authoring prompt fixture | The tier definitions and the avoid-list contract given to each author | `utils/specialists/tests/fixtures/variant_prompt.md` |
| Gold reference artifact | What each of the 120 gold questions extracts, proven reproducible | `docs/evaluation/variants-2026-08-29/reference.json` |
| Variant bank | ~600 tiered variants plus ~30 negative controls | `docs/evaluation/variants-2026-08-29/variants.json` |
| Deterministic lexicon | Stemming, bounded edit distance, gloss promotion; no dataset names | `utils/planner/lexicon.py` |
| Lexicon unit tests | Per-mechanism tests including edit-distance false-positive bounds | `utils/planner/tests/test_lexicon.py` |
| Name search index | Keyword ranking over 9,138 canonical name+description records, no new dependency | `utils/specialists/schema/namesearch.py` |
| Name resolution tests | Exact, quoted, and ambiguous-substring name cases; Q27 label regression | `utils/specialists/resolve/tests/test_name_resolution.py` |
| Name search tests | Gold entity ranks top-k for a fixture paraphrase set | `utils/specialists/tests/test_namesearch.py` |
| Gated interpreter *(conditional)* | Closed-vocabulary rename-and-select seam, default off, cached | `utils/planner/interpreter.py` |
| Interpreter gate tests | Invented label and invented identifier both rejected; off-state byte-identical | `utils/planner/tests/test_interpreter_gate.py` |
| Experiment record | Per-tier metrics for every arm, in `manifest.yaml` and `RESULTS.md` | `docs/research/experiments/EXP-2026-08-0XX-variant-robustness/` |
| Ledger updates | C-001, C-010, C-021, C-025 amended; Q4 partially answered; Q27 closed | `docs/research/CLAIMS.md`, `OPEN_QUESTIONS.md`, `DECISIONS.md` |
