#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path

# Load the central .env into the environment BEFORE importing modules whose
# configuration is resolved at import time, so every setting comes from one
# place. Real shell/CI env vars still take precedence.
from utils.config import load_env

load_env()

from utils.download import DatasetDownloader
from utils.graph_loader.config import GRAPH_ACTIONS
from utils.graph_loader.main import run_graph_command
from utils.graph_loader.registry import LoaderResolutionError
from utils.infrastructure import docker_start, docker_status, docker_stop, docker_stop_service
from utils.kg_builder import KGBuildRunner
from utils.neo4j_login import create_neo4j_login
from utils.planner.cli import run_plan_command
from utils.specialists.cli import run_query_command
from utils.yolo import YoloRunner

logger = logging.getLogger("ariadne.main")


def setup_logging(job_type: str) -> Path:
    """Set up logging to console and a sequential log file.

    Format: logs/<sequence_number>-<job_type>.log
    """
    logs_dir = Path.cwd() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    pattern = re.compile(rf"^(\d+)-{job_type}\.log$")

    max_num = 0
    if logs_dir.exists():
        for path in logs_dir.iterdir():
            if path.is_file():
                match = pattern.match(path.name)
                if match:
                    try:
                        num = int(match.group(1))
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        pass

    next_num = max_num + 1
    log_file = logs_dir / f"{next_num}-{job_type}.log"

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    return log_file


def _neo4j_browser_url() -> str:
    """Derive the Neo4j browser URL from environment variables."""
    neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:5456")
    http_port = os.environ.get("NEO4J_HTTP_PORT", "5455")

    host = "localhost"
    if neo4j_uri.startswith("bolt://"):
        host_port = neo4j_uri.removeprefix("bolt://").split("/", 1)[0]
        parsed_host = host_port.split(":")[0]
        if parsed_host:
            host = parsed_host

    return f"http://{host}:{http_port}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Ariadne federated knowledge graph CLI\n\n"
            "Use the steps below in order to download data, build artifacts,\n"
            "start infrastructure, configure credentials, and load graphs.\n"
            "Each step is independent — only run what you need."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
SINGLE-COMMAND SHORTCUT
-----------------------
  Run the entire pipeline in one go (download → build → docker → load → verify):
    uv run main.py --yolo-all

TYPICAL WORKFLOW
----------------
  Step 1 — Download raw datasets:
    uv run main.py --download
    uv run main.py --download --force          # re-download even if files already exist

  Step 2 — Build portable graph artifacts from the raw data:
    uv run main.py --build attack
    uv run main.py --build all
    uv run main.py --build attack --dry-run    # preview what would be written (no changes)

  Step 3 — Start local graph infrastructure (Docker):
    uv run main.py --docker start
    uv run main.py --docker status             # see what's running
    uv run main.py --docker stop               # shut everything down

  Step 4 — Configure Neo4j credentials (saved to .env):
    uv run main.py --neo4j-login               # interactive prompts
    uv run main.py --neo4j-login \\             # non-interactive (all flags at once)
        --neo4j-uri bolt://localhost:5456 \\
        --neo4j-user neo4j \\
        --neo4j-password mypassword

  Step 5 — Load data into a graph backend:
    uv run main.py --graph neo4j --dataset attack
    uv run main.py --graph gremlin --dataset attack
    uv run main.py --graph all --dataset attack    # load into both backends

  Step 6 — Verify loaded data or check infrastructure health:
    uv run main.py --graph verify --dataset attack   # validate data, no reload
    uv run main.py --graph health                    # ping backends (no dataset needed)

STOP A SPECIFIC BACKEND
-----------------------
  uv run main.py --graph-stop neo4j
  uv run main.py --graph-stop gremlin
  uv run main.py --graph-stop all

VERSION OVERRIDES (--docker start only)
----------------------------------------
  uv run main.py --docker start --neo4j-version 5.18.0
  uv run main.py --docker start --gremlin-version 3.7.2
