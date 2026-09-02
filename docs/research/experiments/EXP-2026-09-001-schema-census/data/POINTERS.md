# POINTERS — EXP-2026-09-001

The census is **committed**, not git-ignored: it is small, it is a derived
artifact of two pinned raw files, and every later question-generation run needs
to cite the exact census it drew from. The two source hashes below are the ones
already pinned in `data/versions.json`; the census agreeing with them is what
makes it reproducible without shipping a 52 MB bundle.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---:|---|
| Census (machine) | `docs/evaluation/schema-census/attack-19.0-capec-3.9/census.json` | 62502 | sha256:1f1b354a75299fdfa16b66f3a38ac8931c1371f3624190d35028ad3cb0e4877d | node types, properties, typed edges, fan-out, coverage |
| Census (report) | `docs/evaluation/schema-census/attack-19.0-capec-3.9/CENSUS.md` | 8583 | sha256:fc21e9393a16564aa1a0821548488dee8984232700f6343cae4fd09725dd88d9 | rendered tables |
| Source: ATT&CK | `data/raw/attack/v19.0/enterprise-attack.json` | 52680865 | sha256:df520ea0775a57db7bff760145b02fed89290802913e056b7ed5970b02f3626a | pinned STIX bundle, v19.0 |
| Source: CAPEC | `data/raw/capec/v3.9/capec_latest.xml` | 3849998 | sha256:70279a2dff0cb0ad79e546adb07828335a704ad5210e047e09e986172fc9e34d | pinned CAPEC XML, v3.9 |
| Code | `utils/specialists/evalset/schema_census.py` | 23170 | sha256:91f0aeed9aa6cc0a36e0d4c9613ab59c38383cfae9fb8a160cd91a79e151e174 | the enumeration |
| Tests | `utils/specialists/evalset/tests/test_schema_census.py` | 7235 | sha256:1a0ea833e5ffeeb0445fdeddb5f0d43f03898931ef86c718cc91084d080932c6 | 13 assertions, incl. agreement with `gold_bank` |
| Code (v2 parse) | `utils/specialists/evalset/raw_graph.py` | 22299 | sha256:9cd8cce5d8113af1bc18575faeb205e97b537ddb9ea9e6cc830b0b98f72a43bf | added by A-1 / Step 1 |
| Code (enumerator) | `utils/specialists/evalset/composition.py` | 33584 | sha256:53654a59a75c159129599ce574ed6564894c8f5b54802bb2dc579fa284a18e48 | added by A-1 / Step 1 |
| Tests (enumerator) | `utils/specialists/evalset/tests/test_composition.py` | 11162 | sha256:5e6cd808cdc7dd05e56be6a440a3b95d9263182e37580000876a081deff413a6 | added by A-1 / Step 1 |
| Spec pool | `docs/evaluation/composition/attack-19.0-capec-3.9/specs.json` | 3198426 | sha256:b1bdcbd55754d8e542e764b745214df56ae3198df392631641bd70a4d2ec4726 | added by A-1 / Step 1 |
| Spec pool report | `docs/evaluation/composition/attack-19.0-capec-3.9/report.json` | 632 | sha256:e952b67d68e6d880c6fcef3659064dc36ec0211e0ae456422e5d8c18e11d47d4 | added by A-1 / Step 1 |
| Code (renderer) | `utils/specialists/evalset/render.py` | 18667 | sha256:a0dfb2b83abc639a71db9d7151272a172b44e63dd9269d23efc822a176d28f09 | added by Step 4 |
| Tests (renderer) | `utils/specialists/evalset/tests/test_render.py` | 9523 | sha256:e0f43ec0f3cd100cb5070be3f93583dc77899e9a37309a970fb0b939d8826a19 | added by Step 4 |
| Render pilot | `docs/evaluation/composition/attack-19.0-capec-3.9/rendered.json` | 33938 | sha256:1fbfcb7c401b5f7a78ff304235c6bd774954292776e104f08e7d2f4484c97270 | added by Step 4 |
| Code (brief writer) | `scripts/prepare_briefs.py` | 7709 | sha256:cba8459a3a179acb987e68e55189885131b29b9b6c07475d57ca203329f80446 | Author = Opus 5 subagents |
| Code (ingest/validate) | `scripts/ingest_authored.py` | 5595 | sha256:0ace2ce426e9085678fcdf4872d405f50189ecae5c2d3c73fb66f29744fb1a91 | Author = Opus 5 subagents |
| Opus 5 author pilot | `docs/evaluation/composition/authored/ingested.json` | 37581 | sha256:659c1cd5c10a3e91451422abfcb59d7bf21c700a444ab16e917a13beb57fd690 | Author = Opus 5 subagents |

Regenerate:

```
uv run python -m utils.specialists.evalset.schema_census
uv run python scripts/enumerate_compositions.py --per-shape 4
uv run python scripts/prepare_briefs.py --limit 42 --batches 2
# author each briefs/*.json with an Opus 5 subagent -> authored/*.json
uv run python scripts/ingest_authored.py
```
