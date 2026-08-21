# Is it worth keeping the two databases apart?

**Run started** 2026-08-21T15:55:09+00:00 · **phases** 14, 0 failed

The project's pitch is that keeping MITRE ATT&CK and MITRE CAPEC in two separate databases, each spoken to in its own language, is worth the extra complexity. Nobody had ever checked, because the alternative — pour both into one database and ask it one question — had never been built. It has now.

## 1. The comparison

Every row below answered **the same questions**, with **the same plan**, and was graded by **the same grader in the same session**.

**Read the first two rows against each other and ignore the rest.** They are the same code with the same settings; the only difference is how many databases sit behind them, and neither has a language model in it, so neither wanders between runs. The third row disables the templates *and* hands the writing to a language model — it is the study's strongest version, but comparing it with the first row would be comparing two things at once.

| version | question set 1 | question set 2 |
|---|---:|---:|
| ONE database holding both catalogues | **0.9233** (0.857–0.983) | **0.9367** (0.870–0.990) |
| TWO databases, everything else identical | **0.9567** (0.910–0.993) | **0.9367** (0.873–0.987) |
| Two databases, no templates, answer written by a language model | **0.9833** (0.950–1.000) | **1.0000** (1.000–1.000) |
| Two databases, pre-written templates | **0.9667** (0.917–1.000) | **0.9667** (0.917–1.000) |

Figures are judged correctness from 0 to 1, with a 95% confidence range over the 30 questions in each set.

**Merging minus federating, on the like-for-like comparison:**

- question set 1: **-0.0334**
- question set 2: **+0.0000**

At least one difference is larger than the grader's own spread of 0.0050. That does not by itself make it real — 30 questions is small — but it is not noise in the grader.

## 2. What separates them apart from the score

| version | set | made something up | declined | declined with proof |
|---|---|---:|---:|---:|
| ONE database holding both catalogues | question set 1 | 2 | 2 | 2 |
| ONE database holding both catalogues | question set 2 | 3 | 1 | 1 |
| TWO databases, everything else identical | question set 1 | 3 | 2 | 2 |
| TWO databases, everything else identical | question set 2 | 1 | 3 | 3 |
| Two databases, no templates, answer written by a language model | question set 1 | 0 | 2 | 2 |
| Two databases, no templates, answer written by a language model | question set 2 | 1 | 4 | 4 |
| Two databases, pre-written templates | question set 1 | 0 | 2 | 2 |
| Two databases, pre-written templates | question set 2 | 0 | 3 | 3 |

*"Made something up"* counts answers containing at least one statement the grader could not find in the retrieved evidence. *"Declined with proof"* counts refusals that carried the query that justified refusing.

## 3. The advantage the merged version gets, stated plainly

Two identifier reconciliations happen when the merged database is built, and they are the reason it can answer cross-source questions at all.

- CAPEC entries get the public identifier ATT&CK entries already carry.
- CAPEC's ATT&CK mapping entries store `1027.001` where ATT&CK stores `T1027.001`; the merged build reconciles the two.

Both are things the two-database system already does **in code, at query time**. Moving them into the data is the merged design's own argument for itself — reconcile once at load rather than at every query — so this is the merged condition rather than a thumb on the scale. One consequence does favour the merged version and must be reported with any result: in one database the next step of a cross-catalogue question is reachable without leaving the engine, so the merged version can follow a link that the two-database version retrieves and cannot act on. That is a real property of the architecture, not an artifact of this harness.

## 4. What ran

| phase | what it did | result | time |
|---|---|---|---:|
| `P0` | graphs live, merged store whole and separable, banks on disk | ok | 15s |
| `M1-run-merged-0819` | run merged on bank20260819 | ok | 1s |
| `M2-run-merged-0820` | run merged on bank20260820 | ok | 1s |
| `M3-run-generic_composed-0819` | run generic_composed on bank20260819 | ok | 2s |
| `M4-run-generic_composed-0820` | run generic_composed on bank20260820 | ok | 1s |
| `M5-judge-merged-0819` | grade merged answers on bank20260819 | ok | 172s |
| `M6-judge-merged-0820` | grade merged answers on bank20260820 | ok | 272s |
| `M7-judge-generic_composed-0819` | grade generic_composed answers on bank20260819 | ok | 171s |
| `M8-judge-generic_composed-0820` | grade generic_composed answers on bank20260820 | ok | 214s |
| `M9-judge-generic-0819` | re-grade the committed generic answers on bank20260819 | ok | 133s |
| `M10-judge-generic-0820` | re-grade the committed generic answers on bank20260820 | ok | 362s |
| `M11-judge-deterministic-0819` | re-grade the committed deterministic answers on bank20260819 | ok | 249s |
| `M12-judge-deterministic-0820` | re-grade the committed deterministic answers on bank20260820 | ok | 228s |
| `M9` | write the plain-language report | ok | 0s |

## 5. Things that would make these numbers wrong

1. **Thirty questions per set.** A difference of a few hundredths is noise at that size.
2. **The grader is a language model.** It is the same one used for every other figure in the study, and it graded every cell here in one session, so it cancels out of the comparison — but it has never been checked against a human.
3. **Every question names an entity.** Nothing here measures the open-ended regime, where the two designs might differ most.
4. **One run per cell.** The merged and templated versions are reproducible; the no-templates version has a language model in the loop and would vary if re-run.

