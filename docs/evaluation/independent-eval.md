# Independent Cross-Model Evaluation (Sonnet 5)

120 saved e2e answers, each graded by a **separate Sonnet 5 agent** against the question's **gold assertions** and full retrieved evidence — an independent check on the skynet self-judgment (same model that wrote the answers).

## Headline

| Metric | Independent (Sonnet 5) | skynet self-judge |
|---|---|---|
| correctness | **0.8946** | — |
| completeness | **0.8952** | 0.95 (evidence_sufficiency) |
| faithfulness | **0.9558** | 0.9733 |
| groundedness | **0.9575** | 0.9342 |

**Verdicts:** 91 CORRECT · 27 PARTIAL · 2 INCORRECT (of 120). Hallucinations flagged in 11 answers.

## Where the independent judge disagrees with skynet

- **Faithfulness lower (0.956 vs 0.973):** the independent grader caught more unsupported claims than skynet did on its own output — mild self-preference bias, exactly the concern.
- **Groundedness higher (0.958 vs 0.934):** the Sonnet grader was given the related-neighbour descriptions skynet's judge had stripped, so it correctly credited grounding skynet penalized.

## Weakest categories (mean correctness < 1.0)

| Category | n | correctness | verdicts |
|---|---|---|---|
| C-ABS | 3 | 0.17 | {'INCORRECT': 2, 'PARTIAL': 1} |
| C-CSQ | 2 | 0.35 | {'PARTIAL': 2} |
| A-SW | 3 | 0.45 | {'PARTIAL': 3} |
| F-CWE | 5 | 0.59 | {'PARTIAL': 5} |
| A-GRP | 4 | 0.76 | {'CORRECT': 2, 'PARTIAL': 2} |
| A-SCN | 1 | 0.85 | {'PARTIAL': 1} |
| A-CMP | 8 | 0.86 | {'CORRECT': 5, 'PARTIAL': 3} |
| C-LKP | 5 | 0.88 | {'PARTIAL': 4, 'CORRECT': 1} |
| A-MC | 3 | 0.88 | {'CORRECT': 2, 'PARTIAL': 1} |
| F-PART | 4 | 0.91 | {'CORRECT': 3, 'PARTIAL': 1} |
| F-CTM | 10 | 0.92 | {'CORRECT': 8, 'PARTIAL': 2} |
| A-MIT | 8 | 0.94 | {'CORRECT': 7, 'PARTIAL': 1} |
| C-PRE | 2 | 0.95 | {'CORRECT': 2} |
| A-DET | 3 | 0.97 | {'CORRECT': 2, 'PARTIAL': 1} |
| C-EXE | 3 | 0.98 | {'CORRECT': 3} |

## The 2 INCORRECT + top hallucinations

- **C-ABS-01** (corr=0): Gold requires must_include_ids=[CAPEC-7] (present, satisfied) and must_include_related=[CAPEC-66, CAPEC-248] (the standard and meta ancestors reached by walking two CHILD_OF hops from CAPEC-7). The evidence record for CAPEC-7 carries related=[{"id":"CAPEC-66"},{"id":"CAPEC-248"}]
- **C-ABS-02** (corr=0.15): The question asks for CAPEC-16's standard ancestor and its meta ancestor. The executed query (logic_flow.results[0].query) is exactly a two-hop CHILD_OF traversal — ap→parent→grandparent — matching the gold hierarchy walk, and the single returned record's "related" list contains 

**Hallucination pattern:** 
- A-CMP-01: "The campaign is associated with one software, 18 subtechniques, and 10 techniques." — these specific counts appear nowhere in the retrieved evidence. The record's `description` fi
- A-DET-02: Narrative claims all five analytics (AN1275–AN1279) "monitor for high volumes of failed authentication attempts followed by a successful login" — but AN1278's evidence description 
- A-CMP-02: "The campaign is associated with 13 techniques and 14 sub-techniques." — no such counts appear anywhere in the evidence. The retrieved record's `related` array is empty ([]), and n
- C-ABS-01: "The provided evidence does not contain the identifiers for the standard or meta ancestors of CAPEC-7" — this is false. The single retrieved record (logic_flow.results[0].records[0
- A-SW-02: Narrative labels T1055.001 as "DLL Injection" — the retrieved record's actual technique name is "Dynamic-link Library Injection"; the answer substitutes an informal alias not prese
- A-SCN-01: MEDUSA (S1220) — named in narrative but absent from logic_flow.results[0].records and from claims/citations; no supporting evidence in the artifact.

Per-case judgments saved alongside answers: `docs/evaluation/answers/<id>.judgment.json`.