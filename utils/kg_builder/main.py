#!/usr/bin/env python3

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class KGBuildRunner:
    """Orchestrates portable graph artifact generation from raw MITRE datasets."""

    def __init__(self, data_dir: str | Path = "data", dry_run: bool = False) -> None:
        self.data_dir = Path(data_dir)
        self.dry_run = dry_run

    def build_attack(self) -> None:
        """Build portable ATT&CK graph artifacts under data/graphs/attack/."""
        if self.dry_run:
            logger.info(
                "Dry run: would build ATT&CK portable graph artifacts "
                "(nodes.jsonl, relationships.jsonl, schema, manifest) "
                f"from {self.data_dir / 'raw/attack'}"
            )
            return

        logger.info("ATT&CK graph artifact build is not yet implemented.")
        sys.exit(1)

    def build_capec(self) -> None:
        """CAPEC graph artifact build — reserved for a future implementation phase."""
        logger.info(
            "CAPEC graph artifact build is not yet implemented. "
            "Reserved output: data/processed/pairs/capec.json and data/graphs/capec/."
        )
        sys.exit(2)

    def build_all(self) -> None:
        """Build all available graph artifacts; CAPEC remains future work."""
        self.build_attack()
        logger.info("Skipping CAPEC build (future work).")
