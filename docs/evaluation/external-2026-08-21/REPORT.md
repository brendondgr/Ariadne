# Does Ariadne survive questions it did not write?

Every accuracy figure this project has published came from a question bank Ariadne co-authored. This is the first measurement on questions written by somebody else — two published benchmarks — and the first where **no language model grades the answer**. The score is set arithmetic over ATT&CK identifiers.

## 1. What was asked, and what had to be left out

- **182 questions** survived to be asked.
- CTIBench contributed 60 rows; **14 name software this deployment does not hold** — almost all Mobile, and Ariadne loads Enterprise ATT&CK only.
- Of the gold answers on the software it does hold, **291 of 397** are present in the graph. Nothing here is measuring a hole in the data.
- AttackQA contributed up to 10 questions from each of its 14 enumerating question types, drawn with a fixed seed.
- The two slowest versions ran a fixed **60-question** subset, because they have a language model in the loop and it answers one request at a time.

## 2. The result

| version | asked | found the right answers | said only right answers | got it exactly right |
|---|---:|---:|---:|---:|
| **Ceiling** — read straight from the graph | 182 | 0.986 | 0.810 | 0.703 |
| Ariadne, templates, plan handed to it | 182 | 0.684 | 0.770 | 0.445 |
| Ariadne, templates, plan handed to it *(same 60)* | 60 | 0.717 | 0.781 | 0.483 |
| Ariadne, no templates + model writes the answer | 60 | 0.995 | 0.810 | 0.733 |
| Ariadne, **question text only** — it plans for itself | 60 | 0.613 | 0.767 | 0.450 |

**"Found the right answers"** is recall: of everything the benchmark says is correct, how much did the answer contain. **"Said only right answers"** is precision: of everything the answer named, how much the benchmark agrees with. **"Got it exactly right"** means the answer matched the benchmark's list with nothing missing and nothing extra.

## 3. What was predicted before the run, and what happened

**H1 — Ariadne retrieves what the graph holds.** Predicted within 0.05 of the ceiling. Measured **-0.303**. **refuted**

> The ceiling itself only reaches 0.986 against the benchmark, which is the next point.

**H3 — the benchmarks are out of date, and that is not Ariadne's fault.** The ceiling — a direct read of the graph, with no retrieval in the way — scores **0.810** for precision. It names far more than the benchmark lists because ATT&CK has grown since the benchmark was published. Any arm's low precision has to be read against that number, not against 1.0.

**H2 — external questions score below internal ones.** The project's own banks produce 0.92–1.00. External recall is **0.684** — **outside** it, so the drop the co-authorship figure predicted is real.

**H4 — being handed the plan is worth something.** On the same 60 questions, the version given a plan scores **0.717** and the version that must work out its own plan from the question scores **0.613** — a difference of **-0.104**.

This is the number with the most consequence for the write-up. Every published Ariadne figure is a plan-given figure. The gap here is how much of that number is the retrieval and how much is the plan the bank supplied.

**Aside — templates against the narrator.** On the same 60: templates 0.717, narrator 0.995.

## 4. Which question types worked and which did not

Read the last column. A zero means Ariadne did as well as the data allows. A large negative number means the answer is sitting in the graph and Ariadne did not bring it back.

| question type | asked | ceiling | Ariadne | shortfall |
|---|---:|---:|---:|---:|
| campaigns for software | 10 | 1.000 | 0.000 | -1.000 **✗** |
| groups for software | 10 | 1.000 | 0.000 | -1.000 **✗** |
| software for campaign | 10 | 1.000 | 0.000 | -1.000 **✗** |
| software for group | 10 | 1.000 | 0.000 | -1.000 **✗** |
| techniques for group | 10 | 0.990 | 0.295 | -0.694 **✗** |
| techniques for campaign | 10 | 0.988 | 0.326 | -0.661 **✗** |
| campaigns for group | 8 | 1.000 | 1.000 | +0.000 ✓ |
| campaigns for technique | 9 | 0.970 | 0.970 | +0.000 ✓ |
| groups for campaign | 10 | 1.000 | 1.000 | +0.000 ✓ |
| groups for technique | 10 | 0.983 | 0.983 | +0.000 ✓ |
| software for technique | 10 | 0.885 | 0.885 | +0.000 ✓ |
| techniques for software | 55 | 0.998 | 0.998 | +0.000 ✓ |
| techniques parent | 10 | 1.000 | 1.000 | +0.000 ✓ |
| techniques sub | 10 | 1.000 | 1.000 | +0.000 ✓ |

**8 of 14 question types match the ceiling exactly** — on those, Ariadne returns everything the data holds. **4 return nothing at all.**

Split by benchmark, same version:

- **attackqa** — 137 questions, recall 0.597, exact 0.372
- **cti-ate** — 45 questions, recall 1.000, exact 0.667

## 6. What this does not show

1. **Nothing about human phrasing.** Both benchmarks are machine-written. A search on 2026-08-21 found no human-authored ATT&CK question set anywhere public. That gap is still open.
2. **Enterprise ATT&CK only.** Mobile and ICS questions were excluded, not failed.
3. **CAPEC is untouched.** Neither benchmark covers it, so half of what the system does is unmeasured here.
4. **Enumerating questions only.** Every question here has a list for an answer. Open-ended asks are not represented.
5. **The benchmarks are older than the data.** That is what the ceiling row is for, and why no number here should be read against a perfect 1.0.

