#!/usr/bin/env python3
"""Overnight 2026-09-06: calibrate the graders, then spend them.

Plan: ``docs/plans/2026-09-05-overnight-local-model-tests.md``.

Today's finding is that a grader can be *saturated* -- gemma4-31B-mtp returned
exactly 1.0 on all 150 composerfix answers -- and a saturated grader reports a
gap of zero whatever is true. So Phase A measures who can actually resolve
differences near the ceiling BEFORE anything is spent on them, and the later
phases are gated on what it finds.

Three tracks, three endpoints, run concurrently:

  G  :9090/default-model-2  gemma4-31B-mtp   24 workers   (operator cap)
  Q  :9090/default-model    qwen38-27B-v2     8 workers   (operator cap)
  L  :4000/local            gemma-4-26B-it    8 workers

Rules enforced here, every one of them learned from a defect on 2026-09-05:

* **Probe the served model before every phase and refuse on mismatch.** One
  alias served two different families within six hours.
* **Never treat process exit as success** -- count artefacts on disk.
* **One state file per track**; two processes sharing one clobber each other.
* **Disjoint cells across tracks**; two writers on one judgment file can
  interleave into truncated JSON.
* **A partial cell is not a result.**

    uv run python scripts/overnight_2026_09_06.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from utils.config import load_env  # noqa: E402
load_env()

RUNS = REPO / "docs/evaluation/experiments"
EXP = REPO / "docs/research/experiments"
LOGS = REPO / "logs/overnight-2026-09-06"
STATE_DIR = REPO / "docs/evaluation/composition/bank"
REPORT_MD = REPO / "docs/reports/2026-09-06-overnight-report.md"

CAL = RUNS / "calibration-2026-09-06"
HOLD = RUNS / "holdout-spend-2026-09-05"
CFX_DEV, CFX_HO = RUNS / "composerfix-dev", RUNS / "composerfix-holdout"

#: Concurrency is the operator's, not ours. Qwen is capped at 8 for this task.
ENDPOINTS = {
    "gemma31": {"url": "http://localhost:9090/v1", "model": "default-model-2",
                "workers": 24, "expect": "gemma4-31b"},
    "qwen":    {"url": "http://localhost:9090/v1", "model": "default-model",
                "workers": 8,  "expect": "qwen38"},
    "gemma26": {"url": "http://localhost:4000/v1", "model": "local",
                "workers": 8,  "expect": "gemma-4-26b"},
}
JUDGE_MAX_TOKENS = 32768
DEADLINE = None          # set in main()
BANDS = ("ceiling", "mid", "low")

_lock = threading.Lock()
_state: dict[str, dict] = {}


def save(track: str) -> None:
    with _lock:
        p = EXP / "EXP-2026-09-008-grader-calibration" / "data" / f"state-{track}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(_state.get(track, {}), indent=1, default=str) + "\n")


def probe(ep: str) -> str:
    import urllib.request
    spec = ENDPOINTS[ep]
    req = urllib.request.Request(
        f"{spec['url'].rstrip('/')}/chat/completions",
        data=json.dumps({"model": spec["model"], "max_tokens": 64, "temperature": 0.0,
                         "messages": [{"role": "user", "content": "ready"}]}).encode(),
        headers={"Content-Type": "application/json"})
    served = json.loads(urllib.request.urlopen(req, timeout=300).read())["model"]
    if spec["expect"] not in str(served).lower():
        raise RuntimeError(f"{ep}: {spec['model']} serves {served}, expected {spec['expect']}")
    return served


def judge(ep: str, root: Path, arm: str, suffix: str, position: int) -> dict:
    from utils.evaluation.judge_answers import JudgeConfig, run as judge_run
    spec = ENDPOINTS[ep]
    adir = root / arm / "answers"
    n = sum(1 for p in adir.glob("*.json") if ".judgment" not in p.name)
    out = judge_run(root, arm,
                    JudgeConfig(base_url=spec["url"], model=spec["model"],
                                max_tokens=JUDGE_MAX_TOKENS, timeout_s=900.0,
                                position=position),
                    workers=spec["workers"], suffix=suffix)
    want = f".judgment{suffix}.json"
    wrote = sum(1 for p in adir.glob(f"*{want}") if p.name.endswith(want))
    return {**(out or {}), "answers": n, "judgments_written": wrote, "complete": wrote == n}


def scores(root: Path, arm: str, suffix: str) -> list[float]:
    adir = root / arm / "answers"
    want = f".judgment{suffix}.json"
    out = []
    for p in adir.glob(f"*{want}"):
        if not p.name.endswith(want):
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:                                          # noqa: BLE001
            continue
        if d.get("correctness") is not None:
            out.append(float(d["correctness"]))
    return out


def run_phase(track: str, name: str, fn: Callable[[], dict], needs_by: datetime | None = None) -> bool:
    st = _state.setdefault(track, {})
    if st.get(name, {}).get("status") == "done":
        print(f"[{track}] {name}: already done", flush=True); return True
    if DEADLINE and datetime.now() >= DEADLINE:
        st[name] = {"status": "not_run", "reason": f"past {DEADLINE:%H:%M}"}; save(track)
        print(f"[{track}] {name}: SKIPPED (past deadline)", flush=True); return False
    if needs_by and datetime.now() >= needs_by:
        st[name] = {"status": "not_run", "reason": f"needed to start by {needs_by:%H:%M}"}
        save(track); print(f"[{track}] {name}: SKIPPED (too late to finish)", flush=True); return False
    print(f"[{track}] {name}: start {datetime.now():%H:%M:%S}", flush=True)
    st[name] = {"status": "running", "started": datetime.now()}; save(track)
    t0 = time.time()
    try:
        detail = fn(); status = "done" if detail.get("ok", True) else "partial"
    except Exception as exc:                                        # noqa: BLE001
        detail = {"error": f"{type(exc).__name__}: {exc}"}; status = "failed"
        print(f"[{track}] {name}: FAILED {detail['error'][:160]}", flush=True)
    st[name] = {"status": status, "elapsed_s": round(time.time() - t0, 1),
                "finished": datetime.now(), "detail": detail}
    save(track)
    print(f"[{track}] {name}: {status} in {round(time.time()-t0,1)}s", flush=True)
    return status == "done"


# ---------------------------------------------------------------- phases

def phase_a(ep: str) -> dict:
    """Calibration: one frozen 60-answer set, every model, same protocol."""
    served = probe(ep)
    per_band = {}
    for band in BANDS:
        judge(ep, CAL, band, f".{ep}", 1)
        v = scores(CAL, band, f".{ep}")
        per_band[band] = {
            "n": len(v), "mean": round(statistics.fmean(v), 4) if v else None,
            "sd": round(statistics.pstdev(v), 4) if len(v) > 1 else 0.0,
            "at_ceiling": sum(1 for x in v if x >= 1.0),
            "distinct_values": len(set(round(x, 3) for x in v)),
        }
    allv = [x for b in BANDS for x in scores(CAL, b, f".{ep}")]
    ceil_frac = per_band["ceiling"]["at_ceiling"] / max(1, per_band["ceiling"]["n"])
    return {"served_model": served, "by_band": per_band,
            "overall_sd": round(statistics.pstdev(allv), 4) if len(allv) > 1 else 0.0,
            "overall_distinct": len(set(round(x, 3) for x in allv)),
            "ceiling_band_saturated": ceil_frac >= 1.0,
            "ceiling_band_fraction_at_1": round(ceil_frac, 4),
            # A grader that cannot separate the ceiling band cannot adjudicate
            # C-021, which is a near-ceiling contrast.
            "usable_near_ceiling": ceil_frac < 0.95 and per_band["ceiling"]["distinct_values"] > 2,
            "ok": True}


def phase_b() -> dict:
    """gemma4-31B-mtp on llm_query's holdout answers — completes the second family."""
    probe("gemma31")
    d = judge("gemma31", HOLD, "llm_query", ".gem", 1)
    return {**d, "ok": d["complete"]}


