#!/usr/bin/env python3
"""E1 — the text boundary (EXP-2026-11-015, Era 2 Step 8).

The query builders and the resolver read the question only through
``SpecialistTask.signals``, which is derived from ``text`` once, when the task is
made. So a task whose ``text`` is replaced by nonsense *after* creation must give
the same query and the same records.

Two checks:

* **offline** — no ``task.text`` read remains in the Cypher and Gremlin
  builders or anywhere under ``utils/specialists/resolve/``;
* **live** — every one of the 120 golden questions
  (``golden/{attack,capec,federated}_questions.json``) is run through the rules
  pipeline (``iter_pipeline(..., use_llm=False)``) twice: once as is, and once
  with every task's text replaced by nonsense at the specialist boundary. Each
  specialist call's query and records must be identical. The attack and capec
  entries' authored tasks are also run directly through their specialist the
  same two ways.
"""

from __future__ import annotations

import dataclasses
import os
import re
import threading
from pathlib import Path

import pytest

from utils.specialists.evalset.compile_banks import (
    ATTACK_BANK_PATH,
    CAPEC_BANK_PATH,
    FEDERATED_BANK_PATH,
    load_bank,
)

REPO = Path(__file__).resolve().parents[3]
NONSENSE = "zzq blorp"

# -- offline: no English read past the boundary ------------------------------

_NO_TEXT_FILES = (
    "utils/specialists/cypher/builder.py",
    "utils/specialists/gremlin/builder.py",
    *sorted(
        str(p.relative_to(REPO))
        for p in (REPO / "utils/specialists/resolve").glob("*.py")
    ),
)
_TEXT_READ_RE = re.compile(r"\btask\.text\b|getattr\(\s*[\w.]*task\s*,\s*[\"']text[\"']")


def test_no_task_text_read_in_builders_or_resolver() -> None:
    offenders = []
    for rel in _NO_TEXT_FILES:
        for no, line in enumerate((REPO / rel).read_text().splitlines(), 1):
            if _TEXT_READ_RE.search(line):
                offenders.append(f"{rel}:{no}: {line.strip()}")
    assert len(_NO_TEXT_FILES) >= 4
    assert not offenders, "the specialists must read signals, not text:\n" + "\n".join(offenders)


def test_signals_survive_a_text_swap_and_round_trip() -> None:
    from utils.specialists.contracts import SpecialistTask

    task = SpecialistTask(
        sub_question_id="q", source="attack",
        text="List every technique APT29 uses on Windows, and what is T1055?",
    )
    swapped = dataclasses.replace(task, text=NONSENSE)
    assert swapped.signals == task.signals
    assert task.signals.bulk_scan and task.signals.definitional
    assert task.signals.attack_seed_ids == ("T1055",)
    again = SpecialistTask.from_dict(task.to_dict())
    assert again.signals == task.signals
    # An old serialised task without the key derives its signals from the text.
    legacy = {k: v for k, v in task.to_dict().items() if k != "signals"}
    assert SpecialistTask.from_dict(legacy).signals == task.signals


# -- live: 120 golden questions, text replaced by nonsense --------------------

_ENTRIES = [
    *(("attack", e) for e in load_bank(ATTACK_BANK_PATH)["questions"]),
    *(("capec", e) for e in load_bank(CAPEC_BANK_PATH)["questions"]),
    *(("federated", e) for e in load_bank(FEDERATED_BANK_PATH)["questions"]),
]


def _strip_clock(record: dict) -> dict:
    prov = record.get("provenance")
    if isinstance(prov, dict):
        record = {**record, "provenance": {k: v for k, v in prov.items() if k != "timestamp"}}
    return record


def _observed(result) -> dict:
    return {
        "query": result.query,
        "records": [_strip_clock(r.to_dict()) for r in result.records],
        "ok": result.ok,
        "partial": result.partial,
        "error": result.error,
        "join_values": list(result.join_values()),
    }


class _Recorder:
    """Wraps ``QuerySpecialist.run``: optionally blanks the text, records the outcome."""

    def __init__(self) -> None:
        self.blank = False
        self.calls: dict[tuple, list[dict]] = {}
        self._lock = threading.Lock()

    def install(self, monkeypatch) -> None:
        from utils.specialists.base import QuerySpecialist

        original = QuerySpecialist.run
        recorder = self

        def run(self, task):  # noqa: ANN001 — same signature as the original
            if recorder.blank:
                task = dataclasses.replace(task, text=NONSENSE)
                assert task.text == NONSENSE
            result = original(self, task)
            key = (task.sub_question_id, task.source, tuple(task.seed_ids), self.card.dataset)
            with recorder._lock:
                recorder.calls.setdefault(key, []).append(_observed(result))
            return result

        monkeypatch.setattr(QuerySpecialist, "run", run)

    def take(self) -> dict:
        out, self.calls = self.calls, {}
        return {k: sorted(v, key=repr) for k, v in out.items()}


@pytest.fixture(scope="module")
def live_env():
    from utils.config import load_env

    load_env()
    os.environ.setdefault("ORCH_MAX_HOPS", "5")
    from utils.specialists.tests.test_cypher_specialist import _neo4j_reachable
    from utils.specialists.tests.test_gremlin_specialist import _gremlin_reachable

    uri = os.environ.get("GREMLIN_URI", "ws://localhost:6455/gremlin")
    if not _neo4j_reachable() or not _gremlin_reachable(uri):
        pytest.skip("the text-boundary check needs BOTH backends live")

    from utils.specialists.config import SpecialistConfig
    from utils.specialists.federation import SpecialistRouter

    return SpecialistRouter(SpecialistConfig.from_env())


def _run_pipeline(entry: dict) -> None:
    from utils.orchestration.main import PipelineRun, iter_pipeline

    mode = entry.get("partial_mode")
    injected = {"attack": None} if mode == "attack_down" else (
        {"capec": None} if mode == "capec_down" else None
    )
    run = PipelineRun(question=entry["question"], mode="query")
    for _event, _payload in iter_pipeline(
        entry["question"], mode="query", use_llm=False, specialists=injected, run=run,
    ):
        pass


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.parametrize("bank,entry", _ENTRIES, ids=lambda x: x["id"] if isinstance(x, dict) else x)
def test_text_swap_changes_no_query_and_no_record(live_env, monkeypatch, bank: str, entry: dict) -> None:
    from utils.specialists.contracts import SpecialistTask

    recorder = _Recorder()
    recorder.install(monkeypatch)

    # 1. The rules pipeline, from the question: planner -> tasks -> specialists.
    _run_pipeline(entry)
    plain = recorder.take()
    recorder.blank = True
    _run_pipeline(entry)
    blank = recorder.take()
    recorder.blank = False
    # A question can legitimately reach no specialist (F-PART-04: its only
    # source is down); then both passes must agree on that too.
    assert blank == plain, f"{entry['id']}: a text swap changed a query or its records"

    # 2. The bank's authored task, straight to its specialist.
    if bank in ("attack", "capec"):
        task = SpecialistTask.from_dict(entry["task"])
        specialist = live_env._specialist_for(task.source)  # noqa: SLF001 — test
        first = _observed(specialist.run(task))
        swapped = _observed(specialist.run(dataclasses.replace(task, text=NONSENSE)))
        assert swapped == first, f"{entry['id']}: authored task changed under a text swap"
