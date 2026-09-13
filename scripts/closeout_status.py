#!/usr/bin/env python3
"""Is the close-out chain doing what it is supposed to? One command.

    uv run python scripts/closeout_status.py

Written because the honest answer to "is it running?" twice turned out to be no,
and because a chain that reports only at the end is a chain you find out about
at the end. It reads state off disk and runs nothing, so it is safe to call at
any moment, including mid-grading.

Four things, in the order they go wrong:

1. **Is anything alive.** Matched on the process's interpreter field, never on a
   text pattern — `pgrep -f` matches any command line that merely mentions the
   script, which held the supervisor open against a watcher for two hours.
2. **Which stages are done**, from the chain's own state file, including the
   ones deliberately not requested.
3. **How much of each cell is judged**, answers against sidecars, because a
   stage exits zero whether it graded a case or wrote an error beside it.
4. **The numbers so far**, marked preliminary until every cell is complete.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.closeout_run import (  # noqa: E402
    ARMS, CONTROL, FRESH, PASSES, REGRESSION, SIDES, STATE, STAGES, _ungraded,
)


def _alive() -> list[str]:
    out = subprocess.check_output(["ps", "-eo", "pid,args", "--no-headers"], text=True)
    found = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2 or "python" not in parts[1]:
            continue
        for tag in ("closeout_run.py", "judge_answers", "experiment_untruncated",
                    "repair_control_run.py"):
            if tag in line:
                found.append(f"{parts[0]} {tag}")
                break
    return found


def _cell_rows(root: Path, arms=ARMS, sides=(None,)) -> list[tuple[str, int, int]]:
    rows = []
    for side in sides:
        base = root if side is None else root / side
        for arm in arms:
            answers = [
                p for p in (base / arm / "answers").glob("*.json")
                if ".judgment" not in p.name
            ] if (base / arm / "answers").is_dir() else []
            if not answers:
                continue
            for suffix, _position in PASSES:
                done = len(answers) - len(_ungraded(base, arm, suffix))
                name = f"{side + '/' if side else ''}{arm}{suffix}"
                rows.append((name, done, len(answers)))
    return rows


def main() -> int:
    print("processes")
    alive = _alive()
    for row in alive or ["  (nothing running)"]:
        print(f"  {row}" if alive else row)

    sup = subprocess.run(
        ["bash", "-c",
         "ps -eo pid,args --no-headers | awk '/closeout_supervise[.]sh/ {print $1}'"],
        capture_output=True, text=True).stdout.split()
    print(f"  supervisor: {' '.join(sup) if sup else 'NOT RUNNING'}")

    print("\nstages")
    state = json.loads(STATE.read_text()) if STATE.is_file() else {}
    for name, _fn in STAGES:
        row = state.get(name)
        if not isinstance(row, dict):
            print(f"  {name:28s} —")
            continue
        mark = "ok" if row.get("ok") else "FAILED"
        secs = row.get("elapsed_s")
        print(f"  {name:28s} {mark}"
              + (f"  {secs:.0f}s" if isinstance(secs, (int, float)) else ""))

    print("\njudged (answers with a sidecar / answers)")
    groups = [("control", CONTROL, SIDES), ("fresh", FRESH, (None,)),
              ("regression", REGRESSION, (None,))]
    for label, root, sides in groups:
        if not root.is_dir():
            continue
        rows = _cell_rows(root, sides=sides)
        if not rows:
            continue
        print(f"  {label}")
        for name, done, total in rows:
            bar = "complete" if done == total else f"{done / max(total, 1):.0%}"
            print(f"    {name:34s} {done:4d} / {total:<4d} {bar}")

    print("\nnumbers so far")
    try:
        from scripts.paired_control_score import score

        report = score(CONTROL, partial=True)
        tag = "PRELIMINARY — " if report.get("preliminary") else ""
        for arm in ARMS:
            row = (report["arms"].get(arm) or {}).get("overall")
            if row is None:
                print(f"  {arm:18s} not yet pairable")
                continue
            print(f"  {arm:18s} n={row['n']:3d}  {row['before']:.4f} -> "
                  f"{row['after']:.4f}  {row['paired_difference']:+.4f} "
                  f"± {row['standard_error']:.4f}")
        gate = report["kill_gate"]
        print(f"  {tag}kill gate: fabricated_mapping "
              f"{gate['fabricated_mapping_reference']} -> "
              f"{gate['fabricated_mapping_repaired']}  "
              f"{'passes' if gate['passes'] else 'FAILS'}")
    except SystemExit as exc:
        print(f"  not scorable yet: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
