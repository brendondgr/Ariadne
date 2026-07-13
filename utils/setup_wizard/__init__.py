#!/usr/bin/env python3
"""Ariadne one-shot setup wizard (stage 2 — runs inside the project env).

``python3 setup.py`` at the repo root is stage 1: a stdlib-only bootstrap
that checks for ``uv``, runs ``uv sync``, and re-execs this package via
``uv run python -m utils.setup_wizard``. Stage 2 owns everything that needs
project dependencies: prerequisite checks, ``.env`` creation, the full data
pipeline (delegated to ``YoloRunner``), web dependencies, and the hand-off to
``app.py``.

Each step follows one contract — *describe* what will run, *detect* whether
it is already done (offer to skip), *run* it, and on failure offer
retry / skip / abort — so a partially set-up clone re-runs only what is
missing, and a failure never dead-ends without naming the fix.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from utils.config import env_str
from utils.launcher.preflight import check_port
from utils.yolo import StepResult, print_summary_table

from .steps import (
    ROOT,
    DataStep,
    EnvStep,
    InferenceServerStep,
    PrerequisitesStep,
    WebDepsStep,
    WizardStep,
)
from .ui import WizardUI

WEB_PORT = 16500
API_PORT = 16501


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="setup.py",
        description="Interactive one-shot setup: deps → .env → data pipeline → web → launch.",
    )
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Non-interactive: accept every default, auto-skip completed steps.")
    parser.add_argument("--fresh", action="store_true",
                        help="Re-run every step even when it looks already done (backs up .env).")
    parser.add_argument("--skip-sync", action="store_true",
                        help="(consumed by stage 1) Skip `uv sync`.")
    parser.add_argument("--skip-env", action="store_true", help="Skip the .env step.")
    parser.add_argument("--skip-inference", action="store_true",
                        help="Skip configuring/probing the local inference (LLM) server.")
    parser.add_argument("--skip-data", action="store_true",
                        help="Skip the data pipeline (download/build/docker/load/verify).")
    parser.add_argument("--skip-web", action="store_true", help="Skip `npm install`.")
    parser.add_argument("--no-launch", action="store_true",
                        help="Set everything up but print the launch command instead of running it.")
    parser.add_argument("--no-browser", action="store_true",
                        help="Don't open the workbench in a browser after launch.")
    parser.add_argument("--prod", action="store_true",
                        help="Launch the workbench in production mode (next build + start).")
    return parser.parse_args(argv)


def _sync_result() -> StepResult:
    """Record stage 1's `uv sync` outcome (passed down via the environment)."""
    status = os.environ.get("ARIADNE_SETUP_SYNC", "")
    if status == "ok":
        return StepResult("Sync Python Environment (uv sync)", status="ok", detail=".venv ready")
    if status == "skipped":
        return StepResult("Sync Python Environment (uv sync)", status="skipped",
                          detail="--skip-sync")
    return StepResult("Sync Python Environment (uv sync)", status="skipped",
                      detail="already inside the project env")


def _run_step(step: WizardStep, ui: WizardUI, *, fresh: bool, skip: bool) -> StepResult:
    """Drive one step through the describe → detect → run → failure-menu contract."""
    if skip:
        return StepResult(step.title, status="skipped", detail="skipped by flag")

    done, detail = step.detect()
    if done and not fresh:
        if ui.confirm(f"{step.title}: already done ({detail}). Skip?", default=True):
            return StepResult(step.title, status="skipped", detail=detail)

    while True:
        ui.say(f"→ {step.describe()}")
        result = step.run(ui)
        if result.status in ("ok", "skipped"):
            ui.say(f"{result.symbol} {step.title} — {result.detail or result.status_label}")
            return result

        choice = ui.failure_menu(step.title, result.detail, step.remediation,
                                 required=step.required)
        if choice == "retry":
            continue
        if choice == "skip":
            result.status = "skipped"
            result.detail = f"skipped after failure: {result.detail}"
            return result
        return result  # abort — caller stops on failed/needs_input


EXAMPLE_QUERY = (
    "Which CAPEC patterns related to credential theft map to ATT&CK "
    "techniques, and what mitigations apply?"
)


