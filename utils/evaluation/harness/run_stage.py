#!/usr/bin/env python3
"""Runner agent (stage 1): golden set -> ``answers.jsonl``.

Drives each golden entry through the live Ariadne pipeline and persists the
produced answer as an :class:`AnswerRecord`. Single-source entries go through
the specialist + synthesis path; federated entries go through the router +
synthesis path — reusing the proven ``run_single`` / ``run_federated`` drivers
from :mod:`utils.evaluation.score_e2e` (including one router per degradation
mode, so partial-degradation federated entries run with the failed source
absent, exactly as the golden fixture expects).

When the live stack is unreachable the agent scores nothing and returns an empty
list, mirroring the ``score_e2e`` ``--no-live`` discipline. Per-entry failures
are captured on the record (``error``) rather than aborting the whole run.
"""

from __future__ import annotations

import dataclasses
import logging
import time
from typing import Any

from utils.evaluation.harness.contracts import AnswerRecord
from utils.evaluation.harness.golden import GoldenEntry

logger = logging.getLogger("ariadne.evaluation.harness.runner")


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


class RunnerAgent:
    """Runs golden entries through the pipeline and yields ``AnswerRecord``s."""

    def __init__(self, *, use_llm_pipeline: bool = False, data_dir: str | None = None):
        self._use_llm = use_llm_pipeline
        self._data_dir = data_dir
        self._routers: dict[Any, Any] | None = None
        self._synth_config = None

    def _build(self) -> None:
        from utils.specialists.config import SpecialistConfig
        from utils.specialists.federation import SpecialistRouter
        from utils.synthesis.config import SynthesisConfig

        config = SpecialistConfig.from_env(self._data_dir)
        synth_config = SynthesisConfig.from_env()
        if self._use_llm:
            config = dataclasses.replace(config, llm_enabled=True)
            synth_config = dataclasses.replace(synth_config, llm_enabled=True)
        self._synth_config = synth_config

        full = SpecialistRouter(config)
        # One router per degradation mode (see score_e2e): a partial-degradation
        # federated entry must run with the failed source absent.
        self._routers = {
            None: full,
            "boundary": full,
            "attack_down": SpecialistRouter(config, cards=full.cards, specialists={"attack": None}),
            "capec_down": SpecialistRouter(config, cards=full.cards, specialists={"capec": None}),
        }

    def run(self, entries: list[GoldenEntry]) -> list[AnswerRecord]:
        from utils.evaluation.score_e2e import run_federated, run_single

        if self._routers is None:
            self._build()
        assert self._routers is not None
        full = self._routers[None]

        records: list[AnswerRecord] = []
        for entry in entries:
            started = time.time()
            try:
                if entry.kind == "federated":
                    router = self._routers.get(
                        entry.entry.get("partial_mode"), full
                    )
                    _evidence, answer = run_federated(
                        entry.entry, router, self._synth_config
                    )
                else:
                    specialist = full._specialist_for(entry.source)
                    if specialist is None:
                        raise RuntimeError(f"no specialist for source {entry.source!r}")
                    _evidence, answer = run_single(
                        entry.entry, specialist, self._synth_config
                    )
                record = answer_to_record(
                    entry, answer, exit_code=0, wall_s=time.time() - started
                )
            except Exception as exc:  # keep the batch alive; record the failure
                logger.warning("runner failed on %s: %s", entry.question_id, exc)
                record = AnswerRecord(
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
                    timings={"wall_s": round(time.time() - started, 4)},
                )
            records.append(record)
            logger.info("ran %s (%s)", record.question_id, record.error or "ok")
        return records
