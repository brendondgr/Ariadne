# Datasets

Provenance, licence, version, and access for every dataset any experiment
touches. One card per dataset under [`cards/`](cards/).

**Nothing here is authored by this project except the question catalogue.** Every
technique, attack pattern, mitigation, group, and identifier originates in MITRE.
The full third-party attribution text is in [`NOTICE`](../../../NOTICE) at the
repository root, reproduced under licences that require MITRE's copyright
designation to travel with any copy.

| Dataset | Version | Card | Licence | Role |
|---|---|---|---|---|
| MITRE ATT&CK® | 19.0 | [`cards/mitre-attack.md`](cards/mitre-attack.md) | MITRE ATT&CK Terms of Use (royalty-free, attribution required) | The Neo4j side of the federation |
| MITRE CAPEC™ | 3.9 | [`cards/mitre-capec.md`](cards/mitre-capec.md) | MITRE CAPEC Terms of Use (attribution required) | The Gremlin side of the federation |
| Ariadne golden catalogue | 120q-2026-07 | [`cards/golden-catalogue-120.md`](cards/golden-catalogue-120.md) | Authored by this project | The evaluation question set for every experiment on record |

## Version pinning

Source versions and checksums are pinned in
[`data/versions.json`](../../../data/versions.json), which is tracked while the
downloaded artifacts themselves are git-ignored:

| Source | Version | SHA-256 | Size | Downloaded |
|---|---|---|---|---|
| ATT&CK | 19.0 | `df520ea0775a57db7bff760145b02fed89290802913e056b7ed5970b02f3626a` | 52,680,865 B | 2026-07-23 |
| CAPEC | 3.9 | `70279a2dff0cb0ad79e546adb07828335a704ad5210e047e09e986172fc9e34d` | 3,849,998 B | 2026-07-23 |

Rebuild both from scratch:

```bash
uv run main.py --download
uv run main.py --build attack
uv run main.py --build capec
```

## ⚠️ Release blocker

There is **no LICENSE file** for Ariadne's own source code. `NOTICE` is a
third-party data attribution and explicitly states it is not the project's own
licence. The artifact cannot legally be released — and USENIX-family venues make
acceptance conditional on public artifact availability. Roughly half a day of
work; tracked in [`../OPEN_QUESTIONS.md`](../OPEN_QUESTIONS.md) and
[`../paper/venue-targets.md`](../paper/venue-targets.md).
