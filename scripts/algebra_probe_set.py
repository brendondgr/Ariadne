#!/usr/bin/env python3
"""Phase G's probe set for the operator algebra (Era 2, Step 9).

The census (EXP-2026-11-020) found observed demand for one new operator only
(verify), so the probe set is not weighted by frequency: it draws about
``TARGET`` items per operator per dataset, with verify weighted three times.
Semantics: ``docs/era-2-expansion/operator-algebra.md``.

    uv run python scripts/algebra_probe_set.py generate
    uv run python scripts/algebra_probe_set.py bank --wording reworded.jsonl

``generate`` (read-only on the measured stores):
1. draws structured items per operator from each card (attack, capec), with
   parameters taken from values actually stored;
2. runs each item's operator tree on its dataset's runtime engine (ATT&CK on
   Neo4j bolt :5456 through ``compile_cypher``; CAPEC on Gremlin :6455 through
   ``compile_gremlin``) and keeps the finished result as gold. Items whose gold
   is empty (unless deliberately negative), incomplete (over the row cap or
   partial) or whose anchors are not found are dropped and counted;
3. adds the external items that are now answerable (Step 6's medians and
   shortest chains; a sample of AttackQA's verify rows) and writes
   ``step6-relabel.json``;
4. splits the items into ``tune`` and ``measure`` halves, deterministically and
   stratified by (operator, dataset);
5. writes ``probe-structured.json`` and ``wording-input.jsonl``.

``bank`` turns the structured items plus reworded questions into two banks in
the dev-bank format that ``utils/evaluation/experiment_untruncated.py --bank``
loads: ``probe-tune.json`` and ``probe-measure.json``.

No language model runs here, nothing is written to a store, and no sealed bank
is opened. AttackQA text is not written out (D-020): its items carry our own
template question and the row id only.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = REPO / "docs/evaluation/algebra-2026-11/probe"
SHAPE = REPO / "docs/evaluation/shape-count-2026-11"
STEP6_BANKS = {
    "attack": REPO / "docs/evaluation/banks/card-sonnet-2026-11-16-attack-exit-tuning/bank.json",
    "capec": REPO / "docs/evaluation/banks/card-sonnet-2026-11-16-capec-exit-tuning/bank.json",
}
EXTERNAL = REPO / ".cache/external-benchmarks"
SEALED = re.compile(r"heldout|holdout|fresh", re.I)
SEED = 20261120
NEO4J_URI = "bolt://localhost:5456"
GREMLIN_URI = "ws://localhost:6455/gremlin"
ROW_CAP = 1000  # the runtime row cap; gold must be complete under it
SAMPLE_CAP = 100_000  # for drawing parameters only, never for gold
MAX_GOLD_IDS = 300  # a node answer longer than this cannot be enumerated in an answer
MAX_RANK_IDS = 25  # a rank whose ties blow past this is degenerate
NEG_SHARE = 0.10  # at most this share of items are deliberate negatives
TIMEOUT_S = 60

#: Items per operator per dataset. Verify carries three times the weight (census).
TARGET = {"O1": 10, "O2": 10, "O3": 10, "O4": 30, "O5": 10, "O6": 10, "O7": 10, "O7b": 10, "O8": 10}
SWITCH = {"O7b": "extended", "O8": "extended"}  # everything else is "core"
ATTACKQA_VERIFY_SAMPLE = 15

LABEL_NOUN = {
    # ATT&CK
    "Technique": "technique", "SubTechnique": "sub-technique", "Group": "group", "Software": "software",
    "Campaign": "campaign", "Mitigation": "mitigation", "Tactic": "tactic", "DetectionStrategy": "detection strategy",
    "Analytic": "analytic", "DataComponent": "data component", "Matrix": "matrix",
    # CAPEC
    "AttackPattern": "attack pattern", "Category": "category", "View": "view", "Weakness": "weakness",
    "ExecutionStep": "execution step", "Example": "example", "Skill": "skill", "Resource": "resource",
    "Prerequisite": "prerequisite", "Consequence": "consequence", "Indicator": "indicator",
    "ExternalReference": "external reference", "TaxonomyEntry": "taxonomy entry", "AlternateTerm": "alternate term",
}
PLURAL = {"software": "software", "analytic": "analytics", "category": "categories", "matrix": "matrices",
          "detection strategy": "detection strategies", "weakness": "weaknesses", "taxonomy entry": "taxonomy entries"}


def noun(label: str, n: int = 1) -> str:
    s = LABEL_NOUN.get(label, label)
    if n == 1:
        return s
    if s in PLURAL:
        return PLURAL[s]
    return s + "s"


def techs(label: str) -> str:
    """Plural noun, with the Technique/SubTechnique split made explicit."""
    if label == "Technique":
        return "techniques (parent techniques, not sub-techniques)"
    return noun(label, 2)


# --------------------------------------------------------------------------- #
# Stores (read-only)
# --------------------------------------------------------------------------- #


class Stores:
    """The measured stores, read-only: a Neo4j READ session and Gremlin traversals with no mutation step."""

    MUTATING = re.compile(r"\b(addV|addE|drop|property|mergeV|mergeE)\s*\(")

    def __init__(self) -> None:
        from gremlin_python.driver import client as gclient
        from gremlin_python.driver.serializer import GraphSONSerializersV3d0
        from neo4j import GraphDatabase

        from utils.config import load_env

        load_env()
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(os.environ.get("NEO4J_USER", "neo4j"),
                                                            os.environ.get("NEO4J_PASSWORD", "")),
                                           notifications_min_severity="OFF")
        self.client = gclient.Client(GREMLIN_URI, "g", message_serializer=GraphSONSerializersV3d0())

    def close(self) -> None:
        self.driver.close()
        self.client.close()

    def cypher(self, text: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        from neo4j import Query

        with self.driver.session(default_access_mode="READ") as s:
            return [r.data() for r in s.run(Query(text, timeout=TIMEOUT_S), params or {})]

    def gremlin(self, text: str, params: dict[str, Any] | None = None) -> list[Any]:
        if self.MUTATING.search(text):
            raise RuntimeError(f"refusing a mutating traversal: {text[:120]}")
        return self.client.submit(text, params or {},
                                  request_options={"evaluationTimeout": TIMEOUT_S * 1000}).all().result()


# --------------------------------------------------------------------------- #
# Cards and engines
# --------------------------------------------------------------------------- #

EDGE_PROPS = ("relationship_type", "stix_type", "phase_name", "log_source_names", "step")


def load_cards() -> dict[str, Any]:
    from utils.agent.catalog import load_all

    cats, _ = load_all(str(REPO / "data"), live=False)
    out = {}
    for ds in ("attack", "capec"):
        c = cats[ds]
        out[ds] = c.model if hasattr(c, "model") else c._model
    return out


def add_stored_edge_props(cards: dict[str, Any], stores: Stores) -> dict[str, dict[str, list[str]]]:
    """Give each card's relationships the edge properties the store holds (neither card declares any yet).

    Only the keys in ``EDGE_PROPS`` are added (``id`` and the long ``description`` are not
    filter parameters). The probe records which items need these (``needs_edge_props``).
    """
    from utils.agent.catalog import PropertyModel

    added: dict[str, dict[str, list[str]]] = {"attack": {}, "capec": {}}
    rows = stores.cypher("MATCH ()-[r]->() UNWIND keys(r) AS k "
                         "RETURN type(r) AS rel, k, collect(DISTINCT valueType(r[k])) AS types")
    for r in rows:
        rel, k, types = r["rel"], r["k"], r["types"]
        if rel in cards["attack"].relations and k in EDGE_PROPS and len(types) == 1:
            vtype = "list" if types[0].startswith("LIST") else "string" if types[0].startswith("STRING") else None
            if vtype:
                cards["attack"].relations[rel].properties[k] = PropertyModel(k, vtype, vtype)
                added["attack"].setdefault(rel, []).append(k)
    from utils.graph_loader.stores.gremlin import gremlin_edge_label

    for name, rel in cards["capec"].relations.items():
        keys = stores.gremlin(f"g.E().hasLabel('{gremlin_edge_label(name)}').properties().key().dedup()")
        for k in keys:
            if k not in EDGE_PROPS:
                continue
            sample = stores.gremlin(f"g.E().hasLabel('{gremlin_edge_label(name)}').has('{k}').limit(1).values('{k}')")
            vtype = "list" if sample and isinstance(sample[0], list) else "string"
            rel.properties[k] = PropertyModel(k, vtype, vtype)
            added["capec"].setdefault(name, []).append(k)
    return added


class Engine:
    """Compile, run and finish one operator tree on one dataset's runtime engine."""

    def __init__(self, ds: str, card: Any, stores: Stores) -> None:
        from utils.specialists.algebra.compiled import Backend

        self.ds, self.card, self.stores = ds, card, stores
        mk = Backend.cypher if ds == "attack" else Backend.gremlin
        self.backend = mk(card, row_cap=ROW_CAP)
        self.sampler = mk(card, row_cap=SAMPLE_CAP)
        self._cache: dict[str, Any] = {}

    def run(self, node: Any, sample: bool = False) -> Any:
        from utils.specialists.algebra import check
        from utils.specialists.algebra.compiled import finish
        from utils.specialists.cypher.compile import compile_cypher
        from utils.specialists.gremlin.compile import compile_gremlin

        check(node, self.card)
        be = self.sampler if sample else self.backend
        compiled = (compile_cypher if self.ds == "attack" else compile_gremlin)(node, be)
        raw = self.stores.cypher(compiled.text, compiled.params) if self.ds == "attack" else \
            self.stores.gremlin(compiled.text, compiled.params)
        return finish(raw, compiled)

    # --- sampling helpers (never gold) ---
    def ids(self, nodeset: Any) -> list[str]:
        from utils.specialists.algebra import Nodes

        key = "ids" + repr(nodeset)
        if key not in self._cache:
            r = self.run(Nodes(nodeset), sample=True)
            self._cache[key] = sorted(row["id"] for row in r.rows)
        return self._cache[key]

    def values(self, nodeset: Any, prop: str) -> list[Any]:
        from utils.specialists.algebra import Values

        key = f"vals{prop}" + repr(nodeset)
        if key not in self._cache:
            r = self.run(Values(nodeset, prop), sample=True)
            out: set[Any] = set()
            for row in r.rows:
                v = row["value"]
                for x in (v if isinstance(v, list) else [v]):
                    if isinstance(x, (str, int, float, bool)):
                        out.add(x)
            self._cache[key] = sorted(out, key=lambda x: (str(type(x)), x))
        return self._cache[key]


class Ids:
    """Stored id <-> public id and name, for one dataset, read once from the store."""

    def __init__(self, ds: str, stores: Stores) -> None:
        self.ds = ds
        self.public: dict[str, str] = {}
        self.name: dict[str, str] = {}
        self.label: dict[str, str] = {}
        if ds == "attack":
            rows = stores.cypher("MATCH (n) WHERE n.id IS NOT NULL RETURN n.id AS id, n.attack_id AS pub, n.name AS name, "
                                 "[l IN labels(n) WHERE NOT l IN ['AttackObject','STIXObject']] AS ls")
            for r in rows:
                self.public[r["id"]] = r["pub"] or r["id"]
                self.name[r["id"]] = r["name"] or ""
                self.label[r["id"]] = (r["ls"] or [""])[0]
        else:
            from utils.specialists.gremlin.normalizer import public_member_id

            rows = stores.gremlin("g.V().project('id','label','name').by(values('id'))"
                                  ".by(label).by(coalesce(values('name'), constant('')))")
            for r in rows:
                self.public[r["id"]] = public_member_id(r["id"])
                self.name[r["id"]] = r["name"] or ""
                self.label[r["id"]] = r["label"]
        self.stored: dict[str, str] = {}
        for s, p in self.public.items():
            self.stored.setdefault(p, s)

    def ref(self, stored: str) -> str:
        """``group G0016 (APT29)``: the label noun, the public id, and the name when it adds anything."""
        pub, nm = self.public.get(stored, stored), self.name.get(stored, "")
        lab = noun(self.label.get(stored, ""))
        return f"{lab} {pub} ({nm})" if nm and nm != pub else f"{lab} {pub}"

    def is_public(self, stored: str) -> bool:
        pub = self.public.get(stored, stored)
        return bool(pub) and ":" not in pub and "--" not in pub


# --------------------------------------------------------------------------- #
# Items
# --------------------------------------------------------------------------- #


