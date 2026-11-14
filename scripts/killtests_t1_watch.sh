#!/usr/bin/env bash
# Keep checking relay aliases; run T1 (killtests_t1_model.py) on whatever model each
# healthy alias serves. A model already scored is resumed instantly (all stages done).
# Exits once a result exists whose folder name contains $WANT (default: Qwen's stop
# token, stop151645).
#   KILLTESTS_CONCURRENCY=64 scripts/killtests_t1_watch.sh default-model default-model-2
set -u
cd "$(dirname "$0")/.."
WANT="${WANT:-stop151645}"
ALIASES=("$@")
while true; do
  healthy=$(curl -s -m 20 localhost:9090/v1/models | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)["data"]
    print(" ".join(m["id"] for m in d if (m.get("relay") or {}).get("health")=="healthy"))
except Exception:
    pass')
  for a in "${ALIASES[@]}"; do
    if [[ " $healthy " == *" $a "* ]]; then
      uv run python scripts/killtests_t1_model.py "$a" --no-wait || echo "$(date +%T) run on $a failed"
    fi
  done
  if compgen -G "logs/killtests-2026-11/t1-models/*${WANT}*/killrule.json" > /dev/null; then
    echo "$(date +%T) found $WANT result; exiting"
    exit 0
  fi
  sleep 300
done
