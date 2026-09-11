#!/usr/bin/env python3
"""Gremlin-specific validator for the CAPEC specialist.

The pre-run gate for Gremlin traversals: structural, read-only safety,
schema conformance (labels, edge types, directions), and cap injection.
Property graphs have no traversal-time schema enforcement, so this validator
is deliberately strict — unbounded traversals can exhaust resources.
"""

from __future__ import annotations

import re
from typing import Any

from utils.graph_loader.stores.gremlin import gremlin_edge_label
from utils.specialists.validation import BaseValidator

# Match hasLabel('X')/hasLabel("X") capturing X. Both quote styles are valid
# Gremlin/Groovy string literals; validating only double quotes would let a
# single-quoted unknown label bypass schema conformance (found by an adversarial
# gate probe — see utils/specialists/tests/fixtures/adversarial_probes.py).
_HAS_LABEL_RE = re.compile(r"""hasLabel\(["']([^"']+)["']\)""")
# Match out('R')/out("R"), in(...), both(...) capturing R.
_OUT_RE = re.compile(r"""\.out\(["']([^"']+)["']\)""")
_IN_RE = re.compile(r"""\.in\(["']([^"']+)["']\)""")
_BOTH_RE = re.compile(r"""\.both\(["']([^"']+)["']\)""")
# Match trailing .limit(n) capturing n.
_LIMIT_TRAILING_RE = re.compile(r'\.limit\((\d+)\)\s*$')
# Count chained traversal steps (out/in/both).
_TRAVERSAL_STEP_RE = re.compile(r'\.(out|in|both)\(')

#: Mutating steps the gate must reject regardless of what a card happens to
#: list. The card's ``disallowed_steps`` is data and was written when TinkerPop's
#: mutating surface was smaller; `mergeV`/`mergeE` were added to the language
#: later and no card names them. EXP-2026-08-016 found 8 live bypasses through
#: exactly that gap, so the authoritative list lives in code and the card's list
#: is additive rather than definitive.
_EXTRA_WRITE_STEPS = ("mergeV", "mergeE")

#: A Groovy closure in a submitted traversal is arbitrary code execution on the
#: Gremlin server, not a query. No template emits one — every projection goes
#: through `project`/`by`/`fold` — so any brace-delimited block is rejected. The
#: map literal `[:]` is unaffected: it uses brackets, not braces.
_GROOVY_CLOSURE_RE = re.compile(r"\{[^}]*\}")

#: `repeat(...)` is legitimate — `capec_hierarchy_chain` emits
#: `repeat(...).times(3).emit()` — but only when it carries a bound. An
#: unbounded `repeat` walks the graph until it runs out of graph.
_REPEAT_RE = re.compile(r"\.repeat\(")
_TIMES_RE = re.compile(r"\.times\((\d+)\)")


def _extract_edge_anchors(query: str) -> list[tuple[str, str, str]]:
    """Return [(direction, rel, anchor_label)] for each traversal step.

    We parse the query left-to-right.  The anchor label is the most recent
    hasLabel("X") call before the out/in/both step.  This covers the primary
    shapes built by GremlinQueryBuilder.

    **A label anchors the next step only.** After one traversal the traverser is
    standing somewhere else, and the label it started from says nothing about
    where it is now. Carrying the label forward made the validator reject
    ``hasLabel("Category").in("MEMBER_OF").out("HAS_EXECUTION_STEP")`` — a
    correct two-leg walk — on the grounds that a Category has no execution step,
    which is true and not what the second step is asking. An unknown anchor is
    already handled: `schema_reasons` skips the direction check rather than
    guessing, so the edge type is still checked and the endpoint check is
    deferred to the `hasLabel` that follows, if one does.
    """
    results: list[tuple[str, str, str]] = []
    # Find all hasLabel and out/in/both positions.
    tokens: list[tuple[int, str, str]] = []  # (pos, kind, value)
    for m in _HAS_LABEL_RE.finditer(query):
        tokens.append((m.start(), "label", m.group(1)))
    for m in _OUT_RE.finditer(query):
        tokens.append((m.start(), "out", m.group(1)))
    for m in _IN_RE.finditer(query):
        tokens.append((m.start(), "in", m.group(1)))
    for m in _BOTH_RE.finditer(query):
        tokens.append((m.start(), "both", m.group(1)))
    tokens.sort(key=lambda t: t[0])

    current_label = ""
    for _pos, kind, value in tokens:
        if kind == "label":
            current_label = value
        elif kind in ("out", "in", "both"):
            results.append((kind, value, current_label))
            # Consumed: the traverser has moved and the label no longer
            # describes where it stands.
            current_label = ""
    return results


