# Independent Evaluation — Failure Analysis

A close reading of the 120 Sonnet 5 grading rationales, verified against the live
pipeline. The goal: understand **where, why, and how** the answers were marked
down — and, just as important, where the *grading* itself was misled.

> **Headline correction up front:** roughly half of the faithfulness/groundedness
> penalties the independent panel assigned are **artifacts of the judging harness
> I built**, not pipeline faults. My answer-serializer dropped the very evidence
> (`properties`, `facets`) that grounded the flagged claims. Once corrected, the
> pipeline shows **essentially no genuine hallucination** — its real weakness is
> **under-enumeration** (it retrieves everything but only names a sample in prose).

---

## 1. Scoreboard (as graded)

| Metric | Independent (Sonnet 5) | skynet self-judge |
|---|---|---|
| correctness | 0.895 | — |
| completeness | 0.895 | 0.95 (sufficiency) |
| faithfulness | 0.956 | 0.973 |
| groundedness | 0.958 | 0.934 |

Verdicts: **91 CORRECT · 27 PARTIAL · 2 INCORRECT.** 39 cases were less than
perfect on some axis. Those 39 are what this report dissects.

The corrected faithfulness (removing harness artifacts, §3) is **~0.99** — the
pipeline is more faithful than either judge could measure.

---

## 2. How the failures break down

Every one of the 39 imperfect cases falls into one of six buckets. Only two are
genuine pipeline defects; the rest are grading artifacts or benign.

