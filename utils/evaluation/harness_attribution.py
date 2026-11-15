#!/usr/bin/env python3
"""Where the planned path loses an answer, and in which stage (EXP-2026-11-009, Era 2 Step 4).

For a question the authored plan answers and a planner arm does not (0 records),
:func:`code` assigns **exactly one cause**: the first one in pipeline order,
with the full codebook in the experiment's ``PROTOCOL.md``. Every other
applicable cause is kept as a flag, so multi-label counts can be reported too.

Each cause belongs to a **stage**:

- ``plan``: the planner's own output (``observed_plan``) was already wrong. For
  the LLM planner that is the model's decision.
- ``downstream``: the plan named the right things and the harness lost them
  (the resolver re-reading the English, the gate, the builders).

Ordering plan causes first makes the downstream share a lower bound.

Model-free and pure: it reads saved answer artifacts only.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SAVED_ROOT = Path("docs/evaluation/experiments/plan-source-2026-09-14")
AUTHORED, DET, LLM = "generic_composed", "generic_planned", "generic_planned_llm"

#: Causes in pipeline order (the first that applies is the cause).
CAUSES = ("source", "shape", "relation", "english_reread", "decomposition", "limit", "entity",
          "direction", "missing_operator", "other")
STAGE = {"source": "plan", "shape": "plan", "relation": "plan", "decomposition": "plan", "limit": "plan",
         "entity": "plan", "missing_operator": "plan", "english_reread": "downstream",
         "direction": "downstream", "other": "unattributed"}

DEPTH_REJECT = "exceeds max_traversal_depth"


@dataclass(frozen=True)
class Step:
    """One executed sub-question, as the run's traces recorded it."""

    source: str
    sub_question: str
    labels: tuple[str, ...]
    rels: tuple[str, ...]
    seeds: tuple[str, ...]
    template: str | None
    query: str
    ok: bool
    error: str
    summary: str


def steps(answer: dict[str, Any]) -> list[Step]:
    out = []
    for r in (answer.get("logic_flow") or {}).get("results") or []:
        tr = {t.get("step"): t for t in r.get("traces") or []}
        rs = (tr.get("resolve") or {}).get("detail") or {}
        gate = (tr.get("gate") or {}).get("detail") or {}
        out.append(Step(
            source=str(r.get("source") or ""),
            sub_question=str(r.get("sub_question") or ""),
            labels=tuple(rs.get("labels") or ()),
            rels=tuple(rs.get("relationships") or ()),
            seeds=tuple(str(s) for s in rs.get("seed_ids") or ()),
            template=gate.get("template"),
            query=str(r.get("query") or gate.get("query") or ""),
            ok=bool(r.get("ok")),
            error=str(r.get("error") or ""),
            summary=str(r.get("summary") or ""),
        ))
    return out


def observed_plan(answer: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((answer.get("run_meta") or {}).get("observed_plan")) or [])


def records(answer: dict[str, Any]) -> int:
    return int((answer.get("evidence_volume") or {}).get("records") or 0)


def anchors(question: str, authored: list[Step]) -> set[str]:
    """Authored seed ids written in the question; else the first authored step's seeds."""
    all_seeds = {s for st in authored for s in st.seeds}
    named = {s for s in all_seeds if s and s in question}
    if named:
        return named
    return set(authored[0].seeds) if authored else set()


_CYPHER_OUT = r"-\[[^\]]*:{rel}\b[^\]]*\]->"
_CYPHER_IN = r"<-\[[^\]]*:{rel}\b[^\]]*\]-"
_CYPHER_ANY = r"-\[[^\]]*:{rel}\b[^\]]*\]-(?!>)"


def orientations(query: str, rel: str) -> set[str]:
    """How a query traverses ``rel``: ``>`` out, ``<`` in, ``-`` either way."""
    r = re.escape(rel)
    found = set()
    if re.search(_CYPHER_OUT.format(rel=r), query):
        found.add(">")
    if re.search(_CYPHER_IN.format(rel=r), query):
        found.add("<")
    if re.search(r'\bout[EV]?\(\s*["\']' + r + r'["\']', query):
        found.add(">")
    if re.search(r'\bin[EV]?\(\s*["\']' + r + r'["\']', query):
        found.add("<")
    if re.search(r'\bboth[EV]?\(\s*["\']' + r + r'["\']', query):
        found.add("-")
    # an undirected Cypher pattern (not already counted as "<-[...]-" or "-[...]->")
    for m in re.finditer(_CYPHER_ANY.format(rel=r), query):
        start = m.start()
        if start == 0 or query[start - 1] != "<":
            found.add("-")
    return found


