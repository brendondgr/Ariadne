# Plan 03 — Deferred work register

**Audience:** anyone — human or agent — who picks up an item and wonders why it
was not done already.
**This is not a task list.** It is a register of decisions to postpone, each
with the reason, the thing that unblocks it, and the cost of doing it early.
Nothing here should be started because it looks available.

The failure this document prevents is the most common one on a project at this
stage: an agent with spare capacity picks up the merged-graph baseline because
it is well-specified, and burns ten days measuring something the holdout was
about to make irrelevant.

---

## 1. Blocked on a human decision

### 1.1 The repository license

**Owner:** PI (Olmo Zavala Romero), with FSU policy input.
**Cost if skipped:** total. No artifact release, therefore no demo track. EACL
System Demonstrations, IEEE Big Data Demo and SIGMOD Demo are all closed until
this exists.
**Cost if guessed:** worse than waiting. A license applied without institutional
sign-off on a grant-funded artifact is a problem that surfaces later and cannot
be quietly reversed once published.

Two realistic options. **Apache-2.0** carries an explicit patent grant and is
the usual choice for a research artifact with industrial funding — the patent
clause is generally what makes a corporate sponsor comfortable. **MIT** is
simpler and contains no patent language.

Also needs confirming: whether the ReliaQuest Innovation Challenge Fund terms
impose any constraint on release.

**Note the separation.** MITRE attribution is *not* blocked on this and is
handled in Plan 01 Task 3. ATT&CK and CAPEC attribution requirements are
independent of whatever license the project itself carries.

**Unblocked by:** an email. Send it in week 1 with the 22 September date in it.

### 1.2 The remaining model fields

**Owner:** whoever administers the vLLM deployment.
**Status:** partly resolved — the model is **Gemma 4 31B**. Outstanding: the
**quantisation** and the **exact context window**.
**Cost if skipped:** Reproducibility caps at 3 instead of 4. Not fatal, but it
is the cheapest remaining point on the board.

Plan 01 Task 10 records what is known and marks the two gaps rather than
guessing. Close them by asking, not by inferring from behaviour.

---

## 2. Blocked on the holdout gate

Everything in this section is **deliberately not started** until the Step 4
result exists. The gate is at
`docs/plans/branch-a-publication-readiness-plan.md` §6.

### 2.1 The merged-single-graph control — 10 days

**Why deferred:** it measures whether federation cost any correctness on a
question set whose validity is exactly what the holdout is testing. Run it first
and you may have spent ten days characterising an artifact.

**Also worth being clear about what it is for.** It is a control, not a
competing design, and the expected outcome is a **tie** on correctness. The
claim it licenses is *federation matches merged-graph correctness while
preserving per-source provenance, avoiding ETL staleness and requiring no schema
reconciliation.* Anyone who starts this expecting federation to win has
misunderstood it and will report the wrong thing.

**Non-mechanical decisions it contains** — these are the substance and must not
be made unattended: how to reconcile two overlapping id spaces under one schema;
what to do with the 15 CAPEC `MAPS_TO` edges (spanning 10 distinct technique
ids) that do not resolve to a live ATT&CK object; how to count provenance
granularity lost in the merge.

**Unblocked by:** holdout ≥ 0.70.

### 2.2 The NVD/CWE third source and crossover curve — 12 days

**Why deferred:** it is the designated release valve. It is also the highest-value
item in the parent plan, which is precisely why it must not start before the
foundation under it is verified.

**Scope, when it starts:** only the CVE slice reachable from the 336 CWEs that
already bridge into CAPEC. Not all of NVD. In a relational or document store,
not a third property graph — the point is heterogeneity at the level of data
model, since Cypher and Gremlin are two dialects over one model and a database
audience will say so.

**Reduced form** if the holdout lands in 0.70–0.85: skip the new store entirely
and run the crossover curve on ATT&CK and CAPEC alone, ablating templates in a
fixed order from the 19 the bank exercises down to zero, with Arm G as the
endpoint. Five days instead of twelve, still produces the curve, loses the
data-model argument.

**Unblocked by:** holdout ≥ 0.85 for the full form, ≥ 0.70 for the reduced form.

### 2.3 Anything that quotes the headline number

Slides, abstracts, the pitch narrative, README claims. Every one of them will
need rewriting if the holdout moves the figure, and rewriting a number across
five documents is how inconsistencies like the 2.6 s / 1.6 s splice happen in
the first place.

**Unblocked by:** the gate, unconditionally.

---

## 3. Blocked on judgement, not on time

These look mechanical and are not. Doing them unattended produces output that
looks right and is not.

### 3.1 Judge consolidation — the design half

Plan 01 does **not** include this. Porting `scratchpad/judge_untruncated.mjs`
into `utils/evaluation/independent_judge/` is mostly mechanical, but three parts
are not:

- **Which existing judge it supersedes.** The repository already has
  `utils/evaluation/llm_judge/` (faithfulness only, never sees gold) and
  `utils/evaluation/harness/correctness_judge.py` (gold-aware, grades the
  agentic path). Adding a third path without deciding the relationship makes the
  evaluation story worse, not better.
