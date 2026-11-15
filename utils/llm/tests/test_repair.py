"""Era 2 Step 2: every reply repair, one fixture per format, offline."""

from __future__ import annotations

import json

import pytest

from utils.llm.repair import (
    REPAIR_KINDS,
    RepairEvent,
    close_json,
    extract_json_object,
    looping,
    loose_json,
    parse_arguments,
    recover_leaked_calls,
    split_thinking,
)

KNOWN = {"resolve_entity", "count", "expand"}


# --------------------------------------------------------------------------- #
# Repair events are a closed set
# --------------------------------------------------------------------------- #


def test_unknown_repair_kind_is_rejected():
    with pytest.raises(ValueError):
        RepairEvent("quietly_fixed")


def test_every_kind_is_constructible_and_serialises():
    for kind in REPAIR_KINDS:
        assert RepairEvent(kind, "d", "c1").as_dict() == {"kind": kind, "detail": "d", "call_id": "c1"}


# --------------------------------------------------------------------------- #
# Leaked calls
# --------------------------------------------------------------------------- #


def _one(text):
    rest, calls = recover_leaked_calls(text, KNOWN)
    assert len(calls) == 1, calls
    return rest, calls[0]


def test_gemma_native_marker():
    rest, c = _one('Let me look.<|tool_call>call:resolve_entity{text:<|"|>Norway<|"|>,label:<|"|>Team<|"|>}<tool_call|>')
    assert (c.name, json.loads(c.arguments), c.kind) == (
        "resolve_entity", {"text": "Norway", "label": "Team"}, "leaked_call_gemma")
    assert rest == "Let me look."


def test_gemma_26b_call_tag():
    _, c = _one('<call:count{"handle": "set:3"}</call>')
    assert (c.name, json.loads(c.arguments)) == ("count", {"handle": "set:3"})


def test_gemma_marker_with_unknown_name_still_counts_when_explicit():
    _, calls = recover_leaked_calls('<|tool_call>call:drop_db{x:1}<tool_call|>', KNOWN)
    assert [c.name for c in calls] == ["drop_db"]          # the loop answers "unknown tool"


def test_bare_name_without_marker_must_be_known():
    _, calls = recover_leaked_calls('call:drop_db{"x": 1}</call>', KNOWN)
    assert calls == []


def test_hermes():
    _, c = _one('<tool_call>{"name": "expand", "arguments": {"handle": "set:1", "relation": "USES"}}</tool_call>')
    assert (c.name, json.loads(c.arguments), c.kind) == (
        "expand", {"handle": "set:1", "relation": "USES"}, "leaked_call_hermes")


def test_known_name_as_tag():
    _, c = _one('<count>{"handle": "set:2"}</count>')
    assert (c.name, c.kind) == ("count", "leaked_call_tag")


def test_unknown_tag_is_not_a_call():
    assert recover_leaked_calls('<note>{"a": 1}</note>', KNOWN)[1] == []


def test_fenced_json_naming_a_tool():
    _, c = _one('```json\n{"name": "count", "arguments": {"handle": "set:9"}}\n```')
    assert (c.name, json.loads(c.arguments), c.kind) == ("count", {"handle": "set:9"}, "leaked_call_json")


def test_bare_json_naming_a_tool():
    _, c = _one('{"name": "count", "parameters": {"handle": "set:9"}}')
    assert json.loads(c.arguments) == {"handle": "set:9"}


def test_json_not_naming_a_known_tool_is_left_alone():
    assert recover_leaked_calls('{"name": "Norway", "kind": "Team"}', KNOWN)[1] == []


def test_python_style_calls_parsed_not_executed():
    rest, calls = recover_leaked_calls("resolve_entity(text='APT29')\ncount(handle='set:1')", KNOWN)
    assert rest == ""
    assert [(c.name, json.loads(c.arguments), c.kind) for c in calls] == [
        ("resolve_entity", {"text": "APT29"}, "leaked_call_python"),
        ("count", {"handle": "set:1"}, "leaked_call_python"),
    ]


