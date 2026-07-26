# What Went Wrong, and What Actually Fixed It

A follow-up to `summary.md`. The first pass concluded "un-truncated deterministic wins,
the LLM path regressed." That was the right ranking for the wrong reason, and the
comparison that produced it was invalid. This document corrects it, isolates each cause,
and records what each fix bought.

## 1. The comparison was invalid

The committed baseline (`docs/evaluation/independent-eval.md`) is produced by
`utils/evaluation/generate_e2e.py`, which replays each catalogue entry's **pre-authored
gold plan**. For a federated entry that plan hard-wires the cross-source join:

```json
{"source": "capec", "text": "Which ATT&CK techniques does CAPEC-150 map to?"},
{"source": "attack", "text": "What mitigations …for those mapped techniques?", "seed_from": "q1"}
```

`seed_from: q1` is the join. The baseline never had to *find* it.

Arm B replaced that plan with an LLM planner working from raw question text. So
`B − baseline` moved **two** variables at once — un-truncation *and* the planner — and
attributing the drop to un-truncation (as the first revision of `summary.md` did) was
wrong.

**Arm C (`gold_llm`)** is the missing control: the baseline's exact configuration with
only the bounds lifted. It retrieves byte-identically to Arm A (1,840 records / 839
related), so the decomposition finally holds.

| Contrast | Isolates | Δ correctness |
|---|---|---|
| C − baseline | **un-truncation alone** | **+0.0674** |
| B − C | **LLM planning alone** | **−0.1960** |
| A − C | deterministic vs LLM synthesis | −0.0120 |

Un-truncation was **strictly positive on all four metrics** (+0.067 correctness, +0.067
completeness, +0.022 faithfulness, +0.032 groundedness). It was never the regression.
The entire regression is the planner.

## 2. Locating failures mechanically

`utils/evaluation/failure_terminus.py` classifies each graded case by the **last stage at
which the gold answer was still recoverable**, computed from the artifacts rather than
from judge prose. Ordered ladder, first match wins: `gold_cap_collision`,
`pipeline_timeout`, `retrieval_empty`, `seed_lost`, `wrong_query`, `incomplete_retrieval`,
`property_gap`, `projection_gap`, `unfaithful`, `other`.

| Terminus | Arm A | Arm C | Arm B | Fix lives in |
|---|---|---|---|---|
| `incomplete_retrieval` | 1 | 1 | 11 | planner / router |
| `seed_lost` | 0 | 0 | 8 | planner / router |
| `projection_gap` | 0 | 0 | 6 | synthesis |
| `property_gap` | 5 | 0 | 0 | synthesis |
| `pipeline_timeout` | 0 | 0 | 5 | orchestration |
| `retrieval_empty` | 0 | 0 | 2 | planner / router |
| `unfaithful` | 0 | 4 | 2 | narrator |
| `gold_cap_collision` | 2 | 2 | 2 | gold / experiment |

**Only 2 of Arm B's 36 failures are faithfulness. 26 of 36 are planning/retrieval.**
This is what turned "the judge says it's wrong" into "this stage lost the information."

## 3. The four defects

### 3.1 The narrator was blind to execution state

`llm_composer.build_evidence_context` had three branches:

```python
if result.records:   → shown as records
elif result.ok:      → "EMPTY SUB-QUESTIONS (ran cleanly, zero records)"
# else:              → silently dropped
```

A sub-question that errored, timed out, or was dependency-skipped **never reached the
prompt**, and `evidence.skipped` / `unsupported` / `sequencing` / `partial` — which the
federation already populates — were never read at all. The model saw an unanswered part
of the request with no reason attached and supplied a plausible one:

- **F-CTM-08**: both hops skipped on a pipeline timeout → *"None of the live graph sources
  cover this request."* A **coverage** claim invented for a **timeout**.
- **F-PART-04**: "CAPEC source is down" sat in `answer.notes`, invisible to the narrator.
- **F-CTM-04 / C-MAP-02**: q2 returned 0 rows *because its seed was lost*; the narrator
  saw only "ran cleanly, zero records" and concluded *"no mitigations exist."*
- **A-GRP-02**: asserted absence about CAPEC — a source never queried.

**Fix.** Emit an execution record (failed/skipped hops with their real reason, whether a
dependent hop was seeded, run status), and forbid in both system prompts: inventing an
absence-explanation, stating an unread count, asserting absence for an unqueried source,
and assigning identifiers to tactics/phases the evidence does not carry.

**Bought:** hallucinations in the LLM-synthesis arm **12 → 3**; faithfulness 0.9779 →
0.9921; groundedness 0.9896 → 0.9983.

### 3.2 The deterministic composer never projected properties

A claim's text is `result.summary`, the normalizer's id-line template, which never reads a
record's own properties. All five C-LKP lookups answered `"Found 1 CAPEC record(s):
CAPEC-555."` while `Abstraction: Standard, Status: Stable` sat in the evidence.

**Fix.** `composer._attribute_claims` emits a citation-backed claim per record stating its
own short scalar attributes, bounded to lookup-shaped results (≤10 records) so a 300-row
scan is unaffected.

**Bought:** all 5 C-LKP cases INCORRECT → CORRECT.

### 3.3 Neighbour ids were left unnormalised

`gremlin/normalizer._normalize_neighbors` canonicalised the **anchor's** id but used the
**neighbour's** raw, so a `CHILD_OF` parent surfaced as `capec:attack-pattern:560` instead
of `CAPEC-560` and matched no gold assertion. Two committed tests had codified the bug —
one's own failure message read `expected CWE-89` while asserting `'cwe:89'`.

