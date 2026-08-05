# Plan 01 — Overnight-safe work

**Audience:** an unattended agent, running without supervision, in the Ariadne
repository.
**Goal:** clear every mechanical task blocking the rest of the programme, so
that a human waking up tomorrow finds the busy work gone and nothing important
decided on their behalf.
**Duration:** one session. All twelve tasks together are roughly a day of
human-equivalent work.
**Prerequisite:** none. This is the first thing that happens.
**Unblocks:** Plan 02 (needs the freeze tag), and every demo submission (needs
the attribution notice).

---

## 0. The contract

Every task below satisfies three conditions, and you must not add tasks that
do not:

1. **Mechanically verifiable.** Success is checkable against a file, a count, or
   a recomputation — never against judgement about what the project should
   claim.
2. **Reversible.** Nothing here deletes data, rewrites history, or changes
   runtime behaviour that an experiment depends on.
3. **Decision-free.** If completing a task requires choosing what the project
   asserts, it is out of scope. Record the question and move on.

If you find yourself reasoning about whether a claim is *defensible*, you have
left this plan. Stop, write the question into `_overnight/questions.md`, and
continue with the next task.

---

## 1. Hard prohibitions

These are not preferences. Violating any of them damages work that cannot be
cheaply redone.

**Do not modify any file under `utils/specialists/` except docstrings and
comments.** The template builders are about to be frozen and measured. A
behavioural change here silently invalidates every number produced afterwards.
Docstring corrections are explicitly permitted and are Task 8.

**Do not touch the question banks.** `utils/specialists/tests/golden/*.json` and
everything under `utils/specialists/evalset/` are inputs to a blind experiment.
Not one byte.

**Do not delete dead code.** `_node_lookup` (`utils/specialists/cypher/builder.py:395`)
and `_capec_lookup` (`utils/specialists/gremlin/builder.py:243`) are unreachable,
but `_capec_lookup` is referenced by
`utils/specialists/tests/test_gremlin_validator.py:215`. Mark them, do not
remove them. Deletion is a behavioural change dressed as tidying.

**Do not run any experiment, arm, or evaluation.** Nothing that calls an LLM
endpoint, nothing that writes under `docs/evaluation/experiments/*/answers/` or
`*/judgment*`. Recomputing *statistics from existing committed judgment files* is
required and is Task 4 — that is reading, not running.

**Do not modify `.env`.** It is gitignored and it is the operator's machine
state. `.env.example` is in scope and is Task 9.

**Do not `git push`.** Commit freely; the repository's standing rule is commit
without pushing unless explicitly asked.

**Do not write the related-work section, the holdout questions, or any part of
the pitch.** Those are Plans 02 and 04 and they are not yours.

**Do not rewrite git history.** No rebase, no amend of anything already
committed, no force anything.

---

## 2. Setup

Create a working directory for your own artifacts. It is committed, because the
audit trail matters more than tidiness:

```
docs/plans/robustness/_overnight/
├── run-log.md            # what you did, in order, with timestamps
├── numbers.json          # Task 4 output — the canonical recomputed figures
├── verification.md       # Task 12 output — the self-check
└── questions.md          # anything you could not resolve without a decision
```

Record the starting commit SHA and `git status` output in `run-log.md` before
touching anything.

---

## 3. Tasks

Execute in order. Commit after each. If a task fails, record the failure in
`run-log.md`, skip it, and continue — do not improvise a workaround.

### Task 1 — Commit the untracked Arm G work

`git status` currently shows four uncommitted or untracked paths that together
constitute the Arm G control, which is the strongest result in the project and
is currently outside version control:

- `utils/specialists/cypher/builder.py` (modified — `SPECIALIST_GENERIC_ONLY` path)
- `utils/specialists/gremlin/builder.py` (modified — same)
- `utils/evaluation/experiment_untruncated.py` (modified — the `generic` arm)
- `docs/evaluation/experiments/untruncated-generic/` (untracked — 241 files)

Also untracked: `docs/pitch/`.

