# POINTERS — EXP-2026-09-001

The census is **committed**, not git-ignored: it is small, it is a derived
artifact of two pinned raw files, and every later question-generation run needs
to cite the exact census it drew from. The two source hashes below are the ones
already pinned in `data/versions.json`; the census agreeing with them is what
makes it reproducible without shipping a 52 MB bundle.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---:|---|
| Census (machine) | `docs/evaluation/schema-census/attack-19.0-capec-3.9/census.json` | 54260 | sha256:8d7ecd0998df289854cc0cd2c672daa32771d63f59dbf73717e2cd54a1731a88 | node types, properties, typed edges, fan-out, coverage |
| Census (report) | `docs/evaluation/schema-census/attack-19.0-capec-3.9/CENSUS.md` | 7767 | sha256:453d7fd8e5ddf24975918ca621708a8f05e01835408fd1a3913af2ae65ee84fa | rendered tables |
| Source: ATT&CK | `data/raw/attack/v19.0/enterprise-attack.json` | 52680865 | sha256:df520ea0775a57db7bff760145b02fed89290802913e056b7ed5970b02f3626a | pinned STIX bundle, v19.0 |
| Source: CAPEC | `data/raw/capec/v3.9/capec_latest.xml` | 3849998 | sha256:70279a2dff0cb0ad79e546adb07828335a704ad5210e047e09e986172fc9e34d | pinned CAPEC XML, v3.9 |
| Code | `utils/specialists/evalset/schema_census.py` | 34798 | sha256:5bd0c4752df62754cbe15145d53081c586632a6ad0e321dd57db0314d9851444 | the enumeration |
| Tests | `utils/specialists/evalset/tests/test_schema_census.py` | 7235 | sha256:1a0ea833e5ffeeb0445fdeddb5f0d43f03898931ef86c718cc91084d080932c6 | 13 assertions, incl. agreement with `gold_bank` |

Regenerate:

```
uv run python -m utils.specialists.evalset.schema_census
```
