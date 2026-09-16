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


def _has_footing(form: IntentForm, card: SourceCardView) -> bool:
    """Does this card recognise anything in the form?

    A federated form carries one anchor and two datasets, and the second dataset
    is reached *through the first one's answer* — it has no anchor of its own
    yet. Rendering a sentence for it anyway produced "In ATT&CK, summarise
    CAPEC-555", which is not a question about anything. A card earns a sentence
    by knowing the anchor's identifier scheme or by owning a target label.
    """
    if any(card.has_label(l) for l in form.target_labels):
        return True
    if any(card.has_label(l) for l in form.anchor_labels):
        return True
    if form.anchor_titles and not form.anchors:
        return True
    # Whether an identifier is *this* dataset's business is the resolver's call,
    # not a label inference. CAPEC answers a question anchored on `T1040`
    # through its TaxonomyEntry seeds even though it has no Technique label, and
    # inferring the label instead dropped the whole reverse-direction federated
    # family. `_ids_in` is that ladder.
    return bool(form.anchors and _ids_in(" ".join(form.anchors), card.dataset))


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
    datasets = [d for d in form.datasets if d in cards and _has_footing(form, cards[d])]
    if not datasets:
        raise FormError(f"no live card for datasets {list(form.datasets)}")
    return " ".join(render_for(form, cards[d], cards) for d in datasets)


# -- deterministic fill -----------------------------------------------------


def _selected_datasets(
    question: str, cards: dict[str, SourceCardView]
) -> tuple[tuple[str, ...], dict[str, tuple[Any, ...]]]:
    """Which sources the shipped router picks, and what each one matched.

    This is the drafter's own selection, not a reimplementation of it. Routing
    the rewrite stage differently from the stage it feeds would put a second
    opinion about which catalogue a question belongs to into a pipeline whose
    whole claim is that there is only one.
    """
    from .drafter import (
        _distinctive_name_tokens,
        _match_card,
        _select_sources,
        _tokens as _drafter_tokens,
    )

    tokens = _drafter_tokens(question)
    claimed = _distinctive_name_tokens(cards)
    scored = {
        ds: _match_card(tokens, card, claimed=claimed, dataset=ds)
        for ds, card in cards.items()
    }
    selected = _select_sources(scored)
    ordered = tuple(sorted(selected, key=lambda ds: (-scored[ds][0], -scored[ds][1], ds)))

    # What each source matched, asked again with the *source-naming* words taken
    # out. Those words earn a source its routing point and must keep doing so —
    # but they are not vocabulary, and letting them reach entities through the
    # gloss index pulls in whatever they happen to brush against: `att` reaches
    # ATT&CK's `Matrix` gloss, so every ATT&CK question came back with `Matrix`
    # in its target labels. Same matcher, narrower question.
    naming = set().union(*claimed.values()) if claimed else set()
    vocabulary = {
        ds: _match_card(tokens - naming, card, claimed=claimed, dataset=ds)
        for ds, card in cards.items()
    }
    return ordered, vocabulary


def _mode_for(intent: Any, question: str) -> str:
    """Map the classified intent onto the form's three modes.

    ``count`` is not an intent the classifier has, so it is read off the
    question's own words; everything else is a projection of the closed intent
    taxonomy, so the form cannot disagree with the plan about what was asked.
    """
    from .intent import Intent

    if _COUNT_RE.search(question or ""):
        return MODE_COUNT
    label = getattr(intent, "label", None)
    if label in {Intent.DEFINITIONAL, Intent.LOOKUP}:
        return MODE_DESCRIBE
    if label in {
        Intent.ENUMERATION,
        Intent.TRAVERSAL,
        Intent.REMEDIATION,
        Intent.CORRELATION,
    }:
        return MODE_ENUMERATE
    return MODE_DESCRIBE


_COUNT_RE = re.compile(r"\bhow\s+many\b|\bcount\s+(?:the\s+)?\w", re.IGNORECASE)


def _ids_in(question: str, dataset: str) -> tuple[str, ...]:
    """Identifiers the text cites, through the resolver's own per-dataset ladder.

    :func:`utils.specialists.resolve.resolver._native_ids` is the shipped rule
    for which identifier families a dataset owns and in what priority — CAPEC
    reads CAPEC ids first, then CWE, then ATT&CK ids as taxonomy seeds, and it
    is a priority, not a union. Reimplementing that here would give the rewrite
    stage a second opinion about what an identifier is, which is the one thing
    this design exists not to have.
    """
    from types import SimpleNamespace

    from utils.specialists.resolve.resolver import _native_ids

    return tuple(_native_ids(SimpleNamespace(text=question or "", seed_ids=()), dataset))


