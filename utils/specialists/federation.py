#!/usr/bin/env python3
"""Weave the specialists into the planner workflow.

The planner emits a machine-readable ``Plan`` (sub-questions routed to sources,
declared joins, unsupported parts). This module dispatches each sub-question to
the specialist that serves its source, runs it, and collects the normalised
evidence into a single bundle keyed for the (future) synthesis agent.

The handoff is **evidence, not prose** (briefing §3): the federation gathers
each specialist's validated query, normalised records, grounded summary, and
provenance, and builds a ``join_index`` over the shared join key — but it does
**not** perform the cross-source join or compose a final answer. That is the
synthesis agent's job, kept deliberately out of scope here.
"""

from __future__ import annotations

import dataclasses

from dataclasses import dataclass, field
from typing import Any, Sequence

from utils.planner.cards import SourceCardView, load_source_cards
from utils.planner.join_keys import get_join_key
from utils.planner.schema import Plan, SubQuestion

from . import build_specialist
from .config import SpecialistConfig
from .contracts import EvaluatorTrace, SpecialistResult, SpecialistTask


@dataclass
class FederatedEvidence:
    """All specialist evidence for one planned request, ready for synthesis."""

    request: str
    results: list[SpecialistResult] = field(default_factory=list)
    unsupported: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    partial: bool = False
    # Dependent-sequencing audit trail: one entry per consumer sub-question
    # that was seeded from (or skipped because of) a producer's join values.
    sequencing: list[dict[str, Any]] = field(default_factory=list)

    def by_source(self) -> dict[str, list[SpecialistResult]]:
        out: dict[str, list[SpecialistResult]] = {}
        for result in self.results:
            out.setdefault(result.task.source, []).append(result)
        return out

    def join_index(self) -> dict[str, list[dict[str, str]]]:
        """Map each join-key value to the (source, record) entries that carry it.

        This is the synthesis spine: a join value present under two different
        sources is a candidate cross-source correlation. The federation only
        *indexes* it; the synthesis agent decides what to do with it.
        """
        index: dict[str, list[dict[str, str]]] = {}
        for result in self.results:
            for record in result.records:
                for value in record.join_values:
                    index.setdefault(value, []).append(
                        {
                            "source": result.task.source,
                            "primary_id": record.primary_id,
                            "name": record.name,
                        }
                    )
        return index

    def cross_source_join_values(self) -> list[str]:
        """Join values reported by more than one distinct source."""
        out: list[str] = []
        for value, entries in self.join_index().items():
            if len({e["source"] for e in entries}) > 1:
                out.append(value)
        return sorted(out)

    def ok(self) -> bool:
        return bool(self.results) and all(r.ok for r in self.results) and not self.partial

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "results": [r.to_dict() for r in self.results],
            "unsupported": list(self.unsupported),
            "skipped": list(self.skipped),
            "partial": self.partial,
            "sequencing": list(self.sequencing),
            "join_index": self.join_index(),
            "cross_source_join_values": self.cross_source_join_values(),
        }


# -- dependent sequencing (join-derived ordering) ---------------------------
#
# The proposal's flagship flow is dependent: "retrieve mitigations FOR THOSE
# IDS" — the ATT&CK task consumes the T-IDs the CAPEC task produces. Ordering
# is derived from the declared join's canonical key, never invented: the
# endpoint that reaches the key via a mapping edge (``via_edge``) *produces*
# join values; the endpoint whose records natively carry the key *consumes*
# them as seed ids. With exactly two endpoints the dependency is acyclic by
# construction. Independent sub-questions keep the existing order unchanged.


#: Words with which a sub-question points back at the one before it. Deliberately
#: narrow: "it"/"its" are excluded because a hop that names its own anchor uses
#: them too ("the patterns that correspond to it"), and that hop is not a
#: consumer.
_ANAPHORA = ("those", "these", "them", "their", "each of", "the resulting")


def refers_back(sq: SubQuestion) -> bool:
    """Does this sub-question's text point at the previous hop's result?

    "For each of THOSE: the CWE weaknesses each of those exploits" cannot be
    executed on its own — it has no anchor until the hop before it supplies one.
    That is what makes it a consumer, and it is stated in the plan's own words
    rather than derived from a join key whose direction is declared once and
    fixed.
    """
    text = (getattr(sq, "text", "") or "").lower()
    return any(word in text for word in _ANAPHORA)


