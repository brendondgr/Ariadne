# Phase 2 — the top-tier programme

**Written 2026-09-06.** A sequenced plan for the work that would put this project
in front of a top-tier programme committee.

Companion to [`paper/venue-readiness-2026-09.md`](paper/venue-readiness-2026-09.md),
which assessed what the record supports today and concluded: journal now, top tier
not this cycle. This file answers the next question — **what would change that**.

---

## What this is not

**This does not replace or reorder anything currently running or already queued.**
The live queue stands exactly as it is:

| Live work | Status | Owner of the decision |
|---|---|---|
| Semantic Web Journal submission, target 2–3 months | The current path | `paper/checklists/conference-full-paper.md` §6 |
| `Q30`–`Q34` record repairs (calibration write-up, holdout reconciliation, the false CI claim, retracted figures, `n_runs`) | Paperwork, one week | `OPEN_QUESTIONS.md` |
| Ten of eleven paper sections | Weeks 2–7 of the journal path | `paper/OUTLINE.md` |
| Any experiment already scaffolded and pre-registered | Runs to completion | its own `PROTOCOL.md` |

Nothing below competes for those weeks. **Step 0 is the only part that overlaps**,
and it overlaps deliberately, because all three of its items are already owed to the
journal paper and are cheap.

Everything from Phase A onward assumes the journal submission is out the door.

---

## The idea the whole programme rests on

The system's one unrepeatable property is that **no language model writes a query on
any shipped path**. Treat that as a control condition rather than an architectural
virtue. Every text-to-query, GraphRAG and KGQA system in the literature has a
stochastic query-writing step between the variable under test and the score. This
one does not, which makes it an *instrument* — and instruments reach top venues when
they answer questions the field cannot otherwise answer.

The second principle, which does more work than any single experiment:

> **Choose the study whose ground truth is constructed rather than judged.**
> Non-existence, graph isomorphism and deleted-record counts are all ground truth by
> construction. Every study below is built that way, which is why none of them
> depends on the human annotators `Q6` closed as unavailable.

---

## Programme at a glance

| Step | Slug | Question it answers | Cost | Gate |
|---|---|---|---|---|
| 0.1 | `llm-query-seeded-repeats` | Does the query-writing arm's result survive three seeded runs? | Days | Owed anyway |
| 0.2 | `graph-snapshot-freeze` | Which exact graph state is every cross-system number measured against? | 1 day | Blocks all of B, C |
| 0.3 | `external-bank-ingest` | What do we score on questions nobody here wrote? | 1 week | Blocks B3, C7 |
| 1 | `synthetic-entity-generator` | Can we mint schema-plausible entities with no referent? | 2 weeks | **Blocks Phase B entirely** |
| A1 | `judge-corruption-ladder` | What is the smallest true quality difference each judge can resolve? | 2 weeks | — |
| A2 | `judge-inversion-map` | Where does a judge reverse the true ordering? | 2 weeks | — |
| A3 | `published-gap-audit` | How many published KGQA gaps sit below their own judge's resolution? | 3 weeks | Needs A1 |
| B1 | `false-premise-bank` | A probe set of entities that do not exist | 1 week | Needs 1 |
| B2 | `false-premise-arms` | Do our three arms fabricate on absent premises? | 1 week | Needs B1 |
| B3 | `false-premise-external` | Do published systems fabricate, with citations? | 4–6 weeks | Needs B1, 0.2 |
| B4 | `absence-witness` | Can a constructed query prove non-existence, checkably? | 2 weeks | Needs B2 |
| B5 | `isomorphic-twin-build` | A structurally identical graph with no memorable names | 2 weeks | Needs 1 |
| B6 | `twin-contamination-arms` | How much of our accuracy is recall rather than retrieval? | 2 weeks | Needs B5 |
| B7 | `twin-contamination-external` | Same question, other people's systems | 3 weeks | Needs B5, B3 |
| C1 | `federation-staleness` | What does merging cost when a source changes? | 2 weeks | — |
| C2 | `federation-leakage-adversarial` | Can a probe force a cross-source leak? | 3 weeks | — |
| C3 | `licence-restricted-source` | Is there a source the merged baseline cannot legally hold? | 2 weeks | — |
| C4–C6 | `second-domain-*` | Does any of this hold outside cybersecurity? | 10–14 weeks | — |
| C7 | `foreign-authored-templates` | Does the result survive templates we did not write? | 3 weeks | Needs C4 |

