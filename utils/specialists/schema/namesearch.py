#!/usr/bin/env python3
"""Rank canonical entities by name and description, for questions with no id.

EXP-2026-08-020 Arm 2 left the router honest and still empty-handed: at T4 and
T5 — where a question names its entity in ordinary English and never gives the
identifier — record identity is **0.0000** and non-dumping recall is **0.0000**.
The router now correctly declines instead of returning the catalogue, but it
declines to *everything*.

The missing signal is not in the schema card. It is in the data: every canonical
node carries a ``name`` and almost every one carries a ``description``, and
T1176's description opens *"Adversaries may abuse software extensions to
establish persistent access…"*. "browser extension persistence" should reach it.

**BM25 over the canonical snapshot, and nothing else.** No embedding model, no
vector store, no new dependency — this project has none and this module does not
add one. The index is built from the same checksummed snapshot the identifier
schemes are learned from, so it is deterministic, offline, and carries to any
source whose nodes have names.

## The threshold is the whole design

A ranker always returns a best match. Returning it unconditionally would trade
Arm 2's honest silence for confident error — which is the trade Arm 1 already
made once and had to be undone. So a candidate is accepted only when it is both
**strong** in absolute terms and **clearly ahead** of the runner-up. A question
that half-matches thirty patterns equally has not identified one, and the right
answer there is the abstention Arm 2 already produces.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

REPO = Path(__file__).resolve().parents[3]

_WORD_RE = re.compile(r"[a-z0-9]+")

#: BM25 term-frequency saturation and length normalisation. Standard values;
#: nothing here is tuned to this dataset, deliberately — a threshold fitted to
#: ATT&CK would be one more dataset-specific surface (C-010).
_K1 = 1.5
_B = 0.75

#: A name match is worth more than a description match. A description is long
#: and incidental words are cheap in it; a name is the thing the analyst is
#: reaching for.
_NAME_WEIGHT = 3

#: Acceptance. `MIN_SCORE` keeps a weak best-match from being promoted at all;
#: `MIN_MARGIN` requires the winner to beat the runner-up by that ratio, so an
#: ambiguous field of near-equal candidates resolves to nothing rather than to
#: whichever one sorted first.
#: Read at call time so a sweep can vary them without editing code — and so the
#: values a run used are recoverable from its environment rather than from a
#: diff. Defaults are the a-priori values, chosen before any variant was scored.
MIN_SCORE = 4.0
MIN_MARGIN = 1.25

#: Distinctiveness (EXP-2026-09-023). A complete name that is **one ordinary
#: word** — the sub-technique named "Credentials", the tool named "at", the
#: sub-technique named "Malware" — appears in questions that are not about it,
#: and bound 54 wrong anchors on the exposed bank and 43 on the sealed one.
#:
#: Two rules were tried. H1, ``df``: drop a single-token name whose token occurs
#: in more than ``DISTINCT_MAX_DF`` of the corpus's own documents. **Falsified**:
#: it also drops "Phishing" and "APT29", which are common words *and* the names
#: analysts actually use, and it cannot see "at", which the tokenizer never
#: indexes. Kept so the record reproduces; never shipped.
#:
#: AMENDMENT A-1, ``struct`` (the value ``1`` selects it): a single-token name is
#: a lookup only when the question writes it **as a standalone proper noun** —
#: the same casing as the name, as a whole word, not inside a longer capitalised
#: run (sentence-initial capitals ignored), and long enough to be a token the
#: index can represent. No number to tune, nothing catalogue-specific: "what is
#: Phishing" binds, "stolen credentials were used" does not, "Crimson Hollow"
#: does not bind the software named "Crimson". Multi-word names are never touched.
DISTINCT_MAX_DF = 0.01

#: A capitalised run: two or more consecutive Title-Case / all-caps words.
_CAP_RUN_RE = re.compile(r"(?:[A-Z][A-Za-z0-9'\-]*)(?:\s+[A-Z][A-Za-z0-9'\-]*)+")
#: The tokenizer's minimum; a shorter name has no representable token.
_MIN_TOKEN = 3


def _distinct_mode() -> str:
    """``""`` (off, the default), ``"struct"`` (A-1; also ``1``) or ``"df"`` (H1, falsified)."""
    raw = os.environ.get("ARIADNE_EXACT_NAME_DISTINCT", "").strip().lower()
    if raw in {"1", "true", "yes", "on", "struct"}:
        return "struct"
    if raw == "df":
        return "df"
    return ""


def _standalone_proper_noun(name: str, text: str) -> bool:
    """Does ``text`` write the one-word ``name`` as a name, not as a word?"""
    if len(name) < _MIN_TOKEN:
        return False
    m = re.search(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", text or "")
    if m is None:
        return False
    # Sentence-initial capitalisation is not a proper-noun signal: "Browsing
    # Hardware as a starting point" must still bind the category "Hardware", so
    # runs are looked for in the text *after* its first word.
    lead = re.match(r"\s*[A-Za-z0-9'\-]+", text or "")
    body_start = lead.end() if lead else 0
    for run in _CAP_RUN_RE.finditer(text[body_start:]):
        start, end = run.start() + body_start, run.end() + body_start
        if start <= m.start() and m.end() <= end and (end - start) > (m.end() - m.start()):
            return False
    return True


def _distinct_on() -> bool:
    """Is any distinctiveness rule applied to exact-name matches? Default off."""
    return bool(_distinct_mode())


def _min_score() -> float:
    return float(os.environ.get("ARIADNE_NS_MIN_SCORE", MIN_SCORE))


def _min_margin() -> float:
    return float(os.environ.get("ARIADNE_NS_MIN_MARGIN", MIN_MARGIN))

#: Multiplier applied when the question contains an entity's complete name.
#: Large on purpose: it must clear `MIN_MARGIN` against a near-miss whose name
#: merely *contains* the query ("Blind SQL Injection" for "SQL Injection").
_EXACT_NAME_BOOST = 2.0

_STOP = frozenset(
    """a an and are as at be by for from has have how in into is it its of on or
    that the their to was were what which who whom with you your they them then
    this these those does do did can could may would should i we me my our all
    any some more most other such about against during without within""".split()
)


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall((text or "").lower())
            if len(w) >= 3 and w not in _STOP]


@dataclass(frozen=True)
class Candidate:
    """One ranked entity: enough to seed a query, and to explain the choice."""

    entity_id: str
    label: str
    name: str
    score: float


class NameIndex:
    """A BM25 index over one dataset's canonical names and descriptions."""

    def __init__(self, docs: list[tuple[str, str, str, list[str]]]) -> None:
        #: (entity_id, label, name, tokens)
        self._docs = docs
        self._n = len(docs) or 1
        self._avgdl = (sum(len(d[3]) for d in docs) / self._n) if docs else 1.0
        postings: dict[str, list[tuple[int, int]]] = {}
        for i, (_id, _lab, _name, toks) in enumerate(docs):
            counts: dict[str, int] = {}
            for tok in toks:
                counts[tok] = counts.get(tok, 0) + 1
            for tok, tf in counts.items():
                postings.setdefault(tok, []).append((i, tf))
        self._postings = postings
        # First token of every entity name -> the docs whose name starts there.
        # `exact_name_matches` used to scan all 9,138 documents per call, which
        # was tolerable while it ran only on questions nothing else could route.
        # It now runs on every seedless question, so the scan has to become a
        # lookup: a name can only appear in the text if its *first* word does.
        first: dict[str, list[int]] = {}
        for i, (_id, _lab, name, _toks) in enumerate(docs):
            words = _WORD_RE.findall(name.lower())
            if words:
                first.setdefault(words[0], []).append(i)
        self._name_first = first

    def token_df(self, token: str) -> float:
        """Fraction of this dataset's documents (name + description) containing ``token``."""
        return len(self._postings.get(token, ())) / self._n

    def search(
        self, text: str, *, top_k: int = 5, labels: Iterable[str] | None = None
    ) -> list[Candidate]:
        """Rank entities against ``text``, optionally restricted to ``labels``.

        **The label filter is not an optimisation, it is the accuracy fix.**
        Unrestricted, "how do I stop attackers abusing browser extensions"
        ranks `DET0044 Detecting Malicious Browser Extensions` above the
        technique it detects, because a detection strategy's *name* repeats the
        question's words. The router already knows which entity types the
        question is about; passing them removes a whole class of confident
        wrong answers rather than trying to out-score it.
        """
        keep = {l for l in (labels or ()) if l}
        query = _tokens(text)
        if not query:
            return []
        scores: dict[int, float] = {}
        for term in set(query):
            posting = self._postings.get(term)
            if not posting:
                continue
            # +1 inside the log keeps IDF non-negative for a term in every doc,
            # which otherwise lets a ubiquitous word push a score down.
            idf = math.log(1 + (self._n - len(posting) + 0.5) / (len(posting) + 0.5))
            for i, tf in posting:
                dl = len(self._docs[i][3]) or 1
                denom = tf + _K1 * (1 - _B + _B * dl / self._avgdl)
                scores[i] = scores.get(i, 0.0) + idf * (tf * (_K1 + 1)) / denom
        if keep:
            scores = {i: s for i, s in scores.items() if self._docs[i][1] in keep}

        # **An exact name is not term overlap and must not be scored as if it
        # were.** BM25 ranks `Blind SQL Injection` above `SQL Injection` for the
        # query "SQL Injection", and puts `Phishing`, `Mobile Phishing` and
        # `Voice Phishing` in an exact three-way tie — so the margin rule
        # rejects all of them and T3, the tier that exists to test exact names,
        # resolves nothing. When the question literally contains an entity's
        # whole name, that entity is what was asked about.
        low = " " + " ".join(_WORD_RE.findall((text or "").lower())) + " "
        for i in list(scores):
            name_toks = _WORD_RE.findall(self._docs[i][2].lower())
            if not name_toks:
                continue
            if f" {' '.join(name_toks)} " in low:
                # Longer exact names are stronger evidence: matching all four
                # words of "Inhibit System Recovery Now" says more than matching
                # the single word "Phishing".
                scores[i] *= _EXACT_NAME_BOOST + 0.5 * len(name_toks)
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], self._docs[kv[0]][0]))
        return [
            Candidate(self._docs[i][0], self._docs[i][1], self._docs[i][2], round(s, 4))
            for i, s in ranked[:top_k]
        ]

    def resolve(self, text: str, *, labels: Iterable[str] | None = None) -> Candidate | None:
        """The single confident match, or ``None``.

        ``None`` is the common and correct answer. See the module note: an
        unconfident guess here undoes Arm 2's honesty, which cost real work.
        """
        hits = self.search(text, top_k=2, labels=labels)
        if not hits or hits[0].score < _min_score():
            return None
        if len(hits) > 1 and hits[1].score > 0 and hits[0].score / hits[1].score < _min_margin():
            return None
        return hits[0]


