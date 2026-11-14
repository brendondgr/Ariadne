import json
import os
import subprocess
import sys
import textwrap

from utils.killtests import heartbeat
from utils.killtests.stages import ItemCache, Stage


def test_stage_resumes_without_redoing_finished_items(tmp_path):
    calls = []
    st = Stage(tmp_path, "s")
    st.map([(str(i), i) for i in range(5)], lambda x: calls.append(x) or x * 2)
    assert len(calls) == 5
    calls.clear()
    st2 = Stage(tmp_path, "s")
    out = st2.map([(str(i), i) for i in range(8)], lambda x: calls.append(x) or x * 2)
    assert sorted(calls) == [5, 6, 7]
    assert out == {str(i): i * 2 for i in range(8)}


def test_errors_are_recorded_not_cached_and_retried_on_restart(tmp_path):
    st = Stage(tmp_path, "e")
    out = st.map([("a", 1), ("b", 0)], lambda x: 1 / x)
    assert "error" in out["b"] and st.errors == 1
    st2 = Stage(tmp_path, "e")
    assert "b" not in st2.cache and "a" in st2.cache


def test_torn_cache_line_is_skipped(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text(json.dumps({"key": "a", "value": 1}) + "\n" + '{"key": "b", "va')
    c = ItemCache(p)
    assert "a" in c and "b" not in c


def test_finish_writes_marker_and_output(tmp_path):
    st = Stage(tmp_path, "f")
    assert not st.done
    st.finish({"x": 1})
    assert st.done and Stage(tmp_path, "f").load() == {"x": 1}


def test_killed_process_resumes(tmp_path):
    """A real SIGKILL mid-stage: the restart finishes only what was left."""
    script = textwrap.dedent(f"""
        import os, sys, time
        sys.path.insert(0, {os.getcwd()!r})
        from pathlib import Path
        from utils.killtests.stages import Stage
        st = Stage(Path({str(tmp_path)!r}), "k")
        def fn(x):
            if x == 6 and os.environ.get("DIE"):
                os.kill(os.getpid(), 9)
            return x
        st.map([(str(i), i) for i in range(10)], fn)
        st.finish(len(st.cache))
    """)
    r = subprocess.run([sys.executable, "-c", script], env={**os.environ, "DIE": "1"})
    assert r.returncode != 0
    assert len(ItemCache(tmp_path / "cache" / "k.jsonl")) == 6
    r = subprocess.run([sys.executable, "-c", script], env={k: v for k, v in os.environ.items() if k != "DIE"})
    assert r.returncode == 0
    assert Stage(tmp_path, "k").load() == 10


def test_heartbeat_written(tmp_path):
    heartbeat.configure(tmp_path, run="t")
    heartbeat.beat("s", 3, 10, 0)
    heartbeat.beat("t", 1, 2, 0)
    hb = heartbeat.read(tmp_path)
    assert hb["stages"]["s"]["done"] == 3 and hb["stages"]["t"]["total"] == 2 and hb["run"] == "t"
