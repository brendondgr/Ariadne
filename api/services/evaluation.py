"""Serve the committed evaluation reports and run the e2e eval live (SSE).

``read_evaluation_report`` returns the last-written ``component-evaluation.json``
and ``e2e-evaluation.json`` from ``docs/evaluation/`` — a fast, always-available
surface that needs no Docker stack (it just serves committed JSON), with an
``available`` flag per report so the dashboard degrades gracefully.

``stream_eval_run`` re-runs the end-to-end evaluation in a worker thread,
forwarding the runner's log output as SSE ``log`` events then a terminal
``done`` carrying the fresh headline metrics — mirroring the admin runner. It is
slow and needs both backends up, so it is a deliberate user action, not a page
load.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from pathlib import Path
from typing import Any, Iterator

from utils.graph_loader.config import LoaderConfig

from .infra import _QueueLogHandler, _sse

logger = logging.getLogger("ariadne.api.evaluation")

_COMPONENT_JSON = "component-evaluation.json"
_E2E_JSON = "e2e-evaluation.json"


def _reports_dir() -> Path:
    # docs/ lives at the project root, resolved the same way LoaderConfig finds data/.
    root = Path(LoaderConfig.from_data_dir().data_dir).resolve().parent
    return root / "docs" / "evaluation"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:  # pragma: no cover - defensive
        logger.warning("could not read %s: %s", path, exc)
        return None


def read_evaluation_report() -> dict[str, Any]:
    """Return the committed component + e2e reports (each with an availability flag)."""
    reports = _reports_dir()
    component = _read_json(reports / _COMPONENT_JSON)
    e2e = _read_json(reports / _E2E_JSON)
    return {
        "component_available": component is not None,
        "e2e_available": e2e is not None,
        "component": component,
        "e2e": e2e,
    }


def _headline(report: dict[str, Any] | None) -> dict[str, Any]:
    """Pull the four e2e headline numbers for the done event (best-effort).

    ``report`` is the read-endpoint payload; its ``e2e`` field holds the full
    e2e report file, whose own score block is again keyed ``e2e``.
    """
    scores = (report or {}).get("e2e", {})
    if not isinstance(scores, dict):
        return {}
    block = scores.get("e2e", {})
    if not block.get("live"):
        return {}
    o = block["overall"]
    return {
        "cross_source_exact": o["cross_source_accuracy"]["exact_match"]["rate"],
        "mapping_recall": o["mapping_recall"]["micro_recall"],
        "provenance": o["provenance_correctness"]["fully_provenanced"]["rate"],
        "inspectability": o["analyst_inspectability"]["mean_inspectability"],
        "judge_source": o["llm_judge"]["source"],
    }


def stream_eval_run(
    *, live: bool = True, judge: bool = False, limit: int | None = None
) -> Iterator[str]:
    """Run the end-to-end evaluation in a worker thread, streaming progress."""
    sink: "queue.Queue[Any]" = queue.Queue()
    handler = _QueueLogHandler(sink)
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))

    root = logging.getLogger()
    prior_level = root.level
    root.addHandler(handler)
    if prior_level == logging.NOTSET or prior_level > logging.INFO:
        root.setLevel(logging.INFO)

    def run() -> None:
        try:
            from utils.evaluation.run_e2e_eval import main as run_e2e_eval

            argv: list[str] = []
            if not live:
                argv.append("--no-live")
            if judge:
                argv.append("--judge")
            if limit is not None:
                argv += ["--limit", str(limit)]
            run_e2e_eval(argv)
            sink.put(("done", {"ok": True, "message": "e2e evaluation completed",
                               "metrics": _headline(read_evaluation_report())}))
        except Exception as exc:  # noqa: BLE001 - report failure, don't crash the stream
            logger.exception("e2e evaluation failed")
            sink.put(("done", {"ok": False, "message": f"{type(exc).__name__}: {exc}"}))
        finally:
            sink.put(None)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()

    try:
        yield _sse("status", {"message": "running end-to-end evaluation"})
        while True:
            item = sink.get()
            if item is None:
                break
            kind, data = item
            yield _sse(kind, data)
    finally:
        root.removeHandler(handler)
        root.setLevel(prior_level)
