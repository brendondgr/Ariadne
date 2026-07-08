"""The synthesis subgraph: verifier always runs; narrator is best-effort.

The synthesis package's own suite pins the full answer contract; these pin
the chain semantics at the graph boundary with stub composers/narrators.
"""

from __future__ import annotations

from utils.orchestration.agents.synthesis.graph import build_synthesis_graph
from utils.specialists.federation import FederatedEvidence
from utils.synthesis.composer import DeterministicComposer
from utils.synthesis.config import SynthesisConfig
from utils.synthesis.contracts import SynthesizedAnswer
from utils.synthesis.factory import synthesize


def _evidence() -> FederatedEvidence:
    return FederatedEvidence(request="q", results=[], unsupported=[], skipped=[])


def test_verifier_always_runs_over_the_composed_draft():
    """Even a composer emitting an unverified draft gets a verification report."""

    class StubComposer:
        name = "stub"

        def compose(self, evidence):
            return SynthesizedAnswer(request=evidence.request, composer=self.name)

    config = SynthesisConfig(llm_enabled=False)
    graph = build_synthesis_graph(StubComposer(), config)
    out = graph.invoke({"evidence": _evidence()})
    answer = out["answer"]
    assert answer.verification is not None, "verify must be an unconditional edge"
    assert answer.composer == "stub"


def test_llm_off_narrator_is_a_no_op():
    config = SynthesisConfig(llm_enabled=False)
    graph = build_synthesis_graph(DeterministicComposer(config), config)
    out = graph.invoke({"evidence": _evidence()})
    assert out["answer"].fallback_reason is None


def test_llm_on_unreachable_narrator_keeps_deterministic_answer():
    # llm_enabled with an unroutable endpoint: apply_llm_narrative must catch
    # ComposerUnavailable, keep the deterministic narrative, record the reason.
    config = SynthesisConfig(
        llm_enabled=True, llm_base_url="http://127.0.0.1:1/v1", llm_timeout_s=0.2
    )
    graph = build_synthesis_graph(DeterministicComposer(config), config)
    out = graph.invoke({"evidence": _evidence()})
    answer = out["answer"]
    assert answer.narrative, "deterministic narrative must survive"
    assert answer.fallback_reason and "narrator unavailable" in answer.fallback_reason


def test_synthesize_facade_matches_direct_graph_run():
    config = SynthesisConfig(llm_enabled=False)
    via_facade = synthesize(_evidence(), config)
    via_graph = build_synthesis_graph(DeterministicComposer(config), config).invoke(
        {"evidence": _evidence()}
    )["answer"]
    assert via_facade.to_dict() == via_graph.to_dict()
