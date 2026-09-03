# POINTERS — EXP-2026-09-002

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| judged rollup | `docs/evaluation/composition/bank/judged.json` | 71 | `sha256:aee0ccbe890e57946741ffe0cbdb561796d91f0cd2c760091dc1a18b9c2ac08b` | The three headline arm figures |
| judged detail | `docs/evaluation/composition/bank/judged-detail.json` | 281 | `sha256:a21291fe4d399eeb70e7a11af5e1ef1661de2d279a8e3f1c2261a0ad21bc6e51` | Per-arm cases judged + judgment counts |
| direction contrast | `docs/evaluation/composition/bank/direction.json` | 5729 | `sha256:1720b10600ea5b5d4c193e6ac49b97a80c94a59cbe9c4deb53539361b52453ea` | Paired forward/reverse deltas, 20 shapes |
| anomaly triage | `docs/evaluation/composition/bank/anomalies.json` | 5827 | `sha256:cd234b522dc7a72c20d0c007426a7793a5add592b15151881687e6d71b3a3a5e` | Failure causes by tier; abstention outcomes |
| budget probe | `docs/evaluation/composition/bank/budget-probe.json` | 2208 | `sha256:bd6ad1e4a1fb095011fa48d60a19b43ead8d95c5252571ea099ae45f5f519659` | The llm_query confound, re-probed |
| model-free scores | `docs/evaluation/composition/bank/score.json` | 233633 | `sha256:6fb4eaf1168e7960065f912cdb2a220726ec1a5b035f00fac60c7652aa29e048` | Per-question recall (EXP-2026-09-001 A-5 recomputed) |
| run state | `docs/evaluation/composition/bank/overnight-state.json` | 11147 | `sha256:06c24cc9553c9a0007b2852f2452ac612dc6b2807573f72a4d3cf3609db01a94` | 16 phases, timings, preflight + grader identity |
| bank (full) | `docs/evaluation/composition/bank/bank.json` | 1188163 | `sha256:ad99afb18934bd7db233c292d235a4350c332114c357ea624123031ff0ab434e` | 572 questions; hash matches the run's preflight |
| bank (dev half) | `docs/evaluation/composition/bank/bank-dev.json` | 573495 | `sha256:a4ca6702029cae7784574b0307b9f76d4718a039f3254f2c0ff708a2fa1a4119` | The 284 answered here; holdout excluded |
| morning report | `docs/reports/2026-09-02-overnight-report.md` | 11747 | `sha256:43a4b7165559d152e0a8866af6d49a6cca73efb653a906f43402707aeee66133` | Jargon-free narrative rendered from the above |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```

**The bank hash matches** the value `overnight-state.json` recorded at preflight
(`ad99afb1…`), so the question set has not changed since it was answered.
