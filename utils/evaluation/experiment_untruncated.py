#!/usr/bin/env python3
"""Controlled two-arm experiment: what does *un-truncated* retrieval buy us?

Both arms run the **same 120 golden questions, in the same order, against the
same two graphs**. The only differences are the two independent variables:

* **ARM A — deterministic** (``--arm deterministic``): the reproducible path.
  Each entry's pre-authored ``task`` / ``sub_questions`` are replayed through
  ``score_e2e.run_single`` / ``run_federated`` with the specialist LLM drafter
  **off** and a bare ``SynthesisConfig()`` — deterministic drafters, deterministic
  composer, no narrator. No LLM anywhere in the loop.
* **ARM B — llm** (``--arm llm``): the agentic path. Each *raw question* is driven
  through ``iter_pipeline(question, use_llm=True)``, so the LLM plans and routes
  it, drafts the queries, and writes the narrative. Both LLM planning and LLM
  synthesis are on.

The **common** change to both arms is the un-truncation profile
(:func:`untruncated_env`): every retrieval, synthesis-evidence and artifact bound
is lifted so ``describe``/``expand`` return full neighbourhoods and the synthesis
stage receives the whole evidence set rather than a sampled id line. The bounds
are env-driven with the committed defaults intact, so a normal run is unaffected.

Artifacts are the *same shape* the independent-eval panel already grades
(``generate_e2e._artifact``), so the existing 120-agent Sonnet judge harness runs
over either arm unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

DEFAULT_ROOT = "docs/evaluation/experiments/untruncated"
# ARM C ("gold_llm") is the control that makes the other two readable: it is the
# committed baseline's exact configuration (gold-replay plan + LLM drafter + LLM
# synthesis) with ONLY the un-truncation profile added, so C − baseline isolates
# un-truncation, A − C isolates the composer, and B − C isolates LLM planning.
ARMS = ("deterministic", "llm", "gold_llm", "llm_loop", "gold_loop_llm", "generic",
        "llm_query", "merged")

# -- the un-truncation profile ----------------------------------------------
# Every one of these keys is read *at call time* by the bound it names, with the
# committed default preserved when the key is absent. Setting them all is what
# "lift the caps" means operationally; the numbers are deliberately far above any
# real fan-out in the catalogue (the largest is TrickBot's 55 techniques, the
# widest scan ~300 rows) rather than infinite, so a runaway query still stops.
UNTRUNCATED_ENV: dict[str, str] = {
    # -- retrieval: how much the graphs are allowed to return -----------------
    "SPECIALIST_MAX_RESULT_ROWS": "20000",      # hard ceiling (was 1000)
    "SPECIALIST_EXPAND_PAGE_SIZE": "20000",     # expand paging cap (was 50)
    "SPECIALIST_RELATED_DESC_CHARS": "20000",   # neighbour description (was 400)
    "SPECIALIST_EXPAND_DESC_CHARS": "20000",    # expand-member description (was 400)
    # -- synthesis: how much evidence the composer/narrator actually sees ------
    "SYNTHESIS_MAX_RECORDS_PER_RESULT": "2000",   # was 50
    "SYNTHESIS_MAX_RELATED_PER_RECORD": "2000",   # was 30
    "SYNTHESIS_MAX_FACETS_PER_RECORD": "200",     # was 20
    "SYNTHESIS_MAX_PROP_CHARS": "20000",          # was 600
    "SYNTHESIS_MAX_RELATED_DESC_CHARS": "20000",  # was 400
    "SYNTHESIS_MAX_PROP_LIST_ITEMS": "500",       # was 10
    "SYNTHESIS_MAX_ENUMERATION_IDS": "2000",      # was 200
    "SYNTHESIS_MAX_ENUMERATION_CLAIMS": "500",    # was 25
    "SYNTHESIS_MAX_CITATIONS": "200",             # fact-claim id sample (was 8)
    # -- the judge's artifact: it must see everything the pipeline saw ---------
    "EVAL_ARTIFACT_MAX_RECORDS": "2000",        # was 50
    "EVAL_ARTIFACT_MAX_RELATED": "2000",        # was 100
    "EVAL_ARTIFACT_MAX_FACETS": "200",          # was 20
    "EVAL_ARTIFACT_MAX_DESC_CHARS": "20000",    # was 600
    "EVAL_ARTIFACT_MAX_PROP_LIST_ITEMS": "500",  # was 10
}

# The per-task row cap authored into every bank entry (``questions.py``
# ATTACK_LIMITS / CAPEC_LIMITS). Overridden in memory so the committed banks —
# and therefore the gold set and question order — stay byte-identical.
TASK_MAX_RESULT_ROWS = 20000
TASK_MAX_TRAVERSAL_DEPTH = 3  # unchanged: depth is the question's shape, not a cap


def untruncated_env(*, arm: str, llm_model: str, llm_max_tokens: int) -> dict[str, str]:
    """The full env overlay for one arm (bounds + that arm's LLM posture)."""
    env = dict(UNTRUNCATED_ENV)
    if arm in ("llm_loop", "gold_loop_llm", "generic"):
        # ARM E — the workbench flow as designed: LLM planning + LLM synthesis
        # **with the iterative retrieval loop actually chasing something**. Arm B
        # ran at ORCH_MAX_HOPS=5 but still executed a single pass, because
        # sufficiency was decided purely by cross-source join closure — a
        # single-source question had no join and was "sufficient by construction"
        # after one hop, and a describe that returned only facet COUNTS looked
        # complete. ORCH_CHASE_FACETS makes an un-fetched, question-relevant facet
        # a real gap, so the loop re-plans an expansion hop for it.
        env.update({
            "PLANNER_LLM_ENABLED": "true",
            "SPECIALIST_LLM_ENABLED": "true",
            "SYNTHESIS_LLM_ENABLED": "true",
            "PLANNER_LLM_MODEL": llm_model,
            "SPECIALIST_LLM_MODEL": llm_model,
            "SYNTHESIS_LLM_MODEL": llm_model,
            "PLANNER_LLM_MAX_TOKENS": str(llm_max_tokens),
            "SPECIALIST_LLM_MAX_TOKENS": str(llm_max_tokens),
            "SYNTHESIS_LLM_MAX_TOKENS": str(llm_max_tokens),
            "SYNTHESIS_LLM_THINKING_BUDGET": str(llm_max_tokens // 2),
            "ORCH_MAX_HOPS": "5",
            "ORCH_CHASE_FACETS": "true",
            "ORCH_MAX_FACET_EXPANSIONS": "4",
        })
        if arm == "generic":
            # ARM G — the "no hand-written templates" control. Identical to ARM F
            # except every MITRE question-shape template is disabled, so the
            # pipeline must answer from schema-driven primitives alone. The delta
            # F − G is exactly what the 19 bespoke templates are worth.
            env["SPECIALIST_GENERIC_ONLY"] = "true"
    elif arm == "gold_llm":
        # Match the committed baseline byte-for-byte except the bounds: the .env
        # LLM seams stay exactly as generate_e2e.py reads them.
        env.update({
            "PLANNER_LLM_ENABLED": "false",   # gold plan is replayed; planner never runs
            "SPECIALIST_LLM_ENABLED": "true",
            "SYNTHESIS_LLM_ENABLED": "true",
            "SPECIALIST_LLM_MODEL": llm_model,
            "SYNTHESIS_LLM_MODEL": llm_model,
            "SPECIALIST_LLM_MAX_TOKENS": str(llm_max_tokens),
            "SYNTHESIS_LLM_MAX_TOKENS": str(llm_max_tokens),
            "SYNTHESIS_LLM_THINKING_BUDGET": str(llm_max_tokens // 2),
        })
    elif arm == "llm_query":
        # The C-012 baseline: Arm A exactly — gold-replay plan, deterministic
        # extraction, deterministic composition — with ONE variable changed, the
        # thing that writes the query. Holding the plan constant is the point: a
        # difference against `deterministic` is then attributable to query
        # generation and to nothing else. `llm` already varies planning.
        env.update({
            "PLANNER_LLM_ENABLED": "false",
            "SYNTHESIS_LLM_ENABLED": "false",
            "CONVERSATION_LLM_ENABLED": "false",
            # Distinct from SPECIALIST_LLM_ENABLED, which four other arms set to
            # mean "LLM drafter/synthesis" and which no builder reads.
            "SPECIALIST_LLM_QUERY_BUILDER": "true",
            "SPECIALIST_LLM_ENABLED": "false",
            "SPECIALIST_LLM_MODEL": llm_model,
            "SPECIALIST_LLM_MAX_TOKENS": str(llm_max_tokens),
        })
    elif arm == "merged":
        # The C-015 counterfactual: ONE store holding both catalogues instead of
        # two engines speaking two languages. Everything else is held at Arm H's
        # posture — no LLM anywhere, templates disabled so a single uniform
        # capability answers both halves — because Arm H is what this is
        # compared against and the number is only worth having if exactly one
        # thing differs between them.
        #
        # The isolation is these two variables and nothing else. ARIADNE_DATA_DIR
        # points the source-card loader and the schema registry at the merged
        # dataset, which lives outside `data/` precisely so no other arm can see
        # it; NEO4J_URI points at the second container. Neither is set anywhere
        # else, so no other arm can reach the merged store either.
        env.update({
            "ARIADNE_DATA_DIR": "data-merged",
            "NEO4J_URI": "bolt://localhost:5458",
            "SPECIALIST_GENERIC_ONLY": "true",
            "PLANNER_LLM_ENABLED": "false",
            "SPECIALIST_LLM_ENABLED": "false",
            "SYNTHESIS_LLM_ENABLED": "false",
            "CONVERSATION_LLM_ENABLED": "false",
        })
    elif arm == "deterministic":
        # Reproducible mode: no LLM in planning, drafting, or synthesis.
        env.update({
            "PLANNER_LLM_ENABLED": "false",
            "SPECIALIST_LLM_ENABLED": "false",
            "SYNTHESIS_LLM_ENABLED": "false",
            "CONVERSATION_LLM_ENABLED": "false",
        })
    else:
        # LLM planning + LLM synthesis. Every caller gets a generous budget: the
        # local model is a reasoning model and truncates to empty on a small one.
        env.update({
            "PLANNER_LLM_ENABLED": "true",
            "SPECIALIST_LLM_ENABLED": "true",
            "SYNTHESIS_LLM_ENABLED": "true",
            "PLANNER_LLM_MODEL": llm_model,
            "SPECIALIST_LLM_MODEL": llm_model,
            "SYNTHESIS_LLM_MODEL": llm_model,
            "PLANNER_LLM_MAX_TOKENS": str(llm_max_tokens),
            "SPECIALIST_LLM_MAX_TOKENS": str(llm_max_tokens),
            "SYNTHESIS_LLM_MAX_TOKENS": str(llm_max_tokens),
            # Cap *reasoning* to half the budget so visible output always has room.
            "SYNTHESIS_LLM_THINKING_BUDGET": str(llm_max_tokens // 2),
            # The iterative-retrieval loop is part of an honest LLM-planned arm
            # (the repo default); the user's .env pins it to 1.
            "ORCH_MAX_HOPS": "5",
        })
    return env


def apply_env(overlay: dict[str, str]) -> None:
    os.environ.update(overlay)


#: Assertions that make a question about *which entities*, not *how many*.
_CONTENT_ASSERTIONS = (
    "must_include_ids", "must_include_related", "must_correlate",
    "expect_names", "expect_properties",
)


def is_bounded_scan(entry: dict) -> bool:
    """True when the entry's gold is *purely quantitative* — a record-count window.

    Nearly every entry carries ``max_records`` (a lookup asserts 1), so the cap
    alone means nothing. A **scan** is the case where the count IS the whole
    requirement: ``{"min_records": 250, "max_records": 300}`` with no id, name or
    property assertion. There the row limit is the answer's specification ("a
    label scan must come back bounded"), not an incidental sampling cap, so
    lifting it would violate the contract the question exists to test. Every other
    question keeps the full un-truncation.
    """
    def _scan_like(asserts: Any) -> bool:
        if not isinstance(asserts, dict):
            return False
        if asserts.get("max_records") is None:
            return False
        if any(asserts.get(k) for k in _CONTENT_ASSERTIONS):
            return False
        return True

    asserts = entry.get("assertions") or {}
    if _scan_like(asserts):
        return True
    return any(_scan_like(v) for v in asserts.values())


def lift_task_limits(entry: dict) -> dict:
    """Return ``entry`` with every *sampling* row cap lifted (in memory only)."""
    if is_bounded_scan(entry):
        return entry

    def _lift(limits: dict | None) -> dict:
        out = dict(limits or {})
        out["max_result_rows"] = TASK_MAX_RESULT_ROWS
        out.setdefault("max_traversal_depth", TASK_MAX_TRAVERSAL_DEPTH)
        return out

    patched = dict(entry)
    if isinstance(patched.get("task"), dict):
        task = dict(patched["task"])
        task["limits"] = _lift(task.get("limits"))
        patched["task"] = task
    if isinstance(patched.get("sub_questions"), list):
        patched["sub_questions"] = [
            {**sub, "limits": _lift(sub.get("limits"))} if isinstance(sub, dict) else sub
            for sub in patched["sub_questions"]
        ]
    return patched


# -- the work list (identical for both arms) --------------------------------


def load_work(bank: str | None = None) -> list[tuple[dict, str]]:
    """The catalogue entries in a fixed order: federated, then attack, capec.

    With ``bank`` set, load that single bank file instead of the three committed
    ones — this is how the blind holdout runs through the identical arm code
    rather than through a parallel path that would have to be trusted separately.
    A federated entry is the one carrying ``sub_questions``; a single-source
    entry's kind is its ``task.source``.
    """
    if bank:
        entries = json.loads(Path(bank).read_text())["questions"]
        federated = [e for e in entries if "sub_questions" in e]
        attack_q = [e for e in entries if "task" in e and e["task"]["source"] == "attack"]
        capec_q = [e for e in entries if "task" in e and e["task"]["source"] == "capec"]
    else:
        from utils.evaluation.score_e2e import _load_banks

        federated, attack_q, capec_q = _load_banks()
    work: list[tuple[dict, str]] = [(e, "federated") for e in federated]
    work += [(e, "attack") for e in attack_q]
    work += [(e, "capec") for e in capec_q]
    return [(lift_task_limits(e), kind) for e, kind in work]


# -- ARM A: deterministic ---------------------------------------------------


class _RouterPool:
    """Thread-local router sets — the Gremlin client is not shareable."""

    def __init__(self, llm_enabled: bool, llm_query_builder: bool = False) -> None:
        self._local = threading.local()
        self._llm = llm_enabled
        self._llm_query_builder = llm_query_builder

    def _build(self) -> dict[str, Any]:
        import dataclasses

        from utils.specialists.config import SpecialistConfig
        from utils.specialists.federation import SpecialistRouter

        config = dataclasses.replace(
            SpecialistConfig.from_env(),
            llm_enabled=self._llm,
            llm_query_builder=self._llm_query_builder,
        )
        full = SpecialistRouter(config)
        return {
            "full": full,
            "routers": {
                None: full,
                "boundary": full,
                "attack_down": SpecialistRouter(
                    config, cards=full.cards, specialists={"attack": None}
                ),
                "capec_down": SpecialistRouter(
                    config, cards=full.cards, specialists={"capec": None}
                ),
            },
        }

    def get(self) -> dict[str, Any]:
        state = getattr(self._local, "state", None)
        if state is None:
            state = self._build()
            self._local.state = state
        return state


class _MergedPool:
    """One Cypher specialist over the merged store, standing in for both sources.

    The federated arms route an ATT&CK sub-question to the Cypher specialist and
    a CAPEC one to the Gremlin specialist. Here both land on the same specialist,
    because there is only one store. Everything upstream is untouched: the
    authored plan still declares two sub-questions and a join, `run_plan` still
    orders producer before consumer and seeds the consumer from the producer's
    join values, and synthesis still assembles the answer the same way. What
    changes is that the two retrievals hit one engine in one language.

    Holding the plan constant is the whole point. A merged arm that also
    collapsed the decomposition would differ from Arm H in two ways at once, and
    the resulting number would not say which one moved it.

    Thread-local like `_RouterPool`, for the same reason: a database client is
    not safely shareable across the worker threads.
    """

    def __init__(self) -> None:
        self._local = threading.local()

    def _build(self) -> dict[str, Any]:
        import dataclasses

        from utils.planner.cards import load_source_cards
        from utils.specialists import build_specialist
        from utils.specialists.config import SpecialistConfig
        from utils.specialists.federation import SpecialistRouter

        config = dataclasses.replace(
            SpecialistConfig.from_env(), llm_enabled=False, llm_query_builder=False
        )
        cards = load_source_cards(config.data_dir)
        card = cards.get("merged")
        if card is None:
            raise RuntimeError(
                f"no merged source card under {config.data_dir}/source_cards — "
                "build it with `uv run python -m utils.kg_builder.merge`"
            )
        specialist = build_specialist("merged", card, config)

        def router(**overrides: Any) -> SpecialistRouter:
            # `_specialist_for` short-circuits on this dict, so the merged
            # specialist answers for both source names the plan uses. A `None`
            # entry means that source is unreachable, which is how the partial
            # modes reproduce the abstention behaviour the C-ABS questions test.
            specialists: dict[str, Any] = {"attack": specialist, "capec": specialist}
            specialists.update(overrides)
            return SpecialistRouter(config, cards=cards, specialists=specialists)

        full = router()
        return {
            "full": full,
            "specialist": specialist,
            "routers": {
                None: full,
                "boundary": full,
                "attack_down": router(attack=None),
                "capec_down": router(capec=None),
            },
        }

    def get(self) -> dict[str, Any]:
        state = getattr(self._local, "state", None)
        if state is None:
            state = self._build()
            self._local.state = state
        return state


def _run_gold_replay(entry: dict, kind: str, pool: _RouterPool, *, llm_synthesis: bool
                     ) -> tuple[Any, Any, dict]:
    """Replay the authored task/plan; synthesis is deterministic or the LLM narrator."""
    from utils.evaluation.score_e2e import run_federated, run_single
    from utils.synthesis.config import SynthesisConfig

    # from_env() turns the narrator on (ARM C, the baseline's config); the bare
    # constructor is deterministic-composer-only (ARM A).
    synth = SynthesisConfig.from_env() if llm_synthesis else SynthesisConfig()
    state = pool.get()
    if kind == "federated":
        router = state["routers"][entry.get("partial_mode")]
        evidence, answer = run_federated(entry, router, synth)
    else:
        specialist = state["full"]._specialist_for(kind)
        if specialist is None:
            raise RuntimeError(f"no specialist for source {kind!r}")
        evidence, answer = run_single(entry, specialist, synth)
    return evidence, answer, {
        "planner": "gold-replay",
        "synthesis": "llm" if llm_synthesis else "deterministic",
    }


def run_deterministic(entry: dict, kind: str, pool: _RouterPool) -> tuple[Any, Any, dict]:
    """ARM A — gold-replay plan, no LLM anywhere."""
    return _run_gold_replay(entry, kind, pool, llm_synthesis=False)


def run_gold_llm(entry: dict, kind: str, pool: _RouterPool) -> tuple[Any, Any, dict]:
    """ARM C — the baseline's configuration, un-truncated: gold plan + LLM synthesis."""
    return _run_gold_replay(entry, kind, pool, llm_synthesis=True)


# -- ARM B: LLM-planned + LLM synthesis -------------------------------------


def _plan_dict(plan: Any) -> list[dict[str, Any]]:
    subs = getattr(plan, "sub_questions", None) or []
    out = []
    for sub in subs:
        out.append({
            "sub_question_id": getattr(sub, "id", None),
            "source": getattr(sub, "source", None),
            "text": getattr(sub, "text", None),
            "seed_ids": list(getattr(sub, "seed_ids", ()) or ()),
            "depends_on": getattr(sub, "depends_on", None),
            "limits": (
                sub.limits.to_dict()
                if hasattr(getattr(sub, "limits", None), "to_dict") else None
            ),
        })
    return out


def _gold_plan(entry: dict, kind: str):
    """The catalogue's authored plan as a real :class:`Plan`.

    Federated entries carry ``sub_questions`` + a declared join; single-source
    entries carry one ``task``. Both become the same shape so the orchestration
    graph can run them, which is what lets the retrieval loop operate on top of
    an *accurate* plan instead of a model-drafted one.
    """
    from utils.evaluation.score_e2e import _build_plan
    from utils.planner.schema import Limits, Plan, SubQuestion

    if kind == "federated":
        return _build_plan(entry)
    task = entry["task"]
    return Plan(
        request=entry["question"],
        sub_questions=[
            SubQuestion(
                id=task.get("sub_question_id") or "q1",
                source=task["source"],
                text=task["text"],
                entities=list(task.get("entities") or []),
                limits=Limits(**(task.get("limits") or {})),
                join_key=task.get("join_key"),
                rationale="golden evalset",
            )
        ],
    )


class _GoldPlanAgent:
    """A ``PlanningAgent`` whose first plan is the authored one.

    Everything else — cards, the liveness probe, and crucially ``replan`` — is the
    real agent, so the iterative loop behaves exactly as it does in the app. This
    isolates the synthesizer: retrieval starts from a plan that is known-correct,
    so any remaining gap is the loop's or the writer's, not the planner's.
    """

    def __init__(self, inner, plan):
        self._inner = inner
        self._plan = plan

    def plan(self, request: str):
        return self._plan

    def replan(self, *args, **kwargs):
        return self._inner.replan(*args, **kwargs)

    def __getattr__(self, name):  # cards, _cards, _probe, …
        return getattr(self._inner, name)


def run_gold_loop_llm(entry: dict, kind: str, _pool: Any) -> tuple[Any, Any, dict]:
    """ARM F — accurate deterministic extraction + the loop + LLM synthesis.

    The authored plan supplies correct seeding (no planner variance), the
    deterministic templates do the extraction, the facet loop chases anything a
    first hop only counted, and the claim-grounded narrator writes the answer.
    """
    import dataclasses

    from utils.orchestration.main import PipelineRun, iter_pipeline
    from utils.planner.agent import PlanningAgent
    from utils.planner.config import PlannerConfig

    inner = PlanningAgent(dataclasses.replace(PlannerConfig.from_env(), llm_enabled=False))
    agent = _GoldPlanAgent(inner, _gold_plan(entry, kind))

    injected: dict[str, Any] | None = None
    mode = entry.get("partial_mode")
    if mode == "attack_down":
        injected = {"attack": None}
    elif mode == "capec_down":
        injected = {"capec": None}

    run = PipelineRun(question=entry["question"], mode="query")
    plan = evidence = answer = None
    for event, payload in iter_pipeline(
        entry["question"], mode="query", use_llm=True,
        agent=agent, specialists=injected, run=run,
    ):
        if event == "plan":
            plan = payload.get("plan")
        elif event == "evidence":
            evidence = payload.get("evidence")
        elif event == "answer":
            plan = payload.get("plan") or plan
            evidence = payload.get("evidence") or evidence
            answer = payload.get("synthesized")
    if answer is None or evidence is None:
        raise RuntimeError(f"pipeline produced no answer (status={run.status!r})")
    return evidence, answer, {
        "planner": "gold-plan (injected)",
        "synthesis": "llm (claim-grounded)",
        "loop": "facet-chasing",
        "observed_plan": _plan_dict(plan),
        "exit_code": run.exit_code,
        "status": run.status,
    }


def run_llm(entry: dict, kind: str, _pool: Any) -> tuple[Any, Any, dict]:
    """Drive the raw question through the real LLM pipeline (plan + synthesis)."""
    from utils.orchestration.main import PipelineRun, iter_pipeline

    # A partial-degradation scenario must still run with its source absent, or the
    # question the entry poses (what happens when CAPEC is down?) is not the one asked.
    injected: dict[str, Any] | None = None
    mode = entry.get("partial_mode")
    if mode == "attack_down":
        injected = {"attack": None}
    elif mode == "capec_down":
        injected = {"capec": None}

    run = PipelineRun(question=entry["question"], mode="query")
    plan = evidence = answer = None
    for event, payload in iter_pipeline(
        entry["question"], mode="query", use_llm=True, specialists=injected, run=run
    ):
        if event == "plan":
            plan = payload.get("plan")
        elif event == "evidence":
            evidence = payload.get("evidence")
        elif event == "answer":
            plan = payload.get("plan") or plan
            evidence = payload.get("evidence") or evidence
            answer = payload.get("synthesized")
    if answer is None or evidence is None:
        raise RuntimeError(f"pipeline produced no answer (status={run.status!r})")
    return evidence, answer, {
        "planner": "llm",
        "synthesis": "llm",
        "observed_plan": _plan_dict(plan),
        "exit_code": run.exit_code,
        "status": run.status,
    }


# -- driver -----------------------------------------------------------------


RUNNERS = {
    "deterministic": run_deterministic,
    "llm": run_llm,
    "gold_llm": run_gold_llm,
    "llm_loop": run_llm,   # same driver; the arm differs only in its env
    "gold_loop_llm": run_gold_loop_llm,
    "generic": run_gold_loop_llm,   # same driver; templates disabled via env
    # Same driver as ARM A: the arm differs only in who writes the query, which
    # is decided by the pool's SpecialistConfig, not by the runner.
    "llm_query": run_deterministic,
    # Same driver again: the gold-replay path does not care how many stores are
    # behind the router it is handed. `_MergedPool` is what makes it one.
    "merged": run_deterministic,
}


def _one(entry: dict, kind: str, arm: str, pool: Any) -> dict[str, Any]:
    from utils.evaluation.generate_e2e import _artifact

    started = time.time()
    evidence, answer, extra = RUNNERS[arm](entry, kind, pool)
    artifact = _artifact(entry, kind, evidence, answer)
    artifact["arm"] = arm
    artifact["run_meta"] = {**extra, "wall_s": round(time.time() - started, 3)}
    # The evidence volume this arm actually pulled — the experiment's headline
    # retrieval statistic, and the thing the caps used to bound.
    artifact["evidence_volume"] = {
        "results": len(evidence.results),
        "records": sum(len(r.records) for r in evidence.results),
        "related": sum(len(rec.related) for r in evidence.results for rec in r.records),
    }
    return artifact


def run_arm(
    arm: str,
    *,
    root: str = DEFAULT_ROOT,
    workers: int = 4,
    limit: int | None = None,
    only: set[str] | None = None,
    bank: str | None = None,
) -> dict[str, Any]:
    """Run every question in the bank for one arm, persisting answer + evidence."""
    from utils.evaluation.score_e2e import _category_of

    work = load_work(bank)
    if only:
        work = [(e, k) for e, k in work if e["id"] in only]
    if limit is not None:
        work = work[:limit]

    out = Path(root) / arm / "answers"
    out.mkdir(parents=True, exist_ok=True)
    # ARM B builds its own specialists inside iter_pipeline; the gold-replay arms
    # share a thread-local router set (ARM C keeps the .env LLM drafter, as the
    # baseline did; ARM A forces it off).
    if arm in ("llm", "llm_loop", "gold_loop_llm", "generic"):
        pool = None
    elif arm == "merged":
        pool = _MergedPool()
    else:
        pool = _RouterPool(
            llm_enabled=(arm == "gold_llm"),
            llm_query_builder=(arm == "llm_query"),
        )

    manifest: list[dict[str, Any]] = []
    total = len(work)
    started = time.time()
    print(f"[{arm}] running {total} questions with {workers} workers…", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_one, e, k, arm, pool): e["id"] for e, k in work}
        done = 0
        for fut in as_completed(futures):
            cid = futures[fut]
            done += 1
            try:
                artifact = fut.result()
            except Exception as exc:  # noqa: BLE001 — one bad case must not sink the arm
                print(f"  ! {cid}: {type(exc).__name__}: {exc}", file=sys.stderr)
                manifest.append({"id": cid, "ok": False, "error": f"{type(exc).__name__}: {exc}"})
                continue
            (out / f"{cid}.json").write_text(
                json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            manifest.append({
                "id": cid, "ok": True, "kind": artifact["kind"],
                "tier": artifact["tier"], "category": artifact["category"],
                "records": artifact["evidence_volume"]["records"],
                "related": artifact["evidence_volume"]["related"],
                "wall_s": artifact["run_meta"]["wall_s"],
            })
            if done % 10 == 0 or done == total:
                print(f"  [{arm}] … {done}/{total}", file=sys.stderr)

    manifest.sort(key=lambda m: m["id"])
    doc = {
        "arm": arm,
        "bank": bank or "committed 120-question catalogue",
        "count": len(manifest),
        "ok": sum(1 for m in manifest if m.get("ok")),
        "workers": workers,
        "wall_s": round(time.time() - started, 1),
        "profile": {k: os.environ.get(k) for k in sorted(UNTRUNCATED_ENV)},
        "task_max_result_rows": TASK_MAX_RESULT_ROWS,
        "llm": {
            "planner": os.environ.get("PLANNER_LLM_ENABLED"),
            "specialist": os.environ.get("SPECIALIST_LLM_ENABLED"),
            "synthesis": os.environ.get("SYNTHESIS_LLM_ENABLED"),
            "model": os.environ.get("SYNTHESIS_LLM_MODEL"),
            "max_hops": os.environ.get("ORCH_MAX_HOPS"),
            "chase_facets": os.environ.get("ORCH_CHASE_FACETS"),
        },
        "categories": sorted({_category_of(m["id"]) for m in manifest}),
        "cases": manifest,
    }
    (Path(root) / arm / "manifest.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"[{arm}] wrote {doc['ok']}/{doc['count']} artifacts to {out}/ in {doc['wall_s']}s",
        file=sys.stderr,
    )
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=None, help="first N questions (smoke)")
    parser.add_argument("--only", default=None, help="comma-separated case ids")
    parser.add_argument(
        "--bank",
        default=None,
        help="run a single bank file (e.g. the holdout) instead of the committed three",
    )
    parser.add_argument(
        "--llm-model",
        default="skynet",
        help="model id for ARM B (the .env default; the relay also exposes 'local')",
    )
    parser.add_argument("--llm-max-tokens", type=int, default=16384)
    args = parser.parse_args(argv)

    from utils.config import load_env

    load_env()
    apply_env(untruncated_env(
        arm=args.arm, llm_model=args.llm_model, llm_max_tokens=args.llm_max_tokens
    ))
    only = {s.strip() for s in args.only.split(",")} if args.only else None
    run_arm(
        args.arm, root=args.root, workers=args.workers,
        limit=args.limit, only=only, bank=args.bank,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