| Bucket | Cases | Real pipeline fault? |
|---|---|---|
| A. Harness-serialization artifact (grounding stripped) | ~7 (C-LKP×4, A-CMP×2, A-SCN×1) | **No** — answer was faithful |
| B. Under-enumeration (composer samples, doesn't list) | ~17 (A-SW, A-GRP, A-MIT, C-CSQ, F-CWE, F-CTM…) | **Yes — dominant defect** |
| C. Structured-hierarchy mishandling (C-ABS) | 3 | **Yes — narrow** |
| D. Minor over-generalization | ~3 (A-DET-02, F-CTM-01…) | Yes, minor |
| E. Citation-mechanics ding (content correct) | ~6 (C-EXE×3, A-TAC, C-PRE, A-CMP-TEC-01) | No — provenance metadata only |
| F. Communication/surfacing gap | ~3 (F-PART-04…) | Yes, minor |

---

## 3. Bucket A — the grading was misled (NOT hallucination)

This is the most important section. Several answers were penalized hard for
"fabricating" values that the pipeline **genuinely retrieved** — my judging
artifact just didn't include them.

### The A-CMP "fabricated counts" (A-CMP-01, A-CMP-02)

- **Judge said:** *"'associated with one software, 18 subtechniques, and 10
  techniques' — these counts appear nowhere in the evidence… fabricated."*
  (faithfulness 0.5).
- **Reality:** the live record's `facets` are exactly
  `Software:1, SubTechnique:18, Technique:10`. The narrator read them correctly.
- **Cause:** `generate_e2e._record_dict` serializes only
  `{primary_id, name, label, description, join_values, related}` — it **drops the
  `facets` field**. The judge never saw the counts' source.

### The C-LKP "invented abstraction/status" (C-LKP-01, 03, 04, 05)

- **Judge said:** *"'abstraction level of Standard'… no Abstraction field appears
  in the retrieved record… ungrounded."* (faithfulness 0.25–0.6).
- **Reality:** C-LKP-01's live record has `Abstraction='Standard', Status='Stable'`
  — matching both the narrative and gold. Confirmed live for all siblings.
- **Cause:** same `_record_dict` — it keeps only `description` out of the
  `properties` dict and **discards every other property** (Abstraction, Status).
  One Sonnet agent (C-LKP-04) actually traced this to
  *"generate_e2e.py's `_record_dict` (lines 54–80)"* itself — the panel diagnosed
  my bug for me.

### The A-SCN "10 ungrounded software ids" (A-SCN-01)

- The scan returned **300** rows; the narrator named 50. My serializer caps
  records at `_MAX_RECORDS_PER_RESULT = 40`, so 10 of the named ids fell outside
  the judge's view and were flagged ungrounded. They were in the real result set.

**Net effect of Bucket A:** ~7 cases carried large faithfulness/groundedness
penalties for correct, grounded answers. Correcting just these lifts panel
faithfulness from 0.956 to ~0.99. **The pipeline did not hallucinate here — the
harness under-served the judge.**

> **Fix:** extend `_record_dict` to include a bounded `properties` (all scalar
> attributes, not just `description`) and the `facets` list, and raise/annotate
> the 40-record cap. Then re-run the 120-agent pass for a true faithfulness read.

---

## 4. Bucket B — the real, dominant defect: under-enumeration

This is genuine and unaffected by serialization. **Retrieval is perfect; the
deterministic composer only surfaces a sample of ids in prose.** faithfulness and
groundedness stay ~1.0, but completeness collapses.

Representative cases (gold-ids surfaced / required):

| Case | Question | Surfaced | Why |
|---|---|---|---|
| A-SW-03 | techniques used by TrickBot | **10 / 55** | composer lists ~10 "e.g." ids |
| A-SW-02 | techniques used by Cobalt Strike | **15 / 73** | same |
| A-SW-01 | techniques (T1550 pass-the-hash set) | **4 / 17** | same |
| A-GRP-03 | techniques used by group G0007 | **0 / 5** | sampled 8 of 37; missed all 5 gold |
| A-MIT-05 | mitigations for T1003 | **4 / 9** | "including M1041, M1015…" |
| F-CWE-01…05 | CAPEC→ATT&CK **+ mitigations** | mitigations **5/25, 5/20…** | mitigation half truncated |
| C-CSQ-01/02 | consequences of CAPEC-66/98 | **0 / 4, 0 / 3** | states the count, not the ids |

**Root cause:** the specialist's `summarize()` emits an id-line + short sample,
and `_fact_claim` uses that as the claim; the LLM narrator paraphrases the sample
rather than enumerating the full `related`/`join_values` set. On "which
techniques / what mitigations" questions the gold expects the *whole* list.

The federated `F-CWE`/`F-CTM` pattern is the sharpest: the **technique-mapping
half is always perfect** (correlation/mapping_recall = 1.0), but the **mitigations
half is 25–30% surfaced** even though every mitigation is in the retrieved
evidence.

---

## 5. Bucket C — structured-hierarchy mishandling (C-ABS, the 2 INCORRECT)

The abstraction-hierarchy questions ("walk up: name the standard vs meta
ancestor") are the only genuinely *wrong* answers, and they have a shared root.

- **C-ABS-03 (root cause):** the Gremlin query correctly fetches parent
  (standard) and grandparent (meta) as *ordered, distinct* roles, but the
  **normalizer flattens them into one unordered `related` list**, discarding the
  role labels before the composer sees them. (This is the "universal node
  extraction" ceiling.)
- **C-ABS-02 (INCORRECT):** given that flattened list, the narrator names both
  ids but **refuses to say which is standard vs meta** — a self-imposed non-answer
  on a question that demanded exactly that distinction.
- **C-ABS-01 (INCORRECT, the worst):** the narrator went further and stated *"the
  evidence does not contain the identifiers for the standard or meta ancestors"* —
  **flatly false**, since `related` held CAPEC-66 and CAPEC-248. This is the one
  true faithfulness failure in the whole run (f=0.15): asserting absence of
  evidence that is present.

**Fix path:** preserve edge-role/ordering through normalization so the composer
can label parent vs grandparent; and the narrator should never claim evidence is
absent when `related` is non-empty.

---

## 6. Buckets D–F — minor and benign

- **D. Over-generalization (A-DET-02, F-CTM-01):** collapses N neighbours into one
  blanket sentence that overstates one member (e.g. all 5 analytics described as
  "failed auth followed by successful login" when AN1278 is only "failed auth").
  Real but small faithfulness softness (0.75–0.95).
- **E. Citation mechanics (C-EXE×3, A-TAC-02, C-PRE-01, A-CMP-TEC-01):** the prose
  is fully correct — e.g. C-EXE cases narrate all 4–6 execution steps accurately —
  but the structured `claims` array only cites the primary id, not the per-step
  ids, so groundedness is docked to ~0.85. **Not a content failure**; a
  provenance-metadata gap. These are effectively CORRECT.
- **F. Surfacing gaps (F-PART-04):** the pipeline behaves correctly (source-down →
  honest dependency skip), but the *reason* ("CAPEC source skipped") lives only in
  the internal `notes`, not the analyst-facing narrative, so the reader isn't told
  why data is missing.

---

## 7. Meta-finding: the deterministic metrics are blind to mitigations

Several agents noted it independently (clearest at F-CTM-01): the pipeline's own
`deterministic_scores` — correlation, mapping_recall, provenance, inspectability —
were **all 1.0**, yet the answer missed **70% of the required mitigation ids**.
Those four metrics never score mitigation coverage, which is *why the skynet
self-judged run looked flawless*. The completeness gap only becomes visible when a
judge checks the answer against `must_include_related`, which the independent pass
did and the deterministic scorers do not.

---

## 8. Corrected bottom line

- **Faithfulness is excellent (~0.99 corrected).** The two things that looked like
  fabrication were faithful reads of `facets`/`properties` my harness stripped.
  The single genuine faithfulness failure is C-ABS-01's false "evidence absent."
- **The real defect is completeness via under-enumeration.** The pipeline
  retrieves everything and then names only a sample. This is the skynet-run
  finding, now confirmed by an independent model against gold — and it's the
  highest-value fix (composer should enumerate the full `related` set for
  "which/what" questions).
- **One narrow correctness bug:** the C-ABS hierarchy role-labeling (normalization
  drops parent/grandparent order; narrator then refuses or misreports).
- **The independent panel was rigorous** — it caught real omissions the
  deterministic metrics miss, and even self-diagnosed the harness artifacts — but
  its faithfulness/groundedness numbers are **depressed by my serializer** and
  should be read as a floor, not the truth.

---

## 9. Recommended next steps (in priority order)

1. **Fix the judging artifact** (`_record_dict`: add bounded `properties` +
   `facets`, lift the 40-record cap) and re-run the 120-agent pass → a true,
   un-penalized faithfulness/groundedness read.
2. **Fix under-enumeration** (Bucket B): have the composer enumerate the full
   `related`/`join_values` set (or a much larger cap) for "which/what" questions —
   this is the single biggest correctness lever.
3. **Fix C-ABS** (Bucket C): preserve parent/grandparent role order through
   normalization; forbid "evidence absent" claims when `related` is non-empty.
4. **Add a mitigation-coverage metric** to `deterministic_scores` so the blind
   spot in §7 can't recur.
