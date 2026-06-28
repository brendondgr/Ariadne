#!/usr/bin/env python3
"""Single-command pipeline runner for ``uv run main.py --yolo-all``.

Orchestrates download → build → credentials check → docker start →
load ATT&CK → Neo4j → load CAPEC → Gremlin → verify, printing a
live prefix line per step and a Unicode summary table at the end.
"""

from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from utils.config import env_str
from utils.download import DatasetDownloader
from utils.graph_loader.config import (
    DEFAULT_GREMLIN_URI,
    DEFAULT_NEO4J_PASSWORD,
    DEFAULT_NEO4J_URI,
    LoaderConfig,
)
from utils.graph_loader.main import run_graph_command
from utils.infrastructure import docker_start
from utils.kg_builder import KGBuildRunner

StepStatus = Literal["ok", "skipped", "failed", "pending"]

_COL_STEP = 38
_COL_STATUS = 10
_COL_DETAIL = 45


@dataclass
class StepResult:
    name: str
    status: StepStatus = "pending"
    detail: str = ""
    duration_s: float = 0.0

    @property
    def symbol(self) -> str:
        return {"ok": "✓", "skipped": "—", "failed": "✗", "pending": "·"}[self.status]

    @property
    def status_label(self) -> str:
        return {
            "ok": "OK",
            "skipped": "Skipped",
            "failed": "FAILED",
            "pending": "Pending",
        }[self.status]


def _cell(text: str, width: int) -> str:
    """Left-align text in a fixed-width cell, truncating with '…' if needed."""
    if len(text) > width:
        return text[: width - 1] + "…"
    return text.ljust(width)


def print_summary_table(results: list[StepResult]) -> None:
    """Render a Unicode box-drawing summary table to stdout."""
    w_step = _COL_STEP
    w_status = _COL_STATUS
    w_detail = _COL_DETAIL

    top = f"╔{'═' * (w_step + 2)}╤{'═' * (w_status + 2)}╤{'═' * (w_detail + 2)}╗"
    hdr_sep = f"╠{'═' * (w_step + 2)}╪{'═' * (w_status + 2)}╪{'═' * (w_detail + 2)}╣"
    row_sep = f"╟{'─' * (w_step + 2)}┼{'─' * (w_status + 2)}┼{'─' * (w_detail + 2)}╢"
    bot = f"╚{'═' * (w_step + 2)}╧{'═' * (w_status + 2)}╧{'═' * (w_detail + 2)}╝"

    def row(step: str, status: str, detail: str) -> str:
        return (
            f"║ {_cell(step, w_step)} │ {_cell(status, w_status)} │ {_cell(detail, w_detail)} ║"
        )

    print()
    print(top)
    print(row("Step", "Status", "Detail"))
    print(hdr_sep)
    for i, r in enumerate(results):
        status_str = f"{r.symbol} {r.status_label}"
        dur = f" ({r.duration_s:.1f}s)" if r.duration_s > 0 else ""
        print(row(r.name, status_str, r.detail + dur))
        if i < len(results) - 1:
            print(row_sep)
    print(bot)

    failed = [r for r in results if r.status == "failed"]
    if failed:
        names = ", ".join(r.name for r in failed)
        print(f"\n  ✗ {len(failed)} step(s) failed: {names}\n")
    else:
        print("\n  All steps completed successfully.\n")


