# POINTERS — EXP-2026-11-022

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| off-A scores | docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h/metrics-offA.json | 21812 | sha256:bb760cb83e36ae9dff9e0399174646edb6b1b68a522adb143ad958129bd942ce | off-A sitting: banks and probe per arm |
| core-1 scores | docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h/metrics-core.json | 41033 | sha256:4bfe887f59ed8989f9e17dc24fb3233ba81955eca8e7dd7c5958c6f763154efe | first core sitting (superseded): banks and probe per arm |
| core-2 scores | docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h/core-superseded-2/metrics-stop-check.json | 44946 | sha256:1820bbf3dff86da145513a132dc40fd4d7aa706a92b4e49b8dfbae82eba6177f | second core sitting (superseded): banks, probe, stop check, provisional bar |
| off-A answers T-lazy | docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h/off-A/variants/T-lazy.json | 5356012 | sha256:44d23c8e96ecd2f156ed7c13cca18c0c45d59b2efb7e2f383ee3e026b9089f2f | off-A variant answers, T-lazy |
| core-2 answers T-lazy | docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h/core-superseded-2/variants/T-lazy.json | 6314387 | sha256:3246ac639f3186cc05d92d1ea5a7830efe2c34a8742c7695a92a611e65a76f0c | core-2 variant answers, T-lazy |
| off-A answers T-full | docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h/off-A/variants/T-full.json | 5581917 | sha256:f44fcaf34059fec61b75e74f5eea2ad9a7f2a17955ca7a6e543ba55bbd73acfa | off-A variant answers, T-full |
| core-2 answers T-full | docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h/core-superseded-2/variants/T-full.json | 6233548 | sha256:0b030e5739205545d275eda5c28ab891bfeaabc7b7b8dbbed0bbb1b82529fb66 | core-2 variant answers, T-full |
| off-A answers T-lazy-G | docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h/off-A/variants/T-lazy-G.json | 4649934 | sha256:b3ecadad1981d1d69142e61c0ac0b08fee6f1248d230ff89727ec756a1b02c8c | off-A variant answers, T-lazy-G |
| core-2 answers T-lazy-G | docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h/core-superseded-2/variants/T-lazy-G.json | 4809333 | sha256:bb65bdb2f3dce654975b0a533c3a063bd84f96b2cf33e49d9100355fc0b5df38 | core-2 variant answers, T-lazy-G |
| fix4-small score | docs/evaluation/experiments/algebra-exposure-2026-11-20/fix4-small/score.json | 2901 | sha256:f8da57e02fc4da3bcd9c8371ade01ec7a046b23070b8ab0993a71f5dce3ba865 | proving set fix4-small: Amendment bars |
| fix5-small score | docs/evaluation/experiments/algebra-exposure-2026-11-20/fix5-small/score.json | 3644 | sha256:aaaac434198c55811a4127496d6896cd4791425c11c5d3692c183dc898da5186 | proving set fix5-small: Amendment bars |
| fix6-small score | docs/evaluation/experiments/algebra-exposure-2026-11-20/fix6-small/score.json | 4380 | sha256:be2c09c5cc8096f52a8b216a97867d1da10b97323f66e65d1f04653af23a18b3 | proving set fix6-small: Amendment bars |

If this experiment reads no raw output outside `docs/research/`, delete the
table and write one line: `No external artifacts: <why>` — the validator
rejects an empty table on a completed experiment.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