@dataclass
class Coding:
    qid: str
    arm: str
    cause: str
    stage: str
    mechanism: str = ""
    flags: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def code(qid: str, authored_answer: dict[str, Any], planned_answer: dict[str, Any], *, arm: str) -> Coding:
    """The first cause in pipeline order, plus every applicable flag."""
    llm = arm == LLM
    question = str(authored_answer.get("question") or "")
    A, P, OP = steps(authored_answer), steps(planned_answer), observed_plan(planned_answer)
    anchor = anchors(question, A)
    a_rels = {r for s in A for r in s.rels}
    p_rels = {r for s in P for r in s.rels}
    p_elems = p_rels | {lab for s in P for lab in s.labels}
    op_ents = {e for t in OP for e in (t.get("entities") or [])}
    plan_elems = op_ents if llm else p_elems
    op_text = " ".join(str(t.get("text") or "") for t in OP)
    p_seeds = {s for st in P for s in st.seeds}
    texts = " ".join(f"{s.error} {s.summary}" for s in P)

    flags: list[tuple[str, str]] = []                       # (cause, mechanism), in pipeline order
    if not A or A[0].source not in {str(t.get("source")) for t in OP}:
        flags.append(("source", "no_sub_questions" if not OP else "authored_source_not_routed"))
    if any(s.template == "describe" for s in A) and not any(s.template == "describe" for s in P):
        flags.append(("shape", "attribute_lookup_planned_as_traversal"))
    if a_rels - plan_elems:
        flags.append(("relation", "missing:" + ",".join(sorted(a_rels - plan_elems))))
    if llm and a_rels and a_rels <= op_ents and not a_rels <= p_rels:
        flags.append(("english_reread", "resolver_changed_schema"))
    if DEPTH_REJECT in texts:
        added = (p_elems - op_ents) if llm else set()
        flags.append(("english_reread", "resolver_added_schema:" + ",".join(sorted(added))) if added
                     else ("relation", "superfluous_schema"))
    if "Skipped" in texts or "depends on" in texts or (OP and len(OP) != len(A)):
        flags.append(("decomposition", "dependent_step_skipped" if ("Skipped" in texts or "depends on" in texts)
                      else f"steps_{len(OP)}_vs_authored_{len(A)}"))
    need_depth = max((len(s.rels) for s in A), default=0)
    op_depths = [int((t.get("limits") or {}).get("max_traversal_depth") or 0) for t in OP]
    op_rows = [int((t.get("limits") or {}).get("max_result_rows") or 0) for t in OP]
    if OP and ((op_depths and min(op_depths) < need_depth) or (op_rows and min(op_rows) < records(authored_answer))):
        flags.append(("limit", f"depth {min(op_depths)} < {need_depth}" if op_depths and min(op_depths) < need_depth
                      else f"rows {min(op_rows)} < {records(authored_answer)}"))
    if anchor and not any(a in op_text for a in anchor):
        flags.append(("entity", "anchor_not_in_plan_text"))
    if anchor and any(a in op_text for a in anchor) and not (anchor & p_seeds):
        flags.append(("english_reread", "seeds_dropped"))
    for rel in sorted(a_rels & p_rels):
        a_or = set().union(*(orientations(s.query, rel) for s in A)) if A else set()
        p_or = set().union(*(orientations(s.query, rel) for s in P)) if P else set()
        if a_or and p_or and "-" not in a_or | p_or and not (a_or & p_or):
            flags.append(("direction", f"{rel}: authored {sorted(a_or)} vs planned {sorted(p_or)}"))
            break

    # The rules above run in the protocol's pipeline order, so the first flag
    # raised is the cause.
    first = flags[0] if flags else ("other", "bound_correctly_but_empty")
    return Coding(qid=qid, arm=arm, cause=first[0], stage=STAGE[first[0]], mechanism=first[1],
                  flags=[f"{c}:{m}" for c, m in flags],
                  detail={"anchor": sorted(anchor), "authored_rels": sorted(a_rels),
                          "plan_elements": sorted(plan_elems), "planned_rels": sorted(p_rels),
                          "planned_seeds": sorted(p_seeds), "steps_authored": len(A), "steps_planned": len(OP)})


