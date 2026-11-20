"""Tests for the algebra probe set (Era 2, Step 9, Phase G): split, bank emitter, scorer.

None of these touch a store or a model; generation itself runs live and is not tested here.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

import pytest

from scripts import algebra_probe_score as aps
from scripts import algebra_probe_set as ap


def _item(iid: str, op: str = "O1", ds: str = "attack", kind: str = "nodes", ids=("T1001", "T1002"),
          value=None, negative: bool = False, source: str = "generated") -> dict:
    gold = {"kind": kind, "ids": list(ids) if kind == "nodes" else [],
            "stored_ids": [f"attack-pattern--{x}" for x in ids] if kind == "nodes" else [],
            "value": value, "total": len(ids), "complete": True}
    return {"id": iid, "dataset": ds, "operator": op, "detail": f"{op}.x", "switch": ap.SWITCH.get(op, "core"),
            "source": source, "external_ref": None, "template_question": f"Q {iid}?", "description": "d",
            "ir": {"@": "Nodes"}, "reduce": None, "needs_edge_props": False,
            "anchors": [{"public": "G0016", "stored": "intrusion-set--x", "label": "Group", "name": "APT29"}],
            "entities": ["Group", "USES", "Technique"], "negative": negative, "gold": gold}


def _items() -> list[dict]:
    out = []
    for op in ap.TARGET:
        for ds in ("attack", "capec"):
            for n in range(5 if op != "O4" else 9):
                out.append(_item(f"PG-{ds}-{op}-{n:04d}", op, ds))
    return out


# --------------------------------------------------------------------------- split


def test_split_is_deterministic_and_order_free():
    a = ap.split_items([dict(i) for i in _items()])
    b = ap.split_items([dict(i) for i in reversed(_items())])
    assert {i["id"]: i["split"] for i in a} == {i["id"]: i["split"] for i in b}


def test_split_is_stratified_per_operator_and_dataset():
    items = ap.split_items(_items())
    strata = collections.defaultdict(collections.Counter)
    for i in items:
        strata[(i["operator"], i["dataset"])][i["split"]] += 1
    for key, c in strata.items():
        assert c["tune"] >= 1 and c["measure"] >= 1, key
        assert abs(c["tune"] - c["measure"]) <= 1, key


def test_split_depends_on_ids_only():
    items = ap.split_items(_items())
    renamed = ap.split_items([{**i, "template_question": "changed"} for i in _items()])
    assert [i["split"] for i in items] == [i["split"] for i in renamed]


# --------------------------------------------------------------------------- negatives and sealed banks


def test_negative_quota_caps_share():
    items = [_item(f"I{n}") for n in range(90)] + [_item(f"N{n}", negative=True) for n in range(20)]
    drops = collections.Counter()
    kept = ap.cap_negatives(items, drops)
    neg = sum(1 for i in kept if i["negative"])
    assert neg / len(kept) <= ap.NEG_SHARE + 1e-9
    assert sum(drops.values()) == 20 - neg


def test_refuses_sealed_banks(tmp_path):
    for name in ("bank-holdout.json", "heldout/bank.json", "fresh-2026/bank.json"):
        with pytest.raises(PermissionError):
            ap.open_tuning_bank(tmp_path / name)
    for p in ap.STEP6_BANKS.values():
        assert not ap.SEALED.search(str(p))


# --------------------------------------------------------------------------- bank emitter


def _structured() -> dict:
    items = ap.split_items(_items() + [_item("PG-attack-O2-v", "O2", kind="value", value=4.0, ids=()),
                                       _item("PG-capec-O4-v", "O4", ds="capec", kind="value", value=False, ids=(),
                                             negative=True)])
    return {"meta": {"created": "2026-11-20"}, "items": items}


def test_bank_emitter_format_loads_in_experiment_untruncated(tmp_path):
    from utils.evaluation.experiment_untruncated import load_work

    s = _structured()
    wording = {i["id"]: f"Reworded {i['id']}?" for i in s["items"]}
    paths = ap.emit_banks(s, wording, tmp_path)
    seen = set()
    for split, p in paths.items():
        doc = json.loads(p.read_text())
        work = load_work(str(p))
        assert len(work) == len(doc["questions"]) == sum(1 for i in s["items"] if i["split"] == split)
        for entry, kind in work:
            assert kind in ("attack", "capec")
            assert entry["question"].startswith("Reworded ")
            assert entry["split"] == split
            assert entry["task"]["source"] == kind
            assert entry["task"]["seed_ids"] == ["G0016"]
            assert entry["ex_gold"]["kind"] in ("set", "value")
            assert entry["algebra_probe"]["id"] == entry["id"]
            seen.add(entry["id"])
    assert seen == {i["id"] for i in s["items"]}


def test_bank_emitter_gold_shapes(tmp_path):
    s = _structured()
    paths = ap.emit_banks(s, {i["id"]: "q" for i in s["items"]}, tmp_path)
    entries = {e["id"]: e for p in paths.values() for e in json.loads(p.read_text())["questions"]}
    assert entries["PG-attack-O2-v"]["ex_gold"] == {"pool": "algebra", "scheme": "attack", "kind": "value",
                                                     "expected": [], "value": 4.0}
    assert entries["PG-capec-O4-v"]["ex_gold"]["value"] is False
    node = entries["PG-attack-O1-0000"]["ex_gold"]
    assert node["kind"] == "set" and node["expected"] == ["T1001", "T1002"]


def test_bank_emitter_refuses_missing_wording(tmp_path):
    s = _structured()
    with pytest.raises(SystemExit):
        ap.emit_banks(s, {}, tmp_path)


def test_read_wording(tmp_path):
    p = tmp_path / "w.jsonl"
    p.write_text('{"id": "a", "question": "A?"}\n\n{"id": "b", "question": "B?"}\n')
    assert ap.read_wording(p) == {"a": "A?", "b": "B?"}


# --------------------------------------------------------------------------- scorer


def _entry(item: dict) -> dict:
    return ap.bank_entry({**item, "split": "measure"}, item["template_question"])


def _answer(iid: str, *, results=None, claims=None) -> dict:
    return {"id": iid, "answer": {"claims": [{"entity_ids": c} for c in (claims or [])]},
            "run_meta": {"algebra_results": results} if results is not None else {}}


def _step(**kw) -> dict:
    return {"step": "s1", "kind": kw.pop("kind", "nodes"), "value": kw.pop("value", None), "ids": kw.pop("ids", []),
            "rows": kw.pop("rows", []), "total": None, "complete": True, "info": {}}


def test_scorer_node_gold_from_algebra_results():
    e = _entry(_item("n1"))
    assert aps.judge(e, _answer("n1", results=[_step(ids=["X"]), _step(ids=["T1002", "T1001"])]))["verdict"] == "exact"
    # the last step is the answer, not an earlier one
    assert aps.judge(e, _answer("n1", results=[_step(ids=["T1001", "T1002"]), _step(ids=["T1001"])]))["verdict"] \
        == "confidently_wrong"
    # stored ids are translated through the item's own map
    st = _step(ids=["attack-pattern--T1001", "attack-pattern--T1002"])
    assert aps.judge(e, _answer("n1", results=[st]))["verdict"] == "exact"
    assert aps.judge(e, _answer("n1", results=[_step(ids=[])]))["verdict"] == "abstained"


def test_scorer_node_gold_falls_back_to_entity_ids():
    e = _entry(_item("n2"))
    assert aps.judge(e, _answer("n2", claims=[["T1001"], ["T1002"]]))["verdict"] == "exact"
    assert aps.judge(e, _answer("n2", claims=[["T1001"], ["T9999"]]))["verdict"] == "confidently_wrong"
    assert aps.judge(e, _answer("n2", claims=[]))["verdict"] == "abstained"
    assert aps.judge(e, None)["verdict"] == "missing"


def test_scorer_shortest_reads_paths():
    e = _entry(_item("p", "O8", kind="nodes", ids=("T1071", "C0057", "T1546.016")))
    rows = [{"path": ["T1071", "USES", "C0057", "USES", "T1546.016"], "rels": ["USES", "USES"]}]
    assert aps.judge(e, _answer("p", results=[_step(kind="shortest", rows=rows)]))["verdict"] == "exact"


def test_scorer_capec_stored_forms():
    e = _entry(_item("c", ds="capec", ids=("CAPEC-66", "CWE-89")))
    assert aps.judge(e, _answer("c", results=[_step(ids=["capec:attack-pattern:66", "cwe:89"])]))["verdict"] == "exact"


def test_scorer_scalar_values():
    e = _entry(_item("v", "O2", kind="value", value=10.5, ids=()))
    ok = lambda v: aps.judge(e, _answer("v", results=[_step(kind="aggregate", value=v)]))["verdict"]  # noqa: E731
    assert ok(10.5) == "exact"
    assert ok(10.5 * (1 + 1e-12)) == "exact"
    assert ok(10.6) == "confidently_wrong"
    assert ok(None) == "abstained"
    ei = _entry(_item("vi", "O2", kind="value", value=4, ids=()))
    assert aps.judge(ei, _answer("vi", results=[_step(kind="count", value=4.0)]))["verdict"] == "exact"
    assert aps.judge(ei, _answer("vi", results=[_step(kind="count", value=5)]))["verdict"] == "confidently_wrong"


def test_scorer_bool_and_dates():
    e = _entry(_item("b", "O4", kind="value", value=False, ids=(), negative=True))
    assert aps.judge(e, _answer("b", results=[_step(kind="verify", value=False)]))["verdict"] == "exact"
    assert aps.judge(e, _answer("b", results=[_step(kind="verify", value=True)]))["verdict"] == "confidently_wrong"
    assert aps.judge(e, _answer("b", results=[_step(kind="verify", value=0)]))["verdict"] == "confidently_wrong"
    d = _entry(_item("d", "O2", kind="value", value="2004-06-01T04:00:00.000Z", ids=()))
    assert aps.judge(d, _answer("d", results=[_step(kind="aggregate", value="2004-06-01")]))["verdict"] == "exact"
    assert aps.judge(d, _answer("d", results=[_step(kind="aggregate", value="2004-06-02")]))["verdict"] \
        == "confidently_wrong"


def test_scorer_scalar_without_structure_is_unparsed():
    e = _entry(_item("u", "O2", kind="value", value=3, ids=()))
    assert aps.judge(e, _answer("u", claims=[["CAPEC-1"]]))["verdict"] == "unparsed"
    assert aps.judge(e, _answer("u"))["verdict"] == "abstained"


def test_scorer_negative_node_gold_empty_is_exact():
    e = _entry(_item("z", "O7", ids=(), negative=True))
    assert aps.judge(e, _answer("z", results=[_step(ids=[])]))["verdict"] == "exact"
    assert aps.judge(e, _answer("z", results=[_step(ids=["T1001"])]))["verdict"] == "confidently_wrong"


def test_score_report_groups(tmp_path):
    items = [_item("a1", "O1"), _item("a2", "O8"), _item("a3", "O4", kind="value", value=True, ids=())]
    bank = {"meta": {}, "questions": [_entry(i) for i in items]}
    (tmp_path / "bank.json").write_text(json.dumps(bank))
    ans = tmp_path / "arm" / "answers"
    ans.mkdir(parents=True)
    (ans / "a1.json").write_text(json.dumps(_answer("a1", results=[_step(ids=["T1001", "T1002"])])))
    (ans / "a2.json").write_text(json.dumps(_answer("a2", results=[_step(ids=["T1001"])])))
    (ans / "a2.judgment.json").write_text(json.dumps({"id": "a2", "junk": True}))
    rep = aps.score(tmp_path / "arm", tmp_path / "bank.json")
    assert rep["overall"]["exact"] == 1 and rep["overall"]["confidently_wrong"] == 1 and rep["overall"]["missing"] == 1
    assert rep["by_switch"]["extended"]["confidently_wrong"] == 1
    assert rep["by_operator"]["O1"]["exact_rate"] == 1.0
    assert set(rep["by_switch"]) == {"core", "extended"}


# --------------------------------------------------------------------------- the committed probe set


PROBE = ap.OUT / "probe-structured.json"


@pytest.mark.skipif(not PROBE.exists(), reason="probe set not generated")
def test_committed_probe_set_is_well_formed():
    from utils.specialists.algebra import from_dict

    doc = json.loads(PROBE.read_text())
    items = doc["items"]
    assert len({i["id"] for i in items}) == len(items)
    strata = collections.defaultdict(set)
    for i in items:
        from_dict(i["ir"])  # every IR round-trips
        strata[(i["operator"], i["dataset"])].add(i["split"])
        g = i["gold"]
        assert g["complete"] is True
        if g["kind"] == "nodes":
            assert g["ids"] or i["negative"]
            assert all(":" not in x and "--" not in x for x in g["ids"])
        else:
            assert g["value"] is not None
        assert i["switch"] == ("extended" if i["operator"] in ("O7b", "O8") else "core")
    assert all(s == {"tune", "measure"} for s in strata.values())
    assert sum(i["negative"] for i in items) <= ap.NEG_SHARE * len(items)
    # AttackQA text never committed: external items carry our own template wording
    for line in (ap.OUT / "wording-input.jsonl").read_text().splitlines():
        row = json.loads(line)
        assert set(row) == {"id", "dataset", "template_question", "description"}
