# Branch A — Publication & Pitch Readiness (Public Data Only) — Plan

**Horizon:** 4 August – 23 October 2026 (end of the funded project period)
**Constraint:** no third-party or partner-supplied data is assumed. Every item
below is executable with MITRE ATT&CK, MITRE CAPEC, MITRE CWE and NVD/CVE — all
public and redistributable.
**Audit baseline:** `docs/research/audit-2026-08-03.md` — readiness L3, mean
1.875 / 4 across eight axes, one axis at zero.
**Target:** every axis at 3 or above, mean 3.50, with one axis (novelty
defensibility) honestly capped at 3.

---

## 1. Introduction

The 3 August audit scored this repository 1.875 / 4 and called the publishable
asset "not the system — the seven-arm controlled experiment already sitting in
the repository." That is correct but incomplete. Three things have changed or
been discovered since it was written, and together they change what this project
should claim.

**First, the strongest result in the project is sitting outside version
control.** `docs/evaluation/experiments/untruncated-generic/` contains a fully
executed, independently judged 120-case arm — Arm G, the
`SPECIALIST_GENERIC_ONLY` control that disables every hand-written MITRE
template — scoring **0.6388** (recomputed from the 120 judgment files: 64
correct / 14 partial / 42 incorrect) against Arm F's 0.9957. That is a
**−0.357** effect, three times the size of the −0.1185 LLM-planning penalty the
entire report is built around. It appears nowhere under `docs/evaluation/`. It
surfaces only in `docs/pitch/checkin-pitch.md:196`, which is itself untracked,
and which flags the run as "summary not yet committed."

The audit cannot be faulted for missing it: `git status` still shows
`untruncated-generic/` as untracked and the `SPECIALIST_GENERIC_ONLY` changes to
`utils/specialists/cypher/builder.py`, `utils/specialists/gremlin/builder.py`
and `utils/evaluation/experiment_untruncated.py` as uncommitted. On tracked
`main`, Arm G does not exist. The documentation plan's instruction "do not
describe Arm G as a result" was correct under those conditions and remains
correct until the code path is committed — which is why committing it is the
first action in this plan, and why it must precede the freeze tag.

**Second, the scoop check resolves in the project's favour, but not for the
reason the audit gives.** AgCyRAG (Kurniawan et al., RAGE-KG @ ISWC 2025) is
closer to this architecture than "partially scoops" suggests: an LLM-generated
Cypher agent over a Neo4j log graph and a templated SPARQL agent over the SEPSES
CSKG in Virtuoso, orchestrated by LangGraph with a reflection loop. Two stores,
two query languages, one security-domain agentic loop, public repository. What
it does not have is a single quantitative number — three worked examples and no
evaluation. And its limitations section contains this, verbatim:

> "Analytic capabilities are constrained by the reliance on predefined Cypher
> and SPARQL queries exposed via MCP, which currently prevent LLM agents from
> executing arbitrary queries on the two graph data sources. While this
> restriction helps manage complexity and guide the analytic process —
> **significantly improving the quality of answers** — it also limits the
> ability to freely explore available knowledge."

A named prior system asserts this project's central claim as an aside, files it
under limitations, and never measures it. That is the opening. The contribution
is not the architecture; it is the measurement of an assertion someone else has
already put in print.

**Third, the claim as currently stated is too weak to survive review, and the
fix is a scope extension the proposal already authorises.** "Templates beat LLM
query planning" is a null result in a family that already exists (Bast &
Haussmann CIKM 2015; Zheng et al. PVLDB 2018), and it is vulnerable to the
obvious objection that the templates were authored alongside the questions that
exercise them. It also rests on a thin foundation: only 177 of 558 live CAPEC
patterns carry any ATT&CK mapping, giving the federation 271 mapping edges, of
which 256 resolve to a live ATT&CK object.

The defensible version is a **boundary claim**: the template advantage is a
function of the structural regularity of the source, and it can be located. On a
closed, curated, ID-bearing catalogue like ATT&CK or CAPEC, a validated template
library dominates free-form generation. On a less regular source it should
degrade, and the crossover — how many templates a source needs before routing
overtakes generation — is measurable. That claim is novel, actionable,
falsifiable, and it converts the project's biggest weakness (a hand-picked,
richly-mapped question set over a thin join surface) into the experimental
variable.

It also stays inside the funded scope. The proposal's Project Summary promises
"guidelines for migrating the same agent framework to other query languages,"
and §4 Future Development commits to "add vulnerability feeds, strengthen
security-specific schemas." Adding a scoped NVD/CVE slice, bridged through CWE
into CAPEC, delivers both — not a deviation from them. A third source with a
different data model is also the only way the phrase "different query languages"
becomes defensible to a database audience, for whom Cypher and Gremlin are two
dialects over one data model rather than genuine heterogeneity.

This plan sequences the work to raise all eight axes into the 3–4 range by
23 October, gated on a single early experiment that determines whether the
headline number is real.

---

## 2. Gaps & Unanswered Questions

