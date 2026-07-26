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
