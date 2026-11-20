# RESULTS — EXP-2026-11-020 Era 2 Step 9 Phase A: which retrieval shapes do the questions need?

## 1. Headline

**Almost every question available to this project needs only what Ariadne does today, plus one
operator: verify.**
- **Own banks:** today's operations cover 0.9845; the rest is Step 6's out-of-coverage set.
- **AttackQA, weighted to its full 25,335 rows:**
  - 0.44 is "verify" (one link between two named entities);
  - 0.4954 is covered today;
  - 0.0645 is outside retrieval.
- **No source needs aggregates, ranking, grouping, time or paths,** except 9 of Step 6's 13
  out-of-coverage questions, which were written to be out of coverage.
- **The labellers agreed:** κ = 0.9386 on the coverage stage.
- **Hypotheses:** H1, H3 and H4 hold. H2 holds on verify (≥ 0.40) and on the rare operators
  (0 < 0.02). Its outside-retrieval range fails: 0.0645, not 0.10 to 0.35.

## 2. Results table

From `data/metrics.json` and `tables/coverage.md` (both from `counts.json`).
- **Runs:** one labelling pass (`n_runs: 1`).
- **External shares** are sample estimates: 600 AttackQA rows, stratified by family. No
  intervals are given; the per-family table carries the detail.

**Checks (protocol)**

| Check | Bar | Result | Pass |
|---|---|---|---|
| Every item has a label from the rubric's codes | 100% | 673 of 673; the script rejects unknown codes | yes |
| κ on the coverage stage, 135 items | ≥ 0.80 | 0.9386; exact stage 0.963, exact codes 0.963 | yes |
| `count` re-run | byte-identical | identical md5 on both outputs | yes |
| Sealed banks opened | 0 | 0; the allowlist plus a test that spies on file opens | yes |

**Cumulative coverage (selected stages)**

| Source | n | today | after op 4 | after op 6 | after op 8 | outside |
|---|---|---|---|---|---|---|
| dev 284 | 284 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |
| gold 120 (variants inherit) | 120 (+579) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |
| Step 6 tuning | 433 | 0.9700 | 0.9700 | 0.9792 | 0.9931 | 0.0069 |
| own banks, pooled | 837 | 0.9845 | 0.9845 | 0.9892 | 0.9964 | 0.0036 |
| AttackQA, weighted | 25,335 | 0.4954 | 0.9355 | 0.9355 | 0.9355 | 0.0645 |
| CTIBench cti-ate | 60 | 0 | 0 | 0 | 0 | 1.0000 |

**Needs by code** (share of questions needing it; AttackQA weighted)

| Code | Own banks | AttackQA |
|---|---|---|
| `T.walk` | dominant (0.79 to 0.97 per bank) | 0.2584 |
| `T.describe` | 0.12 to 0.15 | 0.1779 |
| `T.count` | 3 items | 0.0592 |
| `O4.verify` | 0 | **0.4400** |
| `O2.aggregate` + `O6.groupby` | 4 items (medians), Step 6 only | 0 |
| `O7b.time` | 3 items ("year to year"), Step 6 only | 0 |
| `O8.path` | 3 items (shortest chain), Step 6 only | 0 |
| `O1`, `O3`, `O5`, `O7a`, `O7c`, `O7d` | 0 | 0 |
| `G1`, `G2`, `G3` | 0 | 0 |
| `X.textsearch` / `X.other` | 0 | 0.0622 / 0.0024 |
| `X.similar` | 3 items, Step 6 only | 0 |
| `X.extract` | — | CTIBench: 1.0 |

## 3. Figures

None. The tables are the result.

## 4. Interpretation

- **The plan's expectation holds, but only trivially.** Operators 1–7 "cover ≥ 0.95 of
  Ariadne's own banks" because today's operations already cover 0.98. The banks cannot tell us
  whether the new operators are needed.
- **The one outside source with volume asks for verify.**
  - About 44% of AttackQA is "how does S use T", "how can M mitigate T" and "how can DC detect T".
  - The answer is the link between two named entities and the text on it.
