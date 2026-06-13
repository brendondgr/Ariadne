#!/usr/bin/env python3

from __future__ import annotations

import logging
from typing import Any

from ..config import BuildConfig
from ..models import NormalizedGraph

logger = logging.getLogger(__name__)


class AttackPreprocessor:
    """Convert ATT&CK STIX bundle objects into a normalized graph model."""

    def __init__(self, config: BuildConfig) -> None:
        self.config = config

    def preprocess(self, bundle: dict[str, Any]) -> NormalizedGraph:
        raise NotImplementedError("ATT&CK preprocessing will be implemented in step 4.")
