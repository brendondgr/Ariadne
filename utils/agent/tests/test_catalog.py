"""E2 (EXP-2026-11-015): the catalog is generated from every loaded card, with no per-graph code.

Three checks, each over every card this machine can produce (``catalog.load_all``):

1. every tool's parameters validate as a JSON Schema (Draft 2020-12) meta-schema;
2. every enum equals the card's own set (read from the card independently of the adapter);
3. no label, relation or graph name of any card appears in the catalog/tool code.

``jsonschema`` is not a project dependency. The check imports it when present;
otherwise it runs the same check in a throwaway environment from uv's offline
cache (``uv run --offline --no-project --with jsonschema``); if neither works it
skips and says why.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from utils.agent.catalog import ALL_OPS, DIRECTIONS, TOOL_NAMES, Catalog, from_killtest_card, load_all

AGENT = Path(__file__).resolve().parents[1]
REPO = AGENT.parents[1]
NEW_FILES = ("catalog.py", "coerce.py", "errors.py", "tools.py")
#: No file in utils/agent/ may name a card's label or relation (E2). The Step 5 prose
#: hits (two docstring examples, one message word) were reworded on 2026-11-18.
PREEXISTING: dict[str, set[str]] = {}
SAVED_CARDS = sorted((REPO / "logs" / "killtests-2026-11").glob("*/cards-v3/card-*.json"))


@pytest.fixture(scope="module")
def loaded() -> tuple[dict[str, Catalog], dict[str, str]]:
    cats, skipped = load_all(REPO / "data")
    print("\nE2 generated:", sorted(cats))
    print("E2 skipped:", json.dumps(skipped, indent=1))
    return cats, skipped


def _card_sets(name: str, cat: Catalog) -> tuple[set[str], set[str], set[str]]:
    """The card's own labels, relations and properties, read without the adapter."""
    if cat.model.source_format == "source_card":
        from utils.planner.cards import load_source_cards

        v = load_source_cards(REPO / "data")[name]
        props = {p for lab in v.node_labels for p in (v.node_properties.get(lab) or {})}
        return set(v.node_labels), set(v.relationship_types), props
    from utils.killtests.typed.request import Card

    c = Card(name) if (REPO / "data/external/cypherbench/graphs/schemas" / f"{name}_schema.json").exists() else None
    assert c is not None, f"no static schema for {name}"
    return set(c.labels), set(c.rels), {p for ps in c.labels.values() for p in ps}


# --------------------------------------------------------------------------- #
# JSON Schema (Draft 2020-12)
# --------------------------------------------------------------------------- #

_CHECK = r"""
import json, sys
from jsonschema import Draft202012Validator
bad = []
for name, schema in json.load(sys.stdin):
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        bad.append([name, str(exc)[:300]])
print(json.dumps({"checked": "jsonschema", "bad": bad}))
"""


def _check_schemas(items: list[tuple[str, dict]]) -> dict:
    try:
        from jsonschema import Draft202012Validator  # noqa: F401
    except ImportError:
        uv = shutil.which("uv")
        if not uv:
            pytest.skip("jsonschema is not installed and uv is not on PATH")
        proc = subprocess.run([uv, "run", "--offline", "--no-project", "--with", "jsonschema", "python", "-I",
                               "-c", _CHECK], input=json.dumps(items), capture_output=True, text=True,
                              timeout=300, cwd="/")
        if proc.returncode != 0:
            pytest.skip(f"jsonschema unavailable offline: {proc.stderr[-300:]}")
        return json.loads(proc.stdout.strip().splitlines()[-1]) | {"via": "uv offline cache"}
    bad = []
    for name, schema in items:
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # noqa: BLE001
            bad.append([name, str(exc)[:300]])
    return {"checked": "jsonschema", "bad": bad, "via": "installed"}


def test_attack_capec_and_every_cypherbench_schema_are_generated(loaded):
    cats, skipped = loaded
    static = {p.name[: -len("_schema.json")]
              for p in (REPO / "data/external/cypherbench/graphs/schemas").glob("*_schema.json")}
    assert len(static) == 11
    assert static | {"attack", "capec"} <= set(cats)
    for name, why in skipped.items():
        assert why, name  # every skipped card says why


def test_every_catalog_validates_as_json_schema_2020_12(loaded):
    cats, _ = loaded
    items = []
    for name, cat in cats.items():
        for detail in ("full", "names"):
            for spec in cat.specs(detail):
                items.append((f"{name}/{detail}/{spec['function']['name']}", spec["function"]["parameters"]))
    out = _check_schemas(items)
    print(f"\nE2 schema check: {len(items)} parameter schemas via {out['via']}; bad={len(out['bad'])}")
    assert out["bad"] == []


def test_every_enum_equals_the_cards_set(loaded):
    cats, _ = loaded
    for name, cat in cats.items():
        labels, rels, props = _card_sets(name, cat)
        specs = {s["function"]["name"]: s["function"]["parameters"]["properties"] for s in cat.specs()}
        assert sorted(specs) == sorted(TOOL_NAMES)
        assert set(specs["expand"]["relation"]["enum"]) == rels, name
        assert set(specs["expand"]["to_label"]["enum"]) == labels, name
        assert set(specs["resolve_entity"]["label"]["enum"]) == labels, name
        assert set(specs["expand"]["direction"]["enum"]) == set(DIRECTIONS)
        for tool, arg in (("filter", "property"), ("aggregate", "property"), ("group", "by"), ("rank", "by")):
            assert set(specs[tool][arg]["enum"]) == props, (name, tool)
        assert set(specs["filter"]["op"]["enum"]) == set(ALL_OPS)
        assert specs["expand"]["depth"]["maximum"] == cat.model.max_depth


