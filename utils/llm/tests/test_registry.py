"""Era 2 Step 2: the model registry and the token-id identity check (offline)."""

from __future__ import annotations

import textwrap

import pytest

from utils.llm import registry as R
from utils.llm.tests.fakeserver import FakeServer, body


@pytest.fixture(autouse=True)
def _fresh_cache():
    R.clear_identity_cache()
    yield
    R.clear_identity_cache()


def _spec(base_url: str, stop: int | None = 106, **kw) -> R.ModelSpec:
    return R.ModelSpec(name="gemma-test", kind="llm", endpoint=base_url, alias="default-model",
                       stop_token_id=stop, family="gemma", **kw)


# --------------------------------------------------------------------------- #
# The shipped registry
# --------------------------------------------------------------------------- #


def test_shipped_registry_loads_and_names_identities():
    reg = R.load()
    assert "gemma4-31b" not in reg and "gemma4-31b-remote" not in reg     # retired 2026-11-15
    assert reg["qwen38-27b"].stop_token_id == 248046
    assert reg["qwen38-27b"].reasoning_extra() == {"reasoning_effort": "medium"}
    assert reg["pplx-decider"].kind == "decision"
    for spec in reg.values():
        assert spec.max_tokens >= 2048
        if spec.kind == "llm":
            assert spec.alias
        if spec.kind == "llm" and spec.status == "open":
            assert spec.stop_token_id, f"{spec.name} is open without a verified identity"


def test_unknown_model_names_the_known_ones():
    with pytest.raises(KeyError, match="minicpm47-35b"):
        R.load()["gpt-nonexistent"]


def _write(tmp_path, text):
    p = tmp_path / "models.yaml"
    p.write_text(textwrap.dedent(text))
    return p


def test_small_default_budget_is_rejected(tmp_path):
    p = _write(tmp_path, """
        defaults: {max_tokens: 512}
        models: {}
    """)
    with pytest.raises(ValueError, match="2048"):
        R.load(p)


def test_fallback_default_is_rejected(tmp_path):
    p = _write(tmp_path, """
        defaults: {max_tokens: 16384, fallback: other}
        models: {}
    """)
    with pytest.raises(ValueError, match="fallback"):
        R.load(p)


def test_bad_kind_and_missing_alias_are_rejected(tmp_path):
    p = _write(tmp_path, """
        defaults: {max_tokens: 16384}
        models:
          x: {kind: oracle, endpoint: http://h}
    """)
    with pytest.raises(ValueError, match="kind"):
        R.load(p)
    p = _write(tmp_path, """
        defaults: {max_tokens: 16384}
        models:
          x: {kind: llm, endpoint: http://h}
    """)
    with pytest.raises(ValueError, match="alias"):
        R.load(p)


def test_reasoning_level_validated():
    reg = R.load()
    assert reg["qwen38-27b"].reasoning_extra("none") == {"reasoning_effort": "none"}
    with pytest.raises(ValueError):
        reg["qwen38-27b"].reasoning_extra("ultra")
    with pytest.raises(ValueError):
        reg["pplx-decider"].reasoning_extra("high")
    assert reg["pplx-decider"].reasoning_extra() == {}
    assert reg["minicpm47-35b"].reasoning_off == "none"


# --------------------------------------------------------------------------- #
# Identity, against a fake endpoint
# --------------------------------------------------------------------------- #


def test_identity_verified_when_the_expected_tokenizer_answers():
    with FakeServer([body("ok", token_ids=[1, 2, 106], model="default-model-2")]) as srv:
        ident = R.require_identity(_spec(srv.base_url))
    assert ident.verified is True and ident.last_token_id == 106
    assert ident.envelope_model == "default-model-2"          # recorded, not trusted
    sent = srv.requests[0]
    assert sent["return_token_ids"] is True and sent["max_tokens"] >= 2048


def test_identity_blocks_a_swapped_model():
    # The registry expects Gemma (106); the endpoint answers with Qwen's 248046.
    with FakeServer([body("ok", token_ids=[9, 248046], model="default-model")]) as srv:
        with pytest.raises(R.IdentityMismatch, match="248046"):
            R.require_identity(_spec(srv.base_url))


def test_identity_without_token_ids_is_not_verified():
    with FakeServer([body("ok")]) as srv:
        spec = _spec(srv.base_url)
        assert R.check_identity(spec).verified is None
        R.clear_identity_cache()
        srv.script.append(body("ok"))
        with pytest.raises(R.IdentityMismatch, match="cannot be verified"):
            R.require_identity(spec)


def test_decision_model_is_unverifiable_not_verified():
    spec = R.load()["pplx-decider"]
    assert R.check_identity(spec).verified is None
    assert R.require_identity(spec, allow_unverifiable=True).verified is None


def test_identity_cache_respects_max_age():
    with FakeServer([body("ok", token_ids=[106]), body("ok", token_ids=[248046])]) as srv:
        spec = _spec(srv.base_url)
        assert R.check_identity(spec).verified is True
        assert R.check_identity(spec, max_age_s=3600).verified is True      # cached
        assert R.check_identity(spec).verified is False                     # re-probed: swapped
        assert len(srv.requests) == 2


def test_unreachable_endpoint_raises_unavailable():
    with pytest.raises(R.LLMUnavailable):
        R.check_identity(_spec("http://127.0.0.1:9/v1", connect_timeout_s=0.5))


def test_default_is_the_one_open_model():
    reg = R.load()
    assert reg.default.name == "minicpm47-35b" and reg.default.status == "open"
    assert reg.open_models() == ["minicpm47-35b"]
    assert reg.default.think_close_token_id == 248069 and len(reg.default.prompt_fingerprint) == 16


def test_default_must_be_open(tmp_path):
    p = _write(tmp_path, """
        defaults: {max_tokens: 16384, default_model: x}
        models:
          x: {kind: llm, endpoint: http://h, alias: a, status: closed}
    """)
    with pytest.raises(ValueError, match="open"):
        R.load(p)


def test_a_model_with_no_known_identity_cannot_be_verified():
    spec = R.ModelSpec(name="new", kind="llm", endpoint="http://127.0.0.1:9/v1", alias="a", status="closed")
    with pytest.raises(R.IdentityMismatch, match="cannot be verified"):
        R.require_identity(spec)


def test_prompt_fingerprint_separates_models_sharing_an_end_of_turn_id():
    fp = (248045, 846, 198)
    spec = R.ModelSpec(name="mc", kind="llm", endpoint="", alias="a", stop_token_id=248046, prompt_fingerprint=fp)
    good = body("ok", token_ids=[31248, 248046]); good["prompt_token_ids"] = list(fp)
    other = body("ok", token_ids=[9, 248046]); other["prompt_token_ids"] = [248045, 846, 198, 1]
    with FakeServer([good, other]) as srv:
        spec = R.ModelSpec(**{**spec.__dict__, "endpoint": srv.base_url})
        assert R.check_identity(spec).verified is True
        R.clear_identity_cache()
        bad = R.check_identity(spec)
    assert bad.verified is False and "fingerprint" in bad.reason
