#!/usr/bin/env python3
"""The intent form and its deterministic renderer.

EXP-2026-08-020 measured what the deterministic engine's 1.0000 on the 120 gold
questions actually is: a property of *phrasing*. Keep the identifier and change
one verb and record identity falls to 0.50; drop the identifier and keep the
exact name, 0.24; paraphrase the name or describe the entity, 0.0000 on 208
questions across every arm tried. Nothing behind the router is wrong — the
router is being asked a question in words it does not have.

This module holds the front half of the fix. An :class:`IntentForm` is the
question reduced to five slots the engine already understands, and
:func:`render` turns a filled form back into a **tier-0 sentence in the source
card's own vocabulary** — the wording the engine answers perfectly. Filling the
form is where the work moves: deterministically where the shipped machinery can
bind a slot, and (later, behind a flag) by a model choosing from candidate lists
it cannot add to.

**The renderer names no catalogue.** Every word it emits about *what* is being
asked comes from the card: label and relationship-type identifiers, the source's
own name from ``provenance.source_name``, and the ``entity_descriptions`` gloss.
Nothing here knows that ATT&CK has techniques or that CAPEC has attack patterns,
and a third source delivered tomorrow renders through the same code.

**A form never guesses.** ``unbound`` names the slots that could not be filled;
an unfilled slot is reported, never replaced with the best available match. That
is what keeps the ranked name index out of the deterministic path, which is the
finding EXP-2026-08-020 Step 6 paid for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Iterable

from .cards import SourceCardView

# -- the closed slot vocabulary ---------------------------------------------

#: What the analyst wants *done* with the anchor. Three values, deliberately.
#: ``describe`` is one node's own properties; ``enumerate`` is the nodes reached
#: from it; ``count`` is how many there are. Everything the 120 gold questions
#: ask is one of these three, and a fourth would need a renderer template and a
#: gold column before it could be scored.
MODE_DESCRIBE = "describe"
MODE_ENUMERATE = "enumerate"
MODE_COUNT = "count"
MODES: tuple[str, ...] = (MODE_DESCRIBE, MODE_ENUMERATE, MODE_COUNT)

#: Which way the relationship points, read from the anchor label's side. ``out``
#: means the anchor is the edge's source; ``in`` means it is the target. The
#: value is resolved from the card's declared endpoints, never from the verb the
#: analyst used — "what mitigates T1047" and "what does T1047 need mitigating
#: for" are the same edge traversed the same way.
DIR_OUT = "out"
DIR_IN = "in"
DIRECTIONS: tuple[str, ...] = (DIR_OUT, DIR_IN)

#: Slot names, so ``unbound`` entries are checkable rather than free text.
SLOT_ANCHORS = "anchors"
SLOT_ANCHOR_LABELS = "anchor_labels"
SLOT_TARGET_LABELS = "target_labels"
SLOT_RELATION = "relation"
SLOT_DIRECTION = "direction"
SLOT_MODE = "mode"
SLOT_DATASETS = "datasets"
SLOTS: tuple[str, ...] = (
    SLOT_ANCHORS,
    SLOT_ANCHOR_LABELS,
    SLOT_TARGET_LABELS,
    SLOT_RELATION,
    SLOT_DIRECTION,
    SLOT_MODE,
    SLOT_DATASETS,
)


#: The one slot without which there is no sentence to render at all: without a
#: dataset there is no vocabulary to render into. Everything else
#: degrades: an unbound ``anchor_labels`` renders the anchor bare (which is what
#: an invented identifier deserves — labelling ``T9999`` a Technique would turn a
#: negative control into a positive one), an unbound ``relation`` renders as
#: "related to", and an unbound ``target_labels`` renders as a description.
_RENDER_REQUIRED: frozenset[str] = frozenset({SLOT_DATASETS})


class FormError(ValueError):
    """Raised when a form cannot be rendered because a required slot is empty."""


@dataclass(frozen=True)
class IntentForm:
    """One question reduced to the slots the engine already answers.

    Every collection field is a tuple so a form is hashable and can key a cache.
    ``unbound`` is the honest part: it names the slots nothing could bind, and a
    form with anything in it is not renderable as a tier-0 question.
    """

    anchors: tuple[str, ...] = ()
    anchor_labels: tuple[str, ...] = ()
    target_labels: tuple[str, ...] = ()
    relation: str | None = None
    direction: str | None = None
    mode: str = MODE_DESCRIBE
    datasets: tuple[str, ...] = ()
    unbound: tuple[str, ...] = ()
    #: Free-text words from the original question that no slot claimed. Carried
    #: so the renderer can keep an anchor the resolver will match by *title*
    #: when there is no identifier to cite. Never used for routing.
    anchor_titles: tuple[str, ...] = ()
    #: Where each slot's value came from, for the answer record. Values are
    #: short provenance tags such as ``"exact-id"`` or ``"model"``.
    sources: dict[str, str] = field(default_factory=dict, compare=False)

    # -- predicates ---------------------------------------------------------

    @property
    def is_bound(self) -> bool:
        """True when nothing is outstanding and there is something to anchor on."""
        return not self.unbound and bool(self.anchors or self.anchor_titles)

    def with_unbound(self, *slots: str) -> "IntentForm":
        """A copy with ``slots`` added to ``unbound`` (deduped, slot-ordered)."""
        marked = set(self.unbound) | {s for s in slots if s in SLOTS}
        return replace(self, unbound=tuple(s for s in SLOTS if s in marked))

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchors": list(self.anchors),
            "anchor_labels": list(self.anchor_labels),
            "target_labels": list(self.target_labels),
            "relation": self.relation,
            "direction": self.direction,
            "mode": self.mode,
            "datasets": list(self.datasets),
            "unbound": list(self.unbound),
            "anchor_titles": list(self.anchor_titles),
            "sources": dict(self.sources),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "IntentForm | None":
        if not data:
            return None
        return cls(
            anchors=tuple(str(a) for a in data.get("anchors") or ()),
            anchor_labels=tuple(str(a) for a in data.get("anchor_labels") or ()),
            target_labels=tuple(str(a) for a in data.get("target_labels") or ()),
            relation=data.get("relation") or None,
            direction=data.get("direction") or None,
            mode=str(data.get("mode") or MODE_DESCRIBE),
            datasets=tuple(str(d) for d in data.get("datasets") or ()),
            unbound=tuple(str(u) for u in data.get("unbound") or ()),
            anchor_titles=tuple(str(t) for t in data.get("anchor_titles") or ()),
            sources=dict(data.get("sources") or {}),
        )


# -- card vocabulary --------------------------------------------------------


def _split_identifier(name: str) -> list[str]:
    """CamelCase / SCREAMING_SNAKE -> lowercase words. Mirrors the drafter."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name or "")
    spaced = spaced.replace("_", " ")
    return [w.lower() for w in spaced.split() if w]


