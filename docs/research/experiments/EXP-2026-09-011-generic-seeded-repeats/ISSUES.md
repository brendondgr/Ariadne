# ISSUES — EXP-2026-09-011

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

## 2026-09-09 — `code.dirty: true`: the judge was edited between and during its sessions
**Impact:** provenance only.
**Cause:** `code.commit` is `4eb9b91` (2026-09-06 20:37, EXP-2026-09-008's
write-up). Generation ran 2026-09-07 00:13–03:31 under
`scripts/seeded_repeats.py` as of `bc95277`/`1de8b53`. The pre-registered
grading (00:59–02:47) ran under `scripts/seeded_repeats_judge.py` while
`5cec72a` (00:44), `1652dd9` (01:10) and `b693676` (01:12) were being
committed to it — the last of which "released default-model" mid-session,
which is why the pre-registered blocks ran on `default-model-2/-3/-4`. The
extension grading (10:15–13:00) ran after `228a700` (10:02) and `768ef08`
(10:34) changed the endpoint set again.
**Resolution:** `dirty: true` kept; the code that produced the numbers is a
moving set of commits on 2026-09-07, not `4eb9b91`.
**Paper implication:** none.

## 2026-09-09 — two script defects found while launching the extension (PROTOCOL A-1)
**Impact:** none on any reported number; both would have produced a silent
no-op rather than a wrong figure.
**Cause:** `seeded_repeats_judge.py` hard-coded the pre-registered seed list,
so a run launched for the extension would have exited reporting success
having graded nothing; `answers_present()` globbed `*.json` and counted
judgment sidecars as answers, so the short-seed guard could never fire.
**Resolution:** fixed at `228a700` (`--seeds preregistered|extension`; count
answer files only) before the extension was graded.
**Paper implication:** none.

## 2026-09-09 — 283 stale `*.judgment.q1.error.txt` files on seed 1729
**Impact:** none; all 284 `.q1` judgments exist and `n: 284` is what grades.
`data/judge-state.json` `errors: 283` counts these leftovers.
**Cause:** the first `.q1` attempt on seed 1729 hit HTTP 502 on a dead alias
and was retried to completion (RESULTS A-3).
**Resolution:** left on disk; noted in `data/POINTERS.md`.
**Paper implication:** none.

## 2026-09-09 — the two seed sets were graded in separate sessions
**Impact:** a session effect cannot be separated from seed variance in the
six-seed SD; the extension trio's higher internal SD (0.0097) is consistent
with either (RESULTS A-1 Limits).
**Cause:** the extension's grading was not queued behind its generation and
the endpoints were down when it was started at 09:57 (PROTOCOL A-1 Status).
**Resolution:** not resolved; six seeds in one session were not run.
**Paper implication:** quote 0.0074 with this caveat.

## 2026-09-09 — the manifest carried the withdrawn three-seed SD as primary
See RESULTS A-2: `balanced_across_seed_sd` 0.0039 moved to
`metrics.withdrawn`, `primary` → `six_seed_balanced_sd`, and every scaffold
field filled (old → new listed there).
