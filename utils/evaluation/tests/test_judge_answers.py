#!/usr/bin/env python3
"""What counts as an answer, when a run judges the same set more than once.

The overnight sweep grades one answer set three times to measure the judge's
own run-to-run spread. Each pass writes ``<case>.judgment<suffix>.json`` beside
the answer. The second pass therefore has to walk past the first pass's output,
and the third past both — so "is this an answer?" is not the trivial question
it looks like.

It was got wrong once, and the failure was quiet: a filter that excluded only
``.judgment.json`` let pass three pick up pass two's thirty judgments, grade
them as answers, and report ``n=60`` on a set of thirty. Nothing raised. The
roll-up simply averaged thirty real scores with thirty meaningless ones.
"""

from __future__ import annotations

from utils.evaluation.judge_answers import answer_files


def _touch(directory, *names):
    for name in names:
        (directory / name).write_text("{}")


def test_a_bare_judgment_is_not_an_answer(tmp_path):
    answers = tmp_path / "arm" / "answers"
    answers.mkdir(parents=True)
    _touch(answers, "H-01.json", "H-01.judgment.json")
    assert [p.name for p in answer_files(tmp_path, "arm")] == ["H-01.json"]


def test_a_suffixed_judgment_is_not_an_answer(tmp_path):
    """The regression: ``.judgment.run2.json`` does not end in ``.judgment.json``."""
    answers = tmp_path / "arm" / "answers"
    answers.mkdir(parents=True)
    _touch(answers, "H-01.json", "H-01.judgment.json", "H-01.judgment.run2.json")
    assert [p.name for p in answer_files(tmp_path, "arm")] == ["H-01.json"]


def test_three_passes_never_grow_the_answer_set(tmp_path):
    """Simulate the sweep: each pass must see the same thirty answers."""
    answers = tmp_path / "arm" / "answers"
    answers.mkdir(parents=True)
    cases = [f"H-{i:02d}" for i in range(30)]
    _touch(answers, *[f"{c}.json" for c in cases])
    for suffix in ("", ".run2", ".run3"):
        assert len(answer_files(tmp_path, "arm")) == 30
        _touch(answers, *[f"{c}.judgment{suffix}.json" for c in cases])
    assert len(answer_files(tmp_path, "arm")) == 30


def test_an_error_sidecar_is_not_an_answer(tmp_path):
    answers = tmp_path / "arm" / "answers"
    answers.mkdir(parents=True)
    _touch(answers, "H-01.json")
    (answers / "H-01.judgment.error.txt").write_text("boom")
    assert [p.name for p in answer_files(tmp_path, "arm")] == ["H-01.json"]


# --- extraction ------------------------------------------------------------
#
# Three replies that EXP-2026-08-021 lost, one per failure mode it recorded.
# Six of 1,794 gradings failed there and every one was in the top 5% of answers
# by size, so the loss was systematic rather than thin: it fell on one question
# type and quietly left the hardest cases out of a judged mean.

from utils.evaluation.judge_answers import _json_objects, _parse  # noqa: E402

_COMPLETE = (
    '{"verdict": "PARTIAL", "correctness": 0.5, "faithfulness": 1.0, '
    '"groundedness": 1.0, "completeness": 0.5, "rationale": "x"}'
)


def test_two_objects_in_one_reply_no_longer_lose_the_judgment():
    """The 'Extra data' mode: a greedy match spanned draft *and* verdict.

    The judgment existed and was discarded, which is a different defect from
    never having one.
    """
    reply = f'thinking out loud\n{{"verdict": "CORRECT"}}\nfinal:\n{_COMPLETE}'
    assert _parse(reply)["correctness"] == 0.5


def test_a_lead_object_missing_fields_does_not_win_on_position():
    """The 'missing 5 fields' mode: the first object is not always the answer."""
    reply = f'{{"verdict": "CORRECT"}}\n{_COMPLETE}'
    parsed = _parse(reply)
    assert parsed["verdict"] == "PARTIAL" and "rationale" in parsed


def test_a_truncated_reply_still_raises():
    """The truncation mode is NOT a parser problem and must stay a failure.

    There is no judgment in a reply that stopped mid-object. Recovering it needs
    a bigger budget, not a cleverer parser, which is why judge_one escalates.
    """
    import pytest

    with pytest.raises(ValueError, match="no JSON object"):
        _parse('\n\n{\n "verdict": "CORRECT",\n "correctness": 0.95,')


def test_a_brace_in_prose_is_not_an_object():
    assert _json_objects('costs {approx} then {"a": 1}') == [{"a": 1}]


def test_the_richest_object_is_returned_when_none_is_complete():
    """So `_normalise` names the real gaps rather than whichever came first."""
    reply = '{"verdict": "CORRECT"}\n{"verdict": "CORRECT", "correctness": 0.9}'
    assert _parse(reply) == {"verdict": "CORRECT", "correctness": 0.9}
