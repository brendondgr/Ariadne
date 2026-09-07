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
