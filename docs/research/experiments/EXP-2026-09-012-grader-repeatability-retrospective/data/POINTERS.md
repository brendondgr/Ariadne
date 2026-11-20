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
| Judgment sidecar tree (input) | `docs/evaluation/experiments` | 1909094433 | `sha256:5da961fd09c0d0bdb456d56f8b32209a113090077a8fb1f53ea55e23270f8981` | Tree, **re-hashed 2026-11-20 (thirteenth time)**: EXP-2026-11-019 added `written-id-guard-2026-11-20/` (1243581 bytes: two variant arms and three dev arms of 15 answers; previous hash sha256:7465fe905572…). Before that, twelfth time: EXP-2026-11-018 added `typed-engine-fixes-2026-11-20/` (62474089 bytes: variant arms and dev answers, no judgment sidecars); no judgment sidecar this experiment reads was changed; previous `sha256:73ce6e1d6bef…`. **Re-hashed 2026-11-19 (eleventh time)**: EXP-2026-11-017 added `bridge-guard-2026-11-19/` (60064338 bytes: variant arms and dev answers, no judgment sidecars); no judgment sidecar this experiment reads was changed; previous `sha256:807506747e9a…` |

The canonical output is `data/recompute-audit.json` (inside `docs/research/`,
no pointer needed). `data/2026-09-07-recompute-audit.json` is an earlier copy
that still contains one contaminated cell and is kept for the record only.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
