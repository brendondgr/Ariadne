r"""Turn composition specs plus authored questions into a runnable bank.

The existing runners take a bank: a list of questions, each with a `task` (or
`sub_questions` for a federated one) describing which store to ask and what
vocabulary the answer touches. This module writes that file from a spec.

**What it does not write is a template.** `holdout_protocol.compile_bank`
derives `expected_template` from a hand-written category map, and records on
every entry that the value is derived and therefore not a scoring signal. Specs
have no category, so there is nothing to derive from and the field is simply
absent — which is the honest state of affairs, and the reason it can be absent
is that `score_e2e` already strips it as an authoring key.

`entities` is not a template either. It is the graph vocabulary the answer path
touches — anchor label, predicate, step labels — read straight off the census.
The committed banks use the same mixed vocabulary (`["AttackPattern",
"EXPLOITS_WEAKNESS", "Weakness"]`), so this is the existing contract, derived
from the data rather than from a category someone wrote down.

Gold travels through unchanged. `ex_gold.expected` is what the enumerator
computed by walking the raw files, and nothing here may recompute, widen or
repair it: the point of the split between this module and `composition` is that
the answer is fixed before a question exists and stays fixed afterwards.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from utils.specialists.evalset.composition import Spec

#: The one declared cross-source join in the snapshot; see the census.
JOIN_KEY = "attack-technique-id"

#: Spec tier -> the bank's coarse difficulty label. The bank format predates the
#: D-tiers and its consumers expect these three, so both are written: `tier` for
#: compatibility and `d_tier` for the measurement that matters.
TIER_TO_BANK_TIER: dict[str, str] = {
    "D0": "adversarial",
    "D1": "easy",
    "D2": "medium",
    "D3": "medium",
    "D4": "hard",
    "D5": "hard",
    "D6": "hard",
}

DEFAULT_LIMITS = {"max_traversal_depth": 3, "max_result_rows": 300, "query_timeout_ms": 5000}


def _graph_predicate(predicate: str) -> str:
    """The name the loaded graph uses for this census predicate.

    The census names an edge the way the *source* declares it; the store names
    it its own way. Feeding the census's name into a bank produced a probe that
    retrieved nothing on shapes the committed banks answer perfectly — the
    failure that led to the reconciliation. The map is the reconciliation's,
    imported rather than duplicated so the two cannot drift.
    """
    from scripts.reconcile_graph import PREDICATE_MAP

    mapped = PREDICATE_MAP.get(predicate)
    if mapped is None:
        raise KeyError(
            f"{predicate!r} has no graph relationship. Either it is not loaded — in "
            "which case no question about it can be answered and it must not enter a "
            "bank — or PREDICATE_MAP is stale."
        )
    return mapped[0]


def _graph_label(label: str) -> str:
    from scripts.reconcile_graph import LABEL_MAP

    mapped = LABEL_MAP.get(label, label)
    if mapped is None:
        raise KeyError(f"{label!r} is not loaded; a question about it is unanswerable")
    return mapped


#: (census predicate) -> the label the graph gives that edge's target, when it
#: differs from the target's own label. `MAPS_TO` is the only case: the census
#: says CAPEC-66 maps to a *Technique*, because that is what CAPEC declares,
#: while the store materializes the target as a `TaxonomyEntry` node. A global
#: label map cannot express this — the same census label is `Technique`
#: everywhere else — so the override is keyed on the edge.
OBJECT_LABEL_OVERRIDE: dict[str, str] = {
    "MAPS_TO[ATTACK]": "TaxonomyEntry",
    "MAPS_TO[WASC]": "TaxonomyEntry",
    "MAPS_TO[OWASP Attacks]": "TaxonomyEntry",
}


def _entities(spec: Spec) -> list[str]:
    """Graph vocabulary the answer path touches, in path order.

    Translated into the store's names, because that is what a specialist keys
    on. The committed banks use the same mixed vocabulary of labels and
    relationship types.
    """
    out = [_graph_label(spec.anchor_label)]
    for step in spec.steps:
        target = (
            OBJECT_LABEL_OVERRIDE.get(step.predicate)
            if not step.reverse
            else None
        ) or _graph_label(step.label)
        out.extend([_graph_predicate(step.predicate), target])
    # Preserve order, drop repeats — a path that revisits a label says it once.
    seen: set[str] = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def answerable(spec: Spec) -> bool:
    """Whether every hop and label on this spec's path exists in the load.

    A bank must not contain a question the store cannot answer for reasons the
    question does not disclose: it would grade the system on rows nobody
    loaded. Since 2026-09-01 every census shape is loaded, so this returns True
    throughout — it stays because the next snapshot may not be so tidy.
    """
    try:
        _entities(spec)
    except KeyError:
        return False
    return True


#: Labels the CAPEC store owns. Everything else lives in ATT&CK.
CAPEC_LABELS = frozenset({
    "AttackPattern", "Category", "View", "Weakness",
    "ExecutionStep", "Consequence", "Skill", "CapecMitigation", "Prerequisite",
    "Indicator", "Example", "Resource", "AlternateTerm",
    "TaxonomyEntry:WASC", "TaxonomyEntry:OWASP Attacks",
})


def home_store(label: str) -> str:
    return "capec" if label in CAPEC_LABELS else "attack"


def _leg_source(spec: Spec, index: int) -> str:
    """Which store answers leg `index`: the one its *subject* lives in.

    Not "the one after the bridge". The bridge hop is itself answered in CAPEC,
    because CAPEC is what declares the mapping — routing it to ATT&CK sent
    "which techniques does CAPEC-66 map to" to the store that has never heard of
    CAPEC-66, and it retrieved nothing.
    """
    subject = spec.anchor_label if index == 0 else spec.steps[index - 1].label
    return home_store(subject)


def _leg_text(spec: Spec, index: int, gloss: str) -> str:
    subject = spec.anchor_key if index == 0 else "each of those"
    return f"For {subject}: {gloss}."


def to_entry(spec: Spec, question: str, register: str) -> dict[str, Any]:
    """One bank question. Federated when the path crosses stores."""
    from utils.specialists.evalset import render as rd

    brief = rd.brief_for(spec)
    # Federated means the answer needs *both* stores. A single hop across the
    # bridge does not: CAPEC declares the mapping, so "which techniques does
    # CAPEC-66 map to" is answered entirely within CAPEC — which is how the
    # committed `C-MAP` entries are shaped, as a single capec task carrying a
    # join key. Routing it as a two-store plan retrieved nothing.
    federated = len(spec.steps) > 1 and any(
        s.predicate == "MAPS_TO[ATTACK]" for s in spec.steps
    )
    declares_join = any(s.predicate == "MAPS_TO[ATTACK]" for s in spec.steps)

    common = {
        "id": f"{spec.id}::{register}",
        "spec_id": spec.id,
        "register": register,
        "tier": TIER_TO_BANK_TIER[spec.tier],
        "d_tier": spec.tier,
        "split": "generated",
        "question": question,
        "assertions": {
            "min_records": 0 if spec.tier == "D0" else 1,
            "must_include_ids": [spec.anchor_key],
            "must_include_related": list(spec.gold),
        },
        "ex_gold": {
            "pool": "join" if federated else "neighbors",
            "expected": list(spec.gold),
            # The scheme of the ANSWER: the store the last hop lands in.
            "scheme": home_store(spec.steps[-1].label) if spec.steps
            else home_store(spec.anchor_label),
            "kind": spec.gold_kind,
        },
        "spec": {
            "anchor_label": spec.anchor_label,
            "shapes": list(spec.shapes),
            "gold_width": spec.gold_width,
            "dangling": list(spec.dangling),
            "filters": [
                {"label": f.label, "property": f.property, "op": f.op, "value": f.value}
                for f in spec.filters
            ],
            "steps": [
                {"predicate": s.predicate, "reverse": s.reverse, "label": s.label}
                for s in spec.steps
            ],
        },
    }

    if not federated:
        return {
            **common,
            "task": {
                "sub_question_id": "q1",
                "source": _leg_source(spec, 0) if spec.steps else home_store(spec.anchor_label),
                "text": question,
                "entities": _entities(spec),
                "limits": dict(DEFAULT_LIMITS),
                "join_key": JOIN_KEY if declares_join else None,
                "seed_ids": [spec.anchor_key],
                "rationale": "generated from the schema census",
            },
        }

    legs = brief.ask.split(", and then ")
    subs = []
    for index, step in enumerate(spec.steps):
        gloss = legs[index] if index < len(legs) else brief.ask
        subs.append(
            {
                "id": f"q{index + 1}",
                "source": _leg_source(spec, index),
                "text": _leg_text(spec, index, gloss),
                "entities": [
                    _graph_label(spec.anchor_label if index == 0 else spec.steps[index - 1].label),
                    _graph_predicate(step.predicate),
                    _graph_label(step.label),
                ],
                "limits": dict(DEFAULT_LIMITS),
                "join_key": JOIN_KEY,
                "rationale": "generated from the schema census",
            }
        )
    return {
        **common,
        "hops": len(spec.steps),
        "sources": sorted({s["source"] for s in subs}),
        "sequenced": True,
        "partial_mode": None,
        "sub_questions": subs,
    }


def to_bank(
    pairs: Sequence[tuple[Spec, str, str]],
    *,
    attack_version: str,
    capec_version: str,
    author_model: str,
    seed: int,
    note: str = "",
) -> dict[str, Any]:
    """`pairs` are (spec, question, register)."""
    return {
        "meta": {
            "attack_version": attack_version,
            "capec_version": capec_version,
            "generator": "utils/specialists/evalset/composition.py "
                         "+ utils/specialists/evalset/spec_bank.py",
            "gold_source": "raw snapshot via raw_graph; NOT recomputed here",
            "split": "generated",
            "seed": seed,
            "author_model": author_model,
            "author_path": "subagent",
            "expected_template": "absent by design — specs carry no category to derive one from",
            "built_at": datetime.now(timezone.utc).isoformat(),
            "note": note,
        },
        "questions": [to_entry(spec, question, register) for spec, question, register in pairs],
    }


def write(bank: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bank, indent=1, ensure_ascii=False) + "\n")