**Note the tension with the prohibition above.** You are committing existing
uncommitted changes to `utils/specialists/`, not authoring new ones. Commit
exactly what is on disk. Do not edit those three files in this task. If
`git diff` shows anything you did not expect — anything beyond the
generic-only gating — stop and record it in `questions.md` rather than
committing.

Verify before committing: `docs/evaluation/experiments/untruncated-generic/generic/`
contains 120 `*.json` answers, 120 `*.judgment.json`, and a `manifest.json`
reporting `count: 120`.

Commit: `Overnight (1/12): Commit the Arm G generic-only control code path and its 120-case artifacts.`

### Task 2 — Bring `docs/pitch/` under version control

Untracked, and it contains the only existing mention of the Arm G result
(`checkin-pitch.md:196`). Commit as-is; do not edit its contents.

Commit: `Overnight (2/12): Track docs/pitch/.`

### Task 3 — Write the MITRE attribution NOTICE

There is no attribution notice anywhere in the repository despite the entire
value proposition resting on ATT&CK and CAPEC.

Create `NOTICE` at the repository root containing: a statement that this project
uses MITRE ATT&CK® and CAPEC™, the required MITRE attribution language, links to
the ATT&CK Terms of Use and the CAPEC terms, and the exact dataset versions in
use — **ATT&CK 19.0** and **CAPEC 3.9**, with the SHA256 values recorded in
`data/versions.json`. Link `NOTICE` from `README.md`.

If you can retrieve the current MITRE terms text, use it verbatim. If you
cannot, write the attribution statement from the version information you have,
mark the terms-text section `<!-- TODO: verify against MITRE terms page -->`,
and log it in `questions.md`. **Do not paraphrase legal text from memory and
present it as quoted.**

**This is not the license.** The repository license is a PI decision and is
explicitly out of scope. Do not create a `LICENSE` file, do not add a `license`
field to `pyproject.toml` or `web/package.json`, do not pick one.

Commit: `Overnight (3/12): Add the MITRE ATT&CK and CAPEC attribution notice.`

### Task 4 — Recompute every arm figure from the judgment files

This is the foundation for Tasks 5–7. Do not carry any number forward from prose
in the repository or from this plan; derive all of them yourself.

For every arm directory under `docs/evaluation/experiments/*/`, read every
`*.judgment.json` and compute: n, mean correctness, mean completeness, mean
faithfulness, mean groundedness, the CORRECT/PARTIAL/INCORRECT counts, total
hallucinations and the number of cases carrying at least one. Read `manifest.json`
for `wall_s`. Compute `evidence_records` and `related` from the answer files.

Write the result to `_overnight/numbers.json`, keyed by directory path, with a
`source_files` count per entry so the derivation is auditable.

Expected values, for your own sanity check only — **if yours disagree, trust
yours and flag the discrepancy in `questions.md`**:
`untruncated-fixed/deterministic` (Arm A) 0.9972, 1.6 s, 1,061 records;
`untruncated-goldloop/gold_loop_llm` (Arm F) 0.9957;
`untruncated-claimnarr/gold_llm` (Arm D) 0.9917;
`untruncated-fixed/gold_llm` (Arm C) 0.9690;
`untruncated-loop2/llm_loop` (Arm E) 0.8560;
`untruncated-fixed/llm` (Arm B) 0.8505;
`untruncated-generic/generic` (Arm G) 0.6388, 64/14/42.

Keep the pre-fix runs (`untruncated/`, `untruncated-loop/`) in a separate
`superseded` block. They must never be aggregated with the post-fix runs.

Commit: `Overnight (4/12): Recompute all arm statistics from the committed judgment files.`

### Task 5 — Add Arm G to both arm tables

Using `_overnight/numbers.json` only.

- `docs/evaluation/2026-07-26/README.md` — add the Arm G row to the results
  table with its full metric set.
- `docs/evaluation/experiments/README.md:18-24` — the code→letter map currently
  covers A, B, C, E, F. Add **D** (`untruncated-claimnarr/gold_llm`) and **G**
  (`untruncated-generic/generic`).

State the **F − G delta (−0.357)** immediately alongside the **B − C planning
delta (−0.1185)**, so a reader sees the relative magnitudes without arithmetic.
Add one sentence noting that Arm G is a *generic-primitives* control — templates
disabled, schema-driven primitives only — and **not** free-form LLM query
generation, which has never been run.

