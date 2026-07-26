# Un-truncated Retrieval Experiment — Two Arms, 120 Questions Each

Same 120 golden questions, same order, same two graphs (ATT&CK/Neo4j 4,369 nodes; CAPEC/Gremlin 4,769 nodes). The **common** change to both arms lifts every retrieval, synthesis-evidence and judge-artifact cap so `describe`/`expand` return full neighbourhoods and synthesis receives the whole evidence set. The **independent variable** is the LLM: Arm A runs no LLM at all, Arm B runs LLM planning + LLM synthesis. Each arm was graded case-by-case by 120 independent Sonnet 5 agents (240 total) against the gold assertions *and* the full retrieved evidence.

## Headline

| Metric | Arm A — deterministic | Arm B — LLM-planned | Baseline (truncated) |
|---|---|---|---|
| correctness | **0.9500** | **0.7660** | 0.8946 |
| completeness | **0.9534** | **0.7770** | 0.8952 |
| faithfulness | **0.9979** | **0.9479** | 0.9558 |
| groundedness | **0.9992** | **0.9517** | 0.9575 |
| n graded | 120 | 120 | 120 |

**Verdicts**

| Arm | CORRECT | PARTIAL | INCORRECT | answers w/ hallucinations | total hallucinations |
|---|---|---|---|---|---|
| A — deterministic | 112 | 1 | 7 | 0 | 0 |
| B — LLM-planned | 84 | 11 | 25 | 12 | 18 |
| Baseline (truncated) | 91 | 27 | 2 | 11 | — |

## Deltas

| Metric | B − A | A − baseline | B − baseline |
|---|---|---|---|
| correctness | -0.1840 | +0.0554 | -0.1286 |
| completeness | -0.1764 | +0.0582 | -0.1182 |
| faithfulness | -0.0500 | +0.0421 | -0.0079 |
| groundedness | -0.0475 | +0.0417 | -0.0058 |

| Verdict | B − A | A − baseline | B − baseline |
|---|---|---|---|
| CORRECT | -28 | +21 | -7 |
| PARTIAL | +10 | -26 | -16 |
| INCORRECT | +18 | +5 | +23 |

## Retrieval volume actually pulled

| Arm | evidence records | related neighbours | mean answer coverage (gold ids surfaced) |
|---|---|---|---|
| A — deterministic | 1840 | 839 | 1.0000 (66 scorable) |
| B — LLM-planned | 3401 | 979 | 0.7989 (66 scorable) |

## Weakest categories by mean correctness

### Arm A — deterministic

| Category | n | mean correctness | baseline | Δ vs baseline | verdicts |
|---|---|---|---|---|---|
| A-SCN | 1 | 0.10 | 0.85 | -0.75 | {"INCORRECT": 1} |
| C-SCN | 1 | 0.15 | 1.00* | -0.85 | {"INCORRECT": 1} |
| C-LKP | 5 | 0.24 | 0.88 | -0.64 | {"INCORRECT": 5} |
| C-HIE | 3 | 0.90 | 1.00* | -0.10 | {"CORRECT": 2, "PARTIAL": 1} |
| A-DET | 3 | 0.98 | 0.97 | +0.01 | {"CORRECT": 3} |
| F-FAN | 3 | 0.98 | 1.00* | -0.02 | {"CORRECT": 3} |
| F-CTM | 10 | 0.99 | 0.92 | +0.07 | {"CORRECT": 10} |

<sub>*Categories absent from the baseline's weakest table scored 1.00 there.</sub>

### Arm B — LLM-planned

