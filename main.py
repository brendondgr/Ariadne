#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from utils.download import DatasetDownloader
from utils.graph_loader.config import GRAPH_ACTIONS
from utils.graph_loader.main import GraphLoaderNotReadyError, run_graph_command
from utils.graph_loader.registry import LoaderResolutionError
from utils.infrastructure import docker_start, docker_status, docker_stop
from utils.kg_builder import KGBuildRunner

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ariadne federated knowledge graph CLI"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download datasets (MITRE ATT&CK and CAPEC)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force download even if files already exist",
    )
    parser.add_argument(
        "--build",
        choices=["attack", "capec", "all"],
        help=(
            "Build portable graph artifacts from raw datasets "
            "(attack: ATT&CK JSONL/Cypher/CSV bundle; capec: future work)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview build actions without writing artifacts",
    )
    parser.add_argument(
        "--docker",
        choices=["start", "stop", "status"],
        help="Manage local Neo4j and Gremlin Docker infrastructure",
    )
    parser.add_argument(
        "--neo4j-version",
        help="Override pinned Neo4j image version for --docker start",
    )
    parser.add_argument(
        "--gremlin-version",
        help="Override pinned Gremlin image version for --docker start",
    )
    parser.add_argument(
        "--dataset",
        choices=["attack", "capec", "all"],
        help="Dataset to load or verify from built canonical graph artifacts",
    )
    parser.add_argument(
        "--graph",
        choices=sorted(GRAPH_ACTIONS),
        help=(
            "Graph backend action: load neo4j/gremlin/all, verify without loading, "
            "or health for infrastructure reachability only"
        ),
    )

    args = parser.parse_args()

    # Determine job type
    if args.download:
        job_type = "download"
    elif args.build:
        job_type = f"build-{args.build}"
    elif args.docker:
        job_type = f"docker-{args.docker}"
    elif args.graph is not None:
        if args.graph == "health":
            job_type = "graph-health"
        elif args.dataset:
            job_type = f"load-{args.dataset}-{args.graph}"
        else:
            job_type = "graph-missing-dataset"
    else:
        # If no arguments provided, print help and exit
        parser.print_help()
        sys.exit(0)

    # Set up logging for the selected job
    log_file = setup_logging(job_type)

    logger.info(f"Starting job: {job_type}")
    logger.info(f"Log file: {log_file}")

    try:
        if args.download:
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
        elif args.graph is not None:
            if args.graph != "health" and not args.dataset:
                parser.error("--dataset is required unless --graph health is used.")
            if args.dataset == "all" and args.graph not in {"neo4j", "gremlin", "all", "verify"}:
                parser.error("--dataset all is not supported yet; use attack.")
            if args.dataset == "all":
                raise ValueError("--dataset all is not supported yet; use attack.")
            run_graph_command(dataset=args.dataset, graph=args.graph)
            logger.info("Job completed successfully.")
    except (LoaderResolutionError, ValueError, GraphLoaderNotReadyError, ConnectionError) as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Job {job_type} failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
