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


class LlmHealthModel(BaseModel):
    """Reachability of the synthesis LLM endpoint for the header status pill."""

    status: Literal["live", "down"]
    base_url: str
    model: str
    enabled: bool
    reason: str | None = None


class HealthResponse(BaseModel):
    sources: list[LiveSourceModel]
    docker: DockerStateModel
    llm: LlmHealthModel
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
    synthesis: LLMGroup
    eval: LLMGroup


class ConnectionConfig(BaseModel):
    """Graph-connection settings. The Neo4j password is never returned."""

    neo4j_uri: str
    neo4j_user: str
    neo4j_password_set: bool
    gremlin_uri: str


class OrchestrationGroup(BaseModel):
    """Resolved LangGraph orchestration settings (utils/orchestration)."""

    checkpointer: bool
    recursion_limit: int
    pipeline_timeout_s: float


class ConfigResponse(BaseModel):
    llm: LLMConfig
    connection: ConnectionConfig
    orchestration: OrchestrationGroup


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


class OrchestrationUpdate(BaseModel):
    """Partial update for the orchestration settings; every field is optional."""

    checkpointer: bool | None = None
    recursion_limit: int | None = Field(default=None, ge=1)
    pipeline_timeout_s: float | None = Field(default=None, gt=0)


class ConfigUpdateRequest(BaseModel):
    planner: LLMGroupUpdate | None = None
    specialist: LLMGroupUpdate | None = None
    synthesis: LLMGroupUpdate | None = None
    eval: LLMGroupUpdate | None = None
    connection: ConnectionUpdate | None = None
    orchestration: OrchestrationUpdate | None = None


# ---------------------------------------------------------------------------
# Query — the federated pipeline request (streamed back as SSE).
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    mode: Literal["plan", "query"] = "query"
    drafter: Literal["deterministic", "llm"] = "deterministic"


# ---------------------------------------------------------------------------
# Conversations — persisted, memory-inclusive threads.
# ---------------------------------------------------------------------------


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    turn_count: int = 0


class ConversationTurn(BaseModel):
    id: str
    conversation_id: str
    seq: int
    role: str
    created_at: str
    question: str | None = None
    payload: dict | None = None
    mode: str | None = None
    drafter: str | None = None
    route: str | None = None


class ConversationDetail(ConversationSummary):
    turns: list[ConversationTurn] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary] = Field(default_factory=list)


class ConversationCreateRequest(BaseModel):
    title: str | None = None


class ConversationRenameRequest(BaseModel):
    title: str = Field(min_length=1)


class ConversationQueryRequest(BaseModel):
    question: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    mode: Literal["plan", "query"] = "query"
    drafter: Literal["deterministic", "llm"] = "deterministic"


# ---------------------------------------------------------------------------
# Admin — infrastructure / data / graph actions (mirrors main.py modes).
# ---------------------------------------------------------------------------

AdminAction = Literal[
    "docker-status",
    "docker-start",
    "docker-stop",
    "graph-health",
    "graph-load",
    "graph-verify",
    "graph-stop",
    "data-download",
    "data-build",
    "yolo-all",
]


class AdminActionRequest(BaseModel):
    action: AdminAction
    dataset: Literal["attack", "capec", "all"] | None = None
    graph: Literal["neo4j", "gremlin", "all"] | None = None
    force: bool = False
    dry_run: bool = False
    neo4j_version: str | None = None
    gremlin_version: str | None = None


# ---------------------------------------------------------------------------
# Graph visualization — canonical file-based graph payload.
# ---------------------------------------------------------------------------

GraphDataset = Literal["attack", "capec"]


class GraphNodeModel(BaseModel):
    id: str
    label: str
    labels: list[str]
    name: str
    properties: dict


class GraphEdgeModel(BaseModel):
    id: str
    source: str
    target: str
    type: str


class GraphCountsModel(BaseModel):
    nodes: int
    relationships: int


class GraphPayloadResponse(BaseModel):
    dataset: str
    backend: str
    counts: GraphCountsModel
    nodes_by_label: dict[str, int]
    nodes: list[GraphNodeModel]
    edges: list[GraphEdgeModel]


# ---------------------------------------------------------------------------
# Evaluation — read the committed reports; run the e2e eval live (SSE).
# ---------------------------------------------------------------------------


class EvaluationReportResponse(BaseModel):
    """The latest committed evaluation reports for the dashboard.

    Both blocks are the reports' own JSON (already shaped by the report
    builders and mirrored in ``web/lib/types.ts``), so they are typed loosely as
    ``dict`` here. ``available`` is false for a report whose file is absent.
    """

    component_available: bool
    e2e_available: bool
    component: dict | None = None
    e2e: dict | None = None


class EvalRunRequest(BaseModel):
    """Trigger a live end-to-end evaluation run (streamed back as SSE)."""

    live: bool = True
    judge: bool = False
    limit: int | None = Field(default=None, ge=1)
