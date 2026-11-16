"""Era 2 Step 5: result handles (offline)."""

from __future__ import annotations

import pytest

from utils.agent.handles import HandleStore


@pytest.fixture
def store(tmp_path):
    s = HandleStore(tmp_path / "runs.sqlite", "r_1")
    yield s
    s.close()


def test_put_and_get_keep_every_id_sorted_and_deduplicated(store):
    rec = store.put("Technique", ["T3", "T1", "T2", "T1"], query="MATCH …")
    assert rec.handle == "set:1" and rec.ids == ("T1", "T2", "T3") and rec.total == 3 and rec.complete
    assert store.get("set:1") == rec
    assert store.put("Group", ["G1"]).handle == "set:2"


def test_a_complete_set_must_hold_its_whole_total(store):
    with pytest.raises(ValueError):
        store.put("T", ["a"], total=5)
    rec = store.put("T", ["a"], total=5, complete=False)
    assert rec.total == 5 and not rec.complete


@pytest.mark.parametrize("op, want", [("intersect", ("b",)), ("union", ("a", "b", "c")), ("minus", ("a",))])
def test_set_ops(store, op, want):
    a = store.put("X", ["a", "b"]).handle
    b = store.put("X", ["b", "c"]).handle
    out = store.set_op(op, a, b)
    assert out.ids == want and out.complete and out.origin == {"op": op, "inputs": [a, b]}


def test_an_op_on_an_incomplete_set_is_incomplete(store):
    a = store.put("X", ["a"], total=9, complete=False).handle
    b = store.put("X", ["a", "b"]).handle
    assert not store.set_op("intersect", a, b).complete


def test_keyset_paging_over_a_stored_set(store):
    h = store.put("X", [f"id{i:03d}" for i in range(25)]).handle
    pages, after = [], None
    while True:
        p = store.page(h, after, 10)
        if not p:
            break
        pages.append(p)
        after = p[-1]
    assert [len(p) for p in pages] == [10, 10, 5]
    assert sum(pages, []) == list(store.get(h).ids)


def test_handles_survive_a_new_process(tmp_path):
    s1 = HandleStore(tmp_path / "runs.sqlite", "r_9")
    s1.put("X", ["a", "b"])
    s1.close()
    s2 = HandleStore(tmp_path / "runs.sqlite", "r_9")
    assert s2.get("set:1").ids == ("a", "b") and s2.handles() == ["set:1"]
    assert HandleStore(tmp_path / "runs.sqlite", "r_other").handles() == []    # per run
    s2.close()


@pytest.mark.parametrize("bad", ["set:", "set:x", "3", "result:1"])
def test_bad_handles_are_refused(store, bad):
    with pytest.raises(KeyError):
        store.get(bad)


def test_the_handles_table_shares_the_run_log_file(tmp_path):
    from utils.agent.contracts import AgentRequest
    from utils.agent.log import RunLog

    path = tmp_path / "runs.sqlite"
    with RunLog(path, commit="c") as log:
        rid = log.create_run(AgentRequest(question="q", graph="g"))
    s = HandleStore(path, rid)
    s.put("X", ["a"])
    with RunLog(path, commit="c") as log:
        assert log.events(rid)[0].type == "request"
    s.close()