class GremlinValidator(BaseValidator):
    """Deterministic pre-run gate for Gremlin queries against CAPEC."""

    kind = "gremlin"

    def structural_reasons(self, query: str) -> list[str]:
        """Query must start with g.V( or g.E( and carry no Groovy closure."""
        stripped = query.strip()
        reasons: list[str] = []
        if not (stripped.startswith("g.V(") or stripped.startswith("g.E(")):
            reasons.append("Gremlin query must start with 'g.V(' or 'g.E('")
        if _GROOVY_CLOSURE_RE.search(query):
            # `g.V().filter{ it.get()... }` is arbitrary Groovy on the server,
            # and it passed every other check because it is structurally a read.
            reasons.append(
                "Gremlin query contains a Groovy closure '{...}': arbitrary "
                "server-side code is not a query"
            )
        return reasons

    def violates_read_only(self, query: str, card: Any) -> list[str]:
        """Reject any disallowed step listed in card.safety['disallowed_steps']."""
        reasons: list[str] = []
        disallowed: list[str] = list((card.safety or {}).get("disallowed_steps", []))
        disallowed += [step for step in _EXTRA_WRITE_STEPS if step not in disallowed]
        for step in disallowed:
            pattern = re.compile(r'\.' + re.escape(step) + r'\(')
            if pattern.search(query):
                reasons.append(
                    f"disallowed mutating step '.{step}(' found in query"
                )
        return reasons

    def schema_reasons(self, query: str, card: Any) -> list[str]:
        """Validate labels and edge types (including directions) against the card."""
        reasons: list[str] = []
        node_labels: frozenset[str] = card.node_labels
        # The card records source-vocabulary relationship names (e.g. CAPEC's
        # CamelCase ChildOf); the loaded graph carries the SCREAMING_SNAKE
        # form. Queries speak the graph convention, so card names are matched
        # through the same normalization the loader applies at load time.
        rel_types: frozenset[str] = frozenset(
            gremlin_edge_label(r) for r in card.relationship_types
        )
        allowed_patterns_raw: dict[str, list[list[str]]] = card.allowed_edge_patterns or {}
        allowed_patterns: dict[str, list[list[str]]] = {
            gremlin_edge_label(r): p for r, p in allowed_patterns_raw.items()
        }

        # Validate every hasLabel("X").
        for m in _HAS_LABEL_RE.finditer(query):
            label = m.group(1)
            if label not in node_labels:
                reasons.append(
                    f"hasLabel references unknown label {label!r}"
                )

        # Validate every traversal step and its direction/endpoints.
        for direction, rel, anchor_label in _extract_edge_anchors(query):
            if rel not in rel_types:
                reasons.append(
                    f".{direction}(\"{rel}\") references unknown relationship type {rel!r}"
                )
                continue
            # Direction/endpoint check: we only check when anchor_label is known.
            if not anchor_label or anchor_label not in node_labels:
                continue
            patterns = allowed_patterns.get(rel, [])
            if not patterns:
                reasons.append(
                    f"relationship {rel!r} has no allowed_edge_patterns in card"
                )
                continue
            # For out(rel) from anchor_label: [anchor_label, *] must exist.
            # For in(rel) from anchor_label: [*, anchor_label] must exist.
            # For both(rel): either direction is acceptable.
            valid_sources = {p[0] for p in patterns if len(p) == 2}
            valid_targets = {p[1] for p in patterns if len(p) == 2}
            if direction == "out" and anchor_label not in valid_sources:
                reasons.append(
                    f".out(\"{rel}\") from {anchor_label!r} is not an allowed "
                    f"edge direction (allowed sources: {sorted(valid_sources)})"
                )
            elif direction == "in" and anchor_label not in valid_targets:
                reasons.append(
                    f".in(\"{rel}\") from {anchor_label!r} is not an allowed "
                    f"edge direction (allowed targets: {sorted(valid_targets)})"
                )
            # both() is permissive — only reject if the label appears in neither role.
            elif direction == "both":
                if anchor_label not in valid_sources and anchor_label not in valid_targets:
                    reasons.append(
                        f".both(\"{rel}\") from {anchor_label!r} is not an allowed "
                        f"endpoint for {rel!r}"
                    )

        return reasons

    def schema_warnings(self, query: str, card: Any) -> list[str]:
        """Say when the card's allowlist disagrees with the loaded graph.

        Q45. Five CAPEC edges the canonical snapshot carries were declared in the
        card's relationship types and absent from its ``allowed_edge_patterns``.
        `schema_reasons` treats a relationship with no pattern as forbidden — the
        right default, since a missing pattern cannot be distinguished from a
        deliberately excluded one — so 34 development questions were rejected
        before they ran and the trace said only "no allowed_edge_patterns in
        card". Read cold, that is indistinguishable from "this edge is not real".

        This does not change the verdict, and must not. The card stays the sole
        permission source; the registry only gets to say the gate and the data
        disagree, so a lagging card is visible in the trace instead of looking
        like an absent edge.
        """
        try:
            from utils.specialists.schema import get_registry

            registry = get_registry()
        except Exception:  # noqa: BLE001 — no registry, no warning; never a verdict
            return []
        if registry is None:
            return []
        rel_types = frozenset(
            gremlin_edge_label(r) for r in (card.relationship_types or ())
        )
        allowed = {
            gremlin_edge_label(r): p
            for r, p in (card.allowed_edge_patterns or {}).items()
        }
        dataset = getattr(card, "dataset", None) or getattr(card, "source", None)
        warnings: list[str] = []
        seen: set[tuple[str, str, str]] = set()
        for direction, rel, anchor_label in _extract_edge_anchors(query):
            if rel not in rel_types or allowed.get(rel):
                continue
            if not anchor_label or (direction, rel, anchor_label) in seen:
                continue
            seen.add((direction, rel, anchor_label))
            try:
                real = registry.facet_exists(
                    anchor_label, rel, direction, None, dataset=dataset
                )
            except TypeError:
                real = registry.facet_exists(anchor_label, rel, direction, None)
            except Exception:  # a registry fault must never change a verdict
                continue
            if real:
                warnings.append(
                    f"card lags the graph: {rel!r} from {anchor_label!r} is "
                    f"declared and observed in the loaded schema but has no "
                    f"allowed_edge_patterns, so the gate rejects it. "
                    f"Regenerate the source card."
                )
        return warnings

    def cap_reasons(
        self, query: str, card: Any, limits: dict[str, int]
    ) -> list[str]:
        """Reject an over-deep traversal before it reaches the database.

        Property-graph traversers multiply with each hop, so a traversal already
        deeper than ``max_traversal_depth`` cannot be made safe by injecting a
        row ``.limit()`` — it must be rejected outright (briefing §4 point 2).
        """
        max_depth: int = limits.get("max_traversal_depth", 3) or 3
        reasons: list[str] = []

        # `repeat(...)` collapses an arbitrary walk into one step, so counting
        # traversal steps cannot see it. It is legitimate only with a bound at
        # or under the cap — which is what `capec_hierarchy_chain` emits.
        if _REPEAT_RE.search(query):
            bounds = [int(n) for n in _TIMES_RE.findall(query)]
            if not bounds:
                reasons.append(
                    "repeat(...) with no times(n) bound is an unbounded traversal"
                )
            elif max(bounds) > max_depth:
                reasons.append(
                    f"repeat(...).times({max(bounds)}) exceeds "
                    f"max_traversal_depth {max_depth}"
                )

        depth = len(_TRAVERSAL_STEP_RE.findall(query))
        if depth > max_depth:
            reasons.append(
                f"traversal depth {depth} exceeds max_traversal_depth {max_depth} "
                f"(too many chained out/in/both steps)"
            )
        return reasons

    def inject_caps(
        self, query: str, limits: dict[str, int], card: Any
    ) -> tuple[str, list[str]]:
        """Inject or clamp the trailing .limit(n) to the row cap."""
        injected: list[str] = []
        max_rows: int = limits.get("max_result_rows", 1000) or 1000

        m = _LIMIT_TRAILING_RE.search(query)
        if m is None:
            # No trailing limit — inject one.
            capped = query.rstrip() + f".limit({max_rows})"
            injected.append(f"injected .limit({max_rows})")
            return capped, injected

        existing = int(m.group(1))
        if existing > max_rows:
            # Clamp to the allowed maximum.
            capped = _LIMIT_TRAILING_RE.sub(f".limit({max_rows})", query)
            injected.append(f"clamped .limit({existing}) -> .limit({max_rows})")
            return capped, injected

        return query, injected
