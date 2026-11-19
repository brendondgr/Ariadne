#!/usr/bin/env python3
"""The planner's typed mode (Era 2 Step 8, EXP-2026-11-015 build item 6).

The English drafter (:mod:`utils.planner.llm_drafter`) writes sub-questions in
words and the builders read signals derived from those words. The typed mode
writes the request itself, against the tool catalog generated from each card
(:mod:`utils.agent.catalog`):

1. The model is shown the catalog -- ``lazy``: names only (``Catalog.summary``);
   ``full``: the whole card (``Catalog.render``) -- and may call
   ``find_schema``, ``describe`` and ``resolve_entity`` (the catalog's own
   tools, :class:`utils.agent.tools.Tools`, no store attached), **at most four
   calls in total**. It then emits one typed plan as JSON.
2. Every step is validated against the catalog's option rules and coerced
   (:mod:`utils.agent.coerce`; every fix recorded with ``filled_by``). A step
   that cannot be repaired is refused with the envelope of
   :mod:`utils.agent.errors`.
3. Refusals get exactly **one** repair turn carrying the envelopes. A step still
   refused after it is dropped, counted, and written into the plan's
   ``unsupported`` parts (it becomes an abstention).
4. The plan is an ordinary :class:`~utils.planner.schema.Plan` whose
   sub-questions have ``text == ""`` and a ``step``; the specialists build
   their signals from the step alone (``utils.specialists.signals.step_signals``)
   and the builders execute it (``_typed_step``).

This is a single plan, not a loop: the loop is Step 11. With up to four catalog
calls, one emission and one repair it is "a typed plan with up to six planner
turns".

Nothing here names a graph, a label or a relation: everything comes from the
cards, the catalogs and the schema registry's learned identifier schemes.
"""

from __future__ import annotations

import json
import logging
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .cards import SourceCardView
from .discovery import LiveSourceView
from .join_keys import CANONICAL_JOIN_KEYS, resolve_join_key
from .llm_drafter import DrafterUnavailable, extract_json_object
from .schema import JoinDeclaration, Limits, Plan, SubQuestion, UnsupportedPart

if TYPE_CHECKING:
    from .intent import IntentClassification

logger = logging.getLogger("ariadne.planner.typed")

MODES = ("lazy", "full")
#: Catalog tools the planner may call before it emits.
PLANNER_TOOLS = ("find_schema", "describe", "resolve_entity")
MAX_CATALOG_CALLS = 4
#: Model turns at most: four tool turns, the emission, one repair.
MAX_TURNS = MAX_CATALOG_CALLS + 2
STEP_KINDS = ("expand", "count", "describe", "scan", "common")


# --------------------------------------------------------------------------- #
# Catalogs (one per card, built once per process)
# --------------------------------------------------------------------------- #

_CATALOGS: dict[tuple[str, ...], dict[str, Any]] = {}
_CAT_LOCK = threading.Lock()


def catalogs_for(cards: dict[str, SourceCardView]) -> dict[str, Any]:
    """``{dataset: Catalog}`` for these cards (cached by dataset names)."""
    from utils.agent.catalog import catalog_for

    key = tuple(sorted(cards))
    with _CAT_LOCK:
        if key not in _CATALOGS:
            _CATALOGS[key] = {ds: catalog_for(cards[ds]) for ds in sorted(cards)}
        return _CATALOGS[key]


# --------------------------------------------------------------------------- #
# The prompt
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """\
You are the planner of a graph question-answering system. You do not answer the \
question. You write ONE typed plan, as JSON, that a deterministic engine executes \
exactly as written against the graphs below. The engine reads no English: what the \
plan states is all it knows.

A plan is a list of steps. Each step names one graph and asks for one set:
- "expand": the entities reached from an anchor over a path of hops;
- "count": the same set, when the question asks how many;
- "describe": the anchor entity itself and its properties (no path);
- "scan": every entity of one label, only when the question asks for all of them (no \
anchor; give the label as "anchor_label");
- "common": the entities linked to EVERY one of two or more anchors (give the ids as a \
list: "anchor": {"id": ["<id>", "<id>"]}; no path).

An anchor is an entity: give its "id" when the question writes one, otherwise its \
exact "name" and its "label". A hop is one relation of the graph, its direction \
("out": the anchor side is the relation's subject; "in": the anchor side is its \
object) and the label the hop reaches (omit "target_label" to keep every label the \
relation reaches there). "depth" (default 1) repeats a single hop over \
a relation that links a label to itself (a hierarchy). "filter" keeps only the last \
label's members whose property equals a value.

Tools: find_schema, describe and resolve_entity look things up in the catalog \
(relations with their directions and plain readings, properties, entity ids). You may \
make at most 4 tool calls in total. Then reply with the plan JSON only.

Rules:
- Use only labels, relations and properties of the named graph. Never invent one.
- A step on one graph may start from an earlier step on another graph through a \
declared join key: "anchor": {"from_step": "<id>", "label": "<Label>"}.
- An entity id of one graph may anchor a step on another graph that a declared join key \
links to it; give the label it has there as "anchor_label". The engine bridges it.
- On one graph, chain hops in one step's path rather than starting a step from another.
- When the question writes an entity id, anchor on that id even if resolve_entity cannot \
find it. The engine then answers that the entity is not in the graph, which is the right \
answer. Never put a scan in place of an anchor you could not find.
- If part of the question cannot be expressed this way, put it in "unsupported" with \
a reason. Do not answer a different question instead.

Reply with exactly this JSON shape, nothing else:
{"steps": [{"id": "q1", "graph": "<graph>", "kind": "expand|count|describe|scan",
            "anchor": {"id": "<entity id>"} or {"name": "<entity name>", "label": "<Label>"},
            "anchor_label": "<Label>",
            "path": [{"relation": "<relation>", "direction": "out|in", "target_label": "<Label> (omit for every label it reaches)"}],
            "depth": 1,
            "filter": null or {"property": "<property>", "value": "<value>"}}],
 "unsupported": [{"description": "<part>", "reason": "<why>"}],
 "assumptions": ["<any reading you chose>"]}
"""


