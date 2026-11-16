"""Era 2 Step 5: the composer never presents a cut list as complete."""

from __future__ import annotations

from utils.specialists.contracts import EvaluatorTrace
from utils.synthesis.composer import DeterministicComposer, _primary_enumeration_claim
from utils.synthesis.tests._fixtures import make_evidence, make_record, make_result


def _many(n: int):
    return make_result(text="which techniques does the group use?",
                       records=[make_record(f"T{1000 + i}", name=f"Tech {i}") for i in range(n)])


def test_a_complete_short_list_says_all():
    c = _primary_enumeration_claim(_many(5))
    assert c.text.startswith("All 5 result(s) for this question: ")


def test_a_list_cut_by_the_listing_bound_states_the_real_total(monkeypatch):
    monkeypatch.setenv("SYNTHESIS_MAX_ENUMERATION_IDS", "10")
    c = _primary_enumeration_claim(_many(25))
    assert c.text.startswith("25 result(s) for this question; the first 10 are listed: ")
    assert "All" not in c.text and len(c.entity_ids) == 10


def test_a_result_cut_at_the_row_ceiling_says_at_least_and_notes_it():
    r = _many(4)
    r.partial = True
    r.traces.append(EvaluatorTrace("ceiling", ok=False, reasons=["cut"],
                                   detail={"row_ceiling": 4, "rows_returned": 4}))
    c = _primary_enumeration_claim(r)
    assert c.text.startswith("At least 4 result(s) for this question (the query stopped at its row ceiling of 4")
    answer = DeterministicComposer().compose(make_evidence([r]))
    assert any("row ceiling of 4" in n and "partial" in n for n in answer.notes)
