"""Running an algebra step inside a specialist (Era 2, Step 9, Phase G).

A typed step of kind ``algebra`` (only the typed planner writes one, and only
behind ``ARIADNE_ALGEBRA_CORE``) carries the internal form as JSON with
**public** anchor ids. :func:`run_algebra` is the specialist's path for it:

1. **Ids.** Every public id in the tree, and the seeds an earlier step handed
   over for a ``FromStep``, are mapped to stored ids by a store lookup
   (operator-algebra.md §1). Neo4j: a node's ``attack_id`` or ``id``. Gremlin: the
   namespaced ids ``_walk_candidate_ids`` offers (``CAPEC-66`` ->
   ``capec:attack-pattern:66`` / ``capec:category:66`` / ``capec:view:66``), kept
   only when a vertex has one. An id that maps to nothing is passed through
   unchanged and so matches nothing: the compiled query reports it as
   ``anchor_not_found`` (S12), which is mapped back to the public id.
2. **Compile.** The builder's ``_typed_step`` dispatches the step to
   ``compile_cypher`` / ``compile_gremlin`` with the card and the task's row cap
   (:func:`draft`); ``FromStep`` parameters are filled with the stored seeds.
3. **Run and finish.** One query, one envelope record, ``compiled.finish``.
4. **Into the answer.** Result nodes become evidence records (public ids, card
   labels, with their ``value`` for a rank or a group); a scalar, rank, group,
   verify or path result is also stated as one plain sentence by the
   deterministic composer (:func:`claim_text`). The machine-readable result is
   an ``algebra`` trace on the specialist result; :func:`algebra_results` reads
   those traces into ``run_meta.algebra_results``.

Nothing here runs when both switches are off, because no step of kind
``algebra`` exists then.
"""

from __future__ import annotations

import dataclasses
import functools
import json
import re
from typing import Any

from .compiled import Compiled, Result, finish
from .base import Anchors, FromStep

#: The trace step that carries a finished result.
TRACE = "algebra"
#: Rows kept in the machine-readable result (the evidence keeps the row cap).
CONTRACT_ROWS = 50
#: Members named in a group or ranking sentence before "and N more".
SENTENCE_ITEMS = 25
_TECHNIQUE_ID_RE = re.compile(r"^T\d{4}(?:\.\d{3})?$")


# --------------------------------------------------------------------------- #
# The card and the tree
# --------------------------------------------------------------------------- #


@functools.lru_cache(maxsize=None)
def card_model(dataset: str) -> Any:
    """The catalog's ``CardModel`` of a source card (what the planner validated against)."""
    from utils.agent.catalog import catalog_for
    from utils.planner.cards import load_source_cards

    return catalog_for(load_source_cards()[dataset]).model


def backend_name(card: Any) -> str:
    return "gremlin" if str(getattr(card, "runtime_backend", "")).lower() == "gremlin" else "cypher"


def spec_of(step: Any) -> dict[str, Any]:
    spec = step.algebra_spec() if step is not None else None
    if not spec:
        raise ValueError("not an algebra step")
    return spec


def _map_anchors(node: Any, fn: Any) -> Any:
    """``node`` with every ``Anchors`` replaced by ``fn(anchors)``."""
    if isinstance(node, Anchors):
        return fn(node)
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        return dataclasses.replace(node, **{f.name: _map_anchors(getattr(node, f.name), fn)
                                            for f in dataclasses.fields(node)})
    if isinstance(node, tuple):
        return tuple(_map_anchors(x, fn) for x in node)
    return node


def _walk(node: Any, kind: type) -> list[Any]:
    out: list[Any] = []

    def go(x: Any) -> None:
        if isinstance(x, kind):
            out.append(x)
        if dataclasses.is_dataclass(x) and not isinstance(x, type):
            for f in dataclasses.fields(x):
                go(getattr(x, f.name))
        elif isinstance(x, (tuple, list)):
            for y in x:
                go(y)

    go(node)
    return out


# --------------------------------------------------------------------------- #
# Ids: public <-> stored, by store lookup
# --------------------------------------------------------------------------- #

_CYPHER_TO_STORED = ("MATCH (n) WHERE n.attack_id IN $ids OR n.id IN $ids "
                     "RETURN n.id AS id, coalesce(n.attack_id, n.id) AS pub")