@dataclasses.dataclass
class Cand:
    """One candidate before its gold is known."""

    operator: str  # O1..O8, O7b
    detail: str  # e.g. "O7c.union", "O1.size"
    node: Any  # the IR tree
    question: str
    description: str
    anchors: list[str]  # stored ids named in the question
    entities: list[str]  # labels and relationships the question touches
    negative: bool = False  # deliberately empty / false
    reduce: str | None = None  # "median": O2 over a groupby's values (not one tree in the IR)
    source: str = "generated"
    external_ref: str | None = None


def item_id(ds: str, cand: Cand) -> str:
    from utils.specialists.algebra import to_dict

    blob = json.dumps({"ds": ds, "ir": to_dict(cand.node), "reduce": cand.reduce}, sort_keys=True)
    h = hashlib.sha256(blob.encode()).hexdigest()[:10]
    prefix = "PX" if cand.source != "generated" else "PG"
    return f"{prefix}-{ds}-{cand.operator}-{h}"


def uses_edge_props(node: Any) -> bool:
    from utils.specialists.algebra import Hop

    found = False

    def walk(x: Any) -> None:
        nonlocal found
        if isinstance(x, Hop) and x.edge_conds:
            found = True
        if dataclasses.is_dataclass(x) and not isinstance(x, type):
            for f in dataclasses.fields(x):
                walk(getattr(x, f.name))
        elif isinstance(x, (tuple, list)):
            for y in x:
                walk(y)

    walk(node)
    return found


def compute_gold(eng: Engine, ids: Ids, cand: Cand) -> tuple[dict[str, Any] | None, str | None]:
    """The gold for a candidate, or ``(None, reason)`` when it must be dropped."""
    from utils.specialists.algebra.compiled import median

    try:
        r = eng.run(cand.node)
    except Exception as exc:  # noqa: BLE001 - a candidate that cannot run is dropped and counted
        msg = f"{type(exc).__name__}: {exc}"
        if "Timed" in msg or "timeout" in msg.lower() or "Timeout" in msg:
            return None, "timeout"
        if "InvalidOp" in msg or type(exc).__name__ == "InvalidOp":
            return None, "invalid"
        return None, "run_error"
    if r.info.get("anchor_not_found"):
        return None, "anchor_not_found"
    if not r.complete or r.partial:
        return None, "incomplete"
    gold: dict[str, Any] = {"result_kind": r.kind, "total": r.total, "complete": r.complete}
    pub = lambda s: ids.public.get(s, s)  # noqa: E731
    if cand.reduce:
        vals = [row["value"] for row in r.rows]
        if cand.reduce != "median":
            return None, "invalid"
        gold.update(kind="value", value=median(vals), ids=[], stored_ids=[],
                    reduce={"fn": "median", "over": "groupby values, zeros included", "n": len(vals)})
        if gold["value"] is None:
            return None, "empty"
        return gold, None
    if r.kind in ("nodes", "rank", "groupby"):
        rows = r.rows
        gold.update(kind="nodes", stored_ids=[x["id"] for x in rows], ids=[pub(x["id"]) for x in rows],
                    value=None)
        if r.kind in ("rank", "groupby"):
            gold["values"] = {pub(x["id"]): x["value"] for x in rows}
            if r.kind == "rank" and r.info.get("unranked") is not None:
                gold["unranked"] = r.info["unranked"]
        if not rows and not cand.negative:
            return None, "empty"
        if rows and cand.negative:
            return None, "negative_not_empty"
        if r.kind == "rank" and len(rows) > MAX_RANK_IDS:
            return None, "rank_tie_blowup"
        if len(rows) > MAX_GOLD_IDS:
            return None, "too_large_to_enumerate"
        if any(not ids.is_public(x["id"]) for x in rows):
            return None, "non_public_ids"
        return gold, None
    if r.kind in ("count", "aggregate"):
        gold.update(kind="value", value=r.value, ids=[], stored_ids=[])
        if r.value is None or (r.value == 0 and not cand.negative):
            return None, "empty"
        return gold, None
    if r.kind == "verify":
        gold.update(kind="value", value=bool(r.info.get("exists")), ids=[], stored_ids=[],
                    witness=[{"relation": w["relation"], "direction": w["direction"],
                              "properties": {k: v for k, v in w["properties"].items()
                                             if k in ("relationship_type", "id", "phase_name", "step")},
                              "has_description": bool(w["properties"].get("description"))} for w in r.rows])
        if gold["value"] == cand.negative:
            return None, "verify_polarity"
        return gold, None
    if r.kind == "shortest":
        if not r.rows:
            return None, "empty"
        nodes = sorted({pub(x) for row in r.rows for x in row["path"][0::2]})
        gold.update(kind="nodes", ids=nodes,
                    stored_ids=sorted({x for row in r.rows for x in row["path"][0::2]}),
                    value=len(r.rows[0]["rels"]),
                    paths=[[pub(x) if i % 2 == 0 else x for i, x in enumerate(row["path"])] for row in r.rows])
        if any(":" in x or "--" in x for x in nodes):
            return None, "non_public_ids"
        if len(nodes) > MAX_GOLD_IDS:
            return None, "too_large_to_enumerate"
        return gold, None
    return None, f"unsupported_kind_{r.kind}"


def finish_item(ds: str, ids: Ids, cand: Cand, gold: dict[str, Any]) -> dict[str, Any]:
    from utils.specialists.algebra import to_dict

    return {
        "id": item_id(ds, cand),
        "dataset": ds,
        "operator": cand.operator,
        "detail": cand.detail,
        "switch": SWITCH.get(cand.operator, "core"),
        "source": cand.source,
        "external_ref": cand.external_ref,
        "template_question": cand.question,
        "description": cand.description,
        "ir": to_dict(cand.node),
        "reduce": cand.reduce,
        "needs_edge_props": uses_edge_props(cand.node),
        "anchors": [{"public": ids.public.get(a, a), "stored": a, "label": ids.label.get(a, ""),
                     "name": ids.name.get(a, "")} for a in cand.anchors],
        "entities": cand.entities,
        "negative": cand.negative,
        "gold": gold,
    }


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #

Template = Callable[[random.Random], "Cand | None"]


def pick(rng: random.Random, seq: list[Any]) -> Any:
    return seq[rng.randrange(len(seq))] if seq else None


REL_PHRASE = {
    ("USES", "out"): "use", ("MITIGATES", "out"): "mitigate", ("DETECTS", "out"): "detect",
    ("HAS_SUBTECHNIQUE", "out"): "have as a sub-technique", ("HAS_TECHNIQUE", "out"): "include",
    ("ATTRIBUTED_TO", "out"): "get attributed to", ("HAS_ANALYTIC", "out"): "include the analytic",
    ("MONITORS", "out"): "monitor",
    ("ChildOf", "out"): "have as a parent (is it a child of)", ("CanPrecede", "out"): "precede (can it precede)",
    ("EXPLOITS_WEAKNESS", "out"): "exploit", ("MEMBER_OF", "out"): "belong to (is it a member of)",
    ("IN_VIEW", "out"): "appear in", ("PeerOf", "out"): "have as a peer", ("CanFollow", "out"): "follow (can it follow)",
    ("CanAlsoBe", "out"): "also count as (can it also be)",
}


