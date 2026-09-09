# POINTERS — EXP-2026-08-012

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

Table filled 2026-09-09 (it was the blank scaffold until then; RESULTS A-1).
Hashes as of 2026-09-09. The manifest's original entrypoint wrote to
`docs/evaluation/external-2026-08-21-fixed`, which does not exist; the
surviving post-fix answers are in `docs/evaluation/external-2026-08-21-post-fix/`
(stamped 2026-08-21 20:59–21:12, i.e. after the composer fix 887c2cd 20:58) and
have no `metrics.json` beside them. Re-scored offline with
`scripts/external_validation.py::score_cell` on 2026-09-09 they give
deterministic 0.7633 / 0.7872 / 0.6593 (n 182), subset-60 0.8184 / 0.8032 /
0.7000, llm plan-free 0.6934 / 0.7861 / 0.6333 and oracle 0.9863 — every
headline and Addendum figure exactly.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Post-fix run directory | `docs/evaluation/external-2026-08-21-post-fix` | 530860 | sha256:2ab3409ff8a1ef979c7b678736305b055e21255080d12d20e5974d980bc291f1 | Three answer directories and their `*.summary.json` |
| Oracle, plan-given | `docs/evaluation/external-2026-08-21-post-fix/oracle--plan-given` | 173473 | sha256:379eee03cf08d911f9e3525c339bd1015094b4a73fd0622281f1ddf32d8b34d5 | 182 direct reads; tree hash identical to EXP-2026-08-010's oracle directory — the ceiling did not move |
| Deterministic, plan-given (after both fixes) | `docs/evaluation/external-2026-08-21-post-fix/deterministic--plan-given` | 212129 | sha256:31b87fb331cf4b3a9ddf177a2bddd8679b2033d2924a554558dce2a9394d6c24 | 182 answers → 0.7633 recall / 0.6593 exact, 0 of 14 families empty, 12 of 14 at ceiling; subset-60 0.8184 |
| LLM, plan-free (after both fixes) | `docs/evaluation/external-2026-08-21-post-fix/llm--plan-free` | 144919 | sha256:9f704532c1490e6b048005221130725882889ee57d40a2a435273abc40e71231 | 60 answers → 0.6934 recall (Addendum H5) |
| Summary, deterministic | `docs/evaluation/external-2026-08-21-post-fix/deterministic--plan-given.summary.json` | 119 | sha256:42c95ed1a730012bc6a80268abd7d0eeef4eed8087a6328321e81c375c367bdb | Sweep phase summary |
| Summary, llm | `docs/evaluation/external-2026-08-21-post-fix/llm--plan-free.summary.json` | 108 | sha256:7e207bb8bce5a6fc22d0f20be96d54dfb9f1ba74ad2b07cecff5a0a9daeb5c7b | Sweep phase summary |
| Summary, oracle | `docs/evaluation/external-2026-08-21-post-fix/oracle--plan-given.summary.json` | 112 | sha256:1f627a6ff010d32ca0e3cc68813be1a2e44feee817c86f6359675e0f395b88d0 | Sweep phase summary |

The "before" side of every figure (0.6836 / 0.4451 / 0.7170 / 0.6132 and the
0.9953 subset-60 ceiling) is EXP-2026-08-010's `docs/evaluation/external-2026-08-21/`,
hashed in that experiment's POINTERS. The unshipped Fix 1 is
`data/proposed-fix1-widen-target.patch` in this directory (in git); its
counterfactual 0.9825 has no stored answer set (ISSUES I1) and was not
re-verified.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
