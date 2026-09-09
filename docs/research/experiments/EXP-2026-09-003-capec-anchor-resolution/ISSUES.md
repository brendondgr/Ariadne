# ISSUES — EXP-2026-09-003

## I-1 — The hypothesis was wrong by a factor of twelve

The plan predicted 47 cases would move; 2 did. Recorded here rather than
softened in RESULTS, because the error is instructive: every one of the 60
failing drafts really did carry `hasLabel("AttackPattern")`, so the correlation
was perfect and the causal claim still wrong. The label bug blocked those
questions at the *retrieval* stage while a routing bug blocks them at the
*template selection* stage, and only the outer one was visible.

**Refuse to conclude:** that a shared symptom across failures implies a shared
cause. It did not here, and the same reasoning produced EXP-2026-09-002's "63 of
63" figure, which was an artifact of a classifier with one reachable branch.

## I-2 — n = 37, one run, no interval

A targeted re-run over the affected dev questions, not a bank re-measurement.
Two questions moving is a count, not an estimate, and carries no interval.
`D-010` is still in force.

## I-3 — The comparison is against stale saved answers

"Before" is read from the EXP-2026-09-002 artifacts, produced 2026-09-02 against
the *previous* graph build. The ATT&CK property policy widened and both stores
were reloaded on 2026-09-03 between the two, so the two sides of this comparison
did not see identical graphs.

**Why it does not invalidate the finding:** all 37 questions are CAPEC-anchored,
and CAPEC's build was not changed — only its store was reloaded, from the same
committed export, to 6,374 / 8,582. The one CAPEC difference is the recovered
`HAS_REFERENCE` edge (the store previously held 8,581), which touches no
question here. **Refuse to conclude** anything about ATT&CK-anchored questions
from this run.

## I-4 — The experiment id collides with the parent plan's reservation

`docs/plans/2026-09-03-measurement-and-retrieval-repair.md` Step 8 reserved
`EXP-2026-09-003` for the post-repair arm comparison. `make new-experiment`
allocated it here first. The arm comparison will take the next free id; this is
recorded so a reader chasing the plan's text does not conclude the arm
comparison was filed and lost.

## I-5 — Two pre-existing suite failures, neither caused here

`test_docs_contracts.py::test_every_cited_repo_path_exists` fails on a dangling
pointer in EXP-2026-09-001's `POINTERS.md`
(`docs/evaluation/composition/authored/ingested.json`, committed at `eeef322`,
not tracked in HEAD). `test_pipeline.py::test_event_order_matches_streaming_contract`
fails under the local `.env` pin `ORCH_MAX_HOPS=1` and passes at 5. Both were
verified present before this work.

## I-6 — 2026-09-09: seeds and lockfile

`seeds: []` is accurate: the deterministic arm takes no model and no random
draw, and the 37 ids were selected by the plan, not sampled.
`environment.lockfile` pointed at `env/requirements.lock`, which was never
written; set to `null` in A-1. The dependency set is `uv.lock` at `2432ce8`.