def catalog_block(catalogs: dict[str, Any], mode: str) -> str:
    """The catalog part of the prompt: names only (``lazy``) or the whole card (``full``)."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    parts = []
    for ds in sorted(catalogs):
        cat = catalogs[ds]
        parts.append(cat.summary() if mode == "lazy" else cat.render())
    keys = "\n".join(f"- {k.name}: {k.description}" for k in CANONICAL_JOIN_KEYS)
    return "GRAPHS:\n" + "\n\n".join(parts) + "\n\nDECLARED JOIN KEYS:\n" + (keys or "(none)")


def build_messages(request: str, catalogs: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": catalog_block(catalogs, mode) + f"\n\nQUESTION:\n{request}"},
    ]


def tool_specs(catalogs: dict[str, Any]) -> list[dict[str, Any]]:
    """``find_schema``, ``describe`` and ``resolve_entity`` over every graph.

    Each takes an optional ``graph``; without it the call runs on every graph
    and the results are tagged with the graph they came from.
    """
    graphs = sorted(catalogs)
    labels = sorted({lab for c in catalogs.values() for lab in c.labels()})
    first = catalogs[graphs[0]]
    out = []
    for spec in first.specs("names"):
        fn = spec["function"]
        if fn["name"] not in PLANNER_TOOLS:
            continue
        params = json.loads(json.dumps(fn["parameters"]))
        params.pop("x-options", None)
        if "label" in params["properties"]:
            params["properties"]["label"] = {"type": "string", "enum": labels}
        params["properties"]["graph"] = {"type": "string", "enum": graphs,
                                         "description": "the graph to look in (default: every graph)"}
        out.append({"type": "function", "function": {"name": fn["name"], "description": fn["description"],
                                                     "parameters": params}})
    return out


# --------------------------------------------------------------------------- #
# Validation of one step against the catalog
# --------------------------------------------------------------------------- #


@dataclass
class StepCheck:
    """One step after validation: a clean step, or the refusal envelopes."""

    id: str
    graph: str = ""
    step: Any = None                  # utils.specialists.signals.TypedStep
    from_step: str | None = None
    join_key: str | None = None
    refusals: list[dict[str, Any]] = field(default_factory=list)
    fixes: list[dict[str, Any]] = field(default_factory=list)
    raw: Any = None

    @property
    def ok(self) -> bool:
        return self.step is not None and not self.refusals


class PlanContext:
    """The catalogs, their tools (no store attached) and the identifier lookup of one draft."""

    def __init__(self, cards: dict[str, SourceCardView], catalogs: dict[str, Any], workdir: Path,
                 live: set[str] | None = None, request: str = "") -> None:
        from utils.agent.handles import HandleStore
        from utils.agent.tools import Tools

        self.cards = cards
        self.catalogs = {ds: c for ds, c in catalogs.items() if live is None or ds in live}
        run_id = uuid.uuid4().hex[:12]
        self.handles = HandleStore(workdir / "handles.db", run_id)
        self.tools = {ds: Tools(cat, None, self.handles) for ds, cat in self.catalogs.items()}
        self.request = request
        #: id-shaped ``resolve_entity`` texts that no graph holds (set by ``_run_tool``)
        self.failed_lookups: list[str] = []
        #: ``(graph, id, label, text)`` of every entity ``resolve_entity`` found during this draft
        self.found_lookups: list[tuple[str, str, str, str]] = []
        self._written: list[str] | None = None

    def close(self) -> None:
        self.handles.close()

    # -- identifiers ---------------------------------------------------------

    def known_id(self, graph: str, value: str) -> tuple[str, str] | None:
        """``(id as stored, label)`` when the graph's entity index holds ``value``.

        Exact first, then ignoring case and separators (``ab12`` -> ``AB12``,
        ``XY 7`` -> ``XY-7``). The index is the name index the resolver
        already uses, so this is an existence check, not a format check.
        """
        idx = _id_index(graph)
        if value in idx.get("exact", {}):
            return value, idx["exact"][value]
        key = _id_key(value)
        return idx.get("loose", {}).get(key)

    def id_labels(self, graph: str, value: str) -> list[str]:
        """Labels of ``graph`` that hold ``value``: the entity index, else the learned id scheme."""
        hit = self.known_id(graph, value)
        if hit is not None:
            return [hit[1]]
        try:
            from utils.specialists.gremlin.builder import _walk_candidate_ids
            from utils.specialists.schema import get_registry

            schema = get_registry().dataset(graph)
        except Exception:  # noqa: BLE001 — no registry: nothing can be checked
            return []
        if schema is None:
            return []
        found: set[str] = set()
        for cand in [value, *_walk_candidate_ids([value])]:
            found |= set(schema.labels_for_id(cand))
        return sorted(found)

    def written_ids(self) -> list[str]:
        """Tokens of the request that have the form of an entity id of a live graph.

        The planner reads the question (the specialists do not); this is only
        used to refuse a whole-label scan that would stand in for a named entity.
        """
        if self._written is None:
            import re

            found: list[str] = []
            for tok in re.findall(r"[A-Za-z][A-Za-z0-9]*(?:[-:][A-Za-z0-9]+)*(?:\.\d+)?", self.request or ""):
                if not any(ch.isdigit() for ch in tok) or tok in found:
                    continue
                if any(self.id_labels(g, tok) for g in self.catalogs):
                    found.append(tok)
            self._written = found
        return self._written

    def foreign_id(self, graph: str, value: str) -> str | None:
        """Another graph joined to ``graph`` whose ids admit ``value`` (a bridge anchor)."""
        for other in sorted(self.catalogs):
            if other == graph or other not in self.cards or graph not in self.cards:
                continue
            if self.id_labels(other, value) and resolve_join_key(self.cards[graph], self.cards[other]):
                return other
        return None


_ID_INDEX: dict[str, dict[str, dict[str, Any]]] = {}


def _id_key(value: str) -> str:
    import re

    return re.sub(r"[^0-9A-Z.]+", "", str(value).upper())


def _id_index(graph: str) -> dict[str, dict[str, Any]]:
    """The entity ids of ``graph``'s name index, exact and loose (cached)."""
    with _CAT_LOCK:
        if graph not in _ID_INDEX:
            exact: dict[str, str] = {}
            loose: dict[str, tuple[str, str] | None] = {}
            try:
                from utils.specialists.schema.namesearch import index_for

                for eid, label, _name, _toks in index_for(graph)._docs:  # noqa: SLF001
                    exact[eid] = label
                    k = _id_key(eid)
                    loose[k] = None if k in loose and loose[k] != (eid, label) else (eid, label)
            except Exception:  # noqa: BLE001 — no index: only the id schemes check
                pass
            _ID_INDEX[graph] = {"exact": exact, "loose": {k: v for k, v in loose.items() if v}}
        return _ID_INDEX[graph]


