# Pitch numbers audit — 2026-09-10

Second verification pass over `Ariadne_October_Pitch.pptx` and
`Ariadne_October_Pitch_Script.docx`, following the one logged in
[`october-pitch-plan.md`](october-pitch-plan.md) §7 (2026-09-06).

Two weeks of experiments have landed since that pass: `EXP-2026-09-009`,
`-010`, `-011`, `-013`, `-014`, `-015`, `-016`, plus the record cleanup of
2026-09-09. This pass re-checks every slide number against the record as it
stands today and applies the corrections below.

Every figure quoted here is read from a committed manifest or `RESULTS.md`.
Per [`../research/CURRENT.md`](../research/CURRENT.md), no withdrawn figure is
quoted without its replacement.

---

## 1. The cost figure does not reproduce — corrected

**Was, slide 5 and script:** "hand-written took four seconds. Letting the AI
write the queries took two days. Forty thousand times."

`EXP-2026-09-016` measured this directly instead of estimating it, and found
that the two halves are **different quantities**. Four seconds was one path's
wall clock; two days was another path's *summed machine time* across 24
workers. Dividing them inflates the ratio by the worker count before any real
effect. Reconstructing the same construction on this experiment's numbers gives
31,252x, which identifies how the figure was formed and shows it is not stable
across nights.

**The two-day half does reproduce** — summed machine time for the
AI-writes-the-query path is 2.93 days.

Held to one quantity, same 284 questions, 24 workers, one machine:

| path | wall clock | model calls | ratio | judged correctness |
|---|---|---|---|---|
| hand-written templates | 8.1 s | 0 | 1x | 0.4946 |
| schema-assembled | 1,168.6 s (19.5 min) | 159 | 144x | 0.6569 |
| AI writes the query | 11,407.8 s (3.2 h) | 413 | **1,408x** | 0.4043 |

Single analyst, one worker, 20 questions: hand-written 0.006 s median,
AI-written 182.0 s median. The schema-assembled latency cell is not reported
(`EXP-2026-09-016` `I-4`).

**Corrected to 1,400x**, stated as wall clock on both sides, with the
concurrency named. `EXP-2026-09-016` A-1, A-2, A-3, A-5.

## 2. The schema-assembled path is not model-free — corrected

**Was, backup slide B1:** "Reads the database's own structure (schema-assembled,
no templates, no model)".

That path disables the hand-written templates but keeps LLM planning, an LLM
specialist seam and the multi-hop retrieval loop. It made **159 model calls**
over 284 questions (`EXP-2026-09-016` A-1), and `EXP-2026-09-010` established
that its narrator calls a model. `CLAIMS.md` already carries this — `C-023` is
`partial` in part for this reason — but the slide said otherwise.

Corrected to "no model writes a query", which is the property that is actually
true and is the one slide 3 claims. The cost line now names the call counts.

**Slide 3's two rules are unaffected.** No model writes a query on any path
except the AI-writes-the-query baseline, which is a comparator and is not
shipped.

## 3. Seeded repeats now exist — the Q&A answer was stale

**Was, script Q&A:** "What we have not done is repeat pipeline runs across
seeds."

That is no longer true, and the replacement is stronger:

| | seeds | across-seed SD |
|---|---|---|
| schema-assembled (`EXP-2026-09-011`) | 6 | 0.0074 |
| AI writes the query (`EXP-2026-09-009`) | 3 | 0.0089 |

The +0.168 gap is **7.3x** the three-SD band (`gap_over_3sd_ratio_six_seed`).

## 4. A grader reversal exists on the development half — prepared for, not hidden

`EXP-2026-09-009` found that on the **284 development questions**, the
`gemma4-31B-mtp` grader reverses the ordering: it scores the AI-written path
0.7054 against the schema-assembled path's 0.6698, and
`deterministic - llm_query` is **-0.2885** under it against **+0.1012** under
qwen. That grader emitted **two distinct values** across all 852 of its
judgments — it is precise, repeatable and measuring almost nothing, which is the
same pathology `EXP-2026-09-008` found when it dropped a grader for being unable
to resolve near-ceiling differences.

**The slide's claim is about the holdout and survives.** On the 288 held-out
questions both families agree on the ordering (`C-023` gemma gap 0.2143;
`C-012` holdout/gemma +0.0643). Slide 5 says "288 held-back questions" and
"two independent graders agree on the order", which is accurate as written.

No slide change. **A prepared Q&A answer has been added**, because an engineer
reading the repository will find `EXP-2026-09-009` and the answer should not be
improvised.

## 5. A superseded figure survived in a stage direction — corrected

Slide 7's notes and the script's cut list read "go straight to the 0.79". That
is the superseded `0.7877` identity retrieval figure, which §5 of the pitch plan
explicitly forbids quoting. Corrected to 0.66 (`EXP-2026-08-011` A-10).

## 6. A new cross-check worth having in the backup

`EXP-2026-09-016` A-5 graded the AI-written path on the 284 development
questions and got **0.4043**. `EXP-2026-09-007` reports **0.4039** for the same
path on the 288 held-out questions. A 0.0004 difference, on a different question
set, five days later, under a separately configured run. Added to backup slide
B1.

## 7. Checked and unchanged

| Slide number | Status |
|---|---|
| 0.6546 / 0.4862 / 0.4039 blind bar chart (slide 5, B1) | ✅ `C-023`, `EXP-2026-09-007` |
| Contrasts +0.168 / +0.251 / +0.082 with CIs (B1) | ✅ `C-023`, `C-012` |
| Zero made-up claims; 888 of 888 verified claims cited a record | ✅ `EXP-2026-08-014`; from the verifier, not a judge |
| 240 / 240 adversarial probes, 15 bypasses found and closed | ✅ `EXP-2026-08-016` |
| 0 vs 1,083 records rewritten, 9,138 nodes | ✅ `EXP-2026-08-017` |
| 3 sources, 2 languages, nothing changed when the third was added (n=117) | ✅ `EXP-2026-08-013` |
| 0.66 vs 0.13 identity retrieval recall, synthetic records, 72 types | ✅ `EXP-2026-08-011` A-10 |
| 12 / 12 refusals on the bridge | ✅ `EXP-2026-08-013` |
| Paraphrase 0 of 104; reword about half | ✅ `EXP-2026-08-020` |
| Co-authorship bias +0.03 to +0.05 | ✅ `C-021`; the 0.1472 reading stays forbidden |
| Federation not claimed more accurate than merging | ✅ `C-022`, `D-030` |
| July 0.9957 confined to backup B2 | ✅ |

## 8. Checked and deliberately not changed

- **`Q48` — the judge counts abstention boilerplate as fabricated claims.** It
  inflates hallucination counts in proportion to how often a path abstains. **No
  deck figure comes from that judge.** Slide 4's "0 claims / 0 invented
  mappings" and the script's "888 of 888" both come from the deterministic
  verifier. Nothing to correct; recorded so the next pass does not re-derive it.
- **`Q47` — the schema-assembled path silently runs model-free at the default
  timeout.** Audited clear: every run behind `C-023` sits at or below a 0.06
  fallback rate against a degraded reference of 0.70. No published figure is
  affected, so no deck figure is.
- **`Q45` — five CAPEC relationships are declared but not allowlisted**, and the
  schema-assembled path scores 0.0000 on the 34 development questions that need
  them. Fixing it would *raise* the margin slide 5 quotes. It needs a graded
  re-run on the LLM server and is **not** done in this pass. Until it is, every
  deck figure stands as measured, which is the safe direction.

---

*Corrections applied to the deck, the script and the plan in the same commit as
this file.*
