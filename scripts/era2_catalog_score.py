#!/usr/bin/env python3
"""EXP-2026-11-015 scorer: the four gates (G1-G4), typed-path health, paired intervals.

    uv run python scripts/era2_catalog_score.py --data <exp>/data \
        --runs docs/evaluation/experiments/tool-catalog-2026-11-18

Reads, under ``--runs`` (default ``--data``):

* ``variants/<arm>.json`` -- ``scripts/variant_harness.py compare`` output for
  ``R`` (rules-only, ``--name R.json``), ``E``, ``T-lazy``, ``T-full`` and
  ``T-lazy-G`` (``--arm``; these also carry the 120 gold questions as tier
  ``T0``). Every row already holds ``score()``'s fields: ``records_exact``,
  ``wrong_entity``, ``abstained``.
* ``dev/<arm>/answers/*.json`` -- ``experiment_untruncated`` answers for
  ``planned_llm_english`` (E), ``planned_llm_typed_lazy`` (T-lazy) and
  ``planned_llm_typed_full`` (T-full); ``dev-gemma/planned_llm_typed_lazy`` for
  T-lazy-G.
* the authored baseline, ``--authored`` (default: the committed
  ``generic_composed`` answers of the 2026-11-16 walk-fix harness run; pass a
  fresh ``generic_composed`` run's ``answers`` directory to use that instead).

Definitions (PROTOCOL "Metrics"):

* **empty retrieval (lost)**: the authored plan returns records and the arm
  returns none (``planner_cost_score``'s rule); ``gained`` and ``both_empty``
  are reported beside it.
* **confidently wrong**: on variants, ``wrong_entity`` and not ``abstained``,
  over tiers T0-T5; on the dev bank, the arm and the authored plan both return
  records and their entity-id sets do not overlap.
* **G1** T-lazy T1 ``records_exact`` >= 0.80; **G2** T-lazy lost <= floor(E lost / 2)
  (amendment 1; ``<= 38`` reported); **G3** T-lazy T0 ``records_exact`` >= 0.98;
  **G4** T-lazy's confidently-wrong count not above E's, on variants and on dev.
* **paired intervals**: each arm minus E, 2,000 bootstrap resamples, seed
  20261118. Dev resamples questions. Variants resample *gold questions* (all of
  a question's variants move together, since they share an anchor and a
  reference), which is the conservative reading of "over cases".

Writes ``<data>/metrics.json`` and ``<data>/../tables/scoreboard.md``.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
AUTHORED = (REPO / "docs" / "evaluation" / "experiments" / "harness-attribution-qwen-walkfix-2026-11-16"
            / "generic_composed" / "answers")
VARIANT_ARMS = ("R", "E", "T-lazy", "T-full", "T-lazy-G")
DEV_ARMS = {"E": "dev/planned_llm_english", "T-lazy": "dev/planned_llm_typed_lazy",
            "T-full": "dev/planned_llm_typed_full", "T-lazy-G": "dev-gemma/planned_llm_typed_lazy"}
CW_TIERS = ("T0", "T1", "T2", "T3", "T4", "T5")
SEED = 20261118
RESAMPLES = 2000
G1_BAR, G3_BAR, OLD_G2_BAR = 0.80, 0.98, 38


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #


def load_variant_rows(path: Path) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text())
    return [r for r in rows if "records_exact" in r]


def load_dev(answers: Path) -> dict[str, dict[str, Any]]:
    """Case id -> artifact (judgment sidecars excluded)."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(glob.glob(str(answers / "*.json"))):
        if ".judgment" in Path(p).name:
            continue
        a = json.loads(Path(p).read_text())
        out[a["id"]] = a
    return out


def dev_records(artifact: dict[str, Any]) -> int:
    return int((artifact.get("evidence_volume") or {}).get("records") or 0)


def dev_ids(artifact: dict[str, Any]) -> set[str]:
    """Every entity id the answer's evidence holds: record ids and their related ids."""
    ids: set[str] = set()
    for res in (artifact.get("logic_flow") or {}).get("results") or []:
        for rec in res.get("records") or []:
            if rec.get("primary_id"):
                ids.add(str(rec["primary_id"]).upper())
            for rel in rec.get("related") or []:
                rid = rel.get("id") if isinstance(rel, dict) else rel
                if rid:
                    ids.add(str(rid).upper())
    return ids


