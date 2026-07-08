#!/usr/bin/env python3
"""Hermetic tests for the SQLite conversation store.

Each test uses a fresh temp-DB path (``tmp_path``) so nothing touches the real
``data/`` directory and tests never interfere with one another.
"""

from __future__ import annotations

import pytest

from utils.conversation.store import ConversationNotFound, ConversationStore


@pytest.fixture()
def store(tmp_path):
    return ConversationStore(tmp_path / "threads.sqlite3")


def test_creates_db_file_and_parent_dirs(tmp_path):
    db = tmp_path / "nested" / "dir" / "threads.sqlite3"
    ConversationStore(db)
    assert db.exists()


def test_create_and_get_conversation(store):
    convo = store.create_conversation("Phishing techniques")
    assert convo.title == "Phishing techniques"
    assert convo.turn_count == 0
    assert convo.created_at == convo.updated_at

    fetched = store.get_conversation(convo.id)
    assert fetched is not None
    assert fetched.id == convo.id
    assert fetched.title == "Phishing techniques"


def test_get_missing_conversation_returns_none(store):
    assert store.get_conversation("does-not-exist") is None


def test_create_with_explicit_id(store):
    convo = store.create_conversation("Custom", conversation_id="fixed-id")
    assert convo.id == "fixed-id"
    assert store.get_conversation("fixed-id") is not None


def test_append_turns_are_sequenced_and_ordered(store):
    convo = store.create_conversation("thread")
    t0 = store.append_turn(convo.id, "user", question="Which techniques map to CAPEC-98?")
    t1 = store.append_turn(
        convo.id,
        "assistant",
        payload={"headline": "CAPEC-98 maps to T1566 and T1598"},
        route="graph",
        mode="query",
        drafter="llm",
    )
    t2 = store.append_turn(convo.id, "user", question="tell me more about T1598")

    assert (t0.seq, t1.seq, t2.seq) == (0, 1, 2)

    turns = store.list_turns(convo.id)
    assert [t.seq for t in turns] == [0, 1, 2]
    assert [t.role for t in turns] == ["user", "assistant", "user"]
    assert turns[1].payload == {"headline": "CAPEC-98 maps to T1566 and T1598"}
    assert turns[1].route == "graph"
    assert turns[1].mode == "query"
    assert turns[1].drafter == "llm"


def test_append_turn_bumps_updated_at(store):
    convo = store.create_conversation("thread")
    original = store.get_conversation(convo.id)
    assert original is not None
    store.append_turn(convo.id, "user", question="hello")
    bumped = store.get_conversation(convo.id)
    assert bumped is not None
    assert bumped.updated_at >= original.updated_at
    assert bumped.turn_count == 1


def test_append_turn_to_missing_conversation_raises(store):
    with pytest.raises(ConversationNotFound):
        store.append_turn("missing", "user", question="hi")


def test_list_conversations_orders_by_updated_at_desc(store):
    a = store.create_conversation("A")
    b = store.create_conversation("B")
    # Touch A after B so A becomes most-recent.
    store.append_turn(b.id, "user", question="q-b")
    store.append_turn(a.id, "user", question="q-a")

    listed = store.list_conversations()
    assert [c.id for c in listed] == [a.id, b.id]
    assert {c.turn_count for c in listed} == {1}


def test_rename_conversation(store):
    convo = store.create_conversation("Old title")
    renamed = store.rename_conversation(convo.id, "New title")
    assert renamed.title == "New title"
    assert store.get_conversation(convo.id).title == "New title"


def test_rename_missing_conversation_raises(store):
    with pytest.raises(ConversationNotFound):
        store.rename_conversation("missing", "x")


def test_delete_conversation_cascades_turns(store):
    convo = store.create_conversation("thread")
    store.append_turn(convo.id, "user", question="hi")
    store.append_turn(convo.id, "assistant", payload={"a": 1})

    assert store.delete_conversation(convo.id) is True
    assert store.get_conversation(convo.id) is None
    # Cascade removed the turns too.
    assert store.list_turns(convo.id) == []


def test_delete_missing_conversation_returns_false(store):
    assert store.delete_conversation("missing") is False


def test_payload_roundtrips_nested_json(store):
    convo = store.create_conversation("thread")
    payload = {
        "headline": "x",
        "sections": [{"claims": ["a", "b"], "n": 2}],
        "nested": {"deep": {"value": True}},
    }
    store.append_turn(convo.id, "assistant", payload=payload)
    turns = store.list_turns(convo.id)
    assert turns[0].payload == payload


def test_store_persists_across_instances(tmp_path):
    db = tmp_path / "threads.sqlite3"
    store1 = ConversationStore(db)
    convo = store1.create_conversation("persisted")
    store1.append_turn(convo.id, "user", question="hi")

    store2 = ConversationStore(db)
    assert store2.get_conversation(convo.id) is not None
    assert len(store2.list_turns(convo.id)) == 1
