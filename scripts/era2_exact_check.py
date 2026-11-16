#!/usr/bin/env python3
"""EXP-2026-11-011: the Step 5 checks, recorded.

    uv run python scripts/era2_exact_check.py --out <experiment>/data

1. runs the Step 5 test suites (offline and live) and records their counts;
2. re-runs the deterministic arm on both banks and generic_composed on dev, and
   diffs them against the same arms run on the tree before Step 5;
3. counts ceiling hits on dev at 20,000 and at 1,000 rows (the census);
4. checks every primary enumeration claim's N against its result's distinct ids.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

SUITES = ["utils/specialists/tests/test_never_silent_truncation.py", "utils/synthesis/tests/test_never_silent.py",
          "utils/agent/tests/test_handles.py", "utils/agent/tests/test_contracts.py",
          "utils/agent/tests/test_exact_live.py", "utils/specialists/tests/test_ceiling_live.py"]
CLOCK = {"wall_s", "timing_ms", "elapsed_ms", "duration_ms", "latency_ms", "ms", "total_ms", "plan_ms",
         "synthesis_ms", "timings"}
NEW_FIELDS = {"row_ceiling", "truncated"}


def _strip(o, drop):
    if isinstance(o, dict):
        return {k: _strip(v, drop) for k, v in o.items() if k not in drop}
    if isinstance(o, list):
        return [_strip(v, drop) for v in o]
    return o


def _ids(d):
    out = set()
    for c in (d.get("answer") or {}).get("claims") or []:
        out |= set(c.get("entity_ids") or [])
    return out


def diff(new_dir: Path, old_dir: Path) -> dict:
    n = same_ids = same_answer = same_all = 0
    changed = []
    for f in sorted(new_dir.glob("*.json")):
        if ".judgment" in f.name:
            continue
        o = old_dir / f.name
        if not o.exists():
            changed.append({"case": f.name, "why": "missing in baseline"})
            continue
        a, b = json.loads(f.read_text()), json.loads(o.read_text())
        n += 1
        same_ids += _ids(a) == _ids(b)
        sa = _strip(a.get("answer"), CLOCK) == _strip(b.get("answer"), CLOCK)
        same_answer += sa
        sall = _strip({k: v for k, v in a.items() if k != "run_meta"}, CLOCK | NEW_FIELDS) == \
            _strip({k: v for k, v in b.items() if k != "run_meta"}, CLOCK | NEW_FIELDS)
        same_all += sall
        if not (sa and sall):
            changed.append({"case": f.name, "answer_same": sa, "rest_same_except_new_fields": sall})
    return {"n": n, "same_ids": same_ids, "same_answer": same_answer,
            "same_except_new_trace_fields": same_all, "changed": changed[:20]}


def run_arm(arm: str, bank: str, root: Path, extra_env: dict | None = None) -> Path:
    env = {**os.environ, "ORCH_MAX_HOPS": "5", **(extra_env or {})}
    subprocess.run([sys.executable, "-m", "utils.evaluation.experiment_untruncated", "--arm", arm,
                    "--bank", bank, "--root", str(root), "--workers", "8"], cwd=REPO, env=env, check=True,
                   stdout=subprocess.DEVNULL)
    return root / arm / "answers"


def census(answers: Path) -> dict:
    hit, total = [], 0
    for f in sorted(answers.glob("*.json")):
        if ".judgment" in f.name:
            continue
        total += 1
        d = json.loads(f.read_text())
        for r in (d.get("logic_flow") or {}).get("results") or []:
            for t in r.get("traces") or []:
                if t.get("step") == "ceiling":
                    hit.append(f.stem)
    return {"questions": total, "hit_ceiling": len(set(hit)), "cases": sorted(set(hit))[:20]}


def enumeration_counts(answers: Path) -> dict:
    """G4: every enumeration claim's N against what it lists and what it says it withholds."""
    has = re.compile(r" has (\d+) ")
    whole = re.compile(r"^(?:All |At least )?(\d+) result\(s\) for this question")
    withheld = re.compile(r"(\d+) further (?:is|are) withheld")
    checked = bad = 0
    problems = []
    for f in sorted(answers.glob("*.json")):
        if ".judgment" in f.name:
            continue
        d = json.loads(f.read_text())
        results = (d.get("logic_flow") or {}).get("results") or []
        for c in (d.get("answer") or {}).get("claims") or []:
            if c.get("kind") != "enumeration":
                continue
            text = c.get("text") or ""
            listed = len(c.get("entity_ids") or [])
            w = withheld.search(text)
            m_whole, m_has = whole.match(text), has.search(text)
            if m_whole:
                distinct = {rec.get("primary_id") for r in results for rec in (r.get("records") or [])
                            if rec.get("primary_id")}
                want, n = len(distinct), int(m_whole.group(1))
            elif m_has:
                want, n = listed + (int(w.group(1)) if w else 0), int(m_has.group(1))
            else:
                continue
            checked += 1
            if n != want:
                bad += 1
                problems.append({"case": f.stem, "claim_n": n, "expected": want, "text": text[:160]})
    return {"claims_checked": checked, "mismatches": bad, "problems": problems[:10]}


def suites() -> dict:
    out = {}
    for s in SUITES:
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", s], cwd=REPO,
                           capture_output=True, text=True)
        tail = (p.stdout.strip().splitlines() or [""])[-1]
        out[s] = {"exit": p.returncode, "summary": tail}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--scratch", default="/tmp/claude-1000/-home-bdgr-Agents-Ariadne/e287aee2-08ba-47b4-b868-f26f2b870fe3/scratchpad")
    a = ap.parse_args(argv)
    out, scratch = Path(a.out), Path(a.scratch)
    root = scratch / "exp011"
    res: dict = {"suites": suites()}
    res["regression"] = {}
    for b in ("2026-08-19", "2026-08-20"):
        new = run_arm("deterministic", f"docs/evaluation/banks/bank-{b}/bank.json", root / f"bank{b.replace('-', '')}")
        res["regression"][f"deterministic bank-{b}"] = diff(new, scratch / "walkreg" / f"bank{b.replace('-', '')}" / "deterministic" / "answers")
    dev = run_arm("generic_composed", "docs/evaluation/composition/bank/bank-dev.json", root / "dev")
    res["regression"]["generic_composed dev"] = diff(
        dev, REPO / "docs/evaluation/experiments/harness-attribution-qwen-walkfix-2026-11-16/generic_composed/answers")
    res["census_20000"] = census(dev)
    dev1000 = run_arm("generic_composed_capped", "docs/evaluation/composition/bank/bank-dev.json", root / "dev1000")
    res["census_1000"] = census(dev1000)
    res["g4_enumeration_counts"] = enumeration_counts(dev)
    out.mkdir(parents=True, exist_ok=True)
    (out / "exact.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1)[:5000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
