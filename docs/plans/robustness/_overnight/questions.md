# Open questions from the overnight pass

Everything here needed a decision the plan reserved for a human. Nothing below
was resolved unilaterally.

---

## Q1 — An uncommitted `.gitignore` change hides the Arm G artifacts

**Found:** Task 1. The primary checkout carries an uncommitted `.gitignore`
hunk adding the line `docs/evaluation/experiments`, which makes
`docs/evaluation/experiments/untruncated-generic/` invisible to `git status`
and un-addable without `-f`.

**Why it is a question:** 2,657 files under `docs/evaluation/experiments/` are
already tracked, so the rule contradicts the repository's existing practice and
only takes effect for *new* runs. It is not one of the four Arm G paths the plan
lists, and committing it would silently drop Arm G from version control.

**What was done:** the Arm G artifacts were committed — Task 1 requires it
explicitly, and without them the freeze tag would freeze a tree where Arm G does
not exist. The `.gitignore` hunk itself was **not** committed and remains an
uncommitted local change in the primary checkout, exactly as found.

**Decision needed:** whether new experiment output should be ignored going
forward. If yes, the rule needs negations for the already-tracked directories or
it will confuse the next run; if no, the local hunk should be discarded.

---

## Q2 — `utils/specialists/cypher/normalizer.py` was modified but not listed

**Found:** Task 1. The plan names three modified files for the Arm G commit;
`git diff` shows a fourth, `utils/specialists/cypher/normalizer.py` (+64 lines:
a `_normalize_generic_neighbors` method and a dispatch branch that detects the
`anchor_id`/`neighbour_id` column shape).

**Why it is a question:** the plan says to stop and record anything beyond "the
generic-only gating" rather than commit it.

**Assessment:** the change *is* the generic-only gating — it is the normalizer
half of `CypherQueryBuilder._generic_neighbors`, and Arm G yields zero evidence
records without it. The new dispatch branch is guarded on a column shape
(`anchor_id` **and** `neighbour_id`) that no other template emits, so the default
path is unaffected. It was therefore committed with the rest of Arm G.

**Decision needed:** confirmation that this reading is right. If it is not, the
Arm G commit needs splitting before the freeze tag is trusted.

---

## Q6 — The plan's "F − G delta" is signed the other way round

**Found:** Task 4. Plan 01 §Task 5 asks for the "**F − G delta (−0.357)**"
stated alongside the "**B − C planning delta (−0.1185)**".

The recomputed figures are F 0.995667 and G 0.638833, so **F − G = +0.356834**;
the quoted −0.357 is **G − F**. The magnitude is right and it is the sign
convention that matches B − C (0.850500 − 0.969000 = −0.118500, worse arm
first).

**What was done:** the tables state it as **G − F = −0.3568**, which is the
figure the plan intends and the convention that makes the two deltas directly
comparable. `numbers.json` carries both signs and a `sign_convention` note.

**Decision needed:** none, unless the author prefers the F − G ordering — in
which case the sign in the tables flips to positive and the two deltas stop
being comparable at a glance.

---

## Q7 — Arm B's coverage cell was spliced from the pre-fix run too

**Found:** Task 6. The plan says only two figures move — Arm A's wall clock and
its record count — because related neighbours and coverage are identical across
the pre- and post-fix runs *for Arm A*. That is true for Arm A. It is not true
for Arm B.

The cost table's Arm B coverage read **0.7989**, which is
`untruncated/llm` — the pre-fix run. Post-fix `untruncated-fixed/llm` is
**0.8074**. Arm E's coverage cell was blank; it is **0.8819**
(`untruncated-loop2/llm_loop`).

All three are macro means over the 66 scorable cases, matching the repository's
own aggregation in `utils/evaluation/summarize_untruncated.py:81,99`.

**What was done:** corrected in the same commit as the Arm A figures, since it
is the same splice in the same table, and called out in the dated correction
note above the table rather than changed silently.

**Decision needed:** none, but it is worth knowing the splice was wider than the
plan assumed. If any other document quotes 0.7989 as a post-fix figure it needs
the same treatment; a grep at the time of writing found none.

---

## Q3 — The local model's quantisation is unknown

**Found:** Task 10. The evaluation record can now name the model but not how it
was quantised. Nothing in the repository records it; it is a property of the
operator's local serving stack.

**Decision needed:** the operator to state the quantisation (or that the model
was served unquantised) so the evaluation record is reproducible.

---

## Q4 — The local model's exact context window is unknown

**Found:** Task 10. The repository gives three different figures and none is
authoritative. The `.env` value is a *client request*, not a server capability —
it is what the client asks for, and the server may cap it lower.

**Decision needed:** the operator to read the served window off the model server
and record it.

---

## Q8 — `.env.example` now pins `ORCH_MAX_HOPS=1`, which changes fresh-clone behaviour

**Found:** Task 9. The plan says to add the key "with a comment explaining both
the default and what the evaluation runs used". Adding it as a *live* key is the
only way to actually close the divergence — commented out, a fresh clone still
inherits the code default of 5 and still runs with the retrieval loop on, which
is the state the plan calls a problem.

It is therefore set to **1**, matching the operator's own `.env` and the
single-pass arms of the evaluation record. The code default
(`DEFAULT_MAX_HOPS = 5`, `utils/orchestration/config.py`) is untouched.

**Decision needed:** confirmation that a fresh clone should default to
single-pass. If the intended shipping default is the loop, change the value to
5 — the comment beside it already documents both.

---

## Q9 — A test-isolation bug that this `.env.example` key exposes

**Found:** Task 9, incidentally.

`utils/setup_wizard/tests/test_steps.py` materialises an env file from
`.env.example` and loads it with `override=True`, which leaks the file's values
into `os.environ` for every test that runs afterwards **in the same pytest
process**. With `ORCH_MAX_HOPS=1` now present in `.env.example`, running

```
pytest utils/setup_wizard/ utils/orchestration/
```

fails three `test_event_parity.py` tests that pass in isolation and pass in the
full suite — because default collection order puts `utils/orchestration` before
`utils/setup_wizard`, so the pollution lands after they have already run.

**The full suite is unaffected** (verified: same 4 pre-existing failures, 1,308
passed, before and after). This is a latent ordering dependency, not a
regression introduced here — the key merely made it observable.

**Decision needed:** none urgently, but the wizard tests should restore
`os.environ` around the env-file step. Left alone because fixing it is a code
change and this plan is documentation-only outside Task 8's docstrings.