def exclusive_source_words(cards: dict[str, SourceCardView]) -> dict[str, set[str]]:
    """Per-dataset name tokens that **no other live source also claims**.

    The drafter already discards a name token another source uses as a *label*
    (``attack`` names CAPEC's ``AttackPattern``, so it names neither source).
    What it does not discard is a token two sources both claim as their own
    name: with "MITRE ATT&CK" and "MITRE CAPEC" live, the word ``mitre`` scores
    an identifier hit for *both*, and a sentence that opens "In MITRE ATT&CK"
    hands CAPEC a free point it did not earn. That is not a router bug — the
    router is right that the word names a source, it just cannot say which — it
    is a constraint on what this renderer is allowed to say. So the renderer
    names a source only in words that name it uniquely.
    """
    from .drafter import _distinctive_name_tokens

    claimed = _distinctive_name_tokens(cards)
    return {
        ds: words - set().union(*(w for other, w in claimed.items() if other != ds), set())
        for ds, words in claimed.items()
    }


def source_phrase(card: SourceCardView, cards: dict[str, SourceCardView] | None = None) -> str:
    """How the card names itself, for the "In <source>," clause.

    ``provenance.source_name`` with every word another live source also claims
    struck out — see :func:`exclusive_source_words`. Falls back to the dataset
    key when nothing survives, and to the full name when there are no other
    cards to collide with.
    """
    name = str((card.provenance or {}).get("source_name") or "").strip()
    if not name:
        return card.dataset
    if not cards or len(cards) < 2:
        return name
    mine = exclusive_source_words(cards).get(card.dataset, set())
    # Split the way the drafter splits a source name — the ampersand is a word
    # boundary there, so "ATT&CK" contributes `att`, and matching any other way
    # would strike out the very word that names the source.
    kept = [w for w in name.split() if set(_split_identifier(w.replace("&", " "))) & mine]
    return " ".join(kept) or card.dataset


