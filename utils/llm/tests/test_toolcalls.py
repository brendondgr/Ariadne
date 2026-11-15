"""Era 2 Step 2: the universal tool-call format, retries and the token policy (offline)."""

from __future__ import annotations

import json

import pytest

from utils.llm.client import RawCompletion
from utils.llm.registry import ModelSpec
from utils.llm.tests.fakeserver import FakeServer, body, native_call, stream
from utils.llm.toolcalls import (
    ModelReply,
    chat,
    finalize,
    refuse_fallback,
    to_wire_messages,
    tool_result_message,
)
from utils.llm.types import LLMUnavailable

TOOLS = [
    {"type": "function", "function": {"name": "resolve_entity", "parameters": {
        "type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "count", "parameters": {
        "type": "object", "properties": {"handle": {"type": "string"}}, "required": ["handle"]}}},
]
KNOWN = {"resolve_entity", "count"}
MSGS = [{"role": "user", "content": "How many matches did Norway play?"}]


def spec(url: str, name: str = "m1", **kw) -> ModelSpec:
    return ModelSpec(name=name, kind="llm", endpoint=url, alias="alias", stop_token_id=106,
                     connect_timeout_s=1.0, read_timeout_s=10.0, **kw)


# --------------------------------------------------------------------------- #
# finalize (pure)
# --------------------------------------------------------------------------- #


def test_native_call_needs_no_repair():
    raw = RawCompletion(tool_calls=[{"id": "c1", "name": "count", "arguments": '{"handle": "set:1"}'}],
                        finish_reason="tool_calls")
    r = finalize(raw, "m", KNOWN)
    assert [(c.name, c.arguments, c.source) for c in r.tool_calls] == [("count", {"handle": "set:1"}, "native")]
    assert r.repairs == [] and r.status == "ok"


def test_native_call_with_truncated_arguments_is_repaired_and_logged():
    raw = RawCompletion(tool_calls=[
        {"id": "c1", "name": "resolve_entity", "arguments": '{"text": "Norw'},
        {"id": "c2", "name": "count", "arguments": '{"handle": "set:1"}'}])
    r = finalize(raw, "m", KNOWN)
    assert r.tool_calls[0].arguments == {"text": "Norw"}
    assert [(e.kind, e.call_id) for e in r.repairs] == [("args_closed_truncated", "c1")]


def test_bad_arguments_are_kept_not_dropped():
    raw = RawCompletion(tool_calls=[{"id": "c1", "name": "count", "arguments": "handle=set 1"}])
    r = finalize(raw, "m", KNOWN)
    c = r.tool_calls[0]
    assert c.bad_arguments and c.arguments is None and c.raw_arguments == "handle=set 1"
    assert [e.kind for e in r.repairs] == ["args_bad"]
    assert c.to_wire()["function"]["arguments"] == "handle=set 1"


def test_leaked_call_in_text_becomes_a_call():
    raw = RawCompletion(content='<|tool_call>call:resolve_entity{text:<|"|>Norway<|"|>}<tool_call|>')
    r = finalize(raw, "m", KNOWN)
    assert [(c.name, c.arguments, c.source) for c in r.tool_calls] == [
        ("resolve_entity", {"text": "Norway"}, "leaked_call_gemma")]
    assert r.text == "" and [e.kind for e in r.repairs] == ["leaked_call_gemma"]


def test_leaks_are_not_looked_for_when_native_calls_exist():
    raw = RawCompletion(content='{"name": "count", "arguments": {"handle": "x"}}',
                        tool_calls=[{"id": "c1", "name": "count", "arguments": "{}"}])
    assert len(finalize(raw, "m", KNOWN).tool_calls) == 1


def test_thinking_in_text_is_split_and_reasoning_kept_apart():
    raw = RawCompletion(content="<think>count it</think>Fourteen.", reasoning="server thinking")
    r = finalize(raw, "m", KNOWN)
    assert r.text == "Fourteen." and "server thinking" in r.thinking and "count it" in r.thinking
    assert "thinking" not in r.assistant_message() and r.assistant_message()["content"] == "Fourteen."


def test_cap_with_no_output_is_cut_off_not_an_error():
    raw = RawCompletion(content="", reasoning="x" * 5000, finish_reason="length",
                        usage={"completion_tokens": 16384})
    r = finalize(raw, "m", KNOWN)
    assert r.status == "cut_off_at_cap" and not r.error
    assert [e.kind for e in r.repairs] == ["cut_off_at_cap"]


