"""E3 (EXP-2026-11-015): 1,000 seeded invalid tool calls; every refusal names a valid option.

The calls are drawn (seed 20261118) over the catalogs of the two source cards,
from these mutations of otherwise valid calls: a relation the label does not
have; the wrong direction; an unknown relation, label or property; a property
of another label; an operator the property's type does not take; a value of
the wrong type; missing arguments; an out-of-range or non-integer depth; depth
on a relation that does not repeat; an unknown handle; an unknown set operator
or aggregate; an unknown argument; a k below 1.

Each case carries the set of options that would have been valid. A case passes
when the call is refused (``ok: false`` with a known code) and its ``fix`` names
at least one of those options as a whole word. Validation runs before any store
is touched, so no store is connected.
"""

from __future__ import annotations

import random
import re
import string
from collections import Counter
from pathlib import Path

import pytest

from utils.agent.catalog import AGG_FNS, catalog_for
from utils.agent.coerce import Ambiguous, NoMatch, coerce_name
from utils.agent.errors import CODES
from utils.agent.handles import SET_OPS, HandleStore
from utils.agent.tools import Tools

SEED = 20261118
N = 1000
REPO = Path(__file__).resolve().parents[3]


def _named(fix: str, option: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9_])" + re.escape(str(option)) + r"(?![A-Za-z0-9_])", fix) is not None


def _gibberish(rng: random.Random, options: list[str]) -> str:
    """A name no option is a near miss of."""
    while True:
        s = "".join(rng.choice(string.ascii_lowercase) for _ in range(rng.randint(7, 12)))
        try:
            coerce_name(s, options, "x")
        except NoMatch:
            return s
        except Ambiguous:
            continue


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    from utils.planner.cards import load_source_cards

    views = load_source_cards(REPO / "data")
    out = {}
    for ds in sorted(views):
        cat = catalog_for(views[ds])
        store = HandleStore(tmp_path_factory.mktemp(ds) / "h.db", "fuzz")
        handles = {lab: store.put(lab, [f"x-{lab}-1", f"x-{lab}-2"]).handle for lab in cat.labels()}
        out[ds] = (cat, Tools(cat, None, store), handles)
    return out


