# Issues — EXP-2026-09-019

## I-1 — "model-free" was a declaration, not a fact (resolved)

`iter_pipeline` applies its `use_llm` argument as
`dataclasses.replace(PlannerConfig.from_env(), llm_enabled=use_llm)`, and does
the same to the specialist and synthesis configs. That **overwrites** the
env-resolved value, so an arm pinning `PLANNER_LLM_ENABLED=false`,
`SPECIALIST_LLM_ENABLED=false` and `SYNTHESIS_LLM_ENABLED=false` still ran every
seam live against `ARIADNE_LLM_BASE_URL`.

`generic_planned` was wired to `run_rewrite`, which passes `use_llm=True`, and
so ran LLM-planned against `:9090` / `qwen38-27B-v2` while its own environment
said it had no model. Caught by patching `socket.socket.connect` for a single
question: the planner's `OpenAICompatibleDrafter` opened a connection to the
configured endpoint. Wall clock agreed — 89 to 241 seconds a question, against
0.16 once the posture was corrected.

Resolved by making the posture a parameter at the call site:
`_run_real_pipeline(..., use_llm=...)`, with `run_planned` (False) for this arm.
`run_meta` also stopped hardcoding `"planner": "deterministic"` regardless of
what ran. Locked by `utils/evaluation/tests/test_experiment_arms.py`.

## I-2 — the planner's limits travel with its plan (open)

`generic_planned`'s difference is attributed to "the plan" in the headline, but
the planner emits its own per-sub-question limits — observed plans carry
`max_result_rows: 1000` and `max_traversal_depth: 3` — where the gold-replay
path inherits the lifted bounds via `lift_task_limits`. Some share of the
−0.3814 may be the tighter limits rather than a worse decomposition. Separating
them needs a third arm holding the planner's decomposition and lifting its
limits. Not run.

## I-3 — `rewrite_off` and `rewrite_det` are affected by I-1 (open, not this experiment's to fix)

The same defect applies to EXP-2026-09-014's arms: their env pins every seam
`false` and their comment says "no language model anywhere", but they go through
`run_rewrite` and therefore ran with live seams. `run_rewrite` was deliberately
left at `use_llm=True` here, because those figures are published and changing
the posture would silently re-describe them. Whether they meant to be model-free
is a question for an amendment to that experiment, not a silent edit from this
one.

## I-4 — a pre-existing unrelated test failure

`utils/specialists/evalset/tests/test_variant_scoring.py::test_every_rewrite_mode_states_both_flags`
fails on `ARIADNE_REWRITE_DERIVE_RELATION` being an extra key in `REWRITE_ENV`.
Confirmed pre-existing: it fails with this experiment's changes stashed out.
Not touched.

## I-5 — Steps 3–5 not run

The 2B seams and the 2×2 are outstanding. The endpoint they will use is
characterised (`data/endpoint.json`) and its chosen concurrency is 4.

## I-6 — seeds not recorded

`seeds: []` in the manifest. Both Step 2 arms are model-free and deterministic,
so there is nothing to seed; this will stop being true at Step 3.

## I-7 — `make validate-research` is red repo-wide, from before this experiment

Three `pointer-hash-mismatch` rows fail the whole-record validation:
`EXP-2026-09-001/data/POINTERS.md` (`scripts/prepare_briefs.py`),
`EXP-2026-09-007/data/POINTERS.md` (`utils/evaluation/judge_answers.py`) and
`EXP-2026-09-012/data/POINTERS.md` (`docs/evaluation/experiments`). All three
were verified to fail with this experiment's run root moved out of the tree, so
none is caused by it. The third's hash *also* moves whenever anything is written
under `docs/evaluation/experiments`, which this experiment does — but it was
already stale beforehand. This experiment's own folder validates.

## I-8 — 11 of 284 claim *texts* differed because main moved mid-run (resolved)

At n=284 the claim-identity gate reported 273 of 284 identical. The 11 that
differed did so in `text` and in nothing else: zero differences in `entity_ids`,
zero in `citations`, zero in `verdict`, and zero new unsupported verdicts
anywhere in the run.

**The cause was the tree changing underneath the comparison, not the narrator
and not load.** A concurrent session committed `1f507002` — "I-20: name the
edge, not the label" — at 17:30:38, which adds `DETECTS` to `_REL_NOUNS` in
`utils/synthesis/composer.py` so the noun stops falling through to the
neighbour's LABEL. The two arms straddled it:

| Arm | Process started | Answers written | Code it held |
| --- | --- | --- | --- |
| `generic_local_narrator` | 16:56 | 16:58:34 – 18:47:42 | pre-fix, imported before 17:30 |
| `generic_narrator_off` | 18:47 | 18:47:44 – 18:47:46 | post-fix |

A running process keeps the module it imported, so the treatment arm rendered
its whole 284 with the old noun table while its control, started afterwards,
used the new one. Every one of the 11 affected cases is a `DETECTS`-family edge
— `AN0662`, `AN1955`, `AN0749`, `AN1112`, `DET0130`, `DET0189`, `DET0891`,
`DET0285`, `DET0181` — and `AN0749` is the case named in that commit's own
message.

Confirmed twice. First over exactly those 11 cases on one code version: 11 of
11 byte-identical. Then over the **whole bank** — the authored-plan/2B cell was
regenerated into the `twobytwo` root on the current tree before the judged pass,
giving **284 of 284 claims byte-identical**, fallback rate 0.0282, 0 new
unsupported. The earlier one-worker checks agreed for the same reason: both
sides were post-fix by then.

