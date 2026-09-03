"""Scoring for property reads, whose gold is a *value* rather than an id.

## The defect this exists to fix

`score_answer_coverage` measures the fraction of gold the answer names, and
resolves gold through `_surfaced_ids`, which collects identifiers: claim
``entity_ids``, citation ``primary_id``, and anything in the narrative matching
``T1234 | TA0043 | M1050 | S0152 | G0092 | DS0017 | CAPEC-98 | CWE-79``.

The expansion bank's D1 tier asks for a property's value and places that value in
``must_include_related`` -- a coverage key. So the gold for "What does T1037
describe?" is the technique's entire prose description, and the gold for "What
else is G0092 called?" is ``CHIMBORAZO``, ``Hive0065``, ``Spandex Tempest``.
Neither a paragraph nor an alias is an identifier, so neither can ever enter the
surfaced set. **Every D1 question in the bank was therefore scored against a rule
it could not satisfy, for every arm, on every run** -- which is why 53 of 63
landed on exactly ``1/(gold_width + 1)``: the anchor id was the only creditable
item and it sits in the denominator.

`score_answer_coverage` already documents returning ``None`` for "negatives,
boundary, **property-only**" entries. The bank re-enabled the path by accident.
The fix is to match property values the way a reader would -- by looking for them
in what the answer actually says.

## The rule, fixed before any figure was computed

Pre-registered 2026-09-03, ahead of re-scoring, so it cannot be tuned to a
result. Deliberately **threshold-free**: there is no knob here to fit.

1. **Normalise both sides identically.** Strip ``(Citation: ...)`` spans, casefold,
   and split on runs of non-alphanumerics into a token sequence. Punctuation,
   markdown and whitespace differences stop mattering; wording does not.
2. **A gold value counts as surfaced when its token sequence appears contiguously
   in the answer's token sequence.** Contiguity, rather than raw substring
   matching, gives word boundaries for free: gold ``True`` is not credited by the
   word ``truest``, and gold ``Linux`` is not credited by ``linuxserver``.
3. **Credit is the fraction of gold values surfaced.** For a single-valued
   property that is binary. There is no partial credit *within* a value: a
   truncated description scores 0, because an analyst shown half a description
   was not given the answer. If truncation turns out to dominate, that is a real
   finding about the composer and belongs in the record, not smoothed away by a
   similarity threshold.
4. **A boolean value must be stated together with its property name.**
   Added 2026-09-03 after the first re-score caught a false-positive class:
   asked "Can T1072 be applied remotely?", gold ``False``, the composer never
   mentions ``x_mitre_remote_support`` at all -- but the deterministic trailer
   it appends to every record prints ``revoked: False; x_mitre_deprecated:
   False; x_mitre_is_subtechnique: False``, and a bare ``False`` matched one of
   those. A boolean is uninformative on its own **by construction here**: the
   composer emits several of them per record, so the token cannot identify which
   property it answers. ``true``/``false`` gold is therefore credited only when
   ``<property> <value>`` appears as a contiguous run.

   The scope is deliberately boolean-only. The first attempt required this of
   every one-token value and wrongly rejected ``CHIMBORAZO`` as an alias -- a
   distinctive proper noun that the composer never prints as some other
   property's value. **Known residual risk:** a short enum drawn from a closed
   vocabulary (``High``, ``Detailed``, ``Implicit``) could in principle match
   incidentally the same way. None was observed doing so, and widening the rule
   to catch a hypothetical costs real matches, so it is recorded as a limitation
   rather than papered over.

   **This correction lowers the figure** -- 21 questions moved before it, 17
   after -- which is the opposite direction from fitting a rule to a result.
5. **Anchor identifiers keep the existing id path.** Only ``must_include_related``
   on a property read is rescored; ``must_include_ids`` is still matched by
   `_surfaced_ids`, and set-valued gold on non-property tiers is untouched.

This rule can only raise scores, and it raises them for every arm equally,
because the defect was in the yardstick and not in any arm. It is therefore not
evidence that anything improved, and the record must report the pre-repair figure
beside it.
"""

from __future__ import annotations

import re
from typing import Any

#: STIX prose carries provenance inline. It is noise for a containment test and
#: the composer is free to drop it, so remove it from both sides symmetrically.
_CITATION_RE = re.compile(r"\(Citation:[^)]*\)", re.IGNORECASE)

#: STIX prose carries markdown links, and the composer renders them as their
#: label. Resolving ``[text](url)`` to ``text`` on both sides is what rule 1
#: already promises ("markdown ... differences stop mattering"); without it the
#: url's words land in the middle of the gold token run and break contiguity.
#: Added 2026-09-03 after the first re-score, as an implementation correction --
#: the stated rule did not change and no threshold was introduced. It moved 6 of
#: 68 unmatched values; the changelog carries the figure on both sides.
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")

#: Rule 4's scope. Booleans are the only values the composer is guaranteed to
#: print for several properties of the same record, so they alone cannot
#: identify which property they answer.
_BOOLEAN_TOKENS = frozenset({("true",), ("false",)})

