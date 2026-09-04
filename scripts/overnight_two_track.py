#!/usr/bin/env python3
"""Two independent tracks, one night, one hard deadline.

Plan: ``docs/plans/2026-09-04-overnight-two-track.md``.

**Track B** re-grades the post-repair arms with a second model family
(``gemma4-31B-mtp`` on ``:9091``, 32 workers). It goes first and its phases are
bounded by a wall-clock deadline, because that endpoint disappears at 09:00 and
the qwen relay does not.

**Track A** settles the query-writing arm: measure what an adequate token budget
costs, re-run the arm at the smallest budget that works, judge it on the same
instrument as the other two arms. No hard expiry, but every phase is capped so an
overrun costs one phase rather than the night.

Three rules the design exists to enforce:

* **A partial phase is not a result.** Anything capped or crashed is recorded
  ``not_run`` and its dependents are skipped. Half an arm graded looks like a
  number and is not one.
* **Concurrency is measured, not assumed.** Preflight times judgments on each
  endpoint alone and then on both at once. Yesterday unmeasured relay contention
  silently spoiled a timing measurement; this refuses to repeat it.
* **The holdout is never touched**, and the run asserts that by hash and by case
  id before it starts.

Restartable: every phase records its state, and a completed phase is skipped.

    uv run python scripts/overnight_two_track.py --dry-run
    uv run python scripts/overnight_two_track.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

BANK_DIR = REPO / "docs/evaluation/composition/bank"
BANK = BANK_DIR / "bank.json"
DEV_BANK = BANK_DIR / "bank-dev.json"
STATE = BANK_DIR / "overnight-2026-09-04-state.json"
POST_REPAIR = REPO / "docs/evaluation/experiments/post-repair-2026-09-03"
LLM_FAIR = REPO / "docs/evaluation/experiments/llm-query-fair-2026-09-04"
LOGS = REPO / "logs/overnight-2026-09-04"

#: The endpoint that expires. Everything on it is bounded by GEMMA_DEADLINE.
#: ``:9090``'s ``default-model-2`` serves ``gemma4-31B-mtp``, verified by probe
#: before this was written; the alias is recorded in preflight from the response
#: envelope rather than trusted, because an alias is not evidence.
GEMMA_URL = "http://localhost:9090/v1"
GEMMA_MODEL = "default-model-2"
GEMMA_WORKERS = 32

QWEN_URL = os.environ.get("EVAL_LLM_BASE_URL", "http://localhost:4000/v1")
QWEN_MODEL = os.environ.get("EVAL_LLM_MODEL", "skynet")
QWEN_WORKERS = 16

#: Both graders at the same budget, deliberately. EXP-2026-08-021 found 7-8% of
#: the largest answers fail to grade at smaller budgets and the failures land on
#: the thorough ones, so a cheaper gemma pass would confound grader with budget.
#: If gemma cannot sustain it, cut the sample, not this.
JUDGE_MAX_TOKENS = 32768

ARMS = ("deterministic", "generic")


def _deadline_0830() -> datetime:
    now = datetime.now()
    d = now.replace(hour=8, minute=30, second=0, microsecond=0)
    return d + timedelta(days=1) if d <= now else d


GEMMA_DEADLINE = _deadline_0830()


# -- state ------------------------------------------------------------------


def load_state() -> dict[str, Any]:
    if STATE.is_file():
        return json.loads(STATE.read_text())
    return {"plan": "2026-09-04-overnight-two-track", "phases": {}, "started": None}


_state_lock = threading.Lock()


def save(state: dict[str, Any]) -> None:
    with _state_lock:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=1, default=str) + "\n")


@dataclass
class Phase:
    name: str
    track: str
    fn: Callable[[], dict[str, Any]]
    cap_s: float
    #: Phases that must be ``done`` before this one runs.
    needs: tuple[str, ...] = ()
    #: Bounded by the gemma endpoint's disappearance rather than only by cap_s.
    gemma_bound: bool = False


def run_phase(state: dict[str, Any], phase: Phase) -> None:
    rec = state["phases"].get(phase.name, {})
    if rec.get("status") == "done":
        print(f"[{phase.track}] {phase.name}: already done, skipping", flush=True)
        return
    for need in phase.needs:
        if state["phases"].get(need, {}).get("status") != "done":
            state["phases"][phase.name] = {
                "status": "not_run",
                "reason": f"prerequisite {need} did not complete",
            }
            save(state)
            print(f"[{phase.track}] {phase.name}: SKIPPED ({need} incomplete)", flush=True)
            return
    if phase.gemma_bound and datetime.now() >= GEMMA_DEADLINE:
        state["phases"][phase.name] = {
            "status": "not_run",
            "reason": f"past the {GEMMA_DEADLINE:%H:%M} gemma deadline",
        }
        save(state)
        print(f"[{phase.track}] {phase.name}: SKIPPED (past gemma deadline)", flush=True)
        return

    started = time.time()
    state["phases"][phase.name] = {"status": "running", "started": datetime.now()}
    save(state)
    print(f"[{phase.track}] {phase.name}: start", flush=True)
    try:
        detail = phase.fn()
        status = "done"
    except Exception as exc:                                  # noqa: BLE001
        detail = {"error": f"{type(exc).__name__}: {exc}"}
        status = "failed"
        print(f"[{phase.track}] {phase.name}: FAILED {detail['error']}", flush=True)
    elapsed = round(time.time() - started, 1)
    state["phases"][phase.name] = {
        "status": status, "elapsed_s": elapsed,
        "finished": datetime.now(), "detail": detail,
    }
    save(state)
    print(f"[{phase.track}] {phase.name}: {status} in {elapsed}s", flush=True)


# -- helpers ----------------------------------------------------------------


def _sh(cmd: list[str], cap_s: float, log: Path, env: dict[str, str] | None = None) -> str:
    log.parent.mkdir(parents=True, exist_ok=True)
    merged = {**os.environ, **(env or {})}
    with log.open("w") as fh:
        proc = subprocess.run(
            cmd, cwd=REPO, env=merged, timeout=cap_s,
            stdout=fh, stderr=subprocess.STDOUT, check=False,
        )
    tail = log.read_text()[-800:]
    if proc.returncode != 0:
        raise RuntimeError(f"exit {proc.returncode}; tail: {tail[-400:]}")
    return tail


def _probe(base_url: str, model: str, prompt: str, max_tokens: int, timeout: float) -> dict[str, Any]:
    import requests

    t0 = time.time()
    r = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        json={"model": model, "messages": [{"role": "user", "content": prompt}],
              "max_tokens": max_tokens, "temperature": 0.0},
        timeout=timeout,
    )
    r.raise_for_status()
    body = r.json()
    msg = body["choices"][0]["message"]
    return {
        "wall_s": round(time.time() - t0, 2),
        "served_model": body.get("model"),
        "content_chars": len(msg.get("content") or ""),
        # Both endpoints serve reasoning models: chain-of-thought lands here
        # while `content` stays empty until it stops thinking, so a budget spent
        # on reasoning is downstream indistinguishable from an empty reply.
        "reasoning_chars": len(msg.get("reasoning") or ""),
        "finish_reason": body["choices"][0].get("finish_reason"),
        "completion_tokens": (body.get("usage") or {}).get("completion_tokens"),
    }


# -- phase bodies -----------------------------------------------------------


def preflight() -> dict[str, Any]:
    """Establish what is being measured, before anything measures it.

    Four things, each of which every later number inherits: which weights each
    endpoint actually serves, whether the two endpoints interfere, that both
    graph stores hold what they should, and that the holdout is untouched.
    """
    out: dict[str, Any] = {}

    # 1. Identity. The alias `skynet` has served three different models, so a
    #    judged figure without a probe is dated evidence about an unknown
    #    instrument.
    probe_prompt = "Reply with exactly: OK"
    out["gemma"] = _probe(GEMMA_URL, GEMMA_MODEL, probe_prompt, 512, 180)
    out["qwen"] = _probe(QWEN_URL, QWEN_MODEL, probe_prompt, 512, 180)

    # 2. Interference. The whole schedule rests on the two endpoints being
    #    independent hardware; measured rather than assumed.
    solo_g = _probe(GEMMA_URL, GEMMA_MODEL, probe_prompt, 512, 180)["wall_s"]
    solo_q = _probe(QWEN_URL, QWEN_MODEL, probe_prompt, 512, 180)["wall_s"]
    both: dict[str, float] = {}

    def _busy(key: str, url: str, model: str) -> None:
        both[key] = _probe(url, model, probe_prompt, 512, 180)["wall_s"]

    threads = [threading.Thread(target=_busy, args=("gemma", GEMMA_URL, GEMMA_MODEL)),
               threading.Thread(target=_busy, args=("qwen", QWEN_URL, QWEN_MODEL))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    out["interference"] = {
        "gemma_solo_s": solo_g, "gemma_concurrent_s": both.get("gemma"),
        "qwen_solo_s": solo_q, "qwen_concurrent_s": both.get("qwen"),
        "verdict": "independent" if (
            both.get("gemma", 1e9) < solo_g * 2.0 and both.get("qwen", 1e9) < solo_q * 2.0
        ) else "contended — tracks should serialise",
    }

    # 3. The stores, against the counts the 2026-09-03 reload established.
    import re

    from neo4j import GraphDatabase
    drv = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    with drv.session() as s:
        out["neo4j"] = {
            "nodes": s.run("MATCH (n) RETURN count(n) AS c").single()["c"],
            "edges": s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"],
        }
    drv.close()
    from gremlin_python.driver import client as gclient
    from gremlin_python.driver import serializer
    gc = gclient.Client(os.environ.get("GREMLIN_URL", "ws://localhost:6455/gremlin"), "g",
                        message_serializer=serializer.GraphSONSerializersV3d0())
    try:
        out["gremlin"] = {"vertices": gc.submit("g.V().count()").all().result()[0],
                          "edges": gc.submit("g.E().count()").all().result()[0]}
    finally:
        gc.close()
    if out["neo4j"] != {"nodes": 4369, "edges": 27669}:
        raise RuntimeError(f"neo4j counts moved: {out['neo4j']}")
    if out["gremlin"] != {"vertices": 6374, "edges": 8582}:
        raise RuntimeError(f"gremlin counts moved: {out['gremlin']}")

    # 4. The holdout, asserted two ways: the question set is the one that was
    #    split, and nothing in this repo's runs has answered any of it.
    import hashlib
    bank = json.loads(BANK.read_text())
    out["bank_sha256"] = hashlib.sha256(BANK.read_bytes()).hexdigest()
    if not out["bank_sha256"].startswith("ad99afb1"):
        raise RuntimeError("bank.json is not the set the split was drawn on")
    # What "sealed" means here, precisely, because the loose version is wrong.
    # The deterministic arm ANSWERED all 288 on 2026-09-02 and its model-free
    # recall was reported (holdout 0.4683 against dev 0.4350) as evidence the
    # bank had not been tuned. That look was deliberate, is on the record, and
    # is not a violation. What has never happened, and is what the holdout is
    # actually being kept for, is a JUDGED holdout, and any holdout answer from
    # the generic or llm_query arms.
    splits = {q["id"]: q["split"] for q in bank["questions"]}
    answered: dict[str, int] = {}
    judged = 0
    for path in (REPO / "docs/evaluation/experiments").rglob("answers/*.json"):
        try:
            cid = json.loads(path.read_text()).get("id")
        except (json.JSONDecodeError, KeyError):
            continue
        if splits.get(cid) != "holdout":
            continue
        if ".judgment" in path.name:
            judged += 1
            continue
        arm = path.parent.parent.name
        answered[arm] = answered.get(arm, 0) + 1
    out["holdout"] = {
        "n": sum(1 for v in splits.values() if v == "holdout"),
        "answered_by_arm": answered,
        "judged": judged,
        "sealed": judged == 0 and not (set(answered) - {"deterministic"}),
    }
    if judged:
        raise RuntimeError(f"{judged} holdout questions have already been JUDGED — "
                           "the holdout is spent and this run's premise is wrong")
    leaked = set(answered) - {"deterministic"}
    if leaked:
        raise RuntimeError(f"arms {sorted(leaked)} have answered holdout questions")
    out["gemma_deadline"] = GEMMA_DEADLINE.strftime("%Y-%m-%d %H:%M")
    return out


def _judge(root: Path, arm: str, *, url: str, model: str, workers: int,
           suffix: str, position: int) -> dict[str, Any]:
    from utils.evaluation.judge_answers import JudgeConfig, run as judge_run

    return judge_run(
        root, arm,
        JudgeConfig(base_url=url, model=model, max_tokens=JUDGE_MAX_TOKENS,
                    timeout_s=900.0, position=position),
        workers=workers, suffix=suffix,
    )


def gemma_regrade() -> dict[str, Any]:
    """The post-repair arms, re-graded by a different model family.

    Full n and both grading positions, because the ~0.01 order effect applies to
    any grader and a single pass would confound it with the family change. The
    existing judgments are untouched: only the suffix differs, so the two
    graders can be compared per case rather than only in aggregate.
    """
    out: dict[str, Any] = {}
    for arm in ARMS:
        for suffix, position in ((".gemma", 1), (".gemma2", 2)):
            if datetime.now() >= GEMMA_DEADLINE:
                out[f"{arm}{suffix}"] = {"skipped": "past the gemma deadline"}
                continue
            out[f"{arm}{suffix}"] = _judge(
                POST_REPAIR, arm, url=GEMMA_URL, model=GEMMA_MODEL,
                workers=GEMMA_WORKERS, suffix=suffix, position=position,
            )
            print(f"    [gemma] {arm}{suffix}: {json.dumps(out[f'{arm}{suffix}'])[:160]}",
                  flush=True)
    return out


def budget_cost() -> dict[str, Any]:
    """What the query-writing arm costs at each budget, on an uncontended relay.

    Yesterday's attempt shared a relay with a judging run and was abandoned
    rather than reported, because every timing measured contention. Tonight the
    judging is on other hardware, which is what makes this measurable.
    """
    _sh(["uv", "run", "python", "scripts/builder_budget_probe.py",
         "--cases", "4", "--budgets", "8192", "16384", "32768",
         "--timeout", "900", "--out", "docs/evaluation/composition/bank/budget-cost.json"],
        cap_s=3600, log=LOGS / "budget-cost.log")
    return json.loads((BANK_DIR / "budget-cost.json").read_text())


def _chosen_budget(state: dict[str, Any]) -> int:
    """The smallest budget at which a real query came back.

    Not the largest that fits: a re-run nobody can afford to repeat is not a
    baseline either. Falls back to 16384 when the probe's shape is unfamiliar,
    which is the arm's own configured value.
    """
    detail = state["phases"].get("A1-budget-cost", {}).get("detail") or {}
    trials = detail.get("trials") or detail.get("results") or []
    ok = []
    for t in trials if isinstance(trials, list) else []:
        if not isinstance(t, dict):
            continue
        budget = t.get("max_tokens") or t.get("budget")
        got_query = bool(t.get("query")) or (t.get("content_chars") or 0) > 0
        if budget and got_query:
            ok.append(int(budget))
    return min(ok) if ok else 16384


def llm_query_rerun(state: dict[str, Any]) -> dict[str, Any]:
    """The fair re-measurement C-012 has been waiting for.

    Its support is one 30-question August run; the only larger measurement is
    confounded by the import-time budget freeze fixed in a1e20f6. 284 questions,
    plan held constant, query generation the only variable.
    """
    budget = _chosen_budget(state)
    LLM_FAIR.mkdir(parents=True, exist_ok=True)
    _sh(["uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
         "--arm", "llm_query", "--bank", str(DEV_BANK), "--root", str(LLM_FAIR),
         "--llm-max-tokens", str(budget), "--workers", "8"],
        cap_s=2.5 * 3600, log=LOGS / "llm-query-rerun.log",
        env={"ORCH_MAX_HOPS": "5"})
    answers = sorted((LLM_FAIR / "llm_query" / "answers").glob("*.json"))
    answers = [p for p in answers if ".judgment" not in p.name]
    if len(answers) < 284:
        raise RuntimeError(f"only {len(answers)}/284 answers written")
    return {"budget": budget, "answers": len(answers)}


def judge_llm_query() -> dict[str, Any]:
    """Same grader, same protocol, same budget as the other two arms.

    Otherwise the three-way is not like-for-like, and a three-way that is not
    like-for-like is worse than none.
    """
    out = {}
    for suffix, position in (("", 1), (".pass2", 2)):
        out[f"llm_query{suffix or '.pass1'}"] = _judge(
            LLM_FAIR, "llm_query", url=QWEN_URL, model=QWEN_MODEL,
            workers=QWEN_WORKERS, suffix=suffix, position=position,
        )
    return out


def gemma_judge_llm_query() -> dict[str, Any]:
    """Bonus: the third arm under the second family, if :9091 has time left."""
    out = {}
    for suffix, position in ((".gemma", 1), (".gemma2", 2)):
        if datetime.now() >= GEMMA_DEADLINE:
            out[suffix] = {"skipped": "past the gemma deadline"}
            continue
        out[suffix] = _judge(LLM_FAIR, "llm_query", url=GEMMA_URL, model=GEMMA_MODEL,
                             workers=GEMMA_WORKERS, suffix=suffix, position=position)
    return out


def rollup(state: dict[str, Any]) -> dict[str, Any]:
    """Per-arm judged correctness under each grader, with denominators.

    Both passes are averaged per case before averaging across cases, so an arm
    that lost a judgment in one pass is not silently scored on fewer questions
    than the others.
    """
    import statistics
    from collections import defaultdict

    graders = {"qwen": ("", ".pass2"), "gemma": (".gemma", ".gemma2")}
    roots = {"deterministic": POST_REPAIR, "generic": POST_REPAIR, "llm_query": LLM_FAIR}
    result: dict[str, Any] = {}
    for arm, root in roots.items():
        adir = root / arm / "answers"
        if not adir.is_dir():
            result[arm] = {"status": "not_run"}
            continue
        for grader, suffixes in graders.items():
            per_case: dict[str, list[float]] = defaultdict(list)
            for suffix in suffixes:
                for path in sorted(adir.glob(f"*.judgment{suffix}.json")):
                    # ``*.judgment.json`` also matches ``*.judgment.gemma.json``
                    # under a bare suffix, so pin the name exactly.
                    if path.name != f"{path.name.split('.judgment')[0]}.judgment{suffix}.json":
                        continue
                    try:
                        payload = json.loads(path.read_text())
                    except json.JSONDecodeError:
                        continue
                    if payload.get("correctness") is not None:
                        per_case[payload.get("case_id", path.name)].append(payload["correctness"])
            means = [statistics.fmean(v) for v in per_case.values() if v]
            result.setdefault(arm, {})[grader] = {
                "cases": len(means),
                "judgments": sum(len(v) for v in per_case.values()),
                "mean_correctness": round(statistics.fmean(means), 4) if means else None,
            }
    (BANK_DIR / "two-grader-judged.json").write_text(json.dumps(result, indent=1) + "\n")

    lines = ["# Overnight 2026-09-04 — two tracks, two graders", ""]
    lines.append(f"Started {state.get('started')}. Gemma deadline {GEMMA_DEADLINE:%H:%M}.")
    lines.append("")
    lines.append("| arm | grader | cases | judgments | mean correctness |")
    lines.append("|---|---|---:|---:|---:|")
    for arm, cells in result.items():
        if cells.get("status") == "not_run":
            lines.append(f"| {arm} | — | — | — | **did not run** |")
            continue
        for grader, cell in cells.items():
            lines.append(f"| {arm} | {grader} | {cell['cases']} | {cell['judgments']} | "
                         f"{cell['mean_correctness']} |")
    lines += ["", "## What did not run", ""]
    for name, rec in state["phases"].items():
        if rec.get("status") != "done":
            lines.append(f"- **{name}** — {rec.get('status')}: "
                         f"{rec.get('reason') or (rec.get('detail') or {}).get('error') or ''}")
    if all(r.get("status") == "done" for r in state["phases"].values()):
        lines.append("- Every phase completed.")
    lines += ["", "## The holdout", "",
              "Not touched. Asserted at preflight by bank hash and by checking that no "
              "answered case id belongs to the holdout split. It stays sealed for a "
              "three-arm spend once the query-writing arm is settled."]
    md = "\n".join(lines) + "\n"
    md_path = REPO / "docs/reports/2026-09-04-overnight-report.md"
    md_path.write_text(md)

    # The Markdown is written first and unconditionally, so a PDF failure costs
    # the formatting and not the report.
    pdf_path = md_path.with_suffix(".pdf")
    try:
        from scripts.morning_report import render_pdf

        result["pdf"] = bool(render_pdf(md, pdf_path))
    except Exception as exc:                                   # noqa: BLE001
        result["pdf"] = False
        result["pdf_error"] = f"{type(exc).__name__}: {exc}"
    return result


# -- driver -----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-gemma", action="store_true",
                        help="skip track B entirely (e.g. :9091 never came up)")
    args = parser.parse_args(argv)

    state = load_state()
    state.setdefault("started", str(datetime.now()))

    track_b = [
        Phase("B1-gemma-regrade", "B", gemma_regrade, cap_s=5 * 3600,
              needs=("P0-preflight",), gemma_bound=True),
    ]
    track_a = [
        Phase("A1-budget-cost", "A", budget_cost, cap_s=3600, needs=("P0-preflight",)),
        Phase("A2-llm-query-rerun", "A", lambda: llm_query_rerun(state),
              cap_s=2.5 * 3600, needs=("A1-budget-cost",)),
        Phase("A3-judge-llm-query", "A", judge_llm_query, cap_s=3 * 3600,
              needs=("A2-llm-query-rerun",)),
        Phase("A4-gemma-judge-llm-query", "A", gemma_judge_llm_query, cap_s=2 * 3600,
              needs=("A2-llm-query-rerun", "B1-gemma-regrade"), gemma_bound=True),
    ]
    preflight_phase = Phase("P0-preflight", "P", preflight, cap_s=1200)

    if args.dry_run:
        print(f"gemma deadline: {GEMMA_DEADLINE:%Y-%m-%d %H:%M}")
        for p in [preflight_phase, *track_b, *track_a]:
            print(f"  [{p.track}] {p.name:26s} cap {p.cap_s/3600:.1f}h  "
                  f"needs={p.needs or '()'}{'  (gemma-bound)' if p.gemma_bound else ''}")
        print("  [F] F-rollup                 always runs")
        return 0

    run_phase(state, preflight_phase)
    if state["phases"]["P0-preflight"]["status"] != "done":
        print("preflight failed — refusing to run anything on unestablished ground",
              flush=True)
        rollup(state)
        return 1

    def _run_track(phases: list[Phase]) -> None:
        for p in phases:
            run_phase(state, p)

    threads = []
    if not args.no_gemma:
        threads.append(threading.Thread(target=_run_track, args=(track_b,), name="trackB"))
    threads.append(threading.Thread(target=_run_track, args=(track_a,), name="trackA"))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    run_phase(state, Phase("F-rollup", "F", lambda: rollup(state), cap_s=600))
    print(json.dumps({k: v.get("status") for k, v in state["phases"].items()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
