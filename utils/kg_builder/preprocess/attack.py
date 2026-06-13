#!/usr/bin/env python3

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import BuildConfig
from ..io import load_json
from ..models import NormalizedGraph

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AttackBundleLoadResult:
    """Result of loading a raw ATT&CK STIX bundle."""

    bundle: dict[str, Any]
    source_path: Path
    bundle_id: str | None
    object_count: int
    attack_version: str


def load_attack_bundle(config: BuildConfig) -> AttackBundleLoadResult:
    """Locate and load the pinned ATT&CK Enterprise STIX bundle."""
    paths = config.paths()
    source_path = paths.attack_raw_file

    if not source_path.exists():
        raise FileNotFoundError(
            f"ATT&CK raw dataset not found at {source_path}. "
            "Run `uv run main.py --download` first."
        )

    bundle = load_json(source_path)
    if bundle.get("type") != "bundle":
        raise ValueError(f"Expected STIX bundle at {source_path}, got type={bundle.get('type')!r}")

    objects = bundle.get("objects")
    if not isinstance(objects, list):
        raise ValueError(f"STIX bundle at {source_path} is missing an objects array.")

    logger.info(
        "Loaded ATT&CK bundle id=%s objects=%d version=%s from %s",
        bundle.get("id"),
        len(objects),
        config.attack_version,
        source_path,
    )

    return AttackBundleLoadResult(
        bundle=bundle,
        source_path=source_path,
        bundle_id=bundle.get("id"),
        object_count=len(objects),
        attack_version=config.attack_version,
    )


class AttackPreprocessor:
    """Convert ATT&CK STIX bundle objects into a normalized graph model."""

    def __init__(self, config: BuildConfig) -> None:
        self.config = config

    def preprocess(self, bundle: dict[str, Any]) -> NormalizedGraph:
        raise NotImplementedError("ATT&CK preprocessing will be implemented in step 4.")
