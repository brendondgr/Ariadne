#!/usr/bin/env python3
"""Text-derived task signals: the specialists' only view of the question's words.

Era 2 Step 8 (EXP-2026-11-015, "What gets built" item 5). The query builders and
the resolver used to read ``SpecialistTask.text`` directly, in twenty places, to
decide things like "is this a bulk scan", "which ids does it name" and "which
entity name does it contain". Each of those readings is computed here **once**,
when the task is made, and carried on the task as a frozen, serialisable
``TaskSignals``. Past that point nothing in ``utils/specialists/cypher``,
``utils/specialists/gremlin`` or ``utils/specialists/resolve`` reads the text:
replacing ``task.text`` with nonsense after creation changes no query and no
record (check E1, ``tests/test_typed_boundary.py``).

Two kinds of field:

* **Decisions** that need nothing but the text: ``bulk_scan``, ``definitional``,
  the identifier families named, the concept anchors.
* **Lexical inputs** to lookups that also need the card, a name index or the
  schema registry, which only the builder knows: the raw name candidates per
  extraction pass, the word tokens the name index matches on, the words the
  slot binder matches property names on, and which observed registry values the
  question writes. Each is exactly the input the original lookup took from the
  text, so the lookup's answer is unchanged.

The typed plan (item 6) is meant to fill the decision fields itself; the lexical
fields are what the rules path still needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_TUPLE_FIELDS = (
    "attack_ids", "capec_ids", "cwe_ids", "attack_seed_ids", "concept_terms",
    "name_tokens", "proper_nouns", "question_words", "mentioned_values",
)


#: What a typed step asks for. ``expand``: the neighbours over a path;
#: ``count``: the same set, for a count; ``describe``: the anchor itself;
#: ``scan``: every member of one label; ``common``: what every anchor links to.
STEP_KINDS = ("expand", "count", "describe", "scan", "common")


@dataclass(frozen=True)
class TypedHop:
    """One hop of a typed path: a card relation, its direction, the label it reaches."""

    relation: str
    direction: str
    target_label: str

    def to_dict(self) -> dict[str, Any]:
        return {"relation": self.relation, "direction": self.direction, "target_label": self.target_label}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TypedHop":
        return cls(str(data.get("relation") or ""), str(data.get("direction") or ""),
                   str(data.get("target_label") or ""))


@dataclass(frozen=True)
class TypedStep:
    """A validated typed request: everything the builder needs, no English.

    ``anchor_ids`` are entity ids (from ``resolve_entity`` or written by the
    planner and checked); ``hops`` is the path from the anchor, every hop
    checked against the catalog's option rules; ``depth`` repeats a single
    repeating hop; ``filter`` is ``(property, value)`` on the last hop's label.
    """

    kind: str
    anchor_label: str = ""
    anchor_ids: tuple[str, ...] = ()
    hops: tuple[TypedHop, ...] = ()
    depth: int = 1
    filter: tuple[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "anchor_label": self.anchor_label,
                               "anchor_ids": list(self.anchor_ids),
                               "hops": [h.to_dict() for h in self.hops], "depth": self.depth}
        if self.filter is not None:
            out["filter"] = {"property": self.filter[0], "value": self.filter[1]}
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TypedStep":
        flt = data.get("filter")
        return cls(
            kind=str(data.get("kind") or "expand"),
            anchor_label=str(data.get("anchor_label") or ""),
            anchor_ids=tuple(str(x) for x in data.get("anchor_ids") or ()),
            hops=tuple(TypedHop.from_dict(h) for h in data.get("hops") or ()),
            depth=int(data.get("depth") or 1),
            filter=(str(flt.get("property")), str(flt.get("value"))) if isinstance(flt, dict) else None,
        )

    def entities(self) -> list[str]:
        """The card names the step touches, in path order (anchor, rel, label, ...)."""
        out = [self.anchor_label] if self.anchor_label else []
        for h in self.hops:
            out += [h.relation, h.target_label]
        return [e for e in dict.fromkeys(out) if e]


@dataclass(frozen=True)
class TaskSignals:
    """Everything the specialists may know about the question's wording."""

    #: ``utils.planner.intent.asks_for_bulk_scan``: a request for a whole label.
    bulk_scan: bool = False
    #: ``utils.planner.intent.is_definitional_request``: "what is X" / describe.
    definitional: bool = False
    #: ATT&CK technique ids (``extract_attack_ids``).
    attack_ids: tuple[str, ...] = ()
    #: CAPEC ids, normalised to ``CAPEC-N``.
    capec_ids: tuple[str, ...] = ()
    #: CWE ids, normalised to ``CWE-N``.
    cwe_ids: tuple[str, ...] = ()
    #: Every ATT&CK id family (T/TA/M/G/S/DET/DC/C), the ATT&CK seed priority.
    attack_seed_ids: tuple[str, ...] = ()
    #: ``utils.specialists.concepts.concept_terms``.
    concept_terms: tuple[str, ...] = ()
    #: The raw strings each name-extraction pass found (``name_term_candidates``);
    #: the card's schema words filter them in the resolver.
    name_candidates: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: Lower-cased ``[a-z0-9]+`` tokens, in order: all the name index reads.
    name_tokens: tuple[str, ...] = ()
    #: One-word index names the text writes as a standalone proper noun. Only
    #: filled when ``ARIADNE_EXACT_NAME_DISTINCT=struct`` (off by default).
    proper_nouns: tuple[str, ...] = ()
    #: ``canonical._question_words``: the words a property name is matched on.
    question_words: tuple[str, ...] = ()
    #: Registry-observed property values the text writes (``_value_in_text``).
    mentioned_values: tuple[str, ...] = ()
    #: A typed step from the typed planner (EXP-2026-11-015 item 6), or ``None``.
    #: When present the builders execute it instead of reading the lexical
    #: fields; ``None`` (every rules-path task) changes nothing and is omitted
    #: from ``to_dict``.
    step: "TypedStep | None" = None

    @property
    def name_text(self) -> str:
        """The tokens rejoined: re-tokenises to exactly ``name_tokens``."""
        return " ".join(self.name_tokens)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"bulk_scan": self.bulk_scan, "definitional": self.definitional}
        for key in _TUPLE_FIELDS:
            out[key] = list(getattr(self, key))
        out["name_candidates"] = {k: list(v) for k, v in self.name_candidates.items()}
        if self.step is not None:
            out["step"] = self.step.to_dict()
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskSignals":
        return cls(
            bulk_scan=bool(data.get("bulk_scan", False)),
            definitional=bool(data.get("definitional", False)),
            name_candidates={
                str(k): tuple(str(x) for x in v)
                for k, v in (data.get("name_candidates") or {}).items()
            },
            step=TypedStep.from_dict(data["step"]) if isinstance(data.get("step"), dict) else None,
            **{key: tuple(str(x) for x in data.get(key) or ()) for key in _TUPLE_FIELDS},
        )


