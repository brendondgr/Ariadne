"""EXP-2026-11-015's planner arms, seam by seam (dev-bank runner and variant harness).

What these pin, because each has already produced a plausible wrong number in
this project:

* the model is the REGISTRY entry's endpoint and alias -- never ``--llm-model``,
  whose default ``default-model`` serves Gemma since 2026-11-18;
* the planner seam is on and the specialist, synthesis and conversation seams
  are off, both in the arm's environment and at the call site (``use_llm=True``
  overwrites every ``*_LLM_ENABLED``, so the call site is what decides);
* the three arms differ only in the drafter the planning agent is given;
* the rules-only variant capture is unchanged when no planner arm is chosen.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

import utils.evaluation.experiment_untruncated as exp
from utils.llm.registry import load

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def registry():
    return load()


class TestDevBankArms:
    def test_the_three_arms_are_registered_and_wired(self):
        for arm in exp.PLANNER_ARMS:
            assert arm in exp.ARMS
        assert exp.RUNNERS["planned_llm_english"] is exp.run_planned_english
        assert exp.RUNNERS["planned_llm_typed_lazy"] is exp.run_planned_typed
        assert exp.RUNNERS["planned_llm_typed_full"] is exp.run_planned_typed
        # Existing arms are untouched.
        assert exp.RUNNERS["generic_planned_llm"] is exp.run_planned_llm

    @pytest.mark.parametrize("arm", exp.PLANNER_ARMS)
    def test_env_takes_the_model_from_the_registry_and_pins_the_seams(self, arm, registry):
        qwen = registry["qwen38-27b"]
        env = exp.planner_arm_env(arm, qwen)
        assert env["PLANNER_LLM_ENABLED"] == "true"
        for seam in ("SPECIALIST_LLM_ENABLED", "SYNTHESIS_LLM_ENABLED", "CONVERSATION_LLM_ENABLED",
                     "SPECIALIST_LLM_QUERY_BUILDER", "PLANNER_INTENT_LLM_ENABLED"):
            assert env[seam] == "false", seam
        assert env["SPECIALIST_GENERIC_ONLY"] == "true" and env["ORCH_MAX_HOPS"] == "5"
        assert env["PLANNER_LLM_MODEL"] == qwen.alias == "default-model-2"
        assert env["PLANNER_LLM_BASE_URL"] == qwen.endpoint
        assert env["LLM_REASONING_EFFORT"] == "medium"
        assert env["ARIADNE_PLANNER_REGISTRY_MODEL"] == "qwen38-27b"
        assert env.get("ARIADNE_TYPED_PLANNER") == exp.TYPED_MODES.get(arm)

    def test_gemma_runs_at_its_default_thinking(self, registry):
        env = exp.planner_arm_env("planned_llm_typed_lazy", registry["gemma4-31b"])
        assert env["PLANNER_LLM_MODEL"] == "default-model" and env["LLM_REASONING_EFFORT"] == ""

    def test_the_english_control_is_today_s_generic_planned_llm_posture(self, registry):
        today = exp.untruncated_env(arm="generic_planned_llm", llm_model="x", llm_max_tokens=16384)
        mine = exp.planner_arm_env("planned_llm_english", registry["qwen38-27b"])
        for key in ("SPECIALIST_GENERIC_ONLY", "PLANNER_LLM_ENABLED", "SPECIALIST_LLM_ENABLED",
                    "SYNTHESIS_LLM_ENABLED", "CONVERSATION_LLM_ENABLED", "ARIADNE_REWRITE",
                    "ARIADNE_REWRITE_MODEL"):
            assert mine[key] == today[key], key

    @pytest.mark.parametrize("runner", [exp.run_planned_english, exp.run_planned_typed])
    def test_the_call_site_turns_only_the_planner_on(self, runner, monkeypatch):
        seen = {}

        def fake(entry, kind, **kw):
            seen.update(kw)
            return object(), object(), {}

        monkeypatch.setattr(exp, "_run_real_pipeline", fake)
        monkeypatch.setenv("ARIADNE_TYPED_PLANNER", "lazy")
        monkeypatch.setenv("SPECIALIST_GENERIC_ONLY", "true")
        from utils.agent.tests.scripted import ScriptedModel

        monkeypatch.setattr(exp, "_TYPED_MODEL", ScriptedModel(["{}"]))
        _, _, extra = runner({"id": "x", "question": "q"}, "attack", None)
        assert seen["use_llm"] is True
        assert seen["llm_synthesis"] is False and seen["llm_specialist"] is False
        agent = seen["agent"]
        assert agent._config.llm_enabled is True  # noqa: SLF001
        drafter = type(agent._drafter).__name__  # noqa: SLF001
        assert drafter == ("TypedDrafter" if runner is exp.run_planned_typed else "HybridDrafter")
        assert extra["seams"]["specialist_llm"] is False and extra["seams"]["synthesis_llm"] is False


@pytest.fixture(scope="module")
def vh():
    sys.path.insert(0, str(REPO))
    import scripts.variant_harness as vh

    return vh


class TestVariantHarnessArms:
    def test_arms_and_models(self, vh):
        assert set(vh.PLANNER_ARMS) == {"E", "T-lazy", "T-full", "T-lazy-G"}
        assert vh.PLANNER_ARMS["E"]["typed"] is None
        assert vh.PLANNER_ARMS["T-lazy"] == {"typed": "lazy", "model": "qwen38-27b"}
        assert vh.PLANNER_ARMS["T-full"]["typed"] == "full"
        assert vh.PLANNER_ARMS["T-lazy-G"] == {"typed": "lazy", "model": "gemma4-31b"}

    def test_the_rules_capture_is_called_exactly_as_before(self, vh, monkeypatch):
        calls = []

        def fake_iter(question, **kw):
            calls.append(kw)
            return iter(())

        import utils.orchestration.main as om

        monkeypatch.setattr(om, "iter_pipeline", fake_iter)
        out = vh.capture_one("q", object())
        assert calls[0]["use_llm"] is False and "agent" not in calls[0] and "specialist_config" not in calls[0]
        assert "planner" not in out and "typed" not in out
        assert inspect.signature(vh.capture_one).parameters["planner"].default is None

    def test_a_planner_capture_turns_only_the_planner_on(self, vh, monkeypatch):
        calls = []

        def fake_iter(question, **kw):
            calls.append(kw)
            return iter(())

        import utils.orchestration.main as om
        from utils.agent.tests.scripted import ScriptedModel

        monkeypatch.setattr(om, "iter_pipeline", fake_iter)
        out = vh.capture_one("q", object(), {"typed": "lazy", "model_obj": ScriptedModel(["{}"])})
        kw = calls[0]
        assert kw["use_llm"] is True and kw["specialist_config"].llm_enabled is False
        assert kw["specialist_config"].llm_query_builder is False
        assert type(kw["agent"]._drafter).__name__ == "TypedDrafter"  # noqa: SLF001
        assert "planner" in out and out["typed"] == []
