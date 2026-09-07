#!/usr/bin/env python3
"""The LLM composer path: stubbed HTTP, fallback, and verifier-gated output.

No network anywhere: the OpenAI-compatible endpoint is stubbed at
``requests.post``. The decisive test is fabrication-then-cut: a "model" that
invents an identifier gets its claim cut by the same deterministic verifier
that gates the mechanical composer.
"""

from __future__ import annotations

import json

import pytest

from utils.synthesis.composer import DeterministicComposer
from utils.synthesis.config import SynthesisConfig
from utils.synthesis.factory import HybridComposer, select_composer, synthesize
from utils.synthesis.llm_composer import (
    ComposerUnavailable,
    OpenAICompatibleComposer,
    _record_line,
    build_evidence_context,
    build_messages,
    extract_json_object,
    parse_answer,
)
from utils.synthesis.verifier import verify_answer

from ._fixtures import make_evidence, make_record, make_result


def _evidence():
    attack = make_result(
        records=[
            make_record(
                "T1047",
                name="WMI",
                join_values=("T1047",),
                related=[{"id": "M1038", "name": "Execution Prevention"}],
            )
        ],
        summary="One technique.",
    )
    empty = make_result(
        sub_question_id="q2",
        records=[],
        ok=True,
        query="MATCH (t:Technique {attack_id: $id}) RETURN t",
        text="does T9999 exist?",
    )
    return make_evidence([attack, empty])


def _chat_response(payload: dict) -> object:
    class _Resp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    return _Resp()


def _stub_post(monkeypatch, response=None, exc=None):
    calls: list[dict] = []

    # **kwargs because the shared transport in utils.llm.client sends `headers`
    # (an Authorization only materializes when a key is configured) and a
    # (connect, read) timeout tuple. The stand-in must accept what the real
    # requests.post accepts, or a signature mismatch reads as a transport bug.
    def fake_post(url, json=None, timeout=None, **kwargs):  # noqa: A002 - requests API shape
        calls.append({"url": url, "payload": json, "timeout": timeout})
        if exc is not None:
            raise exc
        return response

    monkeypatch.setattr("requests.post", fake_post)
    return calls


# -- prompt construction --------------------------------------------------


def test_build_messages_shows_records_and_empties():
    messages = build_messages(_evidence())
    assert messages[0]["role"] == "system"
    user = messages[1]["content"]
    assert "T1047" in user and "M1038" in user
    assert "EMPTY SUB-QUESTIONS" in user
    assert "does T9999 exist?" in user
    # The executed query is not the model's to invent or echo; abstention
    # proof is attached by the verifier from the evidence itself.
    assert "MATCH (t:Technique" not in user


def test_build_messages_caps_record_context():
    big = make_result(records=[make_record(f"T1{i:03d}") for i in range(80)])
    user = build_messages(make_evidence([big]))[1]["content"]
    assert "30 more record(s) omitted" in user


# -- JSON extraction / parsing --------------------------------------------


def test_extract_json_object_tolerates_prose_and_fences():
    blob = 'Here is the answer:\n```json\n{"headline": "h", "claims": []}\n```'
    assert extract_json_object(blob) == {"headline": "h", "claims": []}


@pytest.mark.parametrize("bad", ["", "no json here", '{"unbalanced": '])
def test_extract_json_object_rejects_garbage(bad):
    with pytest.raises(ComposerUnavailable):
        extract_json_object(bad)


def test_parse_answer_builds_llm_draft():
    data = {
        "headline": "h",
        "claims": [
            {
                "text": "T1047 found.",
                "citations": [{"source": "attack", "primary_id": "T1047"}],
                "entity_ids": ["T1047"],
                "kind": "fact",
                "sub_question_id": "q1",
            }
        ],
        "abstentions": [
            {"sub_question_id": "q2", "source": "attack", "statement": "not established"}
        ],
    }
    answer = parse_answer(data, _evidence())
    assert answer.composer == "llm"
    assert answer.claims[0].citations[0].primary_id == "T1047"
    assert answer.abstentions[0].sub_question_id == "q2"
    assert answer.verification is None  # a draft, not a verdict


def test_parse_answer_reads_final_answer_as_narrative():
    data = {"headline": "h", "final_answer": "T1047 is WMI.", "claims": []}
    answer = parse_answer(data, _evidence())
    assert answer.narrative == "T1047 is WMI."


