#!/usr/bin/env bash
# Keep EXP-2026-09-011's judging alive until a deadline.
#
# The overnight driver retries judging three times. Both spare attempts were
# spent on deliberate restarts (sharding, then releasing default-model), not on
# failures, so the run is now one hiccup away from ending incomplete with hours
# of GPU time left. This watchdog is the backstop.
#
# It relaunches ONLY when judging is both incomplete and not running. Judging is
# idempotent -- the judge skips any case that already has a sidecar -- so a
# relaunch re-grades nothing and a crashed pass loses only the case in flight.
#
#   nohup bash scripts/judging_watchdog.sh 07:35 &

set -u
DEADLINE="${1:-07:35}"
ROOT="docs/evaluation/experiments/seeded-repeats-generic-2026-09-06"
LOG="logs/judging-watchdog.log"
TARGET=1704
RELAUNCHES=0
MAX_RELAUNCHES=12   # a crash loop should stop, not spin until morning

count() {
  local n=0 c
  for s in 1729 20260906 424242; do
    for suf in q1 q2; do
      c=$(ls "$ROOT/seed-$s/generic/answers/"*.judgment.$suf.json 2>/dev/null | wc -l)
      n=$((n + c))
    done
  done
  echo "$n"
}

echo "[$(date +%H:%M)] watchdog up, deadline $DEADLINE, target $TARGET" >> "$LOG"

while true; do
  now=$(date +%H:%M)
  [[ "$now" > "$DEADLINE" ]] && { echo "[$now] deadline reached, standing down" >> "$LOG"; break; }

  n=$(count)
  if [ "$n" -ge "$TARGET" ]; then
    echo "[$now] complete: $n/$TARGET" >> "$LOG"
    break
  fi

  if ! pgrep -f "scripts/seeded_repeats_judge.py" > /dev/null 2>&1; then
    if [ "$RELAUNCHES" -ge "$MAX_RELAUNCHES" ]; then
      echo "[$now] $RELAUNCHES relaunches reached; refusing to spin. $n/$TARGET" >> "$LOG"
      break
    fi
    RELAUNCHES=$((RELAUNCHES + 1))
    echo "[$now] judging not running at $n/$TARGET — relaunch #$RELAUNCHES" >> "$LOG"
    nohup uv run python scripts/seeded_repeats_judge.py --arm generic --workers 32 \
      >> "logs/judging-relaunch-$RELAUNCHES.log" 2>&1 &
    sleep 120   # let the endpoint probes finish before judging liveness again
  fi
  sleep 180
done
