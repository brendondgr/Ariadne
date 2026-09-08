# POINTERS — EXP-2026-09-014

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Step-0 Arm-6 re-capture | `docs/evaluation/variants-2026-08-29/reference_2026-09-08.json` | 319942 | `sha256:d36411e12851049b3c4a957898d61cdcf47580ea3476daa30ec9f728dda98a68` | The 120 golden questions captured on 2026-09-08 with every LLM seam off. R0's reference. |
| Gold-form round-trip | `docs/research/experiments/EXP-2026-09-014-hybrid-rewrite-stage/data/roundtrip_gold_forms.json` | 294151 | `sha256:119f9751dc59bc92f90c96b5b5c7ded59212258917688e56351b8215c7f540b6` | Per-case round-trip of all 120 slot-gold forms: the form, the rendered sentence, what it retrieved, and the diff against the reference. |
| Deterministic bind rate | `docs/research/experiments/EXP-2026-09-014-hybrid-rewrite-stage/data/deterministic_bind_rate.json` | 1466 | `sha256:6a61b4486b570f2a4b7301a49da486683f517f98214c9604e2188316fd83973b` | Per-tier slot-binding rate of the deterministic fill: how many questions bind every slot with no model involved, and which slots stay unbound. |
| Anchor recall@k (tune half) | `docs/research/experiments/EXP-2026-09-014-hybrid-rewrite-stage/data/recall_at_k_tune.json` | 124849 | `sha256:e51d636531f17904d8f3065f54127cdb35a25d3d85032700e74c3ee29cad7264` | Recall of the gold anchor in the top-5 candidate lists, per tier, on the tune half only. The ceiling on what any chooser can reach. |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