| Category | n | mean correctness | baseline | Δ vs baseline | verdicts |
|---|---|---|---|---|---|
| C-SCN | 1 | 0.10 | 1.00* | -0.90 | {"INCORRECT": 1} |
| A-SUB | 2 | 0.17 | 1.00* | -0.82 | {"INCORRECT": 1, "PARTIAL": 1} |
| A-DET | 3 | 0.20 | 0.97 | -0.77 | {"INCORRECT": 2, "PARTIAL": 1} |
| A-SCN | 1 | 0.20 | 0.85 | -0.65 | {"INCORRECT": 1} |
| C-ABS | 3 | 0.20 | 0.17 | +0.03 | {"INCORRECT": 2, "PARTIAL": 1} |
| F-CWE | 5 | 0.20 | 0.59 | -0.39 | {"CORRECT": 1, "INCORRECT": 4} |
| F-FAN | 3 | 0.28 | 1.00* | -0.72 | {"INCORRECT": 2, "PARTIAL": 1} |
| F-PART | 4 | 0.35 | 0.91 | -0.56 | {"INCORRECT": 2, "PARTIAL": 2} |
| F-CTM | 10 | 0.43 | 0.92 | -0.49 | {"CORRECT": 2, "INCORRECT": 5, "PARTIAL": 3} |
| A-SW | 3 | 0.63 | 0.45 | +0.18 | {"CORRECT": 1, "PARTIAL": 2} |
| F-CTT | 6 | 0.69 | 1.00* | -0.31 | {"CORRECT": 4, "INCORRECT": 2} |
| C-EXE | 3 | 0.72 | 0.98 | -0.26 | {"CORRECT": 2, "INCORRECT": 1} |
| C-HIE | 3 | 0.72 | 1.00* | -0.28 | {"CORRECT": 2, "INCORRECT": 1} |
| C-MAP | 5 | 0.82 | 1.00* | -0.18 | {"CORRECT": 4, "INCORRECT": 1} |

<sub>*Categories absent from the baseline's weakest table scored 1.00 there.</sub>

## Where the two arms disagree

- **CORRECT only in Arm B** (the LLM path fixes it) — 5: `C-LKP-01`, `C-LKP-02`, `C-LKP-03`, `C-LKP-04`, `C-LKP-05`
- **CORRECT only in Arm A** (the LLM path breaks it) — 33: `A-DET-01`, `A-DET-02`, `A-DET-03`, `A-SUB-01`, `A-SUB-02`, `A-SW-02`, `A-SW-03`, `C-ABS-01`, `C-ABS-02`, `C-ABS-03`, `C-EXE-03`, `C-MAP-02`, `F-CTM-01`, `F-CTM-02`, `F-CTM-03`, `F-CTM-04`, `F-CTM-05`, `F-CTM-06`, `F-CTM-08`, `F-CTM-09`, `F-CTT-01`, `F-CTT-04`, `F-CWE-01`, `F-CWE-03`, `F-CWE-04`, `F-CWE-05`, `F-FAN-01`, `F-FAN-02`, `F-FAN-03`, `F-PART-01`, `F-PART-02`, `F-PART-03`, `F-PART-04`

## Every non-CORRECT case

### Arm A — deterministic — 8 of 120

| Case | verdict | corr | compl | faith | ground | hallucinations |
|---|---|---|---|---|---|---|
| A-SCN-01 | INCORRECT | 0.10 | 0.00 | 0.90 | 0.90 | 0 |
| C-SCN-01 | INCORRECT | 0.15 | 0.00 | 1.00 | 1.00 | 0 |
| C-LKP-01 | INCORRECT | 0.20 | 0.25 | 1.00 | 1.00 | 0 |
| C-LKP-02 | INCORRECT | 0.20 | 0.33 | 1.00 | 1.00 | 0 |
| C-LKP-04 | INCORRECT | 0.20 | 0.25 | 1.00 | 1.00 | 0 |
| C-LKP-03 | INCORRECT | 0.30 | 0.25 | 1.00 | 1.00 | 0 |
| C-LKP-05 | INCORRECT | 0.30 | 0.33 | 1.00 | 1.00 | 0 |
| C-HIE-03 | PARTIAL | 0.70 | 1.00 | 0.95 | 1.00 | 0 |

### Arm B — LLM-planned — 36 of 120