Commit: `Overnight (5/12): Report Arm G in both arm tables with the F-G delta.`

### Task 6 — Propagate the Arm A cost correction

The cost column currently splices pre-fix Arm A figures next to post-fix
correctness. The post-fix run is **1.6 s / 1,061 records**, not 2.6 s / 1,840.
Related neighbours (839) and coverage (1.0000) are identical across both runs,
so only two figures move.

Correct every occurrence and every derived figure:

- `docs/evaluation/2026-07-26/README.md:41` and `:217`
- `docs/pitch/checkin-pitch.md:245`
- `docs/research/audit-2026-08-03.md:296` and `:533`

The derived **"392× wall-clock difference" becomes 637×** at 1.6 s. Recompute it
rather than trusting that figure; show your arithmetic in the commit body.

`docs/research/audit-2026-08-03.md` is a dated historical document. Do not
silently rewrite it — insert a dated correction note alongside the original
figure, matching the convention already used at
`docs/evaluation/2026-07-26/README.md:62-70`.

Commit: `Overnight (6/12): Correct the Arm A cost figures to 1.6 s / 1,061 records and the derived speedup to 637x.`

### Task 7 — Reconcile the template count

The repository gives four different answers:

| Location | Says |
|---|---|
| `README.md:39` | 16 Cypher + 11 Gremlin = 27 |
| `README.md:186` | "24 total" |
| `docs/evaluation/2026-07-26/portability.md:72` | "24 total" |
| `docs/research/audit-2026-08-03.md:30` | 17 Cypher + 11 Gremlin = 28 |
| `utils/specialists/cypher/builder.py:128` | "The fifteen intent templates" |

**Derive the truth mechanically.** Count the distinct `template="…"` string
literals in each builder, and separately count the `QueryDraft`-returning
methods. Determine reachability from `build()`. Determine which the question
banks exercise by scanning `expected_template` across the three bank files.

Write the derivation into `_overnight/numbers.json` under a `templates` key —
per-builder counts, the shared names, the dead ones, the reachable ones, the
exercised ones — then update every location above to agree with it. State the
figure the same way everywhere: *N distinct template identifiers, of which M are
exercised by the 120-question bank.*

Commit: `Overnight (7/12): Reconcile the template count across all five locations against a mechanical derivation.`

### Task 8 — Fix the stale builder docstrings

Docstrings and comments only. **No logic.**

- `utils/specialists/cypher/builder.py:128` claims "The fifteen intent templates"
  and lists names including `node_dossier` and `node_dossier_by_name` that no
  longer exist as methods. Correct the count and the list.
- `utils/specialists/gremlin/builder.py:147-153` lists a five-template priority
  order including `capec_dossier_by_name`, which no longer exists. Correct it.
- Add a one-line `# Dead: no production caller` comment above `_node_lookup`
  (`cypher/builder.py:395`) and `_capec_lookup` (`gremlin/builder.py:243`), the
  latter noting it is still referenced by
  `utils/specialists/tests/test_gremlin_validator.py:215`.

Run the test suite afterwards and confirm the count is unchanged. If any test
fails, revert this task entirely and log it.

Commit: `Overnight (8/12): Correct the stale template docstrings in both builders.`

### Task 9 — Close the `.env.example` divergences

`.env.example` cannot reproduce the documented behaviour:

- **`ORCH_MAX_HOPS` is absent entirely.** A fresh clone therefore runs at the
  code default of 5 — retrieval loop on — while the evaluation record describes
  a pinned single pass. Add the key with a comment explaining both the default
  and what the evaluation runs used.
- **`EVAL_LLM_MAX_TOKENS`** reads 1024 in the example against 32000 in `.env`.
  Align the example with the value the evaluations actually used and say so in a
  comment.
- The pipeline comment block at `.env.example:193-199` describes
  "probe → plan → specialists → bundle → synthesize" and omits assess/replan
  entirely. Correct it to match `utils/orchestration/main.py:271-308`, and note
  that the assess/replan loop is inert at `max_hops=1` and that
  `ORCH_ASSESS_MODE=llm` degrades to deterministic because no critic is wired
  (`policy.py:40`, `main.py:199`).