""",
    )

    # ── Step 1-2: Data pipeline ───────────────────────────────────────────────
    data = parser.add_argument_group(
        "Data Pipeline (steps 1-2)",
        "Download raw datasets and build portable graph artifacts.",
    )
    data.add_argument(
        "--download",
        action="store_true",
        help="Download MITRE ATT&CK and CAPEC datasets",
    )
    data.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if files already exist (use with --download)",
    )
    data.add_argument(
        "--build",
        choices=["attack", "capec", "all"],
        metavar="{attack,capec,all}",
        help="Build graph artifacts from downloaded data (attack = JSONL/Cypher/CSV bundle)",
    )
    data.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview --build actions without writing any files",
    )

    # ── Step 3: Infrastructure ────────────────────────────────────────────────
    infra = parser.add_argument_group(
        "Infrastructure — Docker (step 3)",
        "Start, stop, or inspect the local Neo4j and Gremlin containers.",
    )
    infra.add_argument(
        "--docker",
        choices=["start", "stop", "status"],
        metavar="{start,stop,status}",
        help="start: launch containers  |  stop: shut them down  |  status: show what's running",
    )
    infra.add_argument(
        "--neo4j-version",
        metavar="VERSION",
        help="Override the pinned Neo4j image version (use with --docker start)",
    )
    infra.add_argument(
        "--gremlin-version",
        metavar="VERSION",
        help="Override the pinned Gremlin image version (use with --docker start)",
    )

    # ── Step 4: Credentials ───────────────────────────────────────────────────
    creds = parser.add_argument_group(
        "Neo4j Credentials (step 4)",
        "Save connection details to the central .env file.",
    )
    creds.add_argument(
        "--neo4j-login",
        action="store_true",
        help="Interactively create/update Neo4j credentials in .env",
    )
    creds.add_argument(
        "--neo4j-uri",
        metavar="URI",
        help="Bolt URI (e.g. bolt://localhost:5456) — skips the URI prompt with --neo4j-login",
    )
    creds.add_argument(
        "--neo4j-user",
        metavar="USER",
        help="Username — skips the user prompt with --neo4j-login",
    )
    creds.add_argument(
        "--neo4j-password",
        metavar="PASSWORD",
        help="Password — skips the password prompt with --neo4j-login",
    )

    # ── Steps 5-6: Graph backend ──────────────────────────────────────────────
    graph = parser.add_argument_group(
        "Graph Backend (steps 5-6)",
        "Load data into graph backends, verify loaded data, or stop a backend.",
    )
    graph.add_argument(
        "--graph",
        choices=sorted(GRAPH_ACTIONS),
        metavar="{neo4j,gremlin,all,verify,health}",
        help=(
            "neo4j / gremlin / all: load --dataset into that backend\n"
            "verify: validate already-loaded data (requires --dataset)\n"
            "health: ping backends only — no --dataset needed"
        ),
    )
    graph.add_argument(
        "--dataset",
        choices=["attack", "capec", "all"],
        metavar="{attack,capec,all}",
        help="Which dataset to load or verify (required for --graph, except --graph health)",
    )
    graph.add_argument(
        "--graph-stop",
        choices=["neo4j", "gremlin", "all"],
        metavar="{neo4j,gremlin,all}",
        help="Stop a running backend container without removing it",
    )

    # ── Full pipeline shortcut ────────────────────────────────────────────────
    yolo = parser.add_argument_group(
        "Full Pipeline (--yolo-all)",
        "Run the entire pipeline end-to-end: download → build → docker → load → verify.",
    )
    yolo.add_argument(
        "--yolo-all",
        action="store_true",
        help=(
            "Run every pipeline step in sequence: download datasets, build artifacts, "
            "check credentials, start Docker, load ATT&CK→Neo4j and CAPEC→Gremlin, "
            "then verify. Already-done steps are skipped automatically."
        ),
    )

    # ── Step 7: Planning agent ────────────────────────────────────────────────
    planner = parser.add_argument_group(
        "Planning Agent (step 7)",
        "Read the live graphs and emit a machine-readable routing plan for a question.",
    )
    planner.add_argument(
        "--plan",
        metavar="QUESTION",
        help="Plan an analyst question over the live graphs (probes liveness, emits a plan)",
    )
    planner.add_argument(
        "--plan-llm",
        action="store_true",
        help="Use the OpenAI-compatible LLM drafter for --plan (default: deterministic)",
    )

    # ── Steps 8-9: Query specialists ──────────────────────────────────────────
    specialists = parser.add_argument_group(
        "Query Specialists (steps 8-9)",
        "Plan a question, then run the Cypher/Gremlin specialists over the plan "
        "and print the normalized, provenance-linked evidence.",
    )
    specialists.add_argument(
        "--query",
        metavar="QUESTION",
        help="Plan a question and run the source-specific specialists over the live graphs",
    )
    specialists.add_argument(
        "--query-llm",
        action="store_true",
        help="Use the OpenAI-compatible LLM drafter when planning for --query",
    )

    args = parser.parse_args()

    # Determine job type
    if args.yolo_all:
        job_type = "yolo-all"
    elif args.download:
        job_type = "download"
    elif args.build:
        job_type = f"build-{args.build}"
    elif args.docker:
        job_type = f"docker-{args.docker}"
    elif args.neo4j_login:
        job_type = "neo4j-login"
    elif args.graph is not None:
        if args.graph == "health":
            job_type = "graph-health"
        elif args.dataset:
            job_type = f"load-{args.dataset}-{args.graph}"
        else:
            job_type = "graph-missing-dataset"
    elif args.graph_stop:
        job_type = f"graph-stop-{args.graph_stop}"
    elif args.plan:
        job_type = "plan"
    elif args.query:
        job_type = "query"
    else:
        # If no arguments provided, print help and exit
        parser.print_help()
        sys.exit(0)

    # Set up logging for the selected job
    log_file = setup_logging(job_type)

    logger.info(f"Starting job: {job_type}")
    logger.info(f"Log file: {log_file}")

    try:
        if args.yolo_all:
            results = YoloRunner().run()
            if any(r.status == "failed" for r in results):
                sys.exit(1)
        elif args.download:
            downloader = DatasetDownloader(force=args.force)
            downloader.download_all()

            logger.info("Job completed successfully.")
            logger.info(f"Data directory: {downloader.data_dir.resolve()}")
        elif args.build:
            runner = KGBuildRunner(dry_run=args.dry_run)
            if args.build == "attack":
                runner.build_attack()
            elif args.build == "capec":
                runner.build_capec()
            elif args.build == "all":
                runner.build_all()

            logger.info("Job completed successfully.")
        elif args.docker == "start":
            docker_start(
                neo4j_version=args.neo4j_version,
                gremlin_version=args.gremlin_version,
            )
            logger.info("Job completed successfully.")
        elif args.docker == "stop":
            docker_stop()
            logger.info("Job completed successfully.")
        elif args.docker == "status":
            docker_status()
            logger.info("Job completed successfully.")
        elif args.neo4j_login:
            create_neo4j_login(
                uri=args.neo4j_uri,
                user=args.neo4j_user,
                password=args.neo4j_password,
            )
            logger.info("Job completed successfully.")
        elif args.graph is not None:
            if args.graph != "health" and not args.dataset:
                parser.error("--dataset is required unless --graph health is used.")
            if args.dataset == "all" and args.graph not in {"neo4j", "gremlin", "all", "verify"}:
                parser.error("--dataset all is not supported yet; use attack.")
            if args.dataset == "all":
                raise ValueError("--dataset all is not supported yet; use attack.")
            run_graph_command(dataset=args.dataset, graph=args.graph)
            logger.info("Job completed successfully.")
            if args.graph in {"neo4j", "all"}:
                browser_url = _neo4j_browser_url()
                logger.info("Neo4j browser: %s", browser_url)
                print(f"\nGraph loaded. View it at: {browser_url}\n")
        elif args.graph_stop:
            docker_stop_service(args.graph_stop)
            logger.info("Job completed successfully.")
        elif args.plan:
            code = run_plan_command(args.plan, use_llm=args.plan_llm)
            if code == 2:
                sys.exit(2)
            logger.info("Job completed successfully.")
        elif args.query:
            code = run_query_command(args.query, use_llm=args.query_llm)
            if code == 2:
                sys.exit(2)
            logger.info("Job completed successfully.")
    except (LoaderResolutionError, ValueError, RuntimeError, ConnectionError) as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Job {job_type} failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