def attack_templates(eng: Engine, ids: Ids) -> dict[str, list[Template]]:
    from utils.specialists.algebra import (Aggregate, Anchors, Cond, Count, GroupBy, Having, Hop, Nodes, Rank, Reach,
                                           Scan, Shortest, TypeScan, Union_, Verify, Walk, Where)

    R = ids.ref
    USES_T = Hop("USES", "out", "Technique")
    USES_S = Hop("USES", "out", "Software")
    MIT_T = Hop("MITIGATES", "out", "Technique")
    TAC_T = Hop("HAS_TECHNIQUE", "out", "Technique")
    DET_T = Hop("DETECTS", "out", "Technique")
    linked = lambda lab, hop: eng.ids(Having(Scan(lab), hop, True))  # noqa: E731

    def walk_from(lab: str, hop: Hop, rng: random.Random) -> tuple[str, Any] | None:
        a = pick(rng, linked(lab, hop))
        return (a, Walk(Anchors((a,), lab), (hop,))) if a else None

    # ---------------- O1 filter ----------------
    def o1_platform(rng, lab="Group", hop=USES_T, op="contains"):
        w = walk_from(lab, hop, rng)
        if not w:
            return None
        a, walk = w
        v = pick(rng, eng.values(walk, "x_mitre_platforms"))
        if v is None:
            return None
        neg = " do not" if op == "not_contains" else ""
        verb = {"USES": "used by", "MITIGATES": "mitigated by"}.get(hop.relation, "linked to")
        return Cand("O1", f"O1.{op}", Nodes(Where(walk, (Cond("x_mitre_platforms", op, v),))),
                    f"Which {techs(hop.target)} {verb} {R(a)}{neg} list {v} among their platforms?",
                    f"{noun(hop.target, 2)} reached from {ids.public[a]} by {hop.relation}, filtered on platform "
                    f"{'excluding' if neg else 'including'} {v}", [a], [lab, hop.relation, hop.target])

    def o1_size(rng):
        w = walk_from("Mitigation", MIT_T, rng)
        if not w:
            return None
        a, walk = w
        n = rng.choice([2, 3, 4])
        return Cand("O1", "O1.size", Nodes(Where(walk, (Cond("x_mitre_platforms", "size", n, ">="),))),
                    f"Which {techs('Technique')} mitigated by {R(a)} list at least {n} platforms?",
                    f"techniques mitigated by {ids.public[a]} with {n}+ platforms", [a],
                    ["Mitigation", "MITIGATES", "Technique"])

    def o1_two(rng):
        w = walk_from("Tactic", TAC_T, rng)
        if not w:
            return None
        a, walk = w
        vals = eng.values(walk, "x_mitre_platforms")
        if len(vals) < 2:
            return None
        v1, v2 = sorted(rng.sample(vals, 2))
        return Cand("O1", "O1.and", Nodes(Where(walk, (Cond("x_mitre_platforms", "contains", v1),
                                                       Cond("x_mitre_platforms", "contains", v2)))),
                    f"Which {techs('Technique')} in {R(a)} list both {v1} and {v2} as platforms?",
                    f"techniques of tactic {ids.public[a]} on both {v1} and {v2}", [a],
                    ["Tactic", "HAS_TECHNIQUE", "Technique"])

    def o1_present(rng):
        w = walk_from("Group", USES_S, rng)
        if not w:
            return None
        a, walk = w
        return Cand("O1", "O1.present", Nodes(Where(walk, (Cond("x_mitre_aliases", "present"),))),
                    f"Which software used by {R(a)} has any recorded aliases?",
                    f"software used by {ids.public[a]} that has aliases", [a], ["Group", "USES", "Software"])

    def o1_text(rng):
        w = walk_from(rng.choice(["Group", "Software"]), USES_T, rng)
        if not w:
            return None
        a, walk = w
        names = [ids.name[x] for x in eng.ids(walk) if ids.name.get(x)]
        words = sorted({wd for n in names for wd in re.findall(r"[A-Z][a-z]{3,}", n)})
        wd = pick(rng, words)
        if not wd:
            return None
        return Cand("O1", "O1.contains_text", Nodes(Where(walk, (Cond("name", "contains_text", wd),))),
                    f"Which {techs('Technique')} used by {R(a)} have '{wd}' in their name?",
                    f"techniques used by {ids.public[a]} whose name contains '{wd}'", [a],
                    [ids.label[a], "USES", "Technique"])

    def o1_analytic(rng):
        hop = Hop("HAS_ANALYTIC", "out", "Analytic")
        w = walk_from("DetectionStrategy", hop, rng)
        if not w:
            return None
        a, walk = w
        v = pick(rng, eng.values(walk, "x_mitre_platforms"))
        if v is None:
            return None
        return Cand("O1", "O1.contains", Nodes(Where(walk, (Cond("x_mitre_platforms", "contains", v),))),
                    f"Which analytics of {R(a)} apply to the {v} platform?",
                    f"analytics of detection strategy {ids.public[a]} on {v}", [a],
                    ["DetectionStrategy", "HAS_ANALYTIC", "Analytic"])

    def o1_notc(rng):
        return o1_platform(rng, "Software", USES_T, "not_contains")

    def o1_sub(rng):
        hop = Hop("HAS_SUBTECHNIQUE", "out", "SubTechnique")
        w = walk_from("Technique", hop, rng)
        if not w:
            return None
        a, walk = w
        n = rng.choice([1, 2, 3])
        return Cand("O1", "O1.size", Nodes(Where(walk, (Cond("x_mitre_platforms", "size", n, ">"),))),
                    f"Which sub-techniques of {R(a)} list more than {n} platform{'s' if n > 1 else ''}?",
                    f"sub-techniques of {ids.public[a]} with more than {n} platforms", [a],
                    ["Technique", "HAS_SUBTECHNIQUE", "SubTechnique"])

    # ---------------- O2 aggregate ----------------
    def o2_count_label(rng):
        lab = rng.choice(["Group", "Software", "Campaign", "Mitigation", "Technique", "SubTechnique", "Tactic",
                          "DetectionStrategy", "Analytic", "DataComponent"])
        return Cand("O2", "O2.count", Aggregate(Scan(lab), "count"),
                    f"How many {noun(lab, 2)} does the ATT&CK catalogue contain in total?",
                    f"catalogue-wide count of {noun(lab, 2)}", [], [lab])

    def o2_count_filtered(rng):
        lab = rng.choice(["Technique", "Software", "SubTechnique"])
        v = pick(rng, eng.values(Scan(lab), "x_mitre_platforms"))
        if v is None:
            return None
        return Cand("O2", "O2.count", Aggregate(Where(Scan(lab), (Cond("x_mitre_platforms", "contains", v),)), "count"),
                    f"How many {techs(lab)} in ATT&CK list {v} as a platform?",
                    f"count of {noun(lab, 2)} on platform {v}", [], [lab])

    def o2_count_values(rng):
        lab, prop, what = rng.choice([("Technique", "x_mitre_version", "version numbers"),
                                      ("Software", "x_mitre_version", "version numbers"),
                                      ("Group", "x_mitre_version", "version numbers")])
        return Cand("O2", "O2.count_values", Aggregate(Scan(lab), "count_values", prop),
                    f"How many distinct {what} ({prop}) appear across all ATT&CK {noun(lab, 2)}?",
                    f"distinct values of {prop} over {noun(lab, 2)}", [], [lab])

    def o2_minmax(rng):
        lab, prop = rng.choice([("Campaign", "first_seen"), ("Campaign", "last_seen"), ("Group", "created"),
                                ("Software", "created"), ("Mitigation", "modified"), ("Technique", "created")])
        fn = rng.choice(["min", "max"])
        word = "earliest" if fn == "min" else "latest"
        return Cand("O2", f"O2.{fn}", Aggregate(Scan(lab), fn, prop),
                    f"What is the {word} {prop.replace('_', ' ')} date of any ATT&CK {noun(lab)}?",
                    f"{fn} of {prop} over all {noun(lab, 2)}", [], [lab])

    def o2_minmax_walk(rng):
        w = walk_from("Group", USES_T, rng)
        if not w:
            return None
        a, walk = w
        fn = rng.choice(["min", "max"])
        word = "earliest" if fn == "min" else "most recent"
        return Cand("O2", f"O2.{fn}", Aggregate(walk, fn, "modified"),
                    f"Among the {techs('Technique')} used by {R(a)}, what is the {word} last-modified date?",
                    f"{fn} of modified over techniques used by {ids.public[a]}", [a], ["Group", "USES", "Technique"])

    def o2_walk_scan(rng):
        lab, hop, q = rng.choice([
            ("Campaign", Hop("ATTRIBUTED_TO", "out", "Group"), "How many distinct groups have at least one campaign "
                                                               "attributed to them?"),
            ("Mitigation", MIT_T, "How many distinct techniques (not sub-techniques) are mitigated by at least one "
                                  "mitigation?"),
            ("DetectionStrategy", DET_T, "How many distinct techniques (not sub-techniques) are detected by at least "
                                         "one detection strategy?"),
            ("Campaign", USES_S, "How many distinct software entries are used by at least one campaign?")])
        return Cand("O2", "O2.count", Aggregate(Walk(Scan(lab), (hop,)), "count"), q,
                    f"count of {hop.target} reached by {hop.relation} from any {lab}", [], [lab, hop.relation, hop.target])

    def o2_median(rng):
        lab, hop, q = rng.choice([
            ("Tactic", TAC_T, "What is the median number of techniques (not sub-techniques) per tactic?"),
            ("Technique", Hop("MITIGATES", "in", "Mitigation"), "What is the median number of mitigations per "
                                                                "technique (not sub-technique)?"),
            ("Group", USES_T, "What is the median number of techniques (not sub-techniques) used per group?"),
            ("Software", USES_T, "What is the median number of techniques (not sub-techniques) used per software?")])
        return Cand("O2", "O2.median", GroupBy(Scan(lab), (hop,), "count"), q,
                    f"median over {noun(lab, 2)} of the count of {hop.target} by {hop.relation} (zeros included)",
                    [], [lab, hop.relation, hop.target], reduce="median")

    # ---------------- O3 rank ----------------
    T_ = "techniques (not sub-techniques)"
    RANKS = [  # (label, hop, verb singular, verb plural, object)
        ("Group", USES_T, "uses", "use", T_),
        ("Software", USES_T, "uses", "use", T_),
        ("Technique", Hop("MITIGATES", "in", "Mitigation"), "has", "have", "mitigations"),
        ("Mitigation", MIT_T, "mitigates", "mitigate", T_),
        ("Tactic", TAC_T, "includes", "include", T_),
        ("DetectionStrategy", Hop("HAS_ANALYTIC", "out", "Analytic"), "has", "have", "analytics"),
        ("DataComponent", Hop("MONITORS", "in", "Analytic"), "is monitored by", "are monitored by", "analytics"),
        ("Campaign", USES_T, "uses", "use", T_),
        ("Technique", Hop("HAS_SUBTECHNIQUE", "out", "SubTechnique"), "has", "have", "sub-techniques"),
        ("Technique", Hop("USES", "in", "Group"), "is used by", "are used by", "groups"),
    ]

    def rank_q(lab: str, k: int, sing: str, plur: str, obj: str, scope: str = "") -> str:
        who = f"{noun(lab)}{' (not sub-technique)' if lab == 'Technique' else ''}"
        if k == 1:
            return f"Which {who}{scope} {sing} the most {obj}? (If several tie, name them all.)"
        return f"Which {k} {techs(lab) if lab == 'Technique' else noun(lab, 2)}{scope} {plur} the most {obj}? " \
               f"(Include any that tie with the {k}{'rd' if k == 3 else 'th'}.)"

    def o3_walk(rng):
        lab, hop, sing, plur, obj = pick(rng, RANKS)
        k = rng.choice([1, 1, 3, 5])
        return Cand("O3", "O3.by_walk", Rank(Scan(lab), "desc", k, by_walk=(hop,)), rank_q(lab, k, sing, plur, obj),
                    f"top {k} {noun(lab, 2)} by count of {hop.relation} {hop.direction} {hop.target}, ties kept",
                    [], [lab, hop.relation, hop.target])

    def o3_prop(rng):
        lab, prop, order, q = rng.choice([
            ("Campaign", "first_seen", "asc", "Which campaign was first seen earliest? (If several tie, name them all.)"),
            ("Campaign", "last_seen", "desc", "Which campaign was last seen most recently?"),
            ("Group", "created", "asc", "Which group was added to ATT&CK earliest (by created date)?"),
            ("Mitigation", "modified", "desc", "Which mitigation was modified most recently?"),
            ("Tactic", "created", "desc", "Which tactic was created most recently?")])
        return Cand("O3", "O3.by_prop", Rank(Scan(lab), order, 1, prop=prop), q,
                    f"{noun(lab)} with the {'smallest' if order == 'asc' else 'largest'} {prop}", [], [lab])

    def o3_sub(rng):
        w = walk_from("Group", USES_S, rng)
        if not w:
            return None
        a, walk = w
        return Cand("O3", "O3.by_walk", Rank(walk, "desc", 1, by_walk=(USES_T,)),
                    f"Of the software used by {R(a)}, which uses the most techniques (not sub-techniques)? "
                    f"(If several tie, name them all.)",
                    f"software of {ids.public[a]} ranked by techniques used, top 1 with ties", [a],
                    ["Group", "USES", "Software", "Technique"])

    # ---------------- O4 verify ----------------
    VPAIRS = [("Group", "USES", "Technique"), ("Group", "USES", "Software"), ("Software", "USES", "Technique"),
              ("Campaign", "USES", "Technique"), ("Campaign", "ATTRIBUTED_TO", "Group"),
              ("Mitigation", "MITIGATES", "Technique"), ("Mitigation", "MITIGATES", "SubTechnique"),
              ("DetectionStrategy", "DETECTS", "Technique"), ("Technique", "HAS_SUBTECHNIQUE", "SubTechnique"),
              ("Tactic", "HAS_TECHNIQUE", "Technique"), ("Group", "USES", "SubTechnique"),
              ("Software", "USES", "SubTechnique"), ("Analytic", "MONITORS", "DataComponent")]
    vcount = [0]

    def o4(rng):
        i = vcount[0]
        vcount[0] += 1
        sl, rel, tl = VPAIRS[i % len(VPAIRS)]
        hop = Hop(rel, "out", tl)
        negative = i % 6 == 5
        with_rel = i % 2 == 0
        src = pick(rng, linked(sl, hop))
        if not src:
            return None
        nb = set(eng.ids(Walk(Anchors((src,), sl), (hop,))))
        pool = sorted(set(eng.ids(Scan(tl))) - nb) if negative else sorted(nb)
        tgt = pick(rng, pool)
        if not tgt:
            return None
        node = Verify(Anchors((src,), sl), Anchors((tgt,), tl), rel if with_rel else None, "out" if with_rel else None)
        if with_rel:
            q = f"Does {R(src)} {REL_PHRASE[(rel, 'out')]} {R(tgt)}?"
        else:
            q = f"Is {R(src)} directly linked to {R(tgt)} in ATT&CK, and if so by what relationship?"
        return Cand("O4", "O4.verify" + ("" if with_rel else ".any"), node, q,
                    f"is there a {rel if with_rel else 'direct'} link from {ids.public[src]} to {ids.public[tgt]}",
                    [src, tgt], [sl, rel, tl], negative=negative)

    # ---------------- O5 typescan ----------------
    def o5_platform(rng, count=False):
        lab = rng.choice(["Technique", "SubTechnique", "Software"])
        v = pick(rng, eng.values(Scan(lab), "x_mitre_platforms"))
        if v is None:
            return None
        ts = TypeScan(lab, (Cond("x_mitre_platforms", "contains", v),))
        if count:
            return Cand("O5", "O5.count", Count(ts), f"How many ATT&CK {techs(lab)} list {v} as a platform?",
                        f"count of {noun(lab, 2)} on {v}", [], [lab])
        return Cand("O5", "O5.typescan", Nodes(ts), f"Which ATT&CK {techs(lab)} list {v} as a platform?",
                    f"every {noun(lab)} on {v}", [], [lab])

    def o5_aliases(rng):
        n = rng.choice([4, 5, 6, 8])
        return Cand("O5", "O5.typescan", Nodes(TypeScan("Group", (Cond("aliases", "size", n, ">="),))),
                    f"Which groups have at least {n} recorded aliases?", f"groups with {n}+ aliases", [], ["Group"])

    def o5_name(rng):
        lab = rng.choice(["Mitigation", "DataComponent", "DetectionStrategy"])
        words = sorted({w for x in eng.ids(Scan(lab)) for w in re.findall(r"[A-Z][a-z]{4,}", ids.name.get(x, ""))})
        wd = pick(rng, words)
        if not wd:
            return None
        return Cand("O5", "O5.typescan", Nodes(TypeScan(lab, (Cond("name", "contains_text", wd),))),
                    f"Which ATT&CK {noun(lab, 2)} have '{wd}' in their name?",
                    f"{noun(lab, 2)} whose name contains '{wd}'", [], [lab])

    def o5_family(rng):
        v = pick(rng, eng.values(Scan("Software"), "x_mitre_platforms"))
        if v is None:
            return None
        return Cand("O5", "O5.typescan", Nodes(TypeScan("Software", (Cond("is_family", "=", True),
                                                                      Cond("x_mitre_platforms", "contains", v)))),
                    f"Which software entries are malware families and list {v} as a platform?",
                    f"software with is_family true on {v}", [], ["Software"])

    def o5_remote(rng):
        return Cand("O5", "O5.typescan", Nodes(TypeScan("Technique", (Cond("x_mitre_remote_support", "=", True),))),
                    "Which techniques (not sub-techniques) support remote execution (x_mitre_remote_support is true)?",
                    "techniques with remote support", [], ["Technique"])

    # ---------------- O6 groupby ----------------
    def o6_zero(rng):
        lab, hop, q = rng.choice([
            ("Group", USES_S, "Which groups use no software at all?"),
            ("Campaign", USES_S, "Which campaigns use no software at all?"),
            ("Technique", Hop("MITIGATES", "in", "Mitigation"), "Which techniques (not sub-techniques) have no mitigation?"),
            ("Mitigation", Hop("MITIGATES", "out", "SubTechnique"), "Which mitigations mitigate no sub-technique?")])
        return Cand("O6", "O6.having_zero", GroupBy(Scan(lab), (hop,), "count", having=("=", 0)), q,
                    f"{noun(lab, 2)} whose count of {hop.relation} {hop.target} is 0 (empty groups kept)", [],
                    [lab, hop.relation, hop.target])

    def o6_having(rng):
        lab, hop, what = rng.choice([("Mitigation", MIT_T, "mitigate"), ("Campaign", USES_S, "use"),
                                     ("Group", USES_S, "use"), ("Software", USES_T, "use"),
                                     ("Tactic", TAC_T, "include")])
        n = rng.choice([10, 15, 20, 25, 30, 40]) if hop.target == "Technique" else rng.choice([5, 8, 10, 15])
        return Cand("O6", "O6.having", GroupBy(Scan(lab), (hop,), "count", having=(">=", n)),
                    f"Which {noun(lab, 2)} {what} at least {n} {techs(hop.target)}?",
                    f"{noun(lab, 2)} with count({hop.relation} {hop.target}) >= {n}", [], [lab, hop.relation, hop.target])

    def o6_end(rng):
        v = pick(rng, eng.values(Scan("Technique"), "x_mitre_platforms"))
        if v is None:
            return None
        k = rng.choice([1, 3])
        return Cand("O6", "O6.end_conds", GroupBy(Scan("Tactic"), (TAC_T,), "count",
                                                  end_conds=(Cond("x_mitre_platforms", "contains", v),),
                                                  order="desc", k=k),
                    f"Which {'tactic includes' if k == 1 else f'{k} tactics include'} the most techniques (not "
                    f"sub-techniques) that list {v} as a platform{'' if k == 1 else ' (ties included)'}?",
                    f"tactics ranked by count of their {v} techniques, top {k}", [], ["Tactic", "HAS_TECHNIQUE", "Technique"])

    def o6_sub(rng):
        w = walk_from("Tactic", TAC_T, rng)
        if not w:
            return None
        a, walk = w
        n = rng.choice([3, 4, 5, 6])
        return Cand("O6", "O6.having", GroupBy(walk, (Hop("HAS_SUBTECHNIQUE", "out", "SubTechnique"),), "count",
                                               having=(">=", n)),
                    f"Which techniques in {R(a)} have at least {n} sub-techniques?",
                    f"techniques of {ids.public[a]} with {n}+ sub-techniques", [a],
                    ["Tactic", "HAS_TECHNIQUE", "Technique", "HAS_SUBTECHNIQUE", "SubTechnique"])

    def o6_walk(rng):
        w = walk_from("Group", USES_S, rng)
        if not w:
            return None
        a, walk = w
        n = rng.choice([5, 10, 15, 20])
        return Cand("O6", "O6.having", GroupBy(walk, (USES_T,), "count", having=(">", n)),
                    f"Of the software used by {R(a)}, which use more than {n} techniques (not sub-techniques)?",
                    f"software of {ids.public[a]} with > {n} techniques", [a], ["Group", "USES", "Software", "Technique"])

    def o6_max(rng):
        return Cand("O6", "O6.max", GroupBy(Scan("Tactic"), (TAC_T,), "max", "created", order="desc", k=1),
                    "Which tactic includes the most recently created technique (not sub-technique)?",
                    "tactic whose techniques have the latest max(created)", [], ["Tactic", "HAS_TECHNIQUE", "Technique"])

    # ---------------- O7 union / absence / edge filters (core) ----------------
    def o7_union_md(rng):
        m = pick(rng, linked("Mitigation", MIT_T))
        d = pick(rng, linked("DetectionStrategy", DET_T))
        if not (m and d):
            return None
        return Cand("O7", "O7c.union", Nodes(Union_((Walk(Anchors((m,), "Mitigation"), (MIT_T,)),
                                                     Walk(Anchors((d,), "DetectionStrategy"), (DET_T,))))),
                    f"Which techniques (not sub-techniques) are either mitigated by {R(m)} or detected by {R(d)}?",
                    f"union of techniques mitigated by {ids.public[m]} and detected by {ids.public[d]}", [m, d],
                    ["Mitigation", "MITIGATES", "DetectionStrategy", "DETECTS", "Technique"])

    def o7_union_gc(rng):
        g = pick(rng, linked("Group", USES_S))
        c = pick(rng, linked("Campaign", USES_S))
        if not (g and c):
            return None
        return Cand("O7", "O7c.union", Nodes(Union_((Walk(Anchors((g,), "Group"), (USES_S,)),
                                                     Walk(Anchors((c,), "Campaign"), (USES_S,))))),
                    f"Which software is used either by {R(g)} or by {R(c)}?",
                    f"union of software used by {ids.public[g]} and by {ids.public[c]}", [g, c],
                    ["Group", "Campaign", "USES", "Software"])

    def o7_union_gs(rng):
        g = pick(rng, linked("Group", USES_T))
        s = pick(rng, linked("Software", USES_T))
        if not (g and s):
            return None
        return Cand("O7", "O7c.union", Nodes(Union_((Walk(Anchors((g,), "Group"), (USES_T,)),
                                                     Walk(Anchors((s,), "Software"), (USES_T,))))),
                    f"Which techniques (not sub-techniques) are used either by {R(g)} or by {R(s)}?",
                    f"union of techniques used by {ids.public[g]} and by {ids.public[s]}", [g, s],
                    ["Group", "Software", "USES", "Technique"])

    def o7_absence_tac(rng):
        w = walk_from("Tactic", TAC_T, rng)
        if not w:
            return None
        a, walk = w
        hop, what = rng.choice([(Hop("MITIGATES", "in", "Mitigation"), "no mitigation"),
                                (Hop("DETECTS", "in", "DetectionStrategy"), "no detection strategy"),
                                (Hop("USES", "in", "Group"), "no group using them")])
        return Cand("O7", "O7d.absence", Nodes(Having(walk, hop, False)),
                    f"Which techniques (not sub-techniques) in {R(a)} have {what}?",
                    f"techniques of {ids.public[a]} lacking any {hop.relation} {hop.direction} {hop.target}", [a],
                    ["Tactic", "HAS_TECHNIQUE", "Technique", hop.relation, hop.target])

    def o7_absence_scan(rng):
        lab, hop, q = rng.choice([
            ("Campaign", Hop("ATTRIBUTED_TO", "out", "Group"), "Which campaigns are not attributed to any group?"),
            ("Software", Hop("USES", "in", "Group"), "Which software is used by no group?"),
            ("Technique", Hop("DETECTS", "in", "DetectionStrategy"),
             "Which techniques (not sub-techniques) are detected by no detection strategy?")])
        return Cand("O7", "O7d.absence", Nodes(Having(Scan(lab), hop, False)), q,
                    f"{noun(lab, 2)} with no {hop.relation} {hop.direction} {hop.target}", [], [lab, hop.relation, hop.target])

    def o7_missing(rng):
        w = walk_from("Group", USES_S, rng)
        if not w:
            return None
        a, walk = w
        return Cand("O7", "O7d.missing", Nodes(Where(walk, (Cond("x_mitre_aliases", "missing"),))),
                    f"Which software used by {R(a)} has no recorded aliases?",
                    f"software of {ids.public[a]} lacking x_mitre_aliases", [a], ["Group", "USES", "Software"])

    def o7_edge_an(rng):
        hop0 = Hop("MONITORS", "out", "DataComponent")
        a = pick(rng, linked("Analytic", hop0))
        if not a:
            return None
        rows = eng.stores.cypher("MATCH (n {id:$id})-[r:MONITORS]->() UNWIND r.log_source_names AS v "
                                 "RETURN DISTINCT v ORDER BY v", {"id": a})
        v = pick(rng, [r["v"] for r in rows])
        if not v:
            return None
        hop = Hop("MONITORS", "out", "DataComponent", (Cond("log_source_names", "contains", v),))
        return Cand("O7", "O7a.edgefilter", Nodes(Walk(Anchors((a,), "Analytic"), (hop,))),
                    f"Which data components does {R(a)} monitor through the {v} log source?",
                    f"data components monitored by {ids.public[a]} on edges whose log_source_names contain {v}",
                    [a], ["Analytic", "MONITORS", "DataComponent"])

    def o7_edge_scan(rng):
        rows = eng.stores.cypher("MATCH ()-[r:MONITORS]->() UNWIND r.log_source_names AS v "
                                 "RETURN v, count(*) AS c ORDER BY v")
        v = pick(rng, [r["v"] for r in rows if 2 <= r["c"] <= 120])
        if not v:
            return None
        hop = Hop("MONITORS", "out", "DataComponent", (Cond("log_source_names", "contains", v),))
        return Cand("O7", "O7a.edgefilter", Nodes(Having(Scan("Analytic"), hop, True)),
                    f"Which analytics monitor any data component through the {v} log source?",
                    f"analytics with a MONITORS edge whose log_source_names contain {v}", [],
                    ["Analytic", "MONITORS", "DataComponent"])

    def o7_edge_phase(rng):
        w = walk_from("Group", USES_T, rng)
        if not w:
            return None
        a, walk = w
        phase = pick(rng, [r["v"] for r in eng.stores.cypher(
            "MATCH ()-[r:HAS_TECHNIQUE]->() RETURN DISTINCT r.phase_name AS v ORDER BY v")])
        hop = Hop("HAS_TECHNIQUE", "in", "Tactic", (Cond("phase_name", "=", phase),))
        return Cand("O7", "O7a.edgefilter", Nodes(Having(walk, hop, True)),
                    f"Which techniques (not sub-techniques) used by {R(a)} are listed under the kill-chain phase "
                    f"'{phase}'?",
                    f"techniques of {ids.public[a]} with a HAS_TECHNIQUE edge whose phase_name is {phase}", [a],
                    ["Group", "USES", "Technique", "HAS_TECHNIQUE", "Tactic"])

    # ---------------- O7b time (extended) ----------------
    def dates(nodeset, prop):
        return sorted({str(v)[:10] for v in eng.values(nodeset, prop) if re.match(r"^\d{4}-\d{2}-\d{2}", str(v))})

    def o7b_scan(rng):
        lab, prop = rng.choice([("Campaign", "first_seen"), ("Campaign", "last_seen"), ("Group", "created"),
                                ("Software", "created"), ("Mitigation", "modified"), ("Technique", "created"),
                                ("Group", "modified"), ("Tactic", "modified")])
        ds_ = dates(Scan(lab), prop)
        if len(ds_) < 2:
            return None
        op = rng.choice(["before", "after", "between", "year"])
        pw = prop.replace("_", " ")
        if op == "between":
            a, b = sorted(rng.sample(ds_, 2))
            c, txt = Cond(prop, "between", (a, b)), f"between {a} and {b} (inclusive)"
        elif op == "year":
            y = int(pick(rng, ds_)[:4])
            c, txt = Cond(prop, "year", y, "="), f"in {y}"
        else:
            d = pick(rng, ds_)
            c, txt = Cond(prop, op, d), f"{op} {d}"
        count = rng.random() < 0.3
        ts = TypeScan(lab, (c,))
        if count:
            return Cand("O7b", f"O7b.{op}", Count(ts), f"How many {techs(lab)} have a {pw} date {txt}?",
                        f"count of {noun(lab, 2)} with {prop} {op} {c.value}", [], [lab])
        return Cand("O7b", f"O7b.{op}", Nodes(ts), f"Which {techs(lab)} have a {pw} date {txt}?",
                    f"{noun(lab, 2)} with {prop} {op} {c.value}", [], [lab])

    def o7b_walk(rng):
        lab, hop = rng.choice([("Group", USES_S), ("Tactic", TAC_T), ("Group", USES_T), ("Mitigation", MIT_T)])
        w = walk_from(lab, hop, rng)
        if not w:
            return None
        a, walk = w
        prop = rng.choice(["created", "modified"])
        ds_ = dates(walk, prop)
        if len(ds_) < 2:
            return None
        op = rng.choice(["before", "after", "year"])
        if op == "year":
            y = int(pick(rng, ds_)[:4])
            c, txt = Cond(prop, "year", y, "="), f"in {y}"
        else:
            d = pick(rng, ds_[1:] if op == "before" else ds_[:-1])
            c, txt = Cond(prop, op, d), f"{op} {d}"
        return Cand("O7b", f"O7b.{op}", Nodes(Where(walk, (c,))),
                    f"Which {techs(hop.target)} linked to {R(a)} by {hop.relation.lower().replace('_', ' ')} were "
                    f"{prop} {txt}?",
                    f"{noun(hop.target, 2)} of {ids.public[a]} with {prop} {op} {c.value}", [a],
                    [lab, hop.relation, hop.target])

    # ---------------- O8 paths (extended) ----------------
    def o8_shortest(rng):
        kind = rng.choice(["tt", "gg", "ts"])
        if kind == "gg":
            pool, la, lb = eng.ids(Scan("Group")), "Group", "Group"
            a, b = sorted(rng.sample(pool, 2))
        elif kind == "ts":
            a = pick(rng, eng.ids(Scan("Technique")))
            b = pick(rng, eng.ids(Scan("SubTechnique")))
            la, lb = "Technique", "SubTechnique"
        else:
            pool, la, lb = eng.ids(Scan("Technique")), "Technique", "Technique"
            a, b = sorted(rng.sample(pool, 2))
        return Cand("O8", "O8.shortest", Shortest(Anchors((a,), la), Anchors((b,), lb), (), 3),
                    f"What is the shortest chain of relationships (any relationship, either direction) that connects "
                    f"{R(a)} and {R(b)}?",
                    f"all shortest paths between {ids.public[a]} and {ids.public[b]}, depth cap 3", [a, b], [la, lb])

    def o8_reach(rng):
        lab, rels, q, d = rng.choice([
            ("SubTechnique", (("HAS_SUBTECHNIQUE", "in"), ("HAS_TECHNIQUE", "in")),
             "Which techniques and tactics can be reached upward from {a} through parent-technique and tactic links?", 2),
            ("Analytic", (("HAS_ANALYTIC", "in"), ("DETECTS", "out")),
             "Which detection strategies, and the techniques they detect, can be reached from {a}?", 2),
            ("Campaign", (("ATTRIBUTED_TO", "out"),),
             "Which groups can be reached from {a} by following attribution links?", 6),
            ("Mitigation", (("MITIGATES", "out"), ("HAS_SUBTECHNIQUE", "out")),
             "Which techniques and sub-techniques can be reached from {a} by following mitigates and sub-technique "
             "links (any number of steps up to 3)?", 3),
        ])
        a = pick(rng, eng.ids(Scan(lab)))
        if not a:
            return None
        return Cand("O8", "O8.reach", Nodes(Reach(Anchors((a,), lab), rels, d)), q.format(a=R(a)),
                    f"nodes reachable from {ids.public[a]} via {rels} within {d} steps", [a],
                    [lab] + [r for r, _ in rels])

    return {
        "O1": [o1_platform, o1_size, o1_two, o1_present, o1_text, o1_analytic, o1_notc, o1_sub],
        "O2": [o2_count_label, o2_count_filtered, o2_count_values, o2_minmax, o2_minmax_walk, o2_walk_scan, o2_median],
        "O3": [o3_walk, o3_walk, o3_prop, o3_sub],
        "O4": [o4],
        "O5": [lambda r: o5_platform(r), lambda r: o5_platform(r, True), o5_aliases, o5_name, o5_family, o5_remote],
        "O6": [o6_zero, o6_having, o6_end, o6_sub, o6_walk, o6_max],
        "O7": [o7_union_md, o7_absence_tac, o7_edge_an, o7_union_gc, o7_absence_scan, o7_edge_scan, o7_union_gs,
               o7_missing, o7_edge_phase],
        "O7b": [o7b_scan, o7b_walk],
        "O8": [o8_shortest, o8_reach],
    }