def test_option_rules_follow_the_cards_directions(loaded):
    cats, _ = loaded
    for name, cat in cats.items():
        xo = next(s for s in cat.specs() if s["function"]["name"] == "expand")["function"]["parameters"]["x-options"]
        assert set(xo["labels"]) == set(cat.labels())
        for lab, entry in xo["labels"].items():
            for o in entry["relations"]:
                pats = cat.model.relations[o["relation"]].patterns
                pair = (lab, o["target"]) if o["direction"] == "out" else (o["target"], lab)
                assert pair in pats, (name, lab, o)
                assert o["reading"] and o["reading_source"] in ("frozen", "template")
                assert o["max_depth"] == (cat.model.max_depth if pair[0] == pair[1] else 1)
        fx = next(s for s in cat.specs() if s["function"]["name"] == "filter")["function"]["parameters"]["x-options"]
        for lab, entry in fx["labels"].items():
            assert set(entry["properties"]) == set(cat.label_properties(lab))


def test_frozen_readings_are_used_wherever_they_exist(loaded):
    cats, _ = loaded
    readings = json.loads((REPO / "docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability"
                           "/data/readings.json").read_text())
    used = 0
    for name, cat in cats.items():
        for lab in cat.labels():
            for o in cat.model.options(lab):
                key = f"{name}|{lab}|{o.relation}|{o.direction}|{o.target}"
                if key in readings:
                    assert (o.reading, o.reading_source) == (readings[key], "frozen")
                    used += 1
                else:
                    assert o.reading_source == "template"
    assert used == len(readings), "every frozen reading names an option of its card"


def test_directions_come_from_the_card_or_the_schema_registry(loaded):
    cats, _ = loaded
    src = {n: c.model.direction_source for n, c in cats.items() if c.model.source_format == "source_card"}
    print("\nE2 direction sources:", src)
    for n, s in src.items():
        assert s in ("card:safety.allowed_edge_patterns", "schema_registry:label_facets")


def test_gremlin_cards_translate_relation_names_for_the_store(loaded):
    cats, _ = loaded
    from utils.graph_loader.stores.gremlin import gremlin_edge_label

    for cat in cats.values():
        if cat.model.backend == "gremlin":
            for r in cat.relations():
                assert cat.edge_label(r) == gremlin_edge_label(r)
                assert cat.card_relation(gremlin_edge_label(r)) == r
        elif cat.model.source_format == "killtest_schema":
            assert all(cat.edge_label(r) == r for r in cat.relations())


def test_both_renderings_exist_and_the_summary_names_only(loaded):
    cats, _ = loaded
    for cat in cats.values():
        s, full = cat.summary(), cat.render()
        assert all(lab in s for lab in cat.labels()) and all(r in s for r in cat.relations())
        assert len(full) > len(s)
        assert all("x-options" not in s["function"]["parameters"] for s in cat.specs("names"))


# --------------------------------------------------------------------------- #
# No per-graph code
# --------------------------------------------------------------------------- #


def _all_names(cats: dict[str, Catalog], skipped: dict[str, str]) -> set[str]:
    names: set[str] = set(skipped)
    for g, c in cats.items():
        names |= set(c.labels()) | set(c.relations()) | {g}
    for p in SAVED_CARDS:
        d = json.loads(p.read_text())
        names |= {d["name"]} | {e["label"] for e in d["entities"]} | {r["label"] for r in d["relations"]}
    return names


def _hits(path: Path, names: set[str]) -> set[str]:
    text = path.read_text()
    return {n for n in names if re.search(r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])", text)}


def test_no_graph_label_or_relation_name_in_the_agent_code(loaded):
    cats, skipped = loaded
    names = _all_names(cats, skipped)
    found = {p.name: _hits(p, names) for p in sorted(AGENT.glob("*.py"))}
    print(f"\nE2 grep: {len(names)} names over {len(found)} files; hits {({k: v for k, v in found.items() if v})}")
    for f in NEW_FILES:
        assert found[f] == set(), (f, found[f])
    for f, hits in found.items():
        if f not in NEW_FILES:
            assert hits <= PREEXISTING.get(f, set()), (f, hits)


@pytest.mark.skipif(not SAVED_CARDS, reason="no saved introspected cards (logs/ is not in git)")
def test_saved_introspected_cards_also_generate(loaded):
    """Supplementary: the Text2Cypher / Mind the Query cards EXP-2026-11-006 introspected and saved.

    Not counted as "loaded" cards (their stores are what E2 asks about); this only
    shows the adapter takes them with no per-graph code.
    """
    for p in SAVED_CARDS:
        raw = json.loads(p.read_text())
        cat = Catalog(from_killtest_card(raw))
        specs = {s["function"]["name"]: s["function"]["parameters"]["properties"] for s in cat.specs()}
        assert set(specs["expand"]["relation"]["enum"]) == {r["label"] for r in raw["relations"]}
        assert set(specs["expand"]["to_label"]["enum"]) == {e["label"] for e in raw["entities"]}
