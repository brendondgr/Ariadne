# Is it worth keeping the two databases apart?

**Run started** 2026-08-21T15:32:41+00:00 · **phases** 10, 1 failed

The project's pitch is that keeping MITRE ATT&CK and MITRE CAPEC in two separate databases, each spoken to in its own language, is worth the extra complexity. Nobody had ever checked, because the alternative — pour both into one database and ask it one question — had never been built. It has now.

## 1. The comparison

Every row below answered **the same questions**, with **the same plan**, and was graded by **the same grader in the same session**. The only thing that differs between the first two rows is how many databases sit behind them.

| version | question set 1 | question set 2 |
|---|---:|---:|
| One database holding both catalogues | **0.9552** (0.900–1.000) | **0.9667** (0.917–1.000) |
| Two databases, no templates (the fair comparison) | **0.9833** (0.950–1.000) | **1.0000** (1.000–1.000) |
| Two databases, pre-written templates | **0.9667** (0.917–1.000) | **0.9310** (0.862–0.983) |

Figures are judged correctness from 0 to 1, with a 95% confidence range over the 30 questions in each set.

**Merging minus federating, on the like-for-like comparison:**

- question set 1: **-0.0281**
- question set 2: **-0.0333**

At least one difference is larger than the grader's own spread of 0.0050. That does not by itself make it real — 30 questions is small — but it is not noise in the grader.

## 2. What separates them apart from the score

| version | set | made something up | declined | declined with proof |
|---|---|---:|---:|---:|
| One database holding both catalogues | question set 1 | 2 | 2 | 2 |
| One database holding both catalogues | question set 2 | 1 | 1 | 1 |
| Two databases, no templates (the fair comparison) | question set 1 | 0 | 2 | 2 |
| Two databases, no templates (the fair comparison) | question set 2 | 0 | 3 | 3 |
| Two databases, pre-written templates | question set 1 | 0 | 1 | 1 |
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
| `P0` | graphs live, merged store whole and separable, banks on disk | ok | 12s |
| `M1-run` | run the merged arm on bank20260819 | ok | 1s |
| `M1-judge` | grade the merged arm on bank20260819 | ok | 232s |
| `M2-run` | run the merged arm on bank20260820 | ok | 1s |
| `M2-judge` | grade the merged arm on bank20260820 | ok | 203s |
| `M3-judge-generic-1` | re-grade the committed generic answers on bank20260819 with this session's grader | ok | 158s |
| `M3-judge-generic-2` | re-grade the committed generic answers on bank20260820 with this session's grader | ok | 122s |
| `M4-judge-deterministic-1` | re-grade the committed deterministic answers on bank20260819 with this session's grader | ok | 129s |
| `M4-judge-deterministic-2` | re-grade the committed deterministic answers on bank20260820 with this session's grader | ok | 179s |
| `M9` | write the plain-language report | **None** | 0s |

**`M9` failed:** `None`

## 5. Things that would make these numbers wrong

1. **Thirty questions per set.** A difference of a few hundredths is noise at that size.
2. **The grader is a language model.** It is the same one used for every other figure in the study, and it graded every cell here in one session, so it cancels out of the comparison — but it has never been checked against a human.
3. **Every question names an entity.** Nothing here measures the open-ended regime, where the two designs might differ most.
4. **One run per cell.** The merged and templated versions are reproducible; the no-templates version has a language model in the loop and would vary if re-run.

