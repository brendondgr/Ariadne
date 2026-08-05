# Ariadne End-to-End Evaluation — 2026-07-26

A controlled, independently-judged evaluation of the full question-answering
pipeline over the 120-question golden catalogue, run against the live MITRE
ATT&CK (Neo4j) and CAPEC (Gremlin) graphs.

**Headline:** the pipeline went from **0.8946 correctness / 91 CORRECT / 11 answers
carrying hallucinations** to **0.9972 correctness / 120 CORRECT / zero
hallucinations** (deterministic) and **0.9957 / 119 CORRECT / zero INCORRECT**
(LLM-written). Eight defects were found and fixed. The single largest remaining
lever is **LLM planning**, which costs ~0.14 correctness on its own.

| Document | Contents |
|---|---|
| `README.md` (this file) | Method, results, defects, verdict, reproduction |
| `portability.md` | What survives a new dataset / new schema |
| [`../experiments/untruncated/root-cause.md`](../experiments/untruncated/root-cause.md) | The mid-investigation root-cause analysis |

---

## 1. Results

All figures are means over 120 questions, each graded by a **separate Sonnet 5
agent** (one per question, 840 agents across the seven study runs, plus 120 more
for the Arm G control run added afterwards) against the question's gold
assertions *and* its full retrieved evidence.

| # | Configuration | Plan | Extract | Synthesize | corr | compl | faith | ground | C/P/I | halluc |
|---|---|---|---|---|---|---|---|---|---|---|
| — | **Committed baseline** (truncated) | gold | determ. | LLM | 0.8946 | 0.8952 | 0.9558 | 0.9575 | 91/27/2 | 11 |
| **A** | **Deterministic** | gold | determ. | determ. | **0.9972** | **1.0000** | **0.9993** | **1.0000** | **120/0/0** | **0** |
| **F** | **Determ. + loop + LLM writer** | gold | determ.+loop | LLM (claims) | **0.9957** | 0.9990 | 0.9960 | 0.9992 | **119/1/0** | 3 |
| D | Determ. + LLM writer | gold | determ. | LLM (claims) | 0.9917 | 0.9958 | 0.9936 | 0.9975 | 119/0/1 | 1 |
| C | Determ. + LLM writer (evidence-grounded) | gold | determ. | LLM (evidence) | 0.9690 | 0.9672 | 0.9921 | 0.9983 | 110/8/2 | 3 |
| E | LLM-planned + loop | **LLM** | determ.+loop | LLM (claims) | 0.8560 | 0.8877 | 0.9575 | 0.9729 | 97/7/16 | 15 |
| B | LLM-planned | **LLM** | determ. | LLM (claims) | 0.8505 | 0.8692 | 0.9683 | 0.9750 | 92/14/14 | 12 |
| **G** | **Templates disabled** (generic primitives) | **LLM** | generic primitives + loop | LLM (claims) | **0.6388** | 0.6802 | 0.9658 | 0.9788 | 64/14/42 | 7 |

Cost and volume, same 120 questions:

| Arm | wall clock | evidence records | related neighbours | answer coverage |
|---|---|---|---|---|
| A deterministic | **2.6 s** | 1,840 | 839 | **1.0000** |
| F determ. + loop + LLM | 533 s | **1,080** | 866 | **1.0000** |
| E LLM-planned + loop | 1,043 s | 3,449 | 2,000 | — |
| B LLM-planned | 1,020 s | 2,814 | 621 | 0.7989 |
| G templates disabled | 915 s | 252 | 1,749 | 0.8979 |

> **Read this table twice.** Arm F retrieves the *least* evidence of any LLM arm
> and scores the *highest*. Arm B retrieves 2.6× more than Arm F and surfaces
> 20% less of the gold. Throughout this evaluation, precision in *planning* beat
> volume in *retrieval*, every time.

### The two deltas, side by side

The matrix isolates two independent effects, and they are an order of magnitude
apart. Stated in the same direction — treated arm minus its reference, so both
are negative:

| Effect | Contrast | Delta (correctness) |
|---|---|---|
| Disabling the **templates** | **G − F** (0.6388 − 0.9957) | **−0.3568** |
| Swapping in **LLM planning** | **B − C** (0.8505 − 0.9690) | **−0.1185** |

Losing the hand-written templates costs **3.0× what LLM planning costs**. The
templates, not the planner, are where this system's accuracy lives.

