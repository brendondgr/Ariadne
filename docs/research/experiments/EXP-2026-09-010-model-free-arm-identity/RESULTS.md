# RESULTS — EXP-2026-09-010 — do the model-free arms actually repeat?

**Run 2026-09-06/07.** Two arms, two full runs each over 284 questions.
Hypotheses pre-registered; amendments A-1, A-2 and A-3 record what the run
found along the way and are part of the result.

---

## Headline

**The query path is reproducible. The composition seam is not — and it is the
composition that gets scored.**

| Arm | compared | identical | verdict |
|---|---|---|---|
| `deterministic` | 284 | **284** | **content-identical** |
| `generic` | 276 *(8 excluded)* | 133 | **differs in a scored field** |

`deterministic` is byte-identical in every field the scorer reads. `generic`
differs on **143 of 276** answers — and every difference is in exactly one place:

```
answer.narrative     143
```

**Nothing else moved.** Retrieval, coverage, claims, gold matching, evidence: all
identical across both runs. The variation is confined to the prose a language
model writes at the end.

---

## What this establishes

**1. The architectural claim survives, and is now measured.** No language model
writes a query on either arm, and the consequence is visible: **retrieval is
byte-identical across independent runs of both arms.** The paper has asserted
that determinism; this is the first direct measurement of it, and it holds.

**2. `deterministic` needs no replication.** 284/284 identical in every scored
field, modulo two clock keys. `n_runs: 1` on that arm is **sufficient by
construction**, and that is now a measurement rather than an assumption. This is
a stronger statement than a mean ± SD over three draws would have given.

**3. `generic`'s single-draw figures are not defensible on the same grounds.**
Its composition seam calls a language model (`run_meta.synthesis: "llm
(claim-grounded)"`, amendment A-2), and 52% of its answers are worded differently
on a rerun **at the same seed**. Whatever `EXP-2026-09-002`, `-005` and `-007`
measured for this arm, they measured one wording of it.

**4. What this does *not* say.** A different wording is not necessarily a
different score. Two phrasings of the same retrieved facts may grade identically,
and the verifier constrains what the narrator may assert. **How much of this
variation reaches the judged number is `EXP-2026-09-011`**, which this result
promotes from useful to necessary.

## Against the pre-registered table

| Outcome | Consequence, decided beforehand |
|---|---|
| H1 (`deterministic` identical) | ✅ **holds** — no further replication owed |
| H2 (`generic` identical) | ❌ **fails** |
| H3 (differences avoid scored fields) | ❌ **fails** — `answer.narrative` is the field the grader reads |

The pre-registration said the H3 row was the expensive one and that it would be
reported rather than re-run away. It is reported.

Its stated consequence was that `C-023`'s judged figures "cannot be quoted as
point estimates". **That consequence is now conditional on `EXP-2026-09-011`**,
because this experiment localised the variance to a seam whose effect on the
score is measurable and not yet measured. Quoting it as settled either way would
overstate what is known.

---

## Method notes that are part of the result

Three guards in this experiment were wrong, each in a way the data exposed. All
three are recorded in `PROTOCOL.md` amendments rather than quietly repaired.

**A-1 — the volatile-key list was built by prediction, not observation.** The
pre-registered exclusion missed `run_meta.wall_s`, so `deterministic` first read
2/284 rather than 284/284. The list had been derived by regex-matching key names
in **one** artifact of a **different arm**. The correct method is the one the run
performed: run twice and see what moves.

**A-2 — the first `generic` attempt was invalid.** Its narrator died mid-run; 60
of 284 answers were silently degraded and the harness returned success. The
capture looked like arm non-determinism and was one inspection from being
reported as such. It also established the fact that reframed this whole
experiment: `generic` is not model-free.

**A-3 — one question cannot be narrated at all**, in any run:
`D4-mitigates-uses-M1047-b63672::indirect` exceeds the context window by a single
token, deterministically.

**The acceptance rule was also wrong, and its failure mode was arithmetic.**
Requiring a capture with zero transient failures looked prudent. At the observed
~0.7% per-answer rate, P(a capture is perfect) = 0.134, so demanding two perfect
captures within three attempts each succeeds ~12% of the time. The comparison
never needed perfect captures — it needed to know which answers to exclude. Both
final captures carried 5 transient failures and 1 deterministic one; **8 answers
were excluded and 276 compared.**

---

## Limits

- **Identity within one process lifetime**, on one machine, against one store
  state. It does not test across a reload, a restart, or different hardware —
  the weakest form of the claim, and the one actually relied upon.
- The `generic` captures ran with the narrator pinned to `:9090/default-model`
  rather than `.env`'s `:4000/skynet`, which was failing. Same backend by
  operator confirmation; recorded as a deliberate deviation.
- **8 of 284 answers excluded** for transient narration failure. If those 8 were
  systematically different from the rest, the 0.4819 identity rate is biased; we
  have no reason to think so and no evidence either way.
- Two runs give identity or non-identity. They do **not** give a distribution over
  wordings, and no claim here depends on one.

---

## AMENDMENT A-1 (2026-09-09) — record repair: the manifest was a scaffold with results bolted on

**What was wrong.** `manifest.yaml` carried `status: complete` with
`date_completed: null`, `authors: []`, template prose in `purpose` and
`hypothesis`, `code.entrypoint: "<exact command>"`, `data.*` placeholders
with `n_examples: 0`, `compute.hardware: "<cpu/gpu, ram>"` with
`wall_clock_hours: 0.0`, `llm.model: "<provider>/<model>@<version-or-date>"`
with `max_tokens: 2048`, and `metrics.primary: identity_rate_content` — a
name that is not a key in `metrics.values`. `data/POINTERS.md` was the empty
template, `data/metrics.json` did not exist, and `ISSUES.md` was empty although
`code.dirty: true`, `seeds: []`, three guard defects (PROTOCOL A-1..A-3) and a
deliberate endpoint deviation are all ISSUES-shaped.

