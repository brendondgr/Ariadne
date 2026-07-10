#!/usr/bin/env python3
"""Runner agent (stage 1): golden set -> ``answers.jsonl``.

Two run modes, both concurrent (a thread pool, since each question is I/O-bound
on the graph backends + the LLM endpoints):

* **agentic** (``--agentic``) — the real end-to-end pipeline. Each *raw question*
  is driven through ``iter_pipeline(question, use_llm=True)``, so the local LLM
  plans/routes it (planner), drafts the queries (specialists), and composes the
  answer (synthesis) — "the agentic process we set up", exactly as the workbench
  runs it. Every call builds its own agent + specialists, so concurrent calls are
  independent and thread-safe.
* **gold** (default) — the isolated retrieval path: each entry's pre-authored
  ``task`` / ``sub_questions`` are replayed through ``score_e2e.run_single`` /
  ``run_federated`` (deterministic composer unless ``--llm-pipeline``). Fast and
  reproducible; isolates retrieval + synthesis from planner variance. Routers are
  thread-local so the pool stays safe.

When the live stack is unreachable the agent scores nothing. Per-entry failures
are captured on the record (``error``), never fatal to the batch. Answers are
persisted in the original golden order regardless of completion order.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from utils.evaluation.harness.contracts import AnswerRecord
from utils.evaluation.harness.golden import GoldenEntry

logger = logging.getLogger("ariadne.evaluation.harness.runner")

DEFAULT_CONCURRENCY = 16


def stack_reachable() -> bool:
    """True when both graph backends are up (probes the specialist test helpers)."""
    try:
        from utils.specialists.tests.test_cypher_specialist import _neo4j_reachable
        from utils.specialists.tests.test_gremlin_specialist import _gremlin_reachable

        return bool(_neo4j_reachable() and _gremlin_reachable())
    except Exception:  # pragma: no cover - defensive: never let probing crash
        return False


def _extract_produced_ids(answer) -> list[str]:
    """Ordered-unique ids the answer actually asserts.

    Combines each rendered claim's structured ``entity_ids`` + citation ids with
    ids scanned from the claim text and the narrative — the deterministic
    composer states related ids in prose (``"e.g. M1038, M1040"``), so scanning
    is what makes the correctness backstop see them. Abstention text is *not*
    scanned: a "no mitigations found for T1234" line must not count T1234 as a
    produced fact.
    """
    from utils.evaluation.harness.ids import canonical, scan_ids

    seen: set[str] = set()
    ordered: list[str] = []

    def _add(raw: str) -> None:
        cid = canonical(raw)
        if cid and cid not in seen:
            seen.add(cid)
            ordered.append(cid)

    for claim in answer.rendered_claims():
        for eid in claim.entity_ids:
            _add(eid)
        for cit in claim.citations:
            _add(cit.primary_id)
        for cid in scan_ids(claim.text):
            _add(cid)
    for cid in scan_ids(getattr(answer, "narrative", "")):
        _add(cid)
    return ordered


def _claims_payload(answer) -> list[dict[str, Any]]:
    return [
        {
            "text": claim.text,
            "kind": claim.kind,
            "entity_ids": list(claim.entity_ids),
            "citations": [
                {"source": cit.source, "primary_id": cit.primary_id}
                for cit in claim.citations
            ],
        }
        for claim in answer.rendered_claims()
    ]


def _abstentions_payload(answer) -> list[dict[str, Any]]:
    return [{"source": a.source, "statement": a.statement} for a in answer.abstentions]


def answer_to_record(
    entry: GoldenEntry, answer, *, exit_code: int | None, wall_s: float
) -> AnswerRecord:
    """Fold a produced ``SynthesizedAnswer`` into a persistable ``AnswerRecord``."""
    return AnswerRecord(
        question_id=entry.question_id,
        set_name=entry.set_name,
        tier=entry.tier,
        kind=entry.kind,
        source=entry.source,
        question=entry.question,
        narrative=getattr(answer, "narrative", ""),
        claims=_claims_payload(answer),
        abstentions=_abstentions_payload(answer),
        produced_ids=_extract_produced_ids(answer),
        gold_expected_ids=sorted(entry.gold_expected_ids),
        gold_kind=entry.gold_kind,
        expect_empty=entry.expect_empty,
        exit_code=exit_code,
        timings={"wall_s": round(wall_s, 4)},
    )


def _error_record(entry: GoldenEntry, exc: Exception, wall_s: float) -> AnswerRecord:
    return AnswerRecord(
        question_id=entry.question_id,
        set_name=entry.set_name,
        tier=entry.tier,
        kind=entry.kind,
        source=entry.source,
        question=entry.question,
        gold_expected_ids=sorted(entry.gold_expected_ids),
        gold_kind=entry.gold_kind,
        expect_empty=entry.expect_empty,
        exit_code=None,
        error=f"{type(exc).__name__}: {exc}",
        timings={"wall_s": round(wall_s, 4)},
    )


class RunnerAgent:
    """Runs golden entries through the pipeline concurrently into ``AnswerRecord``s."""

    def __init__(
        self,
        *,
        agentic: bool = False,
        use_llm_pipeline: bool = False,
        concurrency: int = DEFAULT_CONCURRENCY,
        data_dir: str | None = None,
    ):
        self._agentic = agentic
        # agentic mode drives the LLM throughout; --llm-pipeline turns the LLM on
        # in the gold path's specialist/synthesis composers.
        self._use_llm = use_llm_pipeline or agentic
        self._concurrency = max(1, concurrency)
        self._data_dir = data_dir
        self._tls = threading.local()  # per-worker gold routers

    # --- gold path (thread-local routers) -----------------------------------

    def _gold_context(self):
        ctx = getattr(self._tls, "gold", None)
        if ctx is None:
            ctx = self._build_gold_context()
            self._tls.gold = ctx
        return ctx

    def _build_gold_context(self):
        import dataclasses

        from utils.specialists.config import SpecialistConfig
        from utils.specialists.federation import SpecialistRouter
        from utils.synthesis.config import SynthesisConfig

        config = SpecialistConfig.from_env(self._data_dir)
        synth_config = SynthesisConfig.from_env()
        if self._use_llm:
            config = dataclasses.replace(config, llm_enabled=True)
            synth_config = dataclasses.replace(synth_config, llm_enabled=True)
        full = SpecialistRouter(config)
        routers = {
            None: full,
            "boundary": full,
            "attack_down": SpecialistRouter(config, cards=full.cards, specialists={"attack": None}),
            "capec_down": SpecialistRouter(config, cards=full.cards, specialists={"capec": None}),
        }
        return routers, synth_config

    def _run_gold_one(self, entry: GoldenEntry) -> AnswerRecord:
        from utils.evaluation.score_e2e import run_federated, run_single

        routers, synth_config = self._gold_context()
        started = time.time()
        try:
            if entry.kind == "federated":
                router = routers.get(entry.entry.get("partial_mode"), routers[None])
                _evidence, answer = run_federated(entry.entry, router, synth_config)
            else:
                specialist = routers[None]._specialist_for(entry.source)
                if specialist is None:
                    raise RuntimeError(f"no specialist for source {entry.source!r}")
                _evidence, answer = run_single(entry.entry, specialist, synth_config)
            return answer_to_record(
                entry, answer, exit_code=0, wall_s=time.time() - started
            )
        except Exception as exc:
            logger.warning("gold runner failed on %s: %s", entry.question_id, exc)
            return _error_record(entry, exc, time.time() - started)

    # --- agentic path (real pipeline per raw question) ----------------------

    def _run_agentic_one(self, entry: GoldenEntry) -> AnswerRecord:
        from utils.orchestration.main import PipelineRun, iter_pipeline

        started = time.time()
        run = PipelineRun(question=entry.question, mode="query")
        answer = None
        try:
            for event, payload in iter_pipeline(
                entry.question, mode="query", use_llm=True,
                data_dir=self._data_dir, run=run,
            ):
                if event == "answer":
                    answer = payload.get("synthesized")
            if answer is None:
                raise RuntimeError("pipeline produced no synthesized answer")
            return answer_to_record(
                entry, answer, exit_code=run.exit_code, wall_s=time.time() - started
            )
        except Exception as exc:
            logger.warning("agentic runner failed on %s: %s", entry.question_id, exc)
            return _error_record(entry, exc, time.time() - started)

    # --- batch driver -------------------------------------------------------

    def _run_one(self, entry: GoldenEntry) -> AnswerRecord:
        record = (
            self._run_agentic_one(entry)
            if self._agentic
            else self._run_gold_one(entry)
        )
        logger.info("ran %s (%s)", record.question_id, record.error or "ok")
        return record

    def run(self, entries: list[GoldenEntry]) -> list[AnswerRecord]:
        results: list[AnswerRecord | None] = [None] * len(entries)
        with ThreadPoolExecutor(max_workers=self._concurrency) as pool:
            futures = {pool.submit(self._run_one, e): i for i, e in enumerate(entries)}
            for future in as_completed(futures):
                results[futures[future]] = future.result()
        return [r for r in results if r is not None]
