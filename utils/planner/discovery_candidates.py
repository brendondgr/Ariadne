"""Offline, card-driven candidate discovery; deliberately not an anchor resolver.

Only graph records enter the corpus. Gold data, dataset-specific names, and
identifier grammars are absent from this module. A live search adapter can return
the same Candidate shape; callers must validate identity and evidence against
the live source before answering. Scores are ranks, never probabilities.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .cards import SourceCardView
from utils.specialists.schema.namesearch import _tokens

Key = tuple[str, str]
_WORDS = re.compile(r"\w+", re.UNICODE)


def _normal(text: str) -> str:
    return " ".join(_WORDS.findall(text.casefold()))


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                yield item


@dataclass(frozen=True)
class Document:
    key: Key
    label: str
    name: str
    identifiers: tuple[str, ...]
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Context:
    neighbour: Key
    relation: str
    direction: str
    text: str


@dataclass(frozen=True)
class Candidate:
    key: Key
    label: str
    name: str
    score: float
    exact: tuple[str, ...]
    views: tuple[str, ...]
    matched_fields: tuple[str, ...]
    context: tuple[Context, ...]


class _BM25:
    def __init__(self, texts: Mapping[Key, str]) -> None:
        self.lengths: dict[Key, int] = {}
        self.postings: dict[str, dict[Key, int]] = defaultdict(dict)
        for key, text in sorted(texts.items()):
            tokens = _tokens(text)
            self.lengths[key] = len(tokens)
            for token, frequency in Counter(tokens).items():
                self.postings[token][key] = frequency
        self.n = len(texts)
        self.average = sum(self.lengths.values()) / max(1, self.n) or 1.0

    def search(self, text: str, limit: int) -> list[tuple[Key, float]]:
        scores: dict[Key, float] = defaultdict(float)
        for token in sorted(set(_tokens(text))):
            posting = self.postings.get(token, {})
            idf = math.log(1 + (self.n - len(posting) + 0.5) / (len(posting) + 0.5))
            for key, tf in posting.items():
                norm = 1.5 * (0.25 + 0.75 * self.lengths[key] / self.average)
                scores[key] += idf * tf * 2.5 / (tf + norm)
        return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]


class DiscoveryIndex:
    """Three frozen lexical ablations over a common, source-qualified corpus.

    ``sources`` maps source keys to (card, canonical nodes, canonical edges).
    Its membership is the caller's source-access boundary. Production callers
    must supply only authorized, live sources. This class performs no discovery
    of additional sources, no database execution, and no automatic binding.
    """

    def __init__(
        self,
        sources: Mapping[str, tuple[SourceCardView, Iterable[dict], Iterable[dict]]],
        *,
        max_neighbours: int = 32,
        neighbour_chars: int = 512,
    ) -> None:
        if max_neighbours < 0 or neighbour_chars < 1:
            raise ValueError("invalid graph context budget")
        self.documents: dict[Key, Document] = {}
        self.contexts: dict[Key, tuple[Context, ...]] = {}
        self.context_truncated: set[Key] = set()
        self._schema_words: dict[str, set[str]] = {}
        edges: dict[str, list[dict]] = {}
        cards: dict[str, SourceCardView] = {}
        for dataset, (card, nodes, relationships) in sorted(sources.items()):
            if dataset != card.dataset:
                raise ValueError("source key does not match card dataset")
            cards[dataset] = card
            edges[dataset] = list(relationships)
            self._schema_words[dataset] = {
                _normal(re.sub(r"([a-z])([A-Z])", r"\1 \2", word).replace("_", " "))
                for word in card.node_labels | card.relationship_types
            }
            identity = card.raw.get("identity") or {}
            id_fields = set(identity.get("join_key") or ()) | {
                identity.get("unique_backstop"), card.provenance.get("id_property")
            }
            for node in nodes:
                label, record_id = node.get("label"), node.get("id")
                if not record_id or not card.has_label(label):
                    continue
                key = (dataset, str(record_id))
                if key in self.documents:
                    raise ValueError(f"duplicate canonical identity: {key}")
                props = node.get("properties") or {}
                fields = tuple(
                    (prop, text)
                    for prop in sorted(card.node_properties.get(label, {}))
                    for text in _strings(props.get(prop))
                    if text.strip()
                )
                identifiers = {str(record_id)}
                for prop in id_fields - {None}:
                    identifiers.update(_strings(props.get(prop)))
                self.documents[key] = Document(
                    key, label, str(node.get("name") or ""),
                    tuple(sorted(identifiers)), fields,
                )

        # Individual components that repeat within a label (e.g. an object type
        # in a composite key) cannot identify a record by themselves. Keep
        # collisions across labels/sources visible as multiple exact candidates.
        frequencies = Counter(
            (doc.key[0], doc.label, value.casefold())
            for doc in self.documents.values() for value in doc.identifiers
        )
        self._id_first: dict[str, list[tuple[str, Key]]] = defaultdict(list)
        self._name_first: dict[str, list[tuple[str, Key]]] = defaultdict(list)
        for key, doc in sorted(self.documents.items()):
            for value in doc.identifiers:
                if frequencies[(key[0], doc.label, value.casefold())] == 1:
                    words = _WORDS.findall(value.casefold())
                    if words:
                        self._id_first[words[0]].append((value.casefold(), key))
            name = _normal(doc.name)
            if name and name not in self._schema_words[key[0]]:
                self._name_first[name.split()[0]].append((name, key))

        adjacent: dict[Key, set[tuple[Key, str, str]]] = defaultdict(set)
        for dataset, relationships in edges.items():
            card = cards[dataset]
            for edge in relationships:
                a = (dataset, str(edge.get("source_id", "")))
                b = (dataset, str(edge.get("target_id", "")))
                rel = str(edge.get("type", ""))
                if a not in self.documents or b not in self.documents or not card.has_relationship(rel):
                    continue
                patterns = card.allowed_edge_patterns.get(rel)
                if patterns and [self.documents[a].label, self.documents[b].label] not in patterns:
                    continue
                adjacent[a].add((b, rel, "out"))
                adjacent[b].add((a, rel, "in"))
        for key, neighbours in adjacent.items():
            if len(neighbours) > max_neighbours:
                self.context_truncated.add(key)
            contexts = []
            for neighbour, rel, direction in sorted(neighbours)[:max_neighbours]:
                doc = self.documents[neighbour]
                text = " ".join([doc.name, *(value for _, value in doc.fields)])[:neighbour_chars]
                contexts.append(Context(neighbour, rel, direction, text))
            self.contexts[key] = tuple(contexts)
        names = {key: doc.name for key, doc in self.documents.items()}
        properties = {key: " ".join(v for _, v in doc.fields) for key, doc in self.documents.items()}
        self._indexes = {
            "pooled": _BM25({key: (names[key] + " ") * 3 + properties[key] for key in names}),
            "name": _BM25(names),
            "properties": _BM25(properties),
            "graph": _BM25({key: " ".join(c.text for c in self.contexts.get(key, ())) for key in names}),
        }

    def exact_matches(self, question: str) -> dict[Key, tuple[str, ...]]:
        matches: dict[Key, set[str]] = defaultdict(set)
        words = set(_WORDS.findall(question.casefold()))
        for first in sorted(words):
            for value, key in self._id_first.get(first, ()):
                if re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", question.casefold()):
                    matches[key].add("id")
        # Retain duplicate names and separately mentioned shorter names. Only
        # remove a shorter occurrence contained in a longer matched occurrence.
        normalized = " " + _normal(question) + " "
        spans = []
        for first in sorted(words):
            for name, key in self._name_first.get(first, ()):
                for match in re.finditer(r"(?= " + re.escape(name) + r" )", normalized):
                    spans.append((match.start(), match.start() + len(name), key))
        for start, end, key in spans:
            if not any(s <= start and end <= e and e - s > end - start for s, e, _ in spans):
                matches[key].add("name")
        return {key: tuple(sorted(reasons)) for key, reasons in sorted(matches.items())}

    def search(self, question: str, *, arm: str = "fields", top_k: int = 10) -> list[Candidate]:
        if arm not in {"pooled", "fields", "graph"}:
            raise ValueError(f"unknown discovery arm: {arm}")
        if top_k < 1:
            raise ValueError("top_k must be positive")
        views = {"pooled": ("pooled",), "fields": ("name", "properties"),
                 "graph": ("name", "properties", "graph")}[arm]
        scores: dict[Key, float] = defaultdict(float)
        evidence: dict[Key, list[str]] = defaultdict(list)
        for view in views:
            for rank, (key, _score) in enumerate(self._indexes[view].search(question, 100), 1):
                scores[key] += 1 / (60 + rank)
                evidence[key].append(view)
        exact = self.exact_matches(question)
        keys = set(scores) | set(exact)
        ranked = sorted(keys, key=lambda key: (
            0 if "id" in exact.get(key, ()) else 1 if key in exact else 2,
            -scores[key], key,
        ))[:top_k]
        tokens = set(_tokens(question))
        return [Candidate(
            key, self.documents[key].label, self.documents[key].name,
            scores[key], exact.get(key, ()), tuple(evidence[key]),
            tuple(sorted({prop for prop, value in self.documents[key].fields if tokens & set(_tokens(value))})),
            tuple(c for c in self.contexts.get(key, ()) if tokens & set(_tokens(c.text))) if arm == "graph" else (),
        ) for key in ranked]
