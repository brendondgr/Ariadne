#!/usr/bin/env python3
"""Coercion of near-miss tool arguments (Era 2, Step 8).

A model that writes ``persons`` for a label, ``Out`` for a direction or
``"3"`` for a depth meant something the catalog can name exactly. This module
makes those repairs, and only those, and records every one::

    {"field": "relation", "from": "works_at", "to": "worksAt", "filled_by": "case_separator"}

What it fixes:

* **names** (labels, relations, properties): a unique case- and
  separator-insensitive match (``has part`` -> ``HAS_PART``);
  otherwise a unique option within a small edit distance (at most 2, and
  tighter for short names, see :func:`max_distance`);
* **enums** (directions, operators, functions): case only;
* **numbers**: ``"8"`` -> 8 for an integer argument; a number written as text
  for a numeric property, and a number for a text property, by the card's
  value type; ``"true"``/``"false"`` for a boolean property.

What it never does: choose between two candidates. If two options are equally
reachable the value is **ambiguous** and the call is refused with both named.
A coercion that would change the meaning (a direction flipped, a property
moved to another label) is not a coercion; it is the caller's choice, and the
refusal says what the choices are.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

_SEP = re.compile(r"[^0-9a-z]+")
_INT = re.compile(r"^[+-]?\d+$")
_NUM = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


class Ambiguous(ValueError):
    """Two or more options are equally good matches; never guess."""

    def __init__(self, field: str, got: Any, candidates: list[str]) -> None:
        super().__init__(f"{field}: {got!r} could be any of {candidates}")
        self.field, self.got, self.candidates = field, got, candidates


class NoMatch(ValueError):
    """No option is close enough to repair to."""

    def __init__(self, field: str, got: Any) -> None:
        super().__init__(f"{field}: {got!r} matches no option")
        self.field, self.got = field, got


@dataclass
class Coercions:
    """The fixes applied to one call, in order."""

    fixes: list[dict[str, Any]] = field(default_factory=list)

    def add(self, field_: str, before: Any, after: Any, filled_by: str) -> None:
        self.fixes.append({"field": field_, "from": before, "to": after, "filled_by": filled_by})

    def __bool__(self) -> bool:
        return bool(self.fixes)


def squash(text: str) -> str:
    """Lower case, separators removed: ``Has-Part_X`` -> ``haspartx``."""
    return _SEP.sub("", str(text).lower())


def _soft(text: str) -> str:
    """Lower case, every run of separators as one ``_``, camelCase split the same way."""
    t = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(text).strip())
    return re.sub(r"[^0-9a-z]+", "_", t.lower()).strip("_")


def distance(a: str, b: str) -> int:
    """Optimal-string-alignment (restricted Damerau-Levenshtein) distance."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if not la or not lb:
        return la or lb
    prev2: list[int] = []
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        prev2, prev = prev, cur
    return prev[lb]


def max_distance(text: str) -> int:
    """The edit budget for a name: 2 from six characters, 1 at five, 0 below.

    The protocol's ceiling is 2. Short names get less, because one or two edits
    turn a short word into another real one (``in`` -> ``on``, ``game`` -> ``name``,
    ``rate`` -> ``date``); a short name is repaired only by case and separators.
    """
    n = len(squash(text))
    return 2 if n >= 6 else 1 if n == 5 else 0