Do not change any default in code. Documentation and example configuration only.

Commit: `Overnight (9/12): Close the .env.example divergences and correct the pipeline comment.`

### Task 10 — Record the model identity

`docs/evaluation/README.md` — record that the local model referred to as
`skynet` throughout the evaluation record is **Gemma 4 31B**.

Two fields remain unknown and must be written as unknown, not guessed: the
**quantisation**, and the **exact context window**. The repository currently
reports the window three inconsistent ways — "unknown from the client side"
(`docs/plans/answer-truncation-fix-plan.md:51`), "~64k"
(`docs/evaluation/2026-07-26/README.md:301`), and `48000` (`.env:139,159`).
Replace all three with a single statement naming the model, listing the two
outstanding fields as open, and cross-referencing the three prior figures so the
history is visible.

Add both open fields to `questions.md`.

Commit: `Overnight (10/12): Record the evaluation model as Gemma 4 31B and consolidate the context-window discrepancy.`

### Task 11 — Tag the freeze

**This must be the last substantive task.** Everything above changes files that
the frozen tag should contain — particularly Task 1, without which the tag would
freeze a tree where Arm G does not exist.

```
git tag -a freeze/holdout-v1 -m "Frozen for the blind holdout. Templates and planner immutable from this point."
```

Write the resulting SHA into `_overnight/run-log.md`, into
`docs/plans/robustness/02-holdout-question-generation.md` §2, and into
`docs/plans/branch-a-publication-readiness-plan.md` Step 1.

Commit: `Overnight (11/12): Tag freeze/holdout-v1 ahead of the blind holdout.`

### Task 12 — Self-verify

Write `_overnight/verification.md` containing:

- Every number you changed, with its old value, new value, and the file the new
  value was derived from.
- Confirmation that `git diff freeze/holdout-v1 -- utils/specialists/` shows
  **only** docstring and comment changes.
- Test suite result before and after, with counts.
- The full list of files touched.
- Everything in `questions.md`, restated.

Then re-derive three figures independently, from the raw files rather than from
`numbers.json`: Arm G's mean correctness, Arm A's record count, and the template
count. If any disagrees with what you wrote, say so prominently at the top of
the file rather than quietly correcting it.

Commit: `Overnight (12/12): Self-verification record for the overnight pass.`

---

## 4. Morning review checklist

For the human, in this order. Roughly fifteen minutes.

1. **Read `_overnight/questions.md` first.** Anything the agent could not
   resolve without a decision is here. This is the highest-value output of the
   whole run.
2. **Check the freeze diff:** `git diff freeze/holdout-v1 -- utils/specialists/`.
   Anything beyond docstrings means the freeze is compromised and the tag must
   be moved after fixing.
3. **Spot-check three numbers** in `_overnight/verification.md` against the
   files they claim to come from. If the agent recomputed Arm G as anything
   other than ~0.6388, understand why before proceeding.
4. **Confirm no `LICENSE` file was created.** That decision is not the agent's.
5. **Confirm nothing was pushed:** `git log origin/main..HEAD` should show all
   twelve commits still local.
6. **Read the NOTICE.** If Task 3 could not retrieve the MITRE terms text, the
   TODO marker needs a human to close it before any artifact release.

Once 1–6 pass, Plan 02 is unblocked.

---

## 5. Explicitly out of scope

Recorded here so a later agent does not assume they were forgotten.

| Item | Where it lives |
|---|---|
| Repository license | Plan 03 — PI decision |
| Holdout question generation | Plan 02 |
| Related-work section | Plan 04 |
| Judge consolidation into `utils/evaluation/independent_judge/` | Plan 03 — the design call of which existing judge to supersede is not mechanical |
| Merged-graph control, NVD ingestion | Plan 03 — both gated on the holdout |
| Demo deployment and screencast | Plan 03 |
| Deleting dead template methods | Plan 03 — behavioural change |
| Anything touching `ORCH_MAX_HOPS` in code, or the assess/replan loop | Plan 03 — deliberately not rehabilitated |
