#!/usr/bin/env python3
"""One refusal envelope for every tool (Era 2, Step 8).

Every refusal a tool returns has the same shape::

    {"ok": false, "code": ..., "detail": ..., "fix": ..., "problems": [...]}

* ``code`` is one of :data:`CODES`;
* ``detail`` says what was wrong, in one sentence;
* ``fix`` says what to send instead. When the refusal is about a **choice** (a
  relation, a direction, a label, a property, an operator, a depth, a handle),
  ``fix`` names valid options taken from the catalog's option rules, so the
  model never has to guess what would have been accepted;
* ``problems`` lists each offending field: ``{field, got, options}``.

``empty`` carries :func:`utils.agent.view.diagnose_empty`'s reason and fix,
with the nearest valid options read from the anchors' own edges.
"""

from __future__ import annotations

from typing import Any, Iterable

CODES = ("invalid_request", "empty", "ambiguous_anchor", "partial", "not_in_card", "repeated_call")

#: How many options a fix lists before it says how many more there are.
FIX_OPTIONS = 25


def _fmt(x: Any) -> str:
    return x if isinstance(x, str) else repr(x)


def name_options(options: Iterable[Any], limit: int = FIX_OPTIONS) -> str:
    """``a, b, c`` (and ``+n more``), in the order given."""
    opts = [_fmt(o) for o in options]
    head = ", ".join(opts[:limit])
    if len(opts) > limit:
        head += f" (+{len(opts) - limit} more; call describe for all)"
    return head


def problem(field: str, got: Any, options: Iterable[Any] = ()) -> dict[str, Any]:
    return {"field": field, "got": got, "options": [o for o in options]}


def refusal(code: str, detail: str, fix: str, problems: Iterable[dict[str, Any]] = (),
            **extra: Any) -> dict[str, Any]:
    """The envelope. ``extra`` keys (``coerced``, ``reason``, ``nearest`` ...) ride along."""
    if code not in CODES:
        raise ValueError(f"unknown refusal code {code!r}; one of {CODES}")
    if not fix:
        raise ValueError("a refusal must say how to fix it")
    return {"ok": False, "code": code, "detail": detail, "fix": fix, "problems": list(problems), **extra}


def choice(code: str, detail: str, field: str, got: Any, options: Iterable[Any], *,
           what: str | None = None, hint: str = "", **extra: Any) -> dict[str, Any]:
    """A refusal about a choice: the fix names the valid options."""
    opts = list(options)
    if not opts:
        raise ValueError(f"a choice refusal for {field!r} needs at least one valid option")
    fix = f"choose {what or field} from: {name_options(opts)}"
    if hint:
        fix = f"{fix}. {hint}"
    return refusal(code, detail, fix, [problem(field, got, opts)], **extra)


def is_refusal(content: Any) -> bool:
    return isinstance(content, dict) and content.get("ok") is False and content.get("code") in CODES


def empty(diagnosis: dict[str, Any], *, nearest_text: list[str] | None = None,
          **extra: Any) -> dict[str, Any]:
    """An ``empty`` refusal from :func:`utils.agent.view.diagnose_empty`'s output.

    ``nearest_text`` is the anchors' nearest valid options already written in
    the card's vocabulary (``REL out -> Label (n)``); they are appended to the fix.
    """
    reason = str(diagnosis.get("reason") or "empty")
    fix = str(diagnosis.get("fix") or "")
    if nearest_text:
        fix = f"{fix}; options at these anchors: {name_options(nearest_text)}" if fix else \
            f"options at these anchors: {name_options(nearest_text)}"
    if not fix:
        fix = "check the anchor ids and the relation with describe"
    return refusal("empty", f"the set is empty: {reason}", fix,
                   [problem("result", 0, nearest_text or [])], reason=reason,
                   nearest=diagnosis.get("nearest") or [], **extra)


__all__ = ["CODES", "FIX_OPTIONS", "choice", "empty", "is_refusal", "name_options", "problem", "refusal"]