def _pluralise(word: str) -> str:
    """English plural, three rules deep. Enough for identifier words."""
    if word.endswith("s") or word.endswith("x") or word.endswith("ch") or word.endswith("sh"):
        return word + "es"
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def label_phrase(card: SourceCardView, label: str, *, plural: bool = False) -> str:
    """A label as words, e.g. ``SubTechnique`` -> ``sub technique``.

    The identifier itself is the routing signal — the drafter's concept index is
    built from exactly these words — so the phrase is the split identifier, not
    a gloss. ``plural`` adds the trailing ``s`` the drafter already singularises.
    """
    words = _split_identifier(label)
    if not words:
        return label
    if plural:
        words = words[:-1] + [_pluralise(words[-1])]
    return " ".join(words)


def relation_phrase(card: SourceCardView, relation: str) -> str:
    """A relationship type as words, e.g. ``EXPLOITS_WEAKNESS`` -> ``exploits weakness``."""
    return " ".join(_split_identifier(relation)) or relation


def relation_gloss(card: SourceCardView, relation: str) -> str:
    """The card's own sentence about ``relation``, or ``""``.

    Read from ``entity_descriptions.relationships`` — human context, never
    routing truth (cards.py module note), which is why it is appended to the
    rendered sentence rather than replacing any of it.
    """
    glosses = (card.entity_descriptions or {}).get("relationships") or {}
    return str(glosses.get(relation) or "").strip()


# -- rendering --------------------------------------------------------------

#: Candidate verbs per mode, most natural first, and candidate connectors for
#: the relation-free case. The renderer renders every combination and keeps the
#: one the router misreads least — see :func:`_misreadings` for why a fixed
#: wording is not safe.
_MODE_VERBS: dict[str, tuple[str, ...]] = {
    MODE_DESCRIBE: ("describe", "summarise", "report on", "look up"),
    MODE_ENUMERATE: ("list", "give", "return", "name"),
    MODE_COUNT: ("count", "tally", "total"),
}

#: How an anchor is attached to its targets when no relation is bound.
_CONNECTORS: tuple[str, ...] = ("related to", "for", "of", "belonging to")


def _routing_inert(phrase: str, cards: dict[str, SourceCardView]) -> bool:
    """True when no word of ``phrase`` reaches an entity in any live card.

    Asked through the drafter's own :func:`_match_card`, not by looking words up
    in the index directly, because the index is not the whole matcher: stems and
    a bounded edit distance sit in front of it, and `describe` reaches CAPEC's
    ``AttackPattern`` through the stem of `describing` rather than through any
    literal key. A check that misses that is worse than none — it would report
    the very collision it exists to catch as clean.
    """
    from .drafter import _match_card, _tokens as _drafter_tokens

    tokens = _drafter_tokens(phrase)
    if not tokens:
        return True
    for card in cards.values():
        _id_hits, _gloss_hits, entities, matched = _match_card(tokens, card)
        if entities or matched:
            return False
    return True


def _misreadings(
    sentence: str, form: IntentForm, cards: dict[str, SourceCardView]
) -> tuple[int, int]:
    """How badly does the router misread this sentence, relative to the form?

    A renderer that only worries about *nouns* gets the routing right and the
    reading wrong. Two phrasings cost more than every other defect in the first
    round-trip put together, and neither is a vocabulary collision:

    ``related to``  is a **correlation** cue. "list the techniques related to
                    group G0016" routed to ATT&CK correctly, then the drafter's
                    correlation rule pulled in the declared join partner, and
                    the answer came back with all 558 CAPEC attack patterns
                    attached to a single-source question.
    ``list``        is a **bulk-scan** cue. "list the attack patterns for
                    CAPEC-98" asks for the whole label, so a question about one
                    pattern's neighbours was answered with the catalogue.

    So the check is not "avoid these words". It is: classify the sentence the
    way the pipeline will, and require the reading to match the form. A form
    naming one dataset must not read as cross-source; a form carrying an anchor
    must not read as a scan of everything. Both cue sets live in
    ``utils.planner.intent`` and are the router's own, so this cannot drift away
    from what the pipeline actually does.

    Returns ``(scan, correlation)`` as 0/1 flags rather than one boolean, so a
    caller can rank candidates when none is clean. Ranking matters because the
    two misreadings do not cost the same and one of them is sometimes
    unavoidable: a relation *named* ``MAPS_TO`` makes any faithful sentence read
    as correlation, and the gold question for those cases reads that way too. A
    spurious bulk scan is never unavoidable, and it is the one that returns the
    catalogue, so it is ranked first.
    """
    from .intent import DeterministicIntentClassifier, Intent, asks_for_bulk_scan

    scan = int(bool(asks_for_bulk_scan(sentence)) and bool(form.anchors or form.anchor_titles))
    reading = DeterministicIntentClassifier().classify(sentence, cards)
    correlation = int(reading.label == Intent.CORRELATION and len(form.datasets) < 2)
    return scan, correlation


