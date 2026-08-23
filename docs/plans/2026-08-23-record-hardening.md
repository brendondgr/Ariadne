# Record Hardening — closing the backlog the measurements opened

**Date:** 2026-08-23
**Status:** proposed, not started
**Supersedes:** nothing. Append-only per global rule 4.

## 1. Introduction

Twenty-four experiments have produced a system whose strongest results are the
ones that went against it: federation refuted on correctness, templates refuted
as the seat of accuracy, and schema-agnostic transfer shown to work only after
four couplings that no code reading found. That record is the project's main
asset, and it is currently out of step with itself — the open-questions register
says the paper's headline claim is unsupported when an experiment supports it,
says a day of work remains on machinery that already ships, and asks for a
merge-cost measurement that cannot be taken without confounding it.

This plan does three things, in dependency order. First it reconciles the living
ledgers with what has already been measured, so everything downstream is written
against something true. Then it removes the two capability inflations found by
audit — dead templates counted as templates, and a claim whose plain reading its
own data contradicts. Then it runs the four measurements that convert asserted
properties into evidenced ones: the verifier ablation, bank-draw variance, probe
expansion with tenant isolation, and the surviving federation argument. No venue
deadline governs the sequence; the ordering is dependency, not calendar.

**Judging is deferred throughout.** Every step below reports deterministic or
mechanical metrics only. Where a judged half exists it is declared in the
protocol and left unrun, with Sonnet named as the instrument, so the decision to
buy judging later does not require re-designing any experiment.

---

## 2. Gaps & Unanswered Questions

### Assumptions taken (simple gaps)

- **Venue target.** Both near-term deadlines are dropped (ARTMAN 31 Aug, EACL
  demo 22 Sept). *Assumption*: no venue target is set; the record is built for
  correctness and venue selection is revisited after Step 8.
- **Judge instrument.** *Assumption*: when judging is bought it is Sonnet via the
  relay, not local `skynet` — the local judge is measured to overstate
  faithfulness by 0.43 (EXP-2026-07-010). Each protocol names it as the deferred
  half rather than leaving it unspecified.
- **Verifier gate switches.** *Assumption*: the four switches ship permanently
  with all-on defaults, mirroring `SPECIALIST_GENERIC_ONLY`, so the ablation is
  repeatable and no existing recorded number moves. An experiment-only branch
  would make the ablation unreproducible the moment it is deleted.
- **Dead-template reachability.** *Assumption*: unreachable means no bank
  question routes there, so deletion moves no score.
  `utils/specialists/tests/test_holdout_bank.py` confirms it rather than trusting
  the reading.
- **Anchor pool depth.** *Assumption*: all ten variance draws are `--dry-run`
  first. If ten anchor-disjoint banks are not available, the bank count is
  reduced — anchors are never reused, since 51% of reseeds collide without the
  exclusion registry.
- **Q15's finding is recorded, not fixed.** *Assumption*: if the Arm H abstention
  read finds a real defect, Step 3 records it and stops. A fix moves recorded
  numbers and needs its own experiment plus a recorded-answer regression diff.
- **Merge cost and onboarding cost are excluded from Step 8**, deliberately. Both
  are functions of which two graphs are chosen — ATT&CK and CAPEC merge cheaply
  because they already share edge semantics and a taxonomy crosswalk, so any
  figure would be a statement about those two catalogues rather than about
  merging.

### Human intervention is needed to answer these

1. **Does the variance sweep cover the identity schema as well as the
   catalogues?** Step 6 as written resamples banks over ATT&CK/CAPEC, where the
   templates-vs-generic gap is the paper claim. The gap is far larger on the
   identity schema (+0.59 retrieval, EXP-2026-08-011), and a confidence interval
   there would be the stronger result — but it doubles the run and needs the
   identity stack live. **Human intervention is needed to answer this question.**

2. **Does the verifier ablation stop at the mechanical diff, or buy Sonnet for
   the residual?** Most of each gate's delta is classifiable without a judge —
   the other gates are deterministic predicates and gold is set-valued. A
   residual of genuinely ambiguous claims will remain. The plan as written
   reports that count and stops. Judging it is the deferred half.
   **Human intervention is needed to answer this question.**

