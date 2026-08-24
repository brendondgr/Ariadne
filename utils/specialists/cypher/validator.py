#!/usr/bin/env python3
"""Deterministic Cypher pre-run gate for the MITRE ATT&CK / Neo4j specialist.

The four abstract methods from ``BaseValidator`` are implemented here for Cypher:

  * ``structural_reasons``  — one statement, MATCH + RETURN present.
  * ``violates_read_only``  — rejects write clauses declared in the card safety
                              block (CREATE / MERGE / DELETE / SET / REMOVE / DROP
                              and DETACH DELETE / LOAD CSV / FOREACH / CALL { ).
  * ``schema_reasons``      — every node label and relationship type in the query
                              must exist in the card; an attack_id filter without
                              any node label is also rejected.
  * ``inject_caps``         — appends or clamps LIMIT to ``max_result_rows``.
"""

from __future__ import annotations

import re
from typing import Any

from ..validation import BaseValidator, word_present

# Extracts node labels from patterns like (:Technique) or (n:Technique)
_NODE_LABEL_RE = re.compile(r"\(\w*\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\{[^}]*\})?\s*\)")

#: Every label in a node pattern, not just the first, and backtick-quoted ones
#: too. The original regex read one bare identifier per pattern, so
#: `(n:Technique:Secret)` reported only `Technique` and `(x:`Secret`)` reported
#: nothing at all — two live scope escapes EXP-2026-08-016 found. This matches
#: the whole label chain and the escaping form; the per-label split is done by
#: the caller.
_NODE_LABEL_CHAIN_RE = re.compile(
    r"\(\s*\w*\s*:\s*((?:`[^`]+`|[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s*:\s*(?:`[^`]+`|[A-Za-z_][A-Za-z0-9_]*))*)"
)

#: One relationship hop in a MATCH path. A literal chain of these is a traversal
#: of the same depth as a variable-length path and must be capped the same way;
#: only the `*` form was checked before.
_HOP_RE = re.compile(r"-\s*\[[^\]]*\]\s*->|<-\s*\[[^\]]*\]\s*-|-\s*\[[^\]]*\]\s*-")

# Extracts relationship types from patterns like [:MITIGATES], -[r:USES]-> or
# the alternation form -[r:OWNS|WRITE_DACL]->.
#
# The alternation arm is not cosmetic. The previous pattern required the type to
# be followed immediately by `]`, so `[r:OWNS|WRITE_DACL]` matched NOTHING at
# all -- and a query using alternation therefore had *no* relationship type
# checked against the card. A validator that silently declines to validate is
# worse than one that rejects, so the group now spans the alternation and each
# alternative is checked separately below.
_REL_TYPE_RE = re.compile(
    r"\[\s*\w*\s*:\s*([A-Za-z_][A-Za-z0-9_]*(?:\s*\|\s*[A-Za-z_][A-Za-z0-9_]*)*)"
    r"\s*(?:\{[^}]*\})?\s*\]"
)

# Matches an existing LIMIT clause and its integer argument
_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)

# Checks whether the query *filters* on attack_id (a comparison / IN / string
# predicate), not merely returns it. A bare "attack_id" grep also fired on a
# RETURN alias (``n.attack_id AS id``), so a name-scoped query that returns the
# id was wrongly rejected as an unscoped id filter; keying on the predicate form
# keeps the STIX-ambiguity guard while letting name lookups return the id.
_ATTACK_ID_FILTER_RE = re.compile(
    r"\battack_id\b\s*(?:=|<>|<|>|=~|\bIN\b|\bCONTAINS\b|\bSTARTS\b|\bENDS\b)",
    re.IGNORECASE,
)

# Relationship-bracket contents, e.g. the "r:USES*1..3" inside -[r:USES*1..3]->
_REL_BRACKET_RE = re.compile(r"\[([^\]]*)\]")
# A variable-length quantifier inside a relationship bracket: *  *3  *1..3  *..3  *2..
_STAR_BOUNDS_RE = re.compile(r"\*\s*(\d*)\s*(\.\.)?\s*(\d*)")

# Extra write-like clauses not always covered by the card's disallowed_clauses list
_EXTRA_WRITE_CLAUSES = [
    "DETACH DELETE",
    "LOAD CSV",
    "FOREACH",
    "CALL {",
    # `USE <db>` re-targets the whole statement at another database, which puts
    # it outside the card's schema entirely — the card cannot vouch for a graph
    # it does not describe. Found live by EXP-2026-08-016.
    "USE",
]