def verb_for(mode: str, cards: dict[str, SourceCardView] | None) -> str:
    """The first routing-inert verb for ``mode``, or the most natural one."""
    options = _MODE_VERBS.get(mode) or _MODE_VERBS[MODE_DESCRIBE]
    if not cards:
        return options[0]
    for option in options:
        if _routing_inert(option, cards):
            return option
    return options[0]


def _anchor_phrase(form: IntentForm, card: SourceCardView) -> str:
    """The anchor as the engine's resolver ladder wants to see it.

    An identifier when there is one — the resolver's tier 2, the highest
    authority any wording can carry — and a Title-Cased name otherwise, which is
    tier 3/4. Labelled with the anchor label when one is bound, because the
    label word is what routes the sentence to the right entity type.
    """
    label = form.anchor_labels[0] if form.anchor_labels else ""
    cited = list(form.anchors) or list(form.anchor_titles)
    body = ", ".join(cited)
    if label and card.has_label(label):
        return f"{label_phrase(card, label)} {body}".strip()
    return body


def _candidates(
    form: IntentForm,
    card: SourceCardView,
    cards: dict[str, SourceCardView],
) -> list[str]:
    """Every sentence this form could render to, best-first.

    The shape is fixed per mode and every content word comes from the card:

    ``describe``   ``In <source>, describe <label> <anchor>.``
    ``enumerate``  ``In <source>, list the <targets> <clause>.``
    ``count``      ``In <source>, count the <targets> <clause>.``

    Only the function words vary across candidates — the verb and, when no
    relation is bound, the connector. The nouns are the card's own identifiers
    and never change, because they are the routing signal; what changes is the
    scaffolding that turns them into a sentence, and that is exactly the part
    the router also reads for intent.
    """
    where = source_phrase(card, cards)
    anchor = _anchor_phrase(form, card)
    targets = [l for l in form.target_labels if card.has_label(l)]
    target_words = ", ".join(label_phrase(card, l, plural=True) for l in targets)
    verbs = [v for v in _MODE_VERBS.get(form.mode, ()) if _routing_inert(v, cards)] or [
        (_MODE_VERBS.get(form.mode) or _MODE_VERBS[MODE_DESCRIBE])[0]
    ]

    if not anchor:
        if not targets:
            raise FormError("cannot render a form with neither an anchor nor a target label")
        return [f"In {where}, {v} the {target_words}." for v in verbs]

    if not targets and form.mode != MODE_DESCRIBE and form.anchor_labels and form.relation:
        # The target slot names a label this card does not carry. The relation
        # does carry one, and the schema knows which — see `neighbour_labels`.
        targets = [
            l
            for l in neighbour_labels(
                form.anchor_labels[0], form.relation, form.direction, card.dataset
            )
            if card.has_label(l)
        ]
        target_words = ", ".join(label_phrase(card, l, plural=True) for l in targets)

    if form.mode == MODE_DESCRIBE or not targets:
        describe_verbs = [
            v for v in _MODE_VERBS[MODE_DESCRIBE] if _routing_inert(v, cards)
        ] or [_MODE_VERBS[MODE_DESCRIBE][0]]
        return [f"In {where}, {v} {anchor}." for v in describe_verbs]

    # A relation the form could not tie to the anchor is not emitted. Naming an
    # edge the anchor's label does not have does not narrow the question, it
    # widens it: "list the techniques related to group G0016 by has technique"
    # matched HAS_TECHNIQUE, which in this catalogue runs Tactic->Technique, and
    # came back with all 748 techniques instead of the 27 the group uses.
    relation = (
        form.relation
        if form.relation
        and card.has_relationship(form.relation)
        and SLOT_RELATION not in form.unbound
        else None
    )
    if relation is None:
        return [
            f"In {where}, {v} the {target_words} {c} {anchor}."
            for v in verbs
            for c in _CONNECTORS
        ]

    link = relation_phrase(card, relation)
    # Direction is carried in the wording so the sentence reads the way the edge
    # runs: the targets act on the anchor, or the anchor on them. With no
    # resolved direction the relation is still *named* — it is the strongest
    # routing token in the sentence — but it is not made the verb of a clause
    # that would assert an endpoint order the schema does not declare.
    #
    # The card's gloss for the relation is deliberately **not** appended. It is
    # human context, not routing truth (cards.py §1.1), and pasting it in emits
    # whatever labels the sentence happens to mention: ATT&CK glosses
    # HAS_TECHNIQUE as "A Tactic contains a Technique", so a question about a
    # *group's* techniques arrived at the router talking about tactics. The
    # gloss's place is the candidate list a model chooses from, not the
    # sentence the router reads.
    if form.direction == DIR_IN:
        clauses = [f"that {link} {anchor}"]
    elif form.direction == DIR_OUT:
        clauses = [f"that {anchor} {link}"]
    else:
        clauses = [f"{c} {anchor} by {link}" for c in _CONNECTORS]
    return [f"In {where}, {v} the {target_words} {cl}." for v in verbs for cl in clauses]