_CYPHER_TO_PUBLIC = ("MATCH (n) WHERE n.id IN $ids "
                     "RETURN n.id AS id, coalesce(n.attack_id, n.id) AS pub, labels(n) AS labels")
_GREMLIN_TO_STORED = "g.V().has('id', within(ids)).values('id').dedup()"
_GREMLIN_TO_PUBLIC = ("g.V().has('id', within(ids)).project('id', 'label', 'tn', 'eid')"
                      ".by(values('id')).by(label())"
                      ".by(coalesce(values('taxonomy_name'), constant('')))"
                      ".by(coalesce(values('entry_id'), constant('')))")


def _lookup_limits(limits: dict[str, int], n: int) -> dict[str, int]:
    return {**limits, "max_result_rows": max(1000, 4 * n + 10)}


def to_stored(connector: Any, backend: str, public: list[str], limits: dict[str, int]) -> dict[str, list[str]]:
    """``{public id: [stored ids]}``; an id no node holds maps to ``[]``."""
    public = list(dict.fromkeys(str(p) for p in public if str(p)))
    if not public:
        return {}
    if backend == "cypher":
        rows = connector.run(_CYPHER_TO_STORED, {"ids": public}, _lookup_limits(limits, len(public)))
        out: dict[str, list[str]] = {p: [] for p in public}
        for r in rows:
            sid, pub = str(r.get("id")), str(r.get("pub"))
            for key in (pub, sid):
                if key in out and sid not in out[key]:
                    out[key].append(sid)
        return {k: sorted(v) for k, v in out.items()}
    from utils.specialists.gremlin.builder import _walk_candidate_ids

    cands = {p: list(dict.fromkeys([p, *_walk_candidate_ids([p])])) for p in public}
    every = sorted({c for cs in cands.values() for c in cs})
    rows = connector.run(_GREMLIN_TO_STORED, {"ids": every}, _lookup_limits(limits, len(every)))
    found = {str(r.get("_raw", r)) if isinstance(r, dict) else str(r) for r in rows}
    return {p: [c for c in cs if c in found] for p, cs in cands.items()}


def to_public(connector: Any, backend: str, stored: list[str], card: Any,
              limits: dict[str, int]) -> dict[str, tuple[str, str]]:
    """``{stored id: (public id, card label)}`` for the stored ids a result names."""
    stored = list(dict.fromkeys(str(s) for s in stored if s is not None and str(s)))
    if not stored:
        return {}
    labels = set(card.labels)
    out: dict[str, tuple[str, str]] = {}
    if backend == "cypher":
        for r in connector.run(_CYPHER_TO_PUBLIC, {"ids": stored}, _lookup_limits(limits, len(stored))):
            lab = next((x for x in r.get("labels") or [] if x in labels), "")
            out[str(r.get("id"))] = (str(r.get("pub")), lab)
        return out
    from utils.specialists.gremlin.normalizer import _expand_member_id, _taxonomy_public_id

    for r in connector.run(_GREMLIN_TO_PUBLIC, {"ids": stored}, _lookup_limits(limits, len(stored))):
        sid = str(r.get("id"))
        pub = _taxonomy_public_id({"taxonomy_name": r.get("tn"), "entry_id": r.get("eid")},
                                  _expand_member_id(sid)) if r.get("tn") else _expand_member_id(sid)
        out[sid] = (pub, str(r.get("label") or ""))
    return out


# --------------------------------------------------------------------------- #
# Compiling (the builders' dispatch)
# --------------------------------------------------------------------------- #


def draft(resolved: Any, backend: str) -> Any:
    """The ``QueryDraft`` of an algebra step whose anchors already hold stored ids.

    ``FromStep`` parameters are filled with ``resolved.task.seed_ids`` (stored ids,
    set by :func:`run_algebra`). The finishing contract rides in ``meta["algebra"]``.
    """
    from utils.specialists.validation import QueryDraft

    from .compiled import Backend
    from .ir import from_dict

    task = resolved.task
    spec = spec_of(task.signals.step)
    node = from_dict(spec["ir"])
    card = card_model(resolved.dataset)
    if backend == "cypher":
        from utils.specialists.cypher.compile import compile_cypher

        compiled = compile_cypher(node, Backend.cypher(card, row_cap=task.max_rows()))
    else:
        from utils.specialists.gremlin.compile import compile_gremlin

        compiled = compile_gremlin(node, Backend.gremlin(card, row_cap=task.max_rows()))
    params = dict(compiled.params)
    for name in (compiled.meta.get("inputs") or {}):
        params[name] = list(task.seed_ids)
    return QueryDraft(query=compiled.text, params=params, template="algebra", expected_nonempty=False,
                      meta={"algebra": {"kind": compiled.kind, "post": compiled.post, "meta": compiled.meta},
                            "op": spec.get("op")})


