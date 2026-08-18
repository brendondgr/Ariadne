#!/usr/bin/env python3
"""Can the values a query binds inhabit the property it filters?

This is the guard the blind holdout was missing. ``WHERE g.attack_id IN
['T1550.002']`` filters Group identifiers against a technique identifier: it
matches nothing, and before this module nothing could tell that outcome apart
from an honest "no groups use this technique". One is a bug, the other is an
answer, and a system that cannot distinguish them will report the bug as the
answer every time.

The check is deliberately timid. It fails a draft only when **every** value
bound to a filter is a positive mismatch — a query that would return rows for
some of its seeds is a real query, and dropping it would lose real answers.
Anything the schema registry has not learned is ``undetermined`` and passes.
That asymmetry is what lets the guard run against a source nobody has seen: on
UUID-keyed telemetry it is silent rather than wrong.

Extraction lives here rather than in the validator because it is the same
question in both languages, and because a builder can bypass parsing entirely by
declaring its bindings in ``meta["bindings"]`` — the mechanism a third query
language would use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from utils.specialists.schema import get_registry
from utils.specialists.schema.idscheme import MISMATCH
from utils.specialists.schema.registry import SchemaRegistry
from utils.specialists.validation import QueryDraft

# A label reaches an alias two ways: inline in a node pattern, ``(t:Technique)``,
# or as a predicate, ``WHERE (t:Technique OR t:SubTechnique)``. Both count.
_CY_ALIAS_LABEL = re.compile(r"\((\w+)\s*:\s*(\w+)")
_CY_LABEL_PRED = re.compile(r"\b(?:WHERE|AND|OR)\s+\(?\s*(\w+)\s*:\s*(\w+)")
_CY_IN_PARAM = re.compile(r"(\w+)\.(\w+)\s+IN\s+\$(\w+)")
_CY_EQ_PARAM = re.compile(r"(\w+)\.(\w+)\s*=\s*\$(\w+)")
_GR_TOKEN = re.compile(
    r'hasLabel\(\s*"(?P<label>[^"]+)"\s*\)'
    r'|has\(\s*"(?P<prop>[^"]+)"\s*,\s*(?:within\(\s*(?P<within>\w+)\s*\)|(?P<bare>\w+))\s*\)'
)


@dataclass(frozen=True)
class Binding:
    """One ``label.property`` filtered against the values of one parameter."""

    label: str
    property: str
    param: str
    values: tuple[Any, ...]

    def describe(self) -> str:
        return f"{self.label}.{self.property} bound to {list(self.values)}"


def _as_values(value: Any) -> tuple[Any, ...]:
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(value)
    return (value,)


def _cypher_bindings(query: str, params: dict[str, Any]) -> tuple[Binding, ...]:
    """One binding per ``(alias-label, property)`` — an alias may carry several.

    ``MATCH (t) WHERE (t:Technique OR t:SubTechnique) AND t.attack_id IN $ids``
    binds one alias to two labels. Both are emitted; because they share a
    parameter, the grouping in :func:`unsatisfiable_bindings` then treats the
    filter as satisfiable when either label admits the values, which is what the
    query means.
    """
    aliases: dict[str, list[str]] = {}
    for pattern in (_CY_ALIAS_LABEL, _CY_LABEL_PRED):
        for alias, label in pattern.findall(query):
            labels = aliases.setdefault(alias, [])
            if label not in labels:
                labels.append(label)
    found: list[Binding] = []
    for pattern in (_CY_IN_PARAM, _CY_EQ_PARAM):
        for alias, prop, param in pattern.findall(query):
            if param not in params:
                continue
            for label in aliases.get(alias, ()):
                found.append(Binding(label, prop, param, _as_values(params[param])))
    return tuple(found)


def _gremlin_bindings(query: str, params: dict[str, Any]) -> tuple[Binding, ...]:
    """Walk the traversal left to right, carrying the most recent ``hasLabel``."""
    label: str | None = None
    found: list[Binding] = []
    for match in _GR_TOKEN.finditer(query):
        if match.group("label"):
            label = match.group("label")
            continue
        param = match.group("within") or match.group("bare")
        prop = match.group("prop")
        if label is None or param not in params:
            continue
        found.append(Binding(label, prop, param, _as_values(params[param])))
    return tuple(found)


def extract_bindings(draft: QueryDraft) -> tuple[Binding, ...]:
    """Every ``(label, property, values)`` the draft filters on.

    A declaration in ``meta["bindings"]`` — a list of ``{"label", "property",
    "param"}`` dicts — wins over parsing. Declaration is the durable mechanism:
    it travels with the builder and survives a query language these parsers have
    never seen.
    """
    params = dict(draft.params or {})
    declared = (draft.meta or {}).get("bindings")
    if declared:
        return tuple(
            Binding(
                str(entry["label"]),
                str(entry["property"]),
                str(entry.get("param", "")),
                _as_values(params.get(entry.get("param", ""))),
            )
            for entry in declared
            if entry.get("param") in params
        )
    query = draft.query or ""
    if query.lstrip().startswith("g."):
        return _gremlin_bindings(query, params)
    return _cypher_bindings(query, params)


def unsatisfiable_bindings(
    draft: QueryDraft, dataset: str, registry: SchemaRegistry | None = None
) -> tuple[Binding, ...]:
    """The draft's bindings that cannot match, grouped by parameter.

    Grouping is what keeps the guard honest about disjunction.
    ``subtechnique_parent`` filters ``WHERE t.attack_id IN $ids OR st.attack_id
    IN $ids`` — seeded with a sub-technique id the first disjunct matches
    nothing and the second matches exactly the right row. Judged one binding at
    a time that query looks broken; judged one *parameter* at a time it is
    correct, which it is.

    The rule therefore is: a parameter is unsatisfiable only when every place it
    is bound rejects every value it carries. A conjunction of one good and one
    impossible filter is missed by this — deliberately, because the bias of this
    whole module is to stay silent rather than to accuse wrongly.
    """
    if not dataset:
        return ()
    registry = registry or get_registry()
    grouped: dict[str, list[Binding]] = {}
    for index, binding in enumerate(extract_bindings(draft)):
        if not binding.values:
            continue
        grouped.setdefault(binding.param or f"#{index}", []).append(binding)

    doomed: list[Binding] = []
    for bindings in grouped.values():
        verdicts = [
            registry.value_verdict(binding.label, binding.property, value, dataset=dataset)
            for binding in bindings
            for value in binding.values
        ]
        if verdicts and all(verdict == MISMATCH for verdict in verdicts):
            doomed.extend(bindings)
    return tuple(doomed)


def binding_reasons(
    draft: QueryDraft, dataset: str, registry: SchemaRegistry | None = None
) -> list[str]:
    """Gate reasons for a draft that cannot match, phrased for the retry loop.

    The reason names the property, the values, and what that property's
    identifiers actually look like, because it is fed back to the builder as
    repair feedback as well as recorded in the trace.
    """
    registry = registry or get_registry()
    schema = registry.dataset(dataset)
    reasons: list[str] = []
    for binding in unsatisfiable_bindings(draft, dataset, registry):
        shapes: Sequence[str] = ()
        if schema is not None:
            learned = schema.id_schemes(binding.label, binding.property)
            if learned is not None:
                shapes = sorted(learned.schemes)
            candidates = sorted(registry.labels_for_id(binding.values[0], dataset=dataset))
        else:
            candidates = []
        detail = f"binding mismatch: {binding.describe()}"
        if shapes:
            detail += f", but {binding.label}.{binding.property} looks like {shapes}"
        if candidates:
            detail += f"; those values identify {candidates}"
        reasons.append(detail)
    return reasons