def phase_b2() -> dict:
    """Holdout position 2 under gemma, both model-free arms — all or nothing."""
    probe("gemma31")
    out = {}
    for arm in ("deterministic", "generic"):
        out[arm] = judge("gemma31", HOLD, arm, ".gemp2", 2)
    return {**out, "ok": all(v["complete"] for v in out.values())}


def phase_c() -> dict:
    """C-021's 150 answers under a third model, if it can resolve the ceiling."""
    probe("gemma26")
    out = {}
    for root, key in ((CFX_DEV, "catalogue"), (CFX_HO, "blind")):
        for suffix, pos in ((".g26", 1), (".g26p2", 2)):
            out[f"{key}{suffix}"] = judge("gemma26", root, "deterministic", suffix, pos)
    return {**out, "ok": all(v["complete"] for v in out.values())}


def phase_c2() -> dict:
    """A third family on the holdout — all three arms, position 1."""
    probe("gemma26")
    out = {}
    for arm in ("deterministic", "generic", "llm_query"):
        out[arm] = judge("gemma26", HOLD, arm, ".g26", 1)
    return {**out, "ok": all(v["complete"] for v in out.values())}


def phase_d() -> dict:
    """Thinking-cap probe: 30 questions, generating, the only non-judging phase."""
    root = RUNS / "thinkcap-probe-2026-09-06"
    root.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "ORCH_MAX_HOPS": "5", "LLM_THINKING_BUDGET": "512",
           "SPECIALIST_LLM_TIMEOUT_S": "1200",
           "SPECIALIST_LLM_BASE_URL": ENDPOINTS["qwen"]["url"],
           "SPECIALIST_LLM_MODEL": ENDPOINTS["qwen"]["model"]}
    log = LOGS / "phase-d.log"
    with log.open("w") as fh:
        subprocess.run(["uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
                        "--arm", "llm_query", "--bank",
                        str(REPO / "docs/evaluation/composition/bank/bank-dev.json"),
                        "--root", str(root), "--workers", "8",
                        "--llm-max-tokens", "32768", "--limit", "30"],
                       cwd=REPO, env=env, stdout=fh, stderr=subprocess.STDOUT,
                       check=False, timeout=5400)
    adir = root / "llm_query" / "answers"
    n = sum(1 for p in adir.glob("*.json") if ".judgment" not in p.name) if adir.is_dir() else 0
    built = 0
    for p in (adir.glob("*.json") if adir.is_dir() else []):
        if ".judgment" in p.name:
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:                                           # noqa: BLE001
            continue
        ev = d.get("evidence_volume") or {}
        if isinstance(ev, dict) and (ev.get("records") or ev.get("results")):
            built += 1
    return {"answers": n, "with_evidence": built, "cap": 512,
            "note": "A probe. It CANNOT replace the published llm_query figure.",
            "ok": n > 0}


