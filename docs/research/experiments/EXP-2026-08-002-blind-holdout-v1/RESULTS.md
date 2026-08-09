# RESULTS — EXP-2026-08-002 Blind holdout v1

Full write-up, including the per-category table, the failure analysis and the
gate decision: [`docs/evaluation/holdout-v1/README.md`](../../../evaluation/holdout-v1/README.md).
Per-case verdicts: [`results.json`](../../../evaluation/holdout-v1/results.json).
Raw answers, evidence and judgments: `docs/evaluation/experiments/holdout-v1/`.

Every number below is produced by `utils/evaluation/holdout_report.py` from the
per-case judgment files.

## Headline

| | Arm A (deterministic) | Arm F (loop + claim-bound writer) |
|---|---|---|
| Blind correctness | **0.689** (bootstrap 95% CI 0.550 – 0.817) | **0.708** (0.565 – 0.838) |
| Development correctness | 0.9972 | 0.9957 |
| Blind − development | **−0.308** | **−0.287** |
| CORRECT rate | 17/30 = 0.567 (Wilson 0.392 – 0.726) | 19/30 = 0.633 (0.455 – 0.781) |
| Hallucinations | 1 | 0 |
| Wall clock, 30 questions | 1.0 s | 554.0 s |

Excluding the one malformed authored question: 0.709 and 0.729 at n=29.

## What it shows

**C-013 is answered, and the answer is negative for C-001 as stated.** The
0.9972 development figure does not survive a blind question set. It was
substantially a property of the questions.

**But the drop is concentrated, not uniform**, and that is the usable finding.
Seven of sixteen categories score 1.00 on both arms — mitigations, tactics,
execution, weakness, mapping, pattern-to-mitigation, reverse-mapping. The loss
sits in four diagnosable modes:

1. **Reverse direction is unserved** (`groups`, `software`, 4 questions, ~0.03).
   `group_techniques` binds `$ids` to `Group.attack_id`; the holdout seeds a
   technique id, so the query is structurally unsatisfiable. The system answers
   *A → B* and was asked *B → A*. The development bank only ever asks one
   direction, which is why this was invisible.
2. **Facet counts instead of neighbours** (`consequence`, `prerequisite`,
   `hierarchy`, 3 questions, ~0.13). Retrieval succeeded, synthesis did not use
   it — `H-PRE-01` retrieved all three skill nodes and reported none of them.
3. **Metadata instead of substance** (`lookup`, 3 questions, 0.55 / 0.62). Every
   case satisfied its computed gold and was still PARTIAL. This is a limitation
   of computed gold, not only of the system.
4. **Chain incompleteness** (`cwe-chain`, 3 questions, ~0.65).

**The federated path generalises best.** By stratum: federated 0.890 / 0.905,
CAPEC 0.619 / 0.656, ATT&CK 0.568 / 0.579. The project's actual contribution is
the part that holds up.

**The abstention machinery holds completely.** On the four abstention-expected
anchors — no live ATT&CK mapping, the case a system is most tempted to
hallucinate through — both arms abstained 4/4, carried the executed query as
proof 4/4, and fabricated a mapping **0/4**. This is the strongest result in the
run and it is the one C-017 has been waiting for, though four cases is still too
few to promote that claim.

**Arm F − Arm A = +0.019 for 554× the wall clock.** The loop and the
claim-bound writer buy almost nothing here, because the dominant failures are
retrieval-shape failures the loop does not chase. This does not contradict C-005
or C-006 — both were measured on in-distribution questions — but it bounds them.

## Effect on the claim ledger

| Claim | Before | After |
|---|---|---|
| C-013 | `unsupported` | **`supported`** — the holdout exists, is auditable, and answers the question it was built to answer |
| C-001 | `partial` | **`refuted as stated`** — near-ceiling correctness is not a general capability; it holds on covered question shapes |
| C-014 | `unsupported` | **`partial`** — the coverage boundary is now measured for relation direction, though not for non-anchored questions |

## Deviations

1. **Missing `join_key` on the CAPEC `mapping` category.** The Compiler emitted
   `join_key: null`, so `H-MAP-01`/`H-MAP-02` routed to `describe` and returned
   facet counts; the three committed `C-MAP-*` entries all carry the key, so the
   holdout was being compared against a different plan than the development set
   gets for the same category. Harness defect, not a wrong answer — §9's crash
   rule applies. Fixed, both cases re-run and re-judged on both arms, question
   text untouched. Arm A moved 0.627 → 0.689.
2. **One malformed authored question kept, not repaired** (`H-SW-01`). See
   [`ISSUES.md`](ISSUES.md).
3. **Three judgment files** were not written by their grading agents although
   the agents returned the verdicts; each was recovered verbatim from the
   workflow journal rather than re-graded.

## Limitations

- n=30. The intervals are wide, per-category cells hold 1–4 questions, and the
  Branch A gate's 0.70 threshold sits 0.011 from the result with a CI spanning
  three of its four bands. This gate cannot be resolved sharply at this n.
- An LLM-authored holdout controls **co-authorship bias** but not the question
  distribution being a model's idea of what an analyst asks. A human-authored
  set remains the stronger test; a further 15–20 questions would be a cheap
  secondary check.
- One run, no variance estimate. The Author, the judge and Arm F's pipeline are
  all nondeterministic; only Arm A would replay byte-identically.
- Computed gold cannot express "answer the question the analyst asked", which is
  exactly what the `lookup` cases failed at while passing their assertions.