def test_python_style_with_non_literal_is_refused():
    # __import__ would run code if evaluated; literal_eval refuses it.
    assert recover_leaked_calls("count(handle=__import__('os').getcwd())", KNOWN)[1] == []


def test_python_style_with_unknown_function_is_refused():
    assert recover_leaked_calls("os.system(cmd='ls')", KNOWN)[1] == []


def test_prose_with_parentheses_is_not_a_call():
    assert recover_leaked_calls("The answer (as counted) is 14.", KNOWN)[1] == []


# --------------------------------------------------------------------------- #
# Arguments
# --------------------------------------------------------------------------- #


def test_valid_arguments_need_no_repair():
    p = parse_arguments('{"handle": "set:1"}')
    assert p.value == {"handle": "set:1"} and p.events == ()


def test_dict_arguments_pass_through():
    assert parse_arguments({"a": 1}).value == {"a": 1}


def test_empty_arguments_are_an_empty_object():
    assert parse_arguments("").value == {}


def test_loose_dialect():
    p = parse_arguments('{text:<|"|>Norway<|"|>,limit:3}', "c1")
    assert p.value == {"text": "Norway", "limit": 3}
    assert [e.kind for e in p.events] == ["args_loose_json"]


def test_truncated_arguments_closed():
    # vLLM's streaming Gemma parser drops the closing "} of all calls but the last.
    p = parse_arguments('{"text": "Norway", "label": "Te')
    assert p.value == {"text": "Norway", "label": "Te"}
    assert [e.kind for e in p.events] == ["args_closed_truncated"]


def test_truncated_after_colon_and_comma():
    assert close_json('{"a": 1, "b":') == {"a": 1, "b": None}
    assert close_json('{"a": [1, 2,') == {"a": [1, 2]}


def test_complete_but_invalid_is_not_closed():
    assert close_json('{"a": 1}}') is None
    assert close_json('{"a": 1}') is None


def test_unrepairable_arguments_are_kept_as_bad():
    p = parse_arguments("handle = set 1", "c9")
    assert p.value is None and "valid JSON" in (p.error or "")
    assert [(e.kind, e.call_id) for e in p.events] == [("args_bad", "c9")]


def test_non_object_arguments_are_bad():
    p = parse_arguments("[1, 2]")
    assert p.value is None and [e.kind for e in p.events] == ["args_not_object"]


def test_loose_json_rejects_non_objects():
    assert loose_json("[1]") is None


# --------------------------------------------------------------------------- #
# Thinking
# --------------------------------------------------------------------------- #


def test_think_tag_split():
    thinking, text, ev = split_thinking("<think>count first</think>\n\nThe answer is 3.")
    assert (thinking, text, [e.kind for e in ev]) == ("count first", "The answer is 3.", ["thinking_split_tag"])


def test_unclosed_think_is_all_thinking():
    thinking, text, _ = split_thinking("<think>still going")
    assert (thinking, text) == ("still going", "")


def test_gemma_channel_split():
    thinking, text, ev = split_thinking("<|channel>thought I should count.<channel|>Fourteen.")
    assert (thinking, text, [e.kind for e in ev]) == ("I should count.", "Fourteen.", ["thinking_split_channel"])


def test_no_markers_no_events():
    assert split_thinking("The user wants a count. Fourteen.") == ("", "The user wants a count. Fourteen.", [])


# --------------------------------------------------------------------------- #
# Free-text JSON (the kill tests' typed requests)
# --------------------------------------------------------------------------- #


def test_fenced_json_reply():
    r = extract_json_object('Here:\n```json\n{"nodes": {}}\n```')
    assert r.value == {"nodes": {}} and [e.kind for e in r.events] == ["json_fenced"]


def test_braces_reply():
    r = extract_json_object('sure: {"a": 1} done')
    assert r.value == {"a": 1} and [e.kind for e in r.events] == ["json_braces"]


def test_clean_json_reply_has_no_events():
    r = extract_json_object('{"a": 1}')
    assert r.value == {"a": 1} and r.events == ()