Total, if everything runs: six to nine months, plus one collaborator who can stand up
other people's systems. **Nothing here requires a human annotator.**

---

## Step 0 — three cheap moves, start them now

These three overlap the journal path on purpose. All three are already owed.

### 0.1 Three seeded runs of the query-writing arm

`Q34(c)` already names this. It is blocking at every tier above workshop and it is
days of machine time.

```bash
make new-experiment SLUG=llm-query-seeded-repeats
```

Pre-register in `PROTOCOL.md` before running:

- **H1** the ordering `generic > deterministic > llm_query` holds in all three runs.
- **H2** the across-seed standard deviation on `llm_query` is below 0.03.
- **H3** `deterministic − llm_query` stays positive in all three runs under both grader families.
- **Falsifies H3:** any run in which the sign flips. That outcome is *publishable and
  more interesting than the alternative* — it would mean C-012 was never established.

Record the seeds. `seeds: []` is the field that made this necessary in the first place.

### 0.2 Freeze and hash the graph snapshot

Before any number is measured against another system, pin the graph state.

A June 2026 paper found that rank order across four grounded systems did not survive
re-deriving the grounding graph ten weeks later. You already seal question banks with
SHA-256 (`EXP-2026-09-007`). Extend the same discipline to the graph:

- one command that exports ATT&CK 19.0 and CAPEC 3.9 to a versioned dump;
- a SHA-256 over each dump, recorded in `data/POINTERS.md`;
- every Phase B and C manifest carries the snapshot hash in `data.version`.

File as **`D-031` — every cross-system comparison names a graph snapshot hash.**

### 0.3 Ingest the external question sets

`RELATED_WORK.md` already records two resources the project is not using:

- **TITAN** (arXiv:2510.14670) — 88,209 natural-language-to-path pairs over an ATT&CK
  graph, authored elsewhere. The scoop watch note reads "never say no ATT&CK question
  resource exists." This closes the externally-authored-questions objection and the
  co-authorship-bias objection in one move.
- **CTIConnect** (KDD 2026, DOI 10.1145/3770855.3817527) — a live leaderboard, i.e. a
  published external number on a comparable task, obtainable without running anyone's
  code. The scoop watch note reads "engage or be asked why not."

```bash
make new-experiment SLUG=external-bank-ingest
```

Report our arms on a TITAN sample beside the leaderboard figure. Expect to score
worse. **Report it anyway** — an honest external number is worth more than an
internal ablation, and it is the first thing an A-tier reviewer looks for.

---

## Step 1 — the one piece of shared infrastructure

**Build this once. Phase B is two papers off the back of it.**

A generator that mints entities which are *schema-plausible and have no referent*:
correct identifier morphology (`T1234.567`, `CAPEC-999`), correct naming style,
plausible tactic or category association, and — verifiably — no node in either graph.

```bash
make new-experiment SLUG=synthetic-entity-generator
```

The generator drives two different constructions:

| Use | Construction | Serves |
|---|---|---|
| **Absent entities** | New identifiers with no node behind them | B1, B2, B3, B4 |
| **Isomorphic twin** | Every real node renamed, structure byte-identical | B5, B6, B7 |

Requirements worth pre-registering, because they are what a reviewer will attack:

1. **Absence is verified, not assumed.** Every minted identifier is checked against both stores and against the raw upstream distributions.
2. **Plausibility is measured, not asserted.** Hold out a sample of *real* identifiers, mix them with minted ones, and confirm a human or a held-out model cannot separate them above chance. If minted entities are obviously fake, the fabrication result means nothing.
3. **The twin is provably isomorphic.** Node and edge counts, degree distribution and shape census identical to the original. Your existing schema census (`EXP-2026-09-001`, 34 shapes) is the check.
4. **The twin's names carry no signal.** Not `T1234` to `T5678`, which a model may still pattern-match — new morphology entirely.

**Kill gate:** if requirement 2 fails and minted entities are separable from real ones,
Phase B's fabrication result is confounded and B3 must not run until it is fixed.

---

## Phase A — do this first, because the window is closing

Play 3. Small, needs no new system, and someone else is walking toward it.

**Novelty position, as of 2026-09-06.** *LLM Judges Have Dark Current*
(arXiv:2606.15610, June 2026) already took the "judge as measurement instrument"
framing and built a controlled quality ladder. What it left open: only three
open-weight judges, a coarse three-point ladder, no continuous dose-response curve,
**no inversion region**, and no grounded-QA constructions. JudgeArena
(arXiv:2608.02620) is the tooling someone will use to finish the job.

**Re-read the scoop watch before starting. If the inversion region has been taken,
stop and skip to Phase B.**

### A1 — `judge-corruption-ladder`

Constructed quality deltas, no annotator required. From a set of known-good answers,
produce a ladder by controlled damage:

| Axis | Construction | True Δ |
|---|---|---|
| Evidence deletion | drop *k* of *n* gold records | known exactly |
| Entity substitution | swap one entity for a graph sibling | known exactly |
| Citation stripping | remove provenance, keep prose | known exactly |
| Hedge injection | weaken assertions, keep content | known exactly |

Measure, per judge, the smallest Δ it can resolve — a discrimination threshold, in the
psychophysics sense. Ten or more judges, open and hosted.

- **H1** every judge has a resolution floor above zero.
- **H2** the floor rises as answer quality approaches the ceiling.
- **Falsifies:** a judge with a flat, low floor across all bands. That judge becomes the reference instrument and the paper narrows.

### A2 — `judge-inversion-map`

The part nobody has done, and **you already hold the only instance I could find**:
`gemma-4-26B-it` scored the low band at 0.6435 against the mid band at 0.6239, when
the true ordering is mid above low — inside the 0.40–0.65 range where all three of
your arms sit (`EXP-2026-09-008/data/state-gemma26.json`).

A judge that adds noise is survivable. A judge that *reverses* the ordering is a
different failure, and it is invisible to the correlation statistics everyone reports.

Map, per judge, the quality bands in which ordering reverses. Report inversion rate,
not correlation.

### A3 — `published-gap-audit`

The one with teeth. Take a named set of published KGQA and RAG comparisons, re-grade
each with **its own paper's stated judge**, and report how many headline gaps fall
below that judge's measured resolution floor from A1.

Precedent one domain over: a June 2026 study found seven of ten multi-agent
architectures report effects below the noise floor.

- **Kill gate:** if fewer than about a fifth of audited gaps fall below resolution, the
  audit is not a paper — fold A1 and A2 into a methods section and move on.

---

## Phase B — the flagship

Plays 1 and 2, sharing Step 1's generator. This is the strongest shot.

### B1–B4: grounded citations do not verify the premise

**The claim.** Retrieval-grounded, citation-producing systems answer confidently
about entities that do not exist, returning genuinely retrieved and genuinely cited
records for a premise with no referent — and a system that *constructs* rather than
generates its query can emit a machine-checkable witness of absence instead.

**You already have the pilot** and are filing it as a limitation: four of thirty
non-existent-entity questions answered with up to 558 cited records
(`EXP-2026-08-020`).

**B1 `false-premise-bank`.** Roughly 500 absent entities from Step 1, questions
generated across all 34 census shapes so coverage is structural rather than
convenient. Seal with SHA-256 and pre-register before any system sees it.

