# Publication plan — from the current record to a submitted paper

**Status:** proposed, 2026-09-03. Nothing below has been run.
**Supersedes as a work plan:** the X1–X10 distance estimate in
[`docs/research/audit-2026-08-31.md`](../research/audit-2026-08-31.md) §8.5,
which is three days stale in two ways this plan corrects.

---

## 1. Introduction

The project is at **L4 readiness**: ready for a workshop or demo submission
today, and **exactly one axis short** of an applied conference. That axis is
*novelty defensibility* (scored 2, needs 3), and the audit's own finding is that
it is raised **by writing, not by measuring** — seven of eight axes already clear
the bar. The framing is settled (`D-027`): *the architecture is the method
section; the contribution is the measurements and the resource.*

Two things have changed since that assessment was written, and both change the
plan. First, **X1 is already done** — Q24 closed on 2026-08-31 and is drafted in
[`paper/sections/09-failure-localisation.md`](../research/paper/sections/09-failure-localisation.md),
so the audit's "cheapest decisive next action" is spent. Second,
**EXP-2026-09-002 is now filed**, and it makes the paper's primary result
materially stronger: the boundary on the template advantage is the templates'
question **vocabulary**, not the schema. That is the claim the paper should lead
with.

But EXP-2026-09-002 also introduced the single largest threat to its own
headline, and this plan is sequenced around it. **The template arm's 0.4934 was
measured with a live defect in the template path** — 63 of 63 property reads and
68 of 68 containment questions built a query that returned zero rows, with
Group, Tactic and View at exactly 0.0000. A reviewer will say, correctly, *"your
baseline had a bug."* Until that defect is fixed and both arms re-run, **the
0.1642 gap is not quotable in a paper.** Everything downstream of the headline
therefore waits on Step 1.

---

## 2. Gaps & Unanswered Questions

**Simple gaps — assumption stated, proceeding.**

- **Does the empty-query defect also affect the `generic` arm?** `anomalies.json`
  records `"arm": "deterministic"` only; the generic arm was never triaged.
  *Assumption:* it must be measured, not assumed, and Step 1 triages both arms
  before either number is quoted. If the defect is symmetric the gap survives
  unchanged; if it is not, the gap moves.
- **How much does the fix move the gap?** Unknown and unknowable in advance.
  *Assumption:* plan for both outcomes. Step 1's exit criterion is *"the gap is
  re-measured"*, not *"the gap survives"* — a narrowed or reversed gap is a
  result, not a failure, and the paper's §5 accommodates either.
- **`llm_query` at an adequate budget.** *Assumption:* fix the two budget defects
  and re-run that arm once. If wall-clock proves prohibitive (the arm already
  cost 4.9 h at 4096; 32768 will be far worse), declare it out of scope for this
  paper and report EXP-2026-08-008's figure as C-012's sole support, with the
  confound documented. **Do not** ship 0.3712.
- **The one missing `llm_query` case** (283 of 284, ISSUES I-7). *Assumption:*
  account for it during Step 3's re-run; it cannot move a 0.1642 gap.

**Complex gaps — human intervention is needed to answer these.**

- **Venue and deadline.** `venue-targets.md` is stale by its own banner, every
  date in it was read on 3 August, and several have passed. EACL 2027 System
  Demonstrations is listed at **22 September** — 19 days out — and the reason it
  was dropped ("an open backlog a submission would have to be written around")
  is recorded as **no longer applying**. There is also an unimported independent
  venue report at `~/Downloads/ariadne-venue-report.md`.
  **Human intervention is needed to answer this question:** demo track now, or
  applied conference in the December window?
- **Priority against the 23 October ReliaQuest pitch.** The grant's contractual
  deliverable is a live demo and evaluation results, and two roadmap rows in
  `docs/goals.md` remain open. This plan consumes the same weeks.
  **Human intervention is needed to answer this question.**
