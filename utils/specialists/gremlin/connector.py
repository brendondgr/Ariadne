#!/usr/bin/env python3
"""Gremlin connector for the CAPEC specialist.

Wraps gremlin-python's Client for bounded, read-only query execution.
Connects lazily (on the first run() call, or explicitly via connect()),
applies the task's timeout, caps rows, and surfaces any backend failure
as an ExecutionError so the scaffold loop can handle it uniformly.
"""

from __future__ import annotations

import logging
from typing import Any

from utils.specialists.errors import ExecutionError

logger = logging.getLogger("ariadne.specialists.gremlin")


class GremlinConnector:
    """Bounded, read-only Gremlin execution (Connector protocol)."""

    def __init__(self, uri: str) -> None:
        self._uri = uri
        self._client: Any = None  # gremlin_python.driver.client.Client | None

    # -- Connector protocol --------------------------------------------------

    def connect(self) -> None:
        """Open the Gremlin client connection."""
        try:
            from gremlin_python.driver import client as gremlin_client
            from gremlin_python.driver.serializer import GraphSONSerializersV3d0

            self._client = gremlin_client.Client(
                self._uri,
                "g",
                message_serializer=GraphSONSerializersV3d0(),
            )
            logger.debug("Gremlin connected: %s", self._uri)
        except Exception as exc:
            raise ExecutionError(f"Gremlin connect failed: {exc}") from exc

    def close(self) -> None:
        """Close the Gremlin client, swallowing errors."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                logger.debug("Gremlin close failed", exc_info=True)
            finally:
                self._client = None

    def run(
        self,
        query: str,
        params: dict[str, Any],
        limits: dict[str, int],
    ) -> list[dict[str, Any]]:
        """Submit *query* with *params* and return up to max_result_rows rows.

        Raises ExecutionError on any backend failure.
        """
        if self._client is None:
            self.connect()

        timeout_ms: int = limits.get("query_timeout_ms", 5000) or 5000
        timeout_s: float = timeout_ms / 1000.0
        max_rows: int = limits.get("max_result_rows", 1000) or 1000

        try:
            result_set = self._client.submit(query, bindings=params)
            rows: list[Any] = result_set.all().result(timeout=timeout_s)
        except Exception as exc:
            raise ExecutionError(str(exc)) from exc

        # Cap to max_result_rows (belt-and-suspenders: the query already has .limit).
        capped: list[dict[str, Any]] = []
        for row in rows[:max_rows]:
            if isinstance(row, dict):
                capped.append(row)
            else:
                # elementMap() always returns dict; include unexpected shapes as-is
                # so the normalizer can inspect them.
                capped.append({"_raw": row})
        return capped