def _observed_values(graph: str, label: str, prop: str) -> list[str]:
    """Values the schema registry observed for ``label.prop`` (a sample; may be empty)."""
    try:
        from utils.specialists.schema import get_registry

        vocab = getattr(get_registry().dataset(graph), "label_value_vocabulary", None) or {}
        return sorted(str(v) for v in (vocab.get(label) or {}).get(prop) or ())
    except Exception:  # noqa: BLE001
        return []


def _env(code: str, detail: str, field_: str, got: Any, options: list[str], what: str | None = None,
         hint: str = "") -> dict[str, Any]:
    from utils.agent import errors as E

    opts = [str(o) for o in options] or [field_]
    return E.choice(code, detail, field_, got, opts, what=what, hint=hint)


def check_step(raw: Any, index: int, ctx: PlanContext, earlier: dict[str, StepCheck]) -> StepCheck:
    """Validate and coerce one raw step. Never raises; refusals are envelopes."""
    from utils.agent import errors as E
    from utils.agent.coerce import Ambiguous, Coercions, NoMatch, coerce_enum, coerce_int, coerce_name
    from utils.agent.tools import Refused
    from utils.specialists.signals import TypedHop, TypedStep

    log = Coercions()
    sid = str((raw or {}).get("id") or f"q{index + 1}") if isinstance(raw, dict) else f"q{index + 1}"
    out = StepCheck(id=sid, raw=raw)

    def refuse(env: dict[str, Any]) -> StepCheck:
        out.refusals.append(env)
        out.fixes = list(log.fixes)
        return out

    if not isinstance(raw, dict):
        return refuse(E.refusal("invalid_request", f"step {sid} is not a JSON object",
                                "write each step as an object with id, graph, kind, anchor and path",
                                [E.problem("step", raw, ["id", "graph", "kind", "anchor", "path"])]))
    graphs = sorted(ctx.catalogs)
    graph_raw = raw.get("graph") or raw.get("source")
    if graph_raw is None and len(graphs) == 1:
        graph_raw = graphs[0]
        log.add("graph", None, graph_raw, "only_graph")
    try:
        graph = coerce_name(graph_raw, graphs, "graph", log)
    except (NoMatch, Ambiguous):
        return refuse(_env("not_in_card", f"step {sid}: graph {graph_raw!r} is not a live graph", "graph",
                           graph_raw, graphs, what="graph"))
    out.graph = graph
    cat, tools = ctx.catalogs[graph], ctx.tools[graph]

    kind_raw = raw.get("kind") or "expand"
    try:
        kind = coerce_enum(kind_raw, STEP_KINDS, "kind", log)
    except (NoMatch, Ambiguous):
        return refuse(_env("invalid_request", f"step {sid}: kind {kind_raw!r} is not a step kind", "kind",
                           kind_raw, list(STEP_KINDS), what="kind"))

    anchor = raw.get("anchor")
    if isinstance(anchor, str):
        log.add("anchor", anchor, {"id": anchor}, "single_from_text")
        anchor = {"id": anchor}
    anchor = anchor if isinstance(anchor, dict) else {}
    label_raw = raw.get("anchor_label") or anchor.get("label")

    def _label(value: Any, field_: str) -> str:
        try:
            return coerce_name(value, cat.labels(), field_, log)
        except (NoMatch, Ambiguous):
            raise Refused(_env("not_in_card", f"step {sid}: {field_} {value!r} is not a label of {graph}",
                               field_, value, cat.labels(), what="label")) from None

    try:
        # -- scan: one label, no anchor -------------------------------------
        if kind == "scan":
            target = label_raw
            path = raw.get("path") or []
            if not target and isinstance(path, list) and path and isinstance(path[-1], dict):
                target = path[-1].get("target_label")
            if not target:
                raise Refused(_env("invalid_request", f"step {sid}: a scan needs the label to list",
                                   "anchor_label", None, cat.labels(), what="anchor_label"))
            lab = _label(target, "anchor_label")
            named = ctx.written_ids()
            if named or ctx.failed_lookups:
                what = named or ctx.failed_lookups
                raise Refused(E.refusal(
                    "invalid_request",
                    f"step {sid}: a scan lists every {lab}, but the question names {', '.join(what[:3])}",
                    "anchor the step on the named entity instead: {\"id\": \"" + what[0] + "\"}. An id that "
                    "is not in the graph is answered as not found; an id of another graph is bridged through "
                    "the join key (give this graph's label as anchor_label)",
                    [E.problem("kind", "scan", ["expand", "describe", "count"])]))
            out.step = TypedStep(kind="scan", anchor_label=lab)
            out.fixes = list(log.fixes)
            return out

        # -- the anchor -----------------------------------------------------
        ids: list[str] = []
        anchor_label = ""
        from_step = anchor.get("from_step") or raw.get("from_step")
        if from_step:
            prod = earlier.get(str(from_step))
            if prod is None or not prod.ok:
                raise Refused(_env("invalid_request", f"step {sid}: from_step {from_step!r} is not an earlier "
                                   "accepted step", "from_step", from_step,
                                   [k for k, v in earlier.items() if v.ok] or ["an anchor id or name"],
                                   what="from_step"))
            if prod.graph == graph:
                fix = (f"on one graph, add this step's hops to the path of step {from_step} (a path may have "
                       "several hops) instead of starting a new step from it")
                bridge = _bridge_hint(ctx, graph, label_raw, [v for v in earlier.values() if v.ok])
                if bridge:
                    fix += ". " + bridge
                raise Refused(E.refusal(
                    "invalid_request", f"step {sid}: from_step {from_step!r} is on the same graph", fix,
                    [E.problem("from_step", from_step, [f"{from_step}.path"])]))
            key = resolve_join_key(ctx.cards[prod.graph], ctx.cards[graph])
            producer_ok = key is not None and any(e.dataset == prod.graph and e.produces for e in key.endpoints)
            if not producer_ok:
                bridge = _bridge_hint(ctx, graph, label_raw, [prod, *(v for v in earlier.values() if v.ok)])
                raise Refused(E.refusal(
                    "invalid_request",
                    f"step {sid}: no declared join key carries values from {prod.graph} to {graph}",
                    bridge or ("anchor this step on entity ids directly (an id of the other graph is bridged "
                               "through the join key), or use one graph"),
                    [E.problem("from_step", from_step, ["anchor.id"])]))
            out.from_step, out.join_key = str(from_step), key.name
            if not label_raw:
                raise Refused(_env("invalid_request", f"step {sid}: from_step needs the label its values are",
                                   "anchor.label", None, cat.labels(), what="anchor.label"))
            anchor_label = _label(label_raw, "anchor_label")
        elif anchor.get("id") not in (None, "", []):
            raw_ids = anchor["id"] if isinstance(anchor["id"], list) else [anchor["id"]]
            labels_seen: set[str] = set()
            for rid in raw_ids:
                rid_s = str(rid).strip()
                hit = ctx.known_id(graph, rid_s)
                if hit is not None and hit[0] != rid_s:
                    log.add("anchor.id", rid_s, hit[0], "case_separator")
                    rid_s = hit[0]
                labs = ctx.id_labels(graph, rid_s)
                if not labs:
                    other = ctx.foreign_id(graph, rid_s)
                    if other is not None:
                        key = resolve_join_key(ctx.cards[graph], ctx.cards[other])
                        out.join_key = key.name if key else None
                        ids.append(rid_s)
                        continue
                    raise Refused(E.refusal(
                        "not_in_card", f"step {sid}: {rid_s!r} is not an entity id of {graph}",
                        "call resolve_entity with the entity's name to get its id, or anchor by "
                        "{\"name\": ..., \"label\": ...}; labels: " + E.name_options(cat.labels()),
                        [E.problem("anchor.id", rid_s, ["resolve_entity"])]))
                ids.append(rid_s)
                labels_seen |= set(labs)
            if label_raw:
                anchor_label = _label(label_raw, "anchor_label")
                if labels_seen and anchor_label not in labels_seen:
                    if len(labels_seen) == 1:
                        fixed = next(iter(labels_seen))
                        log.add("anchor_label", anchor_label, fixed, "id_scheme")
                        anchor_label = fixed
                    else:
                        raise Refused(_env("invalid_request", f"step {sid}: the anchor ids are "
                                           f"{sorted(labels_seen)}, not {anchor_label}", "anchor_label",
                                           anchor_label, sorted(labels_seen), what="anchor_label"))
            elif len(labels_seen) == 1:
                anchor_label = next(iter(labels_seen))
                log.add("anchor_label", None, anchor_label, "id_scheme")
            elif kind == "common" and labels_seen:
                anchor_label = sorted(labels_seen)[0]
            elif out.join_key and not labels_seen:
                raise Refused(_env("invalid_request", f"step {sid}: the anchor ids belong to another graph; "
                                   f"name the {graph} label the path starts from", "anchor_label", None,
                                   cat.labels(), what="anchor_label"))
            else:
                raise Refused(_env("invalid_request", f"step {sid}: the anchor ids fit several labels",
                                   "anchor_label", None, sorted(labels_seen), what="anchor_label"))
        elif anchor.get("name"):
            args: dict[str, Any] = {"text": str(anchor["name"])}
            if label_raw:
                args["label"] = _label(label_raw, "anchor_label")
            # Run directly, not through ``Tools.call``: the model may already have
            # asked resolve_entity the same thing, and a repeat refusal is not
            # what a validation of the plan means.
            got = tools._run_resolve_entity(tools.validate("resolve_entity", args))  # noqa: SLF001
            if not got.get("ok"):
                raise Refused(got)
            if got.get("status") != "found":
                cands = got.get("candidates") or []
                raise Refused(E.refusal(
                    "ambiguous_anchor", f"step {sid}: no confident match for {anchor['name']!r}",
                    "anchor by one candidate's id: " + E.name_options(
                        f"{c['id']} {c['name']} ({c['label']})" for c in cands),
                    [E.problem("anchor.name", anchor["name"], [c["id"] for c in cands])], candidates=cands))
            ids = [str(i) for i in got.get("ids") or []]
            anchor_label = str(got.get("kind") or args.get("label") or "")
            if anchor_label not in cat.labels():
                anchor_label = _label(anchor_label or label_raw, "anchor_label")
            log.add("anchor", {"name": anchor["name"]}, {"id": ids}, "resolve_entity")
        else:
            raise Refused(E.refusal("invalid_request", f"step {sid}: the step has no anchor",
                                    "give anchor {\"id\": ...} (the id the question writes, even if "
                                    "resolve_entity did not find it) or {\"name\": ..., \"label\": ...}",
                                    [E.problem("anchor", raw.get("anchor"), ["id", "name", "from_step"])]))

        # -- common: what every anchor links to --------------------------------
        if kind == "common":
            if len(ids) < 2:
                raise Refused(_env("invalid_request", f"step {sid}: \"common\" needs two or more anchor ids",
                                   "anchor.id", anchor.get("id"), ["a list of two or more ids"],
                                   what="anchor.id", hint="or use kind \"expand\" from one anchor"))
            out.step = TypedStep(kind="common", anchor_label=anchor_label, anchor_ids=tuple(ids))
            out.fixes = list(log.fixes)
            return out

        # -- describe: the anchor only ----------------------------------------
        if kind == "describe":
            out.step = TypedStep(kind="describe", anchor_label=anchor_label, anchor_ids=tuple(ids))
            out.fixes = list(log.fixes)
            return out

        # -- the path: every hop through the catalog's own expand check -------
        path = raw.get("path")
        if path is None and raw.get("relation"):
            path = [{"relation": raw.get("relation"), "direction": raw.get("direction"),
                     "target_label": raw.get("target_label")}]
            log.add("path", None, "from relation/direction/target_label", "single_hop")
        if isinstance(path, dict):
            path = [path]
        if not isinstance(path, list) or not path:
            opts = [f"{o.relation} {o.direction} -> {o.target}" for o in cat.options(anchor_label)]
            raise Refused(_env("invalid_request", f"step {sid}: an {kind} step needs a path", "path", path,
                               opts or cat.relations(), what="a hop from " + anchor_label,
                               hint="or use kind \"describe\" for the anchor itself"))
        depth_raw = raw.get("depth", 1)
        try:
            depth = coerce_int(depth_raw if depth_raw is not None else 1, "depth", log)
        except NoMatch:
            raise Refused(_env("invalid_request", f"step {sid}: depth {depth_raw!r} is not an integer", "depth",
                               depth_raw, [str(i) for i in range(1, cat.model.max_depth + 1)],
                               what="depth")) from None
        if depth > 1 and len(path) > 1:
            raise Refused(_env("invalid_request", f"step {sid}: depth repeats a single hop; this path has "
                               f"{len(path)}", "depth", depth, ["1"], what="depth",
                               hint="or give a one-hop path over a repeating relation"))
        hops: list[Any] = []
        here = anchor_label
        for j, hop in enumerate(path):
            if not isinstance(hop, dict):
                raise Refused(_env("invalid_request", f"step {sid}: hop {j + 1} is not an object", "path",
                                   hop, ["relation", "direction", "target_label"], what="hop fields"))
            handle = ctx.handles.put(here, ids if j == 0 and ids else ["_"]).handle
            args = {"from": handle, "relation": hop.get("relation")}
            if hop.get("direction") is not None:
                args["direction"] = hop.get("direction")
            if hop.get("target_label") is not None:
                args["to_label"] = hop.get("target_label")
            if len(path) == 1:
                args["depth"] = depth
            try:
                call = tools.validate("expand", args)
            except Refused as r:
                env = dict(r.envelope)
                env["detail"] = f"step {sid}, hop {j + 1}: {env.get('detail')}"
                raise Refused(env) from None
            for f in call.log.fixes:
                log.add(f"path[{j}].{f['field']}", f["from"], f["to"], f["filled_by"])
            to = call.args["to_label"]
            if to is None:
                ends = call.args.get("_targets") or []
                if len(ends) == 1:
                    to = ends[0]
                    log.add(f"path[{j}].target_label", None, to, "option_rules")
                else:
                    # No label named and the hop reaches several: keep them all
                    # (the edge decides), as the generic engine does. Recorded.
                    to = ""
                    log.add(f"path[{j}].target_label", None, ends, "all_targets")
            hops.append(TypedHop(call.args["relation"], call.args["direction"], to))
            here = to
        flt = raw.get("filter")
        filt = None
        if isinstance(flt, dict) and flt.get("property") not in (None, ""):
            props = cat.label_properties(here)
            try:
                prop = coerce_name(flt.get("property"), sorted(props), "filter.property", log)
            except (NoMatch, Ambiguous):
                raise Refused(_env("not_in_card", f"step {sid}: {flt.get('property')!r} is not a property "
                                   f"of {here}", "filter.property", flt.get("property"),
                                   sorted(props) or ["no filter"], what=f"a property of {here}")) from None
            if flt.get("value") in (None, ""):
                raise Refused(_env("invalid_request", f"step {sid}: the filter needs a value", "filter.value",
                                   None, [f"a {props[prop].vtype} value"], what="filter.value"))
            value = str(flt.get("value"))
            vocab = _observed_values(graph, here, prop)
            if vocab and value not in vocab:
                try:
                    value = coerce_name(value, vocab, "filter.value", log)
                except (NoMatch, Ambiguous):
                    pass  # the observed values are a sample: an unseen value is not refused
            filt = (prop, value)
        out.step = TypedStep(kind=kind, anchor_label=anchor_label, anchor_ids=tuple(ids), hops=tuple(hops),
                             depth=depth if len(hops) == 1 else 1, filter=filt)
        out.fixes = list(log.fixes)
        return out
    except Refused as r:
        return refuse(r.envelope)


