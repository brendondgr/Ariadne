# POINTERS — EXP-2026-08-011

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

Table filled 2026-09-09 (it was the blank scaffold until then; RESULTS A-11).
Hashes are as of 2026-09-09. **Two of the `sweep_state.json` files were re-used
by later runs and no longer hold the figures first computed from them** — see
the rows and ISSUES I-16.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Bank 1 (development) run directory | `docs/evaluation/identity-2026-08-21` | 798949 | sha256:e3d48b5e121a2363854e268c935322c47933f7a3e6edb71169564c026e029f58 | `gold.json`, `discards.json`, `authored.json`, `bank.json` (27 authored of 30 drawn), `judge_payloads/`, `judgments.json` (flagged UNUSABLE, I-7), `sweep_state.json` |
| Bank 1 sweep state (**post-fix**) | `docs/evaluation/identity-2026-08-21/sweep_state.json` | 390903 | sha256:2bd69a876da9cfe3b428b70f47e1baeda795192ba399e2915d50be7b2533c3e7 | mtime 2026-08-21 20:45 — written by the post-fix re-run (commit 74d027e, 19:23). Reproduces A-1's 0.8519 / 0.2778 and per-kind exactly. **Does not hold the §1 pre-fix 0.0000 / 0.0000 run; that state was overwritten** (I-16) |
| Bank 2 (blind) run directory | `docs/evaluation/identity-bank2-2026-08-22` | 1083698 | sha256:ecaf3f882d92d89353ad47d72385b7df4ae1e220218f3f945bafdce2c7686dc4 | 28 questions, zero anchor overlap with bank 1; `sweep_state.json` (A-5: 0.7857 / 0.1964, per-kind), `judgments.json` (A-6 local-judge session over both arms: 0.9821 / 0.8893 …), `judge_payloads/` |
| Bank 2 sweep state | `docs/evaluation/identity-bank2-2026-08-22/sweep_state.json` | 447775 | sha256:751b307d9356fcec270ab2b8038b762d00e35f52973fcf42c7ef5b1b406e2a65 | A-5 retrieval, reproduces exactly |
| Bank 2 local judgments | `docs/evaluation/identity-bank2-2026-08-22/judgments.json` | 36370 | sha256:1ba5cdc324b56612830e69d1635dda908bda00dc98a51a227ff5e8a4c860d2ba | A-6 figures, reproduce exactly from the per-verdict rows |
| Bank 3 run directory | `docs/evaluation/identity-bank3-2026-08-22` | 2429877 | sha256:99fa6604739b7770e7373b4cbc895ccb919c6d1fa2e2955f6f1d9370ae42ba3b | 117 questions authored by Claude Fable (I-10); `gold.json`, `discards.json`, `authored.json`, `bank.json`, `judge_payloads/`, `sweep_state.json` |
| Bank 3 sweep state (**post-I-11**) | `docs/evaluation/identity-bank3-2026-08-22/sweep_state.json` | 1344578 | sha256:87c25a4b193d41058ba6cea4df9f43a02483c1495cd9e20d23d3acfd83011e83 | mtime 2026-08-22 10:51 — written after the I-11 resolver fix (34e07df). Reproduces A-10's recall 0.6923 / 0.1140, precision 0.1357 / 0.0572 and 22.7 / 15.8 records per answer exactly. **Does not hold A-8's 0.7877 / 0.3177 nor A-10's "before" row; that state was overwritten** (I-16) |
| Bank 3 after the I-12 anchor fix | `docs/evaluation/identity-bank3-anchorfix-2026-08-22` | 2120189 | sha256:e5bd63576aca96a54558d9d0c59f6df8674e2876c9caf4cf527b64eeda077ddf | `bank.json` + `sweep_state.json` (2026-08-22 12:53): I-12's 0.7094 / 0.2194, ids 8.24 / 1.95, max 54 / 2 — reproduces exactly; also EXP-2026-08-013's one-source baseline |
| Sonnet verdicts, banks 1 and 2 | `docs/evaluation/identity-crossmodel-2026-08-22/sonnet_verdicts.json` | 64581 | sha256:8bd09c5d6e5b70413d8b6c289a35b0493d5204faba49c83e585d836839bea0cb | A-7: 102 verdicts from ten independent Sonnet judges (6 unattributable excluded); 0.55 / 0.35 blind, 0.6135 / 0.314 development |
| Sonnet verdicts, bank 3 after I-9 | `docs/evaluation/identity-bank3-crossmodel-2026-08-22/sonnet_verdicts.json` | 112991 | sha256:da29d00264f15b998fc7aeb4fba6f3997e73e5d7f5c9231e541bd9b24df2c33d | A-9: 233 verdicts, 12 judges; 0.7009 / 0.7094, sufficiency 0.3691 / 0.2248 |
| Sonnet verdicts, bank 3 after I-9 + I-11 | `docs/evaluation/identity-bank3-final-2026-08-22/sonnet_verdicts.json` | 104634 | sha256:e0692ed9bbbed9fc2ec612fda6ccc19517686a293e33c53b18844062f963680d | A-10: 234 verdicts, 6 judges; 0.8175 / 0.9282, groundedness 0.9256 / 0.9274, sufficiency 0.4731 / 0.2957 |

Recompute retrieval with `scripts/identity_sweep.py::score` over the
`retrieval` field of each question in a `sweep_state.json`; judged figures are
means over the verdict rows.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
