#!/usr/bin/env python3
"""Run the Ariadne analyst-workbench web server.

This is a thin orchestrator for the Next.js app under ``web/``: it verifies the
Node toolchain, installs JavaScript dependencies on first run, and launches the
server. Development mode (hot reload) is the default; ``--prod`` does a
production build then serves it.

Examples
--------
    python app.py                  # dev server on http://localhost:3000
    python app.py --port 4000      # dev server on a different port
    python app.py --host 0.0.0.0   # expose on the local network
    python app.py --prod           # production build, then `next start`
    python app.py --skip-install   # don't touch node_modules
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ariadne.app")

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DEFAULT_PORT = 3000


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
    """Run a command, streaming its output, and return its exit code."""
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


def run_server(npm: str, *, prod: bool, port: int, host: str | None) -> int:
    """Launch the dev server, or build then serve in production mode."""
    forwarded: list[str] = ["--port", str(port)]
    if host:
        forwarded += ["--hostname", host]

    if prod:
        logger.info("Building the production bundle …")
        build_code = _run([npm, "run", "build"], cwd=WEB_DIR)
        if build_code != 0:
            logger.error("Production build failed (exit %d).", build_code)
            return build_code
        script = "start"
    else:
        script = "dev"

    shown_host = host or "localhost"
    logger.info(
        "Starting the %s server on http://%s:%d  (Ctrl+C to stop)",
        "production" if prod else "development",
        shown_host,
        port,
    )
    return _run([npm, "run", script, "--", *forwarded], cwd=WEB_DIR)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="app.py",
        description="Run the Ariadne analyst-workbench web server (Next.js, under web/).",
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Production mode: `next build` then `next start` (default is dev with hot reload).",
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Port to serve on (default {DEFAULT_PORT})."
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Hostname to bind (e.g. 0.0.0.0 to expose on the network; default is Next's localhost).",
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
    ensure_dependencies(npm, force=args.install, skip=args.skip_install)

    try:
        return run_server(npm, prod=args.prod, port=args.port, host=args.host)
    except KeyboardInterrupt:
        logger.info("\nServer stopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