def test_reply_cut_off_inside_an_unterminated_fence_is_closed():
    r = extract_json_object('```json\n{"nodes": {"n": {"label": "Team"}}, "answer": {"kind": "na')
    assert r.value == {"nodes": {"n": {"label": "Team"}}, "answer": {"kind": "na"}}
    assert "args_closed_truncated" in [e.kind for e in r.events]


def test_think_then_json():
    r = extract_json_object('<think>plan</think>{"a": 1}')
    assert r.value == {"a": 1} and [e.kind for e in r.events] == ["thinking_split_tag"]


def test_no_json_at_all():
    r = extract_json_object("I cannot express this question.")
    assert r.value is None and r.error == "no JSON object in the reply"


def test_empty_reply():
    assert extract_json_object("").value is None


# --------------------------------------------------------------------------- #
# Runaway
# --------------------------------------------------------------------------- #


def test_runaway_detected():
    span = "the same three hundred characters " * 9   # ~306 chars
    assert looping("preamble " + span * 12)


def test_short_or_varied_text_is_not_runaway():
    assert not looping("ok " * 900)          # 2,700 chars: below the 3,000 floor
    assert not looping("".join(f"line {i} differs\n" for i in range(2000)))


def test_truncated_reply_is_never_closed_at_an_inner_brace():
    # Regression: the first-{-to-last-} slice of a truncated reply ends at an
    # inner "}", and closing that slice silently dropped the "answer" field.
    r = extract_json_object('{"nodes": {"n": {"label": "Team"}}, "answer": {"kind": "na')
    assert r.value == {"nodes": {"n": {"label": "Team"}}, "answer": {"kind": "na"}}
    assert "args_closed_truncated" in [e.kind for e in r.events]


def test_trailing_prose_after_a_complete_object_is_not_a_truncation():
    r = extract_json_object('{"a": {"b": 1}} and that is all')
    assert r.value == {"a": {"b": 1}} and [e.kind for e in r.events] == ["json_braces"]


def test_reply_cut_off_at_the_cap_is_not_closed():
    # EXP-2026-11-007: every closed capped reply had lost its tail ("answer" missing,
    # values chopped). A capped reply is incomplete, not a parser artefact.
    r = extract_json_object('```json\n{"nodes": {"n": {"label": "Team", "name": "France 201', cut_off=True)
    assert r.value is None and "token cap" in (r.error or "")
    assert "args_bad" in [e.kind for e in r.events]


def test_cut_off_arguments_are_bad_not_closed():
    p = parse_arguments('{"text": "Norw', "c1", cut_off=True)
    assert p.value is None and [e.kind for e in p.events] == ["args_bad"]


# --------------------------------------------------------------------------- #
# Real replies saved by the kill tests (EXP-2026-11-006 part C)
# --------------------------------------------------------------------------- #

from pathlib import Path  # noqa: E402

REAL = {r["name"]: r for r in json.loads(
    (Path(__file__).parent / "fixtures" / "killtest_replies.json").read_text())}


@pytest.mark.parametrize("name", ["gemma_fenced_ok", "qwen_leading_newlines_fenced_ok"])
def test_real_well_formed_replies_read_like_the_old_parser(name):
    from utils.killtests.typed.prompts import extract_request
    raw = REAL[name]["raw"]
    r = extract_json_object(raw)
    assert r.value == extract_request(raw)
    assert [e.kind for e in r.events] == ["json_fenced"]


def test_real_capped_partial_reply_stays_invalid():
    raw = REAL["gemma_capped_partial_json"]["raw"]
    assert extract_json_object(raw, cut_off=True).value is None
    # Without the cap flag it would "parse" -- the defect EXP-2026-11-007 found.
    assert extract_json_object(raw).value is not None


def test_real_capped_empty_reply_has_nothing_to_recover():
    r = extract_json_object(REAL["gemma_capped_empty"]["raw"], cut_off=True)
    assert r.value is None