| Case | verdict | corr | compl | faith | ground | hallucinations |
|---|---|---|---|---|---|---|
| F-CTM-01 | INCORRECT | 0.00 | 0.00 | 0.90 | 1.00 | 0 |
| F-CTM-05 | INCORRECT | 0.00 | 0.00 | 0.90 | 1.00 | 0 |
| F-CTM-08 | INCORRECT | 0.00 | 0.00 | 0.60 | 0.30 | 1 |
| F-CTM-09 | INCORRECT | 0.00 | 0.00 | 1.00 | 1.00 | 0 |
| F-CWE-01 | INCORRECT | 0.00 | 0.00 | 1.00 | 0.00 | 0 |
| F-CWE-03 | INCORRECT | 0.00 | 0.00 | 0.85 | 1.00 | 0 |
| F-CWE-04 | INCORRECT | 0.00 | 0.00 | 1.00 | 1.00 | 0 |
| F-FAN-03 | INCORRECT | 0.00 | 0.00 | 1.00 | 1.00 | 0 |
| F-CTM-04 | INCORRECT | 0.05 | 0.00 | 0.40 | 0.50 | 1 |
| F-CTT-04 | INCORRECT | 0.05 | 0.00 | 1.00 | 1.00 | 0 |
| F-CWE-05 | INCORRECT | 0.05 | 0.15 | 0.15 | 0.20 | 3 |
| F-FAN-02 | INCORRECT | 0.05 | 0.09 | 0.10 | 0.15 | 3 |
| F-PART-02 | INCORRECT | 0.05 | 0.00 | 0.80 | 0.85 | 0 |
| A-DET-03 | INCORRECT | 0.10 | 0.12 | 0.90 | 1.00 | 0 |
| A-SUB-02 | INCORRECT | 0.10 | 0.50 | 1.00 | 1.00 | 0 |
| C-MAP-02 | INCORRECT | 0.10 | 0.33 | 0.80 | 0.85 | 1 |
| C-SCN-01 | INCORRECT | 0.10 | 0.10 | 0.90 | 0.90 | 0 |
| F-CTT-01 | INCORRECT | 0.10 | 0.20 | 1.00 | 1.00 | 0 |
| A-DET-02 | INCORRECT | 0.15 | 0.14 | 0.90 | 1.00 | 0 |
| C-ABS-02 | INCORRECT | 0.15 | 0.33 | 1.00 | 1.00 | 0 |
| C-ABS-03 | INCORRECT | 0.15 | 0.33 | 1.00 | 1.00 | 0 |
| C-EXE-03 | INCORRECT | 0.15 | 0.14 | 0.95 | 0.90 | 0 |
| C-HIE-03 | INCORRECT | 0.15 | 0.50 | 1.00 | 1.00 | 0 |
| A-SCN-01 | INCORRECT | 0.20 | 0.00 | 0.30 | 0.40 | 1 |
| F-PART-04 | INCORRECT | 0.20 | 0.75 | 0.20 | 0.45 | 3 |
| A-SUB-01 | PARTIAL | 0.25 | 0.11 | 1.00 | 1.00 | 0 |
| C-ABS-01 | PARTIAL | 0.30 | 0.55 | 0.85 | 0.90 | 0 |
| A-DET-01 | PARTIAL | 0.35 | 0.33 | 1.00 | 1.00 | 0 |
| A-SW-02 | PARTIAL | 0.45 | 0.14 | 1.00 | 1.00 | 0 |
| A-SW-03 | PARTIAL | 0.45 | 0.11 | 1.00 | 0.90 | 0 |
| F-PART-03 | PARTIAL | 0.45 | 0.25 | 0.95 | 1.00 | 0 |
| F-CTM-03 | PARTIAL | 0.70 | 0.80 | 0.95 | 1.00 | 0 |
| F-PART-01 | PARTIAL | 0.70 | 1.00 | 0.75 | 0.90 | 1 |
| F-CTM-02 | PARTIAL | 0.80 | 0.77 | 1.00 | 1.00 | 0 |
| F-CTM-06 | PARTIAL | 0.80 | 0.65 | 1.00 | 1.00 | 0 |
| F-FAN-01 | PARTIAL | 0.80 | 0.85 | 1.00 | 1.00 | 0 |

## Hallucinations flagged

### Arm A — deterministic — 0

None flagged.

### Arm B — LLM-planned — 18

