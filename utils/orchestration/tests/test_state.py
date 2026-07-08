"""PipelineState reducers and contract round-tripping through a real graph.

The point of these tests: the graph state must carry the *actual* frozen
contract objects (SpecialistResult, Plan, ...) unmangled, and the accumulate
reducers must let a loop node return only its per-iteration delta.
"""

from langgraph.graph import END, START, StateGraph

from utils.orchestration.state import PipelineState, PlanningState, merge_dicts
from utils.planner.schema import Plan
from utils.specialists.contracts import SpecialistResult, SpecialistTask


def _result(sq_id: str) -> SpecialistResult:
    task = SpecialistTask(sub_question_id=sq_id, source="attack", text="q")
    return SpecialistResult(task=task, ok=True, records=[], summary=f"summary-{sq_id}")


def test_merge_dicts_later_keys_win():
    assert merge_dicts({"a": 1, "b": 1}, {"b": 2, "c": 3}) == {"a": 1, "b": 2, "c": 3}


def test_pipeline_state_accumulates_specialist_deltas():
    """Two loop iterations each return one result; the state holds both."""

    def first(state: PipelineState) -> dict:
        r = _result("sq-1")
        return {"results": [r], "by_id": {"sq-1": r}, "cursor": 1,
                "specialist_timings": [{"sub_question": "sq-1", "ms": 1.0}]}

    def second(state: PipelineState) -> dict:
        assert state["cursor"] == 1  # overwrite semantics
        r = _result("sq-2")
        return {"results": [r], "by_id": {"sq-2": r}, "cursor": 2,
                "specialist_timings": [{"sub_question": "sq-2", "ms": 2.0}]}

    g = StateGraph(PipelineState)
    g.add_node("first", first)
    g.add_node("second", second)
    g.add_edge(START, "first")
    g.add_edge("first", "second")
    g.add_edge("second", END)
    out = g.compile().invoke({"question": "q", "mode": "query"})

    assert [r.task.sub_question_id for r in out["results"]] == ["sq-1", "sq-2"]
    assert set(out["by_id"]) == {"sq-1", "sq-2"}
    assert out["cursor"] == 2
    assert [t["ms"] for t in out["specialist_timings"]] == [1.0, 2.0]
    # The objects come back as the same frozen dataclasses, not copies/dicts.
    assert isinstance(out["results"][0], SpecialistResult)
    assert out["results"][0] is out["by_id"]["sq-1"]


def test_pipeline_state_contracts_round_trip_unmangled():
    plan = Plan(request="what techniques?")

    def put(state: PipelineState) -> dict:
        return {"plan": plan, "timings": {"plan_ms": 12.5}}

    def add_timing(state: PipelineState) -> dict:
        return {"timings": {"total_ms": 99.0}}

    g = StateGraph(PipelineState)
    g.add_node("put", put)
    g.add_node("add_timing", add_timing)
    g.add_edge(START, "put")
    g.add_edge("put", "add_timing")
    g.add_edge("add_timing", END)
    out = g.compile().invoke({"question": "q"})

    assert out["plan"] is plan
    assert out["plan"].to_dict()["request"] == "what techniques?"
    # timings merge across nodes rather than overwriting.
    assert out["timings"] == {"plan_ms": 12.5, "total_ms": 99.0}


def test_planning_state_trace_accumulates_and_feedback_overwrites():
    def draft1(state: PlanningState) -> dict:
        return {"iteration": 1, "trace": [{"iteration": 1}], "feedback": ["bad join"]}

    def draft2(state: PlanningState) -> dict:
        assert state["feedback"] == ["bad join"]
        return {"iteration": 2, "trace": [{"iteration": 2}], "feedback": None}

    g = StateGraph(PlanningState)
    g.add_node("draft1", draft1)
    g.add_node("draft2", draft2)
    g.add_edge(START, "draft1")
    g.add_edge("draft1", "draft2")
    g.add_edge("draft2", END)
    out = g.compile().invoke({"request": "r"})

    assert [t["iteration"] for t in out["trace"]] == [1, 2]
    assert out["feedback"] is None
    assert out["iteration"] == 2
