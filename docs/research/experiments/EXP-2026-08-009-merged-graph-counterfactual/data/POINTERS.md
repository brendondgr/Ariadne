# POINTERS — EXP-2026-08-009

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

Table filled 2026-09-09 (it was the blank scaffold until then; RESULTS A-2).
Directory rows are tree hashes as of 2026-09-09. Every `answers/` directory has
gained grader sidecars since the `.c015` pass this experiment reported:
`.c022rev1`/`.c022rev2` (2026-08-31 20:55–21:48, this experiment's A-1
reversed-order passes), `.qwen38`/`r2`–`r5` (2026-08-31, EXP-2026-08-021; `r3`
and `r4` have one error file and n = 29 on some arms), `.bld*` (2026-08-31,
EXP-2026-08-022, deterministic arm only), `.g31`/`.g31p2` (2026-09-05). The
answer files (2026-08-21 11:55 for `merged` and `generic_composed`; 2026-08-20
00:47–00:55 for `generic` and `deterministic` on bank 20; 2026-08-19 for bank
19's `generic` and `deterministic`, shared with EXP-2026-08-008) and the
`.c015` sidecars (2026-08-21 11:37–12:28) are unchanged; every §1–§3 cell
reproduces from the `.c015` files exactly (audit 2026-09-09).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Sweep roll-up | `docs/evaluation/merged-2026-08-21-v2/metrics.json` | 5251 | sha256:73defc6c18219c70c62d37d6db23447a7d006a99f26b4608239b545bbc8fb980 | The eight cells as `merged_sweep.py` rolled them up from the `.c015` sidecars; `data/metrics.json` is derived from it |
| Sweep state | `docs/evaluation/merged-2026-08-21-v2/state.json` | 15973 | sha256:dc63661db699cff1729c82c43fb4af2c4f326d56b32acbab0aff3a689b2d237f | Per-phase status incl. the P0 separation checks (8/8) and store counts |
| Sweep report | `docs/evaluation/merged-2026-08-21-v2/REPORT.md` | 5874 | sha256:f36e97a296e0111e549ebbfe5d4fcf62e3c9b57c5f680ef48e548ccb718948fe | Human-readable form of the same run |
| merged, bank 19 | `docs/evaluation/experiments/bank20260819/merged/answers` | 782507 | sha256:0ce6f296098c29a3cebfbab77bee3b85e44e3d92e29ffd38cb83d820a2acb4ec | 30 answers + `.c015` (0.9233) + later passes (`.qwen38r3` n = 29) |
| generic_composed, bank 19 | `docs/evaluation/experiments/bank20260819/generic_composed/answers` | 827843 | sha256:62fc5212910b62d4cce9fe6a96d38eb864c8cff6e4319975269a2bf4b2140e5d | 30 answers + `.c015` (0.9567) + later passes (`.qwen38r3` n = 29) |
| merged, bank 20 | `docs/evaluation/experiments/bank20260820/merged/answers` | 873769 | sha256:ff221cf6fbaeb37fb37e00c7dbfab00fbb831be5dd17cf82daee2314006ceeb5 | 30 answers + `.c015` (0.9367) + later passes |
| generic_composed, bank 20 | `docs/evaluation/experiments/bank20260820/generic_composed/answers` | 854072 | sha256:ba89f20e3a52b2be2e41840ab6dc4f94982c5798eba78cc647e1c0d415838ea5 | 30 answers + `.c015` (0.9367) + later passes (`.qwen38r3`, `r4` n = 29) |
| generic, bank 20 (secondary) | `docs/evaluation/experiments/bank20260820/generic/answers` | 883220 | sha256:f7c6a193a8ea997e77805b4cd4dc555d71009b48435ba2a58b4bc40052c6fd61 | 30 answers + `.c015` + later passes |
| deterministic, bank 20 (secondary) | `docs/evaluation/experiments/bank20260820/deterministic/answers` | 893664 | sha256:264c26e3ffe0cdc9e2f715cb1ad6d3b5fde1e238d5302d7e695bc74bc8e112fa | 30 answers + `.c015` + later passes (`.bld*`, `.qwen38r4` n = 29) |
| generic, bank 19 (secondary) | `docs/evaluation/experiments/bank20260819/generic/answers` | 853113 | sha256:0219150fb82b5233e0425e5d4ab4279cc47ae5bafa533f95cd3498615b1a0d73 | Shared with EXP-2026-08-008; the `.c015` sidecars here are this experiment's |
| deterministic, bank 19 (secondary) | `docs/evaluation/experiments/bank20260819/deterministic/answers` | 828548 | sha256:e034f420eb44ffe349146654dae18ce0e172b4e99aa7eff9dbddf9a909323d35 | Shared with EXP-2026-08-008; the `.c015` sidecars here are this experiment's |

The superseded first pass (PROTOCOL amendment of 2026-08-21, ISSUES D1) lives
under `docs/evaluation/merged-2026-08-21/` and is not pointed at: none of its
figures is quoted.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
