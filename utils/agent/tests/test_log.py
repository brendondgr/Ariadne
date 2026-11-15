"""Era 2 Step 3: the run log, rebuild, fork, the driver, and resume (offline)."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import threading
import time
from pathlib import Path

import pytest

from utils.agent.contracts import AgentRequest, Budget
from utils.agent.log import EVENT_TYPES, RunLog
from utils.agent.rebuild import NOT_RUN, pending_calls, rebuild, trim_unresolved
from utils.agent.runner import drive, resume, start
from utils.agent.tests.scripted import FOUR_STEPS, ScriptedModel, toolbox

REQ = AgentRequest(question="How many matches did Norway play?", graph="wwc")


@pytest.fixture
def log(tmp_path):
    with RunLog(tmp_path / "runs.sqlite", commit="testcommit") as lg:
        yield lg


# --------------------------------------------------------------------------- #
# Append and read
# --------------------------------------------------------------------------- #


def test_request_is_the_first_event_and_seq_is_ordered(log):
    rid = log.create_run(REQ)
    log.append(rid, "fast_path", {"confident": False})
    ev = log.events(rid)
    assert [(e.seq, e.type) for e in ev] == [(1, "request"), (2, "fast_path")]
    assert ev[0].payload["question"] == REQ.question
    assert all(e.tree_commit == "testcommit" for e in ev)
    assert log.run(rid)["state"] == "running"


def test_unknown_event_type_is_refused(log):
    rid = log.create_run(REQ)
    with pytest.raises(ValueError):
        log.append(rid, "note", {})


def test_event_types_are_the_planned_set():
    assert set(EVENT_TYPES) == {"request", "fast_path", "model_call", "repair", "tool_call", "tool_result",
                                "validator", "clarification", "answer", "envelope", "error", "state"}


def _writer(path: str, rid: str, tag: str, n: int) -> None:
    with RunLog(path, commit="c") as lg:
        for i in range(n):
            lg.append(rid, "error", {"writer": tag, "i": i})


def test_concurrent_writers_get_gap_free_ordered_seqs(tmp_path):
    path = str(tmp_path / "runs.sqlite")
    with RunLog(path, commit="c") as lg:
        rid = lg.create_run(REQ)
    ctx = mp.get_context("fork")
    procs = [ctx.Process(target=_writer, args=(path, rid, f"p{k}", 150)) for k in range(4)]
    threads = [threading.Thread(target=_writer, args=(path, rid, f"t{k}", 150)) for k in range(4)]
    for w in (*procs, *threads):
        w.start()
    for w in (*procs, *threads):
        w.join()
    assert all(p.exitcode == 0 for p in procs)
    with RunLog(path, commit="c") as lg:
        ev = lg.events(rid)
    assert [e.seq for e in ev] == list(range(1, 1 + 1 + 8 * 150))
    by_writer: dict[str, list[int]] = {}
    for e in ev[1:]:
        by_writer.setdefault(e.payload["writer"], []).append(e.payload["i"])
    assert len(by_writer) == 8 and all(v == list(range(150)) for v in by_writer.values())


def test_append_overhead_is_small(log):
    rid = log.create_run(REQ)
    n = 300
    t = time.perf_counter()
    for i in range(n):
        log.append(rid, "error", {"i": i, "detail": "x" * 200})
    per_ms = (time.perf_counter() - t) / n * 1000
    assert per_ms < 5.0, f"{per_ms:.2f} ms per append"


# --------------------------------------------------------------------------- #
# Rebuild
# --------------------------------------------------------------------------- #


def _model_call(log, rid, calls, step=1, text=""):
    return log.append(rid, "model_call", {
        "step": step, "text": text, "finish_reason": "tool_calls", "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "seconds": 0.5, "tool_calls": [{"id": cid, "name": n, "arguments": a, "source": "native"} for cid, n, a in calls]},
        served_model="m/1")


def test_rebuild_two_calls_two_results(log):
    rid = log.create_run(REQ)
    _model_call(log, rid, [("a", "resolve_entity", {"text": "Norway", "label": "Team"}),
                           ("b", "resolve_entity", {"text": "Sweden", "label": "Team"})], text="Resolving both.")
    log.append(rid, "tool_result", {"id": "a", "name": "resolve_entity", "content": {"handle": "set:1"}})
    log.append(rid, "tool_result", {"id": "b", "name": "resolve_entity", "content": {"handle": "set:2"}})
    msgs = rebuild(log.events(rid), "SYSTEM")
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "tool", "tool"]
    assert msgs[1]["content"] == REQ.question
    assert msgs[2]["content"] == "Resolving both."
    assert [c["id"] for c in msgs[2]["tool_calls"]] == ["a", "b"]
    assert json.loads(msgs[2]["tool_calls"][0]["function"]["arguments"]) == {"label": "Team", "text": "Norway"}
    assert [(m["tool_call_id"], json.loads(m["content"])) for m in msgs[3:]] == [
        ("a", {"handle": "set:1"}), ("b", {"handle": "set:2"})]


def test_rebuild_missing_result_gets_the_not_run_placeholder(log):
    rid = log.create_run(REQ)
    _model_call(log, rid, [("a", "count", {"handle": "set:1"}), ("b", "count", {"handle": "set:2"})])
    log.append(rid, "tool_result", {"id": "a", "name": "count", "content": {"total": 3}})
    msgs = rebuild(log.events(rid))
    assert msgs[-1] == {"role": "tool", "tool_call_id": "b", "content": NOT_RUN}
    assert [c["id"] for c in pending_calls(log.events(rid))] == ["b"]


def test_bad_arguments_are_sent_back_as_written(log):
    rid = log.create_run(REQ)
    log.append(rid, "model_call", {"step": 1, "text": "", "tool_calls": [
        {"id": "a", "name": "count", "arguments": None, "raw_arguments": "handle=set 1", "error": "bad"}]})
    msgs = rebuild(log.events(rid))
    assert msgs[-2]["tool_calls"][0]["function"]["arguments"] == "handle=set 1"


def test_rebuild_requires_the_request_first(log):
    with pytest.raises(ValueError):
        rebuild([])


# --------------------------------------------------------------------------- #
# Fork
# --------------------------------------------------------------------------- #


def test_fork_drops_a_trailing_unresolved_step(log):
    rid = log.create_run(REQ)
    _model_call(log, rid, [("a", "resolve_entity", {"text": "Norway", "label": "Team"})])
    log.append(rid, "tool_result", {"id": "a", "name": "resolve_entity", "content": {"handle": "set:1"}})
    seq_unresolved = _model_call(log, rid, [("b", "expand", {"handle": "set:1"}), ("c", "expand", {"handle": "set:1"})], step=2)
    log.append(rid, "tool_call", {"id": "b", "name": "expand", "arguments": {"handle": "set:1"}})
    log.append(rid, "tool_result", {"id": "b", "name": "expand", "content": {"handle": "set:2"}})
    log.append(rid, "repair", {"kind": "args_loose_json"})
    fid = log.fork(rid, at_seq=log.events(rid)[-1].seq)
    kept = [e for e in log.events(fid) if e.type != "state"]
    assert [e.type for e in kept] == ["request", "model_call", "tool_result"]
    assert all(e.seq < seq_unresolved for e in log.events(rid)[:3])
    run = log.run(fid)
    assert run["parent_id"] == rid and run["state"] == "running"
    assert len(log.events(rid)) == 7                     # the parent is untouched


def test_fork_of_a_finished_run_reopens_it(log):
    rid = start(log, REQ)
    env = drive(log, rid, ScriptedModel(FOUR_STEPS), toolbox())
    assert env.status == "answered"
    fid = log.fork(rid, at_seq=log.events(rid)[-1].seq)
    assert not any(e.type == "envelope" for e in log.events(fid))
    env2 = drive(log, fid, ScriptedModel(FOUR_STEPS), toolbox())
    assert env2.comparable() | {"run_id": None} == env.comparable() | {"run_id": None}


def test_trim_keeps_a_resolved_tail(log):
    rid = log.create_run(REQ)
    _model_call(log, rid, [("a", "count", {})])
    log.append(rid, "tool_result", {"id": "a", "name": "count", "content": {}})
    assert [e.type for e in trim_unresolved(log.events(rid))] == ["request", "model_call", "tool_result"]


# --------------------------------------------------------------------------- #
# The driver
# --------------------------------------------------------------------------- #


def test_scripted_run_answers_with_exact_sets_and_a_full_log(log):
    rid = start(log, REQ)
    env = drive(log, rid, ScriptedModel(FOUR_STEPS), toolbox())
    assert env.status == "answered" and env.path == "loop"
    assert env.answer.sets[0].model_dump() == {"handle": "set:2", "kind": "Match", "total": 3, "complete": True,
                                               "ids": ["match:1995-06-06", "match:1995-06-10", "match:1995-06-13"]}
    assert env.trace.tools == ["resolve_entity", "expand", "finish"] and env.trace.steps == 3
    assert env.trace.served_model == "scripted/0"
    types = [e.type for e in log.events(rid)]
    assert types == ["request",
                     "model_call", "tool_call", "tool_result",
                     "model_call", "tool_call", "tool_result",
                     "model_call", "tool_call", "tool_result", "answer", "envelope", "state"]
    assert log.run(rid)["state"] == "done"
    assert drive(log, rid, ScriptedModel([]), toolbox()) == env          # a finished run returns its envelope


def test_finish_with_an_unknown_handle_is_refused_and_the_model_retries(log):
    steps = [FOUR_STEPS[0], [("finish", {"answer": "x", "handles": ["set:9"]})],
             [("finish", {"answer": "One team.", "handles": ["set:1"]})]]
    env = drive(log, start(log, REQ), ScriptedModel(steps), toolbox())
    assert env.status == "answered" and env.answer.sets[0].handle == "set:1"


def test_step_budget_ends_the_run_insufficient(log):
    req = REQ.model_copy(update={"budget": Budget(steps=2)})
    loop = [[("resolve_entity", {"text": "Norway", "label": "Team"})]] * 5
    env = drive(log, start(log, req), ScriptedModel(loop), toolbox())
    assert env.status == "insufficient" and "step budget" in env.reason and env.trace.steps == 2


def test_text_only_reply_ends_insufficient(log):
    env = drive(log, start(log, REQ), ScriptedModel(["I am not sure."]), toolbox())
    assert env.status == "insufficient" and "without calling finish" in env.reason


def test_unknown_tool_is_answered_with_a_fix(log):
    steps = [[("drop_db", {})], FOUR_STEPS[0], FOUR_STEPS[1], FOUR_STEPS[2]]
    rid = start(log, REQ)
    drive(log, rid, ScriptedModel(steps), toolbox())
    first = next(e for e in log.events(rid) if e.type == "tool_result")
    assert "unknown tool" in first.payload["content"]["error"] and "fix" in first.payload["content"]


# --------------------------------------------------------------------------- #
# Crash and resume
# --------------------------------------------------------------------------- #


def _crash_after(path: str, rid: str, k: int) -> None:
    """Drive the run, killing the process right after the k-th append of this process."""
    count = [0]
    real = RunLog.append

    def append(self, *a, **kw):
        seq = real(self, *a, **kw)
        count[0] += 1
        if count[0] == k:
            os._exit(17)
        return seq

    RunLog.append = append
    with RunLog(path, commit="c") as lg:
        drive(lg, rid, ScriptedModel(FOUR_STEPS), toolbox())
    os._exit(0)


def test_a_crash_at_every_append_resumes_to_the_same_envelope(tmp_path):
    ref_path = tmp_path / "ref.sqlite"
    with RunLog(ref_path, commit="c") as lg:
        ref_id = start(lg, REQ)
        reference = drive(lg, ref_id, ScriptedModel(FOUR_STEPS), toolbox()).comparable()
        appends = len(lg.events(ref_id)) - 1                     # all but the request
        ref_types = [e.type for e in lg.events(ref_id)]
    ctx = mp.get_context("fork")
    for k in range(1, appends + 1):
        path = str(tmp_path / f"crash{k}.sqlite")
        with RunLog(path, commit="c") as lg:
            rid = start(lg, REQ)
        p = ctx.Process(target=_crash_after, args=(path, rid, k))
        p.start()
        p.join()
        assert p.exitcode in (17, 0), f"k={k}: exit {p.exitcode}"
        with RunLog(path, commit="c") as lg:
            if p.exitcode == 17:
                assert lg.run(rid)["state"] in ("running", "done"), k
            env = drive(lg, rid, ScriptedModel(FOUR_STEPS), toolbox())
            got = env.comparable()
            types = [e.type for e in lg.events(rid)]
        got["run_id"] = reference["run_id"]
        assert got == reference, f"crash after append {k} gave a different envelope"
        # no call is logged twice, whatever the crash point
        assert types.count("tool_call") == ref_types.count("tool_call"), (k, types)
        assert types.count("tool_result") == ref_types.count("tool_result"), (k, types)


# --------------------------------------------------------------------------- #
# Clarification: pause and resume
# --------------------------------------------------------------------------- #

ASK = [("ask_caller", {"why": "two teams match", "questions": [{
    "header": "Which Norway?", "question": "Women's or men's team?",
    "options": [{"label": "Norway (women)"}, {"label": "Norway (men)"}]}]})]


def test_interactive_run_pauses_and_resumes_where_it_asked(log):
    req = REQ.model_copy(update={"interactive": True})
    steps = [ASK, *FOUR_STEPS]
    rid = start(log, req)
    paused = drive(log, rid, ScriptedModel(steps), toolbox())
    assert paused.status == "needs_clarification" and paused.clarification.resume == rid
    assert paused.clarification.questions[0].options[0].label == "Norway (women)"
    assert log.run(rid)["state"] == "needs_clarification"
    assert drive(log, rid, ScriptedModel(steps), toolbox()) == paused        # still waiting
    resume(log, rid, {"Which Norway?": "Norway (women)"})
    msgs = rebuild(log.events(rid))
    assert json.loads(msgs[-1]["content"]) == {"answers": {"Which Norway?": "Norway (women)"}}
    env = drive(log, rid, ScriptedModel(steps), toolbox())
    assert env.status == "answered" and env.trace.tools[0] == "ask_caller"
    with pytest.raises(ValueError):
        resume(log, rid, {})                                                  # not paused any more


def test_non_interactive_run_never_pauses(log):
    env = drive(log, start(log, REQ), ScriptedModel([ASK, *FOUR_STEPS]), toolbox())
    assert env.status == "answered"
    assert "ask_caller" not in [t["function"]["name"] for t in toolbox().specs(False)]


def test_malformed_question_is_returned_to_the_model(log):
    req = REQ.model_copy(update={"interactive": True})
    bad = [("ask_caller", {"why": "x", "questions": [{"header": "H", "question": "Q", "options": [{"label": "only"}]}]})]
    rid = start(log, req)
    env = drive(log, rid, ScriptedModel([bad, *FOUR_STEPS]), toolbox())
    assert env.status == "answered"
    first = next(e for e in log.events(rid) if e.type == "tool_result")
    assert "malformed" in first.payload["content"]["error"]


def test_a_crash_while_paused_resumes_cleanly(tmp_path):
    path = tmp_path / "runs.sqlite"
    req = REQ.model_copy(update={"interactive": True})
    steps = [ASK, *FOUR_STEPS]
    with RunLog(path, commit="c") as lg:
        rid = start(lg, req)
        drive(lg, rid, ScriptedModel(steps), toolbox())
    with RunLog(path, commit="c") as lg:                     # a new process, later
        resume(lg, rid, {"Which Norway?": "Norway (women)"})
    with RunLog(path, commit="c") as lg:
        assert drive(lg, rid, ScriptedModel(steps), toolbox()).status == "answered"


# --------------------------------------------------------------------------- #
# Provenance
# --------------------------------------------------------------------------- #


def test_every_model_call_names_its_served_model_and_usage(log):
    rid = start(log, REQ)
    drive(log, rid, ScriptedModel(FOUR_STEPS), toolbox())
    prov = log.provenance(rid)
    assert prov["ok"] and prov["models"] == ["scripted/0"] and prov["model_calls"] == 3
    assert prov["commits"] == ["testcommit"]


def test_provenance_flags_a_call_without_identity(log):
    rid = log.create_run(REQ)
    log.append(rid, "model_call", {"step": 1, "usage": {}})
    prov = log.provenance(rid)
    assert not prov["ok"] and prov["missing_served_model"] == [2] and prov["missing_usage"] == [2]


def test_tree_commit_is_recorded_from_git():
    from utils.agent.log import tree_commit
    c = tree_commit(Path(__file__).resolve().parents[3])
    assert len(c.split("-")[0]) == 40