def _cases(world: dict) -> list[tuple[str, str, dict, set[str]]]:
    rng = random.Random(SEED)
    cases: list[tuple[str, str, dict, set[str]]] = []
    kinds = ["bad_relation_for_label", "wrong_direction", "unknown_relation", "bad_to_label", "unknown_to_label",
             "depth_out_of_range", "depth_not_repeating", "depth_wrong_type", "missing_relation", "missing_from",
             "missing_text", "unknown_property", "property_of_other_label", "op_wrong_for_type",
             "value_wrong_type", "unknown_label_resolve", "unknown_describe", "bad_set_op", "unknown_handle",
             "bad_agg_fn", "agg_needs_numeric", "unknown_argument", "bad_k", "missing_property"]
    attempts = 0
    while len(cases) < N:
        attempts += 1
        assert attempts < 50 * N, "case generator stalled"
        ds = rng.choice(sorted(world))
        cat, tools, handles = world[ds]
        labs = cat.labels()
        lab = rng.choice(labs)
        h = handles[lab]
        here = cat.options(lab)
        rels_here = sorted({o.relation for o in here})
        props = sorted(cat.label_properties(lab))
        kind = rng.choice(kinds)
        args: dict
        valid: set[str]
        if kind == "bad_relation_for_label":
            others = sorted(set(cat.relations()) - set(rels_here))
            if not others or not rels_here:
                continue
            args, valid = {"from": h, "relation": rng.choice(others)}, set(rels_here)
            tool = "expand"
        elif kind == "wrong_direction":
            singles = [o for o in here if len(cat.options(lab, o.relation)) and
                       {x.direction for x in cat.options(lab, o.relation)} == {o.direction}]
            if not singles:
                continue
            o = rng.choice(singles)
            args = {"from": h, "relation": o.relation, "direction": "in" if o.direction == "out" else "out"}
            valid, tool = {o.direction}, "expand"
        elif kind == "unknown_relation":
            if not rels_here:
                continue
            args = {"from": h, "relation": _gibberish(rng, cat.relations())}
            valid, tool = set(rels_here), "expand"
        elif kind in ("bad_to_label", "unknown_to_label"):
            if not here:
                continue
            o = rng.choice(here)
            ends = sorted({x.target for x in cat.options(lab, o.relation, o.direction)})
            if kind == "bad_to_label":
                wrong = sorted(set(labs) - set(ends))
                if not wrong:
                    continue
                to = rng.choice(wrong)
            else:
                to = _gibberish(rng, labs)
            args = {"from": h, "relation": o.relation, "direction": o.direction, "to_label": to}
            valid, tool = set(ends), "expand"
        elif kind == "depth_out_of_range":
            if not here:
                continue
            o = rng.choice(here)
            top = cat.model.max_depth if o.repeating else 1
            args = {"from": h, "relation": o.relation, "direction": o.direction, "to_label": o.target,
                    "depth": rng.choice([0, -1, cat.model.max_depth + 1, cat.model.max_depth + 7, 100])}
            valid, tool = {str(i) for i in range(1, top + 1)}, "expand"
        elif kind == "depth_not_repeating":
            flat = [o for o in here if not o.repeating]
            if not flat:
                continue
            o = rng.choice(flat)
            args = {"from": h, "relation": o.relation, "direction": o.direction, "depth": rng.randint(2, 3)}
            valid, tool = {"1"}, "expand"
        elif kind == "depth_wrong_type":
            if not here:
                continue
            o = rng.choice(here)
            top = cat.model.max_depth if o.repeating else 1
            args = {"from": h, "relation": o.relation, "direction": o.direction,
                    "depth": rng.choice(["deep", 2.5, True, None, [2], {"n": 2}, "two"])}
            if args["depth"] is None:
                args["depth"] = "none"
            valid, tool = {str(i) for i in range(1, top + 1)}, "expand"
        elif kind == "missing_relation":
            if not rels_here:
                continue
            args, valid, tool = {"from": h}, set(rels_here), "expand"
        elif kind == "missing_from":
            if not here:
                continue
            o = rng.choice(here)
            args = {"relation": o.relation, "direction": o.direction}
            valid, tool = set(handles.values()), "expand"
        elif kind == "missing_text":
            tool = rng.choice(["find_schema", "resolve_entity"])
            args = rng.choice([{}, {"text": ""}, {"text": "   "}, {"k": 3} if tool == "find_schema" else {"label": lab}])
            valid = {"text"}
        elif kind == "missing_property":
            if not props:
                continue
            tool = rng.choice(["filter", "group", "rank"])
            args = {"set": h, "op": "=", "value": "x"} if tool == "filter" else {"set": h, "k": 3}
            if tool == "group":
                args = {"set": h}
            valid = set(props)
        elif kind in ("unknown_property", "property_of_other_label"):
            if not props:
                continue
            if kind == "unknown_property":
                p = _gibberish(rng, cat.properties())
            else:
                others = sorted(set(cat.properties()) - set(props))
                if not others:
                    continue
                p = rng.choice(others)
            tool = rng.choice(["filter", "group", "rank"])
            args = {"set": h, "property": p, "op": "=", "value": "x"} if tool == "filter" else \
                {"set": h, "by": p} if tool == "group" else {"set": h, "by": p, "k": 3}
            valid = set(props)
        elif kind == "op_wrong_for_type":
            if not props:
                continue
            p = cat.label_properties(lab)[rng.choice(props)]
            bad = sorted({"<", ">", "<=", ">=", "contains", "not_contains", "starts_with", "like", "~="} - set(p.ops))
            args = {"set": h, "property": p.name, "op": rng.choice(bad), "value": "x"}
            valid, tool = set(p.ops), "filter"
        elif kind == "value_wrong_type":
            typed = [cat.label_properties(lab)[x] for x in props]
            if not typed:
                continue
            p = rng.choice(typed)
            bad = {"boolean": ["maybe", {"a": 1}, [True], 3.5, "yes please"],
                   "string": [{"a": 1}, [1, 2], None, True],
                   "list": [{"a": 1}, None, True]}.get(p.vtype, [{"a": 1}])
            v = rng.choice(bad)
            if v is None:
                v = {"none": None}
            args = {"set": h, "property": p.name, "op": p.ops[0], "value": v}
            valid, tool = {p.vtype}, "filter"
        elif kind == "unknown_label_resolve":
            args = {"text": "some name", "label": _gibberish(rng, labs)}
            valid, tool = set(labs), "resolve_entity"
        elif kind == "unknown_describe":
            target = _gibberish(rng, labs + cat.relations())
            args = {"target": rng.choice([target, 17, {"x": 1}, ""]) if rng.random() < 0.3 else target}
            valid, tool = set(labs) | set(cat.relations()), "describe"
        elif kind == "bad_set_op":
            args = {"op": rng.choice(["xor", "join", "difference", "merge", "and", "plus"]), "a": h,
                    "b": handles[rng.choice(labs)]}
            valid, tool = set(SET_OPS), "set_op"
        elif kind == "unknown_handle":
            tool = rng.choice(["count", "set_op", "expand", "filter"])
            bogus = rng.choice(["set:999", "set:0", "x-none-1", "handle1", "set-999", "set:", "Set 404"])
            args = {"set": bogus} if tool in ("count", "filter") else \
                {"op": "union", "a": bogus, "b": h} if tool == "set_op" else \
                {"from": bogus, "relation": rels_here[0] if rels_here else cat.relations()[0]}
            if tool == "filter":
                args |= {"property": "name", "op": "=", "value": "x"}
            if tool == "expand" and not bogus.lower().startswith("set"):
                continue  # a bare id is a valid seed list; the store decides
            valid = set(handles.values())
        elif kind == "bad_agg_fn":
            args = {"set": h, "fn": rng.choice(["median", "mean", "total", "stddev", "mode"]), "property": "name"}
            valid, tool = set(AGG_FNS), "aggregate"
        elif kind == "agg_needs_numeric":
            nonnum = [x for x in props if cat.label_properties(lab)[x].vtype not in ("integer", "number",
                                                                                    "number_text")]
            if not nonnum:
                continue
            args = {"set": h, "fn": rng.choice(["sum", "avg"]), "property": rng.choice(nonnum)}
            numeric = sorted(x for x in props if x not in nonnum)
            valid, tool = set(numeric) | {"count"}, "aggregate"
        elif kind == "unknown_argument":
            tool = rng.choice(["expand", "count", "find_schema", "describe"])
            base = {"expand": {"from": h, "relation": rels_here[0] if rels_here else "X"}, "count": {"set": h},
                    "find_schema": {"text": "uses"}, "describe": {"target": lab}}[tool]
            args = base | {_gibberish(rng, ["from", "relation", "direction", "to_label", "depth", "set", "text",
                                            "k", "target"]): 1}
            valid = {"from", "relation", "direction", "to_label", "depth", "set", "text", "k", "target"}
        elif kind == "bad_k":
            if not props:
                continue
            args = {"set": h, "by": "name" if "name" in props else props[0], "k": rng.choice([0, -3, "many", 2.5])}
            valid, tool = {"1", "5", "10"}, "rank"
        else:  # pragma: no cover
            raise AssertionError(kind)
        cases.append((ds, tool, args, valid | {"__kind__" + kind}))
    return cases


def test_one_thousand_invalid_calls_are_refused_with_a_fix_naming_a_valid_option(world):
    cases = _cases(world)
    assert len(cases) == N
    passed, failures, codes, kinds = 0, [], Counter(), Counter()
    for ds, tool, args, valid in cases:
        kind = next(v for v in valid if v.startswith("__kind__"))[8:]
        opts = {v for v in valid if not v.startswith("__kind__")}
        kinds[kind] += 1
        out = world[ds][1].call(tool, args)
        ok = (out.get("ok") is False and out.get("code") in CODES and bool(out.get("fix"))
              and any(_named(out["fix"], o) for o in opts))
        codes[out.get("code")] += 1
        if ok:
            passed += 1
        else:
            failures.append((ds, kind, tool, args, out))
    print(f"\nE3: {passed}/{N} refused with a fix naming a valid option; codes {dict(codes)}")
    print("E3 kinds:", dict(sorted(kinds.items())))
    for f in failures[:10]:
        print("FAIL", f)
    assert passed == N