# --------------------------------------------------------------------------- #
# Running (the specialist's path)
# --------------------------------------------------------------------------- #


def run_algebra(specialist: Any, task: Any, resolved: Any, limits: dict[str, int], traces: list[Any]) -> Any:
    """Map ids, compile, run, finish, and hand the result over as evidence. Never raises."""
    from utils.specialists.contracts import EvaluatorTrace, SpecialistResult

    from .ir import from_dict, to_dict

    step = task.signals.step
    card = card_model(resolved.dataset)
    backend = backend_name(specialist.card)
    query = ""
    connected = False
    try:
        spec = spec_of(step)
        node = from_dict(spec["ir"])
        specialist.connector.connect()
        connected = True
        seeds = list(task.seed_ids) if _walk(node, FromStep) else []
        public = [i for a in _walk(node, Anchors) for i in a.ids] + seeds
        stored_of = to_stored(specialist.connector, backend, public, limits)
        back: dict[str, str] = {}

        def stored(ids: tuple[str, ...]) -> list[str]:
            out: list[str] = []
            for p in ids:
                hit = stored_of.get(p) or [p]  # unknown: passed through, reported as not found (S12)
                for s in hit:
                    back.setdefault(s, p)
                    if s not in out:
                        out.append(s)
            return out

        node2 = _map_anchors(node, lambda a: Anchors(tuple(stored(a.ids)), a.label))
        seeds2 = tuple(stored(tuple(seeds)))
        step2 = dataclasses.replace(step, algebra=json.dumps({**spec, "ir": to_dict(node2)}, sort_keys=True,
                                                               ensure_ascii=False))
        task2 = dataclasses.replace(task, seed_ids=seeds2 if seeds else task.seed_ids,
                                    signals=dataclasses.replace(task.signals, step=step2))
        resolved2 = dataclasses.replace(resolved, task=task2)
        builder = specialist.builder
        if not hasattr(builder, "_typed_step"):
            # A model-backed builder never compiles an algebra step (and must not
            # be asked to): the deterministic builder of this backend does.
            if backend == "cypher":
                from utils.specialists.cypher.builder import CypherQueryBuilder as _B
            else:
                from utils.specialists.gremlin.builder import GremlinQueryBuilder as _B
            builder = _B()
        d = builder.build(resolved2, None)
        if d.template != "algebra":
            raise ValueError(f"the builder did not compile the algebra step (template {d.template!r})")
        query = d.query
        traces.append(EvaluatorTrace("gate", ok=True, reasons=[], detail={
            "attempt": 1, "template": "algebra", "query": d.query, "injected": [],
            "note": "compiled by the operator algebra (validated against the card; read-only by construction)",
            "id_map": {p: stored_of.get(p, []) for p in dict.fromkeys(public)}}))
        rows = specialist.connector.run(d.query, d.params, limits)
        a = d.meta["algebra"]
        result = finish(rows, Compiled(d.query, d.params, a["kind"], a.get("post"), a.get("meta") or {}))
        traces.append(EvaluatorTrace("execute", ok=True, reasons=[], detail={"row_count": len(result.rows)}))
        names = _result_stored_ids(result)
        pub = to_public(specialist.connector, backend, names, card, limits)
        entry = contract_entry(task.sub_question_id, result, pub, back)
        records = _records(specialist.card, d.query, result, pub, task.max_rows())
        traces.append(EvaluatorTrace(TRACE, ok=True, reasons=[], detail={
            "result": entry, "op": spec.get("op"), "ir": spec.get("ir"), **_describe_op(node)}))
        summary = specialist.normalizer.summarize(records, resolved) if records else claim_text(
            {"result": entry, "op": spec.get("op"), **_describe_op(node)})
        return SpecialistResult(task=task, query=d.query, records=records, summary=summary, traces=traces,
                                ok=True, partial=not result.complete)
    except Exception as exc:  # noqa: BLE001 - a specialist reports failures, never raises
        reason = f"{type(exc).__name__}: {exc}"
        traces.append(EvaluatorTrace(TRACE, ok=False, reasons=[reason], detail={
            "result": {"step": task.sub_question_id, "kind": None, "value": None, "ids": [], "rows": [],
                       "total": None, "complete": False, "info": {"error": reason}}}))
        return SpecialistResult(task=task, query=query, traces=traces, ok=False, partial=True, error=reason)
    finally:
        if connected:
            try:
                specialist.connector.close()
            except Exception:  # noqa: BLE001
                pass


