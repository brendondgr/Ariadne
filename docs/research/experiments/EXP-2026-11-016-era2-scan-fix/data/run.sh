#!/bin/bash
# EXP-2026-11-016 (scan fix), on one commit. R first; then the Qwen chain and the Gemma chain in parallel.
set -u
cd /home/bdgr/Agents/Ariadne
EXP=docs/research/experiments/EXP-2026-11-016-era2-scan-fix; L=$EXP/logs; RUNS=docs/evaluation/experiments/scan-fix-2026-11-19; mkdir -p $RUNS/variants; export ORCH_MAX_HOPS=5
B=docs/evaluation/composition/bank/bank-dev.json
git rev-parse HEAD > $L/TREE; git status --short | grep -v '^?? \.\./' > $L/STATUS
uv run main.py --dataset attack --graph verify > $L/verify.log 2>&1 && uv run main.py --dataset capec --graph verify >> $L/verify.log 2>&1 || { echo "STORES FAILED"; exit 1; }
uv run python scripts/variant_harness.py capture --out $RUNS/variants --name reference.json --workers 8 > $L/R-capture1.log 2>&1
uv run python scripts/variant_harness.py capture --out $RUNS/variants --name reference_check.json --workers 8 > $L/R-capture2.log 2>&1
cmp $RUNS/variants/reference.json $RUNS/variants/reference_check.json > $L/R-cmp.log 2>&1 && echo IDENTICAL >> $L/R-cmp.log || echo DIFFER >> $L/R-cmp.log
uv run python scripts/variant_harness.py compare --out $RUNS/variants --name R.json --workers 8 > $L/R-compare.log 2>&1
echo "R done $(date)" >> $L/progress.log
(
 for a in E T-lazy T-full; do uv run python scripts/variant_harness.py compare --out $RUNS/variants --arm $a --workers 16 > $L/var-$a.log 2>&1; echo "var $a done $(date) rc=$?" >> $L/progress.log; done
 for a in planned_llm_english planned_llm_typed_lazy planned_llm_typed_full; do uv run python -m utils.evaluation.experiment_untruncated --arm $a --bank $B --root $RUNS/dev --workers 16 > $L/dev-$a.log 2>&1; echo "dev $a done $(date) rc=$?" >> $L/progress.log; done
) &
(
 uv run python scripts/variant_harness.py compare --out $RUNS/variants --arm T-lazy-G --workers 16 > $L/var-T-lazy-G.log 2>&1; echo "var T-lazy-G done $(date) rc=$?" >> $L/progress.log
 uv run python -m utils.evaluation.experiment_untruncated --arm planned_llm_typed_lazy --model gemma4-31b --bank $B --root $RUNS/dev-gemma --workers 16 > $L/dev-gemma.log 2>&1; echo "dev gemma done $(date) rc=$?" >> $L/progress.log
) &
wait
echo "ALL DONE $(date)" >> $L/progress.log