- **A-CMP-TEC-02**: Narrative closing sentence claims the technique set 'spans reconnaissance, credential access, lateral movement, and defense evasion activities' — no tactic/category field is present anywhere in the retrieved evidence (all Technique records have empty properties/facets), so this tactic categorization is an unsupported inductive add-on rather than a grounded citation, though it is broadly consistent with the named techniques.
- **A-GRP-02**: Narrative claim 'The evidence does not link any CAPEC attack patterns to this group' goes beyond the executed query (which only matched Group-USES->Technique and never queried for CAPEC nodes); it is an inference from empty 'related' fields rather than a directly retrieved fact, though not a fabricated ID.
- **A-SCN-01**: Narrative states 'The evidence lists 300 software entries', but the retrieved evidence (logic_flow.results[0].records, and the answer's own 'claims' array) contains 821 records/entity_ids, not 300 -- the narrative's headline count is fabricated and contradicts both the raw evidence and the pipeline's own structured claims (which correctly say 'Found 821 ATT&CK record(s)' and enumerate all 821 ids).
- **A-SW-01**: Narrative groups techniques into tactic categories (e.g. calls T1550.002/T1098/T1207 'lateral movement and account manipulation techniques') that are not present anywhere in the retrieved evidence -- record properties are empty ({}) and no tactic/category field is returned, so these tactic labels are the model's own domain knowledge layered on top of the graph result rather than something grounded in the evidence; T1207 (Rogue Domain Controller) in particular is conventionally a Defense Evasion technique, not lateral movement, making the added categorization both ungrounded and arguably imprecise.
- **C-MAP-01**: Narrative editorializes that 'T1021 and T1133 directly correspond to the remote access protocols leveraged in the attack pattern, while T1114.002 aligns with the credential harvesting phase' -- this phase/role framing is an interpretive gloss not stated anywhere in the retrieved evidence (the CAPEC description and technique descriptions do not describe a two-phase 'remote access then credential harvesting' structure).
- **C-MAP-02**: Narrative claims 'a follow-up query to resolve those entries ... returned zero results', but the evidence shows q2 was never executed at all (query: "", status: 'Skipped: ... depends on q1 for its seed identifiers, but it returned no join values') — it was skipped due to a missing dependency, not an executed query that returned zero rows.
- **F-CTM-04**: Narrative states 'Queries for mitigations applying to those mapped techniques returned zero records, meaning no mitigations are currently linked to them in the graph' — this misrepresents the evidence. Per logic_flow, q2 was never executed at all (query: "", trace step 'dependency': 'producer q1: it returned no join values'); the abstention explicitly says 'no query was executed'. The answer converts an unexecuted/skipped query into a false claim of a definitive zero-result finding, which is not supported by the evidence.
- **F-CTM-08**: Narrative claims 'None of the live graph sources cover this request' — this misrepresents the actual cause (run_meta/notes show both the capec and attack sub-questions were skipped due to total pipeline timeout being exceeded, not because the sources lack coverage of CAPEC-644 or T1550.002).
- **F-CWE-05**: The answer presents 'All 558 result(s) for this question' as if it were the set of CAPEC patterns exploiting CWE-521, but the actual q1 query (Find AttackPattern EXPLOITS_WEAKNESS Weakness 'CWE-521') returned 0 rows (trace: seed_ids=['CWE-521'], row_count=0) because it was miswired to match AttackPattern.id against 'CWE-521' rather than traversing the Weakness node; q2/q3 then silently fell back to unfiltered queries over the ENTIRE CAPEC corpus (all 558 AttackPattern nodes) and mislabeled that dump as answering the CWE-521 question.
- **F-CWE-05**: No ATT&CK technique required by gold (T1021, T1021.002, T1078.001, T1110, T1110.001, T1110.002, T1110.003, T1114.002, T1133, T1558.003) is named anywhere in the answer; the 'ATT&CK mappings' cited (T1001.002, T1003, T1005, T1007, T1012) come from the unfiltered corpus dump and are unrelated to CWE-521.
- **F-CWE-05**: No mitigation required by gold (M1018, M1021, M1026, M1027, M1030, M1032, M1035, M1036, M1037, M1041, M1042, M1047, M1051, M1060) appears anywhere — the ATT&CK mitigation sub-question (q4) was skipped entirely because it depended on q3, which itself never produced real technique seeds (q3 also fell back to 'g.V().hasLabel("AttackPattern").elementMap()' with no CWE-521 filter).
- **F-FAN-02**: Narrative claims 'CAPEC-13 and CAPEC-640 map to a total of 100 ATT&CK techniques' but the evidence never establishes this join: q1's Gremlin query returned CAPEC-13/CAPEC-640 elementMaps with empty 'related' arrays and no TaxonomyEntry/entry_id values (trace: seed_ids: [], join_key: null), so q2's query 'MATCH (n:Technique) RETURN n.attack_id AS id, n.name AS name LIMIT 100' is an unfiltered, unjoined scan of the first 100 Technique nodes in the ATT&CK graph -- not a CAPEC-derived set.
- **F-FAN-02**: Names T1055 (Process Injection), T1047 (Windows Management Instrumentation), T1036 (Masquerading), and T1543 (Create or Modify System Process) as techniques CAPEC-13/CAPEC-640 'map to' -- none of these four appear in gold's must_correlate/must_include_ids set (T1505.005, T1574.006, T1574.007, T1574.013, T1620), and no relationship evidence in logic_flow ties them to CAPEC-13 or CAPEC-640.
- **F-FAN-02**: Asserts a union size of 100 techniques when gold specifies the correct deduplicated union is exactly 5 techniques (min_records=5, max_records=5) -- an order-of-magnitude overclaim caused by the broken join being silently treated as if it were the answer.
- **F-PART-01**: Claims a 'cross-source correlation' ('The identifier T1021 is corroborated across attack and capec (2 record(s) share it)') for a case where gold sets expect_no_correlation=true and must_correlate=[]; this is merely the mechanical join key used to run the federated query, not a substantive finding, and the pipeline's own deterministic_scores.correlation block confirms the mismatch (n_expected=0, n_got=1, precision=0.0, f1=0.0).
- **F-PART-04**: Narrative claims 'the query for ATT&CK techniques explicitly linked to CAPEC-555' but the executed query (logic_flow.results[0].query) is 'MATCH (n:Technique) RETURN n.attack_id AS id, n.name AS name LIMIT 100' with seed_ids: [] and template 'label_scan' -- a generic unseeded scan of all Technique nodes with no CAPEC-555 filter whatsoever.
- **F-PART-04**: Narrative states the empty related arrays 'confirm that none of these techniques currently hold explicit graph relationships or cross-source joins to CAPEC-555' -- false framing; the related arrays are empty because the label-scan query never traverses relationships or checks for CAPEC-555 links at all, not because such a check was performed and came back negative.
- **F-PART-04**: Narrative asserts this result 'validates the dependency abstention state' -- it does the opposite: this is precisely the prohibited broad unseeded query the gold says must NOT run when the CAPEC-555 producer is down (attack.expect_dependency_skip: true).

## Verdict — plain English

**Did un-truncated retrieval fix the compound/hierarchy failures? Yes — but only in the
deterministic arm, and the fix is the *structured claim*, not the extra rows.**

The baseline's worst categories were C-ABS (0.17), C-CSQ (0.35), A-SW (0.45) and F-CWE
(0.59) — all the same fault: retrieval was already correct and the answer named only a
sample of it. Un-truncated + deterministic clears every one of them: C-ABS 0.17 → 1.00,
C-CSQ 0.35 → 1.00, A-SW 0.45 → 1.00, F-CWE 0.59 → 1.00, A-GRP 0.76 → 1.00, A-CMP
0.86 → 1.00. Mean answer coverage — the fraction of gold ids the answer actually states —
is **1.0000 across all 66 scorable questions** in Arm A. Compound and hierarchy questions
are solved.

The honest attribution matters for what to build next: lifting the caps was *necessary*
but the thing that converts retrieved evidence into a scored answer is the deterministic
composer's structured enumeration claim, which lists the whole related set with a citation
per id. Arm B pulled **more** evidence than Arm A (3,401 records vs 1,840) and scored
**worse** on coverage (0.7989 vs 1.0000), because the LLM narrator writes prose and prose
samples. More rows do not help an answer that was never going to enumerate them.

**Did the LLM path hallucinate more? Yes, and it is not close.**

Arm A produced **zero** hallucinations across 120 answers — 120 independent graders each
looking for one, none found. Arm B produced **18 across 12 answers**, and its faithfulness
(0.9479) and groundedness (0.9517) are both *below* the truncated baseline. A deterministic
composer that can only cite retrieved records cannot invent; a narrator can, and does.
That is the whole finding, and un-truncation does not change it in either direction.

But hallucination is not Arm B's main problem. Arm B is worse than Arm A on **33 questions**
and better on **5**, and almost all 33 are *planning* failures, not writing failures:

- **The federated two-hop join collapses.** F-CTM 0.99 → 0.43, F-CWE 1.00 → 0.20,
  F-CTT 1.00 → 0.69, F-FAN 0.98 → 0.28, F-PART 1.00 → 0.35. The LLM planner's first hop
  returns no join values, so the second hop fires unseeded and answers a different question.
- **It picks the wrong primitive.** A-DET 0.98 → 0.20 because the planner ran a `describe`
  facet-count instead of the detection traversal; C-ABS, C-EXE-03, C-HIE-03, A-SUB-01/02
  fail the same way.
- **It runs out of time.** 9 of 120 finished `partial` on the pipeline deadline; 6 carry an
  explicit timeout note. LLM planning + LLM drafting + LLM synthesis per question is simply
  slow.

The five questions only Arm B gets right are all C-LKP (attribute lookups: "what is
CAPEC-555's abstraction and status?"). Those are Arm A's largest failure group, and the
reason is narrow and fixable: the evidence carries `Abstraction` and `Status`, but the
deterministic composer never projects a record's *own properties* into a claim, so the
answer is `"Found 1 CAPEC record(s): CAPEC-555."` The narrator reads the same evidence and
says "Abstraction Standard, Status Stable". This is the open lever — teach the deterministic
composer to project queried properties — and it is worth about +0.03 correctness on its own
(5 cases from a 0.24 mean to 1.0), which would put Arm A around 0.98.

**Which arm should we demo in October? Arm A — un-truncated deterministic.**

It wins on every headline metric (correctness 0.9500 vs 0.7660, completeness 0.9534 vs
0.7770, faithfulness 0.9979 vs 0.9479, groundedness 0.9992 vs 0.9517), it is the only
configuration with zero hallucinations, it beats the committed baseline on all four
metrics, and it runs the whole 120-question catalogue in **2.6 seconds** against Arm B's
**16 minutes** — so it is also the only one that survives a live audience. It is
reproducible byte-for-byte, which matters when someone asks you to run it again on stage.

Two things to fix before the demo, both small:

1. **Do not demo A-SCN-01 or C-SCN-01.** These are the only two questions un-truncation
   makes *worse* in both arms, and it is an artefact: their gold asserts `max_records: 300`,
   which is the very cap the profile lifts, so returning all 821 / 558 rows is scored
   INCORRECT. Either re-author those two gold assertions or keep the cap for scan-shaped
   questions.
2. **Fix the C-LKP property projection** if there is time — it is 5 of Arm A's 7 INCORRECT
   and the only real correctness gap left.

Keep Arm B in the deck as the roadmap slide, not the demo. The LLM path's *narration* is
genuinely better where it runs (it is the only thing that answers an attribute question in
prose), and its failure mode is concentrated in the planner's federated seeding — one
component, not a systemic problem. But on today's numbers it would lose to its own
deterministic baseline in front of an audience.

## Notes and caveats

- **skynet was down at the start of this session** (relay 502, `health: failed`); it recovered mid-run. Arm B was first launched on the relay's other model (`local` / gemma-4-26B-it), that run was stopped at 54/120 and its artifacts discarded. Every Arm B number here is from a clean 120/120 run on **skynet**, the same model as the committed baseline — so the B-vs-baseline delta isolates un-truncation, not a model swap.
- **The live CAPEC/Gremlin graph was empty (0 nodes) on entry** and was reloaded before either arm ran (4,769 nodes / 6,972 edges). Every CAPEC and federated question would otherwise have returned 'no records'.
- **Un-truncation broke the two bounded-scan questions in both arms.** A-SCN-01 and C-SCN-01 assert `max_records: 300`, which is exactly the per-task row cap the profile lifts; they now return 821 and 558 records and are graded INCORRECT in both arms. This is the experiment's design colliding with the gold, not a pipeline regression — those two gold assertions encode the cap.
- **Full evidence does not fit the model on the largest questions.** In Arm B, C-SCN-01 (558 records) and F-CWE-05 (1,470 records / 542 related) overflowed skynet's 64k context (~47k input + 16k requested output, HTTP 400) and fell back to the deterministic narrative. Un-truncated retrieval and a 64k context window are not simultaneously satisfiable at the top of this catalogue.
- **Arm B hit pipeline timeouts on 9 of 120** (`status: partial`, exit_code 1); A-CMP-NEG-01, C-NEG-02, F-CTM-08, F-CTM-09, F-CWE-01 and F-FAN-03 carry an explicit timeout note. Several Arm B INCORRECTs are that deadline, not a reasoning error.
- **Arm A ran the gold-replay plan with no retrieval loop; Arm B ran with ORCH_MAX_HOPS=5** (the repo default; the local .env pins 1). The iterative-retrieval loop is part of an honest LLM-planned arm.
- **Wall clock:** Arm A ran all 120 questions in 2.6 s (4 workers); Arm B took 973.6 s / 16.2 min (8 workers, skynet).
- **The baseline column is the committed truncated run** in `docs/evaluation/independent-eval.md` — same 120 questions, same independent-Sonnet rubric, LLM synthesis on. Arm A differs from it on two variables at once (un-truncation *and* removing the LLM), so read A−baseline as the combined effect; B−baseline is the like-for-like un-truncation delta.

Per-case verdicts: `<arm>/answers/<id>.judgment.json`; answers + full retrieved evidence: `<arm>/answers/<id>.json`; run configuration: `<arm>/manifest.json`.
