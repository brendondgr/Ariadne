# POINTERS — EXP-2026-08-020

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

Filled retrospectively on 2026-09-09 (RESULTS A-1): the table was the empty
scaffold from 2026-08-29 until then. Every file below is git-tracked under
`docs/evaluation/variants-2026-08-29/`; hashes were computed with
`uv run python -m utils.research_record.hashing` on 2026-09-09 and each file's
introducing commit was read from `git log`. **The same directory also holds
files from EXP-2026-09-014** (`reference_2026-09-08.json`, `scored_R*_tune*.json`,
all committed 2026-09-08) — those are not this experiment's artifacts and are
not listed.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Authoring inputs | `docs/evaluation/variants-2026-08-29/authoring` | 432461 | sha256:a9498a7ab4bc0f1e4d564aaab1762f9cdbf5dc165764ec2be95da70303c555d8 | Tree: `inputs.json` + 12 `batch_*.json` prompts (b040e18) and 12 `authored_*.json` Sonnet replies (25b0c5d) |
| Variant bank | `docs/evaluation/variants-2026-08-29/variants.json` | 219487 | sha256:428a23467ecf8aed1f266186504d6f68d0a9d88173cc090149558d078bdea63c | 579 gated variants over six tiers, frozen (25b0c5d) |
| Rejected variants | `docs/evaluation/variants-2026-08-29/variants_rejected.json` | 655 | sha256:4e78d650a53107733d0e9a56997067359eb722da9dff7a94368a65717daa64b3 | Variants the gate refused (25b0c5d) |
| Variants with control | `docs/evaluation/variants-2026-08-29/variants_with_control.json` | 259610 | sha256:5348761ae3e690f714e63e382a43420cc0313babbc521113f7b1870e02194207 | The 579 variants plus the 120 T0 controls = 699 runs (0ae78c1) |
| Gold reference, Arm 0 | `docs/evaluation/variants-2026-08-29/reference.json` | 323213 | sha256:76966f0c7a016c1aaa2c04741f3ac486280bc6dc66959bb99c0aff995e48d469 | Reference captured twice and proved byte-identical (61fdd8e) |
| Scored Arm 0 | `docs/evaluation/variants-2026-08-29/scored_arm0.json` | 4458400 | sha256:036705d92ab4d9f661ddc311496c389b661f07db2f91ebaba4a93c3131335267 | 699 scored runs, shipped router — the headline tier table (0ae78c1) |
| Reference, lexicon arms | `docs/evaluation/variants-2026-08-29/reference_lexicon.json` | 321431 | sha256:580f15cc2843b813837a63b9b4a6c7928f495bfc595562c0160801bf04dab19a | Reference under `ARIADNE_LEXICON` (2b48a91); identical bytes to `reference_arm2/4/5/6.json` |
| Scored Arm 1 | `docs/evaluation/variants-2026-08-29/scored_arm1.json` | 5239900 | sha256:8d352935d596d69a219bb82c3be68f2ea0d822852db54888bfa034a162526bc7 | Lexicon only (2b48a91) |
| Reference, Arm 2 | `docs/evaluation/variants-2026-08-29/reference_arm2.json` | 321431 | sha256:580f15cc2843b813837a63b9b4a6c7928f495bfc595562c0160801bf04dab19a | (2b48a91) |
| Scored Arm 2 | `docs/evaluation/variants-2026-08-29/scored_arm2.json` | 4050147 | sha256:e12c0d81afe54ce490174cb0c2cd127f230650f5995b15d845b3b9adeffb49d3 | Lexicon + no unanchored scan (2b48a91) |
| Reference, Arm 3 | `docs/evaluation/variants-2026-08-29/reference_arm3.json` | 294739 | sha256:886f376320a8a033786074eaffde84faea26d246b0c0bed97052379add0cc115 | (a65bcd9) |
| Scored Arm 3 | `docs/evaluation/variants-2026-08-29/scored_arm3.json` | 4012510 | sha256:2d3a0cb27f23a2abcc1255469a0d28f3744bb2c71cd1af647d9072121078eef2 | Arm 2 + ranked name search (a65bcd9) |
| Reference, Steps 1–2 off | `docs/evaluation/variants-2026-08-29/ref_step12_off.json` | 323213 | sha256:76966f0c7a016c1aaa2c04741f3ac486280bc6dc66959bb99c0aff995e48d469 | Identical bytes to `reference.json`: the Steps 1–2 fixes are inert on the catalogue (0dc748c) |
| Reference, Arm 4 | `docs/evaluation/variants-2026-08-29/reference_arm4.json` | 321431 | sha256:580f15cc2843b813837a63b9b4a6c7928f495bfc595562c0160801bf04dab19a | (0dc748c) |
| Scored Arm 4 | `docs/evaluation/variants-2026-08-29/scored_arm4.json` | 4062653 | sha256:741ffd59175cd07e582fd64649aa8b16a6819fa69265f0a9c1e1449611b50bea | Steps 1–2 + ranked matching (0dc748c) |
| Reference, Arm 5 | `docs/evaluation/variants-2026-08-29/reference_arm5.json` | 321431 | sha256:580f15cc2843b813837a63b9b4a6c7928f495bfc595562c0160801bf04dab19a | (538d0c0) |
| Scored Arm 5 | `docs/evaluation/variants-2026-08-29/scored_arm5.json` | 4053934 | sha256:b5afdbf92b9fd7c4a653bd2e77cbda587e7bac8ad29eff3fb3534beacd076a3a | Steps 1–2 + exact-name matching only (538d0c0) |
| Step 6 split | `docs/evaluation/variants-2026-08-29/split.json` | 3302 | sha256:c5d2c260b2eb04bdd6d8544413fb5186f123c0ee3a80e5cc1e8feeb30dd65138 | Frozen tune/report halves for the threshold fit (f6893c8) |
| Step 6 slot gold | `docs/evaluation/variants-2026-08-29/slot_gold.json` | 36224 | sha256:36aa52df72f75c6af3c107d171e5d94ed13f731ec2fbf5711f4813d6dc626648 | Gold derived from data, not behaviour (f6893c8) |
| Step 6 slot gold findings | `docs/evaluation/variants-2026-08-29/slot_gold_findings.json` | 8308 | sha256:590efc62b118a2df309012cb8a6d5014427921fa83be0015ad5bc70972c87bfc | (f6893c8) |
| Step 6 sweep, baseline | `docs/evaluation/variants-2026-08-29/sweep_baseline.json` | 2332231 | sha256:7c887d8c7aea94126f69ec80cd325b4b4f0d581efd504918fd4d5326fe74ef4d | (446bc45) |
| Step 6 sweep 4 / 1.25 | `docs/evaluation/variants-2026-08-29/sweep_4_1p25pjson` | 2335636 | sha256:1cf4dd2d5dea8e4675d37cb5a8e1cbce09222f03c40d72ebcd64dac797349a9a | Score-threshold × margin grid point (446bc45); the filenames lack a dot before `json` as written by the sweep |
| Step 6 sweep 4 / 1.6 | `docs/evaluation/variants-2026-08-29/sweep_4_1p6pjson` | 2332099 | sha256:ed30dd6efee21ab26968a61bbe266611f65eb8801b4e369edfb9e78c7d006ce2 | (446bc45) |
| Step 6 sweep 4 / 2.2 | `docs/evaluation/variants-2026-08-29/sweep_4_2p2pjson` | 2332099 | sha256:ed30dd6efee21ab26968a61bbe266611f65eb8801b4e369edfb9e78c7d006ce2 | (446bc45) |
| Step 6 sweep 8 / 1.25 | `docs/evaluation/variants-2026-08-29/sweep_8_1p25pjson` | 2335504 | sha256:5197fd48b77955c3990a9197932dc6c41559e0336135370617f1e38b4ee0b08d | (446bc45) |
| Step 6 sweep 8 / 1.6 | `docs/evaluation/variants-2026-08-29/sweep_8_1p6pjson` | 2332099 | sha256:ed30dd6efee21ab26968a61bbe266611f65eb8801b4e369edfb9e78c7d006ce2 | (446bc45) |
| Step 6 sweep 8 / 2.2 | `docs/evaluation/variants-2026-08-29/sweep_8_2p2pjson` | 2332099 | sha256:ed30dd6efee21ab26968a61bbe266611f65eb8801b4e369edfb9e78c7d006ce2 | (b8c3b99) |
| Step 6 sweep 12 / 1.25 | `docs/evaluation/variants-2026-08-29/sweep_12_1p25pjson` | 2335504 | sha256:5197fd48b77955c3990a9197932dc6c41559e0336135370617f1e38b4ee0b08d | (b8c3b99) |
| Step 6 sweep 12 / 1.6 | `docs/evaluation/variants-2026-08-29/sweep_12_1p6pjson` | 2332099 | sha256:ed30dd6efee21ab26968a61bbe266611f65eb8801b4e369edfb9e78c7d006ce2 | (b8c3b99) |
| Step 6 sweep 12 / 2.2 | `docs/evaluation/variants-2026-08-29/sweep_12_2p2pjson` | 2332099 | sha256:ed30dd6efee21ab26968a61bbe266611f65eb8801b4e369edfb9e78c7d006ce2 | (b8c3b99) |
| Step 6 threshold sweep summary | `docs/evaluation/variants-2026-08-29/threshold_sweep.json` | 2470 | sha256:ed69307cc8a9805b1f2fbe4336195125b6ff3998c313a8869f7560e85012d958 | The tune/report table behind "68 % precision on the frozen half" (b8c3b99) |
| Reference, Arm 6 | `docs/evaluation/variants-2026-08-29/reference_arm6.json` | 321431 | sha256:580f15cc2843b813837a63b9b4a6c7928f495bfc595562c0160801bf04dab19a | (9f02dc6) |
| Scored Arm 6 | `docs/evaluation/variants-2026-08-29/scored_arm6.json` | 3235108 | sha256:565b5568ec851cf443e02e174d803541412e6c7eac1289e3f236ed65479f83cd | Defaults on, names resolved before the ladder — the shipped configuration (9f02dc6) |

`data/metrics.json` in this folder is the per-arm tier table the harness
emitted, plus a `manifest_metrics` object added 2026-09-09 (RESULTS A-1).

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
