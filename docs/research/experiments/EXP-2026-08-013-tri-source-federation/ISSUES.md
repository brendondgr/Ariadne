# ISSUES — EXP-2026-08-013

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. This file was the empty template until 2026-09-09; the
entries below were written during the record audit from RESULTS.md, the
artifacts and git, and are dated by when they were recorded here.

## 2026-09-09 — The first run was invalid and its numbers are discarded

**Impact:** the first three-source run showed `describe` collapsing 0.812 →
0.438 and read like a routing defect. It was nothing of the kind: the
composition lacked the `graphs/<dataset>/canonical/` tree, so every
schema-driven primitive silently fell back to a hardcoded MITRE shape. Recorded
in RESULTS "Two defects had to be fixed"; **no figure from that run is quoted**
and no artifact of it survives under a distinct path (the valid re-run wrote to
the same `identity-bank3-tri-2026-08-22/` directory).

**Resolution:** `scripts/tri_compose.py` now copies the canonical tree and
`--check` refuses a composition without one.

## 2026-09-09 — The partial-right control was removed; its first draw (0.8889) is discarded

**Impact:** the tri-source bank has no `bridge-partial` kind. Every anchor
holding `GET_CHANGES` is also touched by another mapped right, so a T1003.006
in the evidence cannot be attributed to the half-right; the control could not
distinguish the behaviour it exists to test. Its first draw scored 0.8889 and
that number is not reported anywhere but here and RESULTS "Two gold defects".

**Resolution:** not resolved. Needs a tenant generated with an isolated
replication right — a separate experiment.

## 2026-09-09 — Negative-anchor gold was dirty; `bridge-refusal` moved 0.8333 → 1.0000 on the gold fix alone

**Impact:** the sampler indexed outgoing edges only while the runtime walk is
direction-agnostic, so `dc202` was drawn as a refusal control and then
correctly produced T1098 from an edge held over it. The system was right and
the gold was wrong. The reported refusal figure (1.0 generic, 0.4167
templates) is after the fix; the `_redraw` files in
`docs/evaluation/tri-bank-2026-08-22/` are that redraw.

## 2026-09-09 — The recorded commit predates every "after" figure; runs used uncommitted trees

**Impact:** `code.commit` was `544f978b…` (2026-08-22 13:50, "Record I-12
through I-15") — the pre-fix, pre-bridge tree: the router fix is `9841b859…`
(14:45), the bridge declaration `95b8c91d…` (15:53), the seeding `484bf0cb…`
(16:22), the tri-bank record `4a97053d…` (16:54), and
`utils/planner/edge_correspondence.py` is absent from `544f978`. Only the
pre-routing figures (0.6239 / 0.1254) come from that tree. The artifacts were
written *before* the commits that contain their code — routing sweeps 14:42–14:43
against a 14:45 commit, bridge sweeps 16:13–16:20 against 15:53 / 16:22
commits, the tri-bank at 16:42 against 16:54 — so each measured run used a
working tree that was committed minutes later.

**Resolution:** `code.commit` is now `4a97053d3756179f966a11e8bb90d38833ddecf2`,
the last of the series and the one that recorded the Phase 2 measurement;
`dirty: true`, because every post-fix artifact predates the commit holding its
code. The per-figure trees are listed in RESULTS A-1.

## 2026-09-09 — "Phase 2 … not started" is stale in RESULTS and PROTOCOL

**Impact:** the RESULTS status line and PROTOCOL "Phase 2 — cross-source
correlation (not started)" were written after phase 1 and never updated when
the bridge was built and measured the same afternoon (RESULTS "Phase 2 — the
declared bridge" and "Phase 2 measured"). The manifest status comment is right.
Prose is append-only; RESULTS A-1 records the correction.

## 2026-09-09 — Manifest keys and `data/metrics.json` keys disagreed; Phase 2 values were missing from the manifest

**Impact:** the manifest's `*_tri_source*` keys are `*_tri_source_prerouting*`
in `data/metrics.json` (same values), and the manifest carried none of the
post-routing, bridge or tri-bank values the RESULTS headline rests on.

**Resolution:** keys renamed to match `data/metrics.json`; the post-routing,
no-routed, golden-router, bridge and tri-bank headline values added; `primary`
set to `retrieval_generic_tri_source_postrouting`. RESULTS A-1.

## 2026-09-09 — Hardware never recorded; config hash filled

`compute.hardware` said "unknown — recorded at run time" and never was; it is
`unknown`. `config.hash` for `data-tri/tri_manifest.json` was null and is now
its sha256 as of 2026-09-09 (the file has not changed since 2026-08-22 per its
tree position in the pointers; earlier content cannot be verified).
