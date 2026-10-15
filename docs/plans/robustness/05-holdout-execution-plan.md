# Plan 05 — Holdout execution (implementation plan)

**Parent (normative):** `02-holdout-question-generation.md`
**Operator brief (fixes open execution details):** `04-holdout-execution-brief.md`

This file is the *executable* plan for those two. Where the brief and the parent
plan differ, the brief wins — it was written later and explicitly to close gaps.
Neither of those files is edited; this is a new record, per the append-only rule.

---

## 1. Introduction

The 120-question golden catalogue was authored by the same person, at the same
time, as the templates that answer it, so its 0.9972 correctness figure cannot
distinguish "the system works" from "the questions were shaped by knowing what
the system handles". This plan executes the blind holdout that separates those:
30 questions drawn from mechanically-seeded uniform anchors, written by an agent
that never sees the template inventory, with gold computed independently from
the raw MITRE snapshot, run against the frozen tree and graded cross-model.

The approach is a strict role separation carried through in tooling rather than
in instructions. A committed sampler script draws the anchors and the draw is
committed *before* any question exists, so the git timestamp proves ordering. A
fresh Claude Fable 5 subagent at high reasoning effort writes each question from
a prompt that contains nothing but the anchor, its type, its snapshot name, the
category description, and the reference-discipline rule — no repository access,
no file paths, no examples from the existing bank. The orchestrator session
(which has read the plans, the README, and the eval docs) computes gold, compiles
the bank, and runs Arms A and F, but never writes question text.

---

## 2. Gaps & unanswered questions

- **The freeze tag versus `main`.** `freeze/holdout-v1` points at `974e85a`;
  `main` is 40+ commits ahead. *Verified*: `git diff freeze/holdout-v1 --
  utils/specialists/ utils/planner/ utils/synthesis/ utils/orchestration/`
  touches exactly one file, `utils/specialists/tests/test_docs_contracts.py`, a
  test. The system under test is byte-identical to the freeze. *Decision*: run
  the arms from a **detached worktree at the tag** anyway, with only the holdout
  bank and the harness `--bank` flag copied in as untracked files, so
  `git describe --exact-match` passes on the checkout that produced the numbers.

- **The harness loads the 120-question banks by name.**
  `experiment_untruncated.load_work()` calls `score_e2e._load_banks()`, which is
  hard-wired to the three committed banks. A `--bank` option is required.
  *Assumption*: adding an option to `utils/evaluation/` is not a behavioural
  change to the system under test (the freeze covers `utils/specialists/` and the
  planner), so this is permitted; the diff will be shown in the write-up.

- **`_category_of` derives the category from the id prefix** (`H-MIT-01` →
  `H-MIT`). The `H-` ids therefore give per-category reporting for free.
  *Assumption*: reuse it rather than adding a parallel mechanism.

- **The Author's context is narrower in the brief than in the parent plan.**
  Plan 02 §3 permits the Author to read the raw snapshot for names and
  descriptions; the brief §4 grants "No repo file access" and enumerates the
  prompt contents exhaustively. *Decision*: follow the brief. The Author sees the
  id, the type, the snapshot name, and the category description — nothing else.
  This is the stronger blind, and it is recorded as such.

- **Reasoning effort is not settable on a plain subagent spawn.** The brief
  mandates high effort. *Decision*: author and judge via the Workflow tool, whose
  `agent()` accepts `effort`. This is multi-agent orchestration and is used here
  only because the brief requires it.

- **How many federated anchors must be over-drawn to hit ~6 answerable / ~4
  abstention-expected?** Depends on the live mapping density, which the sampler
  measures. *Assumption*: over-draw the federated stratum until both partitions
  are filled, recording the full draw order and the over-draw count in
  `anchors.json`, exactly as §2.4 requires.

- **Will Arm F complete 30 questions against the local model without a
  timeout?** Unknown until run. *Assumption*: it will, since it completed 120 in
  the `untruncated-goldloop` run. A crash is a deviation to be logged and
  re-run, per §9; a wrong answer is a result.

- **The Branch A §6 gate document.** `docs/plans/branch-a-publication-readiness-plan.md`
  was deleted in the 2026-08-06 plan trim. Its decision rule must be recovered
  from git history before the number is handed to it. *Human intervention may be
  needed* if the thresholds cannot be recovered verbatim — they may not be
  renegotiated after seeing the result, so a reconstruction from memory is not
  acceptable.

---

## 3. Steps

### Step 1 — Bootstrap, freeze verification, and this plan

- **Locations**: worktree root; `data/versions.json`;
  `data/graphs/attack/runtime/fixture-qa-report.json`; this file;
  `docs/changelog.jsonl`.