# --------------------------------------------------------------------------- #
# per-item outcomes
# --------------------------------------------------------------------------- #


def variant_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("case_id")), str(row.get("tier")), str(row.get("question")))


def confidently_wrong_variant(row: dict[str, Any]) -> bool:
    return bool(row.get("wrong_entity")) and not bool(row.get("abstained"))


def dev_outcome(arm: dict[str, Any] | None, authored: dict[str, Any] | None) -> dict[str, bool]:
    """``lost`` / ``gained`` / ``both_empty`` / ``confidently_wrong`` for one dev question.

    A missing arm answer (the run errored) counts as no records.
    """
    ra = dev_records(arm) if arm else 0
    rc = dev_records(authored) if authored else 0
    cw = False
    if ra > 0 and rc > 0:
        cw = not (dev_ids(arm or {}) & dev_ids(authored or {}))
    return {"lost": rc > 0 and ra == 0, "gained": ra > 0 and rc == 0, "both_empty": ra == 0 and rc == 0,
            "confidently_wrong": cw}


# --------------------------------------------------------------------------- #
# summaries
# --------------------------------------------------------------------------- #


def tier_table(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by[str(r.get("tier"))].append(r)
    out = {}
    for tier in sorted(by):
        g = by[tier]
        n = len(g)
        out[tier] = {
            "n": n,
            "records_exact": round(sum(bool(r["records_exact"]) for r in g) / n, 4),
            "wrong_entity": round(sum(bool(r.get("wrong_entity")) for r in g) / n, 4),
            "abstained": round(sum(bool(r.get("abstained")) for r in g) / n, 4),
            "confidently_wrong": sum(confidently_wrong_variant(r) for r in g),
            "errors": sum(1 for r in g if r.get("error")),
        }
    return out


def dev_summary(arm: dict[str, dict[str, Any]], authored: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ids = sorted(authored)
    outs = {i: dev_outcome(arm.get(i), authored.get(i)) for i in ids}
    return {
        "n": len(ids),
        "answered": sum(1 for i in ids if i in arm),
        "lost": sum(o["lost"] for o in outs.values()),
        "gained": sum(o["gained"] for o in outs.values()),
        "both_empty": sum(o["both_empty"] for o in outs.values()),
        "confidently_wrong": sum(o["confidently_wrong"] for o in outs.values()),
        "lost_ids": [i for i, o in outs.items() if o["lost"]],
        "confidently_wrong_ids": [i for i, o in outs.items() if o["confidently_wrong"]],
    }


def bootstrap(clusters: list[list[float]], *, resamples: int = RESAMPLES, seed: int = SEED,
              stat: str = "mean") -> dict[str, Any]:
    """Percentile interval of a paired difference, resampling whole clusters.

    ``clusters`` holds the per-item differences of each cluster (a cluster of one
    for dev questions). ``stat``: ``mean`` (per item) or ``sum`` (a count).
    """
    flat = [x for c in clusters for x in c]
    if not flat:
        return {"estimate": None, "lo": None, "hi": None, "n": 0}

    def f(cs: list[list[float]]) -> float:
        xs = [x for c in cs for x in c]
        if stat == "sum":
            return float(sum(xs))
        return sum(xs) / len(xs) if xs else 0.0

    rng = random.Random(seed)
    k = len(clusters)
    draws = sorted(f([clusters[rng.randrange(k)] for _ in range(k)]) for _ in range(resamples))
    lo = draws[int(math.floor(0.025 * (resamples - 1)))]
    hi = draws[int(math.ceil(0.975 * (resamples - 1)))]
    return {"estimate": round(f(clusters), 4), "lo": round(lo, 4), "hi": round(hi, 4), "n": len(flat),
            "clusters": k, "resamples": resamples, "seed": seed}


def paired_variants(arm_rows: list[dict[str, Any]], e_rows: list[dict[str, Any]],
                    value: Callable[[dict[str, Any]], float], tiers: tuple[str, ...] | None,
                    stat: str = "mean") -> dict[str, Any]:
    e = {variant_key(r): r for r in e_rows}
    by_case: dict[str, list[float]] = defaultdict(list)
    for r in arm_rows:
        k = variant_key(r)
        if k not in e or (tiers is not None and k[1] not in tiers):
            continue
        by_case[k[0]].append(value(r) - value(e[k]))
    return bootstrap(list(by_case.values()), stat=stat)


def paired_dev(arm: dict[str, dict[str, Any]], e: dict[str, dict[str, Any]],
               authored: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    clusters = [[float(dev_outcome(arm.get(i), authored[i])[key]) - float(dev_outcome(e.get(i), authored[i])[key])]
                for i in sorted(authored)]
    return bootstrap(clusters, stat="sum")


def typed_health(logs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Typed-path health over one log per question (the last draft of each)."""
    logs = [g for g in logs if g]
    if not logs:
        return None
    n = len(logs)
    fell = [g for g in logs if g.get("fallback")]
    planned = [g for g in logs if not g.get("fallback") or g.get("fallback") == "floor"]

    def share(pred: Callable[[dict[str, Any]], bool]) -> float:
        return round(sum(1 for g in logs if pred(g)) / n, 4)

    return {
        "questions": n,
        "valid_at_first_emission": share(lambda g: bool(g.get("valid_first"))),
        "valid_at_first_emission_no_coercion": share(lambda g: bool(g.get("valid_first_raw"))),
        "fixed_by_coercion": share(lambda g: bool(g.get("valid_first")) and not g.get("valid_first_raw")),
        "repair_used": share(lambda g: bool(g.get("repair_used"))),
        "fixed_by_repair": share(lambda g: bool(g.get("fixed_by_repair"))),
        "still_refused_questions": share(lambda g: int(g.get("still_refused") or 0) > 0),
        "still_refused_steps": sum(int(g.get("still_refused") or 0) for g in logs),
        "fallback_unavailable": sum(1 for g in fell if g.get("fallback") == "unavailable"),
        "fallback_floor": sum(1 for g in fell if g.get("fallback") == "floor"),
        "catalog_calls_per_question": round(sum(int(g.get("n_catalog_calls") or 0) for g in planned)
                                            / max(1, len(planned)), 3),
        "model_calls_per_question": round(sum(int(g.get("model_calls") or 0) for g in planned)
                                          / max(1, len(planned)), 3),
        "prompt_tokens_per_question": round(sum(int(g.get("prompt_tokens") or 0) for g in planned)
                                            / max(1, len(planned)), 1),
        "completion_tokens_per_question": round(sum(int(g.get("completion_tokens") or 0) for g in planned)
                                                / max(1, len(planned)), 1),
        "coercion_fixes_by_kind": _count(f.get("filled_by") for g in logs for f in g.get("coercions") or []),
        "final_refusal_codes": _count(x.get("code") for g in logs for x in g.get("refusals") or []
                                      if x.get("final")),
    }


def _count(items: Any) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for x in items:
        out[str(x)] += 1
    return dict(sorted(out.items()))


def _last(logs: Any) -> dict[str, Any] | None:
    if isinstance(logs, list) and logs:
        return logs[-1]
    return logs if isinstance(logs, dict) else None


# --------------------------------------------------------------------------- #
# the whole score
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# post-hoc diagnosis (reported, not gated; RESULTS §4)
# --------------------------------------------------------------------------- #

OUTCOME_CLASSES = ("exact", "anchor_only", "refused_or_empty", "superset", "subset", "mixed", "wrong")


def variant_class(row: dict[str, Any], ref: dict[str, Any] | None) -> str:
    """One variant answer against the reference capture of its gold question.

    ``anchor_only``: the sets differ only by the reference's own seed ids (the answer lists
    the anchor beside its records, or leaves it out). ``wrong``: records and no overlap.
    """
    if row.get("records_exact"):
        return "exact"
    if row.get("abstained"):
        return "refused_or_empty"
    if ref is None:
        return "wrong" if row.get("wrong_entity") else "mixed"
    want, got = set(ref.get("entity_ids") or []), set(row.get("entity_ids") or [])
    seeds = set(ref.get("seed_ids") or [])
    if want - seeds == got - seeds:
        return "anchor_only"
    if not (want & got):
        return "wrong"
    if got > want:
        return "superset"
    if got < want:
        return "subset"
    return "mixed"


def anchorless_scan_variant(row: dict[str, Any]) -> bool:
    """The typed plan holds a ``scan`` step with no anchor ids (it reads a whole label)."""
    for part in (row.get("planner") or {}).get("plan") or []:
        step = part.get("step") or {}
        if step.get("kind") == "scan" and not step.get("anchor_ids"):
            return True
    return False


def anchorless_scan_dev(artifact: dict[str, Any]) -> bool:
    """A result gated through a ``*_scan`` template with no seed ids."""
    for res in (artifact.get("logic_flow") or {}).get("results") or []:
        steps = res.get("traces") or res.get("steps") or []
        seeded = None
        for st in steps if isinstance(steps, list) else []:
            det = st.get("detail") or {}
            if st.get("step") == "resolve":
                seeded = bool(det.get("seed_ids"))
            if st.get("step") == "gate" and str(det.get("template", "")).endswith("_scan") and seeded is False:
                return True
    return False


def diagnosis(variants: dict[str, list[dict[str, Any]]], dev: dict[str, dict[str, dict[str, Any]]],
              cw_ids: dict[str, list[str]], reference: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm, rows in variants.items():
        by_tier: dict[str, dict[str, int]] = {}
        insensitive: dict[str, float] = {}
        for t in sorted({str(r.get("tier")) for r in rows}):
            g = [r for r in rows if str(r.get("tier")) == t]
            cls = [variant_class(r, reference.get(str(r.get("case_id")))) for r in g]
            by_tier[t] = {c: cls.count(c) for c in OUTCOME_CLASSES}
            insensitive[t] = round(sum(c in ("exact", "anchor_only") for c in cls) / len(g), 4)
        cw = [r for r in rows if str(r.get("tier")) in CW_TIERS and confidently_wrong_variant(r)]
        out[arm] = {"classes_by_tier": by_tier, "records_exact_anchor_insensitive": insensitive,
                    "cw_T0_T5": len(cw),
                    "cw_T0_T5_anchorless_scan": sum(anchorless_scan_variant(r) for r in cw),
                    "cw_T0_T5_catalogue_dump": sum(bool(r.get("catalogue_dump")) for r in cw)}
    for arm, answers in dev.items():
        ids = cw_ids.get(arm) or []
        out.setdefault(arm, {})["dev_cw_anchorless_scan"] = sum(
            anchorless_scan_dev(answers[i]) for i in ids if i in answers)
    return out


def score(variants: dict[str, list[dict[str, Any]]], dev: dict[str, dict[str, dict[str, Any]]],
          authored: dict[str, dict[str, Any]],
          reference: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"variants": {}, "dev": {}, "health": {}, "paired_vs_E": {}, "gates": {}}
    for arm, rows in variants.items():
        out["variants"][arm] = {"tiers": tier_table(rows),
                                "confidently_wrong_T0_T5": sum(confidently_wrong_variant(r) for r in rows
                                                               if str(r.get("tier")) in CW_TIERS)}
    for arm, answers in dev.items():
        out["dev"][arm] = dev_summary(answers, authored)
    for arm in set(variants) | set(dev):
        logs = [_last(r.get("typed")) for r in variants.get(arm, [])]
        dlogs = [_last((a.get("run_meta") or {}).get("typed")) for a in dev.get(arm, {}).values()]
        h = {"variants": typed_health(logs), "dev": typed_health(dlogs)}
        if h["variants"] or h["dev"]:
            out["health"][arm] = h

    e_rows = variants.get("E")
    e_dev = dev.get("E")
    for arm in [a for a in VARIANT_ARMS if a != "E"]:
        cell: dict[str, Any] = {}
        if e_rows is not None and arm in variants:
            tiers = sorted({str(r.get("tier")) for r in variants[arm]})
            cell["records_exact_by_tier"] = {
                t: paired_variants(variants[arm], e_rows, lambda r: float(bool(r["records_exact"])), (t,))
                for t in tiers}
            cell["confidently_wrong_T0_T5"] = paired_variants(
                variants[arm], e_rows, lambda r: float(confidently_wrong_variant(r)), CW_TIERS, stat="sum")
        if e_dev is not None and arm in dev:
            cell["dev_lost"] = paired_dev(dev[arm], e_dev, authored, "lost")
            cell["dev_confidently_wrong"] = paired_dev(dev[arm], e_dev, authored, "confidently_wrong")
        if cell:
            out["paired_vs_E"][arm] = cell
    out["gates"] = gates(out)
    if reference is not None:
        out["diagnosis"] = diagnosis(variants, dev, {a: d["confidently_wrong_ids"] for a, d in out["dev"].items()},
                                     reference)
    return out


def gates(m: dict[str, Any]) -> dict[str, Any]:
    v, d = m["variants"], m["dev"]

    def tier(arm: str, t: str) -> float | None:
        return ((v.get(arm) or {}).get("tiers") or {}).get(t, {}).get("records_exact")

    g: dict[str, Any] = {}
    t1 = tier("T-lazy", "T1")
    g["G1"] = {"bar": G1_BAR, "value": t1, "pass": None if t1 is None else t1 >= G1_BAR}
    lost_t, lost_e = (d.get("T-lazy") or {}).get("lost"), (d.get("E") or {}).get("lost")
    bar = None if lost_e is None else lost_e // 2
    g["G2"] = {"bar": bar, "rule": "T-lazy lost <= floor(E lost / 2) (amendment 1)", "value": lost_t,
               "E_lost": lost_e, "pass": None if lost_t is None or bar is None else lost_t <= bar,
               "reported_old_bar_38": {"bar": OLD_G2_BAR,
                                       "pass": None if lost_t is None else lost_t <= OLD_G2_BAR}}
    t0 = tier("T-lazy", "T0")
    g["G3"] = {"bar": G3_BAR, "value": t0, "pass": None if t0 is None else t0 >= G3_BAR}
    cw_tv = (v.get("T-lazy") or {}).get("confidently_wrong_T0_T5")
    cw_ev = (v.get("E") or {}).get("confidently_wrong_T0_T5")
    cw_td = (d.get("T-lazy") or {}).get("confidently_wrong")
    cw_ed = (d.get("E") or {}).get("confidently_wrong")
    parts = []
    if cw_tv is not None and cw_ev is not None:
        parts.append(cw_tv <= cw_ev)
    if cw_td is not None and cw_ed is not None:
        parts.append(cw_td <= cw_ed)
    g["G4"] = {"variants": {"T-lazy": cw_tv, "E": cw_ev}, "dev": {"T-lazy": cw_td, "E": cw_ed},
               "pass": None if len(parts) < 2 else all(parts),
               "complete": len(parts) == 2}
    g["all_pass"] = all(g[k]["pass"] for k in ("G1", "G2", "G3", "G4")) if all(
        g[k]["pass"] is not None for k in ("G1", "G2", "G3", "G4")) else None
    return g


# --------------------------------------------------------------------------- #
# the table
# --------------------------------------------------------------------------- #


def _f(x: Any) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.4f}"
    return str(x)


def _ci(c: dict[str, Any] | None) -> str:
    if not c or c.get("estimate") is None:
        return "—"
    return f"{c['estimate']:+.4f} [{c['lo']:+.4f}, {c['hi']:+.4f}]"


def _le(part: dict[str, Any]) -> bool | None:
    """One G4 part: T-lazy's count not above E's (``None`` if either is missing)."""
    t, e = part.get("T-lazy"), part.get("E")
    return None if t is None or e is None else t <= e


def scoreboard(m: dict[str, Any], exp_id: str = "EXP-2026-11-015") -> str:
    g = m["gates"]
    lines = [f"# {exp_id} scoreboard", "", "Generated by `scripts/era2_catalog_score.py`. "
             "Do not edit by hand.", "", "## Gates (T-lazy against E)", "",
             "| Gate | Bar | T-lazy | E | Pass |", "|---|---|---|---|---|",
             f"| G1 synonym tier (T1 records_exact) | ≥ {G1_BAR} | {_f(g['G1']['value'])} | "
             f"{_f(((m['variants'].get('E') or {}).get('tiers') or {}).get('T1', {}).get('records_exact'))} | "
             f"{_f(g['G1']['pass'])} |",
             f"| G2 empty retrievals (dev lost) | ≤ ⌊E/2⌋ = {_f(g['G2']['bar'])} | {_f(g['G2']['value'])} | "
             f"{_f(g['G2']['E_lost'])} | {_f(g['G2']['pass'])} |",
             f"| G2 reported: old bar | ≤ {OLD_G2_BAR} | {_f(g['G2']['value'])} | | "
             f"{_f(g['G2']['reported_old_bar_38']['pass'])} |",
             f"| G3 original wording (T0 records_exact) | ≥ {G3_BAR} | {_f(g['G3']['value'])} | "
             f"{_f(((m['variants'].get('E') or {}).get('tiers') or {}).get('T0', {}).get('records_exact'))} | "
             f"{_f(g['G3']['pass'])} |",
             f"| G4 confidently wrong, variants T0–T5 | ≤ E | {_f(g['G4']['variants']['T-lazy'])} | "
             f"{_f(g['G4']['variants']['E'])} | {_f(_le(g['G4']['variants']))} |",
             f"| G4 confidently wrong, dev | ≤ E | {_f(g['G4']['dev']['T-lazy'])} | {_f(g['G4']['dev']['E'])} | "
             f"{_f(_le(g['G4']['dev']))} |",
             f"| G4 (both parts) | | | | {_f(g['G4']['pass'])} |", "", f"All four: **{_f(g['all_pass'])}**", "",
             "## Variants, records_exact per tier", ""]
    tiers = sorted({t for a in m["variants"].values() for t in a["tiers"]})
    lines += ["| Arm | " + " | ".join(tiers) + " | CW T0–T5 |", "|---" * (len(tiers) + 2) + "|"]
    for arm in VARIANT_ARMS:
        a = m["variants"].get(arm)
        if a:
            lines.append(f"| {arm} | " + " | ".join(_f(a["tiers"].get(t, {}).get("records_exact")) for t in tiers)
                         + f" | {a['confidently_wrong_T0_T5']} |")
    lines += ["", "## Dev bank (284) against the authored plan", "",
              "| Arm | answered | lost | gained | both empty | confidently wrong |", "|---|---|---|---|---|---|"]
    for arm in VARIANT_ARMS:
        d = m["dev"].get(arm)
        if d:
            lines.append(f"| {arm} | {d['answered']} | {d['lost']} | {d['gained']} | {d['both_empty']} | "
                         f"{d['confidently_wrong']} |")
    lines += ["", "## Paired differences against E (2,000 resamples, seed 20261118)", "",
              "| Arm | T1 records_exact | T0 records_exact | CW T0–T5 (count) | dev lost (count) | "
              "dev CW (count) |", "|---|---|---|---|---|---|"]
    for arm, c in m["paired_vs_E"].items():
        rt = c.get("records_exact_by_tier") or {}
        lines.append(f"| {arm} | {_ci(rt.get('T1'))} | {_ci(rt.get('T0'))} | {_ci(c.get('confidently_wrong_T0_T5'))} "
                     f"| {_ci(c.get('dev_lost'))} | {_ci(c.get('dev_confidently_wrong'))} |")
    lines += ["", "## Typed-path health", "",
              "| Arm | set | valid first | fixed by coercion | fixed by repair | still refused | fallbacks "
              "| catalog calls/q | prompt tokens/q |", "|---|---|---|---|---|---|---|---|---|"]
    for arm, h in m["health"].items():
        for where in ("variants", "dev"):
            x = h.get(where)
            if x:
                lines.append(f"| {arm} | {where} | {_f(x['valid_at_first_emission'])} | "
                             f"{_f(x['fixed_by_coercion'])} | {_f(x['fixed_by_repair'])} | "
                             f"{_f(x['still_refused_questions'])} | "
                             f"{x['fallback_unavailable'] + x['fallback_floor']} | "
                             f"{x['catalog_calls_per_question']} | {x['prompt_tokens_per_question']} |")
    dg = m.get("diagnosis")
    if dg:
        lines += ["", "## Diagnosis (post hoc; reported, not gated)", "",
                  "Outcome classes on T0 and T1 against the reference capture. `anchor_only`: the "
                  "sets differ only by the gold question's seed ids.", "",
                  "| Arm | tier | " + " | ".join(OUTCOME_CLASSES) + " |", "|---" * (len(OUTCOME_CLASSES) + 2) + "|"]
        for arm in VARIANT_ARMS:
            x = dg.get(arm) or {}
            for t in ("T0", "T1"):
                c = (x.get("classes_by_tier") or {}).get(t)
                if c:
                    lines.append(f"| {arm} | {t} | " + " | ".join(str(c[k]) for k in OUTCOME_CLASSES) + " |")
        tiers = sorted({t for x in dg.values() for t in (x.get("records_exact_anchor_insensitive") or {})})
        lines += ["", "`records_exact` with the anchor ids ignored:", "",
                  "| Arm | " + " | ".join(tiers) + " |", "|---" * (len(tiers) + 1) + "|"]
        for arm in VARIANT_ARMS:
            ai = (dg.get(arm) or {}).get("records_exact_anchor_insensitive")
            if ai:
                lines.append(f"| {arm} | " + " | ".join(_f(ai.get(t)) for t in tiers) + " |")
        lines += ["", "Confidently wrong, by cause:", "",
                  "| Arm | CW T0–T5 | of which anchorless scan | of which catalogue dump | dev CW | "
                  "of which anchorless scan |", "|---|---|---|---|---|---|"]
        for arm in VARIANT_ARMS:
            x = dg.get(arm)
            if x and "cw_T0_T5" in x:
                lines.append(f"| {arm} | {x['cw_T0_T5']} | {x['cw_T0_T5_anchorless_scan']} | "
                             f"{x['cw_T0_T5_catalogue_dump']} | {(m['dev'].get(arm) or {}).get('confidently_wrong', '—')} | "
                             f"{x.get('dev_cw_anchorless_scan', '—')} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="the experiment's data directory (metrics.json is written here)")
    ap.add_argument("--runs", default=None,
                    help="where the run outputs (variants/, dev/, dev-gemma/) live; default: --data")
    ap.add_argument("--authored", default=str(AUTHORED),
                    help="answers directory of the authored-plan baseline (generic_composed)")
    args = ap.parse_args(argv)
    data = Path(args.data)
    runs = Path(args.runs) if args.runs else data
    variants = {arm: load_variant_rows(runs / "variants" / f"{arm}.json")
                for arm in VARIANT_ARMS if (runs / "variants" / f"{arm}.json").exists()}
    dev = {arm: load_dev(runs / sub / "answers") for arm, sub in DEV_ARMS.items()
           if (runs / sub / "answers").is_dir()}
    authored = load_dev(Path(args.authored))
    if not authored:
        print(f"no authored answers under {args.authored}", file=sys.stderr)
        return 2
    ref_path = runs / "variants" / "reference.json"
    reference = ({str(r["case_id"]): r for r in json.loads(ref_path.read_text())}
                 if ref_path.exists() else None)
    m = score(variants, dev, authored, reference)
    m["inputs"] = {"variants": sorted(variants), "dev": {a: DEV_ARMS[a] for a in sorted(dev)},
                   "authored": str(Path(args.authored).resolve().relative_to(REPO))
                   if Path(args.authored).resolve().is_relative_to(REPO) else str(args.authored)}
    (data / "metrics.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    tables = data.parent / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    exp_id = "-".join(data.resolve().parent.name.split("-")[:4])  # EXP-YYYY-MM-NNN
    (tables / "scoreboard.md").write_text(scoreboard(m, exp_id))
    print(scoreboard(m, exp_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