- **Reading the re-judge disagreements.** The port must re-judge one completed
  arm and compare verdicts. Agreement is a number; *what a disagreement means*
  is a judgement, and a material disagreement is a standing kill criterion for
  everything downstream.
- **What the pinned judge model should be.** Changing it changes comparability
  with all 840 existing verdicts.

**Unblocked by:** a human sitting with it for half a day. It is a Step 2 item and
it should happen in week 1, attended.

### 3.2 The related-work section

**Deferred to Plan 04**, which is a separate research programme in a separate
repository, and which can start immediately in parallel.

**Why it is not overnight-safe despite being pure writing:** Positioning is the
0/4 axis. The failure mode of unattended scholarly writing is fabricated
citations, and a related-work section full of plausible references that do not
exist converts a gap into a credibility problem. It is strictly worse than
leaving the section empty.

**Unblocked by:** nothing. Start Plan 04 now.

### 3.3 Deleting the dead template methods

`_node_lookup` (`utils/specialists/cypher/builder.py:395`) and `_capec_lookup`
(`utils/specialists/gremlin/builder.py:243`) have no production callers.
`_capec_lookup` is still referenced by
`utils/specialists/tests/test_gremlin_validator.py:215`.

Plan 01 marks them with comments and does not remove them. Deletion is a
behavioural change to a frozen component, and the freeze is what makes the
holdout meaningful.

**Unblocked by:** the holdout completing. Then it is a five-minute cleanup.

---

## 4. Blocked on infrastructure

### 4.1 Demo deployment and screencast — 3 days

**Target:** `ariadne.brendondgr.com`. Scheduled for 26–28 August in the parent
plan, off the critical path, because it is the only item tied to a hard external
deadline (EACL Demos, 22 September) that does not depend on the gate.

Three things to settle before starting, none of which are urgent today:

- **The deployment is not just the app.** Neo4j and the Gremlin Server run
  alongside it — size the host for both backends plus ~9,100 nodes and ~34,600
  edges. `docker/docker-compose.yml` already defines the stack; its `web`
  service is `profiles: [disabled]` and needs enabling.
- **The LLM path needs a serve-or-omit decision.** Either expose a reachable
  Gemma 4 31B endpoint or ship deterministic-only. The latter is defensible,
  arguably the better story given the findings, and removes the demo's only
  unbounded cost.
- **The URL identifies you.** Fine for EACL System Demonstrations
  (single-blind). Breaks anonymity for the EACL Industry Track (double-blind)
  and ARTMAN (anonymous, desk-reject otherwise), both of which would need a
  neutral mirror or an anonymised screencast.

**Unblocked by:** §1.1, for the artifact release the demo tracks require.

---

## 5. Deliberately not being done at all

Recorded so nobody revives them thinking they were overlooked.

### 5.1 A benchmark or resource-track contribution

The audit's Path 2. Dropped. CTIArena (arXiv 2510.11974) now occupies that
ground with 691 practitioner-reviewed QA pairs across nine tasks, and a
150-question bank cannot compete on resource-track terms. The question bank
remains valuable as *evaluation infrastructure for this paper* — it is just not
the contribution.

### 5.2 Rehabilitating the agentic retrieval loop

`ORCH_MAX_HOPS`, the assess/replan machinery, `ORCH_CHASE_FACETS`, the
`ORCH_ASSESS_MODE=llm` critic seam. The loop is structurally inert at
`max_hops=1` and effectively inert even at 5, and `LLMCritic` is a bare type
alias (`utils/orchestration/agents/assess/policy.py:40`) whose only production
caller passes no critic (`main.py:199`).

Document it accurately as an inert seam. Do not defend it, do not make it work.
Making it work is a feature, and the audit's judgement that "the marginal return
on engineering has gone negative" is correct. Plan 01 Task 9 corrects the
`.env.example` description of it, which is a documentation fix and not a
rehabilitation.

### 5.3 New system features of any kind

Step 7 of the parent plan is the sole engineering exception, and it exists to
serve a measurement rather than to improve the tool. Anything else — better
templates, more intents, a nicer UI, additional entity types — buys a better
tool and no better paper, on a calendar that has 10 days of slack.

### 5.4 Top-tier security venues

NDSS, IEEE S&P, USENIX Security. Out of reach on the current evidence, and
chasing them costs weeks that the related-work section and the merged-graph
control need. Both USENIX cycles are additionally unreachable on registration
deadlines.

---

## 6. Ordering summary

| When | What | Gated on |
|---|---|---|
| Tonight | Plan 01 | nothing |
| Now, parallel | Plan 04 (separate repo) | nothing |
| Week 1 | License email; model fields; judge consolidation, attended | humans |
| After Plan 01 | Plan 02 — the holdout | `freeze/holdout-v1` |
| ~21 Aug | **THE GATE** | holdout result |
| Late Aug | Demo deployment | license |
| Sep | Merged-graph control | gate ≥ 0.70 |
| Oct | NVD + crossover | gate ≥ 0.85, or reduced form |
| Oct | Pitch assembly | everything |

If an item is not in this table and not in Plans 01, 02 or 04, it is not being
done this cycle.