- **Is 0.9972 a capability or a coverage artifact?** *Unresolved, and this plan
  is gated on it.* All 120 evaluation questions were authored alongside the
  templates that answer them, with anchors hand-picked for mapping richness.
  `utils/specialists/evalset/federated_questions.py:58-60` says so outright:
  "CWEs whose bridged patterns carry ATTACK-taxonomy mappings — **many famous web
  CWEs bridge only to unmapped patterns and would be empty chains**." Step 4
  settles it. If blind correctness falls below ~0.85, Steps 6 and 7 are
  re-scoped (see §6).

- **Who authors the blind holdout questions?** *Resolved: an LLM (Claude Fable),
  under the mechanical protocol in Step 4.* This controls the actual threat,
  which is **co-authorship bias** — questions shaped by knowledge of which
  templates exist. A model given no access to `utils/specialists/` cannot have
  that knowledge. It introduces one new risk in exchange: a model left to choose
  its own anchors will gravitate to famous, richly-connected entities (T1003,
  T1055, Mimikatz), which is the exact sampling bias the holdout exists to
  remove. **Anchor selection must therefore be mechanical and seeded, never
  delegated to the model.** A secondary benefit: unlike a human-authored holdout,
  a seeded prompt-and-anchor-list protocol is itself reproducible, and the
  generation prompt ships with the artifact.

- **What model is `skynet`?** *Substantially resolved: **Gemma 4 31B**.* Still
  outstanding are the quantisation and the exact context window — the tree
  records the window three inconsistent ways: "unknown from the client side"
  (`docs/plans/answer-truncation-fix-plan.md:51`), "~64k"
  (`docs/evaluation/2026-07-26/README.md:301`), and `48000` (`.env:139,159`).
  With base model and parameter count known, a third party can approximately
  reproduce the LLM path for the first time, which lifts Reproducibility's
  ceiling from 3 to 4 once the remaining two fields are recorded.

- **What license?** *Unresolved, blocking, and not the RA's decision — see
  Step 1b.* Note that it is separable from MITRE attribution: the NOTICE file can
  and should be written now, since ATT&CK and CAPEC attribution requirements are
  independent of whatever license the project itself carries.

- **Where is the demo hosted?** *Resolved: a subdomain of the RA's personal site,
  `ariadne.brendondgr.com`.* Three consequences are handled in Step 8 — the
  deployment must include the Neo4j and Gremlin backends and not just the
  application; the LLM path needs an explicit serve-or-omit decision; and a
  personally-identifying URL is fine for EACL System Demonstrations
  (single-blind) but breaks anonymity for the EACL Industry Track (double-blind)
  and for ARTMAN (anonymous, desk-reject otherwise).

- **Does the merged-graph control belong in this plan?** *Resolved: yes, but its
  purpose is inverted from the audit's framing.* It is not run to show federation
  wins on correctness — it should tie, and a tie is the good outcome. It is run
  to establish that federation costs nothing in correctness while preserving
  per-source provenance, avoiding ETL staleness and requiring no schema
  reconciliation. Without it, "federation preserves provenance" is a design
  assertion. It is also the only answer to the published merged-Neo4j approach
  (*ATT&CK to CVE: A Large-Scale Automated Knowledge Graph for Threat
  Intelligence*, IEEE), which a reviewer will otherwise raise unprompted.

- **How much NVD?** *Assumption:* not all of it. Only the CVE slice reachable
  from the 336 CWEs that already bridge into CAPEC (`gold_bank.json`
  `capec.cwe_to_capec`). Bounded, ingestible in days rather than weeks, widens
  the join surface substantially, and keeps the federated question class inside a
  domain the existing gold machinery can compute over.

- **Which store for NVD?** *Assumption:* a relational or document store, not a
  third property graph. A third property graph teaches nothing new; the point is
  to make the heterogeneity claim true at the level of data model, not dialect.
  Final choice deferred to Step 7, driven by whichever connector is cheapest to
  validate.

- **How many templates are there, actually?** *Unresolved in the repository
  itself, and Step 3 must fix it.* The tree gives four different answers:
  `README.md:39` says 16 Cypher + 11 Gremlin (27); `README.md:186` and
  `docs/evaluation/2026-07-26/portability.md:72` say "24 total";
  `docs/research/audit-2026-08-03.md:30` says 17 + 11 (28);
  `utils/specialists/cypher/builder.py:128` says "The fifteen intent templates"
  and names two that no longer exist. Ground truth: **25 distinct template
  identifiers** across the two builders (26 methods, of which `_node_lookup` and
  `_capec_lookup` are dead and `_generic_neighbors` is reachable only under
  `SPECIALIST_GENERIC_ONLY`), of which the 120-question bank exercises **19**.

- **Does the total fit in the remaining time?** *Yes, with thin slack.* 4 August
  to 23 October is 59 Mon–Fri days, 58 net of Labor Day (7 September). The RA
  steps below sum to 48 days, leaving roughly 10 — about one day in six, which a
  single failed experiment consumes. Step 7 is the designated release valve.

