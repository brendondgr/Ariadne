#!/bin/bash
# Written-id guard smoke: 22 variant items (10 targets, 12 controls) and 15 dev items (5 targets, 10 controls).
set -u
cd /home/bdgr/Agents/Ariadne
S=/tmp/claude-1000/-home-bdgr-Agents-Ariadne/e287aee2-08ba-47b4-b868-f26f2b870fe3/scratchpad/wid-smoke
export ORCH_MAX_HOPS=5
B=docs/evaluation/composition/bank/bank-dev.json
P=$S/progress.log
git rev-parse HEAD > $S/TREE; git diff --stat > $S/DIFFSTAT
wait_relay() { for i in $(seq 1 120); do curl -sf localhost:9090/v1/models >/dev/null && return 0; sleep 5; done; echo "RELAY DOWN $(date)" >> $P; return 1; }
var() { local a=$1; wait_relay
  uv run python scripts/variant_harness.py compare --out $S --arm $a --no-gold --workers 11 > $S/var-$a.log 2>&1; echo "var $a rc=$? $(date)" >> $P
  uv run python scripts/era2_modelless.py $S/$a.json >> $P 2>&1; }
dev() { local a=$1 root=$2; shift 2; wait_relay
  uv run python -m utils.evaluation.experiment_untruncated --arm $a --bank $B --root $root --workers 15 --only "$(cat $S/dev_ids.txt)" "$@" > $S/dev-$a-$(basename $root).log 2>&1; echo "dev $a $(basename $root) rc=$? $(date)" >> $P
  uv run python scripts/era2_modelless.py $root/$a >> $P 2>&1; }
( var T-lazy; dev planned_llm_typed_lazy $S/dev; dev planned_llm_typed_full $S/dev ) &
( var T-lazy-G; dev planned_llm_typed_lazy $S/dev-gemma --model gemma4-31b ) &
wait
echo "DONE $(date)" >> $P
