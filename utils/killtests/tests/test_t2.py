"""T2: gate policy, gold resolution on known cases, and the model-free raw path."""
import socket

import pytest

from utils.killtests.graph import DESCRIBE
from utils.killtests.t2 import interpretations as I
from utils.killtests.t2.run import build_interpretations, gate, gold_facets, guess, score_item


# ----------------------------------------------------------------- pure policy

def test_gate_answers_when_all_nonempty_agree():
    recs = {"A#f": ["x", "y"], "B#g": ["x", "y"], "C#h": []}
    g = gate(recs, [("A", "f"), ("B", "g"), ("C", "h")])
    assert g["decision"] == "answer" and g["answer"] == ["x", "y"]


def test_gate_asks_when_answers_differ_and_abstains_when_all_empty():
    assert gate({"A#f": ["x"], "B#g": ["y"]}, [("A", "f"), ("B", "g")])["decision"] == "ask"
    assert gate({"A#f": []}, [("A", "f")])["decision"] == "abstain"
    assert gate({}, [])["decision"] == "abstain"


def test_guess_takes_first_interpretation():
    assert guess({"A#f": ["x"], "B#g": ["y"]}, [("A", "f"), ("B", "g")])["answer"] == ["x"]
    assert guess({"A#f": []}, [("A", "f")])["decision"] == "abstain"


def test_score_item_counts_correct_and_gold_presence():
    item = {"tier": "T3", "split": "confirm", "gold_anchor": "A"}
    ex = {
        "records": {"A#f": ["x"], "B#f": ["y"]},
        "interps": {"raw": [["A", "f"], ["B", "f"]], "filtered": [["A", "f"]],
                    "guess_raw": [["B", "f"]], "guess_filtered": [["A", "f"]],
                    "raw_capped": False, "filtered_capped": False},
        "gold": {"by_dir": {"out": ["f"]}, "answers": {"out": ["x"]}, "resolved": True, "negative": False},
    }
    s = score_item(item, ex)
    assert s["raw"]["decision"] == "ask" and s["raw"]["gold_present"]
    assert s["filtered"]["correct"] and s["guess_filtered"]["correct"]
    assert not s["guess_raw"]["correct"]


# ------------------------------------------------------------ lexical support

def test_lexical_support_reads_relation_and_label_words():
    assert I.lexically_supported("What are the mitigations for T1047?", "MITIGATES|in|Mitigation")
    assert not I.lexically_supported("What are the mitigations for T1047?", "USES|in|Group")
    assert not I.lexically_supported("anything", DESCRIBE)


# ------------------------------------------------------- gold on known cases (live)

def _live():
    from utils.config import load_env
    load_env()
    try:
        from utils.killtests.graph import GraphExecutor
        gx = GraphExecutor()
        gx.records("attack", "T1047", "Technique", "MITIGATES|in|Mitigation")
        return gx
    except Exception:
        pytest.skip("graph stores not reachable")


def test_gold_known_cases():
    gx = _live()
    g = gold_facets({"gold_anchor": "T1047", "gold_relation": "MITIGATES", "gold_target_labels": ["Mitigation"]}, gx)
    assert g["by_dir"] == {"in": ["MITIGATES|in|Mitigation"]}
    g = gold_facets({"gold_anchor": "CAPEC-66", "gold_relation": "ChildOf", "gold_target_labels": ["AttackPattern"]}, gx)
    assert set(g["by_dir"]) == {"in", "out"}
    g = gold_facets({"gold_anchor": "T9999", "gold_relation": None, "gold_target_labels": []}, gx)
    assert g["negative"]
    assert gx.records("capec", "CAPEC-66", "AttackPattern", "ChildOf|out|AttackPattern") == ("CAPEC-248",)
    assert len(gx.records("attack", "T1047", "Technique", "MITIGATES|in|Mitigation")) == 4


HAND = [  # ten questions whose meaning is known; raw must keep the gold interpretation
    ("What are the mitigations for T1047?", "T1047", "MITIGATES|in|Mitigation"),
    ("Which groups use T1566?", "T1566", "USES|in|Group"),
    ("Which software uses T1059?", "T1059", "USES|in|Software"),
    ("What techniques does G0016 use?", "G0016", "USES|out|Technique"),
    ("What is the parent of CAPEC-66?", "CAPEC-66", "ChildOf|out|AttackPattern"),
    ("Which weaknesses does CAPEC-66 exploit?", "CAPEC-66", "EXPLOITS_WEAKNESS|out|Weakness"),
    ("What mitigations does CAPEC-66 have?", "CAPEC-66", "HAS_MITIGATION|out|Mitigation"),
    ("Describe T1047.", "T1047", DESCRIBE),
    ("What is CAPEC-116?", "CAPEC-116", DESCRIBE),
    ("Which tactics is T1047 under?", "T1047", "HAS_TECHNIQUE|in|Tactic"),
]


def test_raw_path_is_model_free_and_keeps_gold(monkeypatch):
    gx = _live()
    from utils.killtests import candidates

    real = socket.create_connection

    def guarded(addr, *a, **k):
        if addr[1] in (9090, 7500):
            raise AssertionError(f"model socket opened: {addr}")
        return real(addr, *a, **k)

    monkeypatch.setattr(socket, "create_connection", guarded)
    for q, anchor, facet in HAND:
        cands = candidates.anchor_candidates(q)
        assert cands[0]["entity_id"] == anchor, q
        interps = build_interpretations({"question": q}, cands, {}, 0.05, 40)
        assert (anchor, facet) in interps["raw"], (q, interps["raw"])
        for a, f in interps["raw"]:
            c = next(x for x in cands if x["entity_id"] == a)
            gx.records(c["dataset"], a, c["label"], f)
