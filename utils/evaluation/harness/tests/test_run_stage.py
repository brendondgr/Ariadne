#!/usr/bin/env python3
"""Runner-agent tests (hermetic: drivers monkeypatched, no DB)."""

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


def _fake_answer() -> SynthesizedAnswer:
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
        narrative="T1047 is mitigated by M1018.",
        claims=[claim],
        verification=VerificationReport(verdicts=[ClaimVerdict(verdict="supported")]),
    )


def _entry() -> GoldenEntry:
    return GoldenEntry(
        question_id="A-MIT-01",
        set_name="attack",
        tier="easy",
        kind="single",
        source="attack",
        question="What mitigations for T1047?",
        entry={"id": "A-MIT-01", "task": {"source": "attack"}},
        gold_expected_ids=frozenset({"M1018", "M1026"}),
        gold_kind="ids",
    )


def test_answer_to_record_extracts_produced_ids():
    record = answer_to_record(_entry(), _fake_answer(), exit_code=0, wall_s=0.5)
    assert record.produced_ids == ["T1047", "M1018"]
    assert record.gold_expected_ids == ["M1018", "M1026"]  # sorted
    assert record.claims[0]["citations"][0]["primary_id"] == "T1047"
    assert record.timings["wall_s"] == 0.5


def test_runner_drives_single_and_records(monkeypatch, tmp_path):
    from utils.evaluation import score_e2e

    # Fake the whole live layer: build() succeeds with a stub router whose
    # _specialist_for returns a sentinel, and run_single returns our answer.
    class _StubRouter:
        cards = {}

        def _specialist_for(self, source):
            return object()

    agent = RunnerAgent()
    agent._routers = {None: _StubRouter()}
    agent._synth_config = object()

    monkeypatch.setattr(
        score_e2e, "run_single", lambda entry, spec, cfg: (None, _fake_answer())
    )

    records = agent.run([_entry()])
    assert len(records) == 1
    assert records[0].error is None
    assert records[0].produced_ids == ["T1047", "M1018"]


def test_runner_captures_per_entry_failure(monkeypatch):
    from utils.evaluation import score_e2e

    class _StubRouter:
        cards = {}

        def _specialist_for(self, source):
            return object()

    agent = RunnerAgent()
    agent._routers = {None: _StubRouter()}
    agent._synth_config = object()

    def _boom(*a, **k):
        raise RuntimeError("neo4j down")

    monkeypatch.setattr(score_e2e, "run_single", _boom)
    records = agent.run([_entry()])
    assert records[0].error is not None
    assert "neo4j down" in records[0].error


def test_run_stage_cli_hermetic_writes_empty(tmp_path):
    from utils.evaluation.harness import cli

    out = str(tmp_path / "golden")
    rc = cli.main(["--stage", "run", "--set", "attack", "--limit", "2", "--no-live", "--out-dir", out])
    assert rc == 0
    rows = list(read_jsonl(str(tmp_path / "golden" / "answers.jsonl")))
    assert rows == []  # hermetic: nothing scored
