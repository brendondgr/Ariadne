"""Setup-wizard steps: idempotency probes, .env writes, orchestration. Hermetic."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

import utils.setup_wizard as wizard
from utils.launcher.preflight import CheckResult, FAIL, PASS
from utils.setup_wizard import _run_step
from utils.setup_wizard.steps import (
    DataStep,
    EnvStep,
    PrerequisitesStep,
    WebDepsStep,
    WizardStep,
    write_port_config,
)
from utils.setup_wizard.ui import WizardUI
from utils.yolo import StepResult

ROOT = Path(__file__).resolve().parents[3]


def scripted_ui(monkeypatch, answers: list[str]) -> WizardUI:
    """A WizardUI whose prompts consume ``answers`` in order."""
    feed = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _="": next(feed))
    return WizardUI(assume_yes=False)


# ── ui ───────────────────────────────────────────────────────────────────────


def test_confirm_parses_yes_no_and_default(monkeypatch):
    ui = scripted_ui(monkeypatch, ["y", "n", ""])
    assert ui.confirm("q?") is True
    assert ui.confirm("q?") is False
    assert ui.confirm("q?", default=False) is False  # empty → default


def test_assume_yes_resolves_every_prompt_to_its_default():
    ui = WizardUI(assume_yes=True)
    assert ui.confirm("q?", default=True) is True
    assert ui.confirm("q?", default=False) is False
    assert ui.prompt_text("label", "the-default") == "the-default"
    assert ui.choose("q?", {"k": "eep", "r": "ecreate"}, "k") == "k"


def test_choose_reprompts_until_valid(monkeypatch):
    ui = scripted_ui(monkeypatch, ["bogus", "r"])
    assert ui.choose("q?", {"k": "eep", "r": "ecreate"}, "k") == "r"


def test_failure_menu_under_yes_retries_once_then_aborts_required():
    ui = WizardUI(assume_yes=True)
    assert ui.failure_menu("Step", "boom", "", required=True) == "retry"
    assert ui.failure_menu("Step", "boom", "", required=True) == "abort"


def test_failure_menu_under_yes_skips_optional_after_retry():
    ui = WizardUI(assume_yes=True)
    assert ui.failure_menu("Opt", "boom", "", required=False) == "retry"
    assert ui.failure_menu("Opt", "boom", "", required=False) == "skip"


# ── .env writes ──────────────────────────────────────────────────────────────


def test_write_port_config_keeps_ports_and_uris_consistent(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("NEO4J_BOLT_PORT=5456\nNEO4J_URI=bolt://localhost:5456\n")

    write_port_config(
        bolt_port="7777", http_port="7778", gremlin_port="7779", env_file=env_file)

    content = env_file.read_text()
    assert "NEO4J_BOLT_PORT=7777" in content
    assert "NEO4J_URI=bolt://localhost:7777" in content
    assert "GREMLIN_PORT=7779" in content
    assert "GREMLIN_URI=ws://localhost:7779/gremlin" in content


def test_env_step_creates_env_from_example(tmp_path):
    (tmp_path / ".env.example").write_text("KEY=value\n")
    step = EnvStep(root=tmp_path)
    assert step.detect() == (False, "")

    result = step.run(WizardUI(assume_yes=True))
    assert result.status == "ok"
    assert (tmp_path / ".env").read_text() == "KEY=value\n"
    assert step.detect()[0] is True


def test_env_step_keeps_existing_env_by_default(tmp_path):
    (tmp_path / ".env.example").write_text("KEY=example\n")
    (tmp_path / ".env").write_text("KEY=mine\n")
    step = EnvStep(root=tmp_path)

    result = step.run(WizardUI(assume_yes=True))
    assert result.status == "ok"
    assert (tmp_path / ".env").read_text() == "KEY=mine\n"


def test_env_step_recreate_backs_up_first(tmp_path, monkeypatch):
    (tmp_path / ".env.example").write_text("KEY=example\n")
    (tmp_path / ".env").write_text("KEY=mine\n")
    ui = scripted_ui(monkeypatch, ["r", ""])  # recreate, then Enter = defaults

    result = EnvStep(root=tmp_path).run(ui)
    assert result.status == "ok"
    assert (tmp_path / ".env").read_text() == "KEY=example\n"
    assert (tmp_path / ".env.bak").read_text() == "KEY=mine\n"


def test_env_step_needs_input_when_example_missing(tmp_path):
    result = EnvStep(root=tmp_path).run(WizardUI(assume_yes=True))
    assert result.status == "needs_input"
    assert ".env.example" in result.detail


# ── prerequisites ────────────────────────────────────────────────────────────


def _fake_check(name: str, status: str) -> CheckResult:
    return CheckResult(name, status, "detail", "fix it")


def test_prerequisites_aggregates_failures():
    step = PrerequisitesStep()
    step.checks = (lambda: _fake_check("npm", PASS), lambda: _fake_check("docker", FAIL))
    result = step.run(WizardUI(assume_yes=True))
    assert result.status == "needs_input"
    assert "docker" in result.detail


def test_prerequisites_ok_when_all_pass():
    step = PrerequisitesStep()
    step.checks = (lambda: _fake_check("npm", PASS),)
    assert step.run(WizardUI(assume_yes=True)).status == "ok"


# ── data / web probes ────────────────────────────────────────────────────────


def test_data_step_detects_missing_and_complete_state(tmp_path, monkeypatch):
    step = DataStep(root=tmp_path)
    assert step.detect() == (False, "")

    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "versions.json").write_text(json.dumps({}))
    for dataset, backend in (("attack", "neo4j"), ("capec", "gremlin")):
        runtime = tmp_path / "data" / "graphs" / dataset / "runtime" / backend
        runtime.mkdir(parents=True)
        (runtime / "load-manifest.json").write_text(json.dumps({}))
    monkeypatch.setattr("utils.setup_wizard.steps._tcp_up", lambda *a, **k: True)

    done, detail = step.detect()
    assert done is True
    assert "loaded" in detail


def test_data_step_not_done_when_backends_down(tmp_path, monkeypatch):
    step = DataStep(root=tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "versions.json").write_text("{}")
    for dataset, backend in (("attack", "neo4j"), ("capec", "gremlin")):
        runtime = tmp_path / "data" / "graphs" / dataset / "runtime" / backend
        runtime.mkdir(parents=True)
        (runtime / "load-manifest.json").write_text("{}")
    monkeypatch.setattr("utils.setup_wizard.steps._tcp_up", lambda *a, **k: False)
    assert step.detect() == (False, "")


def test_web_step_detects_node_modules(tmp_path):
    step = WebDepsStep(root=tmp_path)
    assert step.detect() == (False, "")
    (tmp_path / "web" / "node_modules").mkdir(parents=True)
    assert step.detect()[0] is True


# ── orchestration (_run_step) ────────────────────────────────────────────────


class FakeStep(WizardStep):
    key = "fake"
    title = "Fake Step"
    required = True
    remediation = "do the thing"

    def __init__(self, *, done=(False, ""), outcomes=("ok",)):
        self._done = done
        self._outcomes = list(outcomes)
        self.runs = 0

    def describe(self):
        return "faking …"

    def detect(self):
        return self._done

    def run(self, ui):
        self.runs += 1
        status = self._outcomes.pop(0) if self._outcomes else "ok"
        return StepResult(self.title, status=status, detail=status)


def test_run_step_skips_when_flagged():
    step = FakeStep()
    result = _run_step(step, WizardUI(assume_yes=True), fresh=False, skip=True)
    assert result.status == "skipped"
    assert step.runs == 0


def test_run_step_auto_skips_detected_done_under_yes():
    step = FakeStep(done=(True, "already there"))
    result = _run_step(step, WizardUI(assume_yes=True), fresh=False, skip=False)
    assert result.status == "skipped"
    assert step.runs == 0


def test_run_step_fresh_forces_rerun_despite_detect():
    step = FakeStep(done=(True, "already there"))
    result = _run_step(step, WizardUI(assume_yes=True), fresh=True, skip=False)
    assert result.status == "ok"
    assert step.runs == 1


def test_run_step_retries_once_then_aborts_under_yes():
    step = FakeStep(outcomes=("failed", "failed"))
    result = _run_step(step, WizardUI(assume_yes=True), fresh=False, skip=False)
    assert result.status == "failed"
    assert step.runs == 2  # initial + the one automatic --yes retry


def test_run_step_retry_can_recover():
    step = FakeStep(outcomes=("failed", "ok"))
    result = _run_step(step, WizardUI(assume_yes=True), fresh=False, skip=False)
    assert result.status == "ok"
    assert step.runs == 2


def test_run_step_interactive_skip_after_failure(monkeypatch):
    step = FakeStep(outcomes=("failed",))
    ui = scripted_ui(monkeypatch, ["s"])  # failure menu → [s]kip
    result = _run_step(step, ui, fresh=False, skip=False)
    assert result.status == "skipped"
    assert "skipped after failure" in result.detail


# ── stage 1 (root setup.py) ──────────────────────────────────────────────────


def load_stage1():
    spec = importlib.util.spec_from_file_location("ariadne_setup_stage1", ROOT / "setup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage1_exits_when_uv_missing_under_yes(monkeypatch, capsys):
    stage1 = load_stage1()
    monkeypatch.setattr(stage1.shutil, "which", lambda _: None)
    monkeypatch.setattr(stage1.Path, "home", classmethod(lambda cls: Path("/nonexistent")))
    assert stage1.main(["--yes"]) == 1
    out = capsys.readouterr().out
    assert "astral.sh/uv/install.sh" in out


def test_stage1_syncs_then_execs_stage2_with_forwarded_args(monkeypatch):
    stage1 = load_stage1()
    calls = {}
    monkeypatch.setattr(stage1.shutil, "which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(
        stage1.subprocess, "run",
        lambda cmd, **kw: type("R", (), {"returncode": 0})())
    monkeypatch.setattr(
        stage1.os, "execvp",
        lambda file, args: calls.setdefault("exec", (file, args)))

    stage1.main(["--yes", "--no-launch"])

    file, args = calls["exec"]
    assert file == "/usr/bin/uv"
    assert args[:5] == ["/usr/bin/uv", "run", "python", "-m", "utils.setup_wizard"]
    assert "--yes" in args and "--no-launch" in args
    assert stage1.os.environ["ARIADNE_SETUP_SYNC"] == "ok"
    assert stage1.os.environ["ARIADNE_SETUP_REEXEC"] == "1"


def test_stage1_skip_sync_records_skipped(monkeypatch):
    stage1 = load_stage1()
    calls = {}
    monkeypatch.setattr(stage1.shutil, "which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(
        stage1.subprocess, "run",
        lambda cmd, **kw: pytest.fail("uv sync must not run with --skip-sync"))
    monkeypatch.setattr(
        stage1.os, "execvp",
        lambda file, args: calls.setdefault("exec", (file, args)))

    stage1.main(["--skip-sync", "--yes"])
    assert calls["exec"]
    assert stage1.os.environ["ARIADNE_SETUP_SYNC"] == "skipped"


def test_stage1_sync_failure_stops_under_yes(monkeypatch):
    stage1 = load_stage1()
    monkeypatch.setattr(stage1.shutil, "which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(
        stage1.subprocess, "run",
        lambda cmd, **kw: type("R", (), {"returncode": 2})())
    monkeypatch.setattr(
        stage1.os, "execvp",
        lambda *a: pytest.fail("must not exec stage 2 after a failed sync"))
    assert stage1.main(["--yes"]) == 1


# ── wizard argparse ──────────────────────────────────────────────────────────


def test_parse_args_flags_round_trip():
    args = wizard.parse_args(
        ["--yes", "--fresh", "--skip-data", "--no-launch", "--no-browser", "--prod"])
    assert args.yes and args.fresh and args.skip_data
    assert args.no_launch and args.no_browser and args.prod
    assert not args.skip_env and not args.skip_web