- **What**: reset the worktree onto local `main`; symlink the gitignored
  `data/{raw,graphs,processed,source_cards}` and `.env`; verify both snapshot
  SHA256s against `data/versions.json` byte-for-byte; confirm
  `git rev-parse freeze/holdout-v1` resolves to `974e85a…`; confirm the freeze
  diff over `utils/specialists/`, `utils/planner/`, `utils/synthesis/`,
  `utils/orchestration/` is test-only; confirm both graphs are **loaded**, not
  merely reachable, by running one real query against each.
- **Rationale**: §4 of the parent plan makes the snapshot hashes a precondition —
  a version skew produces a low number with a plausible excuse and nobody
  checks. The liveness check is separate from the health check because the health
  check does not count nodes, and an empty graph looks like a routing bug.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: Holdout Execution (1/8) Complete: Verified the
  freeze tag, both snapshot hashes, and live non-empty graphs, and recorded the
  execution plan.

### Step 2 — The sampler

- **Locations**: `utils/specialists/evalset/holdout_protocol.py` (new);
  `utils/specialists/evalset/tests/test_holdout_protocol.py` (new).
- **What**: a module-level `HOLDOUT_SEED` constant (not `1729`, with the
  never-change comment §2.3 requires); population builders reading
  `gold_bank.json` and the fixture-QA report for ATT&CK techniques /
  sub-techniques, CAPEC live patterns (including the 381 unmapped), and bridged
  CWEs; a `draw()` returning the stratified uniform sample (12/8/10) with the
  federated stratum over-drawn and partitioned into answerable /
  abstention-expected; SHA256 over each population list; and the author-prompt
  builder. No degree, mapping-count, or fame weighting anywhere.
- **Rationale**: the single most likely way this experiment dies silently is
  anchors drawn from the rich part of the graph. Making the draw a committed,
  re-runnable script is what lets a reviewer regenerate the set and check that.
- **Tests**: determinism (two draws with the same seed are identical),
  population sizes match the documented counts, no revoked/deprecated/retired id
  appears, strata counts are exact, the federated partition is by live-mapping
  presence and not by anything else.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: Holdout Execution (2/8) Complete: Added the
  seeded uniform anchor sampler and its tests.

### Step 3 — The draw

- **Locations**: `docs/evaluation/holdout-v1/anchors.json` (new).
- **What**: run the sampler; emit seed, per-class population sizes, population
  SHA256s, the full draw order including over-draws, the federated partition,
  and an empty `discards` array to be filled in Step 5.
- **Rationale**: committing the draw before a single question exists is what
  makes "the anchors were not chosen to suit the questions" checkable rather
  than asserted. This commit must land before Step 4 starts.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: Holdout Execution (3/8) Complete: Drew and
  committed the 30 holdout anchors before any question was authored.

### Step 4 — Authoring

- **Locations**: `docs/evaluation/holdout-v1/author-prompt.md` (new, verbatim);
  `docs/evaluation/holdout-v1/authored.json` (new, raw returns).
- **What**: one fresh Claude Fable 5 subagent at high reasoning effort per
  anchor, prompt containing only the anchor id, entity type, snapshot name,
  category label, the §5 category descriptions verbatim, and the
  reference-discipline rule. It returns one analyst question and nothing else —
  no answer, no template guess, no tier. Record
  `"author_model": "claude-fable-5 (high effort)"`.
- **Rationale**: the write-lock is the experiment. Enforcing it by prompt
  construction — the prompt contains no repository path, no file, no example —
  rather than by telling an agent to avert its eyes is the whole point of §3.
- **Validation**: every returned question mentions its anchor id; no question
  mentions a template name, another anchor, or an answer; count is 30.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: Holdout Execution (4/8) Complete: Authored 30
  blind questions with fresh Fable 5 high-effort subagents under the §3 lock.

### Step 5 — Compile gold and assemble the bank

- **Locations**: `utils/specialists/evalset/holdout_protocol.py` (compile
  functions); `utils/specialists/tests/golden/holdout_questions.json` (new);
  `docs/evaluation/holdout-v1/anchors.json` (discard log appended).
- **What**: compute `assertions`, `ex_gold`, and the derived `expected_template`
  from `gold_bank.py` output only. Emit entries with `split: "holdout"`, `H-`
  ids, and `holdout_meta.expected_template_is_derived: true`. Federated entries
  follow the `federated_questions.json` shape (`hops`, `sources`, `sequenced`,
  `partial_mode`, `sub_questions[]` with `seed_from` / `join_key`);
  abstention-expected entries carry `expect_no_correlation` and an empty related
  set. A gold-computation failure discards the anchor and takes the next from the
  seeded sequence, with the reason logged.
- **Rationale**: gold is computed, never authored, and computed by the *existing*
  parser that reads the raw STIX/XML rather than the built graph — that
  independence is what makes the answer key a check on the ingest as well.