class CypherValidator(BaseValidator):
    """Pre-run gate for Cypher queries against the ATT&CK Neo4j source card."""

    kind = "cypher"

    def structural_reasons(self, query: str) -> list[str]:
        """Reject multi-statement queries and those missing MATCH or RETURN."""
        reasons: list[str] = []
        # Remove a single trailing semicolon (allowed) then check for any others
        stripped = query.rstrip()
        if stripped.endswith(";"):
            stripped = stripped[:-1]
        if ";" in stripped:
            reasons.append(
                "query contains multiple statements (';' found inside the body)"
            )
        if not word_present(query, "MATCH"):
            reasons.append("query must contain a MATCH clause")
        if not word_present(query, "RETURN"):
            reasons.append("query must contain a RETURN clause")
        return reasons

    def violates_read_only(self, query: str, card: Any) -> list[str]:
        """Reject any write clause declared in the card safety block or extra list."""
        reasons: list[str] = []
        disallowed = list(card.safety.get("disallowed_clauses", []))
        # Always check the extra multi-word / punctuated write clauses too
        for clause in disallowed + _EXTRA_WRITE_CLAUSES:
            if word_present(query, clause):
                reasons.append(f"query contains disallowed write clause: {clause!r}")
        return reasons

    def schema_reasons(self, query: str, card: Any) -> list[str]:
        """Check labels and relationship types against the card; reject id-only filters."""
        reasons: list[str] = []

        # Extract node labels — every label in each pattern, backticks stripped.
        node_labels = [
            part.strip().strip("`")
            for chain in _NODE_LABEL_CHAIN_RE.findall(query)
            for part in re.split(r"\s*:\s*", chain)
            if part.strip()
        ]
        for label in node_labels:
            if not card.has_label(label):
                reasons.append(
                    f"node label {label!r} is not in the card schema "
                    f"(known: {sorted(card.node_labels)})"
                )

        # Extract relationship types
        rel_types = [
            alternative.strip()
            for group in _REL_TYPE_RE.findall(query)
            for alternative in group.split("|")
            if alternative.strip()
        ]
        for rel in rel_types:
            if not card.has_relationship(rel):
                reasons.append(
                    f"relationship type {rel!r} is not in the card schema "
                    f"(known: {sorted(card.relationship_types)})"
                )

        # Reject an attack_id filter without any node label (ambiguous STIX type)
        if _ATTACK_ID_FILTER_RE.search(query) and not node_labels:
            reasons.append(
                "query filters on attack_id but contains no node label; "
                "add a label to avoid matching the wrong STIX type"
            )

        return reasons

    def cap_reasons(
        self, query: str, card: Any, limits: dict[str, int]
    ) -> list[str]:
        """Reject unbounded or over-deep variable-length path expansions.

        A pattern like ``-[:USES*]->`` (unbounded) or ``-[:USES*1..9]->`` (deeper
        than ``max_traversal_depth``) can explode the search space, so it is
        rejected before execution — the Cypher analogue of the Gremlin depth gate.
        """
        max_depth: int = limits.get("max_traversal_depth", 3) or 3
        reasons: list[str] = []

        # A literal chain of hops is a traversal of the same depth as a
        # variable-length path and was never counted: only the `*` form below was
        # checked, so `(a)-[:R]-(b)-[:R]-(c)-[:R]-(d)-[:R]-(e)` walked four hops
        # past a cap of three. Counted per MATCH-ish segment rather than per
        # query, so two independent 2-hop patterns are not summed into a false
        # positive.
        for segment in re.split(r"\bWITH\b|\bUNION\b|\bRETURN\b", query, flags=re.I):
            hops = len(_HOP_RE.findall(segment))
            if hops > max_depth:
                reasons.append(
                    f"traversal depth {hops} exceeds max_traversal_depth "
                    f"{max_depth} (literal hop chain)"
                )
                break

        for bracket in _REL_BRACKET_RE.findall(query):
            if "*" not in bracket:
                continue
            match = _STAR_BOUNDS_RE.search(bracket)
            lower, dots, upper = (match.group(1), match.group(2), match.group(3)) if match else ("", "", "")
            if upper:
                hops: int | None = int(upper)
            elif lower and not dots:
                hops = int(lower)  # form "*n" means exactly n hops
            else:
                hops = None  # "*", "*..", "*n.." — unbounded upper bound
            label = bracket.strip()
            if hops is None:
                reasons.append(
                    f"unbounded variable-length path '[{label}]' is not allowed "
                    f"(cap the upper bound at max_traversal_depth {max_depth})"
                )
            elif hops > max_depth:
                reasons.append(
                    f"variable-length path '[{label}]' exceeds "
                    f"max_traversal_depth {max_depth}"
                )
        return reasons

    def inject_caps(
        self, query: str, limits: dict[str, int], card: Any
    ) -> tuple[str, list[str]]:
        """Append or clamp the LIMIT clause to ``max_result_rows``."""
        max_rows = limits.get("max_result_rows", 1000)
        injected: list[str] = []

        match = _LIMIT_RE.search(query)
        if match is None:
            # No LIMIT present — append one
            query = query.rstrip().rstrip(";") + f" LIMIT {max_rows}"
            injected.append(f"LIMIT {max_rows} appended (none present)")
        else:
            existing = int(match.group(1))
            if existing > max_rows:
                # Clamp the existing LIMIT
                query = _LIMIT_RE.sub(f"LIMIT {max_rows}", query, count=1)
                injected.append(
                    f"LIMIT clamped from {existing} to {max_rows}"
                )

        return query, injected
