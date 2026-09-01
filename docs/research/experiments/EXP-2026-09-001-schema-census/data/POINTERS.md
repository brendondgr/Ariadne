# POINTERS — EXP-2026-09-001

The census is **committed**, not git-ignored: it is small, it is a derived
artifact of two pinned raw files, and every later question-generation run needs
to cite the exact census it drew from. The two source hashes below are the ones
already pinned in `data/versions.json`; the census agreeing with them is what
makes it reproducible without shipping a 52 MB bundle.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---:|---|
| Census (machine) | `docs/evaluation/schema-census/attack-19.0-capec-3.9/census.json` | 61980 | sha256:1dd0d3cdced9e4888182a66786829847c4ec68c3db1b63abf98bad90a6393da0 | node types, properties, typed edges, fan-out, coverage |
| Census (report) | `docs/evaluation/schema-census/attack-19.0-capec-3.9/CENSUS.md` | 8470 | sha256:e622dcf4cc703354db6e60b2f69f34af2024167d66f6b55ae940c892c5944a78 | rendered tables |
| Source: ATT&CK | `data/raw/attack/v19.0/enterprise-attack.json` | 52680865 | sha256:df520ea0775a57db7bff760145b02fed89290802913e056b7ed5970b02f3626a | pinned STIX bundle, v19.0 |
| Source: CAPEC | `data/raw/capec/v3.9/capec_latest.xml` | 3849998 | sha256:70279a2dff0cb0ad79e546adb07828335a704ad5210e047e09e986172fc9e34d | pinned CAPEC XML, v3.9 |
| Code | `utils/specialists/evalset/schema_census.py` | 23170 | sha256:91f0aeed9aa6cc0a36e0d4c9613ab59c38383cfae9fb8a160cd91a79e151e174 | the enumeration |
| Tests | `utils/specialists/evalset/tests/test_schema_census.py` | 7235 | sha256:1a0ea833e5ffeeb0445fdeddb5f0d43f03898931ef86c718cc91084d080932c6 | 13 assertions, incl. agreement with `gold_bank` |
| Code (v2 parse) | `utils/specialists/evalset/raw_graph.py` | 21656 | sha256:ac6d225f1ad51320439f43eacb8d8b7ad39974797e9b31e3d7172a8cbb816aa5 | added by A-1 / Step 1 |
| Code (enumerator) | `utils/specialists/evalset/composition.py` | 30866 | sha256:f0064a7be4b0cbb28716e95a8b4f7c9cd4222253a3bebc2ed84d8aa7d430b615 | added by A-1 / Step 1 |
| Tests (enumerator) | `utils/specialists/evalset/tests/test_composition.py` | 9876 | sha256:feff437cb485063837532dbec43ad9aae4cffa2bf4948555e5cd669177905e34 | added by A-1 / Step 1 |
| Spec pool | `docs/evaluation/composition/attack-19.0-capec-3.9/specs.json` | 2899782 | sha256:4edfbecd182e211d2d52e5f3d7159a58ebf1652c7fb143d650a070b0824594f0 | added by A-1 / Step 1 |
| Spec pool report | `docs/evaluation/composition/attack-19.0-capec-3.9/report.json` | 632 | sha256:3c43f5fc7b1010b11f6d29a1a15dd6372295281ce4ad02595f8bd91eca11c104 | added by A-1 / Step 1 |

Regenerate:

```
uv run python -m utils.specialists.evalset.schema_census
uv run python scripts/enumerate_compositions.py --per-shape 4
```