def _labels_for_id(value: str, dataset: str, *, registry: Any = None) -> tuple[str, ...]:
    """The label(s) ``value``'s identifier implies in ``dataset``.

    The registry first, because its schemes are *learned* from each dataset's
    canonical snapshot and so cover a catalogue nobody wrote a rule for; the
    resolver's committed shapes second, because the registry keys on the
    canonical id (``capec:attack-pattern:555``) while every question writes the
    analyst-facing one (``CAPEC-555``).
    """
    if registry is None:
        from utils.specialists.schema import get_registry

        registry = get_registry()
    learned = registry.labels_for_id(value, dataset=dataset)
    if learned:
        return tuple(sorted(learned))
    from utils.specialists.resolve.resolver import infer_label

    inferred = infer_label(value, dataset)
    return (inferred,) if inferred else ()


def _card_entities(
    matched: Iterable[str], card: SourceCardView
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split what the router matched into this card's labels and relationships."""
    labels = tuple(sorted({e for e in matched if card.has_label(e)}))
    relations = tuple(sorted({e for e in matched if card.has_relationship(e)}))
    return labels, relations


def _anchor_first_on() -> bool:
    """``ARIADNE_ANCHOR_BEFORE_ROUTING``, read at call time. Default off."""
    import os

    return os.environ.get("ARIADNE_ANCHOR_BEFORE_ROUTING", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _anchor_owners(
    question: str, cards: dict[str, SourceCardView]
) -> tuple[tuple[str, ...], str | None]:
    """Which sources own an anchor the question names — before any routing.

    EXP-2026-09-023 H2 (Q59). ``deterministic_fill`` used to choose the
    datasets from the question's *other* words and only then look the entity
    name up, in those datasets alone. "Which countermeasures apply to Windows
    Management Instrumentation?" routes nowhere — "countermeasures" is not a
    card word — so the name was never looked up, while "What mitigations …"
    bound T1047 at once. An entity name implies its dataset; this asks every
    live source for identifiers and complete names first and returns the
    owners in the order the caller should try them.

    Returns ``(owners, ambiguity)``. ``ambiguity`` is a reason string when the
    *same* complete name exists in more than one source and nothing else in the
    question decides between them — CAPEC's "Phishing" and ATT&CK's "Phishing"
    — in which case the caller must surface the ambiguity rather than let
    dataset order pick a catalogue. Identifiers are never ambiguous: a scheme
    belongs to one source.
    """
    from utils.specialists.resolve import _schema_word_set
    from utils.specialists.schema.namesearch import exact_name_matches_all

    by_id = tuple(ds for ds in cards if _ids_in(question, ds))
    if by_id:
        return by_id, None
    exclude = {ds: _schema_word_set(card) for ds, card in cards.items()}
    hits = exact_name_matches_all(tuple(cards), question, exclude=exclude)
    if not hits:
        return (), None
    owners: list[str] = []
    for ds, _cand in hits:
        if ds not in owners:
            owners.append(ds)
    by_name: dict[str, set[str]] = {}
    for ds, cand in hits:
        by_name.setdefault(cand.name.strip().lower(), set()).add(ds)
    collided = sorted(n for n, dss in by_name.items() if len(dss) > 1)
    ambiguity = (
        f"ambiguous: {collided[0]!r} is a complete name in {len(by_name[collided[0]])} sources"
        if collided
        else None
    )
    return tuple(owners), ambiguity


def deterministic_fill(
    question: str,
    cards: dict[str, SourceCardView],
    intent: Any = None,
    *,
    registry: Any = None,
    anchor_first: bool | None = None,
) -> IntentForm:
    """Bind every slot the shipped machinery can, and report the rest.

    This is the "skip the model" path. Everything bound here is byte-reproducible
    and free, and a tier-0 question should bind completely so the model is never
    consulted for one.

    **It never guesses.** The ranked name index is deliberately not consulted:
    EXP-2026-08-020 measured its accept decision at 68% precision on a frozen
    half and no threshold over the available signals could fix it, so a slot it
    would have filled is left in ``unbound`` for Step 4's closed-choice stage
    instead. Exact *complete-name* matches are a different kind of evidence —
    a lookup, not a similarity score — and are used, but only when the text
    contains exactly one, because "exact" is not "unique" and two readings are
    an ambiguity to surface rather than a tie to break.
    """
    from .intent import DeterministicIntentClassifier

    if intent is None:
        intent = DeterministicIntentClassifier().classify(question, cards)
    datasets, scored = _selected_datasets(question, cards)
    mode = _mode_for(intent, question)

    # -- Q59: the entity's own source, before the router's opinion.
    #
    # The router's selection stands whenever it already covers a source that
    # owns the anchor — it is the tie-break when the same name lives in two
    # catalogues. It is overridden only when it chose nothing, or chose a
    # source that does not hold the entity the question names ("Which ATT&CK
    # techniques does Probe System Files correspond to?" routes to ATT&CK on
    # the word ATT&CK, and Probe System Files is a CAPEC pattern). A collision
    # the router cannot break is reported, never resolved by dataset order.
    dataset_source = "router"
    anchor_ambiguity: str | None = None
    if anchor_first is None:
        anchor_first = _anchor_first_on()
    if anchor_first:
        owners, collision = _anchor_owners(question, cards)
        if owners and not any(ds in datasets for ds in owners):
            if collision and not datasets:
                anchor_ambiguity = collision
                datasets = tuple(owners)
            else:
                datasets = tuple(owners) + tuple(d for d in datasets if d not in owners)
            dataset_source = "anchor-first"

    if not datasets:
        return IntentForm(mode=mode, sources={SLOT_MODE: "intent"}).with_unbound(
            SLOT_DATASETS, SLOT_ANCHORS, SLOT_ANCHOR_LABELS, SLOT_TARGET_LABELS,
            SLOT_RELATION, SLOT_DIRECTION,
        )

    sources: dict[str, str] = {SLOT_MODE: "intent", SLOT_DATASETS: dataset_source}

    # -- anchors: ids first (the resolver's highest-authority tier), then a
    #    complete name, then nothing.
    #
    # Asked of **every** selected source, not just the leading one, because the
    # anchor's dataset is whichever one's ladder recognises the identifier and
    # that need not be the source the question leads with. "Which ATT&CK
    # techniques correspond to CAPEC-555?" routes to ATT&CK first — the word
    # ATT&CK is right there — and ATT&CK's ladder does not read `CAPEC-555`, so
    # asking only the leader left the anchor unbound on a question that names
    # its anchor in plain text. The source that owns the anchor then leads the
    # dataset order, because that is where the first hop starts.
    anchors: tuple[str, ...] = ()
    primary = datasets[0]
    for candidate_ds in datasets:
        found = _ids_in(question, candidate_ds)
        if found:
            anchors, primary = found, candidate_ds
            break
    card = cards[primary]
    anchor_titles: tuple[str, ...] = ()
    anchor_labels: tuple[str, ...] = ()
    if anchors:
        sources[SLOT_ANCHORS] = "exact-id"
        labels = {l for a in anchors for l in _labels_for_id(a, primary, registry=registry)}
        anchor_labels = tuple(sorted(labels))
        if anchor_labels:
            sources[SLOT_ANCHOR_LABELS] = "id-scheme"
    else:
        from utils.specialists.schema.namesearch import exact_name_matches

        # A complete-name match that *is* a schema word is not an entity the
        # question named. "List ATT&CK software entries" contains the complete
        # name "Software" — a real Software node — and anchoring on it turned a
        # bounded scan into a lookup of one arbitrary tool. The resolver's own
        # name extraction filters schema words for the same reason.
        from utils.specialists.resolve import _schema_word_set

        exact = []
        for candidate_ds in datasets:
            if anchor_ambiguity:
                # The same complete name in two sources and nothing to choose
                # between them: not a bind. Reported on the form so the trace
                # says why, and so the anchor gate stands the model down.
                break
            schema_words = _schema_word_set(cards[candidate_ds])
            hits = [
                c
                for c in exact_name_matches(candidate_ds, question)
                if c.name.strip().lower() not in schema_words
            ]
            if hits:
                exact, primary, card = hits, candidate_ds, cards[candidate_ds]
                break
        if anchor_ambiguity:
            sources[SLOT_ANCHORS] = anchor_ambiguity
        elif len(exact) == 1:
            # Cite the **identifier**, keeping the name for provenance. This is
            # the whole point of rewriting into tier-0 form: the analyst gave a
            # name, the resolver's highest-authority tier wants an id, and the
            # complete-name match is a lookup that supplies one. Leaving the
            # anchor as a title instead put the canonical question back on the
            # resolver's fuzzy rung for no reason.
            #
            # Only when the resolver can read that id back out of the text,
            # though. Its ladder owns the MITRE families (T-ids, CAPEC-, CWE-)
            # and nothing else; a Synapse graph's ``node-<hash>`` id is not
            # in any of them, so citing it would strand the anchor on a string
            # no rung matches (2026-09-16: "polymer type node-64deb8c7…" ran
            # ``describe_by_name`` over the id and returned nothing). The name
            # is then the anchor, at the exact-name rung the same lookup just
            # proved will hit.
            entity_id = exact[0].entity_id or ""
            citable = bool(entity_id) and entity_id.upper() in {
                found.upper() for found in _ids_in(entity_id, primary)
            }
            anchors = (entity_id,) if citable else ()
            anchor_titles = (exact[0].name,)
            anchor_labels = (exact[0].label,) if exact[0].label else ()
            sources[SLOT_ANCHORS] = "exact-name"
            if anchor_labels:
                sources[SLOT_ANCHOR_LABELS] = "exact-name"
        elif len(exact) > 1:
            sources[SLOT_ANCHORS] = f"ambiguous: {len(exact)} complete names in the text"

    # -- relation and target labels: whatever the router matched in this card,
    #    minus the anchor's own label, which is where the question starts rather
    #    than what it asks for.
    matched = scored[primary][2]
    labels, relations = _card_entities(matched, card)
    target_labels = tuple(l for l in labels if l not in anchor_labels)
    if target_labels:
        sources[SLOT_TARGET_LABELS] = "card-vocabulary"
    relation = relations[0] if len(relations) == 1 else None
    if relation:
        sources[SLOT_RELATION] = "card-vocabulary"
    elif len(relations) > 1:
        sources[SLOT_RELATION] = f"ambiguous: {len(relations)} relationship types matched"

    # -- mode: a question that names a relation is not a describe.
    #
    # `_mode_for` projects the classified intent, and the classifier calls an
    # identifier-bearing question a lookup unless a stronger cue fires — so
    # "What malware and tools does G0024 use?" arrived here as a describe, the
    # form bound with no relation required, the model rung was never consulted,
    # and the answer was the group's own record (EXP-2026-09-023 sealed T3,
    # EXP-2026-09-025 smoke). When the router matched a target label other than
    # the anchor's in the question's own words, the analyst asked for related
    # entities, not the anchor's record; the relation may still be unbound
    # ("use" does not stem to USES) and is then the model rung's to fill. A
    # definitional phrasing keeps the describe.
    if mode == MODE_DESCRIBE and target_labels:
        from .intent import is_definitional_request

        if not is_definitional_request(question):
            mode = MODE_ENUMERATE
            sources[SLOT_MODE] = "relation-in-question"

    # -- direction: the declared endpoints, never the analyst's verb.
    direction = None
    if relation and anchor_labels:
        direction = direction_for(
            anchor_labels[0],
            relation,
            target_labels[0] if target_labels else None,
            primary,
            registry=registry,
        )
        if direction:
            sources[SLOT_DIRECTION] = "schema-registry"

    form = IntentForm(
        anchors=anchors,
        anchor_labels=anchor_labels,
        target_labels=target_labels,
        relation=relation,
        direction=direction,
        mode=mode,
        datasets=(primary,) + tuple(d for d in datasets if d != primary),
        anchor_titles=anchor_titles,
        sources=sources,
    )

    from .intent import asks_for_bulk_scan

    missing: list[str] = []
    if not anchors and not anchor_titles and not asks_for_bulk_scan(question):
        # An anchorless form is legitimate only when the question really is a
        # scan. Otherwise it renders to "list the mitigations", which is a
        # catalogue dump wearing a question's clothes — the I-11 failure class,
        # and the one EXP-2026-08-020 measured returning all 558 CAPEC patterns
        # for an invented anchor.
        missing.append(SLOT_ANCHORS)
    if (anchors or anchor_titles) and not anchor_labels:
        missing.append(SLOT_ANCHOR_LABELS)
    if mode is not MODE_DESCRIBE and not target_labels:
        missing.append(SLOT_TARGET_LABELS)
    if mode is not MODE_DESCRIBE and relation is None:
        missing.append(SLOT_RELATION)
    elif relation and direction is None:
        # The relation is a word from this card, but not one the anchor's label
        # carries in either direction. Reported, not rendered — see
        # `form_from_slot_gold` for what emitting it anyway cost.
        missing.append(SLOT_RELATION)
    return form.with_unbound(*missing) if missing else form


# -- candidate lists --------------------------------------------------------

#: How many ranked entities a list carries. Five, because a list is read by a
#: chooser and a longer one buys recall the chooser cannot use: EXP-2026-08-020
#: found the right entity in the top one or two whenever it was there at all.
DEFAULT_TOP_K = 5


@dataclass(frozen=True)
class Choice:
    """One option a chooser may pick, with everything needed to tell it apart."""

    index: int
    value: str
    label: str = ""
    name: str = ""
    gloss: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"index": self.index, "value": self.value}
        for key in ("label", "name", "gloss"):
            if getattr(self, key):
                out[key] = getattr(self, key)
        return out


@dataclass(frozen=True)
class CandidateLists:
    """The closed world a model is allowed to choose from, per dataset.

    Nothing outside these lists can enter a form. That is what makes "closed
    choice" a property of the system rather than an instruction in a prompt: the
    gate in Step 4 checks membership, and a pick that is not an index into one of
    these lists is rejected before it reaches the renderer.
    """

    dataset: str
    anchors: tuple[Choice, ...] = ()
    relations: tuple[Choice, ...] = ()
    labels: tuple[Choice, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "anchors": [c.to_dict() for c in self.anchors],
            "relations": [c.to_dict() for c in self.relations],
            "labels": [c.to_dict() for c in self.labels],
        }

    def anchor_at(self, index: Any) -> Choice | None:
        return _at(self.anchors, index)

    def relation_at(self, index: Any) -> Choice | None:
        return _at(self.relations, index)

    def label_at(self, index: Any) -> Choice | None:
        return _at(self.labels, index)


def _at(choices: tuple[Choice, ...], index: Any) -> Choice | None:
    """``choices[index]`` when ``index`` is a valid one, else ``None``.

    Deliberately strict about the *type*: a model that returns ``"MITIGATES"``
    where an index was asked for has not chosen from the list, it has written a
    name that happens to be on it, and accepting that would make the closed
    world advisory. It is rejected here and the reason is recorded.
    """
    if isinstance(index, bool) or not isinstance(index, int):
        return None
    return choices[index] if 0 <= index < len(choices) else None


def _in_scope_labels(form: IntentForm, card: SourceCardView) -> tuple[str, ...]:
    """Labels the ranked search should be restricted to, or ``()`` for all.

    The label filter is not an optimisation, it is the accuracy fix (see
    `namesearch.NameIndex.search`): unrestricted, "how do I stop attackers
    abusing browser extensions" ranks the *detection strategy* above the
    technique it detects, because a strategy's name repeats the question's
    words. Whatever the form already bound about the *anchor's* type is exactly
    that filter.

    Only the **anchor** labels scope it. Including the target labels was worth
    measuring and was wrong: at T3 the form binds `Mitigation` as the target and
    the anchor it is missing is a `Technique`, so restricting the search to the
    targets guaranteed the gold anchor could never appear. Recall@5 was 0.0385.
    """
    scoped = {l for l in form.anchor_labels if card.has_label(l)}
    return tuple(sorted(scoped))


def candidate_lists(
    question: str,
    form: IntentForm,
    cards: dict[str, SourceCardView],
    *,
    top_k: int = DEFAULT_TOP_K,
    dataset: str | None = None,
) -> CandidateLists:
    """Build the closed choice set for the slots ``form`` left unbound.

    Entities come from the shipped BM25 name index, used **only as a list
    producer**: no accept decision, no threshold, nothing here can be
    over-fitted. That distinction is the finding EXP-2026-08-020 paid for — the
    index "works as a component and fails as a router", so it is used as a
    component. Relations and labels come from the card, which is a closed set by
    construction.
    """
    from utils.specialists.schema.namesearch import description_of, search_in

    chosen = dataset or (form.datasets[0] if form.datasets else "")
    card = cards.get(chosen)
    if card is None:
        return CandidateLists(dataset=chosen)

    anchors: tuple[Choice, ...] = ()
    if SLOT_ANCHORS in form.unbound or not (form.anchors or form.anchor_titles):
        from utils.specialists.schema import rerank as _rr

        labels = _in_scope_labels(form, card) or None
        if _rr.rerank_on():
            # EXP-2026-09-028: re-order a wider pool by embedding similarity
            # and hand the chooser the top of THAT. A re-ordering of what the
            # index already found; never a new candidate. Stands down when the
            # question carries an exact complete name (a lookup, which the
            # reranker was measured to hurt).
            from utils.specialists.schema.namesearch import exact_name_matches

            pool = search_in(chosen, question, top_k=_rr.pool_size(), labels=labels)
            if not exact_name_matches(chosen, question):
                pool, _backend = _rr.rerank(question, pool, dataset=chosen)
            hits = pool[:top_k]
        else:
            hits = search_in(chosen, question, top_k=top_k, labels=labels)
        anchors = tuple(
            Choice(
                index=i,
                value=hit.entity_id,
                label=hit.label,
                name=hit.name,
                gloss=description_of(chosen, hit.entity_id),
            )
            for i, hit in enumerate(hits)
        )

    rel_glosses = (card.entity_descriptions or {}).get("relationships") or {}
    relations = tuple(
        Choice(index=i, value=rel, gloss=str(rel_glosses.get(rel) or ""))
        for i, rel in enumerate(sorted(card.relationship_types))
    )
    node_glosses = (card.entity_descriptions or {}).get("nodes") or {}
    labels = tuple(
        Choice(index=i, value=label, gloss=str(node_glosses.get(label) or ""))
        for i, label in enumerate(sorted(card.node_labels))
    )
    return CandidateLists(
        dataset=chosen, anchors=anchors, relations=relations, labels=labels
    )


def candidate_lists_all(
    question: str,
    form: IntentForm,
    cards: dict[str, SourceCardView],
    *,
    top_k: int = DEFAULT_TOP_K,
) -> dict[str, CandidateLists]:
    """Candidate lists for every dataset still in play.

    The form's datasets when routing bound them, and **every live card** when it
    did not. That case is not an edge case: at T4 the router leaves the source
    unbound on more than half the bank, and a per-dataset list keyed on a
    dataset the form does not have is an empty list — so the questions with the
    least deterministic footing were being handed nothing to choose from at all.
    Offering both sources' lists lets the chooser pick the source by picking the
    entity, which is the same closed decision and needs no extra rung.
    """
    datasets = tuple(d for d in form.datasets if d in cards) or tuple(sorted(cards))
    return {
        ds: candidate_lists(question, form, cards, top_k=top_k, dataset=ds)
        for ds in datasets
    }


# -- the gate ---------------------------------------------------------------

#: Why a form was refused. Recorded on the form so the answer record can say
#: which rung declined and on what grounds, rather than only that it abstained.
GATE_OK = "ok"


@dataclass(frozen=True)
class GateVerdict:
    """The gate's decision about one filled form."""

    passed: bool
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "reasons": list(self.reasons)}


