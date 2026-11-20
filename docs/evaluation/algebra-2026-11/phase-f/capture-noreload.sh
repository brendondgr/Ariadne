#!/bin/bash
# Capture today's answers on freshly reloaded measured stores. Usage: capture.sh <label> (before|after)
set -u
cd ${WT:-/home/bdgr/Agents/Ariadne}
S=/tmp/claude-1000/-home-bdgr-Agents-Ariadne/e287aee2-08ba-47b4-b868-f26f2b870fe3/scratchpad/storefix
L=$1; O=$S/$L; mkdir -p $O; P=$O/progress.log
export ORCH_MAX_HOPS=5; PY=/home/bdgr/Agents/Ariadne/.venv/bin/python
git rev-parse HEAD > $O/TREE; git status --short | grep -v '^?? \.\./' > $O/STATUS
echo "no reload (Phase F)" >> $P
echo "reloaded $(date)" >> $P
true
mkdir -p $O/variants; cp docs/evaluation/variants-2026-09-15/variants.json $O/variants/variants.json
$PY scripts/variant_harness.py capture --out $O/variants --name reference.json --workers 8 > $O/R.log 2>&1; echo "R rc=$? $(date)" >> $P
for b in bank-2026-08-19 bank-2026-08-20; do
  $PY -m utils.evaluation.experiment_untruncated --arm deterministic --bank docs/evaluation/banks/$b/bank.json --root $O/$b --workers 4 > $O/det-$b.log 2>&1; echo "det $b rc=$? $(date)" >> $P
done
$PY -m utils.evaluation.experiment_untruncated --arm deterministic --bank docs/evaluation/composition/bank/bank-dev.json --root $O/dev --workers 8 > $O/det-dev.log 2>&1; echo "det dev rc=$? $(date)" >> $P
R=docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants
for a in T-lazy T-full T-lazy-G; do
  $PY scripts/algebra_pipeline_replay.py $R $a $O/replay-$a.json --workers 8 > $O/replay-$a.log 2>&1; echo "replay $a rc=$? $(date)" >> $P
done
echo "DONE $(date)" >> $P
