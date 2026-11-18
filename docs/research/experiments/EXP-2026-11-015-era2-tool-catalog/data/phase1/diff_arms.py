"""Diff an after-run against a before-run using scripts/era2_exact_check.diff (clock fields excluded)."""
import json, sys
from pathlib import Path
sys.path.insert(0, "/home/bdgr/Agents/Ariadne")
import scripts.era2_exact_check as ec
ec.NEW_FIELDS = ec.NEW_FIELDS | {"signals"}  # the task's new serialised field (Step 8)
diff = ec.diff
new, old = Path(sys.argv[1]), Path(sys.argv[2])
out = {}
for sub in ("bank20260819/deterministic", "bank20260820/deterministic", "dev/generic_composed"):
    out[sub] = diff(new / sub / "answers", old / sub / "answers")
print(json.dumps(out, indent=1))
