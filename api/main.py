"""FastAPI application exposing Ariadne capabilities to the web workbench.

Run directly with uvicorn (``uvicorn api.main:app``) or via the root
``app.py`` launcher, which starts this service alongside the Next.js front end.
``utils.config.load_env()`` is invoked at import so the service reads the same
central ``.env`` that ``main.py`` does.
"""

from __future__ import annotations

from datetime import datetime, timezone

from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi import Path as PathParam
from fastapi.responses import StreamingResponse

from utils.config import load_env

from .models import (
    AdminActionRequest,
    ConfigResponse,
    ConfigUpdateRequest,
    ConversationCreateRequest,
    ConversationDetail,
    ConversationListResponse,
    ConversationQueryRequest,
    ConversationRenameRequest,
    ConversationSummary,
    DockerStateModel,
    EvalRunRequest,
    EvaluationReportResponse,
    DATASET_NAME_PATTERN,
    GraphDataset,
    GraphPayloadResponse,
    HealthResponse,
    LiveSourceModel,
    LLMEndpointProbe,
    LLMModelsResponse,
    LLMProbeResponse,
    LlmHealthModel,
    QueryRequest,
)
from .services import conversations as conversations_service
from .services.config import apply_update, read_config, validate_update
from .services.llm_models import list_models, test_endpoint
from .services.evaluation import read_evaluation_report, stream_eval_run
from .services.graph import load_canonical_graph
from .services.health import docker_state, live_sources, llm_health
from .services.infra import stream_admin_action
from .services.query import stream_query_events

# Load the central .env once, mirroring main.py's entry-point behaviour.
load_env()

# Import both specialist backends now, on the import thread, so no request ever
# takes a module import lock.
#
# ``build_specialist`` imports its backend subpackage lazily, which is right for
# the CLI -- a caller that only wants ATT&CK should not pay for the Gremlin
# driver. In the service it is a hazard: the import runs on a LangGraph worker
# thread, and a request that stalls partway through it holds the lock for
# ``utils.specialists.cypher.specialist`` forever. This was observed live on
# 2026-09-07 -- one wedged request, then every later query blocked in
# ``_lock_unlock_module`` inside ``build_specialist``, and eventually /api/health
# stopped answering too. Only a restart cleared it.
#
# The service needs both backends anyway, so paying for them once at startup
# costs nothing and removes the whole failure class. ``build_specialist`` is
# unchanged; these imports simply mean its lazy ones are always already resolved.
from utils.specialists.cypher import specialist as _warm_cypher  # noqa: E402,F401
from utils.specialists.gremlin import specialist as _warm_gremlin  # noqa: E402,F401

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
            backend=s.backend, status=s.status, uri=s.uri, reason=s.reason, nodes=s.nodes
        )
        for s in live_sources()
    ]
    llm = llm_health()
    return HealthResponse(
        sources=sources,
        docker=DockerStateModel(available=available, services=services, reason=reason),
        llm=LlmHealthModel(
            status=llm.status,
            base_url=llm.base_url,
            model=llm.model,
            enabled=llm.enabled,
            reason=llm.reason,
        ),
        checked_at=_utcnow_iso(),
    )


@app.get("/api/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    """Return the resolved LLM and connection settings (Neo4j password redacted)."""
    return read_config()


@app.put("/api/config", response_model=ConfigResponse)
def put_config(request: ConfigUpdateRequest) -> ConfigResponse:
    """Persist a partial settings update to ``.env`` and return the new config.

    Rejected with a 422 naming the field when the update would leave the settings
    incoherent — most importantly a thinking budget at or above ``max_tokens``,
    which makes the model spend its whole allowance reasoning and return empty
    content. Refusing beats clamping: a value the server quietly rewrites is
    indistinguishable downstream from a value the operator chose.
    """
    errors = validate_update(request)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    return apply_update(request)


@app.post("/api/llm/models", response_model=LLMModelsResponse)
def post_llm_models(request: LLMEndpointProbe | None = None) -> LLMModelsResponse:
    """List what the configured (or supplied) endpoint actually serves.

    POST rather than GET because the body may carry an unsaved endpoint and an
    API key, and a secret has no business in a query string. Always 200: an
    unreachable endpoint is reported in the body, since someone's GPU box being
    off is not a fault of this service.
    """
    return list_models(request.scope if request else None, request)


@app.post("/api/llm/test", response_model=LLMProbeResponse)
def post_llm_test(request: LLMEndpointProbe | None = None) -> LLMProbeResponse:
    """Prove the endpoint answers, by sending a real completion.

    Always 200; the verdict is in the body. A failing test is information, not a
    server error.
    """
    return test_endpoint(request.scope if request else None, request)


@app.post("/api/query")
def post_query(request: QueryRequest) -> StreamingResponse:
    """Run the federated pipeline, streaming each stage as a Server-Sent Event."""
    stream = stream_query_events(
        request.question,
        mode=request.mode,
        use_llm=request.drafter == "llm",
        narrate=request.narrate,
        thinking_budget=request.thinking_budget,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@app.get("/api/conversations", response_model=ConversationListResponse)
def get_conversations() -> ConversationListResponse:
    """List saved conversation threads, most-recently-updated first."""
    return ConversationListResponse(
        conversations=conversations_service.list_conversations()
    )


@app.post("/api/conversations", response_model=ConversationSummary)
def post_conversation(request: ConversationCreateRequest) -> ConversationSummary:
    """Create a new (empty) conversation thread."""
    return ConversationSummary(**conversations_service.create_conversation(request.title))


@app.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str) -> ConversationDetail:
    """Return a thread with all of its turns for rehydration."""
    detail = conversations_service.get_conversation(conversation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetail(**detail)


@app.patch("/api/conversations/{conversation_id}", response_model=ConversationSummary)
def patch_conversation(
    conversation_id: str, request: ConversationRenameRequest
) -> ConversationSummary:
    """Rename a conversation thread."""
    renamed = conversations_service.rename_conversation(conversation_id, request.title)
    if renamed is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationSummary(**renamed)


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict[str, bool]:
    """Delete a conversation thread and its turns."""
    deleted = conversations_service.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True}


@app.post("/api/conversation-query")
def post_conversation_query(request: ConversationQueryRequest) -> StreamingResponse:
    """Run one memory-inclusive conversational turn, streaming it as SSE."""
    stream = conversations_service.stream_conversation_events(
        request.question,
        request.conversation_id,
        mode=request.mode,
        use_llm=request.drafter == "llm",
        verify=request.verify,
        narrate=request.narrate,
        thinking_budget=request.thinking_budget,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
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
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@app.get("/api/graph/{dataset}", response_model=GraphPayloadResponse)
def get_graph(
    dataset: Annotated[GraphDataset, PathParam(pattern=DATASET_NAME_PATTERN)],
) -> GraphPayloadResponse:
    """Return nodes and edges from the canonical graph files for visualization."""
    try:
        payload = load_canonical_graph(dataset)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GraphPayloadResponse(**payload)


@app.get("/api/evaluation", response_model=EvaluationReportResponse)
def get_evaluation() -> EvaluationReportResponse:
    """Return the latest committed component + end-to-end evaluation reports."""
    return EvaluationReportResponse(**read_evaluation_report())


@app.post("/api/eval-run")
def post_eval_run(request: EvalRunRequest) -> StreamingResponse:
    """Re-run the end-to-end evaluation live, streaming progress as SSE."""
    stream = stream_eval_run(
        live=request.live, judge=request.judge, limit=request.limit
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