def _describe_op(node: Any) -> dict[str, Any]:
    """The few facts of the tree the sentence needs (fn, property, order)."""
    from .aggregate import Aggregate
    from .groupby import GroupBy
    from .rank import Rank

    if isinstance(node, Aggregate):
        return {"fn": node.fn, "property": node.prop}
    if isinstance(node, GroupBy):
        return {"fn": node.fn, "property": node.prop, "order": node.order}
    if isinstance(node, Rank):
        return {"property": node.prop, "order": node.order,
                "by_path": [h.relation for h in node.by_walk or ()]}
    return {}


def _result_stored_ids(result: Result) -> list[str]:
    out: list[str] = []
    for r in result.rows:
        if r.get("id") is not None:
            out.append(str(r["id"]))
        for x in (r.get("path") or [])[0::2]:
            out.append(str(x))
    return list(dict.fromkeys(out))


def _pub(pub: dict[str, tuple[str, str]], back: dict[str, str], sid: Any) -> str:
    s = str(sid)
    if s in pub:
        return pub[s][0]
    return back.get(s, s)


def contract_entry(step_id: str, result: Result, pub: dict[str, tuple[str, str]],
                   back: dict[str, str]) -> dict[str, Any]:
    """The machine-readable result: the contract ``run_meta.algebra_results`` holds."""
    rows: list[dict[str, Any]] = []
    ids: set[str] = set()
    for r in result.rows:
        row = dict(r)
        if row.get("id") is not None:
            row["id"] = _pub(pub, back, row["id"])
            ids.add(row["id"])
        if isinstance(row.get("path"), list):
            row["path"] = [_pub(pub, back, x) if i % 2 == 0 else x for i, x in enumerate(row["path"])]
            ids.update(str(x) for x in row["path"][0::2])
        rows.append(row)
    info = dict(result.info)
    if "anchor_not_found" in info:
        info["anchor_not_found"] = [back.get(str(x), str(x)) for x in info["anchor_not_found"]]
        info["anchor_not_found"] = list(dict.fromkeys(info["anchor_not_found"]))
    value = result.value
    return json.loads(json.dumps({
        "step": step_id, "kind": result.kind, "value": value, "ids": sorted(ids),
        "rows": rows[:CONTRACT_ROWS], "total": result.total, "complete": bool(result.complete), "info": info,
    }, default=str))


def _records(card: Any, query: str, result: Result, pub: dict[str, tuple[str, str]], cap: int) -> list[Any]:
    """Evidence records: one per result node, or one result record for a scalar/verify answer."""
    from utils.specialists.evidence import emit_record

    scheme = str((getattr(card, "provenance", None) or {}).get("id_scheme") or "id")
    out: list[Any] = []
    if result.kind in ("count", "aggregate", "verify"):
        return [emit_record(card=card, query=query, record_id=f"algebra:{result.kind}", primary_id="",
                            id_scheme=scheme, label="Result", name=f"{result.kind} result",
                            properties={"value": result.value, **({k: result.info[k] for k in
                                                                    ("exists", "anchor_not_found")
                                                                    if k in result.info})})]
    seen: set[str] = set()
    for r in result.rows:
        sids = [r["id"]] if r.get("id") is not None else list((r.get("path") or [])[0::2])
        for sid in sids:
            sid = str(sid)
            if sid in seen or sid not in pub:
                continue
            seen.add(sid)
            p, lab = pub[sid]
            props: dict[str, Any] = {}
            if result.kind in ("rank", "groupby", "values"):
                props["value"] = r.get("value")
            for k, v in r.items():
                if k not in ("id", "name", "value", "path", "rels", "properties") and v is not None:
                    props[k] = v
            out.append(emit_record(card=card, query=query, record_id=sid, primary_id=p, id_scheme=scheme,
                                   label=lab or "Entity", name=str(r.get("name") or p), properties=props,
                                   join_values=(p,) if _TECHNIQUE_ID_RE.match(p) else ()))
            if len(out) >= cap:
                return out
    return out


