# Research Decisions

ADR-style, dated, **append-only**. One entry per research decision: metric
choices, baseline selection, dataset exclusions, scope cuts, framing.

Reviewers ask "why did you use X?". This is where the honest answer already
lives, written at the time rather than reconstructed under pressure.

Add entries with [`templates/DECISION.md`](templates/DECISION.md). Never edit an
existing entry — supersede it with a new one that names the entry it replaces.

---

## D-001 — Primary metric is judge-scored correctness, not the four `goals.md` metrics

**Date:** 2026-07-26
**Context:** The project's stated end-to-end metrics — cross-source answer
accuracy, mapping recall, provenance correctness, analyst inspectability — all
read 1.0 while an independent panel scored the same answers at 0.8946
correctness with hallucinations in 11 of 120.
**Options:** (a) keep the four `goals.md` metrics as primary, since they are
deterministic and reproducible; (b) adopt judge-scored correctness as primary and
demote the four to secondary; (c) report both as co-primary.
**Decision:** (b). Judge-scored correctness is primary; the four `goals.md`
metrics are reported as secondary and explicitly labelled as what they are.
**Consequences:** The primary metric is now non-reproducible — it depends on an
LLM judge whose verdicts are not stable across runs. That cost is accepted
because three of the four alternatives are self-consistency checks that a
confidently wrong pipeline passes. Every reported correctness figure must name
its judge run. See C-009.

## D-002 — Evaluation is cross-model by construction

**Date:** 2026-07-26
**Context:** The first end-to-end evaluation had `skynet` grading answers
`skynet` wrote. Independent grading found faithfulness 0.956 against a
self-reported 0.973 — the self-preference bias the concern predicted.
**Options:** (a) keep self-judging, it is cheap and local; (b) grade with a
different model; (c) human annotation.
**Decision:** (b). One independent Sonnet 5 agent per answer, given the gold
assertions *and* the full retrieved evidence. 840 agents across the seven study
runs, plus 120 for the Arm G control.
**Consequences:** Expensive, and it introduces a dependency on a commercial model
in the evaluation path. It also means self-judged numbers already in the
repository cannot be compared with post-decision numbers. (c) remains
unaddressed — there is still no human-versus-judge agreement statistic, which a
reviewer will ask for. Tracked as Q6.

## D-003 — Both inter-arm deltas are reported treated-minus-reference

**Date:** 2026-08-04
**Context:** The study reports two effects — disabling templates, and swapping in
LLM planning — and they were being quoted with inconsistent signs and, in one
plan document, with the letters reversed ("F − G delta (−0.357)"; F − G is
*positive*).
**Options:** (a) report each delta in whatever direction reads naturally;
(b) fix a single convention.
**Decision:** (b). Treated minus reference, always, so both effects are negative
and directly comparable: templates **G − F = −0.3568**, planning
**B − C = −0.1185**.
**Consequences:** Some prose elsewhere in the repository still carries the old
labels and is now wrong on its face. Those documents are dated records and are
not edited in place; this entry is the correction of record.

## D-004 — Arm G is a generic-primitives control, not a free-form-generation baseline

**Date:** 2026-07-26
**Context:** Arm G disables every hand-written intent template, leaving only
schema-driven primitives. It is tempting to describe this as "the LLM writes the
queries instead", which would make it the baseline the paper's headline claim
needs.
**Options:** (a) describe Arm G as a text-to-query baseline; (b) describe it
precisely as a generic-primitives control and state that the free-form baseline
does not exist.
**Decision:** (b). **No LLM writes Cypher or Gremlin in any arm of this study.**
**Consequences:** The paper's intended headline claim (C-012) has *no* supporting
experiment, and the ledger says so. This is the single most consequential honesty
decision in the record: (a) would have made the paper look finished and would not
have survived a reviewer reading the harness.

## D-005 — No baseline system was implemented, and this is recorded rather than worked around

**Date:** 2026-08-03
**Context:** Not one alternative system has ever been implemented or run. Every
comparison in the record is Ariadne against Ariadne.
**Options:** (a) frame inter-arm contrasts as though they were baselines;
(b) build a baseline before publishing anything; (c) record the absence
explicitly and treat the two missing baselines as named backlog items.
**Decision:** (c) now, (b) before any archival submission. The two required
baselines are the free-form text-to-Cypher/Gremlin system (C-012) and the
merged-single-graph system (C-015).
**Consequences:** `baselines_compared` is empty in all eleven back-filled
manifests, and it is empty *truthfully*. No result in this repository may be
described as beating anything external.

## D-006 — The 120-question catalogue ships each question's `expected_template`

**Date:** 2026-07-26 (recorded 2026-08-06)
**Context:** Questions were authored alongside the templates that answer them,
and each carries the template it expects.
**Options:** (a) author questions independently of the templates; (b) accept the
coupling to get a computable gold set quickly.
**Decision:** (b), taken for build speed.
**Consequences:** Severe, and the reason C-001 is `partial` rather than
`supported`. The catalogue cannot distinguish capability from coverage, and no
number derived from it is a defensible headline until a blind holdout reports.
This decision is the direct cause of open question Q1.

## D-007 — Raw run artifacts stay in `docs/evaluation/`; the record stores pointers plus hashes

**Date:** 2026-08-06
**Context:** The seven-arm study's artifacts are 62 MB across 2,894 JSON files,
with single answer files up to 2.6 MB. The research record must stay cloneable in
seconds and reject anything above ~10 MB.
**Options:** (a) copy artifacts into each experiment folder; (b) adopt DVC or Git
LFS; (c) leave them in place and reference them by relative path plus SHA-256.
**Decision:** (c). Each experiment's `data/POINTERS.md` carries a directory hash
that folds every file's relative path and content digest in sorted order, so a
rename counts as a change.
**Consequences:** The record depends on `docs/evaluation/` not being reorganised;
if it moves, every pointer breaks at once — which the validator will catch, but
only after the fact. (b) was rejected because adopting a new artifact-tracking
tool is an explicit non-goal of this retrofit.