def test_prompt_requests_a_final_answer():
    from utils.synthesis.llm_composer import _SYSTEM_PROMPT

    assert "final_answer" in _SYSTEM_PROMPT


# -- HTTP failure modes ---------------------------------------------------


def test_http_error_raises_unavailable(monkeypatch):
    class _Resp:
        status_code = 503
        text = "overloaded"

    _stub_post(monkeypatch, response=_Resp())
    with pytest.raises(ComposerUnavailable, match="HTTP 503"):
        OpenAICompatibleComposer(SynthesisConfig()).compose(_evidence())


def test_transport_error_raises_unavailable(monkeypatch):
    import requests

    _stub_post(monkeypatch, exc=requests.ConnectionError("refused"))
    # The shared transport names the provider and the unreachable host rather
    # than saying "request failed", and carries the underlying cause verbatim --
    # the actionable half of the message. Assert the cause survives, not the
    # phrasing around it.
    with pytest.raises(ComposerUnavailable, match="refused"):
        OpenAICompatibleComposer(SynthesisConfig()).compose(_evidence())


def test_happy_path_posts_graded_sampling_params(monkeypatch):
    """Greedy and seeded, not merely temperature 0.

    Q2: temperature 0 was already sent everywhere it matters, and it is not the
    same as determinism — a server doing greedy decoding still reduces floating
    point over whatever batch a request lands in. `seed` removes every remaining
    source of variation that is under client control; it cannot make batched
    inference bit-exact, and nothing at the client can.
    """
    calls = _stub_post(
        monkeypatch, response=_chat_response({"headline": "h", "claims": []})
    )
    answer = OpenAICompatibleComposer(SynthesisConfig()).compose(_evidence())
    assert answer.composer == "llm"
    payload = calls[0]["payload"]
    assert payload["temperature"] == 0
    assert payload["top_p"] == 1
    assert payload["seed"] == 1729
    assert calls[0]["url"].endswith("/chat/completions")


# -- hybrid fallback -------------------------------------------------------


def test_hybrid_falls_back_and_records_reason(monkeypatch):
    import requests

    _stub_post(monkeypatch, exc=requests.ConnectionError("refused"))
    config = SynthesisConfig(llm_enabled=True)
    hybrid = HybridComposer(
        OpenAICompatibleComposer(config), DeterministicComposer(config)
    )
    answer = hybrid.compose(_evidence())
    assert answer.composer == "deterministic"
    assert "LLM composer unavailable" in (answer.fallback_reason or "")
    assert hybrid.last_used == "deterministic"


def test_select_composer_respects_flag():
    """`llm_claims` selects the LLM composer; `llm_enabled` deliberately does not.

    The two flags mean different things (Q20). `llm_enabled` has always meant
    "an LLM writes the narrative prose over already-verified claims" and is what
    arms `llm` and `gold_llm` set, so it must NOT also switch on the claims
    composer — that would change what those arms do and make the figures behind
    C-002, C-005 and C-006 unreproducible.
    """
    assert isinstance(select_composer(SynthesisConfig()), DeterministicComposer)
    assert isinstance(
        select_composer(SynthesisConfig(llm_claims=True)), HybridComposer
    )
    # The regression this pins: prose-LLM on, claims-LLM off => deterministic.
    assert isinstance(
        select_composer(SynthesisConfig(llm_enabled=True)), DeterministicComposer
    )


# -- the chain: fabrication is cut, abstention is enforced -----------------


