# POINTERS — EXP-2026-09-018

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

## Step 0 — pre-repair model-free references

Captured 2026-09-11 at `cbb48502` **after** reloading the CAPEC fixture into
Gremlin (see `ISSUES.md` I-2 — the first capture ran against an empty CAPEC
store and was discarded). Answer directories are gitignored raw run output
(D-033); what is committed is `data/reference/reference.json`, a per-case digest
with the clock keys stripped plus records, gold coverage, claim and abstention
counts.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| dev reference, `deterministic` (gitignored) | `docs/evaluation/experiments/repair-reference-2026-09-11-dev/deterministic/answers` | 22090767 | `sha256:d7468b38ccb9f7ce232e89db6b82ae374141b0b4932cfa69c7fc43d68045c1a6` | 284 answers, mean gold coverage 0.504786, 25 zero-record. Reproduces `EXP-2026-09-005`'s deterministic dev coverage exactly |
| dev reference, `generic_composed` (gitignored) | `docs/evaluation/experiments/repair-reference-2026-09-11-dev/generic_composed/answers` | 6470440 | `sha256:02c3fc61378ee4325ec05abdc8d201215d70a8a6be91f5390d20600fe1b6ba96` | 284 answers, mean gold coverage 0.599039, 77 zero-record — 34 `capec`, 21 `ns`, 16 `chain`, 6 `none`, reproducing `EXP-2026-09-017` `A-2`'s attribution on a fresh run |
| holdout reference, `deterministic` (gitignored) | `docs/evaluation/experiments/repair-reference-2026-09-11-holdout/deterministic/answers` | 25556950 | `sha256:82c556a37cdce6855b369c13a5cc71ea6599d0b8259853567ade898bbd8fd497` | 288 answers, mean gold coverage 0.539585, 26 zero-record |
| holdout reference, `generic_composed` (gitignored) | `docs/evaluation/experiments/repair-reference-2026-09-11-holdout/generic_composed/answers` | 7811405 | `sha256:fa048b4770ea44e30871b17b831df86caf73f289be369bf3a5809d9c311a32f7` | 288 answers, mean gold coverage 0.636105, 68 zero-record |
| reference summary (committed) | `docs/research/experiments/EXP-2026-09-018-correctness-repair/data/reference/reference.json` | 281717 | `sha256:4a9b0b01875aedb8dfb91b45ff416d2ef780b56957d1cd69478ac75a1b8503ea` | the per-case digests every Step 1–4 diff runs against |
| holdout seal, pre-repair (committed) | `docs/research/experiments/EXP-2026-09-018-correctness-repair/data/holdout_seal_prerepair.json` | 873 | `sha256:0f5f9ae3ee4c236292c642e4a41717949f333d882340d471a81244d441a71d86` | `sealed: false` — the holdout was spent by `holdout-spend-2026-09-05`; this is the state before any repaired arm existed |

## Inputs read from other experiments

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| mechanism assignment | `docs/research/experiments/EXP-2026-09-017-correctness-improvement-diagnostic/data/mechanisms.csv` | 38668 | `sha256:1c6afaa0bc96b7cf26118f5183eaa78c9eb23f82db984e18469003c5f89848d6` | the per-case mechanism slices every hypothesis is read over, fixed at the pre-repair commit |
| dev bank | `docs/evaluation/composition/bank/bank-dev.json` | 573495 | `sha256:a4ca6702029cae7784574b0307b9f76d4718a039f3254f2c0ff708a2fa1a4119` | the 284 selection questions |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
