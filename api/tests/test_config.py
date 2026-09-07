"""Contract tests for /api/config (view + edit the env-backed settings).

Invariants: GET exposes one LLM group plus each stage's deltas and never leaks a
secret; PUT validates, persists to the target .env preserving layout, and mirrors
into os.environ so the next read reflects it. The load-bearing one is
:func:`test_stage_override_then_inherit_round_trip` — "follow the default again"
has to *clear* the stage's keys, because writing the default's current values
into the stage would pin a moving target the next time the default changed.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

import utils.config as uconfig
from api.main import app
from api.models import ConfigUpdateRequest
from api.services import config as config_service
from utils.llm.config import FIELD_SUFFIX, STAGES, env_key

client = TestClient(app)

# Every env key these tests may write — saved and restored so nothing leaks
# between tests, or out into the developer's real environment.
_TOUCHED_KEYS = (
    [env_key(f) for f in FIELD_SUFFIX]
    + [env_key(f, stage) for stage in STAGES for f in FIELD_SUFFIX]
    + ["NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "GREMLIN_URI"]
)


@pytest.fixture(autouse=True)
def preserve_env(tmp_path, monkeypatch):
    """Isolate every test from the developer's real environment AND real .env.

    The ENV_FILE redirect is not optional politeness. Any test that PUTs to
    /api/config without it appends to the operator's live .env — which is exactly
    what happened while these tests were being written: two ARIADNE_LLM_* lines
    landed in a real config file and then leaked into a later test run as a
    mystery failure. Autouse, so a new test cannot forget it.
    """
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(uconfig, "ENV_FILE", env_file)

    saved = {k: os.environ.get(k) for k in _TOUCHED_KEYS}
    for k in _TOUCHED_KEYS:
        os.environ.pop(k, None)
    try:
        yield env_file
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #


def test_get_config_exposes_one_group_plus_stage_deltas() -> None:
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()

    expected = {
        "enabled", "provider", "base_url", "model", "api_key_set",
        "timeout_s", "max_tokens", "thinking_budget", "inherited",
    }
    assert set(body["llm"]["default"]) == expected
    assert set(body["llm"]["stages"]) == set(STAGES), "every stage is addressable"
    for stage, group in body["llm"]["stages"].items():
        assert set(group) == expected, stage


def test_stages_report_as_inheriting_when_nothing_overrides() -> None:
    body = client.get("/api/config").json()
    for stage, group in body["llm"]["stages"].items():
        assert set(group["inherited"]) == set(FIELD_SUFFIX), stage


def test_secrets_are_never_returned() -> None:
    os.environ["ARIADNE_LLM_API_KEY"] = "sk-super-secret"
    os.environ["NEO4J_PASSWORD"] = "hunter2-not-in-body"
    resp = client.get("/api/config")

    assert "sk-super-secret" not in resp.text
    assert "hunter2-not-in-body" not in resp.text
    assert resp.json()["llm"]["default"]["api_key_set"] is True
    assert resp.json()["connection"]["neo4j_password_set"] is True


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #


def test_apply_update_roundtrips_to_temp_env(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("# existing\nNEO4J_USER=neo4j\n", encoding="utf-8")

    req = ConfigUpdateRequest.model_validate(
        {
            "llm": {"enabled": True, "model": "gpt-test", "max_tokens": 8192},
            "llm_stages": {"eval": {"timeout_s": 12.5}},
            "connection": {"neo4j_user": "analyst"},
        }
    )
    result = config_service.apply_update(req, env_file=env_file)

    text = env_file.read_text(encoding="utf-8")
    assert "# existing" in text, "comments and layout survive"
    assert "ARIADNE_LLM_ENABLED=true" in text
    assert "ARIADNE_LLM_MODEL=gpt-test" in text
    assert "ARIADNE_LLM_MAX_TOKENS=8192" in text
    assert "EVAL_LLM_TIMEOUT_S=12.5" in text
    assert text.count("NEO4J_USER=") == 1, "rewritten in place, not duplicated"
    assert "NEO4J_USER=analyst" in text

    assert os.environ["ARIADNE_LLM_MODEL"] == "gpt-test"
    assert result.llm.default.model == "gpt-test"
    assert result.llm.default.max_tokens == 8192
    assert result.connection.neo4j_user == "analyst"


def test_one_group_reaches_every_stage(tmp_path) -> None:
    """The whole point: set the endpoint once, everything follows."""
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    req = ConfigUpdateRequest.model_validate(
        {"llm": {"base_url": "http://gpu-box:8000/v1", "model": "qwen38-27B-v2"}}
    )
    result = config_service.apply_update(req, env_file=env_file)

    for stage, group in result.llm.stages.items():
        assert group.base_url == "http://gpu-box:8000/v1", stage
        assert group.model == "qwen38-27B-v2", stage


def test_stage_override_then_inherit_round_trip(tmp_path) -> None:
    """Setting a stage back to inherit must CLEAR its keys, not rewrite them.

    Writing the default's current values into the stage would leave it pinned to
    a snapshot: the next time the default changed, the stage would silently keep
    the old number and nothing in the file would say it was meant to follow.
    """
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    config_service.apply_update(
        ConfigUpdateRequest.model_validate(
            {"llm": {"base_url": "http://primary:9090/v1", "model": "primary-model"}}
        ),
        env_file=env_file,
    )
    overridden = config_service.apply_update(
        ConfigUpdateRequest.model_validate(
            {"llm_stages": {"eval": {"base_url": "http://gpu2:8000/v1", "model": "judge"}}}
        ),
        env_file=env_file,
    )
    assert overridden.llm.stages["eval"].model == "judge"
    assert "model" not in overridden.llm.stages["eval"].inherited

    reverted = config_service.apply_update(
        ConfigUpdateRequest.model_validate(
            {"llm_stages": {"eval": {"inherit": ["base_url", "model"]}}}
        ),
        env_file=env_file,
    )
    assert reverted.llm.stages["eval"].model == "primary-model"
    assert reverted.llm.stages["eval"].base_url == "http://primary:9090/v1"
    assert "model" in reverted.llm.stages["eval"].inherited

    text = env_file.read_text(encoding="utf-8")
    assert "# unset by Ariadne: EVAL_LLM_MODEL=judge" in text, "cleared, still legible"
    assert "ARIADNE_LLM_MODEL=primary-model" in text


def test_an_explicit_value_beats_inherit_in_the_same_request(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("EVAL_LLM_MODEL=old\n", encoding="utf-8")
    result = config_service.apply_update(
        ConfigUpdateRequest.model_validate(
            {"llm_stages": {"eval": {"model": "new", "inherit": ["model"]}}}
        ),
        env_file=env_file,
    )
    assert result.llm.stages["eval"].model == "new"


def test_collect_updates_skips_an_empty_secret() -> None:
    """A blank field means "leave the stored one alone", never "clear it"."""
    req = ConfigUpdateRequest.model_validate({"connection": {"neo4j_password": ""}})
    sets, _ = config_service.collect_updates(req)
    assert "NEO4J_PASSWORD" not in sets

    req2 = ConfigUpdateRequest.model_validate({"connection": {"neo4j_password": "secret"}})
    sets2, _ = config_service.collect_updates(req2)
    assert sets2["NEO4J_PASSWORD"] == "secret"

    req3 = ConfigUpdateRequest.model_validate({"llm": {"api_key": ""}})
    sets3, _ = config_service.collect_updates(req3)
    assert "ARIADNE_LLM_API_KEY" not in sets3


def test_unknown_stage_is_rejected() -> None:
    req = ConfigUpdateRequest.model_validate({"llm_stages": {"router": {"model": "x"}}})
    with pytest.raises(ValueError, match="Unknown LLM stage"):
        config_service.collect_updates(req)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "payload",
    [
        {"llm": {"base_url": "ftp://nope"}},               # bad scheme
        {"llm": {"timeout_s": 0}},                          # must be > 0
        {"llm": {"max_tokens": 0}},                         # must be >= 1
        {"llm": {"thinking_budget": -1}},                   # must be >= 0
        {"connection": {"neo4j_uri": "http://wrong"}},      # must be bolt/neo4j
        {"connection": {"gremlin_uri": "bolt://wrong"}},
    ],
)
def test_put_config_rejects_invalid_values(payload) -> None:
    assert client.put("/api/config", json=payload).status_code == 422


def test_put_rejects_a_thinking_budget_that_eats_the_whole_allowance() -> None:
    """A budget >= max_tokens returns empty content, not a shorter answer."""
    resp = client.put("/api/config", json={"llm": {"max_tokens": 4096, "thinking_budget": 4096}})
    assert resp.status_code == 422
    assert "thinking_budget" in resp.text


def test_put_rejects_lowering_max_tokens_under_a_stored_budget() -> None:
    """The partial case the request alone cannot see.

    The operator already has a 4096 budget stored and now lowers max_tokens to
    2048 without mentioning the budget. Neither value is invalid on its own.
    """
    client.put("/api/config", json={"llm": {"max_tokens": 16000, "thinking_budget": 4096}})

    resp = client.put("/api/config", json={"llm": {"max_tokens": 2048}})
    assert resp.status_code == 422
    assert "thinking_budget" in resp.text


def test_a_zero_budget_stays_acceptable() -> None:
    """0 means "send no cap" — what every run predating the cap did."""
    resp = client.put("/api/config", json={"llm": {"max_tokens": 4096, "thinking_budget": 0}})
    assert resp.status_code == 200


def test_put_config_endpoint_persists(preserve_env) -> None:
    env_file = preserve_env
    resp = client.put("/api/config", json={"llm": {"model": "local-llm", "enabled": True}})
    assert resp.status_code == 200
    assert resp.json()["llm"]["default"]["model"] == "local-llm"
    assert "ARIADNE_LLM_MODEL=local-llm" in env_file.read_text(encoding="utf-8")
