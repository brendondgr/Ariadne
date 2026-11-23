#!/bin/bash
cd /home/bdgr/Agents/Ariadne
( bash docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data/stage.sh docs/evaluation/experiments/algebra-exposure-2026-11-20/fix5-small core T-lazy; bash docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data/stage.sh docs/evaluation/experiments/algebra-exposure-2026-11-20/fix5-small core T-full; bash docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data/stage.sh docs/evaluation/experiments/algebra-exposure-2026-11-20/fix5-small core+ext T-lazy; bash docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data/stage.sh docs/evaluation/experiments/algebra-exposure-2026-11-20/fix5-small core+ext T-full ) &
( bash docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data/stage.sh docs/evaluation/experiments/algebra-exposure-2026-11-20/fix5-small core T-lazy-G; bash docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data/stage.sh docs/evaluation/experiments/algebra-exposure-2026-11-20/fix5-small core+ext T-lazy-G ) &
wait
echo "ALL FIX4 DONE $(date)" >> docs/evaluation/experiments/algebra-exposure-2026-11-20/fix5-small/progress.log
