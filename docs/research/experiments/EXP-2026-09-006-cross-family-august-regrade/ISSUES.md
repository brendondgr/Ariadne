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

## I-2 — Two transient grading failures, one on each endpoint

Both returned `HTTP Error 400: Bad Request` after three attempts:

| case | pass | prompt | outcome |
|---|---|---|---|
| `F-FAN-02` (`composerfix-dev`) | gemma `.g31` | 26,248 chars (~6.6k tok) | **cleared** on gemma's own `.g31p2` |
| `H-SUB-01` (`composerfix-holdout`) | qwen `.q38b` | 7,600 chars (~1.9k tok) | outstanding; retry queued |

**It is not the content.** Both prompts are clean — zero control characters,
zero surrogates, zero non-ASCII — and both are small; `H-SUB-01` is among the
smallest in its set at ~1.9k tokens, while five answers several times larger
graded without incident. `F-FAN-02` failed on gemma and graded fine on qwen,
then graded fine on gemma's second pass.

**Most likely cause, stated as a hypothesis rather than a finding:** admission
failure under concurrency. Both endpoints were running 16 and 24 workers with
`max_tokens=32768` at the time, and the operator's own warning about this host
is that the KV cache holds 310,144 tokens total, so a long context and high
concurrency cannot both be maxed at once. A request the scheduler cannot admit
surfaces as a 400, which is indistinguishable downstream from a rejected prompt.
Consistent with every observation: load-dependent, content-independent, and it
cleared on a retry at lower load. **Not established** — the response body was
not captured, and reproducing it required an idle endpoint we did not have.

**Handling.** Both cells are re-run at the end of the window, when the endpoints
are quiet; re-running a cell grades only what is missing. Anything still absent
is reported as dropout and excluded from paired statistics, never absorbed — an
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

## I-6 — The judgment sidecar's `model` field records a stale alias

Every judgment written by this experiment carries `judge.model: "skynet"`,
including the 689 written by gemma, because that field records the environment's
default alias rather than the alias the call actually used
(`default-model-2` / `default-model`).

`judge.served_model` is read from the response envelope and is correct:

| suffix | served_model | n |
|---|---|---|
| `.g31` / `.g31p2` | `gemma4-31B-mtp` | 689 |
| `.q38b` | `qwen38-27B-v2` | 149 |

**Consequence.** The two passes are correctly attributed and no fallback
occurred — which is the thing that had to be checked, since a relay that
silently answers from the wrong endpoint would make the whole experiment
meaningless. But **`judge.model` must never be used to identify a grader**, and
any earlier analysis that keyed on it was keying on the environment rather than
on the run. This is `D-028` appearing one level down from where it was written:
the alias is not evidence, and neither is a field that merely copies one.


## I-7 — H1 FAILS AS PRE-REGISTERED: one arm-ordering reversal

The pre-registered success condition was **zero** arm-ordering reversals. The
complete set gives **one**, and it is not a tie artifact:

**`gold_loop_llm` versus `generic_composed`, `bank20260820`**

| grader | gold_loop_llm | generic_composed | paired margin | paired sd |
|---|---|---|---|---|
| qwen38-27B-v2 | 0.9701 | 0.9424 | **+0.0276** | 0.0854 |
| gemma4-31B-mtp | 0.9950 | 0.9983 | **−0.0033** | 0.0287 |

23 pairs compared, 7 excluded as tied, **1 reversed**.

**The hypothesis is recorded as failed and the test is not being redefined
after the fact.** A noise threshold would make it pass, and adding one now —
having seen the result — would be exactly the post-hoc adjustment that makes a
pre-registration worthless.

**What the reversal is, stated separately from whether it counts.** Neither
grader resolves this pair. gemma separates the two arms by 0.0033, inside its
own within-family spread of 0.0036–0.0249 and an order of magnitude inside the
paired sd of 0.0287. qwen's +0.0276 is itself well inside its paired sd of
0.0854. Two graders disagreeing about the order of two arms that neither can
distinguish is a weak disagreement, and it is the only one in 23 pairs.

**What is unaffected.** Every claim-bearing contrast holds:
`contrast_sign_flips = 0` across C-012, C-021 and C-022. Neither arm in the
reversed pair appears in the paper's three-way comparison
(`deterministic`, `generic`, `llm_query`), and neither carries a claim of its
own.

**Consequence for the holdout.** `EXP-2026-09-007`'s stop condition reads: *any
arm-ordering reversal → hold, investigate, and write that up first*. It has been
investigated and written up here. Whether that discharges the condition is a
judgement call about an **irreversible** action, and it is recorded as a
decision rather than taken silently under deadline pressure.
