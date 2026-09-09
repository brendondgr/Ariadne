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

---

# AMENDMENTS

## A-1 (2026-08-23) — Q17 answered, negatively: the malformed question explains none of the `software` loss

**Nothing was re-run.** This reads the two `H-SW-*` entries in
`utils/specialists/tests/golden/holdout_questions.json` and their committed
judgments under `docs/evaluation/experiments/holdout-v1/`.

Q17 asked how much of `software`'s **0.06** was a malformed question rather than
a retrieval failure, and flagged that the category description was written from
the software's point of view while the anchor is always a Technique. The
malformation is confirmed. **Its effect on the score is zero, and removing it
would make the category look worse.**

| id | question | well-formed? | correctness |
|---|---|---|---|
| `H-SW-01` | "What techniques does T1555.005 (Password Managers) implement?" | **No** — asks for techniques, names a technique as though it were software, graded against software ids | **0.10** |
| `H-SW-02` | "Which software has been observed implementing T1005 (Data from Local System)?" | **Yes** — correct direction, technique anchor, software gold | **0.02** |

Mean 0.06, which reproduces the recorded figure exactly. **The well-formed
question scored five times worse than the malformed one**, and Arm F scored
`H-SW-02` at 0.00.

Both failed by the *same* mechanism, and it is the directional one:

> "The executed query fetched only the Technique node's own properties and
> aggregate relationship-type counts (facets), never expanding the 169
> incoming …" — grader on `H-SW-02`

> "The retrieved facets on T1555.005 clearly show a USES-in relationship from
> label Software with count=4 …" — grader on `H-SW-01`

In both cases `describe` returned the anchor and a facet **count** for the
reverse `USES` edge and never expanded it. The system could see that the
relationship existed and could not follow it. That is exactly the reverse-
direction cliff, and the malformed phrasing did not cause it — the malformed
question in fact scored *higher*, because its four-item gold is easier to
partially hit than a 170-item one.

**Conclusion: `software` stays in C-014's supporting evidence, and the reading
is stronger than before rather than weaker.** (Feeds C-014; the directional
mechanism it identifies is also part of what C-023 prices as coverage cost.) The evidence for the directional
cliff no longer rests on a question anyone can dismiss as broken; it rests on
`H-SW-02`, which is well-formed and scored 0.02.

**Incidental, and consistent with C-009:** the local grader scored these two
PARTIAL at 0.25 and 0.35 where Sonnet scored them INCORRECT at 0.10 and 0.02 —
the same overstatement direction recorded elsewhere in the study.

## AMENDMENT A-2 (2026-09-09) — Provenance repaired: an invented commit sha, a blank pointer table, no metrics file, a primary metric that named no key

**What was wrong, and what is now correct.** Nothing was re-run; every number
in this record was recomputed by the B2 audit of 2026-09-09 from the 30 + 30
original `*.judgment.json` files and reproduced exactly (0.689, CI 0.550–0.817,
17 CORRECT, 1 hallucination, 0.7093 excl. `H-SW-01`; 0.7083, CI 0.565–0.838,
19 CORRECT, 0.7293 excl.).

1. `manifest.yaml:27` recorded `code.commit:
   ce3a2d2b7f0e6b0e9e4c9c9a2b0d3f5a7c1e8d94`. **No such object exists** — the
   first seven characters are right and the remaining 33 were padded. The
   commit is `ce3a2d2810ba5d2199d4fea18ac7824b6d9554bf` ("Holdout Execution
   (7/8): Run and grade Arm F, and fix one compiler deviation", 2026-08-09
   13:11 −0400, on `claude/holdout-execution-process-8d74cd`, merged in
   `336d5ef`), verified with `git cat-file -e`. It is also the last commit to
   touch `holdout_questions.json`. **Old → new** as stated.
2. `data/POINTERS.md` was the blank scaffold (one empty row). It now lists
   eight artifacts with hashes: `results.json`, `README.md`, `anchors.json`,
   `authored.json`, `author-prompt.md`, the blind bank, and the two raw output
   directories. The Arm A directory
   (`docs/evaluation/experiments/holdout-v1/deterministic`) has **gained 60
   files since this experiment ran**: 30 `*.judgment.local.json` and 30
   `*.judgment.local.pre-qwen38.json`, dated 2026-08-31, written by
   `EXP-2026-08-021`'s grader-calibration passes (that experiment's POINTERS
   names the `pre-qwen38` set as its preserved Ornith-era calibration
   artifacts). The 30 answer files and 30 original judgment files are dated
   2026-08-09 and are the files the recomputation above used; the tree hash
   recorded pins the directory as it now stands, sidecars included, and the
   pointer row says so. The Arm F directory has no later files.
3. `data/metrics.json` did not exist. Created, with `manifest_metrics` copied
   from the manifest and the per-arm aggregates (CIs, Wilson intervals,
   strata, categories, development comparison) read from `results.json`
   rather than typed.
4. `manifest.yaml:74` set `metrics.primary: correctness`, which is not a key
   in `metrics.values`, so `INDEX.md` rendered this experiment as
   "correctness (not recorded)". **Old:** `correctness` → **new:**
   `arm_a_blind_correctness` (0.689), the figure the gate decision was taken
   on.
5. `manifest.yaml:49` `compute.wall_clock_hours` **0.16 → 0.154**: 1.0 s +
   554.0 s from the run logs (ISSUES §4 explains why the per-arm
   `manifest.json` files cannot confirm this — they were overwritten by the
   two-case re-run).
6. `manifest.yaml:54` named the Arm F pipeline model as "local/skynet
   (gemma4-31B-mtp via vLLM)". Rewritten in the format
   `docs/evaluation/README.md` prescribes — `relay/gemma4-31B-mtp@2026-08-09`
   — with no change in substance: that is what was recorded at run time via
   the relay, not verified from the serving side. The Author and judge fields
   are unchanged.

**Later work on this bank (refinement, no supersession).** `EXP-2026-08-003`
(2026-08-10) ran Arm H against these 30 questions, and `EXP-2026-08-007`
(2026-08-19) re-judged the same bank after the binding/direction and
outer-join repairs: cascade **0.8367**, Arm H 0.8483, Arm F **0.9157** (its
manifest values). Those are post-repair figures on a bank that had already
diagnosed the repaired defect, and `EXP-2026-08-005` ISSUES says why such a
number is a diagnostic rather than a headline; the 0.689 / 0.708 here remain
the only blind pre-repair figures. Both experiments are added to `related`.
`status: complete` and the null supersession links stand.
