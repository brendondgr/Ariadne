# POINTERS — EXP-2026-11-012

The twelve banks this experiment wrote, one per dataset, decision step and split. They are
committed, like earlier held-out sets (`docs/evaluation/variants-holdout-2026-09/`).

- **Held-out banks are sealed** (`meta.sealed: true`). Nothing reads them until the step that
  scores on them. A hash mismatch later means a sealed bank was changed.
- **Each hash is of the bank file as written**, and matches `data/card_bank.json["banks"]`.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `card-2026-11-16-attack-exit-heldout` | `docs/evaluation/banks/card-2026-11-16-attack-exit-heldout/bank.json` | 33,861 | `sha256:ab50c66812cfeb4e0bea33f6be23376c4d1d8ce33b37233270cf31c5e5a8789c` | 23 questions, **sealed** held-out |
| `card-2026-11-16-attack-exit-tuning` | `docs/evaluation/banks/card-2026-11-16-attack-exit-tuning/bank.json` | 35,479 | `sha256:9ad761482c85cda8d86816c412619a75d4caa721805480be741cb87635c6d499` | 27 questions, tuning |
| `card-2026-11-16-attack-grounding-heldout` | `docs/evaluation/banks/card-2026-11-16-attack-grounding-heldout/bank.json` | 238,888 | `sha256:a82812272f6568877ee26cc78af18ea8f41503d71c45c8d1b9a3dfdd39173417` | 156 questions, **sealed** held-out |
| `card-2026-11-16-attack-grounding-tuning` | `docs/evaluation/banks/card-2026-11-16-attack-grounding-tuning/bank.json` | 212,424 | `sha256:41330f29695b0c6b32500de98c3b8af6ce5c7e0746bb2e577d52e1359d3e3c0f` | 138 questions, tuning |
| `card-2026-11-16-attack-relation_choice-heldout` | `docs/evaluation/banks/card-2026-11-16-attack-relation_choice-heldout/bank.json` | 111,938 | `sha256:cbd7c7d1ea96094a75d06c636d476fca7e18b79a9ffe4ffac802bd681552d453` | 76 questions, **sealed** held-out |
| `card-2026-11-16-attack-relation_choice-tuning` | `docs/evaluation/banks/card-2026-11-16-attack-relation_choice-tuning/bank.json` | 94,300 | `sha256:bce5a25ee1b8742b9484ff0fc27939ad59a01d53b07d6ba5c604ee853dd43097` | 63 questions, tuning |
| `card-2026-11-16-capec-exit-heldout` | `docs/evaluation/banks/card-2026-11-16-capec-exit-heldout/bank.json` | 35,595 | `sha256:a34ee3ee52ace2855247696368eb1935c63ddff2d486af502809e5497f267ab7` | 22 questions, **sealed** held-out |
| `card-2026-11-16-capec-exit-tuning` | `docs/evaluation/banks/card-2026-11-16-capec-exit-tuning/bank.json` | 35,476 | `sha256:19cfc8987f8f2fa415ff01b106ba15b9b3c8fbbce639525813f46839bf39bd00` | 22 questions, tuning |
| `card-2026-11-16-capec-grounding-heldout` | `docs/evaluation/banks/card-2026-11-16-capec-grounding-heldout/bank.json` | 139,689 | `sha256:e7650146d7e363c8fcef03919e297af91f07beea566924ab285ab0d23a16c078` | 87 questions, **sealed** held-out |
| `card-2026-11-16-capec-grounding-tuning` | `docs/evaluation/banks/card-2026-11-16-capec-grounding-tuning/bank.json` | 191,064 | `sha256:ae7ef6540ee1c2b031323c53d17f0b12cba869a9bd8c6f81b199caea9ba411a6` | 130 questions, tuning |
| `card-2026-11-16-capec-relation_choice-heldout` | `docs/evaluation/banks/card-2026-11-16-capec-relation_choice-heldout/bank.json` | 63,854 | `sha256:14d812eea034a5eb1eb71a9a7ae3bb360b7e4002ded3d627a19acb4da8693c93` | 40 questions, **sealed** held-out |
| `card-2026-11-16-capec-relation_choice-tuning` | `docs/evaluation/banks/card-2026-11-16-capec-relation_choice-tuning/bank.json` | 75,372 | `sha256:7cbdd6f87af7a4428344b9133657adb87a50946c57fac09c40d265e91a1a7f99` | 53 questions, tuning |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
