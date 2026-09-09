# POINTERS — EXP-2026-08-010

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

Table filled 2026-09-09 (it was the blank scaffold until then; RESULTS A-1).
Hashes as of 2026-09-09. Nothing has been written into
`docs/evaluation/external-2026-08-21/` since the run (all mtimes 2026-08-21
16:38–17:21); every headline, by-benchmark and by-family figure was re-scored
from the answer files with `scripts/external_validation.py::score_cell` on
2026-09-09 and reproduces exactly.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Run directory | `docs/evaluation/external-2026-08-21` | 999908 | sha256:070524cbd9602c7a0674d321581d9165afe2dc5030cffd35ff2dc357224b664b | Everything below plus the four `*.summary.json` files and `REPORT.md` |
| Sweep state | `docs/evaluation/external-2026-08-21/state.json` | 3920 | sha256:493485e36b94715b7223c62c4f7b1f3e45eae5be834504368e56a0739b766b90 | Phase status; P0 records the benchmark digests (cti-ate `79e5354a…`, attackqa `180423ce…`), 182 usable items (45 + 137), 14 families |
| Scored metrics | `docs/evaluation/external-2026-08-21/metrics.json` | 310880 | sha256:829794b3ba1b4b7fce68425d99c5fafa1caeec98a86301680cfc9c67656a2561 | Per-cell micro/macro recall, precision, exact match, by-benchmark and by-family, with `per_item` rows and `sample_seed` 20260821; `data/metrics.json` is a byte-identical copy |
| Run report | `docs/evaluation/external-2026-08-21/REPORT.md` | 8219 | sha256:fe80a7f3fe9348595479346bf191634750212a0bf7fe758a7b10f9194097f77c | Human-readable form; `REPORT.md` in this directory is derived from it |
| Oracle, plan-given | `docs/evaluation/external-2026-08-21/oracle--plan-given` | 173473 | sha256:379eee03cf08d911f9e3525c339bd1015094b4a73fd0622281f1ddf32d8b34d5 | 182 direct graph reads — the ceiling (0.9863 / 0.8100 / 0.7033) |
| Deterministic, plan-given | `docs/evaluation/external-2026-08-21/deterministic--plan-given` | 223786 | sha256:f3e5b4717f6a83433cbfa7e710e6b70e0aadc66a2db6f578c818e03c023e40b9 | 182 template-cascade answers (0.6836 / 0.7701 / 0.4451; subset-60 0.7170 / 0.7815 / 0.4833) |
| Generic, plan-given | `docs/evaluation/external-2026-08-21/generic--plan-given` | 114029 | sha256:952c58393c24ecd9fc3ab194b9be08d18b26b4ccddaf690e7885f97d1b86b0c2 | 60 template-free answers via the relay (0.9953 / 0.8100 / 0.7333) |
| LLM, plan-free | `docs/evaluation/external-2026-08-21/llm--plan-free` | 165149 | sha256:41de9cc0e7572bc8c70900fb7986423b63371bd457745d215ac2fec22a2cdf23 | 60 answers where the model plans from the question text (0.6132 / 0.7670 / 0.4500) |

The benchmarks themselves are cached outside the repository
(`.cache/external-benchmarks/`); their content digests are in `state.json`
P0 above.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
