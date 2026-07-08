#!/usr/bin/env python3
"""Run the Ariadne analyst-workbench — FastAPI backend + Next.js front end.

The workbench is two processes (the FastAPI service under ``api/`` and the
Next.js app under ``web/``), but this launcher's job is bigger than spawning
them: it is the works-the-first-time gate for the LangGraph-orchestrated
pipeline. Startup goes through four phases (``utils/launcher``):

1. **Preflight** — toolchain, ports, web deps, source cards, live graph
   backends, the LLM endpoint, and a compile of the orchestration
   super-graph. Hard failures abort with the fix named; degraded subsystems
   warn and the stack starts anyway (the UI shows Live/Dead pills).
2. **Supervised start** — the API is spawned and polled on ``/api/health``
   until ready, then the web app is spawned and polled until it serves.
   Both outputs stream with ``[api]`` / ``[web]`` prefixes.
3. **Status board** — an honest summary of URLs, orchestrator, data snapshot
   versions, and every check's verdict.
4. **Smoke** — one plan-mode question streamed over the real SSE contract
   (``--smoke full`` for a complete federated query, ``--no-smoke`` to skip).

Examples
--------
    python app.py                  # dev: API :16501 + web on http://localhost:16500
    python app.py --port 4000      # web on a different port
    python app.py --api-port 8800  # API on a different port (proxy follows)
    python app.py --host 0.0.0.0   # expose the web app on the local network
    python app.py --prod           # production build, then serve both
    python app.py --skip-install   # don't touch node_modules
    python app.py --smoke full     # prove a full federated query at boot
    python app.py --no-smoke      # skip the startup smoke query
    python app.py --verbose        # unfiltered child output
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from utils.launcher.display import (
    BoardInfo,
    data_versions,
    format_line,
    render_board,
    stream_output,
    use_color,
)
from utils.launcher.preflight import hard_failures, run_preflight
from utils.launcher.smoke import run_smoke
from utils.launcher.supervise import (
    Child,
    api_health_ready,
    monitor,
    port_serving,
    terminate_all,
    wait_ready,
)

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DEFAULT_PORT = 16500
DEFAULT_API_PORT = 16501

# Dev-server lines worth showing without --verbose (readiness; errors always show).
_QUIET_ALLOW = ("ready", "started", "compiled", "listening", "local:", "network:")


def _emit(line: str) -> None:
    print(line, flush=True)


def _say(source: str, message: str, *, color: bool) -> None:
    _emit(format_line(source, message, color=color))


def _api_command(api_port: int, *, reload: bool) -> list[str]:
    """Build the uvicorn command, preferring `uv run` so deps are guaranteed."""
    uvicorn_args = ["uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(api_port)]
    if reload:
        uvicorn_args.append("--reload")
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", *uvicorn_args]
    return [sys.executable, "-m", *uvicorn_args]


def _spawn(name: str, cmd: list[str], *, cwd: Path, env: dict | None,
           color: bool, verbose: bool) -> Child:
    """Start one child with piped output pumped through the prefixed streamer."""
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    child = Child(name=name, proc=proc)

    def keep(line: str) -> bool:
        child.remember(line)
        return verbose or any(marker in line.lower() for marker in _QUIET_ALLOW)

    assert proc.stdout is not None
    stream_output(name, proc.stdout, color=color, emit=_emit, filter_fn=keep)
    return child


def ensure_web_dependencies(npm: str, *, force: bool, skip: bool, color: bool) -> int:
    """Install web dependencies when node_modules is absent (or when forced)."""
    if skip:
        return 0
    if (WEB_DIR / "node_modules").is_dir() and not force:
        return 0
    _say("preflight", "Installing web dependencies (npm install) …", color=color)
    return subprocess.run([npm, "install", "--no-fund"], cwd=WEB_DIR).returncode


def run_server(args: argparse.Namespace, checks, *, color: bool) -> int:
    """Phases 2–4: supervised start, status board, smoke."""
    npm = shutil.which("npm") or "npm"

    if args.prod:
        _say("preflight", "Building the production bundle …", color=color)
        build = subprocess.run([npm, "run", "build"], cwd=WEB_DIR)
        if build.returncode != 0:
            _say("preflight", f"Production build failed (exit {build.returncode}).", color=color)
            return build.returncode

    web_forwarded = ["--port", str(args.port)] + (["--hostname", args.host] if args.host else [])
    web_cmd = [npm, "run", "start" if args.prod else "dev", "--", *web_forwarded]
    api_cmd = _api_command(args.api_port, reload=not args.prod)
    web_env = {**os.environ, "API_PORT": str(args.api_port)}
    children: list[Child] = []

    def report_exit(child: Child, code: int) -> None:
        _say("preflight", f"The {child.name} process exited (code {code}); stopping the rest.",
             color=color)
        tail = "\n".join(child.tail)
        if tail:
            _emit(tail)

    try:
        # API first, gated on its health endpoint answering.
        _say("api", f"$ {' '.join(api_cmd)}", color=color)
        api = _spawn("api", api_cmd, cwd=ROOT, env=None, color=color, verbose=args.verbose)
        children.append(api)
        ready, reason = wait_ready(
            api, lambda: api_health_ready(args.api_port), what="the API")
        if not ready:
            _say("preflight", reason, color=color)
            return 1
        _say("api", f"ready — http://127.0.0.1:{args.api_port}", color=color)

        # Then the web app, gated on its port serving.
        _say("web", f"$ {' '.join(web_cmd)}", color=color)
        web = _spawn("web", web_cmd, cwd=WEB_DIR, env=web_env, color=color, verbose=args.verbose)
        children.append(web)
        ready, reason = wait_ready(web, lambda: port_serving(args.port), what="the web app")
        if not ready:
            _say("preflight", reason, color=color)
            return 1
        shown_host = args.host or "localhost"
        _say("web", f"ready — http://{shown_host}:{args.port}", color=color)

        # The status board: what is running, what is degraded, how to fix it.
        orchestrator = next(
            (c.detail for c in checks if c.name == "langgraph pipeline"), "LangGraph")
        _emit(render_board(BoardInfo(
            web_url=f"http://{shown_host}:{args.port}",
            api_url=f"http://127.0.0.1:{args.api_port}",
            mode="production" if args.prod else "development",
            orchestrator=orchestrator.replace("super-graph compiled", "LangGraph"),
            data_versions=data_versions(ROOT),
        ), checks, color=color))

        # Prove the pipeline before handing the analyst the keys.
        if args.smoke != "off":
            mode = "query" if args.smoke == "full" else "plan"
            _say("smoke", f"Streaming a {mode}-mode smoke query …", color=color)
            result = run_smoke(args.api_port, mode=mode)
            if not result.ok:
                _say("smoke", f"FAILED: {result.detail}", color=color)
                _say("smoke", f"events seen: {list(result.events)}", color=color)
                return 1
            _say("smoke", f"OK — {result.detail}", color=color)

        _say("preflight", "Workbench up. Ctrl+C to stop.", color=color)
        return monitor(children, on_exit=report_exit)
    except KeyboardInterrupt:
        _say("preflight", "Shutting down …", color=color)
        return 0
    finally:
        terminate_all(children)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="app.py",
        description="Run the Ariadne analyst workbench (FastAPI api/ + Next.js web/).",
    )
    parser.add_argument(
        "--prod", action="store_true",
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
        "--host", default=None,
        help="Hostname to bind the web app (e.g. 0.0.0.0 to expose on the network).",
    )
    parser.add_argument(
        "--install", action="store_true",
        help="Force `npm install` even if web/node_modules already exists.",
    )
    parser.add_argument(
        "--skip-install", action="store_true",
        help="Never run `npm install` (assume dependencies are already present).",
    )
    parser.add_argument(
        "--smoke", nargs="?", const="plan", default="plan", choices=["plan", "full"],
        help="Startup smoke query: plan (default, fast) or full (one federated query).",
    )
    parser.add_argument(
        "--no-smoke", dest="smoke", action="store_const", const="off",
        help="Skip the startup smoke query.",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show all child output (default shows readiness lines and errors).",
    )
    return parser.parse_args(argv)


def _reexec_under_uv_if_needed() -> None:
    """Re-exec through `uv run` when the project env is not already active.

    ``python app.py`` must work with a bare system interpreter, but the
    preflight (graph probes, LangGraph compile) needs the project's
    dependencies. When they are missing and uv is available, transparently
    restart inside the project env; without uv, continue — preflight reports
    the missing deps with the fix named.
    """
    if os.environ.get("ARIADNE_LAUNCHER_REEXEC"):
        return
    try:
        # Concrete imports on purpose: a stray namespace package can make a
        # bare `import langgraph` succeed on the system interpreter.
        import neo4j  # noqa: F401
        from langgraph.graph import StateGraph  # noqa: F401

        return
    except ImportError:
        pass
    uv = shutil.which("uv")
    if not uv:
        return
    os.environ["ARIADNE_LAUNCHER_REEXEC"] = "1"
    os.execvp(uv, [uv, "run", "python", str(ROOT / "app.py"), *sys.argv[1:]])


def main(argv: list[str] | None = None) -> int:
    _reexec_under_uv_if_needed()
    args = parse_args(argv)
    color = use_color()

    # Load .env before preflight: the graph/LLM probes need the live creds
    # the API itself will run with. Tolerate a bare env (no uv, no deps) —
    # preflight will name what is missing.
    try:
        from utils.config import load_env

        load_env()
    except ImportError:
        pass

    if not WEB_DIR.is_dir() or not (WEB_DIR / "package.json").is_file():
        _say("preflight", f"Expected the web app at {WEB_DIR} — is it initialized?", color=color)
        return 1

    # Phase 1: preflight. Hard failures abort with the fix named.
    _say("preflight", "Running preflight checks …", color=color)
    checks = run_preflight(
        root=ROOT, web_port=args.port, api_port=args.api_port,
        will_install=not args.skip_install,
    )
    for check in checks:
        glyph = {"pass": "✓", "warn": "⚠", "fail": "✗"}[check.status]
        line = f"{glyph} {check.name}: {check.detail}"
        if check.status != "pass" and check.remediation:
            line += f"  → {check.remediation}"
        _say("preflight", line, color=color)
    failures = hard_failures(checks)
    if failures:
        _say("preflight",
             f"{len(failures)} blocking failure(s) — fix the above and re-run.", color=color)
        return 1

    npm = shutil.which("npm") or "npm"
    code = ensure_web_dependencies(
        npm, force=args.install, skip=args.skip_install, color=color)
    if code != 0:
        _say("preflight", f"`npm install` failed (exit {code}).", color=color)
        return code

    try:
        return run_server(args, checks, color=color)
    except KeyboardInterrupt:
        _say("preflight", "Server stopped.", color=color)
        return 0


if __name__ == "__main__":
    sys.exit(main())
