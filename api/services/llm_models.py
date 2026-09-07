"""Model discovery and the connection test behind the settings modal.

Both run **server-side** because the browser cannot reach a private endpoint and
must never hold the API key. Both accept an *unsaved* endpoint from the request
body: a Refresh button that only works after Save is the same "type the model
name exactly right" problem in a new place, so the modal can probe a URL the
operator has typed but not yet committed.

Neither ever raises. Discovery returns ``ok: false`` with a reason and the route
still answers 200 — nothing is wrong with this backend when someone's GPU box is
off, and an error banner for a normal operating state trains people to ignore
banners.
"""

from __future__ import annotations

from utils.llm import LLMProvider, LLMSettings, discover_models, probe, resolve

from ..models import LLMEndpointProbe, LLMModelsResponse, LLMProbeResponse, ModelEntry


def settings_for(scope: str | None, override: LLMEndpointProbe | None) -> LLMSettings:
    """Resolve the endpoint to act on.

    Starts from what is stored for ``scope`` (the primary group, or one stage),
    then layers any unsaved values the modal sent. The stored API key survives an
    override that omits it, so an operator can Refresh a changed URL without
    re-typing a secret the server already holds.
    """
    stage = scope if scope in (None, "") else scope
    base = resolve(None if stage in (None, "", "default") else stage, clamp=False)
    if override is None:
        return base

    return LLMSettings(
        enabled=base.enabled,
        provider=(
            LLMProvider.parse(override.provider, base.provider)
            if override.provider
            else base.provider
        ),
        base_url=override.base_url or base.base_url,
        model=override.model or base.model,
        api_key=override.api_key if override.api_key else base.api_key,
        timeout_s=base.timeout_s,
        max_tokens=base.max_tokens,
        thinking_budget=base.thinking_budget,
        connect_timeout_s=base.connect_timeout_s,
        stage=base.stage,
        inherited=base.inherited,
    )


def list_models(
    scope: str | None = None, override: LLMEndpointProbe | None = None
) -> LLMModelsResponse:
    """Ask the endpoint what it serves. Never raises; ``ok: false`` on failure."""
    settings = settings_for(scope, override)
    result = discover_models(settings)
    return LLMModelsResponse(
        ok=result.ok,
        state=result.state,
        reason=result.reason,
        base_url=settings.base_url,
        provider=settings.provider.value,
        models=[
            ModelEntry(
                id=m.id,
                label=m.label,
                context_window=m.context_window,
                max_output_tokens=m.max_output_tokens,
            )
            for m in result.models
        ],
    )
def test_endpoint(
    scope: str | None = None, override: LLMEndpointProbe | None = None
) -> LLMProbeResponse:
    """Prove the endpoint answers. Never raises.

    Deliberately stronger than reachability: this sends a real completion and
    requires content back. A TCP check and a ``/models`` listing both pass
    against a server that cannot complete anything — the 2026-09-05 record has
    ten responses with no ``choices`` key while vLLM was still loading weights.
    """
    settings = settings_for(scope, override)
    result = probe(settings)
    return LLMProbeResponse(
        ok=result.ok,
        latency_ms=result.latency_ms,
        model=result.model,
        reason=result.reason,
        summary=result.summary,
        base_url=settings.base_url,
        provider=settings.provider.value,
    )
