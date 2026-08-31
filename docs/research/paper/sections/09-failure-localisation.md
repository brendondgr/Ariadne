# §9 — Failure localisation: where an LLM-planned pipeline actually loses

**Status:** drafted 2026-08-31, closing `Q24`.
**Claim:** `C-016`. **Prior art it must answer:** Leung et al., EACL 2026.
**Numbers:** recomputed today from the committed artifacts of `EXP-2026-07-002`
via `utils/evaluation/failure_terminus.py`; none is quoted from prose.

---

## 0. A correction that must land before the argument

`C-016` and `EXP-2026-07-002/RESULTS.md` both state *"26 of 36 failures were
planning or retrieval; only 2 were faithfulness."* **That figure does not
reproduce from the committed artifacts.** Re-running the classifier over the
same directory gives **28** non-CORRECT of 120 — which matches the manifest's
own verdict counts (92 CORRECT, 14 PARTIAL, 14 INCORRECT) — with this
distribution:

| terminus | n |
|---|---|
| `incomplete_retrieval` | 11 |
| `projection_gap` | 7 |
| `unfaithful` | **4** |
| `pipeline_timeout` | 4 |
| `gold_cap_collision` | 2 |
| **total** | **28** |

So the denominator is 28, not 36, and unfaithfulness is **4**, not 2. The "36"
almost certainly comes from an earlier judge run, exactly as `C-018` did.
**Quote 4 of 28. Do not quote 2 of 36.** The argument below is stronger with the
corrected numbers, so nothing rests on the discrepancy — but a claim whose
headline figure is unreproducible cannot be defended at all, and this one was.

---

## 1. The apparent contradiction

Leung, Belbahri, Sui, Labach, Zhang, Rose & Cresswell, *Classifying and
Addressing the Diversity of Errors in Retrieval-Augmented Generation Systems*,
EACL 2026, pp. 3185–3207, walk pipeline stages in order and stop at the earliest
error — the same mechanism this project uses — over 832 and 1,222 erroneous
responses, and validate the attribution by intervening on the weak stages and
re-running. Their distribution:

| stage | DragonBall-EN | CLAPnq |
|---|---|---|
| Chunking | 29.7% | — |
| Retrieval | 31.5% | 21.7% |
| Reranking | 7.1% | 2.0% |
| **Generation** | **32.7%** | **76.4%** |

Read naively against *"only 4 of 28 were unfaithful"* (14.3%), our result looks
like a flat contradiction of the only comparable published measurement.

**It is not, and the reason is not "different pipelines."** That sentence is
what a reviewer expects and it concedes the point. The comparison is invalid as
stated for a specific, checkable reason: **the two taxonomies do not partition
the same space.**

---

## 2. Mapping like-for-like

`failure_terminus.py` splits the generation stage into two classes that Leung
et al.'s "Generation" holds together:

- **`projection_gap`** — the gold identifiers *are* in the retrieved evidence and
  the answer never states them. The system had the facts and did not say them.
- **`unfaithful`** — the answer states things the evidence does not support. The
  system said things it did not have.

Both are generation-stage errors under their taxonomy. Comparing our
`unfaithful` alone against their `Generation` compares our narrowest category
against their broadest, and that — not a difference in the systems — produces
most of the apparent gap.

Mapped onto their stages, and excluding the 2 `gold_cap_collision` cases (a
harness artifact where the gold asserts a record-count window the retrieval
profile deliberately lifts, not a system failure), our 26 real failures are:

| their stage | our terminus classes | n | share |
|---|---|---|---|
| Chunking | *(no analogue — a structured store has no chunks)* | 0 | — |
| Retrieval | `incomplete_retrieval` (11) + `pipeline_timeout` (4) | 15 | **57.7%** |
| Reranking | *(no analogue)* | 0 | — |
| **Generation** | `projection_gap` (7) + `unfaithful` (4) | **11** | **42.3%** |

**42.3% sits between their two settings** — above DragonBall-EN's 32.7%, well
below CLAPnq's 76.4%. Under a like-for-like mapping the contradiction largely
dissolves, and our distribution is unremarkable rather than anomalous.

**This is the honest reading and it costs us the headline as originally
written.** `C-016`'s claim that these pipelines fail predominantly at planning
rather than by hallucinating is **not** supported at the stage level: 42% of
failures are generation-stage.

---

## 3. What survives, and it is a better finding