def _canonical_docs(dataset: str) -> list[tuple[str, str, str, list[str]]]:
    path = REPO / "data" / "graphs" / dataset / "canonical" / "nodes.jsonl"
    if not path.exists():
        return []
    docs: list[tuple[str, str, str, list[str]]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        node = json.loads(line)
        props = node.get("properties") or {}
        name = str(node.get("name") or "")
        # The analyst-facing id when there is one, else the canonical id. CAPEC's
        # canonical id is `capec:attack-pattern:66`; every question writes
        # `CAPEC-66`, so the emitted id is normalised to the spelling a query
        # will actually filter on.
        raw_id = str(props.get("attack_id") or node.get("id") or "")
        m = re.match(r"^capec:[a-z-]+:(\d+)$", raw_id, re.IGNORECASE)
        entity_id = f"CAPEC-{m.group(1)}" if m else raw_id
        if not entity_id or not name:
            continue
        # A candidate must be something a query can filter on. CAPEC's execution
        # steps are real nodes with prose descriptions and ids like
        # `capec:attack-pattern:669:step:2`, and unfiltered they outrank the
        # patterns they belong to on any descriptive question. Nothing can be
        # seeded from them, so they are not candidates.
        if ":" in entity_id:
            continue
        toks = _tokens(name) * _NAME_WEIGHT + _tokens(str(props.get("description") or ""))
        if toks:
            docs.append((entity_id, str(node.get("label") or ""), name, toks))
    return docs


@lru_cache(maxsize=8)
def descriptions_for(dataset: str) -> dict[str, str]:
    """``entity_id -> first sentence of the canonical description``.

    A ranked candidate is only useful to a *chooser* if the chooser can tell the
    candidates apart, and two CAPEC patterns can have near-identical names. The
    opening sentence is what distinguishes them, and it is already in the
    snapshot this module reads. Kept here rather than rebuilt by the caller so
    the analyst-facing id normalisation (``capec:attack-pattern:66`` ->
    ``CAPEC-66``) has exactly one implementation.

    First sentence only: the full descriptions run to thousands of characters
    and a prompt built from them would be mostly prose.
    """
    path = REPO / "data" / "graphs" / dataset / "canonical" / "nodes.jsonl"
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        node = json.loads(line)
        props = node.get("properties") or {}
        raw_id = str(props.get("attack_id") or node.get("id") or "")
        m = re.match(r"^capec:[a-z-]+:(\d+)$", raw_id, re.IGNORECASE)
        entity_id = f"CAPEC-{m.group(1)}" if m else raw_id
        if not entity_id or ":" in entity_id:
            continue
        text = " ".join(str(props.get("description") or "").split())
        if not text:
            continue
        head = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
        out[entity_id] = head
    return out


def description_of(dataset: str, entity_id: str) -> str:
    """The first sentence of ``entity_id``'s description, or ``""``."""
    return descriptions_for(dataset).get(entity_id, "")


@lru_cache(maxsize=8)
def index_for(dataset: str) -> NameIndex:
    """Process-cached index for one dataset. Built once, read many."""
    return NameIndex(_canonical_docs(dataset))


def exact_name_matches(
    dataset: str, text: str, *, labels: Iterable[str] | None = None
) -> list[Candidate]:
    """Every entity whose **complete name** appears in ``text``.

    Separate from `resolve` on purpose, and the separation is the point.

    An exact name is a categorically different kind of evidence from a high
    similarity score: it is a lookup, not a guess, and it should not have to
    clear a score threshold tuned for ranked matching. EXP-2026-08-020 measured
    the two bundled together — 3 answers gained, 12 wrong bought — and **ten of
    the twelve wrong came from tiers containing no exact names at all** (0 of
    238 variants at T4/T5/T6 carry one). So the ranked half caused them, and
    welding the two to one threshold blocks a clean win behind a dirty one.

    **But "exact" is not "unique", and that is the trap.** `Phishing` is a
    complete CAPEC name and is also contained in `Mobile Phishing` and
    `Voice Phishing`; `SQL Injection` sits inside `Blind SQL Injection`. So this
    returns a **list**, and the caller must treat two matches as an ambiguity to
    surface rather than a tie to break. Returning the longest, or the first,
    would reintroduce exactly the confident-and-wrong failure this experiment
    exists to name.

    Longest-first so a caller that wants the most specific reading has it
    without re-sorting — but length is never used to *decide*.
    """
    index = index_for(dataset)
    keep = {l for l in (labels or ()) if l}
    distinct = _distinct_mode()
    words = _WORD_RE.findall((text or "").lower())
    low = " " + " ".join(words) + " "
    # Only names whose first word occurs in the question can possibly match, so
    # the candidate set comes from the question's own words rather than from a
    # full pass over the catalogue.
    seen_idx: set[int] = set()
    for w in set(words):
        seen_idx.update(index._name_first.get(w, ()))  # noqa: SLF001 — same module
    out: list[Candidate] = []
    for i in seen_idx:
        entity_id, label, name, _toks = index._docs[i]  # noqa: SLF001 — same module
        if keep and label not in keep:
            continue
        name_toks = _WORD_RE.findall(name.lower())
        if not name_toks:
            continue
        if f" {' '.join(name_toks)} " in low:
            # **A one-word name that is an ordinary word is not a lookup** unless
            # the question writes it as a name. See DISTINCT_MAX_DF for the two
            # rules and why only the structural one ships.
            if distinct and len(name_toks) == 1:
                if distinct == "df" and index.token_df(name_toks[0]) > DISTINCT_MAX_DF:
                    continue
                if distinct == "struct" and not _standalone_proper_noun(name.strip(), text):
                    continue
            out.append(Candidate(entity_id, label, name, float(len(name_toks))))
    out.sort(key=lambda c: (-c.score, c.entity_id))

    # **Drop names nested inside a longer match.** "Software Extensions" also
    # contains the complete name "Software" (T1592.002), and "Spear Phishing"
    # contains "Phishing" — reporting those as competing readings would turn
    # every multi-word entity into a false ambiguity and abstain on the tier
    # this function exists to serve.
    #
    # Genuine ambiguity is two names the question mentions *separately*
    # ("how does Phishing relate to Excavation"), and that survives this filter
    # because neither name sits inside the other.
    kept: list[Candidate] = []
    for cand in out:
        name = " ".join(_WORD_RE.findall(cand.name.lower()))
        if any(f" {name} " in f" {' '.join(_WORD_RE.findall(k.name.lower()))} "
               for k in kept):
            continue
        kept.append(cand)
    return kept


def exact_name_matches_all(
    datasets: Iterable[str],
    text: str,
    *,
    exclude: "dict[str, set[str]] | None" = None,
) -> list[tuple[str, Candidate]]:
    """``exact_name_matches`` over every dataset at once, nesting-aware across them.

    The per-dataset filter drops "Software" inside "Software Extensions" only
    when both names live in the same source. Asked source by source, ATT&CK's
    "Remote Services" and "Credentials" both fire inside CAPEC's "Remote
    Services with Stolen Credentials" — three readings of one phrase, two of
    them false. So the nesting filter is applied again over the union: a name
    contained in a longer matched name from *any* source is not a separate
    mention.

    ``exclude`` maps a dataset to the lower-cased names that are schema words
    there — the caller's ``_schema_word_set`` — so "List ATT&CK software
    entries" does not anchor on the Software node any more than it did before.
    Returns ``(dataset, candidate)`` pairs, longest name first.
    """
    found: list[tuple[str, Candidate]] = []
    for ds in datasets:
        skip = (exclude or {}).get(ds) or set()
        for cand in exact_name_matches(ds, text):
            if cand.name.strip().lower() in skip:
                continue
            found.append((ds, cand))
    found.sort(key=lambda dc: (-dc[1].score, dc[0], dc[1].entity_id))
    kept: list[tuple[str, Candidate]] = []
    for ds, cand in found:
        name = " ".join(_WORD_RE.findall(cand.name.lower()))
        # Strictly shorter only. The same name in two sources — CAPEC's
        # "Phishing" and ATT&CK's "Phishing" — is a genuine cross-source
        # ambiguity for the caller to break, not a nested mention to drop.
        if any(
            (lambda longer: len(name) < len(longer) and f" {name} " in f" {longer} ")(
                " ".join(_WORD_RE.findall(k.name.lower()))
            )
            for _, k in kept
        ):
            continue
        kept.append((ds, cand))
    return kept


def resolve_in(
    dataset: str, text: str, *, labels: Iterable[str] | None = None
) -> Candidate | None:
    return index_for(dataset).resolve(text, labels=labels)


def search_in(
    dataset: str, text: str, *, top_k: int = 5, labels: Iterable[str] | None = None
) -> list[Candidate]:
    return index_for(dataset).search(text, top_k=top_k, labels=labels)
