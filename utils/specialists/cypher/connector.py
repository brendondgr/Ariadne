#!/usr/bin/env python3
"""Bounded, read-only Neo4j connector for the MITRE ATT&CK specialist.

Opens a Bolt session in ``READ_ACCESS`` mode (Neo4j enforces read-only at the
protocol level), executes a single parameterised Cypher query, and caps results
to ``limits["max_result_rows"]``.  Any Neo4j exception is re-raised as
``ExecutionError`` so the scaffold loop can handle it uniformly.
"""

from __future__ import annotations

import logging
from typing import Any

import neo4j
from neo4j import GraphDatabase, Query

from ..config import SpecialistConfig
from ..errors import ExecutionError

logger = logging.getLogger("ariadne.specialists.cypher")


class CypherConnector:
    """A thin, session-scoped Neo4j connector that enforces read-only access.

    Usage follows the scaffold Connector protocol::

        connector = CypherConnector(config)
        connector.connect()
        rows = connector.run(query, params, limits)
        connector.close()

    The ``QuerySpecialist`` scaffold calls ``connect``/``close`` around the full
    retry loop, so one physical connection can serve multiple query attempts.
    """

    def __init__(self, config: SpecialistConfig) -> None:
        self._config = config
        self._driver: neo4j.Driver | None = None

    # -- Connector protocol ----------------------------------------------------

    def connect(self) -> None:
        """Create the Neo4j driver (does not open a session yet)."""
        try:
            self._driver = GraphDatabase.driver(
                self._config.neo4j_uri,
                auth=(self._config.neo4j_user, self._config.neo4j_password),
            )
        except Exception as exc:
            raise ExecutionError(f"Neo4j driver creation failed: {exc}") from exc

    def close(self) -> None:
        """Close the underlying driver and release all connections."""
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:  # noqa: BLE001
                logger.debug("Neo4j driver close failed", exc_info=True)
            finally:
                self._driver = None

    def run(
        self, query: str, params: dict[str, Any], limits: dict[str, int]
    ) -> list[dict[str, Any]]:
        """Execute ``query`` with ``params`` and return at most ``max_result_rows`` rows.

        Raises:
            ExecutionError: wraps any Neo4j or network exception.
        """
        if self._driver is None:
            raise ExecutionError("CypherConnector.connect() must be called before run()")

        timeout_s = limits.get("query_timeout_ms", self._config.query_timeout_ms) / 1000.0
        max_rows = limits.get("max_result_rows", self._config.max_result_rows)

        try:
            with self._driver.session(
                default_access_mode=neo4j.READ_ACCESS
            ) as session:
                result = session.run(Query(query, timeout=timeout_s), params)
                rows: list[dict[str, Any]] = []
                for record in result:
                    rows.append(dict(record))
                    if len(rows) >= max_rows:
                        break
                return rows
        except Exception as exc:
            raise ExecutionError(str(exc)) from exc