def id_signals(text: str) -> TaskSignals:
    """Only the identifier fields — for callers that need nothing else."""
    from .resolve import (
        _extract_attack_seed_ids,
        extract_attack_ids,
        extract_capec_ids,
        extract_cwe_ids,
    )

    return TaskSignals(
        attack_ids=extract_attack_ids(text),
        capec_ids=extract_capec_ids(text),
        cwe_ids=extract_cwe_ids(text),
        attack_seed_ids=_extract_attack_seed_ids(text),
    )


def _mentioned_values(text: str) -> tuple[str, ...]:
    """Every value the schema registry observed that ``text`` writes as a value."""
    try:
        from utils.planner.canonical import _value_in_text
        from utils.specialists.schema import get_registry

        registry = get_registry()
        values: set[str] = set()
        for name in registry.dataset_names():
            schema = registry.dataset(name)
            for props in (getattr(schema, "label_value_vocabulary", None) or {}).values():
                for observed in props.values():
                    values.update(observed)
    except Exception:  # noqa: BLE001 — no registry: the builder binds no filter either
        return ()
    # A value's first word must occur in the text verbatim for the pattern to
    # match at all, so the substring test only skips certain misses.
    return tuple(sorted(
        v for v in values if v.split() and v.split()[0] in text and _value_in_text(v, text)
    ))


def _proper_nouns(text: str) -> tuple[str, ...]:
    """One-word index names ``text`` writes as names (``struct`` mode only)."""
    from .schema import namesearch

    if namesearch._distinct_mode() != "struct":  # noqa: SLF001 — same package
        return ()
    graphs = namesearch.REPO / "data" / "graphs"
    names: set[str] = set()
    for ds_dir in sorted(graphs.iterdir()) if graphs.exists() else ():
        for _id, _label, name, _toks in namesearch.index_for(ds_dir.name)._docs:  # noqa: SLF001
            if len(namesearch._WORD_RE.findall(name.lower())) == 1:  # noqa: SLF001
                names.add(name.strip())
    # The name must occur verbatim for the test to pass, so the substring check
    # only skips certain misses.
    return tuple(sorted(
        n for n in names if n in text and namesearch._standalone_proper_noun(n, text)  # noqa: SLF001
    ))


def step_signals(step: TypedStep) -> TaskSignals:
    """Signals for a typed step: the step itself, plus the id families of its anchors.

    No lexical field is filled. The id fields are read from the anchor ids alone
    (never from a question), so the resolver's native-id priority sees what the
    step names and nothing else.
    """
    ids = id_signals(" ".join(step.anchor_ids))
    return TaskSignals(
        bulk_scan=step.kind == "scan",
        definitional=step.kind == "describe",
        attack_ids=ids.attack_ids,
        capec_ids=ids.capec_ids,
        cwe_ids=ids.cwe_ids,
        attack_seed_ids=ids.attack_seed_ids,
        step=step,
    )


def derive_signals(text: str) -> TaskSignals:
    """Read the question once. The only function here that sees English."""
    from utils.planner.canonical import _question_words
    from utils.planner.intent import asks_for_bulk_scan, is_definitional_request

    from .concepts import concept_terms
    from .resolve import name_term_candidates
    from .schema.namesearch import _WORD_RE

    text = text or ""
    ids = id_signals(text)
    return TaskSignals(
        bulk_scan=asks_for_bulk_scan(text),
        definitional=is_definitional_request(text),
        attack_ids=ids.attack_ids,
        capec_ids=ids.capec_ids,
        cwe_ids=ids.cwe_ids,
        attack_seed_ids=ids.attack_seed_ids,
        concept_terms=concept_terms(text),
        name_candidates=name_term_candidates(text),
        name_tokens=tuple(_WORD_RE.findall(text.lower())),
        proper_nouns=_proper_nouns(text),
        question_words=tuple(sorted(_question_words(text))),
        mentioned_values=_mentioned_values(text),
    )


__all__ = ["STEP_KINDS", "TaskSignals", "TypedHop", "TypedStep", "derive_signals", "id_signals", "step_signals"]
