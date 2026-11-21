#!/usr/bin/env python3
"""The operator algebra as typed-planner step kinds (Era 2, Step 9, Phase G).

Everything here runs only behind ``ARIADNE_ALGEBRA_CORE`` (and, for reach,
shortest and the time ops, ``ARIADNE_ALGEBRA_EXTENDED``); with both off the
typed planner never calls into this module, so its prompt, its tool specs and
its step checking are byte-identical to before (``test_algebra_exposure.py``).

Three things:

1. **The step kinds** (:data:`CORE_KINDS`, :data:`EXTENDED_KINDS`). Each maps
   one-to-one onto a class of ``utils.specialists.algebra``; the planner writes
   the same id/graph/anchor/path fields it already knows plus a few per kind.
   Chaining is the existing ``from_step``.
2. **The prompt text** (:func:`system_section`, :func:`catalog_section`),
   generated from the validator's own operator tables and the cards' value
   types and properties. No graph is named here.
3. **The check** (:func:`check_algebra_step`): parse the raw step into the
   internal form with the typed planner's own anchor resolution and coercion,
   then run ``algebra.validate.check`` against the card. An ``InvalidOp``
   becomes the planner's refusal envelope, so the repair turn reads what is
   allowed instead (Step 8's teaching errors). :func:`check_today_step` does the
   same for today's five kinds (Phase G item 3).

Anchors in the internal form carry the **public** ids the planner works in; the
runtime (``utils.specialists.algebra.runtime``) maps them to stored ids.
"""

from __future__ import annotations

import json
from typing import Any

from utils.specialists.algebra.switches import core_on, extended_on

#: Operators 1-7 as step kinds (``ARIADNE_ALGEBRA_CORE``).
CORE_KINDS = ("filter", "typescan", "aggregate", "rank", "verify", "groupby", "union", "absence")
#: Operator 8 (``ARIADNE_ALGEBRA_EXTENDED``).
EXTENDED_KINDS = ("reach", "shortest")


def kinds() -> tuple[str, ...]:
    """The algebra step kinds the switches expose now (empty when off)."""
    if not core_on():
        return ()
    return CORE_KINDS + (EXTENDED_KINDS if extended_on() else ())


def condition_ops(vtype: str) -> tuple[str, ...]:
    """The condition ops a card value type takes now: the validator's, minus time unless EXTENDED."""
    from utils.specialists.algebra.base import TIME
    from utils.specialists.algebra.validate import allowed_ops

    ops = allowed_ops(vtype)
    return ops if extended_on() else tuple(o for o in ops if o not in TIME)


# --------------------------------------------------------------------------- #
# The prompt
# --------------------------------------------------------------------------- #


def system_section(catalogs: dict[str, Any]) -> str:
    """The operator kinds, for the system prompt. Empty when CORE is off."""
    if not core_on():
        return ""
    from utils.specialists.algebra.aggregate import FNS as AGG_FNS
    from utils.specialists.algebra.base import COMPARE
    from utils.specialists.algebra.groupby import FNS as GROUP_FNS
    from utils.specialists.algebra.path import DEFAULT_DEPTH
    from utils.specialists.algebra.validate import PATH_MAX_DEPTH

    ext = extended_on()
    vtypes = sorted({p.vtype for c in catalogs.values() for lab in c.model.labels.values()
                     for p in lab.properties.values()})
    lines = [
        "",
        "OPERATOR STEPS. Besides the kinds above, a step may be one of these. Each runs exactly as "
        "written; use one only when the question asks for that operation (a filter, a count or other "
        "aggregate, a ranking, a yes/no link check, a per-entity value, an either/or, an absence"
        + (", a reachability or a shortest path" if ext else "") + ").",
        "A set (the input of most of them) is written with the fields of an expand step: an \"anchor\" "
        "with an optional \"path\" (the entities at the end of the path), or \"from_step\": \"<id>\" "
        "(what an earlier step found; give its label as \"anchor_label\"), or only \"anchor_label\" "
        "(every entity of that label). \"where\" keeps the members that meet every condition.",
        "When the question names an entity (by id or by name), anchor on it (\"anchor\" with a \"path\"); "
        "\"typescan\" and a filter over a whole label are for \"every X that ...\", never to look up one "
        "named entity. \"union\" \"parts\" may name earlier steps: \"parts\": [\"q1\", \"q2\"].",
        "- \"filter\": the members of a set that meet \"where\".",
        "- \"typescan\": every entity of \"anchor_label\" that meets \"where\", with the exact total.",
        f"- \"aggregate\": one value over a set: \"fn\" is one of {', '.join(AGG_FNS)}; every fn but "
        "count needs \"property\".",
        "- \"rank\": the first \"k\" members of a set by \"property\", or by how many entities \"by_path\" "
        "(a path) reaches from each; \"order\" is \"desc\" (default) or \"asc\"; ties at the cut are kept.",
        "- \"verify\": whether the anchor (one id) is linked to \"other\" ({\"id\": \"<id>\"}); optionally "
        "only by \"relation\", with \"direction\" out, in or both.",
        f"- \"groupby\": for each member of a set (usually \"anchor_label\" with an optional \"where\"), "
        f"walk \"path\" and compute \"fn\" ({', '.join(GROUP_FNS)}; default count) over the entities "
        "reached (\"property\" for all but count), counting only those meeting \"end_where\". "
        "\"having\": {\"op\": \">\", \"value\": 10} keeps the members whose value compares; \"order\" and "
        "\"k\" rank them. A member that reaches nothing is kept, with count 0.",
        "- \"union\": the members of any of \"parts\", a list of sets.",
        "- \"absence\": the members of a set with no \"lacks\" link ({\"relation\", \"direction\", "
        "\"target_label\", \"where\"}), or without the property \"lacks_property\".",
    ]
    if ext:
        lines += [
            f"- \"reach\": every entity reachable from the anchor in 1 to \"depth\" steps (default "
            f"{DEFAULT_DEPTH}, at most {PATH_MAX_DEPTH}) over \"relations\": [{{\"relation\": "
            "\"<relation>\", \"direction\": \"out|in|both\"}] (omit for every relation).",
            "- \"shortest\": every shortest path from the anchor to \"other\", over \"relations\", "
            "within \"depth\".",
        ]
    lines.append("A condition is {\"property\": \"<property>\", \"op\": \"<op>\", \"value\": <value>}. "
                 "The ops a property takes depend on its type:")
    for vt in vtypes:
        lines.append(f"- {vt}: {', '.join(condition_ops(vt))}")
    tail = (f"\"present\" and \"missing\" take no value. \"size\"{' and \"year\"' if ext else ''} compare a "
            f"number, with \"cmp\" one of {', '.join(COMPARE)}.")
    if ext:
        tail += " \"before\"/\"after\" take a date YYYY-MM-DD; \"between\" takes [\"<from>\", \"<to>\"]."
    lines.append(tail + " An entity that lacks a property never meets a condition on it (\"missing\" "
                 "asks for that). Write values as the graph stores them.")
    lines.append("Example: {\"id\": \"q1\", \"graph\": \"<graph>\", \"kind\": \"aggregate\", \"anchor\": "
                 "{\"id\": \"<entity id>\"}, \"path\": [{\"relation\": \"<relation>\", \"direction\": \"out\", "
                 "\"target_label\": \"<Label>\"}], \"fn\": \"count\"}")
    return "\n".join(lines) + "\n"