def gate_form(
    form: IntentForm,
    lists: dict[str, CandidateLists],
    cards: dict[str, SourceCardView],
    *,
    registry: Any = None,
) -> GateVerdict:
    """Is every value in ``form`` something it was *allowed* to contain?

    This is what makes "closed choice" true rather than asserted. The prompt asks
    the model to pick indices out of lists; nothing about a prompt guarantees it
    did. So the form is checked against the same closed world afterwards, and a
    form that fails is abstained on rather than repaired — a repaired form is a
    guess wearing the deterministic path's clothes.

    Four things are checked, and each corresponds to a way the LLM drafter and
    the free-form query arm were measured going wrong:

    - every **anchor** is on the candidate list for a dataset the form names;
    - every **label** is declared by the card of a dataset the form names;
    - every **relation** is declared by that card;
    - the **direction** agrees with the card's endpoints for the relation.

    A form the model never touched passes trivially, which is the point: the gate
    is one predicate over forms, not a special case for model output.
    """
    reasons: list[str] = []
    datasets = [d for d in form.datasets if d in cards]
    if not datasets:
        reasons.append(f"no live source for datasets {list(form.datasets)}")
        return GateVerdict(False, tuple(reasons))

    allowed_anchors = {
        c.value.upper() for ds in datasets for c in (lists.get(ds) or CandidateLists(ds)).anchors
    }
    for anchor in form.anchors:
        # An anchor the *deterministic* path bound comes from the resolver's own
        # identifier ladder, which is a lookup and not a choice, so it needs no
        # list. An anchor the model supplied does.
        if form.sources.get(SLOT_ANCHORS, "").startswith("model") and (
            anchor.upper() not in allowed_anchors
        ):
            reasons.append(f"anchor {anchor!r} is not on any candidate list")

    for label in (*form.anchor_labels, *form.target_labels):
        if not any(cards[ds].has_label(label) for ds in datasets):
            reasons.append(f"label {label!r} is not declared by any selected source")

    if form.relation:
        if not any(cards[ds].has_relationship(form.relation) for ds in datasets):
            reasons.append(
                f"relation {form.relation!r} is not declared by any selected source"
            )
        elif form.direction is not None:
            if form.direction not in DIRECTIONS:
                reasons.append(f"direction {form.direction!r} is not a direction")
            elif form.anchor_labels:
                declared = direction_for(
                    form.anchor_labels[0],
                    form.relation,
                    form.target_labels[0] if form.target_labels else None,
                    datasets[0],
                    registry=registry,
                )
                if declared is not None and declared != form.direction:
                    reasons.append(
                        f"direction {form.direction!r} contradicts the declared "
                        f"endpoints of {form.relation!r} (which runs {declared!r} "
                        f"from {form.anchor_labels[0]!r})"
                    )

    if form.mode not in MODES:
        reasons.append(f"mode {form.mode!r} is not one of {list(MODES)}")

    return GateVerdict(not reasons, tuple(reasons))


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


