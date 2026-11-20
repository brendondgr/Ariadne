#!/usr/bin/env python3
"""The tool catalog, generated from a card (Era 2, Step 8).

Nothing in this module knows any graph. A card in either format goes through
one adapter into :class:`CardModel` -- labels, relations with their
``(subject, object)`` direction facets, properties with value types, glosses,
aliases and plain readings -- and the catalog is generated from that model:

* OpenAI-style function specs (the shape :class:`utils.agent.runner.ToolBox`
  takes) whose parameters are JSON Schema (Draft 2020-12) with the card's enums;
* **option rules** under the ``x-options`` extension keyword: which relations
  each label has, in which direction, to which target label, with a plain
  reading for each; which properties each label has, with value type and the
  operators that type takes;
* a names-only prompt summary and a full-card rendering, so a planner can be
  run with either.

Card formats:

1. :class:`utils.planner.cards.SourceCardView` (Ariadne's own sources). The
   direction facets come from ``safety.allowed_edge_patterns`` when the card has
   them; otherwise from the schema registry's canonical-derived triples
   (``SourceCardView.label_facets``), which is the authority the specialists'
   direction checks already use. Glosses and aliases come from
   ``entity_descriptions``; value types from ``node_properties``; the depth limit
   from ``SourceCardView.limits()``.
2. The kill-test schema dict read by :class:`utils.killtests.typed.request.Card`
   (``{name, entities, relations}``), through that class, so the key property
   and the implicit ``name`` match what the typed validator sees.

Readings: a card whose dataset appears in the frozen EXP-2026-11-014 readings
file takes its readings from there (``reading_source: "frozen"``); every
(relation, direction, target) without one gets a deterministic template
reading (``reading_source: "template"``).

Store vocabulary: the catalog always shows the card's relation names. A
relation's ``store_name`` is what a query sends: Ariadne's Gremlin loader stores
every edge in SCREAMING_SNAKE (``gremlin_edge_label``), the kill-test loaders
keep the source names. :meth:`Catalog.edge_label` is the function to hand to
:class:`utils.agent.exact.GremlinBackend`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from utils.agent.handles import SET_OPS
from utils.agent.runner import ASK_CALLER_SPEC, FINISH_SPEC

REPO = Path(__file__).resolve().parents[2]
READINGS = (REPO / "docs" / "research" / "experiments" / "EXP-2026-11-014-era2-decision-model-usability"
            / "data" / "readings.json")

DIRECTIONS = ("out", "in")
#: Depth limit for a card that states none.
DEFAULT_MAX_DEPTH = 3
HANDLE_PATTERN = r"^set:[0-9]+$"

#: Card value types -> the catalog's value types.
VALUE_TYPES = {
    "string": "string", "str": "string", "text": "string",
    "boolean": "boolean", "bool": "boolean",
    "array": "list", "list": "list", "list[str]": "list",
    "int": "integer", "integer": "integer", "long": "integer",
    "float": "number", "double": "number", "number": "number",
    "float_text": "number_text",
    "date": "date", "datetime": "datetime",
}
#: Which filter operators each value type takes.
OPS_BY_TYPE = {
    "string": ("=", "<>", "starts_with", "ends_with", "contains_text"),
    "integer": ("=", "<>", "<", ">", "<=", ">="),
    "number": ("=", "<>", "<", ">", "<=", ">="),
    "number_text": ("=", "<>", "<", ">", "<=", ">="),
    "date": ("=", "<>", "<", ">", "<=", ">="),
    "datetime": ("=", "<>", "<", ">", "<=", ">="),
    "boolean": ("=", "<>"),
    "list": ("contains", "not_contains"),
}
ALL_OPS = tuple(dict.fromkeys(op for ops in OPS_BY_TYPE.values() for op in ops))
AGG_FNS = ("count", "sum", "avg", "min", "max")
NUMERIC = ("integer", "number", "number_text")

#: Tools whose calls run now, and the ones whose schemas exist but whose
#: operators arrive in Step 9.
IMPLEMENTED = ("find_schema", "resolve_entity", "describe", "expand", "count", "set_op", "not_expressible")
SCHEMA_ONLY = ("filter", "aggregate", "group", "rank", "verify")
EXITS = ("ask_caller", "finish")
TOOL_NAMES = ("find_schema", "resolve_entity", "describe", "expand", "filter", "aggregate", "group", "rank",
              "set_op", "count", "verify", "not_expressible", "ask_caller", "finish")


# --------------------------------------------------------------------------- #
# The internal card model
# --------------------------------------------------------------------------- #


def words(name: str) -> str:
    """A schema name in words: ``HAS_PART_X`` -> ``has part x``, ``worksAt`` -> ``works at``."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name))
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return " ".join(re.split(r"[^0-9A-Za-z]+", s)).strip().lower()


