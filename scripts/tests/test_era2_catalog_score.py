"""The EXP-2026-11-015 scorer on synthetic inputs: every gate, both CW readings, the bootstrap."""

from __future__ import annotations

import json

from scripts import era2_catalog_score as S


def _row(case, tier, exact, wrong=False, abstained=False, q=None, typed=None):
    r = {"case_id": case, "tier": tier, "question": q or f"{case}-{tier}", "records_exact": exact,
         "wrong_entity": wrong, "abstained": abstained}
    if typed is not None:
        r["typed"] = [typed]
    return r


def _art(case, ids, typed=None):
    recs = [{"primary_id": i, "related": []} for i in ids]
    a = {"id": case, "evidence_volume": {"records": len(recs)},
         "logic_flow": {"results": [{"records": recs}]}, "run_meta": {}}
    if typed is not None:
        a["run_meta"]["typed"] = [typed]
    return a


class TestDefinitions:
    def test_confidently_wrong_on_variants_excludes_abstentions(self):
        assert S.confidently_wrong_variant(_row("a", "T1", False, wrong=True))
        assert not S.confidently_wrong_variant(_row("a", "T1", False, wrong=True, abstained=True))
        assert not S.confidently_wrong_variant(_row("a", "T1", True))

    def test_dev_outcomes(self):
        auth = _art("x", ["T1", "T2"])
        assert S.dev_outcome(_art("x", []), auth)["lost"]
        assert S.dev_outcome(None, auth)["lost"]                    # an errored question retrieved nothing
        assert S.dev_outcome(_art("x", ["T9"]), auth)["confidently_wrong"]
        assert not S.dev_outcome(_art("x", ["t2", "T9"]), auth)["confidently_wrong"]  # ids compared upper-case
        assert S.dev_outcome(_art("x", ["T9"]), _art("x", []))["gained"]
        assert S.dev_outcome(_art("x", []), _art("x", []))["both_empty"]

    def test_related_ids_count_toward_overlap(self):
        arm = {"id": "x", "evidence_volume": {"records": 1},
               "logic_flow": {"results": [{"records": [{"primary_id": "A", "related": [{"id": "T2"}]}]}]}}
        assert not S.dev_outcome(arm, _art("x", ["T2"]))["confidently_wrong"]


def _fixture():
    cases = [f"c{i}" for i in range(10)]
    variants = {
        "E": [_row(c, t, exact=(i % 2 == 0), wrong=(i == 1 and t == "T1")) for i, c in enumerate(cases)
              for t in ("T0", "T1")],
        "T-lazy": [_row(c, t, exact=(t == "T0" or i < 9), typed={"valid_first": True, "valid_first_raw": i > 2,
                                                                  "n_catalog_calls": 2, "prompt_tokens": 100,
                                                                  "model_calls": 2})
                   for i, c in enumerate(cases) for t in ("T0", "T1")],
    }
    authored = {c: _art(c, [f"T{i}"]) for i, c in enumerate(cases)}
    dev = {
        "E": {c: _art(c, [] if i < 4 else [f"T{i}"]) for i, c in enumerate(cases)},          # lost 4
        "T-lazy": {c: _art(c, [] if i < 2 else (["Z"] if i == 9 else [f"T{i}"])) for i, c in enumerate(cases)},
    }
    return variants, dev, authored


class TestGates:
    def test_all_four_gates_from_synthetic_arms(self):
        variants, dev, authored = _fixture()
        m = S.score(variants, dev, authored)
        g = m["gates"]
        assert g["G1"]["value"] == 0.9 and g["G1"]["pass"]
        assert g["G3"]["value"] == 1.0 and g["G3"]["pass"]
        # amendment 1: floor(E lost / 2) = 2; T-lazy lost 2.
        assert g["G2"]["E_lost"] == 4 and g["G2"]["bar"] == 2 and g["G2"]["value"] == 2 and g["G2"]["pass"]
        assert g["G2"]["reported_old_bar_38"]["pass"]
        # variants: E has one CW (c1 T1), T-lazy none; dev: T-lazy has one (c9), E none -> G4 fails.
        assert g["G4"]["variants"] == {"T-lazy": 0, "E": 1}
        assert g["G4"]["dev"] == {"T-lazy": 1, "E": 0}
        assert g["G4"]["pass"] is False and g["all_pass"] is False

    def test_g2_follows_the_measured_control(self):
        variants, dev, authored = _fixture()
        dev["E"] = {c: _art(c, [] if i < 3 else ["T"]) for i, c in enumerate(sorted(authored))}   # lost 3
        g = S.score(variants, dev, authored)["gates"]
        assert g["G2"]["bar"] == 1 and g["G2"]["pass"] is False

    def test_missing_arms_leave_gates_undecided_not_passed(self):
        g = S.score({}, {}, {"c": _art("c", ["T1"])})["gates"]
        assert g["G1"]["pass"] is None and g["G4"]["pass"] is None and g["all_pass"] is None

    def test_typed_health(self):
        variants, dev, authored = _fixture()
        h = S.score(variants, dev, authored)["health"]["T-lazy"]["variants"]
        assert h["questions"] == 20 and h["valid_at_first_emission"] == 1.0
        assert h["fixed_by_coercion"] == 0.3 and h["catalog_calls_per_question"] == 2.0