def relations_between(
    anchor_label: str,
    target_label: str | None,
    dataset: str,
    *,
    registry: Any = None,
) -> tuple[str, ...]:
    """Relations the declared schema allows between two labels, either direction.

    The mirror of :func:`neighbour_labels`. It exists because the relation slot
    is the one the model is worst at and the one the graph already knows: given
    an anchor label and a target label, CAPEC determines the relation for 16 of
    its 17 label pairs and ATT&CK for all 19 of its own. Asking a model to guess
    a value the schema pins is the same mistake as asking it to guess direction,
    and :func:`direction_for` already refuses to make that one.

    Returns every candidate, not a single answer, so the caller decides what to
    do with an ambiguous pair. An empty result means the pair is not declared,
    which is a finding about the labels, not a licence to fall back to a default.
    """
    if not anchor_label or not target_label:
        return ()
    if registry is None:
        from utils.specialists.schema import get_registry

        registry = get_registry()
    schema = registry.dataset(dataset)
    if schema is None:
        return ()
    return tuple(
        sorted(
            {
                f.rel_type
                for f in schema.label_facets(anchor_label)
                if f.neighbour_label == target_label
            }
        )
    )


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


# -- the requested slots ----------------------------------------------------
#
# What the plan does not carry. The gold plan, and the LLM-drafted plan the
# shipped path uses, both carry the ordered graph vocabulary, the seed ids and
# the limits and nothing else — no requested property, no filter. So the
# composer enumerates whatever came back and never states the field that was
# asked for, and no builder filters anything. On the development half that is
# `Q52` (39 questions, 13.2% of the judged loss) and half of `Q53`.
#
# These are bound from the question's own words against the card's declared
# property names and the registry's observed values, so the benchmark and the
# shipped path derive them the same way. Extending the plan schema instead was
# considered and rejected: it would hand the system a perfectly-filled slot the
# live planner does not produce, and the measured gain would not transfer
# (operator decision, 2026-09-11).