def test_empty_without_cap_is_empty():
    assert finalize(RawCompletion(finish_reason="stop"), "m", KNOWN).status == "empty"


# --------------------------------------------------------------------------- #
# Message conversion
# --------------------------------------------------------------------------- #


def test_wire_messages_drop_thinking_and_null_content():
    out = to_wire_messages([
        {"role": "assistant", "content": None, "thinking": "secret",
         "tool_calls": [native_call("count", "{}")]},
        {"role": "tool", "tool_call_id": "call_1", "content": {"total": 3}},
    ])
    assert out[0]["content"] == "" and "thinking" not in out[0]
    assert out[1]["content"] == '{"total": 3}'


def test_tool_result_message():
    assert tool_result_message("c1", {"a": 1}) == {"role": "tool", "tool_call_id": "c1", "content": '{"a": 1}'}


# --------------------------------------------------------------------------- #
# chat() against a scripted server
# --------------------------------------------------------------------------- #


def test_streamed_native_tool_call_is_assembled():
    chunks = stream(
        {"reasoning": "resolve first"},
        {"tool_calls": [{"index": 0, "id": "call_a", "function": {"name": "resolve_entity", "arguments": ""}}]},
        {"tool_calls": [{"index": 0, "function": {"arguments": '{"text": '}}]},
        {"tool_calls": [{"index": 0, "function": {"arguments": '"Norway"}'}}]},
        finish="tool_calls", model="default-model-2")
    with FakeServer([chunks]) as srv:
        r = chat(spec(srv.base_url), MSGS, TOOLS)
    assert [(c.id, c.name, c.arguments) for c in r.tool_calls] == [("call_a", "resolve_entity", {"text": "Norway"})]
    assert r.thinking == "resolve first" and r.envelope_model == "default-model-2"
    assert r.usage["completion_tokens"] == 7 and r.attempts == 1 and r.repairs == []
    sent = srv.requests[0]
    assert sent["tools"] == TOOLS and sent["stream"] is True and sent["max_tokens"] >= 2048


def test_empty_stream_is_retried_once_without_streaming():
    with FakeServer([stream(finish="stop"), body("Fourteen.")]) as srv:
        r = chat(spec(srv.base_url), MSGS, TOOLS)
    assert r.text == "Fourteen." and r.attempts == 2
    assert [e.kind for e in r.repairs] == ["empty_retry"]
    assert srv.requests[0]["stream"] is True and srv.requests[1]["stream"] is False


def test_empty_twice_is_reported_empty():
    with FakeServer([stream(finish="stop"), body("")]) as srv:
        r = chat(spec(srv.base_url), MSGS, TOOLS)
    assert r.status == "empty" and r.attempts == 2


def _runaway_stream():
    span = "I will now count the matches again and again. " * 7   # ~322 chars
    return stream(*[{"content": span} for _ in range(40)], finish="length")


def test_runaway_is_cut_retried_then_succeeds():
    with FakeServer([_runaway_stream(), stream({"content": "Fourteen."})]) as srv:
        r = chat(spec(srv.base_url), MSGS, TOOLS)
    assert r.status == "ok" and r.text == "Fourteen." and r.attempts == 2
    assert [e.kind for e in r.repairs] == ["runaway_retry"]


def test_runaway_twice_is_an_honest_error():
    with FakeServer([_runaway_stream(), _runaway_stream()]) as srv:
        r = chat(spec(srv.base_url), MSGS, TOOLS)
    assert r.status == "runaway" and r.error and not r.text and not r.tool_calls
    assert [e.kind for e in r.repairs] == ["runaway_retry", "runaway_error"]


def test_small_budget_is_refused():
    with pytest.raises(ValueError, match="2,048"):
        chat(spec("http://127.0.0.1:9/v1"), MSGS, max_tokens=512)


def test_unreachable_without_fallback_raises():
    with pytest.raises(LLMUnavailable):
        chat(spec("http://127.0.0.1:9/v1"), MSGS)


def test_fallback_records_both_models_and_runners_refuse_it():
    with FakeServer([body("Fourteen.")]) as srv:
        r = chat(spec("http://127.0.0.1:9/v1", name="primary"), MSGS, stream=False,
                 fallback=spec(srv.base_url, name="backup"))
    assert r.model == "backup" and r.fallback_from == "primary"
    with pytest.raises(RuntimeError, match="fallback"):
        refuse_fallback([r.as_row()])
    assert refuse_fallback([ModelReply(model="m").as_row()])


