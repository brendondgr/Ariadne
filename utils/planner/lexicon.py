#!/usr/bin/env python3
"""Word handling for card-grounded routing: stems, near-misses, gloss forms.

The router matches a request's words against the node labels and relationship
types a source's schema card declares. Until this module that match was
case-folded string equality with a single concession — a trailing ``s``. Which
means ``"mitigations"`` routes and ``"mitigating"``, ``"defend"`` and the typo
``"mitgations"`` do not, and the question falls through to a generic describe
that answers confidently about the right entity with the wrong information.

Three mechanisms, none of which names a dataset, so all three carry to a schema
nobody has written a template for:

``stem``          conservative suffix stripping, so the inflections of one word
                  collapse to one key.
``within_one``    bounded edit distance for typos.
``gloss_forms``   the indexable forms of a word appearing in a card's prose
                  description, which is where ``defensive`` already sits unused
                  in ATT&CK's gloss for ``Mitigation``.

**Everything here is a pure function of its input.** No I/O, no clock, no
randomness — the router stays byte-reproducible, which every claim the project
makes about the deterministic path depends on.

## Why the stemmer is deliberately timid

An aggressive stemmer buys recall and pays for it in false routes, and a false
route is worse than no route: it answers the wrong question confidently instead
of declining. So the suffix list is short, every rule has a minimum stem length,
and the cases that must *not* collapse are pinned by tests —
``use``/``user``, ``group``/``groupware``, ``analytic``/``analysis``.
"""

from __future__ import annotations

import re

#: Suffixes stripped, longest first. ``min_stem`` is the length the *remainder*
#: must reach; below it the rule does not fire. These bounds are what stop
#: ``uses`` becoming ``us`` and colliding with half the language.
_SUFFIXES: tuple[tuple[str, int], ...] = (
    ("ements", 5),
    ("ement", 5),
    ("ings", 4),
    ("ing", 4),
    ("ions", 4),
    ("ion", 4),
    ("ives", 4),
    ("ive", 4),
    ("ers", 4),
    ("ies", 4),
    ("ed", 4),
    ("es", 4),
    ("er", 5),
    ("s", 3),
)

#: The remainder must still reach this after the silent-``e`` rule below.
_MIN_STEM = 4

#: Words whose stem would be misleading and which carry routing weight as-is.
#: Kept tiny on purpose: an exception list is a maintenance burden and a place
#: for dataset knowledge to hide, which is exactly what this module avoids.
_INVARIANT: frozenset[str] = frozenset({
    "analysis", "access", "process", "status", "was", "has", "its",
})


def stem(word: str) -> str:
    """A conservative stem: one suffix rule, then the silent ``e``.

    One suffix rule, not a loop. Repeated stripping is where a timid stemmer
    turns aggressive and each extra pass multiplies the collisions.

    **The silent ``e`` is why there are two passes and not one.** English hides
    a stem boundary behind a final ``e``: ``technique``/``techniques`` and
    ``mitigate``/``mitigating`` each split differently under suffix stripping
    alone, so the singular and the inflected form land on different keys and the
    router misses exactly the word it was widened to catch. Removing a trailing
    ``e`` afterwards puts both on ``techniqu`` and ``mitigat``.

    Note there is no ``ation`` rule. ``ion`` already carries it —
    ``mitigation``, ``mitigations``, ``mitigating`` and ``mitigate`` all reach
    ``mitigat`` — whereas an ``ation`` rule would take the noun to ``mitig``
    and strand it away from the verb.
    """
    low = (word or "").strip().lower()
    if len(low) < 4 or low in _INVARIANT:
        return low
    for suffix, min_stem in _SUFFIXES:
        if low.endswith(suffix) and len(low) - len(suffix) >= min_stem:
            low = low[: -len(suffix)]
            break
    if low.endswith("e") and len(low) - 1 >= _MIN_STEM:
        low = low[:-1]
    return low


def within_one(a: str, b: str, *, min_len: int = 5) -> bool:
    """True when ``a`` and ``b`` differ by at most one edit.

    Guarded by ``min_len`` because at four characters a single edit spans a
    surprising amount of English — ``care``/``core``/``card``/``cart`` are all
    one apart — and the router would start answering a different question than
    the one asked. Length difference above one is rejected before any work.
    """
    if a == b:
        return True
    if len(a) < min_len or len(b) < min_len or abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    # a is now the shorter (or equal). Walk both, allowing one divergence.
    i = j = 0
    edited = False
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        if edited:
            return False
        edited = True
        if len(a) == len(b):
            i += 1
        j += 1
    return True


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]+")


def gloss_forms(text: str, *, min_len: int = 4) -> set[str]:
    """Indexable stems from a card's human description of an entity.

    ATT&CK glosses ``Mitigation`` as *"A defensive measure that reduces
    technique risk"*. The word ``defensive`` is already in the card and already
    reachable; ``defend`` misses it only because the index stores the surface
    form. Storing the stem makes both hit the same key.
    """
    return {
        stem(w) for w in _WORD_RE.findall(text or "")
        if len(w) >= min_len
    } - {""}


def index_keys(name: str) -> set[str]:
    """Every key a label or relationship word should be indexed under.

    Both the surface form and the stem, so an exact match still wins on its own
    key and an inflected request word finds the stem. Returning both rather than
    only the stem keeps the existing exact-match behaviour bit-for-bit intact.
    """
    low = (name or "").strip().lower()
    if not low:
        return set()
    return {low, stem(low)}


def lookup_keys(token: str) -> set[str]:
    """Every key a *request* token should be looked up under."""
    return index_keys(token)


def nearest(token: str, keys: set[str], *, min_len: int = 5) -> str | None:
    """The single index key within one edit of ``token``, or ``None``.

    **Ambiguity is answered with silence.** Two keys one edit away means the
    typo could have been either word, and picking one by iteration order would
    route a question on an accident of dict ordering. Returning ``None`` sends
    it down the honest no-match path instead.
    """
    if len(token) < min_len:
        return None
    hits = [k for k in keys if within_one(token, k, min_len=min_len)]
    return hits[0] if len(hits) == 1 else None
