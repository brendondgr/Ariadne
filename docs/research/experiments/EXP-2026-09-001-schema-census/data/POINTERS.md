# POINTERS — EXP-2026-09-001

The census is **committed**, not git-ignored: it is small, it is a derived
artifact of two pinned raw files, and every later question-generation run needs
to cite the exact census it drew from. The two source hashes below are the ones
already pinned in `data/versions.json`; the census agreeing with them is what
makes it reproducible without shipping a 52 MB bundle.

**Re-hashed 2026-09-09 (A-6).** The first table pinned eight files at the
`a61dedb` / `585e7dc` blobs; A-2 (`1dd69d9`) regenerated the census and the spec
pool and A-5 (`eeef322`) touched the enumerator and brief writer again, and the
table was never re-pinned. Every row below is the file as it stands at
`eeef322`, which is byte-identical to HEAD for every path listed. Directories
carry a tree hash (`utils/research_record/hashing.py::sha256_tree`).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| Census (machine) | `docs/evaluation/schema-census/attack-19.0-capec-3.9/census.json` | 63138 | sha256:e2f55f821e557d9acfb3beeb73b67dd68f032a071638fe3203f0777077f77cb1 | node types, properties, typed edges, fan-out, coverage (v2; was sha256:1f1b354a…, 62502 B, the `a61dedb` blob) |
| Census (report) | `docs/evaluation/schema-census/attack-19.0-capec-3.9/CENSUS.md` | 8571 | sha256:b488c0ab24fd099b8c678e00a2bfb36a2c1a78bdfbe04044d63666595d80a75c | rendered tables (was sha256:fc21e939…) |
| Source: ATT&CK | `data/raw/attack/v19.0/enterprise-attack.json` | 52680865 | sha256:df520ea0775a57db7bff760145b02fed89290802913e056b7ed5970b02f3626a | pinned STIX bundle, v19.0 |
| Source: CAPEC | `data/raw/capec/v3.9/capec_latest.xml` | 3849998 | sha256:70279a2dff0cb0ad79e546adb07828335a704ad5210e047e09e986172fc9e34d | pinned CAPEC XML, v3.9 |
| Code | `utils/specialists/evalset/schema_census.py` | 23170 | sha256:91f0aeed9aa6cc0a36e0d4c9613ab59c38383cfae9fb8a160cd91a79e151e174 | the enumeration |
| Tests | `utils/specialists/evalset/tests/test_schema_census.py` | 7235 | sha256:1a0ea833e5ffeeb0445fdeddb5f0d43f03898931ef86c718cc91084d080932c6 | 13 assertions, incl. agreement with `gold_bank` |
| Code (v2 parse) | `utils/specialists/evalset/raw_graph.py` | 22830 | sha256:436d7c5a0a8d7d102a117af6518d68d34298f5e020841aa379d141bf90a57db8 | added by A-1 / Step 1; changed at `1dd69d9` (was sha256:9cd8cce5…) |
| Code (enumerator) | `utils/specialists/evalset/composition.py` | 35309 | sha256:58014e35696139c86931a0218eab92f7901e4ffe40d6a0375e1a1be581929506 | added by A-1 / Step 1; changed at `1dd69d9` and `eeef322` (was sha256:53654a59…) |
| Tests (enumerator) | `utils/specialists/evalset/tests/test_composition.py` | 12211 | sha256:8e663c40b8b9ab880e32eb79d99b1965ee2a2c7b243bf906f361302c96331d01 | added by A-1 / Step 1; changed at `1dd69d9` (was sha256:5e6cd808…) |
| Spec pool | `docs/evaluation/composition/attack-19.0-capec-3.9/specs.json` | 3223764 | sha256:2bfa5bb939d0ec8bcd2f79045314b09677fae56073a36ace8fd3d43d5cb0dc62 | added by A-1 / Step 1; regenerated at `1dd69d9` (was sha256:b1bdcbd5…, 3198426 B) |
| Spec pool report | `docs/evaluation/composition/attack-19.0-capec-3.9/report.json` | 632 | sha256:4c9c10e73bce33e9ce1b2765997c490e84c2339748fd950b4c86ecb5640b9b72 | added by A-1 / Step 1; regenerated at `1dd69d9` (was sha256:e952b67d…) |
| Code (renderer) | `utils/specialists/evalset/render.py` | 18667 | sha256:a0dfb2b83abc639a71db9d7151272a172b44e63dd9269d23efc822a176d28f09 | added by Step 4 |
| Tests (renderer) | `utils/specialists/evalset/tests/test_render.py` | 9523 | sha256:e0f43ec0f3cd100cb5070be3f93583dc77899e9a37309a970fb0b939d8826a19 | added by Step 4 |
| Render pilot | `docs/evaluation/composition/attack-19.0-capec-3.9/rendered.json` | 33938 | sha256:1fbfcb7c401b5f7a78ff304235c6bd774954292776e104f08e7d2f4484c97270 | added by Step 4 |
| Code (brief writer) | `scripts/prepare_briefs.py` | 10388 | sha256:68aa5e05f3a5aaf5b8cf9922acb3a67d2a6b01b8cd3c96f9d40b7508af0769fe | Author = Opus 5 subagents; changed at `1dd69d9` and `eeef322` (was sha256:cba8459a…, 7709 B) |
| Code (ingest/validate) | `scripts/ingest_authored.py` | 5595 | sha256:0ace2ce426e9085678fcdf4872d405f50189ecae5c2d3c73fb66f29744fb1a91 | Author = Opus 5 subagents |
| Opus 5 author pilot (successor) | `docs/evaluation/composition/bank/ingested.json` | 180507 | sha256:d05000092ccfd268a9a49f9ca2030c3ac3aa6805a5740db3bd105af26304c85d | **Not the pilot.** The 42-brief pilot `docs/evaluation/composition/authored/ingested.json` (37581 B, sha256:659c1cd5…) was deleted at `eeef322`; this is the full-bank ingest that replaced it. The pilot survives only as `git show 585e7dc:docs/evaluation/composition/authored/ingested.json` — ISSUES I-7 |
| A-2 / A-4 probe: selection | `docs/evaluation/composition/probe/selection.json` | 4285 | sha256:798fa9a3fce4ff24c9004ccc37b259461e5c7fded3a861f83e10b14d187e5621 | which shapes and controls the probe drew |
| A-2 / A-4 probe: bank | `docs/evaluation/composition/probe/bank.json` | 177503 | sha256:74d4a573f09ce46ec8d0d3db2e8c0fd3a0c62af70c4e5e84f62875c2b8fc054d | the 80 probe questions (corrected run; the first 78-question draw was overwritten — ISSUES I-8) |
| A-2 / A-4 probe: report | `docs/evaluation/composition/probe/probe-report.json` | 67682 | sha256:115daefa9a480033088c915e8e7605baca276a05bf01ca14e5d2451acbd749e7 | A-4's per-shape recall |
| A-4 probe answers (gitignored) | `docs/evaluation/experiments/probe-2026-09-01/deterministic/answers` | 1818468 | sha256:312a45c21cd7f358bceaf9af3338b75ea199a970480c53bd7d7731a8a6a39301 | 80 answer files (tree); reproduces A-4's 0.4029 / 14 fully answered exactly (audit 2026-09-09) |
| Code (reconciliation) | `scripts/reconcile_graph.py` | 12445 | sha256:33e4d1098df31545c60920aafcb40281c650e0f975489f3dc14012aae2c7e2de | A-2's census-to-graph predicate map |
| A-5 bank | `docs/evaluation/composition/bank/bank.json` | 1188163 | sha256:ad99afb18934bd7db233c292d235a4350c332114c357ea624123031ff0ab434e | 572 questions, 284 dev / 288 holdout |
| A-5 answers (gitignored) | `docs/evaluation/experiments/expansion-2026-09-01/deterministic/answers` | 47007195 | sha256:c523e069d0c29f3679810c98e1d1398f252e3b51ac564e0c2866f6ddd74d21d3 | 572 answer files (tree), the model-free run behind A-5 |
| A-5 scores | `docs/evaluation/composition/bank/score.json` | 302627 | sha256:a3f779fc042a81d4fc6ff5bef3dcac511790e5d4557713a8c0fbf07f59faa1e6 | per-question recall + `report` block (0.4522 / 0.5060 / 37 of 61). Rewritten 2026-09-08 by `a460fa2` (a `rewrite` provenance block was added); the `report` values are unchanged. A-5's numbers were computed from the `eeef322` blob, sha256:6fb4eaf1168e7960065f912cdb2a220726ec1a5b035f00fac60c7652aa29e048, 233633 B |
| Code (scorer) | `scripts/score_bank.py` | 9517 | sha256:aff81a88dea78b40aa099bf1e94b9b335d97106b911fa2861945b32412b41a2c | the model-free scorer, as it stands at HEAD (it has changed since A-5; the recorded figures reproduce from the `eeef322` score.json rows) |

Regenerate:

```
uv run python -m utils.specialists.evalset.schema_census
uv run python scripts/enumerate_compositions.py --per-shape 4
uv run python scripts/prepare_briefs.py --limit 42 --batches 2
# author each briefs/*.json with an Opus 5 subagent -> authored/*.json
uv run python scripts/ingest_authored.py
uv run python -m utils.research_record.hashing <path>   # hashes
```