**What is now recorded (old → new), and how each was established.**

| field | was | is | established from |
|---|---|---|---|
| `date_completed` | `null` | `2026-09-07` | `b-try1` capture `finished` 2026-09-07T00:00:05 (`generic-rerun-state.json`); completion commit `e76eab1` 00:03 |
| `authors` | `[]` | `[brendondgr]` | git author of `9e79114`, `0f2d81b`, `1bcf3bb`, `62d7097`, `e76eab1` |
| `purpose`, `hypothesis` | template text | filled from PROTOCOL.md; H1–H3 quoted with outcomes | PROTOCOL.md (2026-09-06, before any run) and its amendments |
| `code.entrypoint` | `<exact command>` | `arm_identity_check.py --workers 32` → `generic_identity_rerun.py` → `arm_identity_analyse.py` | the three scripts' docstrings |
| `data.*` | placeholders, `n_examples: 0` | `bank-dev.json`, dev half, 284, `hash` = pre-flight sha256 | `run-state.json` and `generic-rerun-state.json` `preflight.bank_sha256`; re-hashed 2026-09-09, identical |
| `compute.hardware` | placeholder | CPU-only deterministic arm; narrator on `:9090/default-model` (re-run) / `:4000/skynet` (first pair); 32 workers | `generic-rerun-state.json` `narrator`; PROTOCOL A-2; RESULTS Limits |
| `compute.wall_clock_hours` | `0.0` | `1.1` | sum of the six recorded `elapsed_s` (3,896 s); the aborted `a-try2` attempt is unrecorded |
| `llm.model` | placeholder | `relay/qwen38-27B-v2@2026-09-06` | `generic-rerun-state.json` `preflight.narrator`, read from the response envelope |
| `llm.max_tokens` | `2048` (template) | `16384` | the context-overflow message quoted in PROTOCOL A-3 ("requested 16384 output tokens") |
| `llm.nondeterminism_note` | template | states what was measured and what was excluded | this RESULTS |
| `metrics.primary` | `identity_rate_content` (not a key) | `identity_rate_deterministic` | the headline row of the table above; `identity_rate_generic` is the second |
| `related` | `[]` | `[EXP-2026-09-002, -005, -007, -009, -011]` | the single-draw `generic` figures this bears on, and the sibling seeded experiments |

No value in `metrics.values` changed. The 2026-09-09 audit (verify-b6,
`r010.py`) reproduced 284/284 (excluding `timing_ms` + `wall_s`), 2/284
(excluding `timing_ms` only), and 276 / 133 / 0.4819 / 143 under the documented
exclusion of the eight transient-failure answers, and confirmed
`run_meta.synthesis` = `deterministic` / `llm (claim-grounded)` on the captures.

**Pointers.** `data/POINTERS.md` now lists both capture trees and the bank
file with bytes and SHA-256 as of 2026-09-09; neither tree has been written to
since 2026-09-07 00:00. **Metrics file.** `data/metrics.json` created with every
`metrics.values` entry, the deterministic comparison block from
`run-state.json`, the final generic comparison block from
`generic-rerun-state.json`, and the invalidated first pair labelled as such.

## AMENDMENT A-2 (2026-09-09) — `data/identity-analysis.json` holds the invalidated first `generic` pair

`data/identity-analysis.json` is titled as this experiment's analysis and its
`generic` block reports 224/284 identical (0.7887), "DIFFERS IN A SCORED
FIELD", with `answer.fallback_reason` differing on 60 answers. That is the
**first** generic pair — `arm-identity-2026-09-06/{a,b}` — whose run B lost its
narrator on 60 of 284 answers and which PROTOCOL A-2 records as `not_run`. The
file was written by `scripts/arm_identity_analyse.py` at `1bcf3bb`
(2026-09-06 19:38) and nothing in it said so. The figures this RESULTS and the
manifest report for `generic` (276 compared, 133 identical, 0.4819,
`answer.narrative` 143) come from the guarded re-run and live only in
`data/generic-rerun-state.json`. Its `deterministic` block (2/284 → 284/284) is
the reported result.

The file is kept — it is the evidence for A-2 — and gains a
`status_2026-09-09` field saying the above. Nothing else in it was changed.

## AMENDMENT A-3 (2026-09-09) — the "~0.7 % per-answer rate → P = 0.134" line is unsourced

§"Method notes" (lines 97–99) says the acceptance rule failed arithmetically
because "at the observed ~0.7 % per-answer rate, P(a capture is perfect) =
0.134". (1 − 0.007)^284 = 0.136, so the line is internally consistent, but no
file in `data/` records a 0.7 % rate. What the manifest records is
`transient_failure_rate_per_answer` **0.0176** (5 transient failures per
capture, `generic-rerun-state.json` `corrupt_rate`), under which
P(perfect capture) = (1 − 0.0176)^284 = **0.0065** — which makes the argument
stronger, not weaker: demanding perfect captures was even less likely to
succeed than the prose says. The 0.7 % figure is not corrected because its
source cannot be established; it should not be quoted. The conclusion (exclude
the failed answers rather than demand a perfect capture; 8 excluded, 276
compared) is unaffected.
