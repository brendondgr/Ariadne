# ISSUES — EXP-2026-09-006

Things that went wrong, were wrong, or limit what this experiment can say.
Written as they were found, not reconstructed afterwards.

## I-1 — The second grader is saturated on the C-021 arm and cannot measure it

`gemma4-31B-mtp` returned **exactly 1.0 on all 120 catalogue answers and all 30
blind answers**, across both grading positions. Zero variance, both sets.

Its C-021 gap of **+0.0000 is a property of the instrument, not of the
questions**: a grader with no spread returns a gap of zero whatever is true.
For comparison, on the same 120 catalogue answers `qwen38-27B-v2` places 11
below 1.0 and the unidentified August model places 27 below.

**Consequence.** C-021 is adjudicated by the named qwen pass alone. gemma
contributes a null with a stated reason and **must not be reported as a second
family agreeing that the gap is zero.** That sentence would be the most
misleading claim available from this experiment.

Saturation is now computed per cell (`saturated`, `frac_at_ceiling`, `sd` in
`data/rollup.json`) rather than noticed by eye, and the sign-flip check is
guarded on it — a saturated grader cannot flip a sign because it never had one.

**Scope of the problem.** Saturation is a ceiling effect, not a defect in the
model. On the two blind banks, where scores are spread, gemma is saturated in
**0 of 12 cells** (`llm_query` sd 0.32–0.35, `merged` 0.17), so it remains a
usable second family exactly where H1 is decided. Checked separately: it is
**not** saturated on the post-repair arms either (sd 0.42–0.45 against qwen's
0.30–0.33), so `EXP-2026-09-005`'s cross-family confirmation is unaffected.

**The general lesson, which belongs in the paper.** The two graders differ in
*shape*, not only in level: gemma grades close to binary, qwen grades with
partial credit. That one fact explains gemma's higher spread on mixed banks,
its all-1.0 on a near-ceiling bank, and its wider arm gap on identical answers.

## I-2 — One transient grading failure, since resolved

`F-FAN-02` (`composerfix-dev`) returned HTTP 400 after three attempts in gemma's
first pass. qwen graded the same answer without incident, and gemma graded it
successfully in its own second pass, so it was **endpoint load, not a rejection
of the content**. It is not the largest answer in the set; five larger ones
passed. Recorded because a dropped case must never be silently absorbed — an
earlier `.cross` pass dropped exactly the three lowest-scoring `llm_query`
answers and read 0.24 high as a result.

## I-3 — The recorded C-021 figure is over 119 answers, not 120

The unidentified August pass dropped `C-SCN-01`, the 476 KB answer, so the
**+0.0483** on record is a mean over 119 catalogue answers. Both named passes
cover all 120. The difference is immaterial to the conclusion and is stated
because the denominators are not identical.

## I-4 — The two tracks shared one state file

The gemma and qwen tracks are separate OS processes and were writing the same
JSON state file, each holding its own in-memory dict, so each overwrote the
other's records. **Bookkeeping corruption, not data corruption** — the
judgments are sidecar files and those are authoritative — but a run record that
silently disagrees with the run is exactly the class of defect this project
keeps finding. Fixed to one file per track, and `scripts/cross_family_rollup.py`
reads sidecars only and never consults a state file.

## I-5 — What this experiment cannot say

- **Nothing about levels.** Between-family offsets are large relative to
  within-family spread and the levels were never quotable. This measures
  *ordering* and *contrast sign*.
- **Nothing about a third family.** Two families is not a panel.
- **Nothing new about the August question sets.** ±0.06 question-sampling at
  n=30 still dominates every margin below 0.06, C-022's included. A null that
  survives a grader change is still a null over 30 questions.