---

## 3. Step-by-Step Instructions

> **Deviation from `planner.md` recorded here once, and it governs every step
> below:** the reference template says *push to GitHub*. Global rule 1 and the
> operator's standing directive say **commit, never push**. Every step therefore
> ends in a local commit with the stated message and no push.

### Step 1: Reconcile the living ledgers with what has already been measured

- **Locations**:
  - `docs/research/OPEN_QUESTIONS.md` — Q3 gains an ANSWERED block citing
    EXP-2026-08-008 (0.9467 against 0.5000); Q16 gains an ANSWERED block citing
    `utils/specialists/evalset/make_bank.py` (ships `--seed`, `--scale`,
    `--no-exclusion`, `--dry-run`) and `scripts/night2_sweep.py::make_bank2`,
    which exercised the exclusion registry against a real second draw; Q5's
    remainder is rewritten to drop merge-cost and onboarding-cost as
    dataset-confounded and to point at the structural argument Step 8 builds.
  - `docs/research/OPEN_QUESTIONS.md` §"Known weaknesses to state in the paper" —
    Q6 (judge–human agreement) closed as *will not do*, with the cross-model
    calibration (r = 0.9275 against Sonnet; self-judging overstates by 0.43) as
    the standing substitute.
  - `docs/research/CLAIMS.md` — C-003's evidence column gains the precision and
    recall cells already measured in EXP-2026-08-010 (§ headline table) and
    EXP-2026-08-011 (A-10, the I-11 precision/recall trade).
  - `docs/research/paper/venue-targets.md` — records that both near-term
    deadlines are dropped and no target is currently set.
- **Rationale**: every step below cites these files. Q3 currently tells a reader
  the paper's intended headline claim has no supporting experiment when
  EXP-2026-08-008 supports it decisively, and Q16 budgets a day for machinery
  that already ships. Writing Step 3 or Step 8 against the register in its
  present state would propagate both errors into the paper.
- **Action**: run `make validate-research` and `make index`. Once validated,
  commit stating: `Record Hardening (1/8) Complete: the register now agrees with
  the experiments — Q3, Q16 and Q5 corrected, judge–human agreement closed as a
  stated limitation.`

### Step 2: Delete the two unreachable query templates

- **Locations**:
  - `utils/specialists/cypher/builder.py` — `_node_lookup` and its dispatch
    commentary; the builder already documents that it has no reachable caller.
  - `utils/specialists/gremlin/builder.py` — `_capec_lookup`, which the source
    states was "subsumed by `describe` and has no caller".
  - `utils/specialists/cypher/normalizer.py` — the `node_lookup` row branches,
    which reduce to `label_scan`.
  - `utils/specialists/gremlin/normalizer.py` — the `capec_lookup` flat-row
    branch.
  - `utils/planner/evaluation/build_corpus.py` — the two `"lookup"` mappings.
  - `utils/specialists/tests/test_holdout_bank.py` — the declared template-name
    list.
  - `README.md` — the census sentence ("25 distinct … of which 19 are exercised")
    recounted.
  - `docs/plans/robustness/_overnight/derive_templates.py` — rerun to regenerate
    the count rather than editing it by hand.
- **Rationale**: Q13. Both templates are counted as capability in the README and
  in any paper table derived from it, and both are documented in their own source
  as having no caller. Deleting is the honest fix; it also removes normalizer
  branches that can never fire, which is what Step 4's contract test will pin.
- **Action**: run `uv run python -m pytest utils/specialists/tests/` and rerun
  `derive_templates.py`, confirming the census moves and that no bank question
  changes routing. Once validated, commit stating: `Record Hardening (2/8)
  Complete: two unreachable templates deleted and the capability census recounted
  from the code rather than asserted.`

### Step 3: Rewrite C-003, with its two supporting reads settled first

