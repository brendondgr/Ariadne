#!/usr/bin/env python3
"""Tests for the persistence/rehydration domain helpers."""

from __future__ import annotations

from types import SimpleNamespace

from utils.conversation.persistence import (
    conversation_anchor,
    dossier_detail_block,
    dossier_index_line,
    dossiers_from_records,
    entity_ids_in,
    facts_from_synthesized,
    history_from_turns,
    referential_followup,
)
from utils.conversation.store import TurnRecord
from utils.synthesis.contracts import (
    Claim,
    ClaimVerdict,
    SynthesizedAnswer,
    VerificationReport,
)


def _verified_answer():
    claims = [Claim(text="CAPEC-98 maps to T1566"), Claim(text="CAPEC-98 maps to T1598")]
    verification = VerificationReport(
        verdicts=[ClaimVerdict(verdict="supported"), ClaimVerdict(verdict="supported")]
    )
    return SynthesizedAnswer(request="q", claims=claims, verification=verification)


def test_facts_from_synthesized_returns_verified_claims():
    facts = facts_from_synthesized(_verified_answer())
    assert facts == ["CAPEC-98 maps to T1566", "CAPEC-98 maps to T1598"]


def test_facts_from_synthesized_none_and_unverified():
    assert facts_from_synthesized(None) == []
    # An unverified draft (no verification report) renders no claims -> no facts.
    draft = SynthesizedAnswer(request="q", claims=[Claim(text="unverified")])
    assert facts_from_synthesized(draft) == []


def test_facts_dedupe():
    claims = [Claim(text="same"), Claim(text="same")]
    verification = VerificationReport(
        verdicts=[ClaimVerdict(verdict="supported"), ClaimVerdict(verdict="supported")]
    )
    ans = SynthesizedAnswer(request="q", claims=claims, verification=verification)
    assert facts_from_synthesized(ans) == ["same"]


def _turn(seq, role, **kw):
    return TurnRecord(
        id=f"t{seq}", conversation_id="c", seq=seq, role=role, created_at="t", **kw
    )


def test_history_from_turns_shapes_roles():
    turns = [
        _turn(0, "user", question="which techniques map to CAPEC-98?"),
        _turn(
            1,
            "assistant",
            payload={
                "final_answer": "CAPEC-98 maps to T1566 and T1598.",
                "facts": ["CAPEC-98 maps to T1598"],
            },
        ),
    ]
    history = history_from_turns(turns)
    assert history == [
        {"role": "user", "content": "which techniques map to CAPEC-98?"},
        {
            "role": "assistant",
            "content": "CAPEC-98 maps to T1566 and T1598.",
            "facts": ["CAPEC-98 maps to T1598"],
        },
    ]


def test_history_from_turns_assistant_without_facts():
    turns = [_turn(0, "assistant", payload={"final_answer": "hi"})]
    history = history_from_turns(turns)
    assert history == [{"role": "assistant", "content": "hi"}]


def test_history_from_turns_limit_keeps_recent():
    turns = [_turn(i, "user", question=f"q{i}") for i in range(5)]
    history = history_from_turns(turns, limit=2)
    assert [h["content"] for h in history] == ["q3", "q4"]


# ---------------------------------------------------------------------------
# Entity dossier model + formatters
# ---------------------------------------------------------------------------


def _dossier_record(neighbor_total=23, related=None):
    return SimpleNamespace(
        primary_id="M1049",
        name="Antivirus/Antimalware",
        properties={"description": "Antivirus solutions use signatures and heuristics.", "neighbor_total": neighbor_total},
        related=related
        if related is not None
        else [
            {"id": "T1566", "name": "Phishing", "type": "MITIGATES", "direction": "out"},
            {"id": "T1204", "name": "User Execution", "type": "MITIGATES", "direction": "out"},
        ],
    )


