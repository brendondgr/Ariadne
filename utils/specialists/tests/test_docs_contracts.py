#!/usr/bin/env python3
"""Consistency guard for the maintained documentation set.

Two failure modes make docs worse than no docs: citing files that have moved,
and describing wire shapes the code no longer emits. This suite pins both.

``DOCS`` is the contract set an external integrator reads (source cards, the
four frozen seams, the safety model, the migration guide) plus the documents
that orient a newcomer (README, structure, architecture, goals, commands, the
changelog guide) and the evaluation indexes. ``MAINTAINED_DOCS`` adds every canonical skill.

``docs/plans/`` is deliberately excluded: it is a dated historical record, and a
plan that cites the tree as it stood when the plan was written is correct, not
stale.

``docs/research/`` **is** checked — it is the live research record, not an
archive — with two exclusions named in ``RESEARCH_EXCLUDED``: the dated audit
snapshot, which is never edited in place, and ``templates/``, whose placeholders
are not paths.

Check 1: every repo-relative path a doc cites in backticks exists.
Check 2: every relative markdown link resolves.
Check 3: the wire shapes the interfaces doc tabulates (to_dict key sets and the
omit-when-empty rules) match what the dataclasses actually serialize.
Check 4: every canonical skill has exactly one pointer in each agent folder,
and the pointer folders carry no instructions of their own.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

DOCS = (
    "README.md",
    "docs/RESULTS.md",
    "docs/structure.md",
    "docs/ARCHITECTURE.md",
    "docs/goals.md",
    "docs/commands.md",
    "docs/source_cards.md",
    "docs/agent-interfaces.md",
    "docs/query-safety.md",
    "docs/migration-guide.md",
    "docs/CHANGELOG.md",
    "docs/evaluation/README.md",
    "docs/evaluation/experiments/README.md",
    "CONTRIBUTING.md",
)

SKILLS_ROOT = Path("docs/skills")
RESEARCH_ROOT = Path("docs/research")
AGENT_POINTER_DIRS = (".claude/skills", ".agents/skills")

#: The research record's living ledgers and per-experiment documents are checked
#: like any maintained doc. ``audit-2026-08-03.md`` is excluded: it is a dated
#: snapshot, deliberately not edited in place, and its body cites files that were
#: later removed — its AMENDMENTS section records where that content went.
#: ``templates/`` is excluded because template placeholders are not paths.
#: ``AGENT_INSTRUCTIONS.md`` is also excluded: it is the contract installed
#: verbatim from its source, and its section 6 carries fenced *example* markdown
#: (the README snippet to paste) whose links are illustrations, not citations.
#: ``experiments/`` (added 2026-09-09) and ``history/`` are excluded for the same
#: reason as the audit: a completed experiment is an append-only record of what
#: existed on its run date, and a raw artifact it cites may since have been
#: deleted or overwritten — that fact belongs in the experiment's ISSUES.md and
#: in its hashed POINTERS.md (which the research validator checks), not in a
#: silent edit of RESULTS.md. ``OPEN_QUESTIONS-ANSWERED.md`` and
#: ``CLAIMS-HISTORY.md`` are verbatim archives and are excluded likewise.
RESEARCH_EXCLUDED = (
    "audit-2026-08-03.md",
    "templates/",
    "AGENT_INSTRUCTIONS.md",
    "experiments/",
    "history/",
    "OPEN_QUESTIONS-ANSWERED.md",
    "CLAIMS-HISTORY.md",
)


def _skill_names() -> list[str]:
    root = REPO_ROOT / SKILLS_ROOT
    return sorted(p.name for p in root.iterdir() if (p / "SKILL.md").is_file())


def _research_docs() -> list[str]:
    """Every research-record markdown file that is a maintained document."""
    root = REPO_ROOT / RESEARCH_ROOT
    if not root.is_dir():
        return []
    return sorted(
        str(p.relative_to(REPO_ROOT))
        for p in root.rglob("*.md")
        if not any(token in str(p.relative_to(REPO_ROOT)) for token in RESEARCH_EXCLUDED)
    )


def _maintained_docs() -> list[str]:
    """DOCS plus every canonical skill file and every research-record document."""
    skills = sorted(
        str(p.relative_to(REPO_ROOT))
        for p in (REPO_ROOT / SKILLS_ROOT).rglob("*.md")
    )
    return [*DOCS, *skills, *_research_docs()]

# Backtick-quoted repo-relative citations, e.g. `utils/specialists/base.py` or
# `utils/specialists/gremlin/{builder,validator}.py`. Placeholder citations
# containing <...> (e.g. `test_<backend>_validator.py`) are templates, not
# paths, and are skipped.
_PATH_RE = re.compile(r"`((?:utils|api|docs|web|data)/[\w/{},.<>-]+)`")
_ALTERNATION_RE = re.compile(r"(.*)\{([^}]+)\}(.*)")


_FILE_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".mjs", ".css", ".md", ".mdc", ".json",
    ".jsonl", ".yml", ".yaml", ".svg", ".ipynb", ".xml", ".csv", ".sql",
}


def _is_dotted_symbol(raw: str) -> bool:
    """``utils/conversation.iter_conversation`` is a symbol, not a path."""
    tail = raw.rsplit("/", 1)[-1]
    if "." not in tail:
        return False
    return not any(tail.endswith(suffix) for suffix in _FILE_SUFFIXES)


def _cited_paths(doc_text: str) -> list[str]:
    paths: list[str] = []
    for raw in _PATH_RE.findall(doc_text):
        if "<" in raw or _is_dotted_symbol(raw):
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
    for doc in _maintained_docs():
        text = (REPO_ROOT / doc).read_text(encoding="utf-8")
        for path in _cited_paths(text):
            if path.startswith("data/"):
                continue  # gitignored, machine-local — documented shape only
            if path.startswith("docs/evaluation/golden/"):
                continue  # gitignored harness run output; regenerated, not committed
            if not (REPO_ROOT / path).exists():
                missing.append(f"{doc} -> {path}")
    assert not missing, "docs cite nonexistent paths:\n" + "\n".join(missing)


def test_every_relative_markdown_link_resolves() -> None:
    """A [text](target) link into the repo must land on something real.

    Catches exactly the drift that moving a file introduces: the mover updates
    the file and forgets the eight documents pointing at it.
    """
    link_re = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
    broken: list[str] = []
    for doc in _maintained_docs():
        doc_path = REPO_ROOT / doc
        for target in link_re.findall(doc_path.read_text(encoding="utf-8")):
            target = target.split("#")[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (doc_path.parent / target).resolve().exists():
                broken.append(f"{doc} -> {target}")
    assert not broken, "docs contain broken relative links:\n" + "\n".join(broken)


def test_every_skill_has_a_pointer_in_every_agent_folder() -> None:
    """`docs/skills/` is canonical; the agent folders mirror it exactly.

    A skill with no pointer is invisible to the agent that folder serves, and a
    pointer with no skill sends it to a file that does not exist.
    """
    names = set(_skill_names())
    assert names, "no canonical skills found — did docs/skills/ move?"

    for folder in AGENT_POINTER_DIRS:
        root = REPO_ROOT / folder
        assert root.is_dir(), f"{folder} is missing"
        present = {p.name for p in root.iterdir() if (p / "SKILL.md").is_file()}
        assert present == names, (
            f"{folder} is out of sync with docs/skills/: "
            f"missing={sorted(names - present)} extra={sorted(present - names)}"
        )



def test_agent_folders_contain_no_instructions() -> None:
    """The repository's own rule: agent folders are pointers only.

    A pointer is short and names the canonical file. Anything longer is a
    duplicated instruction set that will drift away from docs/skills/.
    """
    offenders: list[str] = []
    for folder in AGENT_POINTER_DIRS:
        for path in (REPO_ROOT / folder).rglob("*"):
            if not path.is_file() or path.suffix != ".md":
                continue
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(REPO_ROOT)
            if "docs/skills/" not in text:
                offenders.append(f"{rel}: does not point at docs/skills/")
            elif len(text.splitlines()) > 20:
                offenders.append(f"{rel}: {len(text.splitlines())} lines — not a pointer")
    assert not offenders, (
        "agent folders must be pointers only:\n" + "\n".join(offenders)
    )


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
        "abstentions", "notes", "composer", "narrative_source",
        "fallback_reason", "verification", "edges",
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