**What Arm G is, precisely.** It is a *generic-primitives* control: the
`SPECIALIST_GENERIC_ONLY` gate disables every hand-written intent template and
leaves only the schema-driven primitives — describe an anchor, walk one
relationship the source card declares, scan a label
([`cypher/builder.py`](../../../utils/specialists/cypher/builder.py) `_build_generic`).
It answers the way the system would have to on a graph nobody has authored
templates for. It is **not** free-form LLM query generation — no LLM writes
Cypher or Gremlin in any arm of this study, and that experiment has never been
run.

### The three findings that matter

1. **Un-truncating retrieval helped, and was never the regression.** Isolated by
   Arm C against the baseline (identical config, only the caps lifted):
   **+0.067 correctness, +0.067 completeness, +0.022 faithfulness, +0.032
   groundedness** — positive on all four.
2. **LLM planning is the whole regression.** Arm B − Arm C = **−0.1185
   correctness** (0.8505 − 0.9690), with identical extraction and identical
   synthesis. The baseline never had to *find* its cross-source join;
   `seed_from: q1` is authored into the gold.

   > **Corrected 2026-08-04.** This finding previously read −0.196. That figure
   > was computed against an *earlier* judge run in which Arm C scored 0.9620
   > (110/8/2 became 109/9/2 — see `changelog.jsonl`), before the eight defect
   > fixes below. It is not reproducible from the post-fix table above, which is
   > the one printed here. Quote **−0.1185** within this run. The qualitative
   > finding is unaffected: with extraction and synthesis held constant, LLM
   > planning is still the dominant single effect in the matrix, and against the
   > best deterministic-planned arm the gap is larger still (F 0.9957 − E 0.8560
   > = **−0.1397**, which is the ~0.14 quoted in the headline).
3. **The accuracy-vs-readability trade is not real.** Arm F scores 0.9957
   against the deterministic ceiling's 0.9972 — a 0.0015 gap — with **zero
   INCORRECT**, full gold coverage, and readable analyst prose instead of a
   claim table. It only became true once the narrator was bound to the
   *verified claims* rather than left to re-read the raw evidence.

### By category

Baseline weak categories, and where they landed:

| Category | n | baseline | Arm A | Arm F | Arm E (LLM-planned) |
|---|---|---|---|---|---|
| C-ABS (abstraction hierarchy) | 3 | 0.17 | **1.000** | **1.000** | 0.283 |
| C-CSQ (consequences) | 2 | 0.35 | **1.000** | **1.000** | 0.525 |
| A-SW (software techniques) | 3 | 0.45 | **1.000** | **1.000** | 0.783 |
| F-CWE (federated CWE) | 5 | 0.59 | **1.000** | **1.000** | 0.524 |
| A-GRP (group techniques) | 4 | 0.76 | **1.000** | **1.000** | 1.000 |
| C-LKP (attribute lookup) | 5 | 0.88 | **1.000** | 0.990 | 0.980 |
| F-CTM (federated mitigations) | 10 | 0.92 | 0.997 | 0.965 | 1.000 |
| F-PART (degraded sources) | 4 | 0.91 | **1.000** | **1.000** | 0.237 |

Every category the independent panel previously flagged is now at or near 1.0 in
both recommended arms. The LLM-planned column shows where planning failure
concentrates: hierarchy, federated joins, and degraded-source scenarios.

---

## 2. Method

### Arms

Seven full runs, each 120 questions in fixed order against the same two graphs.
Three independent variables:

* **Plan** — the catalogue's *authored* plan (correct seeding, zero variance) vs
  an *LLM planner* working from raw question text.
* **Extract** — deterministic template router, optionally with the
  **facet-chasing retrieval loop**.
* **Synthesize** — deterministic composer, LLM narrator reading *evidence*, or
  LLM narrator reading *verified claims*.

**Arm G is a later eighth run**, not part of the original matrix. It moves a
fourth variable the seven-arm design held fixed — whether the hand-written
intent templates exist at all — so it is reported in the same tables but should
be read as a control against Arm F rather than as a cell of the 2×2×3 design.

Common to every arm: the **un-truncation profile**, which lifts every retrieval,
synthesis-evidence and judge-artifact bound via env keys whose defaults are the
committed values, so a normal run is unaffected.

### Judging

Each answer is graded by one independent Sonnet 5 agent against the gold
assertions and the full retrieved evidence, scoring correctness, completeness,
faithfulness, groundedness, and listing every unsupported claim. Cross-model on
purpose: the pipeline's own model must not grade its own output.

### Failure terminus

`utils/evaluation/failure_terminus.py` classifies each graded case by **the last
stage at which the gold answer was still recoverable**, computed from the
artifacts rather than from judge prose:

