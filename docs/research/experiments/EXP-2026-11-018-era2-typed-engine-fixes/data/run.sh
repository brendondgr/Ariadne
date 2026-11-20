#!/bin/bash
# EXP-2026-11-018 (typed engine fixes), on one commit. R first; then the Qwen chain and the Gemma chain in parallel.
# Differences from EXP-2026-11-017's run.sh (its ISSUES): every arm attempt waits for the :9090 relay first,
# so a tunnel restart cannot fail an arm at its first call.
set -u
cd /home/bdgr/Agents/Ariadne
EXP=docs/research/experiments/EXP-2026-11-018-era2-typed-engine-fixes; L=$EXP/logs; RUNS=docs/evaluation/experiments/typed-engine-fixes-2026-11-20
mkdir -p $RUNS/variants $L; export ORCH_MAX_HOPS=5
B=docs/evaluation/composition/bank/bank-dev.json
P=$L/progress.log
git rev-parse HEAD > $L/TREE; git status --short | grep -v '^?? \.\./' > $L/STATUS
uv run main.py --dataset attack --graph verify > $L/verify.log 2>&1 && uv run main.py --dataset capec --graph verify >> $L/verify.log 2>&1 || { echo "STORES FAILED $(date)" >> $P; exit 1; }
cp docs/evaluation/variants-2026-09-15/variants.json $RUNS/variants/variants.json

uv run python scripts/variant_harness.py capture --out $RUNS/variants --name reference.json --workers 8 > $L/R-capture1.log 2>&1; rc=$?; echo "R capture1 rc=$rc $(date)" >> $P
uv run python scripts/variant_harness.py capture --out $RUNS/variants --name reference_check.json --workers 8 > $L/R-capture2.log 2>&1; rc=$?; echo "R capture2 rc=$rc $(date)" >> $P
cmp $RUNS/variants/reference.json $RUNS/variants/reference_check.json > $L/R-cmp.log 2>&1 && echo IDENTICAL >> $L/R-cmp.log || echo DIFFER >> $L/R-cmp.log
uv run python scripts/variant_harness.py compare --out $RUNS/variants --name R.json --workers 8 > $L/R-compare.log 2>&1; rc=$?; echo "R compare rc=$rc $(date)" >> $P

# wait_relay: up to 10 minutes for the :9090 relay (systemd restarts the tunnel in about 20 s)
wait_relay() { for i in $(seq 1 120); do curl -sf localhost:9090/v1/models >/dev/null && return 0; sleep 5; done; echo "RELAY DOWN $(date)" >> $P; return 1; }
# var <arm> [extra args]: one variant arm, H1-checked, re-run once on a relay drop
var() {
  local a=$1; shift
  for attempt in 1 2; do
    wait_relay
    uv run python scripts/variant_harness.py compare --out $RUNS/variants --arm $a --workers 16 "$@" > $L/var-$a.$attempt.log 2>&1; rc=$?
    uv run python scripts/era2_modelless.py $RUNS/variants/$a.json >> $L/H1.log 2>&1; h=$?
    echo "var $a attempt=$attempt rc=$rc H1=$h $(date)" >> $P
    [ $h -eq 0 ] && return 0
    mv $RUNS/variants/$a.json $L/dropped-var-$a.$attempt.json
  done
}
# dev <arm> <root> [extra args]: one dev arm, H1-checked, re-run once on a relay drop
dev() {
  local a=$1 root=$2; shift 2
  for attempt in 1 2; do
    wait_relay
    uv run python -m utils.evaluation.experiment_untruncated --arm $a --bank $B --root $root --workers 16 "$@" > $L/dev-$a-$(basename $root).$attempt.log 2>&1; rc=$?
    uv run python scripts/era2_modelless.py $root/$a >> $L/H1.log 2>&1; h=$?
    echo "dev $a ($(basename $root)) attempt=$attempt rc=$rc H1=$h $(date)" >> $P
    [ $h -eq 0 ] && return 0
    mv $root/$a $L/dropped-dev-$(basename $root)-$a.$attempt
  done
}

(
 for a in E T-lazy T-full; do var $a; done
 for a in planned_llm_english planned_llm_typed_lazy planned_llm_typed_full; do dev $a $RUNS/dev; done
) &
(
 var T-lazy-G
 dev planned_llm_typed_lazy $RUNS/dev-gemma --model gemma4-31b
) &
wait
echo "ALL DONE $(date)" >> $P
