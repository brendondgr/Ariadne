# POINTERS — EXP-2026-08-002

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This table was blank until 2026-09-09 (RESULTS A-2); every hash below
was computed that day with `uv run python -m utils.research_record.hashing`
(files: SHA-256 of the bytes; directories: tree hash over relative path +
per-file digest). `docs/evaluation/experiments/` is gitignored, so those two
rows are the only integrity link to the raw run output.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Results | `docs/evaluation/holdout-v1/results.json` | 106280 | sha256:3c3af75e38934949b534786648d3d6565fc2e4cd2d88dae59200f15dd846e08f | Every number in the manifest and RESULTS, produced by `utils/evaluation/holdout_report.py` from the judgment files; per-case verdicts for both arms |
| Write-up | `docs/evaluation/holdout-v1/README.md` | 12781 | sha256:cdd2e92a58fc478fd65ac74e61338c74e89286359988c6cc9c37f7b746ccecf3 | Full write-up: per-category table, failure analysis, gate decision |
| Anchor draw | `docs/evaluation/holdout-v1/anchors.json` | 10489 | sha256:8d448630e86579c39f715e4c36b97d0d25b0435c1f4f1f56229491bc22dc702c | The seeded (20260805) uniform anchor sample, committed before any question existed |
| Authored questions | `docs/evaluation/holdout-v1/authored.json` | 4081 | sha256:f9b3b3c37414324f7de4658925e0dc16764c1d94446586f747a604668a499d4a | The Author's 30 questions as written, before gold was attached |
| Author prompt | `docs/evaluation/holdout-v1/author-prompt.md` | 47162 | sha256:3812db1f5127ce33b5a74b1e967d89f2f93ddfd436fd25d6d54be55c4ee69d6e | The prompt the blind Author received (`llm.prompt_files[0]`) |
| Blind bank | `utils/specialists/tests/golden/holdout_questions.json` | 51152 | sha256:cee87ec0e229f200d4052cb41899cb56bcbdf4e91ff9f358eba1f127b6232be0 | The 30 questions with independently computed gold; last changed in the run commit `ce3a2d2` |
| Arm A raw output | `docs/evaluation/experiments/holdout-v1/deterministic` | 459551 | sha256:0396515e7db3aac420c2233e0b9388ead80d4429b9aa4b918dc40ac0a6128650 | 30 answers + 30 `*.judgment.json` (Sonnet 5, 2026-08-09) + `manifest.json` **plus 60 files this experiment did not produce**: 30 `*.judgment.local.json` and 30 `*.judgment.local.pre-qwen38.json`, written 2026-08-31 by `EXP-2026-08-021`'s grader-calibration passes. The 30 answers and 30 original judgments carry 2026-08-09 mtimes and reproduce every number here (B2 audit 2026-09-09). `manifest.json` covers only the 2-case re-run (ISSUES §4) |
| Arm F raw output | `docs/evaluation/experiments/holdout-v1/gold_loop_llm` | 487676 | sha256:db48570e15a1645b1ede25168921511f3c1830fa21785e04809787bb046dafd4 | 30 answers + 30 `*.judgment.json` (2026-08-09) + `manifest.json` (2-case re-run only, ISSUES §4). No later files |

Not pointed at: `scratchpad/judge_holdout.mjs` (`llm.prompt_files[1]`), which
is not in the repository — see ISSUES §8. The Arm A tree hash pins the
directory *as it stands*, later sidecars included; if `EXP-2026-08-021`'s
files are ever moved, this row must be re-hashed and the answers' own
invariance re-checked by hashing `answers/*.json` and `answers/*.judgment.json`
only.