- **Locations**:
  - Q15 — the nine Arm H catalogue abstentions that carried no executed query,
    in the EXP-2026-08-007 run artifacts under `docs/evaluation/`. Determine for
    each whether the query was never executed, executed and lost, or executed and
    not attached. `utils/synthesis/verifier.py::_enforce_abstentions` is where
    proof is attached and is the location the finding will name.
  - Q17 — the two `H-SW-*` questions and their judgments from EXP-2026-08-002.
    One is known malformed (asks for techniques, names a technique as the anchor,
    graded against software ids).
  - `docs/research/CLAIMS.md` — C-003 rewritten; C-014's `software` evidence
    adjusted by whatever Q17 returns.
  - `docs/research/OPEN_QUESTIONS.md` — Q15 and Q17 status blocks.
- **Rationale**: C-003 is described in the ledger as the strongest result in the
  study and three independent measurements contradict its plain reading — Arm H
  level on the catalogue, ahead on the fresh bank, and 0.278 ahead externally.
  The replacement is scoped by evidence already on disk: templates buy precision
  and provable abstention *on schemas they were written for*, and cost coverage;
  on an unseen schema they lose both axes. Q15 matters because the generic path
  is what gets recommended for new schemas and its abstention defect travels with
  it. Q17 decides whether `software` belongs in the directional-cliff evidence at
  all.
- **Action**: run `make validate-research`. Once validated, commit stating:
  `Record Hardening (3/8) Complete: C-003 rewritten around precision and provable
  abstention, with the software category and the Arm H abstention gap resolved.`

### Step 4: D-019 — decide the evidence reader's coupling, and pin it with a test

- **Locations**:
  - `docs/research/DECISIONS.md` — new D-019 recording that the reader's dispatch
    on template-emitted column shapes is **part of what C-012 compares**, not an
    artifact to be corrected away. Guaranteeing a query's output is consumable is
    a property templates provide, and the free-form arm wears its absence.
  - `utils/specialists/evidence.py` — `check_record` / `check_contract` are the
    contract surface the decision describes.
  - `utils/specialists/tests/test_evidence_contract.py` *(new)* — assert the
    reader's accepted column-shape set equals the set the surviving templates
    emit, so adding or deleting a template without updating the reader fails the
    suite.
  - `docs/research/CLAIMS.md` — C-012's phrasing note points at D-019, and both
    figures stay on the record (0.5000 raw, 0.5739 crediting every reader
    failure).
- **Rationale**: Q18, decided as the operator directed — defend the coupling
  rather than build a generic reader. A decision record alone is unenforced
  prose; the test is what converts it into a property, and it retroactively
  guards Step 2 against orphaning a normalizer branch.
- **Action**: run `uv run python -m pytest utils/specialists/tests/` and
  `make validate-research`. Once validated, commit stating: `Record Hardening
  (4/8) Complete: D-019 defends the evidence reader's template coupling as part
  of the comparison, and a contract test now enforces it.`

### Step 5: EXP-2026-08-014 — the verifier ablation

- **Locations**:
  - `docs/research/experiments/EXP-2026-08-014-verifier-ablation/` scaffolded via
    `make new-experiment SLUG=verifier-ablation`. `PROTOCOL.md` written before
    anything runs.
  - `utils/synthesis/config.py` — `SynthesisConfig` gains four gate switches read
    from the environment, all defaulting on.
  - `utils/synthesis/verifier.py` — the four predicates inside `_verify_claim`
    (uncited, citation-resolves, entity-grounded, correlation-corroborated) and
    `_enforce_abstentions` become individually bypassable.
  - `scripts/ablation_sweep.py` *(new)* — five conditions (all-on baseline plus
    four single-gate-off), deterministic, over both catalogue banks; modelled on
    the `ARMS` / `BASE_ENV` / `apply_env` pattern in `scripts/identity_sweep.py`.
  - `utils/synthesis/tests/` — a regression asserting that all-gates-on output is
    byte-identical to the current recorded answers.
- **Design**: measure the **diff, not the run**. For each gate, take the claims
  that survive with it disabled and die with it enabled; that delta is a handful
  of claims per gate rather than thousands. Classify the delta mechanically —
  the other three gates are deterministic predicates and gold is set-valued — and
  report the residual ambiguous count rather than judging it. Negatives are
  **consolidated, not authored**: the twelve tri-source unanswerables, the bridge
  refusal/partial/control set, and the original ten become one declared negative
  pool.
