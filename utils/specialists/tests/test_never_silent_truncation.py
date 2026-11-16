"""Era 2 Step 5: nothing is cut silently.

1. A source scan: every row cap (``LIMIT`` / ``.limit(``) in the connectors,
   query builders and primitives is the trailing row cap the validators govern,
   whose cut the connectors and the scaffold detect. Any other cap fails the scan.
2. The scaffold marks a result that filled its ceiling exactly as partial when
   one more row exists, and not when it does not.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "cypher/connector.py", ROOT / "gremlin/connector.py", ROOT / "cypher/builder.py",
         ROOT / "gremlin/builder.py", *sorted((ROOT / "primitives").glob("*.py"))]
CAP = re.compile(r"\bLIMIT\b|\.limit\(", re.IGNORECASE)
#: The governed row cap: a trailing limit written from the task's own row limit (``lim``).
GOVERNED = re.compile(r"\.limit\(\{lim\}\)|LIMIT \{lim\}|LIMIT \$limit")


def _caps():
    """Every string literal (f-strings included) that builds a capped query.

    Read from the syntax tree, so comments and docstrings that merely mention a
    cap are not counted; only literals that can reach a database are.
    """
    import ast

    for path in FILES:
        rel = str(path.relative_to(ROOT))
        tree = ast.parse(path.read_text())
        docstrings = {id(n.value) for n in ast.walk(tree)
                      if isinstance(n, ast.Expr) and isinstance(getattr(n, "value", None), ast.Constant)}
        inside_fstring = {id(v) for n in ast.walk(tree) if isinstance(n, ast.JoinedStr) for v in n.values}
        for node in ast.walk(tree):
            if id(node) in docstrings or id(node) in inside_fstring:
                continue
            if isinstance(node, ast.JoinedStr) or (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                text = ast.unparse(node)
                if CAP.search(text):
                    yield rel, text


def test_every_row_cap_is_the_governed_one():
    stray = [(rel, text) for rel, text in _caps() if not GOVERNED.search(text)]
    assert not stray, f"row caps outside the truncation check: {stray}"


def test_the_scan_actually_finds_the_caps():
    assert sum(1 for _ in _caps()) >= 10


def test_the_scan_would_catch_a_stray_cap(tmp_path, monkeypatch):
    bad = tmp_path / "bad.py"
    bad.write_text('def q(n):\n    """LIMIT in a docstring is fine."""\n    return f"MATCH (n) RETURN n LIMIT 25"\n')
    import sys

    monkeypatch.setattr(sys.modules[__name__], "FILES", [bad])
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    assert [t for _, t in _caps()] == ["f'MATCH (n) RETURN n LIMIT 25'"]


class _Conn:
    def __init__(self, n_rows):
        self.n_rows, self.calls = n_rows, []

    def run(self, query, params, limits):
        self.calls.append(query)
        return [{"i": i} for i in range(min(self.n_rows, limits["max_result_rows"]))]


class _Val:
    def cap_at(self, query, rows):
        return f"{query} PROBE {rows}"


def _truncated(n_rows, ceiling):
    from utils.specialists.base import QuerySpecialist

    spec = QuerySpecialist.__new__(QuerySpecialist)
    spec.connector, spec.validator = _Conn(n_rows), _Val()
    rows = spec.connector.run("Q", {}, {"max_result_rows": ceiling})
    return spec._truncated(rows, "Q", {}, {"max_result_rows": ceiling}), spec.connector.calls


@pytest.mark.parametrize("n_rows, ceiling, want, probes", [
    (3, 5, False, 0),       # under the ceiling: complete, no probe
    (5, 5, False, 1),       # exactly the ceiling and nothing more: probed, complete
    (9, 5, True, 1),        # more exist: probed, cut
])
def test_a_full_ceiling_is_probed(n_rows, ceiling, want, probes):
    truncated, calls = _truncated(n_rows, ceiling)
    assert truncated is want and len(calls) == 1 + probes
    if probes:
        assert calls[-1] == f"Q PROBE {ceiling + 1}"


def test_rows_that_know_they_were_cut_are_believed():
    from utils.specialists.base import QuerySpecialist
    from utils.specialists.rows import Rows

    spec = QuerySpecialist.__new__(QuerySpecialist)
    spec.connector, spec.validator = _Conn(0), _Val()
    assert spec._truncated(Rows([{}], truncated=True), "Q", {}, {"max_result_rows": 9}) is True
    assert spec._truncated(Rows([{}] * 9, truncated=False), "Q", {}, {"max_result_rows": 9}) is False
    assert spec.connector.calls == []


def test_a_validator_that_cannot_raise_its_cap_leaves_a_full_result_unproven():
    from utils.specialists.base import QuerySpecialist

    spec = QuerySpecialist.__new__(QuerySpecialist)
    spec.connector, spec.validator = _Conn(5), object()
    assert spec._truncated([{}] * 5, "Q", {}, {"max_result_rows": 5}) is True


@pytest.mark.parametrize("mod, query, want", [
    ("cypher", "MATCH (n) RETURN n LIMIT 1000", "MATCH (n) RETURN n LIMIT 1001"),
    ("cypher", "MATCH (n) RETURN n", "MATCH (n) RETURN n LIMIT 1001"),
    ("gremlin", "g.V().limit(1000)", "g.V().limit(1001)"),
    ("gremlin", "g.V()", "g.V().limit(1001)"),
])
def test_validators_raise_their_cap_for_the_probe(mod, query, want):
    if mod == "cypher":
        from utils.specialists.cypher.validator import CypherValidator as V
    else:
        from utils.specialists.gremlin.validator import GremlinValidator as V
    assert V().cap_at(query, 1001) == want