_TOKEN_SPLIT_RE = re.compile(r"[^0-9a-z]+")


def normalize_tokens(text: str | None) -> tuple[str, ...]:
    """Casefolded alphanumeric tokens, citations removed.

    The same function runs over the gold value and over the answer, so any
    transformation it applies is symmetric and cannot favour either side.
    """
    if not text:
        return ()
    stripped = _CITATION_RE.sub(" ", str(text))
    stripped = _MARKDOWN_LINK_RE.sub(r"\1", stripped).casefold()
    return tuple(t for t in _TOKEN_SPLIT_RE.split(stripped) if t)


def contains_tokens(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    """Whether ``needle`` appears as a contiguous run inside ``haystack``.

    An empty needle is not surfaced by anything: a property with no value is not
    a question, and the bank's generator already drops those.
    """
    if not needle or len(needle) > len(haystack):
        return False
    first = needle[0]
    span = len(needle)
    for i, token in enumerate(haystack):
        if token == first and haystack[i:i + span] == needle:
            return True
    return False


def is_property_read(entry: dict[str, Any]) -> bool:
    """Whether this bank entry asks for a property value rather than neighbours.

    Structural, not tier-based, so the golden catalogue -- which carries no
    ``spec`` at all -- is never caught by it. A property spec traverses no edges
    (``steps == []``) and its shapes are ``Label.property`` rather than
    ``Label -[edge]-> Label``.
    """
    spec = entry.get("spec")
    if not isinstance(spec, dict):
        return False
    if spec.get("steps"):
        return False
    shapes = spec.get("shapes") or []
    if not shapes:
        return False
    return all(
        isinstance(s, str) and "." in s and "-[" not in s and "->" not in s
        for s in shapes
    )


def property_name_of(entry: dict[str, Any]) -> str | None:
    """The property a D1 shape asks about: ``Technique.x_mitre_platforms`` -> the tail."""
    spec = entry.get("spec") or {}
    shapes = spec.get("shapes") or []
    if not shapes or "." not in str(shapes[0]):
        return None
    return str(shapes[0]).split(".", 1)[1]


def score_property_values(
    answer_text: str | None,
    gold_values: list[str],
    property_name: str | None = None,
) -> dict[str, Any]:
    """Fraction of the requested property values the answer actually states.

    A boolean value is only credited when the answer names the property beside
    it (rule 4): ``False`` on its own is satisfied by any of the several
    booleans the composer prints per record.
    """
    haystack = normalize_tokens(answer_text)
    prop_tokens = normalize_tokens(property_name) if property_name else ()
    found: list[str] = []
    missing: list[str] = []
    for value in gold_values:
        needle = normalize_tokens(value)
        if needle in _BOOLEAN_TOKENS and prop_tokens:
            hit = contains_tokens(haystack, prop_tokens + needle)
        else:
            hit = contains_tokens(haystack, needle)
        (found if hit else missing).append(value)
    return {
        "gold": len(gold_values),
        "found": len(found),
        "coverage": len(found) / len(gold_values) if gold_values else None,
        "missing": sorted(missing),
    }


def answer_text_from_artifact(payload: dict[str, Any]) -> str:
    """Everything the analyst reads, recovered from a saved answer artifact.

    The JSON-side counterpart of `score_e2e._answer_text`, for re-scoring runs
    that already happened without re-running them.
    """
    answer = payload.get("answer") or {}
    parts = [answer.get("headline") or "", answer.get("narrative") or ""]
    for claim in answer.get("claims") or []:
        if isinstance(claim, dict):
            parts.append(str(claim.get("text") or ""))
    return " ".join(parts)


def rescore_artifact(entry: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any] | None:
    """Re-score one saved property-read artifact under the pre-registered rule.

    **The identifier half of the verdict is not recomputed.** It is read back out
    of the artifact's own ``missing`` list, so the old and the new figure differ
    in exactly one thing -- how a property *value* is matched -- and no drift in
    id normalisation or claim rendering can leak into the comparison.
    """
    from utils.synthesis.grounding import normalize_id

    if not is_property_read(entry):
        return None
    recorded = (payload.get("deterministic_scores") or {}).get("coverage") or {}
    if not recorded:
        return None

    asserts = entry.get("assertions", {}) or {}
    id_gold = [str(v) for v in asserts.get("must_include_ids", []) or []]
    value_gold = [str(v) for v in asserts.get("must_include_related", []) or []]
    missing_before = {str(m) for m in recorded.get("missing") or []}
    found_ids = [i for i in id_gold if normalize_id(i) not in missing_before]

    values = score_property_values(
        answer_text_from_artifact(payload), value_gold, property_name_of(entry)
    )
    gold_n = len(id_gold) + values["gold"]
    found_n = len(found_ids) + values["found"]
    return {
        "gold": gold_n,
        "found": found_n,
        "coverage": found_n / gold_n if gold_n else None,
        "coverage_before": recorded.get("coverage"),
        "values_found": values["found"],
        "values_gold": values["gold"],
        "property_read": True,
    }