**B2 `false-premise-arms`.** The three arms. Primary metric:
**confident-answer-with-citations rate on a premise with no referent.**

**B3 `false-premise-external`.** Four or five published systems with public code —
Microsoft GraphRAG, AgCyRAG (`github.com/sepses/multi-agents-cykg-rag`), EICopilot,
a frontier-model text-to-Cypher baseline, CTIConnect. This is the step that needs the
collaborator, and it is the step that satisfies A-tier items A10 and A11 outright.

**B4 `absence-witness`.** The differentiator. The deterministic and schema-derived
paths return the query and its empty result set as evidence. Abstention with a proof,
not a confidence threshold. Verify the witness mechanically: an independent checker
re-executes the emitted query against the sealed snapshot and confirms the empty
result.

- **H1** external systems fabricate with citations on at least 15% of absent-premise questions.
- **H2** the `llm_query` arm fabricates at a materially higher rate than the model-free arms.
- **H3** the witness verifies on 100% of declines. **Anything below 100% is a bug, not a result.**
- **Kill gate on H1:** if external systems fabricate below about 10%, this is not a field-wide finding. Pivot to the witness mechanism as a smaller, still-publishable systems contribution and do not overclaim.

**Related work to engage rather than avoid.** *Deceptive Grounding*
(arXiv:2607.09349, July 2026) found 8–87% attribution failure across 13 models in
clinical RAG, and its ablation explicitly says removing entity-specific evidence
shifts all failures to confabulation — that is the exact regime B1 constructs. It
validates the mechanism without occupying the KGQA setting. PhantomBench
(arXiv:2606.11105) covers non-existent entities for bare models with no retrieval.
Cite both early and position against them; do not let a reviewer find them first.

### B5–B7: a contamination number, not a contamination excuse

**The claim.** Original-minus-twin accuracy is a per-system contamination estimate.

**Why this is worth more than closing an objection.** It *explains your headline
result*. If the schema-derived path drops less on the twin than the query-writing path
does, you have a mechanism: schema-derived construction wins because it is not
reciting. That converts "our system does better" into "here is why, and it generalises
past our codebase." **This is the largest available upgrade to the claim you already
have.** ATT&CK is about as memorised as a taxonomy gets, which makes it the ideal
substrate rather than a liability.

- **H1** all systems lose accuracy on the twin.
- **H2** the loss is largest for `llm_query` and smallest for `generic`.
- **H3** retrieval-grounded external systems lose less than ungrounded baselines.
- **Falsifies H2, and this matters:** if `generic` drops as much as `llm_query`, the schema-derived advantage is *also* memorisation, and C-023 needs rewriting rather than defending. Pre-register that you will report it either way.

**Novelty position.** DynBench (KGSWC 2025) and Dynamic-KGQA rename entities as
benchmark *hygiene*; GRIT (arXiv:2608.27142) does isomorphism-preserving perturbation
as a *robustness* benchmark. Nobody reports the drop as a contamination measurement.
Take the number, not the fix.

---

## Phase C — what makes it generalise

Not papers on their own. They are what stop a reviewer saying "one system, one domain."

### C1 `federation-staleness`

Federation currently buys no accuracy. Make it buy something countable and
model-free: mutate a source, then measure **time-to-correct-answer**. Merging needs a
rebuild — time it. Federation is immediate. Nobody in KGQA measures freshness, and it
is a real operational axis that pairs with the 1,083-of-9,138 edit count you already
have (`EXP-2026-08-017`).

### C2 `federation-leakage-adversarial`

Probes engineered to induce cross-source contamination; target leak rate zero, with
the database privilege boundary as the enforcement point. The suite to beat is
Hamzić et al. (arXiv:2604.11419), 82.5% schema-evasion success, already in the scoop
watch.

### C3 `licence-restricted-source`

