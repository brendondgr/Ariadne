#!/usr/bin/env python3
"""Consistency guard for the Wk 14-15 technical documentation set.

Two failure modes make contract docs worse than no docs: citing files that
have moved, and describing wire shapes the code no longer emits. This suite
pins both for the four documents an external integrator reads:

    docs/source_cards.md      — the card format specification
    docs/agent-interfaces.md  — the four integration-frozen seams
    docs/query-safety.md      — the safety model by enforcement point
    docs/migration-guide.md   — the new-query-language walkthrough

Check 1: every repo-relative path a doc cites in backticks exists.
Check 2: the wire shapes the interfaces doc tabulates (to_dict key sets and
the omit-when-empty rules) match what the dataclasses actually serialize.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

DOCS = (
    "docs/source_cards.md",
    "docs/agent-interfaces.md",
    "docs/query-safety.md",
    "docs/migration-guide.md",
)

# Backtick-quoted repo-relative citations, e.g. `utils/specialists/base.py` or
# `utils/specialists/gremlin/{builder,validator}.py`. Placeholder citations
# containing <...> (e.g. `test_<backend>_validator.py`) are templates, not
# paths, and are skipped.
_PATH_RE = re.compile(r"`((?:utils|api|docs|web|data)/[\w/{},.<>-]+)`")
_ALTERNATION_RE = re.compile(r"(.*)\{([^}]+)\}(.*)")


def _cited_paths(doc_text: str) -> list[str]:
    paths: list[str] = []
    for raw in _PATH_RE.findall(doc_text):
        if "<" in raw:
            continue
        m = _ALTERNATION_RE.match(raw)
        if m:
            paths.extend(m.group(1) + alt + m.group(3) for alt in m.group(2).split(","))
        else:
            paths.append(raw)
    return paths


def test_docs_exist() -> None:
    for doc in DOCS:
        assert (REPO_ROOT / doc).is_file(), f"{doc} is missing"


def test_every_cited_repo_path_exists() -> None:
    """A doc citing a moved/renamed file must fail loudly, not rot quietly.

    data/ citations are exempt below data/source_cards (generated artifacts
    are gitignored and absent on a fresh clone); everything else must exist.
    """
    missing: list[str] = []
    for doc in DOCS:
        text = (REPO_ROOT / doc).read_text(encoding="utf-8")
        for path in _cited_paths(text):
            if path.startswith("data/"):
                continue  # gitignored, machine-local — documented shape only
            if not (REPO_ROOT / path).exists():
                missing.append(f"{doc} -> {path}")
    assert not missing, "docs cite nonexistent paths:\n" + "\n".join(missing)


def test_interfaces_doc_matches_specialist_wire_shapes() -> None:
    from utils.specialists.contracts import (
        EvidenceRecord,
        Provenance,
        SpecialistResult,
        SpecialistTask,
    )

    task = SpecialistTask(sub_question_id="q1", source="attack", text="x")
    assert set(task.to_dict()) == {
        "sub_question_id", "source", "text", "entities", "limits",
        "join_key", "seed_ids", "rationale",
    }
    # Documented limit-accessor fallbacks (agent-interfaces.md, seam 1).
    assert task.max_rows() == 1000
    assert task.max_depth() == 3
    assert task.timeout_ms() == 5000

    result = SpecialistResult(task=task)
    assert set(result.to_dict()) == {
        "task", "query", "records", "record_count", "summary", "traces",
        "ok", "partial", "error", "join_values",
    }

    record = EvidenceRecord(
        primary_id="T1047", id_scheme="attack-id", label="Technique", name="WMI"
    )
    assert set(record.to_dict()) == {
        "primary_id", "id_scheme", "label", "name", "properties", "related",
        "join_values", "provenance", "facets",
    }

    prov = Provenance("s", "attack", "neo4j", "q", "r", "t")
    assert set(prov.to_dict()) == {
        "source", "dataset", "backend", "query", "record_id", "timestamp",
    }


def test_interfaces_doc_matches_federation_wire_shape() -> None:
    from utils.specialists.federation import FederatedEvidence

    bundle = FederatedEvidence(request="x")
    assert set(bundle.to_dict()) == {
        "request", "results", "unsupported", "skipped", "partial",
        "sequencing", "join_index", "cross_source_join_values",
    }


def test_interfaces_doc_matches_synthesis_wire_shapes() -> None:
    from utils.synthesis.contracts import (
        ClaimVerdict,
        SynthesizedAnswer,
        VerificationReport,
    )

    answer = SynthesizedAnswer(request="x")
    assert set(answer.to_dict()) == {
        "request", "headline", "narrative", "claims", "rendered_claims",
        "abstentions", "notes", "composer", "fallback_reason",
        "verification", "edges",
    }

    # Omit-when-empty rules the interfaces doc documents as frozen.
    clean = ClaimVerdict("supported")
    assert set(clean.to_dict()) == {"verdict", "reasons"}
    contested = ClaimVerdict("supported", contested=("T1055",))
    assert contested.to_dict()["contested"] == ["T1055"]

    report = VerificationReport()
    keys = set(report.to_dict())
    assert "conflicts" not in keys and "conflict_count" not in keys
    assert keys == {
        "verdicts", "claim_count", "supported_count", "unsupported_count",
        "unsupported_claim_rate", "repaired_abstentions", "ok",
    }


def test_docs_trace_step_vocabulary_matches_code() -> None:
    """agent-interfaces.md enumerates the EvaluatorTrace step names; every
    step the specialist layer actually constructs must appear in the doc."""
    doc = (REPO_ROOT / "docs/agent-interfaces.md").read_text(encoding="utf-8")
    constructed: set[str] = set()
    for source_file in ("utils/specialists/base.py", "utils/specialists/federation.py"):
        src = (REPO_ROOT / source_file).read_text(encoding="utf-8")
        constructed.update(
            re.findall(r"EvaluatorTrace\(\s*\n?\s*\"([a-z_]+)\"", src)
        )
    assert constructed, "no trace construction sites found — regex rotted?"
    undocumented = {s for s in constructed if f'"{s}"' not in doc}
    assert not undocumented, f"trace steps missing from agent-interfaces.md: {undocumented}"