# --------------------------------------------------------------------------- #
# The answer: one plain sentence, and the run metadata
# --------------------------------------------------------------------------- #


def trace_of(result: Any) -> dict[str, Any] | None:
    """The ``algebra`` trace detail of a specialist result, or ``None``."""
    for t in getattr(result, "traces", None) or []:
        if getattr(t, "step", "") == TRACE:
            return dict(t.detail or {})
    return None


def _items(rows: list[dict[str, Any]], with_value: bool = True) -> str:
    shown = [f"{r.get('name') or r.get('id')} ({r.get('id')})" + (f": {r.get('value')}" if with_value else "")
             for r in rows[:SENTENCE_ITEMS]]
    more = len(rows) - len(shown)
    return "; ".join(shown) + (f"; and {more} more" if more > 0 else "")


def claim_text(detail: dict[str, Any]) -> str:
    """The plain sentence stating an algebra result (deterministic; no model)."""
    e = detail.get("result") or {}
    kind, value, rows = e.get("kind"), e.get("value"), e.get("rows") or []
    missing = (e.get("info") or {}).get("anchor_not_found") or []
    lost = f" Not in the graph: {', '.join(missing)}." if missing else ""
    if kind == "count" and detail.get("fn") == "count_values":
        return f"There are {value} distinct values of {detail.get('property')} (exact).{lost}"
    if kind == "count":
        return f"The count is {value} (distinct entities, exact).{lost}"
    if kind == "aggregate":
        fn, prop = detail.get("fn") or "aggregate", detail.get("property")
        what = f"{fn} of {prop}" if prop else fn
        return f"The {what} is {value if value is not None else 'undefined (no values)'}.{lost}"
    if kind == "verify":
        if missing:
            return f"The link cannot be checked:{lost}"
        if value:
            rels = sorted({f"{r.get('relation')} ({r.get('direction')})" for r in rows})
            return f"Yes: they are linked by {', '.join(rels)}."
        return "No: no link between them was found."
    if kind == "rank":
        key = detail.get("property") or ("the number of " + "/".join(detail.get("by_path") or []) + " links")
        return (f"Ranked by {key} ({detail.get('order') or 'desc'}; ties at the cut kept): "
                f"{_items(rows)}.{lost}")
    if kind == "groupby":
        fn, prop = detail.get("fn") or "count", detail.get("property")
        what = f"{fn} of {prop}" if prop else fn
        return f"{e.get('total')} member(s), with their {what}: {_items(rows)}.{lost}"
    if kind == "shortest":
        if not rows:
            return f"No path was found within the depth cap.{lost}"
        paths = [" -> ".join(str(x) for x in r.get("path") or []) for r in rows[:SENTENCE_ITEMS]]
        return f"{e.get('total')} shortest path(s): " + "; ".join(paths) + "." + lost
    if kind in ("nodes", "describe", "values"):
        tail = "" if e.get("complete") else " (more exist than are listed)"
        return f"{e.get('total')} entit{'y' if e.get('total') == 1 else 'ies'} match{tail}.{lost}"
    return ""


def algebra_results(evidence: Any) -> list[dict[str, Any]]:
    """Every algebra result of a run, in evidence order: ``run_meta.algebra_results``."""
    out = []
    for r in getattr(evidence, "results", None) or []:
        d = trace_of(r)
        if d is not None and isinstance(d.get("result"), dict):
            out.append(d["result"])
    return out


__all__ = ["CONTRACT_ROWS", "TRACE", "algebra_results", "backend_name", "card_model", "claim_text",
           "contract_entry", "draft", "run_algebra", "to_public", "to_stored", "trace_of"]