#: Words in a property identifier that carry no meaning to match on. The vendor
#: prefix ``x_mitre`` is not a word a question uses, and the rest are too common
#: to distinguish one property from another.
_PROPERTY_STOPWORDS = frozenset(
    {"x", "mitre", "of", "is", "a", "the", "and", "or", "id", "ref", "refs"}
)

#: Properties whose values restate what a record *is* rather than describe it,
#: and which therefore carry no filter. ``stix_type`` duplicates the label
#: ("malware", "campaign", "tool"), so any question that names the kind of thing
#: it is asking about matches it — 31 of the development half's 39 spurious
#: bindings were exactly that, and the noise then tripped the ambiguity guard and
#: suppressed 12 real platform filters as well. The identity and bookkeeping
#: fields are here for the same reason: a question naming an identifier is
#: anchoring on it, not filtering by it.
_NON_FILTER_PROPERTIES = frozenset(
    {
        "stix_type",
        "id",
        "attack_id",
        "name",
        "source_path",
        "created",
        "modified",
        "revoked",
        "description",
        "external_references",
        "x_mitre_deprecated",
        "x_mitre_version",
    }
)

#: The shortest shared prefix that counts as the same word. Five characters is
#: what the questions need — "how severe" for ``Typical_Severity``, "how likely"
#: for ``Likelihood_Of_Attack``, "what does it describe" for ``description`` —
#: and short enough not to collide: "status" and "state" share four.
_MIN_STEM = 5


