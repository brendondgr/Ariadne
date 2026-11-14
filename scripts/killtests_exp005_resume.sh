#!/usr/bin/env bash
# EXP-2026-11-005: resume part B after relay outages.
#
# Only successful generations are cached, so a rerun of the generate stage retries exactly the
# calls that failed with a relay error. The derived stage files (generate/repair/execute/score
# results, and the execute cache, which records generation errors as rows) are removed first.
# The model behind each alias is re-identified by tokenizer token id before every pass, and the
# run header is rewritten with the current mapping (the first mapping is kept). Passes repeat
# until no generation error remains, at most MAX_PASSES times.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=logs/killtests-2026-11/exp005
MAX_PASSES=${MAX_PASSES:-6}
healthy() {
  for m in default-model default-model-2; do
    curl -s -m 120 http://localhost:9090/v1/chat/completions -H 'content-type: application/json' \
      -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"Say ok.\"}],\"max_tokens\":64}" \
      | grep -q '"choices"' || return 1
  done
}
for pass in $(seq 1 "$MAX_PASSES"); do
  until healthy; do echo "$(date -Is) relay not healthy; waiting"; sleep 120; done
  echo "$(date -Is) pass $pass: relay healthy"
  uv run python - <<'EOF' || exit 2
import json, time
from pathlib import Path
from utils.config import load_env
load_env()
from utils.killtests.config import get
from utils.killtests.relay import RelayClient
from utils.killtests.t2c.run import identify
cfg = get()
relay = RelayClient(cfg.relay_url, max_tokens=cfg.relay_max_tokens)
hp = Path("logs/killtests-2026-11/exp005/run_header.json")
hdr = json.loads(hp.read_text())
now = [identify(relay, a) for a in ("default-model", "default-model-2")]
if {i["model"] for i in now} != {i["model"] for i in hdr["identities"]}:
    raise SystemExit(f"model set changed: {now}")
hdr.setdefault("identities_initial", hdr["identities"])
hdr.setdefault("resumes", []).append({"at": time.time(), "identities": now})
hdr["identities"] = now
hp.write_text(json.dumps(hdr, indent=1))
print({i["alias"]: i["model"] for i in now})
EOF
  rm -f "$OUT"/B-generate.{done,json} "$OUT"/B-repair.{done,json} "$OUT"/B-execute.{done,json} \
        "$OUT"/B-score.{done,json} "$OUT"/cache/B-execute.jsonl
  KILLTESTS_CONCURRENCY=${KILLTESTS_CONCURRENCY:-64} uv run --with pyarrow python -m utils.killtests.t2c.run B 2>&1 \
    | grep -v "Received error message\|With results dictionary\|^$"
  n=$(uv run python -c "
import json
g=json.load(open('$OUT/B-generate.json'))['generations']
r=json.load(open('$OUT/B-repair.json'))['generations']
print(sum('error' in v for v in g.values())+sum('error' in v for v in r.values()))")
  echo "$(date -Is) pass $pass: $n generation errors remain"
  [ "$n" = "0" ] && exit 0
done
exit 1