`gold_cap_collision` → `pipeline_timeout` → `retrieval_empty` → `seed_lost` →
`wrong_query` → `incomplete_retrieval` → `property_gap` → `projection_gap` →
`unfaithful` → `other`

This is what converted "the judge says this is wrong" into "*this stage* lost
the information," and it is what made every defect below findable. It showed
that only **2 of Arm B's 36 failures were faithfulness**; 26 of 36 were
planning/retrieval — the opposite of the intuition that LLM answers fail by
making things up.

---

## 3. Defects found and fixed

| # | Defect | Where | Effect |
|---|---|---|---|
| 1 | Narrator blind to execution state | `llm_composer.build_evidence_context` | hallucinations 12 → 3 |
| 2 | Composer never projected record properties | `synthesis/composer.py` | 5 C-LKP INCORRECT → CORRECT |
| 3 | Neighbour ids left unnormalised | `gremlin/normalizer.py` | C-HIE-03 PARTIAL → CORRECT |
| 4 | Declared join never reached its sub-questions | `planner/schema.py` | `seed_lost` 8 → 0 |
| 5 | Evidence doubled every retrieval hop | `orchestration/state.py` | 90 results → 14 |
| 6 | Enumeration claim disabled by the un-truncation profile | `assess/facets.py` | E: 0.8150 → 0.8560 |
| 7 | Relationship direction stated backwards | `synthesis/composer.py` | 2 of F's 3 hallucinations |
| 8 | Bounded-scan gold collided with the lifted cap | `experiment_untruncated.py` | 2 INCORRECT → CORRECT |

The three most instructive:

**#1 — the narrator invented reasons for absence.** `build_evidence_context` had
three branches: records shown, `ok`-with-zero-rows listed as empty, and
**everything else silently dropped**. A sub-question that errored, timed out, or
was dependency-skipped never reached the prompt, and `evidence.skipped` /
`unsupported` / `sequencing` / `partial` — which the federation already
populates — were never read at all. So the model saw an unanswered request with
no explanation and supplied a plausible one: *"None of the live graph sources
cover this request"* for what was actually a **timeout**. Fixed by emitting an
execution record and forbidding invented absence-explanations, unread counts,
and unsupported tactic groupings.

**#4 — a declared join never reached its sub-questions.** The LLM planner emits
the plan-level join correctly but leaves each participating sub-question's own
`join_key` null. The router keys on the *sub-question's* field, so the bridge hop
silently downgraded from `capec_maps_to` (which produces join values) to
`describe` (which produces facet *counts*). No join values → the dependent hop
ran unseeded → it answered a broader question than the analyst asked. **19 of Arm
B's 36 failures.** The planner was never confused; two representations of the
same fact disagreed.

**#5 — evidence doubled every hop.** The specialists subgraph shares
`PipelineState`, inherits the accumulated `results`, and returns them — which the
parent's `operator.add` reducer appended a second time. One question came back
with **90 results built from 14 distinct sub-questions** (16×, 8×, 4×, 2×). A
single-pass run never notices; it is only reachable once the loop iterates, which
it never did before this work.

---

## 4. The retrieval loop

The app's documented workflow is *plan → retrieve → assess → re-plan until
confident*. **It never ran.** A traced execution at `ORCH_MAX_HOPS=5` emitted one
plan, one evidence, one assess, then answered. Three stacked causes:

1. The local `.env` pins `ORCH_MAX_HOPS=1`, so the front end is single-pass **by
   configuration**.
2. Even at 5, sufficiency was decided purely by cross-source join closure, with
   `if not plan.joins: sufficient=True` — so **any single-source question was
   complete by construction after one hop**, and a `describe` returning only
   facet counts looked complete.
3. `expandable_facets()`, which knows "MITIGATES × 6 counted, never fetched", was
   defined and **never called**.

`ORCH_CHASE_FACETS` (default **off**) plus `assess/facets.py` closes this:
relevance-rank the facet frontier against the request and the plan's declared
entities, cap it per hop, and emit ordinary sub-questions so expansions run the
same draft → gate → execute → normalise path.

**Measured effect depends entirely on plan quality.** On top of an *LLM* plan the
loop is roughly neutral (0.8505 → 0.8560, buying completeness and costing
faithfulness). On top of an *accurate* plan it is part of the best result
(Arm F, 0.9957, coverage 1.0000). The loop compensates for weak planning; it does
not replace it.

---

## 5. Recommendation

**Demo Arm F, keep Arm A as the reproducible fallback.**

