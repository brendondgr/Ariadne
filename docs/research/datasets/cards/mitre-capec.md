# Dataset Card — MITRE CAPEC™

**Version:** 3.9 · **Downloaded:** 2026-07-23 · **Engine:** TinkerPop Gremlin Server (Gremlin)
**SHA-256:** `70279a2dff0cb0ad79e546adb07828335a704ad5210e047e09e986172fc9e34d` (3,849,998 B)
**Used by:** every experiment on record

---

## What it is

MITRE's Common Attack Pattern Enumeration and Classification: attack patterns
organised in an abstraction hierarchy (meta → standard → detailed), with
prerequisites, consequences, execution flows, skills required, and mappings to
CWE weaknesses and to ATT&CK techniques.

In Ariadne it is the **Gremlin side** of the federation — a genuinely different
engine with a genuinely different traversal model, which is the point: the
federation is cross-*language*, not just cross-endpoint. Roughly 4,888 vertices
in the loaded fixture.

## Provenance and version pinning

Sourced from MITRE's published CAPEC XML release, pinned by version and checksum
in [`data/versions.json`](../../../../data/versions.json).

```bash
uv run main.py --download
uv run main.py --build capec       # canonical artifacts + Gremlin export
uv run main.py --dataset capec --graph gremlin
```

## Licence — attribution is mandatory

Used under MITRE's CAPEC™ Terms of Use. As with ATT&CK, MITRE's copyright
designation and licence must travel with any copy. Full text:
[`NOTICE`](../../../../NOTICE) §2.

## Limitations affecting results

* **Mapping coverage is the binding constraint on the federated slice.** Only a
  minority of CAPEC patterns carry resolvable ATT&CK mappings (the audit puts
  the join surface at ~31.7%), which hard-caps how many federated questions can
  exist at all — a few hundred, no matter how much effort goes into authoring.
* **Deprecated patterns are excluded** by build policy.
* **Anchors in the question catalogue were sampled by mapping richness**, so the
  federated questions over-represent the best-connected corner of CAPEC. This is
  one of the specific biases the blind holdout (Q1) is designed to expose.
* **The fixture has been found empty (0 nodes) at session start.** Verify counts
  before trusting any CAPEC or federated result; an empty fixture returns "no
  records" rather than failing loudly.