- **Q26 — do the banks emit executable gold queries?** The audit calls the
  resource *"may be the stronger paper"*, and the schema census removed the
  circularity objection by supplying a neutral `(subject, predicate, object)`
  shape. It is still a scope decision with a 1–1.5 week cost.
  **Human intervention is needed to answer this question.**
- **Funder assent** for publishing a releasable proxy for the identity results
  (X7). The strongest transfer results in the record sit on non-redistributable
  data. Gated on other people. **Human intervention is needed.**

---

## 3. Hierarchical Step-by-Step Instructions

> **Repository note.** The planner skill's template says *push to GitHub*. This
> repository does not push — `docs/skills/global-project-rules` rule 1 requires a
> commit at every step and forbids `git push` unless the operator asks in the
> session. Every step below therefore ends in a **commit**, and every step also
> appends to `docs/changelog.jsonl` and runs `make validate-research` if it
> touches `docs/research/`.

### Step 0 — File EXP-2026-09-002 ✅ COMPLETE (2026-09-03, commit `5660fa2`)

The overnight sweep is in the research record; C-023 is amended to the
vocabulary condition; C-012 carries a do-not-cite warning on the confounded arm.
35 experiments validate.

---

### Step 1 — Fix the empty-query defect, and re-measure the headline

- **Locations**: `utils/specialists/` (the deterministic template builder and its
  property-read templates), `utils/specialists/evalset/`, the source-card
  property mappings under `data/source_cards/overlays/`,
  `scripts/anomaly_triage.py` (extend to accept `--arm generic`),
  `scripts/expansion_overnight.py` (re-run phases `run:*`, `score`, `judge:*`).
- **Rationale**: this is the gate on everything that quotes the headline. 131
  failures share one cause — a query is built, passes the gate, executes cleanly,
  and looks where the answer is not — and three node types fail at exactly
  0.0000 while everything else works about half the time. That is the signature
  of a property-name or storage-location mismatch, not a capability limit. It is
  the cheapest open defect in the project **and** it is a confound on the
  paper's primary comparison. Triage the `generic` arm in the same pass so the
  post-fix comparison is symmetric.
- **Guard**: per `ariadne-recorded-answer-regression`, re-run the deterministic
  arm over **both** committed banks and diff excluding clock keys before
  accepting the fix — a builder change that moves the expansion bank must not
  silently move the golden catalogue.
- **Exit criterion**: the judged gap is **re-measured post-fix on both arms**,
  and `docs/research/CLAIMS.md` C-023 quotes the post-fix number. A narrowed,
  unchanged or reversed gap all satisfy this step.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Publication Plan (1/9) Complete: fixed the
  empty-query defect in the template path and re-measured the C-023 headline on
  both arms.*

---

### Step 2 — Record the re-measurement as EXP-2026-09-003

- **Locations**: `make new-experiment SLUG=empty-query-repair`, then
  `docs/research/experiments/EXP-2026-09-003-*/`, `docs/research/CLAIMS.md`.
- **Rationale**: Step 1 changes a headline number, and a changed headline that
  is not in the record is exactly the failure EXP-2026-09-002 was filed to
  correct. The protocol must be written **before** the re-run, so in practice
  Step 1 and Step 2 interleave: scaffold and write `PROTOCOL.md` first, run, then
  fill `RESULTS.md`. Mark EXP-2026-09-002 `superseded_by` if the gap moves
  materially; leave it standing if it does not.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Publication Plan (2/9) Complete: recorded the
  post-repair headline as EXP-2026-09-003 and reconciled C-023.*

---

### Step 3 — Settle the `llm_query` arm: fix the budget, or cut it

- **Locations**: the builder's budget resolution (the path that ignores `.env`'s
  `2048` and defaults to `4096`), `.env.example`,
  `scripts/builder_budget_probe.py`, `docs/research/CLAIMS.md` C-012.
