#!/usr/bin/env python3
"""The catalog's tools, as thin wrappers over the Step 5 retrieval (Era 2, Step 8).

Retrieval is not re-implemented here. ``expand`` and ``count`` are
:func:`utils.agent.exact.fetch` and :class:`utils.agent.handles.HandleStore`;
what the model sees is :func:`utils.agent.view.build_view`; an empty result is
explained by :func:`utils.agent.view.diagnose_empty`; ``resolve_entity`` is
the existing name search (:mod:`utils.specialists.schema.namesearch`);
``find_schema`` ranks the card's own words with that module's BM25 index
(no embedding model: the project has none, so this is BM25 only).

Every call is **validated and coerced before it runs**, against the option
rules of the catalog (:mod:`utils.agent.catalog`) and with the coercions of
:mod:`utils.agent.coerce`; a call that cannot be repaired is refused with the
envelope of :mod:`utils.agent.errors`, whose ``fix`` names the valid options.
So an invalid call never reaches a store.

Implemented: ``find_schema``, ``resolve_entity``, ``describe``, ``expand``,
``count``, ``set_op``, ``not_expressible`` (recorded). ``filter``,
``aggregate``, ``group``, ``rank`` and ``verify`` have their schemas and their
validation; a valid call is refused, naming the tools that are available (the
operators arrive in Step 9). ``ask_caller`` and ``finish`` are the run's exits
and are handled by :mod:`utils.agent.runner`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from utils.agent import errors as E
from utils.agent.catalog import AGG_FNS, ALL_OPS, DIRECTIONS, HANDLE_PATTERN, IMPLEMENTED, NUMERIC, Catalog, words
from utils.agent.coerce import (Ambiguous, Coercions, NoMatch, coerce_bool, coerce_enum, coerce_int, coerce_name,
                                coerce_value)
from utils.agent.exact import SetSpec, fetch
from utils.agent.handles import SET_OPS, HandleStore
from utils.agent.runner import ToolBox
from utils.agent.view import build_view, diagnose_empty

_HANDLE = re.compile(HANDLE_PATTERN)
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
#: Strings that mean a handle even when mis-spelt (``set-3``, ``Set 3``, ``set:``).
_HANDLE_LIKE = re.compile(r"^set\W*[0-9]*$", re.IGNORECASE)
ORDERABLE = NUMERIC + ("date", "datetime", "string")


class Refused(Exception):
    """Raised inside validation; carries the envelope."""

    def __init__(self, envelope: dict[str, Any]) -> None:
        super().__init__(envelope.get("detail"))
        self.envelope = envelope


@dataclass
class Call:
    tool: str
    args: dict[str, Any]
    log: Coercions = field(default_factory=Coercions)


def _option_text(o: Any) -> str:
    return f"{o.relation} {o.direction} -> {o.target} ({o.reading})"


class Tools:
    """One run's tools: a catalog, a backend (or None), a handle store."""

    def __init__(self, catalog: Catalog, backend: Any, handles: HandleStore, *,
                 name_dataset: str | None = None) -> None:
        self.catalog = catalog
        self.backend = backend
        self.handles = handles
        self.name_dataset = catalog.name if name_dataset is None else name_dataset
        self.records: list[dict[str, Any]] = []
        self._seen: dict[str, dict[str, Any]] = {}
        self._schema_index: Any = None
        self._schema_docs: list[dict[str, Any]] = []
        self._params = {s["function"]["name"]: s["function"]["parameters"] for s in catalog.specs("names")}

    # ------------------------------------------------------------------ #
    # validation helpers
    # ------------------------------------------------------------------ #

    def _held(self) -> list[str]:
        return self.handles.handles()

    def _name(self, c: Call, key: str, options: list[str], *, what: str, refuse_options: list[str] | None = None,
              code: str = "not_in_card") -> str:
        value = c.args.get(key)
        try:
            return coerce_name(value, options, key, c.log)
        except Ambiguous as exc:
            raise Refused(E.choice(code, f"{key}: {value!r} is ambiguous between {exc.candidates}", key, value,
                                   exc.candidates, what=what, hint="it was not guessed")) from None
        except NoMatch:
            opts = refuse_options if refuse_options else options
            raise Refused(E.choice(code, f"{key}: {value!r} is not a {what} of this card", key, value, opts,
                                   what=what)) from None

    def _enum(self, c: Call, key: str, options: list[str] | tuple[str, ...], *, what: str) -> str:
        value = c.args.get(key)
        try:
            return coerce_enum(value, list(options), key, c.log)
        except (NoMatch, Ambiguous):
            raise Refused(E.choice("invalid_request", f"{key}: {value!r} is not one of the allowed values", key,
                                   value, list(options), what=what)) from None

    def _handle(self, c: Call, key: str) -> Any:
        value = c.args.get(key)
        held = self._held()
        if isinstance(value, str) and _HANDLE_LIKE.match(value.strip()) and not _HANDLE.match(value.strip()):
            m = re.search(r"[0-9]+", value)
            if m and f"set:{int(m.group())}" in held:
                c.log.add(key, value, f"set:{int(m.group())}", "case_separator")
                value = c.args[key] = f"set:{int(m.group())}"
        if isinstance(value, str) and _HANDLE.match(value.strip()):
            value = value.strip()
            if value in held:
                return self.handles.get(value)
        if held:
            raise Refused(E.choice("invalid_request", f"{key}: {value!r} is not a set handle of this run", key,
                                   value, held, what=f"{key} (a handle you hold)"))
        raise Refused(E.refusal("invalid_request", f"{key}: {value!r} is not a set handle and no set exists yet",
                                "make a set first with resolve_entity or expand, then pass its handle (set:N)",
                                [E.problem(key, value, ["resolve_entity", "expand"])]))

    def _label_of(self, rec: Any) -> str | None:
        return rec.kind if rec is not None and rec.kind in self.catalog.model.labels else None

    def _props_for(self, label: str | None) -> dict[str, Any]:
        if label:
            return self.catalog.label_properties(label)
        out: dict[str, Any] = {}
        for lab in self.catalog.labels():
            for k, p in self.catalog.label_properties(lab).items():
                out.setdefault(k, p)
        return out

    def _check_args(self, c: Call) -> None:
        """Unknown argument names (repaired when near), missing required ones."""
        params = self._params[c.tool]
        allowed = list(params["properties"])
        fixed: dict[str, Any] = {}
        for k, v in c.args.items():
            if k in allowed:
                fixed[k] = v
                continue
            try:
                kk = coerce_name(k, allowed, "argument", c.log)
            except (NoMatch, Ambiguous):
                raise Refused(E.choice("invalid_request", f"{c.tool} takes no argument {k!r}", "argument", k,
                                       allowed, what=f"{c.tool}'s arguments")) from None
            if kk in c.args:
                raise Refused(E.choice("invalid_request", f"{c.tool}: {k!r} repeats {kk!r}", "argument", k,
                                       allowed, what=f"{c.tool}'s arguments"))
            fixed[kk] = v
        c.args = fixed
        missing = [k for k in params.get("required", []) if c.args.get(k) in (None, "", [])]
        if missing:
            k = missing[0]
            opts = self._options_for_missing(c, k)
            raise Refused(E.choice("invalid_request", f"{c.tool} needs {missing}", k, None, opts,
                                   what=k if opts != [k] else "the argument to send"))

    def _options_for_missing(self, c: Call, key: str) -> list[str]:
        """What a missing argument could be: the option rules where they apply, else the argument's name."""
        label = None
        h = c.args.get("from") or c.args.get("set")
        if isinstance(h, str) and h in self._held():
            label = self._label_of(self.handles.get(h))
        if key == "relation":
            return sorted({o.relation for o in self.catalog.options(label)}) if label else self.catalog.relations()
        if key in ("from", "set", "a", "b"):
            return self._held() or [key]
        if key in ("property", "by"):
            return sorted(self._props_for(label)) or [key]
        if key == "op":
            return list(SET_OPS) if c.tool == "set_op" else list(ALL_OPS)
        if key == "fn":
            return list(AGG_FNS)
        if key == "target":
            return self.catalog.labels() + self.catalog.relations()
        return [key]

    # ------------------------------------------------------------------ #
    # validation per tool (returns the clean arguments)
    # ------------------------------------------------------------------ #

    def _text(self, c: Call, key: str) -> str:
        v = c.args.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            c.log.add(key, v, str(v), "text_from_number")
            v = str(v)
        if not isinstance(v, str) or not v.strip():
            raise Refused(E.choice("invalid_request", f"{key} must be non-empty text", key, v, [key],
                                   what="the argument to send as text"))
        return v.strip()

    def validate(self, tool: str, args: dict[str, Any] | None) -> Call:
        """Check and coerce one call. Raises :class:`Refused` with the envelope."""
        if tool not in self._params:
            raise Refused(E.choice("invalid_request", f"unknown tool {tool!r}", "tool", tool,
                                   sorted(self._params), what="a tool"))
        if not isinstance(args, dict):
            raise Refused(E.choice("invalid_request", "arguments must be one JSON object", "arguments", args,
                                   list(self._params[tool]["properties"]), what=f"{tool}'s arguments"))
        c = Call(tool, dict(args))
        self._check_args(c)
        getattr(self, f"_v_{tool}")(c)
        return c

    def _v_find_schema(self, c: Call) -> None:
        c.args["text"] = self._text(c, "text")
        k = c.args.get("k", 8)
        try:
            k = coerce_int(k, "k", c.log)
        except NoMatch:
            k = -1
        if not 1 <= k <= 50:
            raise Refused(E.choice("invalid_request", f"k: {c.args.get('k')!r} is not an integer from 1 to 50",
                                   "k", c.args.get("k"), ["1", "8", "50"], what="k (1 to 50)"))
        c.args["k"] = k

    def _v_resolve_entity(self, c: Call) -> None:
        c.args["text"] = self._text(c, "text")
        if c.args.get("label") is not None:
            c.args["label"] = self._name(c, "label", self.catalog.labels(), what="label")

    def _v_describe(self, c: Call) -> None:
        t = c.args.get("target")
        if isinstance(t, list) and len(t) == 1:
            c.log.add("target", t, t[0], "single_from_list")
            t = t[0]
        if not isinstance(t, str) or not t.strip():
            raise Refused(E.choice("invalid_request", f"target: {t!r} is not a name, handle or id", "target", t,
                                   self.catalog.labels() + self.catalog.relations(), what="target"))
        c.args["target"] = t.strip()

    def _v_expand(self, c: Call) -> None:
        cat = self.catalog
        src = c.args.get("from")
        rec, seeds = None, None
        if isinstance(src, str) and _HANDLE_LIKE.match(src.strip()):
            rec = self._handle(c, "from")
            seeds = list(rec.ids)
        elif isinstance(src, str) and src.strip():
            seeds = [src.strip()]
            c.log.add("from", src, seeds, "list_from_single")
        elif isinstance(src, list) and src and all(isinstance(x, str) and x.strip() for x in src):
            seeds = [x.strip() for x in src]
        else:
            held = self._held()
            raise Refused(E.choice("invalid_request", f"from: {src!r} is neither a handle nor a list of ids", "from",
                                   src, held or ["resolve_entity"], what="from (a handle you hold)" if held else
                                   "a tool that makes a set"))
        label = self._label_of(rec)
        here = cat.options(label) if label else []
        rel_here = sorted({o.relation for o in here})
        rel = self._name(c, "relation", cat.relations(), what="relation",
                         refuse_options=[_option_text(o) for o in here] or None)
        if label:
            opts = cat.options(label, rel)
            if not opts:
                raise Refused(E.choice("invalid_request", f"{label} has no {rel} relation", "relation", rel,
                                       [_option_text(o) for o in here] or rel_here,
                                       what=f"a relation {label} has"))
        else:
            opts = cat.relation_options(rel)
        dirs = sorted({o.direction for o in opts}) or list(DIRECTIONS)
        d = c.args.get("direction")
        if d is None:
            if label and len(dirs) == 1:
                d = dirs[0]
                c.log.add("direction", None, d, "option_rules")
            else:
                raise Refused(E.choice("invalid_request", f"direction is needed: {rel} goes both ways here",
                                       "direction", None, dirs, what="direction",
                                       hint="; ".join(_option_text(o) for o in opts[:8])))
        else:
            d = self._enum(c, "direction", list(DIRECTIONS), what="direction")
            if label and d not in dirs:
                raise Refused(E.choice("invalid_request", f"{label} has {rel} only as direction {dirs}",
                                       "direction", d, dirs, what="direction",
                                       hint="; ".join(_option_text(o) for o in opts[:8])))
        opts = [o for o in opts if o.direction == d] if label else opts
        ends = sorted({o.target for o in opts}) or cat.labels()
        to = c.args.get("to_label")
        if to is not None:
            to = self._name(c, "to_label", cat.labels(), what="label", refuse_options=ends)
            if label and to not in ends:
                raise Refused(E.choice("invalid_request", f"{label} {rel} {d} goes to {ends}, not {to}",
                                       "to_label", to, ends, what="to_label"))
        depth_raw = c.args.get("depth", 1)
        max_d = cat.model.max_depth
        repeating = any(o.repeating for o in opts) if opts else False
        top = max_d if repeating else 1
        try:
            depth = coerce_int(depth_raw, "depth", c.log)
        except NoMatch:
            depth = None
        if depth is None or not 1 <= depth <= top:
            why = (f"depth must be an integer from 1 to {top}" if repeating or depth is None or depth < 1
                   else f"{rel} is not a repeating relation here, so depth is 1")
            raise Refused(E.choice("invalid_request", f"depth: {depth_raw!r}: {why}", "depth", depth_raw,
                                   [str(i) for i in range(1, top + 1)], what="depth"))
        c.args.update({"relation": rel, "direction": d, "to_label": to, "depth": depth})
        c.args["_seeds"], c.args["_label"] = seeds, label
        c.args["_targets"] = sorted({o.target for o in opts}) if label else []

    def _v_set_op(self, c: Call) -> None:
        c.args["op"] = self._enum(c, "op", SET_OPS, what="op")
        self._handle(c, "a")
        self._handle(c, "b")

    def _v_count(self, c: Call) -> None:
        self._handle(c, "set")

    def _v_not_expressible(self, c: Call) -> None:
        c.args["part"] = self._text(c, "part")
        c.args["needs"] = self._text(c, "needs")

    def _set_label(self, c: Call) -> str | None:
        return self._label_of(self._handle(c, "set"))

    def _property(self, c: Call, key: str, label: str | None, *, allow: Callable[[Any], bool] | None = None,
                  what: str = "property") -> Any:
        props = self._props_for(label)
        names = sorted(props)
        if not names:
            raise Refused(E.choice("invalid_request", f"{label or 'this set'} has no properties to use",
                                   key, c.args.get(key), [o for o in IMPLEMENTED], what="another tool"))
        name = self._name(c, key, self.catalog.properties(), what=what, refuse_options=names,
                          code="not_in_card")
        if name not in props:
            raise Refused(E.choice("invalid_request", f"{name} is not a property of {label}", key, name, names,
                                   what=f"a property of {label}"))
        p = props[name]
        if allow is not None and not allow(p):
            ok = [n for n, q in sorted(props.items()) if allow(q)]
            if not ok:
                raise Refused(E.choice("invalid_request", f"no property of {label or 'this set'} fits {c.tool}",
                                       key, name, ["count"] if c.tool == "aggregate" else list(IMPLEMENTED),
                                       what="fn" if c.tool == "aggregate" else "another tool"))
            raise Refused(E.choice("invalid_request", f"{name} ({p.vtype}) does not fit {c.tool}", key, name, ok,
                                   what=what))
        c.args[key] = name
        return p

    def _v_filter(self, c: Call) -> None:
        label = self._set_label(c)
        p = self._property(c, "property", label)
        ops = list(p.ops)
        op = c.args.get("op")
        try:
            op = coerce_enum(op, ops, "op", c.log)
        except (NoMatch, Ambiguous):
            raise Refused(E.choice("invalid_request", f"op {op!r} does not apply to {p.name} ({p.vtype})", "op",
                                   op, ops, what=f"op for a {p.vtype} property")) from None
        c.args["op"] = op
        v = c.args.get("value")
        try:
            c.args["value"] = coerce_value(v, p.vtype, "value", c.log)
        except NoMatch:
            examples = {"boolean": ["true", "false"], "list": ["one element, as text"]}.get(p.vtype, [])
            raise Refused(E.choice("invalid_request", f"value {v!r} is not a {p.vtype}", "value", v,
                                   [p.vtype] + examples, what=f"a value of type {p.vtype}")) from None

    def _v_aggregate(self, c: Call) -> None:
        label = self._set_label(c)
        fn = self._enum(c, "fn", AGG_FNS, what="fn")
        c.args["fn"] = fn
        if fn == "count":
            if c.args.get("property") is not None:
                self._property(c, "property", label)
            return
        if c.args.get("property") is None:
            props = self._props_for(label)
            ok = sorted(n for n, q in props.items() if q.vtype in NUMERIC)
            raise Refused(E.choice("invalid_request", f"{fn} needs a numeric property", "property", None,
                                   ok or ["count"], what="property" if ok else "fn"))
        allow = (lambda q: q.vtype in NUMERIC) if fn in ("sum", "avg") else (lambda q: q.vtype in ORDERABLE)
        self._property(c, "property", label, allow=allow)

    def _v_group(self, c: Call) -> None:
        self._property(c, "by", self._set_label(c))

    def _v_rank(self, c: Call) -> None:
        self._property(c, "by", self._set_label(c), allow=lambda q: q.vtype in ORDERABLE)
        k = c.args.get("k")
        try:
            k = coerce_int(k, "k", c.log)
        except NoMatch:
            k = 0
        if k < 1:
            raise Refused(E.choice("invalid_request", f"k: {c.args.get('k')!r} is not a positive integer", "k",
                                   c.args.get("k"), ["1", "5", "10"], what="k (a positive integer)"))
        c.args["k"] = k
        if c.args.get("order") is not None:
            c.args["order"] = self._enum(c, "order", ("desc", "asc"), what="order")
        if c.args.get("ties") is not None:
            try:
                c.args["ties"] = coerce_bool(c.args["ties"], "ties", c.log)
            except NoMatch:
                raise Refused(E.choice("invalid_request", "ties must be true or false", "ties", c.args["ties"],
                                       ["true", "false"], what="ties")) from None

    def _v_verify(self, c: Call) -> None:
        c.args["claim"] = self._text(c, "claim")
        sets = c.args.get("sets") or []
        if not isinstance(sets, list):
            sets = [sets]
        for i, h in enumerate(sets):
            c.args[f"_s{i}"] = h
            self._handle(c, f"_s{i}")
            c.args.pop(f"_s{i}")

    # ------------------------------------------------------------------ #
    # running a call
    # ------------------------------------------------------------------ #

    def call(self, tool: str, args: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
        """Validate, coerce, refuse a repeat, then run. Always returns a dict."""
        try:
            c = self.validate(tool, {**(args or {}), **kw})
        except Refused as r:
            return r.envelope
        key = tool + json.dumps({k: v for k, v in c.args.items() if not k.startswith("_")}, sort_keys=True,
                                default=str)
        prev = self._seen.get(key)
        if prev is not None and tool not in ("not_expressible",):
            h = prev.get("handle")
            return E.refusal("repeated_call", f"{tool} was already called with these arguments",
                             f"use {h}, which that call returned" if h else
                             "use the earlier result; change an argument to ask something new",
                             [E.problem("call", tool, [h] if h else [])], coerced=c.log.fixes)
        try:
            out = getattr(self, f"_run_{tool}")(c)
        except Refused as r:
            out = r.envelope
        if c.log.fixes:
            out["coerced"] = c.log.fixes
        if not E.is_refusal(out) or out.get("code") == "empty":
            self._seen[key] = out
        return out

    def _need_backend(self) -> None:
        if self.backend is None:
            raise Refused(E.refusal("invalid_request", "no store is connected to this run",
                                    "use find_schema or describe on labels and relations; they need no store",
                                    [E.problem("store", None, ["find_schema", "describe"])]))

    def _run_find_schema(self, c: Call) -> dict[str, Any]:
        if self._schema_index is None:
            from utils.specialists.schema.namesearch import NameIndex

            self._schema_docs = self.catalog.search_documents()
            docs = []
            for i, d in enumerate(self._schema_docs):
                name_toks = _toks(words(d["name"]))
                docs.append((str(i), d["kind"], words(d["name"]), name_toks * 3 + _toks(d["text"])))
            self._schema_index = NameIndex(docs)
        hits = self._schema_index.search(c.args["text"], top_k=c.args["k"] * 3)
        out, seen = [], set()
        for h in hits:
            d = self._schema_docs[int(h.entity_id)]
            key = (d["kind"], d["name"], d.get("label"), d.get("direction"), d.get("target"))
            if key in seen:
                continue
            seen.add(key)
            out.append({k: v for k, v in d.items() if k != "text"} | {"score": h.score})
            if len(out) >= c.args["k"]:
                break
        if not out:
            return E.choice("not_in_card", f"nothing in the card matches {c.args['text']!r}", "text",
                            c.args["text"], self.catalog.labels(), what="a label to describe",
                            hint="or try other words")
        return {"ok": True, "matches": out, "method": "bm25"}

    def _run_resolve_entity(self, c: Call) -> dict[str, Any]:
        from utils.specialists.schema import namesearch as ns

        text, label = c.args["text"], c.args.get("label")
        labels = [label] if label else None
        exact = ns.exact_name_matches(self.name_dataset, text, labels=labels)
        if len(exact) > 1:
            cands = [_cand(x) for x in exact]
            return E.refusal("ambiguous_anchor", f"{text!r} names {len(exact)} entities",
                             "choose one: " + E.name_options(f"{x['id']} {x['name']} ({x['label']})" for x in cands)
                             + "; or ask_caller", [E.problem("text", text, [x["id"] for x in cands])],
                             candidates=cands)
        one = exact[0] if exact else ns.resolve_in(self.name_dataset, text, labels=labels)
        if one is not None:
            ids = self._store_ids(one)
            rec = self.handles.put(one.label, ids, query=f"resolve_entity({text!r})",
                                   origin={"tool": "resolve_entity", "text": text, "name_id": one.entity_id})
            return {"ok": True, "status": "found", "handle": rec.handle, "kind": rec.kind, "total": rec.total,
                    "complete": True, "ids": list(rec.ids), "candidates": [_cand(one)],
                    "match": "exact_name" if exact else "ranked"}
        hits = ns.search_in(self.name_dataset, text, top_k=5, labels=labels)
        if hits:
            return {"ok": True, "status": "candidates", "candidates": [_cand(h) for h in hits],
                    "note": "no confident match; pass a candidate's id to expand or describe, or ask_caller"}
        return E.refusal("empty", f"no entity of this graph matches {text!r}",
                         "try other words, a label from: " + E.name_options(self.catalog.labels()),
                         [E.problem("text", text, self.catalog.labels())], reason="no_entity_match")

    def _store_ids(self, cand: Any) -> list[str]:
        """The store's id for a name-search candidate (the analyst-facing id may differ)."""
        if self.backend is None:
            return [cand.entity_id]
        if self.backend.anchors_found((cand.entity_id,)):
            return [cand.entity_id]
        if not _IDENT.match(cand.label or ""):
            return [cand.entity_id]
        be = self.backend
        if be.name == "cypher":
            q = f"MATCH (n:{cand.label}) WHERE n.name = $name RETURN DISTINCT {be._id('n')} AS id"
            got = [str(r["id"]) for r in be._rows(q, {"name": cand.name})]
        else:
            got = [str(x) for x in be._submit(f"g.V().hasLabel('{cand.label}').has('name', name).{be._id()}.dedup()",
                                              {"name": cand.name})]
        return got or [cand.entity_id]

    def _run_describe(self, c: Call) -> dict[str, Any]:
        t = c.args["target"]
        cat = self.catalog
        if t in cat.model.labels:
            return {"ok": True, "kind": "label", "name": t, "text": cat.describe_label(t),
                    "options": cat.x_options([t])["labels"][t]}
        if t in cat.model.relations:
            return {"ok": True, "kind": "relation", "name": t, "text": cat.describe_relation(t),
                    "options": [o.as_dict(cat.model.max_depth) for o in cat.relation_options(t)]}
        if _HANDLE.match(t):
            c.args["set"] = t
            rec = self._handle(c, "set")
            c.args.pop("set")
            self._need_backend()
            return {"ok": True, **self._view(rec)}
        try:
            fixed = coerce_name(t, cat.labels() + cat.relations(), "target", c.log)
            c.args["target"] = fixed
            return self._run_describe(c)
        except Ambiguous as exc:
            return E.choice("not_in_card", f"target {t!r} is ambiguous", "target", t, exc.candidates,
                            what="target", hint="it was not guessed")
        except NoMatch:
            pass
        if self.backend is not None and self.backend.anchors_found((t,)):
            rows = self.backend.describe_ids([t], ("name",))
            facets = self.backend.anchor_facets((t,))
            return {"ok": True, "kind": "entity", "id": t, "rows": rows,
                    "edges": [{"relation": cat.card_relation(f["rel"]), "direction": f["direction"],
                               "label": f["label"], "n": int(f["n"])} for f in facets]}
        return E.choice("not_in_card", f"{t!r} is not a label, relation, handle or known id", "target", t,
                        cat.labels() + cat.relations() + self._held(), what="target",
                        hint="for an entity's name, use resolve_entity")

    def _view(self, rec: Any) -> dict[str, Any]:
        v = build_view(rec, self.backend)
        return v

    def _run_expand(self, c: Call) -> dict[str, Any]:
        self._need_backend()
        a = c.args
        seeds, label, rel, d, to, depth = a["_seeds"], a["_label"], a["relation"], a["direction"], a["to_label"], \
            a["depth"]
        acc: set[str] = set()
        frontier = list(seeds)
        complete, queries = True, []
        first_spec = None
        for level in range(depth):
            spec = SetSpec(tuple(frontier), rel, d, to, label if level == 0 else (to or label))
            first_spec = first_spec or spec
            got = fetch(self.backend, spec)
            complete = complete and got.complete
            queries.append(got.query)
            new = set(got.ids) - acc
            acc |= set(got.ids)
            frontier = sorted(new)
            if not frontier:
                break
        if not acc:
            diag = diagnose_empty(first_spec, self.backend)
            nearest = [f"{self.catalog.card_relation(f['rel'])} {f['direction']} -> {f['label']} ({f['n']})"
                       for f in diag.get("nearest") or []]
            diag["nearest"] = [{**f, "rel": self.catalog.card_relation(f["rel"])} for f in diag.get("nearest") or []]
            return E.empty(diag, nearest_text=nearest)
        ends = a.get("_targets") or []
        kind = to or (ends[0] if len(ends) == 1 else "mixed")
        rec = self.handles.put(kind, sorted(acc), complete=complete, total=None if complete else len(acc),
                               query=" ; ".join(queries),
                               origin={"tool": "expand", "from": a.get("from"), "relation": rel, "direction": d,
                                       "to_label": to, "depth": depth})
        out = {"ok": True, **self._view(rec)}
        opt = self.catalog.options(label, rel, d, kind) if label else []
        if opt:
            out["reading"] = opt[0].reading
        if not complete:
            out["warning"] = {"code": "partial", "detail": "the safety ceiling stopped the fetch",
                              "fix": "narrow the set (to_label, a smaller from) before expanding"}
        return out

    def _run_count(self, c: Call) -> dict[str, Any]:
        rec = self.handles.get(c.args["set"])
        return {"ok": True, "handle": rec.handle, "total": rec.total, "complete": rec.complete}

    def _run_set_op(self, c: Call) -> dict[str, Any]:
        rec = self.handles.set_op(c.args["op"], c.args["a"], c.args["b"])
        if self.backend is None:
            return {"ok": True, "handle": rec.handle, "kind": rec.kind, "total": rec.total, "complete": rec.complete}
        return {"ok": True, **self._view(rec)}

    def _run_not_expressible(self, c: Call) -> dict[str, Any]:
        rec = {"part": c.args["part"], "needs": c.args["needs"]}
        self.records.append(rec)
        return {"ok": True, "recorded": rec}

    def _not_yet(self, c: Call) -> dict[str, Any]:
        return E.refusal("invalid_request", f"{c.tool} is not available yet (it arrives in Step 9)",
                         "use one of the available tools: " + E.name_options(IMPLEMENTED),
                         [E.problem("tool", c.tool, list(IMPLEMENTED))])

    _run_filter = _run_aggregate = _run_group = _run_rank = _run_verify = _not_yet

    # ------------------------------------------------------------------ #

    def toolbox(self) -> ToolBox:
        """A runner ToolBox over these tools (``finish`` and ``ask_caller`` are the runner's own)."""
        box = ToolBox()
        for spec in self.catalog.specs("full"):
            name = spec["function"]["name"]
            if name in ("finish", "ask_caller"):
                continue
            box.add(spec, _bound(self, name))
        return box


def _bound(tools: Tools, name: str) -> Callable[..., dict[str, Any]]:
    def fn(**kw: Any) -> dict[str, Any]:
        return tools.call(name, kw)

    fn.__name__ = name
    return fn


def _toks(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", str(text).lower()) if len(w) >= 3]


def _cand(x: Any) -> dict[str, Any]:
    return {"id": x.entity_id, "label": x.label, "name": x.name, "score": x.score}


def build_toolbox(catalog: Catalog, backend: Any, handles: HandleStore, **kw: Any) -> tuple[ToolBox, Tools]:
    """The runner's ToolBox for a catalog, a backend and a run's handle store."""
    tools = Tools(catalog, backend, handles, **kw)
    return tools.toolbox(), tools


def backend_for(catalog: Catalog, client: Any, **kw: Any) -> Any:
    """An exact backend for ``client`` that speaks the store's relation names."""
    from utils.agent.exact import CypherBackend, GremlinBackend

    if hasattr(client, "submit"):
        return GremlinBackend(client, edge_label=catalog.model.edge_label, **kw)
    return CypherBackend(client, **kw)


__all__ = ["Refused", "Tools", "backend_for", "build_toolbox"]