@dataclass(frozen=True)
class PropertyModel:
    name: str
    vtype: str
    raw_type: str
    optional: bool = True
    example: Any = None

    @property
    def ops(self) -> tuple[str, ...]:
        return OPS_BY_TYPE[self.vtype]


@dataclass(frozen=True)
class RelationOption:
    """One (relation, direction, target) a label has, with its plain reading."""

    label: str
    relation: str
    direction: str
    target: str
    reading: str
    reading_source: str
    repeating: bool

    def as_dict(self, max_depth: int) -> dict[str, Any]:
        return {"relation": self.relation, "direction": self.direction, "target": self.target,
                "reading": self.reading, "reading_source": self.reading_source,
                "max_depth": max_depth if self.repeating else 1}


@dataclass
class LabelModel:
    name: str
    gloss: str = ""
    key: str = ""
    properties: dict[str, PropertyModel] = field(default_factory=dict)
    options: list[RelationOption] = field(default_factory=list)


@dataclass
class RelationModel:
    name: str
    gloss: str = ""
    aliases: tuple[str, ...] = ()
    patterns: tuple[tuple[str, str], ...] = ()
    properties: dict[str, PropertyModel] = field(default_factory=dict)
    store_name: str = ""


@dataclass
class CardModel:
    """One card, normalised. ``name`` is the dataset / graph name."""

    name: str
    source_format: str
    backend: str
    labels: dict[str, LabelModel]
    relations: dict[str, RelationModel]
    max_depth: int
    direction_source: str
    edge_label: Callable[[str], str] | None = None

    def options(self, label: str) -> list[RelationOption]:
        return list(self.labels[label].options) if label in self.labels else []

    def property_names(self) -> list[str]:
        return sorted({p for lab in self.labels.values() for p in lab.properties})


def _prop(name: str, raw: Any) -> PropertyModel:
    if isinstance(raw, dict):
        t = str(raw.get("type") or "string")
        vtype = VALUE_TYPES.get(t.lower(), "string")
        ex = raw.get("example")
        if vtype == "list" and isinstance(ex, list) and any(not isinstance(x, str) for x in ex):
            # A list of objects (``external_references``) is not a list property: both
            # stores hold it as JSON text (operator-algebra.md, amendment 4).
            vtype = "string"
        return PropertyModel(name, vtype, t, bool(raw.get("optional", True)), ex)
    t = str(raw or "string")
    return PropertyModel(name, VALUE_TYPES.get(t.lower(), "string"), t)


def _load_readings(path: Path = READINGS) -> dict[str, str]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def template_reading(label: str, relation: str, direction: str, target: str, gloss_words: str = "") -> str:
    """``the {target} that this {label} {relation}`` (``out``), inverted for ``in``."""
    rel = gloss_words or words(relation)
    if direction == "out":
        return f"the {words(target)} that this {words(label)} {rel}"
    return f"the {words(target)} that {rel} this {words(label)}"


def _build_options(model: CardModel, readings: dict[str, str]) -> None:
    for rel in model.relations.values():
        for subj, obj in rel.patterns:
            for label, direction, target in ((subj, "out", obj), (obj, "in", subj)):
                if label not in model.labels:
                    continue
                key = f"{model.name}|{label}|{rel.name}|{direction}|{target}"
                if key in readings:
                    reading, src = readings[key], "frozen"
                else:
                    reading, src = template_reading(label, rel.name, direction, target), "template"
                opt = RelationOption(label, rel.name, direction, target, reading, src, subj == obj)
                if opt not in model.labels[label].options:
                    model.labels[label].options.append(opt)
    for lab in model.labels.values():
        lab.options.sort(key=lambda o: (o.relation, o.direction, o.target))