@dataclass(frozen=True)
class RequestedSlots:
    """What the question asked for, beyond which records to fetch.

    Every field may be ``None``, and ``None`` means *not bound* rather than
    *not present*. Nothing here is guessed: a property is bound only when the
    question's words match one declared property and no other, and a filter
    value only when the registry has observed that exact value on that property.
    """

    #: The property the answer must state, e.g. ``x_mitre_platforms``.
    property: str | None = None
    #: ``(label, property, value)`` the answer must be restricted to.
    filter: tuple[str, str, str] | None = None
    #: The relationship the question asked about, from the plan's ordered
    #: entities — what an empty result must be reported as empty *of*.
    relation: str | None = None

    def any_bound(self) -> bool:
        """True when the question said something the plan did not carry.

        A method rather than a ``@property``: the field below is *named*
        ``property``, which shadows the builtin inside the class body.
        """
        return bool(self.property or self.filter or self.relation)


def _question_words(text: str) -> frozenset[str]:
    return frozenset(w for w in re.findall(r"[A-Za-z_]+", (text or "").lower()) if w)


def _same_word(a: str, b: str) -> bool:
    """Equal, or sharing a stem long enough to be the same word.

    "platforms"/"platform", "severe"/"severity", "likely"/"likelihood",
    "typically"/"typical", "describe"/"description". The stem bound is what
    stops "status"/"state" and "count"/"country".
    """
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) < _MIN_STEM:
        return False
    common = 0
    for x, y in zip(shorter, longer):
        if x != y:
            break
        common += 1
    return common >= _MIN_STEM