## D-008 — The append-only rule binds completed experiments, not the ledgers

**Date:** 2026-08-06
**Context:** `docs/skills/global-project-rules/SKILL.md` rule 4 forbade editing
anything under `docs/research/` in place. The research record needs `INDEX.md`
regenerated on every commit and four ledgers that are living documents, so the
rule as written deadlocked the design.
**Options:** (a) keep the blanket ban and put the ledgers elsewhere, breaking the
one-canonical-location principle; (b) narrow the rule.
**Decision:** (b). Append-only binds **completed experiment folders** and
`audit-2026-08-03.md`. It does not bind `CLAIMS.md`, `DECISIONS.md`,
`OPEN_QUESTIONS.md`, `RELATED_WORK.md`, generated files, or an in-progress
experiment.
**Consequences:** The rule is now conditional rather than absolute, which is
weaker protection. Enforcement moves to the validator and CI rather than to a
flat prohibition an agent can read in one line.

## D-009 — Back-filled provenance is recorded as `unknown`, never reconstructed

**Date:** 2026-08-06
**Context:** Eleven experiments were back-filled from runs that predate the
record. Per-arm commits, seeds, and lockfiles were never captured.
**Options:** (a) infer plausible values from git history around the run dates;
(b) omit the fields; (c) record `unknown` / empty and explain in `ISSUES.md`.
**Decision:** (c). The manifest schema is deliberately strict about *absent*
fields and permissive about *unknown* values, so this is expressible rather than
a workaround.
**Consequences:** Eleven manifests carry `code.commit: unknown` and empty
`seeds`. That is visibly incomplete, which is the point — a back-filled
experiment with three known fields is more useful than one with ten invented
ones, and a reader can see at a glance which results are re-runnable.

## D-010 — Every arm is `n_runs: 1`, and no delta carries a significance test

**Date:** 2026-08-06
**Context:** Each arm ran once. Seeds were never recorded. The study reports
point estimates.
**Options:** (a) report the deltas with a test computed from per-question
variation; (b) re-run the arms with seeds before recording anything;
(c) record `n_runs: 1`, `std: null`, `statistical_test: null` and treat the
re-run as backlog.
**Decision:** (c). `std` is null rather than 0.0 throughout, to keep "measured as
zero variance" distinct from "one run, variance unknown".
**Consequences:** No inter-arm delta in this study can be given a p-value as
recorded — including the two headline deltas. Re-running seven arms with seeds
is roughly an hour of wall clock plus 840 judge agents, and is a decision for the
operator rather than something to trigger during a retrofit. Tracked as Q2.

## D-011 — Specialist execution stays strictly sequential, not `Send`-parallel

**Date:** 2026-07 (migrated here 2026-08-06 from the LangGraph orchestration plan
before that plan was deleted)
**Context:** LangGraph's `Send` API can run independent sub-questions
concurrently, which would cut wall clock on the LLM arms substantially.
**Options:** (a) enable `Send`-based parallel fan-out; (b) preserve strictly
sequential, `execution_order()`-driven semantics.
**Decision:** (b). Two reasons: sequential execution is what makes the committed
evaluation artifacts **byte-reproducible**, and dependent sub-questions are
seeded from producers' harvested join identifiers, so ordering is load-bearing
rather than incidental. Parallel execution also failed the snapshot gold, while
sequenced reproduces it.
**Consequences:** Arm A's 1.6 s is achieved *without* parallelism, so the 637×
speed advantage over the LLM arms is not an artifact of a concurrency choice.
Enabling `Send` later would change result ordering, timings, and the committed
baselines — it is a decision that invalidates existing artifacts, not a free
optimisation. The original plan flagged this as needing human input; it remains
open in that sense, and nothing in the record depends on it changing.

## D-012 — Documentation accuracy is a maintained property with a test behind it

