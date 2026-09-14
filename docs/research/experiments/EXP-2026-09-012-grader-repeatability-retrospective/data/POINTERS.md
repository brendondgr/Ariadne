# POINTERS — EXP-2026-09-012

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

Filled 2026-09-09 (RESULTS.md A-1). This experiment reads a **tree**, not a
run directory: every `*.judgment*.json` under `docs/evaluation/experiments`.
The hash below is that tree as it stands on 2026-09-09 (25,318 judgment
sidecars). It is **not** the tree the numbers were computed from on
2026-09-07 02:53: EXP-2026-09-011's extension grading (2026-09-07 10:15–13:00)
added 1,704 `.q1`/`.q2` sidecars under `seeded-repeats-generic-2026-09-06`,
so two of the 218 audited cells now hold 1,704 judgments where the audit saw
852 (RESULTS A-3). Nothing else under the tree is known to have changed; the
stored output `data/recompute-audit.json` is the record of what was read.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Judgment sidecar tree (input) | `docs/evaluation/experiments` | 1561004654 | `sha256:8f8361ebf27d73f893eb919c328959b97858ee0c9c75407998f77c67386777af` | Tree, **re-hashed 2026-09-14 (sixth time)** — `EXP-2026-09-018` added its paired control, sealed fresh set and holdout regression, and `EXP-2026-09-019` its 2x2, together taking the tree from 1.31 GB to 1.51 GB, and then `EXP-2026-09-019`'s judged pass added 2,272 judgment sidecars (was `sha256:1f00631063dd…, 1514738557 bytes, earlier on 2026-09-14) (was `sha256:92ea1e10d397…`, 1313336567 bytes, 2026-09-12; `sha256:05dd61d1b601…` earlier the same day) (was `sha256:28cd732c4241…`, 1229038988 bytes, earlier the same day; `sha256:579433ecb5de…`, 861377303 bytes, 2026-09-11; and `sha256:c7b9993b1d90…`, 401843103 bytes, 2026-09-09 — see ISSUES; every `EXP-2026-09-018` step writes a capture under this tree and moves this hash without touching this experiment's input). Every `**/answers/*.judgment*.json` is a candidate cell; sidecars whose suffix itself contains `.judgment`, or that sit under a `_contaminated*` directory, are excluded (30 on 2026-09-07). Cells with fewer than 20 judgments are dropped. A future hash mismatch here means grading passes were added or removed since 2026-09-09, not that any recorded figure changed. |

The canonical output is `data/recompute-audit.json` (inside `docs/research/`,
no pointer needed). `data/2026-09-07-recompute-audit.json` is an earlier copy
that still contains one contaminated cell and is kept for the record only.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