def _property_words(prop: str) -> frozenset[str]:
    return frozenset(
        word for word in _split_identifier(prop) if word not in _PROPERTY_STOPWORDS
    )


def _matching_properties(
    words: frozenset[str], properties: Iterable[str]
) -> list[str]:
    """Declared properties whose identifier words the question uses."""
    hits: list[str] = []
    for prop in sorted(properties):
        prop_words = _property_words(prop)
        if not prop_words:
            continue
        if any(_same_word(w, p) for w in words for p in prop_words):
            hits.append(prop)
    return hits


def requested_slots(
    text: str,
    entities: Iterable[str],
    card: SourceCardView,
    registry: Any = None,
    *,
    labels: Iterable[str] = (),
) -> RequestedSlots:
    """Bind what the question asked for, or leave it unbound.

    ``labels`` are the card-declared labels the plan named, in order; the first
    is the anchor's label and the ones after it are where a filter may sit. When
    omitted they are read off ``entities``.

    **Ambiguity is refusal, not a coin toss.** If the question's words match two
    declared properties the slot stays unbound and the answer behaves exactly as
    it does today. `EXP-2026-09-018` Step 3 measured the alternative: breaking a
    tie by preference scored *worse* than not acting, because a confident wrong
    answer displaces a fallback that was sometimes right.
    """
    entities = list(entities or ())
    words = _question_words(text)
    label_list = [label for label in (labels or entities) if card.has_label(label)]
    relations = [rel for rel in entities if card.has_relationship(rel)]

    # -- the requested property, read off the anchor's declared properties ----
    prop: str | None = None
    if label_list:
        candidates = _matching_properties(
            words, card.label_property_keys(label_list[0])
        )
        if len(candidates) == 1:
            prop = candidates[0]

    # -- the filter: a value the data carries, on a declared property --------
    #
    # Bound from the VALUE, not from the property's name. A filtered question
    # names the value and usually not the field: "which techniques used by APT1
    # apply to macOS" says ``macOS`` and never says ``platform``. Twenty-six of
    # the twenty-seven platform-filtered development questions are that shape, so
    # requiring the property word would bind almost none of them.
    #
    # What keeps this from guessing is that the value must be one the registry
    # has *observed* on that property, and must name exactly one property across
    # every label the plan mentions. A value that two properties could carry is
    # not read at all.
    bound_filter: tuple[str, str, str] | None = None
    if registry is not None:
        matches: list[tuple[str, str, str]] = []
        for label in label_list:
            for candidate in sorted(card.label_property_keys(label)):
                if candidate in _NON_FILTER_PROPERTIES:
                    continue
                for value in registry.observed_values(
                    label, candidate, dataset=card.dataset
                ):
                    if _value_in_text(value, text):
                        matches.append((label, candidate, value))
        # A value that two properties share is ambiguous on its own — "Medium"
        # is both a `Typical_Severity` and a `Likelihood_Of_Attack`. The
        # question does say which: "rated Medium likelihood", "with a typical
        # severity of Medium". So the property's OWN name breaks the tie, which
        # is the same declared vocabulary the property slot is bound from, not a
        # second guess. When it cannot break it, nothing is bound.
        if len({(label, candidate) for label, candidate, _ in matches}) > 1:
            named = [
                match
                for match in matches
                if _matching_properties(words, [match[1]])
            ]
            if len({(label, candidate) for label, candidate, _ in named}) == 1:
                matches = named

        # One reading only. Two properties, or two values of one property, is a
        # question this cannot read and must not answer wrongly.
        if len({(label, candidate) for label, candidate, _ in matches}) == 1:
            values = {value for _, _, value in matches}
            if len(values) == 1:
                bound_filter = matches[0]

    # The relation slot means "the ONE relation this question is about", and it
    # is bound only when the plan names exactly one. A two-hop request names
    # two, and its final leg is walked from the intermediate entities rather
    # than from the anchor — so "CAPEC-33 has no MAPS_TO" was attributing to the
    # anchor an emptiness that was measured, if at all, about its peers. The
    # judge recorded that as a fabricated mapping (`EXP-2026-09-018` Step 6).
    #
    # A chained question therefore gets no absence claim. That is the honest
    # position: this composer has no sentence for "none of the things you asked
    # about have any", and inventing one attributed to the wrong entity is worse
    # than saying nothing.
    return RequestedSlots(
        property=prop,
        filter=bound_filter,
        relation=relations[0] if len(relations) == 1 else None,
    )


