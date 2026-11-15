#!/usr/bin/env python3
"""EXP-2026-11-008: the run log's guarantees, measured (Era 2, Step 3).

    uv run python scripts/era2_runlog_check.py --out <experiment>/data

Writes ``runlog.json`` (every metric in PROTOCOL.md) and ``live-events.jsonl``
(the full event logs of the live runs).
"""

from __future__ import annotations

import argparse
import glob
import json
import multiprocessing as mp
import os
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.agent.contracts import AgentRequest, envelope_from_synthesis, validate_envelope  # noqa: E402
from utils.agent.log import RunLog  # noqa: E402
from utils.agent.runner import RegistryModel, drive, start  # noqa: E402
from utils.agent.tests.scripted import FOUR_STEPS, ScriptedModel, toolbox  # noqa: E402
from utils.llm.registry import load  # noqa: E402

REQ = AgentRequest(question="How many matches did Norway play?", graph="wwc")
SYSTEM = ("You answer questions about a football (soccer) graph by calling tools. Each tool returns a "
          "result and a set handle (set:N) that later calls can build on. Call finish with the "
          "handles your answer rests on.")


# --------------------------------------------------------------------------- #
# G1: crash at every append
# --------------------------------------------------------------------------- #


def _crash_after(path: str, rid: str, k: int) -> None:
    count = [0]
    real = RunLog.append

    def append(self, *a, **kw):
        seq = real(self, *a, **kw)
        count[0] += 1
        if count[0] == k:
            os._exit(17)
        return seq

    RunLog.append = append
    with RunLog(path) as lg:
        drive(lg, rid, ScriptedModel(FOUR_STEPS), toolbox())
    os._exit(0)


def crash_sweep(tmp: Path) -> dict:
    with RunLog(tmp / "ref.sqlite") as lg:
        ref_id = start(lg, REQ)
        ref = drive(lg, ref_id, ScriptedModel(FOUR_STEPS), toolbox())
        reference = ref.comparable()
        n_appends = len(lg.events(ref_id)) - 1
        ref_types = [e.type for e in lg.events(ref_id)]
    envelopes = [ref]
    equal, dup, exits = 0, 0, []
    for k in range(1, n_appends + 1):
        path = str(tmp / f"crash{k}.sqlite")
        with RunLog(path) as lg:
            rid = start(lg, REQ)
        p = mp.get_context("fork").Process(target=_crash_after, args=(path, rid, k))
        p.start()
        p.join()
        exits.append(p.exitcode)
        with RunLog(path) as lg:
            env = drive(lg, rid, ScriptedModel(FOUR_STEPS), toolbox())
            types = [e.type for e in lg.events(rid)]
        envelopes.append(env)
        got = env.comparable()
        got["run_id"] = reference["run_id"]
        equal += got == reference
        dup += (types.count("tool_call") != ref_types.count("tool_call")
                or types.count("tool_result") != ref_types.count("tool_result"))
    return {"crash_points": n_appends, "crash_points_equal": equal, "duplicate_calls": dup,
            "exit_codes": exits, "envelopes": envelopes}


# --------------------------------------------------------------------------- #
# E1 / E2
# --------------------------------------------------------------------------- #


def overhead(tmp: Path, n: int = 2000) -> dict:
    with RunLog(tmp / "bench.sqlite") as lg:
        rid = lg.create_run(REQ)
        payload = {"detail": "x" * 1000}
        times = []
        for _ in range(n):
            t = time.perf_counter()
            lg.append(rid, "error", payload)
            times.append((time.perf_counter() - t) * 1000)
    times.sort()
    return {"append_ms_median": round(statistics.median(times), 4),
            "append_ms_p95": round(times[int(0.95 * n)], 4), "append_n": n}


def _writer(path: str, rid: str, tag: str, n: int) -> None:
    with RunLog(path) as lg:
        for i in range(n):
            lg.append(rid, "error", {"writer": tag, "i": i})


def concurrency(tmp: Path, per: int = 250) -> dict:
    path = str(tmp / "conc.sqlite")
    with RunLog(path) as lg:
        rid = lg.create_run(REQ)
    procs = [mp.get_context("fork").Process(target=_writer, args=(path, rid, f"p{k}", per)) for k in range(4)]
    threads = [threading.Thread(target=_writer, args=(path, rid, f"t{k}", per)) for k in range(4)]
    for w in (*procs, *threads):
        w.start()
    for w in (*procs, *threads):
        w.join()
    with RunLog(path) as lg:
        ev = lg.events(rid)
    seqs_ok = [e.seq for e in ev] == list(range(1, 2 + 8 * per))
    order: dict[str, list[int]] = {}
    for e in ev[1:]:
        order.setdefault(e.payload["writer"], []).append(e.payload["i"])
    order_ok = len(order) == 8 and all(v == list(range(per)) for v in order.values())
    return {"concurrent_writers": 8, "concurrent_per_writer": per, "concurrent_seq_ok": seqs_ok and order_ok}


