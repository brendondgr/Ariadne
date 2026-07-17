#!/usr/bin/env python3
"""The ``expand`` primitive: the members of one facet with a bounded description, paged.

``describe`` tells you a Technique has 858 ``USES`` neighbours in a single facet
row; ``expand`` fetches those members — id, name, label, and a **bounded**
description (truncated per member). The description is what lets a follow-up read a
member's substance — an unnamed CAPEC mitigation node carries *only* a description
— without a second hop, while the truncation keeps a 519-neighbour fan-out a page
of summaries (~KBs), not ~500 KB of full records. If the planner wants a
neighbour's *full* record it still calls ``describe`` on it — the same primitive
recursing. Two calls, one concept.

The rule that matters is not *never truncate* — it is **never truncate
silently**. Every :class:`ExpandResult` carries the real ``total`` and an explicit
``truncated`` flag, so a page of 50 out of 858 is an honest answer the planner can
act on (fetch the next page, or narrow), rather than a bare list of 50 that lies
by omission — which is what the 25-neighbour cap did.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

OUT = "out"
IN = "in"


@dataclass(frozen=True)
class ExpandRequest:
    """Ask for one page of the members of a single facet of an anchor node.

    The facet coordinates — ``rel_type`` / ``direction`` / ``target_label`` — must
    come from a facet block the model actually saw (a ``describe`` result), so
    ``expand`` can never name a relationship or label the schema does not carry.
    """

    dataset: str
    anchor_id: str
    anchor_label: str
    rel_type: str
    direction: str
    target_label: str
    page: int = 0
    page_size: int = 50

    def skip(self) -> int:
        return max(0, self.page) * max(1, self.page_size)

    def end(self) -> int:
        return self.skip() + max(1, self.page_size)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "anchor_id": self.anchor_id,
            "anchor_label": self.anchor_label,
            "rel_type": self.rel_type,
            "direction": self.direction,
            "target_label": self.target_label,
            "page": self.page,
            "page_size": self.page_size,
        }


@dataclass(frozen=True)
class ExpandResult:
    """One page of a facet's members plus the honest total and truncation flag."""

    members: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    page: int = 0
    page_size: int = 50
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "members": list(self.members),
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "truncated": self.truncated,
        }


def paginate(
    all_members: list[dict[str, Any]],
    request: ExpandRequest,
    *,
    total: int | None = None,
    pre_sliced: bool = False,
) -> ExpandResult:
    """Build an :class:`ExpandResult`, computing the truncation signal honestly.

    ``total`` is the real member count (defaults to ``len(all_members)`` when the
    backend returned every member). When the backend already sliced server-side,
    pass ``pre_sliced=True`` and the real ``total`` so this does not slice again.
    ``truncated`` is True whenever members beyond this page exist — never inferred
    from a short list.
    """
    real_total = total if total is not None else len(all_members)
    if pre_sliced:
        page_members = list(all_members)
    else:
        page_members = all_members[request.skip() : request.end()]
    truncated = request.end() < real_total
    return ExpandResult(
        members=page_members,
        total=real_total,
        page=request.page,
        page_size=request.page_size,
        truncated=truncated,
    )
