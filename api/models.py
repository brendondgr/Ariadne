"""Pydantic response/request models for the Ariadne web service.

These shapes are the contract the Next.js front end consumes. The trace/evidence
payloads streamed by the query endpoint are passed through as the backend's own
``to_dict()`` output (already mirrored by ``web/lib/types.ts``), so they are typed
loosely here as ``dict`` rather than re-declared field by field.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

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


# ---------------------------------------------------------------------------
# Configuration (LLM + connection) — view and edit the env-backed settings.
# ---------------------------------------------------------------------------


class LLMGroup(BaseModel):
    """Resolved LLM settings for one agent (planner or specialist)."""

    enabled: bool
    base_url: str
    model: str
    timeout_s: float
    max_tokens: int


class LLMConfig(BaseModel):
    planner: LLMGroup
    specialist: LLMGroup


class ConnectionConfig(BaseModel):
    """Graph-connection settings. The Neo4j password is never returned."""

    neo4j_uri: str
    neo4j_user: str
    neo4j_password_set: bool
    gremlin_uri: str


class ConfigResponse(BaseModel):
    llm: LLMConfig
    connection: ConnectionConfig


def _validate_http_url(value: str | None) -> str | None:
    if value is not None and not value.startswith(("http://", "https://")):
        raise ValueError("base_url must start with http:// or https://")
    return value


class LLMGroupUpdate(BaseModel):
    """Partial update for one agent's LLM settings; every field is optional."""

    enabled: bool | None = None
    base_url: str | None = None
    model: str | None = None
    timeout_s: float | None = Field(default=None, gt=0)
    max_tokens: int | None = Field(default=None, ge=1)

    _check_url = field_validator("base_url")(_validate_http_url)


class ConnectionUpdate(BaseModel):
    neo4j_uri: str | None = None
    neo4j_user: str | None = None
    neo4j_password: str | None = None
    gremlin_uri: str | None = None

    @field_validator("neo4j_uri")
    @classmethod
    def _check_bolt(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("bolt://", "neo4j://", "bolt+s://", "neo4j+s://")):
            raise ValueError("neo4j_uri must start with bolt:// or neo4j://")
        return v

    @field_validator("gremlin_uri")
    @classmethod
    def _check_ws(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("ws://", "wss://")):
            raise ValueError("gremlin_uri must start with ws:// or wss://")
        return v


class ConfigUpdateRequest(BaseModel):
    planner: LLMGroupUpdate | None = None
    specialist: LLMGroupUpdate | None = None
    connection: ConnectionUpdate | None = None
