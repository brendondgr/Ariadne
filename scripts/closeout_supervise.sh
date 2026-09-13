#!/bin/bash
# Keep the close-out chain alive without a human attached.
#
# The chain already resumes at stage granularity, so re-running it is cheap and
# safe: completed stages are skipped and a killed stage costs only its in-flight
# requests. What was missing was anything to DO the re-running. This supervises
# rather than races: it waits for any live chain to exit before deciding whether
# to start another, so there is never more than one.
#
# Everything the chain touches is local (Neo4j, Gremlin, the model on :9090), so
# a dropped connection to this host does not interrupt the work — only the
# watching. This is the part that replaces the watching.
cd /home/bdgr/Agents/Ariadne || exit 1
LOG=logs/closeout-2026-09-12/supervisor.log
mkdir -p logs/closeout-2026-09-12
STAGES="control-generate control-judge control-score fresh-seal fresh-generate fresh-judge regression-generate regression-judge t6-rates latency"

done_yet() {
  python3 - "$STAGES" <<'PY'
import json, sys, pathlib
stages = sys.argv[1].split()
p = pathlib.Path("docs/evaluation/experiments/closeout-2026-09-12-state.json")
if not p.is_file():
    sys.exit(1)
state = json.loads(p.read_text())
sys.exit(0 if all((state.get(s) or {}).get("ok") for s in stages) else 1)
PY
}

for attempt in $(seq 1 60); do
  while pgrep -f "scripts/closeout_run.py" >/dev/null; do sleep 60; done
  if done_yet; then
    echo "$(date '+%F %T') all stages complete after $((attempt-1)) restart(s)" >> "$LOG"
    exit 0
  fi
  echo "$(date '+%F %T') chain not running and not complete — restart $attempt" >> "$LOG"
  uv run python scripts/closeout_run.py >> logs/closeout-2026-09-12/chain.out 2>&1
  # A stage that fails instantly would otherwise spin; back off before retrying.
  sleep 120
done
echo "$(date '+%F %T') gave up after 60 restarts — a stage is failing repeatedly" >> "$LOG"