def catalog_section(catalogs: dict[str, Any], mode: str) -> str:
    """Property names and types per graph, for the lazy prompt (the full card lists them already)."""
    if not core_on() or mode != "lazy":
        return ""
    parts = []
    for ds in sorted(catalogs):
        props: dict[str, set[str]] = {}
        for lab in catalogs[ds].model.labels.values():
            for p in lab.properties.values():
                props.setdefault(p.name, set()).add(p.vtype)
        shown = ", ".join(f"{n} ({'/'.join(sorted(t))})" for n, t in sorted(props.items()))
        parts.append(f"{ds}: {shown}")
    return "\n\nPROPERTIES (for conditions; describe a label to see which it has):\n" + "\n".join(parts)


# --------------------------------------------------------------------------- #
# Checking an algebra step
# --------------------------------------------------------------------------- #


def _ids_in(node: Any) -> list[str]:
    from utils.specialists.algebra.base import Anchors

    out: list[str] = []

    def walk(x: Any) -> None:
        import dataclasses

        if isinstance(x, Anchors):
            out.extend(i for i in x.ids if i not in out)
        elif dataclasses.is_dataclass(x) and not isinstance(x, type):
            for f in dataclasses.fields(x):
                walk(getattr(x, f.name))
        elif isinstance(x, (tuple, list)):
            for y in x:
                walk(y)

    walk(node)
    return out


def _first_label(node: Any) -> str:
    """The label a step is "about", for ``TypedStep.anchor_label`` (entities, seed harvest)."""
    from utils.specialists.algebra.base import Anchors, FromStep, Scan
    from utils.specialists.algebra.typescan import TypeScan

    found: list[str] = []

    def walk(x: Any) -> None:
        import dataclasses

        if found:
            return
        if isinstance(x, FromStep) and x.labels:
            found.append(x.labels[0])
        elif isinstance(x, (Anchors, Scan, TypeScan)) and x.label:
            found.append(x.label)
        elif dataclasses.is_dataclass(x) and not isinstance(x, type):
            for f in dataclasses.fields(x):
                walk(getattr(x, f.name))
        elif isinstance(x, (tuple, list)):
            for y in x:
                walk(y)

    walk(node)
    return found[0] if found else ""


def _teach(sid: str, exc: Exception, card: Any = None) -> dict[str, Any]:
    """An ``InvalidOp`` as the planner's refusal envelope.

    For a hop the card does not allow from where the walk is, the fix names the
    hop and lists the relations (direction and target) that do leave the labels
    the walk has reached there.
    """
    import re

    from utils.agent import errors as E

    where = str(getattr(exc, "where", "step"))
    msg = str(exc)
    fix = "change the step as this says; it lists what the card allows here"
    hop = re.search(r"(hops|by_path|path|lacks)\[(\d+)\]", where)
    at = re.search(r"(?:joins none of|from) \[([^\]]*)\]", msg)
    if card is not None and hop and at:
        labels = [x.strip().strip("'\"") for x in at.group(1).split(",") if x.strip()]
        opts = sorted({f"{o.relation} {o.direction} -> {o.target}" for lab in labels
                       for o in getattr(card, "options", lambda _l: [])(lab)})
        n = int(hop.group(2)) + 1
        fix = (f"hop {n} starts from {', '.join(labels)}; the relations that leave there are: "
               + ("; ".join(opts) if opts else "none") + f". Choose hop {n} from these, or name a "
               f"target_label on hop {n - 1} so the walk is at a label that has the relation you want"
               if n > 1 else f"hop 1 starts from {', '.join(labels)}; the relations that leave there are: "
               + ("; ".join(opts) if opts else "none"))
    return E.refusal("invalid_request", f"step {sid}: {msg}", fix, [E.problem(where, None, [])])


