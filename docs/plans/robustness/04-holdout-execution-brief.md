# Plan 04 — Holdout execution brief (operator copy)

**Parent:** `02-holdout-question-generation.md` — that plan is normative; this
brief only fixes execution details it left open. Author-role constraint added
here: **the Author MUST be a Claude Fable 5 subagent at high reasoning effort.
No other model, no lower effort, no exceptions.** Record
`"author_model": "claude-fable-5 (high effort)"` in every `holdout_meta`.

## Roles

| Role | Held by | Context |
|---|---|---|
| Sampler | `holdout_protocol.py` (script) | Full repo |
| Author | **Fable 5 High Effort subagent**, one fresh spawn per anchor | §3 whitelist only — enforced by prompt construction, not instruction |
| Compiler | Orchestrator session | Full repo |

The orchestrator session is contaminated (has read plans, README, eval docs)
and may never author question text. One agent, one role.

## Steps

1. **Freeze check.** Detached checkout of `freeze/holdout-v1` (`974e85a`);
   `git describe --exact-match` must pass. Verify both snapshot SHA256s against
   `data/versions.json`; abort on mismatch.
2. **Sampler.** Write + commit `utils/specialists/evalset/holdout_protocol.py`.
   New fixed seed (not 1729), module-level constant. Strata 12 ATT&CK / 8 CAPEC /
   10 federated, uniform within stratum, federated over-drawn to partition
   ~6 answerable / ~4 abstention-expected.
3. **Draw.** Emit `docs/evaluation/holdout-v1/anchors.json` (seed, populations,
   draw order, population SHA256s). **Commit before any authoring** — the
   timestamp proves draw preceded questions.
4. **Author.** Per anchor, spawn a fresh **Fable 5 High Effort** subagent whose
   prompt contains ONLY: anchor id, entity type, snapshot name, category label,
   the §5 category descriptions verbatim, and the reference-discipline rule
   (cite id + snapshot name on first mention; no recall from memory; no network).
   No repo file access. It returns one analyst question, nothing else — no
   answer, no template guess, no tier. Save the exact prompt verbatim to
   `docs/evaluation/holdout-v1/author-prompt.md`.
5. **Compile.** Gold via existing `gold_bank.py` only. Failure ⇒ discard anchor,
   redraw from seeded sequence, log reason. Assemble
   `utils/specialists/tests/golden/holdout_questions.json`: `split: "holdout"`,
   `H-` ids, `expected_template_is_derived: true`.
6. **Run.** Arms A and F only, on the frozen tag, consolidated judge.
   **Nothing changes between compile and write-up.** Crash ⇒ fix, log as
   deviation, re-run. Wrong answer ⇒ result, not bug.
7. **Report.** `docs/evaluation/holdout-v1/README.md`: Wilson intervals (n=30),
   dev-set figure alongside, per-category breakdown, federated strata reported
   separately (abstention-expected scored on abstention behaviour), discard log,
   and the §10 limitation statement verbatim. Hand the number to the Branch A §6
   gate; thresholds are not renegotiated after seeing the result.

## Deliverables

Per parent plan §8: `holdout_protocol.py`, `holdout_questions.json`,
`docs/evaluation/holdout-v1/{anchors.json, author-prompt.md, README.md,
results.json}`, raw artifacts under `docs/evaluation/experiments/holdout-v1/`.
