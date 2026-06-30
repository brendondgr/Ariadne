"""FastAPI application exposing Ariadne capabilities to the web workbench.

Run directly with uvicorn (``uvicorn api.main:app``) or via the root
``app.py`` launcher, which starts this service alongside the Next.js front end.
``utils.config.load_env()`` is invoked at import so the service reads the same
central ``.env`` that ``main.py`` does.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from utils.config import load_env

from .models import (
    AdminActionRequest,
    ConfigResponse,
    ConfigUpdateRequest,
    DockerStateModel,
    HealthResponse,
    LiveSourceModel,
    QueryRequest,
)
from .services.config import apply_update, read_config
from .services.health import docker_state, live_sources
from .services.infra import stream_admin_action
from .services.query import stream_query_events

# Load the central .env once, mirroring main.py's entry-point behaviour.
load_env()

app = FastAPI(
    title="Ariadne Workbench API",
    version="0.1.0",
    summary="Web service layer over the Ariadne federated graph pipeline.",
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@app.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Report live/down/starting status for each graph backend plus Docker state."""
    available, services, reason = docker_state()
    sources = [
        LiveSourceModel(
            backend=s.backend, status=s.status, uri=s.uri, reason=s.reason
        )
        for s in live_sources()
    ]
    return HealthResponse(
        sources=sources,
        docker=DockerStateModel(available=available, services=services, reason=reason),
        checked_at=_utcnow_iso(),
    )


@app.get("/api/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    """Return the resolved LLM and connection settings (Neo4j password redacted)."""
    return read_config()


@app.put("/api/config", response_model=ConfigResponse)
def put_config(request: ConfigUpdateRequest) -> ConfigResponse:
    """Persist a partial settings update to ``.env`` and return the new config."""
    return apply_update(request)


@app.post("/api/query")
def post_query(request: QueryRequest) -> StreamingResponse:
    """Run the federated pipeline, streaming each stage as a Server-Sent Event."""
    stream = stream_query_events(
        request.question,
        mode=request.mode,
        use_llm=request.drafter == "llm",
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/admin")
def post_admin(request: AdminActionRequest) -> StreamingResponse:
    """Run an infrastructure/data/graph action, streaming its logs as SSE."""
    stream = stream_admin_action(
        request.action,
        dataset=request.dataset,
        graph=request.graph,
        force=request.force,
        dry_run=request.dry_run,
        neo4j_version=request.neo4j_version,
        gremlin_version=request.gremlin_version,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
