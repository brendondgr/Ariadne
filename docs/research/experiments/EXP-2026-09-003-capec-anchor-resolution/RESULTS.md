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

---

## AMENDMENT A-1 (2026-09-09) — Record repair: pointer label, hypothesis denominators, and one unexplained decrease

Written from the 2026-09-09 audit (`verify-b5.md`), which reproduced every
manifest value from the two pointed directories: mean coverage over the 37 ids
**0.0816 → 0.1081**, 2 improved, 12 of 12 predicted survivors survived. No
number changes.

1. **Hypothesis denominators.** The manifest's `hypothesis` says *"47 cases
   move … and 15 named cases do not"*; the metrics use n = 25 predicted movers
   and n = 12 predicted survivors (25 + 12 = 37 = the re-run set). Both are
   right about different populations: 47 and 15 are the plan's counts over the
   whole bank (`docs/plans/2026-09-03-capec-anchor-resolution.md`), and 25 / 12
   are the counts among the 37 dev questions this run re-answered — PROTOCOL.md
   `:40` already states the latter. The hypothesis text is left as written.
2. **Pointer label.** POINTERS row 2 called `expansion-2026-09-01` *"EXP-2026-09-002's
   artifacts"*. That directory is EXP-2026-09-001 A-5's model-free run of
   2026-09-02; 002's judged arms wrote to `expansion-judged-2026-09-01`. The two
   hold identical coverage values for these 37 ids (the audit computed the
   "before" mean from both: 0.0816 either way), so nothing numeric depends on
   the label. Corrected in the row; hashes unchanged and re-verified.
3. **One question went down, and the table does not say so.** Of the 37,
   34 were unchanged, 2 improved and **one fell** — `D6-HAS_MEMBER-MAPS_TO[ATTACK]-CAPEC-703…::formal`,
   0.0196 → 0.0. EXP-2026-09-004 ISSUES I-2 explains it: the 0.0196 was credit
   for an id the abstention boilerplate happened to name, so the decrease is
   the removal of a false positive, not a regression. The `questions_improved: 2`
   count is correct; a `questions_regressed` count would be 0 under 004's
   reading and 1 by raw count.
4. **ISSUES I-5** says EXP-2026-09-001's dangling pointer target
   (`docs/evaluation/composition/authored/ingested.json`) was *"committed at
   eeef322"*; it was **deleted** at `eeef322` (EXP-2026-09-001 A-6 / I-7).
5. **Manifest.** `environment.lockfile`: env/requirements.lock → null (never
   written; ISSUES I-6). `related` gains EXP-2026-09-004 (the routing defect
   this experiment exposed) and EXP-2026-09-005 (the arm comparison after both
   repairs). `data/metrics.json` created from `metrics.values`.

6. **`metrics.primary`** named `mean_recall_on_affected_questions`, a key that does
   not exist in `metrics.values`; it now names `mean_recall_after` (0.1081), the
   headline cell of the table at the top of this file.
