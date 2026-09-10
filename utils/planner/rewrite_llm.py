#!/usr/bin/env python3
"""The one place a model touches the rewrite stage — and all it may do is choose.

EXP-2026-08-020 measured what happens when a model is given the question and let
loose on the schema: the LLM drafter cost -0.1185 against the deterministic one,
and a free-form query arm reached 0.50 record identity where the deterministic
engine reaches 1.0000. This seam is different in *kind*, not degree. The model is
handed the question and a set of numbered lists, and its entire output is a set
of **indices into those lists**. It cannot name a source, choose a hop, write a
query, or emit an identifier that is not on the list it was given.

Three things enforce that, and no one of them is enough alone:

1. The prompt asks for indices, not names.
2. :func:`_pick` refuses anything that is not an ``int`` in range — a model that
   returns ``"MITIGATES"`` has written a name that happens to be on the list,
   which is not the same as having chosen from it.
3. :func:`utils.planner.canonical.gate_form` re-checks the finished form against
   the same closed world, so a bug in 1 or 2 abstains rather than ships.

The model may also decline. ``"ambiguous": true`` abstains and says so, which is
the honest answer when a paraphrase fits three patterns equally — and abstention
is the behaviour this project's value proposition rests on.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from utils.llm import LLMUnavailable
from utils.llm import chat as llm_chat
from utils.llm import probe as llm_probe
from utils.llm_sampling import sampling_params

from .canonical import (
    MODES,
    SLOT_ANCHORS,
    SLOT_ANCHOR_LABELS,
    SLOT_DATASETS,
    SLOT_DIRECTION,
    SLOT_RELATION,
    SLOT_TARGET_LABELS,
    CandidateLists,
    IntentForm,
    candidate_lists_all,
    direction_for,
    gate_form,
    relations_between,
)
from .cards import SourceCardView
from .llm_drafter import extract_json_object
from .rewrite_cache import CacheEntry, RewriteCache, cache_key

logger = logging.getLogger("ariadne.planner.rewrite")

#: Bumped whenever the prompt changes in a way that could change a pick. It is
#: part of the cache key, so an old run's choices are never served for a new
#: prompt — which would silently mix two experiments.
PROMPT_VERSION = "rewrite-v1"

#: A reasoning model spends tokens before it emits anything, and a small budget
#: truncates it to empty — which the pipeline then reports as "LLM unavailable"
#: and nobody looks further (D-030). The output here is a handful of integers;
#: the budget is almost entirely for the thinking in front of them.
MIN_MAX_TOKENS = 2048


class RewriteUnavailable(Exception):
    """Raised when the endpoint cannot produce a usable set of choices.

    Mirrors :class:`~utils.planner.llm_drafter.DrafterUnavailable`: the stage
    never grades itself, and every transport, HTTP, budget or parse failure ends
    here so the caller falls back to the deterministic form.
    """


_SYSTEM_PROMPT = """\
You translate a security analyst's question into a fixed form by CHOOSING FROM \
NUMBERED LISTS. You never write queries, never name a data source, and never \
invent an identifier, label or relationship.

Your entire output is one JSON object whose values are INTEGERS taken from the \
lists you are shown, plus the two flags below. Any value that is not an integer \
from a list will be discarded.

All three indices must come from the SAME source block. Picking an anchor from one source and a relationship from another is not a question anything can answer.

Fields (every one optional — omit a field you cannot choose):
  "anchor":       index into ANCHOR CANDIDATES — the one entity the question is \
about.
  "relation":     index into RELATIONSHIPS — the edge the question asks to \
follow.
  "target_label": index into NODE LABELS — the kind of thing the answer should \
be.
  "mode":         one of "describe", "enumerate", "count".
  "ambiguous":    true if the question could equally be about more than one \
anchor candidate, or if none of them is what it is about. Prefer this to a \
guess: an honest "I cannot tell" is a correct answer here and a confident wrong \
one is not.
  "why":          one short sentence naming the words in the question that made \
you choose. No more than 25 words.

