"""The health call: stale heartbeat -> RED, model swap -> RED, no progress -> AMBER."""
import dataclasses
import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture()
def status(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("killtests_status", REPO / "scripts/killtests_status.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["killtests_status"] = mod
    spec.loader.exec_module(mod)
    from utils.killtests import config

    cfg = dataclasses.replace(config.get(), out_dir=tmp_path)
    pre = {"served_models": {"default-model": "m1"}, "decider": {"served_model_name": "d1"},
           "graphs": {"attack_neo4j": {"nodes": 1, "edges": 1}, "capec_gremlin": {"nodes": 2, "edges": 2}}}
    (tmp_path / "preconditions.json").write_text(json.dumps(pre))
    (tmp_path / "chain.json").write_text(json.dumps({"tests": {"t2": {"status": "running"}}}))
    monkeypatch.setattr(mod, "_supervisor_running", lambda out: True)
    monkeypatch.setattr(mod, "_chain_running", lambda: True)
    monkeypatch.setattr(mod.provenance, "served_model", lambda cfg, alias: "m1")
    monkeypatch.setattr(mod.provenance, "decider_identity", lambda cfg: {"served_model_name": "d1"})
    monkeypatch.setattr(mod.provenance, "neo4j_count", lambda *a: {"nodes": 1, "edges": 1})
    monkeypatch.setattr(mod.provenance, "gremlin_count", lambda *a: {"nodes": 2, "edges": 2})
    return mod, cfg, tmp_path


def _beat(path, age_s, done=5, total=10):
    t = time.time() - age_s
    path.joinpath("heartbeat.json").write_text(json.dumps(
        {"stages": {"t2/decide": {"done": done, "total": total, "errors": 0, "started_at": t - 60, "updated_at": t}}}))


def test_green_when_fresh(status):
    mod, cfg, out = status
    _beat(out, 10)
    assert mod.check(cfg)["status"] == "GREEN"


def test_stale_heartbeat_is_red(status):
    mod, cfg, out = status
    _beat(out, 3600)
    r = mod.check(cfg)
    assert r["status"] == "RED" and any("heartbeat" in x for x in r["reasons"])


def test_model_swap_is_red(status, monkeypatch):
    mod, cfg, out = status
    _beat(out, 10)
    monkeypatch.setattr(mod.provenance, "served_model", lambda cfg, alias: "other-model")
    r = mod.check(cfg)
    assert r["status"] == "RED" and any("now serves" in x for x in r["reasons"])


def test_capec_emptied_is_red(status, monkeypatch):
    mod, cfg, out = status
    _beat(out, 10)
    monkeypatch.setattr(mod.provenance, "gremlin_count", lambda *a: {"nodes": 0, "edges": 0})
    assert mod.check(cfg)["status"] == "RED"


def test_no_progress_is_amber(status):
    mod, cfg, out = status
    _beat(out, 10)
    mod.check(cfg)
    st = json.loads((out / "status_state.json").read_text())
    st["progress_changed_at"] -= 3 * 3600
    (out / "status_state.json").write_text(json.dumps(st))
    r = mod.check(cfg)
    assert r["status"] == "AMBER" and any("no progress" in x for x in r["reasons"])


def test_done_reports_verdicts(status):
    mod, cfg, out = status
    (out / "report.done").write_text("done\n")
    (out / "report.json").write_text(json.dumps({"t2": {"verdict": "survives"}}))
    r = mod.check(cfg)
    assert r["status"] == "DONE" and r["verdicts"] == {"t2": "survives"}
