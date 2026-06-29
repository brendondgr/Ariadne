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
from utils.recovery import classify_failure, retry_with_backoff

StepStatus = Literal["ok", "skipped", "failed", "needs_input", "pending"]

# Returned by ``YoloRunner._guarded`` when the wrapped action could not be
# completed; distinguishes a guarded failure from a legitimately ``None`` result.
_GUARD_FAILED = object()

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
        return {
            "ok": "✓",
            "skipped": "—",
            "failed": "✗",
            "needs_input": "?",
            "pending": "·",
        }[self.status]

    @property
    def status_label(self) -> str:
        return {
            "ok": "OK",
            "skipped": "Skipped",
            "failed": "FAILED",
            "needs_input": "NEEDS INPUT",
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
    needs_input = [r for r in results if r.status == "needs_input"]
    if failed:
        names = ", ".join(r.name for r in failed)
        print(f"\n  ✗ {len(failed)} step(s) failed: {names}")
    if needs_input:
        names = ", ".join(r.name for r in needs_input)
        print(f"\n  ? {len(needs_input)} step(s) need human input: {names}")
        print("    Review the detail above, resolve the issue, then re-run --yolo-all.")
    if failed or needs_input:
        print()
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

    def _note_retry(self, attempt: int, exc: BaseException, delay: float) -> None:
        print(
            f"\n    ↻ transient error ({type(exc).__name__}); "
            f"retry {attempt} in {delay:.0f}s...",
            flush=True,
        )

    def _guarded(self, r: StepResult, action, *, retries: int = 2):
        """Run ``action`` with bounded retry on transient errors.

        On success returns the action's value and records the elapsed time on
        ``r``. On failure, classifies the error and sets ``r`` accordingly —
        ``failed`` for transient errors that exhausted their retries,
        ``needs_input`` for errors that require human intervention — then
        returns the ``_GUARD_FAILED`` sentinel so the caller can stop.
        """
        try:
            result, dur = self._timed(
                retry_with_backoff,
                action,
                retries=retries,
                base_delay=2.0,
                should_retry=lambda exc: classify_failure(exc) == "transient",
                on_retry=self._note_retry,
            )
            r.duration_s = dur
            return result
        except Exception as exc:  # noqa: BLE001 — classified into status below
            if classify_failure(exc) == "needs_human":
                r.status = "needs_input"
                r.detail = f"needs human input: {exc}"
            else:
                r.status = "failed"
                r.detail = str(exc)
            return _GUARD_FAILED

    def _invalid_canonical_datasets(self) -> list[str]:
        """Return datasets whose on-disk canonical artifacts fail validation."""
        from utils.kg_builder.validate import validate_canonical_artifacts

        invalid: list[str] = []
        for dataset in ("attack", "capec"):
            canonical_dir = self._data_dir / "graphs" / dataset / "canonical"
            try:
                validate_canonical_artifacts(canonical_dir)
            except Exception:  # noqa: BLE001 — any failure means "rebuild this"
                invalid.append(dataset)
        return invalid

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

        stale: list[str] = []
        if already_built:
            # "Graph already existing" path: validate the on-disk artifacts. If
            # they are consistent, skip; if they are stale/corrupt, fall through
            # to a clean rebuild (the builder backs the old copy up first).
            stale = self._invalid_canonical_datasets()
            if not stale:
                r.status = "skipped"
                r.detail = "Canonical manifests already present (validated)"
                return r
            print(
                f"\n    ⚠ stale canonical artifacts detected ({', '.join(stale)}); "
                "backing up and rebuilding clean...",
                flush=True,
            )

        try:
            runner = KGBuildRunner()
            _, dur = self._timed(runner.build_all)
            r.status = "ok"
            r.duration_s = dur
            r.detail = (
                f"rebuilt clean after stale artifacts ({', '.join(stale)})"
                if stale
                else "attack + capec"
            )
        except Exception as exc:
            if classify_failure(exc) == "transient":
                r.status = "failed"
                r.detail = str(exc)
            else:
                # A freshly cleaned rebuild that still fails (e.g. schema
                # validation) is a genuine data/schema bug, not a recoverable
                # stale-state condition — escalate rather than loop.
                r.status = "needs_input"
                r.detail = f"needs human input: {exc}"
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

        if self._guarded(r, docker_start) is _GUARD_FAILED:
            return r
        r.status = "ok"
        r.detail = f"Neo4j :{neo4j_port}, Gremlin :{gremlin_port}"
        return r

    def _step_load_attack(self) -> StepResult:
        r = StepResult(self.STEPS[4])
        if (
            self._guarded(r, lambda: run_graph_command(dataset="attack", graph="neo4j"))
            is _GUARD_FAILED
        ):
            return r
        manifest = _read_runtime_manifest(self._config, "attack", "neo4j")
        if manifest:
            nodes = manifest.get("nodes_loaded", "?")
            edges = manifest.get("edges_loaded", "?")
            r.detail = f"{nodes:,} nodes, {edges:,} relationships"
        else:
            r.detail = "loaded"
        r.status = "ok"
        return r

    def _step_load_capec(self) -> StepResult:
        r = StepResult(self.STEPS[5])
        if (
            self._guarded(r, lambda: run_graph_command(dataset="capec", graph="gremlin"))
            is _GUARD_FAILED
        ):
            return r
        manifest = _read_runtime_manifest(self._config, "capec", "gremlin")
        if manifest:
            nodes = manifest.get("nodes_loaded", "?")
            r.detail = f"{nodes:,} vertices"
        else:
            r.detail = "loaded"
        r.status = "ok"
        return r

    def _step_verify(self) -> StepResult:
        r = StepResult(self.STEPS[6])
        parts: list[str] = []
        statuses: list[str] = []
        t0 = time.monotonic()

        for dataset, backend in [("attack", "neo4j"), ("capec", "gremlin")]:
            label = "ATT&CK" if dataset == "attack" else "CAPEC"
            try:
                retry_with_backoff(
                    lambda d=dataset: run_graph_command(dataset=d, graph="verify"),
                    retries=2,
                    base_delay=2.0,
                    should_retry=lambda exc: classify_failure(exc) == "transient",
                    on_retry=self._note_retry,
                )
                parts.append(f"{label} ✓")
                statuses.append("ok")
            except Exception as exc:
                parts.append(f"{label} ✗ ({exc})")
                statuses.append(
                    "needs_input" if classify_failure(exc) == "needs_human" else "failed"
                )

        r.duration_s = time.monotonic() - t0
        r.detail = "  ".join(parts)
        if "failed" in statuses:
            r.status = "failed"
        elif "needs_input" in statuses:
            r.status = "needs_input"
        else:
            r.status = "ok"
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

            if r.status in ("failed", "needs_input") and i in ABORT_ON_FAIL:
                aborted = True

        print_summary_table(results)
        return results
