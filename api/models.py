"""Pydantic response/request models for the Ariadne web service.

These shapes are the contract the Next.js front end consumes. The trace/evidence
payloads streamed by the query endpoint are passed through as the backend's own
``to_dict()`` output (already mirrored by ``web/lib/types.ts``), so they are typed
loosely here as ``dict`` rather than re-declared field by field.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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
    """One resolved LLM endpoint — the primary group, or one stage's.

    ``inherited`` names the fields this stage took from the primary group rather
    than setting for itself, which is what lets the settings modal render a stage
    row as "inherit" versus "custom" without guessing. For the primary group it
    is always empty.

    The API key is write-only, exactly like ``neo4j_password``: ``api_key_set``
    says whether one is configured and the value is never returned.
    """

    enabled: bool
    provider: str
    base_url: str
    model: str
    api_key_set: bool = False
    timeout_s: float
    max_tokens: int
    thinking_budget: int = 0
    inherited: list[str] = Field(default_factory=list)


class LLMConfig(BaseModel):
    """The single LLM group, plus each stage's optional deltas.

    This replaces the previous four sibling groups (planner/specialist/synthesis/
    eval). Those were confusing rather than flexible: the chat pane actually ran
    on a fifth group the modal never showed (``CONVERSATION_LLM_*``, which
    silently inherited synthesis), and two of the four it did show were inert for
    a chat turn. Now there is one endpoint everything follows, and ``stages``
    carries the overrides for an operator who genuinely wants a second model.
    """

    default: LLMGroup
    stages: dict[str, LLMGroup] = Field(default_factory=dict)


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
    """Partial update for one LLM group; every field is optional.

    ``inherit`` is what makes "follow the default again" expressible. A field
    simply *omitted* from a partial update means "leave it alone"; a field named
    in ``inherit`` means "clear it, so this stage follows the primary group".
    Collapsing those two into one null value would make it impossible to tell
    them apart on the wire, and the service would have to guess.
    """

    enabled: bool | None = None
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    #: Write-only. Accepted here, never returned; "" is ignored rather than
    #: treated as "clear the key", mirroring how neo4j_password behaves.
    api_key: str | None = None
    timeout_s: float | None = Field(default=None, gt=0)
    max_tokens: int | None = Field(default=None, ge=1)
    thinking_budget: int | None = Field(default=None, ge=0)
    #: Field names to unset for this stage so it inherits the primary group.
    inherit: list[str] = Field(default_factory=list)

    _check_url = field_validator("base_url")(_validate_http_url)

    @model_validator(mode="after")
    def _budget_below_max_tokens(self) -> "LLMGroupUpdate":
        """Refuse a thinking budget that leaves nothing for the answer.

        A budget at or above ``max_tokens`` makes the model spend its whole
        allowance reasoning and return empty content, which reaches a caller as a
        silent "LLM unavailable" rather than an error. Rejected with a named
        field rather than quietly clamped, so the modal can say why and the
        operator keeps the number they chose.

        Only checked when the update carries both halves; the pair moves together
        (see COUPLED_FIELDS in utils.llm.config), so a partial update that sets
        one and not the other is validated against the resolved value in the
        service layer.
        """
        if (
            self.thinking_budget is not None
            and self.max_tokens is not None
            and self.thinking_budget
            and self.thinking_budget >= self.max_tokens
        ):
            raise ValueError(
                f"thinking_budget ({self.thinking_budget}) must be less than "
                f"max_tokens ({self.max_tokens}); use 0 to send no cap"
            )
        return self


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


class LLMEndpointProbe(BaseModel):
    """Unsaved endpoint values from the settings modal.

    Every field is optional and falls back to what is stored, so the modal can
    Refresh a URL the operator has typed without first saving it — and without
    re-sending an API key the server already holds.
    """

    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    #: "default" (or omitted) for the primary group, else a stage name.
    scope: str | None = None

    _check_url = field_validator("base_url")(_validate_http_url)


class ModelEntry(BaseModel):
    """One model a server says it serves. Everything but ``id`` may be absent."""

    id: str
    label: str
    context_window: int | None = None
    max_output_tokens: int | None = None


class LLMModelsResponse(BaseModel):
    """A discovery result. Always HTTP 200 — see ``ok``.

    An unreachable local server is a normal operating state, not a fault of this
    service, so it is reported in the body rather than as a 5xx. ``state`` is one
    of "unreachable", "empty", "no-listing", or "" when models came back; they
    need three different fixes and conflating them frustrates people.
    """

    ok: bool
    state: str = ""
    reason: str = ""
    base_url: str = ""
    provider: str = ""
    models: list[ModelEntry] = Field(default_factory=list)


class LLMProbeResponse(BaseModel):
    """The verdict of the settings modal's Test button. Always HTTP 200."""

    ok: bool
    latency_ms: int = 0
    model: str = ""
    reason: str = ""
    summary: str = ""
    base_url: str = ""
    provider: str = ""


class ConfigUpdateRequest(BaseModel):
    """A partial settings update. Every section is optional.

    ``llm`` edits the one group everything follows; ``llm_stages`` carries
    per-stage overrides keyed by stage name (planner, specialist, synthesis,
    conversation, eval).
    """

    llm: LLMGroupUpdate | None = None
    llm_stages: dict[str, LLMGroupUpdate] = Field(default_factory=dict)
    connection: ConnectionUpdate | None = None
    orchestration: OrchestrationUpdate | None = None


# ---------------------------------------------------------------------------
# Query — the federated pipeline request (streamed back as SSE).
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    mode: Literal["plan", "query"] = "query"
    drafter: Literal["deterministic", "llm"] = "deterministic"
    #: Rewrite the narrative prose with a model, over claims already composed
    #: and verified. Separate from ``drafter`` because ``drafter="llm"`` also
    #: hands QUERY construction to a model, which measures far worse than the
    #: template cascade. The narrator seam is the one measured not to change a
    #: fact: 284/284 claims byte-identical, +0.0000 coverage
    #: (``EXP-2026-09-019`` Step 3). Costs ~1,340x the deterministic composer,
    #: so it is per-request rather than a default.
    narrate: bool = False


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
    #: Same narrator-only seam as ``QueryRequest.narrate``.
    narrate: bool = False


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