def test_synthesize_cuts_llm_fabrication_and_enforces_abstention(monkeypatch):
    fabricated = {
        "headline": "Confidently wrong.",
        "claims": [
            {
                "text": "T1047 found.",
                "citations": [{"source": "attack", "primary_id": "T1047"}],
                "entity_ids": ["T1047"],
                "kind": "fact",
            },
            {
                "text": "T1047 is mitigated by M9999.",  # invented
                "citations": [{"source": "attack", "primary_id": "T1047"}],
                "entity_ids": ["M9999"],
                "kind": "fact",
            },
        ],
        "abstentions": [],  # model "forgot" — the verifier must not
    }
    _stub_post(monkeypatch, response=_chat_response(fabricated))
    evidence = _evidence()
    # The LLM claims composer's output flows through the same deterministic
    # verifier, which cuts anything the evidence does not ground.
    draft = OpenAICompatibleComposer(SynthesisConfig()).compose(evidence)
    answer = verify_answer(draft, evidence)

    assert answer.composer == "llm"
    assert answer.verification is not None
    # The grounded claim survives; the fabricated mitigation is cut.
    assert [c.text for c in answer.rendered_claims()] == ["T1047 found."]
    (_, verdict), = answer.flagged_claims()
    assert any("M9999" in r for r in verdict.reasons)
    # The omitted abstention was repaired with the executed query as proof.
    assert len(answer.abstentions) == 1
    assert answer.abstentions[0].query.startswith("MATCH (t:Technique")
    assert answer.verification.repaired_abstentions == 1


def test_synthesize_deterministic_default_is_verified_clean():
    evidence = _evidence()
    answer = synthesize(evidence, SynthesisConfig())  # LLM disabled
    assert answer.composer == "deterministic"
    assert answer.verification is not None and answer.verification.ok
    assert len(answer.abstentions) == 1


# -- carry-through regression guard (Step 5) ---------------------------------


def test_evidence_context_carries_description_facets_and_edge_direction():
    """_record_line used to drop properties and strip edge type/direction, so the
    composer wrote blind to what a node is and how it connects. Guard against a
    regression: the context must carry the description, the facet block, and the
    edge direction/type."""
    rec = make_record(
        "T1059",
        name="Command and Scripting Interpreter",
        properties={
            "description": "Adversaries may abuse command and script interpreters.",
            "x_mitre_platforms": ["Windows", "Linux"],
        },
        facets=[
            {"rel": "HAS_SUBTECHNIQUE", "direction": "out", "label": "SubTechnique", "count": 13},
            {"rel": "MITIGATES", "direction": "in", "label": "Mitigation", "count": 0},
        ],
        related=[
            {"id": "M1038", "name": "Execution Prevention", "type": "MITIGATES",
             "direction": "in", "label": "Mitigation"},
        ],
    )
    ctx = build_evidence_context(make_evidence([make_result(records=[rec])]))
    assert "Adversaries may abuse command and script interpreters" in ctx  # description
    assert "HAS_SUBTECHNIQUE" in ctx and '"count": 13' in ctx              # facet block
    assert '"direction": "in"' in ctx                                      # edge direction
    # the honest zero facet is present so the model can assert absence
    assert '"count": 0' in ctx


def test_related_neighbour_carries_its_description():
    """A related neighbour's description is its only content when it has no name
    (an unnamed CAPEC mitigation node). It was dropped, so the composer reported
    'no description available' for a mitigation whose text was right there."""
    rec = make_record(
        "CAPEC-459",
        name="Creating a Rogue Certification Authority Certificate",
        related=[
            {
                "id": "capec:attack-pattern:459:mitigation:1",
                "name": "capec:attack-pattern:459:mitigation:1",
                "label": "Mitigation",
                "description": "Certification Authorities need to stop using deprecated "
                "hashing algorithms; use SHA-256 or SHA-512.",
            }
        ],
    )
    data = json.loads(_record_line(rec))
    assert data["related"][0]["description"].startswith("Certification Authorities need to stop")
    ctx = build_evidence_context(make_evidence([make_result(records=[rec])]))
    assert "use SHA-256 or SHA-512" in ctx


def test_related_neighbour_description_is_bounded():
    rec = make_record(
        "CAPEC-1", name="X",
        related=[{"id": "m1", "name": "m1", "label": "Mitigation", "description": "y" * 1000}],
    )
    data = json.loads(_record_line(rec))
    desc = data["related"][0]["description"]
    assert desc.endswith("…") and len(desc) <= 401  # bounded, truncation-marked


def test_record_line_bounds_properties_and_signals_omissions():
    rec = make_record(
        "T1",
        properties={"description": "x" * 1000, "external_references": [{"external_id": "T1"}]},
    )
    data = json.loads(_record_line(rec))
    assert data["properties"]["description"].endswith("…")            # truncated, signalled
    assert "external_references" not in data["properties"]            # bulky array dropped
    assert data["properties"]["_omitted_properties"] == ["external_references"]  # but marked