# --------------------------------------------------------------------------- #
# Populations
# --------------------------------------------------------------------------- #


def load_arm(root: Path, arm: str) -> dict[str, dict[str, Any]]:
    out = {}
    for f in sorted((root / arm / "answers").glob("*.json")):
        if ".judgment" in f.name:
            continue
        d = json.loads(f.read_text())
        out[d["id"]] = d
    return out


def lost(authored: dict[str, dict], planned: dict[str, dict]) -> list[str]:
    """Questions the authored plan answered (records > 0) and the planner did not (0)."""
    return sorted(q for q in authored if q in planned and records(authored[q]) > 0 and records(planned[q]) == 0)


def coverage(answers: dict[str, dict]) -> dict[str, float]:
    return {q: float(((d.get("deterministic_scores") or {}).get("coverage") or {}).get("coverage") or 0.0)
            for q, d in answers.items()}


def paired(a: dict[str, float], b: dict[str, float]) -> dict[str, Any]:
    """Mean of b − a over shared questions, with its standard error."""
    qs = sorted(set(a) & set(b))
    diffs = [b[q] - a[q] for q in qs]
    n = len(diffs)
    if not n:
        return {"n": 0}
    mean = sum(diffs) / n
    sd = (sum((d - mean) ** 2 for d in diffs) / (n - 1)) ** 0.5 if n > 1 else 0.0
    return {"n": n, "mean_a": round(sum(a[q] for q in qs) / n, 4), "mean_b": round(sum(b[q] for q in qs) / n, 4),
            "diff": round(mean, 4), "se": round(sd / n ** 0.5, 4)}


def tier_of(qid: str) -> str:
    return qid.split("-", 1)[0]


# --------------------------------------------------------------------------- #
# Second annotator
# --------------------------------------------------------------------------- #


def packet(qid: str, authored: dict[str, Any], planned: dict[str, Any], arm: str) -> dict[str, Any]:
    """Everything an annotator needs to code one question, and nothing of the automatic code."""
    def st(s: Step) -> dict[str, Any]:
        return {"source": s.source, "sub_question": s.sub_question, "labels": list(s.labels),
                "relationships": list(s.rels), "seed_ids_bound": list(s.seeds), "template": s.template,
                "query": s.query[:700], "error": s.error[:300], "summary": s.summary[:200]}
    return {
        "qid": qid,
        "planner": "LLM planner (Gemma 4 26B; its plan format has no seed-id field)" if arm == LLM
                   else "deterministic rules planner",
        "question": authored.get("question"),
        "authored_records": records(authored),
        "authored_steps": [st(s) for s in steps(authored)],
        "planner_observed_plan": observed_plan(planned),
        "planner_executed_steps": [st(s) for s in steps(planned)],
    }


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    if not n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return round((po - pe) / (1 - pe), 4) if pe < 1 else 1.0


# --------------------------------------------------------------------------- #
# Post-hoc sensitivity (EXP-2026-11-009 RESULTS §4): the builder's fixed walk
# --------------------------------------------------------------------------- #

BUILDER_WALK = "repeat(...).times("


def recode_builder_walk(c: Coding, planned_answer: dict[str, Any]) -> Coding:
    """The post-hoc correction, kept apart from the pre-registered rule.

    The pre-registered rule 5 read every depth rejection as an over-long chain
    built from the plan's own elements. The saved traces show a second origin:
    the query builder emits a fixed ``repeat(...).times(3)`` walk whatever depth
    the plan set, and the gate then rejects the builder's own query. When the
    plan named every authored relation (``superfluous_schema``) and the rejected
    query is that walk, the plan was right and the harness lost it.
    """
    if c.mechanism != "superfluous_schema":
        return c
    errs = " ".join(s.error for s in steps(planned_answer))
    if BUILDER_WALK not in errs:
        return c
    return Coding(qid=c.qid, arm=c.arm, cause="english_reread", stage="downstream",
                  mechanism="builder_fixed_walk_depth", flags=c.flags + ["english_reread:builder_fixed_walk_depth"],
                  detail=c.detail)


__all__ = ["AUTHORED", "CAUSES", "DET", "LLM", "SAVED_ROOT", "STAGE", "Coding", "Step", "anchors", "code",
           "cohen_kappa", "coverage", "recode_builder_walk", "load_arm", "lost", "observed_plan", "orientations", "packet", "paired",
           "records", "steps", "tier_of"]
