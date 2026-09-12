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

## Step 4b — the data-matched control, and the run after the data fixes

`Q54` and `Q55` changed the graph, so the Step 0 reference no longer differs
from the repaired arms in code alone. A **second** pre-repair capture was taken
at `e09c2571` against the fixed data. Diffing against the Step 0 reference gives
the programme's whole effect, code and data together; diffing against this one
isolates the code. Both are kept, because collapsing them would make it
impossible to say which moved a number.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| control, dev `deterministic` | `docs/evaluation/experiments/repair-reference-datafix-2026-09-11-dev/deterministic/answers` | 22804326 | `sha256:201e6680675431c077d92bcfaae0d2a2e62ff37090d674f40c37d06f91154ffa` | pre-repair code at `e09c2571`, post-fix data; mean gold coverage 0.510067 |
| control, dev `generic_composed` | `docs/evaluation/experiments/repair-reference-datafix-2026-09-11-dev/generic_composed/answers` | 6561547 | `sha256:afb1bc32db48eb4e65bdb2a0499d0205e07cdec5cf038673bcdcee304547ad8b` | 0.626244, 60 zero-record |
| control, holdout `deterministic` | `docs/evaluation/experiments/repair-reference-datafix-2026-09-11-holdout/deterministic/answers` | 26384734 | `sha256:60746f3f74d7950b0e39f978f69ac11c6a69e4757b4dff0f0e444792103e64cf` | 0.541321 |
| control, holdout `generic_composed` | `docs/evaluation/experiments/repair-reference-datafix-2026-09-11-holdout/generic_composed/answers` | 7907390 | `sha256:fb87a7e91d484f771477838b4a9776a4829a3af9d1c13d13476e48706e6678a1` | 0.658569, 53 zero-record |
| after 4b, dev `deterministic` | `docs/evaluation/experiments/repair-after-step4b-dev/deterministic/answers` | 22890346 | `sha256:75c6bf1914f069c4fb2b400d02624bda9515e5b7727e90ca03a2075470be2818` | 0.538471 |
| after 4b, dev `generic_composed` | `docs/evaluation/experiments/repair-after-step4b-dev/generic_composed/answers` | 6557712 | `sha256:b895fb26913fb707bd9684b3c33785392d7d47aa1bc3e88f2a5a433daf9ec7ca` | 0.700967, 31 zero-record, coverage lost on none |
| after 4b, holdout `deterministic` | `docs/evaluation/experiments/repair-after-step4b-holdout/deterministic/answers` | 26561023 | `sha256:c8449ca6ff3fcd1de819a374c26fc21d07bc404d058c91d0c9f90390a60bb587` | 0.552317 |
| after 4b, holdout `generic_composed` | `docs/evaluation/experiments/repair-after-step4b-holdout/generic_composed/answers` | 7945103 | `sha256:02f1a5c29711184e87ae4ea6a1f2da85090ea6ddde7693aa772cc22ad64d8436` | 0.719427, 28 zero-record, coverage lost on none |

## Step 5 — the frozen-evidence pair

Two compositions over byte-identical evidence, graded by one judge in one
sitting, each in both counterbalanced positions.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| original composition + judgments | `docs/evaluation/experiments/frozen-2026-09-11/generic_original/answers` | 7268861 | `sha256:5f9c0315ce400f4f97d0c4208431584c13e2980fde7742ac3539e6dcbff906f5` | the 284 saved `EXP-2026-09-005` generic answers, re-graded here rather than quoted; paired mean 0.6588 |
| repaired composition + judgments | `docs/evaluation/experiments/frozen-2026-09-11/generic_recomposed/answers` | 7288196 | `sha256:60d7309dbd051df044e5ae7d5a3a07e8ad51017195f7651974378ac99087ba45` | the same evidence recomposed; paired mean 0.6794 |
| recomposition summary (committed) | `docs/evaluation/experiments/frozen-2026-09-11/recompose-summary.json` | 339 | `sha256:8136ab25ebaafc8a0a2a775ce4550f24b72ce8f7177dcf93dcc0bc38a184a658` | 26 changed, 258 unchanged, requested values 6 of 19 → 19 of 19 |
| judged metrics (committed) | `docs/evaluation/experiments/frozen-2026-09-11/frozen-metrics.json` | 1991 | `sha256:9d7e8b40f2ef56b41a871a31975db31efe88c0c3064d3a1d7796e24403e5e378` | drift control, paired means, tier table, kill gate |

## Inputs read from other experiments

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| mechanism assignment | `docs/research/experiments/EXP-2026-09-017-correctness-improvement-diagnostic/data/mechanisms.csv` | 38668 | `sha256:1c6afaa0bc96b7cf26118f5183eaa78c9eb23f82db984e18469003c5f89848d6` | the per-case mechanism slices every hypothesis is read over, fixed at the pre-repair commit |
| dev bank | `docs/evaluation/composition/bank/bank-dev.json` | 573495 | `sha256:a4ca6702029cae7784574b0307b9f76d4718a039f3254f2c0ff708a2fa1a4119` | the 284 selection questions |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
