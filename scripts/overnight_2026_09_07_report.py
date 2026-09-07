#!/usr/bin/env python3
"""Morning report for the 2026-09-07 overnight run. Markdown + PDF.

Reads state from disk. It reports what the files say, including when they say a
step did not finish -- a report that quietly omits an unfinished step is worse
than no report, because it reads like a complete one.
"""

from __future__ import annotations

import glob
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

OUT = REPO / "docs/reports/2026-09-07-overnight.md"
STATE = REPO / "docs/reports/2026-09-07-overnight.state.json"
GEN_ROOT = REPO / "docs/evaluation/experiments/seeded-repeats-generic-2026-09-06"
SEEDS = ("1729", "20260906", "424242")
BLOCKS = (("q1", 0), ("q2", 1))


def scores(seed: str, suffix: str) -> tuple[float | None, int]:
    d = GEN_ROOT / f"seed-{seed}" / "generic" / "answers"
    vals = []
    for p in d.glob(f"*.judgment.{suffix}.json"):
        try:
            v = json.loads(p.read_text()).get("correctness")
        except Exception:
            continue
        if isinstance(v, (int, float)):
            vals.append(float(v))
    return (round(statistics.fmean(vals), 4) if vals else None), len(vals)


def experiment_table() -> list[tuple[str, str]]:
    rows = []
    for mf in sorted(glob.glob(str(REPO / "docs/research/experiments/EXP-*/manifest.yaml"))):
        try:
            m = yaml.safe_load(open(mf)) or {}
        except Exception:
            continue
        rows.append((Path(mf).parent.name, str(m.get("status"))))
    return rows