def capec_templates(eng: Engine, ids: Ids) -> dict[str, list[Template]]:
    from utils.specialists.algebra import (Aggregate, Anchors, Cond, Count, GroupBy, Having, Hop, Nodes, Rank, Reach,
                                           Scan, Shortest, TypeScan, Union_, Verify, Walk, Where)

    R = ids.ref
    MEM_IN = Hop("MEMBER_OF", "in", "AttackPattern")
    VIEW_IN = Hop("IN_VIEW", "in", "AttackPattern")
    CHILD_IN = Hop("ChildOf", "in", "AttackPattern")
    linked = lambda lab, hop: eng.ids(Having(Scan(lab), hop, True))  # noqa: E731
    AP_PROPS = {"Typical_Severity": "typical severity", "Likelihood_Of_Attack": "likelihood of attack",
                "Abstraction": "abstraction level", "Status": "status"}

    def ap_set(rng) -> tuple[str, Any, str] | None:
        """A named set of attack patterns: a category's members, a view's members, or a pattern's children."""
        lab, hop, phrase = rng.choice([("Category", MEM_IN, "members of {a}"), ("View", VIEW_IN, "in {a}"),
                                       ("AttackPattern", CHILD_IN, "children of {a}")])
        a = pick(rng, linked(lab, hop))
        return (a, Walk(Anchors((a,), lab), (hop,)), phrase.format(a=R(a))) if a else None

    # ---------------- O1 ----------------
    def o1_ne(rng):
        s = ap_set(rng)
        if not s:
            return None
        a, walk, ph = s
        prop = rng.choice(list(AP_PROPS))
        v = pick(rng, eng.values(walk, prop))
        if v is None:
            return None
        return Cand("O1", "O1.<>", Nodes(Where(walk, (Cond(prop, "<>", v),))),
                    f"Which attack patterns that are {ph} have a {AP_PROPS[prop]} other than '{v}'?",
                    f"attack patterns {ph} with {prop} <> {v}", [a], [ids.label[a], "AttackPattern"])

    def o1_two(rng):
        s = ap_set(rng)
        if not s:
            return None
        a, walk, ph = s
        p1, p2 = sorted(rng.sample(["Typical_Severity", "Likelihood_Of_Attack", "Abstraction"], 2))
        v1, v2 = pick(rng, eng.values(walk, p1)), pick(rng, eng.values(walk, p2))
        if v1 is None or v2 is None:
            return None
        return Cand("O1", "O1.and", Nodes(Where(walk, (Cond(p1, "=", v1), Cond(p2, "=", v2)))),
                    f"Which attack patterns that are {ph} have {AP_PROPS[p1]} '{v1}' and {AP_PROPS[p2]} '{v2}'?",
                    f"attack patterns {ph} with {p1}={v1} and {p2}={v2}", [a], [ids.label[a], "AttackPattern"])

    def o1_text(rng):
        s = ap_set(rng)
        if not s:
            return None
        a, walk, ph = s
        words = sorted({w for x in eng.ids(walk) for w in re.findall(r"[A-Z][a-z]{4,}", ids.name.get(x, ""))})
        wd = pick(rng, words)
        if not wd:
            return None
        return Cand("O1", "O1.contains_text", Nodes(Where(walk, (Cond("name", "contains_text", wd),))),
                    f"Which attack patterns that are {ph} have '{wd}' in their name?",
                    f"attack patterns {ph} whose name contains '{wd}'", [a], [ids.label[a], "AttackPattern"])

    def o1_present(rng):
        s = ap_set(rng)
        if not s:
            return None
        a, walk, ph = s
        prop = rng.choice(["Likelihood_Of_Attack", "Typical_Severity"])
        return Cand("O1", "O1.present", Nodes(Where(walk, (Cond(prop, "present"),))),
                    f"Which attack patterns that are {ph} have a stated {AP_PROPS[prop]}?",
                    f"attack patterns {ph} with {prop} present", [a], [ids.label[a], "AttackPattern"])

    def o1_cwe(rng):
        hop = Hop("EXPLOITS_WEAKNESS", "in", "AttackPattern")
        a = pick(rng, [x for x in linked("Weakness", hop) if len(eng.ids(Walk(Anchors((x,), "Weakness"), (hop,)))) >= 3])
        if not a:
            return None
        walk = Walk(Anchors((a,), "Weakness"), (hop,))
        v = pick(rng, eng.values(walk, "Abstraction"))
        if v is None:
            return None
        return Cand("O1", "O1.<>", Nodes(Where(walk, (Cond("Abstraction", "<>", v),))),
                    f"Which attack patterns that exploit {R(a)} are not at the '{v}' abstraction level?",
                    f"attack patterns exploiting {ids.public[a]} with Abstraction <> {v}", [a],
                    ["Weakness", "EXPLOITS_WEAKNESS", "AttackPattern"])

    # ---------------- O2 ----------------
    def o2_count_label(rng):
        lab = rng.choice(["AttackPattern", "Weakness", "Category", "View", "Mitigation", "ExecutionStep", "Example",
                          "Skill", "Prerequisite", "ExternalReference"])
        return Cand("O2", "O2.count", Aggregate(Scan(lab), "count"),
                    f"How many {noun(lab, 2)} does the CAPEC catalogue contain in total?",
                    f"catalogue-wide count of {noun(lab, 2)}", [], [lab])

    def o2_count_values(rng):
        lab, prop = rng.choice([("AttackPattern", "Typical_Severity"), ("AttackPattern", "Likelihood_Of_Attack"),
                                ("AttackPattern", "Abstraction"), ("ExecutionStep", "phase"), ("Skill", "level"),
                                ("ExternalReference", "publication_year"), ("TaxonomyEntry", "taxonomy_name")])
        return Cand("O2", "O2.count_values", Aggregate(Scan(lab), "count_values", prop),
                    f"How many distinct values of {prop.replace('_', ' ').lower()} occur across all CAPEC "
                    f"{noun(lab, 2)}?", f"distinct values of {prop} over {noun(lab, 2)}", [], [lab])

    def o2_minmax(rng):
        fn = rng.choice(["min", "max"])
        word = "earliest" if fn == "min" else "latest"
        if rng.random() < 0.5:
            return Cand("O2", f"O2.{fn}", Aggregate(Scan("ExternalReference"), fn, "publication_year"),
                        f"What is the {word} publication year of any external reference in CAPEC?",
                        f"{fn} of publication_year over all references", [], ["ExternalReference"])
        hop = Hop("HAS_REFERENCE", "out", "ExternalReference")
        cands = [x for x in linked("AttackPattern", hop)
                 if len(eng.values(Walk(Anchors((x,), "AttackPattern"), (hop,)), "publication_year")) >= 2]
        a = pick(rng, cands)
        if not a:
            return None
        return Cand("O2", f"O2.{fn}", Aggregate(Walk(Anchors((a,), "AttackPattern"), (hop,)), fn, "publication_year"),
                    f"What is the {word} publication year among the external references of {R(a)}?",
                    f"{fn} of publication_year over references of {ids.public[a]}", [a],
                    ["AttackPattern", "HAS_REFERENCE", "ExternalReference"])

    def o2_count_walk(rng):
        v = rng.choice(["Meta", "Standard"])
        return Cand("O2", "O2.count", Aggregate(Walk(TypeScan("AttackPattern", (Cond("Abstraction", "=", v),)),
                                                     (CHILD_IN,)), "count"),
                    f"How many distinct attack patterns are children of a '{v}'-level attack pattern?",
                    f"count of children of {v}-abstraction patterns", [], ["AttackPattern", "ChildOf"])

    def o2_count_filtered(rng):
        prop = rng.choice(["Typical_Severity", "Likelihood_Of_Attack"])
        v = pick(rng, eng.values(Scan("AttackPattern"), prop))
        return Cand("O2", "O2.count", Aggregate(TypeScan("AttackPattern", (Cond(prop, "=", v),
                                                                           Cond("Status", "<>", "Deprecated"))),
                                                "count"),
                    f"How many attack patterns have {AP_PROPS[prop]} '{v}' and a status other than Deprecated?",
                    f"count of attack patterns with {prop}={v} and Status <> Deprecated", [], ["AttackPattern"])

    def o2_median(rng):
        lab, hop, q = rng.choice([
            ("AttackPattern", Hop("HAS_MITIGATION", "out", "Mitigation"),
             "What is the median number of mitigations per attack pattern?"),
            ("Category", MEM_IN, "What is the median number of member attack patterns per category?"),
            ("AttackPattern", Hop("EXPLOITS_WEAKNESS", "out", "Weakness"),
             "What is the median number of weaknesses exploited per attack pattern?"),
            ("AttackPattern", Hop("HAS_EXECUTION_STEP", "out", "ExecutionStep"),
             "What is the median number of execution steps per attack pattern?")])
        return Cand("O2", "O2.median", GroupBy(Scan(lab), (hop,), "count"), q,
                    f"median over {noun(lab, 2)} of the count of {hop.target} (zeros included)", [],
                    [lab, hop.relation, hop.target], reduce="median")

    # ---------------- O3 ----------------
    RANKS = [  # (label, hop, verb singular, verb plural, object)
        ("AttackPattern", Hop("HAS_MITIGATION", "out", "Mitigation"), "has", "have", "mitigations"),
        ("AttackPattern", Hop("EXPLOITS_WEAKNESS", "out", "Weakness"), "exploits", "exploit", "weaknesses"),
        ("AttackPattern", Hop("HAS_EXECUTION_STEP", "out", "ExecutionStep"), "has", "have", "execution steps"),
        ("AttackPattern", CHILD_IN, "has", "have", "direct child attack patterns"),
        ("Weakness", Hop("EXPLOITS_WEAKNESS", "in", "AttackPattern"), "is exploited by", "are exploited by",
         "attack patterns"),
        ("Category", MEM_IN, "has", "have", "member attack patterns"),
        ("View", VIEW_IN, "directly contains", "directly contain", "attack patterns"),
        ("AttackPattern", Hop("REQUIRES_SKILL", "out", "Skill"), "lists", "list", "required skills"),
        ("AttackPattern", Hop("HAS_PREREQUISITE", "out", "Prerequisite"), "has", "have", "prerequisites"),
    ]

    def o3_scan(rng):
        lab, hop, sing, plur, obj = pick(rng, RANKS)
        k = rng.choice([1, 1, 3])
        q = (f"Which {noun(lab)} {sing} the most {obj}? (If several tie, name them all.)" if k == 1 else
             f"Which {k} {noun(lab, 2)} {plur} the most {obj}? (Include any that tie with the {k}rd.)")
        return Cand("O3", "O3.by_walk", Rank(Scan(lab), "desc", k, by_walk=(hop,)), q,
                    f"top {k} {noun(lab, 2)} by count of {hop.relation} {hop.direction}, ties kept", [],
                    [lab, hop.relation, hop.target])

    def o3_set(rng):
        s = ap_set(rng)
        if not s:
            return None
        a, walk, ph = s
        hop, what = rng.choice([(Hop("HAS_MITIGATION", "out", "Mitigation"), "the most mitigations"),
                                (Hop("EXPLOITS_WEAKNESS", "out", "Weakness"), "the most exploited weaknesses"),
                                (Hop("HAS_EXECUTION_STEP", "out", "ExecutionStep"), "the most execution steps"),
                                (Hop("HAS_CONSEQUENCE", "out", "Consequence"), "the most consequences")])
        return Cand("O3", "O3.by_walk", Rank(walk, "desc", 1, by_walk=(hop,)),
                    f"Among the attack patterns that are {ph}, which has {what}? (If several tie, name them all.)",
                    f"attack patterns {ph} ranked by {hop.relation} count, top 1 with ties", [a],
                    [ids.label[a], "AttackPattern", hop.relation])

    def o3_least(rng):
        s = ap_set(rng)
        if not s:
            return None
        a, walk, ph = s
        return Cand("O3", "O3.by_walk_asc", Rank(walk, "asc", 1, by_walk=(Hop("HAS_MITIGATION", "out", "Mitigation"),)),
                    f"Among the attack patterns that are {ph}, which has the fewest mitigations (zero counts)? (If several tie, name them all.)",
                    f"attack patterns {ph} with the fewest mitigations, ties kept", [a],
                    [ids.label[a], "AttackPattern", "HAS_MITIGATION"])

    # ---------------- O4 verify ----------------
    VPAIRS = [("AttackPattern", "ChildOf", "AttackPattern"), ("AttackPattern", "EXPLOITS_WEAKNESS", "Weakness"),
              ("AttackPattern", "MEMBER_OF", "Category"), ("AttackPattern", "IN_VIEW", "View"),
              ("AttackPattern", "CanPrecede", "AttackPattern"), ("Category", "IN_VIEW", "View"),
              ("AttackPattern", "PeerOf", "AttackPattern"), ("AttackPattern", "CanFollow", "AttackPattern")]
    vcount = [0]

    def o4(rng):
        i = vcount[0]
        vcount[0] += 1
        sl, rel, tl = VPAIRS[i % len(VPAIRS)]
        hop = Hop(rel, "out", tl)
        negative = i % 6 == 5
        with_rel = i % 2 == 0
        src = pick(rng, linked(sl, hop))
        if not src:
            return None
        nb = set(eng.ids(Walk(Anchors((src,), sl), (hop,))))
        pool = sorted(x for x in set(eng.ids(Scan(tl))) - nb - {src} if ids.is_public(x)) if negative else \
            sorted(x for x in nb if ids.is_public(x))
        tgt = pick(rng, pool)
        if not tgt:
            return None
        node = Verify(Anchors((src,), sl), Anchors((tgt,), tl), rel if with_rel else None, "out" if with_rel else None)
        q = f"Does {R(src)} {REL_PHRASE[(rel, 'out')]} {R(tgt)}?" if with_rel else \
            f"Is {R(src)} directly linked to {R(tgt)} in CAPEC, and if so by what relationship?"
        return Cand("O4", "O4.verify" + ("" if with_rel else ".any"), node, q,
                    f"is there a {rel if with_rel else 'direct'} link from {ids.public[src]} to {ids.public[tgt]}",
                    [src, tgt], [sl, rel, tl], negative=negative)

    # ---------------- O5 ----------------
    def o5_two(rng):
        p1, p2 = sorted(rng.sample(["Typical_Severity", "Likelihood_Of_Attack", "Abstraction", "Status"], 2))
        v1, v2 = pick(rng, eng.values(Scan("AttackPattern"), p1)), pick(rng, eng.values(Scan("AttackPattern"), p2))
        return Cand("O5", "O5.typescan", Nodes(TypeScan("AttackPattern", (Cond(p1, "=", v1), Cond(p2, "=", v2)))),
                    f"Which attack patterns have {AP_PROPS[p1]} '{v1}' and {AP_PROPS[p2]} '{v2}'?",
                    f"attack patterns with {p1}={v1} and {p2}={v2}", [], ["AttackPattern"])

    def o5_text(rng):
        words = sorted({w for x in eng.ids(Scan("AttackPattern"))
                        for w in re.findall(r"[A-Z][a-z]{4,}", ids.name.get(x, ""))})
        wd = pick(rng, words)
        return Cand("O5", "O5.typescan", Nodes(TypeScan("AttackPattern", (Cond("name", "contains_text", wd),))),
                    f"Which attack patterns have '{wd}' in their name?", f"attack patterns whose name contains '{wd}'",
                    [], ["AttackPattern"])

    def o5_small(rng):
        lab, prop = rng.choice([("Category", "Status"), ("View", "Type"), ("View", "Status")])
        v = pick(rng, eng.values(Scan(lab), prop))
        return Cand("O5", "O5.typescan", Nodes(TypeScan(lab, (Cond(prop, "=", v),))),
                    f"Which CAPEC {noun(lab, 2)} have {prop.lower()} '{v}'?", f"{noun(lab, 2)} with {prop}={v}", [], [lab])

    def o5_count(rng):
        lab, prop = rng.choice([("Skill", "level"), ("ExecutionStep", "phase"), ("AttackPattern", "Typical_Severity"),
                                ("TaxonomyEntry", "taxonomy_name")])
        v = pick(rng, eng.values(Scan(lab), prop))
        return Cand("O5", "O5.count", Count(TypeScan(lab, (Cond(prop, "=", v),))),
                    f"How many CAPEC {noun(lab, 2)} have {prop.replace('_', ' ').lower()} '{v}'?",
                    f"count of {noun(lab, 2)} with {prop}={v}", [], [lab])

    def o5_missing(rng):
        v = pick(rng, eng.values(Scan("AttackPattern"), "Abstraction"))
        return Cand("O5", "O5.typescan", Nodes(TypeScan("AttackPattern", (Cond("Abstraction", "=", v),
                                                                           Cond("Likelihood_Of_Attack", "missing")))),
                    f"Which '{v}'-level attack patterns have no stated likelihood of attack?",
                    f"attack patterns with Abstraction={v} and no Likelihood_Of_Attack", [], ["AttackPattern"])

    # ---------------- O6 ----------------
    def o6_having(rng):
        lab, hop, verb = rng.choice([("Category", MEM_IN, "have"), ("View", VIEW_IN, "directly contain"),
                                     ("AttackPattern", Hop("HAS_MITIGATION", "out", "Mitigation"), "have"),
                                     ("AttackPattern", Hop("EXPLOITS_WEAKNESS", "out", "Weakness"), "exploit"),
                                     ("Weakness", Hop("EXPLOITS_WEAKNESS", "in", "AttackPattern"), "are exploited by")])
        n = rng.choice([5, 8, 10, 12]) if lab != "AttackPattern" else rng.choice([7, 9, 10, 12, 15])
        tn = "member attack patterns" if hop.target == "AttackPattern" and lab == "Category" else noun(hop.target, 2)
        return Cand("O6", "O6.having", GroupBy(Scan(lab), (hop,), "count", having=(">=", n)),
                    f"Which {noun(lab, 2)} {verb} at least {n} {tn}?",
                    f"{noun(lab, 2)} with count({hop.relation} {hop.direction}) >= {n}", [], [lab, hop.relation, hop.target])

    def o6_zero(rng):
        s = ap_set(rng)
        if not s:
            return None
        a, walk, ph = s
        hop, what = rng.choice([(Hop("HAS_EXECUTION_STEP", "out", "ExecutionStep"), "no execution steps"),
                                (Hop("EXPLOITS_WEAKNESS", "out", "Weakness"), "no exploited weakness"),
                                (Hop("HAS_EXAMPLE", "out", "Example"), "no examples")])
        return Cand("O6", "O6.having_zero", GroupBy(walk, (hop,), "count", having=("=", 0)),
                    f"Which attack patterns that are {ph} have {what}?",
                    f"attack patterns {ph} with count({hop.relation}) = 0", [a], [ids.label[a], "AttackPattern", hop.relation])

    def o6_end(rng):
        prop = rng.choice(["Typical_Severity", "Likelihood_Of_Attack"])
        v = pick(rng, eng.values(Scan("AttackPattern"), prop))
        k = rng.choice([1, 3])
        return Cand("O6", "O6.end_conds", GroupBy(Scan("Category"), (MEM_IN,), "count",
                                                  end_conds=(Cond(prop, "=", v),), order="desc", k=k),
                    f"Which {'category has' if k == 1 else f'{k} categories have'} the most member attack patterns "
                    f"with {AP_PROPS[prop]} '{v}'{'' if k == 1 else ' (ties included)'}?",
                    f"categories ranked by members with {prop}={v}, top {k}", [], ["Category", "MEMBER_OF", "AttackPattern"])

    def o6_walk(rng):
        s = ap_set(rng)
        if not s:
            return None
        a, walk, ph = s
        n = rng.choice([2, 3, 4, 5])
        return Cand("O6", "O6.having", GroupBy(walk, (Hop("HAS_MITIGATION", "out", "Mitigation"),), "count",
                                               having=(">=", n)),
                    f"Which attack patterns that are {ph} have at least {n} mitigations?",
                    f"attack patterns {ph} with {n}+ mitigations", [a], [ids.label[a], "AttackPattern", "HAS_MITIGATION"])

    def o6_skill(rng):
        n = rng.choice([2, 3])
        v = rng.choice(["High", "Medium", "Low"])
        return Cand("O6", "O6.end_conds", GroupBy(Scan("AttackPattern"), (Hop("REQUIRES_SKILL", "out", "Skill"),),
                                                  "count", end_conds=(Cond("level", "=", v),), having=(">=", n)),
                    f"Which attack patterns require at least {n} skills at the '{v}' level?",
                    f"attack patterns with {n}+ required skills of level {v}", [], ["AttackPattern", "REQUIRES_SKILL", "Skill"])

    # ---------------- O7 core ----------------
    def o7_union(rng):
        c = pick(rng, linked("Category", MEM_IN))
        v = pick(rng, linked("View", VIEW_IN))
        if not (c and v):
            return None
        return Cand("O7", "O7c.union", Nodes(Union_((Walk(Anchors((c,), "Category"), (MEM_IN,)),
                                                     Walk(Anchors((v,), "View"), (VIEW_IN,))))),
                    f"Which attack patterns are either members of {R(c)} or directly in {R(v)}?",
                    f"union of members of {ids.public[c]} and of {ids.public[v]}", [c, v],
                    ["Category", "MEMBER_OF", "View", "IN_VIEW", "AttackPattern"])

    def o7_union_ap(rng):
        a = pick(rng, linked("AttackPattern", CHILD_IN))
        if not a:
            return None
        other, phrase = rng.choice([(Hop("CanPrecede", "out", "AttackPattern"), "can be preceded by {a}"),
                                    (Hop("ChildOf", "out", "AttackPattern"), "are parents of {a}"),
                                    (Hop("PeerOf", "out", "AttackPattern"), "are peers of {a}")])
        return Cand("O7", "O7c.union", Nodes(Union_((Walk(Anchors((a,), "AttackPattern"), (CHILD_IN,)),
                                                     Walk(Anchors((a,), "AttackPattern"), (other,))))),
                    f"Which attack patterns either are children of {R(a)} or {phrase.format(a=R(a))}?",
                    f"union of children of {ids.public[a]} and {other.relation} {other.direction}", [a],
                    ["AttackPattern", "ChildOf", other.relation])

    def o7_absence(rng):
        s = ap_set(rng)
        if not s:
            return None
        a, walk, ph = s
        hop, what = rng.choice([(Hop("HAS_MITIGATION", "out", "Mitigation"), "no mitigation"),
                                (Hop("EXPLOITS_WEAKNESS", "out", "Weakness"), "no exploited weakness"),
                                (Hop("MAPS_TO", "out", "TaxonomyEntry"), "no taxonomy mapping")])
        return Cand("O7", "O7d.absence", Nodes(Having(walk, hop, False)),
                    f"Which attack patterns that are {ph} have {what}?",
                    f"attack patterns {ph} lacking any {hop.relation}", [a], [ids.label[a], "AttackPattern", hop.relation])

    def o7_absence_cond(rng):
        s = ap_set(rng)
        if not s:
            return None
        a, walk, ph = s
        v = rng.choice(["High", "Medium", "Low"])
        hop = Hop("REQUIRES_SKILL", "out", "Skill")
        return Cand("O7", "O7d.absence", Nodes(Having(walk, hop, False, (Cond("level", "=", v),))),
                    f"Which attack patterns that are {ph} require no skill at the '{v}' level?",
                    f"attack patterns {ph} lacking a {v}-level required skill", [a],
                    [ids.label[a], "AttackPattern", "REQUIRES_SKILL", "Skill"])

    def o7_edge(rng):
        steps = sorted(eng.stores.gremlin("g.E().hasLabel('HAS_EXECUTION_STEP').values('step').dedup()"), key=int)
        st = pick(rng, [s for s in steps if int(s) >= 6])
        hop = Hop("HAS_EXECUTION_STEP", "out", "ExecutionStep", (Cond("step", "=", st),))
        if rng.random() < 0.5:
            return Cand("O7", "O7a.edgefilter", Nodes(Having(Scan("AttackPattern"), hop, True)),
                        f"Which attack patterns have an execution step numbered {st}?",
                        f"attack patterns with a HAS_EXECUTION_STEP edge whose step = '{st}'", [],
                        ["AttackPattern", "HAS_EXECUTION_STEP", "ExecutionStep"])
        s = ap_set(rng)
        if not s:
            return None
        a, walk, ph = s
        st = pick(rng, [s for s in steps if 3 <= int(s) <= 6])
        hop = Hop("HAS_EXECUTION_STEP", "out", "ExecutionStep", (Cond("step", "=", st),))
        return Cand("O7", "O7a.edgefilter", Nodes(Having(walk, hop, False)),
                    f"Which attack patterns that are {ph} have no execution step numbered {st}?",
                    f"attack patterns {ph} lacking a HAS_EXECUTION_STEP edge with step = '{st}'", [a],
                    [ids.label[a], "AttackPattern", "HAS_EXECUTION_STEP"])

    # ---------------- O8 ----------------
    def o8_reach(rng):
        rel, d, q = rng.choice([
            (("ChildOf", "out"), 6, "Which attack patterns are ancestors of {a} (following child-of links upward, any depth up to 6)?"),
            (("ChildOf", "in"), 6, "Which attack patterns are descendants of {a} (following child-of links downward, any depth up to 6)?"),
            (("CanPrecede", "out"), 6, "Which attack patterns can follow {a} in a chain of can-precede links (up to 6 steps)?"),
            (("CanFollow", "out"), 6, "Which attack patterns can {a} follow in a chain of can-follow links (up to 6 steps)?")])
        hop = Hop(rel[0], rel[1], "AttackPattern")
        a = pick(rng, linked("AttackPattern", hop))
        if not a:
            return None
        return Cand("O8", "O8.reach", Nodes(Reach(Anchors((a,), "AttackPattern"), (rel,), d)), q.format(a=R(a)),
                    f"attack patterns reachable from {ids.public[a]} via {rel[0]} {rel[1]} within {d}", [a],
                    ["AttackPattern", rel[0]])

    def o8_shortest(rng):
        if rng.random() < 0.5:
            a = pick(rng, linked("AttackPattern", Hop("ChildOf", "out", "AttackPattern")))
            if not a:
                return None
            anc = eng.ids(Reach(Anchors((a,), "AttackPattern"), (("ChildOf", "out"),), 6))
            sib = pick(rng, [x for x in eng.ids(Reach(Anchors((pick(rng, anc),), "AttackPattern"), (("ChildOf", "in"),), 3))
                             if x != a]) if anc else None
            b = sib
        else:
            pool = [x for x in eng.ids(Scan("AttackPattern"))]
            a, b = sorted(rng.sample(pool, 2))
        if not (a and b):
            return None
        a, b = sorted([a, b])
        return Cand("O8", "O8.shortest", Shortest(Anchors((a,), "AttackPattern"), Anchors((b,), "AttackPattern"), (), 6),
                    f"What is the shortest chain of relationships (any relationship, either direction) that connects "
                    f"{R(a)} and {R(b)}?",
                    f"all shortest paths between {ids.public[a]} and {ids.public[b]}, depth cap 6", [a, b],
                    ["AttackPattern"])

    return {
        "O1": [o1_ne, o1_two, o1_text, o1_present, o1_cwe],
        "O2": [o2_count_label, o2_count_values, o2_minmax, o2_count_walk, o2_count_filtered, o2_median],
        "O3": [o3_scan, o3_set, o3_scan, o3_least],
        "O4": [o4],
        "O5": [o5_two, o5_text, o5_small, o5_count, o5_missing],
        "O6": [o6_having, o6_zero, o6_end, o6_walk, o6_skill],
        "O7": [o7_union, o7_absence, o7_edge, o7_union_ap, o7_absence_cond],
        "O7b": [],  # CAPEC stores no ISO date (publication_year is a bare year, which S6 never matches)
        "O8": [o8_reach, o8_shortest],
    }