def from_source_card(view: Any, *, readings: dict[str, str] | None = None,
                     data_dir: str | Path | None = None) -> CardModel:
    """Adapter for :class:`utils.planner.cards.SourceCardView`."""
    readings = _load_readings() if readings is None else readings
    desc = view.entity_descriptions or {}
    node_gloss = desc.get("nodes") or {}
    rel_gloss = desc.get("relationships") or {}
    paraphrases = desc.get("relationship_paraphrases") or {}
    labels = {}
    for lab in sorted(view.node_labels):
        props = {p: _prop(p, spec) for p, spec in sorted((view.node_properties.get(lab) or {}).items())}
        key = "name" if "name" in props else next(iter(props), "")
        labels[lab] = LabelModel(lab, str(node_gloss.get(lab) or ""), key, props)

    patterns: dict[str, set[tuple[str, str]]] = {r: set() for r in view.relationship_types}
    if view.allowed_edge_patterns:
        direction_source = "card:safety.allowed_edge_patterns"
        for rel, pairs in view.allowed_edge_patterns.items():
            for s, o in pairs:
                patterns.setdefault(rel, set()).add((s, o))
    else:
        direction_source = "schema_registry:label_facets"
        for lab in sorted(view.node_labels):
            for f in view.label_facets(lab, data_dir):
                if f.direction == "out" and f.rel_type in patterns:
                    patterns[f.rel_type].add((lab, f.neighbour_label))

    edge_label = None
    if str(view.runtime_backend).lower() == "gremlin":
        from utils.graph_loader.stores.gremlin import gremlin_edge_label

        edge_label = gremlin_edge_label
    rels = {}
    for r in sorted(view.relationship_types):
        rels[r] = RelationModel(r, str(rel_gloss.get(r) or ""), tuple(paraphrases.get(r) or ()),
                                tuple(sorted(patterns.get(r) or ())), {},
                                edge_label(r) if edge_label else r)
    depth = int(view.limits().get("max_traversal_depth") or 0) or DEFAULT_MAX_DEPTH
    model = CardModel(view.dataset, "source_card", str(view.runtime_backend), labels, rels, depth,
                      direction_source, edge_label)
    _build_options(model, readings)
    return model


def from_killtest_card(card: Any, *, name: str | None = None, max_depth: int = DEFAULT_MAX_DEPTH,
                       readings: dict[str, str] | None = None) -> CardModel:
    """Adapter for the kill-test schema dict, read through ``typed.request.Card``.

    ``card`` is a ``Card`` or a raw ``{name, entities, relations}`` dict.
    """
    from utils.killtests.typed.request import Card

    if isinstance(card, dict):
        card = Card(str(card.get("name") or name or ""), card)
    readings = _load_readings() if readings is None else readings
    labels = {lab: LabelModel(lab, "", card.keys.get(lab, ""),
                              {p: _prop(p, t) for p, t in sorted(props.items())})
              for lab, props in sorted(card.labels.items())}
    rels = {}
    for r, triples in sorted(card.rels.items()):
        eprops: dict[str, PropertyModel] = {}
        for _, _, p in triples:
            eprops.update({k: _prop(k, t) for k, t in p.items()})
        rels[r] = RelationModel(r, "", (), tuple(sorted({(s, o) for s, o, _ in triples})), eprops, r)
    model = CardModel(name or card.graph, "killtest_schema", "neo4j+gremlin", labels, rels, max_depth,
                      "card:relations.subj_label/obj_label")
    _build_options(model, readings)
    return model


# --------------------------------------------------------------------------- #
# The catalog
# --------------------------------------------------------------------------- #


def _fn(name: str, description: str, properties: dict[str, Any], required: list[str],
        options: dict[str, Any] | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"type": "object", "properties": properties, "required": required,
                              "additionalProperties": False}
    if options:
        params["x-options"] = options
    return {"type": "function", "function": {"name": name, "description": description, "parameters": params}}