def test_dossiers_from_records_only_uses_dossier_shaped_records():
    plain = SimpleNamespace(primary_id="T1566", name="Phishing", properties={}, related=[])
    dossiers = dossiers_from_records([_dossier_record(), plain])
    assert set(dossiers) == {"M1049"}
    d = dossiers["M1049"]
    assert d.name == "Antivirus/Antimalware"
    assert d.neighbor_total == 23
    assert d.edges[0].title == "Mitigates"
    assert d.edges[0].node_id == "T1566"


def test_dossier_detail_block_matches_requested_format_with_plus_more():
    d = dossiers_from_records([_dossier_record(neighbor_total=23)])["M1049"]
    block = dossier_detail_block(d)
    assert block.startswith("M1049 (Antivirus/Antimalware): Antivirus solutions")
    assert "adjacent:" in block
    assert "* Mitigates (MITIGATES) -> Phishing (T1566)" in block
    # Only 2 edges present but total is 23 → a "+21 more" tail.
    assert "* (+21 more)" in block


def test_dossier_detail_block_marks_inbound_direction():
    rec = _dossier_record(neighbor_total=1, related=[{"id": "G0016", "name": "APT29", "type": "USES", "direction": "in"}])
    block = dossier_detail_block(dossiers_from_records([rec])["M1049"])
    # Inbound direction is shown by the arrow; the title stays the plain type.
    assert "* Uses (USES) <- APT29 (G0016)" in block


def test_dossier_index_line_lists_held_entities():
    dossiers = dossiers_from_records([_dossier_record()])
    assert dossier_index_line(dossiers) == "Entities held in memory: M1049 (Antivirus/Antimalware)."
    assert dossier_index_line({}) == ""


def test_entity_ids_in_detects_mixed_ids():
    ids = entity_ids_in("compare M1049 with T1566.003 and CAPEC 98")
    assert {"M1049", "T1566.003", "CAPEC-98"} <= ids


# ---------------------------------------------------------------------------
# Deterministic conversation anchor
# ---------------------------------------------------------------------------


def _dossier_turn(seq, dossiers):
    from utils.conversation.persistence import dossier_payload

    return _turn(
        seq, "assistant", payload={"entity_dossiers": dossier_payload(dossiers)}
    )


def test_conversation_anchor_prefers_most_recent_held_entity():
    older = dossiers_from_records(
        [SimpleNamespace(primary_id="T1566", name="Phishing", properties={"neighbor_total": 3}, related=[])]
    )
    newer = dossiers_from_records([_dossier_record()])  # M1049 (Antivirus/Antimalware)
    turns = [
        _turn(0, "user", question="what is T1566?"),
        _dossier_turn(1, older),
        _turn(2, "user", question="what is M1049?"),
        _dossier_turn(3, newer),
    ]
    anchor = conversation_anchor(turns)
    # Most recently hydrated entity comes first, carrying its held name.
    assert anchor[0] == ("M1049", "Antivirus/Antimalware")
    assert ("T1566", "Phishing") in anchor


def test_conversation_anchor_text_fallback_when_no_dossier():
    # No dossier stored, but the answer text printed the entity id.
    turns = [
        _turn(0, "user", question="what is creating a rogue CA certificate?"),
        _turn(1, "assistant", payload={"final_answer": "Creating a Rogue CA Certificate (CAPEC-459) is ..."}),
    ]
    anchor = conversation_anchor(turns)
    assert anchor[0][0] == "CAPEC-459"
    # No dossier held, so the name is empty (id-only anchor).
    assert anchor[0][1] == ""


def test_conversation_anchor_empty_without_turns():
    assert conversation_anchor([]) == []
    assert conversation_anchor([_turn(0, "user", question="hello")]) == []


def test_referential_followup_detects_continuations():
    assert referential_followup("Please explore the execution steps involved.")
    assert referential_followup("show its mitigations")
    assert referential_followup("and the weaknesses?")
    assert referential_followup("tell me more")


def test_referential_followup_ignores_standalone_questions():
    assert not referential_followup("What is Creating a Rogue Certification Authority Certificate?")
    assert not referential_followup("what is phishing?")
