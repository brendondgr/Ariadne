# PROTOCOL — EXP-2026-08-017

**Written before the run.**

## 1. Why this experiment exists

C-015 — *"federating across two engines outperforms merging both sources into a
single graph"* — is **refuted**. EXP-2026-08-009 built the counterfactual and
merging scored −0.0334 on one blind set and +0.0000 on the other. That result
stands and is not being relitigated.

What it left open is most of the actual federation argument. Correctness was
never why practitioners federate; it was the only part anyone had a number for.
Q5's remainder named four surviving reasons — provenance, licensing, staleness,
and not re-running a merge on every catalogue update — none of which is written
down as a claim.

## 2. Two of those four are excluded, deliberately

**Merge cost and onboarding cost are not measurable here**, and attempting them
would produce a number about *these two catalogues* rather than about merging.
ATT&CK and CAPEC merge cheaply **because they already share edge semantics and a
taxonomy crosswalk**; two sources with unrelated schemas would not. A wall-clock
figure over the easy case, generalised to the design, is exactly the strawman
D-004 exists to prevent — in the direction the project already prefers.

Recorded as ruled out rather than deferred. They are not open questions; they are
questions this study cannot answer without confounding them.

## 3. What is measurable, and is not a function of which graphs were chosen

**Did the design require editing the source data?**

That is a property of the architecture, answerable by counting, and it does not
depend on the pair. A merged store must reconcile identifiers *somewhere*, and
having no read-time step it must do so in the data. A federated one reconciles in
code, per engine, at read time.

## 4. Measurement

Over the canonical artifacts of both conditions, count nodes carrying a property
the upstream record does not ship:

* **merged** — `data-merged/graphs/*/canonical/nodes.jsonl`
* **federated** — `data/graphs/{attack,capec}/canonical/nodes.jsonl`

The property is `attack_id`, which every schema-driven Cypher query anchors on
via `coalesce(n.attack_id, n.id)`. ATT&CK nodes carry it upstream; CAPEC nodes do
not — their public id is *derived* from the node id at read time by the Gremlin
normalizer, and their ATT&CK taxonomy entries store a bare number where ATT&CK
stores a `T`-prefixed one.

Deterministic, no model, no graph — a count over committed files.

## 5. The corroborating evidence, assembled not re-run

* **EXP-2026-08-013** — a third source, a customer identity graph, loaded
  unmodified alongside both catalogues, with three live sources retrieving
  identically to one.
* **D-017 / EXP-2026-08-009** — what merging genuinely buys: the next identifier
  is reachable without leaving the engine, so consumer sub-questions skipped for
  want of a join value fall from 7 of 30 to 3 of 30.

## 6. Hypothesis

The merged condition required writing a property onto a substantial fraction of
one catalogue's nodes; the federated condition required writing none. **Stated
before counting:** if federation also rewrites, the claim collapses and C-022 is
not made.

## 7. Threats declared in advance

* **This is a structural claim, not a performance one.** It says merging costs a
  data edit, not that the edit is harmful. Whether that matters is an argument
  about provenance and update cadence, and the paper must present it as such.
* **One property, one pair.** `attack_id` is the property *this* pair needed. A
  different pair would need different reconciliation — which is the point (the
  requirement generalises, the specific edit does not) but is not shown here.
* **Licensing is not measured and will not be.** It is a legal constraint, and
  citing it as evidence would be dressing an argument as a result.