def test_reasoning_level_is_sent_and_recorded():
    s = ModelSpec(name="q", kind="llm", endpoint="", alias="a", reasoning_param="reasoning_effort",
                  reasoning_values=("xhigh", "medium"), reasoning_default="medium")
    with FakeServer([body("ok")]) as srv:
        s = ModelSpec(**{**s.__dict__, "endpoint": srv.base_url})
        r = chat(s, MSGS, stream=False)
    assert srv.requests[0]["reasoning_effort"] == "medium"
    assert r.request_extra == {"reasoning_effort": "medium"}


def test_row_is_json_serialisable():
    raw = RawCompletion(tool_calls=[{"id": "c1", "name": "count", "arguments": "bad"}])
    json.dumps(finalize(raw, "m", KNOWN).as_row())


def test_capped_reply_last_call_not_closed_but_earlier_calls_are():
    raw = RawCompletion(finish_reason="length", tool_calls=[
        {"id": "c1", "name": "count", "arguments": '{"handle": "set:1'},          # streaming-parser loss
        {"id": "c2", "name": "resolve_entity", "arguments": '{"text": "Norw'}])  # cut off at the cap
    r = finalize(raw, "m", KNOWN)
    assert r.tool_calls[0].arguments == {"handle": "set:1"}
    assert r.tool_calls[1].bad_arguments and "token cap" in r.tool_calls[1].error
    assert [e.kind for e in r.repairs] == ["args_closed_truncated", "args_bad"]


def test_streamed_non_ascii_survives():
    # requests guesses ISO-8859-1 for text/event-stream without a charset.
    chunks = stream({"tool_calls": [{"index": 0, "id": "c", "function": {
        "name": "resolve_entity", "arguments": '{"text": "Zürich – São Paulo"}'}}]}, {"content": "Größe"})
    with FakeServer([chunks]) as srv:
        r = chat(spec(srv.base_url), MSGS, TOOLS)
    assert r.tool_calls[0].arguments == {"text": "Zürich – São Paulo"}


# --------------------------------------------------------------------------- #
# An unclosed think block (MiniCPM 4.7 behind vLLM's reasoning parser, 2026-11-15)
# --------------------------------------------------------------------------- #

THINK_CLOSE = 248069


def test_unclosed_think_reply_is_promoted_to_the_answer_and_logged():
    raw = RawCompletion(content="", reasoning="Okay", finish_reason="stop", token_ids=[31248, 248046])
    r = finalize(raw, "m", KNOWN, think_close_token_id=THINK_CLOSE)
    assert (r.text, r.thinking, r.status) == ("Okay", "", "ok")
    assert [e.kind for e in r.repairs] == ["content_in_reasoning"]


def test_closed_think_with_no_answer_is_not_promoted():
    raw = RawCompletion(content="", reasoning="I should count...", finish_reason="stop",
                        token_ids=[5, 6, THINK_CLOSE, 248046])
    assert finalize(raw, "m", KNOWN, think_close_token_id=THINK_CLOSE).status == "empty"


def test_no_promotion_without_token_ids_or_when_cut_off_or_unconfigured():
    base = dict(content="", reasoning="Okay")
    assert finalize(RawCompletion(**base, finish_reason="stop"), "m", KNOWN,
                    think_close_token_id=THINK_CLOSE).status == "empty"           # no ids: unproven
    assert finalize(RawCompletion(**base, finish_reason="length", token_ids=[1]), "m", KNOWN,
                    think_close_token_id=THINK_CLOSE).status == "cut_off_at_cap"
    assert finalize(RawCompletion(**base, finish_reason="stop", token_ids=[1]), "m", KNOWN).status == "empty"


def test_promoted_reply_can_hold_a_leaked_call():
    raw = RawCompletion(content="", reasoning='<tool_call>{"name": "count", "arguments": {"handle": "set:1"}}</tool_call>',
                        finish_reason="stop", token_ids=[1, 2])
    r = finalize(raw, "m", KNOWN, think_close_token_id=THINK_CLOSE)
    assert [c.name for c in r.tool_calls] == ["count"]
    assert [e.kind for e in r.repairs] == ["content_in_reasoning", "leaked_call_hermes"]


def test_think_close_spec_requests_token_ids():
    s = ModelSpec(name="mc", kind="llm", endpoint="", alias="a", think_close_token_id=THINK_CLOSE)
    with FakeServer([body(None, reasoning="Okay", token_ids=[31248, 248046])]) as srv:
        s = ModelSpec(**{**s.__dict__, "endpoint": srv.base_url})
        r = chat(s, MSGS, stream=False)
    assert srv.requests[0]["return_token_ids"] is True
    assert r.text == "Okay"
