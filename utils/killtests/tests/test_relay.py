"""Live probe of the relay on :9090 (skipped when it is not running)."""
import pytest

from utils.killtests.relay import RelayClient


def test_completion_records_served_model():
    c = RelayClient()
    try:
        aliases = c.healthy_aliases()
    except Exception:
        pytest.skip("relay on :9090 not reachable")
    if not aliases:
        pytest.skip("no healthy relay alias")
    out = c.complete(aliases[0], [{"role": "user", "content": "Reply with the single word: ok"}])
    assert out.served_model and out.served_model != "unknown"
    # A real answer came back. Under MiniCPM 4.7 (2026-11-15) a one-word reply
    # never closes the template's think block, and the server files it under
    # reasoning; `text` deliberately stays `content` only (see relay.Completion).
    assert out.text.strip() or out.reasoning.strip()
    assert c.max_tokens >= 2048
