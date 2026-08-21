#!/usr/bin/env python3
"""The mapping from an external question family to one graph lookup.

AttackQA groups its rows by a ``source`` string that names the relation the
question is about. Each of the families below has a set-valued answer made
entirely of ATT&CK identifiers, which is what makes a grader-free score
possible; the rest of AttackQA is prose and is out of scope here.

The mapping is declared once, applied to every item without per-item judgement,
and is the *only* thing this experiment authors about an external question. The
question text itself is used verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Family:
    """One question shape, and the single graph lookup that answers it."""

    name: str
    rel: str
    direction: str                 # "out" from the anchor, or "in" toward it
    anchor_labels: tuple[str, ...]
    target_labels: tuple[str, ...]
    #: Entity types for the replayed plan. Two endpoint labels, nothing more --
    #: any richer hint would be this experiment doing the planner's job.
    entities: tuple[str, ...]


_TECH = ("Technique", "SubTechnique")

FAMILIES: dict[str, Family] = {f.name: f for f in (
    Family("relationships_techniques_for_software", "USES", "out",
           ("Software",), _TECH, ("Software", "Technique")),
    Family("relationships_software_for_technique", "USES", "in",
           _TECH, ("Software",), ("Technique", "Software")),
    Family("relationships_techniques_for_group", "USES", "out",
           ("Group",), _TECH, ("Group", "Technique")),
    Family("relationships_groups_for_technique", "USES", "in",
           _TECH, ("Group",), ("Technique", "Group")),
    Family("relationships_software_for_group", "USES", "out",
           ("Group",), ("Software",), ("Group", "Software")),
    Family("relationships_groups_for_software", "USES", "in",
           ("Software",), ("Group",), ("Software", "Group")),
    Family("relationships_techniques_for_campaign", "USES", "out",
           ("Campaign",), _TECH, ("Campaign", "Technique")),
    Family("relationships_campaigns_for_technique", "USES", "in",
           _TECH, ("Campaign",), ("Technique", "Campaign")),
    Family("relationships_software_for_campaign", "USES", "out",
           ("Campaign",), ("Software",), ("Campaign", "Software")),
    Family("relationships_campaigns_for_software", "USES", "in",
           ("Software",), ("Campaign",), ("Software", "Campaign")),
    Family("relationships_campaigns_for_group", "ATTRIBUTED_TO", "in",
           ("Group",), ("Campaign",), ("Group", "Campaign")),
    Family("relationships_groups_for_campaign", "ATTRIBUTED_TO", "out",
           ("Campaign",), ("Group",), ("Campaign", "Group")),
    Family("techniques_sub", "HAS_SUBTECHNIQUE", "out",
           ("Technique",), ("SubTechnique",), ("Technique", "SubTechnique")),
    Family("techniques_parent", "HAS_SUBTECHNIQUE", "in",
           ("SubTechnique",), ("Technique",), ("SubTechnique", "Technique")),
)}

#: cti-ate poses one question shape only: what techniques does this software use.
#: It is the same lookup as AttackQA's software family, which is what lets the
#: two benchmarks be read against each other.
CTI_ATE_FAMILY = FAMILIES["relationships_techniques_for_software"]