_HANDLE = {"type": "string", "pattern": HANDLE_PATTERN, "description": "a set handle such as set:3"}


class Catalog:
    """The tool catalog of one card."""

    def __init__(self, model: CardModel) -> None:
        self.model = model

    # -- option rules -------------------------------------------------------

    @property
    def name(self) -> str:
        return self.model.name

    def labels(self) -> list[str]:
        return sorted(self.model.labels)

    def relations(self) -> list[str]:
        return sorted(self.model.relations)

    def properties(self) -> list[str]:
        return self.model.property_names()

    def label_properties(self, label: str) -> dict[str, PropertyModel]:
        lab = self.model.labels.get(label)
        return dict(lab.properties) if lab else {}

    def options(self, label: str, relation: str | None = None, direction: str | None = None,
                target: str | None = None) -> list[RelationOption]:
        return [o for o in self.model.options(label)
                if (relation is None or o.relation == relation)
                and (direction is None or o.direction == direction)
                and (target is None or o.target == target)]

    def relation_options(self, relation: str) -> list[RelationOption]:
        return [o for lab in self.labels() for o in self.model.options(lab) if o.relation == relation]

    def edge_label(self, relation: str) -> str:
        """The store's name for a card relation (identity unless the store renames)."""
        rel = self.model.relations.get(relation)
        return rel.store_name if rel and rel.store_name else relation

    def card_relation(self, stored: str) -> str:
        """The card's name for a store relation name (inverse of :meth:`edge_label`)."""
        for r in self.model.relations.values():
            if r.store_name == stored or r.name == stored:
                return r.name
        return stored

    def x_options(self, labels: Iterable[str] | None = None, *, relations: bool = True,
                  properties: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {"max_depth": self.model.max_depth, "labels": {}}
        for lab in labels if labels is not None else self.labels():
            m = self.model.labels[lab]
            entry: dict[str, Any] = {}
            if relations:
                entry["relations"] = [o.as_dict(self.model.max_depth) for o in m.options]
            if properties:
                entry["properties"] = {p.name: {"type": p.vtype, "ops": list(p.ops)}
                                       for p in m.properties.values()}
            out["labels"][lab] = entry
        return out

    # -- specs --------------------------------------------------------------

    def specs(self, detail: str = "full") -> list[dict[str, Any]]:
        """Every tool's function spec. ``detail``: ``full`` (with ``x-options``) or ``names``."""
        if detail not in ("full", "names"):
            raise ValueError("detail must be 'full' or 'names'")
        full = detail == "full"
        labels, rels, props = self.labels(), self.relations(), self.properties()
        depth = self.model.max_depth
        lab_enum = {"type": "string", "enum": labels}
        rel_enum = {"type": "string", "enum": rels}
        prop_enum = {"type": "string", "enum": props} if props else {"type": "string"}
        set_ref = {"anyOf": [_HANDLE, {"type": "array", "items": {"type": "string"}, "minItems": 1}],
                   "description": "a set handle (set:3) or a list of entity ids"}
        value = {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "boolean"},
                           {"type": "array", "items": {"type": ["string", "number"]}}]}
        specs = [
            _fn("find_schema", "Search the card for labels, relations and properties matching some words. "
                "Returns ranked matches with their readings.",
                {"text": {"type": "string", "minLength": 1},
                 "k": {"type": "integer", "minimum": 1, "maximum": 50, "default": 8}}, ["text"]),
            _fn("resolve_entity", "Find the entity a name refers to. Returns one match (with a set handle), "
                "several candidates, an ambiguity, or nothing.",
                {"text": {"type": "string", "minLength": 1}, "label": lab_enum}, ["text"]),
            _fn("describe", "Describe a label or relation of the card (its options and properties), a set "
                "handle (its view), or an entity id (its edges).",
                {"target": {"type": "string", "minLength": 1,
                            "description": "a label, a relation, a set handle, or an entity id"}},
                ["target"], {"labels": labels, "relations": rels} if full else None),
            _fn("expand", "The neighbours of a set over one relation, in one direction, optionally only "
                "those of one label. depth > 1 follows a repeating relation up to that many hops.",
                {"from": set_ref, "relation": rel_enum,
                 "direction": {"type": "string", "enum": list(DIRECTIONS)},
                 "to_label": lab_enum,
                 "depth": {"type": "integer", "minimum": 1, "maximum": depth, "default": 1}},
                ["from", "relation"], self.x_options(properties=False) if full else None),
            _fn("filter", "Keep the members of a set whose property satisfies a condition.",
                {"set": _HANDLE, "property": prop_enum, "op": {"type": "string", "enum": list(ALL_OPS)},
                 "value": value}, ["set", "property", "op", "value"],
                self.x_options(relations=False) if full else None),
            _fn("aggregate", "One aggregate over a set: count, or sum/avg/min/max of a numeric property (property rules: filter's x-options).",
                {"set": _HANDLE, "fn": {"type": "string", "enum": list(AGG_FNS)}, "property": prop_enum},
                ["set", "fn"]),
            _fn("group", "Split a set's members by a property's values.",
                {"set": _HANDLE, "by": prop_enum}, ["set", "by"]),
            _fn("rank", "The top k members of a set by a property; ties at the cut are kept unless ties=false.",
                {"set": _HANDLE, "by": prop_enum, "k": {"type": "integer", "minimum": 1},
                 "order": {"type": "string", "enum": ["desc", "asc"], "default": "desc"},
                 "ties": {"type": "boolean", "default": True}}, ["set", "by", "k"]),
            _fn("set_op", "intersect, union or minus of two sets, as a new set.",
                {"op": {"type": "string", "enum": list(SET_OPS)}, "a": _HANDLE, "b": _HANDLE},
                ["op", "a", "b"]),
            _fn("count", "The exact number of members of a set.", {"set": _HANDLE}, ["set"]),
            _fn("verify", "Check a claim against the sets it rests on.",
                {"claim": {"type": "string", "minLength": 1},
                 "sets": {"type": "array", "items": _HANDLE}}, ["claim"]),
            _fn("not_expressible", "Say that part of the question cannot be expressed with this card's tools, "
                "and what would be needed.",
                {"part": {"type": "string", "minLength": 1}, "needs": {"type": "string", "minLength": 1}},
                ["part", "needs"]),
            json.loads(json.dumps(ASK_CALLER_SPEC)),
            json.loads(json.dumps(FINISH_SPEC)),
        ]
        return specs

    # -- prompt renderings --------------------------------------------------

    def summary(self) -> str:
        """Names only: labels and relations. Details come through find_schema and describe."""
        return (f"Graph {self.name}.\nLabels: {', '.join(self.labels())}.\n"
                f"Relations: {', '.join(self.relations())}.\n"
                "Call find_schema or describe for a label's relations, directions, readings and properties.")

    def describe_label(self, label: str) -> str:
        m = self.model.labels[label]
        lines = [f"{label}" + (f": {m.gloss}" if m.gloss else "")]
        if m.properties:
            lines.append("  properties: " + ", ".join(f"{p.name} ({p.vtype})" for p in m.properties.values()))
        for o in m.options:
            arrow = f"-[{o.relation}]->" if o.direction == "out" else f"<-[{o.relation}]-"
            extra = f", depth up to {self.model.max_depth}" if o.repeating else ""
            lines.append(f"  {o.relation} {o.direction} -> {o.target}: {o.reading} "
                         f"({label}{arrow}{o.target}{extra})")
        return "\n".join(lines)

    def describe_relation(self, relation: str) -> str:
        r = self.model.relations[relation]
        lines = [f"{relation}" + (f": {r.gloss}" if r.gloss else "")]
        if r.aliases:
            lines.append("  also said as: " + ", ".join(r.aliases[:12]))
        for s, o in r.patterns:
            lines.append(f"  ({s})-[{relation}]->({o})")
        return "\n".join(lines)

    def render(self) -> str:
        """The whole card: every label with its properties and relation options."""
        head = f"Graph {self.name}. Expand depth is at most {self.model.max_depth}.\n"
        return head + "\n".join(self.describe_label(lab) for lab in self.labels())

    # -- documents for find_schema -----------------------------------------

    def search_documents(self) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        for lab in self.labels():
            m = self.model.labels[lab]
            docs.append({"kind": "label", "name": lab, "text": f"{words(lab)} {m.gloss}"})
            for p in m.properties.values():
                docs.append({"kind": "property", "name": p.name, "label": lab, "type": p.vtype,
                             "text": f"{words(p.name)} {words(lab)}"})
            for o in m.options:
                rel = self.model.relations[o.relation]
                docs.append({"kind": "relation", "name": o.relation, "label": lab, "direction": o.direction,
                             "target": o.target, "reading": o.reading,
                             "text": " ".join([words(o.relation), o.reading, rel.gloss, " ".join(rel.aliases),
                                               words(o.target)])})
        return docs


