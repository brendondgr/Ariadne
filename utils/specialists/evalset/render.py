r"""Turn a composition spec into a natural question, and nothing more.

This is the generator's model half, and its job is deliberately small. The spec
already carries the answer; the model contributes phrasing. If it ever
contributed the answer, every score measured against that gold would be
circular, so the model is never shown the gold, never shown the path, and never
shown anything named after the system under test.

**What the model sees** is a `Brief`: the anchor's name and identifier, its type
in ordinary words, the relation in ordinary words, the constraint if there is
one, and what kind of thing the answer is. That is the same restriction
`author.py` enforces for the holdout banks, tightened in one direction — the
brief also strips the *schema's own vocabulary*.

That last point is the reason this module exists rather than reusing `author`
directly. Our own record says a question set that avoided the schema's words
would have found the vocabulary problem immediately, and the predicates are the
schema's words: `kill_chain_phase`, `x_mitre_analytic_refs`, `MAPS_TO[ATTACK]`.
Handing those to the renderer would guarantee the leakage we are trying to
measure. So each predicate has a **gloss** written from what the source
documentation means by it, and the raw predicate never reaches the prompt.

The glosses are the one hand-authored artifact in the pipeline, which makes them
the one place bias could enter. Two things bound it: they are written from
source semantics rather than from any template, and `schema_leakage` fails any
rendered question that contains a raw schema token, so a gloss that smuggled one
in would be caught by the question it produced rather than by inspection.

Three registers per spec. Phrasing is part of what a question set tests, and a
single register from a single model explores a narrow band — `author.py` records
that limitation honestly and it applies here too. Three does not fix it; it
widens the band and makes paraphrase robustness measurable rather than assumed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from utils.specialists.evalset.composition import Spec

#: Label -> (singular, plural) as a person refers to that kind of thing. Written
#: from what the catalogues call them, not from any query template. Plurals are
#: explicit because "piece of malware or tool" does not pluralise by adding an s,
#: and a brief that reads awkwardly produces a question that reads awkwardly.
LABEL_GLOSS: dict[str, tuple[str, str]] = {
    "Technique": ("ATT&CK technique", "ATT&CK techniques"),
    "Tactic": ("ATT&CK tactic", "ATT&CK tactics"),
    "Group": ("threat group", "threat groups"),
    "Software": ("piece of malware or tooling", "malware and tools"),
    "Mitigation": ("ATT&CK mitigation", "ATT&CK mitigations"),
    "Campaign": ("campaign", "campaigns"),
    "DataComponent": ("data component", "data components"),
    "DataSource": ("data source", "data sources"),
    "DetectionStrategy": ("detection strategy", "detection strategies"),
    "Analytic": ("detection analytic", "detection analytics"),
    "Matrix": ("ATT&CK matrix", "ATT&CK matrices"),
    "AttackPattern": ("CAPEC attack pattern", "CAPEC attack patterns"),
    "Weakness": ("CWE weakness", "CWE weaknesses"),
    "Category": ("CAPEC category", "CAPEC categories"),
    "View": ("CAPEC view", "CAPEC views"),
    "ExecutionStep": ("execution step", "execution steps"),
    "Consequence": ("consequence", "consequences"),
    "Skill": ("skill", "skills"),
    "CapecMitigation": ("mitigation", "mitigations"),
    "Prerequisite": ("prerequisite", "prerequisites"),
    "Indicator": ("indicator", "indicators"),
    "Example": ("example", "example instances"),
    "Resource": ("resource", "resources"),
    "AlternateTerm": ("alternate name", "alternate names"),
    "TaxonomyEntry:WASC": ("WASC taxonomy entry", "WASC taxonomy entries"),
    "TaxonomyEntry:OWASP Attacks": ("OWASP taxonomy entry", "OWASP taxonomy entries"),
}


def label_words(label: str) -> tuple[str, str]:
    return LABEL_GLOSS.get(label, (label, f"{label}s"))


#: Predicate -> (forwards, backwards), each a relative clause describing the
#: OBJECT, with `{s}` standing for the subject.
#:
#: The earlier frame was "the {plural} it {gloss}", which produced
#: "the attack patterns it can happen after". That is correct English and a
#: garden path: it means "patterns X such that CAPEC-98 can happen after X", and
#: Opus 5 read it as "patterns that can happen after CAPEC-98" — the exact
#: inversion, on the exact axis the blind holdout failed on. The weaker author
#: model happened not to invert it, which is worse than useless as reassurance.
#:
#: So every gloss now names its own direction explicitly. "that can precede {s}"
#: cannot be read backwards.
RELATION_GLOSS: dict[str, tuple[str, str]] = {
    "uses": ("{s} uses", "that use {s}"),
    "mitigates": ("{s} mitigates", "that mitigate {s}"),
    "detects": ("{s} detects", "that detect {s}"),
    "subtechnique-of": ("{s} is a sub-technique of", "that are sub-techniques of {s}"),
    "attributed-to": ("{s} is attributed to", "that {s} is attributed to"),
    "kill_chain_phase": ("{s} belongs to", "that belong to {s}"),
    "x_mitre_analytic_refs": ("that implement {s}", "that {s} implements"),
    "tactic_refs": ("{s} covers", "that cover {s}"),
    "log_source": ("{s} draws on", "that draw on {s}"),
    "ChildOf": ("{s} is a more specific case of", "that are more specific cases of {s}"),
    "ParentOf": ("{s} is a more general case of", "that are more general cases of {s}"),
    "CanPrecede": ("that can follow {s}", "that can precede {s}"),
    "CanFollow": ("that can precede {s}", "that can follow {s}"),
    "CanAlsoBe": ("{s} can also be carried out as", "that can also be carried out as {s}"),
    "PeerOf": ("that are peers of {s}", "that are peers of {s}"),
    "EXPLOITS_WEAKNESS": ("{s} exploits", "that exploit {s}"),
    "MAPS_TO[ATTACK]": ("{s} corresponds to", "that correspond to {s}"),
    "MAPS_TO[WASC]": ("{s} corresponds to", "that correspond to {s}"),
    "MAPS_TO[OWASP Attacks]": ("{s} corresponds to", "that correspond to {s}"),
    "HAS_EXECUTION_STEP": ("{s} is carried out through", "that {s} is a step in"),
    "HAS_CONSEQUENCE": ("{s} can have", "that {s} is a consequence of"),
    "REQUIRES_SKILL": ("{s} requires", "that require {s}"),
    "HAS_MITIGATION": ("that mitigate {s}", "that {s} mitigates"),
    "HAS_PREREQUISITE": ("{s} requires as a precondition", "that {s} is a precondition for"),
    "HAS_INDICATOR": ("that indicate {s}", "that {s} indicates"),
    "HAS_EXAMPLE": ("that illustrate {s}", "that {s} illustrates"),
    "REQUIRES_RESOURCE": ("{s} requires", "that require {s}"),
    "HAS_ALTERNATE_TERM": ("{s} also goes by", "that {s} is another name for"),
    "HAS_MEMBER": ("{s} contains", "that contain {s}"),
}

#: Property -> how to phrase it as a *restriction*. Distinct from PROPERTY_GLOSS
#: because the two frames differ: "what it describes" reads as a question and
#: "only those where what it describes is X" does not.
CONSTRAINT_GLOSS: dict[str, str] = {
    "Abstraction": "whose abstraction level is {value}",
    "Typical_Severity": "whose typical severity is {value}",
    "Likelihood_Of_Attack": "where the likelihood of attack is {value}",
    "Status": "whose status is {value}",
    "Type": "of type {value}",
    "x_mitre_platforms": "that apply to {value}",
    "x_mitre_impact_type": "whose impact is on {value}",
    "x_mitre_is_subtechnique": "that are sub-techniques" ,
    "x_mitre_collection_layers": "collected at the {value} layer",
}

#: Property -> how to ask for it without naming the field.
PROPERTY_GLOSS: dict[str, str] = {
    "description": "what it describes",
    "Description": "what it describes",
    "Extended_Description": "the further detail given about it",
    "text": "its text",
    "Abstraction": "how general or specific it is",
    "Typical_Severity": "how severe it typically is",
    "Likelihood_Of_Attack": "how likely such an attack is",
    "x_mitre_platforms": "which platforms it applies to",
    "x_mitre_is_subtechnique": "whether it is a sub-technique",
    "x_mitre_impact_type": "what kind of impact it has",
    "x_mitre_collection_layers": "where the data is collected",
    "aliases": "what else it is called",
    "x_mitre_aliases": "what else it is called",
    "first_seen": "when it was first seen",
    "last_seen": "when it was last seen",
    "is_family": "whether it is a malware family",
    "x_mitre_log_sources": "which log sources it covers",
    "x_mitre_contributors": "who contributed it",
    "x_mitre_remote_support": "whether it can be applied remotely",
    "Type": "what kind of view it is",
}

#: Raw schema vocabulary. A rendered question containing any of these has leaked
#: the schema into the phrasing, which is the exact failure this pipeline exists
#: to avoid, so it is a hard rejection rather than a reported metric.
_LEAK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"x_mitre_\w+"),
    re.compile(r"\bMAPS_TO\b", re.IGNORECASE),
    re.compile(r"\bHAS_[A-Z_]+\b"),
    re.compile(r"\bREQUIRES_[A-Z_]+\b"),
    re.compile(r"\bEXPLOITS_WEAKNESS\b", re.IGNORECASE),
    re.compile(r"\bkill_chain\w*"),
    re.compile(r"\b(?:subtechnique-of|attributed-to|tactic_refs|log_source)\b"),
    re.compile(r"\b(?:AttackPattern|DataComponent|DetectionStrategy|CapecMitigation)\b"),
    re.compile(r"\b(?:ChildOf|CanPrecede|CanFollow|CanAlsoBe|PeerOf)\b"),
    re.compile(r"\bTaxonomyEntry\b"),
)

#: Identifier shapes. Mirrors `author._ID_PATTERNS`; kept here so the two can
#: diverge if the id schemes do.
_ID_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bT\d{4}(?:\.\d{3})?\b"),
    re.compile(r"\bTA\d{4}\b"),
    re.compile(r"\b[GSMC]\d{4}\b"),
    re.compile(r"\bDET\d{4}\b"),
    re.compile(r"\bAN\d{4}\b"),
    re.compile(r"\bDC\d{4}\b"),
    re.compile(r"\bCAPEC-\d+\b", re.IGNORECASE),
    re.compile(r"\bCWE-\d+\b", re.IGNORECASE),
)

REGISTERS: dict[str, str] = {
    "analyst": (
        "Write it the way a security analyst would type it into a search box: "
        "direct, unceremonious, no preamble."
    ),
    "formal": (
        "Write it as a precise written question, the way it would appear in a "
        "report or a checklist."
    ),
    "indirect": (
        "Write it the way someone would ask a colleague who knows the subject — "
        "conversational, and phrased around what they are trying to find out "
        "rather than around the data."
    ),
}


@dataclass(frozen=True)
class Brief:
    """Everything the renderer is allowed to know. Nothing else reaches a prompt.

    Note what is absent: the gold, the path, the tier, and whether the question
    is answerable at all. A D0 spec produces a brief indistinguishable from a
    D2 one, which is the point — a question that telegraphs its own
    unanswerability tests nothing.
    """

    anchor_key: str
    anchor_name: str | None
    anchor_type: str
    ask: str
    answer_type: str
    constraint: str | None


def _describe_relation(predicate: str, reverse: bool) -> str:
    gloss = RELATION_GLOSS.get(predicate)
    if gloss is None:
        raise KeyError(f"no gloss for predicate {predicate!r} — add one before rendering")
    return gloss[1] if reverse else gloss[0]


def brief_for(spec: Spec) -> Brief:
    """Reduce a spec to the domain-language facts a person would need to ask it."""
    anchor_type = label_words(spec.anchor_label)[0]

    if spec.kind == "property":
        ask = PROPERTY_GLOSS.get(spec.return_field, f"its {spec.return_field}")
        answer_type = "a short factual statement"
    else:
        legs = []
        for index, step in enumerate(spec.steps):
            plural = label_words(step.label)[1]
            relation = _describe_relation(step.predicate, step.reverse)
            # The subject of a later leg is the set the previous leg produced.
            # Glosses are third-person singular, so "each of those" keeps
            # agreement where a bare "those" would not.
            subject = "it" if index == 0 else "each of those"
            legs.append(f"the {plural} {relation.format(s=subject)}")
        ask = ", and then ".join(legs)
        answer_type = f"a list of {label_words(spec.return_label)[1]}"

    constraint = None
    if spec.filters:
        parts = []
        for flt in spec.filters:
            template = CONSTRAINT_GLOSS.get(flt.property)
            if template is None:
                raise KeyError(
                    f"no constraint gloss for {flt.property!r} — add one before rendering"
                )
            parts.append(template.format(value=flt.value))
        constraint = "only the ones " + ", ".join(parts)

    return Brief(
        anchor_key=spec.anchor_key,
        anchor_name=spec.anchor_name,
        anchor_type=anchor_type,
        ask=ask,
        answer_type=answer_type,
        constraint=constraint,
    )


def prompt_for(brief: Brief, register: str) -> str:
    """The complete prompt. No system message, no history, no repository context."""
    named = f'"{brief.anchor_name}"' if brief.anchor_name else "an entity"
    lines = [
        "Write exactly one natural-language question. Output only the question.",
        "",
        f"Subject: {named}, a {brief.anchor_type}, identifier {brief.anchor_key}.",
        f"The question should ask for: {brief.ask}.",
    ]
    if brief.constraint:
        lines.append(f"Restrict it to: {brief.constraint}.")
    lines += [
        f"The answer will be {brief.answer_type}.",
        "",
        "Rules:",
        f"- The question must contain the identifier {brief.anchor_key}.",
        "- It must not contain any other identifier.",
        "- Do not answer it, and do not explain yourself.",
        "- Do not use underscores, camel case, or field names of any kind — "
        "write it as a person would say it.",
        "",
        REGISTERS[register],
    ]
    return "\n".join(lines)


def identifiers_in(text: str) -> set[str]:
    found: set[str] = set()
    for pattern in _ID_PATTERNS:
        found.update(match.group(0).upper() for match in pattern.finditer(text))
    return found


def schema_leakage(text: str) -> list[str]:
    """Raw schema vocabulary in the question. Any hit is a hard rejection."""
    hits: list[str] = []
    for pattern in _LEAK_PATTERNS:
        hits.extend(match.group(0) for match in pattern.finditer(text))
    return sorted(set(hits))


def rejection_reason(question: str, spec: Spec) -> str | None:
    """Why this rendering is unusable, or `None` if it is fine.

    Four ways a rendering silently breaks its own gold, in the order they cost
    the most: it says nothing, it explains itself instead of asking, it fails to
    name the anchor so nothing can resolve it, or it names an identifier the
    gold does not cover — including, worst of all, naming the answer.
    """
    text = (question or "").strip()
    if not text:
        return "empty"
    if len(text) > 600:
        return f"too long ({len(text)} chars) — the model probably explained itself"
    if text.count("?") > 1:
        return "more than one question"

    leaks = schema_leakage(text)
    if leaks:
        return f"leaks schema vocabulary: {', '.join(leaks)}"

    anchor = spec.anchor_key.upper()
    found = identifiers_in(text)
    if anchor not in found:
        return f"does not name its anchor {spec.anchor_key}"

    gold = {g.upper() for g in spec.gold}
    if found & gold:
        return f"names the answer: {', '.join(sorted(found & gold))}"

    strays = {s for s in found - {anchor} if not anchor.startswith(s + ".")}
    if strays:
        return f"names other identifiers: {', '.join(sorted(strays))}"
    return None


_WORD = re.compile(r"[a-z]+")


def schema_overlap(question: str, spec: Spec) -> float:
    """Fraction of the question's words that come from the schema's own labels.

    Reported, not enforced. Some overlap is unavoidable and correct — a question
    about mitigations should say "mitigations". What matters is the
    *distribution*: a bank whose questions are mostly schema words is a bank
    that tests vocabulary matching rather than retrieval, and that is the defect
    our own record says a differently-worded set would have caught immediately.
    """
    words = set(_WORD.findall(question.lower()))
    if not words:
        return 0.0
    schema_words: set[str] = set()
    for label in (spec.anchor_label, spec.return_label, *(st.label for st in spec.steps)):
        schema_words.update(_WORD.findall(re.sub(r"(?<!^)(?=[A-Z])", " ", label).lower()))
    for step in spec.steps:
        schema_words.update(_WORD.findall(step.predicate.lower().replace("_", " ")))
    return round(len(words & schema_words) / len(words), 4)


def registers_for(spec: Spec, wanted: Iterable[str] = tuple(REGISTERS)) -> list[str]:
    return [r for r in wanted if r in REGISTERS]


def renderable(spec: Spec) -> bool:
    """Whether every gloss this spec needs exists.

    A missing gloss is a gap in the hand-authored layer, not a property of the
    data. Specs are skipped rather than rendered from the raw predicate, because
    rendering from the raw predicate is precisely the leak.
    """
    if spec.kind == "property":
        return spec.return_field in PROPERTY_GLOSS
    if any(f.property not in CONSTRAINT_GLOSS for f in spec.filters):
        return False
    return all(step.predicate in RELATION_GLOSS for step in spec.steps)


def missing_glosses(specs: Iterable[Spec]) -> dict[str, list[str]]:
    predicates: set[str] = set()
    properties: set[str] = set()
    constraints: set[str] = set()
    for spec in specs:
        if spec.kind == "property":
            if spec.return_field not in PROPERTY_GLOSS:
                properties.add(spec.return_field)
        else:
            predicates.update(
                st.predicate for st in spec.steps if st.predicate not in RELATION_GLOSS
            )
        constraints.update(f.property for f in spec.filters if f.property not in CONSTRAINT_GLOSS)
    return {
        "predicates": sorted(predicates),
        "properties": sorted(properties),
        "constraints": sorted(constraints),
    }


def coverage(specs: Iterable[Spec]) -> dict[str, Any]:
    specs = list(specs)
    ok = [s for s in specs if renderable(s)]
    return {
        "specs": len(specs),
        "renderable": len(ok),
        "rate": round(len(ok) / len(specs), 4) if specs else 0.0,
        "missing": missing_glosses(specs),
    }
