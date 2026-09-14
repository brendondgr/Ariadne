#!/usr/bin/env python3
"""A new thread is titled first, and never on the critical path.

`title_for` reads the question and nothing else, so its old position at the end
of `_persist_turn` cost ~2.9 s at the tail of a first turn and left the sidebar
reading "New conversation" until after the answer was on screen.
"""

from __future__ import annotations

import time

from api.services import conversations as convo_service
from api.tests.test_conversations import (  # reuse the existing fixtures
    _collect,
    _forwarding_runner,
    _verified_answer,
    temp_store,  # noqa: F401 - pytest fixture
)


class _SlowLLM:
    """A titler that takes measurably longer than the rest of the turn."""

    enabled = True

    def __init__(self, delay: float, title: str = "Slow Title") -> None:
        self.delay = delay
        self.title = title

    def complete(self, messages, **kw):  # noqa: ANN001, ANN003
        time.sleep(self.delay)
        return self.title


def test_a_slow_titler_does_not_delay_the_answer(temp_store):  # noqa: F811
    """The pipeline's frames arrive while the titler is still working."""
    convo = temp_store.create_conversation("New conversation")
    started = time.perf_counter()
    first_frame_at: float | None = None
    names: list[str] = []

    for frame in convo_service.stream_conversation_events(
        "Which techniques map to CAPEC-98?",
        convo.id,
        store=temp_store,
        runner=_forwarding_runner(_verified_answer()),
        naming_client=_SlowLLM(0.75),
    ):
        if first_frame_at is None:
            first_frame_at = time.perf_counter() - started
        names.append(frame)

    # The turn's first frame must not have waited on the titler.
    assert first_frame_at is not None and first_frame_at < 0.5, first_frame_at
    # …and the title still lands, resolved at persist time.
    assert any("event: done" in f for f in names)
    assert temp_store.get_conversation(convo.id).title == "Slow Title"


def test_a_failing_titler_falls_back_and_never_sinks_the_turn(temp_store):  # noqa: F811
    class _Boom:
        enabled = True

        def complete(self, messages, **kw):  # noqa: ANN001, ANN003
            raise RuntimeError("endpoint down")

    convo = temp_store.create_conversation("New conversation")
    events = _collect(
        convo_service.stream_conversation_events(
            "Which techniques map to CAPEC-98?",
            convo.id,
            store=temp_store,
            runner=_forwarding_runner(_verified_answer()),
            naming_client=_Boom(),
        )
    )
    names = [e for e, _ in events]
    assert names[-1] == "done"
    # A deterministic title rather than none, and rather than an error frame.
    assert "error" not in names
    assert temp_store.get_conversation(convo.id).title