def render_for(
    form: IntentForm,
    card: SourceCardView,
    cards: dict[str, SourceCardView] | None = None,
) -> str:
    """Render ``form`` as one tier-0 sentence in ``card``'s vocabulary.

    The first candidate the router reads as the form means, else the first
    candidate. Falling back rather than raising is deliberate: a sentence the
    router misreads still retrieves *something* and the miss shows up in the
    round-trip as a finding, whereas a refusal to render would hide the case
    behind a skip.
    """
    if form.mode not in MODES:
        raise FormError(f"unknown mode {form.mode!r}")
    cards = cards or {card.dataset: card}
    options = _candidates(form, card, cards)
    return min(options, key=lambda s: _misreadings(s, form, cards))


def render(form: IntentForm, cards: dict[str, SourceCardView]) -> str:
    """Render ``form`` across every dataset it names, joined into one request.

    A single-source form renders to one sentence. A federated form renders to
    one sentence per source, in the form's own dataset order, because that is
    what the drafter splits into sub-questions — and the order is the order the
    hops must run in.
    """
    blocking = [s for s in form.unbound if s in _RENDER_REQUIRED]
    if blocking:
        raise FormError(f"cannot render a form with unbound slots: {blocking}")
    datasets = [d for d in form.datasets if d in cards]
    if not datasets:
        raise FormError(f"no live card for datasets {list(form.datasets)}")
    return " ".join(render_for(form, cards[d], cards) for d in datasets)


# -- the understanding-gold -------------------------------------------------

#: Bank name -> the datasets a question of that bank touches. The federated bank
#: is the only many-source case and its order is capec-then-attack, which is the
#: hop order every federated gold question runs in.
_BANK_DATASETS: dict[str, tuple[str, ...]] = {
    "attack": ("attack",),
    "capec": ("capec",),
    "federated": ("capec", "attack"),
}

#: Templates whose questions ask for one node's own properties rather than for
#: what it reaches. Read off the gold record, not guessed from the wording.
_DESCRIBE_TEMPLATES: frozenset[str] = frozenset(
    {"describe", "boundary_refusal", "label_scan", "capec_scan", ""}
)


def direction_for(
    anchor_label: str,
    relation: str,
    target_label: str | None,
    dataset: str,
    *,
    registry: Any = None,
) -> str | None:
    """Which way ``relation`` runs from ``anchor_label``, per the declared schema.

    Resolved from the canonical-derived schema registry, which is where the real
    endpoints live — ATT&CK's card declares no ``allowed_edge_patterns`` at all,
    so a card-only rule would silently return nothing for half the corpus.
    Returns ``None`` when the triple is not declared in either direction, which
    is a finding about the form, not a default to paper over.
    """
    if registry is None:
        from utils.specialists.schema import get_registry

        registry = get_registry()
    schema = registry.dataset(dataset)
    if schema is None:
        return None
    for direction in DIRECTIONS:
        if schema.facet_exists(anchor_label, relation, direction, target_label):
            return direction
    # The neighbour label may be a sibling of the one the gold names (a question
    # about "techniques" gold-labelled Technique also reaches SubTechnique). Fall
    # back to the label-only check before giving up.
    for direction in DIRECTIONS:
        if schema.facet_exists(anchor_label, relation, direction, None):
            return direction
    return None


