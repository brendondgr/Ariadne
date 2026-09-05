#!/bin/bash
# Wait for llm_query's 288 answers, then judge all three holdout arms under
# qwen, both positions, no deadline. The non-expiring GPU, so nothing here is
# racing a clock.
#
# Waits for COMPLETENESS, not for the process to exit -- the 12:32 incident was
# a chain that read process-exit as success and drove 288 cases into a dead
# server. A count on disk cannot lie about that.
cd /home/bdgr/Agents/Ariadne
A=docs/evaluation/experiments/holdout-spend-2026-09-05/llm_query/answers
while [ "$(ls $A/*.json 2>/dev/null | grep -vc judgment)" -lt 288 ]; do
  if ! pgrep -f "experiment_untruncated --arm llm_query" >/dev/null; then
    echo "llm_query generation exited at $(date '+%H:%M') with only \
$(ls $A/*.json 2>/dev/null | grep -vc judgment)/288 answers — not judging a partial arm"
    exec uv run python scripts/holdout_judge.py --grader qwen --arm deterministic generic
  fi
  sleep 60
done
echo "llm_query complete at $(date '+%H:%M:%S'); judging all three arms under qwen"
exec uv run python scripts/holdout_judge.py --grader qwen \
     --arm deterministic generic llm_query
