# Correctness Repair Close-out — the last four items, run back-to-back

**Date:** 2026-09-12 · **Seed for the fresh set:** `10140325` · **Model:** only
`http://localhost:9090/v1` / `default-model` (operator directive 2026-09-11) ·
**Git:** commit at every step, never push.

---

## 1. Introduction

`EXP-2026-09-018` has moved the Generic arm on the development half from 0.7845
to **0.9211** (1,704 judgments, both grading positions, `data/dev_half_judged.json`)
and the model-free arm to 0.9210; the Step 6 kill-gate metric,
`fabricated_mapping`, is 0 on both. What remains is not more repair but
**closing the record honestly**: two defects the grader exposed and I recorded
rather than fixed, a comparison that is still one-sided, a fresh sealed set so a
number exists that nothing here has touched, and the write-up that makes the
figures citable.

The plan is ordered so that everything cheap and code-only happens first and is
verified on the exact failing cases before any model runs, then one unattended
server chain does the paired control and the fresh set with a resumable state
file, then the write-up reads from committed artifacts only. The two defects
change the tree, so they must land **before** the paired control, or the control
would measure a tree that no longer exists.

---

## 2. Gaps & Unanswered Questions

- **Author model for the fresh set.** The programme's Step 7 says "the author
  model"; the existing bank's questions were written by Claude author agents from
  briefs and validated by `scripts/ingest_authored.py`. The only endpoint
  sanctioned in this session is `default-model` on `:9090`, and
  `utils/specialists/evalset/author.py` defaults to `:4000` / `local`.
  *Assumption:* render with `scripts/render_questions.py --base-url
  http://localhost:9090/v1 --model default-model`, and let the ingest
  validators (must name the anchor, no other identifier, no answer, no schema
  vocabulary) be the quality gate. **If the rejection rate exceeds 25 %, human
  intervention is needed to answer this question** — either accept a smaller
  fresh set or author the rejected shapes by hand.
- **Fresh set size and split.** *Assumption:* one whole bank, no dev/holdout
  split, targeted at the holdout's size and tier mix (288; D0 25, D1 28, D2 37,
  D3 45, D4 62, D5 58, D6 33), drawn with `--seed 10140325`. Every spec id is
  checked against both existing banks; overlap is reported and the overlapping
  specs are excluded before sealing.
- **The paired-control scorer.** `control-metrics.json` was committed at
  `46652efc` without the script that produced it. *Assumption:* write
  `scripts/paired_control_score.py` and re-derive the Step 6 numbers from the
  committed judgments as its first test — it must reproduce 0.7188 / 0.7845
  before it is trusted on new data.
- **The reference worktree predates Q56.** At `e09c2571` the arm runner's
  default model was the dead `skynet` alias and there was no preflight, so the
  reference side would silently run model-free. *Handled:* the control runner
  passes `--llm-model default-model` explicitly and asserts the fallback rate
  over answers is below 0.14 after each reference arm (`degraded()`), as the
  protocol requires.
- **I-15's fix shape.** Whether the grader stops flagging text items once they
  are quoted and labelled by kind is an empirical question. *Handled:* Step 2
  judges its own 12-case slice before anything larger runs; if the flags do not
  fall, the step records that and the write-up carries the category as a known
  grader artefact instead.
- **Seed provenance.** `10140325` was supplied by the operator on 2026-09-12 and
  is recorded in the bank's metadata and in `POINTERS.md` before any arm runs.

---

## 3. Hierarchical Step-by-Step Instructions

Each step's validation runs first on a **small, named slice** and only then on
the whole bank. Every step ends in a commit. Steps 1–2 are code; Steps 3–4 are
one unattended server chain; Step 5 is the record.

### Step 1 — I-16: a false absence claim names the question's edge, not the store's

