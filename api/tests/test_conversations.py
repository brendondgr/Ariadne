"""Contract tests for the conversations CRUD + conversation-query SSE endpoints.

CRUD is exercised through the TestClient with the service store pointed at a temp
SQLite file. The conversational stream is exercised by calling
``stream_conversation_events`` directly with an injected extraction runner + stub
LLM clients, so the tests are deterministic and need no live graph backend.
"""

from __future__ import annotations

import json
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

import api.main as main
from api.main import app
from api.services import conversations as convo_service
from utils.conversation.store import ConversationStore
from utils.orchestration.main import PipelineRun
from utils.specialists.federation import FederatedEvidence
from utils.synthesis.contracts import (
    Claim,
    ClaimVerdict,
    SynthesizedAnswer,
    VerificationReport,
)

client = TestClient(app)


@pytest.fixture()
def temp_store(tmp_path, monkeypatch):
    store = ConversationStore(tmp_path / "threads.sqlite3")
    monkeypatch.setattr(convo_service, "_store", store)
    return store


def _collect(gen: Iterator[str]) -> list[tuple[str, dict]]:
    events = []
    for frame in gen:
        assert frame.endswith("\n\n")
        head, _, body = frame.partition("\n")
        event = head.removeprefix("event: ")
        data = json.loads(body.removeprefix("data: ").strip())
        events.append((event, data))
    return events


class _StubLLM:
    def __init__(self, replies, *, enabled=True):
        self._replies = list(replies)
        self.enabled = enabled
        self.calls = 0

    def complete(self, messages, **kwargs):
        self.calls += 1
        if not self._replies:
            return ""
        return self._replies[min(self.calls - 1, len(self._replies) - 1)]


def _verified_answer():
    claims = [Claim(text="CAPEC-98 maps to T1566"), Claim(text="CAPEC-98 maps to T1598")]
    verification = VerificationReport(
        verdicts=[ClaimVerdict(verdict="supported"), ClaimVerdict(verdict="supported")]
    )
    return SynthesizedAnswer(
        request="q", narrative="CAPEC-98 maps to T1566 and T1598.",
        claims=claims, verification=verification,
    )


def _forwarding_runner(answer):
    canned = PipelineRun(
        question="q", answer=answer, evidence=FederatedEvidence(request="q"),
        status="answered", exit_code=0,
    )

    def runner(question, *, mode, use_llm, run, forward=None, **kw):
        if forward is not None:
            forward("status", {"phase": "querying"})
            forward("answer", {
                "plan": None, "evidence": canned.evidence,
                "status": "answered", "exit_code": 0,
                "synthesized": canned.answer,
            })
        run.answer = canned.answer
        run.evidence = canned.evidence
        run.status = canned.status
        run.exit_code = canned.exit_code
        return run

    return runner


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #


def test_create_list_get_rename_delete(temp_store):
    # Create.
    created = client.post("/api/conversations", json={}).json()
    cid = created["id"]
    assert created["title"] == "New conversation"
    assert created["turn_count"] == 0

    # List.
    listed = client.get("/api/conversations").json()["conversations"]
    assert [c["id"] for c in listed] == [cid]

    # Get (with turns).
    detail = client.get(f"/api/conversations/{cid}").json()
    assert detail["turns"] == []

    # Rename.
    renamed = client.patch(f"/api/conversations/{cid}", json={"title": "My Thread"}).json()
    assert renamed["title"] == "My Thread"

    # Delete.
    assert client.delete(f"/api/conversations/{cid}").json() == {"deleted": True}
    assert client.get(f"/api/conversations/{cid}").status_code == 404


def test_get_missing_conversation_404(temp_store):
    assert client.get("/api/conversations/nope").status_code == 404


def test_rename_missing_conversation_404(temp_store):
    assert client.patch("/api/conversations/nope", json={"title": "x"}).status_code == 404


def test_delete_missing_conversation_404(temp_store):
    assert client.delete("/api/conversations/nope").status_code == 404


# --------------------------------------------------------------------------- #
# Conversation-query streaming
# --------------------------------------------------------------------------- #


def test_stream_persists_turns_and_autotitles(temp_store):
    convo = temp_store.create_conversation("New conversation")
    events = _collect(
        convo_service.stream_conversation_events(
            "Which techniques map to CAPEC-98?",
            convo.id,
            store=temp_store,
            runner=_forwarding_runner(_verified_answer()),
            naming_client=_StubLLM(["Phishing Mappings"]),
        )
    )
    names = [e for e, _ in events]
    assert names[0] == "status"  # orchestrating
    assert "route" in names and "final" in names
    assert names[-1] == "done"

    # Auto-title assigned on the first turn, surfaced in the conversation event.
    convo_event = dict(events)["conversation"]
    assert convo_event["title"] == "Phishing Mappings"

    # Two turns persisted (user + assistant), with verified facts on the assistant.
    turns = temp_store.list_turns(convo.id)
    assert [t.role for t in turns] == ["user", "assistant"]
    assert turns[1].payload["facts"] == [
        "CAPEC-98 maps to T1566",
        "CAPEC-98 maps to T1598",
    ]
    assert temp_store.get_conversation(convo.id).title == "Phishing Mappings"


def test_stream_missing_conversation_emits_error(temp_store):
    events = _collect(
        convo_service.stream_conversation_events(
            "q", "missing", store=temp_store,
            runner=_forwarding_runner(_verified_answer()),
        )
    )
    assert events[0][0] == "error"
    assert "not found" in events[0][1]["message"]


def test_stream_empty_question_emits_error(temp_store):
    convo = temp_store.create_conversation("t")
    events = _collect(
        convo_service.stream_conversation_events(
            "   ", convo.id, store=temp_store,
            runner=_forwarding_runner(_verified_answer()),
        )
    )
    assert events[0][0] == "error"


def test_second_turn_keeps_title_and_builds_memory(temp_store):
    convo = temp_store.create_conversation("New conversation")
    runner = _forwarding_runner(_verified_answer())
    # First turn -> auto-title.
    _collect(
        convo_service.stream_conversation_events(
            "Which techniques map to CAPEC-98?", convo.id, store=temp_store,
            runner=runner, naming_client=_StubLLM(["Phishing Mappings"]),
        )
    )
    # Second turn -> title unchanged, history now has 2 prior turns.
    events = _collect(
        convo_service.stream_conversation_events(
            "tell me more about T1598", convo.id, store=temp_store,
            runner=runner, naming_client=_StubLLM(["SHOULD NOT BE USED"]),
        )
    )
    convo_event = dict(events)["conversation"]
    assert convo_event["title"] == "Phishing Mappings"  # not re-titled
    assert len(temp_store.list_turns(convo.id)) == 4


def test_conversation_query_endpoint_streams(temp_store, monkeypatch):
    def _fake_stream(question, conversation_id, **kw):
        yield "event: done\ndata: {\"status\": \"answered\"}\n\n"

    monkeypatch.setattr(
        main.conversations_service, "stream_conversation_events", _fake_stream
    )
    resp = client.post(
        "/api/conversation-query",
        json={"question": "q", "conversation_id": "c1"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert "event: done" in resp.text


def test_conversation_query_rejects_empty_question(temp_store):
    resp = client.post(
        "/api/conversation-query", json={"question": "", "conversation_id": "c1"}
    )
    assert resp.status_code == 422
