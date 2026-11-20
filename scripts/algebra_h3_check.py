#!/usr/bin/env python3
"""H3 of EXP-2026-11-021: on today's shapes, the algebra returns the builder's node ids.

For every snapshot row (``docs/evaluation/algebra-2026-11/typed-query-snapshot.jsonl``,
Phase D) whose template is ``typed_step``, ``label_scan``, ``capec_scan`` or
``generic_intersect``:

1. run the builder's own recorded query and parameters on the engine its dataset
   uses (ATT&CK -> Neo4j, CAPEC -> Gremlin), on the **verification pair** (bolt
   5480, ws 6480), never the measured stores;
2. compile the same step with the algebra (``from_typed_step(step, card)``, the
   dataset's own card, the seeds mapped from public to stored ids through the
   store) and run it on the same engine, uncapped;
3. compare the node-id sets. The builder's public ids (ATT&CK ``attack_id``) are
   mapped to stored ids through the store;
4. classify each mismatch. A **documented difference** is one the semantics document
   (``docs/era-2-expansion/operator-algebra.md``) decides against today's builder, and
   is reported apart; anything else is **unexplained** and counts against H3:
   - ``card_invalid_step`` (S3): the algebra refuses a hop the card does not list;
   - ``anchor_of_another_label`` (amendment 4): every seed is a node of another label
     than the step's ``anchor_label`` (today: the placeholder seeds of ``from_step``
     rows), so the algebra says ``anchor_not_found`` where the builder matches the id;
   - ``builder_dropped_filter`` (amendment 4): the step has a filter the builder's
     recorded query does not apply (no ``filterValue``), and the algebra's answer is a
     subset of the builder's;
   - ``walk_returns_to_start`` (amendment 4): the builder's extra nodes are all the
     walk's own start nodes, which a node-acyclic walk never returns. Any other node a
     revisiting walk adds stays unexplained.

Writes ``h3.jsonl`` (one row per snapshot row) and ``h3-summary.json`` to ``--out``.

    uv run python scripts/algebra_h3_check.py --out docs/evaluation/algebra-2026-11/engine-check
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
SNAPSHOT = REPO / "docs/evaluation/algebra-2026-11/typed-query-snapshot.jsonl"
TEMPLATES = ("typed_step", "label_scan", "capec_scan", "generic_intersect")
ENGINE = {"attack": "cypher", "capec": "gremlin"}
UNCAPPED = 1_000_000


def _gid(m) -> str | None:
    """The stored ``id`` property of a Gremlin elementMap (not ``T.id``)."""
    for k, v in dict(m or {}).items():
        if isinstance(k, str) and k == "id":
            return v
    return None


class Mapper:
    """ATT&CK public id (``coalesce(attack_id, id)``) -> stored ids, per label, via Neo4j."""

    def __init__(self, engines):
        self.e = engines
        self.cache: dict[str, list[tuple[str, str]]] = {}

    def load(self, pubs) -> None:
        need = sorted({p for p in pubs if p is not None and p not in self.cache})
        for i in range(0, len(need), 500):
            chunk = need[i:i + 500]
            for p in chunk:
                self.cache[p] = []
            rows = self.e.neo4j_raw("MATCH (n) WHERE coalesce(n.attack_id, n.id) IN $ids "
                                    "RETURN coalesce(n.attack_id, n.id) AS pub, n.id AS id, labels(n)[0] AS label",
                                    {"ids": chunk})
            for r in rows:
                self.cache[r["pub"]].append((r["id"], r["label"]))

    def stored(self, pub: str, label: str | None = None) -> list[str]:
        self.load([pub])
        hits = self.cache.get(pub, [])
        if label:
            narrowed = [i for i, lab in hits if lab == label]
            if narrowed:
                return narrowed
        return [i for i, _ in hits]


def builder_ids(engines, mapper, row: dict, ds: str) -> tuple[set[str], dict]:
    q, params, template = row["query"], row.get("params") or {}, row["template"]
    info: dict = {}
    if ds == "attack":
        recs = engines.neo4j_raw(q, params)
        info["rows"] = len(recs)
        if template == "label_scan":
            pubs = [(r["id"], None) for r in recs]
        elif template == "generic_intersect":
            pubs = [(r["anchor_id"], r.get("anchor_label")) for r in recs]
        else:
            pubs = [(r["neighbour_id"], r.get("neighbour_label")) for r in recs if r.get("neighbour_id") is not None]
        mapper.load([p for p, _ in pubs])
        out: set[str] = set()
        amb = 0
        for p, lab in pubs:
            ids = mapper.stored(p, lab)
            amb += len(ids) > 1
            out.update(ids)
        if amb:
            info["ambiguous_public_ids"] = amb
        return out, info
    recs = engines.gremlin_raw(q, params)
    info["rows"] = len(recs)
    info["truncated_at_1000"] = len(recs) >= 1000
    if template == "capec_scan":
        return {_gid(r) for r in recs if _gid(r)}, info
    return {_gid(r.get("nbr")) for r in recs if _gid(r.get("nbr"))}, info


def stored_seeds(engines, mapper, ds: str, row: dict, seeds: list[str], label: str) -> list[str]:
    if ds == "attack":
        out = []
        for s in seeds:
            out += mapper.stored(s, label)
        return sorted(set(out))
    cands = list((row.get("params") or {}).get("ids") or [])
    if not cands:
        return []
    found = engines.gremlin_raw("g.V().has('id', within(ids)).values('id')", {"ids": cands})
    return sorted(set(found))


def seed_labels(engines, mapper, ds: str, stored: list[str]) -> dict[str, set[str]]:
    """Stored seed id -> its card labels in the store (ATT&CK via Neo4j, CAPEC via Gremlin)."""
    if not stored:
        return {}
    if ds == "attack":
        rows = engines.neo4j_raw("MATCH (n) WHERE n.id IN $ids RETURN n.id AS id, labels(n)[0] AS label",
                                 {"ids": stored})
        pairs = [(r["id"], r["label"]) for r in rows]
    else:
        rows = engines.gremlin_raw("g.V().has('id', within(ids)).project('id', 'label').by('id').by(label())",
                                   {"ids": stored})
        pairs = [(r["id"], r["label"]) for r in rows]
    out: dict[str, set[str]] = {s: set() for s in stored}
    for i, lab in pairs:
        out.setdefault(i, set()).add(lab)
    return out


DOCUMENTED = ("card_invalid_step", "anchor_of_another_label", "builder_dropped_filter", "walk_returns_to_start")


def classify(rec: dict, row: dict, step: dict, labels: dict[str, set[str]]) -> str | None:
    """The documented difference a mismatch is (``DOCUMENTED``), or ``None``: unexplained."""
    if rec.get("equal"):
        return None
    if str(rec.get("error") or "").startswith("InvalidOp"):
        return "card_invalid_step"
    if "error" in rec:
        return None
    only_alg = rec.get("n_only_algebra", len(rec.get("only_algebra") or []))
    want = step.get("anchor_label") or ""
    not_found = ((rec.get("algebra") or {}).get("info") or {}).get("anchor_not_found") or []
    seeds = rec.get("stored_seeds") or []
    if (want and seeds and not_found and rec.get("n_algebra") == 0 and set(seeds) <= set(not_found)
            and all(labels.get(x) and want not in labels[x] for x in seeds)):
        return "anchor_of_another_label"
    if step.get("filter") and "filterValue" not in (row.get("params") or {}) and only_alg == 0:
        return "builder_dropped_filter"
    if (only_alg == 0 and rec.get("n_only_builder", 0) <= len(rec.get("only_builder") or [])
            and set(rec.get("only_builder") or []) <= set(seeds) and rec.get("only_builder")):
        return "walk_returns_to_start"
    return None


def summarise(out_rows: list[dict]) -> dict:
    """Equal rows, documented differences (by kind) and unexplained mismatches; H3 counts the last."""
    by = defaultdict(Counter)
    for r in out_rows:
        kind = ("equal" if r["equal"] else f"documented:{r['documented']}" if r.get("documented")
                else "error" if "error" in r else "differ")
        by[f"{r['dataset']}/{r['template']}"][kind] += 1
    eq = sum(r["equal"] for r in out_rows)
    documented = Counter(r["documented"] for r in out_rows if not r["equal"] and r.get("documented"))
    unexplained = [r["key"] for r in out_rows if not r["equal"] and not r.get("documented")]
    n = len(out_rows)
    return {"rows": n, "equal": eq, "share": round(eq / n, 4) if n else None,
            "documented": dict(sorted(documented.items())), "n_documented": sum(documented.values()),
            "unexplained": len(unexplained),
            "share_equal_or_documented": round((eq + sum(documented.values())) / n, 4) if n else None,
            "by_template": {k: dict(v) for k, v in sorted(by.items())},
            "documented_differences": {k: [r["key"] for r in out_rows if r.get("documented") == k]
                                       for k in sorted(documented)},
            "mismatches": unexplained}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--snapshot", default=str(SNAPSHOT))
    a = ap.parse_args(argv)
    from utils.agent.catalog import load_all
    from utils.specialists.algebra.base import Anchors, Common, Count, Describe, Expand, Nodes, Walk
    from utils.specialists.algebra.compiled import Backend
    from utils.specialists.algebra.differential import Engines, compile_on
    from utils.specialists.algebra.from_typed_step import from_typed_step

    cats, _ = load_all(REPO / "data", live=False)
    cards = {ds: cats[ds].model for ds in ENGINE}
    engines = Engines()
    mapper = Mapper(engines)
    out_rows = []
    for line in Path(a.snapshot).read_text().splitlines():
        row = json.loads(line)
        if row.get("template") not in TEMPLATES:
            continue
        ds, step, seeds = json.loads(row["key"])
        engine = ENGINE[ds]
        rec: dict = {"key": row["key"], "dataset": ds, "engine": engine, "template": row["template"],
                     "kind": step.get("kind")}
        labels: dict[str, set[str]] = {}
        try:
            b_ids, binfo = builder_ids(engines, mapper, row, ds)
            rec["builder"] = binfo
            card = cards[ds]
            anchors = stored_seeds(engines, mapper, ds, row, seeds, step.get("anchor_label") or "")
            rec["stored_seeds"] = anchors
            labels = seed_labels(engines, mapper, ds, anchors)
            # A seed that matches no node stays as written: the algebra says
            # anchor_not_found (S12), where the builder returns no rows.
            node = from_typed_step(dict(step, anchor_ids=anchors or list(seeds)), card)
            if isinstance(node, (Expand, Count)):
                walk = node.walk if isinstance(node, Expand) else node.of
                node = Expand(walk)
            backend = (Backend.cypher if engine == "cypher" else Backend.gremlin)(card, row_cap=UNCAPPED)
            c = compile_on(node, backend)
            r = engines.run(c, engine)
            alg = {x["id"] for x in r.rows}
            rec["algebra"] = {"op": type(node).__name__, "total": r.total, "complete": r.complete,
                              "info": {k: v for k, v in r.info.items() if v}}
            rec["n_builder"], rec["n_algebra"] = len(b_ids), len(alg)
            rec["equal"] = b_ids == alg
            if not rec["equal"]:
                rec["only_builder"] = sorted(b_ids - alg)[:50]
                rec["only_algebra"] = sorted(alg - b_ids)[:50]
                rec["n_only_builder"], rec["n_only_algebra"] = len(b_ids - alg), len(alg - b_ids)
        except Exception as exc:  # noqa: BLE001 - recorded
            rec["error"] = f"{type(exc).__name__}: {exc}"[:500]
            rec["equal"] = False
        rec["documented"] = classify(rec, row, step, labels)
        out_rows.append(rec)
    engines.close()
    outd = Path(a.out)
    outd.mkdir(parents=True, exist_ok=True)
    with open(outd / "h3.jsonl", "w") as fh:
        for r in out_rows:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    summary = summarise(out_rows)
    (outd / "h3-summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps({k: summary[k] for k in ("rows", "equal", "share", "documented", "unexplained",
                                              "share_equal_or_documented", "by_template")}, indent=1))
    return 0 if summary["unexplained"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
