#!/usr/bin/env python3
"""Configuration for the federated planning agent.

Every tunable knob is read from the environment through the central
``utils.config`` helpers so the planner honors the project's single ``.env``
file with sensible fallbacks. Real shell/CI env vars always win.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from utils.config import endpoint_overrides, env_int, env_str
from utils.llm.config import LLMSettings, settings_from_legacy
from utils.llm.config import resolve as resolve_llm

# Discovery / connection defaults mirror utils.graph_loader.config so the
# planner probes the same endpoints the loader writes to.
DEFAULT_NEO4J_URI = "bolt://localhost:5456"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = "password"
DEFAULT_GREMLIN_URI = "ws://localhost:6455/gremlin"

# Drafting defaults: the local OpenAI-compatible endpoint.
DEFAULT_LLM_BASE_URL = "http://localhost:9090/v1"
DEFAULT_LLM_MODEL = "default-model"


def _env_float(name: str, default: float) -> float:
    """Return a float env var, falling back to ``default`` when unset/invalid."""
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class PlannerConfig:
    """Resolved configuration for one planning run."""

    data_dir: Path
    # Discovery / liveness.
    neo4j_uri: str = DEFAULT_NEO4J_URI
    neo4j_user: str = DEFAULT_NEO4J_USER
    neo4j_password: str = DEFAULT_NEO4J_PASSWORD
    gremlin_uri: str = DEFAULT_GREMLIN_URI
    probe_timeout_s: float = 4.0
    cache_ttl_s: float = 5.0
    # A live graph must hold at least this many nodes to count as "loaded"
    # (a bare connect is not enough — see briefing §2.2 content probe).
    min_live_nodes: int = 1
    # Loop control.
    max_iterations: int = 3
    # LLM drafter (OpenAI-compatible). Disabled by default; the deterministic
    # drafter is always the fallback.
    llm_enabled: bool = False
    # LLM intent classifier (same endpoint as the drafter). Disabled by default;
    # the deterministic classifier is always the fallback.
    intent_llm_enabled: bool = False
    # The hybrid rewrite stage. `rewrite_enabled` turns on the deterministic
    # fill and the canonical renderer; `rewrite_model_enabled` additionally lets
    # a model fill the slots the deterministic pass left unbound, choosing only
    # from candidate lists it cannot add to. Both default **off**: with them off
    # the pipeline is byte-identical to the shipped engine, which every step of
    # the 2026-09-08 plan re-proves against the captured reference.
    rewrite_enabled: bool = False
    rewrite_model_enabled: bool = False
    #: Derive the relation slot from the (anchor label, target label) pair
    #: instead of asking the model for it. On by default *within the model
    #: rung* — the pair pins the relation for 16 of CAPEC's 17 declared label
    #: pairs and all 19 of ATT&CK's, and EXP-2026-09-014 measured relation as
    #: the model's worst slot. Set ``ARIADNE_REWRITE_DERIVE_RELATION=0`` to
    #: restore the ask, which is how EXP-2026-09-015 ablates it against the
    #: same cached picks. Inert unless ``rewrite_model_enabled``.
    rewrite_derive_relation: bool = True
    #: Run the rewrite stage **only when the question cites no identifier**.
    #: EXP-2026-09-021 Step 4 measured the stage's effect separately on the two
    #: populations: where an identifier survives it broke 32 answers and fixed
    #: 10, and where none does it fixed 44 and broke 7. The stage canonicalises
    #: a question into the source card's vocabulary, so when the question
    #: already carries the identifier the template ladder reads, canonicalising
    #: discards it. The predicate is the resolver's own ``_native_ids``, not a
    #: second opinion about what an identifier is. Off by default: with it off
    #: the stage behaves exactly as EXP-2026-09-014 measured it.
    rewrite_only_without_identifier: bool = False
    #: Refuse the stage when the anchor was not bound by an exact lookup.
    #: EXP-2026-09-021 AMENDMENT A-1: `deterministic_fill` binds an anchor from
    #: an identifier or a complete-name match and never guesses, but the model
    #: rung then picks one out of a ranked candidate list -- and that is where
    #: wrong answers about the wrong entity come from. At T3 (exact name) the
    #: anchor is an `exact-name` bind 64 times of 101; at T4/T5 (paraphrased
    #: name, description only) the MODEL chooses it 82 and 88 times of 104, and
    #: `wrong_entity` roughly triples. With this set the model may still fill
    #: relation, direction, mode and target labels -- it may never choose who
    #: the question is about. Off by default.
    rewrite_require_resolved_anchor: bool = False
    #: EXP-2026-09-023 H2 (Q59): look an exact name up across every live source
    #: *before* choosing a dataset, and let the name's owner lead when the
    #: router picked nothing or picked a source that does not hold it.
    anchor_before_routing: bool = False
    #: EXP-2026-09-025 (plan Step 6): execute a bound form as a plan instead of
    #: rendering it to English for the drafter to parse again.
    form_execute: bool = False
    #: EXP-2026-09-028 (plan Step 9): the model may choose the anchor from the
    #: (reranked) candidate list when the answer DISCLOSES the choice.
    anchor_disclosed: bool = False
    #: Where the model's picks are cached, keyed by prompt version, served model
    #: and question. Unset means the process default (see rewrite_cache.py).
    rewrite_cache_dir: str | None = None
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_timeout_s: float = 30.0
    # Generous default: the model is a reasoning model that spends tokens before
    # emitting the JSON plan, so the cap must cover reasoning + the plan.
    llm_max_tokens: int = 4096

    def source_cards_dir(self) -> Path:
        return self.data_dir / "source_cards"

    def endpoint_for(self, backend: str, dataset: str | None = None) -> str:
        """The URI for ``backend``, or for ``dataset`` when it names its own.

        ``dataset`` is what makes two sources on one backend addressable. Absent
        an ``ARIADNE_ENDPOINT_<DATASET>`` override this returns the backend-wide
        URI exactly as before, so every existing caller is unaffected.
        """
        if dataset:
            override = endpoint_overrides().get(str(dataset).lower())
            if override:
                return override
        """Return the configured endpoint URI for a runtime backend."""
        if backend == "neo4j":
            return self.neo4j_uri
        if backend == "gremlin":
            return self.gremlin_uri
        raise ValueError(f"Unknown backend: {backend!r}")

    @classmethod
    def from_env(cls, data_dir: str | Path | None = None) -> "PlannerConfig":
        """Build a config from the environment with documented fallbacks."""
        if data_dir is None:
            data_dir = env_str("ARIADNE_DATA_DIR", "data")
        _truthy = {"1", "true", "yes", "on"}
        intent_llm_enabled = (
            os.environ.get("PLANNER_INTENT_LLM_ENABLED", "").strip().lower() in _truthy
        )
        rewrite_enabled = os.environ.get("ARIADNE_REWRITE", "").strip().lower() in _truthy
        rewrite_model_enabled = (
            os.environ.get("ARIADNE_REWRITE_MODEL", "").strip().lower() in _truthy
        )
        _derive = os.environ.get("ARIADNE_REWRITE_DERIVE_RELATION", "").strip().lower()
        rewrite_derive_relation = _derive not in {"0", "false", "no", "off"}
        rewrite_only_without_identifier = (
            os.environ.get("ARIADNE_REWRITE_ONLY_WITHOUT_ID", "").strip().lower() in _truthy
        )
        rewrite_require_resolved_anchor = (
            os.environ.get("ARIADNE_REWRITE_REQUIRE_RESOLVED_ANCHOR", "").strip().lower()
            in _truthy
        )
        anchor_before_routing = (
            os.environ.get("ARIADNE_ANCHOR_BEFORE_ROUTING", "").strip().lower() in _truthy
        )
        form_execute = os.environ.get("ARIADNE_FORM_EXECUTE", "").strip().lower() in _truthy
        anchor_disclosed = os.environ.get("ARIADNE_ANCHOR_DISCLOSED", "").strip().lower() in _truthy
        # The LLM group resolves through utils.llm: PLANNER_LLM_* still wins when
        # set, but falls back to ARIADNE_LLM_* so one endpoint configures every
        # stage. With neither set this is exactly the previous default.
        llm = resolve_llm(
            "planner",
            defaults=LLMSettings(
                base_url=DEFAULT_LLM_BASE_URL, model=DEFAULT_LLM_MODEL,
                timeout_s=30.0, max_tokens=4096,
            ),
        )
        return cls(
            data_dir=Path(data_dir),
            neo4j_uri=env_str("NEO4J_URI", DEFAULT_NEO4J_URI),
            neo4j_user=env_str("NEO4J_USER", DEFAULT_NEO4J_USER),
            neo4j_password=env_str("NEO4J_PASSWORD", DEFAULT_NEO4J_PASSWORD),
            gremlin_uri=env_str("GREMLIN_URI", DEFAULT_GREMLIN_URI),
            probe_timeout_s=_env_float("PLANNER_PROBE_TIMEOUT_S", 4.0),
            cache_ttl_s=_env_float("PLANNER_CACHE_TTL_S", 5.0),
            min_live_nodes=env_int("PLANNER_MIN_LIVE_NODES", 1),
            max_iterations=env_int("PLANNER_MAX_ITERATIONS", 3),
            llm_enabled=llm.enabled,
            intent_llm_enabled=intent_llm_enabled,
            rewrite_enabled=rewrite_enabled,
            rewrite_model_enabled=rewrite_model_enabled,
            rewrite_only_without_identifier=rewrite_only_without_identifier,
            rewrite_require_resolved_anchor=rewrite_require_resolved_anchor,
            anchor_before_routing=anchor_before_routing,
            form_execute=form_execute,
            anchor_disclosed=anchor_disclosed,
            rewrite_derive_relation=rewrite_derive_relation,
            rewrite_cache_dir=env_str("ARIADNE_REWRITE_CACHE_DIR", "") or None,
            llm_base_url=llm.base_url,
            llm_model=llm.model,
            llm_timeout_s=llm.timeout_s,
            llm_max_tokens=llm.max_tokens,
        )

    def llm_settings(self) -> LLMSettings:
        """Transport settings for this config (adds provider + credentials)."""
        return settings_from_legacy(self, "planner")
