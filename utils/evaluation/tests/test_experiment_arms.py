"""Each arm's posture asserted seam by seam, so an arm cannot silently be another.

Two failure shapes this file exists to catch, both of which have already cost
this project a published number.

An arm that *says* it has no language model but inherits one from the operator's
`.env` reports the model's figure under the control's name — `I-4`'s shape, and
the reason `_MODEL_FREE_ARMS` and the preflight exist at all.

And the inverse, which is what `generic_planned` is for: an arm that claims to
run a stage while its runner replays a recorded answer for that stage. Every
headline figure in this programme was produced by a gold-replay runner that
hands the pipeline its plan, so the planner has never executed in any of them.
If `generic_planned` were ever wired to `run_deterministic`, it would produce a
perfectly plausible number for a stage that did not run.
"""

from __future__ import annotations

import utils.evaluation.experiment_untruncated as exp
from utils.evaluation.experiment_untruncated import (
    ARMS,
    RUNNERS,
    _MODEL_FREE_ARMS,
    run_deterministic,
    run_planned,
    run_rewrite,
    untruncated_env,
)

SEAMS = (
    "PLANNER_LLM_ENABLED",
    "SPECIALIST_LLM_ENABLED",
    "SYNTHESIS_LLM_ENABLED",
    "CONVERSATION_LLM_ENABLED",
)


def env_for(arm: str) -> dict[str, str]:
    return untruncated_env(arm=arm, llm_model="unused-model", llm_max_tokens=16384)


class TestGenericPlanned:
    def test_it_is_a_registered_arm(self):
        assert "generic_planned" in ARMS

    def test_it_drives_the_real_pipeline_not_the_gold_replay(self):
        # The entire point of the arm. `run_deterministic` replays the authored
        # plan, so wiring this arm to it would measure nothing.
        assert RUNNERS["generic_planned"] is run_planned
        assert RUNNERS["generic_planned"] is not run_deterministic

    def test_it_does_not_drive_the_rewrite_runner(self):
        # `run_rewrite` passes use_llm=True, which `iter_pipeline` applies as
        # dataclasses.replace(..., llm_enabled=True) over the env-resolved
        # value. Wiring this arm to it would run every seam live against
        # ARIADNE_LLM_BASE_URL while the arm's own env said model-free.
        assert RUNNERS["generic_planned"] is not run_rewrite

    def test_its_control_still_replays_the_authored_plan(self):
        # The other half of the pair must stay what it is, or the difference
        # stops being the plan.
        assert RUNNERS["generic_composed"] is run_deterministic

    def test_every_language_model_seam_is_off(self):
        env = env_for("generic_planned")
        for seam in SEAMS:
            assert env[seam] == "false", f"{seam} is not off"

    def test_the_generic_primitives_are_on(self):
        assert env_for("generic_planned")["SPECIALIST_GENERIC_ONLY"] == "true"

    def test_the_rewrite_stage_is_pinned_off_rather_than_inherited(self):
        # Rewrite is EXP-2026-09-014's variable. Inheriting it from the
        # operator's `.env` would fold two answers into one number.
        env = env_for("generic_planned")
        assert env["ARIADNE_REWRITE"] == "0"
        assert env["ARIADNE_REWRITE_MODEL"] == "0"

    def test_it_differs_from_its_control_in_nothing_but_the_plan(self):
        # Every environment key the two arms share must agree. What differs is
        # the runner, which is asserted above; anything else differing here
        # would mean the paired difference is not the planner.
        planned = env_for("generic_planned")
        composed = env_for("generic_composed")
        shared = set(planned) & set(composed)
        assert {k: planned[k] for k in shared} == {k: composed[k] for k in shared}
        # The only keys planned adds are the pinned rewrite flags, and they are
        # pinned to the shipped default, so they change no behaviour.
        assert set(planned) - set(composed) == {"ARIADNE_REWRITE", "ARIADNE_REWRITE_MODEL"}
        assert set(composed) - set(planned) == set()

    def test_it_skips_the_relay_preflight(self):
        # A model-free arm gated on a relay it never calls fails runs that
        # cannot be affected by the relay.
        assert "generic_planned" in _MODEL_FREE_ARMS

    def test_it_does_not_carry_a_model_id_into_the_run(self):
        # llm_model is threaded through every arm's factory; a model-free arm
        # must not pin it anywhere, or a seam that flips on later inherits it.
        env = env_for("generic_planned")
        assert not [k for k, v in env.items() if v == "unused-model"]