- **Tests**: schema conformance against the three existing banks; every
  `must_include_ids` contains its anchor; every derived template names a real
  template identifier; abstention entries assert no correlation.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: Holdout Execution (5/8) Complete: Computed
  gold independently and assembled the 30-question holdout bank.

### Step 6 — Run Arms A and F on the frozen tag

- **Locations**: `utils/evaluation/experiment_untruncated.py` (`--bank` option,
  `load_work`); `utils/evaluation/score_e2e.py` (`_load_banks` parameterisation);
  a detached worktree at `freeze/holdout-v1`;
  `docs/evaluation/experiments/holdout-v1/{deterministic,gold_loop_llm}/`.
- **What**: add `--bank`, then run Arm A (`--arm deterministic`) and Arm F
  (`--arm gold_loop_llm`) over the holdout bank from a checkout where
  `git describe --exact-match` reports `freeze/holdout-v1`. Nothing else changes
  between Step 5 and Step 8.
- **Rationale**: §9 — a template or planner edit made in response to a holdout
  failure converts the experiment into a second development set, and the result
  still looks like a number, which is what makes it dangerous.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: Holdout Execution (6/8) Complete: Ran Arms A
  and F over the holdout bank from a detached checkout of freeze/holdout-v1.

### Step 7 — Judge and score

- **Locations**: `scripts/judging/judge_holdout.mjs` (new, derived from
  `judge_untruncated.mjs`); `docs/evaluation/experiments/holdout-v1/**/*.judgment.json`;
  `docs/evaluation/holdout-v1/results.json` (new).
- **What**: one independent Sonnet 5 agent per case per arm (60 total), graded
  against gold *and* the full retrieved evidence, cross-model on purpose.
  Abstention-expected cases are graded on abstention behaviour — did it abstain,
  did the abstention carry the executed query, did it avoid inventing a mapping —
  not on answer correctness. Roll up into `results.json` with per-question
  outcomes for both arms.
- **Rationale**: the pipeline's own model must not grade its own output, and the
  two federated strata mean different things so they may not be averaged.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: Holdout Execution (7/8) Complete: Graded both
  arms with independent Sonnet 5 judges and recorded per-question results.

### Step 8 — Report, research record, and the gate

- **Locations**: `docs/evaluation/holdout-v1/README.md` (new);
  `docs/research/experiments/EXP-2026-08-NNN-blind-holdout-v1/` (scaffolded with
  `make new-experiment`); `docs/research/CLAIMS.md`;
  `docs/research/OPEN_QUESTIONS.md`; `docs/changelog.jsonl`.
- **What**: Wilson score intervals at n=30 for both arms, the dev-set figure
  alongside with the same interval treatment, per-category breakdown, the two
  federated strata reported separately, the discard log, and the §10 limitation
  statement verbatim. Recompute every dev-set figure from the committed judgment
  files rather than quoting prose. Then recover the Branch A §6 decision rule
  from git history and apply it as written.
- **Rationale**: at n=30 a bare point estimate overclaims, and a drop
  concentrated in the categories whose original anchors were richest means
  something very different from a uniform one.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: Holdout Execution (8/8) Complete: Reported the
  blind holdout with Wilson intervals, recorded the experiment, and applied the
  gate.

---

## 4. Deliverables

| Deliverable | Description | Location |
| --- | --- | --- |
| Sampler | Seed, populations, stratified uniform draw, prompt builder | `utils/specialists/evalset/holdout_protocol.py` |
| Sampler tests | Determinism, population integrity, strata counts, partition rule | `utils/specialists/evalset/tests/test_holdout_protocol.py` |
| Anchor draw | Seed, populations, SHA256s, draw order, over-draw, discards | `docs/evaluation/holdout-v1/anchors.json` |
| Author prompt | The exact prompt handed to every Fable 5 subagent | `docs/evaluation/holdout-v1/author-prompt.md` |
| Raw authored returns | One question per anchor, unedited | `docs/evaluation/holdout-v1/authored.json` |
| Holdout bank | 30 entries, `split: "holdout"`, computed gold | `utils/specialists/tests/golden/holdout_questions.json` |
| Bank schema tests | Conformance with the three existing banks | `utils/specialists/tests/test_holdout_bank.py` |
| Harness `--bank` | Run any bank through the arm runner | `utils/evaluation/experiment_untruncated.py` |
| Raw run artifacts | Answers + evidence + judgments, both arms | `docs/evaluation/experiments/holdout-v1/` |
| Judge harness | One Sonnet 5 agent per case | `scripts/judging/judge_holdout.mjs` |
| Per-question results | Both arms, both federated strata | `docs/evaluation/holdout-v1/results.json` |
| Write-up | Wilson intervals, per-category, strata, discards, limitation | `docs/evaluation/holdout-v1/README.md` |
| Research record | Protocol, results, manifest, claim linkage | `docs/research/experiments/EXP-2026-08-NNN-blind-holdout-v1/` |
