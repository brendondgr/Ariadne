"""FastAPI application exposing Ariadne capabilities to the web workbench.

Run directly with uvicorn (``uvicorn api.main:app``) or via the root
``app.py`` launcher, which starts this service alongside the Next.js front end.
``utils.config.load_env()`` is invoked at import so the service reads the same
central ``.env`` that ``main.py`` does.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI

from utils.config import load_env

from .models import DockerStateModel, HealthResponse, LiveSourceModel
from .services.health import docker_state, live_sources

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
