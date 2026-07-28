#!/usr/bin/env python3
"""Classify *where* each graded case broke — mechanically, from the artifacts.

A judge's rationale says an answer was wrong; it does not say which stage lost
the information. This walks the saved artifact and locates the **terminus**: the
last pipeline stage at which the gold answer was still recoverable.

The ladder is ordered, and the first rule that fires wins:

``gold_cap_collision``  the gold asserts a record-count window that the
                        un-truncation profile deliberately lifts (the two scans).
``pipeline_timeout``    a sub-question never ran — the run is ``partial``.
``retrieval_empty``     the executed query returned nothing at all.
``seed_lost``           a federated second hop ran with no seed ids (the join
                        broke), so it answered a different question.
``wrong_query``         records came back, but NONE of the gold ids are in the
                        evidence — the wrong traversal ran.
``incomplete_retrieval`` some gold ids reached the evidence and some never did —
                        the template/plan fetched a partial neighbourhood.
``property_gap``        the gold requires attribute VALUES (``expect_properties``
                        /``expect_names``); the evidence carries them and the
                        answer never states them.
``projection_gap``      the gold IDS are in the evidence and the answer never
                        states them — retrieval was fine, synthesis dropped them.
``unfaithful``          the answer states things the evidence does not support.
``other``               graded non-CORRECT with none of the above (judge nuance).

``property_gap`` and ``projection_gap`` are the actionable ones: they are the only
classes whose fix is in synthesis rather than in planning or retrieval.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

_ID_RE = re.compile(
    r"\b(?:T\d{4}(?:\.\d{3})?|TA\d{4}|[MSG]\d{4}|DS\d{4}|DET\d+|AN\d+|CAPEC-\d+|CWE-\d+)\b",
    re.IGNORECASE,
)
_COVERAGE_KEYS = ("must_include_ids", "must_include_related", "must_correlate")


def _norm(v: str) -> str:
    return str(v).strip().upper()


def gold_ids(artifact: dict) -> set[str]:
    """Every id the gold requires the answer to surface (both single + federated)."""
    out: set[str] = set()

    def _walk(asserts: Any) -> None:
        if not isinstance(asserts, dict):
            return
        for key in _COVERAGE_KEYS:
            for v in asserts.get(key) or []:
                out.add(_norm(v))
        # Federated entries nest per-source assertion blocks.
        for value in asserts.values():
            if isinstance(value, dict):
                _walk(value)

    _walk((artifact.get("gold") or {}).get("assertions"))
    return out


def evidence_ids(artifact: dict) -> set[str]:
    """Every id present anywhere in the retrieved evidence."""
    out: set[str] = set()
    for result in (artifact.get("logic_flow") or {}).get("results") or []:
        for rec in result.get("records") or []:
            if rec.get("primary_id"):
                out.add(_norm(rec["primary_id"]))
            for jv in rec.get("join_values") or []:
                out.add(_norm(jv))
            for rel in rec.get("related") or []:
                if isinstance(rel, dict):
                    for k in ("id", "entry_id"):
                        if rel.get(k):
                            out.add(_norm(rel[k]))
    return out


def answer_ids(artifact: dict) -> set[str]:
    """Every id the analyst actually sees — claims, citations, and the prose."""
    answer = artifact.get("answer") or {}
    out: set[str] = set()
    for claim in answer.get("claims") or []:
        for eid in claim.get("entity_ids") or []:
            out.add(_norm(eid))
        for cit in claim.get("citations") or []:
            if cit.get("primary_id"):
                out.add(_norm(cit["primary_id"]))
        out |= {_norm(m) for m in _ID_RE.findall(claim.get("text") or "")}
    out |= {_norm(m) for m in _ID_RE.findall(answer.get("narrative") or "")}
    return out


def gold_property_values(artifact: dict) -> list[tuple[str, str, str]]:
    """``(anchor_id, key, expected_value)`` for every attribute the gold requires.

    ``expect_properties`` (Abstraction/Status/…) and ``expect_names`` are answers
    in their own right — a lookup question is not answered by naming the node.
    """
    asserts = (artifact.get("gold") or {}).get("assertions") or {}
    out: list[tuple[str, str, str]] = []
    for anchor, props in (asserts.get("expect_properties") or {}).items():
        if isinstance(props, dict):
            for key, value in props.items():
                out.append((_norm(anchor), str(key), str(value)))
    for anchor, name in (asserts.get("expect_names") or {}).items():
        # A name identical to the id carries no information (Campaign C0027).
        if str(name) and _norm(name) != _norm(anchor):
            out.append((_norm(anchor), "name", str(name)))
    return out


def _evidence_has_value(artifact: dict, anchor: str, key: str, value: str) -> bool:
    for result in (artifact.get("logic_flow") or {}).get("results") or []:
        for rec in result.get("records") or []:
            if _norm(rec.get("primary_id") or "") != anchor:
                continue
            if key == "name" and _norm(rec.get("name") or "") == _norm(value):
                return True
            props = rec.get("properties") or {}
            if _norm(str(props.get(key, ""))) == _norm(value):
                return True
    return False


def _answer_states_value(artifact: dict, value: str) -> bool:
    answer = artifact.get("answer") or {}
    blob = (answer.get("narrative") or "") + " " + " ".join(
        c.get("text") or "" for c in answer.get("claims") or []
    )
    return _norm(value) in _norm(blob)


def _record_count(artifact: dict) -> int:
    return sum(
        len(r.get("records") or [])
        for r in (artifact.get("logic_flow") or {}).get("results") or []
    )


def _gold_window(artifact: dict) -> tuple[int | None, int | None]:
    asserts = (artifact.get("gold") or {}).get("assertions") or {}
    return asserts.get("min_records"), asserts.get("max_records")


def _seed_lost(artifact: dict) -> bool:
    """A dependent federated hop ran with no seed ids (the cross-source join broke)."""
    for result in (artifact.get("logic_flow") or {}).get("results") or []:
        for trace in result.get("traces") or []:
            blob = f"{trace.get('step', '')} {' '.join(trace.get('reasons') or [])} {trace.get('detail') or ''}"
            low = blob.lower()
            if "no join values" in low or "dependency" in low and "skip" in low:
                return True
    notes = " ".join((artifact.get("answer") or {}).get("notes") or []).lower()
    return "no join values" in notes


def _timed_out(artifact: dict) -> bool:
    meta = artifact.get("run_meta") or {}
    if meta.get("status") == "partial" or meta.get("exit_code") == 1:
        return True
    notes = " ".join((artifact.get("answer") or {}).get("notes") or []).lower()
    return "timeout" in notes


def classify(artifact: dict, judgment: dict) -> dict[str, Any]:
    """Locate the terminus for one graded case."""
    gold = gold_ids(artifact)
    ev = evidence_ids(artifact)
    ans = answer_ids(artifact)
    records = _record_count(artifact)
    lo, hi = _gold_window(artifact)
    halluc = len(judgment.get("hallucinations") or [])

    recoverable = gold & ev          # gold the evidence actually contained
    surfaced = gold & ans            # gold the answer actually stated
    lost_in_synthesis = recoverable - ans
    never_retrieved = gold - ev

    # Attribute answers: present in the evidence but absent from the prose.
    props = gold_property_values(artifact)
    prop_lost = [
        f"{a}.{k}={v}" for a, k, v in props
        if _evidence_has_value(artifact, a, k, v) and not _answer_states_value(artifact, v)
    ]
    prop_missing = [
        f"{a}.{k}={v}" for a, k, v in props
        if not _evidence_has_value(artifact, a, k, v)
    ]

    if hi is not None and records > hi:
        terminus = "gold_cap_collision"
    elif _timed_out(artifact) and (never_retrieved or not records):
        terminus = "pipeline_timeout"
    elif records == 0 and (gold or props):
        terminus = "retrieval_empty"
    elif _seed_lost(artifact) and never_retrieved:
        terminus = "seed_lost"
    elif gold and not recoverable:
        terminus = "wrong_query"
    elif never_retrieved or prop_missing:
        terminus = "incomplete_retrieval"
    elif prop_lost:
        terminus = "property_gap"
    elif lost_in_synthesis:
        terminus = "projection_gap"
    elif halluc:
        terminus = "unfaithful"
    else:
        terminus = "other"

    return {
        "id": artifact.get("id"),
        "category": artifact.get("category"),
        "verdict": judgment.get("verdict"),
        "correctness": judgment.get("correctness"),
        "terminus": terminus,
        "gold_required": len(gold),
        "in_evidence": len(recoverable),
        "in_answer": len(surfaced),
        "lost_in_synthesis": sorted(lost_in_synthesis)[:12],
        "never_retrieved": sorted(never_retrieved)[:12],
        "properties_required": len(props),
        "properties_unstated": prop_lost[:8],
        "properties_unretrieved": prop_missing[:8],
        "records": records,
        "gold_window": [lo, hi],
        "hallucinations": halluc,
    }


def analyse_arm(root: Path, arm: str) -> list[dict[str, Any]]:
    answers = root / arm / "answers"
    rows: list[dict[str, Any]] = []
    for jpath in sorted(answers.glob("*.judgment.json")):
        cid = jpath.name[: -len(".judgment.json")]
        apath = answers / f"{cid}.json"
        if not apath.exists():
            continue
        try:
            judgment = json.loads(jpath.read_text())
            artifact = json.loads(apath.read_text())
        except ValueError:
            continue
        rows.append(classify(artifact, judgment))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="docs/evaluation/experiments/untruncated")
    parser.add_argument("--arms", default="deterministic,llm,gold_llm")
    parser.add_argument("--out", default=None, help="write the per-case rows as JSON")
    args = parser.parse_args(argv)

    root = Path(args.root)
    report: dict[str, Any] = {}
    for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
        rows = analyse_arm(root, arm)
        if not rows:
            continue
        bad = [r for r in rows if r["verdict"] != "CORRECT"]
        report[arm] = {
            "n": len(rows),
            "non_correct": len(bad),
            "terminus_all": dict(Counter(r["terminus"] for r in rows).most_common()),
            "terminus_failures": dict(Counter(r["terminus"] for r in bad).most_common()),
            "gold_recoverable_but_unstated": sum(len(r["lost_in_synthesis"]) for r in rows),
            "gold_never_retrieved": sum(len(r["never_retrieved"]) for r in rows),
            "cases": rows,
        }
        print(f"\n=== {arm}: {len(bad)} non-CORRECT of {len(rows)} ===")
        for terminus, count in Counter(r["terminus"] for r in bad).most_common():
            ids = [r["id"] for r in bad if r["terminus"] == terminus]
            print(f"  {terminus:20s} {count:3d}  {', '.join(ids[:10])}"
                  + (" …" if len(ids) > 10 else ""))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
