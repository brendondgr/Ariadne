#!/bin/bash
# EXP-2026-11-022 Stage 3 re-run (PROTOCOL Amendment 1): core -> stop rule -> core+ext -> off-B, unattended.
# The superseded first core sitting is moved aside to phase-h/core-superseded-1 before this runs.
# The stop rule is checked against off-A after core; on a stop the chain halts and says why.
set -u
cd /home/bdgr/Agents/Ariadne
EXP=docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data
RUNS=docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h
P=$RUNS/progress.log
bash $EXP/phase_h.sh core
uv run python scripts/algebra_phase_h_score.py --runs $RUNS --stop-check core --out $RUNS/metrics-core-fixed.json > $RUNS/stop-check-core.txt 2>&1
if python3 -c "import json,sys; sys.exit(0 if json.load(open('$RUNS/metrics-core-fixed.json'))['stop_rule']['stop'] else 1)"; then
  echo "== CHAIN STOPPED: stop rule fired on the fixed core sitting $(date)" >> $P; exit 3
fi
echo "== stop rule passed on the fixed core sitting $(date)" >> $P
bash $EXP/phase_h.sh core+ext
bash $EXP/phase_h.sh off-B
uv run python scripts/algebra_phase_h_score.py --runs $RUNS --out $EXP/metrics.json > $RUNS/final-score.txt 2>&1
echo "== CHAIN DONE $(date)" >> $P