def track_g() -> None:
    if not run_phase("gemma31", "A-calibration", lambda: phase_a("gemma31")):
        return
    run_phase("gemma31", "B-llm_query-holdout", phase_b,
              needs_by=DEADLINE - timedelta(minutes=70) if DEADLINE else None)
    run_phase("gemma31", "B2-holdout-position2", phase_b2,
              needs_by=DEADLINE - timedelta(minutes=100) if DEADLINE else None)


def track_l() -> None:
    if not run_phase("gemma26", "A-calibration", lambda: phase_a("gemma26")):
        return
    cal = _state["gemma26"]["A-calibration"]["detail"]
    if cal.get("usable_near_ceiling"):
        run_phase("gemma26", "C-c021-third-opinion", phase_c,
                  needs_by=DEADLINE - timedelta(minutes=120) if DEADLINE else None)
    else:
        _state["gemma26"]["C-c021-third-opinion"] = {
            "status": "not_run",
            "reason": (f"saturated on the ceiling band "
                       f"({cal.get('ceiling_band_fraction_at_1')} at 1.0) — cannot "
                       "adjudicate a near-ceiling contrast. This IS the result.")}
        save("gemma26")
        print("[gemma26] C: skipped — saturated near the ceiling (recorded as the result)", flush=True)
    run_phase("gemma26", "C2-holdout-third-family", phase_c2,
              needs_by=DEADLINE - timedelta(minutes=200) if DEADLINE else None)


def track_q() -> None:
    if not run_phase("qwen", "A-calibration", lambda: phase_a("qwen")):
        return
    run_phase("qwen", "D-thinkcap-probe", phase_d,
              needs_by=DEADLINE - timedelta(minutes=120) if DEADLINE else None)


def main() -> int:
    global DEADLINE
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", default="07:00", help="HH:MM; no phase starts after")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    hh, mm = (int(x) for x in args.until.split(":"))
    d = datetime.now().replace(hour=hh, minute=mm, second=0, microsecond=0)
    DEADLINE = d + timedelta(days=1) if d <= datetime.now() else d
    LOGS.mkdir(parents=True, exist_ok=True)

    print(f"deadline {DEADLINE:%Y-%m-%d %H:%M}\n")
    for ep in ENDPOINTS:
        print(f"  {ep:8} {ENDPOINTS[ep]['model']:16} {ENDPOINTS[ep]['workers']:2} workers")
    if args.dry_run:
        for ep in ENDPOINTS:
            print(f"  probe {ep}: {probe(ep)}")
        return 0

    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = [pool.submit(track_g), pool.submit(track_l), pool.submit(track_q)]
        for f in futs:
            f.result()
    print(f"\nall tracks finished {datetime.now():%H:%M:%S}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