# --------------------------------------------------------------------------- #
# Drawing
# --------------------------------------------------------------------------- #


def draw(ds: str, op: str, templates: list[Template], eng: Engine, ids: Ids, target: int, rng: random.Random,
         drops: collections.Counter, seen: set[str], log: Callable[[str], None]) -> list[dict[str, Any]]:
    """Cycle the operator's templates until ``target`` items have exact gold, or tries run out."""
    out: list[dict[str, Any]] = []
    if not templates:
        return out
    tries, max_tries = 0, target * 12
    while len(out) < target and tries < max_tries:
        t = templates[tries % len(templates)]
        tries += 1
        try:
            cand = t(rng)
        except Exception as exc:  # noqa: BLE001 - a template that cannot draw is counted, not fatal
            drops[(ds, op, f"draw_error:{type(exc).__name__}")] += 1
            log(f"  draw error {ds} {op}: {type(exc).__name__}: {str(exc)[:160]}")
            continue
        if cand is None:
            drops[(ds, op, "no_parameters")] += 1
            continue
        iid = item_id(ds, cand)
        if iid in seen:
            drops[(ds, op, "duplicate")] += 1
            continue
        gold, why = compute_gold(eng, ids, cand)
        if gold is None:
            drops[(ds, op, why)] += 1
            continue
        seen.add(iid)
        out.append(finish_item(ds, ids, cand, gold))
    log(f"  {ds} {op}: {len(out)}/{target} after {tries} tries")
    return out


