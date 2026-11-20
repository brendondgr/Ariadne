"""Phase C: every recorded typed step converts to the internal form and back (scripts/algebra_convert_check.py)."""

from __future__ import annotations

import json

import pytest

from scripts import algebra_convert_check as acc


@pytest.mark.skipif(not (acc.RUN / "variants" / "T-lazy.json").exists(), reason="EXP-2026-11-018 outputs absent")
def test_every_recorded_step_converts_and_round_trips(tmp_path):
    out = tmp_path / "report.json"
    assert acc.main([str(acc.RUN), "--out", str(out)]) == 0
    r = json.loads(out.read_text())
    assert r["n_failures"] == 0
    assert r["converted"] == r["json_round_trip"] == r["inverse_round_trip"] == r["steps"]
    # Only the two invalid drafts recorded in EXP-2026-11-018 are refused on the card.
    assert r["refused"] <= 2
