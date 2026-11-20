"""Tests for scripts/count_question_shapes.py (Era 2, Step 9, Phase A)."""

from __future__ import annotations

import builtins
import json
from pathlib import Path

import pytest

from scripts import count_question_shapes as cqs


def test_no_allowlisted_source_is_sealed():
    for rel in cqs.SOURCES.values():
        assert not cqs.SEALED.search(rel), rel
        assert (cqs.REPO / rel).exists(), rel


def test_open_bank_refuses_unknown_and_sealed(monkeypatch):
    with pytest.raises(cqs.SealedBank):
        cqs.open_bank("bank-holdout")
    monkeypatch.setitem(cqs.SOURCES, "sneaky", "docs/evaluation/composition/bank/bank-holdout.json")
    with pytest.raises(cqs.SealedBank):
        cqs.open_bank("sneaky")


def test_deterministic_labels_open_no_sealed_file(monkeypatch):
    opened: list[str] = []
    real_read = Path.read_text

    def spy(self, *a, **k):
        opened.append(str(self))
        return real_read(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", spy)
    real_open = builtins.open
    monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (opened.append(str(f)), real_open(f, *a, **k))[1])
    rows = cqs.label_dev() + cqs.label_gold() + cqs.label_step6()
    assert rows
    assert opened and not [p for p in opened if cqs.SEALED.search(p)]


def test_deterministic_label_sizes():
    dev = cqs.label_dev()
    assert len(dev) == 284
    assert sum("T.describe" in r["codes"] for r in dev) == 35
    assert sum("T.eqfilter" in r["codes"] for r in dev) == 47
    gold = [r for r in cqs.label_gold() if r["source"] == "gold"]
    assert len(gold) == 120
    assert len([r for r in cqs.label_gold() if r["source"] == "variants"]) == 579


def test_stage_of_takes_the_latest_operator():
    assert cqs.stage_of(["T.walk"]) == "today"
    assert cqs.stage_of(["T.walk", "O3.rank", "O1.filter"]) == "3"
    assert cqs.stage_of(["O6.groupby", "O2.aggregate"]) == "6"
    assert cqs.stage_of(["G2.groupbyvalue", "O8.path"]) == "gaps"
    assert cqs.stage_of(["T.walk", "X.knowledge"]) == "outside"
    with pytest.raises(KeyError):
        cqs.stage_of(["T.nonsense"])


def test_allocate_hits_total_and_floor():
    sizes = {"a": 8000, "b": 3, "c": 100, "d": 50}
    plan = cqs.allocate(sizes, 60, 5)
    assert sum(plan.values()) == 60
    assert plan["b"] == 3 and plan["c"] >= 5 and plan["d"] >= 5


def test_cohen_kappa():
    assert cqs.cohen_kappa(["x", "y"] * 5, ["x", "y"] * 5) == 1.0
    assert abs(cqs.cohen_kappa(["x", "x", "y", "y"], ["x", "y", "x", "y"])) < 1e-12


def test_read_labels_rejects_unknown_codes(tmp_path):
    p = tmp_path / "l.jsonl"
    p.write_text(json.dumps({"item": "i", "codes": ["T.walk", "O9.teleport"]}) + "\n")
    with pytest.raises(ValueError):
        cqs.read_labels(p)
