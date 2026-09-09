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

---

## AMENDMENT A-1 (2026-09-09) — the after-condition aggregates excluded after-run1, and four smaller corrections

**What was wrong.** The headline table (lines 11–12) reports the after
condition as "**0 / 12** (twice)" and worst silence "**10.0 s**", and
`manifest.yaml` recorded `runs_exceeding_client_stall_budget_after: {mean:
0.0, n: 2}` and `worst_socket_silence_s_after: {mean: 10.0, n: 2}`. But
`logs/after-run1-12way.log` — one of the two pointed after-runs — ends
"**1/12 runs exceeded the client's 90s stall budget; worst silence 434.6s**"
(run 7, the ~24-way outlier that §"The one outlier, kept" discloses). An
`n: 2` mean that excludes one of its two runs is not a mean of two runs: the
honest n=2 values are **0.5 runs** and **222.3 s**, and the honest headline
is the clean run alone at n=1.

**Manifest corrections (old → new).** The two `*_after` keys were replaced by
keys whose names state what they cover:

| key | was | is |
|---|---|---|
| `runs_exceeding_client_stall_budget_after` | `{mean: 0.0, n: 2}` | removed |
| `runs_exceeding_client_stall_budget_after_clean12way` | — | `{mean: 0.0, n: 1}` (after-run2) |
| `runs_exceeding_client_stall_budget_after_run1_overlapped24way` | — | `{mean: 1.0, n: 1}` (after-run1, run 7) |
| `runs_exceeding_client_stall_budget_after_both_runs` | — | `{mean: 0.5, std: 0.5, n: 2}` |
| `worst_socket_silence_s_after` | `{mean: 10.0, n: 2}` | removed |
| `worst_socket_silence_s_after_clean12way` | — | `{mean: 10.0, n: 1}` |
| `worst_socket_silence_s_after_run1_overlapped24way` | — | `{mean: 434.6, n: 1}` |
| `worst_socket_silence_s_after_both_runs` | — | `{mean: 222.3, std: 212.3, n: 2}` |
| `runs_completing_server_side_after` | — | `{mean: 12.0, n: 2}` (both after logs: 12/12 OK) |
| `metrics.primary` | `runs_exceeding_client_stall_budget` (not a key) | `runs_exceeding_client_stall_budget_after_clean12way` |

The headline table's "(twice)" is left as written; it should be read as "0/12
in the clean 12-way run; 1/12 in the run that overlapped a previous probe",
exactly as lines 53–59 already say. The conclusion — the heartbeat removes all
> 90 s silences at 12-way concurrency and is verified at 12-way, not at 24 —
is unchanged; the outlier is now visible in the machine-readable record and
not only in prose.

**Four smaller corrections, from re-reading the logs.**

1. `data.version` said `sse_gap_probe.py @ 84936c3`. `84936c3` does not
   contain the probe; it was first committed in `31da134` (2026-09-07 17:15),
   as ISSUES.md already says. Manifest corrected to name `31da134` and the
   fact that the probe was uncommitted at run time.
2. Line 51 says the solo trace shows "23 keep-alives at a 10.00 s cadence".
   `logs/after-solo-frame-timings.log` has **24** `: keepalive` frames
   (10.04 s … 240.05 s). Prose left as written.
3. Line 29 groups run 3 under "41–54 s". Parsing
   `logs/before-12way-events.log` per stream, run 3's longest gap is
   **39.9 s** (runs 2, 10, 11 are 54.4, 41.1, 42.8). Every other row of that
   table — 428.7 / 240.1 / 114.3 / 111.2 / 93.2 / 86.9 / 73.0 / 13.9 s, and
   the frame each gap followed — reproduces exactly (verify-b6, `r013.py`),
   as do 5/12 over 90 s and the worst 429 s.
4. `data/POINTERS.md` listed the five logs as a bullet list with paths
   relative to the experiment directory, which the validator reads as an
   empty table. It is now the standard table with repo-relative paths, the
   same five digests (all re-verified on 2026-09-09), byte counts, and a row
   for the probe itself.

**Metrics file.** `data/metrics.json` created with every `metrics.values`
entry, the per-run longest silences of the before condition, both after-run
summaries and the solo-trace counts.