Every 2x2 figure reproduced exactly across that regeneration — coverage 0.8611
and 0.4797, plan effect -0.3814 and -0.3787, model effect +0.0000 and +0.0026,
interaction +0.0027 — so the straddle never touched a reported number. Only the
wall clock moved, 93.527 s to 80.988 s an answer, which is contention and not
the model.

**What this means for Step 3's result.** It strengthens it. The narrator changed
*nothing*: the claim-identity figure would have been 284 of 284 had both arms
run on one tree, and the structured fields were identical even across the two
trees. The wall-clock and fallback figures are unaffected — they do not depend
on the noun table.

The operational lesson is the one `memory: ariadne-concurrent-sessions` already
records and this experiment did not act on: main moves while you work, and a
treatment and its control must be run from one tree. Both arms should have been
run back to back, or the commit pinned, rather than 110 minutes apart.

## I-9 — the specialist seam is not viable at 2B (Step 4 result, not a failure)

On the nine-question gate, `generic_local_full` returned **zero records on 9 of
9 questions** where the model-free control returned records on 9 of 9, and every
one of the nine queries differed from the control's. Counted at the level that matters — drafts submitted to
the gate, not questions — the seam produced **0 working queries out of 17**.

| | 4096-token budget | 16384-token budget |
| --- | ---: | ---: |
| Drafts reaching the gate | 17 | 16 |
| Rejected as empty | 11 | 8 |
| Rejection rate | 0.6471 | 0.5000 |
| Cleared the gate, then failed at the database | 6 of 6 | 8 of 8 |
| **Drafts that actually worked** | **0 of 17** | **0 of 16** |

Quadrupling the token budget is therefore not the missing ingredient, and this
is the reason the budget was made a call-time override rather than a constant:
the claim "a 2B cannot draft these queries" is only worth having if it was
tested. What the larger budget bought was a shift in *failure mode*, not in
outcome — fewer drafts truncated into nothing, and correspondingly more
malformed drafts reaching the database and erroring there.

The empty drafts are the model rambling rather than a context limit: the prompts
are ~870 tokens and the model spends the entire completion budget without
closing a query.

No rejection named `allowed_edge_patterns`. That is worth stating plainly
because the plan expected the allowlist gate to be what stopped a bad draft.
Instead the drafts were empty, and those that were not empty **reached the live
graph engines and failed there** — Gremlin `597: No such property: params`,
Gremlin `499: ... invalid parameters key of [[id]] - these are reserved names`,
and Neo4j `ParameterMissing`. Malformed model-written queries executing against
the database rather than being refused before it is a gate finding in its own
right, and it is not specific to a small model.

The plan's rule is that above a 25% rejection rate this seam is not viable at 2B
and the step records that rather than widening. The observed figure is a total
retrieval failure, so the full 284-question pass was not run.

## I-10 — the sidecar-exclusion this file claimed was never implemented

**What happened.** `data/POINTERS.md` stated that its directory hashes were
taken "judgment sidecars excluded". They were not. `sha256_tree` folds in every
file under the root and has no exclusion of any kind. The three `twobytwo`
answer directories were hashed before they had been graded, so the claim
happened to describe the numbers — until a judged pass wrote sidecars into them
and all three rows broke at once.

**Why the tool is right and the sentence was wrong.** Auditing all 34 directory
pointers on record: **30 match only with sidecars included**, 3 match only
without (these three, hashed pre-judging), and 1 matches neither. Changing
`sha256_tree` to implement the documented exclusion would therefore invalidate
30 correct rows across nine experiments to rescue 3. The prose has been
corrected to describe what the tool does.

**What this does not change.** No number in `RESULTS.md` moves. The answers
themselves were never touched — which is exactly what the audit shows, since
these three directories hash correctly under the sidecar-free rule, meaning
their answer payloads are byte-identical to when the figures were computed.

**Resolution.** Prose corrected; the three rows re-hashed against the graded
directories, with the answer count kept in the Files column so a reader can see
284 answers where the directory now holds 568 files. The general lesson is
recorded rather than smoothed over: **a pointer to a directory that will later
be graded is a pointer to a moving target**, and the fix is either to hash a
manifest of answer payloads or to accept that grading re-hashes the row.

**Paper implication:** none for any figure. It belongs in the account of how the
record checks itself: the check that failed here was a check whose description
and whose behaviour had drifted apart, which is the same class of defect as the
composer's scope line in `EXP-2026-09-018` — a statement asserted from what was
intended rather than from what was done.

## I-10 — the narrator runs after the verifier, so its prose is unchecked (open)

`utils/orchestration/agents/synthesis/graph.py` wires `compose -> verify ->
narrate`. The verifier therefore grounds the *claims* and never sees the
narrative, which is the only part of the answer a language model writes.

Measured two ways and they agree. Directly on the prose: 5 of 284 narratives
name an identifier absent from the verified claims — `TA2541`, and a parent
technique `T1027` where the evidence held only `T1027.006`. Not fabricated
nonsense; real ATT&CK knowledge the model brought from outside the graph, which
in a system whose premise is graph-provenance is a violation regardless of
whether it happens to be true. And from the grader: adding the narrator roughly
doubles flagged hallucinations (0.1743
to 0.3609 per judgment on the
authored plan) and lowers both faithfulness
(0.9523 to 0.9355)
and groundedness (0.956 to
0.9484).

The remedy is structural and small: the grounding predicate already exists and
already runs. Moving it, or a copy of it, after `narrate` would have caught all
five. Not done here — this experiment measures model size and a change to the
synthesis graph would move every recorded arm.