Federate a source that is genuinely licence-restricted, so the merged baseline
**cannot legally exist**. Today this is a motivation backed by synthetic identity
records, and `EXP-2026-08-017` correctly refuses to claim it. Make it a fact with a
licence attached, and the claim becomes writable.

### C4–C6 `second-domain-*`

Nothing here is a law about query construction until it replicates where you wrote no
templates. Biomedical (Hetionet plus ChEMBL or UniProt) and bibliographic (OpenAlex)
each give two engines and two query languages.

**C6 is the sharpest and I have not seen it run: the same content in two different
schemas.** That separates schema difficulty from content difficulty — a control the
entire text-to-query literature lacks.

### C7 `foreign-authored-templates`

Have someone outside the project write the templates for the new domain. This kills
the co-authorship objection on the arm where it bites hardest, and it is the only
clean test of whether `deterministic` was ever a fair comparator.

---

## Phase D — assembly

1. **Pick the venue from the shape of the result, not the calendar.** B1–B4 plus B5–B7 is a resources-and-evaluation paper. A1–A3 is an evaluation-methodology paper. C alone is not a paper.
2. **Re-run the readiness scoring** in `paper/venue-readiness-2026-09.md` against the same tier checklists. The A-tier items that were UNMET — A5, A8, A10, A14 — should now read differently. **A8 stays unmet**: none of this produces a human anchor. What changes is that the flagship claims no longer need one, because their ground truth is constructed.
3. **Mint the DOI.** `Q30`–`Q34` and `ARTIFACT_APPENDIX.md` blockers should be long closed by then; if the copyright sign-off is still open it will have been open for months, which is its own answer.
4. **Re-read the scoop watch.** Every phase gate above says this. It is the single cheapest insurance in the programme.

---

## Ledger entries to reserve when you commit

Following the house conventions in `AGENT_INSTRUCTIONS.md` §5 — do not file these
until the work is actually scheduled, and do not renumber anything existing.

| Kind | Next free | For |
|---|---|---|
| Decision | `D-031` | Every cross-system comparison names a graph snapshot hash (Step 0.2) |
| Decision | `D-032` | Phase 2 targets constructed ground truth; human grading stays closed per `Q6` |
| Claim | `C-026` | Grounded citation does not verify the premise |
| Claim | `C-027` | Constructed queries admit a checkable witness of absence |
| Claim | `C-028` | Original-minus-twin accuracy estimates contamination |
| Claim | `C-029` | Judges invert ordering within measurable quality bands |

Every experiment above follows the standing contract: `make new-experiment SLUG=…`,
`PROTOCOL.md` written and hypotheses pre-registered **before** the run, `RESULTS.md`
after, then `make validate-research && make index`.

---

## What kills each play

Stated up front so a dead play is abandoned early rather than defended late.

| Play | Killed by | Detected at |
|---|---|---|
| A — judge resolution | Someone publishes the inversion region first | Scoop watch re-read, before A2 |
| A — the audit | Fewer than ~20% of published gaps fall below resolution | A3 gate |
| B — fabrication | External systems fabricate below ~10% | B3 gate |
| B — twin | Minted entities are separable from real ones | Step 1, requirement 2 |
| B — twin | `generic` drops as much as `llm_query` | B6 H2 — and this rewrites C-023 |
| C — federation | Staleness advantage is under a minute | C1 |
| C — licence | No genuinely restricted source can be obtained | C3, week 1 |
| All | The seeded runs flip the sign of C-012 | Step 0.1 — **run this first** |

---

## The honest summary

Six to nine months and one collaborator buys a submission that does not depend on a
human annotator, does not depend on beating anyone on accuracy, and carries a result
the field will not enjoy reading. That last property is what a top-tier acceptance
actually rewards.

The alternative — polishing the accuracy table — is unwinnable at that tier without
external baselines and repeated runs, and uninteresting even if won.

*Sequenced from the venue readiness assessment of 2026-09-06 and a novelty sweep run
the same day. Every novelty position above has a date on it and will decay; re-verify
before committing a phase.*