def cap_negatives(items: list[dict[str, Any]], drops: collections.Counter) -> list[dict[str, Any]]:
    """Keep deliberate negatives at or under ``NEG_SHARE`` of the set (drop the latest drawn first)."""
    neg = [i for i in items if i["negative"]]
    allowed = int(NEG_SHARE * (len(items) - len(neg)) / (1 - NEG_SHARE))
    if len(neg) <= allowed:
        return items
    drop = {i["id"] for i in sorted(neg, key=lambda i: hashlib.sha256(i["id"].encode()).hexdigest())[allowed:]}
    for i in items:
        if i["id"] in drop:
            drops[(i["dataset"], i["operator"], "negative_quota")] += 1
    return [i for i in items if i["id"] not in drop]


# --------------------------------------------------------------------------- #
# External items
# --------------------------------------------------------------------------- #


def open_tuning_bank(path: Path) -> dict[str, Any]:
    if SEALED.search(str(path)):
        raise PermissionError(f"refusing a sealed bank: {path}")
    return json.loads(path.read_text())


STEP6_STATUS = {
    "statistical_median": ("core", "O2.aggregate + O6.groupby: a group-by count over every member (zeros "
                                   "included), then the median of the group values"),
    "path_search": ("extended", "O8.path shortest: every acyclic path of the minimum length"),
    "temporal_trend": (None, "asks how a count changed from year to year; the graph holds one ATT&CK/CAPEC release "
                             "and no history, so no operator (O7b included) can answer it"),
    "similarity": (None, "semantic similarity / nearest neighbour (X.similar) is outside retrieval"),
}

