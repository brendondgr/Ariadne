"""Pydantic response/request models for the Ariadne web service.

These shapes are the contract the Next.js front end consumes. The trace/evidence
payloads streamed by the query endpoint are passed through as the backend's own
``to_dict()`` output (already mirrored by ``web/lib/types.ts``), so they are typed
loosely here as ``dict`` rather than re-declared field by field.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SourceStatus = Literal["live", "down", "starting"]


class LiveSourceModel(BaseModel):
    backend: str
    status: SourceStatus
    uri: str
    nodes: int | None = None
    reason: str | None = None


class DockerStateModel(BaseModel):
    available: bool
    services: dict[str, str] = Field(default_factory=dict)
    reason: str | None = None


class HealthResponse(BaseModel):
    sources: list[LiveSourceModel]
    docker: DockerStateModel
    checked_at: str
