#!/usr/bin/env python3
"""Factory function for the MITRE ATT&CK / Neo4j Cypher specialist.

Wires the four language-specific swap points (builder, validator, connector,
normalizer) into the shared ``QuerySpecialist`` scaffold.
"""

from __future__ import annotations

from typing import Any

from ..base import QuerySpecialist
from ..config import SpecialistConfig
from .builder import CypherQueryBuilder
from .connector import CypherConnector
from .normalizer import CypherNormalizer
from .validator import CypherValidator
from utils.specialists.llm_builder import LLMQueryBuilder


def build_cypher_specialist(card: Any, config: SpecialistConfig) -> QuerySpecialist:
    """Construct a ``QuerySpecialist`` for the ATT&CK / Neo4j source.

    Args:
        card:   A ``utils.planner.cards.SourceCardView`` for the ``"attack"``
                dataset — used by the validator and normalizer.
        config: A ``SpecialistConfig`` loaded from the environment — supplies
                the Neo4j URI and credentials used by the connector.

    Returns:
        A ``QuerySpecialist`` ready to call ``.run(task)`` with a
        ``SpecialistTask`` targeting ``source="attack"``.
    """
    return QuerySpecialist(
        card=card,
        # The reserved LLM query-builder seam, finally consumed. When
        # SPECIALIST_LLM_QUERY_BUILDER is on, a model writes the query instead of a
        # template being filled — the C-012 baseline. Everything downstream is
        # unchanged, including the gate, which validates the query string and
        # has never looked at draft.template.
        builder=(
            LLMQueryBuilder(
                card=card,
                language='cypher',
                base_url=config.llm_base_url,
                model=config.llm_model,
                timeout_s=config.llm_timeout_s,
            )
            if config.llm_query_builder
            else CypherQueryBuilder()
        ),
        validator=CypherValidator(),
        connector=CypherConnector(config, getattr(card, "dataset", None)),
        normalizer=CypherNormalizer(),
        max_retries=config.max_retries,
    )
