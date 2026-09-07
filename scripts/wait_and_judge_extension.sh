#!/usr/bin/env bash
# Wait for default-model-2, then grade EXP-2026-09-011's extension seeds.
#
# The operator asked for a 10-minute grace period before touching the endpoint,
# so this sleeps first rather than hammering a server that is still loading
# weights. It then probes until the endpoint answers with the recorded model.
#
# ENDPOINTS in seeded_repeats_judge.py lists -2/-3/-4 and drops any that does
# not answer, so this works whether one, two or three come up.
set -u
LOG=logs/extension-judging-waiter.log
GRACE=${1:-600}

echo "[$(date +%H:%M)] grace period ${GRACE}s before first probe" >> "$LOG"
sleep "$GRACE"

for attempt in $(seq 1 60); do
  served=$(curl -s -m 120 http://localhost:9090/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{"model":"default-model-2","messages":[{"role":"user","content":"OK"}],"max_tokens":2048}' \
    2>/dev/null | python3 -c 'import sys,json
try: d=json.load(sys.stdin)
except Exception: print(""); raise SystemExit
print("" if "error" in d else (d.get("model") or ""))' 2>/dev/null)

  if [ "$served" = "qwen38-27B-v2" ]; then
    echo "[$(date +%H:%M)] default-model-2 serving $served after $attempt probe(s)" >> "$LOG"
    uv run python scripts/seeded_repeats_judge.py \
      --arm generic --seeds extension --workers 32 >> logs/extension-judging.log 2>&1
    echo "[$(date +%H:%M)] judging exited rc=$?" >> "$LOG"
    exit 0
  fi
  echo "[$(date +%H:%M)] probe $attempt: not ready (${served:-no response})" >> "$LOG"
  sleep 120
done
echo "[$(date +%H:%M)] gave up after 60 probes (~2h)" >> "$LOG"
