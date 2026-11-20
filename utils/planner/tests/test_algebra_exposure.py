"""Phase G of Era 2 Step 9: the operator algebra exposed to the typed planner.

- **Off means unchanged.** With both switches off, the planner's full prompt and
  tool specs hash to the values recorded from the reference commit ea7a7e59
  (computed from that tree, before any Phase G edit, with :func:`_prompt_hash`
  exactly as written here), and an operator kind is refused as before.
- **Each new kind** is in the prompt only when its switch is on; ``check_step``
  accepts a valid step and refuses invalid ones with a teaching envelope.
- **Today's kinds** are validated by the algebra when CORE is on: the two
  card-invalid drafts EXP-2026-11-021 found are refused then, and only then.
- **The builder's dropped filter** (amendment 4): kept, and so matching
  nothing, when CORE is on; dropped exactly as before when off.

No model and no store: the catalogs come from the committed source cards and the
entity index from ``data/graphs``.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(
    not (REPO / "data" / "source_cards" / "attack.json").exists()
    or not (REPO / "data" / "graphs" / "attack" / "canonical" / "nodes.jsonl").exists(),
    reason="needs the ATT&CK and CAPEC source cards and canonical graphs under data/",
)

#: sha256 of the full planner prompt (system + user messages) and the tool specs,
#: per card set and mode, recorded from ea7a7e59 before Phase G (2026-11-20).
OFF_HASHES = {
    "attack:lazy": "962fdd72ea86b19639f8a23363a6c52f10921176ad65f50988acf72be356a2ea",
    "attack:full": "c8cff463bd9bffa4ceed3eb30cbf079895c1773c32bbd1f6375d97dc65317555",
    "capec:lazy": "51f8266f7411ae779a7dbbb3121f2de20df52f519ef190a5b7ea1a09b9d89eb3",
    "capec:full": "7e9bc622beee309d4388cea7ee9b521e78e66788dfad588d8702b307e02b3ea5",
    "attack+capec:lazy": "542a3c902be6717e9b80b1279d690452d3df8dfebe52b3a78a6ca8863898080c",
    "attack+capec:full": "7e83f6184e4971b2b545ffb410098fa395cd877cc5d87e7f59b89a00d5b58fdd",
}
SWITCHES = ("ARIADNE_ALGEBRA_CORE", "ARIADNE_ALGEBRA_EXTENDED")


@pytest.fixture(scope="module")
def cards():
    from utils.config import load_env
    from utils.planner.cards import load_source_cards

    load_env()
    return load_source_cards(REPO / "data")


@pytest.fixture
def off(monkeypatch):
    for k in SWITCHES:
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def core(monkeypatch):
    monkeypatch.setenv("ARIADNE_ALGEBRA_CORE", "1")
    monkeypatch.delenv("ARIADNE_ALGEBRA_EXTENDED", raising=False)


@pytest.fixture
def extended(monkeypatch):
    monkeypatch.setenv("ARIADNE_ALGEBRA_CORE", "1")
    monkeypatch.setenv("ARIADNE_ALGEBRA_EXTENDED", "1")


def _prompt_hashes(cards) -> dict[str, str]:
    from utils.planner import typed as T

    out = {}
    for names in (("attack",), ("capec",), ("attack", "capec")):
        cats = T.catalogs_for({n: cards[n] for n in names})
        for mode in T.MODES:
            blob = json.dumps({"messages": T.build_messages("QUESTION TEXT", cats, mode),
                               "tools": T.tool_specs(cats)}, sort_keys=True, ensure_ascii=False)
            out["+".join(names) + ":" + mode] = hashlib.sha256(blob.encode()).hexdigest()
    return out


def _check(cards, steps, request=""):
    from utils.planner.typed import PlanContext, catalogs_for, check_plan

    with tempfile.TemporaryDirectory() as d:
        ctx = PlanContext(cards, catalogs_for(cards), Path(d), request=request)
        try:
            checks, _ = check_plan({"steps": steps}, ctx)
        finally:
            ctx.close()
    return checks


# --------------------------------------------------------------------------- #
# Off means unchanged
# --------------------------------------------------------------------------- #


def test_off_prompt_and_tool_specs_hash_equal_to_the_reference(cards, off):
    assert _prompt_hashes(cards) == OFF_HASHES


def test_off_an_operator_kind_is_refused_with_todays_kinds(cards, off):
    from utils.planner.typed import STEP_KINDS

    c = _check(cards, [{"id": "q1", "graph": "attack", "kind": "aggregate", "anchor_label": "Technique",
                        "fn": "count"}])[0]
    assert not c.ok and c.refusals[0]["code"] == "invalid_request"
    assert "fix" in c.refusals[0] and all(k in c.refusals[0]["fix"] for k in STEP_KINDS)
    assert "aggregate" not in c.refusals[0]["fix"]


def test_switches_change_the_prompt(cards, core):
    assert _prompt_hashes(cards) != OFF_HASHES


# --------------------------------------------------------------------------- #
# The prompt mentions each kind only when its switch is on
# --------------------------------------------------------------------------- #

CORE = ("filter", "typescan", "aggregate", "rank", "verify", "groupby", "union", "absence")
EXT = ("reach", "shortest")


def _system(cards):
    from utils.planner import typed as T

    return T.build_messages("Q", T.catalogs_for(cards), "lazy")[0]["content"]


@pytest.mark.parametrize("kind", CORE + EXT)
def test_prompt_mentions_a_kind_only_when_its_switch_is_on(cards, monkeypatch, kind):
    line = f'- "{kind}":'
    for k in SWITCHES:
        monkeypatch.delenv(k, raising=False)
    assert line not in _system(cards)
    monkeypatch.setenv("ARIADNE_ALGEBRA_CORE", "1")
    assert (line in _system(cards)) == (kind in CORE)
    monkeypatch.setenv("ARIADNE_ALGEBRA_EXTENDED", "1")
    assert line in _system(cards)
    monkeypatch.delenv("ARIADNE_ALGEBRA_CORE")
    assert line not in _system(cards)  # EXTENDED alone exposes nothing


def test_time_ops_are_offered_only_with_extended(cards, monkeypatch):
    monkeypatch.setenv("ARIADNE_ALGEBRA_CORE", "1")
    assert "before" not in _system(cards).split("OPERATOR STEPS")[1]
    monkeypatch.setenv("ARIADNE_ALGEBRA_EXTENDED", "1")
    assert "before" in _system(cards).split("OPERATOR STEPS")[1]


def test_the_operator_text_names_no_graph(cards, extended):
    from utils.planner import typed as T

    text = _system(cards)[len(T.SYSTEM_PROMPT):]
    for name in list(cards) + [lab for c in T.catalogs_for(cards).values() for lab in c.labels()]:
        assert f'"{name}"' not in text and f" {name} " not in text


def test_the_lazy_prompt_lists_properties_with_their_types_when_on(cards, core):
    from utils.planner import typed as T

    user = T.build_messages("Q", T.catalogs_for(cards), "lazy")[1]["content"]
    assert "PROPERTIES (for conditions" in user and "x_mitre_platforms (list)" in user
    full = T.build_messages("Q", T.catalogs_for(cards), "full")[1]["content"]
    assert "PROPERTIES (for conditions" not in full  # the full card lists them already


# --------------------------------------------------------------------------- #
# check_step: each kind accepted when valid, refused with a teaching envelope
# --------------------------------------------------------------------------- #

USES_T = [{"relation": "USES", "direction": "out", "target_label": "Technique"}]
VALID = {
    "filter": {"graph": "attack", "anchor": {"id": "G0007"}, "path": USES_T,
               "where": [{"property": "x_mitre_platforms", "op": "contains", "value": "Linux"}]},
    "typescan": {"graph": "attack", "anchor_label": "Technique",
                 "where": [{"property": "x_mitre_platforms", "op": "contains", "value": "Linux"}]},
    "aggregate": {"graph": "attack", "anchor": {"id": "G0007"}, "path": USES_T, "fn": "count"},
    "rank": {"graph": "attack", "anchor_label": "Group", "k": 3, "by_path": USES_T},
    "verify": {"graph": "attack", "anchor": {"id": "G0007"}, "other": {"id": "T1047"}},
    "groupby": {"graph": "capec", "anchor_label": "AttackPattern", "fn": "count",
                "path": [{"relation": "EXPLOITS_WEAKNESS", "direction": "out", "target_label": "Weakness"}],
                "having": {"op": ">", "value": 10}},
    "union": {"graph": "attack", "parts": [{"anchor": {"id": "G0007"}, "path": USES_T},
                                           {"anchor": {"id": "G0016"}, "path": USES_T}]},
    "absence": {"graph": "attack", "anchor_label": "Technique",
                "lacks": {"relation": "MITIGATES", "direction": "in", "target_label": "Mitigation"}},
    "reach": {"graph": "capec", "anchor": {"id": "CAPEC-66"},
              "relations": [{"relation": "ChildOf", "direction": "out"}], "depth": 4},
    "shortest": {"graph": "capec", "anchor": {"id": "CAPEC-66"}, "other": {"id": "CAPEC-248"}},
}
#: One invalid step per kind, and a word the refusal must teach with.
INVALID = {
    "filter": ({"graph": "attack", "anchor": {"id": "G0007"}, "path": USES_T,
                "where": [{"property": "x_mitre_platforms", "op": "starts_with", "value": "Lin"}]},
               "contains"),
    "typescan": ({"graph": "attack", "anchor_label": "Technique",
                  "where": [{"property": "Abstraction", "op": "=", "value": "Meta"}]}, "x_mitre_platforms"),
    "aggregate": ({"graph": "attack", "anchor_label": "Technique", "fn": "sum", "property": "name"},
                  "numeric"),
    "rank": ({"graph": "attack", "anchor_label": "Group", "k": 3,
              "by_path": [{"relation": "MITIGATES", "direction": "out"}]}, "joins none"),
    "verify": ({"graph": "attack", "anchor": {"id": "G0007"}, "other": {"id": "T1047"},
                "relation": "MITIGATES"}, "never joins"),
    "groupby": ({"graph": "capec", "anchor_label": "AttackPattern", "fn": "avg", "property": "name",
                 "path": [{"relation": "EXPLOITS_WEAKNESS", "direction": "out", "target_label": "Weakness"}]},
                "numeric"),
    "union": ({"graph": "attack", "parts": [{"anchor": {"id": "G0007"}, "path": USES_T}]}, "two or more"),
    "absence": ({"graph": "attack", "anchor_label": "Technique",
                 "lacks": {"relation": "MITIGATES", "direction": "out", "target_label": "Mitigation"}},
                "joins none"),
    "reach": ({"graph": "capec", "anchor": {"id": "CAPEC-66"}, "depth": 11}, "depth must be"),
    "shortest": ({"graph": "capec", "anchor": {"id": "CAPEC-66"}, "other": {"id": "CAPEC-66"}}, "must differ"),
}


@pytest.mark.parametrize("kind", CORE + EXT)
def test_check_step_accepts_a_valid_step(cards, extended, kind):
    from utils.specialists.algebra.ir import from_dict
    from utils.specialists.algebra.validate import check

    c = _check(cards, [{"id": "q1", "kind": kind, **VALID[kind]}])[0]
    assert c.ok, c.refusals
    d = c.step.to_dict()
    assert d["kind"] == "algebra" and d["algebra"]["op"] == kind
    from utils.planner.typed import catalogs_for

    check(from_dict(d["algebra"]["ir"]), catalogs_for(cards)[c.graph].model)  # still valid as stored


@pytest.mark.parametrize("kind", CORE + EXT)
def test_check_step_refuses_an_invalid_step_with_a_teaching_message(cards, extended, kind):
    raw, word = INVALID[kind]
    c = _check(cards, [{"id": "q1", "kind": kind, **raw}])[0]
    assert not c.ok
    env = c.refusals[0]
    assert env["ok"] is False and env["code"] in ("invalid_request", "not_in_card") and env["fix"]
    assert word in (env["detail"] + " " + env["fix"]), env


@pytest.mark.parametrize("kind", EXT)
def test_extended_kinds_are_refused_with_core_alone(cards, core, kind):
    c = _check(cards, [{"id": "q1", "kind": kind, **VALID[kind]}])[0]
    assert not c.ok and "not a step kind" in c.refusals[0]["detail"]


def test_a_time_op_is_refused_with_core_alone_and_accepted_with_extended(cards, monkeypatch):
    step = {"id": "q1", "graph": "attack", "kind": "typescan", "anchor_label": "Technique",
            "where": [{"property": "created", "op": "before", "value": "2018-01-01"}]}
    monkeypatch.setenv("ARIADNE_ALGEBRA_CORE", "1")
    c = _check(cards, [step])[0]
    assert not c.ok and "starts_with" in c.refusals[0]["fix"]
    monkeypatch.setenv("ARIADNE_ALGEBRA_EXTENDED", "1")
    assert _check(cards, [step])[0].ok


def test_from_step_chains_to_an_earlier_step_and_becomes_a_join_free_dependency(cards, core):
    from utils.planner.typed import to_plan

    checks = _check(cards, [
        {"id": "q1", "kind": "expand", "graph": "attack", "anchor": {"id": "G0007"},
         "path": [{"relation": "USES", "direction": "out", "target_label": "Software"}]},
        {"id": "q2", "kind": "filter", "graph": "attack", "from_step": "q1",
         "where": [{"property": "x_mitre_platforms", "op": "contains", "value": "Linux"}]},
    ])
    assert all(c.ok for c in checks), [c.refusals for c in checks]
    ir = checks[1].step.to_dict()["algebra"]["ir"]
    assert ir["of"]["of"] == {"@": "FromStep", "step": "q1", "labels": ["Software"]}
    plan = to_plan("Q", checks, {}, cards, [], "lazy")
    assert plan.sub_questions[1].step["from_step"] == "q1" and not plan.joins
    from utils.specialists.federation import dependency_map, unanchored_typed_step

    assert dependency_map(plan) == {"q2": ("q1",)}
    assert not unanchored_typed_step(plan.sub_questions[1])


def test_an_anchor_name_is_resolved_like_todays_steps(cards, core):
    c = _check(cards, [{"id": "q1", "graph": "attack", "kind": "aggregate",
                        "anchor": {"name": "APT28", "label": "Group"}, "path": USES_T, "fn": "count"}])[0]
    assert c.ok, c.refusals
    assert c.step.anchor_ids == ("G0007",)


def test_the_step_round_trips_through_the_sub_question(cards, core):
    from utils.planner.typed import to_plan
    from utils.specialists.contracts import SpecialistTask

    checks = _check(cards, [{"id": "q1", "kind": "aggregate", **VALID["aggregate"]}])
    plan = to_plan("Q", checks, {}, cards, [], "lazy")
    task = SpecialistTask.from_sub_question(plan.sub_questions[0])
    assert task.signals.step.to_dict() == checks[0].step.to_dict()
    assert task.seed_ids == ("G0007",)
    assert "Group" in plan.sub_questions[0].entities and "USES" in plan.sub_questions[0].entities


# --------------------------------------------------------------------------- #
# Today's kinds through the algebra validator (item 3)
# --------------------------------------------------------------------------- #

CARD_INVALID = [
    {"id": "q1", "graph": "attack", "kind": "expand", "anchor": {"id": "G0001"}, "anchor_label": "Group",
     "path": [{"relation": "USES", "direction": "out"},
              {"relation": "HAS_TACTIC", "direction": "out", "target_label": "Tactic"}]},
    {"id": "q1", "graph": "attack", "kind": "expand", "anchor": {"id": "M1049"}, "anchor_label": "Mitigation",
     "path": [{"relation": "MITIGATES", "direction": "out"},
              {"relation": "DETECTS", "direction": "in", "target_label": "Analytic"}]},
]


@pytest.mark.parametrize("raw", CARD_INVALID)
def test_todays_card_invalid_drafts_are_refused_only_with_core(cards, monkeypatch, raw):
    for k in SWITCHES:
        monkeypatch.delenv(k, raising=False)
    assert _check(cards, [raw])[0].ok
    monkeypatch.setenv("ARIADNE_ALGEBRA_CORE", "1")
    c = _check(cards, [raw])[0]
    assert not c.ok and ("joins none" in c.refusals[0]["detail"] or "reaches" in c.refusals[0]["detail"])


def test_a_valid_today_step_still_passes_with_core(cards, core):
    c = _check(cards, [{"id": "q1", "graph": "attack", "kind": "expand", "anchor": {"id": "G0007"},
                        "path": USES_T, "filter": {"property": "x_mitre_platforms", "value": "Linux"}}])[0]
    assert c.ok, c.refusals
    assert c.step.algebra is None and c.step.kind == "expand"


# --------------------------------------------------------------------------- #
# The builder's dropped filter (item 4, amendment 4)
# --------------------------------------------------------------------------- #

def _compile(cards, source, step_dict):
    from utils.specialists.contracts import SpecialistTask
    from utils.specialists.cypher.builder import CypherQueryBuilder
    from utils.specialists.gremlin.builder import GremlinQueryBuilder
    from utils.specialists.resolve import resolve
    from utils.specialists.signals import TypedStep, step_signals

    step = TypedStep.from_dict(step_dict)
    card = cards[source]
    task = SpecialistTask(sub_question_id="q1", source=source, text="", entities=tuple(step.entities()),
                          limits={"max_traversal_depth": 3, "max_result_rows": 1000, "query_timeout_ms": 5000},
                          seed_ids=tuple(step.anchor_ids), signals=step_signals(step))
    builder = GremlinQueryBuilder() if card.runtime_backend == "gremlin" else CypherQueryBuilder()
    return builder.build(resolve(task, card), None)


def _non_native_steps():
    """Recorded typed steps whose filter property the store does not hold natively (one per graph)."""
    from utils.specialists.schema import get_registry

    reg = get_registry()
    out = {}
    for source, label, hops in (
        ("capec", "AttackPattern", [{"relation": "HAS_EXECUTION_STEP", "direction": "out",
                                     "target_label": "ExecutionStep"}]),
        ("attack", "Group", [{"relation": "USES", "direction": "out", "target_label": "Technique"}]),
    ):
        target = hops[-1]["target_label"]
        props = sorted(reg.dataset(source).label_value_vocabulary.get(target, {}) or []) if reg.dataset(source) else []
        for prop in ["name", "description", "x_mitre_version", *props]:
            try:
                native = reg.is_native_property(target, prop, dataset=source)
                is_list = reg.is_list_property(target, prop, dataset=source)
            except Exception:  # noqa: BLE001
                continue
            if not native and not is_list:
                ids = {"capec": ["CAPEC-66"], "attack": ["G0007"]}[source]
                out[source] = {"anchor_ids": ids, "anchor_label": label, "depth": 1, "kind": "expand",
                               "hops": hops, "filter": {"property": prop, "value": "x"}}
                break
    return out


def test_a_non_native_filter_is_dropped_when_off_and_kept_when_core_is_on(cards, monkeypatch):
    steps = _non_native_steps()
    if not steps:
        pytest.skip("no non-native property on the probed labels")
    for source, step in steps.items():
        for k in SWITCHES:
            monkeypatch.delenv(k, raising=False)
        off = _compile(cards, source, step)
        monkeypatch.setenv("ARIADNE_ALGEBRA_CORE", "1")
        on = _compile(cards, source, step)
        assert off.template == on.template == "typed_step"
        assert "filter" not in off.meta and "filterValue" not in off.params
        assert "filter" in on.meta and on.params.get("filterValue") == "x"


# --------------------------------------------------------------------------- #
# A today's-kind step starting from an operator step on the same graph
# --------------------------------------------------------------------------- #

D6 = [
    {"id": "q1", "graph": "capec", "kind": "typescan", "anchor_label": "TaxonomyEntry",
     "where": [{"property": "taxonomy_name", "op": "=", "value": "ATTACK"},
               {"property": "entry_id", "op": "=", "value": "1491"}]},
    {"id": "q2", "graph": "capec", "kind": "expand", "from_step": "q1",
     "path": [{"relation": "MAPS_TO", "direction": "in", "target_label": "AttackPattern"},
              {"relation": "MAPS_TO", "direction": "out", "target_label": "TaxonomyEntry"}]},
]


def test_an_expand_from_an_operator_step_on_the_same_graph_walks_from_it(cards, core):
    from utils.planner.typed import to_plan

    checks = _check(cards, D6)
    assert all(c.ok for c in checks), [c.refusals for c in checks]
    d = checks[1].step.to_dict()
    assert d["kind"] == "algebra" and d["algebra"]["op"] == "expand"
    walk = d["algebra"]["ir"]["walk"]
    assert d["algebra"]["ir"]["@"] == "Expand"
    assert walk["start"] == {"@": "FromStep", "step": "q1", "labels": ["TaxonomyEntry"]}
    assert [h["relation"] for h in walk["hops"]] == ["MAPS_TO", "MAPS_TO"]
    assert d["algebra"]["labels"] == ["AttackPattern", "TaxonomyEntry"]
    plan = to_plan("Q", checks, {}, cards, [], "lazy")
    from utils.specialists.federation import dependency_map

    assert dependency_map(plan) == {"q2": ("q1",)} and not plan.joins


def test_a_count_from_an_operator_step_is_a_count_of_the_walk(cards, core):
    checks = _check(cards, [D6[0], {**D6[1], "kind": "count"}])
    assert checks[1].ok and checks[1].step.to_dict()["algebra"]["ir"]["@"] == "Count"


@pytest.mark.parametrize("second,word", [
    ({"id": "q2", "graph": "capec", "kind": "common", "from_step": "q1", "anchor": {"id": ["CAPEC-66", "CAPEC-1"]}},
     "operator step"),
    ({"id": "q2", "graph": "capec", "kind": "expand", "from_step": "q1",
      "path": [{"relation": "HAS_SKILL", "direction": "out"}]}, "not a relation"),
])
def test_refusals_from_an_operator_producer_never_ask_to_extend_its_path(cards, core, second, word):
    c = _check(cards, [D6[0], second])[1]
    assert not c.ok
    text = c.refusals[0]["detail"] + " " + c.refusals[0]["fix"]
    assert word in text and "to the path of step" not in text


def test_a_step_from_a_scalar_operator_step_is_refused_with_why(cards, core):
    first = {"id": "q1", "graph": "capec", "kind": "aggregate", "anchor_label": "TaxonomyEntry", "fn": "count"}
    c = _check(cards, [first, D6[1]])[1]
    assert not c.ok and "returns a value" in c.refusals[0]["detail"]


@pytest.mark.parametrize("switch", [False, True])
def test_a_same_graph_from_step_after_todays_filtered_step_keeps_todays_refusal(cards, monkeypatch, switch):
    for k in SWITCHES:
        monkeypatch.delenv(k, raising=False)
    if switch:
        monkeypatch.setenv("ARIADNE_ALGEBRA_CORE", "1")
    checks = _check(cards, [
        {"id": "q1", "graph": "attack", "kind": "expand", "anchor": {"id": "G0007"}, "path": USES_T,
         "filter": {"property": "x_mitre_platforms", "value": "Linux"}},
        {"id": "q2", "graph": "attack", "kind": "expand", "from_step": "q1",
         "path": [{"relation": "MITIGATES", "direction": "in", "target_label": "Mitigation"}]},
    ])
    assert checks[0].ok and not checks[1].ok
    assert "add this step's hops to the path of step q1" in checks[1].refusals[0]["fix"]
