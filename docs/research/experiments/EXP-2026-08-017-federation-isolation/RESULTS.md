# EXP-2026-08-017 — Merging rewrote 1,083 nodes. Federation rewrote none.

**Status:** complete. The hypothesis held, and the number is larger than expected.

## The count

| condition | catalogue nodes | carrying a property upstream does not ship | share |
|---|---:|---:|---:|
| **merged** (`data-merged`) | 9,138 (4,369 ATT&CK + 4,769 CAPEC) | **1,083** | **22.7% of CAPEC** |
| **federated** (`data/graphs/*`) | 9,138 (same two catalogues) | **0** | 0% |

Of the 1,083, **189** are ATT&CK taxonomy entries that gained a `T` prefix —
CAPEC stores the bare `1027.001` where ATT&CK stores `T1027.001`. The other 894
are CAPEC nodes given a public identifier (`CAPEC-66`, `CWE-89`) that the
upstream record does not carry at all: in CAPEC it is *derived* from the node id
at read time.

## What it means, stated carefully

Every schema-driven Cypher query anchors on `coalesce(n.attack_id, n.id)`. The
federated system satisfies that by reconciling **in code, per engine, at read
time** — `_capec_gremlin_id` on the way in, the normalizer's `public_member_id`
on the way out. A merged store queried in Cypher has no read-time step, so it
must reconcile **in the data, at load**.

`utils/kg_builder/merge.py` says this in its own header, and the phrasing is
better than anything this experiment could add:

> the federated system's own work moved from code into data

That is the claim. **Merging does not eliminate the reconciliation; it relocates
it from a function into the stored records.** The relocation is what costs
something:

* the stored catalogue is no longer byte-identical to what MITRE published, so
  "which version of CAPEC is this" stops being answerable from the data alone;
* the edit must be re-applied on **every** catalogue release, and CAPEC and
  ATT&CK ship independently;
* a consumer reading the merged store cannot tell a publisher's field from ours
  without the merge code beside it.

None of that depends on which two graphs were picked. **The specific edit does
not generalise; the requirement to make one does.**

## The third source is the strongest form of it

EXP-2026-08-013 loaded a customer identity graph — 1,339 nodes, 3,814
relationships — **unmodified**, alongside both catalogues, and after the routing
fix three live sources retrieve **identically to one**: zero questions differ, on
either arm, in either direction.

This is the deployment case the funder's challenge is about, and the one where
the architecture stops being a preference. A tenant's identity graph is
frequently the thing that *cannot* be copied into a shared store — for
contractual reasons this experiment does not attempt to measure and will not
claim. What is measured is narrower and sufficient: **federation asked that graph
for nothing.** No property added, no identifier rewritten, no re-export.

## What merging buys, reported beside it

Not hidden, because reporting it is what makes the rest credible. In a single
store the next identifier is reachable without leaving the engine, so the merged
arm can take a join value off a neighbour's record where a federated specialist
cannot act on one. Measured on the blind set (D-017): consumer sub-questions
skipped for want of a join value fall from **7 of 30 to 3 of 30**.

That is a real advantage of single-store architecture, and it is why C-022 is a
claim about *cost and constraint*, not about capability.

## What this does not say

* **Not that federation is more accurate.** C-015 is refuted and stays refuted:
  merging scored −0.0334 and +0.0000 on the two blind sets. This does not touch
  that.
* **Not that merging is wrong.** For two catalogues you control, that ship
  together, under one licence, it is simpler. The claim is scoped to what the
  edit costs, and to when the edit is not permitted.
* **Not that merge cost is high.** Deliberately unmeasured — a wall-clock figure
  over ATT&CK and CAPEC, which merge cheaply *because* they already share edge
  semantics and a taxonomy crosswalk, would be a statement about this pair
  dressed as one about the design. See PROTOCOL §2.

## Threats

* **One property, one pair.** `attack_id` is what *this* pair needed.
* **The 22.7% is a share of CAPEC, not of the merged store.** Against all 9,138
  nodes it is 11.9%. Both are stated so neither can be quoted as the other.
* **A structural claim, not a performance one.** Whether a data edit matters is
  an argument about provenance and update cadence. The count is evidence for the
  premise, not for the conclusion.
* **The count is of nodes, not of distinct edits.** One rule (`public_member_id`)
  produced 894 of them, so 1,083 measures reach, not complexity.
