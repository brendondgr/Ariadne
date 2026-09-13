"""Cover for the four gates, and for the denominator that has gone wrong before."""

from __future__ import annotations

import json

from scripts.narrator_seam_health import health, load


def _artifact(case, claims, *, fallback=None, wall=1.0):
    out = {"id": case, "answer": {"claims": claims}, "run_meta": {"wall_s": wall}}
    if fallback:
        out["answer"]["fallback_reason"] = fallback
    return out


def _claim(text="a", verdict="supported"):
    return {"text": text, "verdict": verdict}


class TestLoader:
    def test_sidecars_and_manifests_are_not_answers(self, tmp_path):
        (tmp_path / "D0-a.json").write_text(json.dumps(_artifact("D0-a", [_claim()])))
        (tmp_path / "D0-a.judgment.rc2.json").write_text(json.dumps(_artifact("D0-a", [])))
        (tmp_path / "manifest.json").write_text(json.dumps({"not": "an answer"}))
        assert set(load(tmp_path)) == {"D0-a"}


class TestGates:
    def _pair(self, narrator, control):
        return health(narrator, control)

    def test_a_clean_run_passes_every_gate(self):
        n = {"a": _artifact("a", [_claim()])}
        c = {"a": _artifact("a", [_claim()])}
        out = self._pair(n, c)
        assert out["passes"] is True
        assert out["fallback_rate"] == 0.0
        assert out["claims_identical"] == 1

    def test_the_fallback_rate_divides_by_answers(self):
        # Two of four, not two of however many files happen to be in the dir.
        n = {str(i): _artifact(str(i), [_claim()],
                               fallback="LLM narrator unavailable (timeout)" if i < 2 else None)
             for i in range(4)}
        out = self._pair(n, {str(i): _artifact(str(i), [_claim()]) for i in range(4)})
        assert out["answers"] == 4
        assert out["fallback_rate"] == 0.5
        assert out["fallback_healthy"] is False

    def test_a_fallback_rate_at_the_threshold_is_healthy(self):
        n = {str(i): _artifact(str(i), [_claim()],
                               fallback="x (y)" if i == 0 else None) for i in range(10)}
        out = self._pair(n, {str(i): _artifact(str(i), [_claim()]) for i in range(10)})
        assert out["fallback_rate"] == 0.1
        assert out["fallback_healthy"] is True

    def test_a_changed_claim_fails_even_when_nothing_else_does(self):
        n = {"a": _artifact("a", [_claim("rewritten by the model")])}
        c = {"a": _artifact("a", [_claim("composed deterministically")])}
        out = self._pair(n, c)
        assert out["claims_changed_case_ids"] == ["a"]
        assert out["passes"] is False

    def test_a_new_unsupported_verdict_fails(self):
        n = {"a": _artifact("a", [_claim(verdict="unsupported")])}
        c = {"a": _artifact("a", [_claim(verdict="supported")])}
        out = self._pair(n, c)
        assert out["new_unsupported_case_ids"] == ["a"]
        assert out["passes"] is False

    def test_an_unsupported_verdict_the_control_already_had_is_not_new(self):
        n = {"a": _artifact("a", [_claim(verdict="unsupported")])}
        c = {"a": _artifact("a", [_claim(verdict="unsupported")])}
        assert self._pair(n, c)["new_unsupported_case_ids"] == []

    def test_the_clock_is_reported_for_both_sides(self):
        n = {"a": _artifact("a", [_claim()], wall=10.0)}
        c = {"a": _artifact("a", [_claim()], wall=2.0)}
        clock = self._pair(n, c)["wall_clock"]
        assert clock["narrator"]["mean_s"] == 10.0
        assert clock["control"]["mean_s"] == 2.0

    def test_an_empty_run_does_not_pass_by_vacuum(self):
        # Zero answers means zero fallbacks, which must not read as healthy.
        assert self._pair({}, {})["passes"] is False