- **Rationale**: two separate defects — a written-down setting that is silently
  ignored, and a default too small for a reasoning model whose chain-of-thought
  runs 16 000+ characters before `content` is emitted. Fixing only the first
  still yields a blank. Per `ariadne-skynet-reasoning-budget`, every caller needs
  a real budget. This is also a live landmine for the October demo, not only for
  the paper.
  **Decide explicitly**: re-run the arm at an adequate budget, or cut it from the
  paper and let C-012 rest on EXP-2026-08-008 alone. Both are defensible; what is
  not defensible is shipping 0.3712.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Publication Plan (3/9) Complete: repaired the
  reasoning-budget defects and [re-ran / cut] the query-writing arm.*

---

### Step 4 — X2: cross-model re-grade of the August headline comparisons

- **Locations**: `docs/plans/2026-08-31-model-migration-qwen38.md` §3–§4 (written,
  status *"proposed — nothing below has been run"*), the saved answer artifacts
  for `EXP-2026-08-007`/`-008`/`-009`, `utils/evaluation/judge_answers.py`,
  `utils/evaluation/grading_order.py`.
- **Rationale**: C-012, C-021 and C-022 — three of the paper's four legs — were
  graded in the 19–21 August window when the served model is **not determinable**
  (Q12). Re-grading the *saved answers* is one variable and needs no pipeline
  run. EXP-2026-09-002 delivers part of this value already, on a 9× larger
  sample by an identified grader, but it does **not** cover C-022's federation
  null, and X2's purpose is to protect those specific saved figures.
- **Risk, stated in advance**: the margins may move. C-012's 0.9467-vs-0.5000 is
  wide enough to survive; C-021's **0.0483** and C-022's null are not obviously
  so. A moved margin is a result and gets recorded, not re-run until it agrees.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Publication Plan (4/9) Complete: re-graded the
  August headline comparisons with an identified model and reconciled C-012,
  C-021, C-022.*

---

### Step 5 — Decide Q26, and if yes, build the resource

- **Locations**: `docs/research/OPEN_QUESTIONS.md` Q26,
  `docs/research/CLAIMS.md` C-025, `utils/specialists/evalset/`,
  `docs/evaluation/composition/bank/`, `docs/research/datasets/`.
- **Rationale**: **the only item that can move the binding axis on its own.** No
  existing artifact pairs security-taxonomy questions with executable gold graph
  queries scored by execution, and the most active competing group has twice
  declared comprehensive evaluation to be future work. The census removed the
  sharpest objection: a query serialized from a census `(subject, predicate,
  object)` path, with no knowledge that Ariadne has templates at all, is
  co-authored by neither arm.
- **The defence is mandatory and mechanical**: a query is gold **only if
  executing it reproduces gold computed independently from the raw STIX/CAPEC
  files**. Emitting our own templates' queries as gold and then scoring ourselves
  against them would be the most circular thing in the project. Build the
  validator before the emitter.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Publication Plan (5/9) Complete: decided Q26
  and [emitted and independently validated executable gold queries / recorded the
  decision not to, with reasons].*

---

### Step 6 — Close the positioning gaps and write the related-work section

- **Locations**: `docs/research/RELATED_WORK.md`,
  `docs/research/OPEN_QUESTIONS.md` Q25,
  `docs/research/paper/sections/02-related-work.md` (new).
- **Rationale**: two halves, and they are ordered. **X5 first** — open the four
  works the novelty audit could not: QUINT, TeBaQA, QAnswer/WDAqua and SG-KBQA,
  plus a sweep of CEUR/ESWC/ISWC 2026 workshop volumes, RAGE-KG 2026 first,
  because that is where the closest group would publish the evaluation they have
  deferred. If TeBaQA's portability evaluation contains a precision-versus-
  coverage table across knowledge graphs, **C-023 narrows** and the paper must
  know that before it is written, not after review. **Then X4** — the prose
  stating the delta against the 20 ranked works.
- **Discipline**: per the robustness plans' shared rule, every citation traces to
  a retrieved document. The audit's most damaging single finding was a citation
  nobody had opened. Anything unverifiable is recorded as unverified.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Publication Plan (6/9) Complete: closed the
  five positioning gaps and wrote the related-work section.*

