"""A small synthetic graph and a random typed-request generator, for the backend
differential test.

The graph is built to hit the cases where Cypher and Gremlin semantics part:
missing properties, one-element lists (never empty lists: the Neo4j
loader keeps ``[]`` and the TinkerGraph loader drops it, and no CypherBench test
graph has one), dates, duplicate names, two
relationship types between the same pair of labels, a self-label relationship,
and edges with start/end years where either may be missing. Its labels share
nothing with any CypherBench graph.

The generator writes requests of every answer kind over every pattern shape the
format allows (a lone subject, one hop either way, two-hop chains, two anchors,
two relationships to the same node, unions, optional counts, time filters).
A request passes when the compiled Cypher and the compiled Gremlin return the
same normalised records.
"""

from __future__ import annotations

import random

from .request import Card

SCHEMA = {
    "name": "fixture",
    "entities": [
        {"label": "Alpha", "properties": {"score": "int", "weight": "float", "born": "date", "tags": "list[str]",
                                          "kind": "str"}},
        {"label": "Beta", "properties": {"rank": "int", "opened": "date", "colors": "list[str]"}},
        {"label": "Gamma", "properties": {"size": "int"}},
    ],
    "relations": [
        {"label": "linkA", "subj_label": "Alpha", "obj_label": "Beta",
         "properties": {"start_year": "int", "end_year": "int"}},
        {"label": "linkB", "subj_label": "Alpha", "obj_label": "Beta", "properties": {}},
        {"label": "toG", "subj_label": "Beta", "obj_label": "Gamma", "properties": {}},
        {"label": "fromG", "subj_label": "Gamma", "obj_label": "Alpha", "properties": {}},
        {"label": "peer", "subj_label": "Alpha", "obj_label": "Alpha", "properties": {}},
    ],
}
# Properties with no repeated values, so "top ... limit" has no ties to break.
UNIQUE = {"score", "born", "rank", "opened"}
TAGS = ["red", "green", "blue", "x", "y"]


def build(seed: int = 7) -> dict:
    rng = random.Random(seed)
    ents, rels = [], []
    years = rng.sample(range(1950, 2020), 70)
    scores = rng.sample(range(1, 500), 60)

    def maybe(v, p=0.25):
        return None if rng.random() < p else v

    for i in range(30):
        ents.append({"eid": f"Alpha#{i}", "label": "Alpha", "name": f"alpha {i % 27}", "properties": {
            "score": maybe(scores[i]), "weight": maybe(round(rng.uniform(1, 9), 1)),
            "born": maybe(f"{years[i]}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"),
            "tags": maybe(rng.sample(TAGS, rng.randint(1, 3))), "kind": maybe(rng.choice(["k1", "k2", "k3"]))}})
    for i in range(15):
        ents.append({"eid": f"Beta#{i}", "label": "Beta", "name": f"beta {i}", "properties": {
            "rank": maybe(scores[30 + i]), "opened": maybe(f"{years[30 + i]}-06-15"),
            "colors": maybe(rng.sample(TAGS, rng.randint(1, 2)))}})
    for i in range(8):
        ents.append({"eid": f"Gamma#{i}", "label": "Gamma", "name": f"gamma {i}",
                     "properties": {"size": maybe(rng.randint(1, 5))}})
    ids = {lab: [e["eid"] for e in ents if e["label"] == lab] for lab in ("Alpha", "Beta", "Gamma")}
    rid = 0

    def edge(lab, s, o, props=None):
        nonlocal rid
        rels.append({"rid": str(rid), "label": lab, "subj_id": s, "obj_id": o, "properties": props or {}})
        rid += 1

    for _ in range(80):
        st = rng.randint(1960, 2015)
        edge("linkA", rng.choice(ids["Alpha"]), rng.choice(ids["Beta"]),
             {"start_year": maybe(st, 0.15), "end_year": maybe(st + rng.randint(0, 10), 0.4)})
    for _ in range(50):
        edge("linkB", rng.choice(ids["Alpha"]), rng.choice(ids["Beta"]))
    for _ in range(30):
        edge("toG", rng.choice(ids["Beta"]), rng.choice(ids["Gamma"]))
    for _ in range(30):
        edge("fromG", rng.choice(ids["Gamma"]), rng.choice(ids["Alpha"]))
    for _ in range(30):
        edge("peer", rng.choice(ids["Alpha"]), rng.choice(ids["Alpha"]))
    return {"schema": SCHEMA, "entities": ents, "relations": rels}


def card() -> Card:
    return Card("fixture", SCHEMA)


