# Dataset Card — MITRE ATT&CK®

**Version:** 19.0 · **Downloaded:** 2026-07-23 · **Engine:** Neo4j (Cypher)
**SHA-256:** `df520ea0775a57db7bff760145b02fed89290802913e056b7ed5970b02f3626a` (52,680,865 B)
**Used by:** every experiment on record

---

## What it is

MITRE's knowledge base of adversary tactics, techniques, and procedures observed
in the wild. In Ariadne it is the **Neo4j side** of the federation, queried in
Cypher: techniques and sub-techniques, tactics, mitigations, groups, software,
campaigns, data components, and detection analytics.

It supplies the **canonical join key** for the federation — ATT&CK technique
identifiers (`T####`, `T####.###`) are what CAPEC attack patterns map onto.

## Provenance and version pinning

Downloaded from MITRE's published release and pinned by version and checksum in
[`data/versions.json`](../../../../data/versions.json). The downloaded artifact
is git-ignored; the pin is tracked, so a rebuild is verifiable.

```bash
uv run main.py --download
uv run main.py --build attack     # canonical artifacts + Neo4j export
uv run main.py --dataset attack --graph neo4j
```

## Licence — attribution is mandatory

Used under the MITRE ATT&CK® Terms of Use, retrieved 2026-08-04. MITRE grants a
non-exclusive, royalty-free licence for research, development, and commercial
purposes, and **requires that MITRE's copyright designation and licence travel
with any copy**.

> © 2026 The MITRE Corporation. This work is reproduced and distributed with the
> permission of The MITRE Corporation.

Full text: [`NOTICE`](../../../../NOTICE) §1.

## Limitations affecting results

* **Version-locked.** Every number in this record is against 19.0. ATT&CK
  reshapes between major versions; results do not transfer across them without
  re-running.
* **Gold is snapshot-derived.** Execution accuracy measures agreement with the
  pinned export, not with ground truth. An ingest error present in both the
  snapshot and the live graph is invisible to exact-set-match.
* **The live fixture must be reloaded after any build-policy change**, or golden
  tests pass against stale data.
