#!/usr/bin/env python3
"""How a canonical property value is stored in a graph engine.

One rule for every writer — the Neo4j loader, the Gremlin loader and the
Gremlin exporter — so the two engines cannot drift. The rule is the operator
algebra's (docs/era-2-expansion/operator-algebra.md §1 and §9 amendment 4):

- ``None`` is not stored.
- A scalar (``str``, ``int``, ``float``, ``bool``) is stored as it is.
- A non-empty list whose elements are all scalars of one type (in practice
  ``list[str]``) is stored as a list value, never as JSON text.
- An empty list is not stored: an empty list counts as missing.
- Anything else — a map, a list of maps (``external_references``), a list
  mixing types or holding nested lists — is not a list property. It is stored
  as JSON text (``sort_keys=True``), so nothing is lost.

Neo4j cannot hold a map or a list of maps at all, and a list it holds must be
homogeneous; that is why the cut falls where it does.
"""

from __future__ import annotations

import json
import re
from typing import Any

#: Property names the writers may interpolate into a query (Cypher backticks,
#: Gremlin ``.property('<key>', …)``). An allowlist, not an escape.
SAFE_PROPERTY_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

_SCALARS = (str, int, float, bool)

#: Returned by :func:`stored_value` for a value the engines do not store.
NOT_STORED = object()


def _homogeneous_scalars(items: list[Any]) -> bool:
    # ``bool`` is a subclass of ``int``; compare exact types so ``[True, 1]``
    # counts as mixed, as it does for Neo4j.
    if not all(isinstance(i, _SCALARS) for i in items):
        return False
    return len({type(i) for i in items}) == 1


def stored_value(value: Any) -> Any:
    """The form ``value`` is stored in, or :data:`NOT_STORED`."""
    if value is None:
        return NOT_STORED
    if isinstance(value, _SCALARS):
        return value
    if isinstance(value, (list, tuple)):
        items = list(value)
        if not items:
            return NOT_STORED
        if _homogeneous_scalars(items):
            return items
        return json.dumps(items, sort_keys=True)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    # Anything else (a date object, say) is stored as its JSON form, falling
    # back to text, rather than dropped.
    return json.dumps(value, sort_keys=True, default=str)


def is_json_encoded(value: Any) -> bool:
    """Would :func:`stored_value` turn ``value`` into JSON text?

    True for maps and for lists that are not homogeneous scalar lists. Such a
    property is stored but is not a queryable scalar or list property.
    """
    encoded = stored_value(value)
    return isinstance(encoded, str) and not isinstance(value, str)


def stored_properties(properties: dict[str, Any] | None) -> dict[str, Any]:
    """Every property as it is stored, with unstored values and unsafe keys dropped.

    Idempotent: applied to its own output it returns the same dict, so a writer
    may apply it to records an exporter has already encoded.
    """
    out: dict[str, Any] = {}
    for key, value in (properties or {}).items():
        if not isinstance(key, str) or not SAFE_PROPERTY_KEY.match(key):
            continue
        encoded = stored_value(value)
        if encoded is NOT_STORED:
            continue
        out[key] = encoded
    return out
