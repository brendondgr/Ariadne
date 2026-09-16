#!/usr/bin/env python3
"""Source-specific query specialists for Ariadne.

Two specialists — the Cypher specialist (MITRE ATT&CK / Neo4j) and the Gremlin
specialist (CAPEC / Gremlin Server) — built on one shared scaffold with four
language-specific swap points (query builder, validator, connector, normalizer).
Each receives a filtered task plus a source card, drafts a bounded read-only
query, validates it deterministically before execution, normalises the evidence
into a shared schema, and hands grounded evidence (not prose) to synthesis.

The language-specific specialists live in the ``cypher`` and ``gremlin``
subpackages and are imported lazily via ``build_specialist`` to keep importing
this package cheap and backend-agnostic.
"""

from __future__ import annotations

from typing import Any

from .config import SpecialistConfig
from .contracts import (
    EvidenceRecord,
    EvaluatorTrace,
    Provenance,
    SpecialistResult,
    SpecialistTask,
)
from .errors import (
    ExecutionError,
    IntakeError,
    NormalizationError,
    SpecialistError,
    ValidationError,
)
from .resolve import ResolvedTask, resolve

__all__ = [
    "SpecialistConfig",
    "SpecialistTask",
    "SpecialistResult",
    "EvidenceRecord",
    "EvaluatorTrace",
    "Provenance",
    "ResolvedTask",
    "resolve",
    "SpecialistError",
    "IntakeError",
    "ValidationError",
    "ExecutionError",
    "NormalizationError",
    "build_specialist",
]


def build_specialist(dataset: str, card: Any, config: SpecialistConfig):
    """Construct the specialist for ``dataset``.

    ``attack`` → Cypher, ``capec`` → Gremlin, ``merged``/``identity`` → Cypher;
    any other dataset → whatever its card's ``runtime_backend`` says.

    Imports the backend subpackage lazily so a caller that only needs one
    backend never imports the other's driver.
    """
    if dataset == "attack":
        from .cypher.specialist import build_cypher_specialist

        return build_cypher_specialist(card, config)
    if dataset == "capec":
        from .gremlin.specialist import build_gremlin_specialist

        return build_gremlin_specialist(card, config)
    if dataset == "merged":
        # The C-015 counterfactual: one Neo4j holding both catalogues, so one
        # Cypher specialist serves questions that the federated arms split
        # across two engines and two languages. Nothing about the specialist
        # changes — it reads its labels, relationships and identifier schemes
        # from the card it is handed, and the merged card declares the union.
        from .cypher.specialist import build_cypher_specialist

        return build_cypher_specialist(card, config)
    if dataset == "identity":
        # EXP-2026-08-011: a schema this codebase has never seen, read from a
        # declared customer catalog rather than derived by scanning instances.
        # The specialist is again unmodified, and that is the entire point of
        # the experiment — if a foreign schema needed a new specialist, C-010's
        # claim that the machinery is card-driven would be false. Whether it
        # actually works on 72 unfamiliar labels is what gets measured.
        from .cypher.specialist import build_cypher_specialist

        return build_cypher_specialist(card, config)
    # Any other dataset — one that arrived with a source card rather than a
    # name this file knows (a Synapse ``export-ariadne`` directory, say) — is
    # dispatched on what its card declares. The four branches above are the
    # documented history of how each MITRE-era dataset was wired; they are
    # kept because their comments are the record, not because the name is
    # needed. Nothing about the specialist changes here either: it reads its
    # labels, relationships and identifier schemes from the card it is handed.
    backend = str(getattr(card, "runtime_backend", "") or "").strip().lower()
    if backend == "neo4j":
        from .cypher.specialist import build_cypher_specialist

        return build_cypher_specialist(card, config)
    if backend == "gremlin":
        from .gremlin.specialist import build_gremlin_specialist

        return build_gremlin_specialist(card, config)
    raise ValueError(
        f"No specialist for dataset {dataset!r}: its card declares "
        f"runtime_backend={backend!r}, expected 'neo4j' or 'gremlin'"
    )
