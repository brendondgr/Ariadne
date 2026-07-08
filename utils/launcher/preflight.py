#!/usr/bin/env python3
"""Ordered pre-launch checks, each with a named remediation.

Every check returns a ``CheckResult``; ``run_preflight`` runs them in order
and never raises. Severity semantics:

* ``fail`` — the workbench cannot function; the launcher aborts.
* ``warn`` — degraded but survivable (a dead graph backend, an unreachable
  LLM): the stack starts, the UI shows Dead pills, the planner degrades.
* ``pass`` — verified working, with detail for the status board.
"""

from __future__ import annotations

import importlib.util
import shutil
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

PASS, WARN, FAIL = "pass", "warn", "fail"


@dataclass(frozen=True)
class CheckResult:
    """One preflight check's outcome."""

    name: str
    status: str  # pass | warn | fail
    detail: str = ""
    remediation: str = ""

    @property
    def ok(self) -> bool:
        return self.status != FAIL


def check_npm() -> CheckResult:
    npm = shutil.which("npm")
    if not npm:
        return CheckResult(
            "npm", FAIL, "npm not found on PATH",
            "Install Node.js 18.18+ (bundles npm) from https://nodejs.org",
        )
    return CheckResult("npm", PASS, npm)


def check_python_deps() -> CheckResult:
    """uv (which provides the project env) or the key packages importable."""
    if shutil.which("uv"):
        return CheckResult("python deps", PASS, "uv on PATH (project env via `uv run`)")
    # langgraph.graph (not bare langgraph) on purpose: a stray namespace
    # package can make the bare import resolve on the system interpreter.
    missing = [
        m for m in ("fastapi", "uvicorn", "langgraph.graph")
        if importlib.util.find_spec(m) is None
    ]
    if missing:
        return CheckResult(
            "python deps", FAIL, f"not importable: {', '.join(missing)} (and `uv` is not on PATH)",
            "uv sync   (or: pip install fastapi 'uvicorn[standard]' langgraph)",
        )
    return CheckResult("python deps", PASS, "fastapi/uvicorn/langgraph importable")


def check_port(port: int, label: str) -> CheckResult:
    """A port the launcher needs must not already be in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            return CheckResult(
                f"{label} port {port}", FAIL, "already in use",
                f"Stop the process holding :{port}, or pass --port/--api-port for a free one",
            )
    return CheckResult(f"{label} port {port}", PASS, "free")


def check_node_modules(web_dir: Path, *, will_install: bool) -> CheckResult:
    if (web_dir / "node_modules").is_dir():
        return CheckResult("web dependencies", PASS, "web/node_modules present")
    if will_install:
        return CheckResult("web dependencies", WARN, "web/node_modules missing — will `npm install`")
    return CheckResult(
        "web dependencies", FAIL, "web/node_modules missing and --skip-install was passed",
        "cd web && npm install",
    )


def check_source_cards(data_dir: Path) -> CheckResult:
    cards_dir = data_dir / "source_cards"
    cards = sorted(p.name for p in cards_dir.glob("*.json")) if cards_dir.is_dir() else []
    if not cards:
        return CheckResult(
            "source cards", WARN, f"none found in {cards_dir} — queries will answer no_sources",
            "uv run main.py --build all",
        )
    return CheckResult("source cards", PASS, ", ".join(cards))


def check_graph_backends() -> list[CheckResult]:
    """Content-probe Neo4j and Gremlin through the planner's own discovery."""
    from utils.planner.agent import PlanningAgent

    try:
        agent = PlanningAgent()
        view = agent.live_sources()
    except Exception as exc:  # noqa: BLE001 - preflight must never crash
        return [CheckResult(
            "graph backends", WARN, f"probe failed: {exc}",
            "uv run main.py --docker start",
        )]
    results = []
    for dataset in sorted(view.sources):
        src = view.sources[dataset]
        if src.live:
            results.append(CheckResult(
                f"{dataset} ({src.backend})", PASS, f"live, {src.node_count} nodes"))
        else:
            remediation = (
                "uv run main.py --docker start && "
                f"uv run main.py --dataset {dataset} --graph {src.backend}"
            )
            results.append(CheckResult(
                f"{dataset} ({src.backend})", WARN, src.reason or "not live", remediation))
    return results or [CheckResult(
        "graph backends", WARN, "no sources known (no cards?)", "uv run main.py --build all")]


def check_llm_endpoint() -> CheckResult:
    from api.services.health import llm_health

    health = llm_health()
    if health.status == "live":
        return CheckResult("llm endpoint", PASS, f"{health.base_url} ({health.model})")
    return CheckResult(
        "llm endpoint", WARN,
        f"{health.base_url}: {health.reason or 'down'} — deterministic fallback will answer",
        "Start the OpenAI-compatible endpoint, or edit it in Settings",
    )


def check_langgraph_compiles() -> CheckResult:
    """Compile the orchestration super-graph — a wiring error aborts at boot."""
    try:
        import dataclasses

        from utils.orchestration.main import build_pipeline_graph
        from utils.planner.agent import PlanningAgent
        from utils.specialists.config import SpecialistConfig
        from utils.synthesis.config import SynthesisConfig

        agent = PlanningAgent()
        graph = build_pipeline_graph(
            agent, None,
            dataclasses.replace(SpecialistConfig.from_env()),
            SynthesisConfig.from_env(),
        )
        nodes = len(graph.get_graph().nodes)
        return CheckResult("langgraph pipeline", PASS, f"super-graph compiled ({nodes} nodes)")
    except Exception as exc:  # noqa: BLE001 - the whole point is to catch wiring errors
        return CheckResult(
            "langgraph pipeline", FAIL, f"{type(exc).__name__}: {exc}",
            "The orchestration graph failed to compile — fix utils/orchestration before serving",
        )


def run_preflight(
    *,
    root: Path,
    web_port: int,
    api_port: int,
    will_install: bool,
    checks: list[Callable[[], CheckResult | list[CheckResult]]] | None = None,
) -> list[CheckResult]:
    """Run every check in order; never raises. ``checks`` is injectable for tests."""
    if checks is None:
        web_dir = root / "web"
        data_dir = root / "data"
        checks = [
            check_npm,
            check_python_deps,
            lambda: check_port(web_port, "web"),
            lambda: check_port(api_port, "api"),
            lambda: check_node_modules(web_dir, will_install=will_install),
            lambda: check_source_cards(data_dir),
            check_graph_backends,
            check_llm_endpoint,
            check_langgraph_compiles,
        ]
    results: list[CheckResult] = []
    for check in checks:
        try:
            outcome = check()
        except Exception as exc:  # noqa: BLE001 - a crashing check is itself a finding
            outcome = CheckResult(getattr(check, "__name__", "check"), FAIL, f"check crashed: {exc}")
        results.extend(outcome if isinstance(outcome, list) else [outcome])
    return results


def hard_failures(results: list[CheckResult]) -> list[CheckResult]:
    return [r for r in results if r.status == FAIL]