def check_algebra_step(raw: dict[str, Any], sid: str, kind: str, graph: str, ctx: Any,
                       earlier: dict[str, Any], log: Any, out: Any) -> Any:
    """Parse and validate one algebra step; returns ``out`` (a ``StepCheck``) with a step or refusals."""
    from utils.agent.tools import Refused
    from utils.specialists.algebra.ir import to_dict
    from utils.specialists.algebra.validate import InvalidOp, check
    from utils.specialists.signals import ALGEBRA_KIND, TypedStep

    p = _Parser(raw, sid, graph, ctx, earlier, log, out)
    try:
        node = p.build(kind)
        try:
            check(node, p.card)
            labels = _result_labels(node, p.card)
        except InvalidOp as exc:
            raise Refused(_teach(sid, exc, p.card)) from None
        spec = {"op": kind, "ir": to_dict(node), "labels": labels}
        out.step = TypedStep(kind=ALGEBRA_KIND, anchor_label=_first_label(node),
                             anchor_ids=tuple(_ids_in(node)),
                             algebra=json.dumps(spec, sort_keys=True, ensure_ascii=False))
        out.fixes = list(log.fixes)
        return out
    except Refused as r:
        out.refusals.append(r.envelope)
        out.fixes = list(log.fixes)
        return out


def _result_labels(node: Any, card: Any) -> list[str]:
    """The labels a node result may hold (empty for a scalar or path result)."""
    from utils.specialists.algebra.base import Nodes
    from utils.specialists.algebra.groupby import GroupBy
    from utils.specialists.algebra.rank import Rank
    from utils.specialists.algebra.validate import check

    if isinstance(node, Nodes):
        return sorted(check(node.of, card) or ())
    from utils.specialists.algebra.base import Expand

    if isinstance(node, Expand):
        # every prefix's end (amendment 3): each hop's reached labels
        from utils.specialists.algebra.validate import check_hop

        here, out = check(node.walk.start, card), set()
        for i, h in enumerate(node.walk.hops):
            here = check_hop(card, here, h, f"hops[{i}]")
            out |= here
        if node.walk.depth > 1:
            out |= check(node.walk, card)
        return sorted(out)
    if isinstance(node, Rank):
        return sorted(check(node.of, card) or ())
    if isinstance(node, GroupBy):
        return sorted(check(node.members, card) or ())
    return []


