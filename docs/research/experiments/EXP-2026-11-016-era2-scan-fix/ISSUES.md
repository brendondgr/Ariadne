# ISSUES — EXP-2026-11-016

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

<!-- Entry template — newest first:

## YYYY-MM-DD — <one-line summary>
**Impact:** what this changes about the reported numbers (e.g. "seed 3 excluded; n=4 not 5 for this cell").
**Cause:** the mechanism, if known.
**Resolution:** what was done. "Not resolved" is a valid answer.
**Paper implication:** what must be stated in the paper because of this.

-->

## 2026-11-19 — scoreboard title was hardcoded to EXP-2026-11-015
**Impact:** none on any number. `tables/scoreboard.md` was first generated with the wrong heading.
**Cause:** `scripts/era2_catalog_score.py` wrote a fixed title.
**Resolution:** after the run, the title is taken from the data directory's experiment id.
EXP-2026-11-015's scoreboard regenerates with identical values. Its arm rows come out in a
different order, so its committed file was left as it was. This is a scoring script, not code
the run measured.
**Paper implication:** none.

## 2026-11-19 — two tunnel drops made three arms answer mostly without a model; the harness did not notice
**Impact:** the following were discarded and re-run on the same commit:
- **dev T-full, attempt 2:** 135 of 284 answers reported "could not reach localhost:9090";
- **variant E, attempt 3:** 510 of 699 rows planned by `DeterministicDrafter`;
- **variant T-lazy-G, attempt 3:** 522 of 699 rows, the same way.

Kept arms have 1–12 such rows, against 2–9 in EXP-2026-11-015.
**Cause:** the :9090 relay is an SSH forward to skynet (`synapse-tunnel.service`). It dropped at
10:58:48 and again at 11:02:51, each time for about a minute. Arms running then failed each
question in about a second and drained most of the queue during the outage. Each arm's identity
check runs only before and after the arm, and both passed. The English path records no error
field when it falls back, so only the planner's `drafter` field and response time show it.
**Resolution:** each affected arm was re-run whole, and the drafter counts were checked for
every kept arm. The invalid outputs are kept under `logs/attempt2-dev-typed_full/` and
`logs/attempt3/` (gitignored). **Not resolved in code:** the harness should count failed model
calls per arm and fail the arm above a threshold. It was not changed mid-experiment, to keep one
commit.
**Paper implication:** any harness figure needs a per-arm model-less count beside it. A
before-and-after identity check is not enough.

## 2026-11-19 — attempt 2's variant arms crashed: the run script never placed variants.json
**Impact:** R compare and all four variant arms failed within a second in attempt 2. The dev
arms were unaffected.
**Cause:** `data/run.sh` copies EXP-2026-11-015's `logs/phase2.sh`, which assumes
`<runs>/variants/variants.json` already exists. In EXP-2026-11-015 it was copied by hand and not
scripted. The progress log reported `rc=0` for every arm because `echo "... $(date) rc=$?"`
reads `$?` after `$(date)` has reset it. EXP-2026-11-015's `phase2.sh` has the same bug; its
outputs were checked separately (identity files, row counts, fallbacks), so its results stand.
**Resolution:** `logs/rerun.sh` (attempt 3) copies `docs/evaluation/variants-2026-09-15/variants.json`
(sha256:428a2346…, the manifest's data hash) and records `rc` before `$(date)`. `logs/rerun4.sh`
(attempt 4) re-ran variant E and T-lazy-G. Both scripts are kept in gitignored `logs/`, so the
tracked tree stayed clean. `data/run.sh` is left as committed with the protocol.
**Paper implication:** none.

## 2026-11-19 — attempt 1 aborted at the store check: the pre-run test suite rewrote the graph manifests
**Impact:** no measured call was made at 01:12. The run was relaunched at 10:27 on the same commit.
**Cause:** the PROTOCOL procedure runs `pytest` before the chain. Several kg_builder and loader
tests write into the real `data/graphs/`:
- they rebuilt both canonical manifests (new build timestamps);
- they rewrote the runtime load manifests (CAPEC's endpoint became `memory://local`).

`--graph verify` then saw a canonical-hash mismatch. Content was unchanged: node and edge
counts were exact, and `nodes.jsonl` hashes 371147e2… (ATT&CK) and 2deb6d93… (CAPEC), as recorded
since EXP-2026-08-017.
**Resolution:** reloaded ATT&CK into Neo4j and CAPEC into Gremlin (both are upsert-only), and
verify passed. Logs: `logs/attempt1-*`.
**Paper implication:** none. Future protocols run the suite before reloading the stores, not
between reloading and running.
