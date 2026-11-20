"""Today's ``TypedStep`` as the internal form, and back.

``from_typed_step`` maps each step kind onto the algebra without changing its
meaning:

| TypedStep | Internal form |
|---|---|
| ``describe``, or ``expand``/``count`` with no hops | ``Describe(Anchors)`` (the builder treats them alike) |
| ``expand`` | ``Expand(Walk(Anchors, hops, depth, last_conds))`` |
| ``count`` | ``Count(Walk(...))`` |
| ``common`` | ``Common(Anchors)``, with no label: its anchors are of different kinds |
| ``scan`` | ``Nodes(Scan(label))`` |

The step's ``filter`` ``(property, value)`` becomes one condition on the last
hop: ``=``, or ``contains`` when the card types the property as a list. The
builder reads a list filter as "contains" today, and S5 allows only that on
lists. Without a card, it stays ``=``. Whether the store holds the property
natively is decided when compiling, exactly as the builder decides it today.

**Anchor ids.** A step may carry none, because they are resolved at run time
(a name anchor, or ``depends_on``). It then gets ``Anchors((), label)``, which
``validate.check`` refuses until the ids are filled in. The builder always
compiles with the resolved seed ids.

``to_typed_step`` is the inverse. ``from_typed_step`` then ``to_typed_step``
returns the step unchanged, up to the builder's own equivalences (``normalise``).
"""

from __future__ import annotations

from typing import Any

from .base import Anchors, Common, Cond, Count, Describe, Expand, Hop, Nodes, Scan, Walk


def normalise(step: Any) -> dict[str, Any]:
    """The step as the builder reads it: describe-like steps drop their hops, depth and filter."""
    d = step.to_dict() if hasattr(step, "to_dict") else dict(step)
    d = {"kind": d.get("kind") or "expand", "anchor_label": d.get("anchor_label") or "",
         "anchor_ids": list(d.get("anchor_ids") or []), "hops": list(d.get("hops") or []),
         "depth": int(d.get("depth") or 1), **({"filter": d["filter"]} if d.get("filter") else {})}
    if d["kind"] in ("describe", "common", "scan") or (d["kind"] in ("expand", "count") and not d["hops"]):
        if d["kind"] in ("expand", "count"):
            d["kind"] = "describe"
        d.update(hops=[], depth=1)
        d.pop("filter", None)
        if d["kind"] == "scan":
            d["anchor_ids"] = []
        if d["kind"] == "common":
            # The anchors are of different kinds and the builder matches them by id
            # alone, so the step's single anchor_label is not a label they share
            # (EXP-2026-11-021, H3: it dropped every anchor of the other kind).
            d["anchor_label"] = ""
    return d


def from_typed_step(step: Any, card: Any = None) -> Any:
    d = normalise(step)
    anchors = Anchors(tuple(d["anchor_ids"]), d["anchor_label"])
    if d["kind"] == "describe":
        return Describe(anchors)
    if d["kind"] == "common":
        return Common(anchors)
    if d["kind"] == "scan":
        return Nodes(Scan(d["anchor_label"]))
    hops = tuple(Hop(h.get("relation") or "", h.get("direction") or "", h.get("target_label") or "")
                 for h in d["hops"])
    conds = ()
    if d.get("filter"):
        f = d["filter"]
        prop = str(f.get("property"))
        target = hops[-1].target if hops else ""
        is_list = bool(card is not None and target in card.labels
                       and getattr(card.labels[target].properties.get(prop), "vtype", "") == "list")
        conds = (Cond(prop, "contains" if is_list else "=", str(f.get("value"))),)
    walk = Walk(anchors, hops, d["depth"], conds)
    if d["kind"] == "count":
        return Count(walk)
    if d["kind"] == "expand":
        return Expand(walk)
    raise ValueError(f"unknown TypedStep kind {d['kind']!r}")


def to_typed_step(node: Any) -> dict[str, Any]:
    """The ``TypedStep.to_dict()`` form of a node ``from_typed_step`` can produce."""
    base = {"anchor_ids": [], "anchor_label": "", "depth": 1, "hops": []}
    if isinstance(node, (Describe, Common)):
        return {**base, "kind": "describe" if isinstance(node, Describe) else "common",
                "anchor_label": node.anchors.label, "anchor_ids": list(node.anchors.ids)}
    if isinstance(node, Nodes) and isinstance(node.of, Scan):
        return {**base, "kind": "scan", "anchor_label": node.of.label}
    if isinstance(node, (Expand, Count)):
        walk = node.walk if isinstance(node, Expand) else node.of
        if not (isinstance(walk, Walk) and isinstance(walk.start, Anchors)):
            raise ValueError("only a walk from anchors is a TypedStep")
        out = {"kind": "expand" if isinstance(node, Expand) else "count", "anchor_label": walk.start.label,
               "anchor_ids": list(walk.start.ids), "depth": walk.depth,
               "hops": [{"relation": h.relation, "direction": h.direction, "target_label": h.target}
                        for h in walk.hops]}
        if walk.last_conds:
            if len(walk.last_conds) != 1 or walk.last_conds[0].op not in ("=", "contains"):
                raise ValueError("a TypedStep holds one '=' (or, on a list, 'contains') filter")
            c = walk.last_conds[0]
            out["filter"] = {"property": c.prop, "value": c.value}
        if any(h.edge_conds for h in walk.hops):
            raise ValueError("a TypedStep has no edge filters")
        return out
    raise ValueError(f"{type(node).__name__} is not expressible as a TypedStep")


__all__ = ["from_typed_step", "normalise", "to_typed_step"]
