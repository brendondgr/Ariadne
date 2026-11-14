# Kill tests (EXP-2026-11-001..003)

Three small, pre-registered experiments, each with a numeric kill rule written before it ran:

| Test | Experiment | Question |
|---|---|---|
| T2 | `EXP-2026-11-001-t2-invariance-gate` | Can a system run every card-valid interpretation of a question, answer only when they agree, and ask otherwise, without asking too often or discarding the meant reading? |
| T3 | `EXP-2026-11-002-t3-synthetic-calibration` | Does an abstention threshold calibrated only on card-generated questions hold its target on real questions? |
| T1 | `EXP-2026-11-003-t1-free-query-gap` | How often do off-the-shelf models write correct Cypher and correct Gremlin for the same questions on unseen graphs? |

## Running

```bash
make killtests-start      # supervised background chain (logs/killtests-2026-11/)
make killtests-status     # GREEN / AMBER / RED / DONE, exit 0 / 1 / 2
make killtests-stop       # stop it; finished stages and items are kept
make killtests-test       # unit tests
uv run python -m utils.killtests.analysis all    # re-evaluate the kill rules
```

Prefix `KILLTESTS_SMOKE=1` to run the small smoke subsets into `logs/killtests-2026-11/smoke/`.

**Scheduled health call.**
- A systemd user timer, `ariadne-killtests-status.timer` (unit files in `~/.config/systemd/user/`),
  runs `make killtests-status` every two hours at :17 and appends to
  `logs/killtests-2026-11/timer.log`.
- A RED result is also appended to `ALERTS.md`.
- Once the run is DONE, remove the timer:
  `systemctl --user disable --now ariadne-killtests-status.timer`.

## What runs where

| Service | Used by |
|---|---|
| `:7500` decider (`pplx-decider-flash`, `choice` questions, temperature 1.0) | T2 anchor and facet scores; T3 anchor scores |
| `:9090` relay (served model recorded on every call) | T1 query writing; T3 rewording |
| `ariadne-neo4j` :5456 and `ariadne-gremlin` :6455 | T2/T3 execution (ATT&CK, CAPEC) |
| `killtests-neo4j` :5470 and `killtests-gremlin` :6470 (`docker/killtests/compose.yml`) | T1 only (CypherBench graphs) |

TinkerGraph is in memory. After a Gremlin container restart, reload:
- CAPEC: `uv run main.py --dataset capec --graph gremlin`;
- the T1 graphs: `uv run python -m utils.killtests.t1.load`.

The health call turns RED when either store is emptied.

## Layout

- **Shared:**
  - `stages.py`: resumable stages; a crash costs in-flight items.
  - `heartbeat.py`: the live progress file the health call reads.
  - `provenance.py`: served models, graph counts, commit.
  - `relay.py`, `decider.py`: the clients. `decider.py` documents the protocol.
  - `banks.py`, `candidates.py`, `graph.py`: the real question sets, anchor candidates, and
    exact facet execution.
- **Per test:**
  - `t2/`: interpretations, the gate, scoring.
  - `t3/`: generator, distance, calibrators (including SPI), evaluation.
  - `t1/`: loader and mirror proof, executor and normaliser, prompts, verified shots and
    hand-written Gremlin.
- **Driver scripts:**
  - `scripts/killtests_run.py`: the chain;
  - `scripts/killtests_supervise.sh`: keeps it alive;
  - `scripts/killtests_status.py`: the health call;
  - `scripts/killtests_ctl.py`: start and stop.