def neighbour_labels(
    anchor_label: str,
    relation: str,
    direction: str | None,
    dataset: str,
    *,
    registry: Any = None,
) -> tuple[str, ...]:
    """Labels ``relation`` reaches from ``anchor_label`` in ``dataset``.

    The target slot can name a label this card does not have — a question about
    what a CAPEC pattern maps to is *about* ATT&CK techniques, but the edge that
    answers it lands on CAPEC's own ``TaxonomyEntry``. Dropping the unknown
    label and falling back to a bare description throws the question away; the
    schema knows what the edge actually reaches, so ask it.
    """
    if registry is None:
        from utils.specialists.schema import get_registry

        registry = get_registry()
    schema = registry.dataset(dataset)
    if schema is None:
        return ()
    return tuple(
        sorted(
            {
                f.neighbour_label
                for f in schema.label_facets(anchor_label)
                if f.rel_type == relation and (direction is None or f.direction == direction)
            }
        )
    )


def form_from_slot_gold(record: dict[str, Any], *, registry: Any = None) -> IntentForm:
    """Build the form a ``slot_gold.json`` record describes.

    ``slot_gold.json`` was built from question metadata and raw-source answers,
    never from system behaviour, which is why it can serve as the understanding
    gold for this stage without defining the incumbent as correct. It records
    four of the seven slots; ``mode`` comes from the recorded template, ``datasets``
    from the bank, and ``direction`` from the declared schema.

    Slots the gold record leaves empty are marked ``unbound`` rather than
    invented: ``A-NEG-01``'s anchor ``T9999`` has no label in the snapshot, and a
    form that quietly labelled it ``Technique`` would turn a negative control
    into a positive one.
    """
    anchors = tuple(str(a) for a in record.get("anchors") or ())
    anchor_labels = tuple(str(a) for a in record.get("anchor_labels") or ())
    target_labels = tuple(str(a) for a in record.get("target_labels") or ())
    relation = record.get("relation") or None
    template = str(record.get("template") or "")
    bank = str(record.get("bank") or "")
    datasets = _BANK_DATASETS.get(bank, ())

    mode = MODE_DESCRIBE if template in _DESCRIBE_TEMPLATES else MODE_ENUMERATE
    if mode is MODE_ENUMERATE and not target_labels:
        mode = MODE_DESCRIBE

    direction = None
    if relation and anchor_labels and datasets:
        direction = direction_for(
            anchor_labels[0],
            str(relation),
            target_labels[0] if target_labels else None,
            datasets[0],
            registry=registry,
        )

    form = IntentForm(
        anchors=anchors,
        anchor_labels=anchor_labels,
        target_labels=target_labels,
        relation=str(relation) if relation else None,
        direction=direction,
        mode=mode,
        datasets=datasets,
        sources={
            SLOT_ANCHORS: "slot-gold",
            SLOT_ANCHOR_LABELS: "slot-gold",
            SLOT_TARGET_LABELS: "slot-gold",
            SLOT_RELATION: str(record.get("relation_source") or "slot-gold"),
            SLOT_MODE: f"template:{template or 'none'}",
            SLOT_DATASETS: f"bank:{bank}",
            SLOT_DIRECTION: "schema-registry",
        },
    )
    missing: list[str] = []
    if relation and direction is None:
        # The gold names a relation the anchor's label does not carry in either
        # direction. `relation_source` says why: 39 of the 120 relations were
        # "matched from the template name", and a template called
        # `group_techniques` yields HAS_TECHNIQUE, which this catalogue declares
        # only from Tactic. That is a finding about the gold, recorded here as
        # an unbound slot rather than silently rendered into a wrong question.
        missing.append(SLOT_RELATION)
    if not anchors and not target_labels:
        # A form with neither is a question nothing could act on. A form with no
        # anchor but a target label is a *scan* — "list every tactic" — where an
        # empty anchor is the right answer, not a gap.
        missing.append(SLOT_ANCHORS)
    if not anchor_labels:
        missing.append(SLOT_ANCHOR_LABELS)
    if not datasets:
        missing.append(SLOT_DATASETS)
    return form.with_unbound(*missing) if missing else form


def load_slot_gold(path: str | Any) -> list[dict[str, Any]]:
    """Read ``slot_gold.json`` as a list of records."""
    import json
    from pathlib import Path

    data = json.loads(Path(path).read_text())
    return data["records"] if isinstance(data, dict) else list(data)