def dependency_map(plan: Plan) -> dict[str, tuple[str, ...]]:
    """Map consumer sub-question id -> **every** producer it depends on.

    A tuple rather than a single id, because with three sources a consumer can
    sit at the end of two declared joins at once. ATT&CK is the consuming end of
    both ``attack-technique-id`` (CAPEC produces) and ``identity-edge-technique``
    (identity produces), and a plan that routes to all three declares both. This
    returned ``dict[str, str]`` and assigned by last-write-wins, so whichever
    join happened to be second silently replaced the first: identity produced
    ``T1649`` correctly, ATT&CK was assigned to CAPEC instead, CAPEC yielded no
    join values, and ATT&CK ran unseeded and returned nothing. The bridge worked
    and the wiring discarded it.

    Order within the tuple is the plan's join order, so seeding is
    deterministic. Still acyclic: producers and consumers are decided by the
    key's endpoints, not by the plan.
    """
    by_source: dict[str, SubQuestion] = {sq.source: sq for sq in plan.sub_questions}
    deps: dict[str, list[str]] = {}
    for join in plan.joins:
        key = get_join_key(join.key)
        if key is None:
            continue
        producer_ds = consumer_ds = None
        for endpoint in key.endpoints:
            # `produces` covers both ways an endpoint derives key values: by
            # walking a mapping edge to reach them, and by holding an edge whose
            # TYPE corresponds to one. The consumer is always the endpoint whose
            # records natively carry the key.
            if endpoint.produces:
                producer_ds = endpoint.dataset
            else:
                consumer_ds = endpoint.dataset
        producer = by_source.get(producer_ds or "")
        consumer = by_source.get(consumer_ds or "")
        if producer is not None and consumer is not None and producer.id != consumer.id:
            # The key's direction is declared once; a question can run either
            # way along it. `attack-technique-id` says CAPEC produces technique
            # ids and ATT&CK consumes them — right for "which techniques does
            # CAPEC-66 map to", backwards for "which CAPEC patterns correspond
            # to T1555, and which CWE weaknesses do those exploit", where the
            # ATT&CK hop holds the only identifier in the question and the CAPEC
            # hop says "each of THOSE".
            #
            # One side naming its own anchors while the other names none settles
            # it: a hop with nothing to start from cannot feed a hop that is
            # already anchored. Both self-anchored or neither leaves the
            # declared direction untouched, so the forward case is unchanged.
            if carries_its_own_seeds(consumer) and not carries_its_own_seeds(producer):
                producer, consumer = consumer, producer
            found = deps.setdefault(consumer.id, [])
            if producer.id not in found:
                found.append(producer.id)
    # A join between two hops that live in the SAME source declares nothing
    # here: `by_source` is keyed by source name, so the second hop overwrites
    # the first and the join's endpoints collapse onto one sub-question. Every
    # D6 question's second hop returned zero records for this reason, and so
    # does a two-step question inside one catalogue — the shape that holds the
    # largest single block of remaining loss (`EXP-2026-09-018`).
    #
    # Plan order supplies what the key cannot, for a sub-question that says in
    # its own words that it depends on the one before it — "the CWE weaknesses
    # each of THOSE exploits" (`refers_back`). Without this it runs unanchored,
    # which is a label scan: the catalogue-dump failure, not an answer. A
    # sub-question that names its own anchor, or that points at nothing, is
    # never given a producer here, so an independent pair is unaffected.
    #
    # A sub-question the key already made a PRODUCER is never given a producer
    # of its own here: the declared join has already placed it, and adding the
    # plan-order edge on top would close a two-question cycle and destroy the
    # ordering the key established.
    produces = {pid for pids in deps.values() for pid in pids}
    for earlier, sq in zip(plan.sub_questions, plan.sub_questions[1:]):
        if sq.id in deps or sq.id in produces or carries_its_own_seeds(sq):
            continue
        if not refers_back(sq):
            continue  # two independent asks, not a chain
        deps[sq.id] = [earlier.id]
    return {consumer: tuple(producers) for consumer, producers in deps.items()}


def execution_order(plan: Plan) -> list[SubQuestion]:
    """Plan order with each join's producer hoisted before its consumer."""
    deps = dependency_map(plan)
    ordered: list[SubQuestion] = []
    placed: set[str] = set()
    by_id = {sq.id: sq for sq in plan.sub_questions}

    def place(sq: SubQuestion) -> None:
        if sq.id in placed:
            return
        placed.add(sq.id)  # guards the recursion before descending
        for producer_id in deps.get(sq.id, ()):
            if producer_id in by_id:
                place(by_id[producer_id])
        ordered.append(sq)

    for sq in plan.sub_questions:
        place(sq)
    return ordered


