#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from utils.download import DatasetDownloader

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

    args = parser.parse_args()

    # Determine job type
    if args.download:
        job_type = "download"
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
    except Exception as e:
        logger.exception(f"Job {job_type} failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
