"""Era 2 Step 6: the card question generator on a small fixture card (offline)."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass

import pytest

from utils.specialists.evalset import card_generator as CG

CARD = {
    "dataset": "toy",
    "node_labels": ["Group", "Technique", "Mitigation"],
    "entity_descriptions": {
        "nodes": {"Group": "An adversary group.", "Technique": "An attack technique.",
                  "Mitigation": "A defensive measure."},
        "relationships": {"USES": "A Group uses a Technique.", "MITIGATES": "A Mitigation mitigates a Technique.",
                          "STUDIES": "A Group researches a Technique without using it yet."},
        "relationship_paraphrases": {"USES": ["employs", "leverages"], "MITIGATES": ["counters"]},
    },
}


@dataclass(frozen=True)
class F:
    rel_type: str
    direction: str
    neighbour_label: str


class Registry:
    FACETS = {"Group": [F("USES", "out", "Technique"), F("STUDIES", "out", "Technique")],
              "Technique": [F("USES", "in", "Group"), F("STUDIES", "in", "Group"), F("MITIGATES", "in", "Mitigation")],
              "Mitigation": [F("MITIGATES", "out", "Technique")]}

    def label_facets(self, label, dataset=None):
        return self.FACETS.get(label, [])


class Backend:
    """A tiny in-memory graph with the exact-backend interface the generator uses."""

    name = "fake"
    NODES = {
        "Group": {"G1": "Alpha Bear", "G2": "Beta Spider", "G3": "Lonely Wolf", "G4": "Beta Spider"},
        "Technique": {"T1": "Phishing", "T2": "Scripting", "T3": "Unused Trick"},
        "Mitigation": {"M1": "Training", "M2": "Filtering"},
    }
    EDGES = [("G1", "USES", "T1"), ("G1", "USES", "T2"), ("G2", "USES", "T2"), ("G4", "USES", "T1"),
             ("M1", "MITIGATES", "T1"), ("M2", "MITIGATES", "T1"), ("M2", "MITIGATES", "T2"),
             ("G1", "STUDIES", "T3"), ("G2", "STUDIES", "T1")]

    def _label(self, i):
        return next(lab for lab, ns in self.NODES.items() if i in ns)

    def _nbrs(self, spec_seed, rel, direction, target):
        out = set()
        for s, r, o in self.EDGES:
            if r != rel:
                continue
            if direction in ("out", "both") and s == spec_seed:
                out.add(o)
            if direction in ("in", "both") and o == spec_seed:
                out.add(s)
        return {x for x in out if not target or self._label(x) == target}

    def nodes(self, label):
        return [{"id": i, "name": n, "description": f"{n} is a {label.lower()}."} for i, n in self.NODES[label].items()]

    def degrees(self, label, rel, direction, target):
        return {i: len(self._nbrs(i, rel, direction, target)) for i in self.NODES[label]}

    def stream(self, spec, ceiling):
        ids = sorted(set().union(*(self._nbrs(s, spec.rel, spec.direction, spec.target_label) for s in spec.seeds)))
        return ids, True

    def count(self, spec):
        return len(self.stream(spec, 10**9)[0])

    def set_query(self, spec):
        return f"fake {spec}"

    def anchors_found(self, seeds):
        return [s for s in seeds if any(s in ns for ns in self.NODES.values())]

    def anchor_facets(self, seeds):
        out = []
        for s, r, o in self.EDGES:
            if s in seeds:
                out.append({"rel": r, "direction": "out", "label": self._label(o), "n": 1})
            if o in seeds:
                out.append({"rel": r, "direction": "in", "label": self._label(s), "n": 1})
        return out


def writer(leak: bool = False):
    """A scripted model: quotes the required reference; leaks forbidden words when asked to."""
    calls = []

    def w(system, user):
        calls.append((system, user))
        if system == CG.SYS_REWORD or system == CG.SYS_DESCRIBE:
            return "a crew of hackers" if "Alpha" not in user else "a northern crew"
        ref = re.search(r"Refer to the known entity exactly as: (.+)", user).group(1)
        if leak and "everyday words" in user and "Your last attempt" not in user:
            return f"Which Technique does {ref} use?"            # leaks 'use'
        if "everyday words" in user:
            return f"Which Technique does {ref} put into practice?"
        if "by what it means" in user:
            return f"Which defensive measures relate to {ref}?" if "Mitigation" in user else \
                   f"Which attack methods are tied to {ref}?" if "Technique (" in user else f"Which crews relate to {ref}?"
        return f"Which entries are linked to {ref}?"
    w.calls = calls
    return w


@pytest.fixture
def gen():
    cfg = CG.GenConfig(seed=7, anchors_per_slot=2, ambiguous=4, out_of_coverage=4, insufficient=4, workers=2)
    return CG.generate(CARD, Registry(), Backend(), writer(), cfg)


def test_slots_come_from_the_card_schema():
    slots = CG.card_slots(CARD, Registry())
    assert {s.key() for s in slots} == {"toy|Group|USES|out|Technique", "toy|Technique|USES|in|Group",
                                        "toy|Group|STUDIES|out|Technique", "toy|Technique|STUDIES|in|Group",
                                        "toy|Technique|MITIGATES|in|Mitigation", "toy|Mitigation|MITIGATES|out|Technique"}


def test_every_answerable_question_carries_its_executed_gold(gen):
    b = Backend()
    ans = [q for q in gen.questions if q["card_gen"]["kind"] == "answerable"]
    assert ans
    for q in ans:
        s = q["card_gen"]["slot"]
        want = sorted(b._nbrs(q["card_gen"]["anchor"], s["rel"], s["direction"], s["target"]))
        assert q["card_gen"]["gold_ids"] == want == q["ex_gold"]["expected"] and want


def test_all_tiers_and_kinds_appear(gen):
    tiers = {q["card_gen"]["tier"] for q in gen.questions if q["card_gen"]["kind"] == "answerable"}
    assert tiers == set(CG.TIERS)
    kinds = {q["card_gen"]["kind"] for q in gen.questions}
    assert kinds == set(CG.KINDS)


def test_splits_share_no_anchor(gen):
    assert CG.split_overlap(gen.questions) == set()
    assert {q["split"] for q in gen.questions} <= {"tuning", "heldout"}


def test_synonym_and_schema_tiers_pass_the_leak_audit(gen):
    assert CG.leak_audit(CARD, gen.questions) == []


def test_a_leaking_synonym_is_retried_then_accepted():
    w = writer(leak=True)
    slot = CG.Slot("toy", "Group", "USES", "out", "Technique")
    r = CG.write_question(w, CARD, slot, "G1", "synonym_relation")
    assert r["ok"] and len(r["attempts"]) == 2 and r["attempts"][0]["problems"] == ["use"]


def test_forbidden_relation_words_include_the_cards_paraphrases():
    f = CG.forbidden_relation_stems(CARD, "USES")
    assert {CG.stem("uses"), CG.stem("employs"), CG.stem("leverages")} <= f
    assert CG.leaked_stems("Which tools does it employ?", f) == ["employ"]


def test_ambiguous_questions_have_differing_readings_and_a_clarification(gen):
    amb = [q for q in gen.questions if q["card_gen"]["kind"] == "ambiguous"]
    assert {q["card_gen"]["ambiguity"] for q in amb} == {"entity", "relation"}
    entity = next(q for q in amb if q["card_gen"]["ambiguity"] == "entity")
    assert set(entity["card_gen"]["readings"]) == {"G2", "G4"} and "Beta Spider" in entity["question"]
    for q in amb:
        r = q["card_gen"]["readings"]
        assert len({tuple(v) for v in r.values()}) >= 2
        assert q["card_gen"]["clarification"]["answer"] in [o["label"] for o in q["card_gen"]["clarification"]["options"]]


def test_insufficient_questions_are_empty_and_diagnosed(gen):
    ins = [q for q in gen.questions if q["card_gen"]["kind"] == "insufficient"]
    assert ins and all(q["card_gen"]["gold_ids"] == [] for q in ins)
    assert all(q["card_gen"]["diagnosis"] in {"relation_absent", "label_excludes_all", "direction_reversed", "no_match"}
               for q in ins)


def test_out_of_coverage_names_its_missing_operator(gen):
    ooc = [q for q in gen.questions if q["card_gen"]["kind"] == "out_of_coverage"]
    assert ooc and {q["card_gen"]["missing_operator"] for q in ooc} <= set(CG.MISSING_OPERATORS)


def test_excluded_anchors_are_never_drawn():
    cfg = CG.GenConfig(seed=7, exclude=frozenset({"G1", "G2"}), workers=2)
    g = CG.generate(CARD, Registry(), Backend(), writer(), cfg)
    assert not any(CG.anchors_of(q) & {"G1", "G2"} for q in g.questions)


def test_banks_are_written_per_dataset_decision_and_split(gen, tmp_path):
    index = CG.write_banks(gen.questions, tmp_path, "card-test", {"generator": "test"})
    assert index and all(v["n"] > 0 and len(v["sha256"]) == 64 for v in index.values())
    held = [b for b in index if b.endswith("-heldout")]
    for b in held:
        body = json.loads((tmp_path / b / "bank.json").read_text())
        assert body["meta"]["sealed"] is True and all(q["split"] == "heldout" for q in body["questions"])


def test_public_ids_exclude_composite_and_stix_ids():
    assert CG.is_public_id("CAPEC-66") and CG.is_public_id("T1059.001")
    assert not CG.is_public_id("capec:attack-pattern:126:alternate-term:1")
    assert not CG.is_public_id("attack-pattern--0a3ead4e-6d47-4ccb-854c-a6a4f9d96b22")


def test_public_ids_are_used_in_questions_and_gold_and_storage_ids_kept_for_fetches():
    cfg = CG.GenConfig(seed=7, workers=2)
    g = CG.generate(CARD, Registry(), Backend(), writer(), cfg, public=lambda i: f"PUB-{i}")
    ans = [q for q in g.questions if q["card_gen"]["kind"] == "answerable"]
    assert ans
    for q in ans:
        cg = q["card_gen"]
        assert cg["anchor"] == f"PUB-{cg['anchor_storage']}"
        assert all(i.startswith("PUB-") for i in cg["gold_ids"])
        if cg["tier"] == "identifier":
            assert cg["anchor"] in q["question"]


def test_a_slot_with_no_edge_anywhere_in_the_store_is_reported_not_used():
    """A card relation the store spells differently reads as empty everywhere: a mismatch, not `insufficient`."""
    class R(Registry):
        FACETS = {**Registry.FACETS, "Mitigation": [*Registry.FACETS["Mitigation"], F("TRAINS", "out", "Group")]}

    cfg = CG.GenConfig(seed=7, ambiguous=0, out_of_coverage=0, insufficient=10, workers=2)
    g = CG.generate(CARD, R(), Backend(), writer(), cfg)
    assert g.absent_slots == ["toy|Mitigation|TRAINS|out|Group"]
    assert not any(q["card_gen"]["slot"] and q["card_gen"]["slot"]["rel"] == "TRAINS" for q in g.questions)
    assert any("no edge anywhere" in n for n in g.notes)


def test_relation_ambiguity_draws_several_anchors_per_pair_and_entity_fills_the_rest():
    cfg = CG.GenConfig(seed=7, anchors_per_slot=2, ambiguous=8, out_of_coverage=0, insufficient=0, workers=2)
    g = CG.generate(CARD, Registry(), Backend(), writer(), cfg)
    amb = Counter(q["card_gen"]["ambiguity"] for q in g.questions if q["card_gen"]["kind"] == "ambiguous")
    assert amb["relation"] > 2            # two label pairs, more than one anchor each
    assert amb["entity"] == 1             # the toy graph shares one name


def test_entity_ambiguity_takes_the_whole_budget_when_the_card_has_no_relation_pair():
    class R(Registry):
        FACETS = {"Group": [F("USES", "out", "Technique")], "Technique": [F("USES", "in", "Group")]}

    nodes = {**Backend.NODES, "Group": {**Backend.NODES["Group"], "G5": "Alpha Bear"}}
    edges = [*Backend.EDGES, ("G5", "USES", "T3")]

    class B(Backend):
        NODES, EDGES = nodes, edges

    cfg = CG.GenConfig(seed=7, ambiguous=2, out_of_coverage=0, insufficient=0, workers=2)
    g = CG.generate(CARD, R(), B(), writer(), cfg)
    amb = [q for q in g.questions if q["card_gen"]["kind"] == "ambiguous"]
    assert {q["card_gen"]["ambiguity"] for q in amb} <= {"entity"}
    assert len(amb) == 2                  # both shared names (G1/G5, G2/G4) sit within one split each


def test_schema_tier_rejects_id_format_hints_copied_from_the_label_description():
    assert CG.format_hints("Which more specific variants (T-ID.NNN) does S0001 use?") == ["NNN", "T-ID"]
    assert CG.format_hints("Which named v19 approaches (DET-IDs) target T1546.016?") == ["DET-IDs", "v19"]
    assert CG.format_hints("Which IPv6 attack methods does G0016 use?") == []
    q = {"id": "x", "question": "Which variants (T-ID.NNN) does G1 use?",
         "card_gen": {"tier": "paraphrased_schema", "slot": {"rel": "USES", "target": "Technique"}}}
    assert CG.leak_audit(CARD, [q]) == [{"id": "x", "tier": "paraphrased_schema", "leaks": ["NNN", "T-ID"]}]