---

### Step 7 — Spend the holdout, once

- **Locations**: `docs/evaluation/composition/bank/bank.json` (the 288 sealed
  questions), `scripts/expansion_overnight.py`, a new experiment folder.
- **Rationale**: **288 questions have never been touched and are worth something
  only while that is true.** They must be spent *after* every fix in Steps 1–3,
  because a holdout run against a system you are still repairing is spent for
  nothing — and re-running it post-fix makes it co-authored with its own
  diagnosis, which is precisely the failure Q1 exists to catch. One run, one
  number, and that number is the paper's blind figure.
- **Prerequisite**: Steps 1, 2 and 3 complete and committed. **Do not start this
  step early under schedule pressure.**
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Publication Plan (7/9) Complete: spent the
  sealed holdout once and recorded the blind figure.*

---

### Step 8 — Write the paper

- **Locations**: `docs/research/paper/OUTLINE.md` §1–§11,
  `docs/research/paper/sections/` (§9 already drafted; §2 from Step 6; the rest
  new), `docs/research/figures/`, `docs/research/tables/`.
- **Rationale**: the record is unusually complete and the prose is almost
  entirely unwritten — one section of eleven exists. Lead with the amended C-023
  (vocabulary, not schema), because it is the strongest and most general result
  and it no longer needs a schema we built ourselves.
- **The outline's four rules bind here**: every number cites an `EXP-` ID; every
  claim appears in `CLAIMS.md` with its status and a `refuted` claim is not
  argued around; every figure is generated by a committed script and regenerates
  under `--check`; every model-dependent number states model, quantisation and
  date, **never the relay alias**.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Publication Plan (8/9) Complete: drafted every
  paper section against the record.*

---

### Step 9 — Artifact, archival identity, and submission mechanics

- **Locations**: `docs/research/paper/ARTIFACT_APPENDIX.md`,
  `docs/research/paper/venue-targets.md` (replace, do not revisit — its own
  banner says so), `docs/research/paper/checklists/`,
  `docs/research/datasets/DATASETS.md`.
- **Rationale**: four items, all cheap and all currently blocking a badge or a
  date. **(a)** Deposit a DOI (Zenodo) — GitHub alone does not satisfy the
  *Available* badge, and this is 0.1 wk with no risk. **(b)** Replace
  `venue-targets.md` and import `~/Downloads/ariadne-venue-report.md`; re-verify
  every deadline against the actual call. **(c)** Complete the target venue's
  reproducibility checklist — every field it asks for is already a `manifest.yaml`
  field by design. **(d)** State the data split wherever identity results are
  quoted: the MITRE half is clean and licensed; the identity and tri-source
  halves are not redistributable.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Publication Plan (9/9) Complete: deposited the
  artifact DOI, refreshed the venue record, and completed the submission
  checklist.*

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Empty-query repair | The fix for the 131-case `query_built_returned_no_rows` defect | `utils/specialists/`, `data/source_cards/overlays/` |
| Two-arm anomaly triage | `anomaly_triage.py` extended to score the `generic` arm, not only `deterministic` | `scripts/anomaly_triage.py` |
| Repair regression test | Runs the deterministic arm over a small subset of **both** committed banks and diffs answers excluding clock keys | `utils/specialists/evalset/tests/test_recorded_answers.py` |
| Property-read unit test | Pins Group / Tactic / View property reads at non-zero recall against a fixture, so the defect cannot silently return | `utils/specialists/tests/test_property_reads.py` |
| EXP-2026-09-003 | The post-repair headline re-measurement, full record | `docs/research/experiments/EXP-2026-09-003-*/` |
| Budget-resolution fix + test | The builder reads `.env`; the default is adequate for a reasoning model | `utils/specialists/`, `utils/specialists/tests/test_builder_budget.py` |
| Cross-model re-grade | X2 executed against the saved August answers | `docs/research/experiments/EXP-2026-09-004-*/` |
| Gold-query validator | Executes an emitted query and asserts it reproduces raw-file gold — **built before the emitter** | `utils/specialists/evalset/gold_query_validator.py` + tests |
| Gold-query emitter (conditional on Q26) | Census-path → executable Cypher/Gremlin, in a shape neutral between arms | `utils/specialists/evalset/` |
| Related-work section | Prose stating the delta against the 20 ranked works | `docs/research/paper/sections/02-related-work.md` |
| Positioning gap closure | Q25's five gaps, each traced to a retrieved document | `docs/research/RELATED_WORK.md` |
| Blind holdout result | The 288 sealed questions, spent once | `docs/research/experiments/EXP-2026-09-005-*/` |
| Paper draft | §1–§11 against `OUTLINE.md` | `docs/research/paper/sections/` |
| Artifact appendix + DOI | Zenodo deposit and the ~2-page appendix assembled from manifests | `docs/research/paper/ARTIFACT_APPENDIX.md` |
| Replacement venue record | Current deadlines, verified against the calls | `docs/research/paper/venue-targets.md` |