def check_plan(data: Any, ctx: PlanContext) -> tuple[list[StepCheck], list[str]]:
    """Validate every step in order. Returns the checks and plan-level problems."""
    problems: list[str] = []
    if not isinstance(data, dict):
        return [], ["the reply is not one JSON object"]
    steps = data.get("steps")
    if steps is None and isinstance(data.get("sub_questions"), list):
        steps = data["sub_questions"]
        problems.append("steps were written as sub_questions")
    if not isinstance(steps, list):
        steps = [] if steps is None else [steps]
    checks: list[StepCheck] = []
    earlier: dict[str, StepCheck] = {}
    for i, raw in enumerate(steps):
        c = check_step(raw, i, ctx, earlier)
        if c.id in earlier:
            c.id = f"{c.id}_{i + 1}"
        earlier[c.id] = c
        checks.append(c)
    _refuse_unlinked_scans(checks, ctx)
    return checks, problems


def _bridge_hint(ctx: PlanContext, graph: str, label: Any, steps: list[StepCheck]) -> str:
    """How to carry the entity an anchored step on another, joined graph found into ``graph``.

    Empty when no such step exists. The id form is the one the engine bridges
    (an id of the other graph plus this graph's label as ``anchor_label``).
    """
    for a in steps:
        if a.graph == graph or a.step is None or not a.step.anchor_ids:
            continue
        if a.graph not in ctx.cards or graph not in ctx.cards:
            continue
        if resolve_join_key(ctx.cards[a.graph], ctx.cards[graph]) is None:
            continue
        ids = list(a.step.anchor_ids)
        lab = str(label or "<the " + graph + " label that stores " + a.graph + " ids>")
        shown = ids[0] if len(ids) == 1 else ids[:5]
        return (f"To reach {graph} from what step {a.id} found on {a.graph}, anchor the {graph} step on "
                f"that id: \"anchor\": {{\"id\": {json.dumps(shown)}}}, \"anchor_label\": \"{lab}\". The engine "
                f"bridges it through the join key; then add the hops from {lab} to what the question asks for")
    return _found_hint(ctx, graph, label, steps)


