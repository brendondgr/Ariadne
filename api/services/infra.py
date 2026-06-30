"""Infrastructure / data / graph admin actions, streamed as Server-Sent Events.

These wrap the same functions ``main.py`` calls for ``--docker``, ``--graph``,
``--download`` and ``--build``. Each action runs in a worker thread while a
temporary root-logging handler forwards the modules' log output to the client as
``log`` events, followed by a terminal ``done`` event. Several of these are
long-running and host-dependent (a Docker daemon, network access, built
artifacts); failures are reported in the ``done`` event rather than raised.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from typing import Any, Iterator

from utils.graph_loader.main import run_graph_command
from utils.infrastructure import docker_start, docker_status, docker_stop, docker_stop_service

from .health import live_sources

logger = logging.getLogger("ariadne.api.infra")

# Root logger is the only place that catches every module's output (docker,
# graph_loader, download, kg_builder use different logger names). Low-throughput
# admin console, so capturing globally for the action's duration is acceptable.
_LOG_FORMAT = "%(name)s: %(message)s"


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class _QueueLogHandler(logging.Handler):
    """Forward log records to a queue as ('log', {...}) items."""

    def __init__(self, sink: "queue.Queue[Any]") -> None:
        super().__init__()
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:  # noqa: BLE001 - never let logging break the stream
            line = record.getMessage()
        self._sink.put(("log", {"line": line, "level": record.levelname}))


def _dispatch(action: str, **kw: Any) -> dict[str, Any]:
    """Run one admin action; mirrors main.py's dispatch. Returns a result dict."""
    if action == "docker-status":
        return {"services": docker_status()}
    if action == "docker-start":
        docker_start(neo4j_version=kw.get("neo4j_version"), gremlin_version=kw.get("gremlin_version"))
        return {}
    if action == "docker-stop":
        docker_stop()
        return {}
    if action == "graph-health":
        sources = live_sources()
        for s in sources:
            logger.info("%s: %s (%s)", s.backend, s.status, s.reason or "ok")
        return {"sources": [{"backend": s.backend, "status": s.status, "reason": s.reason} for s in sources]}
    if action == "graph-load":
        dataset, graph = kw.get("dataset"), kw.get("graph")
        if not dataset or not graph:
            raise ValueError("graph-load requires both 'dataset' and 'graph'")
        if dataset == "all":
            raise ValueError("dataset 'all' is not supported yet; use attack or capec")
        run_graph_command(dataset=dataset, graph=graph)
        return {}
    if action == "graph-verify":
        dataset = kw.get("dataset")
        if not dataset:
            raise ValueError("graph-verify requires 'dataset'")
        run_graph_command(dataset=dataset, graph="verify")
        return {}
    if action == "data-download":
        from utils.download import DatasetDownloader

        DatasetDownloader(force=bool(kw.get("force"))).download_all()
        return {}
    if action == "data-build":
        from utils.kg_builder import KGBuildRunner

        target = kw.get("dataset") or "all"
        runner = KGBuildRunner(dry_run=bool(kw.get("dry_run")))
        builder = {"attack": runner.build_attack, "capec": runner.build_capec, "all": runner.build_all}
        if target not in builder:
            raise ValueError(f"data-build target must be attack/capec/all, got {target!r}")
        builder[target]()
        return {}
    if action == "graph-stop":
        target = kw.get("graph")
        if not target:
            raise ValueError("graph-stop requires 'graph' (neo4j|gremlin|all)")
        docker_stop_service(target)
        return {"action": "graph-stop", "service": target}
    if action == "yolo-all":
        from utils.yolo import YoloRunner

        results = YoloRunner().run()
        failed = [r.name for r in results if r.status == "failed"]
        needs_input = [r.name for r in results if r.status == "needs_input"]
        return {
            "action": "yolo-all",
            "steps": len(results),
            "failed": failed,
            "needs_input": needs_input,
        }
    raise ValueError(f"unknown admin action {action!r}")


def stream_admin_action(action: str, **kwargs: Any) -> Iterator[str]:
    """Run an admin action in a worker thread, streaming its logs then a result."""
    sink: "queue.Queue[Any]" = queue.Queue()
    handler = _QueueLogHandler(sink)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    root = logging.getLogger()
    prior_level = root.level
    root.addHandler(handler)
    if prior_level == logging.NOTSET or prior_level > logging.INFO:
        root.setLevel(logging.INFO)

    def run() -> None:
        try:
            result = _dispatch(action, **kwargs)
            sink.put(("done", {"ok": True, "message": f"{action} completed", **result}))
        except Exception as exc:  # noqa: BLE001 - report failure, don't crash the stream
            logger.exception("admin action %s failed", action)
            sink.put(("done", {"ok": False, "message": f"{type(exc).__name__}: {exc}"}))
        finally:
            sink.put(None)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()

    try:
        yield _sse("status", {"action": action, "message": f"running {action}"})
        while True:
            item = sink.get()
            if item is None:
                break
            kind, data = item
            yield _sse(kind, data)
    finally:
        root.removeHandler(handler)
        root.setLevel(prior_level)