class TestGenericLocalNarrator:
    """The 2B narrator arm: one seam on, everything else held at the control."""

    ARM = "generic_local_narrator"

    def test_only_the_synthesis_seam_is_live(self):
        env = env_for(self.ARM)
        assert env["SYNTHESIS_LLM_ENABLED"] == "true"
        for seam in ("PLANNER_LLM_ENABLED", "SPECIALIST_LLM_ENABLED",
                     "CONVERSATION_LLM_ENABLED"):
            assert env[seam] == "false", f"{seam} is not off"

    def test_it_composes_claims_deterministically(self):
        # The runner is the gold-replay one, so the CLAIMS are composed by the
        # deterministic composer in both this arm and its control. The model
        # rewrites prose over them. If this arm ever drove a claims composer the
        # comparison against generic_composed would stop meaning anything.
        assert RUNNERS[self.ARM] is exp.run_gold_llm

    def test_the_endpoint_is_pinned_rather_than_inherited(self):
        env = env_for(self.ARM)
        assert env["SYNTHESIS_LLM_BASE_URL"].startswith("http")
        assert env["SYNTHESIS_LLM_MODEL"]

    def test_the_endpoint_can_be_repointed_without_editing_code(self, monkeypatch):
        monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://elsewhere:1234/v1")
        monkeypatch.setenv("LOCAL_LLM_MODEL", "other-weights")
        env = env_for(self.ARM)
        assert env["SYNTHESIS_LLM_BASE_URL"] == "http://elsewhere:1234/v1"
        assert env["SYNTHESIS_LLM_MODEL"] == "other-weights"

    def test_the_endpoint_is_read_at_call_time_not_import_time(self, monkeypatch):
        # An import-time environment read is how "LLM-off" runs reached a live
        # model before. If this were a module constant the override above would
        # only work when the env was set before the import.
        monkeypatch.setenv("LOCAL_LLM_MODEL", "late-binding-check")
        assert exp._local_llm_model() == "late-binding-check"

    def test_the_thinking_budget_stays_below_the_token_cap(self):
        # A budget at or above max_tokens is the configuration that returns
        # empty content, which reaches a caller as a silent "LLM unavailable".
        env = env_for(self.ARM)
        assert int(env["SYNTHESIS_LLM_THINKING_BUDGET"]) < int(env["SYNTHESIS_LLM_MAX_TOKENS"])

    def test_the_timeout_is_raised_off_the_120s_default(self):
        # EXP-2026-09-010: the narrator's failures were read time-outs, and a
        # time-out is indistinguishable downstream from a model with nothing to say.
        assert float(env_for(self.ARM)["SYNTHESIS_LLM_TIMEOUT_S"]) > 120.0

    def test_it_differs_from_its_control_only_in_the_narrator(self):
        narrator = env_for(self.ARM)
        composed = env_for("generic_composed")
        shared = set(narrator) & set(composed)
        differing = {k for k in shared if narrator[k] != composed[k]}
        assert differing == {"SYNTHESIS_LLM_ENABLED"}

    def test_it_is_not_treated_as_model_free(self):
        # It has a live seam, so the relay preflight must run for it.
        assert self.ARM not in _MODEL_FREE_ARMS