STEP6_MEDIAN = {  # step 6 id -> (member label, hop)
    "CG-58a3ac8293ed": ("Group", ("USES", "out", "Software")),
    "CG-99e2558015f9": ("Campaign", ("USES", "out", "SubTechnique")),
    "CG-ae0e79679111": ("DetectionStrategy", ("HAS_ANALYTIC", "out", "Analytic")),
    "CG-1ca4ef814dd0": ("AttackPattern", ("HAS_EXAMPLE", "out", "Example")),
}


def step6_items(engines: dict[str, Engine], idss: dict[str, Ids], drops: collections.Counter,
                log: Callable[[str], None]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """External items from Step 6's out-of-coverage set, and its relabel table."""
    from utils.specialists.algebra import Anchors, GroupBy, Hop, Scan, Shortest

    items, relabel = [], []
    for ds, path in STEP6_BANKS.items():
        bank = open_tuning_bank(path)
        for q in bank["questions"]:
            cg = q.get("card_gen") or {}
            if cg.get("kind") != "out_of_coverage":
                continue
            miss = cg.get("missing_operator")
            switch, why = STEP6_STATUS.get(miss, (None, f"unknown missing operator {miss!r}"))
            row = {"id": q["id"], "dataset": ds, "question": q["question"], "missing_operator": miss,
                   "old_status": "out_of_coverage (gold_status: not_expressible, expected [])",
                   "core": "answerable" if switch == "core" else "out_of_coverage",
                   "extended": "answerable" if switch in ("core", "extended") else "out_of_coverage",
                   "why": why, "probe_item": None, "gold": None}
            eng, ids = engines[ds], idss[ds]
            cand = None
            if miss == "statistical_median" and q["id"] in STEP6_MEDIAN:
                lab, (rel, d, tgt) = STEP6_MEDIAN[q["id"]]
                cand = Cand("O2", "O2.median", GroupBy(Scan(lab), (Hop(rel, d, tgt),), "count"), q["question"],
                            f"median over {noun(lab, 2)} of the count of {tgt} by {rel} (zeros included)", [],
                            [lab, rel, tgt], reduce="median", source="external|step6", external_ref=q["id"])
                row["note"] = (f"the anchor {cg.get('anchor')} the generator attached is not used: the question is "
                               "catalogue-wide")
            elif miss == "path_search":
                a, b = ids.stored.get(cg["anchor"]), ids.stored.get(cg["other_anchor"])
                if a and b:
                    la, lb = ids.label[a], ids.label[b]
                    depth = 6 if ds == "capec" else 3
                    cand = Cand("O8", "O8.shortest", Shortest(Anchors((a,), la), Anchors((b,), lb), (), depth),
                                q["question"], f"all shortest paths between {cg['anchor']} and {cg['other_anchor']}",
                                [a, b], [la, lb], source="external|step6", external_ref=q["id"])
                    if ds == "attack":
                        row["note"] = ("gold computed with depth cap 3: at the default cap 6 the ATT&CK Cypher "
                                       "shortest query (its 'beyond' check) exceeds the 60 s timeout")
            if cand is not None:
                gold, why2 = compute_gold(eng, ids, cand)
                if gold is None:
                    drops[(ds, cand.operator, f"external:{why2}")] += 1
                    row["status_detail"] = f"operator applies but gold could not be computed: {why2}"
                    log(f"  step6 {q['id']}: dropped ({why2})")
                else:
                    it = finish_item(ds, ids, cand, gold)
                    items.append(it)
                    row["probe_item"] = it["id"]
                    row["gold"] = {"kind": gold["kind"], "value": gold.get("value"), "ids": gold.get("ids")}
            relabel.append(row)
    relabel.sort(key=lambda r: (r["dataset"], r["id"]))
    return items, relabel


def attackqa_verify_items(eng: Engine, ids: Ids, drops: collections.Counter,
                          log: Callable[[str], None]) -> list[dict[str, Any]]:
    """A deterministic sample of AttackQA rows labelled O4.verify whose two ends are one card relationship.

    ``relationships_uses_software`` (S uses T) and ``relationships_mitigations`` (M mitigates T) qualify;
    ``relationships_detects`` names a data component, which reaches a technique only through
    analytic -> detection strategy, so it is not one link. Only the row id and our own template
    question are written (D-020: AttackQA text stays out of the repository).
    """
    from utils.specialists.algebra import Anchors, Verify

    pq = [json.loads(line) for line in (SHAPE / "per_question.jsonl").read_text().splitlines() if line.strip()]
    want = {p["id"]: p["family"] for p in pq if p["source"] == "attackqa" and "O4.verify" in p["codes"]
            and p["family"] in ("relationships_uses_software", "relationships_mitigations")}
    try:
        from utils.evaluation.external.fetch import read_attackqa

        rows = {f"attackqa:{r['__index_level_0__']}": r for r in read_attackqa(EXTERNAL / "attackqa.parquet")
                if f"attackqa:{r['__index_level_0__']}" in want}
    except Exception as exc:  # noqa: BLE001
        log(f"  attackqa: cannot read the parquet ({type(exc).__name__}: {exc}); skipped")
        drops[("attack", "O4", "external:attackqa_unreadable")] += 1
        return []
    order = sorted(rows, key=lambda k: hashlib.sha256(k.encode()).hexdigest())
    out: list[dict[str, Any]] = []
    quota = {"relationships_uses_software": 10, "relationships_mitigations": 5}
    for key in order:
        fam = want[key]
        if quota.get(fam, 0) <= 0:
            continue
        r = rows[key]
        a, b = ids.stored.get(str(r.get("relation_id"))), ids.stored.get(str(r.get("subject_id")))
        if not (a and b):
            drops[("attack", "O4", "external:anchor_not_found")] += 1
            continue
        la, lb = ids.label[a], ids.label[b]
        rel = "USES" if fam == "relationships_uses_software" else "MITIGATES"
        verb = "use" if rel == "USES" else "mitigate"
        cand = Cand("O4", "O4.verify", Verify(Anchors((a,), la), Anchors((b,), lb), rel, "out"),
                    f"Does {ids.ref(a)} {verb} {ids.ref(b)}, and what does the record say about how?",
                    f"is there a {rel} link from {ids.public[a]} to {ids.public[b]} (AttackQA asks how; the witness "
                    f"edge carries the description)", [a, b], [la, rel, lb], source="external|attackqa",
                    external_ref=key)
        gold, why = compute_gold(eng, ids, cand)
        if gold is None and why == "verify_polarity":  # the link is absent in this release: a natural negative
            cand.negative = True
            gold, why = compute_gold(eng, ids, cand)
        if gold is None:
            drops[("attack", "O4", f"external:{why}")] += 1
            continue
        out.append(finish_item("attack", ids, cand, gold))
        quota[fam] -= 1
    log(f"  attackqa verify: {len(out)} items")
    return out


# --------------------------------------------------------------------------- #
# Split
# --------------------------------------------------------------------------- #


def split_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic, stratified halves.

    Within each stratum (operator, dataset) items are ordered by sha256(id). The parity of the
    first item's hash decides which half it goes to; the rest alternate, so every stratum with
    two or more items has items in both halves and the halves differ in size by at most one per
    stratum. Nothing depends on the order the items were drawn in.
    """
    strata: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for it in items:
        strata[(it["operator"], it["dataset"])].append(it)
    for group in strata.values():
        group.sort(key=lambda i: hashlib.sha256(i["id"].encode()).hexdigest())
        start = int(hashlib.sha256(group[0]["id"].encode()).hexdigest(), 16) % 2
        for n, it in enumerate(group):
            it["split"] = "tune" if (n + start) % 2 == 0 else "measure"
    return items


# --------------------------------------------------------------------------- #
# Bank emission
# --------------------------------------------------------------------------- #

BANK_LIMITS = {"max_traversal_depth": 3, "max_result_rows": ROW_CAP, "query_timeout_ms": 60_000}


def bank_entry(item: dict[str, Any], question: str) -> dict[str, Any]:
    """One dev-bank-format entry for ``experiment_untruncated.load_work``."""
    g = item["gold"]
    ex_gold: dict[str, Any] = {"pool": "algebra", "scheme": item["dataset"]}
    if g["kind"] == "nodes":
        ex_gold.update(kind="set", expected=list(g["ids"]))
    else:
        ex_gold.update(kind="value", expected=[], value=g["value"])
    seeds = [a["public"] for a in item["anchors"]]
    return {
        "id": item["id"],
        "question": question,
        "split": item["split"],
        "tier": "algebra-probe",
        "assertions": {"min_records": 0, "must_include_ids": [], "must_include_related": []},
        "ex_gold": ex_gold,
        "task": {
            "sub_question_id": item["id"],
            "source": item["dataset"],
            "text": question,
            "entities": item["entities"],
            "limits": dict(BANK_LIMITS),
            "join_key": None,
            "seed_ids": seeds,
            "rationale": "algebra probe set (Era 2 Step 9 Phase G)",
        },
        "algebra_probe": item,
    }


def emit_banks(structured: dict[str, Any], wording: dict[str, str], out_dir: Path) -> dict[str, Path]:
    items = structured["items"]
    missing = [i["id"] for i in items if i["id"] not in wording]
    if missing:
        raise SystemExit(f"{len(missing)} items have no reworded question, e.g. {missing[:3]}")
    paths = {}
    for split in ("tune", "measure"):
        entries = [bank_entry(i, wording[i["id"]]) for i in items if i["split"] == split]
        doc = {"meta": {"created": structured["meta"]["created"], "split": split, "count": len(entries),
                        "generator": "scripts/algebra_probe_set.py bank", "sealed": False,
                        "source": "probe-structured.json",
                        "note": "ex_gold.kind 'set' = node ids (public); 'value' = a scalar in ex_gold.value. "
                                "Score with scripts/algebra_probe_score.py."},
               "questions": entries}
        p = out_dir / f"probe-{split}.json"
        p.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
        paths[split] = p
    return paths


def read_wording(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            out[d["id"]] = d["question"]
    return out


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def generate(out_dir: Path = OUT, seed: int = SEED, verbose: bool = True) -> dict[str, Any]:
    import datetime

    log = (lambda s: print(s, file=sys.stderr)) if verbose else (lambda s: None)
    stores = Stores()
    try:
        cards = load_cards()
        added = add_stored_edge_props(cards, stores)
        log(f"edge properties added to the cards: {added}")
        idss = {ds: Ids(ds, stores) for ds in ("attack", "capec")}
        engines = {ds: Engine(ds, cards[ds], stores) for ds in ("attack", "capec")}
        drops: collections.Counter = collections.Counter()
        seen: set[str] = set()
        items: list[dict[str, Any]] = []
        for ds, mk in (("attack", attack_templates), ("capec", capec_templates)):
            tmpls = mk(engines[ds], idss[ds])
            for op in TARGET:
                rng = random.Random(f"{seed}|{ds}|{op}")
                items += draw(ds, op, tmpls.get(op, []), engines[ds], idss[ds], TARGET[op], rng, drops, seen, log)
        ext, relabel = step6_items(engines, idss, drops, log)
        items += ext
        items += attackqa_verify_items(engines["attack"], idss["attack"], drops, log)
    finally:
        stores.close()
    items = cap_negatives(items, drops)
    items = split_items(items)
    items.sort(key=lambda i: (i["dataset"], list(TARGET).index(i["operator"]), i["id"]))
    counts = collections.Counter((i["operator"], i["dataset"], i["split"], i["switch"]) for i in items)
    meta = {
        "created": datetime.date.today().isoformat(),
        "seed": seed,
        "generator": "scripts/algebra_probe_set.py generate",
        "stores": {"attack": f"neo4j {NEO4J_URI} (compile_cypher)", "capec": f"gremlin {GREMLIN_URI} (compile_gremlin)"},
        "row_cap": ROW_CAP,
        "target_per_operator_per_dataset": TARGET,
        "switch": {op: SWITCH.get(op, "core") for op in TARGET},
        "edge_props_added_to_cards": added,
        "rules": {
            "gold": "the finished result of the item's IR on its runtime engine; ids are public (attack_id, CAPEC-<n>, "
                    "CWE-<n>); stored_ids beside them",
            "dropped": "empty gold (unless deliberately negative), incomplete/partial results, anchors not found, "
                       f"node answers over {MAX_GOLD_IDS} ids, ranks whose ties exceed {MAX_RANK_IDS} ids, results "
                       "holding ids with no public form, timeouts, duplicates",
            "negatives": f"deliberate negatives (verify false, empty sets) kept at or under {NEG_SHARE:.0%}",
            "reduce": "reduce='median' marks O2 applied to a groupby's values (zeros included): the IR holds the "
                      "GroupBy, the gold value is the median of every member's value",
            "split": "per (operator, dataset) stratum, ordered by sha256(id), alternating from the first hash's parity",
        },
        "counts": {"items": len(items), "by_operator_dataset_split_switch":
                   [{"operator": k[0], "dataset": k[1], "split": k[2], "switch": k[3], "n": v}
                    for k, v in sorted(counts.items())]},
        "dropped": [{"dataset": k[0], "operator": k[1], "reason": k[2], "n": v} for k, v in sorted(drops.items())],
        "negatives": sum(1 for i in items if i["negative"]),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    structured = {"meta": meta, "items": items}
    (out_dir / "probe-structured.json").write_text(json.dumps(structured, indent=1, ensure_ascii=False) + "\n")
    with (out_dir / "wording-input.jsonl").open("w") as fh:
        for i in items:
            fh.write(json.dumps({"id": i["id"], "dataset": i["dataset"], "template_question": i["template_question"],
                                 "description": i["description"]}, ensure_ascii=False) + "\n")
    relabel_doc = {
        "meta": {"created": meta["created"], "source": [str(p.relative_to(REPO)) for p in STEP6_BANKS.values()],
                 "note": "Every Step 6 out-of-coverage tuning item, with its status once operators are switched on. "
                         "'core' = operators 1-7 without time; 'extended' adds O7b time and O8 paths. Where answerable, "
                         "probe_item names the probe item that carries its IR and gold."},
        "summary": dict(collections.Counter(f"core={r['core']}, extended={r['extended']}" for r in relabel)),
        "items": relabel,
    }
    (out_dir / "step6-relabel.json").write_text(json.dumps(relabel_doc, indent=1, ensure_ascii=False) + "\n")
    return structured


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="draw items and gold from the live stores (read-only)")
    g.add_argument("--out", default=str(OUT))
    g.add_argument("--seed", type=int, default=SEED)
    b = sub.add_parser("bank", help="emit probe-tune.json and probe-measure.json from reworded questions")
    b.add_argument("--wording", required=True, help='JSONL of {"id", "question"}')
    b.add_argument("--structured", default=str(OUT / "probe-structured.json"))
    b.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)
    if args.cmd == "generate":
        s = generate(Path(args.out), args.seed)
        print(json.dumps({"items": len(s["items"]), "negatives": s["meta"]["negatives"]}))
        return 0
    structured = json.loads(Path(args.structured).read_text())
    paths = emit_banks(structured, read_wording(Path(args.wording)), Path(args.out))
    from utils.evaluation.experiment_untruncated import load_work

    for split, p in paths.items():
        work = load_work(str(p))
        print(f"{split}: {p} ({len(work)} entries load)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
