# POINTERS — EXP-2026-09-026

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `scored_anchor_first.json` | `docs/evaluation/variants-2026-09-15/scored_anchor_first.json` | 2,374,888 | `sha256:d88b181a8e6111221de8707f4788c814b7ebf79f3197618566f91b75241a334f` | exposed: anchor_first |
| `scored_form_execute.json` | `docs/evaluation/variants-2026-09-15/scored_form_execute.json` | 2,387,416 | `sha256:4f62754def176ea5aaa43ea4d1c78362949776ed5227ab7d5ddb03f0f339bc08` | exposed: form_execute |
| `scored_generic.json` | `docs/evaluation/variants-2026-09-15/scored_generic.json` | 2,373,621 | `sha256:5d4248f1fd4d6f9fa3cd03ed3367073fdada5c43fee13fdf5c395236663f036c` | exposed: generic |
| `scored_generic_form.json` | `docs/evaluation/variants-2026-09-15/scored_generic_form.json` | 2,508,964 | `sha256:08427f449691e0cee44331229223bfe0b8f5dd6703b0fc9cfa06eb8bcbe2d7d5` | exposed: generic_form |
| `scored_anchor_first.json` | `docs/evaluation/variants-holdout-2026-09/scored_anchor_first.json` | 578,532 | `sha256:b7282dd7a3179f7b46885c752c94d164723a864a066339be30834087ed5fe056` | sealed: anchor_first |
| `scored_form_execute.json` | `docs/evaluation/variants-holdout-2026-09/scored_form_execute.json` | 584,494 | `sha256:36962cf419116bbdb7ca13fce4815451619a354876c38ea7cc1d0fd9a450cfbe` | sealed: form_execute |
| `scored_generic.json` | `docs/evaluation/variants-holdout-2026-09/scored_generic.json` | 627,773 | `sha256:20cd0ab50de1d11a5109b7e5d46d4f738f30fe7dfa7da8d3b3421c34cc161714` | sealed: generic |
| `scored_generic_form.json` | `docs/evaluation/variants-holdout-2026-09/scored_generic_form.json` | 624,759 | `sha256:e9c3214b87cc3c66a3630d2b39fd2f38a7b969cf670cbfbce33aaa12b966dff9` | sealed: generic_form |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