class Generator:
    def __init__(self, kg: dict, seed: int = 11) -> None:
        self.c = card()
        self.rng = random.Random(seed)
        self.names = {lab: sorted({e["name"] for e in kg["entities"] if e["label"] == lab}) for lab in self.c.labels}
        self.values: dict[tuple, list] = {}
        for e in kg["entities"]:
            for k, v in e["properties"].items():
                if v is None:
                    continue
                for x in (v if isinstance(v, list) else [v]):
                    self.values.setdefault((e["label"], k), []).append(x)

    def _hop(self, label: str) -> tuple[str, str, bool]:
        """A relationship touching ``label``: (type, other label, n is source)."""
        opts = []
        for t, ends in self.c.rels.items():
            for s, o, _ in ends:
                if s == label:
                    opts.append((t, o, True))
                if o == label:
                    opts.append((t, s, False))
        return self.rng.choice(opts)

    def _edge(self, a: str, b: str, t: str, a_is_src: bool, i: int) -> dict:
        e = {"from": a, "type": t, "to": b} if a_is_src else {"from": b, "type": t, "to": a}
        if t == "linkA" and self.rng.random() < 0.5:
            e["var"] = f"r{i}"
            e["filters"] = [self.rng.choice([
                {"op": "current", "start": "start_year", "end": "end_year"},
                {"op": "during", "year": self.rng.randint(1960, 2020), "start": "start_year", "end": "end_year"},
                {"prop": "end_year", "op": self.rng.choice(["<", ">=", "="]), "value": self.rng.randint(1960, 2020)}])]
        return e

    def _node(self, label: str, named: bool) -> dict:
        d = {"label": label}
        if named:
            d["name"] = self.rng.choice(self.names[label])
        return d

    def _cond(self, label: str) -> dict | None:
        props = [p for p in self.c.labels[label] if p != "name"]
        if not props:
            return None
        p = self.rng.choice(props)
        t = self.c.labels[label][p]
        vals = self.values.get((label, p)) or [1]
        v = self.rng.choice(vals)
        if t.startswith("list"):
            return {"var": "n", "prop": p, "op": self.rng.choice(["contains", "not_contains"]), "value": v}
        if t == "date" and self.rng.random() < 0.5:
            return {"var": "n", "prop": p, "op": self.rng.choice(["=", "<", ">", "<=", ">=", "<>"]),
                    "value": int(str(v)[:4]), "part": "year"}
        return {"var": "n", "prop": p, "op": self.rng.choice(["=", "<", ">", "<=", ">=", "<>"]), "value": v}

    def request(self) -> dict:
        r = self.rng
        lab = r.choice(list(self.c.labels))
        nodes = {"n": {"label": lab}}
        req: dict = {"nodes": nodes}
        shape = r.choice(["alone", "hop", "hop_named", "chain", "star", "double", "union", "optional", "compare"])
        edges: list[dict] = []
        if shape == "compare":
            nodes["n"]["name"] = r.choice(self.names[lab])
            nodes["m0"] = self._node(lab, True)
            props = [p for p, t in self.c.labels[lab].items() if t in ("int", "float") and p != "name"]
            if not props:
                return self.request()
            req["answer"] = {"kind": "compare", "other": "m0", "prop": r.choice(props),
                             "test": r.choice(["which_greater", "equal", "difference"])}
            return req
        if shape in ("hop", "hop_named", "chain", "optional"):
            t, o, src = self._hop(lab)
            nodes["m0"] = self._node(o, shape == "hop_named")
            edges.append(self._edge("n", "m0", t, src, 0))
            if shape == "chain":
                t2, o2, src2 = self._hop(o)
                nodes["m1"] = self._node(o2, True)
                edges.append(self._edge("m0", "m1", t2, src2, 1))
        if shape == "star":
            for i in range(2):
                t, o, src = self._hop(lab)
                nodes[f"m{i}"] = self._node(o, True)
                edges.append(self._edge("n", f"m{i}", t, src, i))
        if shape == "double":
            if lab not in ("Alpha", "Beta"):
                return self.request()
            nodes["m0"] = self._node("Beta" if lab == "Alpha" else "Alpha", False)
            src = lab == "Alpha"
            edges.append(self._edge("n", "m0", "linkA", src, 0))
            edges.append(self._edge("n", "m0", "linkB", src, 1))
        if shape == "union":
            req["any_of"] = []
            for i in range(2):
                t, o, src = self._hop(lab)
                nodes[f"m{i}"] = self._node(o, True)
                req["any_of"].append([self._edge("n", f"m{i}", t, src, i)])
        if shape == "optional":
            t, o, src = self._hop(lab)
            nodes["m1"] = self._node(o, False)
            req["optional"] = [self._edge("n", "m1", t, src, 2)]
        if edges:
            req["edges"] = edges
        if r.random() < 0.35:
            c = self._cond(lab)
            if c:
                req["where"] = [c]
        req["answer"] = self._answer(lab, nodes, shape, req)
        return req

    def _answer(self, lab: str, nodes: dict, shape: str, req: dict) -> dict:
        r = self.rng
        props = {p: t for p, t in self.c.labels[lab].items()}
        if shape == "optional":
            return {"kind": "count_per", "of": "m1"}
        kinds = ["names", "names_with", "values", "count", "count_values", "aggregate", "top"]
        if any(t.startswith("list") for t in props.values()):
            kinds.append("list_items")
        if shape in ("chain", "hop", "hop_named") and "m0" in nodes:
            kinds.append("count_per")
        k = r.choice(kinds)
        if k == "count_per":
            return {"kind": "count_per", "of": "m0"}
        if k in ("names", "count"):
            return {"kind": k}
        if k == "list_items":
            return {"kind": k, "prop": r.choice([p for p, t in props.items() if t.startswith("list")])}
        if k == "aggregate":
            nums = [p for p, t in props.items() if t in ("int", "float", "date")]
            p = r.choice(nums)
            if props[p] == "date":
                return {"kind": k, "fn": r.choice(["max", "min"]), "prop": p, "part": r.choice([None, "year"])}
            return {"kind": k, "fn": r.choice(["max", "min", "avg", "sum"]), "prop": p}
        if k == "top":
            uniq = [p for p in props if p in UNIQUE]
            if not uniq:
                return {"kind": "names"}
            return {"kind": k, "prop": r.choice(uniq), "order": r.choice(["asc", "desc"]),
                    **({"limit": r.choice([1, 3])} if r.random() < 0.6 else {})}
        p = r.choice(list(props))
        if k == "values":
            return {"kind": k, "prop": p, "distinct": r.random() < 0.5}
        return {"kind": k, "prop": p}
