#!/usr/bin/env python3
"""Find queries that filter a property against values it can never hold.

The blind holdout lost four questions to one shape of defect: routing chose an
anchor from an entity *mention* while binding took its values from the task's
seed ids, and nothing owned the question of whether the two agree. Asked "which
groups use T1550.002", the ATT&CK cascade emitted
``WHERE g.attack_id IN ['T1550.002']`` — a filter of Group identifiers against a
technique identifier, structurally unsatisfiable, silently empty.

This module answers "where else?" without executing anything. It drives both
builders across a space of task shapes, extracts every
``(label, property, bound values)`` triple from the emitted query, and asks the
schema registry whether those values could inhabit that property. The registry
learned the answer from the canonical snapshot
(:mod:`utils.specialists.schema.idscheme`), so the audit carries no knowledge of
ATT&CK or CAPEC and reports on any dataset the registry can see.

**A caveat on triage.** ``seed_in_scope`` marks the findings a direction flip
could repair — the reverse-direction asks. It reads the seed through the same
learned schemes, so on a dataset whose analyst-facing identifier differs from
its stored one (CAPEC calls a pattern ``CAPEC-1``; the graph stores
``capec:attack-pattern:1``) the flag under-reports and those findings triage as
misroutes. The mismatch itself is unaffected — that is judged on the values the
builder actually bound.

**Two kinds of finding, and the second matters as much as the first.**
``mismatch`` is the defect above. ``unchecked`` is a draft that bound parameters
the extractor could not attribute to a labelled property — no defect is claimed,
but nothing was verified either, and a guard whose coverage is unknown is a
guard nobody should trust. Both are reported; only the first is a bug.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from utils.specialists.binding import Binding, extract_bindings, unsatisfiable_bindings
from utils.specialists.contracts import SpecialistTask
from utils.specialists.cypher.builder import CypherQueryBuilder
from utils.specialists.gremlin.builder import GremlinQueryBuilder
from utils.specialists.resolve import ResolvedTask
from utils.specialists.schema import get_registry
from utils.specialists.schema.idscheme import CONSISTENT, MISMATCH, scheme_of
from utils.specialists.schema.registry import SchemaRegistry

# The committed question banks, used as the source of realistic seed vocabulary.
# A dataset arrives with a question catalogue; this reads whatever is there and
# keeps one exemplar per identifier family, so the enumeration stays small.
_BANK_DIR = Path(__file__).resolve().parents[1] / "tests" / "golden"
_BANK_FILES = (
    "attack_questions.json",
    "capec_questions.json",
    "federated_questions.json",
    "holdout_questions.json",
)

# -- Cypher / Gremlin binding extraction -------------------------------------

# -- the case space ----------------------------------------------------------


@dataclass(frozen=True)
class AuditCase:
    """One routing input: a dataset, an entity scope, and a seed identifier."""

    dataset: str
    labels: tuple[str, ...]
    relationships: tuple[str, ...]
    seed_ids: tuple[str, ...]

    def resolved(self) -> ResolvedTask:
        task = SpecialistTask(
            sub_question_id="audit",
            source=self.dataset,
            text="audit probe",
            entities=self.labels,
            seed_ids=self.seed_ids,
        )
        return ResolvedTask(
            task=task,
            dataset=self.dataset,
            labels=self.labels,
            relationships=self.relationships,
            seed_ids=self.seed_ids,
        )


def _bank_tasks() -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for name in _BANK_FILES:
        path = _BANK_DIR / name
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        questions = payload.get("questions", payload) if isinstance(payload, dict) else payload
        for question in questions if isinstance(questions, list) else []:
            if not isinstance(question, dict):
                continue
            # A single-source question carries one ``task``; a federated one
            # carries a ``sub_questions`` list of the same shape.
            task = question.get("task")
            if isinstance(task, dict):
                tasks.append(task)
            for sub in question.get("sub_questions") or ():
                if isinstance(sub, dict):
                    tasks.append(sub)
    return tasks


def seed_vocabulary(dataset: str, extra: Sequence[str] = ()) -> tuple[str, ...]:
    """One exemplar per identifier family the dataset's question banks mention.

    Deduplicating by *scheme* rather than by value is what keeps the enumeration
    to a handful of seeds instead of every id in the catalogue, while still
    covering every kind of identifier an analyst has ever been recorded asking
    about.

    The vocabulary is therefore only as wide as the catalogue: the committed
    CAPEC bank anchors on CAPEC identifiers and nothing else, so CWE and ATT&CK
    anchors reach the Gremlin builder only when a caller passes them in
    ``extra``. That is a real limit on this audit's coverage of that dataset,
    recorded rather than papered over.
    """
    by_scheme: dict[str, str] = {}
    for seed in extra:
        scheme = scheme_of(seed)
        if scheme is not None:
            by_scheme.setdefault(scheme, seed)
    for task in _bank_tasks():
        if task.get("source") != dataset:
            continue
        for seed in task.get("seed_ids") or ():
            scheme = scheme_of(seed)
            if scheme is not None:
                by_scheme.setdefault(scheme, seed)
    return tuple(by_scheme[key] for key in sorted(by_scheme))


def scope_space(dataset: str, registry: SchemaRegistry) -> tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]:
    """``(labels, relationships)`` scopes to probe: from the banks and the schema.

    The bank scopes are the ones an analyst has been observed asking for. The
    schema scopes — every declared ``(source, rel, target)`` triple, in both
    label orders — are the ones nobody has asked for yet, and are where a
    co-authored catalogue is blind by construction.
    """
    scopes: dict[tuple[tuple[str, ...], tuple[str, ...]], None] = {}
    for task in _bank_tasks():
        if task.get("source") != dataset:
            continue
        entities = tuple(task.get("entities") or ())
        if entities:
            scopes.setdefault((entities, ()), None)
    schema = registry.dataset(dataset)
    if schema is not None:
        for label in sorted(schema.labels()):
            scopes.setdefault(((label,), ()), None)
        for source, rel, target in sorted(schema.triples):
            scopes.setdefault(((source, target), (rel,)), None)
            scopes.setdefault(((target, source), (rel,)), None)
    return tuple(scopes)


def enumerate_cases(
    dataset: str,
    registry: SchemaRegistry | None = None,
    extra_seeds: Sequence[str] = (),
) -> Iterator[AuditCase]:
    """The cross-product of scopes and seed exemplars for one dataset."""
    registry = registry or get_registry()
    seeds = seed_vocabulary(dataset, extra_seeds)
    for labels, relationships in scope_space(dataset, registry):
        for seed in seeds:
            yield AuditCase(dataset, labels, relationships, (seed,))


# -- the audit ---------------------------------------------------------------

KIND_MISMATCH = "mismatch"
KIND_UNCHECKED = "unchecked"


@dataclass(frozen=True)
class BindingFinding:
    """One reportable observation about a draft's bindings."""

    kind: str
    dataset: str
    template: str
    labels: tuple[str, ...]
    seed_ids: tuple[str, ...]
    label: str | None
    property: str | None
    values: tuple[Any, ...]
    query: str
    # True when the seed's own label is one the caller put in scope. Those are
    # the reverse-direction asks — "which groups use this technique" — and are
    # both the most plausible and the only ones a direction flip can repair. A
    # foreign seed is a misroute: still a silently empty query, different fix.
    seed_in_scope: bool = False

    def line(self) -> str:
        where = f"{self.label}.{self.property}" if self.label else "(no binding extracted)"
        return (
            f"{self.kind:16}{'*' if self.seed_in_scope else ' '} {self.dataset:7} {self.template:28} "
            f"scope={'+'.join(self.labels) or '-':40} seed={','.join(map(str, self.seed_ids))} "
            f"→ {where} bound to {list(self.values)}"
        )


