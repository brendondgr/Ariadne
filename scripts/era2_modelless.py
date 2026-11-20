"""Count the answers of one planner arm that no model planned (EXP-2026-11-017, check H1).

    uv run python scripts/era2_modelless.py <variants arm .json | dev arm dir> [--max 12]

A relay drop (the :9090 tunnel) mid-arm makes the remaining answers model-less while the
identity check before and after still passes (EXP-2026-11-016 ISSUES). A model-less answer
is one whose planner fell back to ``DeterministicDrafter``, or a dev answer that records
``could not reach localhost:9090``. A healthy arm has 1-12 of 699 (variants) or of 284
(dev); a drop gives hundreds. Prints ``<path> modelless=<n> of <total> OK|RERUN`` and exits
1 when the count is above ``--max``. ``--merge <metrics.json>`` also records
``{"modelless": n, "total": t, "max": m}`` under ``h1.<arm path relative to its run root>``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import era2_catalog_score as S  # noqa: E402

UNREACHABLE = "could not reach localhost:9090"


def count(path: Path) -> tuple[int, int]:
    if path.is_dir():
        files = sorted((path / "answers").glob("*.json")) if (path / "answers").is_dir() else sorted(path.glob("*.json"))
        bad = 0
        for f in files:
            text = f.read_text()
            a = json.loads(text)
            if (a.get("run_meta") or {}).get("drafter_used") == "DeterministicDrafter" or UNREACHABLE in text:
                bad += 1
        return bad, len(files)
    rows = S.load_variant_rows(path)
    bad = sum(1 for r in rows if (r.get("planner") or {}).get("drafter") == "DeterministicDrafter")
    return bad, len(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--max", type=int, default=12)
    ap.add_argument("--merge", default=None, help="a metrics.json to record the count in, under h1")
    args = ap.parse_args(argv)
    bad, total = count(Path(args.path))
    ok = bad <= args.max
    if args.merge:
        mp = Path(args.merge)
        m = json.loads(mp.read_text())
        key = "/".join(Path(args.path).parts[-2:])
        m.setdefault("h1", {})[key] = {"modelless": bad, "total": total, "max": args.max}
        mp.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    print(f"{args.path} modelless={bad} of {total} {'OK' if ok else 'RERUN'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
