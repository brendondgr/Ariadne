"""No module this plan added carries a catalogue identifier or entity name in its code.

Plan `docs/plans/2026-09-15-open-question-correctness.md`, Step 10's
portability contract. Every mechanism the plan shipped is supposed to read the
card, the schema registry, the join-key registry or the graph's own records —
never a MITRE fact. This test walks the AST of each module the plan added and
checks every string constant and every name against the identifier grammars
and the two catalogue names. Docstrings and comments are exempt: they may
*explain* with an example; the code may not *depend* on one.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]

#: Modules the plan added. Modified pre-existing modules are not listed: their
#: catalogue-specific parts predate the plan and are recorded elsewhere.
ADDED = [
    "utils/planner/form_plan.py",
    "utils/specialists/schema/rerank.py",
    "utils/synthesis/disclosure.py",
    "utils/orchestration/agents/assess/facets.py",
    "scripts/generate_relation_lexicon.py",
]

_ID = re.compile(r"\b(?:T\d{4}(?:\.\d{3})?|G\d{4}|S\d{4}|M\d{4}|TA\d{4}|C\d{4}|CAPEC-\d+|CWE-\d+)\b")
_NAMES = re.compile(r"(?i)\b(att&ck|mitre|capec)\b")
_ALLOWED_LITERALS = {"attack", "capec"}  # never used as code literals; asserted below


def _code_strings(tree: ast.AST) -> list[tuple[int, str]]:
    """String constants that are not docstrings."""
    doc_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_nodes.add(id(body[0].value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in doc_nodes:
            out.append((node.lineno, node.value))
    return out


@pytest.mark.parametrize("rel", ADDED)
def test_added_module_names_no_catalogue_entity(rel: str) -> None:
    path = REPO / rel
    tree = ast.parse(path.read_text(), filename=str(path))
    offenders = []
    for lineno, text in _code_strings(tree):
        if _ID.search(text) or _NAMES.search(text) or text.strip().lower() in _ALLOWED_LITERALS:
            offenders.append((lineno, text[:60]))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and _ID.fullmatch(node.id or ""):
            offenders.append((node.lineno, node.id))
    assert not offenders, f"{rel} carries catalogue literals in code: {offenders}"
