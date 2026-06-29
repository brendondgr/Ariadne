#!/usr/bin/env python3
"""Gremlin connector for the CAPEC specialist.

Wraps gremlin-python's Client for bounded, read-only query execution: applies
the task timeout, caps rows, and surfaces any backend failure as an
``ExecutionError`` so the scaffold loop can handle it uniformly.

Event-loop isolation: gremlin-python's default ``AiohttpTransport`` drives its
own asyncio loop via ``run_until_complete``. Inside a host that already runs an
event loop (a Jupyter kernel), that raises "Cannot run the event loop while
another loop is running". To be robust in both the plain-process CLI and a
notebook, the client and every submit are confined to a **dedicated single
worker thread** that has no running loop of its own.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from utils.specialists.errors import ExecutionError

logger = logging.getLogger("ariadne.specialists.gremlin")


class GremlinConnector:
    """Bounded, read-only Gremlin execution (Connector protocol).

    All gremlin-python calls run on a private single-thread executor so the
    driver's internal event loop never collides with a host loop (e.g. Jupyter).
    """

    def __init__(self, uri: str) -> None:
        self._uri = uri
        self._client: Any = None  # gremlin_python.driver.client.Client | None
        self._executor: ThreadPoolExecutor | None = None

    # -- Connector protocol --------------------------------------------------

    def connect(self) -> None:
        """Start the worker thread and open the Gremlin client inside it."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="gremlin-conn"
            )
        try:
            self._executor.submit(self._connect_in_worker).result()
            logger.debug("Gremlin connected: %s", self._uri)
        except Exception as exc:
            raise ExecutionError(f"Gremlin connect failed: {exc}") from exc

    def _connect_in_worker(self) -> None:
        from gremlin_python.driver import client as gremlin_client
        from gremlin_python.driver.serializer import GraphSONSerializersV3d0

        self._client = gremlin_client.Client(
            self._uri,
            "g",
            message_serializer=GraphSONSerializersV3d0(),
        )

    def close(self) -> None:
        """Close the Gremlin client (in its worker thread) and stop the thread."""
        if self._executor is not None:
            try:
                if self._client is not None:
                    self._executor.submit(self._close_in_worker).result(timeout=5)
            except Exception:  # noqa: BLE001
                logger.debug("Gremlin close failed", exc_info=True)
            finally:
                self._executor.shutdown(wait=False)
                self._executor = None
                self._client = None

    def _close_in_worker(self) -> None:
        if self._client is not None:
            self._client.close()

    def run(
        self,
        query: str,
        params: dict[str, Any],
        limits: dict[str, int],
    ) -> list[dict[str, Any]]:
        """Submit *query* with *params* and return up to max_result_rows rows.

        Raises ExecutionError on any backend failure.
        """
        if self._executor is None or self._client is None:
            self.connect()

        timeout_ms: int = limits.get("query_timeout_ms", 5000) or 5000
        timeout_s: float = timeout_ms / 1000.0
        max_rows: int = limits.get("max_result_rows", 1000) or 1000

        assert self._executor is not None
        try:
            rows: list[Any] = self._executor.submit(
                self._submit_in_worker, query, params, timeout_s
            ).result()
        except Exception as exc:
            raise ExecutionError(str(exc)) from exc

        # Cap to max_result_rows (belt-and-suspenders: the query already has .limit).
        capped: list[dict[str, Any]] = []
        for row in rows[:max_rows]:
            if isinstance(row, dict):
                capped.append(row)
            else:
                # elementMap() always returns dict; keep unexpected shapes so the
                # normalizer can inspect them.
                capped.append({"_raw": row})
        return capped

    def _submit_in_worker(
        self, query: str, params: dict[str, Any], timeout_s: float
    ) -> list[Any]:
        return self._client.submit(query, bindings=params).all().result(timeout=timeout_s)