---

## 5. Goals to be met by the end

The plan is complete when **all** of the following hold. These are the
acceptance criteria; a step that leaves one unmet is not finished.

**On the record**

1. `make validate-research` passes, and **no number quoted in the paper exists
   outside an experiment folder.** Every figure regenerates under `--check`.
2. The C-023 headline is a **post-repair** figure, measured on both arms after
   the empty-query defect is fixed, with the pre-repair number retained as
   history rather than deleted.
3. No claim in `CLAIMS.md` that the paper argues is `unsupported` or `refuted`.
4. Every model-dependent number states model, quantisation and date. The string
   `skynet` appears nowhere as a model identity.

**On the science**

5. The empty-query defect is fixed, covered by a regression test, and the
   three zero-scoring node types (Group, Tactic, View) score non-zero.
6. `llm_query` is either re-measured at an adequate budget or explicitly cut,
   and **0.3712 is quoted nowhere as a baseline**.
7. The August headline comparisons are graded by a model that can be named.
8. The 288-question holdout has been spent exactly **once**, after all repairs,
   and its number is the paper's blind figure.
9. Q26 is decided either way, in writing, with the circularity argument
   addressed rather than waved through.

**On publishability**

10. **Novelty defensibility reaches 3** on the audit's scorecard — the one axis
    that currently blocks an applied conference — evidenced by a written
    related-work section and the five Q25 gaps closed.
11. A venue is selected against a **re-verified** deadline, and its
    reproducibility checklist is complete.
12. An archival DOI exists, and the non-redistributable data split is stated
    wherever those results appear.

**The one-line end state**

> Every claim the paper makes is traceable to a hashed artifact produced by a
> recorded run on a system with no known open defect in the path being measured,
> graded by a model that can be named, on questions that were sealed until they
> were answered.

---

## 6. What this plan deliberately does not do

- **It does not chase top-tier archival.** Five axes short, 20–30 weeks, and the
  audit is explicit that novelty defensibility at 2/4 *"is not closable by any
  amount of work on this codebase."* X6 (contamination control), X8 (seeds and
  repeats), X9 (an external *system* baseline) and a second domain result are all
  out of scope here and stay open in the record.
- **It does not act on the direction finding.** Now known to matter, and to
  matter differently per edge. It is a design decision, reported as a result and
  left alone.
- **It does not resolve the 29 open questions.** Most gate nothing this plan
  needs. They stay in `OPEN_QUESTIONS.md` as the future-work section.
- **It does not schedule the October ReliaQuest pitch.** That is the grant's
  contractual deliverable, it consumes the same weeks, and the two roadmap rows
  in `docs/goals.md` remain open. **This plan assumes a decision has been made
  about which comes first, and does not make it.**
- **It does not push to a remote.** Every step commits locally; pushing is the
  operator's call.
