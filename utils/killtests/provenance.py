"""Where every kill-test number came from.

Each output file carries a ``provenance`` header: the git commit, the models
actually served (read off a completion envelope, never the alias), the decider's
identity and temperature, the graph counts, and the seed. ``preconditions()``
records the same facts once at the start of a run, and the health call compares
against it: a served model that changes mid-run, or a graph whose counts move,
voids the stage that saw it.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from typing import Any

from .config import REPO, KillTestConfig


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def git_dirty() -> bool:
    try:
        out = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO, text=True)
        return bool(out.strip())
    except Exception:  # noqa: BLE001
        return True


def _get_json(url: str, timeout: float = 10.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - local endpoints only
        return json.loads(resp.read().decode())


def _post_json(url: str, payload: dict, timeout: float = 120.0) -> Any:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def served_model(cfg: KillTestConfig, alias: str) -> str:
    """The weights behind ``alias`` right now, from a completion's envelope."""
    body = {
        "model": alias,
        "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
        "max_tokens": 2048,
        "temperature": 0,
    }
    try:
        out = _post_json(cfg.relay_url.rstrip("/") + "/chat/completions", body)
        return str(out.get("model") or "unknown")
    except Exception as exc:  # noqa: BLE001
        return f"unreachable: {exc.__class__.__name__}"


def decider_identity(cfg: KillTestConfig) -> dict[str, Any]:
    try:
        h = _get_json(cfg.decider_url.rstrip("/") + "/health")
        return {
            "served_model_name": h.get("served_model_name"),
            "temperature": h.get("temperature"),
            "protocol": (h.get("protocol") or {}).get("template"),
            "status": h.get("status"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": f"unreachable: {exc.__class__.__name__}"}


def neo4j_count(uri: str, user: str, password: str) -> dict[str, int] | str:
    try:
        from neo4j import GraphDatabase

        with GraphDatabase.driver(uri, auth=(user, password)) as drv, drv.session() as s:
            n = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            e = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            return {"nodes": int(n), "edges": int(e)}
    except Exception as exc:  # noqa: BLE001
        return f"unreachable: {exc.__class__.__name__}"


def gremlin_count(uri: str) -> dict[str, int] | str:
    try:
        from gremlin_python.driver import client as gclient
        from gremlin_python.driver.serializer import GraphSONSerializersV3d0

        c = gclient.Client(uri, "g", message_serializer=GraphSONSerializersV3d0())
        try:
            n = c.submit("g.V().count()").all().result(timeout=30)[0]
            e = c.submit("g.E().count()").all().result(timeout=30)[0]
        finally:
            c.close()
        return {"nodes": int(n), "edges": int(e)}
    except Exception as exc:  # noqa: BLE001
        return f"unreachable: {exc.__class__.__name__}"


def preconditions(cfg: KillTestConfig, *, probe_models: bool = True, include_t1: bool = False) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "git_commit": git_commit(),
        "git_dirty": git_dirty(),
        "relay_url": cfg.relay_url,
        "served_models": {m: served_model(cfg, m) for m in cfg.relay_models} if probe_models else {},
        "decider": decider_identity(cfg),
        "graphs": {
            "attack_neo4j": neo4j_count(cfg.neo4j_uri, cfg.neo4j_user, cfg.neo4j_password),
            "capec_gremlin": gremlin_count(cfg.gremlin_uri),
        },
        "seed": cfg.seed,
        "smoke": cfg.smoke,
    }
    if include_t1:
        rec["graphs"]["t1_neo4j"] = neo4j_count(cfg.t1_neo4j_uri, cfg.neo4j_user, cfg.neo4j_password)
        rec["graphs"]["t1_gremlin"] = gremlin_count(cfg.t1_gremlin_uri)
    return rec


def header(cfg: KillTestConfig, **extra: Any) -> dict[str, Any]:
    """The light provenance block stamped on every output (no live probes)."""
    return {"git_commit": git_commit(), "seed": cfg.seed, "smoke": cfg.smoke, **extra}
