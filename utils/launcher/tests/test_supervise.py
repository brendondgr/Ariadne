"""Supervision: readiness gating, crash reporting, monitor loop. Hermetic."""

from __future__ import annotations

from utils.launcher.supervise import Child, monitor, terminate_all, wait_ready


class FakeProc:
    """Just enough of subprocess.Popen for the supervisor."""

    def __init__(self, exit_after_polls: int | None = None, code: int = 1) -> None:
        self._polls = 0
        self._exit_after = exit_after_polls
        self._code = code
        self.terminated = False
        self.killed = False

    def poll(self):
        self._polls += 1
        if self._exit_after is not None and self._polls > self._exit_after:
            return self._code
        return None

    def terminate(self):
        self.terminated = True
        self._exit_after = 0

    def wait(self, timeout=None):
        return self._code

    def kill(self):
        self.killed = True


def _clockwork():
    """A fake monotonic clock advanced by the fake sleep."""
    state = {"now": 0.0}

    def clock() -> float:
        return state["now"]

    def sleep(seconds: float) -> None:
        state["now"] += seconds

    return clock, sleep


def test_wait_ready_success_after_a_few_polls():
    clock, sleep = _clockwork()
    probes = iter([False, False, True])
    child = Child("api", FakeProc())
    ready, reason = wait_ready(
        child, lambda: next(probes), what="the API",
        timeout_s=10, clock=clock, sleep=sleep,
    )
    assert ready and reason == ""


def test_wait_ready_reports_dead_child_with_tail():
    clock, sleep = _clockwork()
    child = Child("api", FakeProc(exit_after_polls=1, code=3))
    child.remember("ImportError: cannot import name 'foo'")
    ready, reason = wait_ready(
        child, lambda: False, what="the API",
        timeout_s=10, clock=clock, sleep=sleep,
    )
    assert not ready
    assert "exited with code 3" in reason
    assert "ImportError" in reason, "the child's last output must be shown"


def test_wait_ready_times_out_with_named_subject():
    clock, sleep = _clockwork()
    child = Child("web", FakeProc())
    ready, reason = wait_ready(
        child, lambda: False, what="the web app",
        timeout_s=5, clock=clock, sleep=sleep,
    )
    assert not ready and "the web app" in reason and "5s" in reason


def test_monitor_returns_first_exit_and_reports():
    healthy = Child("api", FakeProc())
    dying = Child("web", FakeProc(exit_after_polls=2, code=7))
    seen: list[tuple[str, int]] = []
    code = monitor(
        [healthy, dying], sleep=lambda s: None,
        on_exit=lambda child, c: seen.append((child.name, c)),
    )
    assert code == 7
    assert seen == [("web", 7)]


def test_terminate_all_stops_running_children():
    a, b = FakeProc(), FakeProc(exit_after_polls=0, code=0)
    terminate_all([Child("api", a), Child("web", b)])
    assert a.terminated
    assert not b.terminated, "already-exited children are left alone"
