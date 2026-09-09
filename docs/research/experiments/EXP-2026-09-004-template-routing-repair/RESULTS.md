# RESULTS — EXP-2026-09-004

## The short version

**14 of 32 questions improved. Mean recall 0.0787 → 0.4059, a 5.2× move.** The
prediction was 23, so it was wrong again — but wrong in a way worth reading
carefully, because two of the three reasons are defects in the *scorer*, not in
the system.

| | value |
|---|---:|
| questions re-run (dev half; holdout sealed) | 32 |
| improved | **14** |
| genuinely regressed | **0** |
| mean recall, as scored | 0.0787 → **0.4059** |
| mean recall, counting the graph's own id form | 0.0787 → **0.5913** |

## Scoring the prediction

| group | n | predicted | actual |
|---|---:|---|---|
| ATT&CK property reads (Group 2, Tactic 1) | 3 | move | **3 moved** |
| containment on a Category, forward | 12 | move | 8 moved |
| containment on a View, forward | 8 | move | 3 moved |
| containment on a member, reverse | 6 | do not move | **0 moved** |
| `Technique`-anchored containment | 3 | do not move | **0 moved** |

**The "will not move" half was exactly right for the second time running: 9 of
9.** The "will move" half was over-optimistic for the second time running: 14 of
23. That asymmetry is now a pattern and is recorded as such in ISSUES I-1.

## What the fix did

The ATT&CK half worked exactly as intended. `Tactic` went 0.0000 → 1.0000;
`Group` 0.0000 → 0.2250, limited by how much of a group's record the composer
states rather than by what was retrieved.

The CAPEC half works, and works further than the score shows. Asked *"Which
CAPEC categories does the view Mechanisms of Attack (CAPEC-1000) contain?"*, the
system now retrieves **all nine** and names all nine in its answer. It scores
**0.0000**, because it writes them as `capec:category:152` while the gold expects
`CAPEC-152`. See ISSUES I-3.

## Why the other 9 predicted movers did not move

Not one cause, three:

* **7 are compound, two-shape questions** (D4/D6) — "which patterns are peers of
  CAPEC-12, *and* what categories contain each of those?". The containment guard
  added during this work deliberately refuses them, because routing a compound
  question on its second hop answers the wrong one. They need multi-hop
  execution, which this change does not provide and does not claim to.
* **2 retrieve correctly and score zero** on the id-format mismatch above.
* **0 are retrieval failures.** Every query built in this set now runs the right
  traversal in the right direction.

## The regression that was not one

One question appeared to fall 0.0196 → 0.0000. It did not regress. Its "before"
answer was an *abstention* — "the routed sources returned no matching records" —
whose boilerplate hint reads *"e.g. T1566, M1017, or CAPEC-98"*, and `T1566` is
in that question's gold. Refusing to answer earned 1/51. The 0.0000 is the honest
figure and the "after" additionally completes the first hop, returning the view's
member where it previously returned nothing.

Four answers in the run scored credit this way, one of them at 0.1667. ISSUES I-2.

## What a reader should refuse to conclude

- That 0.4059 measures the fix. It measures the fix *through two scorer defects*,
  one of which is worth 0.185 on this set.
- That the CAPEC containment questions are answered. The single-shape ones are;
  the compound ones are not, and 7 of the 32 are compound.
- That any of this moves the deterministic arm's 0.4934. This touched 32 dev
  questions, not the arm. The arm comparison is still to be run.

---

## AMENDMENT A-1 (2026-09-09) — Record repair: what reproduces, what does not, and two cosmetic manifest fixes

Written from the 2026-09-09 audit (`verify-b5.md`). From the two pointed
directories over the 32 ids the audit reproduced **0.0787 → 0.4059, 14
improved** exactly, and confirmed the arithmetic behind the derived figures
(0.4059 / 0.0787 = 5.16×; 0.5913 − 0.4059 = 0.1854 ≈ 0.185; prediction table
rows 3 + 12 + 8 + 6 + 3 = 32; movers 3 + 8 + 3 = 14). No number changes.

1. **`0.5913` is not independently reproducible from the answer files alone.**
   It depends on re-implementing the scorer's id regex to accept the graph's
   `capec:category:N` form (ISSUES I-3); the audit did not attempt it. It is
   recorded as what the scorer would have said under that one change, and it
   is the figure EXP-2026-09-005 and EXP-2026-09-007 quote as "worth 0.185 on
   the subset measured".
2. **Raw decreases = 1, reported regressions = 0.** The same `CAPEC-703` case
   as in EXP-2026-09-003 fell 0.0196 → 0.0 for the reason ISSUES I-2 gives
   (boilerplate credit removed). `questions_regressed: 0` is the reading this
   file argues for at `:57-66`; a raw count would say 1.
3. **Manifest.** `scorer_defect_worth_on_this_set.std`: 0.0 → null (cosmetic;
   every sibling metric uses null for a single measurement).
   `environment.lockfile`: env/requirements.lock → null (never written; ISSUES
   I-7). `related` gains EXP-2026-09-005 and EXP-2026-09-007, which carry I-2
   and I-3 forward as declared, unfixed limitations. `data/metrics.json`
   created from `metrics.values`.

4. **`metrics.primary`** named `mean_recall_on_affected_questions`, a key that does
   not exist in `metrics.values`; it now names `mean_recall_after` (0.4059), the
   as-scored headline.
