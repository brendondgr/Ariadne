"""Era 2 Step 3: the agent contract and the envelope schema (offline)."""

from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from utils.agent.contracts import (
    ENVELOPE_SCHEMA,
    REQUEST_SCHEMA,
    SCHEMA_DIR,
    AgentRequest,
    AnswerEnvelope,
    envelope_from_synthesis,
    validate_envelope,
)

REPO = Path(__file__).resolve().parents[3]


def test_schema_files_are_current():
    for name, schema in (("envelope", ENVELOPE_SCHEMA), ("request", REQUEST_SCHEMA)):
        on_disk = json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text())
        assert on_disk == json.loads(json.dumps(schema)), (
            f"{name}.schema.json is stale: run `uv run python -c 'from utils.agent.contracts import write_schemas; write_schemas()'`")


def test_the_plans_example_envelope_validates():
    env = {
        "run_id": "r_8f3a", "status": "answered", "path": "loop",
        "answer": {"text": "APT29 uses 14 techniques…",
                   "sets": [{"handle": "set:7", "kind": "Technique", "total": 14, "complete": True, "ids": ["T1059"]}]},
        "citations": [{"id": "T1059", "source": "attack", "query_hash": "sha256:00"}],
        "confidence": {"score": 0.93, "threshold": 0.81, "calibrated_on": "card-generated"},
        "trace": {"steps": 4, "tools": ["resolve_entity", "expand", "expand", "set_op"],
                  "served_model": "gemma4-31b/106", "seconds": 7.4},
        "clarification": None, "reason": None,
    }
    assert validate_envelope(env).status == "answered"


def test_the_plans_example_clarification_validates():
    env = {"run_id": "r_1", "status": "needs_clarification", "path": "loop", "clarification": {
        "resume": "r_1", "why": "two anchors", "questions": [{
            "header": "Which APT29?", "question": "Which one do you mean?",
            "options": [{"label": "G0016 APT29", "detail": "SVR"}, {"label": "G0118 UNC2452"}]}]}}
    assert validate_envelope(env).clarification.questions[0].header == "Which APT29?"


@pytest.mark.parametrize("bad, match", [
    ({"status": "answered"}, "requires an answer"),
    ({"status": "insufficient"}, "requires a reason"),
    ({"status": "not_expressible"}, "requires a reason"),
    ({"status": "error"}, "requires a reason"),
    ({"status": "needs_clarification"}, "clarification is set exactly"),
    ({"status": "answered", "answer": {"text": "x"},
      "clarification": {"resume": "r", "questions": [{"header": "h", "question": "q",
                                                      "options": [{"label": "a"}, {"label": "b"}]}]}},
     "clarification is set exactly"),
    ({"status": "answered", "answer": {"text": "x"}, "surprise": 1}, "Extra inputs"),
    ({"status": "maybe"}, "status"),
    ({"status": "answered", "answer": {"text": "x", "sets": [{"handle": "s", "kind": "K", "total": -1,
                                                               "complete": True}]}}, "total"),
])
def test_invalid_envelopes_are_rejected(bad, match):
    with pytest.raises(ValidationError, match=match):
        validate_envelope({"run_id": "r", "path": "loop", **bad})


def test_clarification_options_are_bounded():
    q = {"header": "h", "question": "q", "options": [{"label": "only one"}]}
    with pytest.raises(ValidationError):
        validate_envelope({"run_id": "r", "status": "needs_clarification", "path": "loop",
                           "clarification": {"resume": "r", "questions": [q]}})


def test_clarification_must_resume_this_run():
    with pytest.raises(ValidationError, match="resume"):
        validate_envelope({"run_id": "r", "status": "needs_clarification", "path": "loop", "clarification": {
            "resume": "other", "questions": [{"header": "h", "question": "q",
                                              "options": [{"label": "a"}, {"label": "b"}]}]}})


def test_request_defaults_and_federation():
    r = AgentRequest(question="q", graph=["attack", "capec"])
    assert r.graphs == ["attack", "capec"] and r.mode == "auto" and not r.interactive
    assert r.budget.steps == 6
    with pytest.raises(ValidationError):
        AgentRequest(question="", graph="attack")


def test_comparable_drops_clock_keys():
    env = validate_envelope({"run_id": "r", "status": "insufficient", "path": "loop", "reason": "x",
                             "trace": {"seconds": 9.9}})
    assert "seconds" not in env.comparable()["trace"]


# --------------------------------------------------------------------------- #
# The fast path: every recorded pipeline answer becomes a valid envelope
# --------------------------------------------------------------------------- #

RECORDED = sorted(glob.glob(str(REPO / "docs/evaluation/answers/*.json")))


def test_every_recorded_pipeline_answer_becomes_a_valid_envelope():
    seen = {"answered": 0, "insufficient": 0}
    n = 0
    for path in RECORDED:
        d = json.loads(Path(path).read_text())
        if not isinstance(d.get("answer"), dict):
            continue
        n += 1
        env = envelope_from_synthesis(d["answer"], run_id=f"fast-{d['id']}")
        again = validate_envelope(env.model_dump(mode="json"))       # round-trips through JSON
        assert again == env and env.path == "fast"
        seen[env.status] += 1
        if env.status == "answered":
            assert env.answer.text and env.citations
    assert n == 120 and seen["answered"] > 0 and seen["insufficient"] > 0


def test_unsupported_claims_are_not_shown():
    ans = {"headline": "", "narrative": "", "claims": [
        {"text": "T1 is used.", "citations": [{"source": "attack", "primary_id": "T1"}], "entity_ids": ["T1"],
         "verdict": {"supported": False}}], "abstentions": []}
    env = envelope_from_synthesis(ans, "r")
    assert env.status == "insufficient" and env.citations == []


def test_an_envelope_dumps_to_json_and_back():
    env = AnswerEnvelope(run_id="r", status="not_expressible", path="loop",
                         reason="'trend over time' needs a time-series operator")
    assert validate_envelope(json.loads(env.model_dump_json())) == env
