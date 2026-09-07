# Results — SSE silence under concurrency

## Headline

**Every run succeeded on the server. Five of twelve would still have died in the
browser.** That sentence is the finding; the fix follows from it.

| | before (`4747f15`) | after (`84936c3`) |
| --- | --- | --- |
| runs completing server-side | 12 / 12 | 12 / 12 |
| runs exceeding the 90 s client stall budget | **5 / 12 (42%)** | **0 / 12** (twice) |
| worst socket silence | **429 s** | **10.0 s** |

42% matches the operator's "half the time" almost exactly.

## Before — where the silence was

Longest gap per run, and the frame it followed (`logs/before-12way-events.log`):

| run | longest silence | after | verdict |
| --- | --- | --- | --- |
| 7 | 429 s | `specialist` | cancelled |
| 4 | 240 s | `status(planning)` | cancelled |
| 6 | 114 s | `status(answering)` | cancelled |
| 0 | 111 s | `status(planning)` | cancelled |
| 1 | 93 s | `status(answering)` | cancelled |
| 9 | 87 s | `status(planning)` | survived, barely |
| 8 | 73 s | `status(answering)` | survived |
| 2, 3, 10, 11 | 41–54 s | `status(planning)` | survived |
| 5 | 14 s | `status(planning)` | survived |

Every single longest-gap sits immediately after a status frame that announces an
LLM stage. `status(planning)` — the line the operator reported the ticker
stopping on — accounts for the largest group.

## After — two runs at the same concurrency

`logs/after-run2-12way.log`, a clean 12-way run:

```
0/12 runs exceeded the client's 90s stall budget; worst silence 10.0s
```

Every one of the twelve reports a longest silence of exactly 10.0 s: the
heartbeat interval, hit precisely, which is what a keep-alive on a timer should
look like. Total run times were unchanged (142–335 s) — the fix does not make
the pipeline faster, it makes a slow pipeline *legible*.

A solo trace of the worst question (`logs/after-solo-frame-timings.log`) shows
the mechanism directly: 23 keep-alives at a 10.00 s cadence spanning a 240 s
planner stall, then the terminal events. Zero gaps over 10.5 s.

## The one outlier, kept

`logs/after-run1-12way.log` shows run 7 with a 434 s silence. That probe was
started while the tail of a previous 12-way probe was still in flight — roughly
24 concurrent streams against an 8-worker API. It did not reproduce in the clean
run. It is recorded rather than dropped because it marks the honest limit of
what was tested: the heartbeat is verified at 12-way concurrency, not at 24.

## Secondary observation — a wedged worker

Separately from the timing measurement, `logs/wedged-worker-pyspy.txt` captures
a worker that had stopped serving entirely. One thread sits inside `exec_module`
for `utils.specialists.cypher.specialist`, holding that module's import lock; a
second is blocked in `_lock_unlock_module` inside `build_specialist` and never
returns. Every later query joined the queue and `/api/health` stopped answering
too. This is a different failure from the stall — it needs a restart, not a
reload — and is what the startup warm-up in `api/main.py` removes.

The trigger for the *first* thread's stall is not established from a single
`py-spy` dump; the spliced frames make it unprovable. See ISSUES.md.
