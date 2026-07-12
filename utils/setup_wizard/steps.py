#!/usr/bin/env python3
"""Wizard steps: describe → detect (idempotency probe) → run.

Every step reuses the machinery that already exists — ``utils.launcher.
preflight`` checks, ``utils.yolo.YoloRunner`` for the whole data pipeline,
``app.ensure_web_dependencies`` for npm — so the wizard orchestrates and
never reimplements.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from utils.config import env_str, load_env, set_env_values
from utils.launcher.preflight import CheckResult, FAIL, PASS, check_npm
from utils.yolo import (
    StepResult,
    _parse_bolt_host_port,
    _parse_ws_host_port,
    _tcp_up,
)

from .ui import WizardUI

ROOT = Path(__file__).resolve().parents[2]


class WizardStep:
    """Base contract; subclasses fill in the four pieces."""

    key: str = ""
    title: str = ""
    required: bool = True
    remediation: str = ""

    def describe(self) -> str:
        raise NotImplementedError

    def detect(self) -> tuple[bool, str]:
        """(already done?, human detail) — never raises."""
        return False, ""

    def run(self, ui: WizardUI) -> StepResult:
        raise NotImplementedError


# ── 1. prerequisites ─────────────────────────────────────────────────────────


def check_docker() -> CheckResult:
    """docker CLI + compose v2 + a running daemon."""
    docker = shutil.which("docker")
    if not docker:
        return CheckResult(
            "docker", FAIL, "docker not found on PATH",
            "Install Docker Engine (or Docker Desktop) from https://docs.docker.com/get-docker/",
        )
    compose = subprocess.run(
        [docker, "compose", "version"], capture_output=True, text=True)
    if compose.returncode != 0:
        return CheckResult(
            "docker compose", FAIL, "`docker compose` (v2) is unavailable",
            "Install the Compose plugin: https://docs.docker.com/compose/install/",
        )
    daemon = subprocess.run([docker, "info"], capture_output=True, text=True)
    if daemon.returncode != 0:
        return CheckResult(
            "docker daemon", FAIL, "the Docker daemon is not running",
            "Start Docker (e.g. `systemctl start docker`, or open Docker Desktop)",
        )
    return CheckResult("docker", PASS, compose.stdout.strip().splitlines()[0])


def check_node() -> CheckResult:
    node = shutil.which("node")
    if not node:
        return CheckResult(
            "node", FAIL, "node not found on PATH",
            "Install Node.js 18.18+ from https://nodejs.org",
        )
    version = subprocess.run([node, "--version"], capture_output=True, text=True)
    return CheckResult("node", PASS, version.stdout.strip() or node)


class PrerequisitesStep(WizardStep):
    key = "prereqs"
    title = "Check Prerequisites"
    required = True
    remediation = "Install the missing tool(s) named above, then re-run."

    #: Injectable for tests.
    checks = (check_npm, check_node, check_docker)

    def describe(self) -> str:
        return "Checking for npm, node, and docker (CLI, compose v2, daemon) …"

    def run(self, ui: WizardUI) -> StepResult:
        r = StepResult(self.title)
        failures: list[str] = []
        for check in self.checks:
            outcome = check()
            glyph = "✓" if outcome.status == PASS else "✗"
            ui.say(f"  {glyph} {outcome.name}: {outcome.detail}")
            if outcome.status == FAIL:
                if outcome.remediation:
                    ui.say(f"    fix: {outcome.remediation}")
                failures.append(outcome.name)
        if failures:
            r.status = "needs_input"
            r.detail = f"missing: {', '.join(failures)}"
        else:
            r.status = "ok"
            r.detail = "npm, node, docker all present"
        return r


# ── 2. .env ──────────────────────────────────────────────────────────────────


def write_port_config(
    *, bolt_port: str, http_port: str, gremlin_port: str, env_file: Path
) -> Path:
    """Persist port choices plus the URIs derived from them, in one write.

    ``NEO4J_URI``/``GREMLIN_URI`` are what the loader and specialists actually
    connect to — writing a port without its URI would silently split the
    config, so the derivation lives here rather than in the prompt flow.
    """
    return set_env_values(
        {
            "NEO4J_HTTP_PORT": http_port,
            "NEO4J_BOLT_PORT": bolt_port,
            "GREMLIN_PORT": gremlin_port,
            "NEO4J_URI": f"bolt://localhost:{bolt_port}",
            "GREMLIN_URI": f"ws://localhost:{gremlin_port}/gremlin",
        },
        env_file=env_file,
    )


def customize_env(ui: WizardUI, env_file: Path) -> None:
    """Interactive .env customization: ports → Neo4j login → LLM endpoints."""
    ui.say("Ports (Enter keeps the default):")
    bolt = ui.prompt_text("Neo4j Bolt port", env_str("NEO4J_BOLT_PORT", "5456"))
    http = ui.prompt_text("Neo4j HTTP port", env_str("NEO4J_HTTP_PORT", "5455"))
    gremlin = ui.prompt_text("Gremlin port", env_str("GREMLIN_PORT", "6455"))
    write_port_config(
        bolt_port=bolt, http_port=http, gremlin_port=gremlin, env_file=env_file)

    if ui.confirm("Customize the Neo4j password?", default=False):
        from utils.neo4j_login import create_neo4j_login

        # URI was just derived from the chosen port — only prompt user/password.
        create_neo4j_login(uri=f"bolt://localhost:{bolt}", env_file=env_file)

    if ui.confirm("Enable LLM features (needs an OpenAI-compatible endpoint)?",
                  default=False):
        base_url = ui.prompt_text(
            "LLM base URL", env_str("PLANNER_LLM_BASE_URL", "http://localhost:9090/v1"))
        model = ui.prompt_text(
            "LLM model name", env_str("PLANNER_LLM_MODEL", "default-model"))
        updates: dict[str, str] = {}
        for group in ("PLANNER", "SPECIALIST", "SYNTHESIS", "CONVERSATION", "EVAL"):
            updates[f"{group}_LLM_ENABLED"] = "true"
            updates[f"{group}_LLM_BASE_URL"] = base_url
            updates[f"{group}_LLM_MODEL"] = model
        set_env_values(updates, env_file=env_file)
        ui.say("LLM enabled for planner, specialists, synthesis, conversation, and eval.")


class EnvStep(WizardStep):
    key = "env"
    title = "Configure .env"
    required = True
    remediation = "Check that .env.example exists and the repo is writable."

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self.env_file = root / ".env"
        self.example_file = root / ".env.example"

    def describe(self) -> str:
        return f"Creating {self.env_file.name} from {self.example_file.name} …"

    def detect(self) -> tuple[bool, str]:
        if self.env_file.exists():
            return True, ".env already exists"
        return False, ""

    def run(self, ui: WizardUI) -> StepResult:
        r = StepResult(self.title)
        try:
            if self.env_file.exists():
                choice = ui.choose(
                    ".env exists — keep, customize, or recreate from the example?",
                    {"k": "eep", "c": "ustomize", "r": "ecreate"}, "k")
                if choice == "r":
                    backup = self.env_file.with_name(".env.bak")
                    shutil.copyfile(self.env_file, backup)
                    ui.say(f"Backed up the old .env to {backup.name}")
                    shutil.copyfile(self.example_file, self.env_file)
                elif choice == "k":
                    r.status = "ok"
                    r.detail = "kept the existing .env"
                    load_env()
                    return r
            else:
                if not self.example_file.exists():
                    r.status = "needs_input"
                    r.detail = f"{self.example_file} is missing"
                    return r
                shutil.copyfile(self.example_file, self.env_file)
                ui.say("Created .env with documented defaults.")

            if ui.confirm("Use the defaults (recommended), or customize "
                          "ports/credentials/LLM now? Enter = defaults",
                          default=True):
                r.detail = "defaults (edit .env or use Settings in the UI anytime)"
            else:
                customize_env(ui, self.env_file)
                r.detail = "customized"

            load_env(override=True)
            r.status = "ok"
            return r
        except Exception as exc:  # noqa: BLE001 — surfaced through the failure menu
            r.status = "failed"
            r.detail = str(exc)
            return r


# ── 3. data pipeline (delegated to YoloRunner) ───────────────────────────────


class DataStep(WizardStep):
    key = "data"
    title = "Data Pipeline (download → build → docker → load → verify)"
    required = True
    remediation = ("Review the failing pipeline step above; "
                   "`uv run main.py --yolo-all` re-runs it independently.")

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root

    def describe(self) -> str:
        return ("Running the full data pipeline: download MITRE ATT&CK + CAPEC "
                "(~55 MB), build canonical graphs, start the Neo4j/Gremlin "
                "containers, load both graphs, verify …")

    def _backends_up(self) -> bool:
        neo4j = _parse_bolt_host_port(env_str("NEO4J_URI", "bolt://localhost:5456"))
        gremlin = _parse_ws_host_port(env_str("GREMLIN_URI", "ws://localhost:6455/gremlin"))
        return _tcp_up(*neo4j) and _tcp_up(*gremlin)

    def detect(self) -> tuple[bool, str]:
        try:
            from utils.graph_loader.config import LoaderConfig

            config = LoaderConfig.from_data_dir(self.root / "data")
            versions = self.root / "data" / "versions.json"
            manifests = [
                config.runtime_dir(dataset, backend) / "load-manifest.json"
                for dataset, backend in (("attack", "neo4j"), ("capec", "gremlin"))
            ]
            if versions.exists() and all(m.exists() for m in manifests) and self._backends_up():
                return True, "data downloaded, both graphs loaded, containers up"
        except Exception:  # noqa: BLE001 — a probe failure just means "not done"
            pass
        return False, ""

    def run(self, ui: WizardUI) -> StepResult:
        from utils.yolo import YoloRunner

        r = StepResult(self.title)
        t0 = time.monotonic()
        try:
            results = YoloRunner().run()
        except Exception as exc:  # noqa: BLE001 — surfaced through the failure menu
            r.status = "failed"
            r.detail = str(exc)
            return r
        r.duration_s = time.monotonic() - t0

        bad = [x for x in results if x.status in ("failed", "needs_input")]
        if bad:
            r.status = "needs_input" if any(
                x.status == "needs_input" for x in bad) else "failed"
            r.detail = "; ".join(f"{x.name}: {x.detail}" for x in bad)[:200]
        else:
            r.status = "ok"
            r.detail = "all 7 pipeline steps green"
        return r


# ── 4. web dependencies ──────────────────────────────────────────────────────


class WebDepsStep(WizardStep):
    key = "web"
    title = "Install Web Dependencies (npm install)"
    required = False
    remediation = "cd web && npm install"

    def __init__(self, root: Path = ROOT, *, fresh: bool = False) -> None:
        self.root = root
        self.fresh = fresh

    def describe(self) -> str:
        return "Installing the Next.js workbench dependencies (npm install in web/) …"

    def detect(self) -> tuple[bool, str]:
        if (self.root / "web" / "node_modules").is_dir():
            return True, "web/node_modules present"
        return False, ""

    def run(self, ui: WizardUI) -> StepResult:
        from app import ensure_web_dependencies

        r = StepResult(self.title)
        npm = shutil.which("npm") or "npm"
        t0 = time.monotonic()
        code = ensure_web_dependencies(npm, force=self.fresh, skip=False, color=False)
        r.duration_s = time.monotonic() - t0
        if code != 0:
            r.status = "failed"
            r.detail = f"npm install exited {code}"
        else:
            r.status = "ok"
            r.detail = "web/node_modules ready"
        return r