- **Is CTIArena a threat?** *Resolved: no, but it changes the venue strategy.*
  It contains zero occurrences of Cypher, Gremlin, SPARQL, Neo4j, "federat",
  "provenance" or "abstention"; its structured tasks regex the identifier out of
  the question and paste the official record into the prompt. No overlap. But a
  resource-track benchmark contribution (the audit's Path 2) is now much harder
  to sell, and this plan drops it. CTIArena is used instead as motivation:
  closed-book CAPEC→ATT&CK accuracy maxes at 0.09 across ten frontier models,
  CWE→CAPEC at ≤0.01, attributed by its authors to "long-tail enumerated
  knowledge that is rarely absorbed during pretraining."

---

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Commit Arm G, attribute MITRE, freeze

- **Effort**: 1 day. **Week of 4 August. Unconditional — nothing else starts first.**
- **Locations**: the four uncommitted Arm G paths (`utils/specialists/cypher/builder.py`,
  `utils/specialists/gremlin/builder.py`, `utils/evaluation/experiment_untruncated.py`,
  `docs/evaluation/experiments/untruncated-generic/`); `docs/pitch/` (also
  untracked); `NOTICE` (new, repo root); `README.md`; git tag `freeze/holdout-v1`.
- **Rationale**: Ordering matters here and the obvious ordering is wrong. Tagging
  the current commit would freeze a tree containing no Arm G code path and no Arm
  G artifacts, making the strongest result in the project unreproducible against
  the very tag the holdout is run on. Commit first, then tag. Separately, there
  is no MITRE attribution notice anywhere in the tree despite the entire value
  proposition resting on ATT&CK and CAPEC — and that requirement is independent
  of whichever license the project eventually adopts, so it can be discharged
  now rather than waiting on Step 1b.
- **Action**: Commit the `SPECIALIST_GENERIC_ONLY` code path and the
  `untruncated-generic/` artifacts, and bring `docs/pitch/` under version
  control. Add a NOTICE reproducing the MITRE ATT&CK Terms of Use and the CAPEC
  attribution requirement, linked from the README. Tag `freeze/holdout-v1` and
  record the SHA in this plan.
  Commit: `Branch A (1/9) Complete: Committed the Arm G control, added MITRE attribution, and tagged the pre-holdout freeze.`

### Step 1b: Resolve the license — **open, blocking, PI-owned**

- **Effort**: half a day once decided. **Owner: PI / FSU. Raise in week 1.**
- **Locations**: `LICENSE` (repo root); `license` field in `pyproject.toml` and
  `web/package.json`; `README.md`.
- **Rationale**: Deliberately separated from Step 1 because it is not the RA's
  decision and cannot be unblocked by working harder. There is currently no
  LICENSE file and no `license` field anywhere, so the artifact cannot legally be
  released — and **every demo track requires a released artifact**. This one
  unresolved item blocks EACL System Demonstrations, IEEE Big Data Demo and
  SIGMOD Demo simultaneously. It is the cheapest blocking item in the plan.
- **Action**: Put the question to the PI in week 1, framed with the deadline
  (EACL Demos, 22 September) and the two realistic options: **Apache-2.0**, which
  carries an explicit patent grant and is the usual choice for a research
  artifact with industrial funding, or **MIT**, which is simpler and contains no
  patent language. Confirm whether the ReliaQuest Innovation Challenge Fund terms
  impose any constraint on release. Once decided, add the LICENSE and both
  metadata fields.
  Commit: `Branch A (1b/9) Complete: Repository license.`

### Step 2: Consolidate the judge into the repository and pin the model

- **Effort**: 3 days. **Week of 4–10 August. Prerequisite for every later experiment.**
- **Locations**: `scratchpad/judge_untruncated.mjs` → `utils/evaluation/independent_judge/`;
  existing `utils/evaluation/llm_judge/` and `utils/evaluation/harness/correctness_judge.py`;
  `pyproject.toml`; `docs/commands.md`; `docs/evaluation/README.md`; `.env.example`.
- **Rationale**: Every **arm-level correctness figure** in the seven-arm study
  was produced by an ES module in `scratchpad/`, written for an external workflow
  tool, relying on undeclared globals (`args`, `log`, `agent`, `parallel`), with
  no declared dependency and no test. (The four deterministic end-to-end metrics
  the README headlines — exact-set-match 30/30, mapping recall 113/113,
  provenance 120/120, inspectability 1.0 — do come from in-repo Python and are
  unaffected.) Running new experiments on that foundation compounds an
  unreproducible base, which is why this precedes the holdout.
- **Action**: Reimplement the judge as a first-class module with a pinned judge
  model identifier, an explicit seed and temperature record, a declared
  dependency, and a CLI invocation in `docs/commands.md`. The repository already
  has two judge paths — `llm_judge/` (faithfulness only, never sees gold) and
  `harness/correctness_judge.py` (gold-aware, grades the agentic path) — so
  **extend or supersede them rather than adding a third**, and document which
  judge grades what. Preserve the existing JSON schema exactly so historical
  judgments stay comparable. Re-judge one completed arm and record the agreement
  rate against the original verdicts; poor agreement is itself a finding and must
  be reported.
  **Record the model identity in `docs/evaluation/README.md`: `skynet` is
  Gemma 4 31B.** Capture the two outstanding fields at the same time — the
  quantisation, and the exact context window, currently reported three
  inconsistent ways. With all three recorded the LLM path becomes approximately
  reproducible by a third party for the first time.
  While in `.env.example`, close two divergences it has from `.env`:
  `ORCH_MAX_HOPS` is absent from the example entirely (so a fresh clone runs at
  the code default of 5, loop on, while the evaluation record describes a pinned
  single pass), and `EVAL_LLM_MAX_TOKENS` reads 1024 against `.env`'s 32000.
  Commit: `Branch A (2/9) Complete: Consolidated the independent judge, pinned the model to Gemma 4 31B, and closed the .env.example divergences.`

### Step 3: Write up Arm G and reconcile the numbers it touches

- **Effort**: 2 days. **Week of 11 August.**
- **Locations**: `docs/evaluation/2026-07-26/README.md:41` and `:217`;
  `docs/evaluation/experiments/README.md:18-24`;
  `docs/pitch/checkin-pitch.md:245`; `docs/research/audit-2026-08-03.md:296`
  and `:533`; `utils/evaluation/summarize_untruncated.py`; `README.md`.
- **Rationale**: Arm G is a fully executed, independently judged 120-case
  ablation reported nowhere under `docs/evaluation/`, and it is exactly the
  control that answers "what are the hand-written templates actually worth."
  Two days of writing moves Baseline coverage off 1/4 using evidence already paid
  for — the best effort-to-score ratio in this plan.
- **Action**: Add Arm G to both arm tables with its full metric row, and state
  the F − G delta (−0.357) alongside the B − C planning delta (−0.1185) so a
  reader can see the relative magnitudes. Fix three defects while in there.
  **(a)** The cost column splices pre-fix Arm A figures (2.6 s / 1,840 records)
  next to post-fix correctness; the post-fix run is **1.6 s / 1,061 records**
  (related neighbours 839 and coverage 1.0000 are identical across both, so only
  two figures move). The 2.6 s propagates to the five locations listed above, and
  the derived "392× wall-clock difference" becomes **637×** at 1.6 s. **(b)** Arm
  D has no code row in `docs/evaluation/experiments/README.md`; add it
  (`untruncated-claimnarr/gold_llm`, 0.9917). **(c)** Reconcile the template
  count across `README.md:39`, `README.md:186`, `portability.md:72`, the audit,
  and the `cypher/builder.py:128` docstring, to ground truth: 25 distinct
  identifiers, 19 exercised by the bank, 2 dead. Note explicitly that Arm G is a
  *generic-primitives* control, not free-form query generation, and that the
  free-form counterfactual arrives in Step 7.
  Commit: `Branch A (3/9) Complete: Reported Arm G, corrected the arm cost table, and reconciled the template count.`

### Step 4: The blind holdout — **the gate**

- **Effort**: 4 days. **13–21 August. Results by ~21 August.**
- **Locations**: new `utils/specialists/tests/golden/holdout_questions.json`;
  new `utils/specialists/evalset/holdout_protocol.py` (sampler + prompt +
  recorded seed); output under `docs/evaluation/experiments/holdout-v1/`;
  write-up in `docs/evaluation/holdout-v1/README.md`.
- **Rationale**: The cheapest action that determines whether anything else is
  worth doing. If 0.9972 is a template-coverage artifact then the merged-graph
  control and the NVD extension are measuring the wrong thing and the framing
  changes entirely.
- **Action**: Questions are authored by an LLM (Claude Fable) under a strict
  four-stage protocol. Deviating from it collapses the holdout back into the
  problem it exists to solve.

  **(i) Sample the anchors mechanically, not with the model.** Draw anchors
  uniformly at random, with a recorded seed, from the live CAPEC pattern and
  ATT&CK technique id space — *including* the ~two thirds of CAPEC patterns that
  carry no ATT&CK mapping, and the sparse CWE bridges the current set excludes by
  design. This is the whole point. A model asked to invent its own anchors will
  reach for T1003, T1055 and Mimikatz, reproducing exactly the rich-anchor bias
  the holdout is meant to break.

  **(ii) Give the model the anchors and the category scheme, and nothing else.**
  It must not see `utils/specialists/`, the existing question banks, the README's
  description of what the system does, or any template. Its job is narrow: write
  a natural-sounding analyst question about the anchor it was handed, in the
  style of the named category.

  **(iii) Compute gold with `gold_bank.py`, not with the model.** The existing
  machinery parses the raw STIX and CAPEC XML independently of the ingest, so the
  answer key stays independent of both the specialists and the question author.
  The model never proposes an answer.

  **(iv) Commit the protocol as an artifact.** Seed, sampled anchor list,
  generation prompt and model version. This is a real advantage over a
  human-authored holdout, which cannot be re-run: a reviewer can regenerate the
  entire question set and check it.

  Follow the split convention the repository already has —
  `utils/planner/evaluation/build_corpus.py:51` implements `HOLDOUT_EVERY = 4`
  with separate dev/holdout reporting — rather than inventing new mechanics; the
  three 120-question banks carry no `split` field at all, which is the gap being
  closed. Run Arms A and F only, against the frozen `freeze/holdout-v1` tag,
  judged with the Step 2 judge. Report blind correctness against the development
  figure with a Wilson interval on both, plus a per-category breakdown — the
  interesting failure is a uniform drop versus one concentrated in the categories
  whose anchors were richest. **Do not tune anything in response to the result.**

  **State the limitation plainly in the write-up.** An LLM-authored holdout
  controls co-authorship bias but does not control for the question distribution
  being a model's idea of what an analyst asks. Say so, and note that a
  human-authored set remains the stronger test if a person becomes available —
  a further 15–20 questions would be a cheap secondary check.
  Commit: `Branch A (4/9) Complete: Blind holdout on 30 externally-authored questions, Arms A and F.`

> **GATE.** Evaluate before proceeding. See §6 for the decision rule.

### Step 5: The related-work section

- **Effort**: 5 days. **24 August – 4 September, after the gate.**
- **Locations**: new `docs/research/related-work.md`; new `docs/research/refs.bib`.
- **Rationale**: Positioning scored **0/4** and this is the entirety of it. There
  is no related-work engagement anywhere in the project: `docs/references/` is
  implementation notes, and the only substantial scholarly material in the tree
  is the ~90-entry bibliography inside the audit document, which someone else
  wrote. (`docs/proposal/proposal.md` carries 12 references, two of them the PI's
  own papers.) No non-demo venue accepts a submission without this section, and
  0 → 3 for five days is the highest-yield item in the plan.
- **Action**: Four subsections. **(a) Federated query processing** — the mature
  line (FedBench, LargeRDFBench, FedShop, source selection, cost-based join
  planning), stating plainly which parts this system engages (source selection,
  partially, via token matching) and which it does not (cost estimation, join
  ordering — a fixed producer-then-consumer hoist). Claiming less than the field
  expects is what makes the rest credible. **(b) Text-to-graph-query** —
  Text2Cypher and the ~30–60% execution-accuracy range, 0.189 on an unseen
  production graph, ISO-GQL at ≤4% zero-shot, and the absence of any established
  text-to-Gremlin benchmark. **(c) Agentic KG retrieval in security** — AgCyRAG
  as the closest prior work, quoted honestly on what it does and on its
  unmeasured template assertion; CRAKEN, ARCeR, CyKG-RAG, SEPSES, the ATT&CK-KG.
  **(d) CTI benchmarking and the merged-graph alternative** — CTIArena's
  closed-book collapse on CAPEC→ATT&CK (≤0.09) and CWE→CAPEC (≤0.01) as the
  motivation that kills "just ask the model," and the merged-Neo4j ATT&CK-to-CVE
  work as the alternative Step 6 controls against. Build `refs.bib` as you go.
  Commit: `Branch A (5/9) Complete: Related-work section and bibliography.`

### Step 6: The merged-single-graph control

- **Effort**: 10 days. **10 September – 1 October.**
- **Locations**: `utils/graph_loader/` merged-mode loader;
  new arm in `utils/evaluation/experiment_untruncated.py`;
  `docs/evaluation/experiments/merged/`.
- **Rationale**: Federation is a design choice and a reviewer will ask what it
  cost. **The expected and desirable outcome is a tie on correctness.** The claim
  this licenses is: *federation matches merged-graph correctness on the same
  question set while preserving per-source provenance, avoiding ETL staleness and
  requiring no schema reconciliation.* That is defensible and measured.
  "Federation is more accurate" is neither.
- **Action**: Load both catalogues into a single Neo4j instance under one
  reconciled schema. Answer the same 120 development questions and the 30 holdout
  questions with equivalent templates. Report four things: correctness delta
  (expect ≈ 0); wall-clock delta (expect merged faster — say so); the
  **provenance granularity lost** in the merge, quantified as the number of
  evidence records that can no longer name a source engine, query and timestamp;
  and the **engineering cost of the merge itself** in schema-reconciliation
  decisions required. That last item is strongest stated as a count — in
  particular the **15 CAPEC MAPS_TO edges, spanning 10 distinct ATT&CK technique
  ids, that do not resolve to a live ATT&CK object**, plus the directionally
  inconsistent mappings. Note that the 15 is not readable from
  `utils/graph_loader/fixture_qa/expected/capec_attack_resolution.json`, which
  records only the 10 unresolved ids and `resolution_rate 0.9471` (= 179/189
  ids); the edge count must be recomputed from
  `data/graphs/capec/canonical/relationships.jsonl`.
  Commit: `Branch A (6/9) Complete: Merged-single-graph control and the provenance-cost accounting.`

### Step 7: The NVD/CWE third source and the template crossover curve

- **Effort**: 12 days. **2–21 October. First item cut if upstream slips.**
- **Locations**: `utils/download/` NVD fetcher; new store connector;
  `utils/specialists/<new>/`; `data/source_cards/`;
  `docs/evaluation/experiments/crossover/`.
- **Rationale**: This converts a contested null result into a finding. Three
  things follow at once. It makes "federated across different query languages"
  true at the level of data model rather than dialect. It supplies the
  **free-form generation baseline the audit says is missing** — on a source with
  no templates yet, LLM query generation is the only option, so the comparison
  becomes native rather than staged. And it widens the join surface beyond 271
  edges to something that can carry a research programme. It is also the direct
  delivery of the proposal's §4 commitment to "add vulnerability feeds."
- **Action**: Ingest the CVE slice reachable from the 336 CWEs that already
  bridge into CAPEC. Put it in a relational or document store, not a third
  property graph. Write a source card. Then run the crossover experiment: start
  with **zero** templates for the new source and measure LLM query generation
  correctness, then add templates in a fixed order — most-frequent intent first —
  re-measuring after each. Plot correctness against template count for the new
  source, and place ATT&CK and CAPEC on the same axes using Arm G as their
  zero-template point. The deliverable is one figure: *template advantage as a
  function of source regularity and authoring investment.* Report the crossover
  point, and report honestly if there isn't one. Record the NVD terms of use in
  the NOTICE while ingesting.
  Commit: `Branch A (7/9) Complete: NVD/CWE third source and the template crossover curve.`

### Step 8: Demo assets

- **Effort**: 3 days. **26–28 August, well ahead of the EACL Demos deadline of 22 September.**
- **Locations**: `ariadne.brendondgr.com`; `docker/docker-compose.yml`;
  screencast; `README.md` demo section.
- **Rationale**: EACL System Demonstrations requires both a live URL and a
  screencast; the project has neither, despite the audit listing them as assets
  in hand. IEEE Big Data and SIGMOD demo tracks want the same material. The web
  workbench in `web/` already *is* the demo — it needs deploying and filming, not
  building. Scheduled early because it is the one item tied to a hard external
  deadline that has no dependency on the gate.
- **Action**: Deploy to `ariadne.brendondgr.com` with read-only credentials and a
  rate limit. Three things to plan for:

  **The deployment is not just the app.** Neo4j and the Gremlin Server have to
  run alongside it, so size the host for both backends plus ~9,100 nodes and
  ~34,600 edges. `docker/docker-compose.yml` already defines the stack; its `web`
  service is currently `profiles: [disabled]` and needs enabling.

  **The LLM path needs an explicit decision** — either expose a reachable
  Gemma 4 31B endpoint, or ship the demo deterministic-only. The latter is
  defensible and arguably the better story given the findings, and it removes the
  demo's only unbounded cost.

  **The URL is personally identifying.** Fine for EACL System Demonstrations
  (single-blind); breaks anonymity for the EACL Industry Track (double-blind) and
  ARTMAN (anonymous, desk-reject otherwise). Any anonymous submission needs a
  neutral mirror or an anonymised screencast.

  Record a screencast walking one federated question end to end that **shows the
  inspector panes** — the executed Cypher, the executed Gremlin traversal, the
  join index, the per-claim provenance chips, and one abstention carrying its
  executed query as proof. The inspector is the differentiator; a demo that only
  shows the answer looks like every other chatbot.
  Commit: `Branch A (8/9) Complete: Hosted demo at ariadne.brendondgr.com and screencast.`

### Step 9: Assemble the submissions and the pitch

- **Effort**: 8 days, distributed — roughly 4 pulled forward to 14–18 September
  for the EACL submission, 4 in October for the pitch.
- **Locations**: `docs/pitch/`; paper drafts outside the repository where
  anonymity rules require.
- **Rationale**: One claim, stated the same way in every artifact. Claim clarity
  and Narrative both move here, and they only move if the project stops implying
  five claims it can support one and a half of.
- **Action**: Stake **one** headline claim — *the advantage of a validated
  query-template library over free-form LLM query generation is a function of
  source regularity, and we locate the boundary* — and subordinate C2 through C5
  to supporting results. Lead every artifact with the measurement, never with the
  architecture; leading with the architecture invites the AgCyRAG comparison on
  the worst possible terms. Targets in priority order: **EACL 2027 System
  Demonstrations (22 September)** as the primary academic submission, contingent
  on Step 1b; **ARTMAN @ ACSAC (31 August)** opportunistically and only if the
  gate passes cleanly — with results landing ~21 August this is very tight, it
  requires an anonymised demo URL, and it should be abandoned without regret;
  **SIGMOD 2027 Demo (15 January)** and **ESWC 2027 In-Use (≈10 December)** as
  follow-ons past the funded period. The **ReliaQuest October pitch** is the
  primary deliverable and takes the same spine: here is what we proposed, here is
  what we built, here is what we measured, here is the boundary we found, and
  here is what it predicts for a source like yours.
  Commit: `Branch A (9/9) Complete: Submission and pitch materials aligned on a single claim.`

---

## 4. Axis targets

| Axis | Now | Target | What moves it | Steps |
|---|---|---|---|---|
| Claim clarity | 3 | **4** | One staked claim, consistently stated; template count reconciled | 3, 9 |
| Novelty defensibility | 2 | **3** | Boundary claim + honest AgCyRAG positioning + crossover curve | 5, 7, 9 |
| Evaluation rigor | 2 | **4** | Blind holdout, consolidated judge, Arm G, crossover | 2, 3, 4, 7 |
| Baseline coverage | 1 | **3** | Arm G + merged control + zero-template condition on the new source | 3, 6, 7 |
| Data legitimacy | 3 | **4** | MITRE NOTICE, license, NVD terms recorded | 1, 1b, 7 |
| Reproducibility / artifact | 2 | **4** | Judge in-repo, model identified (Gemma 4 31B), `.env.example` fixed, seeded holdout protocol, hosted demo | 1, 2, 4, 8 |
| Positioning | **0** | **3** | The related-work section — the whole of it | 5 |
| Narrative | 2 | **3** | Follows from a single claim and a real results table | 3, 9 |
| **Mean** | **1.875** | **3.50** | | |

One honest caveat and two dependencies. **Novelty defensibility will not reach
4** while AgCyRAG exists — the architecture is genuinely close, and the correct
move is to concede that and compete on measurement rather than argue.
**Reproducibility targets 4** on the strength of the model being identified as
Gemma 4 31B, but only if the quantisation and context window are recorded too;
it falls back to 3 if they cannot be. **Data legitimacy is gated on Step 1b**,
which is not the RA's decision — without a license the axis stays at 3 and every
demo track stays closed.

---

## 5. Schedule

59 Mon–Fri days from 4 August to 23 October; 58 net of Labor Day (7 September).
48 days of RA work. ~10 days slack.

| Window | Working days | Work | Milestone |
|---|---|---|---|
| 4–10 Aug | 5 | Step 1 (1 d), Step 2 (3 d); **raise Step 1b with the PI** | freeze tag set |
| 11–14 Aug | 4 | Step 3 (2 d), Step 4 begins | — |
| 17–21 Aug | 5 | Step 4 completes (4 d total) | **GATE ~21 Aug** |
| 24 Aug – 4 Sep | 10 | Step 5 (5 d), Step 8 (3 d) | ARTMAN 31 Aug (opportunistic) |
| 8 Sep – 1 Oct | 17 | Step 6 (10 d), Step 9 first half (4 d) | **EACL Demos 22 Sep** |
| 2–21 Oct | 14 | Step 7 (12 d) | release valve |
| 19–23 Oct | 5 | Step 9 second half (4 d) | **ReliaQuest pitch** |

Step 8 sits early and off the critical path because it is the only item tied to
a hard external deadline that does not depend on the gate. Step 1b sits outside
the RA's day count and must be chased, not scheduled.

---

## 6. Decision rule at the Step 4 gate, and kill criteria

**If blind correctness ≥ 0.95** — the development figure holds. Proceed
unchanged. Strongest possible outcome, and the only one that makes ARTMAN on
31 August worth attempting.

**If blind correctness is 0.85–0.95** — expected, and fine. The drop is the
honest generalisation gap; report both numbers everywhere and never quote the
development figure alone again. Proceed unchanged.

**If blind correctness is 0.70–0.85** — the development set was optimistic but
the effect survives. Drop ARTMAN. Re-scope Step 7 to the reduced form: skip the
new store and run the crossover curve on ATT&CK and CAPEC alone, ablating
templates in a fixed order from the 19 the bank actually exercises down to zero,
using Arm G as the endpoint. Five days rather than twelve, still produces the
curve, but without the data-model heterogeneity argument.

**If blind correctness < 0.70** — the 120-question result is substantially a
coverage artifact and the paper changes. Do not proceed to Steps 6 and 7 as
written. The finding becomes *"a validated template library achieves
near-ceiling correctness on covered questions and degrades sharply off-coverage,
and here is the coverage boundary"* — legitimate, arguably more interesting, but
a different paper needing its own plan. Stop and re-plan rather than continuing
on momentum.

**Standing kill criteria, independent of the gate.**
- If the consolidated judge in Step 2 disagrees materially with the original
  verdicts, every downstream number is in question and that must be resolved
  before the holdout runs.
- If the Step 4 anchor sample is not verifiably uniform — if the seed, sampler
  and anchor list are not committed — the holdout does not count and must be
  re-run. A holdout whose sampling cannot be audited is worth nothing.

---

## 7. What this plan deliberately does not do

- **No benchmark/resource-track contribution.** The audit's Path 2 is dropped.
  CTIArena now occupies that ground, and a 150-question bank cannot compete with
  691 practitioner-reviewed QA pairs on resource-track terms.
- **No new system features.** The audit's judgement that "the marginal return on
  engineering has gone negative" is correct. Step 7 is the sole exception and it
  exists to serve a measurement, not to improve the tool.
- **No agentic-loop rehabilitation.** The assess/replan machinery stays as it is,
  documented accurately as an inert seam and not defended. Making it work is a
  feature, and features are what this plan is trying to stop doing. (Step 2 does
  fix the `.env.example` divergence, but that is a reproducibility correction,
  not a rehabilitation.)
- **No pursuit of top-tier security venues.** NDSS, IEEE S&P and USENIX are out
  of reach; chasing them costs weeks that Steps 5 and 6 need.

---

## 8. Relationship to the funded proposal

Every step delivers against a commitment already in the proposal, not around it.

| Proposal commitment | Delivered by |
|---|---|
| "Working demonstration that queries ATT&CK and CAPEC as distinct graph-database sources" | Already built; Step 8 makes it publicly demonstrable |
| "Evaluates routing, query translation, answer grounding, and provenance correctness" | Steps 3, 4, 6 — with the holdout supplying the rigor the proposal implies |
| "Documents guidelines for migrating the same agent framework to other query languages" | Step 7 — a third source in a different data model *is* the migration guide, demonstrated rather than asserted |
| §4: "add vulnerability feeds" | Step 7, NVD/CVE slice |
| "Preserving source provenance, query constraints, and auditability" | Step 6 quantifies exactly what a merge would destroy |
| Deliverable by October 2026 | Step 9, ReliaQuest pitch |

The one place this plan departs from the proposal's *framing* — not its scope —
is that the proposal describes source-specific agents that generate queries,
while the built system routes to validated templates and the measurement shows
that this is the better design for these sources. Present that as the project's
central finding, plainly and early: *we proposed an agentic federated layer,
built it, measured it, and found that the agentic components cost correctness on
this class of source — and here is where that stops being true.* Delivered that
way it is a result. Discovered by a reviewer, it is a gap.

---

## 9. Which steps can run unattended

Not all of them, and the distinction is not about difficulty. It is about
whether the work has a **mechanical success criterion** — something a script or
an agent can check without exercising judgement about what the project should
claim.

| Step | Unattended? | Why |
|---|---|---|
| 1 — Commit Arm G, NOTICE, freeze | **Mostly** | Committing and tagging are mechanical. The NOTICE text is fetchable from MITRE. Review the commit in the morning before it becomes the freeze point. |
| 1b — License | **No** | PI decision. |
| 2 — Judge consolidation | **Partly** | The port and the `.env.example` fixes are mechanical. Which existing judge to supersede is a design call, and the re-judge agreement check needs the Gemma endpoint up and a human reading the disagreements. |
| 3 — Arm G writeup + number reconciliation | **Yes — best candidate** | Every figure is recomputable from committed artifacts and every edit is verifiable against a file. Recompute means from the 120 judgment files, propagate 2.6 s → 1.6 s across five locations, recompute 392× → 637×, reconcile the template count by counting methods. Fully checkable. |
| 4 — Blind holdout | **Yes for the run, with a hard guardrail** | Sampling, generation, gold computation and the two arms all script cleanly. See the warning below. |
| 5 — Related work | **No** | This is the 0/4 axis, and the failure mode of unattended scholarly writing is fabricated citations. Filling Positioning with plausible-looking references that do not exist is strictly worse than leaving it empty. Draft assisted, verify every citation by hand. |
| 6 — Merged-graph control | **Partly** | Loading and running are automatable. The schema-reconciliation decisions — how to merge two overlapping ID spaces, what to do with the 15 unresolved MAPS_TO edges — are the substance of the result and must be made deliberately. |
| 7 — NVD + crossover | **Partly** | Ingestion and the sweep are automatable. Template authoring order and the choice of store are judgement. |
| 8 — Demo + screencast | **No** | DNS, credentials, and recording a video. |
| 9 — Pitch and submissions | **No** | The whole point is choosing what to claim. |

> **Hard guardrail on Step 4.** An unattended agent that encounters a failing
> holdout question and "fixes" the template has destroyed the experiment, and
> the destruction is silent — the result still looks like a number. Any
> overnight run of Step 4 must operate on a detached checkout of
> `freeze/holdout-v1` with write access to nothing under `utils/specialists/`,
> and must fail loudly rather than adapt. If the run cannot be constrained that
> way, run it attended. This is the one place in the plan where an autonomous
> convenience can invalidate the result it was meant to produce.

Two operational notes for any overnight run: Docker with Neo4j and the Gremlin
Server must be up (`logs/` shows 139 `graph-health` invocations, so this is a
recurring failure mode worth pre-checking), and every LLM arm needs the
Gemma 4 31B endpoint reachable for the duration — Arm F took 533 s across
120 questions, so a full merged-control sweep is a multi-hour job.
