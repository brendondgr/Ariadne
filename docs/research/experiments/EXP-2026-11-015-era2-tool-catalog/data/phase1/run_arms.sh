#!/bin/bash
# usage: run_arms.sh <outdir>
set -e
OUT=$1
cd /home/bdgr/Agents/Ariadne
export ORCH_MAX_HOPS=5
for b in 2026-08-19 2026-08-20; do
  uv run python -m utils.evaluation.experiment_untruncated --arm deterministic --bank docs/evaluation/banks/bank-$b/bank.json --root $OUT/bank${b//-/} --workers 8 > $OUT/log-det-$b.txt 2>&1
done
uv run python -m utils.evaluation.experiment_untruncated --arm generic_composed --bank docs/evaluation/composition/bank/bank-dev.json --root $OUT/dev --workers 8 > $OUT/log-gc-dev.txt 2>&1
echo DONE
