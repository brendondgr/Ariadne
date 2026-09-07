# Issues — SSE silence under concurrency

## `dirty: true` at run time

`utils/tests/sse_gap_probe.py` — the instrument itself — was uncommitted when
the "after" runs were taken; it was committed immediately afterwards, unchanged.
The pipeline code under measurement was at `84936c3` and clean.

## Seeds recorded as `[]`

The pipeline pins `LLM_SEED=1729` for every graded call, so sampling is as fixed
as the serving stack allows. But the quantity measured here is **wall-clock
silence on a shared relay under concurrent load**, and no seed controls that.
Recording a seed list would imply a reproducibility this measurement does not
have. The manifest's `nondeterminism_note` says the same thing.

## One "before" run only

The before condition was measured once, at 12-way concurrency. Re-running it
would have meant reverting the fix on a machine the operator was using. The
effect size (5/12 vs 0/12, 429 s vs 10.0 s) is far outside anything a second
sample would move, and the *mechanism* — no bytes are written during an LLM
stage — is visible in the code rather than inferred from the numbers.

## The 24-way outlier is not explained

Run 7 of `after-run1` shows a 434 s silence while roughly 24 streams were in
flight. The heartbeat producer is an ordinary daemon thread feeding a queue, and
the consumer is pulled by Starlette's threadpool, so the plausible explanation is
that the stream's `next()` was not scheduled — but that was not confirmed with a
thread dump before the run ended. Recorded as a known limit, not a diagnosis.

## The import-lock trigger is unproven

`logs/wedged-worker-pyspy.txt` shows the lock *holder* blocked in LangGraph's
`BackgroundExecutor.__exit__`, but py-spy spliced generator frames into that
stack (it shows `stream_conversation_events` called from `dataclasses.__set_name__`,
which cannot happen), so the precise trigger cannot be read off it. The fix does
not depend on knowing it: importing both backends at startup means no request
thread takes that lock at all, so the cycle cannot form regardless of what
started it. Chasing the trigger was deliberately not done.

## Not linked to any claim

`supports_claims: []` is correct and not an omission. This is an engineering
measurement of the web layer. It says nothing about federated retrieval quality
and must not be cited as if it did.