**Date:** 2026-08-04 (migrated here 2026-08-06 from the documentation-accuracy
purge plan before that plan was deleted)
**Context:** Documentation was written alongside a system that moved. Several
load-bearing claims had stopped being true: the README sold an "agentic"
federated system whose specialists are in fact fully deterministic template
compilers, docs/purpose.md (since merged into `docs/ARCHITECTURE.md`, 2026-09-09) had the two specialists' roles **inverted** in its
flagship example, the `SPECIALIST_LLM_*` config block it implied was live had
zero read sites, and skill files pointed at a *web/src/* tree that no longer
exists and a *utils/logger.py* that never did.
**Options:** (a) fix the specific errors; (b) fix them and add a test that fails
when documentation drifts again.
**Decision:** (b). `utils/specialists/tests/test_docs_contracts.py` now checks
that every backticked repo-relative path a maintained doc cites exists, that
every relative markdown link resolves, that serialised wire shapes match the
dataclasses, and that each canonical skill has exactly one pointer per agent
folder.
**Consequences:** Documentation accuracy is enforced rather than trusted. The
cost is that moving a file now breaks a test — which is the intended behaviour.
Every defect that purge fixed was one this test would have caught.

---

## D-013 — Keep a malformed blind question rather than repair it (2026-08-09)

**Context:** During the blind holdout (EXP-2026-08-002), one of the 30 authored
questions came back incoherent. `H-SW-01` asks what techniques the
*sub-technique* T1555.005 implements, because the category description handed to
the Author ("the techniques a piece of software implements") presupposes a
Software anchor while the stratum's population is techniques. The defect is in
the category scheme, not in the sampler or the Author.

**Options:** (a) edit the question so it asks the coherent direction; (b)
discard the anchor and redraw from the seeded sequence; (c) keep it verbatim and
report every figure twice, with and without it.

**Decision:** (c). Editing an authored question after seeing its anchor converts
a blind question into a co-authored one, which is precisely the failure the
experiment exists to detect — and the result would still look like a number,
which is what makes that failure dangerous. Discarding is reserved by plan 02 §6
for anchors whose *gold computation* fails; this one's gold computed fine.

**Consequences:** Arm A reports 0.689 over n=30 and 0.709 over n=29; the
conclusion does not turn on the difference. The same reasoning governed the one
change that *was* made mid-run — a missing `join_key` in the Compiler was fixed
and logged as a deviation, because a defect in the harness is the same class of
thing as a crash, and §9 permits fixing a crash while forbidding fixing a wrong
answer. The line is: **the system's output is a result; the apparatus around it
is a bug.**

---

## D-014 — Apply the publication gate as written, at 0.011 below its threshold (2026-08-09)

**Context:** The Branch A §6 gate sets four bands on blind correctness. Arm A
landed at **0.689** against a `< 0.70` boundary, with a 95% CI of 0.550–0.817
spanning three of the four bands, and Arm F landed at 0.708 — in the band above.

**Options:** (a) apply the `< 0.70` branch as written on the primary arm; (b)
read the gate on Arm F, or on the interval, and take the friendlier branch; (c)
re-derive the thresholds now that the interval width is known.

**Decision:** (a). The plan states the thresholds are not renegotiated after
seeing the result, and a gate that moves once the number is in is not a gate.
Both mitigating facts — the 0.011 margin and Arm F's position — are recorded
alongside the decision as facts, not as grounds for choosing differently.

**Consequences:** Branch A Steps 6 and 7 do not proceed as written; the re-plan
takes the coverage-boundary framing, for which this run already supplies the
boundary. Separately: any future gate on a set this size should be stated as a
decision on the interval rather than on the point, because at n=30 this one
could not be resolved sharply and that was not visible when it was written.

---

## Superseded source documents

D-011 and D-012 record decisions originally written up in the
LangGraph orchestration migration plan and the documentation accuracy purge plan
under *docs/plans/* (paths deliberately not backticked — the files no longer
exist). Those plans, along with 51
others whose work had shipped, were deleted on 2026-08-06 to keep the repository
navigable; their decision content was migrated here first so no reasoning was
lost with them. `docs/plans/robustness/` and its `_overnight/` derivation
scripts are retained — they are live work and the provenance behind the recomputed
figures in every arm's `metrics.json`.
## D-015 — Revise the negative-case gold contract rather than revert the outer join (2026-08-18)

**Context:** Porting the outer-join bridge to `capec_maps_to` and `cwe_chain`
(the generic branch has had it since `EXP-2026-08-004`) changed what a "this
maps to nothing" question returns. The producer now retrieves the anchor with an
empty mapping list, where before it retrieved nothing. Eight committed golden
negative cases assert the old shape: `expect_empty` on records, and zero claims
on federated negatives.

The first consequence was a genuine honesty regression, not a test-expectation
mismatch. `_empty_ok_results` defined an honest empty as "no records", so with a
record present the producer stopped abstaining — and the answer described
CAPEC-16's metadata while never stating that it maps to no ATT&CK technique,
which is the thing the question asked. Fixed before this decision was taken: a
sub-question that declared a join key and came back with no join values is an
honest empty *for that join*, and its abstention carries the executed query.

**Options:** (a) revise the gold contract for negative cases; (b) revert the
template outer join and keep it on the generic branch only, accepting five blind
identifiers; (c) keep the join but suppress the descriptive claims, preserving
the pure-abstention answer shape.

**Decision:** (a), taken by the operator. A negative answer may now carry
supported, cited claims describing the anchor, and **must** still carry the
abstention that states the join came back empty, with the executed query as
proof. A new assertion kind, `expect_no_join`, replaces `expect_empty` on the
seven cases where the anchor genuinely exists — records are required, join
values are forbidden. `expect_empty` keeps its meaning for cases where nothing
exists at all (`A-NEG-01`'s nonexistent T9999 is *not* one of these, and an
early draft of this change wrongly flipped it).

**Consequences:** The honest-abstention property is unchanged in substance and
strengthened in wording — the statement now reads "returned CAPEC-16 with no
linked records" rather than the false "returned no matching records". But the
gold moved, and a moved gold is exactly what this project distrusts elsewhere,
so: the change is in the bank *generators*, not in the compiled JSON; it is
seven assertion flips with no gold value altered; and any figure quoted across
2026-08-18 must say which contract it was measured under. The alternative — gold
that asserts a retrievable pattern is unretrievable — would have been false in a
way no reviewer could check.

---

## D-016 — Widen the Neo4j relationship-name rule rather than rename CAPEC's edges (2026-08-20)

**Context:** The merged-graph counterfactual (C-015) needs ATT&CK and CAPEC in
one Neo4j. ATT&CK loaded; CAPEC's nodes loaded; CAPEC's relationships did not:

    ValueError: Unsafe Neo4j relationship type: 'CanAlsoBe'

`utils/graph_loader/stores/neo4j.py` admitted relationship types matching
`^[A-Z][A-Z0-9_]*$` while admitting labels matching `^[A-Za-z][A-Za-z0-9_]*$`
one line above. Ten of CAPEC's fifteen relationship names are ones this repo
invents — the source XML expresses those links by nesting a `<Mitigation>`
inside an `<Attack_Pattern>` rather than by naming the relationship, so there is
no name to copy — and they are screaming-snake by house style. The other five
(`ChildOf`, `CanPrecede`, `CanFollow`, `PeerOf`, `CanAlsoBe`) are copied
verbatim from the `Nature` attribute of the CAPEC XML. CAPEC had only ever been
loaded into Gremlin, which has no such rule, so MITRE's spelling met this
validator for the first time on 2026-08-19.

**Options:** (a) widen the relationship rule to match the label rule;
(b) normalise the five to `CAN_ALSO_BE`, `CHILD_OF` and so on at load time,
leaving the validator untouched; (c) abandon the merged counterfactual.

**Decision:** (a), taken by the operator on 2026-08-20 after the trade was
written up in `docs/evaluation/night2-2026-08-20/MERGED-LOAD-FINDING.md`.

**Consequences.** This is a change to a function named for safety, and it is
recorded as such rather than slipped in. What the rule blocks — backticks,
quotes, whitespace, punctuation, anything that could close the identifier and
continue the query — is unchanged; only letter case moved, and the label rule
beside it already permitted mixed case, so the codebase held no position that
mixed case was dangerous. `utils/graph_loader/tests/test_neo4j_store.py` now
pins both halves: the six names that must pass, and seven shapes (including a
literal injection string) that must still raise.

Option (b) was rejected on experimental grounds, not engineering ones. Renaming
would make the merged store name its relationships differently from the Gremlin
store holding the same data, so a query written against one would not port to
the other — inside the one experiment that is about whether queries port
between stores. It would have handicapped the merged arm in the comparison the
arm exists to inform, which is the same class of error as building a strawman
baseline. See D-004 on why that class of error is the one this record most
guards against.

## D-017 — The merged graph reconciles identifiers at load, and says so (2026-08-20)

**Context:** Building the C-015 counterfactual surfaced two places where the
merged store cannot answer at all unless something is decided, and both are
decisions about what the *merged condition* is rather than about how to make it
win.

**(a) Public identifiers.** Every schema-driven Cypher query anchors on
`coalesce(n.attack_id, n.id)`. ATT&CK nodes carry `T1047` there. CAPEC nodes
carry nothing — their public id is *derived from the node id* at read time by
the Gremlin normalizer. A merged store queried in Cypher has no read-time step,
so a seed of `CAPEC-66` matches nothing and the arm scores zero for a reason
that is about plumbing.

**(b) The mapping identifier.** CAPEC's ATT&CK taxonomy entries store the bare
number `1027.001` where ATT&CK stores `T1027.001`. The federated system
reconciles that at read time too, in the Gremlin normalizer's `maps_to` handler
(`f"T{entry_id}"` when `taxonomy_name == "ATTACK"`).

**Options:** (a) leave both, and report the resulting failures as the cost of
merging; (b) reconcile both at merge time, in the data; (c) reconcile at query
time in the Cypher path, mirroring the Gremlin code.

**Decision:** (b). Both values are written by `utils/kg_builder/merge.py`, and
the rule for (a) is *imported* from the Gremlin normalizer (`public_member_id`)
rather than restated, so the merged store's public-id surface is identical to
what the federated system reports — `CAPEC-<n>` and `CWE-<n>`, with composite
children keeping raw ids.

**Consequences.** Option (a) was rejected because it would have measured our
plumbing and reported it as an architectural finding — the strawman failure D-004
exists to prevent, in its most tempting form, since the strawman would have
favoured the conclusion the project already prefers. Reconciling identifiers
once at load rather than at every query is the merged design's own argument for
itself; refusing to let the merged arm make that argument is not neutrality.

Option (c) would have worked but puts a CAPEC-shaped rule inside the Cypher
normalizer that four federated arms also run.

**What travels with the claim.** The merged arm gets its cross-catalogue join
values from a *neighbour's* identifier, and the federated arms do not
(`_normalize_generic_neighbors`, gated on the card's `identity.subsumes`). That
asymmetry is deliberate and is a finding rather than a fudge: in a single-store
architecture the next hop is reachable without leaving the engine, and in a
federated one it is not. It must be reported as one of the things merging buys,
not hidden inside a normaliser. Measured effect on the blind set: consumer
sub-questions skipped for want of a join value fell from 7 of 30 to 3 of 30, and
the three that remain are the cases whose gold asserts `expect_dependency_skip`.

## D-018 — Score external benchmarks against an oracle, not against 1.0 (2026-08-21)

**Context.** Both external benchmarks predate the loaded ATT&CK 19.0. A missing
gold identifier is either the system's failure or the benchmark's staleness, and
a score cannot tell them apart.

**Decision.** Every external cell is read against an oracle that reads the
canonical artifacts directly — no plan, no specialist, no query engine — so it
bounds what any retriever over this data could return.

**Why it mattered immediately.** The oracle scores **0.607** precision on
CTIBench's `cti-ate`, returning 466 identifiers where gold lists 283. Without
it, that 0.393 would have been reported as an Ariadne result. It is the
benchmark being four ATT&CK releases old.

**Cost.** One more arm, and the discipline of never quoting a raw external
score without the ceiling beside it.

## D-019 — No language model in the primary metric (2026-08-21)

**Context.** Every headline figure in this project runs through a local judge
that has never been checked against a human. That caveat appears in every
report and cannot be removed by writing it again.

**Decision.** External gold is set-valued ATT&CK identifiers, so scoring is set
arithmetic. Recall, precision, F1 and exact match are computed by one regex and
two set operations. The judge is not invoked.

**Consequence.** These are the only figures in the record that survive the
judge being wrong. That is worth more than their sample size suggests.

## D-020 — Fetch the benchmarks, never commit them (2026-08-21)

CTIBench is CC-BY-NC-SA-4.0 and share-alike would follow a redistributed copy
into this repository's history. AttackQA is Apache-2.0 but is 7 MB of somebody
else's data. Both are fetched at pinned revisions into a gitignored cache; the
scores computed from them are ours and are committed.

## D-021 — Count what the data cannot answer, never drop it (2026-08-21)

14 of CTIBench's 60 rows name software this deployment does not hold — 13
Mobile, plus S0440, retired between the benchmark's snapshot and ATT&CK 19.0.
One further gold identifier is absent. These are excluded from scoring and
reported as a coverage figure. Silently dropping them would turn "we load
Enterprise only" into a better-looking score.

## D-022 — Gold granularity follows the benchmark, per benchmark (2026-08-21)

`cti-ate`'s prompt states that its gold excludes sub-technique identifiers, so
both sides of that comparison are rolled to parent techniques. AttackQA's gold
includes sub-techniques and is left alone. Applying one rule to both would have
manufactured either misses or false hits, depending on direction.

## D-023 — Give an external question the plan an internal one gets (2026-08-21)

**The mistake this corrects.** The derived plan first supplied only the two
endpoint labels, on the reasoning that naming a relationship would be doing the
planner's job. This project's own entries carry the relationship type too —
`H-SUB-01` has `["Technique", "SubTechnique", "HAS_SUBTECHNIQUE"]`.

Withholding it does not make the control purer. It hands external questions a
**weaker** plan than the internal comparison gets, which converts a harness
deficit into an apparent system failure — the exact error the experiment exists
to avoid making about somebody else's benchmark. It zeroed two question
families outright.

**Decision.** The derivation appends the relationship type. The run was stopped
and restarted; the first run's numbers are superseded and quoted nowhere.

**The general rule.** A control that gives the external condition less than the
internal one is not conservative. It is wrong in the direction that flatters the
conclusion you were hoping to draw.

## D-024 — Fix the composer's false labels, accepting that 21 recorded answers change wording (2026-08-21)

**The defect.** EXP-2026-08-010 caught the composer writing, of a piece of
software: *"S0512 (FatDuke) has 2 used techniques: G0016, C0023"*. G0016 is a
Group and C0023 a Campaign. ATT&CK's `USES` joins Group→Software,
Campaign→Software and Software→Technique alike, while `_REL_NOUNS` maps the
relationship to one noun. The identifiers were correct and retrieved; only the
noun was false — the worst shape this failure takes, because a reader has no way
to tell that the label is the part that lied. It was the last known fabrication
source in an otherwise deterministic path.

Two further bugs surfaced in the same function. The label fallback was
**count-blind**, writing "has 1 Skills". And it appended an "s" to the label
verbatim, writing "1 TaxonomyEntrys" — a type name with a plural bolted on.

**Decision.** All three fixed: a noun that asserts a kind is used only when the
neighbours are that kind (`_NOUN_EXPECTS`); the label fallback respects count;
and labels get spelled English forms (`_LABEL_NOUNS`).

**The cost, measured rather than assumed.** Unlike the template fix in
EXP-2026-08-012, this is not free. Re-running the deterministic arm over both
committed banks:

| | |
|---|---:|
| answers whose prose changed | **21 of 60** |
| identifiers named in the answer, unchanged | **60 of 60** |
| claim `entity_ids`, unchanged | **60 of 60** |

Not one identifier moved in any answer. Every text change is an improvement, and
two are outright grammar errors being corrected.

**Why ship anyway.** Unlike D-023's roll-up question, this has a correct answer:
the old text contained statements that were false about grounded identifiers.
Keeping a known falsehood to protect the byte-stability of a figure is the wrong
trade, and the figures rest on claim correctness rather than prose style.

**What travels with it.** Any judged figure computed over those 21 answers was
computed on the old wording. The scores are not invalidated — the claims and
their identifiers are unchanged — but a re-judge is the only way to state a
post-fix number, and none is claimed here.

## D-025 — The evidence reader's template coupling is part of the comparison, not an artifact (2026-08-23)

**Context.** The evidence reader dispatches on the column combinations the
templates produce. A free-form query that returns `group_id` + `group_name` and
nothing else normalises to nothing however correct the query and however real
the rows it returned. Seven of the free-form arm's thirty questions failed that
way in EXP-2026-08-008, which is the single ambiguity in C-012 — the study's
headline claim. Open question Q18 framed the fork precisely: either the coupling
is an artifact of our harness and the baseline should be measured without it, or
guaranteeing that a query's output is consumable is a genuine property templates
provide and the free-form arm should wear it.

**Options.** (a) Build a generic normaliser keyed on `<entity>_id` /
`<entity>_name` conventions rather than on template shapes, and report it as a
secondary arm. (b) Decide that the coupling is part of what is being compared,
and say so.

**Decision:** (b), with an enforcement test.

**Why.** A template library's value proposition is not only "the query is
correct" but "the query is *consumable by the pipeline that has to read it*". A
free-form generator that emits a correct query in a shape nothing downstream can
parse has not delivered an answer, and crediting it as though it had would
measure query-writing in isolation from the system the query lives in. That is a
different and easier problem than the one this project is about.

**What this costs, stated plainly.** It makes the comparison partly a comparison
of *integration*, not purely of query generation, and a reviewer is entitled to
say so. EXP-2026-08-008 therefore reports **both** numbers and always will:
**0.5000** raw, and **0.5739** crediting every reader failure to the baseline.
The conclusion — templates roughly double the free-form arm — survives either
reading, which is the only reason this decision is affordable. **If a future
result depended on which number is quoted, this decision must be revisited
rather than leaned on.**

**Why not (a).** Not because it is wrong — it is the more generous experiment
and it would be worth running. It is deferred because it changes what the
baseline *is* mid-study, and because the conclusion does not turn on it. Q18
stays open in the narrower form: *what would the free-form arm score against a
convention-keyed reader?* That is a question about the baseline's ceiling, not
about whether C-012 holds.

**Enforcement.** A decision recorded only in prose is unenforced, so the
coupling is now pinned by
`utils/specialists/tests/test_evidence_contract.py`, which asserts in both
directions that the set of `<entity>_id` columns the Cypher builder emits equals
the set the normalizer dispatches on. A template emitting a column no reader
branch handles fails the suite (it would otherwise fall to `_normalize_flat` and
emit `unknown` ids — the same failure the free-form arm hit); a reader branch no
template feeds fails it too (dead dispatch, the inflation class that put two
unreachable templates in the capability census until 2026-08-23). The routing
cases additionally pin branch *order*, which is load-bearing: `software_id` +
`technique_id` must beat the actor-software branch, and both must beat the bare
`technique_id` branch.

**Consequence.** The coupling is now a declared, tested property of the system
rather than an accident of implementation, which is the difference between a
design decision and a limitation.

---

## D-026 — The Sikos citation is withdrawn; the gap is argued from the systems literature instead (2026-08-26)

**Context.** Since the 2026-08-03 audit, C-011's novelty argument rested on one
sentence: Sikos (2023) §7 *names* cross-KG federation for security and **cites
nothing for it**, and that silence was read as the shape of a genuine gap. It
was the load-bearing citation under the whole positioning.

The 2026-08-26 novelty audit retrieved and read the paper in full. It does not
say what we said it says:

- `federat` appears **once in the entire article**.
- The worked example attached to it is
  `SELECT ?cve FROM NAMED MITRE FROM NAMED CISCO FROM NAMED NIST` — a **single
  triplestore querying named graphs**. `SERVICE`, `endpoint` and `interlink`
  appear **zero times**. It is not federation in any query-engine sense.
- The paper has **no** future-work, open-problems or research-challenges
  section. §8 is a nine-sentence backward-looking conclusion citing nothing.

The paragraph cites nothing because it is an offhand remark about a capability
the author treats as already available — not because a gap is being flagged.

**Options.** (a) Keep the citation with a hedge. (b) Withdraw it and argue the
gap from a different evidence base. (c) Drop the gap argument entirely and
position purely on measurement.

**Decision:** (b). Withdrawn outright, and replaced with the absence pattern
across the CTI **systems** literature.

**Why.** (a) is not survivable. The paper is open access; a reviewer disproves
the sentence in ninety seconds by downloading it, and a citation that fails on
retrieval poisons every other citation in the section — which is the exact
failure mode `RELATED_WORK.md` was written to prevent, applied to a row this
project inherited from an abstract-level audit and never re-opened.

(c) gives up something real. The gap **is** there; we were pointing at the wrong
evidence for it. The replacement is stronger because it is checkable in the
direction that matters: **the systems that build this architecture decline to
measure it.** CyKG-RAG (2024) and AgCyRAG (2025) ship three anecdotal questions
between them, zero gold queries and zero metrics, and *both* state that
comprehensive evaluation is future work. CTIConnect (KDD 2026) reaches 1,860
expert-verified pairs with no query language at all. Ozsoy (2026) proposes the
problem and explicitly builds nothing. An absence demonstrated by what four
papers do not report beats an absence inferred from one sentence in a survey.

**Consequence.** C-011 is `refuted`; C-024 carries the narrower claim.
`RELATED_WORK.md` records the withdrawal in place rather than deleting the row,
because the error pattern — inheriting an abstract-level row and citing it as
though read — is the transferable lesson. Every citation in that file now
carries an evidence tag (✅ read / 📄 abstract / ⚠️ snippet / UNVERIFIED).

**Generalisation, and the reason this is a decision rather than a fix.** Four of
eight prior-art rows were wrong. All four survived casual checking and failed on
retrieval. **No entry may be cited for what a paper *measured* unless someone
has opened its results section**, and the tag now makes an unopened entry
visible instead of invisible.

---

## D-027 — The architecture is the method section; the contribution is the measurements and the resource (2026-08-26)

**Date:** 2026-08-26
**Context.** The novelty audit's closing judgement is blunt: *"Your architecture
is your method section, not your contribution."* Every architectural component
has published prior art — mediator-wrapper federation (25 years), templates
instead of parsing (a named KBQA family since 2015), constrained generation as
the stronger modern analogue, AgCyRAG for the two-store two-language security
loop, Ozsoy for the cross-language problem statement, EICopilot for
natural-language-to-Gremlin. The hostile-reviewer sentence writes itself:
*"AgCyRAG with a different second query language and a benchmark attached."*

**Options.** (a) Position on architecture and defend novelty in kind.
(b) Position on the measurements, treating the architecture as the instrument
that makes them possible. (c) Position on the resource — the benchmark — and
demote the system to supporting material.

**Decision:** (b) as the primary framing, with (c) recorded as a live
alternative that may become primary. Not (a).

**Why.** (a) is unwinnable and the audit says so with citations. What is
defensible is that **eliminating query generation makes the system a different
measurement instrument, not merely a different implementation** — with no
stochastic query-writing step, stage-wise attribution and the
template-versus-schema-derived comparison are confounded by nothing, which is
precisely why we can run them and the generation-based literature cannot.

The uncomfortable half is recorded rather than softened: **three of the four
headline measurements are nulls** — federation is not more accurate than
merging (C-022), templates are not more accurate than schema-derived
construction (C-023), and query generation is not where the loss is (C-016).
Papers built on nulls need unusually clean design and unusually careful claims,
and **one of our nulls currently contradicts the only comparable published
distribution** (C-016 against Leung et al., EACL 2026). Explaining that
structurally is Q24 and it is the highest-value writing left.

(c) is kept live because the audit rates it the cleanest gap found (C-025) and
because **the group with the closest architecture has now declared comprehensive
evaluation to be future work in two consecutive papers.** That is an unbuilt
artifact with a public promise attached and an active group behind it — both an
opportunity and a clock. It is not primary today for one reason: **we do not
currently ship gold queries** (Q26). If Q26 closes, this decision should be
revisited rather than assumed.

**Consequence.** The paper leads with the instrument-and-measurements framing.
Priority claims on the architecture, the problem statement, natural-language-to-
Gremlin, and the security of graph-query interfaces are **all conceded and cited
explicitly** rather than left for a reviewer to raise. Supersedes nothing;
constrains D-004's positioning guidance with a named alternative.

---

## D-028 — An alias is not a model: record the served weights, and detect a swap rather than trusting a name (2026-08-31)

**Context.** The relay alias `skynet` has now been repointed **three times** —
Gemma 4 31B in July, `Ornith-1.5-35B-A3B-W4A16-SYM` by 24 August, and
`qwen38-27B-v2` on 31 August. The first two swaps were discovered after the fact,
by asking the operator; the window between them is *still* undetermined, and
`EXP-2026-08-007`, `-008` and `-009` — carrying **C-012, C-021 and C-022** — fall
inside it. Seven July manifests record `model: "vllm/gemma-4-31b@unknown"  # the
relay alias 'skynet'`, which is the shape of the problem: the manifest recorded
the alias and believed it had recorded a model.

**Decision.** Four rules, binding on every future run.

1. **A result records the served model, its quantisation and the date — never
   the alias.** The manifest form is `relay/<served-model>@<YYYY-MM-DD>`, as
   `EXP-2026-08-018` already uses. The string `skynet` must not appear in any
   recorded figure.
2. **The served model is *probed*, not asked.** `scripts/model_identity.py`
   issues a minimal completion and reads the `model` field off the response
   envelope. `GET /v1/models` is insufficient and is the reason two swaps went
   unnoticed: the relay answers `skynet` with `upstream_model: "auto"` because it
   hot-swaps. The script reports advertisement-versus-reality mismatches, which
   currently exist.
3. **The run harness records it automatically.** `run_meta` carries the probed
   served model beside `max_hops` and the rest. A run that cannot identify its
   model records `unknown` — never a guess, per `D-009`.
4. **A judged run fails on a mismatch** between the served model and the
   manifest's declared model, rather than producing a figure nobody can attribute
   afterwards.

**Alternatives rejected.**

- *Pin the model id in `.env`.* **Not available.** `qwen38-27B-v2` is not
  separately addressable on the relay — only `auto` and `skynet` are, and both
  hot-swap. Detection is therefore the only defence, which is why rule 2 does the
  work rather than a configuration change.
- *Ask the operator on a schedule.* This is what happened twice and it produced a
  gap of unknown length both times. A question that can be answered mechanically
  should not depend on someone remembering to raise it.
- *Re-run everything on each swap.* Rejected as disproportionate and as
  actively harmful to the record. Roughly four-fifths of this record's primary
  metrics take **no model at all**, and re-running frozen banks or the July arm
  study would destroy comparability rather than restore it. The triage lives in
  [`../plans/2026-08-31-model-migration-qwen38.md`](../plans/2026-08-31-model-migration-qwen38.md) §3.

**Consequence.** The study's "one model, one day" limitation is now formally
"three models over three months, boundaries partly unknown, detected by probe
from 2026-08-31". That is worse than the record used to claim and better than
what it could have claimed had the third swap also gone unnoticed. It also
sharpens an existing argument: the Sonnet panels are provider-hosted and were
untouched by any of the three swaps, so **the cross-model panel is now the
practical choice for anything quoted externally, not merely the principled one**
(`D-002`, `C-009`).

---

## D-029 — Spend the holdout despite a failed pre-registered gate, and say so

**2026-09-05. Operator decision, taken explicitly rather than absorbed.**

[`EXP-2026-09-007`](experiments/EXP-2026-09-007-holdout-spend/PROTOCOL.md)'s stop
condition reads: *any arm-ordering reversal in `EXP-2026-09-006` → hold,
investigate, and write that up first.* The complete cross-family pass produced
**one reversal in 23 pairs**, so H1 failed as written. The holdout was judged
anyway, on the operator's explicit call, with the failure recorded and travelling
with the result.

**Why this is not a quiet reinterpretation.**

1. **The hypothesis stays failed.** H1 is recorded as failed in
   [`ISSUES.md` I-7](experiments/EXP-2026-09-006-cross-family-august-regrade/ISSUES.md).
   No noise threshold was introduced after seeing the result. The obvious repair
   — declare a pair "unranked" when the margin is inside the grader's own spread
   — would make H1 pass and is precisely the post-hoc adjustment that voids a
   pre-registration. It was not made.
2. **The reversal is disjoint from what the holdout measures.** It is
   `gold_loop_llm` against `generic_composed` on `bank20260820`. Neither arm
   appears in the paper's three-way comparison (`deterministic`, `generic`,
   `llm_query`) and neither carries a claim.
3. **Neither grader resolves the pair.** gemma separates them by **0.0033**,
   inside its own within-family spread (0.0036–0.0249) and an order of magnitude
   inside the pair's paired sd of 0.0287; qwen's **+0.0276** is well inside its
   0.0854. One weak disagreement about two arms neither instrument can tell
   apart.
4. **Everything claim-bearing is unmoved.** `contrast_sign_flips = 0` across
   C-012, C-021 and C-022, on 510 frozen answers under two named families.
5. **The resource was expiring.** `gemma4-31B-mtp` was available until 16:00 and
   does not return today. Holding would have cost the only second-family
   grading window for the holdout, indefinitely.

**Alternatives rejected.**

- *Hold the holdout entirely.* The literal reading. Rejected because the reversal
  is disjoint from the holdout's arms and inside both graders' noise, so holding
  would have paid a permanent cost for a defect that cannot touch the result.
- *Judge under qwen only.* Would have produced a clean single-family holdout and
  deferred the cross-family half. Rejected for the same reason as above plus the
  expiry: a single-family holdout is exactly the gap `EXP-2026-09-006` exists to
  close everywhere else.
- *Weaken the tie rule so H1 passes.* Rejected on principle. See point 1.

**Consequence.** The holdout result must be quoted with the sentence *"the
cross-family gate recorded one arm-ordering reversal in 23 pairs, on a pair
neither grader resolves and neither claim uses"* attached. A reader who wants to
discount the holdout on that basis has the number to do it with. That is the
trade this decision makes: the gate was not met, the spend happened anyway, and
the record says so in both places rather than in neither.

---

## D-030 — C-022 is rewritten: the loose reading is dead, the strict one survives

**2026-09-06, from the overnight positioning sweep.**

C-022 rested on a null — *"no paper builds both a federated and a merged version
of the same KGQA system and reports a head-to-head answer-accuracy comparison"*
— recorded on 2026-08-26 with verdict `clear`, confidence medium. **That null is
false.** Two papers do exactly that:

- **SPLIT-RAG** (arXiv:2505.13994v1): ablation B is the merged condition
  verbatim. WebQSP Hit **87.7 split against 70.1 merged** — a 17.6-point gap.
- **FedV-KGQA** (arXiv:2608.24846v1, ISWC 2026 Research Track): federated against
  "a centralized upper bound that trains on the merged KG". Federated trails by
  **0.04 / 0.03 MRR**.

**And they disagree with each other about the sign.**

**What was changed.** The claim now reads *"we are not aware of a head-to-head
answer-accuracy comparison between federated execution across **heterogeneous
live stores** and materialised merging"*, with the within-system neutrality
reported as our own measurement rather than as a gap in the field.

**Why not simply retract it.** Neither paper crosses an engine boundary.
FedV-KGQA vertically partitions **one** benchmark KG and its "federation" is
federated *learning* of embeddings with no runtime inter-silo communication;
SPLIT-RAG partitions **one** Freebase-derived KG inside one system, and its
ablation removes the multi-agent retriever at the same time as it merges, so the
17.6 points cannot be attributed to topology alone. The strict reading — two
live stores, two engines, two query languages — is untouched.

**Alternatives rejected.**

- *Keep the claim as written.* Rejected outright. It was the only claim in the
  record a reviewer could falsify with a two-minute search, and the sweep did.
- *Retract C-022 entirely.* Rejected: the strict comparison genuinely is
  unoccupied, and the structural half — merging relocates reconciliation from
  code into the stored records, 1,083 nodes given identifiers their upstream
  record does not ship — is our own measurement and is unaffected.
- *Report the neutrality without the field claim.* Close to what was done, but it
  discards a real and defensible null. The rewrite keeps it, narrowed to the
  boundary the evidence actually supports.

**Consequence, and it is a burden not a relief.** SPLIT-RAG's 17.6 points is
evidence that integration architecture **can** move accuracy a great deal. Our
own federated-against-merged result is neutral. **A reviewer will ask why ours is
neutral when theirs is not, and the paper must answer it** — most plausibly that
their ablation changes agent count as well as store topology, so the two are not
measuring the same variable. That sentence belongs in the paper, not in this
ledger.

## D-031 — The rewrite stage sits in front of the engine, and the model selects rather than plans (2026-09-08)

**Decision.** The hybrid rewrite stage is **one node between `classify` and
`draft`** in the planner subgraph, and everything downstream — the drafter, the
gate, the specialists, the composer — is untouched and still receives only a
request string. Within that node, a model may **choose from candidate lists it
cannot add to**, and may do nothing else.

**Why the placement.** After `classify` because the deterministic fill reads the
classified intent to pick the mode. Before `draft` because that keeps the
byte-identity claim trivially true with the flag off — proved at every step of
the build — and keeps the change reviewable: one node, one string.

**Why "selects, never plans", and why it is enforced three times.** The two
prior LLM-in-the-loop arms are the argument. The LLM drafter cost −0.1185
against the deterministic one; the free-form query arm reached 0.50 record
identity where the deterministic engine reaches 1.0000. Those failed because the
model was allowed to *name* things — a source, a hop, an identifier. This seam
cannot: the prompt asks for indices, `_pick` refuses anything that is not an
`int` in range, and `gate_form` re-checks the finished form against the same
closed world. Any one alone is an assertion; three make it a property. It is a
measured property, not a claimed one — the gate refuses **41–45 of 195 picks per
run (~22%)**, every run, in both arms.

Direction is never the model's to choose. It is read from the card's declared
endpoints, the only place it is knowable, and a relation whose direction cannot
be resolved is refused rather than rendered.

**Alternatives rejected.**
- *Let the model emit the plan or the query.* Already measured, twice, and both
  lost to the deterministic engine.
- *Let the model return names instead of indices.* A name that happens to be on
  the list is not a choice from the list, and accepting it makes the closed
  world advisory. Rejected in code, not only in prose.
- *Pass structured seeds straight to the drafter instead of a rendered
  sentence.* A later optimisation. Rendering to a sentence is what makes the
  stage testable on its own — `render(slot_gold)` must round-trip to the gold
  records — and what keeps `utils/specialists/` untouched.

## D-032 — `ARIADNE_REWRITE` and `ARIADNE_REWRITE_MODEL` stay OFF by default (2026-09-08)

**Decision.** Both flags remain off. EXP-2026-09-014 pre-registered a ship rule
before any arm ran — T4 and T5 `records_exact` both > 0.25, with T6
`wrong_entity` ≤ 0.1000 and `catalogue_dump` ≤ 0.0667 — and the stage **misses
it by a factor of two to three**: T4 0.0880 ± 0.0089, T5 0.1635 ± 0.0089.

**What it did achieve, because the decision is not that the stage failed.** It is
the first configuration in this record to move T4/T5 off 0.0000, where
EXP-2026-08-020 found exactly zero across every arm it tried. It does so
reproducibly (sd ≤ 0.0160 across three runs, and across two serving instances).
It cuts catalogue dumps at every tier. Its negative control holds at the *slot*
level — T6 `slot_anchor` is 0.0000 — not merely at the record level. And it is
+0.196 at T3.

**Three things had to be true to ship and only one was.**
1. The threshold. Missed.
2. The negative controls. The T6 gate passed and improved — and it was the wrong
   gate. `wrong_entity` roughly **doubles at T4 and T5**, the tiers the stage
   helps (0.1321 → 0.2516, 0.1132 → 0.2453). The stage converts abstention into
   answers and about half of the converted silence is wrong. Writing a gate that
   watched only T6 is a mistake this ledger should own: a negative-control gate
   belongs on every tier the change touches. See Q35.
3. It must fit the shipped budget. It does not. The rewrite's model call is
   charged against the same `PIPELINE_TIMEOUT_S=120` retrieval needs, and under
   it the arm loses records it retrieves at 900 s. See Q37.

**Alternatives rejected.**
- *Ship it anyway on the strength of T4/T5 moving off zero.* Rejected. The rule
  was written before the numbers precisely so this could not be argued after
  them, and the T4/T5 confident-wrong doubling is the failure the project exists
  to avoid.
- *Relax the threshold to fit the result.* Rejected for the same reason. If 0.25
  was the wrong bar, that is an argument to make before the next run, not after
  this one.
- *Ship the deterministic half (`ARIADNE_REWRITE` alone).* Tempting — R1 needs no
  model and is +0.0784 at T3 with fewer dumps — but it is −0.0318 at T2 and 5
  better / 3 worse case by case on 301 questions. That is not a shipping
  margin, and it has not been through the recorded-answer regression on both
  banks.
- *Add a guard that refuses to rewrite federated questions.* Structurally
  justified (Q36) and probably right, but proposing it after seeing the tune
  half makes it post-hoc. It is recorded as a follow-up arm, not folded in.

**Reversible.** Both flags exist and are documented; the decision is which
default they carry, and the next experiment can change it on evidence.