def catalog_for(card: Any, **kw: Any) -> Catalog:
    """A catalog from a ``SourceCardView``, a kill-test ``Card`` / schema dict, or a ``CardModel``."""
    if isinstance(card, CardModel):
        return Catalog(card)
    if hasattr(card, "node_labels") and hasattr(card, "relationship_types"):
        return Catalog(from_source_card(card, **kw))
    return Catalog(from_killtest_card(card, **kw))


# --------------------------------------------------------------------------- #
# Every loaded card
# --------------------------------------------------------------------------- #


def _reachable(uri: str, timeout: float = 1.5) -> bool:
    import socket
    from urllib.parse import urlparse

    u = urlparse(uri)
    try:
        with socket.create_connection((u.hostname or "localhost", u.port or 7687), timeout=timeout):
            return True
    except OSError:
        return False


def load_all(data_dir: str | Path = "data", *, live: bool = True) -> tuple[dict[str, Catalog], dict[str, str]]:
    """Catalogs for every card this machine can produce; ``(catalogs, skipped)``.

    * Ariadne's source cards (``<data_dir>/source_cards``);
    * every CypherBench schema file (static, in ``data/external/cypherbench``);
    * the Text2Cypher and Mind the Query cards, which are introspected from
      their live Neo4j stores: generated only when the store answers (nothing
      is loaded or wiped here); otherwise recorded in ``skipped`` with the reason.
    """
    from utils.planner.cards import load_source_cards

    cats: dict[str, Catalog] = {}
    skipped: dict[str, str] = {}
    for ds, view in load_source_cards(data_dir).items():
        cats[ds] = Catalog(from_source_card(view, data_dir=data_dir))

    from utils.killtests.t1.load import CB

    for path in sorted((CB / "graphs" / "schemas").glob("*_schema.json")):
        g = path.name[: -len("_schema.json")]
        try:
            cats[g] = Catalog(from_killtest_card(json.loads(path.read_text()) | {"cypherbench": True}, name=g))
        except Exception as exc:  # noqa: BLE001 - one bad file is reported, not fatal
            skipped[g] = f"schema file unreadable: {type(exc).__name__}: {exc}"

    from utils.killtests.t2c import load as t2c

    for g in list(t2c.GRAPHS) + list(t2c.MTQ):
        uri = t2c.neo4j_uri(g)
        if not live:
            skipped[g] = "live introspection not requested"
            continue
        if not _reachable(uri):
            skipped[g] = f"store not reachable at {uri} (introspected card needs the live store)"
            continue
        try:
            cats[g] = Catalog(from_killtest_card(t2c.card(g), name=g))
        except Exception as exc:  # noqa: BLE001
            skipped[g] = f"introspection failed at {uri}: {type(exc).__name__}: {exc}"[:300]
    return cats, skipped


__all__ = ["AGG_FNS", "ALL_OPS", "Catalog", "CardModel", "DEFAULT_MAX_DEPTH", "DIRECTIONS", "EXITS",
           "IMPLEMENTED", "LabelModel", "OPS_BY_TYPE", "PropertyModel", "READINGS", "RelationModel",
           "RelationOption", "SCHEMA_ONLY", "TOOL_NAMES", "VALUE_TYPES", "catalog_for", "from_killtest_card",
           "from_source_card", "load_all", "template_reading", "words"]
