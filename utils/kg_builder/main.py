#!/usr/bin/env python3

from __future__ import annotations

import logging
import sys

from .config import BuildConfig
from .preprocess.capec import CAPEC_NOT_IMPLEMENTED_MSG

logger = logging.getLogger(__name__)


class KGBuildRunner:
    """Orchestrates portable graph artifact generation from raw MITRE datasets."""

    def __init__(self, data_dir: str = "data", dry_run: bool = False) -> None:
        self.config = BuildConfig.from_data_dir(data_dir)
        self.dry_run = dry_run

    def build_attack(self) -> None:
        """Build portable ATT&CK graph artifacts under data/graphs/attack/."""
        paths = self.config.paths()
        if self.dry_run:
            logger.info(
                "Dry run: would build ATT&CK portable graph artifacts "
                f"from {paths.attack_raw_file} into {paths.graph_output_dir}"
            )
            return

        logger.info("ATT&CK graph artifact pipeline not yet fully wired.")
        sys.exit(1)

    def build_capec(self) -> None:
        """CAPEC graph artifact build — reserved for a future implementation phase."""
        logger.info(CAPEC_NOT_IMPLEMENTED_MSG)
        sys.exit(2)

    def build_all(self) -> None:
        """Build all available graph artifacts; CAPEC remains future work."""
        self.build_attack()
        logger.info("Skipping CAPEC build (future work).")
