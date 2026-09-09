# Data pointers — EXP-2026-09-013

No dataset. The inputs are twelve fixed question strings held in the probe
itself (`utils/tests/sse_gap_probe.py`, `QUESTIONS`). The outputs are the raw
stream logs under `logs/` in this directory, pinned by content hash. The table
below replaces the bullet list of 2026-09-07 (same five files, same digests,
now with repo-relative paths and byte counts so the validator can read and
re-verify them — RESULTS.md A-1).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Before, 12-way, per-event | `docs/research/experiments/EXP-2026-09-013-sse-stall-under-concurrency/logs/before-12way-events.log` | 13953 | `sha256:4a713e6a6cd3f9c1d4eb150a1a3e91720b12c5e5afb4a5488fc662add4da9079` | Every frame's arrival time per stream, pre-fix behaviour. The 5/12 and 429 s figures are parsed from this. |
| After, run 1, 12-way | `docs/research/experiments/EXP-2026-09-013-sse-stall-under-concurrency/logs/after-run1-12way.log` | 836 | `sha256:860f4e5c1482391d65482fb972d696907e449130e7e2bb74e3cba5b863c31b9b` | First post-fix probe; contains the 24-way outlier (run 7, 434.6 s). Its own summary line reads "1/12 runs exceeded … worst silence 434.6s". |
| After, run 2, 12-way | `docs/research/experiments/EXP-2026-09-013-sse-stall-under-concurrency/logs/after-run2-12way.log` | 831 | `sha256:f0ff9af50518b49a2848cddc761b70cd8fbba633f2031e3a241ff217111e02bb` | Clean 12-way post-fix probe — the headline figure (0/12, worst 10.0 s). |
| After, solo frame timings | `docs/research/experiments/EXP-2026-09-013-sse-stall-under-concurrency/logs/after-solo-frame-timings.log` | 1320 | `sha256:755aef5e28c34978d117660c1e87897603a00b3f72e4c2a1bce56e2bcad63bf4` | Every frame of one run, keep-alives included: 24 `: keepalive` comments at 10.00 s cadence across a 240 s planner stall. |
| Wedged worker | `docs/research/experiments/EXP-2026-09-013-sse-stall-under-concurrency/logs/wedged-worker-pyspy.txt` | 8365 | `sha256:f38510e3b932f859302de608605307ca62a34249c8483fe49f01480e475b9ea1` | py-spy thread dump of the deadlocked worker (secondary observation). |
| The instrument | `utils/tests/sse_gap_probe.py` | 6186 | `sha256:e58b924d6ba8e4bbc95d6f4abd7a7f177095884dd8d7bc63baf37135b332003e` | The probe, as committed in `31da134` (unchanged since). Uncommitted at run time (ISSUES.md). |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
