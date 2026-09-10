# ISSUES — EXP-2026-09-016

## I-1 — The `llm_query` arm answers with an empty query and no model call at all

**Found:** 2026-09-09, during setup, before any cost figure was recorded.

Invoked plainly —

```
uv run python -m utils.evaluation.experiment_untruncated --arm llm_query \
  --bank docs/evaluation/composition/bank/bank-dev.json --workers 4
```

— the arm completes 4 questions in **2.8 seconds**, returns **0 records** on
every one, and the token meter records **0 calls**. Nothing errors. The answer
artifact carries a plausible-looking abstention:

```
"The attack specialist failed and contributed no evidence:
 pre-run gate rejected all drafts: empty query"
```

which reads exactly like a model that had nothing to say, and is instead a model
that was never asked.

**Cause.** The served weights are a reasoning model. At the default 2048-token
budget it spends the whole allowance before emitting any query, the reply comes
back empty, and the gate rejects an empty draft. `scripts/holdout_run.py`
already carries the settled configuration that avoids this, and nothing outside
that script applies it:

| setting | plain invocation | settled |
|---|---|---|
| `--llm-max-tokens` | 2048 | 32768 |
| `SPECIALIST_LLM_TIMEOUT_S` | 30 | 4096 |
| `ORCH_MAX_HOPS` | 1 | 5 |
| `LLM_THINKING_BUDGET` | inherited from `.env` | explicitly unset |

**Why it is worth recording rather than just fixing.** This is the failure mode
that produces a *plausible wrong number* rather than a crash. An arm configured
this way finishes fast, writes a full set of artifacts, abstains politely, and
would be graded as a model that declined to answer 284 times. Any cost figure
taken from it would report the LLM path as **free and instant**, which is the
exact opposite of the truth and would have "confirmed" `C-012`'s cost half
spectacularly.

**Handled** by mirroring `holdout_run.py`'s configuration in this experiment's
driver, and by recording the plain invocation's behaviour here so the next
person to run this arm from the command line recognises what they are seeing.
The arm itself is not changed tonight: making the runner refuse to start when a
reasoning model is paired with a 2048-token budget is the right fix and it is a
behaviour change, so it is filed rather than slipped in beside a measurement.

## I-2 — The figure this experiment re-measures may not reproduce, and the setups differ

Written **before** this experiment's own number exists, so the comparison cannot
be arranged after the fact.

The October pitch plan names *"4 s vs ~2 days, about forty thousand times"* as
one of two numbers that must land in the room, sourced to
`docs/research/reports/2026-09-05-full-report.md`. That report describes the
`llm_query` side as having been **"split across two dedicated machines"**, and
`scripts/holdout_run.py` pins that arm at 16 workers — so roughly **32-way**
concurrency.

This experiment runs it at **24-way on one instance**: *less* parallel. Yet the
first 23 answers land at a median of 420 s each, a rate of about 110 questions
per hour, which projects the full 284 at **under three hours** rather than two
days.

Three things could explain that, and they are not equivalent:

1. The relay's read timeout was raised on 2026-09-09, on the operator's account.
   The earlier run's fourth attempt used a 68-minute cut-off *with retries*, and
   a retried question costs its budget more than once.
2. Serving throughput may simply differ between the two nights — which is `Q46`
   in another guise, and would mean a cost ratio is a figure with a date on it.
3. The two runs may not be measuring the same quantity. "Two days of machine
   time" is ambiguous between wall clock and summed per-question time; at 32-way
   those differ by a factor of 32.

**How this is handled.** The number reported here is the one measured here, with
its concurrency stated beside it, in both regimes. No attempt is made to
reconcile it with the earlier figure or to reproduce that figure's conditions.
If the ratio comes out materially below 40,000x, that is reported plainly and
the pitch is told before October rather than in the room.

## I-3 — 70 seconds of two-way contention at the start of the latency run

The original driver began its own 40-question latency step at 03:36:07. The
handoff that replaces it with the reduced 20-question sample killed the driver
*shell* at 03:36:34, which orphaned rather than stopped its Python child. Both
processes were briefly live and writing to the same root.

Caught at 03:37:47 and the orphan killed. **No answer file had been written by
either**, so nothing is contaminated — but the first question of the surviving
run was contended for roughly 70 s of its execution, and single-user latency is
precisely the number that contention corrupts.

Handled by reporting the first observation's wall clock separately and checking
it against the rest of the sample. If it is an outlier it is excluded and the
exclusion is stated with its `n`; if it is not, nothing is removed.

The underlying lesson is about `pkill` on a wrapper script: killing the shell
leaves the work running, and a measurement that had already started would have
been silently wrong rather than obviously broken.

## I-4 — The arm carrying `C-023` runs as a different arm at the default timeout

**The most consequential thing this experiment found.**

The `generic` arm is not model-free. Its env block in
`utils/evaluation/experiment_untruncated.py` sets `PLANNER_LLM_ENABLED`,
`SPECIALIST_LLM_ENABLED` and `SYNTHESIS_LLM_ENABLED` all true and turns on the
multi-hop loop; only the hand-written templates are disabled. `CLAIMS.md`
records this — `C-023` is `partial` partly because "the generic arm's narrator
calls a model".

Run it twice on the same 284 questions, changing only `SPECIALIST_LLM_TIMEOUT_S`:

| | default (30 s) | 4096 s |
|---|---|---|
| wall clock | **14.0 s** | **1,168.6 s** |
| successful model calls | **0** | **159** |
| tokens | 0 | 817,238 |
| answers carrying a fallback reason | **198 / 284** | 39 / 284 |

Eighty-three times slower, and a different system. The served weights are a
reasoning model; at 30 s **every** call times out, `LLMUnavailable` is raised,
the pipeline falls back to its deterministic path and finishes. No error
surfaces. The only trace is `fallback_reason` on two answers in three, a field
nobody reads unless they are looking for it.

This is the same failure class as `I-1` — a plausible wrong number rather than a
crash — but it lands on the arm that carries the project's headline comparison
rather than on its baseline.

### What it does and does not imply

It does **not** show that any published figure is wrong. `EXP-2026-09-010`
established that this arm's narrator does call a model, so at least that run was
configured well. `scripts/holdout_run.py` passes `SPECIALIST_LLM_TIMEOUT_S=4096`
— but **only inside `if arm == "llm_query"`**, so a `generic` run through that
same script inherits whatever the environment holds.

What it does show is that the arm's identity depends on a variable that neither
the CLI, the arm definition, nor the shared runner sets, and that getting it
wrong is silent. Every `generic` figure in this repository should be checkable
against the `fallback_reason` rate of its own saved answers, which is a cheap
audit and has never been run.

Filed as `Q47`.

### Handled here

Every arm in `A-1` ran at `SPECIALIST_LLM_TIMEOUT_S=4096`. The 30 s run is kept
as the second column above rather than deleted, because it is the finding. The
`generic` latency cell is dropped rather than reported, because it ran before
this was understood and does not match its own throughput cell.