def harvest_seed_ids(
    producer: SpecialistResult | Sequence[SpecialistResult],
    *,
    cap: int,
    prefer_primary_ids: bool = False,
    wanted_labels: Sequence[str] = (),
) -> tuple[tuple[str, ...], bool]:
    """The producers' join values as consumer seeds, deterministic and bounded.

    Accepts one producer or several: a consumer at the end of two declared joins
    is seeded from the union, because dropping either half would answer a
    narrower question than the plan asked.

    Returns ``(seed_ids, truncated)``. Truncation is honest — it is recorded in
    the sequencing audit trail, never silent — and keeps the consumer's query
    inside its own ``max_result_rows`` bound.
    """
    producers = [producer] if isinstance(producer, SpecialistResult) else list(producer)
    if prefer_primary_ids:
        # Which of the producer's ids the consumer anchors on is decided by the
        # LABEL it names, not by where the id sits in the record. "Which attack
        # patterns sit inside the Software category, and what techniques does
        # each of those correspond to" leaves one record whose primary id is the
        # CATEGORY and whose 52 related entries are the patterns; seeding the
        # second hop with the category sends it back to where it started.
        wanted = set(wanted_labels)
        if wanted:
            picked = {
                rid
                for p in producers
                for r in p.records
                for rid, label in (
                    [(r.primary_id, r.label)]
                    + [(x.get("id"), x.get("label")) for x in r.related]
                )
                if rid and label in wanted
            }
            if picked:
                values = sorted(picked)
                if cap and len(values) > cap:
                    return tuple(values[:cap]), True
                return tuple(values), False
        # The producer and the consumer ended up in the SAME store, so the
        # cross-source key is not what links them: the consumer anchors on the
        # producer's own records. "Which CAPEC patterns correspond to T1555, and
        # which CWE weaknesses do those exploit" resolves both hops inside CAPEC
        # once the first is routed there, and the second hop needs the pattern
        # ids the first returned — its join values are the ATT&CK ids it was
        # seeded with, which would send it back where it started.
        values = sorted({r.primary_id for p in producers for r in p.records if r.primary_id})
    else:
        values = sorted({v for p in producers for r in p.records for v in r.join_values})
    if cap and len(values) > cap:
        return tuple(values[:cap]), True
    return tuple(values), False


def reroute_source(
    sq: SubQuestion, cards: dict[str, Any]
) -> str | None:
    """The source that models this sub-question's entities, when its own does not.

    Routing is a structural question and the source card answers it: a card
    either declares a label or relationship type or it does not
    (:meth:`SourceCardView.unknown_entities`). When the assigned card models
    none of what the sub-question names, and exactly one other loaded card
    models **all** of it, the sub-question belongs to that card.

    This is the routing half of the reversed-join fault. "Which CAPEC attack
    patterns correspond to T1555" names ``MAPS_TO`` and ``AttackPattern``;
    ATT&CK models neither, so the specialist refuses at its schema boundary and
    returns nothing, and the dependent second hop is then skipped for want of
    seeds. Every one of the 27 federated development questions had its second
    hop return zero records for this reason (`EXP-2026-09-018`, I-11).

    The test is comparative, not all-or-nothing, because a cross-catalogue hop
    names entities from both sides: "the CAPEC attack patterns that correspond
    to T1555" names ``Technique`` (ATT&CK's) as well as ``MAPS_TO`` and
    ``AttackPattern`` (CAPEC's), and NO single card models all three. The store
    that models the most of them is the one that can execute the hop; CAPEC
    holds the technique too, as a ``TaxonomyEntry``.

    Deliberately narrow. It fires only when the assigned card cannot express the
    whole sub-question, only when another card expresses strictly more of it,
    and only when that destination is unique — so it can only convert a
    boundary refusal into an attempt.

    Returns ``None`` when the assignment stands.
    """
    entities = list(getattr(sq, "entities", ()) or ())
    if not entities:
        return None
    # Structural routing is a property a card declares. A stand-in that does not
    # (the injected doubles in the orchestration tests) opts out, and the
    # sub-question stays exactly where the plan put it.
    modelled = {
        name: len(entities) - len(card.unknown_entities(entities))
        for name, card in cards.items()
        if callable(getattr(card, "unknown_entities", None))
    }
    if sq.source not in modelled:
        return None
    mine = modelled[sq.source]
    if mine == len(entities):
        return None  # its own store expresses the whole sub-question
    best = max(modelled.values())
    if best <= mine:
        return None  # nowhere better to send it
    winners = [name for name, n in modelled.items() if n == best]
    return winners[0] if len(winners) == 1 else None