def _found_hint(ctx: PlanContext, graph: str, label: Any, steps: list[StepCheck]) -> str:
    """The fix for a plan that does not use an entity ``resolve_entity`` found during this draft.

    Empty when every found entity anchors a step (or none was found), or when
    the found entity is on another graph that no join key links to ``graph``.
    """
    used = {i for a in steps if a.step is not None for i in a.step.anchor_ids}
    for g, eid, lab_found, text in ctx.found_lookups:
        if eid in used:
            continue
        if g == graph:
            return (f"resolve_entity found {text!r} as {eid} ({lab_found}). Anchor the step on it: "
                    f"\"anchor\": {{\"id\": \"{eid}\"}}, then add the hops from {lab_found} to what the "
                    "question asks for")
        if g in ctx.cards and graph in ctx.cards and resolve_join_key(ctx.cards[g], ctx.cards[graph]) is not None:
            lab = str(label or "<the " + graph + " label that stores " + g + " ids>")
            return (f"resolve_entity found {text!r} as {eid} on {g}. To reach {graph} from it, anchor the "
                    f"{graph} step on that id: \"anchor\": {{\"id\": \"{eid}\"}}, \"anchor_label\": \"{lab}\". "
                    f"The engine bridges it through the join key; then add the hops from {lab} to what the "
                    "question asks for")
    return ""


