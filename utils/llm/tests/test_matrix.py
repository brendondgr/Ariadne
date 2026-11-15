"""Era 2 Step 2: the matrix runner refuses swapped models and names the served model (offline)."""

from __future__ import annotations

import pytest

from utils.llm import registry as R
from utils.llm.matrix import run_matrix
from utils.llm.tests.fakeserver import FakeServer, body, native_call


@pytest.fixture(autouse=True)
def _fresh_cache():
    R.clear_identity_cache()
    yield
    R.clear_identity_cache()


def _reg(url: str) -> R.Registry:
    spec = R.ModelSpec(name="fake-gemma", kind="llm", endpoint=url, alias="a", stop_token_id=106,
                       connect_timeout_s=1.0, read_timeout_s=10.0)
    return R.Registry({"fake-gemma": spec}, {}, R.REGISTRY_PATH)


def _finish_turns():
    """A model that resolves, expands, then finishes correctly (non-streamed replies)."""
    return [
        body(None, tool_calls=[native_call("resolve_entity", '{"text": "Norway", "label": "Team"}', "c1")],
             finish="tool_calls"),
        body(None, tool_calls=[native_call("expand", '{"handle": "set:1", "relation": "PLAYED_IN", '
                                                     '"direction": "out"}', "c2")], finish="tool_calls"),
        body(None, tool_calls=[native_call("finish", '{"answer": "14 matches", "handles": ["set:2"]}', "c3")],
             finish="tool_calls"),
    ]


def test_swapped_model_is_refused_without_calls():
    with FakeServer([body("ok", token_ids=[248046])]) as srv:
        res = run_matrix(["fake-gemma"], "toolcall-roundtrip", n_questions=1, registry=_reg(srv.base_url))
    assert [r["status"] for r in res.rows] == ["refused"]
    assert len(srv.requests) == 1 and not res.ok


def test_rows_name_the_served_model_and_pass_the_checks():
    # The fake server ignores "stream", so each streamed attempt gets a JSON body;
    # requests' iter_lines then sees no "data:" lines -> empty -> non-stream retry.
    # Script both attempts so the test exercises the same path as a real server.
    script = [body("ok", token_ids=[106])]
    for b in _finish_turns():
        script += [[{"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}], b]
    script.append(body("ok", token_ids=[106]))
    with FakeServer(script) as srv:
        res = run_matrix(["fake-gemma"], "toolcall-roundtrip", n_questions=1, registry=_reg(srv.base_url))
    (row,) = res.rows
    assert row["status"] == "ran" and row["identity_before"]["last_token_id"] == 106
    assert row["identity_after"]["verified"] is True
    c = row["checks"]
    assert c["called_on_turn_1"] and c["finished"] and c["cited_a_given_handle"] and c["answer_correct"]
    assert c["all_calls_known"] and c["all_arguments_readable"]
    assert all(t["model"] == "fake-gemma" for t in row["turns"])


def test_identity_change_mid_run_marks_rows():
    script = [body("ok", token_ids=[106])]
    for b in _finish_turns():
        script += [[{"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}], b]
    script.append(body("ok", token_ids=[248046]))        # swapped by the end
    with FakeServer(script) as srv:
        res = run_matrix(["fake-gemma"], "toolcall-roundtrip", n_questions=1, registry=_reg(srv.base_url))
    assert [r["status"] for r in res.rows] == ["identity_changed"] and not res.ok


def test_unreachable_model_is_reported_not_skipped():
    res = run_matrix(["fake-gemma"], "toolcall-roundtrip", registry=_reg("http://127.0.0.1:9/v1"))
    assert [r["status"] for r in res.rows] == ["unreachable"]


def test_closed_model_is_not_called():
    spec = R.ModelSpec(name="shut", kind="llm", endpoint="http://127.0.0.1:9/v1", alias="a",
                       stop_token_id=106, status="closed")
    res = run_matrix(["shut"], "toolcall-roundtrip", registry=R.Registry({"shut": spec}, {}, R.REGISTRY_PATH))
    assert [r["status"] for r in res.rows] == ["closed"]
