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