def _refuse_unlinked_scans(checks: list[StepCheck], ctx: PlanContext) -> None:
    """Refuse a whole-label scan beside an anchored step on another, joined graph.

    EXP-2026-11-016 follow-up: a plan that has found an entity on one graph and
    lists every member of a label on the other is a failed bridge (F-REV-06 T5:
    262 taxonomy entries for the 2 linked to one technique). The question asked
    about the found entity, so the scan stands in for the link. Steps that start
    from a refused step are refused with it.
    """
    from utils.agent import errors as E

    for c in checks:
        if not c.ok or c.step.kind != "scan":
            continue
        hint = _bridge_hint(ctx, c.graph, c.step.anchor_label, [a for a in checks if a is not c and a.ok])
        if not hint:
            # A step that tried to anchor on an id or a name was refused: the scan
            # would be all that is left of the plan (F-REV-06 T5, T-full, spot-check).
            tried = [a for a in checks if a is not c and not a.ok and isinstance(a.raw, dict)
                     and isinstance(a.raw.get("anchor"), (dict, str))
                     and (isinstance(a.raw["anchor"], str) or a.raw["anchor"].get("id") or a.raw["anchor"].get("name"))]
            if tried:
                a = tried[0]
                hint = (f"step {a.id}, which anchors the entity the question is about, was refused; fix that "
                        f"step as its refusal says instead of listing every {c.step.anchor_label}")
        if not hint:
            continue
        c.refusals.append(E.refusal(
            "invalid_request",
            f"step {c.id}: a scan lists every {c.step.anchor_label}, but this plan already found the entity "
            f"the question is about",
            hint + f". Scan only when the question asks for every {c.step.anchor_label}",
            [E.problem("kind", "scan", ["expand", "describe", "count"])]))
    refused = {c.id for c in checks if not c.ok}
    for c in checks:
        if c.ok and c.from_step in refused:
            c.refusals.append(E.refusal(
                "invalid_request", f"step {c.id}: from_step {c.from_step!r} was refused",
                f"fix step {c.from_step} first, then start this step from it",
                [E.problem("from_step", c.from_step, [c.from_step])]))
            refused.add(c.id)


def to_plan(request: str, checks: list[StepCheck], data: dict[str, Any], cards: dict[str, SourceCardView],
            refused: list[StepCheck], mode: str) -> Plan:
    """The validated steps as a :class:`Plan` (text blanked, a ``step`` on every sub-question)."""
    plan = Plan(request=request)
    by_id = {c.id: c for c in checks if c.ok}
    for c in checks:
        if not c.ok:
            continue
        card = cards[c.graph]
        entities = c.step.entities()
        plan.sub_questions.append(SubQuestion(
            id=c.id, source=c.graph, text="", entities=entities, limits=Limits(**card.limits()),
            join_key=c.join_key, rationale=f"typed plan ({mode})", step=c.step.to_dict()))
        if c.from_step and c.join_key and c.from_step in by_id:
            prod = by_id[c.from_step]
            key = next((k for k in CANONICAL_JOIN_KEYS if k.name == c.join_key), None)
            plan.joins.append(JoinDeclaration(key=c.join_key, sources=[prod.graph, c.graph],
                                              on=key.description if key else ""))
            plan.sub_questions = [
                replace(sq, join_key=sq.join_key or c.join_key) if sq.id == prod.id else sq
                for sq in plan.sub_questions]
    for u in data.get("unsupported") or []:
        if isinstance(u, dict):
            plan.unsupported.append(UnsupportedPart(str(u.get("description") or ""), str(u.get("reason") or "")))
    for c in refused:
        env = c.refusals[-1] if c.refusals else {}
        plan.unsupported.append(UnsupportedPart(
            f"step {c.id} could not be expressed against the catalog",
            f"refused after repair: {env.get('code')}: {env.get('detail')}"))
    plan.assumptions = [str(a) for a in data.get("assumptions") or [] if a] + [f"typed plan ({mode})"]
    plan.partial = bool(plan.unsupported)
    plan.rationale = "typed plan against the card-derived tool catalog"
    return plan


# --------------------------------------------------------------------------- #
# The planner
# --------------------------------------------------------------------------- #


