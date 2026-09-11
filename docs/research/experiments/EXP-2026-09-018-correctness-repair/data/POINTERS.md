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
| dev reference, `deterministic` (gitignored) | `docs/evaluation/experiments/repair-reference-2026-09-11-dev/deterministic/answers` | 22090720 | `sha256:8becb948ba2278282b7dffa1879efd8fdae480e3321569f0f5b8d07134432f1d` | 284 answers, mean gold coverage 0.504786, 25 zero-record. Reproduces `EXP-2026-09-005`'s deterministic dev coverage exactly |
| dev reference, `generic_composed` (gitignored) | `docs/evaluation/experiments/repair-reference-2026-09-11-dev/generic_composed/answers` | 6470534 | `sha256:9f9597ceeeaee48181830a79f5764f276165323f7f8aa7389ff788004ea7693c` | 284 answers, mean gold coverage 0.599039, 77 zero-record — 34 `capec`, 21 `ns`, 16 `chain`, 6 `none`, reproducing `EXP-2026-09-017` `A-2`'s attribution on a fresh run |
| holdout reference, `deterministic` (gitignored) | `docs/evaluation/experiments/repair-reference-2026-09-11-holdout/deterministic/answers` | 25556953 | `sha256:3628ea24ae4b80a4d398324bf3c33fdcb701bef4d80f331bd3ab915efafe1ad0` | 288 answers, mean gold coverage 0.539585, 26 zero-record |
| holdout reference, `generic_composed` (gitignored) | `docs/evaluation/experiments/repair-reference-2026-09-11-holdout/generic_composed/answers` | 7811412 | `sha256:673e1e03e889e990bacee35ff471b8cc9dd6d587e91dfaaa056ff2bbf3ed8ae8` | 288 answers, mean gold coverage 0.636105, 68 zero-record |
| reference summary (committed) | `docs/research/experiments/EXP-2026-09-018-correctness-repair/data/reference/reference.json` | 281717 | `sha256:4a9b0b01875aedb8dfb91b45ff416d2ef780b56957d1cd69478ac75a1b8503ea` | the per-case digests every Step 1–4 diff runs against |
| holdout seal, pre-repair (committed) | `docs/research/experiments/EXP-2026-09-018-correctness-repair/data/holdout_seal_prerepair.json` | 873 | `sha256:0f5f9ae3ee4c236292c642e4a41717949f333d882340d471a81244d441a71d86` | `sealed: false` — the holdout was spent by `holdout-spend-2026-09-05`; this is the state before any repaired arm existed |

**Re-hashed 2026-09-11** after the reference was re-created at `e09c2571`
(`ISSUES` I-3). A tree hash over raw answers covers the `timing_ms` and `wall_s`
values embedded in them, so it does **not** survive a re-run even when the run
is otherwise identical — the stable artifact is `data/reference/reference.json`,
whose digests strip those keys.

The reference **regenerates**: re-running the four arms from a clean checkout at
`e09c2571` reproduces all 1,144 committed digests
(`capture.py --verify`, 284/284, 284/284, 288/288, 288/288). Nothing repaired is
ever written under the `repair-reference-` prefix.

## Step 1 — after the Category/View namespace repair

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| dev, `deterministic` (gitignored) | `docs/evaluation/experiments/repair-after-step1-dev/deterministic/answers` | 22090687 | `sha256:66e373342e96e52f55d7e38dd8417d8cc1a0fd70e788f5ee3a08ae88b9b26a22` | 284 answers, 0 of 284 changed against the reference |
| dev, `generic_composed` (gitignored) | `docs/evaluation/experiments/repair-after-step1-dev/generic_composed/answers` | 6967368 | `sha256:d8efdc877bfa3516a3b8e8b36ffa5931f7ad5c3c5f4365931beb8752c3660d20` | 284 answers, mean gold coverage 0.632121, 26 changed, coverage lost on none |
| holdout, `deterministic` (gitignored) | `docs/evaluation/experiments/repair-after-step1-holdout/deterministic/answers` | 25556923 | `sha256:56b7525fdfa21355be66ca7c857230d6d814f50760b80fd8c90aa19c1ac53742` | 288 answers, 0 of 288 changed |
| holdout, `generic_composed` (gitignored) | `docs/evaluation/experiments/repair-after-step1-holdout/generic_composed/answers` | 8172958 | `sha256:ebc28629e84d5cafde6477549e1ae547897accd8b567f758ceefcc5ca94f04ad` | 288 answers, mean gold coverage 0.667945, 27 changed, coverage lost on none |

