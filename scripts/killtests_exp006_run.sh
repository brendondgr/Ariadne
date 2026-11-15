#!/usr/bin/env bash
# EXP-2026-11-006: run parts A, B and C, retrying failed generations until none remain.
#
# Only successful generations are cached, so a pass after a relay error retries exactly the failed
# calls. Before each later pass, every part's derived stage files and its execute cache (which
# records generation errors as rows) are removed. The model behind each alias is identified by
# tokenizer token id before every pass and recorded in the run header.
set -uo pipefail
cd "$(dirname "$0")/.."
export KILLTESTS_EXPERIMENT=exp006
export KILLTESTS_REASONING_EFFORT='{"qwen38-27b": "medium"}'
export KILLTESTS_CONCURRENCY=${KILLTESTS_CONCURRENCY:-16}
OUT=logs/killtests-2026-11/exp006
MAX_PASSES=${MAX_PASSES:-6}
healthy() {
  for m in default-model default-model-2; do
    curl -s -m 120 http://localhost:9090/v1/chat/completions -H 'content-type: application/json' \
      -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"Say ok.\"}],\"max_tokens\":64}" \
      | grep -q '"choices"' || return 1
  done
}
mkdir -p "$OUT"
for pass in $(seq 1 "$MAX_PASSES"); do
  while :; do
    until healthy; do echo "$(date -Is) relay not healthy; waiting"; sleep 120; done
    echo "$(date -Is) pass $pass: relay healthy"
    uv run python - <<'EOF'
import json, os, time
from pathlib import Path
from utils.config import load_env
load_env()
from utils.killtests.config import get
from utils.killtests.relay import RelayClient
from utils.killtests.typed.run import identify
cfg = get()
relay = RelayClient(cfg.relay_url, max_tokens=cfg.relay_max_tokens)
hp = Path("logs/killtests-2026-11/exp006/run_header.json")
try:
    now = [identify(relay, a) for a in ("default-model", "default-model-2")]
except Exception as exc:  # a transient relay error: wait and retry
    print("identify failed:", exc)
    raise SystemExit(3)
if {i["model"] for i in now} != {"gemma4-31b", "qwen38-27b"}:
    raise SystemExit(f"unexpected models: {now}")
eff = json.loads(os.environ.get("KILLTESTS_REASONING_EFFORT") or "{}")
if hp.exists():
    hdr = json.loads(hp.read_text())
    hdr.setdefault("resumes", []).append({"at": time.time(), "identities": now, "reasoning_effort": eff})
    hdr["identities"] = now
else:
    hdr = {"started_at": time.time(), "identities": now, "concurrency_per_model": cfg.relay_concurrency,
           "max_tokens": cfg.relay_max_tokens, "reasoning_effort": eff}
hp.write_text(json.dumps(hdr, indent=1))
print({i["alias"]: i["model"] for i in now})
EOF
    rc=$?
    [ $rc = 0 ] && break
    [ $rc = 3 ] || exit 2
    sleep 120
  done
  if [ "$pass" -gt 1 ]; then
    for p in A B C; do
      rm -f "$OUT"/$p-generate.{done,json} "$OUT"/$p-repair.{done,json} "$OUT"/$p-execute.{done,json} \
            "$OUT"/$p-score.{done,json} "$OUT"/cache/$p-execute.jsonl
    done
  fi
  uv run --with pyarrow python -m utils.killtests.t2c.run A B C 2>&1 \
    | grep -v "Received error message\|With results dictionary\|Received notification\|^$"
  n=$(uv run python -c "
import json
n = 0
for p in 'ABC':
    for s in ('generate', 'repair'):
        try:
            g = json.load(open(f'$OUT/{p}-{s}.json'))['generations']
        except FileNotFoundError:
            n += 1
            continue
        n += sum('error' in v for v in g.values())
print(n)")
  echo "$(date -Is) pass $pass: $n generation errors remain"
  [ "$n" = "0" ] && exit 0
done
exit 1
