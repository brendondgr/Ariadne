"""Select the Text2Cypher questions and compute their gold rows, mechanically.

From the 2024v1 **test** split, every row whose ``database_reference_alias`` is one of the
three local graphs, deduplicated on (graph, question). A question is kept only if its gold
Cypher, run read-only on the local copy:

- runs without error within 30 s;
- returns at least one row;
- returns only scalar values or lists of them (no nodes, relationships, paths or points,
  which cannot be compared across backends);
- does not use ``LIMIT`` without ``ORDER BY`` (an arbitrary subset).

Every exclusion is counted by reason. No question text is read by this selection.

    uv run --with pyarrow python -m utils.killtests.t2c.gold
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter

from ..stages import Stage
from ..t1.execute import normalise, run_cypher
from .load import GRAPHS, OUT, driver

ALIAS = {f"neo4jlabs_demo_db_{g}": g for g in GRAPHS}
_LIMIT = re.compile(r"\bLIMIT\b", re.I)
_ORDER = re.compile(r"\bORDER\s+BY\b", re.I)


def _scalar(v) -> bool:
    if v is None or isinstance(v, (str, int, float, bool)):
        return True
    if isinstance(v, (list, tuple)):
        return all(_scalar(x) for x in v)
    if isinstance(v, dict):
        return False
    return hasattr(v, "iso_format")  # temporal values are scalars


def select() -> dict:
    st = Stage(OUT, "gold")
    if st.done:
        return st.load()
    import pyarrow.parquet as pq

    from ..config import REPO

    rows = pq.read_table(REPO / "data/external/text2cypher/test.parquet").to_pylist()
    seen, out, why = set(), [], Counter()
    drivers = {g: driver(g) for g in GRAPHS}
    try:
        for r in rows:
            g = ALIAS.get(r["database_reference_alias"])
            if not g:
                continue
            k = (g, r["question"].strip())
            if k in seen:
                why["duplicate"] += 1
                continue
            seen.add(k)
            cy = r["cypher"].strip()
            if _LIMIT.search(cy) and not _ORDER.search(cy):
                why["limit_without_order"] += 1
                continue
            try:
                res = run_cypher(drivers[g], cy)
            except Exception:  # noqa: BLE001
                why["gold_error"] += 1
                continue
            if not res:
                why["empty"] += 1
                continue
            if not all(_scalar(v) for row in res for v in row.values()):
                why["non_scalar"] += 1
                continue
            qid = hashlib.sha1(f"{g}|{r['question']}".encode()).hexdigest()[:16]
            out.append({"qid": qid, "graph": g, "nl_question": r["question"], "gold_cypher": cy,
                        "data_source": r["data_source"], "instance_id": r["instance_id"], "n_rows": len(res),
                        "_gold_norm": [[list(k2), v] for k2, v in normalise(res).items()]})
    finally:
        for d in drivers.values():
            d.close()
    st.finish({"questions": out, "excluded": dict(why), "by_graph": dict(Counter(q["graph"] for q in out)),
               "by_source": dict(Counter(q["data_source"] for q in out))})
    return st.load()


def main() -> int:
    from utils.config import load_env

    load_env()
    s = select()
    print({k: s[k] for k in ("excluded", "by_graph", "by_source")}, len(s["questions"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