def print_next_commands(
    ui: WizardUI,
    *,
    llm_enabled: bool,
    web_port: int = WEB_PORT,
    api_port: int = API_PORT,
) -> None:
    """Print the copy-paste command cheat-sheet the setup finishes on.

    Always shown on a green setup — start the (optional) inference server and
    the Docker graph stack, then either ask a question straight from the CLI or
    launch the web workbench. The inference-server and ``--query-llm`` lines are
    gated on ``llm_enabled`` so the sheet only ever tells the user to start a
    server they actually configured.
    """
    ui.say("")
    ui.header("Next steps — copy/paste any of these")

    number = 0
    if llm_enabled:
        number += 1
        base_url = env_str("PLANNER_LLM_BASE_URL", "http://localhost:9090/v1")
        ui.say(f"{number}. Start your local inference server "
               f"(OpenAI-compatible: vLLM / LM Studio / llama.cpp / Ollama)")
        ui.say(f"     → it must serve {base_url}")
        ui.say("")

    number += 1
    ui.say(f"{number}. Start the graph databases (Docker: Neo4j + Gremlin)")
    ui.say("     uv run main.py --docker start")
    ui.say("")

    number += 1
    ui.say(f"{number}. Ask a federated question straight from the CLI")
    ui.say(f'     uv run main.py --query "{EXAMPLE_QUERY}"'
           + (" --query-llm" if llm_enabled else ""))
    ui.say("")

    number += 1
    ui.say(f"{number}. Launch the analyst web workbench")
    ui.say("     uv run app.py")
    ui.say(f"     → web http://localhost:{web_port}   api http://127.0.0.1:{api_port}")
    ui.say("")


def _launch(args: argparse.Namespace, ui: WizardUI) -> int:
    """Hand off to app.py (its own preflight, status board, and smoke run)."""
    launch_cmd = [sys.executable, str(ROOT / "app.py"), "--skip-install"]
    if not args.no_browser:
        launch_cmd.append("--open")
    if args.prod:
        launch_cmd.append("--prod")

    busy = [p for p in (WEB_PORT, API_PORT) if check_port(p, "probe").status == "fail"]
    if busy:
        ui.say(f"Ports {', '.join(str(p) for p in busy)} are already serving — "
               f"the workbench appears to be running at http://localhost:{WEB_PORT}")
        return 0

    if args.no_launch:
        ui.say("Setup complete — run any command above when you're ready.")
        return 0

    ui.say(f"Launching the workbench — web http://localhost:{WEB_PORT}, "
           f"api http://127.0.0.1:{API_PORT} …")
    os.execv(sys.executable, launch_cmd)
    return 1  # unreachable


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ui = WizardUI(assume_yes=args.yes)

    # Load any existing .env up front: every later step (docker ports, loader
    # credentials, backend probes) must see the user's values even when the
    # .env step itself is skipped as already-done.
    from utils.config import load_env

    load_env()

    ui.header("Ariadne setup wizard")

    steps: list[tuple[WizardStep, bool]] = [
        (PrerequisitesStep(), False),
        (EnvStep(), args.skip_env),
        (InferenceServerStep(), args.skip_inference),
        (DataStep(), args.skip_data),
        (WebDepsStep(fresh=args.fresh), args.skip_web),
    ]

    results: list[StepResult] = []
    for index, (step, skip) in enumerate(steps):
        result = _run_step(step, ui, fresh=args.fresh, skip=skip)
        results.append(result)
        if result.status in ("failed", "needs_input") and step.required:
            ui.say(f"✗ {step.title} is required — stopping here.")
            results.extend(
                StepResult(later.title, status="skipped", detail="Earlier step failed")
                for later, _ in steps[index + 1:]
            )
            break

    results.insert(1, _sync_result())
    print_summary_table(results)

    if any(r.status in ("failed", "needs_input") for r in results):
        ui.say("Fix the failing step above and re-run `python3 setup.py` — "
               "completed steps will offer to skip.")
        return 1

    llm_enabled = env_str("PLANNER_LLM_ENABLED", "false").strip().lower() == "true"
    print_next_commands(ui, llm_enabled=llm_enabled)

    return _launch(args, ui)


__all__ = ["main", "parse_args", "print_next_commands"]
