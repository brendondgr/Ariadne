# i16-baseline-c5cb2906 — the "before" column of I-16's table

Generated in a `git worktree` detached at `c5cb2906` (the commit immediately
before the I-16 fix) against the **same** live Neo4j and Gremlin graphs and in
the same sitting as `i16-full-2026-09-12`. The only difference between the two
captures is `utils/synthesis/composer.py`.

**The answer files are not committed** — `.gitignore` keeps every
`experiments/**/answers/*` that is not a judgment sidecar, and neither of these
captures was graded. That costs nothing here: both arms run with every LLM seam
off, so both sides regenerate byte-for-byte from the commit and the data. The
committed evidence is
`EXP-2026-09-018/data/i16_contradictions.json`, and this is how to reproduce
either column of it:

```bash
# after (this tree)
uv run python -m utils.evaluation.experiment_untruncated --arm generic_composed \
  --bank docs/evaluation/composition/bank/bank-dev.json \
  --root docs/evaluation/experiments/i16-full-2026-09-12/dev --workers 16

# before: the same command in a worktree detached at c5cb2906, writing to
# docs/evaluation/experiments/i16-baseline-c5cb2906/dev
```

Symlink the **subdirectories** of `data/` into the worktree, not `data/` itself:
`data/versions.json` is tracked, so the checkout creates a real directory and a
`ln -s … data` lands inside it. The schema registry then discovers no datasets
and the run reports `33/288` with "no specialist for source 'attack'" on the
rest — it does not fail loudly.

Both banks, both model-free arms:

| Capture | contradictions here | after the fix |
|---|---|---|
| `dev/generic_composed` (284) | 7 | 0 |
| `dev/deterministic` (284) | 6 | 0 |
| `holdout/generic_composed` (288) | 5 | 0 |
| `holdout/deterministic` (288) | 6 | 0 |

The holdout is **not** spent by this: nothing here was graded.