# --------------------------------------------------------------------------- #
# Live: E3, E4, G3
# --------------------------------------------------------------------------- #


def _live_crash(path: str, rid: str) -> None:
    real = RunLog.append

    def append(self, run_id, type, *a, **kw):
        seq = real(self, run_id, type, *a, **kw)
        if type == "model_call":
            os._exit(17)
        return seq

    RunLog.append = append
    model = RegistryModel(load().default)
    with RunLog(path) as lg:
        drive(lg, rid, model, toolbox(), system=SYSTEM)
    os._exit(0)


def live(tmp: Path, runs: int = 3) -> dict:
    spec = load().default
    model = RegistryModel(spec)
    out = {"live_model": model.served_model, "live_runs": runs, "live_answered": 0,
           "provenance_ok_runs": 0, "live": [], "envelopes": [], "events": []}
    path = tmp / "live.sqlite"
    with RunLog(path) as lg:
        for _ in range(runs):
            rid = start(lg, REQ)
            env = drive(lg, rid, model, toolbox(), system=SYSTEM)
            prov = lg.provenance(rid)
            out["live_answered"] += env.status == "answered" and [s.handle for s in env.answer.sets] == ["set:2"]
            out["provenance_ok_runs"] += prov["ok"] and prov["models"] == [model.served_model]
            out["envelopes"].append(env)
            out["live"].append({"run_id": rid, "status": env.status, "tools": env.trace.tools,
                                "steps": env.trace.steps, "repairs": env.trace.repairs,
                                "answer": env.answer.text if env.answer else None, "provenance": prov})
            out["events"] += [e.as_dict() for e in lg.events(rid)]
        # E4: kill a live run right after its first model_call is logged, then resume
        rid = start(lg, REQ)
    p = mp.get_context("fork").Process(target=_live_crash, args=(str(path), rid))
    p.start()
    p.join()
    with RunLog(path) as lg:
        before = len(lg.events(rid))
        env = drive(lg, rid, model, toolbox(), system=SYSTEM)
        ev = lg.events(rid)
        step1 = sum(1 for e in ev if e.type == "model_call" and e.payload.get("step") == 1)
        prov = lg.provenance(rid)
        out["envelopes"].append(env)
        out["live_resume"] = {"run_id": rid, "crash_exit": p.exitcode, "events_at_crash": before,
                              "status": env.status, "tools": env.trace.tools, "provenance": prov}
        out["live_resume_repeated_step1"] = step1 - 1
        out["provenance_ok_runs"] += prov["ok"]
        out["events"] += [e.as_dict() for e in ev]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-live", action="store_true")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="era2-runlog-"))

    res: dict = {}
    crash = crash_sweep(tmp)
    envelopes = crash.pop("envelopes")
    res.update(crash)
    res.update(overhead(tmp))
    res.update(concurrency(tmp))

    fast = 0
    for f in sorted(glob.glob(str(REPO / "docs/evaluation/answers/*.json"))):
        d = json.loads(Path(f).read_text())
        if isinstance(d.get("answer"), dict):
            envelopes.append(envelope_from_synthesis(d["answer"], run_id=f"fast-{d['id']}"))
            fast += 1
    res["fast_path_envelopes"] = fast

    events = []
    if not args.no_live:
        lv = live(tmp)
        envelopes += lv.pop("envelopes")
        events = lv.pop("events")
        res.update(lv)

    valid = 0
    for env in envelopes:
        try:
            validate_envelope(json.loads(env.model_dump_json()))
            valid += 1
        except Exception:  # noqa: BLE001
            pass
    res["envelopes_valid"], res["envelopes_total"] = valid, len(envelopes)

    (out / "runlog.json").write_text(json.dumps(res, indent=1, default=str))
    with open(out / "live-events.jsonl", "w") as fh:
        for e in events:
            fh.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k not in ("live", "live_resume", "exit_codes")}, indent=1))
    print("live:", json.dumps(res.get("live"), indent=1, default=str)[:3000])
    print("live_resume:", json.dumps(res.get("live_resume"), default=str)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
