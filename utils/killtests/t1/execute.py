"""Read-only execution and result normalisation for T1.

**Cypher** runs in a READ access-mode session (Neo4j rejects writes there).
**Gremlin** runs as a script with ``g`` rebound to a ``ReadOnlyStrategy``
traversal source, after a blocklist rejects scripts that could reach outside a
traversal (lambdas touching the system, ``graph.`` mutation, class loading).
A blocked script, a parse error or a timeout counts as a wrong answer.

**Normalisation** (identical for both languages and for the gold): every result
row becomes a tuple of its scalar values, sorted, each value canonicalised
(dates as ISO strings, integral floats as ints, other floats to 6 places,
one-element lists flattened). A result is the multiset of its rows. Two results
are equal when their multisets are equal: column order, column names and row
order are ignored; duplicates count.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

_GREMLIN_BLOCK = re.compile(
    r"(addV|addE|drop\s*\(|mergeV|mergeE|\.property\s*\(|graph\s*\.|System\s*\.|Runtime|"
    r"Class\s*\.|new\s+[A-Z]|getClass|evaluate\s*\(|execute\s*\(|\bfile\b|File\s*\()"
)


def canon(v: Any) -> str:
    if v is None:
        return "null"
    if hasattr(v, "iso_format"):  # neo4j Date / DateTime
        return v.iso_format()[:10] if type(v).__name__ == "Date" else v.iso_format()
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:.6f}".rstrip("0").rstrip(".")
    if isinstance(v, (list, tuple, set)):
        vals = list(v)
        if len(vals) == 1:
            return canon(vals[0])
        return "[" + ",".join(sorted(canon(x) for x in vals)) + "]"
    if isinstance(v, dict):
        return "{" + ",".join(sorted(f"{k}:{canon(x)}" for k, x in v.items())) + "}"
    return str(v)


def _row_values(row: Any) -> list[Any]:
    if isinstance(row, dict):
        out = []
        for v in row.values():
            out.append(v)
        return out
    if isinstance(row, (list, tuple)):
        return list(row)
    return [row]


def normalise(rows: list[Any]) -> Counter:
    return Counter(tuple(sorted(canon(v) for v in _row_values(r))) for r in rows)


def same(a: list[Any], b: list[Any]) -> bool:
    return normalise(a) == normalise(b)


def run_cypher(driver, query: str, timeout_s: float = 30.0) -> list[dict]:
    import neo4j
    from neo4j import Query

    with driver.session(default_access_mode=neo4j.READ_ACCESS) as s:
        res = s.run(Query(query, timeout=timeout_s))
        return [dict(r) for r in res]


def gremlin_blocked(script: str) -> str | None:
    m = _GREMLIN_BLOCK.search(script or "")
    return m.group(0) if m else None


def run_gremlin(client, script: str, timeout_s: float = 30.0) -> list[Any]:
    bad = gremlin_blocked(script)
    if bad:
        raise PermissionError(f"blocked step: {bad}")
    wrapped = "g = g.withStrategies(ReadOnlyStrategy.instance())\n" + script
    return client.submit(wrapped).all().result(timeout=timeout_s)