class _Parser:
    """The raw JSON of one algebra step, into the internal form (public ids)."""

    def __init__(self, raw: dict[str, Any], sid: str, graph: str, ctx: Any, earlier: dict[str, Any],
                 log: Any, out: Any) -> None:
        self.raw, self.sid, self.graph, self.ctx, self.earlier, self.log, self.out = (
            raw, sid, graph, ctx, earlier, log, out)
        self.cat = ctx.catalogs[graph]
        self.card = self.cat.model

    # -- envelopes -----------------------------------------------------------

    def _refuse(self, detail: str, field_: str, got: Any, options: list[Any], what: str | None = None,
                hint: str = "", code: str = "invalid_request") -> Exception:
        from utils.agent.tools import Refused
        from utils.planner.typed import _env

        return Refused(_env(code, f"step {self.sid}: {detail}", field_, got, options, what=what, hint=hint))

    # -- names ------------------------------------------------------------

    def label(self, value: Any, field_: str) -> str:
        from utils.agent.coerce import Ambiguous, NoMatch, coerce_name

        try:
            return coerce_name(value, self.cat.labels(), field_, self.log)
        except (NoMatch, Ambiguous):
            raise self._refuse(f"{field_} {value!r} is not a label of {self.graph}", field_, value,
                               self.cat.labels(), what="label", code="not_in_card") from None

    def relation(self, value: Any, field_: str) -> str:
        from utils.agent.coerce import Ambiguous, NoMatch, coerce_name

        try:
            return coerce_name(value, self.cat.relations(), field_, self.log)
        except (NoMatch, Ambiguous):
            raise self._refuse(f"{field_} {value!r} is not a relation of {self.graph}", field_, value,
                               self.cat.relations(), what="relation", code="not_in_card") from None

    def enum(self, value: Any, options: tuple[str, ...], field_: str, default: str | None = None) -> str:
        from utils.agent.coerce import Ambiguous, NoMatch, coerce_enum

        if value in (None, "") and default is not None:
            return default
        try:
            return coerce_enum(value, options, field_, self.log)
        except (NoMatch, Ambiguous):
            raise self._refuse(f"{field_} {value!r} is not one of {list(options)}", field_, value,
                               list(options), what=field_) from None

    def integer(self, value: Any, field_: str, default: int | None = None) -> int:
        from utils.agent.coerce import NoMatch, coerce_int

        if value in (None, "") and default is not None:
            return default
        try:
            return coerce_int(value, field_, self.log)
        except NoMatch:
            raise self._refuse(f"{field_} {value!r} is not an integer", field_, value, ["an integer"],
                               what=field_) from None

    def prop(self, value: Any, labels: frozenset[str], field_: str) -> str:
        from utils.agent.coerce import Ambiguous, NoMatch, coerce_name

        props = sorted({p for lab in labels for p in self.cat.label_properties(lab)})
        try:
            return coerce_name(value, props, field_, self.log)
        except (NoMatch, Ambiguous):
            raise self._refuse(f"{value!r} is not a property of {sorted(labels)}", field_, value,
                               props or ["no property"], what=f"a property of {'/'.join(sorted(labels))}",
                               code="not_in_card") from None

    # -- anchors and sets ----------------------------------------------------

    def _sub(self, part: dict[str, Any], kind: str, field_: str) -> Any:
        """Resolve an anchor (and path) with the typed planner's own step check."""
        from utils.agent.tools import Refused
        from utils.planner.typed import _check_step

        sub = {"id": self.sid, "graph": self.graph, "kind": kind, "anchor": part.get("anchor")}
        for k in ("anchor_label", "path", "relation", "direction", "target_label", "depth"):
            if part.get(k) is not None:
                sub[k] = part[k]
        if isinstance(sub["anchor"], dict) and sub["anchor"].get("from_step"):
            sub["anchor"] = {k: v for k, v in sub["anchor"].items() if k != "from_step"}
        c = _check_step(sub, 0, self.ctx, {})
        for f in c.fixes:
            self.log.add(f"{field_}.{f['field']}", f["from"], f["to"], f["filled_by"])
        if c.refusals:
            raise Refused(c.refusals[0])
        if c.join_key:
            raise self._refuse(f"{field_}: an operator step anchors on ids of {self.graph}; this id belongs to "
                               "another graph", f"{field_}.id", part.get("anchor"),
                               ["an id of " + self.graph], what="anchor.id",
                               hint="bridge first with an expand step, then start this step from it "
                                    "(\"from_step\")")
        return c.step

    def anchors(self, part: Any, field_: str, one: bool = False) -> Any:
        from utils.specialists.algebra.base import Anchors

        if isinstance(part, str):
            part = {"id": part}
        if not isinstance(part, dict):
            raise self._refuse(f"{field_} must be an entity, {{\"id\": ...}} or {{\"name\": ..., \"label\": ...}}",
                               field_, part, ["id", "name"], what=field_)
        holder = {"anchor": {k: v for k, v in part.items() if k in ("id", "name", "label")},
                  "anchor_label": part.get("label")}
        st = self._sub(holder, "describe", field_)
        if one and len(st.anchor_ids) != 1:
            raise self._refuse(f"{field_} takes exactly one entity", f"{field_}.id", list(st.anchor_ids),
                               ["one id"], what=f"{field_}.id")
        return Anchors(tuple(st.anchor_ids), st.anchor_label)

    def from_step(self, part: dict[str, Any], fs: Any) -> Any:
        from utils.planner.join_keys import resolve_join_key
        from utils.specialists.algebra.base import FromStep

        fs = str(fs)
        prod = self.earlier.get(fs)
        if prod is None or not prod.ok:
            raise self._refuse(f"from_step {fs!r} is not an earlier accepted step", "from_step", fs,
                               [k for k, v in self.earlier.items() if v.ok] or ["an anchor"], what="from_step")
        if self.out.from_step not in (None, fs):
            # A union over several earlier steps: every producer seeds this step.
            extra = getattr(self.out, "from_steps", None) or [self.out.from_step]
            if fs not in extra:
                extra.append(fs)
            self.out.from_steps = extra
        anchor = part.get("anchor") if isinstance(part.get("anchor"), dict) else {}
        label_raw = part.get("anchor_label") or anchor.get("label")
        if prod.graph != self.graph:
            key = resolve_join_key(self.ctx.cards[prod.graph], self.ctx.cards[self.graph])
            if key is None or not any(e.dataset == prod.graph and e.produces for e in key.endpoints):
                raise self._refuse(f"no declared join key carries values from {prod.graph} to {self.graph}",
                                   "from_step", fs, ["anchor.id"], what="from_step")
            if not label_raw:
                raise self._refuse("from_step on another graph needs the label its values are here",
                                   "anchor_label", None, self.cat.labels(), what="anchor_label")
            self.out.join_key = key.name
        label = self.label(label_raw, "anchor_label") if label_raw else _end_label(prod)
        if not label:
            raise self._refuse(f"step {fs} ends at several labels; name the one to start from",
                               "anchor_label", None, self.cat.labels(), what="anchor_label")
        if self.out.from_step is None:
            self.out.from_step = fs
        return FromStep(fs, (label,))

    def nodeset(self, part: dict[str, Any], field_: str = "step", conds: bool = True) -> Any:
        """A set, from ``from_step``, an anchor (and path), or a label; then its ``where``."""
        from utils.specialists.algebra.base import Anchors, Hop, Scan, Walk
        from utils.specialists.algebra.filters import Where
        from utils.specialists.algebra.typescan import TypeScan
        from utils.specialists.algebra.validate import InvalidOp, check
        from utils.agent.tools import Refused

        if isinstance(part, str) and part.strip():
            name = part.strip()
            if name in self.earlier and self.earlier[name].ok:
                self.log.add(field_, part, {"from_step": name}, "step_id_as_set")
                part = {"from_step": name}
            else:
                self.log.add(field_, part, {"anchor": {"id": name}}, "id_as_set")
                part = {"anchor": {"id": name}}
        if not isinstance(part, dict):
            ok = [k for k, v in self.earlier.items() if v.ok]
            ex = (f"\"parts\": [\"{ok[0]}\", \"{ok[1]}\"]" if len(ok) > 1 else
                  f"{{\"from_step\": \"{ok[0]}\"}}" if ok else
                  "{\"anchor\": {\"id\": \"<id>\"}, \"path\": [...]}")
            raise self._refuse(f"{field_} must be a set: an earlier step's id (\"q1\"), {{\"from_step\": \"q1\"}}, "
                               "{\"anchor\": ..., \"path\": [...]} or {\"anchor_label\": ..., \"where\": [...]}",
                               field_, part, ["\"<step id>\"", "from_step", "anchor", "anchor_label"],
                               what="a set", hint="for example " + ex)
        anchor = part.get("anchor")
        fs = part.get("from_step") or (anchor.get("from_step") if isinstance(anchor, dict) else None)
        if fs:
            node: Any = self.from_step(part, fs)
        elif anchor not in (None, "", {}, []):
            if isinstance(anchor, str):
                part = {**part, "anchor": {"id": anchor}}
            walks = bool(part.get("path") or part.get("relation"))
            st = self._sub(part, "expand" if walks else "describe", field_)
            start = Anchors(tuple(st.anchor_ids), st.anchor_label)
            node = (Walk(start, tuple(Hop(h.relation, h.direction, h.target_label) for h in st.hops), st.depth)
                    if st.hops else start)
        elif part.get("anchor_label") or part.get("label"):
            node = Scan(self.label(part.get("anchor_label") or part.get("label"), "anchor_label"))
        else:
            raise self._refuse(f"{field_} needs a set: an anchor (with a path), from_step, or anchor_label",
                               field_, None, ["anchor", "from_step", "anchor_label"], what="a set")
        where = part.get("where") if conds else None
        if where in (None, [], {}):
            return node
        try:
            labels = check(node, self.card)
        except InvalidOp as exc:
            raise Refused(_teach(self.sid, exc, self.card)) from None
        cs = self.conds(where, labels, "where")
        if isinstance(node, Scan):
            return TypeScan(node.label, cs)
        return Where(node, cs)

    # -- conditions ----------------------------------------------------------

    def conds(self, raw: Any, labels: frozenset[str], field_: str) -> tuple[Any, ...]:
        from utils.specialists.algebra.base import Cond

        if isinstance(raw, dict):
            raw = [raw]
        if not isinstance(raw, list):
            raise self._refuse(f"{field_} must be a list of conditions", field_, raw,
                               ["[{\"property\": ..., \"op\": ..., \"value\": ...}]"], what=field_)
        out = []
        for i, c in enumerate(raw):
            f = f"{field_}[{i}]"
            if not isinstance(c, dict):
                raise self._refuse(f"{f} is not an object", f, c, ["property", "op", "value"], what="a condition")
            prop = self.prop(c.get("property"), labels, f"{f}.property")
            types = {self.card.labels[lab].properties[prop].vtype for lab in labels
                     if lab in self.card.labels and prop in self.card.labels[lab].properties}
            vtype = next(iter(types)) if len(types) == 1 else "string"
            ops = condition_ops(vtype)
            op = self.enum(c.get("op"), ops, f"{f}.op", default="=")
            cmp_ = None
            value = c.get("value")
            if op in ("present", "missing"):
                value = None
            elif op in ("size", "year"):
                from utils.specialists.algebra.base import COMPARE

                cmp_ = self.enum(c.get("cmp"), COMPARE, f"{f}.cmp", default="=")
                value = self.integer(value, f"{f}.value")
            elif op == "between":
                value = tuple(str(v) for v in value) if isinstance(value, (list, tuple)) else value
            else:
                value = self.value(value, vtype, op, labels, prop, f"{f}.value")
            out.append(Cond(prop, op, value, cmp_))
        return tuple(out)

    def value(self, value: Any, vtype: str, op: str, labels: frozenset[str], prop: str, field_: str) -> Any:
        from utils.agent.coerce import Ambiguous, NoMatch, coerce_name
        from utils.planner.typed import _observed_values
        from utils.specialists.algebra.validate import NUMERIC_TYPES

        if value is None or value == "":
            raise self._refuse(f"{field_} is missing", field_, value, [f"a {vtype} value"], what=field_)
        if vtype in NUMERIC_TYPES:
            if isinstance(value, str):
                try:
                    value = float(value) if "." in value else int(value)
                except ValueError:
                    raise self._refuse(f"{field_} {value!r} is not a number", field_, value, ["a number"],
                                       what=field_) from None
            return value
        if vtype == "boolean":
            if isinstance(value, str) and value.strip().lower() in ("true", "false"):
                return value.strip().lower() == "true"
            return value
        value = str(value)
        if op in ("=", "<>", "contains", "not_contains"):
            vocab = sorted({v for lab in labels for v in _observed_values(self.graph, lab, prop)})
            if vocab and value not in vocab:
                try:
                    value = coerce_name(value, vocab, field_, self.log)
                except (NoMatch, Ambiguous):
                    pass  # the observed values are a sample: an unseen value is not refused
        return value

    # -- hops ---------------------------------------------------------------

    def hops(self, raw: Any, start: frozenset[str], field_: str, dirs: tuple[str, ...] = ("out", "in")) -> tuple:
        from utils.specialists.algebra.base import Hop
        from utils.specialists.algebra.validate import InvalidOp, check_hop
        from utils.agent.tools import Refused

        if isinstance(raw, dict):
            raw = [raw]
        if not isinstance(raw, list) or not raw:
            raise self._refuse(f"{field_} needs at least one hop", field_, raw,
                               ["[{\"relation\": ..., \"direction\": ..., \"target_label\": ...}]"], what=field_)
        out = []
        here = start
        for i, h in enumerate(raw):
            f = f"{field_}[{i}]"
            if not isinstance(h, dict):
                raise self._refuse(f"{f} is not an object", f, h, ["relation", "direction", "target_label"],
                                   what="a hop")
            rel = self.relation(h.get("relation"), f"{f}.relation")
            d = h.get("direction")
            if d in (None, ""):
                seen = {o.direction for lab in here for o in self.cat.options(lab, rel)}
                if len(seen) == 1:
                    d = next(iter(seen))
                    self.log.add(f"{f}.direction", None, d, "option_rules")
            d = self.enum(d, dirs, f"{f}.direction")
            target = self.label(h["target_label"], f"{f}.target_label") if h.get("target_label") else ""
            hop = Hop(rel, d, target)
            try:
                reach = check_hop(self.card, here, hop, f)
            except InvalidOp as exc:
                raise Refused(_teach(self.sid, exc, self.card)) from None
            if h.get("where"):
                eprops = self.card.relations[rel].properties
                hop = Hop(rel, d, target, self._edge_conds(h["where"], eprops, f"{f}.where"))
            out.append(hop)
            here = reach
        return tuple(out)

    def _edge_conds(self, raw: Any, eprops: dict[str, Any], field_: str) -> tuple:
        from utils.specialists.algebra.base import Cond

        if not eprops:
            raise self._refuse(f"{field_}: this relation carries no property to filter on", field_, raw,
                               ["no where"], what=field_)
        if isinstance(raw, dict):
            raw = [raw]
        out = []
        for i, c in enumerate(raw if isinstance(raw, list) else []):
            prop = self.enum(c.get("property"), tuple(sorted(eprops)), f"{field_}[{i}].property")
            vtype = eprops[prop].vtype
            op = self.enum(c.get("op"), condition_ops(vtype), f"{field_}[{i}].op", default="=")
            out.append(Cond(prop, op, c.get("value"), c.get("cmp")))
        return tuple(out)

    def rels(self, raw: Any, field_: str) -> tuple:
        if raw in (None, [], ""):
            return ()
        if isinstance(raw, dict):
            raw = [raw]
        out = []
        for i, r in enumerate(raw if isinstance(raw, list) else [raw]):
            if isinstance(r, str):
                r = {"relation": r}
            rel = self.relation((r or {}).get("relation"), f"{field_}[{i}].relation")
            d = self.enum((r or {}).get("direction"), ("out", "in", "both"), f"{field_}[{i}].direction",
                          default="both")
            out.append((rel, d))
        return tuple(out)

    # -- the kinds -----------------------------------------------------------

    def build(self, kind: str) -> Any:
        node = self._build(kind)
        if kind in ("filter", "typescan"):
            self._refuse_lookup(node)
        return node

    def _refuse_lookup(self, node: Any) -> None:
        """A whole-label scan pinned to one entity by its identifying property: anchor on it instead."""
        from utils.specialists.algebra.base import Nodes
        from utils.specialists.algebra.typescan import TypeScan

        ts = node.of if isinstance(node, Nodes) else None
        if not isinstance(ts, TypeScan):
            return
        lab = self.card.labels.get(ts.label)
        key = getattr(lab, "key", "") or ""
        pins = [c for c in ts.conds if c.op == "=" and isinstance(c.value, str)
                and (c.prop in ("name", "id", key) or c.prop.endswith("_id"))]
        if not pins:
            return
        c = pins[0]
        cands = [c.value]
        other = {x.prop: x.value for x in ts.conds if x is not c and x.op == "="}
        if "taxonomy_name" in other or len(other) == 1:
            from utils.kg_builder.merge import taxonomy_public_id

            for v in other.values():
                pub = taxonomy_public_id(str(v), c.value)
                if pub and pub not in cands:
                    cands.insert(0, pub)
        anchor = None
        for cand in cands:
            if self.ctx.id_labels(self.graph, cand):
                anchor = f"\"anchor\": {{\"id\": \"{cand}\"}}"
                break
            if self.ctx.foreign_id(self.graph, cand):
                anchor = f"\"anchor\": {{\"id\": \"{cand}\"}}, \"anchor_label\": \"{ts.label}\" (an id the join key bridges)"
                break
        if anchor is None:
            anchor = (f"\"anchor\": {{\"name\": \"{c.value}\", \"label\": \"{ts.label}\"}}" if c.prop == "name"
                      else f"\"anchor\": {{\"id\": \"{c.value}\"}}")
        raise self._refuse(
            f"a {'typescan' if self.raw.get('kind') == 'typescan' else 'filter'} over every {ts.label} with "
            f"{c.prop} = {c.value!r} looks up one named entity",
            "where", [c.prop, c.value], [anchor], what="the entity as the anchor",
            hint=f"anchor the step on it instead ({anchor}) and add the path to what the question asks for; "
                 f"scan a label only for \"every {ts.label} that ...\"")

    def _build(self, kind: str) -> Any:
        from utils.specialists.algebra.aggregate import FNS as AGG_FNS, Aggregate
        from utils.specialists.algebra.base import Cond, Hop, Nodes, Scan
        from utils.specialists.algebra.edges import Having, Union_
        from utils.specialists.algebra.filters import Where
        from utils.specialists.algebra.groupby import FNS as GROUP_FNS, GroupBy
        from utils.specialists.algebra.path import DEFAULT_DEPTH, Reach, Shortest
        from utils.specialists.algebra.rank import Rank
        from utils.specialists.algebra.typescan import TypeScan
        from utils.specialists.algebra.validate import check
        from utils.specialists.algebra.verify import Verify

        raw = self.raw
        if kind == "filter":
            if raw.get("where") in (None, [], {}):
                raise self._refuse("a filter needs \"where\": one or more conditions", "where", None,
                                   ["[{\"property\": ..., \"op\": ..., \"value\": ...}]"], what="where",
                                   hint="or use kind \"expand\" for the whole set")
            return Nodes(self.nodeset(raw))
        if kind == "typescan":
            if not (raw.get("anchor_label") or raw.get("label")):
                raise self._refuse("a typescan needs the label to scan", "anchor_label", None, self.cat.labels(),
                                   what="anchor_label")
            node = self.nodeset({k: v for k, v in raw.items() if k in ("anchor_label", "label", "where")})
            return Nodes(TypeScan(node.label, ()) if isinstance(node, Scan) else node)
        if kind == "aggregate":
            base = self.nodeset(raw)
            fn = self.enum(raw.get("fn"), AGG_FNS, "fn", default="count")
            prop = None
            if fn != "count":
                if raw.get("property") in (None, ""):
                    raise self._refuse(f"{fn} needs \"property\"", "property", None,
                                       sorted({p for lab in check(base, self.card) for p in
                                               self.cat.label_properties(lab)}), what="property")
                prop = self.prop(raw.get("property"), check(base, self.card), "property")
            return Aggregate(base, fn, prop)
        if kind == "rank":
            base = self.nodeset(raw)
            order = self.enum(raw.get("order"), ("desc", "asc"), "order", default="desc")
            k = self.integer(raw.get("k"), "k")
            if raw.get("by_path"):
                return Rank(base, order, k, None, self.hops(raw["by_path"], check(base, self.card), "by_path"))
            if raw.get("property") in (None, ""):
                raise self._refuse("a rank needs \"property\" or \"by_path\"", "property", None,
                                   ["property", "by_path"], what="the ranking key")
            return Rank(base, order, k, self.prop(raw["property"], check(base, self.card), "property"))
        if kind == "verify":
            a = self.anchors(raw.get("anchor"), "anchor", one=True)
            b = self.anchors(raw.get("other"), "other", one=True)
            rel = self.relation(raw["relation"], "relation") if raw.get("relation") else None
            d = (self.enum(raw.get("direction"), ("out", "in", "both"), "direction")
                 if rel and raw.get("direction") else None)
            return Verify(a, b, rel, d)
        if kind == "groupby":
            members = self.nodeset({k: v for k, v in raw.items()
                                    if k in ("anchor", "anchor_label", "label", "from_step", "where")})
            hops = self.hops(raw.get("path"), check(members, self.card), "path")
            fn = self.enum(raw.get("fn"), GROUP_FNS, "fn", default="count")
            ends = frozenset([hops[-1].target]) if hops[-1].target else None
            if ends is None:
                from utils.specialists.algebra.validate import check_walk

                ends = check_walk(self.card, check(members, self.card), hops, 1, "path")
            prop = self.prop(raw.get("property"), ends, "property") if fn != "count" else None
            having = None
            if raw.get("having") not in (None, {}, []):
                h = raw["having"]
                op, val = (h.get("op"), h.get("value")) if isinstance(h, dict) else (list(h) + [None, None])[:2]
                from utils.specialists.algebra.base import COMPARE

                op = self.enum(op, COMPARE, "having.op", default="=")
                if isinstance(val, str):
                    try:
                        val = float(val) if "." in val else int(val)
                    except ValueError:
                        raise self._refuse("having.value must be a number", "having.value", val, ["a number"],
                                           what="having.value") from None
                having = (op, val)
            order = self.enum(raw.get("order"), ("desc", "asc"), "order") if raw.get("order") else None
            k = self.integer(raw.get("k"), "k") if raw.get("k") not in (None, "") else None
            if k is not None and order is None:
                order = "desc"
                self.log.add("order", None, "desc", "default")
            end = self.conds(raw["end_where"], ends, "end_where") if raw.get("end_where") else ()
            return GroupBy(members, hops, fn, prop, having, order, k, end)
        if kind == "union":
            parts = raw.get("parts")
            if not isinstance(parts, list) or len(parts) < 2:
                raise self._refuse("a union needs \"parts\": two or more sets", "parts", parts,
                                   ["[{set}, {set}]"], what="parts")
            return Nodes(Union_(tuple(self.nodeset(p, f"parts[{i}]") for i, p in enumerate(parts))))
        if kind == "absence":
            base = self.nodeset(raw)
            if raw.get("lacks_property"):
                p = self.prop(raw["lacks_property"], check(base, self.card), "lacks_property")
                return Nodes(Where(base, (Cond(p, "missing"),)))
            lacks = raw.get("lacks")
            if not isinstance(lacks, dict):
                raise self._refuse("an absence needs \"lacks\" (a link) or \"lacks_property\"", "lacks", lacks,
                                   ["lacks", "lacks_property"], what="what the members lack")
            hop = self.hops([{k: v for k, v in lacks.items() if k != "where"}], check(base, self.card), "lacks")[0]
            conds: tuple = ()
            if lacks.get("where"):
                from utils.specialists.algebra.validate import check_hop

                conds = self.conds(lacks["where"], check_hop(self.card, check(base, self.card), hop, "lacks"),
                                   "lacks.where")
            return Nodes(Having(base, hop, False, conds))
        if kind == "reach":
            start = self.anchors(raw.get("anchor"), "anchor")
            return Nodes(Reach(start, self.rels(raw.get("relations"), "relations"),
                               self.integer(raw.get("depth"), "depth", default=DEFAULT_DEPTH)))
        if kind == "shortest":
            a = self.anchors(raw.get("anchor"), "anchor", one=True)
            b = self.anchors(raw.get("other"), "other", one=True)
            return Shortest(a, b, self.rels(raw.get("relations"), "relations"),
                            self.integer(raw.get("depth"), "depth", default=DEFAULT_DEPTH))
        raise self._refuse(f"kind {kind!r} is not an operator step", "kind", kind, list(kinds()), what="kind")