@dataclass
class AuditReport:
    """Findings plus what was examined, so coverage is visible."""

    findings: list[BindingFinding] = field(default_factory=list)
    cases: int = 0
    drafts: int = 0
    bindings: int = 0

    def of_kind(self, kind: str) -> list[BindingFinding]:
        return [f for f in self.findings if f.kind == kind]

    def templates_with(self, kind: str) -> tuple[str, ...]:
        return tuple(sorted({f.template for f in self.of_kind(kind)}))

    def in_scope(self, kind: str = KIND_MISMATCH) -> list[BindingFinding]:
        """Findings whose seed label was in the caller's scope — the repairable ones."""
        return [f for f in self.of_kind(kind) if f.seed_in_scope]

    def summary(self) -> str:
        return (
            f"{self.cases} cases, {self.drafts} drafts, {self.bindings} bindings checked — "
            f"{len(self.of_kind(KIND_MISMATCH))} mismatch "
            f"({len(self.in_scope())} with the seed's label in scope), "
            f"{len(self.of_kind(KIND_UNCHECKED))} unchecked"
        )


def _builder_for(dataset: str):
    return CypherQueryBuilder() if dataset == "attack" else GremlinQueryBuilder()


def audit_bindings(
    datasets: Sequence[str] | None = None,
    registry: SchemaRegistry | None = None,
    cases: Iterable[AuditCase] | None = None,
    extra_seeds: dict[str, Sequence[str]] | None = None,
) -> AuditReport:
    """Drive the builders over the case space and report on what they bind."""
    registry = registry or get_registry()
    names = tuple(datasets) if datasets is not None else registry.dataset_names()
    report = AuditReport()

    def _run(case: AuditCase) -> None:
        report.cases += 1
        try:
            draft = _builder_for(case.dataset).build(case.resolved())
        except Exception:
            # A builder that refuses a shape is not a binding defect. The
            # refusal is the honest outcome and is out of scope here.
            return
        report.drafts += 1
        bindings = extract_bindings(draft)
        # Triage signal: does the anchor the caller seeded belong to a label the
        # caller also put in scope? Both the raw seed and the values the builder
        # actually bound are consulted, because a builder may convert an
        # analyst-facing identifier into the graph's own form on the way in.
        seed_labels: set[str] = set()
        for value in list(case.seed_ids) + [v for b in bindings for v in b.values]:
            seed_labels |= registry.labels_for_id(value, dataset=case.dataset)
        in_scope = bool(seed_labels & set(case.labels))
        if not bindings and draft.params:
            report.findings.append(
                BindingFinding(
                    KIND_UNCHECKED, case.dataset, draft.template, case.labels,
                    case.seed_ids, None, None, (), draft.query, in_scope,
                )
            )
            return
        report.bindings += len(bindings)
        doomed = set(unsatisfiable_bindings(draft, case.dataset, registry))
        for binding in bindings:
            if binding not in doomed:
                continue
            report.findings.append(
                BindingFinding(
                    KIND_MISMATCH, case.dataset, draft.template, case.labels,
                    case.seed_ids, binding.label, binding.property, binding.values,
                    draft.query, in_scope,
                )
            )

    if cases is not None:
        for case in cases:
            _run(case)
    else:
        for name in names:
            for case in enumerate_cases(name, registry, (extra_seeds or {}).get(name, ())):
                _run(case)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--dataset", action="append", dest="datasets")
    parser.add_argument("--kind", action="append", dest="kinds")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument(
        "--seed", action="append", dest="seeds",
        help="extra seed identifier, as DATASET=ID (repeatable)",
    )
    args = parser.parse_args(argv)

    extra: dict[str, list[str]] = {}
    for entry in args.seeds or ():
        dataset, _, value = entry.partition("=")
        extra.setdefault(dataset, []).append(value)
    report = audit_bindings(args.datasets, extra_seeds=extra)
    kinds = args.kinds or [KIND_MISMATCH, KIND_UNCHECKED]
    print(report.summary())
    for kind in kinds:
        findings = report.of_kind(kind)
        if not findings:
            continue
        print(f"\n== {kind} ({len(findings)}) — templates: {', '.join(report.templates_with(kind))}")
        for finding in findings[: args.limit]:
            print("  " + finding.line())
        if len(findings) > args.limit:
            print(f"  … {len(findings) - args.limit} more")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