* **Arm A (deterministic)** — 0.9972, 120/120, zero hallucinations, **2.6 s** for
  the whole catalogue, byte-reproducible. The right answer when someone asks you
  to run it again on stage, and the right regression gate in CI.
* **Arm F (deterministic extraction + LLM writer)** — 0.9957, 119/120, zero
  INCORRECT, full gold coverage, readable prose. The right answer when a human
  has to read the output.

**Do not demo the LLM-planned path.** At 0.8560 with 15 hallucinations it loses
to its own deterministic baseline in front of an audience.

Before any demo:

1. **Decide the loop explicitly.** `ORCH_MAX_HOPS=1` and `ORCH_CHASE_FACETS`
   unset means the app today does **not** do what these numbers measure.
2. **Reload the CAPEC/Gremlin fixture and verify counts.** It was found empty
   (0 nodes) at the start of this session; every CAPEC and federated question
   would have returned "no records".
3. **Probe the LLM with a real completion**, not `/v1/models`. `skynet` reported
   healthy while returning 502s.

### Open work, in priority order

1. **LLM planning** — the single largest lever, ~0.14 correctness. The specific
   remaining defect: the router downgrades *single-source* questions to
   `describe` because no join declaration exists to reconcile against. Fix by
   routing on the sub-question's declared `entities` (which name the
   relationship) rather than on surface phrasing.
2. **Pipeline timeouts** — 6 of 120 in the LLM arms finish `partial` on the
   deadline. Raise it or parallelise the stages.
3. **Narrator count discipline** — the one remaining PARTIAL in Arm F (F-CTM-01)
   recomputed a count and said "five techniques" where the evidence held six.
4. **Open-ended questions are unmeasured.** All 120 golden questions are
   anchored. See `portability.md`.

---

## 6. Reproduction

```bash
# 0. Fixtures must be live and non-empty
uv run main.py --dataset capec --graph gremlin
uv run main.py --dataset attack --graph neo4j

# 1. Run an arm (writes answers + full evidence per question)
uv run python -m utils.evaluation.experiment_untruncated \
  --arm deterministic --root docs/evaluation/experiments/<name> --workers 4
# arms: deterministic | gold_llm | llm | llm_loop | gold_loop_llm

# 2. Judge it — 120 independent Sonnet agents, one per question
#    scratchpad/judge_untruncated.mjs, via the Workflow tool
#    args: {"dir": "<root>/<arm>/answers", "arm": "<name>", "ids": [...]}

# 3. Locate where failures terminate
uv run python -m utils.evaluation.failure_terminus --root <root> --arms <arm>

# 4. Roll up
uv run python -m utils.evaluation.summarize_untruncated --root <root>
```

Artifacts per arm: `<id>.json` (answer + full retrieved evidence + executed
queries) and `<id>.judgment.json` (the independent verdict).

---

## 7. Limitations and threats to validity

Recorded so the numbers are not over-read.

* **All 120 questions are anchored.** Every one names an entity or an id. Nothing
  here measures open-ended analyst questions, which is precisely where the
  template router is weakest.
* **The gold set is small and fixed.** 120 questions, hand-authored alongside the
  system. Categories have 1–10 members, so a single case moves a category mean a
  lot.
* **The judge is a model.** Cross-model and evidence-grounded, but still an LLM.
  It occasionally penalised correct answers for citation-metadata reasons, and
  its verdicts are not perfectly stable across runs.
* **Arm A's 120/120 splices two judge runs** — 118 verdicts from the pre-scan-fix
  run plus 2 re-judged — justified only because the other 118 artifacts were
  verified materially identical.
* **One model, one day.** `skynet` (vLLM). An earlier Arm B on the relay's other
  model ran ~6× slower and was discarded. Nothing here generalises to other
  models without re-running.
* **Two questions overflow the context.** C-SCN-01 (558 records) and F-CWE-05
  (1,470 records) exceed skynet's 64k window under the un-truncation profile and
  fall back to the deterministic narrative.

### Method traps worth remembering

* **Provenance timestamps make every artifact differ.** A naive artifact diff
  reported all 120 cases changed after a one-line edit. Compare evidence volume,
  claim text, and coverage instead — the real answer was 2.
* **Module caching decides which code a background run used.** A run launched
  before an edit stays a clean pre-fix control; one launched *during* an edit is
  silently a mix of both.
* **Judge agents drop 2–3 of 120 file writes.** Always backfill from the
  workflow's `journal.jsonl` before computing any aggregate.
* **Raising a cap is not free.** The un-truncation profile broke two things by
  raising limits other logic keyed off: the bounded-scan gold (#8) and the
  enumeration claim (#6).