def check_step_from_algebra(raw: dict[str, Any], sid: str, kind: str, graph: str, ctx: Any, prod: Any,
                            log: Any, out: Any) -> Any:
    """Today's step kind starting from an operator step on the same graph, as an algebra step.

    ``expand`` -> ``Expand(Walk(FromStep, hops, depth, last_conds))``, ``count`` ->
    ``Count(Walk(...))``, ``describe`` -> the producer's nodes (``Nodes(FromStep)``).
    The walk starts from the producer's result labels and runs through the same
    ``FromStep`` seed path as an operator-step chain. Only reachable when an
    algebra switch is on, since only then can a producer be an operator step.
    """
    from utils.agent import errors as E
    from utils.agent.tools import Refused
    from utils.specialists.algebra.base import Cond, Count, Expand, FromStep, Nodes, Walk
    from utils.specialists.algebra.ir import to_dict
    from utils.specialists.algebra.validate import InvalidOp, check
    from utils.specialists.signals import ALGEBRA_KIND, TypedStep

    p = _Parser(raw, sid, graph, ctx, {prod.id: prod}, log, out)
    try:
        if kind not in ("expand", "count", "describe"):
            raise Refused(E.refusal(
                "invalid_request", f"step {sid}: a {kind} step cannot start from step {prod.id}, an operator step",
                f"start an expand (with a path), count or describe step from {prod.id}, or an operator step "
                f"(filter, aggregate, rank, groupby, absence) with \"from_step\": \"{prod.id}\"",
                [E.problem("kind", kind, ["expand", "count", "describe"])]))
        labels = tuple((prod.step.algebra_spec() or {}).get("labels") or ())
        if not labels:
            raise Refused(E.refusal(
                "invalid_request", f"step {sid}: step {prod.id} returns a value, not entities, so no step can "
                "start from it", "start this step from an anchor of its own, or from a step that lists entities",
                [E.problem("from_step", prod.id, ["anchor.id"])]))
        anchor = raw.get("anchor") if isinstance(raw.get("anchor"), dict) else {}
        label_raw = raw.get("anchor_label") or anchor.get("label")
        if label_raw:
            lab = p.label(label_raw, "anchor_label")
            if lab not in labels:
                raise p._refuse(f"step {prod.id} returns {list(labels)}, not {lab}", "anchor_label", label_raw,
                                list(labels), what="anchor_label")
            labels = (lab,)
        start = FromStep(prod.id, labels)
        out.from_step = prod.id
        log.add("from_step", prod.id, f"FromStep({prod.id})", "algebra_producer")
        path = raw.get("path")
        if path is None and raw.get("relation"):
            path = [{"relation": raw.get("relation"), "direction": raw.get("direction"),
                     "target_label": raw.get("target_label")}]
        if kind == "describe" or not path:
            node: Any = Nodes(start)
        else:
            hops = p.hops(path, frozenset(labels), "path")
            depth = p.integer(raw.get("depth"), "depth", default=1)
            conds: tuple = ()
            flt = raw.get("filter")
            if isinstance(flt, dict) and flt.get("property") not in (None, ""):
                ends = check(Walk(start, hops, depth), p.card)
                prop = p.prop(flt.get("property"), ends, "filter.property")
                types = {p.card.labels[lab].properties[prop].vtype for lab in ends
                         if prop in p.card.labels[lab].properties}
                is_list = types == {"list"}
                vt = next(iter(types)) if len(types) == 1 else "string"
                value = p.value(flt.get("value"), vt, "contains" if is_list else "=", ends, prop, "filter.value")
                conds = (Cond(prop, "contains" if is_list else "=", value),)
            walk = Walk(start, hops, depth, conds)
            node = Count(walk) if kind == "count" else Expand(walk)
        try:
            check(node, p.card)
            result = _result_labels(node, p.card)
        except InvalidOp as exc:
            raise Refused(_teach(sid, exc, p.card)) from None
        spec = {"op": kind, "ir": to_dict(node), "labels": result}
        out.step = TypedStep(kind=ALGEBRA_KIND, anchor_label=labels[0], anchor_ids=(),
                             algebra=json.dumps(spec, sort_keys=True, ensure_ascii=False))
        out.fixes = list(log.fixes)
        return out
    except Refused as r:
        out.refusals.append(r.envelope)
        out.fixes = list(log.fixes)
        return out