def rerouted(sq: SubQuestion, cards: dict[str, Any]) -> SubQuestion | None:
    """``sq`` moved to the store that can execute it, or ``None`` to leave it.

    The moved sub-question carries only the entities its new card models. The
    ones left behind are the *other* catalogue's — ``Technique`` on a hop that
    asks CAPEC which patterns correspond to ``T1555`` — and the declared join
    key is exactly the bridge to them, so naming them would trip the
    specialist's schema-boundary refusal on the way to a question the store can
    in fact answer. Seeds and limits are untouched; nothing is invented.
    """
    entities = list(getattr(sq, "entities", ()) or ())
    moved = reroute_source(sq, cards)
    source = moved or sq.source
    card = cards.get(source)
    if card is None or not callable(getattr(card, "unknown_entities", None)):
        return None
    missing = card.unknown_entities(entities)
    # An entity the executing store does not model is normally a hard boundary:
    # answering with what the rest can express answers a different question. It
    # is not a boundary when the sub-question DECLARES A JOIN KEY and another
    # loaded store models the missing entity — that is precisely a hop across
    # the declared bridge, and `_generic_bridge` is the primitive that walks it.
    # "What ATT&CK techniques does each of those correspond to" names
    # ``Technique``, which CAPEC does not model as a label and does reach
    # through ``MAPS_TO``.
    bridgeable = bool(missing) and getattr(sq, "join_key", None) and all(
        any(
            name != source and other.has_entity(e)
            for name, other in cards.items()
        )
        for e in missing
    )
    if moved is None and not bridgeable:
        return None
    keep = [e for e in entities if card.has_entity(e)] if bridgeable else entities
    if not keep:
        return None
    return dataclasses.replace(sq, source=source, entities=keep)


def request_seeds(request: str, source: str) -> tuple[str, ...]:
    """Identifiers the ANALYST'S QUESTION names that ``source`` can anchor on.

    A last resort for a consumer whose producer yielded nothing, and a narrow
    one: the values come from the request verbatim, so nothing is invented, and
    a request naming no identifier returns an empty tuple and changes nothing.

    It exists because the join key's direction is declared once and a question
    can run either way along it. ``attack-technique-id`` says CAPEC produces and
    ATT&CK consumes, which is right for "which techniques does CAPEC-66 map to"
    and backwards for "which CAPEC patterns correspond to T1555" — where ATT&CK
    holds the seed and cannot answer, because it does not model ``MAPS_TO``.
    21 of the 27 federated development questions returned zero records for
    that reason.
    """
    from .resolve import extract_attack_ids, extract_capec_ids, extract_cwe_ids

    if source == "capec":
        return (
            extract_capec_ids(request)
            or extract_cwe_ids(request)
            or extract_attack_ids(request)
        )
    if source == "attack":
        return extract_attack_ids(request)
    return ()


def carries_its_own_seeds(sq: SubQuestion) -> bool:
    """Does this sub-question already name identifiers its own source can anchor on?

    A consumer is a sub-question that has nothing to start from until a producer
    hands it values. One that names ``T1555`` in its own text is not that, and
    must not be skipped when the "producer" it was assigned yields nothing.

    The assignment can be backwards, because `dependency_map` reads the join
    key's declared direction and that direction is fixed: CAPEC *produces*
    ATT&CK technique ids and ATT&CK *consumes* them. True for "which techniques
    does CAPEC-66 map to"; exactly backwards for "which CAPEC patterns
    correspond to T1555", where the ATT&CK side holds the seed. 21 of the 27
    federated development questions returned **zero records** for that reason —
    24% of the repaired arm's remaining judged loss (`EXP-2026-09-018`).

    Reading the text rather than re-deriving the join direction is the
    conservative repair: it can only let a sub-question run that would otherwise
    have been skipped unseeded, and a sub-question that names no identifier is
    unaffected.
    """
    if getattr(sq, "seed_ids", ()):  # the plan said so outright
        return True
    from .resolve import extract_attack_ids, extract_capec_ids, extract_cwe_ids

    text = getattr(sq, "text", "") or ""
    if sq.source == "attack":
        return bool(extract_attack_ids(text))
    if sq.source == "capec":
        return bool(extract_capec_ids(text) or extract_cwe_ids(text))
    return bool(
        extract_attack_ids(text) or extract_capec_ids(text) or extract_cwe_ids(text)
    )


