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

Rows below added 2026-09-09 (RESULTS.md A-1): every remaining file a reported
number was computed from, hashed as it stands on that date. None of these
files has been written to since 2026-09-08 20:35.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Scored variants — R2 run 1 | `docs/evaluation/variants-2026-08-29/scored_R2_tune.run1.json` | 2009269 | `sha256:7e9c91ba58f5d75dc5c8cfa7af7545dfc29b29136166e3c05d29320ec9d9c950` | Draw 1 of the R2 mean ± sd (`metrics_R2_run1.json`). |
| Scored variants — R2 run 2 | `docs/evaluation/variants-2026-08-29/scored_R2_tune.run2.json` | 2021893 | `sha256:a6b716cdd4acf33c777da28449eea603eb4bae6b9effe0d364cab2f66396ba57` | Draw 2 of R2. |
| Scored variants — R2 cached replay | `docs/evaluation/variants-2026-08-29/scored_R2_tune.cached.json` | 2114481 | `sha256:0e7bec27ffbf0f9e904045a53e2dd2c6f5d06bc6057b76f71e992f5bc41dd013` | Fourth run from cache; the 90–92 % hit rate and "within 0.02" figures (`metrics_R2_cached.json`). |
| Scored variants — R3 run 1 | `docs/evaluation/variants-2026-08-29/scored_R3_tune.run1.json` | 2097579 | `sha256:0684b0021fd83b40b79b510c6734593950a4e0ebe89acce2e985840568e3b433` | Draw 1 of R3 (instance B). |
| Scored variants — R3 run 2 | `docs/evaluation/variants-2026-08-29/scored_R3_tune.run2.json` | 2168707 | `sha256:56d7af4a90888cf259def59e9004347c6540142dba746be2fb033af21876ebbc` | Draw 2 of R3. |
| Scored variants — R3 cached replay | `docs/evaluation/variants-2026-08-29/scored_R3_tune.cached.json` | 2121976 | `sha256:9815760e18e02ed3b06ead24606a24bafe675d945a5aba27fb8d087e31964740` | R3's cached replay (`metrics_R3_cached.json`). |
| Superseded — 240s call timeout, R3 | `docs/evaluation/variants-2026-08-29/scored_R3_tune.timeout240.run1.json` | 1200247 | `sha256:925d4466ab32f3745a23876e49c7810925c5189d6f49697d16a20fe7829cb135` | R3's first attempt under the 240 s timeout (`pilot-timeout240/metrics_R3_run1.json`); the R3 T4 0.0755 → 0.0377 swing in ISSUES.md is between this and a second attempt whose scored file was not kept (its metrics are `pilot-timeout240/metrics_R3_run2.json`). |
| Superseded — 120s budget, R2 run 2 | `docs/evaluation/variants-2026-08-29/scored_R2_tune.deadline120.run2.json` | 1253923 | `sha256:466e89e30371d8d7faad715f17a834eb9e2a4fad95b1d6e1eacfbfae4e95751f` | `deadline120/metrics_R2_run2.json`. |
| Superseded — 120s budget, R2 run 3 | `docs/evaluation/variants-2026-08-29/scored_R2_tune.deadline120.run3.json` | 1309779 | `sha256:a990615a1ad2073da62d60a7d58445425b68b150420080b48b0e50fa92dadef3` | `deadline120/metrics_R2_run3.json`. |
| Superseded — 120s budget, R2 cached replay | `docs/evaluation/variants-2026-08-29/scored_R2_tune.deadline120.cached.json` | 2036603 | `sha256:ccad3aa785ef8b3a673241750af2d78e222ac4e32095ec85f01904ebe34e9fb8` | The cached replay at 120 s that recovers T1 to 0.4921 (§"What the deadline costs"). |
| Superseded — 120s budget, R3 run 1 | `docs/evaluation/variants-2026-08-29/scored_R3_tune.deadline120.run1.json` | 1390949 | `sha256:62d65d50f636abdcb9c50c3556569d5139bd680453b363b51a3e88a2067a9b05` | `deadline120/metrics_R3_run1.json`. |
| Superseded — 120s budget, R3 run 2 | `docs/evaluation/variants-2026-08-29/scored_R3_tune.deadline120.run2.json` | 1360151 | `sha256:fd610f68c0c795fc70179cf3f66f56ef1d4025e2310c620f3c0568416017a021` | `deadline120/metrics_R3_run2.json`. |
| Superseded — 120s budget, R3 run 3 | `docs/evaluation/variants-2026-08-29/scored_R3_tune.deadline120.run3.json` | 1257541 | `sha256:d394f1acb124096a934276758fbfa70df1bc444ef354332bc4b9efc0936294f7` | `deadline120/metrics_R3_run3.json`. |
| Superseded — 120s budget, R3 cached replay | `docs/evaluation/variants-2026-08-29/scored_R3_tune.deadline120.cached.json` | 2047831 | `sha256:9701dedd1dbbe04c270c61b387cdf8e4781f1d33d241845171db44f173c81605` | `deadline120/metrics_R3_cached.json`. |
| Variant bank | `docs/evaluation/variants-2026-08-29/variants.json` | 219487 | `sha256:428a23467ecf8aed1f266186504d6f68d0a9d88173cc090149558d078bdea63c` | The 579 frozen variants (2026-08-29) every arm is scored over. |
| Tune / report split | `docs/evaluation/variants-2026-08-29/split.json` | 3302 | `sha256:c5d2c260b2eb04bdd6d8544413fb5186f123c0ee3a80e5cc1e8feeb30dd65138` | 301 tune / 278 report; only the tune half is read. |
| Understanding-gold | `docs/evaluation/variants-2026-08-29/slot_gold.json` | 36224 | `sha256:36aa52df72f75c6af3c107d171e5d94ed13f731ec2fbf5711f4813d6dc626648` | The 120 slot-gold records the slot-accuracy table is scored against; 40 federated records carry only an anchor (ISSUES.md). |
| Shipped Arm-6 reference (not used as R0's reference) | `docs/evaluation/variants-2026-08-29/reference_arm6.json` | 321431 | `sha256:580f15cc2843b813837a63b9b4a6c7928f495bfc595562c0160801bf04dab19a` | The 2026-08-29 capture that no longer reproduces on queries/claims (ISSUES.md); pointed so the diff described there is checkable. |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
