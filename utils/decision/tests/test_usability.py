"""Pure pieces of the EXP-2026-11-014 treatments."""

from utils.decision import usability as U
from utils.decision.items import NONE, Item


def _d4(question: str, gold: str = "USES|out|SubTechnique") -> Item:
    opts = {"USES|out|SubTechnique": "Software -USES-> SubTechnique: g", "USES|out|Technique": "Software -USES-> Technique: g",
            "USES|in|Group": "Software <-USES- Group: g", NONE: "none of these relations"}
    return Item(id="D4:x", decision="D4", group="attack:S1", stratum="name|2+",
                context="Graph: attack. The question is about this known entity: S1 (Software): Net.",
                question=question, prompt="Which relation from the known entity answers the question?",
                options=opts, gold=gold, tags={"dataset": "attack", "real_options": 3})


def test_label_and_keys():
    it = _d4("Which sub-techniques does Net use?")
    assert U.item_label(it) == "Software"
    assert U.relation_keys([it]) == sorted(f"attack|Software|{k}" for k in it.options if k != NONE)


def test_rulefilter_narrows_to_named_target_and_keeps_none():
    r = U.rulefilter_item(_d4("Which sub-techniques does Net use?"))
    # As frozen: "sub-techniques" also names "technique" (the hyphen is a word boundary), so both stay.
    assert r is not None and set(r.options) == {"USES|out|SubTechnique", "USES|out|Technique", NONE}
    assert U.rulefilter_item(_d4("What does Net relate to?")) is None          # nothing named: unchanged


def test_rulefilter_matches_plural_groups_only_for_group():
    r = U.rulefilter_item(_d4("Which groups use Net?", gold="USES|in|Group"))
    assert set(r.options) == {"USES|in|Group", NONE}


def test_shortlist_keys_cumulative_and_excludes_none():
    p = {"a": 0.6, "b": 0.3, "c": 0.05, NONE: 0.05}
    assert U.shortlist_keys(p, 0.5) == ["a"]
    assert U.shortlist_keys(p, 0.9) == ["a", "b"]
    assert U.shortlist_keys(p, 0.99) == ["a", "b", "c"]


def test_yesno_decide():
    assert U.yesno_decide({"a": 0.8, "b": 0.3}, 0.5) == ("a", 0.8)
    k, c = U.yesno_decide({"a": 0.4, "b": 0.3}, 0.5)
    assert k == NONE and abs(c - 0.6) < 1e-9


def test_check_readings_flags_schema_names_length_and_duplicates():
    keys = ["attack|Software|USES|out|Technique", "attack|Software|USES|out|SubTechnique"]
    assert U.check_readings({keys[0]: "the techniques this software uses",
                             keys[1]: "the sub-techniques this software uses"}, keys) == []
    bad = U.check_readings({keys[0]: "the SubTechnique nodes", keys[1]: "the SubTechnique nodes"}, keys)
    assert any("schema" in b for b in bad) and any("same reading" in b for b in bad)
    assert any("over" in b for b in U.check_readings({keys[0]: " ".join(["w"] * 13), keys[1]: "x"}, keys))


def test_wording_item_replaces_text_keeps_none():
    it = _d4("q")
    readings = {f"attack|Software|{k}": f"reading {i}" for i, k in enumerate(it.options) if k != NONE}
    w = U.wording_item(it, readings)
    assert w.id == "W:D4:x" and w.options[NONE] == "none of these relations"
    assert w.options["USES|out|SubTechnique"] == "reading 0"


def test_verifier_gold_is_whether_the_pick_is_right():
    it = _d4("q")
    assert U.verifier_item(it, "USES|out|SubTechnique").gold == "yes"
    assert U.verifier_item(it, "USES|in|Group").gold == "no"