def coerce_name(value: Any, options: Iterable[str], field_: str, log: Coercions | None = None) -> str:
    """``value`` if it is an option, else its unique near-miss; raise otherwise."""
    opts = list(dict.fromkeys(str(o) for o in options))
    if isinstance(value, str) and value in opts:
        return value
    if not isinstance(value, str) or not value.strip():
        raise NoMatch(field_, value)
    key = squash(value)
    same = [o for o in opts if squash(o) == key]
    if len(same) == 1:
        if log is not None:
            log.add(field_, value, same[0], "case_separator")
        return same[0]
    if len(same) > 1:
        raise Ambiguous(field_, value, same)
    budget = max_distance(value)
    if budget:
        # Distance over the lower-cased spelling with separators kept (unified to
        # "_"): dropping a qualifier such as "x." from "x.name" is a change of
        # meaning, not a typo, and must cost more than the budget.
        near = [(distance(_soft(value), _soft(o)), o) for o in opts]
        near = [(d, o) for d, o in near if d <= budget]
        if len(near) == 1:
            if log is not None:
                log.add(field_, value, near[0][1], "edit_distance")
            return near[0][1]
        if len(near) > 1:
            raise Ambiguous(field_, value, sorted(o for _, o in near))
    raise NoMatch(field_, value)


def coerce_enum(value: Any, options: Iterable[str], field_: str, log: Coercions | None = None) -> str:
    """An enum match ignoring case only (no edit distance: enum words are short)."""
    opts = list(options)
    if isinstance(value, str) and value in opts:
        return value
    if isinstance(value, str):
        same = [o for o in opts if o.lower() == value.strip().lower()]
        if len(same) == 1:
            if log is not None:
                log.add(field_, value, same[0], "enum_case")
            return same[0]
        if len(same) > 1:
            raise Ambiguous(field_, value, same)
    raise NoMatch(field_, value)


def coerce_int(value: Any, field_: str, log: Coercions | None = None) -> int:
    """An integer, from ``8``, ``8.0`` or ``"8"``; booleans are not integers."""
    if isinstance(value, bool):
        raise NoMatch(field_, value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        if log is not None:
            log.add(field_, value, int(value), "int_from_number")
        return int(value)
    if isinstance(value, str) and _INT.match(value.strip()):
        out = int(value.strip())
        if log is not None:
            log.add(field_, value, out, "int_from_text")
        return out
    raise NoMatch(field_, value)


def coerce_bool(value: Any, field_: str, log: Coercions | None = None) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        out = value.strip().lower() == "true"
        if log is not None:
            log.add(field_, value, out, "bool_from_text")
        return out
    raise NoMatch(field_, value)


#: Internal value types (see ``catalog.VALUE_TYPES``).
NUMERIC_TYPES = ("integer", "number", "number_text")


def coerce_value(value: Any, vtype: str, field_: str, log: Coercions | None = None) -> Any:
    """``value`` fitted to a property's value type, or :class:`NoMatch`.

    ``integer``/``number``/``number_text`` take numbers or numbers written as
    text (``number_text`` is the card's "numbers stored as text": compared as
    numbers, so a numeric value is what the comparison needs); ``string``,
    ``date`` and ``datetime`` take text (a bare number becomes its text);
    ``boolean`` takes ``true``/``false``; ``list`` takes one element (for
    ``contains``) as text.
    """
    if vtype in NUMERIC_TYPES:
        if isinstance(value, bool):
            raise NoMatch(field_, value)
        if isinstance(value, (int, float)):
            if vtype == "integer" and isinstance(value, float):
                return coerce_int(value, field_, log)
            return value
        if isinstance(value, str) and _NUM.match(value.strip()):
            s = value.strip()
            out: int | float = int(s) if _INT.match(s) else float(s)
            if vtype == "integer" and isinstance(out, float):
                if not out.is_integer():
                    raise NoMatch(field_, value)
                out = int(out)
            if log is not None:
                log.add(field_, value, out, "number_from_text")
            return out
        raise NoMatch(field_, value)
    if vtype == "boolean":
        return coerce_bool(value, field_, log)
    if vtype in ("string", "date", "datetime", "list"):
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out_s = str(value)
            if log is not None:
                log.add(field_, value, out_s, "text_from_number")
            return out_s
        raise NoMatch(field_, value)
    raise NoMatch(field_, value)


__all__ = ["Ambiguous", "Coercions", "NUMERIC_TYPES", "NoMatch", "coerce_bool", "coerce_enum", "coerce_int",
           "coerce_name", "coerce_value", "distance", "max_distance", "squash"]
