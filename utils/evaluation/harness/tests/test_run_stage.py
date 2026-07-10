#!/usr/bin/env python3
"""Runner-agent tests (hermetic: drivers/pipeline monkeypatched, no DB/LLM)."""

from __future__ import annotations

from utils.evaluation.harness.contracts import read_jsonl
from utils.evaluation.harness.golden import GoldenEntry
from utils.evaluation.harness.run_stage import RunnerAgent, answer_to_record
from utils.synthesis.contracts import (
    Citation,
    Claim,
    ClaimVerdict,
    SynthesizedAnswer,
    VerificationReport,
)


def _fake_answer(narrative="T1047 is mitigated by M1018.") -> SynthesizedAnswer:
    claim = Claim(
        text="T1047 is mitigated by M1018",
        citations=(Citation(source="attack", primary_id="T1047"),),
        entity_ids=("T1047", "M1018"),
        kind="fact",
    )
    # rendered_claims() only surfaces verified-supported claims, so a testable
    # answer needs a verification report marking the claim supported.
    return SynthesizedAnswer(
        request="What mitigations for T1047?",
        narrative=narrative,
        claims=[claim],
        verification=VerificationReport(verdicts=[ClaimVerdict(verdict="supported")]),
    )


def _entry(qid="A-MIT-01") -> GoldenEntry:
    return GoldenEntry(
        question_id=qid,
        set_name="attack",
        tier="easy",
        kind="single",
        source="attack",
        question="What mitigations for T1047?",
        entry={"id": qid, "task": {"source": "attack"}},
        gold_expected_ids=frozenset({"M1018", "M1026"}),
        gold_kind="ids",
    )


class _StubRouter:
    cards = {}

    def _specialist_for(self, source):
        return object()


def test_answer_to_record_extracts_produced_ids():
    record = answer_to_record(_entry(), _fake_answer(), exit_code=0, wall_s=0.5)
    assert record.produced_ids == ["T1047", "M1018"]
    assert record.gold_expected_ids == ["M1018", "M1026"]  # sorted
    assert record.claims[0]["citations"][0]["primary_id"] == "T1047"
    assert record.timings["wall_s"] == 0.5


def test_gold_runner_drives_single_and_records(monkeypatch):
    from utils.evaluation import score_e2e

    # Patch the thread-local gold context builder so every worker thread gets a
    # stub router without touching a database.
    monkeypatch.setattr(
        RunnerAgent, "_build_gold_context",
        lambda self: ({None: _StubRouter()}, object()),
    )
    monkeypatch.setattr(
        score_e2e, "run_single", lambda entry, spec, cfg: (None, _fake_answer())
    )

    records = RunnerAgent(concurrency=2).run([_entry()])
    assert len(records) == 1
    assert records[0].error is None
    assert records[0].produced_ids == ["T1047", "M1018"]


def test_gold_runner_captures_per_entry_failure(monkeypatch):
    from utils.evaluation import score_e2e

    monkeypatch.setattr(
        RunnerAgent, "_build_gold_context",
        lambda self: ({None: _StubRouter()}, object()),
    )

    def _boom(*a, **k):
        raise RuntimeError("neo4j down")

    monkeypatch.setattr(score_e2e, "run_single", _boom)
    records = RunnerAgent(concurrency=1).run([_entry()])
    assert records[0].error is not None
    assert "neo4j down" in records[0].error


def test_agentic_runner_drives_iter_pipeline(monkeypatch):
    import utils.orchestration.main as orch

    def _fake_iter(question, **kwargs):
        yield ("status", {"phase": "planning"})
        yield ("evidence", {"evidence": object()})
        yield ("answer", {"synthesized": _fake_answer()})

    monkeypatch.setattr(orch, "iter_pipeline", _fake_iter)
    records = RunnerAgent(agentic=True, concurrency=4).run([_entry()])
    assert len(records) == 1
    assert records[0].error is None
    assert records[0].produced_ids == ["T1047", "M1018"]


def test_agentic_runner_missing_answer_is_error(monkeypatch):
    import utils.orchestration.main as orch

    def _no_answer(question, **kwargs):
        yield ("status", {"phase": "planning"})

    monkeypatch.setattr(orch, "iter_pipeline", _no_answer)
    records = RunnerAgent(agentic=True).run([_entry()])
    assert records[0].error is not None
    assert "no synthesized answer" in records[0].error


def test_concurrent_run_preserves_golden_order(monkeypatch):
    import utils.orchestration.main as orch

    def _iter_by_qid(question, **kwargs):
        # narrative encodes nothing extra; identity check is on question_id order
        yield ("answer", {"synthesized": _fake_answer()})

    monkeypatch.setattr(orch, "iter_pipeline", _iter_by_qid)
    entries = [_entry(f"A-{i:02d}") for i in range(20)]
    records = RunnerAgent(agentic=True, concurrency=8).run(entries)
    assert [r.question_id for r in records] == [e.question_id for e in entries]


def test_run_stage_cli_hermetic_writes_empty(tmp_path):
    from utils.evaluation.harness import cli

    out = str(tmp_path / "golden")
    rc = cli.main(["--stage", "run", "--set", "attack", "--limit", "2", "--no-live", "--out-dir", out])
    assert rc == 0
    rows = list(read_jsonl(str(tmp_path / "golden" / "answers.jsonl")))
    assert rows == []  # hermetic: nothing scored
