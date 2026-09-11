# RESULTS — EXP-2026-09-018 Correctness repair

**Status: planned. No result yet.** The protocol was pre-registered on
2026-09-11 before any repair code was changed; `PROTOCOL.md` holds the six
hypotheses, their thresholds and the kill gate. This file is filled in as the
steps complete, and nothing is written here that `data/metrics.json` does not
carry.

**Disclosure, to appear in the first paragraph of the finished write-up.**
`EXP-2026-09-005` repaired the *template* arm before comparing the arms.
Everything in this experiment repairs the *generic* arm, and so widens a gap
`C-023` already reports in the generic arm's favour. `C-023`'s evidence column
is amended, not replaced. Scoring corrections (`Q44`, `Q48`) are reported apart
from capability gains.

## Step 0 — recorded, corrected, pre-registered (complete, 2026-09-11)

No model, no judge.

- **Mechanism table recorded** as `EXP-2026-09-017` `AMENDMENT A-2`, with
  `data/mechanisms.py` and `data/mechanisms.csv` in that experiment. The
  assignment is first match over six predicates and reproduces the published
  0.6569 and 0.4946 exactly. The row that matters most: on the 67 dev questions
  where no mechanism fires, the generic arm scores **0.9675**.
- **`Q47`'s audit corrected** as `EXP-2026-09-016` `AMENDMENT A-8`. The
  2026-09-10 audit divided fallback counts by the number of *files* in each
  answer directory, which also holds two or more judgment sidecars per answer.
  Over answers the rates are **0.43** (dev), **0.30** (holdout) and **0.07**
  (expansion) against a healthy reference of 0.14. "No published figure is
  affected" is withdrawn. Every one of the 227 fallbacks is a narrator read
  time-out, not the specialist-seam failure `I-4` is about.
- **`Q49` indexed; `Q50`–`Q53` filed** in `OPEN_QUESTIONS.md`.
- **Holdout state pinned.** `scripts/holdout_seal.py` records `sealed: false` —
  the holdout was spent by `holdout-spend-2026-09-05`, 1,152 judgments per arm.
  `data/holdout_seal_prerepair.json` is that state before any repaired arm
  existed, so a later holdout answer is attributable to this experiment.
- **References captured** for `deterministic` and `generic_composed` over both
  banks at `cbb48502`, summarised in `data/reference/reference.json`.

| capture | n | mean gold coverage | zero-record |
|---|---:|---:|---:|
| dev / `deterministic` | 284 | 0.504786 | 25 |
| dev / `generic_composed` | 284 | 0.599039 | 77 |
| holdout / `deterministic` | 288 | 0.539585 | 26 |
| holdout / `generic_composed` | 288 | 0.636105 | 68 |

Two checks on the capture, both passed. The dev `deterministic` mean gold
coverage of **0.504786** is exactly `EXP-2026-09-005`'s. And the 77 zero-record
`generic_composed` dev cases fall into `A-2`'s mechanisms in exactly the
predicted counts — **34 `capec`, 21 `ns`, 16 `chain`**, plus 6 in `none` — which
is the mechanism attribution reproducing on a fresh run of a *different arm*
from the one it was derived on.

Two issues are recorded rather than smoothed over: the reference is not
byte-identical to the 2026-09-03 run and the difference is facet metadata
(`ISSUES` I-1), and the first capture ran against an empty CAPEC store and was
discarded (`ISSUES` I-2).

## Steps 1–8

Not started.