class TestBootstrap:
    def test_seeded_and_paired(self):
        variants, dev, authored = _fixture()
        a = S.score(variants, dev, authored)["paired_vs_E"]["T-lazy"]
        b = S.score(variants, dev, authored)["paired_vs_E"]["T-lazy"]
        assert a == b
        t1 = a["records_exact_by_tier"]["T1"]
        assert t1["estimate"] == 0.4 and t1["lo"] <= 0.4 <= t1["hi"] and t1["clusters"] == 10
        assert a["dev_lost"]["estimate"] == -2.0 and a["dev_lost"]["resamples"] == 2000

    def test_a_constant_difference_has_a_zero_width_interval(self):
        out = S.bootstrap([[1.0], [1.0], [1.0]])
        assert out["lo"] == out["hi"] == out["estimate"] == 1.0


def test_main_writes_metrics_and_the_scoreboard(tmp_path):
    variants, dev, authored = _fixture()
    data = tmp_path / "data"
    (data / "variants").mkdir(parents=True)
    for arm, rows in variants.items():
        (data / "variants" / f"{arm}.json").write_text(json.dumps(rows))
    for arm, answers in dev.items():
        d = data / S.DEV_ARMS[arm] / "answers"
        d.mkdir(parents=True)
        for c, a in answers.items():
            (d / f"{c}.json").write_text(json.dumps(a))
            (d / f"{c}.judgment.json").write_text(json.dumps(_art(c, [])))   # a sidecar is not an answer
    auth = tmp_path / "authored"
    auth.mkdir()
    for c, a in authored.items():
        (auth / f"{c}.json").write_text(json.dumps(a))
    assert S.main(["--data", str(data), "--authored", str(auth)]) == 0
    m = json.loads((data / "metrics.json").read_text())
    assert m["dev"]["E"]["lost"] == 4 and m["dev"]["E"]["answered"] == 10
    board = (tmp_path / "tables" / "scoreboard.md").read_text()
    assert "G2 empty retrievals" in board and "| T-lazy |" in board


class TestDiagnosis:
    REF = {"entity_ids": ["G1", "T1", "T2"], "seed_ids": ["G1"]}

    def _r(self, ids, **kw):
        return {"records_exact": False, "abstained": False, "wrong_entity": False, "entity_ids": ids, **kw}

    def test_each_outcome_class(self):
        assert S.variant_class({"records_exact": True}, self.REF) == "exact"
        assert S.variant_class(self._r([], abstained=True), self.REF) == "refused_or_empty"
        assert S.variant_class(self._r(["T1", "T2"]), self.REF) == "anchor_only"
        assert S.variant_class(self._r(["X9"]), self.REF) == "wrong"
        assert S.variant_class(self._r(["G1", "T1", "T2", "T3"]), self.REF) == "superset"
        assert S.variant_class(self._r(["G1", "T1"]), self.REF) == "subset"
        assert S.variant_class(self._r(["G1", "T1", "T9"]), self.REF) == "mixed"

    def test_anchorless_scan_on_both_sets(self):
        scan = {"planner": {"plan": [{"step": {"kind": "scan", "anchor_ids": [], "hops": []}}]}}
        anchored = {"planner": {"plan": [{"step": {"kind": "scan", "anchor_ids": ["T1"], "hops": []}}]}}
        assert S.anchorless_scan_variant(scan) and not S.anchorless_scan_variant(anchored)
        dev = {"logic_flow": {"results": [{"traces": [
            {"step": "resolve", "detail": {"seed_ids": []}},
            {"step": "gate", "detail": {"template": "capec_scan"}}]}]}}
        seeded = {"logic_flow": {"results": [{"traces": [
            {"step": "resolve", "detail": {"seed_ids": ["T1195"]}},
            {"step": "gate", "detail": {"template": "capec_scan"}}]}]}}
        assert S.anchorless_scan_dev(dev) and not S.anchorless_scan_dev(seeded)