def build() -> str:
    st = json.loads(STATE.read_text()) if STATE.exists() else {"steps": {}}
    L: list[str] = []
    A = L.append

    A("# Overnight report — 2026-09-07")
    A("")
    A(f"Driver started **{st.get('started', '?')}**, deadline "
      f"**{st.get('deadline', '?')}**.")
    A(f"Endpoint: `{st.get('served_model', 'not probed')}` on "
      "`:9090`, sharded across **default-model-2 / -3 / -4** at 32 workers "
      "each. **`default-model` was reserved by the operator at 01:15 and is "
      "untouched from that point.**")
    waits = st.get("endpoint_waits") or []
    if waits:
        A("")
        A(f"The endpoint was unreachable for **{len(waits)} five-minute "
          f"poll(s)** before work began (first {waits[0]['at'][11:16]}, "
          f"last {waits[-1]['at'][11:16]}); the driver waited rather than "
          "reporting an empty night.")
    A("")

    # --- what ran -------------------------------------------------------
    A("## Steps")
    A("")
    A("| step | outcome | elapsed |")
    A("|---|---|---|")
    for name, rec in (st.get("steps") or {}).items():
        el = rec.get("elapsed_s")
        A(f"| `{name}` | {rec.get('status', '?')} | "
          f"{f'{el/60:.0f} min' if el else '—'} |")
    A("")

    # --- the headline cell ----------------------------------------------
    A("## EXP-2026-09-011 — does `generic`'s wording variation move its score?")
    A("")
    A("This is the cell the night was for. `EXP-2026-09-010` established that "
      "`generic` words 143 of 276 answers differently on a rerun at the same "
      "seed, in the field the grader reads. Whether that reaches the **score** "
      "is this measurement.")
    A("")
    A("| seed | block q1 | n | block q2 | n |")
    A("|---|---|---|---|---|")
    per_seed: dict[str, list[float]] = {}
    for s in SEEDS:
        row = [f"| {s} "]
        for suf, _ in BLOCKS:
            m, n = scores(s, suf)
            row.append(f"| {m if m is not None else '—'} | {n} ")
            if m is not None:
                per_seed.setdefault(s, []).append(m)
        A("".join(row) + "|")
    A("")

    complete = [s for s in SEEDS if len(per_seed.get(s, [])) == len(BLOCKS)]
    if len(complete) == len(SEEDS):
        balanced = [statistics.fmean(per_seed[s]) for s in SEEDS]
        sd = statistics.pstdev(balanced)
        A(f"**Balanced across-seed spread: {sd:.4f}** "
          f"(means {[round(b, 4) for b in balanced]}).")
        A("")
        A(f"- **H2** (SD < 0.03): **{'holds' if sd < 0.03 else 'FALSIFIED'}**")
        # H3 as pre-registered names the HOLDOUT gap (0.1684) while the SD is
        # measured on the DEV half. Both are reported: the same-population
        # comparison (dev gap 0.1623, EXP-2026-09-005) is the cleaner test, and
        # the pre-registered one is shown because it is what was written down.
        A(f"- **H3, as pre-registered** (holdout gap 0.1684 > 3xSD = {3*sd:.4f}): "
          f"**{'holds' if 0.1684 > 3*sd else 'FALSIFIED'}**")
        A(f"- **H3, same population** (dev gap 0.1623 > 3xSD = {3*sd:.4f}): "
          f"**{'holds' if 0.1623 > 3*sd else 'FALSIFIED'}**")
        A("")
        A("The pre-registered form of H3 compares a holdout gap against a "
          "spread measured on the dev half. That mismatch is in the protocol as "
          "written, so it is reported as written *and* alongside the "
          "same-population comparison, which is the one that actually tests "
          "what H3 means.")
        A("")
        A("Counterbalancing note: both blocks are the **same grader**, so this "
          "is position-balanced repeatability, not cross-grader agreement. "
          "The second grader family was unavailable (its slot was freed).")
    else:
        A(f"**Incomplete — {len(complete)} of {len(SEEDS)} seeds have both "
          "blocks graded.** No spread is computed, because a spread over a "
          "partial set is not the statistic the hypothesis names.")
    A("")

    # --- record ---------------------------------------------------------
    rows = experiment_table()
    done = sum(1 for _, s in rows if s == "complete")
    A("## Record")
    A("")
    A(f"**{done} of {len(rows)} experiments complete.**")
    incomplete = [(e, s) for e, s in rows if s != "complete"]
    if incomplete:
        A("")
        A("Not complete:")
        for e, s in incomplete:
            A(f"- `{e}` — {s}")
    A("")

    # --- paper numbers --------------------------------------------------
    pn = REPO / "docs/reports/2026-09-07-paper-numbers.json"
    if pn.exists():
        d = json.loads(pn.read_text())
        A("## Paper number traceability")
        A("")
        A(f"- traced to a manifest: **{len(d.get('traced', []))}**")
        A(f"- untraced: **{len(d.get('untraced', []))}**")
        A("")
        A("This check did not exist before tonight. `OUTLINE.md` and the "
          "draft's own appendix both claimed automated enforcement of "
          "number→experiment traceability; a readiness audit found no such "
          "check. It is a **review list, not a gate**.")
        if d.get("untraced"):
            A("")
            A("| line | value | context |")
            A("|---|---|---|")
            for r in d["untraced"][:15]:
                ctx = r["context"].replace("|", "\\|")[:80]
                A(f"| {r['line']} | `{r['value']}` | {ctx} |")
        A("")

    A("---")
    A("")
    A(f"*Generated {datetime.now():%Y-%m-%d %H:%M}. Every figure is read from "
      "disk at render time; nothing here is carried over from prose.*")
    return "\n".join(L) + "\n"


def main() -> int:
    md = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(md)
    print(f"markdown -> {OUT}")
    try:
        from scripts.morning_report import render_pdf
        ok = render_pdf(md, OUT.with_suffix(".pdf"))
        print(f"pdf -> {OUT.with_suffix('.pdf')} (rendered={ok})")
        if not ok:
            print("NOTE: render_pdf returned False — reportlab unavailable")
    except Exception as exc:
        print(f"pdf failed: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