def dependency_skip_result(
    task: SpecialistTask, *, producer_id: str, reason: str
) -> SpecialistResult:
    """An honest empty for a consumer whose producer yielded no join values.

    Mirrors the schema-boundary refusal shape: ok, zero records, NO query
    executed, the dependency named in the trace — so synthesis renders an
    abstention rather than the consumer running a broad unseeded query.
    """
    return SpecialistResult(
        task=task,
        query="",
        records=[],
        summary=(
            f"Skipped: this sub-question depends on {producer_id} for its seed "
            f"identifiers, but {reason}."
        ),
        traces=[
            EvaluatorTrace(
                "dependency",
                ok=True,
                reasons=[f"producer {producer_id}: {reason}"],
                detail={"producer": producer_id},
            )
        ],
        ok=True,
        partial=False,
        error=None,
    )


def bundle_evidence(
    plan: Plan,
    results: list[SpecialistResult],
    skipped: list[dict[str, Any]],
    sequencing: list[dict[str, Any]] | None = None,
) -> FederatedEvidence:
    """Bundle specialist results for one plan — the *only* place the federated
    ``partial`` flag is computed. The router, the CLI, and the API all bundle
    through here so their degradation semantics cannot drift.
    """
    partial = (
        bool(plan.partial)
        or bool(plan.unsupported)
        or bool(skipped)
        or any((not r.ok) or r.partial for r in results)
    )
    return FederatedEvidence(
        request=plan.request,
        results=results,
        unsupported=[u.to_dict() for u in plan.unsupported],
        skipped=skipped,
        partial=partial,
        sequencing=list(sequencing or []),
    )


def status_and_exit(
    *,
    cards_present: bool,
    mode: str = "query",
    plan: Plan | None = None,
    evidence: FederatedEvidence | None = None,
) -> tuple[str, int]:
    """One status/exit-code rule for every pipeline entry point.

    Exit 2 only when no source cards exist; else 1 when the plan (plan mode) or
    the evidence bundle (query mode) is partial, 0 when clean.
    """
    if not cards_present:
        return "no_sources", 2
    if mode == "plan":
        assert plan is not None
        return ("partial", 1) if plan.partial else ("answered", 0)
    assert evidence is not None
    return ("partial", 1) if evidence.partial else ("answered", 0)


