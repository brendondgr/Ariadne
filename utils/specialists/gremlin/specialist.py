#!/usr/bin/env python3
"""Factory for the CAPEC Gremlin specialist.

Wires the four language-specific swap points (builder, validator, connector,
normalizer) into the shared QuerySpecialist scaffold and exposes a single
``build_gremlin_specialist`` entry point.
"""

from __future__ import annotations

from typing import Any

from utils.specialists.base import QuerySpecialist
from utils.specialists.config import SpecialistConfig

from .builder import GremlinQueryBuilder
from .connector import GremlinConnector
from .normalizer import GremlinNormalizer
from .validator import GremlinValidator


def build_gremlin_specialist(card: Any, config: SpecialistConfig) -> QuerySpecialist:
    """Construct a ``QuerySpecialist`` for the CAPEC Gremlin backend.

    *card* must be the ``SourceCardView`` for ``dataset == "capec"`` (loaded
    from the real source card, not the fixture).  *config* provides the
    Gremlin URI and operational limits; the card's ``connection.uri`` is
    intentionally ignored per project convention.
    """
    gremlin_uri = config.endpoint_for("gremlin")
    return QuerySpecialist(
        card=card,
        builder=GremlinQueryBuilder(),
        validator=GremlinValidator(),
        connector=GremlinConnector(gremlin_uri),
        normalizer=GremlinNormalizer(),
        max_retries=config.max_retries,
    )