def _run_tool(ctx: PlanContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """One catalog call (see :func:`_run_tool_inner`); records what ``resolve_entity`` found."""
    res = _run_tool_inner(ctx, name, args)
    if name == "resolve_entity" and isinstance(res, dict):
        text = str((args or {}).get("text") or "")
        for r in [res, *(res.get("results") or [])]:
            if isinstance(r, dict) and r.get("status") == "found" and r.get("graph"):
                for eid in r.get("ids") or []:
                    ctx.found_lookups.append((str(r["graph"]), str(eid), str(r.get("kind") or ""), text))
    return res


def _run_tool_inner(ctx: PlanContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """One catalog call; ``graph`` picks a catalog, else every catalog answers, tagged."""
    from utils.agent import errors as E
    from utils.agent.coerce import Ambiguous, NoMatch, coerce_name

    args = dict(args or {})
    graph = args.pop("graph", None)
    graphs = sorted(ctx.catalogs)
    if name == "resolve_entity" and isinstance(args.get("text"), str):
        # An identifier is not a name: the name search would rank it as words.
        # Answer it from the entity index, on the graph(s) that hold it.
        text = args["text"].strip()
        hits = [(g, ctx.known_id(g, text)) for g in ([graph] if graph in graphs else graphs)]
        hits = [(g, h) for g, h in hits if h is not None]
        if len(hits) == 1:
            g, (eid, lab) = hits[0]
            return {"ok": True, "status": "found", "graph": g, "ids": [eid], "kind": lab, "match": "id"}
        if not hits and graph in graphs:
            elsewhere = [(g, ctx.known_id(g, text)) for g in graphs if g != graph]
            elsewhere = [(g, h) for g, h in elsewhere if h is not None]
            if len(elsewhere) == 1:
                g, (eid, lab) = elsewhere[0]
                return {"ok": True, "status": "found", "graph": g, "ids": [eid], "kind": lab, "match": "id",
                        "note": f"{eid} is an id of {g}, not of {graph}. It can still anchor a {graph} step "
                                "through the join key: give the id and this graph's label as anchor_label."}
        if not hits:
            shaped = {g: ctx.id_labels(g, text) for g in ([graph] if graph in graphs else graphs)}
            shaped = {g: labs for g, labs in shaped.items() if labs}
            if shaped:
                ctx.failed_lookups.append(text)
                g, labs = next(iter(sorted(shaped.items())))
                return {"ok": True, "status": "not_found", "graph": g, "ids": [], "kind": labs[0],
                        "detail": f"{text} has the form of a {'/'.join(labs)} id of {g}, but no such entity "
                                  "is in the graph",
                        "fix": f"anchor the step on {{\"id\": \"{text}\"}} anyway: the engine answers that it "
                               "is not in the graph. Do not replace it with a scan."}
    if graph is not None:
        try:
            graph = coerce_name(graph, graphs, "graph")
        except (NoMatch, Ambiguous):
            return E.choice("not_in_card", f"graph {graph!r} is not a live graph", "graph", graph, graphs,
                            what="graph")
        res = ctx.tools[graph].call(name, args)
        return {**res, "graph": graph} if isinstance(res, dict) else res
    results = {g: ctx.tools[g].call(name, args) for g in graphs}
    ok = {g: r for g, r in results.items() if r.get("ok")}
    if name == "find_schema" and ok:
        matches = [{**m, "graph": g} for g, r in ok.items() for m in r.get("matches") or []]
        matches.sort(key=lambda m: -float(m.get("score") or 0))
        return {"ok": True, "matches": matches[: int(args.get("k") or 8)], "method": "bm25"}
    if len(ok) == 1:
        g, r = next(iter(ok.items()))
        return {**r, "graph": g}
    if ok:
        return {"ok": True, "results": [{**r, "graph": g} for g, r in ok.items()]}
    g0 = graphs[0]
    return {**results[g0], "graph": g0, "other_graphs": {g: results[g].get("detail") for g in graphs[1:]}}


@dataclass
class TypedLog:
    mode: str
    served_model: str = ""
    model_calls: int = 0
    catalog_calls: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    emitted: bool = False
    parse_error: str | None = None
    first_steps: int = 0
    first_refused: int = 0
    first_fixes: int = 0
    valid_first: bool = False
    valid_first_raw: bool = False
    repair_used: bool = False
    fixed_by_repair: bool = False
    still_refused: int = 0
    final_steps: int = 0
    coercions: list[dict[str, Any]] = field(default_factory=list)
    refusals: list[dict[str, Any]] = field(default_factory=list)
    plan_problems: list[str] = field(default_factory=list)
    replies: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    fallback: str | None = None
    seconds: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["n_catalog_calls"] = len(self.catalog_calls)
        d["fixed_by_coercion"] = self.valid_first and not self.valid_first_raw
        return d


class TypedPlanner:
    """Drafts one typed plan for a request (see the module docstring)."""

    def __init__(self, model: Any, mode: str = "lazy") -> None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.model = model
        self.mode = mode

    def _ask(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], log: TypedLog) -> Any:
        from utils.llm import LLMUnavailable

        try:
            reply = self.model(messages, tools)
        except LLMUnavailable as exc:
            raise DrafterUnavailable(str(exc)) from exc
        log.model_calls += 1
        log.served_model = getattr(self.model, "served_model", "") or reply.model
        log.prompt_tokens += int((reply.usage or {}).get("prompt_tokens") or 0)
        log.completion_tokens += int((reply.usage or {}).get("completion_tokens") or 0)
        log.replies.append({"status": reply.status, "finish_reason": reply.finish_reason,
                            "calls": [c.name for c in reply.tool_calls], "text_chars": len(reply.text or ""),
                            "repairs": [r.as_dict() for r in reply.repairs]})
        if getattr(reply, "fallback_from", None):
            raise DrafterUnavailable(f"answered by a fallback model ({reply.fallback_from})")
        return reply

    def plan(self, request: str, cards: dict[str, SourceCardView], live: set[str] | None = None
             ) -> tuple[Plan, TypedLog]:
        from utils.llm.toolcalls import tool_result_message

        started = time.monotonic()
        log = TypedLog(mode=self.mode)
        catalogs = catalogs_for(cards)
        with tempfile.TemporaryDirectory(prefix="typed-plan-") as tmp:
            ctx = PlanContext(cards, catalogs, Path(tmp), live, request=request)
            try:
                if not ctx.catalogs:
                    raise DrafterUnavailable("no live graph to plan against")
                messages = build_messages(request, ctx.catalogs, self.mode)
                specs = tool_specs(ctx.catalogs)
                reply = None
                for _turn in range(MAX_CATALOG_CALLS + 1):
                    budget_left = MAX_CATALOG_CALLS - len(log.catalog_calls)
                    reply = self._ask(messages, specs if budget_left > 0 else [], log)
                    if not reply.tool_calls:
                        break
                    messages.append(reply.assistant_message())
                    for call in reply.tool_calls:
                        if len(log.catalog_calls) >= MAX_CATALOG_CALLS:
                            from utils.agent import errors as E

                            res = E.refusal("invalid_request", "the catalog call budget (4) is spent",
                                            "reply now with the plan JSON", [E.problem("tool", call.name, [])])
                        elif call.name not in PLANNER_TOOLS or call.arguments is None:
                            from utils.agent import errors as E

                            res = E.choice("invalid_request", f"{call.name!r} cannot be called here "
                                           f"({call.error or 'unknown tool'})", "tool", call.name,
                                           list(PLANNER_TOOLS), what="a catalog tool")
                            log.catalog_calls.append({"name": call.name, "ok": False})
                        else:
                            res = _run_tool(ctx, call.name, call.arguments)
                            log.catalog_calls.append({"name": call.name, "args": call.arguments,
                                                      "ok": bool(res.get("ok"))})
                        messages.append(tool_result_message(call.id, res))
                    if len(log.catalog_calls) >= MAX_CATALOG_CALLS:
                        messages.append({"role": "user", "content":
                                         "The catalog call budget is spent. Reply now with the plan JSON only."})
                if reply is None or reply.tool_calls:
                    raise DrafterUnavailable("the model did not emit a plan")
                messages.append(reply.assistant_message())
                data, checks = self._parse_and_check(reply, ctx, log)
                log.emitted = data is not None
                log.first_steps = len(checks)
                log.first_refused = sum(1 for c in checks if not c.ok)
                log.first_fixes = sum(len(c.fixes) for c in checks)
                log.valid_first = data is not None and bool(checks) and log.first_refused == 0
                log.valid_first_raw = log.valid_first and log.first_fixes == 0
                refused = [c for c in checks if not c.ok]
                if data is None or refused:
                    log.repair_used = True
                    messages.append({"role": "user", "content": self._repair_message(data, checks, log)})
                    reply = self._ask(messages, [], log)
                    data2, checks2 = self._parse_and_check(reply, ctx, log)
                    if data2 is None:
                        if data is None:
                            raise DrafterUnavailable(f"no plan JSON after the repair turn ({log.parse_error})")
                    else:
                        data, checks = data2, checks2
                    refused = [c for c in checks if not c.ok]
                    log.fixed_by_repair = not refused and bool(checks)
                for c in checks:
                    log.coercions += [{"step": c.id, **f} for f in c.fixes]
                    log.refusals += [{"step": c.id, "final": True, **{k: e.get(k) for k in
                                                                       ("code", "detail", "fix")}}
                                     for e in c.refusals]
                log.still_refused = len(refused)
                plan = to_plan(request, checks, data or {}, cards, refused, self.mode)
                log.final_steps = len(plan.sub_questions)
                return plan, log
            finally:
                ctx.close()
                log.seconds = round(time.monotonic() - started, 3)

    def _parse_and_check(self, reply: Any, ctx: PlanContext, log: TypedLog
                         ) -> tuple[dict[str, Any] | None, list[StepCheck]]:
        try:
            data = extract_json_object(reply.text or "")
        except DrafterUnavailable as exc:
            log.parse_error = str(exc)
            return None, []
        checks, problems = check_plan(data, ctx)
        log.plan_problems += problems
        for c in checks:
            if c.refusals:
                log.refusals += [{"step": c.id, "final": False, **{k: e.get(k) for k in ("code", "detail", "fix")}}
                                 for e in c.refusals]
        return data, checks

    @staticmethod
    def _repair_message(data: dict[str, Any] | None, checks: list[StepCheck], log: TypedLog) -> str:
        if data is None:
            return ("Your reply was not one JSON plan (" + str(log.parse_error) + "). Reply with the plan JSON "
                    "only, in the shape given.")
        refused = [{"step": c.id, "sent": c.raw, "refusals": c.refusals} for c in checks if not c.ok]
        accepted = [{"step": c.id, "graph": c.graph, **c.step.to_dict()} for c in checks if c.ok]
        return ("The catalog checked your plan. These steps were refused; each refusal says what to send "
                "instead:\n" + json.dumps(refused, ensure_ascii=False, default=str)
                + "\nAccepted as checked:\n" + json.dumps(accepted, ensure_ascii=False)
                + "\nReply with the corrected full plan JSON (same shape). A step you cannot fix goes in "
                  "\"unsupported\". This is the only repair turn.")


# --------------------------------------------------------------------------- #
# The drafter the planning graph uses
# --------------------------------------------------------------------------- #


class TypedDrafter:
    """A ``PlanDrafter`` over :class:`TypedPlanner`, with the English arm's fallback.

    The fallback is the hybrid drafter's, kept identical so the arms differ in
    the hand-off and nothing else: a transport or parse failure drafts with
    the deterministic drafter, and so does a typed plan that routed nothing
    *of the model's own accord* (no step at all). A plan whose steps were all
    refused is **not** floored: the refusals are its abstention.
    """

    def __init__(self, model: Any, mode: str = "lazy", fallback: Any = None) -> None:
        from .drafter import DeterministicDrafter

        self.planner = TypedPlanner(model, mode)
        self.fallback = fallback or DeterministicDrafter()
        self.last_used = ""
        self.logs: list[dict[str, Any]] = []

    def draft(self, request: str, cards: dict[str, SourceCardView], live_view: LiveSourceView,
              feedback: list[str] | None = None, intent: "IntentClassification | None" = None) -> Plan:
        live = {ds for ds in cards if live_view.is_live(ds)}
        try:
            plan, log = self.planner.plan(request, cards, live)
        except DrafterUnavailable as exc:
            logger.info("typed planner unavailable (%s); using deterministic fallback", exc)
            plan = self.fallback.draft(request, cards, live_view, feedback, intent)
            plan.assumptions.append(f"typed planner unavailable ({exc}); used deterministic fallback")
            self.last_used = type(self.fallback).__name__
            self.logs.append({"mode": self.planner.mode, "fallback": "unavailable", "error": str(exc)})
            plan.typed = self.logs[-1]
            return plan
        entry = log.as_dict()
        if feedback:
            entry["gate_feedback"] = list(feedback)
        if not plan.sub_questions and not log.first_refused and not log.still_refused:
            floor = self.fallback.draft(request, cards, live_view, feedback, intent)
            if floor.sub_questions:
                floor.assumptions.append("typed planner routed nothing; used deterministic floor")
                entry["fallback"] = "floor"
                self.logs.append(entry)
                floor.typed = entry
                self.last_used = type(self.fallback).__name__
                return floor
        self.logs.append(entry)
        plan.typed = entry
        self.last_used = type(self).__name__
        return plan


__all__ = ["MAX_CATALOG_CALLS", "MODES", "PLANNER_TOOLS", "PlanContext", "STEP_KINDS", "StepCheck", "SYSTEM_PROMPT",
           "TypedDrafter", "TypedLog", "TypedPlanner", "build_messages", "catalog_block", "catalogs_for",
           "check_plan", "check_step", "to_plan", "tool_specs"]
