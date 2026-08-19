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
