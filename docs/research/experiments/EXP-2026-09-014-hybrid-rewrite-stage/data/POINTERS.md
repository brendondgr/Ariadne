# POINTERS — EXP-2026-09-014

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Step-0 Arm-6 re-capture | `docs/evaluation/variants-2026-08-29/reference_2026-09-08.json` | 319942 | `sha256:d36411e12851049b3c4a957898d61cdcf47580ea3476daa30ec9f728dda98a68` | The 120 golden questions captured on 2026-09-08 with every LLM seam off. R0's reference. |
| Gold-form round-trip | `docs/research/experiments/EXP-2026-09-014-hybrid-rewrite-stage/data/roundtrip_gold_forms.json` | 365711 | `sha256:c6b6800add8c33e4d6bbe519479ca5d9344d44c87906e207d5e778e732e7d291` | Per-case round-trip of all 120 slot-gold forms: the form, the rendered sentence, what it retrieved, and the diff against the reference. |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