- **The graph cannot answer the "how" part.** Every `USES`, `MITIGATES` and `DETECTS` edge in
  the live store carries only `id`; there is no description (checked 2026-11-20, § 6).
  - Verify can say whether the link exists.
  - The procedure text needs the loaders to write relationship properties. The built records
    already hold them. That is a loader change, not a Step 9 operator.
- **Aggregate, rank, group-by, time and path have no natural frequency** in any source on this
  machine. They appear only in the 13 questions Step 6 wrote to be out of coverage.
- **What this changes in Step 9:**
  - **Operator order:** verify moves up; the rest keep the plan's order.
  - **The gaps are not built:** each covers 0% of external retrieval questions (decision rule:
    build at ≥ 2%).
  - **All eight operators are still built** (the operator's decision 2, 2026-11-20). The count
    gives no evidence for operators 1, 3, 5, 7a, 7c and 7d. Their case rests on the
    expressiveness argument for Step 11 and on the probe set, not on observed demand.
  - **Phase G's probe set** cannot be weighted by observed frequency, because most operators
    have none. It uses a floor of 10 per operator, with extra weight on verify.
- **No claim moves.** This is an engineering census.

## 5. Threats to validity

- **Every source is template-generated or close to it.** AttackQA is generated per entity from
  ATT&CK, and Ariadne's banks from walk templates. No set of real analyst questions is on this
  machine. Zero demand for aggregates here is not zero demand among users.
- **The labels are a model's judgement.**
  - κ = 0.94 shows two models read the rubric alike, not that the rubric is right.
  - All five disagreements were reworded names or text questions: "describe" or "outside".
  - They were settled for labeller A, by one person.
- **Reworded names count as named** (adjudication). A stricter reading moves about 3% of
  AttackQA's technique questions from today to outside retrieval.
- **The sample is 600 of 25,335.**
  - Families with 5 to 15 items carry their share with wide uncertainty.
  - The large families (`relationships_uses_software` 166, `relationships_detects` 53,
    `relationships_mitigations` 47, `software` 54, `techniques` 45) dominate the weighted figure.
- **The 13 Step 6 out-of-coverage questions are mislabelled for one purpose.** Three ask how a
  count "changed from year to year". Even with time operators, the graph holds one release and
  no history, so they stay unanswerable.

## 6. What surprised us

- **Verify is the external shape, and the data for its text never reaches the store.** The
  built relationship records keep the STIX `description`. The loaders write only the edge's
  `id`: `relationship_merge_cypher` and `edge_upsert_traversal` in `utils/graph_loader/stores/`.
  "How does S0623 use T1611?" asks for exactly that text. (Corrected 2026-11-20: first written
  as the builder dropping it; see ISSUES.)
- **Step 6's out-of-coverage gold will be wrong once the switches are on.**
  - Four median questions (operators 2 + 6) and three shortest-chain questions (operator 8)
    become answerable.
  - Step 7's exit-decision results and Step 12's ambiguous set use these items.
  - Their gold has to be revised when Phase G turns operators on.
- **The second labeller labelled the 31 "How does S use T" rows by their first words,** after
  reading them. They are one template, so the label is the same either way.

## 7. Follow-ups

- **Phase B (next):** `operator-algebra.md`, with verify defined as existence plus the witness
  edge and its properties.
- **Relationship descriptions:** loading them is a loader change. The data is already built.
  It affects every store and needs the live fixture reload. **It is proposed to the operator for a decision, not done
  here.**
- **Step 6/7 exit sets:** re-label the seven out-of-coverage items that become answerable,
  before any exit metric is quoted with operators on.

## 8. Reproduction

```bash
uv run --with pyarrow python scripts/count_question_shapes.py sample   # draws the 673 items (md5 a85839ad…)
# labels: labels-a.jsonl, labels-b.jsonl, adjudicated.jsonl (committed)
uv run python scripts/count_question_shapes.py count                   # counts.json, per_question.jsonl
uv run python -m pytest -q scripts/tests/test_count_question_shapes.py
```
