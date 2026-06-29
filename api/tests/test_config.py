"""Contract tests for /api/config (view + edit env-backed settings).

Invariants: GET exposes every LLM knob and never leaks the Neo4j password; PUT
validates types, persists to the target .env preserving layout, and mirrors the
new values into os.environ so the next read reflects them.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

import utils.config as uconfig
from api.main import app
from api.models import ConfigUpdateRequest
from api.services import config as config_service

client = TestClient(app)

# All env keys these tests may write — saved and restored to avoid cross-test leak.
_TOUCHED_KEYS = [
    "PLANNER_LLM_ENABLED", "PLANNER_LLM_BASE_URL", "PLANNER_LLM_MODEL",
    "PLANNER_LLM_TIMEOUT_S", "PLANNER_LLM_MAX_TOKENS",
    "SPECIALIST_LLM_ENABLED", "SPECIALIST_LLM_BASE_URL", "SPECIALIST_LLM_MODEL",
    "SPECIALIST_LLM_TIMEOUT_S", "SPECIALIST_LLM_MAX_TOKENS",
    "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "GREMLIN_URI",
]


@pytest.fixture(autouse=True)
def preserve_env():
    saved = {k: os.environ.get(k) for k in _TOUCHED_KEYS}
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_get_config_shape_and_password_redaction() -> None:
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()

    for agent in ("planner", "specialist"):
        group = body["llm"][agent]
        assert set(group) == {"enabled", "base_url", "model", "timeout_s", "max_tokens"}
        assert isinstance(group["enabled"], bool)

    conn = body["connection"]
    assert set(conn) == {"neo4j_uri", "neo4j_user", "neo4j_password_set", "gremlin_uri"}
    assert isinstance(conn["neo4j_password_set"], bool)

    # The plaintext password (if one is configured) must never appear in the body.
    pw = os.environ.get("NEO4J_PASSWORD")
    if pw:
        assert pw not in resp.text


def test_apply_update_roundtrips_to_temp_env(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("# existing\nNEO4J_USER=neo4j\n", encoding="utf-8")

    req = ConfigUpdateRequest.model_validate(
        {
            "planner": {"enabled": True, "model": "gpt-test", "max_tokens": 8192},
            "specialist": {"timeout_s": 12.5},
            "connection": {"neo4j_user": "analyst"},
        }
    )
    result = config_service.apply_update(req, env_file=env_file)

    # Persisted to the file, comments/existing layout preserved.
    text = env_file.read_text(encoding="utf-8")
    assert "# existing" in text
    assert "PLANNER_LLM_ENABLED=true" in text
    assert "PLANNER_LLM_MODEL=gpt-test" in text
    assert "PLANNER_LLM_MAX_TOKENS=8192" in text
    assert "SPECIALIST_LLM_TIMEOUT_S=12.5" in text
    # Existing NEO4J_USER line rewritten in place (not duplicated).
    assert text.count("NEO4J_USER=") == 1
    assert "NEO4J_USER=analyst" in text

    # Mirrored into os.environ + reflected by the returned resolved config.
    assert os.environ["PLANNER_LLM_MODEL"] == "gpt-test"
    assert result.llm.planner.enabled is True
    assert result.llm.planner.model == "gpt-test"
    assert result.llm.planner.max_tokens == 8192
    assert result.llm.specialist.timeout_s == 12.5
    assert result.connection.neo4j_user == "analyst"


def test_collect_updates_skips_empty_password() -> None:
    req = ConfigUpdateRequest.model_validate({"connection": {"neo4j_password": ""}})
    assert "NEO4J_PASSWORD" not in config_service.collect_updates(req)

    req2 = ConfigUpdateRequest.model_validate({"connection": {"neo4j_password": "secret"}})
    assert config_service.collect_updates(req2)["NEO4J_PASSWORD"] == "secret"


@pytest.mark.parametrize(
    "payload",
    [
        {"planner": {"base_url": "ftp://nope"}},      # bad scheme
        {"planner": {"timeout_s": 0}},                 # must be > 0
        {"specialist": {"max_tokens": 0}},             # must be >= 1
        {"connection": {"neo4j_uri": "http://wrong"}}, # must be bolt/neo4j
        {"connection": {"gremlin_uri": "bolt://wrong"}},
    ],
)
def test_put_config_rejects_invalid_values(payload) -> None:
    resp = client.put("/api/config", json=payload)
    assert resp.status_code == 422


def test_put_config_endpoint_persists(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    # Redirect set_env_values' default target at the temp file.
    monkeypatch.setattr(uconfig, "ENV_FILE", env_file)

    resp = client.put("/api/config", json={"specialist": {"model": "local-llm", "enabled": True}})
    assert resp.status_code == 200
    assert resp.json()["llm"]["specialist"]["model"] == "local-llm"
    assert "SPECIALIST_LLM_MODEL=local-llm" in env_file.read_text(encoding="utf-8")
