"""A model-chosen anchor is allowed only when the answer discloses it (EXP-2026-09-028).

Pins: the reranker returns the list unchanged and reports no backend when none
can run; the canonicalize node refuses a model-chosen anchor without the flag
and records id/name under it; the synthesis-side disclosure prepends one claim
and one sentence and nothing else; the flag defaults off.
"""

from __future__ import annotations

import dataclasses

from utils.orchestration.agents.planner.nodes import RUNG_SKIPPED_ANCHOR, build_nodes
from utils.planner import canonical, rewrite_llm
from utils.planner.config import PlannerConfig
from utils.planner.intent import DeterministicIntentClassifier
from utils.planner.schema import Limits, Plan, SubQuestion
from utils.planner.tests._fixtures import load_fixture_cards
from utils.specialists.schema import rerank
from utils.specialists.schema.namesearch import Candidate
from utils.synthesis.contracts import Claim, SynthesizedAnswer
from utils.synthesis.disclosure import apply_disclosure

CARDS = load_fixture_cards()
GOOD = Limits(3, 1000, 5000)


class _Drafter:
    def draft(self, request, cards, live_view, feedback=None, intent=None) -> Plan:
        return Plan(request=request, sub_questions=[SubQuestion("q1", "attack", request, ["Technique"], GOOD)])


def _nodes(**kw):
    config = dataclasses.replace(PlannerConfig(data_dir="."), **kw)
    return build_nodes(_Drafter(), CARDS, 3, DeterministicIntentClassifier(), config)


UNBOUND = canonical.IntentForm(
    anchor_labels=("Technique",), target_labels=("Mitigation",), relation="MITIGATES", direction="in",
    mode=canonical.MODE_ENUMERATE, datasets=("attack",),
).with_unbound(canonical.SLOT_ANCHORS)
CHOSEN = canonical.IntentForm(
    anchors=("T1566",), anchor_labels=("Technique",), target_labels=("Mitigation",), relation="MITIGATES",
    direction="in", mode=canonical.MODE_ENUMERATE, datasets=("attack",),
    sources={canonical.SLOT_ANCHORS: "model", canonical.SLOT_ANCHOR_LABELS: "model:anchor-candidate"},
)
Q = "How do I stop attackers sending deceptive emails to staff?"


def _lists(*a, **k):
    return {"attack": canonical.CandidateLists(dataset="attack", anchors=(
        canonical.Choice(index=0, value="T1566", label="Technique", name="Phishing", gloss=""),
    ))}


def test_without_the_flag_a_model_anchor_is_refused(monkeypatch):
    monkeypatch.setattr(canonical, "deterministic_fill", lambda *a, **k: UNBOUND)
    monkeypatch.setattr(rewrite_llm, "fill", lambda *a, **k: (CHOSEN, {"rung": "model", "cache_hit": False, "served_model": "t", "rejected": []}))
    out = _nodes(rewrite_enabled=True, rewrite_model_enabled=True, rewrite_require_resolved_anchor=True)["canonicalize"](
        {"request": Q, "original_request": Q})
    assert out["rewrite_trace"]["rung"] == RUNG_SKIPPED_ANCHOR


def test_with_the_flag_the_choice_stands_and_is_recorded(monkeypatch):
    monkeypatch.setattr(canonical, "deterministic_fill", lambda *a, **k: UNBOUND)
    monkeypatch.setattr(canonical, "candidate_lists_all", _lists)
    monkeypatch.setattr(rewrite_llm, "fill", lambda *a, **k: (CHOSEN, {"rung": "model", "cache_hit": False, "served_model": "t", "rejected": []}))
    out = _nodes(rewrite_enabled=True, rewrite_model_enabled=True, rewrite_require_resolved_anchor=True,
                 anchor_disclosed=True)["canonicalize"]({"request": Q, "original_request": Q})
    assert out["rewrite_trace"]["rung"] == "model"
    assert out["rewrite_trace"]["disclosed_anchor"] == {"id": "T1566", "name": "Phishing", "label": "Technique", "dataset": "attack"}
    assert out["canonical_question"]


def test_the_disclosure_prefixes_the_headline_and_leaves_the_claims_alone():
    answer = SynthesizedAnswer(request=Q, headline="Found 5 records.", claims=[Claim(text="x", entity_ids=("M1017",))])
    out = apply_disclosure(answer, {"disclosed_anchor": {"id": "T1566", "name": "Phishing", "label": "Technique"}})
    assert out.headline.startswith("Resolved your description to the Technique T1566 (Phishing)")
    assert out.headline.endswith("Found 5 records.")
    assert out.claims == answer.claims, "the claim table stays aligned with the verifier's verdicts"
    assert apply_disclosure(answer, {"rung": "deterministic"}) is answer


def test_the_reranker_stands_down_without_a_backend(monkeypatch):
    monkeypatch.setattr(rerank, "backend", lambda: "")
    cands = [Candidate("T1", "Technique", "A", 1.0), Candidate("T2", "Technique", "B", 0.5)]
    ordered, used = rerank.rerank("q", cands, dataset="attack")
    assert ordered == cands and used == ""


def test_config_reads_the_environment_flag(monkeypatch):
    monkeypatch.delenv("ARIADNE_ANCHOR_DISCLOSED", raising=False)
    assert PlannerConfig.from_env().anchor_disclosed is False
    monkeypatch.setenv("ARIADNE_ANCHOR_DISCLOSED", "1")
    assert PlannerConfig.from_env().anchor_disclosed is True
