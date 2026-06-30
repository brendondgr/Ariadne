#!/usr/bin/env python3
"""Run the Ariadne analyst-workbench — FastAPI backend + Next.js front end.

The workbench is two processes:

* the **FastAPI service** under ``api/`` (live-source health, the federated
  query pipeline, LLM/connection config, and infra control), and
* the **Next.js app** under ``web/``, which proxies ``/api/*`` to the service.

This launcher starts both together, wires the web proxy to the API port (via the
``API_PORT`` env the Next config reads), and shuts both down on Ctrl+C. The API
runs through ``uv run`` when uv is available (so its dependencies are present);
otherwise it falls back to the current interpreter. Dev mode (hot reload on both)
is the default; ``--prod`` does a production ``next build`` then serves.

Examples
--------
    python app.py                  # dev: API :8000 + web on http://localhost:3000
    python app.py --port 4000      # web on a different port
    python app.py --api-port 8800  # API on a different port (proxy follows)
    python app.py --host 0.0.0.0   # expose the web app on the local network
    python app.py --prod           # production build, then serve both
    python app.py --skip-install   # don't touch node_modules
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ariadne.app")

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DEFAULT_PORT = 3000
DEFAULT_API_PORT = 8000


def _find_npm() -> str:
    """Return the npm executable path, or exit with guidance if missing."""
    npm = shutil.which("npm")
    if not npm:
        logger.error(
            "npm was not found on PATH. Install Node.js 18.18+ (which bundles npm) "
            "from https://nodejs.org and re-run."
        )
        raise SystemExit(1)
    return npm


def _run(cmd: list[str], *, cwd: Path) -> int:
    """Run a command to completion, streaming its output; return its exit code."""
    logger.info("$ %s  (in %s)", " ".join(cmd), cwd)
    return subprocess.run(cmd, cwd=cwd).returncode


def ensure_dependencies(npm: str, *, force: bool, skip: bool) -> None:
    """Install web dependencies when node_modules is absent (or when forced)."""
    if skip:
        logger.info("Skipping dependency install (--skip-install).")
        return
    node_modules = WEB_DIR / "node_modules"
    if node_modules.is_dir() and not force:
        logger.info("Dependencies present (web/node_modules) — skipping install.")
        return
    logger.info("Installing web dependencies …")
    code = _run([npm, "install", "--no-fund"], cwd=WEB_DIR)
    if code != 0:
        logger.error("`npm install` failed (exit %d).", code)
        raise SystemExit(code)


def ensure_api_available() -> None:
    """Make sure the FastAPI service can be launched (uv, or importable deps)."""
    if shutil.which("uv"):
        return  # `uv run` will provide the project environment.
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        logger.error(
            "FastAPI/uvicorn are not importable and `uv` is not on PATH. Install the "
            "Python deps with `uv sync` (recommended) or "
            "`pip install fastapi 'uvicorn[standard]'`, then re-run."
        )
        raise SystemExit(1)


def _api_command(api_port: int, *, reload: bool) -> list[str]:
    """Build the uvicorn command, preferring `uv run` so deps are guaranteed."""
    uvicorn_args = ["uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(api_port)]
    if reload:
        uvicorn_args.append("--reload")
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", *uvicorn_args]
    return [sys.executable, "-m", *uvicorn_args]


def _terminate_all(procs: list[tuple[str, subprocess.Popen]]) -> None:
    """Politely stop every still-running child, escalating to kill if needed."""
    for name, proc in procs:
        if proc.poll() is None:
            logger.info("Stopping %s …", name)
            proc.terminate()
    for name, proc in procs:
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            logger.warning("Force-killing %s", name)
            proc.kill()


def run_server(npm: str, *, prod: bool, port: int, host: str | None, api_port: int) -> int:
    """Launch the FastAPI service and the Next.js app together."""
    # In production, build the web bundle first so a failure aborts cleanly.
    if prod:
        logger.info("Building the production bundle …")
        build_code = _run([npm, "run", "build"], cwd=WEB_DIR)
        if build_code != 0:
            logger.error("Production build failed (exit %d).", build_code)
            return build_code

    web_forwarded = ["--port", str(port)] + (["--hostname", host] if host else [])
    web_cmd = [npm, "run", "start" if prod else "dev", "--", *web_forwarded]
    api_cmd = _api_command(api_port, reload=not prod)
    # The Next config reads API_PORT to proxy /api/* to the FastAPI service.
    web_env = {**os.environ, "API_PORT": str(api_port)}

    shown_host = host or "localhost"
    logger.info(
        "Starting %s servers — API http://127.0.0.1:%d · web http://%s:%d  (Ctrl+C to stop)",
        "production" if prod else "development",
        api_port,
        shown_host,
        port,
    )

    procs: list[tuple[str, subprocess.Popen]] = []
    try:
        logger.info("$ %s  (in %s)", " ".join(api_cmd), ROOT)
        procs.append(("api", subprocess.Popen(api_cmd, cwd=ROOT)))
        logger.info("$ %s  (in %s)", " ".join(web_cmd), WEB_DIR)
        procs.append(("web", subprocess.Popen(web_cmd, cwd=WEB_DIR, env=web_env)))

        # Run until either process exits, then tear the other down.
        while True:
            for name, proc in procs:
                code = proc.poll()
                if code is not None:
                    logger.warning("The %s process exited (code %s); stopping the rest.", name, code)
                    return code or 0
            time.sleep(0.4)
    except KeyboardInterrupt:
        logger.info("\nShutting down …")
        return 0
    finally:
        _terminate_all(procs)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="app.py",
        description="Run the Ariadne analyst workbench (FastAPI api/ + Next.js web/).",
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Production mode: `next build` then serve both (default is dev with hot reload).",
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Web port (default {DEFAULT_PORT})."
    )
    parser.add_argument(
        "--api-port", type=int, default=DEFAULT_API_PORT,
        help=f"FastAPI port the web app proxies to (default {DEFAULT_API_PORT}).",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Hostname to bind the web app (e.g. 0.0.0.0 to expose on the network).",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Force `npm install` even if web/node_modules already exists.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Never run `npm install` (assume dependencies are already present).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not WEB_DIR.is_dir():
        logger.error("Expected the web app at %s but it does not exist.", WEB_DIR)
        return 1
    if not (WEB_DIR / "package.json").is_file():
        logger.error("No package.json in %s — is the web app initialized?", WEB_DIR)
        return 1

    npm = _find_npm()
    ensure_api_available()
    ensure_dependencies(npm, force=args.install, skip=args.skip_install)

    try:
        return run_server(
            npm, prod=args.prod, port=args.port, host=args.host, api_port=args.api_port
        )
    except KeyboardInterrupt:
        logger.info("\nServer stopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
