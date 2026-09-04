# RESULTS — EXP-2026-09-005

## The gap survives, and the grader did not notice the repair

| | pre-repair | post-repair | move |
|---|---:|---:|---:|
| deterministic, judged correctness | 0.4934 | **0.4946** | +0.0012 |
| generic, judged correctness | 0.6576 | **0.6569** | −0.0007 |
| **judged gap** | 0.1642 | **0.1623** | −0.0019 |
| deterministic, model-free recall (dev) | 0.4492 | **0.5176** | **+0.0684** |
| generic, model-free recall (dev) | — | 0.6058 pooled / 0.6756 reweighted | — |

568 judgments per arm, 284 cases, **zero grading failures**. Order effect
+0.0043 for deterministic and −0.0063 for generic — both inside the ~0.01
EXP-2026-08-022 measured, and counterbalancing removes them.

**The headline claim is now defensible.** The 0.1642 gap was measured against a
baseline carrying three retrieval defects; repaired, the gap is 0.1623. A
reviewer can no longer say the template arm was simply broken.

## The finding nobody asked for

The deterministic arm's **retrieval improved by 0.0684** on these same 284
questions and its **judged score moved by 0.0012** — inside the grader's own
measured spread of 0.0050 (EXP-2026-09-002 I-5). Statistically, the grader did
not see the repair at all.

Three defects were fixed. 24 questions became answerable that the graph could not
previously answer. Property reads went 0.3958 → 0.6395. A category's members are
now retrieved instead of its status. **None of it reached the score a reader of
the answers assigns.**

That is a claim about the composer, and it is consistent with what this project
already recorded: the deterministic composer's `summarize()` is an id line, and
`ariadne-e2e-sufficiency-ceiling` names exactly this ceiling. Retrieval is no
longer the binding constraint on the deterministic arm — **the answer is**.

## What this does and does not license

**Does:** quoting 0.1623 with the baseline's defects named and repaired. Saying
that schema-assembled queries beat a hand-written template library on the
templates' own catalogues, at a grader-measured 0.16 and a model-free 0.09
pooled / 0.16 reweighted.

**Does not:**
- Any claim about `llm_query`. It was not re-run; its 0.3712 remains a budget
  artifact and must not be cited.
- Any claim that the generic advantage is uniform. On multi-hop (D6) the
  deterministic arm **leads**, 0.3548 to 0.0717.
- Any claim about the holdout, which stays sealed.
- Reading +0.0684 as the repair's full value: two scorer defects recorded in
  EXP-2026-09-004 (id vocabulary, abstention credit) still depress both arms,
  the first by 0.185 on the subset where it was measured.
