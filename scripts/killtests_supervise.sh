#!/bin/bash
# Keep the kill-test chain alive without a human attached (EXP-2026-11-001..003).
#
# Modelled on closeout_supervise.sh, including its hard-won lesson: never ask
# `pgrep -f` whether the chain is running, because any shell whose command line
# merely MENTIONS the script matches. Match on the process's interpreter field.
#
# The chain resumes at stage and item granularity, so restarting it is cheap.
# The supervisor waits for a live chain to exit before deciding anything, so
# there is never more than one. After three failures of the same test it stops
# and writes the reason to ALERTS.md instead of looping on a real defect.
cd /home/bdgr/Agents/Ariadne || exit 1
OUT=${KILLTESTS_OUT:-logs/killtests-2026-11}
mkdir -p "$OUT"
LOG="$OUT/supervisor.log"
CHAIN_LOG="$OUT/chain.log"
ALERTS="$OUT/ALERTS.md"
MAX_FAILS=3
echo $$ > "$OUT/supervisor.pid"

say() { echo "$(date -Is) $*" >> "$LOG"; }

chain_running() {
  ps -eo pid,args --no-headers \
    | awk '$2 ~ /python/ && $0 ~ /scripts\/killtests_run\.py/ { found = 1 } END { exit !found }'
}

done_yet() { [ -f "$OUT/report.done" ]; }

failed_test() {
  python3 -c "
import json,sys
try: s=json.load(open('$OUT/chain.json'))
except Exception: sys.exit(0)
f=[t for t,v in s.get('tests',{}).items() if v.get('status')=='failed']
print(','.join(sorted(f)))"
}

declare -A FAILS
say "supervisor start pid=$$"
while true; do
  if done_yet; then say "report written; supervisor exits"; break; fi
  if chain_running; then sleep 60; continue; fi
  f=$(failed_test)
  if [ -n "$f" ]; then
    FAILS[$f]=$(( ${FAILS[$f]:-0} + 1 ))
    say "chain exited with failed test(s): $f (failure ${FAILS[$f]} of $MAX_FAILS)"
    if [ "${FAILS[$f]}" -ge "$MAX_FAILS" ]; then
      {
        echo "## $(date -Is) RED — supervisor gave up"
        echo ""
        echo "Test(s) \`$f\` failed $MAX_FAILS times. Last error, from chain.json:"
        echo '```'
        python3 -c "import json;s=json.load(open('$OUT/chain.json'));[print(t, v.get('error','')) for t,v in s['tests'].items() if v.get('status')=='failed']"
        echo '```'
        echo ""
      } >> "$ALERTS"
      say "giving up after $MAX_FAILS failures of $f"
      break
    fi
    sleep 120
  fi
  say "starting chain"
  nohup uv run python scripts/killtests_run.py >> "$CHAIN_LOG" 2>&1 &
  sleep 30
done
rm -f "$OUT/supervisor.pid"
