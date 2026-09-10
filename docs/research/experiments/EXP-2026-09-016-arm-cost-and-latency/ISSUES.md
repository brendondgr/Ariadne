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
