# POINTERS — EXP-2026-09-014

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Step-0 Arm-6 re-capture | `docs/evaluation/variants-2026-08-29/reference_2026-09-08.json` | 319942 | `sha256:d36411e12851049b3c4a957898d61cdcf47580ea3476daa30ec9f728dda98a68` | The 120 golden questions captured on 2026-09-08 with every LLM seam off. R0's reference. |
| Gold-form round-trip | `docs/research/experiments/EXP-2026-09-014-hybrid-rewrite-stage/data/roundtrip_gold_forms.json` | 294151 | `sha256:119f9751dc59bc92f90c96b5b5c7ded59212258917688e56351b8215c7f540b6` | Per-case round-trip of all 120 slot-gold forms: the form, the rendered sentence, what it retrieved, and the diff against the reference. |
| Deterministic bind rate | `docs/research/experiments/EXP-2026-09-014-hybrid-rewrite-stage/data/deterministic_bind_rate.json` | 1466 | `sha256:6a61b4486b570f2a4b7301a49da486683f517f98214c9604e2188316fd83973b` | Per-tier slot-binding rate of the deterministic fill: how many questions bind every slot with no model involved, and which slots stay unbound. |
| Anchor recall@k (tune half) | `docs/research/experiments/EXP-2026-09-014-hybrid-rewrite-stage/data/recall_at_k_tune.json` | 124849 | `sha256:e51d636531f17904d8f3065f54127cdb35a25d3d85032700e74c3ee29cad7264` | Recall of the gold anchor in the top-5 candidate lists, per tier, on the tune half only. The ceiling on what any chooser can reach. |

| Scored variants — R0 (rewrite off) | `docs/evaluation/variants-2026-08-29/scored_R0_tune.json` | 2278260 | `sha256:09dbac39901f035d0b6b04904706c362f89f5e1e218588cca6a80b79c2e2432a` | Every tune-half variant scored with the stage off. The control R2/R3 are read against. |
| Scored variants — R1 (deterministic fill) | `docs/evaluation/variants-2026-08-29/scored_R1_tune.json` | 2472804 | `sha256:6238fc92d6fe89db1346e6607b8ac5f75490ff40abc07f9b177d73b167adff30` | The deterministic rewrite, no model, byte-reproducible. |
| Scored variants — R2 run 3 | `docs/evaluation/variants-2026-08-29/scored_R2_tune.run3.json` | 2165091 | `sha256:f833308cdb07a0922ad1c35be83860424d247572849f95c631df2334b5dfbd10` | One of three cleared-cache runs on serving instance A. Runs 1 and 2 and the cached replay sit beside it. |
| Scored variants — R3 run 3 | `docs/evaluation/variants-2026-08-29/scored_R3_tune.run3.json` | 2229423 | `sha256:c22077cb474ea914e8d56cd8201bf224c7095d3db63a8da5566f0bedaea8bccc` | The same on instance B. Cross-instance repeatability, not a model comparison. |
| Superseded — 240s call timeout | `docs/evaluation/variants-2026-08-29/scored_R2_tune.timeout240.run1.json` | 1194024 | `sha256:658cb65194d574795a49c803b53e3517e32c8a1f2f27fb5b66228d7e60c92416` | The first attempt, in which 31-38% of model calls timed out and abstained. Kept as the evidence for the re-run. |
| Superseded — 120s pipeline budget | `docs/evaluation/variants-2026-08-29/scored_R2_tune.deadline120.run1.json` | 1227120 | `sha256:22b0f18f8280f72fa4a9d9ad49f8ea3cbf8b93dcf4771bc1f99fb120d952f6cc` | The second attempt, in which the rewrite's latency starved retrieval. Also the honest measurement of the stage under the SHIPPED budget. |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