Reply with the JSON object and nothing else.\
"""


@dataclass(frozen=True)
class RewriteChoice:
    """What the model returned, before any of it is believed."""

    anchor: Any = None
    relation: Any = None
    target_label: Any = None
    mode: Any = None
    ambiguous: bool = False
    why: str = ""
    served_model: str = ""
    cache_hit: bool = False
    raw: dict[str, Any] | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any], **extra: Any) -> "RewriteChoice":
        return cls(
            anchor=payload.get("anchor"),
            relation=payload.get("relation"),
            target_label=payload.get("target_label"),
            mode=payload.get("mode"),
            ambiguous=bool(payload.get("ambiguous")),
            why=str(payload.get("why") or "")[:200],
            raw=payload,
            **extra,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "anchor": self.anchor,
            "relation": self.relation,
            "target_label": self.target_label,
            "mode": self.mode,
            "ambiguous": self.ambiguous,
            "why": self.why,
        }


# -- the prompt -------------------------------------------------------------


def _render_list(title: str, choices: tuple[Any, ...], *, limit: int | None = None) -> str:
    shown = choices[:limit] if limit else choices
    if not shown:
        return ""
    lines = [f"{title}:"]
    for choice in shown:
        label = f" [{choice.label}]" if getattr(choice, "label", "") else ""
        name = f" {choice.name}" if getattr(choice, "name", "") else ""
        gloss = f" — {choice.gloss}" if getattr(choice, "gloss", "") else ""
        lines.append(f"  {choice.index}. {choice.value}{label}{name}{gloss}")
    return "\n".join(lines)


def build_prompt(
    question: str,
    form: IntentForm,
    lists: dict[str, CandidateLists],
) -> str:
    """The user message: the question, what is already known, and the lists.

    What the deterministic pass already bound is shown as *settled*, not offered
    as a choice. A slot that is bound is not a decision the model gets to revisit
    — that would put a 68%-precision opinion in front of a lookup.
    """
    blocks: list[str] = [f"QUESTION: {question.strip()}"]

    settled: list[str] = []
    if form.anchors:
        settled.append(f"anchor = {', '.join(form.anchors)}")
    if form.anchor_labels:
        settled.append(f"anchor type = {', '.join(form.anchor_labels)}")
    if form.target_labels and SLOT_TARGET_LABELS not in form.unbound:
        settled.append(f"answer type = {', '.join(form.target_labels)}")
    if form.relation and SLOT_RELATION not in form.unbound:
        settled.append(f"relationship = {form.relation}")
    if settled:
        blocks.append("ALREADY DETERMINED (do not choose these again):\n  " + "\n  ".join(settled))

    needed = [s for s in (SLOT_ANCHORS, SLOT_RELATION, SLOT_TARGET_LABELS) if s in form.unbound]
    blocks.append("CHOOSE: " + (", ".join(needed) if needed else "nothing outstanding"))

    for dataset in sorted(lists):
        candidates = lists[dataset]
        parts = [f"--- source: {dataset} ---"]
        if SLOT_ANCHORS in form.unbound and candidates.anchors:
            parts.append(_render_list("ANCHOR CANDIDATES", candidates.anchors))
        if SLOT_RELATION in form.unbound:
            parts.append(_render_list("RELATIONSHIPS", candidates.relations))
        if SLOT_TARGET_LABELS in form.unbound:
            parts.append(_render_list("NODE LABELS", candidates.labels))
        block = "\n".join(p for p in parts if p)
        if block.count("\n"):
            blocks.append(block)

    return "\n\n".join(blocks)


# -- the transport ----------------------------------------------------------


#: Identity probes, one per (endpoint, alias, provider). Probed once per process
#: because it is part of every cache key and an alias is not a model.
_SERVED: dict[tuple[str, str, str], str] = {}


def served_model(settings: Any) -> str:
    """The weights that actually answer, read off a response envelope.

    Never the alias: `skynet` has pointed at three different architectures over
    this project's life and nothing noticed for weeks (D-028). Asked through
    :func:`utils.llm.probe`, which never raises and whose budget is already sized
    so a reasoning model does not spend the whole thing thinking and return
    empty. A probe that fails yields ``model + "?"`` — visibly unverified, so a
    manifest built from it cannot quietly claim an identity nobody checked.
    """
    key = (settings.base_url, settings.model, getattr(settings, "provider", ""))
    cached = _SERVED.get(key)
    if cached:
        return cached
    result = llm_probe(settings)
    identity = (result.model or "").strip() if result.ok else ""
    if not identity:
        logger.warning(
            "could not identify the weights behind %r at %s: %s",
            settings.model, settings.base_url, result.reason or "no model in the envelope",
        )
        identity = f"{settings.model}?"
    _SERVED[key] = identity
    return identity


def choose(
    question: str,
    form: IntentForm,
    cards: dict[str, SourceCardView],
    settings: Any,
    *,
    lists: dict[str, CandidateLists] | None = None,
    cache: RewriteCache | None = None,
    client: Any = None,
) -> tuple[RewriteChoice, dict[str, CandidateLists]]:
    """Ask the model to fill the outstanding slots by choosing from the lists.

    ``client`` is the seam the tests drive: any callable with :func:`chat`'s
    signature. Returns the raw choice *and* the lists it was offered, because the
    caller needs both to apply and to gate.
    """
    lists = lists if lists is not None else candidate_lists_all(question, form, cards)
    cache = cache or RewriteCache()
    call = client or llm_chat

    identity = served_model(settings) if client is None else getattr(settings, "model", "test")
    key = cache_key(PROMPT_VERSION, identity, question)
    hit = cache.get(key)
    if hit is not None:
        return (
            RewriteChoice.from_payload(hit.payload, served_model=identity, cache_hit=True),
            lists,
        )

    budget = max(int(getattr(settings, "max_tokens", 0) or 0), MIN_MAX_TOKENS)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": build_prompt(question, form, lists)},
    ]
    try:
        result = call(
            settings,
            messages,
            max_tokens=budget,
            sampling=sampling_params(
                max_tokens=budget,
                thinking_budget=getattr(settings, "thinking_budget", None),
            ),
        )
    except LLMUnavailable as exc:
        raise RewriteUnavailable(str(exc)) from exc
    if not result.content:
        raise RewriteUnavailable(
            "model returned no content"
            + (" — it was cut off at its output budget" if result.truncated else "")
        )
    try:
        payload = extract_json_object(result.content)
    except Exception as exc:  # DrafterUnavailable and JSON errors alike
        raise RewriteUnavailable(f"could not parse the model's choice: {exc}") from exc

    identity = (result.model or identity) if client is None else identity
    cache.put(
        CacheEntry(
            key=key,
            prompt_version=PROMPT_VERSION,
            served_model=identity,
            question=question,
            payload=payload,
        )
    )
    return RewriteChoice.from_payload(payload, served_model=identity, cache_hit=False), lists


# -- applying a choice ------------------------------------------------------


def _pick(choices: tuple[Any, ...], index: Any) -> Any:
    """``choices[index]`` for a genuine ``int`` index, else ``None``."""
    if isinstance(index, bool) or not isinstance(index, int):
        return None
    return choices[index] if 0 <= index < len(choices) else None


def apply_choice(
    form: IntentForm,
    choice: RewriteChoice,
    lists: dict[str, CandidateLists],
    cards: dict[str, SourceCardView],
    *,
    registry: Any = None,
    derive_relation: bool = True,
) -> tuple[IntentForm, list[str]]:
    """Fold ``choice`` into ``form``, and say what was rejected and why.

    Every returned form is still subject to :func:`gate_form`. This function is
    permissive on purpose about *which* list an index came from — the gate is the
    authority — but strict about the index being an index.
    """
    from dataclasses import replace

    rejected: list[str] = []
    if choice.ambiguous:
        return form, ["the model declined: ambiguous"]

    datasets = [d for d in form.datasets if d in lists] or sorted(lists)
    anchors = form.anchors
    anchor_labels = form.anchor_labels
    target_labels = form.target_labels
    relation = form.relation
    resolved_ds = form.datasets
    sources = dict(form.sources)
    filled: set[str] = set()

    if SLOT_ANCHORS in form.unbound and choice.anchor is not None:
        found = None
        for dataset in datasets:
            candidate = _pick(lists[dataset].anchors, choice.anchor)
            if candidate is not None:
                found = (dataset, candidate)
                break
        if found is None:
            rejected.append(f"anchor index {choice.anchor!r} is not an index into any list")
        else:
            dataset, candidate = found
            anchors = (candidate.value,)
            anchor_labels = (candidate.label,) if candidate.label else anchor_labels
            # The source that owns the chosen anchor leads, exactly as it does on
            # the deterministic path.
            resolved_ds = (dataset,) + tuple(d for d in form.datasets if d != dataset)
            sources[SLOT_ANCHORS] = "model"
            sources[SLOT_ANCHOR_LABELS] = "model:anchor-candidate"
            filled.update({SLOT_ANCHORS, SLOT_ANCHOR_LABELS})

    lead = resolved_ds[0] if resolved_ds else (datasets[0] if datasets else "")

    if SLOT_TARGET_LABELS in form.unbound and choice.target_label is not None and lead in lists:
        candidate = _pick(lists[lead].labels, choice.target_label)
        if candidate is None:
            rejected.append(
                f"target label index {choice.target_label!r} is not an index into the list"
            )
        else:
            target_labels = (candidate.value,)
            sources[SLOT_TARGET_LABELS] = "model"
            filled.add(SLOT_TARGET_LABELS)

    # The relation is the model's worst slot and the schema's easiest fact. An
    # anchor label and a target label pin it for 16 of CAPEC's 17 declared label
    # pairs and for all 19 of ATT&CK's, so where the pair pins it the model is not
    # asked; its index is consulted only when the pair is ambiguous or undeclared,
    # and even then the pick must be one the pair allows. This is the rule
    # ``direction`` has always followed, applied one slot over.
    if SLOT_RELATION in form.unbound:
        derived: tuple[str, ...] = ()
        if derive_relation and anchor_labels and target_labels and lead:
            derived = relations_between(
                anchor_labels[0], target_labels[0], lead, registry=registry
            )
        if len(derived) == 1:
            relation = derived[0]
            sources[SLOT_RELATION] = "schema-registry"
            filled.add(SLOT_RELATION)
        elif choice.relation is not None and lead in lists:
            candidate = _pick(lists[lead].relations, choice.relation)
            if candidate is None:
                rejected.append(
                    f"relation index {choice.relation!r} is not an index into the list"
                )
            elif derived and candidate.value not in derived:
                rejected.append(
                    f"relation {candidate.value!r} is not declared between "
                    f"{anchor_labels[0]!r} and {target_labels[0]!r}"
                )
            else:
                relation = candidate.value
                sources[SLOT_RELATION] = "model"
                filled.add(SLOT_RELATION)

    mode = form.mode
    if choice.mode is not None:
        if isinstance(choice.mode, str) and choice.mode in MODES:
            mode = choice.mode
            sources["mode"] = "model"
        else:
            rejected.append(f"mode {choice.mode!r} is not one of {list(MODES)}")

    # Direction is never the model's to choose. It is read from the declared
    # endpoints, which is the only place it is knowable, and a relation whose
    # direction cannot be resolved stays unbound.
    direction = form.direction
    if relation and anchor_labels and resolved_ds:
        direction = direction_for(
            anchor_labels[0],
            relation,
            target_labels[0] if target_labels else None,
            resolved_ds[0],
            registry=registry,
        )
        if direction:
            sources[SLOT_DIRECTION] = "schema-registry"
        else:
            rejected.append(
                f"relation {relation!r} is not declared from {anchor_labels[0]!r} "
                "in either direction"
            )
            relation = form.relation if SLOT_RELATION not in filled else None
            filled.discard(SLOT_RELATION)

    if direction:
        filled.add(SLOT_DIRECTION)
    remaining = tuple(s for s in form.unbound if s not in filled)
    if SLOT_ANCHORS in filled:
        # Filling the anchor also settles which source the question is about,
        # because the anchor's owner leads.
        remaining = tuple(s for s in remaining if s != SLOT_DATASETS)
    updated = replace(
        form,
        anchors=anchors,
        anchor_labels=anchor_labels,
        target_labels=target_labels,
        relation=relation,
        direction=direction,
        mode=mode,
        datasets=resolved_ds,
        unbound=remaining,
        sources=sources,
    )
    return updated, rejected


def fill(
    question: str,
    form: IntentForm,
    cards: dict[str, SourceCardView],
    settings: Any,
    *,
    lists: dict[str, CandidateLists] | None = None,
    cache: RewriteCache | None = None,
    client: Any = None,
    registry: Any = None,
) -> tuple[IntentForm, dict[str, Any]]:
    """Ask, apply, gate. Returns the form and a trace of what happened.

    The trace is the deliverable as much as the form: the answer record has to be
    able to say which rung answered, on which weights, from cache or not, and —
    when it abstained — on what grounds.
    """
    if form.is_bound:
        # Nothing outstanding. Consulting the model here would spend a call to
        # be told what a lookup already established, and would put a choice in
        # front of a fact — which is the one thing this design does not do. It
        # also keeps the model-consulted rate honest: it is the share of
        # questions the deterministic path could not finish, not of all of them.
        return form, {
            "rung": "deterministic",
            "cache_hit": False,
            "served_model": "",
            "rejected": [],
            "gate": None,
            "why": "",
        }

    trace: dict[str, Any] = {
        "rung": "model",
        "cache_hit": False,
        "served_model": "",
        "rejected": [],
        "gate": None,
        "why": "",
    }
    try:
        choice, lists = choose(
            question, form, cards, settings, lists=lists, cache=cache, client=client
        )
    except RewriteUnavailable as exc:
        trace["rung"] = "abstain"
        trace["rejected"] = [f"model unavailable: {exc}"]
        return form, trace

    trace["cache_hit"] = choice.cache_hit
    trace["served_model"] = choice.served_model
    trace["why"] = choice.why

    filled, rejected = apply_choice(
        form,
        choice,
        lists,
        cards,
        registry=registry,
        derive_relation=bool(getattr(settings, "rewrite_derive_relation", True)),
    )
    trace["rejected"] = rejected
    if choice.ambiguous:
        trace["rung"] = "abstain"
        return form, trace

    verdict = gate_form(filled, lists, cards, registry=registry)
    trace["gate"] = verdict.to_dict()
    if not verdict.passed:
        trace["rung"] = "abstain"
        return form, trace
    return filled, trace