- **Rationale**: Q10 and the unsupported half of C-017. "Eliminates unsupported
  claims" currently rests on provenance and inspectability both reading 1.0,
  which are self-consistency checks and not evidence. Every outcome is
  publishable, including a gate that never fires — that finding shortens the
  system description.
- **Action**: run the synthesis test suite; the default-on regression is the one
  that matters, since a moved byte means a recorded number moved. Then
  `make validate-research`. Once validated, commit stating: `Record Hardening
  (5/8) Complete: EXP-2026-08-014 ablates the four verifier gates and measures
  what each one actually cuts.`

### Step 6: EXP-2026-08-015 — bank-draw variance, retrieval only

- **Locations**:
  - `docs/research/experiments/EXP-2026-08-015-bank-variance/` via
    `make new-experiment SLUG=bank-variance`.
  - `uv run python -m utils.specialists.evalset.make_bank --seed <n> --scale 1
    --dry-run` for all ten draws first, checked against
    `utils/specialists/evalset/drawn_anchors.json`.
  - `scripts/variance_sweep.py` *(new)* — ten banks × two arms
    (`deterministic`, `generic`), reusing `run_one` / `ARMS` / `BASE_ENV` from
    `scripts/identity_sweep.py`.
- **Design**: retrieval metrics only. Both arms are LLM-free and
  byte-reproducible, so the pipeline contributes **zero** variance and every
  point of spread is bank-draw variance — which is the quantity the study has
  never had. Paired percentile bootstrap on the templates-minus-generic gap,
  2000 resamples, seed recorded, matching EXP-2026-08-007's precedent.
- **Rationale**: Q2's open half. Eleven manifests carry a null
  `statistical_test` and every arm figure is `n_runs: 1`. Re-running a
  deterministic pipeline ten times would produce ten identical numbers;
  resampling the bank is where the variance actually lives, and this is the first
  confidence interval the templates-vs-generic gap has ever carried.
- **Action**: confirm the ten banks are anchor-disjoint, then
  `make validate-research`. Once validated, commit stating: `Record Hardening
  (6/8) Complete: EXP-2026-08-015 gives the templates-vs-generic gap its first
  confidence interval, from ten disjoint bank draws.`

### Step 7: EXP-2026-08-016 — probe expansion and tenant isolation

- **Locations**:
  - `utils/specialists/tests/fixtures/adversarial_probes.py` — currently ten
    Cypher and seven Gremlin probes, hand-written. Add a generator producing
    several hundred by mutation across the declared categories: write
    clauses/steps, parameter injection (including the Groovy-escape class),
    labels outside the card schema, unbounded and over-depth traversal, and
    `LIMIT` evasion.
  - `utils/specialists/evalset/score_safety.py` — `score_safety()` consumes the
    expanded suite unchanged.
  - `scripts/isolation_probes.py` *(new)* — with `attack`, `capec` and `identity`
    all live, does any accepted query or returned evidence for a question about
    one source carry records from another? Run against the pre-fix and post-fix
    routing rules.
  - `docs/research/experiments/EXP-2026-08-016-tenant-isolation/`.
- **Rationale**: C-008 rests on seventeen probes, and the suite itself found the
  one bypass that was then fixed — so it partly grades against its own answer
  key. The isolation half is new and is the question a customer graph introduces:
  the pre-fix behaviour is already observed (one abstention returned 558 CAPEC
  records beside the single honest identity record) and this converts an
  observation into a measurement with a before and an after.
- **Action**: run `uv run python -m pytest utils/specialists/tests/`. The gate
  must block 100%; a single miss is a hard failure and is recorded as one, not
  smoothed. Then `make validate-research`. Once validated, commit stating:
  `Record Hardening (7/8) Complete: EXP-2026-08-016 expands the probe suite from
  17 to several hundred and measures cross-source leakage before and after the
  routing fix.`

### Step 8: C-022 — federation as an isolation and non-modification claim

