# RESULTS — EXP-2026-09-003

## The short version

The defect was real, the fix works, and **it recovers 2 questions, not the 47
the plan predicted.** A second defect sits behind the first and the plan did not
see it, because the first one was hiding it.

| | before | after |
|---|---:|---:|
| mean recall over the 37 affected dev questions | 0.0816 | **0.1081** |
| questions whose recall improved | — | **2** |
| predicted to move, that moved | 25 predicted | **2** |
| predicted to survive, that survived | 12 predicted | **12** |

## What was wrong

`_capec_gremlin_id` converted a bare `CAPEC-<n>` to `capec:attack-pattern:<n>`.
CAPEC numbers one sequence across three kinds, so `CAPEC-284` — a View stored at
`capec:view:284` — was looked up as an attack pattern that does not exist. The
visible `hasLabel("AttackPattern")` on five anchors made this look like a label
problem; it was an identity problem, and removing the label filter alone would
have changed nothing.

## That the fix works is not in doubt

Against the live store (CAPEC reloaded 2026-09-03, 6,374 / 8,582), the seeded
`describe` anchor now returns the right kind of vertex for all three:

| seed | before | after |
|---|---|---|
| CAPEC-284 | 0 rows | `capec:view:284` — Detailed Abstractions |
| CAPEC-98 | Phishing | Phishing (unchanged) |
| CAPEC-118 | 0 rows | `capec:category:118` — Collect and Analyze Information |

No `cwe:` vertex is reachable from a CAPEC seed, which is asserted rather than
assumed: `cwe:284` sits in the same store as `capec:view:284`.

## Why recall barely moved anyway

The two questions that improved are exactly the two the anchor alone could fix —
the `View.Type` property reads, 0.0 to 0.5, where the answer *is* the anchor's
own attribute.

Every containment question still fails, and now visibly rather than silently.
Asked *"Which CAPEC attack patterns does the category Engage in Deceptive
Interactions (CAPEC-156) contain?"*, the system now finds the right category —
1 row where it used to find 0 — and answers:

> Found 1 CAPEC record(s): capec:category:156. capec:category:156 (Engage in
> Deceptive Interactions) has Status: Stable.

The gold is six member CAPEC ids. The question routes to `describe`, which
returns the node and its facet **counts**, not its members. Retrieving the right
vertex was a precondition for answering, not an answer.

**So the containment failures are a routing defect, not a label defect.** They
belong with the Cypher-side Group and Tactic mis-routing in Step 4 of the parent
repair plan, which is the same failure in the same shape: the ladder selects a
template that answers a different question.

## What survived, exactly as predicted

All 12. The 2 `AttackPattern`-anchored `describe` cases and the 4
`Technique`-anchored `capec_maps_to` cases were already anchored correctly and
were named in the plan as out of scope; the 5 `Tactic` `tactic_techniques` and 1
`technique_tactics` cases are Cypher-side and untouched here. None moved.

That half of the prediction being exactly right is the reason to trust the other
half being exactly wrong: the instrument is discriminating, and the claim of 47
was an over-attribution, not a measurement error.

## What a reader should refuse to conclude

- That the CAPEC anchor defect was small. It made 45 questions unanswerable at
  the retrieval stage; it simply is not the *last* thing standing between those
  questions and an answer.
- That the 0.1081 figure bounds the fix's value. It bounds the fix's value
  **given the routing defect still present**. The two interact and cannot be
  attributed separately until routing is repaired.
- That anything here says whether the deterministic arm's 0.4934 moves. This
  experiment touched 37 dev questions, not the arm.