Two things survive the correction, and both are stronger than the claim they
replace.

### 3.1 Within the generation stage, the split is the finding

Of 11 generation-stage failures, **7 are the answer failing to state facts it
retrieved** and **4 are the answer stating facts it did not have.** Their
taxonomy cannot separate these; ours does, and **the fixes point in opposite
directions**: `projection_gap` needs the composer to enumerate *more*,
`unfaithful` needs it to enumerate *less*. A system tuned against an aggregate
"generation error rate" would be pulled both ways at once.

So the defensible form of the original intuition is narrow and exact:
**fabrication specifically accounts for 4 of 26 failures (15.4%)** — a minority —
while the larger generation-stage share is *under*-statement, not invention.
That is a claim about a distinction their measurement cannot make, rather than a
disagreement with their numbers.

### 3.2 Adding a planning stage moves failure mass into it — measured within our own study

The strongest version of the argument does not need their pipeline at all. Run
the same classifier across three arms of the same study, same questions, same
grader, same night:

| arm | planner | writer | non-CORRECT | retrieval-side | generation-side |
|---|---|---|---|---|---|
| A — deterministic | authored | deterministic | **0** / 120 | 0 | 0 |
| F — `gold_llm` | **authored** | LLM | 10 / 120 | 0 | 2 `unfaithful` + 6 `other` |
| B — `llm` | **LLM** | LLM | 28 / 120 | **15** | 11 |

Substituting an LLM planner for an authored one, with extraction and synthesis
held constant, adds **18 failures — and 15 of them (83%) are retrieval-side**,
a class that is *empty* in both arms with an authored plan.

That is the claim, stated so it is testable rather than rhetorical:

> **Where a pipeline can fail depends on which stages it has, and adding an
> LLM planning stage adds failures almost entirely to that stage rather than
> redistributing existing ones.**

It also explains the direction of the difference from Leung et al. without
appealing to vagueness: their pipeline **has no planning stage**, so no share of
their distribution can land there, and the mass they attribute to retrieval and
generation is the mass we split three ways.

---

## 4. Three conditions that must travel with the numbers

**(a) Name the arm.** The 28 failures are **Arm B**, the condition in which a
language model plans. The shipped deterministic path has **0 of 120** failures
in this study, so a reader who takes 28/120 as the system's error rate has
misread it by the whole width of the paper. `C-016` currently does not name the
arm and must.

**(b) Our generation stage receives verified claims, not passages.** The
composer is bound to a verified claim set, never to raw retrieved evidence, and
`C-005` measures what that is worth: 0.9690 → 0.9917 → 0.9957 as the binding
tightens, with PARTIAL verdicts going to zero. A generation stage that can only
restate checked claims has structurally less room to be unfaithful than one
writing from retrieved passages. This **predicts** a lower unfaithful share and
is not a post-hoc excuse — the mechanism was measured before the comparison
existed.

**(c) The classifier is ours and has been applied to one system.** Leung et al.
validate their attribution by intervening on the weak stages and re-running.
**We have not done that**, and it is the single cheapest thing that would raise
this from a plausible localisation to a validated one. It belongs in threats to
validity, and it is the natural follow-up experiment.

---

## 5. What to write, and what to stop writing

**Stop:** *"LLM pipeline failures are predominantly planning failures, not
hallucination failures."* At the stage level that is false — 42.3% of Arm B's
failures are generation-stage — and it rests on an unreproducible 2-of-36.

**Write instead**, in this order:

1. Adding an LLM planning stage adds 18 failures over an authored plan, **83% of
   them in planning and retrieval** — a class empty under an authored plan.
2. Within the generation stage, **under-statement outnumbers fabrication 7 to 4**;
   fabrication is **15.4%** of all failures. A taxonomy that merges the two
   cannot see this, and the two have opposite fixes.
3. Mapped to Leung et al.'s stages our generation share is **42.3%**, between
   their two settings. **Cite them as the method's prior art and as the
   comparison that makes ours interpretable — not as a result we contradict.**

---

## 6. Open items this leaves

- **`C-016` needs rewriting** to the form in §5, with the arm named and the
  corrected denominator.
- **`EXP-2026-07-002` needs an AMENDMENTS entry** recording that its 26-of-36
  figure does not reproduce.
- **The intervention check** (§4c) is unrun and is the obvious next experiment:
  fix the stage the classifier blames and confirm the failures it blamed go away.
