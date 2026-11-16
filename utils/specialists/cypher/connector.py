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
from ..rows import Rows

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

    def __init__(self, config: SpecialistConfig, dataset: str | None = None) -> None:
        self._config = config
        # Which source this connector serves. Without it every Neo4j-backed
        # source in the process shares one URI, so a second such source queries
        # the first one's store.
        self._dataset = dataset
        self._driver: neo4j.Driver | None = None

    # -- Connector protocol ----------------------------------------------------

    def connect(self) -> None:
        """Create the Neo4j driver (does not open a session yet)."""
        try:
            self._driver = GraphDatabase.driver(
                self._config.endpoint_for("neo4j", self._dataset),
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
    ) -> Rows:
        """Execute ``query`` with ``params`` and return at most ``max_result_rows`` rows.

        Never silently: the returned :class:`~utils.specialists.rows.Rows` says
        whether the database had more (one extra record is read to find out).
        If the query's own LIMIT equals the cap, ``truncated`` is None (unknown)
        when the cap is reached, and the scaffold probes.

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
                more = False
                for record in result:
                    if len(rows) >= max_rows:
                        more = True          # a record beyond the cap exists
                        break
                    rows.append(dict(record))
                truncated: bool | None = True if more else (None if len(rows) >= max_rows else False)
                return Rows(rows, truncated=truncated, ceiling=max_rows)
        except Exception as exc:
            raise ExecutionError(str(exc)) from exc