- **Locations:** `utils/synthesis/composer.py` — `_relation_is_empty` (line
  ~545) and its warrants `_query_asked_about`, `_schema_denies`,
  `_facet_counts_zero`; `utils/specialists/schema/registry.py` (the edge the
  builder resolved for the anchor's label is already known there);
  `utils/synthesis/tests/test_composer.py` (new tests);
  `scripts/mechanism_check.py` (add a `contradiction` property: an absence
  claim naming a relation whose neighbours the same answer enumerates).
- **What changes:** the absence check currently looks for related entries whose
  `type` equals the *question's* relation name. A View's members hang off
  `IN_VIEW` and a Category's off `MEMBER_OF`; the builder resolves that and
  retrieves the members, then the composer writes "CAPEC-703 has no MEMBER_OF
  relationships" beneath the list of them. The check must treat neighbours the
  executed walk returned for **this sub-question's resolved edge** as satisfying
  the relation, whatever the edge is called — the warrant is the executed query,
  and the query already carries the resolved edge name. Fifteen flags on the
  development half; this is the only open item that costs *correctness*.
- **Rationale:** a false statement with full provenance is the worst thing this
  system can emit, and it is the more urgent of the two defects.
- **Small test first:** the 9 flagged case ids (`CAPEC-703`, `CAPEC-3000`,
  `CAPEC-1000`, `T1518`, `S0065`, `S0267`, `CAPEC-528`, `T1111` cases — listed in
  `data/dev_half_judged.json`) through `generic_composed` with `--only`; the
  contradiction scanner must read **0** on them.
- **Validation:** unit tests green; contradiction count 0 over all 284
  development and all 288 holdout answers model-free; `gold_text_recall.py`
  shows **no question regressing** against `dev-half-2026-09-12` on either
  arm; `mechanism_check.py` unchanged or better on every slice.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  Close-out (1/5) Complete: an absence claim is judged against the edge the
  store resolved, never the name the question used.

### Step 2 — I-15: node text read as an identifier, and our own id examples in answers

- **Locations:** `utils/synthesis/composer.py` — `_related_display` (~1024),
  `_is_composite_child`, `_enumeration_claim` (~1101), `_related_by_label`;
  the three `_ID_EXAMPLES` call sites (~123, ~202, ~1430);
  `utils/synthesis/verifier.py` (the enumeration verdict must still ground
  every *identifier* it lists);
  `utils/synthesis/tests/test_composer.py`;
  `docs/research/experiments/EXP-2026-09-018-correctness-repair/data/flag_classes.py`
  (new: the classifier that produced the four-way flag table, so the count is
  reproducible rather than a chat-log number).
- **What changes:** (a) a related entry with no published identifier is
  rendered as a **labelled quotation in its own sentence** — "one consequence:
  “Confidentiality — Other”" — never as an item in the same comma-list as
  identifiers, so a reader or a grader cannot parse it as an asserted id;
  identifiers keep the existing list. (b) `_ID_EXAMPLES` ("e.g. T1566, M1017,
  or CAPEC-98") is removed from every answer-facing string — 54 flags were the
  system flagging its own help text; the hint moves to a non-claim `notes`
  entry if it is kept at all.
- **Rationale:** 114 + 54 of the 291 flags on the development half; none is an
  invention, but faithfulness is a headline metric and the write-up cannot
  carry "the grader misreads us" as an excuse for 58 % of its flags.
- **Small test first:** the 12 most-flagged answers (`C0029`, three
  `CAPEC-248`, `T1505.005`, `CAPEC-703`, `S0435`, `CAPEC-634` cases and the four
  next) regenerated on `generic_composed` and **judged in one position** —
  about five minutes — then classified with `flag_classes.py`. The
  "node text read as an identifier" and "own id-example" categories must
  fall to ≤ 2 combined on that slice, with correctness on the slice not lower
  than in `dev-half-2026-09-12`.
- **Validation:** unit tests green; `gold_text_recall.py` no regression on
  either bank; the enumeration verifier still grounds 100 % of listed
  identifiers; the deterministic arm's recorded answers diffed per
  `[[ariadne-recorded-answer-regression]]` with only the intended sentences
  changed.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  Close-out (2/5) Complete: text-valued neighbours are quoted and labelled,
  and no answer carries example identifiers.

### Step 3 — The paired control, done as the protocol asks (server, ~5 h unattended)

- **Locations:** `scripts/repair_control_run.py` (reference worktree at
  `e09c2571` on the **current** data, `--llm-model default-model` forced,
  `degraded()` after every arm, 32 workers); **new**
  `scripts/paired_control_score.py` (paired bootstrap per tier and per
  mechanism slice for H1–H3 and H6; kill gate; writes
  `control-metrics.json` — first run must reproduce the committed
  0.7188 / 0.7845 from the Step 6 judgments); `scripts/variant_harness.py
  compare` for the T6 wrong-entity and catalogue-dump rates on the final tree
  against the reference capture; `utils/specialists/evalset/latency.py` driven
  at one worker over 20 questions at `SYNTHESIS_LLM_TIMEOUT_S=120` and `=600`
  for the repaired `generic`; `scripts/model_identity.py --json` before the
  first run; output root `docs/evaluation/experiments/paired-control-2026-09-12/`
  with a `state.json` that resumes step-by-step exactly like
  `scripts/dev_half_judged.py`.
- **What runs:** six cells — `generic`, `generic_composed`, `deterministic` at
  the final tree **and** at `e09c2571` — generated in one sitting on the same
  live graphs, each judged in both positions. The repaired side is re-run even
  though `dev-half-2026-09-12` exists, because Steps 1–2 changed the tree and
  because a pair is two sides of one sitting by definition.
- **Rationale:** `Q46` records a 0.0503 between-session move with zero
  within-session spread. The 0.1366 gap is well outside that and sits exactly
  where the repairs were, but the protocol pre-registered a concurrent control
  and the ship decision rests on it. This step also delivers the two Step 6
  items still missing: the T6 rates and the single-user latency at the shipped
  budget (`Q37`).
- **Small test first:** an 8-question `--only` slice (two per hard tier, one
  per easy tier) through **both** sides, generation only, asserting: the
  reference worktree resolves `data/` and `.env`, its preflight reports
  `qwen38-27B-v2`, its fallback rate is 0, and the `deterministic` reference
  answers are byte-identical to `data/reference/` for those 8. Only then the
  full chain starts.
- **Validation:** every arm's fallback rate below 0.14; `deterministic`
  reference byte-identical to `data/reference/` on all 284 (excluding clock
  keys); `fabricated_mapping` 0 on both repaired arms; T6 wrong-entity and
  catalogue-dump rates not above the reference; latency at 120 s not above 2×
  the reference; H1–H3 and H6 recorded whichever way they fall; the grader-drift
  control (the 222 unchanged answers from Step 5) moves by less than 0.0066.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  Close-out (3/5) Complete: repaired and reference arms generated and judged in
  one sitting; H1–H3, H6, T6 and latency recorded; kill gate read.

### Step 4 — Step 7: a freshly sealed set, seed 10140325, run once (server, ~5 h unattended)

- **Locations:** `scripts/select_bank.py --seed 10140325 --out
  docs/evaluation/composition/bank/selection-fresh-2026-09-12.json` with the
  holdout's tier quotas; `scripts/render_questions.py --seed 10140325
  --base-url http://localhost:9090/v1 --model default-model` (the author);
  `scripts/ingest_authored.py` (the four validators, rejection rate reported);
  `scripts/build_bank.py --out …` writing
  `docs/evaluation/composition/bank/bank-fresh-2026-09-12.json` with the seed,
  the author model identity, the tier mix and the reweighting table in its
  metadata; **new** `scripts/fresh_seal.py` — `holdout_seal.py` generalised
  with a `--bank` argument (its `EXPECTED_BANK_PREFIX` is hard-coded to the old
  bank), asserting **zero** answers and judgments exist for any fresh case id
  under `docs/evaluation/experiments/` and writing the bank's SHA-256 into
  `EXP-2026-09-018/data/POINTERS.md` **before** any arm runs; then one run of
  `generic`, `generic_composed`, `deterministic`, both positions, into
  `docs/evaluation/experiments/fresh-2026-09-12/`; then `bank-holdout.json`
  re-run on the same three arms as a **regression set**, diffed against
  `EXP-2026-09-007`, labelled as such everywhere it appears.
- **Rationale:** the development half selected the configuration and the
  holdout has been graded twice already, so neither is unseen. The only figure
  that can replace 0.6546 on a slide is one from a set nothing here has touched,
  and the seal has to be provable, not asserted.
- **Small tests first:** (a) a dry selection reporting tier mix and shape
  coverage against the holdout's, and the spec-id overlap with both existing
  banks (must be reported; overlapping specs excluded); (b) render **20**
  questions and run the ingest validators — the rejection rate is the gate in
  §2; (c) `fresh_seal.py` must *fail* when pointed at `bank-holdout.json` (it
  has judgments) and *pass* on the fresh bank — a seal check that cannot fail
  is not a check (`holdout_seal.py`'s predecessor was vacuously green); (d) the
  composition invariants in `utils/specialists/evalset/tests/test_composition.py`
  run against the fresh specs (a D6 never anchors on a dangling reference).
- **Validation:** seal recorded before the first answer file exists (the
  runner refuses to start otherwise); all three arms write the full count or
  are recorded `not_run`; fallback below 0.14; the fresh-set figure with paired
  intervals into `metrics.json`; the `none` bucket's 0.9675 either holds on the
  fresh set or the protocol's falsification clause is recorded; holdout
  regression diffed against `EXP-2026-09-007` and never reported as new
  evidence.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  Close-out (4/5) Complete: fresh set drawn with seed 10140325, sealed before
  use, judged once; holdout re-run as regression only.

### Step 5 — Step 8: write-up, ledgers, defaults, pitch numbers

- **Locations:** `EXP-2026-09-018/RESULTS.md` (headline; per-tier and
  per-mechanism before/after from the paired control; the frozen-evidence
  result; the fresh-set figure; the convergence of the two real arms; the
  four-way hallucination-flag table with I-15/I-16 closed; threats to validity
  including the one-sided interim comparison now superseded);
  `manifest.yaml` (`status: complete`, every figure, `supports_claims`);
  `data/metrics.json`; `docs/research/CLAIMS.md` — `C-023` evidence amended
  with the fresh-set and paired-dev figures, `C-017` gains the absence claim
  with proof; `docs/research/DECISIONS.md` — one decision making the chained
  walk and the answer contract the default (if the kill gate held), one making
  a spent holdout a regression set; `docs/research/OPEN_QUESTIONS.md` — close
  `Q45`, `Q50`–`Q53`, record `Q57` (the grader flags identifiers the rolled-up
  gold omits: a completeness-vs-faithfulness tension in the metric itself);
  `docs/pitch/` — **only if** the fresh-set figure is in hand, a numbers audit
  updating slide 5 and B1 with it labelled as such and 0.6546 kept as the
  holdout figure; `docs/changelog.jsonl`; `make index`, `make
  validate-research`, `make check-docs`.
- **Rationale:** the record is the deliverable. A repaired arm without an
  amended claim and an updated pitch is a number in a chat log again.
- **Validation:** all three gates green; every figure in the write-up traces to
  `metrics.json`; `CURRENT.md` regenerated and read before any number is quoted
  in prose; the pitch audit's verification log extended; no uncommitted work.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  Close-out (5/5) Complete: results, claims, decisions, questions and pitch
  figures recorded.

### Running it back-to-back

Steps 1–2 are code and tests (~3 h, model used only for Step 2's five-minute
slice). Steps 3–4 are one script, `scripts/closeout_run.py`, that chains the
paired control and the fresh set with a `state.json` resumable at step
granularity, exactly as `scripts/dev_half_judged.py` does — a kill and restart
loses only in-flight requests. It refuses to start unless the tree is clean at a
commit after Step 2, the model identity probe reports `qwen38-27B-v2`, and the
fresh bank's seal is recorded. Human checkpoints are exactly two: the author
rejection-rate gate in §2 and any kill-gate failure in Step 3, both of which
stop the chain and report rather than proceed.

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Absence-claim fix (I-16) | `_relation_is_empty` satisfied by the store's resolved edge, not the question's name | `utils/synthesis/composer.py` |
| I-16 tests | View/Category members under `IN_VIEW`/`MEMBER_OF` never yield an absence claim; a genuinely empty relation still does | `utils/synthesis/tests/test_composer.py` |
| Contradiction property | `mechanism_check.py` asserts 0 absence-beside-enumeration contradictions per slice | `scripts/mechanism_check.py` |
| Text-neighbour rendering (I-15) | Labelled quotation in its own sentence; identifiers keep the list; no `_ID_EXAMPLES` in answers | `utils/synthesis/composer.py`, `utils/synthesis/verifier.py` |
| I-15 tests | Text items never appear in an identifier list; verifier grounds every listed id; help-text ids absent | `utils/synthesis/tests/test_composer.py`, `test_verifier.py` |
| Flag classifier | Reproduces the four-way hallucination-flag table from judgment files | `EXP-2026-09-018/data/flag_classes.py` |
| Paired-control scorer | Paired bootstrap per tier/mechanism, H1–H3/H6, kill gate; reproduces the committed Step 6 numbers as its own test | `scripts/paired_control_score.py`, `scripts/tests/test_paired_control_score.py` |
| Control runner hardening | `--llm-model` forced on the reference side, `degraded()` per arm, 8-question dry run, resumable state | `scripts/repair_control_run.py` |
| Paired control run | Six cells, one sitting, two positions; T6 rates; latency at 120 s / 600 s | `docs/evaluation/experiments/paired-control-2026-09-12/`, `data/control-metrics.json` |
| Fresh selection | Seed 10140325, holdout tier mix, overlap report | `docs/evaluation/composition/bank/selection-fresh-2026-09-12.json` |
| Fresh bank | Rendered on `default-model`, ingest-validated, seed and author identity in metadata | `docs/evaluation/composition/bank/bank-fresh-2026-09-12.json` |
| Seal | `holdout_seal.py` generalised with `--bank`; fails on a spent bank, passes on the fresh one; hash into POINTERS before any run | `scripts/fresh_seal.py`, `EXP-2026-09-018/data/POINTERS.md` |
| Fresh-set run | Three arms, both positions, once; holdout re-run as regression only | `docs/evaluation/experiments/fresh-2026-09-12/`, `…/holdout-regression-2026-09-12/` |
| Close-out chain | Steps 3–4 unattended with state-file resume and the three start guards | `scripts/closeout_run.py` |
| Experiment record | RESULTS, manifest (`complete`), metrics.json, figures | `docs/research/experiments/EXP-2026-09-018-correctness-repair/` |
| Ledgers and pitch | C-023 / C-017 amended; two decisions; Q45, Q50–Q53 closed, Q57 filed; pitch audit if the fresh figure exists | `docs/research/{CLAIMS,DECISIONS,OPEN_QUESTIONS}.md`, `docs/pitch/`, `docs/changelog.jsonl` |