class TestGenericLocalFull:
    """The specialist seam — the one with a measured downside."""

    ARM = "generic_local_full"

    def test_it_turns_on_the_flag_a_builder_actually_reads(self):
        # SPECIALIST_LLM_ENABLED is NOT that flag. Four other arms set it to
        # mean "LLM drafter/synthesis" and no query builder reads it, so an arm
        # that set only it would run with no model writing any query and report
        # a healthy specialist seam. `utils/specialists/config.py` reads
        # SPECIALIST_LLM_QUERY_BUILDER.
        env = env_for(self.ARM)
        assert env["SPECIALIST_LLM_QUERY_BUILDER"] == "true"

    def test_the_pool_is_built_with_the_query_builder_on(self):
        # The flag alone is not enough: the arm's pool must be constructed with
        # llm_query_builder=True, the same way `llm_query` is.
        import inspect

        source = inspect.getsource(exp.run_arm)
        assert '"llm_query", "generic_local_full"' in source

    def test_it_is_the_narrator_arm_plus_the_specialist_seam(self):
        narrator = env_for("generic_local_narrator")
        full = env_for(self.ARM)
        # Nothing they share may differ: the specialist seam is the only change.
        assert {k: full[k] for k in set(narrator) & set(full)} == narrator
        assert set(full) - set(narrator) == {
            "SPECIALIST_LLM_QUERY_BUILDER", "SPECIALIST_LLM_BASE_URL",
            "SPECIALIST_LLM_MODEL", "SPECIALIST_LLM_MAX_TOKENS",
            "SPECIALIST_LLM_TIMEOUT_S", "LLM_THINKING_BUDGET",
        }

    def test_the_planner_stays_out_of_it(self):
        # Steps 3 and 4 vary the model, not the plan. Both replay the authored
        # decomposition, so they are comparable with generic_composed.
        assert env_for(self.ARM)["PLANNER_LLM_ENABLED"] == "false"

    def test_the_clock_is_long_enough_for_the_budget(self):
        # llm_query's lesson: raising the token budget without raising the clock
        # aborts every call mid-draft, and an aborted call is indistinguishable
        # downstream from a model with nothing to say.
        env = env_for(self.ARM)
        assert float(env["SPECIALIST_LLM_TIMEOUT_S"]) >= 600.0

    def test_it_is_not_treated_as_model_free(self):
        assert self.ARM not in _MODEL_FREE_ARMS


class TestTheLLMPostureIsStatedAtTheCallSite:
    """`use_llm` overwrites the environment, so it is asserted, not assumed.

    On 2026-09-13 a socket trace of `generic_planned` — every seam pinned
    `false` — caught the planner's LLM drafter connecting to the configured
    endpoint. The env said one thing and the call site did another, and the call
    site won. These tests read the argument that actually decides it.
    """

    def _use_llm_passed_by(self, runner, monkeypatch) -> bool:
        captured: dict = {}

        def fake_iter_pipeline(question, *, mode, use_llm, specialists, run, **kw):
            captured["use_llm"] = use_llm
            run.status, run.exit_code = "answered", 0
            yield "answer", {"plan": None, "evidence": {"results": []}, "synthesized": {}}

        import utils.orchestration.main as orch_main

        monkeypatch.setattr(orch_main, "iter_pipeline", fake_iter_pipeline)
        runner({"question": "q", "id": "x"}, "attack", None)
        return captured["use_llm"]

    def test_generic_planned_runs_with_no_model(self, monkeypatch):
        assert self._use_llm_passed_by(run_planned, monkeypatch) is False

    def test_the_rewrite_arms_keep_the_posture_they_were_published_at(self, monkeypatch):
        # Not an endorsement — a lock. EXP-2026-09-014's figures were produced
        # with use_llm=True and changing it here would re-describe them.
        assert self._use_llm_passed_by(run_rewrite, monkeypatch) is True

    def test_the_provenance_records_the_posture_rather_than_asserting_it(self):
        # run_meta used to hardcode "deterministic" whatever ran.
        import inspect

        source = inspect.getsource(exp._run_real_pipeline)
        assert '"use_llm": use_llm' in source


class TestEveryArmDeclaresItsSeams:
    def test_no_model_free_arm_leaves_a_seam_unstated(self):
        # An unset seam is not an off seam: it reads the operator's `.env`.
        for arm in sorted(_MODEL_FREE_ARMS):
            env = env_for(arm)
            for seam in SEAMS:
                assert env.get(seam) == "false", f"{arm}: {seam} is {env.get(seam)!r}"

    def test_every_arm_has_a_runner(self):
        missing = [arm for arm in ARMS if arm not in RUNNERS]
        assert missing == []
