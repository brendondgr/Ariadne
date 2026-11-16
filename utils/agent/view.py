#!/usr/bin/env python3
"""What the agent sees of a result (Era 2, Step 5): lossless reductions only.

The full set stays server-side under its handle. The model gets a view built
only from reductions that do not lie about the set:

* the exact total, and whether the set is complete;
* exact facet counts (by label, and by chosen property values), with the
  remainder counted, never dropped;
* a labelled sample (default 10), with ``sample_of`` saying how many it is a
  sample of;
* for an empty result, a diagnosis: anchor not found, relation absent for that
  anchor, direction reversed, or the target label excludes everything -- with
  the nearest valid options read from the anchors' own edges.

The composer never answers from a view; it lists from the full set.
"""

from __future__ import annotations

from typing import Any

from utils.agent.exact import SetSpec
from utils.agent.handles import SetRecord

SAMPLE = 10
FACET_TOP = 20


def _top(counts: dict[str, int], top: int) -> dict[str, int]:
    """The ``top`` largest counts plus one ``(other)`` bucket: the counts still sum to the total."""
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    head = dict(items[:top])
    rest = sum(v for _, v in items[top:])
    if rest:
        head["(other)"] = rest
    return head


def build_view(rec: SetRecord, backend: Any, *, facet_props: tuple[str, ...] = (),
               sample: int = SAMPLE, name_prop: str = "name") -> dict[str, Any]:
    """The bounded, lossless view of a stored set."""
    view: dict[str, Any] = {"handle": rec.handle, "kind": rec.kind, "total": rec.total,
                            "complete": rec.complete}
    if not rec.complete:
        view["note"] = f"only part of the set is held ({len(rec.ids):,} of {rec.total:,})"
    if not rec.ids:
        return view
    facets = {"label": _top(backend.facet_counts(list(rec.ids), None), FACET_TOP)}
    for prop in facet_props:
        facets[prop] = _top(backend.facet_counts(list(rec.ids), prop), FACET_TOP)
    view["facets"] = facets
    head = list(rec.ids[:sample])
    described = {str(d["id"]): d for d in backend.describe_ids(head, (name_prop,))}
    view["sample"] = [f"{i} {described.get(i, {}).get(name_prop) or ''}".strip() for i in head]
    view["sample_of"] = len(rec.ids)
    return view


def diagnose_empty(spec: SetSpec, backend: Any, *, options: int = 8) -> dict[str, Any]:
    """Why a set came back empty, and the nearest valid options.

    Reasons, in the order they are checked:
    ``anchor_not_found``; ``relation_absent`` (no such edge at these anchors);
    ``direction_reversed`` (the edge exists, the other way round);
    ``label_excludes_all`` (the edge exists that way, to other labels only).
    """
    found = backend.anchors_found(spec.seeds)
    if not found:
        return {"reason": "anchor_not_found", "seeds": list(spec.seeds),
                "fix": "resolve the entity first; none of these ids exists in the graph"}
    facets = backend.anchor_facets(spec.seeds)
    nearest = sorted(facets, key=lambda f: (-int(f["n"]), f["rel"]))[:options]
    same_rel = [f for f in facets if f["rel"] == spec.rel]
    if not same_rel:
        reason, fix = "relation_absent", f"the anchors have no {spec.rel} edges; choose one of the options"
    elif spec.direction != "both" and not any(f["direction"] == spec.direction for f in same_rel):
        reason = "direction_reversed"
        other = "in" if spec.direction == "out" else "out"
        fix = f"{spec.rel} exists here only as direction={other}"
    elif spec.target_label and not any(f["label"] == spec.target_label for f in same_rel):
        reason = "label_excludes_all"
        labels = sorted({f["label"] for f in same_rel})
        fix = f"{spec.rel} leads to {labels}, not {spec.target_label}"
    else:
        reason, fix = "no_match", "the edges exist but no neighbour matches every condition"
    return {"reason": reason, "anchors_found": found, "fix": fix, "nearest": nearest}


__all__ = ["FACET_TOP", "SAMPLE", "build_view", "diagnose_empty"]