class SpecialistRouter:
    """Routes a planner ``Plan`` through the source-specific specialists."""

    def __init__(
        self,
        config: SpecialistConfig | None = None,
        *,
        cards: dict[str, SourceCardView] | None = None,
        specialists: dict[str, Any] | None = None,
    ) -> None:
        self._config = config or SpecialistConfig.from_env()
        self._cards = cards if cards is not None else load_source_cards(self._config.data_dir)
        # Optional pre-built specialists (injectable for testing); else built lazily.
        self._specialists: dict[str, Any] = dict(specialists or {})

    @property
    def cards(self) -> dict[str, SourceCardView]:
        return self._cards

    def _specialist_for(self, source: str) -> Any | None:
        if source in self._specialists:
            return self._specialists[source]
        card = self._cards.get(source)
        if card is None:
            return None
        try:
            specialist = build_specialist(source, card, self._config)
        except ValueError:
            return None
        self._specialists[source] = specialist
        return specialist

    def run_plan(self, plan: Plan) -> FederatedEvidence:
        """Dispatch every sub-question to its specialist and bundle the evidence.

        Sub-questions bound by a declared join run in dependency order: the
        producer first, its T-prefixed join values injected as the consumer's
        ``seed_ids`` (bounded by the consumer's own row limit). Independent
        sub-questions run exactly as before.
        """
        results: list[SpecialistResult] = []
        skipped: list[dict[str, Any]] = []
        sequencing: list[dict[str, Any]] = []
        # Dependencies come from the plan AS WRITTEN, before any re-route. The
        # join key decides which hop feeds which, and moving a hop to the store
        # that can execute it does not change that order — it only changes who
        # runs it. Re-deriving deps after the move would collapse two hops that
        # now share a source into one entry and lose the dependency entirely.
        deps = dependency_map(plan)
        by_id: dict[str, SpecialistResult] = {}
        ran_in: dict[str, str] = {}

        for planned in execution_order(plan):
            moved = rerouted(planned, self._cards)
            sq = moved or planned
            if moved is not None:
                sequencing.append(
                    {
                        "sub_question": sq.id,
                        "rerouted_from": planned.source,
                        "rerouted_to": sq.source,
                        "reason": (
                            f"{planned.source} does not model "
                            + ", ".join(
                                self._cards[planned.source].unknown_entities(
                                    list(planned.entities)
                                )
                            )
                        ),
                    }
                )
            ran_in[sq.id] = sq.source
            specialist = self._specialist_for(sq.source)
            if specialist is None:
                skipped.append(
                    {
                        "sub_question": sq.id,
                        "source": sq.source,
                        "reason": f"no specialist available for source {sq.source!r}",
                    }
                )
                continue

            seed_ids: tuple[str, ...] = ()
            producer_ids = deps.get(sq.id) or ()
            producer_id = ", ".join(producer_ids)
            if producer_ids:
                found = [by_id.get(pid) for pid in producer_ids]
                # Union across producers: a consumer at the end of two declared
                # joins takes both, and one producer failing is not a reason to
                # discard what the other found.
                usable = [p for p in found if p is not None and p.ok]
                task = SpecialistTask.from_sub_question(sq)
                # A sub-question that names its own identifiers is not a
                # consumer, whatever the join key's declared direction says —
                # see `carries_its_own_seeds`. Running it unseeded here is
                # correct: `resolve` will take the seeds out of its own text.
                if not usable and carries_its_own_seeds(sq):
                    usable = []
                    seed_ids, truncated = (), False
                elif not usable:
                    failed = [p for p in found if p is not None and not p.ok]
                    if failed:
                        # Keep the producer's own words. "no valid evidence" is
                        # a summary of the summary and loses what actually went
                        # wrong, which is the only useful part of an abstention.
                        reason = "it failed (" + "; ".join(
                            p.error or "no valid evidence" for p in failed
                        ) + ")"
                    else:
                        reason = "it was not run"
                    result = dependency_skip_result(task, producer_id=producer_id, reason=reason)
                    results.append(result)
                    by_id[sq.id] = result
                    sequencing.append(
                        {"consumer": sq.id, "producer": producer_id,
                         "seed_count": 0, "truncated": False, "skipped": reason}
                    )
                    continue
                same_store = all(
                    ran_in.get(pid) == sq.source for pid in producer_ids
                )
                seed_ids, truncated = harvest_seed_ids(
                    usable,
                    cap=sq.limits.max_result_rows,
                    prefer_primary_ids=same_store,
                    wanted_labels=list(sq.entities),
                ) if usable else ((), False)
                if not seed_ids:
                    # The producer gave nothing. Before abstaining, look for
                    # identifiers in the REQUEST — the analyst's own words, not
                    # an invention. "Which CAPEC patterns correspond to T1555,
                    # and which CWE weaknesses do those exploit" names T1555,
                    # and the CAPEC store can answer the whole thing by walking
                    # MAPS_TO backwards; the plan's split sends the first hop to
                    # ATT&CK, which does not model MAPS_TO at all.
                    #
                    # Only the consuming side is seeded this way, and only from
                    # identifiers the request literally contains, so a question
                    # naming nothing is unaffected.
                    seed_ids = request_seeds(plan.request, sq.source)
                if not seed_ids and not carries_its_own_seeds(sq):
                    reason = "it returned no join values"
                    result = dependency_skip_result(task, producer_id=producer_id, reason=reason)
                    results.append(result)
                    by_id[sq.id] = result
                    sequencing.append(
                        {"consumer": sq.id, "producer": producer_id,
                         "seed_count": 0, "truncated": False, "skipped": reason}
                    )
                    continue
                sequencing.append(
                    {"consumer": sq.id, "producer": producer_id,
                     "seed_count": len(seed_ids), "truncated": truncated, "skipped": None}
                )

            task = SpecialistTask.from_sub_question(sq, seed_ids=seed_ids)
            result = specialist.run(task)
            results.append(result)
            by_id[sq.id] = result

        return bundle_evidence(plan, results, skipped, sequencing)


def run_plan(
    plan: Plan,
    config: SpecialistConfig | None = None,
    *,
    cards: dict[str, SourceCardView] | None = None,
) -> FederatedEvidence:
    """Convenience wrapper: route ``plan`` through a fresh ``SpecialistRouter``."""
    return SpecialistRouter(config, cards=cards).run_plan(plan)