def _value_in_text(value: str, text: str) -> bool:
    """Is ``value`` present in ``text`` as a whole word or phrase?

    Case-sensitive, because the values that matter are proper nouns and category
    names — ``Meta``, ``Windows``, ``Stable`` — and matching case-insensitively
    would bind "meta" in "metadata" or the ordinary English "stable".

    A hyphen does not end a word here. The default word boundary matched ``Meta``
    inside the attack pattern *named* "Using Meta-characters in E-mail Headers",
    and bound an abstraction-level filter to a question about severity. A
    hyphenated compound is one word.
    """
    if not value:
        return False
    body = r"\s+".join(re.escape(part) for part in value.split())
    pattern = re.compile(r"(?<![\w-])" + body + r"(?![\w-])")
    haystack = text or ""
    for match in pattern.finditer(haystack):
        if not _inside_a_name(haystack, match.start(), match.end()):
            return True
    return False


#: A capitalised word that is not the value itself. Used to tell a filter value
#: from the same word inside a proper name.
_TITLE_WORD_RE = re.compile(r"[A-Z][A-Za-z0-9]*")


def _inside_a_name(text: str, start: int, end: int) -> bool:
    """Is this occurrence part of a longer Title Case run?

    "Boot Integrity" is the *name* of mitigation M1046, and ``Integrity`` is
    also an observed value of ``Technique.x_mitre_impact_type``. Binding it as a
    filter restricted a question about that mitigation to impact-type Integrity
    and halved its gold coverage — the only regression the data-layer step
    produced.

    A filter value is introduced by an ordinary word: "apply **to** Windows",
    "**at the** Meta abstraction level", "rated Medium likelihood". A value
    sitting immediately beside another capitalised word is part of a name.
    """
    before = text[:start].rstrip()
    if before:
        tail = before.rsplit(" ", 1)[-1]
        if _TITLE_WORD_RE.fullmatch(tail) and not before.endswith((".", "?", "!", ":")):
            return True
    after = text[end:].lstrip()
    if after:
        head = after.split(" ", 1)[0].rstrip(",.?!;:")
        if _TITLE_WORD_RE.fullmatch(head):
            return True
    return False
