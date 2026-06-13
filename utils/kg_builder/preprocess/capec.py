#!/usr/bin/env python3

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

CAPEC_NOT_IMPLEMENTED_MSG = (
    "CAPEC graph artifact build is not yet implemented. "
    "Reserved output: data/processed/pairs/capec.json and data/graphs/capec/."
)


def build_capec_placeholder() -> None:
    """Reserved entry point for future CAPEC preprocessing."""
    logger.info(CAPEC_NOT_IMPLEMENTED_MSG)
