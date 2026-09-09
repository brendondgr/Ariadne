#!/usr/bin/env python3
"""Repeat grading sessions, so tonight's cross-family number can be interpreted.

`scripts/grader_repeats.py` states the question this answers: *"whether a
between-model offset measured at n=1 survives the within-model spread. If sd
across repeats is of the same order as the offset, the offset was noise and must
be withdrawn."*

Tonight measures qwen against gemma on the same 568 answers. Without gemma's own
spread that comparison cannot be read at all — any gap between the two graders
would be indistinguishable from one grader being noisy. qwen's spread is on
record at 0.0050 (EXP-2026-08-021, five sessions); gemma's is unmeasured.

So: after the main cross-family pass finishes, keep the endpoint busy with
repeat sessions at a **fixed grading position** until the deadline, then compute
the spread and a paired bootstrap interval on the arm gap, and append both to the
morning report.

Runs as a **separate process** from the orchestrator on purpose — it must not be
able to disturb a run already in flight. It only ever adds files with new
suffixes, and `judge_answers` skips any case already judged under a suffix, so a
restart costs nothing.

    uv run python scripts/overnight_validation_passes.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from statistics import fmean, stdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from scripts import overnight_two_track as ot  # noqa: E402

#: Leave the endpoint half an hour before it disappears; a pass that cannot
#: finish is a partial session, and a partial session is not a session.
REPEAT_DEADLINE = ot.GEMMA_DEADLINE - timedelta(minutes=30)
#: Position 1 throughout, matching the ``.gemma`` pass, because spread is only
#: interpretable across sessions graded in the same position -- EXP-2026-08-022
#: measured a ~0.01 effect for position alone.
POSITION = 1
OUT = ot.BANK_DIR / "grader-spread-2026-09-04.json"
LOG = REPO / "logs/overnight-2026-09-04/validation.log"


def _log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as fh:
        fh.write(line + "\n")


def _phase_status(name: str) -> str | None:
    if not ot.STATE.is_file():
        return None
    try:
        return json.loads(ot.STATE.read_text())["phases"].get(name, {}).get("status")
    except (json.JSONDecodeError, KeyError):
        return None


def wait_for(name: str, *, until: datetime) -> bool:
    """Block until a phase reports done, or give up at ``until``."""
    while datetime.now() < until:
        status = _phase_status(name)
        if status == "done":
            return True
        if status in {"failed", "not_run"}:
            _log(f"{name} is {status}; nothing to repeat")
            return False
        time.sleep(60)
    _log(f"gave up waiting for {name}")
    return False


def driver_running() -> bool:
    return subprocess.run(["pgrep", "-f", "overnight_two_track"],
                          capture_output=True).returncode == 0


def repeat_sessions() -> list[str]:
    """Grade the same answers again, at a fixed position, until the deadline."""
    done: list[str] = []
    index = 3                       # .gemma and .gemma2 already exist
    while datetime.now() < REPEAT_DEADLINE:
        suffix = f".gemma_r{index}"
        started = time.time()
        try:
            for arm in ot.ARMS:
                if datetime.now() >= REPEAT_DEADLINE:
                    raise TimeoutError("deadline reached mid-session")
                summary = ot._judge(ot.POST_REPAIR, arm, url=ot.GEMMA_URL,
                                    model=ot.GEMMA_MODEL, workers=ot.GEMMA_WORKERS,
                                    suffix=suffix, position=POSITION)
                _log(f"{suffix} {arm}: {json.dumps(summary)[:140]}")
        except Exception as exc:                                # noqa: BLE001
            # A session cut short is discarded rather than averaged in: a pass
            # over a subset is not comparable with a pass over all of it.
            _log(f"{suffix} abandoned ({type(exc).__name__}: {exc}); not counted")
            break
        done.append(suffix)
        _log(f"{suffix} complete in {time.time() - started:.0f}s "
             f"({len(done)} repeat session(s) so far)")
        index += 1
    return done


def _per_case(arm: str, suffix: str) -> dict[str, float]:
    out: dict[str, float] = {}
    adir = ot.POST_REPAIR / arm / "answers"
    for path in sorted(adir.glob(f"*.judgment{suffix}.json")):
        stem = path.name.split(".judgment")[0]
        if path.name != f"{stem}.judgment{suffix}.json":
            continue
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if payload.get("correctness") is not None:
            out[payload.get("case_id", stem)] = payload["correctness"]
    return out


def analyse(gemma_suffixes: list[str]) -> dict:
    """Within-grader spread, and a paired interval on the arm gap."""
    from utils.evaluation.stats import bootstrap_ci

    result: dict = {"position": POSITION, "sessions": {}}
    for grader, suffixes in (("qwen", ["", ".pass2"]), ("gemma", gemma_suffixes)):
        per_session: dict[str, dict[str, float]] = {}
        for suffix in suffixes:
            cells = {arm: _per_case(arm, suffix) for arm in ot.ARMS}
            if not all(cells.values()):
                continue
            per_session[suffix or ".pass1"] = {
                arm: round(fmean(v.values()), 4) for arm, v in cells.items()
            }
            # The contrast is computed WITHIN a session so a session-level
            # offset cancels rather than inflating the spread.
            per_session[suffix or ".pass1"]["gap"] = round(
                fmean(cells["generic"].values()) - fmean(cells["deterministic"].values()), 4
            )
        result["sessions"][grader] = per_session
        gaps = [s["gap"] for s in per_session.values()]
        result.setdefault("spread", {})[grader] = {
            "n_sessions": len(gaps),
            "mean_gap": round(fmean(gaps), 4) if gaps else None,
            "sd_gap": round(stdev(gaps), 4) if len(gaps) > 1 else None,
        }

    # Paired bootstrap over the questions, on the pass-averaged per-case scores.
    # D-010 and EXP-2026-09-005 I-1 both record that the gap has no interval;
    # this is the cheapest thing that gives it one.
    def _avg(arm: str, suffixes: list[str]) -> dict[str, float]:
        acc: dict[str, list[float]] = {}
        for suffix in suffixes:
            for cid, v in _per_case(arm, suffix).items():
                acc.setdefault(cid, []).append(v)
        return {cid: fmean(v) for cid, v in acc.items()}

    for grader, suffixes in (("qwen", ["", ".pass2"]), ("gemma", gemma_suffixes)):
        det, gen = _avg("deterministic", suffixes), _avg("generic", suffixes)
        shared = sorted(set(det) & set(gen))
        if len(shared) < 30:
            continue
        diffs = [gen[c] - det[c] for c in shared]
        observed, lo, hi = bootstrap_ci(diffs, fmean, n_resamples=2000, seed=1729)
        result.setdefault("paired_bootstrap", {})[grader] = {
            "n_paired": len(shared),
            "mean_gap": round(observed, 4),
            "ci95": [round(lo, 4), round(hi, 4)],
            "excludes_zero": bool(lo > 0 or hi < 0),
        }

    qg = (result.get("spread", {}).get("qwen") or {}).get("mean_gap")
    gg = (result.get("spread", {}).get("gemma") or {}).get("mean_gap")
    sd = (result.get("spread", {}).get("gemma") or {}).get("sd_gap")
    if qg is not None and gg is not None:
        offset = round(gg - qg, 4)
        result["between_grader"] = {
            "qwen_gap": qg, "gemma_gap": gg, "offset": offset,
            "gemma_sd": sd,
            "verdict": (
                "offset is within the within-grader spread — do not read it as a family effect"
                if sd is not None and abs(offset) <= sd
                else "offset exceeds the within-grader spread"
                if sd is not None else "gemma spread not measurable (one session)"
            ),
        }
    return result


def append_to_report(result: dict, sessions: list[str]) -> None:
    md_path = REPO / "docs/research/reports/2026-09-04-overnight-report.md"
    if not md_path.is_file():
        _log("no report to append to")
        return
    lines = ["", "## Validation — repeat grading sessions", ""]
    lines.append(f"Repeat sessions run at position {POSITION}: "
                 f"**{len(sessions)}** beyond the two counterbalanced passes.")
    lines.append("")
    lines.append("| grader | sessions | mean gap (generic − deterministic) | sd across sessions |")
    lines.append("|---|---:|---:|---:|")
    for grader, cell in (result.get("spread") or {}).items():
        lines.append(f"| {grader} | {cell['n_sessions']} | {cell['mean_gap']} | "
                     f"{cell['sd_gap'] if cell['sd_gap'] is not None else '—'} |")
    if result.get("paired_bootstrap"):
        lines += ["", "Paired percentile bootstrap over questions "
                      "(2000 resamples, seed 1729):", "",
                  "| grader | paired n | mean gap | 95% CI | excludes zero |",
                  "|---|---:|---:|---|---|"]
        for grader, cell in result["paired_bootstrap"].items():
            lines.append(f"| {grader} | {cell['n_paired']} | {cell['mean_gap']} | "
                         f"[{cell['ci95'][0]}, {cell['ci95'][1]}] | "
                         f"{'yes' if cell['excludes_zero'] else '**no**'} |")
    if result.get("between_grader"):
        b = result["between_grader"]
        lines += ["", f"**Between graders:** qwen {b['qwen_gap']}, gemma {b['gemma_gap']}, "
                      f"offset {b['offset']}, gemma sd {b['gemma_sd']}. {b['verdict']}."]
    lines += ["", "What repeats measure, and what they do not: re-grading answers that do "
                  "not move measures the *precision of the grader*. It says nothing about "
                  "the accuracy of the arms and nothing about pipeline stability — `D-010` "
                  "stays open for the arms, and only re-running the pipeline can close it.", ""]
    md = md_path.read_text() + "\n".join(lines) + "\n"
    md_path.write_text(md)
    try:
        from scripts.morning_report import render_pdf

        ok = render_pdf(md, md_path.with_suffix(".pdf"))
        _log(f"report re-rendered with the validation section; pdf={ok}")
    except Exception as exc:                                    # noqa: BLE001
        _log(f"pdf re-render failed ({type(exc).__name__}: {exc}); markdown is current")


def main() -> int:
    _log(f"waiting for the cross-family pass; repeats stop at {REPEAT_DEADLINE:%H:%M}")
    if not wait_for("B1-gemma-regrade", until=REPEAT_DEADLINE):
        return 1
    sessions = repeat_sessions()
    _log(f"{len(sessions)} repeat session(s) complete: {sessions}")

    # Do not touch the report until the orchestrator has finished writing it.
    while driver_running() and datetime.now() < ot.GEMMA_DEADLINE:
        time.sleep(60)

    result = analyse([".gemma", *sessions])
    result["repeat_sessions"] = sessions
    OUT.write_text(json.dumps(result, indent=1) + "\n")
    _log(f"analysis -> {OUT}")
    append_to_report(result, sessions)
    print(json.dumps(result.get("spread"), indent=1))
    print(json.dumps(result.get("between_grader"), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