def _end_label(prod: Any) -> str:
    """The one label an earlier accepted step's result holds, or ``""``."""
    st = prod.step
    if st is None:
        return ""
    spec = st.algebra_spec() if hasattr(st, "algebra_spec") else None
    if spec is not None:
        labels = spec.get("labels") or []
        return labels[0] if len(labels) == 1 else ""
    if st.hops:
        return st.hops[-1].target_label or ""
    return st.anchor_label or ""


# --------------------------------------------------------------------------- #
# Today's kinds through the algebra validator (Phase G item 3)
# --------------------------------------------------------------------------- #


def check_today_step(step: Any, card: Any) -> Exception | None:
    """``InvalidOp`` when today's typed step is not valid on the card, else ``None``.

    Ids the step leaves to run time (a name or ``from_step`` anchor) get a
    placeholder, since the validator only needs the shape. A filter value is
    typed as the card types the property (the planner writes text).
    """
    from dataclasses import replace

    from utils.specialists.algebra.base import Anchors, Cond, Count, Describe, Expand, Walk
    from utils.specialists.algebra.from_typed_step import from_typed_step
    from utils.specialists.algebra.validate import NUMERIC_TYPES, InvalidOp, check

    try:
        node = from_typed_step(step if step.anchor_ids or step.kind == "scan"
                               else replace(step, anchor_ids=("_",)), card)
    except ValueError as exc:
        return InvalidOp("step", str(exc))
    walk = node.walk if isinstance(node, Expand) else node.of if isinstance(node, Count) else None
    if isinstance(walk, Walk) and walk.last_conds:
        c = walk.last_conds[0]
        target = walk.hops[-1].target
        vt = getattr(card.labels.get(target).properties.get(c.prop), "vtype", "") if target in card.labels else ""
        value: Any = c.value
        if vt == "boolean" and str(value).lower() in ("true", "false"):
            value = str(value).lower() == "true"
        elif vt in NUMERIC_TYPES:
            try:
                value = float(value) if "." in str(value) else int(value)
            except ValueError:
                pass
        walk = replace(walk, last_conds=(Cond(c.prop, c.op, value, c.cmp),))
        node = Expand(walk) if isinstance(node, Expand) else Count(walk)
    if isinstance(node, Describe) and not node.anchors.ids:
        node = Describe(Anchors(("_",), node.anchors.label))
    try:
        check(node, card)
    except InvalidOp as exc:
        return exc
    return None


__all__ = ["CORE_KINDS", "EXTENDED_KINDS", "catalog_section", "check_algebra_step", "check_step_from_algebra",
           "check_today_step",
           "condition_ops", "kinds", "system_section"]