**Fix.** Canonicalise neighbour ids with `_expand_member_id` (fullmatch, so a composite
child like a mitigation/step keeps its own identity instead of collapsing to its parent).

**Bought:** C-HIE-03 PARTIAL → CORRECT.

### 3.4 A declared join never reached its sub-questions — the planner defect

This is the big one: **19 of Arm B's 36 failures**.

The LLM planner emits the plan-level join correctly:

```
joins: [JoinDeclaration(key='attack-technique-id', sources=['capec','attack'], …)]
```

but leaves each participating sub-question's own `join_key` **null**. The specialist's
template router keys on the *sub-question's* field:

```python
has_join = resolved.has_join or resolved.join_key == "attack-technique-id"
…
if has_join:  return self._capec_maps_to(resolved)   # produces join_values
if has_seeds: return self._describe(resolved)        # produces facet COUNTS
```

So the bridge hop silently downgrades to `describe`. Verified on the failing cases:

| Case | Arm B q1 template | join values | Arm C q1 template | join values |
|---|---|---|---|---|
| F-CTM-01 | `describe` (`.project("node","out","in")`) | **0** | `capec_maps_to` (`.out("MAPS_TO")`) | 6 |
| F-CTM-05 | `describe` | **0** | `capec_maps_to` | 3 |
| F-CTT-01 | `describe` | **0** | `capec_maps_to` | 2 |

No join values → the dependent hop runs **unseeded** → it answers a broader question than
the analyst asked and returns nothing useful. That cascade is `seed_lost` (8) plus most of
`incomplete_retrieval` (11).

Note what this is *not*: the planner is not confused about the join, and the LLM is not
hallucinating a plan. Two representations of the same fact disagreed, and routing depended
on whichever field the model happened to fill in.

**Fix.** `Plan.reconcile_join_keys()` pushes each declared join's key onto the
sub-questions whose source participates in it (never overwriting an explicit value),
applied at the end of `PlanningAgent.plan`. Routing now depends on what the plan
*declared* rather than on model formatting variance.

## 4. Where the numbers landed

| Run | Plan | Synthesis | corr | compl | faith | ground | C/P/I | halluc |
|---|---|---|---|---|---|---|---|---|
| Baseline (truncated) | gold | LLM | 0.8946 | 0.8952 | 0.9558 | 0.9575 | 91/27/2 | 11 |
| Arm A | gold | determ. | 0.9500 | 0.9534 | 0.9979 | 0.9992 | 112/1/7 | 0 |
| Arm C | gold | LLM | 0.9620 | 0.9618 | 0.9779 | 0.9896 | 109/9/2 | 12 |
| Arm B | LLM | LLM | 0.7660 | 0.7770 | 0.9479 | 0.9517 | 84/11/25 | 18 |
| **A + fixes** | gold | determ. | **0.9972** | **1.0000** | **0.9993** | **1.0000** | **120/0/0** | **0** |
| C + fixes | gold | LLM | 0.9690 | 0.9672 | 0.9921 | 0.9983 | 110/8/2 | 3 |

Against the committed baseline the fixed deterministic path is **+0.103 correctness,
+0.105 completeness, +0.044 faithfulness, +0.043 groundedness**, with hallucinations
11 → 0 and every PARTIAL eliminated.

**Deterministic synthesis is now strictly better than LLM synthesis on every metric.**
Before the property-projection fix the narrator was the only thing that could answer an
attribute question; now it is not, and it costs 3 hallucinations and 8 PARTIALs
(federated cases where the prose names a few mitigations instead of enumerating them —
`projection_gap`, the same fault the structured enumeration claim already solves).

## 5. What is still open

1. **Narrator absence-attribution, residual.** `F-PART-02` still reports a *boundary*
   sub-question as "ran cleanly but returned zero records". Boundary cases need routing to
   the NOT SUPPORTED block rather than EMPTY.
2. **LLM-prose under-enumeration.** The narrator prompt explicitly licenses naming "a
   representative few". That is the right trade only because the structured claims carry
   the full set — but it caps the LLM arm's completeness. Either drop the licence for
   enumerative intents or accept deterministic composition.
3. **Pipeline timeouts.** 9 of 120 in Arm B finished `partial` on the deadline. LLM
   planning + drafting + synthesis per question is simply slow; the deadline needs raising
   or the stages need to run concurrently.
4. **Scan-shaped caps.** Handled for the experiment (purely quantitative golds keep their
   row cap) but the underlying question — should a label scan be bounded by policy or by
   the question? — is a product decision, not an eval one.

## 6. Method notes (things that would have misled)

- **Timestamps make every artifact differ.** A naive artifact diff reported all 120 cases
  changed after a one-line change; every record's provenance carries a timestamp. Compare
  evidence volume, claim text, and coverage instead — the real answer was 2.
- **Module caching decides which code a background run used.** Arm C was launched before
  the fixes and therefore remained a clean pre-fix control; a run launched *during* an edit
  would have been a mix of both and silently invalid.
- **Judge agents drop 2–3 of 120 file writes.** Backfill from the workflow's
  `journal.jsonl` before computing any aggregate, or the means are quietly over a
  short set.
- **`skynet` health is not `/v1/models`.** It reported `health: failed` with HTTP 502 on
  completions while still listing. Probe with a real `/chat/completions` call.
