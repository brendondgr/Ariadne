# POINTERS — EXP-2026-09-002

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

**Re-pinned 2026-09-09 (A-1):** `score.json` was rewritten on 2026-09-08
(`a460fa2`, Hybrid Rewrite Stage 6/8 added a `rewrite` provenance block to the
report and a `rung`/`model_consulted` column to every row); its `report` values
are unchanged. The three judged answer directories the headline was computed
from were never listed and are added. Directories carry a tree hash
(`utils/research_record/hashing.py::sha256_tree`).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| judged rollup | `docs/evaluation/composition/bank/judged.json` | 71 | `sha256:aee0ccbe890e57946741ffe0cbdb561796d91f0cd2c760091dc1a18b9c2ac08b` | The three headline arm figures |
| judged detail | `docs/evaluation/composition/bank/judged-detail.json` | 281 | `sha256:a21291fe4d399eeb70e7a11af5e1ef1661de2d279a8e3f1c2261a0ad21bc6e51` | Per-arm cases judged + judgment counts |
| deterministic answers + judgments (gitignored) | `docs/evaluation/experiments/expansion-judged-2026-09-01/deterministic/answers` | 22276594 | `sha256:ce6321af5483ec4a595b5e1b277abf9d242f67c39df172cfab63c04c905c2c65` | 852 files: 284 answers, 284 `.judgment.p1.json`, 284 `.judgment.p2.json`; recomputes 0.4934 exactly (audit 2026-09-09) |
| generic answers + judgments (gitignored) | `docs/evaluation/experiments/expansion-judged-2026-09-01/generic/answers` | 7240840 | `sha256:fbc1eb9ef7d10a8a7f3bb9689a657ede4fc8be5a100e9bdfe525cbeaaff0114a` | 852 files, as above; recomputes 0.6576 exactly |
| llm_query answers + judgments (gitignored) | `docs/evaluation/experiments/expansion-judged-2026-09-01/llm_query/answers` | 2335922 | `sha256:cfa87da3ae95b0d5c8d4d95592035760390f6427bd0a7fc9ee05ec6f8efe441b` | 852 files: 284 answers, 282 + 282 judgments, 2 + 2 `.error.txt` (one different case failed in each pass — A-1 §4); recomputes 0.3712 exactly |
| direction contrast | `docs/evaluation/composition/bank/direction.json` | 5729 | `sha256:1720b10600ea5b5d4c193e6ac49b97a80c94a59cbe9c4deb53539361b52453ea` | Paired forward/reverse deltas, 20 shapes, over all 572 questions (A-1 §1) |
| anomaly triage | `docs/evaluation/composition/bank/anomalies.json` | 5827 | `sha256:cd234b522dc7a72c20d0c007426a7793a5add592b15151881687e6d71b3a3a5e` | Failure causes by tier; abstention outcomes; over all 572 questions (A-1 §1) |
| budget probe | `docs/evaluation/composition/bank/budget-probe.json` | 2208 | `sha256:bd6ad1e4a1fb095011fa48d60a19b43ead8d95c5252571ea099ae45f5f519659` | The llm_query confound, re-probed |
| model-free scores | `docs/evaluation/composition/bank/score.json` | 302627 | `sha256:a3f779fc042a81d4fc6ff5bef3dcac511790e5d4557713a8c0fbf07f59faa1e6` | Per-question recall over 572 rows + `report` (0.4522 / 0.506 / dev 0.435 / holdout 0.4683 / 37 of 61). **Rewritten 2026-09-08 by `a460fa2`**; values unchanged. Was 233633 B, `sha256:6fb4eaf1168e7960065f912cdb2a220726ec1a5b035f00fac60c7652aa29e048` = the `eeef322` blob this experiment read (ISSUES I-10) |
| run state | `docs/evaluation/composition/bank/overnight-state.json` | 11147 | `sha256:06c24cc9553c9a0007b2852f2452ac612dc6b2807573f72a4d3cf3609db01a94` | 16 phases, timings, preflight + grader identity |
| bank (full) | `docs/evaluation/composition/bank/bank.json` | 1188163 | `sha256:ad99afb18934bd7db233c292d235a4350c332114c357ea624123031ff0ab434e` | 572 questions; hash matches the run's preflight |
| bank (dev half) | `docs/evaluation/composition/bank/bank-dev.json` | 573495 | `sha256:a4ca6702029cae7784574b0307b9f76d4718a039f3254f2c0ff708a2fa1a4119` | The 284 the three arms were judged on |
| harness | `scripts/expansion_overnight.py` | 12071 | `sha256:c65ccdbfa8c58c99308aec9dc1e71072e4846f2cb674803306a59761ef568f86` | the 16-phase orchestrator (as at HEAD) |
| direction script | `scripts/direction_contrast.py` | 7516 | `sha256:0841eb3911fd76157bcefdca20a588d39f183e113d74ef2e17ae1c79b6ba10a8` | writes `direction.json` (as at HEAD) |
| triage script | `scripts/anomaly_triage.py` | 7798 | `sha256:4d2969c468077eb7c2ca4429159b457137871700fdbb199af2118742f69ec33e` | writes `anomalies.json`; its `CONTAINMENT` set defines the n=68 population (as at HEAD) |
| morning report | `docs/research/reports/2026-09-02-overnight-report.md` | 11747 | `sha256:43a4b7165559d152e0a8866af6d49a6cca73efb653a906f43402707aeee66133` | Jargon-free narrative rendered from the above |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```

**The bank hash matches** the value `overnight-state.json` recorded at preflight
(`ad99afb1…`), so the question set has not changed since it was answered.