- **Locations**:
  - `docs/research/CLAIMS.md` — new C-022.
  - `docs/research/experiments/EXP-2026-08-017-federation-isolation/`.
  - Evidence assembled from `utils/kg_builder/merge.py` (exactly what the merged
    condition had to write that upstream does not ship — D-017's two
    reconciliations), EXP-2026-08-013 (the identity graph loaded unmodified;
    three sources retrieving identically to one), and EXP-2026-08-009 (the 7→3
    skipped-join figure, reported as what merging buys).
  - `docs/research/OPEN_QUESTIONS.md` — Q5's remainder closed or narrowed.
- **Rationale**: C-015 is refuted on correctness and that result stays refuted.
  What survives is structural and dataset-independent: **merging required editing
  both catalogues at load, and re-doing it on every release; federation ran them
  as shipped.** The advantage merging genuinely holds — cheaper multi-hop across
  the seam, because the next identifier is reachable without leaving the engine —
  is reported alongside, since reporting it is what makes the rest credible.
- **Action**: run `make validate-research` and `make index`. Once validated,
  commit stating: `Record Hardening (8/8) Complete: C-022 states the surviving
  federation case as non-modification and isolation, with what merging buys
  reported beside it.`

---

## 4. Deliverables

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Ledger reconciliation | Q3, Q5, Q16 corrected; Q6 closed as a stated limitation; C-003 evidence column filled from measured precision/recall | `docs/research/OPEN_QUESTIONS.md`, `docs/research/CLAIMS.md`, `docs/research/paper/venue-targets.md` |
| Dead-template removal | Two unreachable templates and their normalizer branches deleted; census recounted from code | `utils/specialists/cypher/builder.py`, `utils/specialists/gremlin/builder.py`, both normalizers, `README.md` |
| Template census regeneration | Recount run, not hand-edited | `docs/plans/robustness/_overnight/derive_templates.py` |
| C-003 rewrite | Claim rescoped to precision and provable abstention, with the coverage cost stated | `docs/research/CLAIMS.md` |
| D-019 decision record | The evidence reader's template coupling defended as part of the comparison | `docs/research/DECISIONS.md` |
| **Evidence-contract test** | Asserts the reader's accepted column shapes equal the surviving templates' emitted shapes | `utils/specialists/tests/test_evidence_contract.py` |
| Verifier gate switches | Four individually bypassable gates, all-on by default | `utils/synthesis/config.py`, `utils/synthesis/verifier.py` |
| **Verifier default-on regression test** | All-gates-on output byte-identical to the recorded answers | `utils/synthesis/tests/` |
| Ablation harness | Five conditions over both catalogue banks, diff-scored | `scripts/ablation_sweep.py` |
| Verifier ablation experiment | What each gate actually cuts, plus the consolidated negative pool | `docs/research/experiments/EXP-2026-08-014-verifier-ablation/` |
| Variance harness | Ten anchor-disjoint bank draws × two arms, retrieval only | `scripts/variance_sweep.py` |
| Bank-variance experiment | First confidence interval on the templates-vs-generic gap | `docs/research/experiments/EXP-2026-08-015-bank-variance/` |
| Expanded probe suite | Several hundred generated adversarial probes across five categories | `utils/specialists/tests/fixtures/adversarial_probes.py` |
| Isolation harness | Cross-source leakage with three live sources, pre- and post-routing-fix | `scripts/isolation_probes.py` |
| Tenant-isolation experiment | Probe block rate and leakage measurement | `docs/research/experiments/EXP-2026-08-016-tenant-isolation/` |
| C-022 and its record | Federation stated as non-modification and isolation | `docs/research/CLAIMS.md`, `docs/research/experiments/EXP-2026-08-017-federation-isolation/` |

### Test subset run at every step

| Test | Scope |
| --- | --- |
| `uv run python -m pytest utils/specialists/tests/` | Builders, normalizers, holdout-bank template list, evidence contract, probe suite |
| `uv run python -m pytest utils/synthesis/tests/` | Verifier gates default-on; composer output unmoved |
| `make validate-research` | Schema, claim linkage, figure and pointer checks |
| `make index` | Regenerates `INDEX.md`; CI fails on a stale copy |
