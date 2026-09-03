"""Regression cover for the row-count read that produced a false cause.

`classify` read ``row_count`` off the result object. The specialists record it
inside ``traces[].detail``, so the read returned nothing for every artifact ever
written, ``query_built_returned_no_rows`` became the only reachable verdict, and
EXP-2026-09-002 published "63 of 63" and "68 of 68" as findings. The first test
is the one that would have caught it: a result holding records must never be
called empty.
"""

from __future__ import annotations

from scripts.anomaly_triage import classify, row_count


def _result(*, traces=None, records=None):
    out: dict = {"source": "attack", "ok": True}
    if traces is not None:
        out["traces"] = traces
    if records is not None:
        out["records"] = records
    return out


def _trace(step: str, rows: int):
    return {"step": step, "ok": True, "reasons": [], "detail": {"row_count": rows}}


def _answer(result, *, records=1, related=0, coverage=0.5):
    return {
        "logic_flow": {"results": [result]},
        "evidence_volume": {"results": 1, "records": records, "related": related},
        "deterministic_scores": {"coverage": {"coverage": coverage}},
    }


class TestRowCount:
    def test_reads_the_trace_detail_not_the_result(self):
        # The field lives one level down. Reading it off the result -- the
        # original defect -- gives 0 for a query that returned 22 rows.
        result = _result(traces=[_trace("execute", 22)])
        assert "row_count" not in result
        assert row_count(result) == 22

    def test_prefers_execute_over_downstream_steps(self):
        result = _result(traces=[_trace("normalize", 3), _trace("execute", 22)])
        assert row_count(result) == 22

    def test_falls_back_to_the_materialised_records(self):
        result = _result(records=[{"primary_id": "T1037"}, {"primary_id": "T1059"}])
        assert row_count(result) == 2

    def test_zero_when_nothing_recorded_a_count(self):
        assert row_count(_result()) == 0

    def test_genuinely_empty_query_still_reads_zero(self):
        assert row_count(_result(traces=[_trace("execute", 0)], records=[])) == 0


class TestClassify:
    def test_a_result_carrying_records_is_never_called_empty(self):
        # The regression. Before the fix this returned
        # "query_built_returned_no_rows" for all 572 artifacts.
        answer = _answer(_result(traces=[_trace("execute", 22)],
                                 records=[{"primary_id": "T1037"}]))
        assert classify(answer, {}) != "query_built_returned_no_rows"

    def test_no_query_built_when_there_are_no_results(self):
        answer = _answer(_result())
        answer["logic_flow"]["results"] = []
        assert classify(answer, {}) == "no_query_built"

    def test_empty_query_is_still_reported_when_it_is_true(self):
        answer = _answer(_result(traces=[_trace("execute", 0)], records=[]),
                         records=0)
        assert classify(answer, {}) == "query_built_returned_no_rows"

    def test_rows_returned_but_nothing_extracted_is_reachable(self):
        # This branch was dead code while rows was always 0.
        answer = _answer(_result(traces=[_trace("execute", 22)]),
                         records=0, related=0)
        assert classify(answer, {}) == "rows_returned_but_no_evidence_extracted"

    def test_wrong_entities_is_reachable(self):
        answer = _answer(_result(traces=[_trace("execute", 22)],
                                 records=[{"primary_id": "T1059"}]),
                         records=22, coverage=0.0)
        assert classify(answer, {}) == "evidence_extracted_but_wrong_entities"

    def test_partial_recall_is_reachable(self):
        answer = _answer(_result(traces=[_trace("execute", 22)],
                                 records=[{"primary_id": "T1037"}]),
                         records=22, coverage=0.5)
        assert classify(answer, {}) == "partial_recall"
