#!/usr/bin/env python3
"""The kill-test health call: GREEN / AMBER / RED / DONE, from facts, not process lists.

    uv run python scripts/killtests_status.py          # or: make killtests-status
    uv run python scripts/killtests_status.py --json

Checks, in order:

- **done**: ``report.done`` exists -> DONE, with the three verdicts.
- **processes**: supervisor and chain alive (interpreter-field match, never ``pgrep -f``).
- **heartbeat**: newest stage update under 10 minutes old; progress moved since
  the previous call (stored in ``status_state.json``).
- **errors**: every stage's error count under 5% of its finished items.
- **models**: the relay's served model and the decider's served model are the
  ones recorded in ``preconditions.json``. A change is RED: a stage that saw two
  models mixes them, and must be re-run.
- **stores**: ATT&CK and CAPEC counts unchanged; the T1 stores non-empty.
- **disk**: more than 10 GB free.

Every call appends one line to ``status.log``; a RED call also appends to
``ALERTS.md``. Exit code: 0 GREEN/DONE, 1 AMBER, 2 RED.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.config import load_env  # noqa: E402

load_env()

from utils.killtests import config, heartbeat, provenance  # noqa: E402

STALE_S = 600
NO_PROGRESS_S = 1800


def _chain_running() -> bool:
    """A python process whose FIRST argument is the chain script.

    Matching the whole command line would also match any shell that merely
    mentions the script (the closeout_supervise.sh lesson); the interpreter
    field plus the first argument cannot be faked that way.
    """
    out = subprocess.run(["ps", "-eo", "pid,args", "--no-headers"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and "python" in Path(parts[1]).name and parts[2].endswith("scripts/killtests_run.py"):
            return True
    return False


def _supervisor_running(out: Path) -> bool:
    """The pid the supervisor wrote, alive, and still the supervisor."""
    try:
        pid = int((out / "supervisor.pid").read_text().strip())
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        return False
    return "killtests_supervise.sh" in cmd


def check(cfg, *, probe_models: bool = True) -> dict:
    out = cfg.out_dir
    now = time.time()
    reasons: list[tuple[str, str]] = []  # (level, text)
    info: dict = {}

    def flag(level: str, text: str) -> None:
        reasons.append((level, text))

    if (out / "report.done").exists():
        rep = json.loads((out / "report.json").read_text())
        return {"status": "DONE", "verdicts": {t: r.get("verdict") for t, r in rep.items()}, "reasons": []}

    chain = {}
    try:
        chain = json.loads((out / "chain.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    info["tests"] = {t: v.get("status") for t, v in (chain.get("tests") or {}).items()}
    for t, v in (chain.get("tests") or {}).items():
        if v.get("status") == "failed":
            flag("AMBER", f"{t} failed last attempt: {v.get('error', '')[:160]}")

    sup = _supervisor_running(out)
    run = _chain_running()
    info["supervisor_alive"], info["chain_alive"] = sup, run
    if not sup:
        flag("RED", "supervisor not running")
    if not run:
        flag("AMBER" if sup else "RED", "chain not running")

    hb = heartbeat.read(out) or {}
    stages = hb.get("stages") or {}
    newest = max((s.get("updated_at", 0) for s in stages.values()), default=0)
    info["heartbeat_age_s"] = round(now - newest) if newest else None
    if not newest:
        flag("AMBER", "no heartbeat yet")
    elif now - newest > STALE_S:
        flag("RED" if run else "AMBER", f"heartbeat {round((now - newest) / 60)} min old")
    progress = {k: v.get("done", 0) for k, v in stages.items()}
    info["progress"] = {k: f"{v.get('done')}/{v.get('total')}" for k, v in stages.items()}
    eta = {}
    for k, v in stages.items():
        done, total, started = v.get("done", 0), v.get("total", 0), v.get("started_at", now)
        if 0 < done < total and now > started:
            eta[k] = round((total - done) * (now - started) / done / 60, 1)
        errs = v.get("errors", 0)
        if done and errs / done > 0.05:
            flag("AMBER", f"{k}: {errs} errors in {done} items")
    info["eta_min"] = eta

    state_p = out / "status_state.json"
    try:
        prev = json.loads(state_p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        prev = {}
    if prev.get("progress") == progress and run and now - prev.get("progress_changed_at", now) > NO_PROGRESS_S:
        flag("AMBER", f"no progress for {round((now - prev['progress_changed_at']) / 60)} min")
    changed_at = now if prev.get("progress") != progress else prev.get("progress_changed_at", now)
    state_p.write_text(json.dumps({"progress": progress, "progress_changed_at": changed_at, "checked_at": now}))

    try:
        pre = json.loads((out / "preconditions.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        pre = {}
        flag("AMBER", "preconditions.json missing")
    if probe_models and pre:
        for alias, served in (pre.get("served_models") or {}).items():
            now_served = provenance.served_model(cfg, alias)
            info.setdefault("served_models", {})[alias] = now_served
            if now_served != served:
                flag("RED", f"relay alias {alias} now serves {now_served!r}, run started on {served!r}")
        dec = provenance.decider_identity(cfg)
        info["decider"] = dec.get("served_model_name") or dec.get("status")
        want = (pre.get("decider") or {}).get("served_model_name")
        if dec.get("served_model_name") != want:
            flag("RED", f"decider now {dec.get('served_model_name') or dec.get('status')!r}, run started on {want!r}")

    g = pre.get("graphs") or {}
    now_a = provenance.neo4j_count(cfg.neo4j_uri, cfg.neo4j_user, cfg.neo4j_password)
    now_c = provenance.gremlin_count(cfg.gremlin_uri)
    info["stores"] = {"attack": now_a, "capec": now_c}
    if g.get("attack_neo4j") and now_a != g["attack_neo4j"]:
        flag("RED", f"ATT&CK store changed: {now_a} vs {g['attack_neo4j']}")
    if g.get("capec_gremlin") and now_c != g["capec_gremlin"]:
        flag("RED", f"CAPEC store changed: {now_c} vs {g['capec_gremlin']} (a Gremlin restart empties it)")
    if "t1" in info["tests"] and info["tests"].get("t1") != "done":
        t1n = provenance.neo4j_count(cfg.t1_neo4j_uri, cfg.neo4j_user, cfg.neo4j_password)
        t1g = provenance.gremlin_count(cfg.t1_gremlin_uri)
        info["stores"]["t1"] = {"neo4j": t1n, "gremlin": t1g}
        for name, c in (("T1 neo4j", t1n), ("T1 gremlin", t1g)):
            if not isinstance(c, dict) or not c.get("nodes"):
                flag("RED", f"{name} empty or unreachable: {c}")

    free_gb = shutil.disk_usage(out).free / 1e9
    info["disk_free_gb"] = round(free_gb, 1)
    if free_gb < 10:
        flag("RED", f"only {free_gb:.1f} GB free")

    level = "GREEN"
    if any(l == "AMBER" for l, _ in reasons):
        level = "AMBER"
    if any(l == "RED" for l, _ in reasons):
        level = "RED"
    return {"status": level, "reasons": [f"{l}: {t}" for l, t in reasons], **info}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-model-probe", action="store_true")
    args = ap.parse_args(argv)
    cfg = config.get()
    r = check(cfg, probe_models=not args.no_model_probe)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    line = f"{stamp} {r['status']} " + ("; ".join(r["reasons"]) or "ok") + f" | {json.dumps(r.get('progress') or r.get('verdicts'))}"
    out = cfg.out_dir
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "status.log", "a") as fh:
        fh.write(line + "\n")
    if r["status"] == "RED":
        with open(out / "ALERTS.md", "a") as fh:
            fh.write(f"## {stamp} RED (health call)\n\n" + "\n".join(f"- {x}" for x in r["reasons"]) + "\n\n")
    if args.json:
        print(json.dumps(r, indent=1, default=str))
    else:
        print(line)
        for k in ("tests", "progress", "eta_min", "served_models", "decider", "disk_free_gb", "verdicts"):
            if r.get(k) is not None:
                print(f"  {k}: {json.dumps(r[k], default=str)}")
    return {"GREEN": 0, "DONE": 0, "AMBER": 1, "RED": 2}[r["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