## Step 2 — after the CAPEC allowlist completion

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| dev, `deterministic` (gitignored) | `docs/evaluation/experiments/repair-after-step2-dev/deterministic/answers` | 22090766 | `sha256:ef4bd2c9c6bc6f0ad65c1e3e798652c9c4c254b8610c731fd00d08261de2ebd7` | 284 answers, 0 of 284 changed against the reference |
| dev, `generic_composed` (gitignored) | `docs/evaluation/experiments/repair-after-step2-dev/generic_composed/answers` | 7153914 | `sha256:5438dd1e191735cadc56dbe6c16f865b05fba2552cb5af8cea0e5bf1c18ad1c9` | 284 answers, mean gold coverage 0.654044, 55 changed cumulatively, coverage lost on none |
| holdout, `deterministic` (gitignored) | `docs/evaluation/experiments/repair-after-step2-holdout/deterministic/answers` | 25556863 | `sha256:642210c7cf533c8506a726d1bbda20006df62039dfc99372d5f6ef9c48c6b57f` | 288 answers, 0 of 288 changed |
| holdout, `generic_composed` (gitignored) | `docs/evaluation/experiments/repair-after-step2-holdout/generic_composed/answers` | 8257423 | `sha256:1b3f4efdd64ad011907f529ee21b0a3f47bb4ec8007c106c4f033d6862ce59ea` | 288 answers, mean gold coverage 0.688673, 45 changed cumulatively, coverage lost on none |

## Step 3 — after the chained walk

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| dev, `deterministic` (gitignored) | `docs/evaluation/experiments/repair-after-step3-dev/deterministic/answers` | 22090772 | `sha256:ce0d266236bc2fee88f8bd25d7ed164914a663ad331fb868e6d6c37de1cff1d9` | 284 answers, 0 of 284 changed against the reference |
| dev, `generic_composed` (gitignored) | `docs/evaluation/experiments/repair-after-step3-dev/generic_composed/answers` | 7391299 | `sha256:c6fd957b16e29758969768e717f42380edfc640265878130877f0e52beb3c401` | 284 answers, mean gold coverage 0.667281, 31 zero-record, coverage lost on none |
| holdout, `deterministic` (gitignored) | `docs/evaluation/experiments/repair-after-step3-holdout/deterministic/answers` | 25556917 | `sha256:bdeed2105b7176d83f327a78f76b6f26f2f046124ffd8fb19d0762814d4f6859` | 288 answers, 0 of 288 changed |
| holdout, `generic_composed` (gitignored) | `docs/evaluation/experiments/repair-after-step3-holdout/generic_composed/answers` | 8668190 | `sha256:a06a53e679b30d0bc7df34c0281ddae006087a6e2b5f09d446645cabf31a7b21` | 288 answers, mean gold coverage 0.706696, 28 zero-record, coverage lost on none |

## Step 4 — after the answer contract

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| dev, `deterministic` (gitignored) | `docs/evaluation/experiments/repair-after-step4-dev/deterministic/answers` | 22152658 | `sha256:65519e81b0fe6ebc39d00c982403626b8a3f0fba716660dd9293358c44c46c4b` | 284 answers, mean gold coverage 0.533190, records unchanged on all 284 |
| dev, `generic_composed` (gitignored) | `docs/evaluation/experiments/repair-after-step4-dev/generic_composed/answers` | 7357986 | `sha256:57940fc06ea9845c3ac3da7770bf286e64a79025971a1e922cf5cce39bf51415` | 284 answers, mean gold coverage 0.695685, 31 zero-record, coverage lost on none |
| holdout, `deterministic` (gitignored) | `docs/evaluation/experiments/repair-after-step4-holdout/deterministic/answers` | 25691265 | `sha256:cdf65e1f75248ad083629ecadc00d1db0abfd412fe1c7a1722e96d1c838bba17` | 288 answers, mean gold coverage 0.550581 |
| holdout, `generic_composed` (gitignored) | `docs/evaluation/experiments/repair-after-step4-holdout/generic_composed/answers` | 8687856 | `sha256:12b67b50075a696c145a2c947785d7575a8eecf4e639084a34a663342d5e9c15` | 288 answers, mean gold coverage 0.717691, 28 zero-record, coverage lost on none |

## Inputs read from other experiments

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| mechanism assignment | `docs/research/experiments/EXP-2026-09-017-correctness-improvement-diagnostic/data/mechanisms.csv` | 38668 | `sha256:1c6afaa0bc96b7cf26118f5183eaa78c9eb23f82db984e18469003c5f89848d6` | the per-case mechanism slices every hypothesis is read over, fixed at the pre-repair commit |
| dev bank | `docs/evaluation/composition/bank/bank-dev.json` | 573495 | `sha256:a4ca6702029cae7784574b0307b9f76d4718a039f3254f2c0ff708a2fa1a4119` | the 284 selection questions |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