def _tcp_up(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _parse_bolt_host_port(uri: str) -> tuple[str, int]:
    uri = uri.removeprefix("bolt://").split("/")[0]
    host, _, port = uri.partition(":")
    return host or "127.0.0.1", int(port or 7687)


def _parse_ws_host_port(uri: str) -> tuple[str, int]:
    stripped = uri.split("://", 1)[1].split("/")[0]
    host, _, port = stripped.partition(":")
    return host or "127.0.0.1", int(port or 8182)


def _read_runtime_manifest(config: LoaderConfig, dataset: str, backend: str) -> dict | None:
    path = config.runtime_dir(dataset, backend) / "load_manifest.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class YoloRunner:
    """Orchestrates the full Ariadne data pipeline in a single run."""

    STEPS = [
        "1. Download Datasets",
        "2. Build Artifacts",
        "3. Configure Credentials",
        "4. Start Docker Infrastructure",
        "5. Load ATT&CK → Neo4j",
        "6. Load CAPEC → Gremlin",
        "7. Verify Graphs",
    ]

    def __init__(self) -> None:
        self._config = LoaderConfig.from_data_dir()
        self._data_dir = self._config.data_dir

    # ── helpers ──────────────────────────────────────────────────────────────

    def _timed(self, fn, *args, **kwargs):
        t0 = time.monotonic()
        result = fn(*args, **kwargs)
        return result, time.monotonic() - t0

    def _print_running(self, idx: int, name: str) -> None:
        total = len(self.STEPS)
        print(f"  → [{idx}/{total}] {name}...", end="", flush=True)

    def _print_result(self, r: StepResult, idx: int) -> None:
        total = len(self.STEPS)
        dur = f" ({r.duration_s:.1f}s)" if r.duration_s > 0 else ""
        detail = f" — {r.detail}" if r.detail else ""
        print(f"\r  {r.symbol} [{idx}/{total}] {r.name}{dur}{detail}          ")

    # ── pipeline steps ───────────────────────────────────────────────────────

    def _step_download(self) -> StepResult:
        r = StepResult(self.STEPS[0])
        downloader = DatasetDownloader(force=False)

        attack_file = (
            downloader.attack_dir / f"enterprise-attack-{downloader.attack_version}.json"
        )
        capec_file = downloader.capec_dir / f"capec_v{downloader.capec_version}.xml"
        already_have = attack_file.exists() and capec_file.exists()

        try:
            _, dur = self._timed(downloader.download_all)
            r.status = "skipped" if already_have else "ok"
            r.detail = (
                f"ATT&CK v{downloader.attack_version}, CAPEC v{downloader.capec_version}"
                + (" (already present)" if already_have else "")
            )
            r.duration_s = dur
        except Exception as exc:
            r.status = "failed"
            r.detail = str(exc)
        return r

    def _step_build(self) -> StepResult:
        r = StepResult(self.STEPS[1])
        attack_manifest = self._data_dir / "graphs" / "attack" / "canonical" / "manifest.json"
        capec_manifest = self._data_dir / "graphs" / "capec" / "canonical" / "manifest.json"
        already_built = attack_manifest.exists() and capec_manifest.exists()

        if already_built:
            r.status = "skipped"
            r.detail = "Canonical manifests already present"
            return r

        try:
            runner = KGBuildRunner()
            _, dur = self._timed(runner.build_all)
            r.status = "ok"
            r.detail = "attack + capec"
            r.duration_s = dur
        except Exception as exc:
            r.status = "failed"
            r.detail = str(exc)
        return r

    def _step_credentials(self) -> StepResult:
        r = StepResult(self.STEPS[2])
        current_pw = env_str("NEO4J_PASSWORD", DEFAULT_NEO4J_PASSWORD)
        if current_pw == DEFAULT_NEO4J_PASSWORD:
            r.status = "skipped"
            r.detail = "Using defaults — run --neo4j-login to customize"
        else:
            r.status = "skipped"
            r.detail = "Already configured in .env"
        return r

    def _step_docker_start(self) -> StepResult:
        r = StepResult(self.STEPS[3])
        neo4j_host, neo4j_port = _parse_bolt_host_port(
            env_str("NEO4J_URI", DEFAULT_NEO4J_URI)
        )
        gremlin_host, gremlin_port = _parse_ws_host_port(
            env_str("GREMLIN_URI", DEFAULT_GREMLIN_URI)
        )

        if _tcp_up(neo4j_host, neo4j_port) and _tcp_up(gremlin_host, gremlin_port):
            r.status = "skipped"
            r.detail = "Neo4j + Gremlin already running"
            return r

        try:
            _, dur = self._timed(docker_start)
            r.status = "ok"
            r.detail = f"Neo4j :{neo4j_port}, Gremlin :{gremlin_port}"
            r.duration_s = dur
        except Exception as exc:
            r.status = "failed"
            r.detail = str(exc)
        return r

    def _step_load_attack(self) -> StepResult:
        r = StepResult(self.STEPS[4])
        try:
            _, dur = self._timed(run_graph_command, dataset="attack", graph="neo4j")
            r.duration_s = dur
            manifest = _read_runtime_manifest(self._config, "attack", "neo4j")
            if manifest:
                nodes = manifest.get("nodes_loaded", "?")
                edges = manifest.get("edges_loaded", "?")
                r.detail = f"{nodes:,} nodes, {edges:,} relationships"
            else:
                r.detail = "loaded"
            r.status = "ok"
        except Exception as exc:
            r.status = "failed"
            r.detail = str(exc)
        return r

    def _step_load_capec(self) -> StepResult:
        r = StepResult(self.STEPS[5])
        try:
            _, dur = self._timed(run_graph_command, dataset="capec", graph="gremlin")
            r.duration_s = dur
            manifest = _read_runtime_manifest(self._config, "capec", "gremlin")
            if manifest:
                nodes = manifest.get("nodes_loaded", "?")
                r.detail = f"{nodes:,} vertices"
            else:
                r.detail = "loaded"
            r.status = "ok"
        except Exception as exc:
            r.status = "failed"
            r.detail = str(exc)
        return r

    def _step_verify(self) -> StepResult:
        r = StepResult(self.STEPS[6])
        parts: list[str] = []
        failed = False
        t0 = time.monotonic()

        for dataset, backend in [("attack", "neo4j"), ("capec", "gremlin")]:
            label = "ATT&CK" if dataset == "attack" else "CAPEC"
            try:
                run_graph_command(dataset=dataset, graph="verify")
                parts.append(f"{label} ✓")
            except Exception as exc:
                parts.append(f"{label} ✗ ({exc})")
                failed = True

        r.duration_s = time.monotonic() - t0
        r.detail = "  ".join(parts)
        r.status = "failed" if failed else "ok"
        return r

    # ── orchestrator ─────────────────────────────────────────────────────────

    def run(self) -> list[StepResult]:
        """Run the full pipeline; returns all StepResults."""
        print("\n  Ariadne — full pipeline (--yolo-all)\n")

        step_fns = [
            self._step_download,
            self._step_build,
            self._step_credentials,
            self._step_docker_start,
            self._step_load_attack,
            self._step_load_capec,
            self._step_verify,
        ]

        # Steps that abort the pipeline on failure (index 0-based, steps 1-4)
        ABORT_ON_FAIL = {0, 1, 2, 3}

        results: list[StepResult] = []
        aborted = False

        for i, fn in enumerate(step_fns):
            step_num = i + 1
            name = self.STEPS[i]

            if aborted:
                r = StepResult(name, status="skipped", detail="Earlier step failed")
                results.append(r)
                self._print_result(r, step_num)
                continue

            self._print_running(step_num, name)
            r = fn()
            results.append(r)
            self._print_result(r, step_num)

            if r.status == "failed" and i in ABORT_ON_FAIL:
                aborted = True

        print_summary_table(results)
        return results
