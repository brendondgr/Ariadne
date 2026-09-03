#!/usr/bin/env python3
"""Did the LLM-query arm fail at writing queries, or fail to finish thinking?

The `llm_query` arm returned records for 67 of 284 questions, and its dominant
recorded failure is the gate refusing an *empty* query 104 times. That number is
only a baseline for C-012 if the model actually produced bad queries. It is not
a baseline if the model never emitted anything.

The served model is a reasoning model behind an OpenAI-shaped relay: its chain
of thought lands in a separate ``reasoning`` field and ``content`` stays empty
until it stops thinking. A budget spent entirely on reasoning therefore returns
``finish_reason='length'`` with ``content=''`` — indistinguishable, downstream,
from a model that had nothing to say.

This probe replays the *exact* builder prompt for real failing cases at several
budgets and records which of the two it was. It changes nothing; it only reads
the arm's own artifacts and asks the relay the same question again.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.planner.cards import load_source_cards            # noqa: E402
from utils.specialists.config import SpecialistConfig        # noqa: E402
from utils.specialists.contracts import SpecialistTask       # noqa: E402
from utils.specialists.llm_builder import (                  # noqa: E402
    DEFAULT_MAX_TOKENS,
    LLMQueryBuilder,
)
from utils.specialists.resolve import ResolvedTask           # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ANSWERS = ROOT / "docs/evaluation/experiments/expansion-judged-2026-09-01/llm_query/answers"
OUT = ROOT / "docs/evaluation/composition/bank/budget-probe.json"
EMPTY = "pre-run gate rejected all drafts: empty query"
LANGUAGE = {"capec": "gremlin", "attack": "cypher"}


def failing_cases(answers: Path, limit: int) -> list[dict[str, Any]]:
    """Cases whose *final* recorded error was an empty query — not a retry that recovered.

    ``D0`` questions are excluded on purpose. They are the negative controls: the
    right behaviour there is to answer nothing, so an empty query is not evidence
    of anything. Probing them would have flattered the hypothesis.
    """
    picked: list[dict[str, Any]] = []
    for path in sorted(answers.glob("*.json")):
        if path.name.startswith("D0-"):
            continue
        doc = json.loads(path.read_text())
        for result in (doc.get("logic_flow") or {}).get("results") or []:
            if result.get("error") != EMPTY:
                continue
            resolve = next(
                (t for t in result.get("traces") or [] if t.get("step") == "resolve"), {}
            )
            detail = resolve.get("detail") or {}
            picked.append(
                {
                    "id": doc["id"],
                    "source": result.get("source") or "capec",
                    "question": result.get("sub_question") or doc.get("question") or "",
                    "labels": tuple(detail.get("labels") or ()),
                    "relationships": tuple(detail.get("relationships") or ()),
                    "seed_ids": tuple(detail.get("seed_ids") or ()),
                }
            )
            break
        if len(picked) >= limit:
            break
    return picked


def _declared_in_env_file(key: str) -> str | None:
    """What ``.env`` says — read from the file, never from ``os.environ``.

    Reading the environment would report whatever this process happens to have,
    which is exactly the confusion being documented: the file declares a value,
    the run never loaded the file, and both look identical from inside a process
    that also never loaded it.
    """
    env_file = ROOT / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip() or None
    return None


def census(answers: Path) -> dict[str, Any]:
    """How much of the arm the empty-query failure actually accounts for."""
    total = empty = with_records = 0
    for path in sorted(answers.glob("*.json")):
        doc = json.loads(path.read_text())
        total += 1
        results = (doc.get("logic_flow") or {}).get("results") or []
        if any(r.get("error") == EMPTY for r in results):
            empty += 1
        if sum(len(r.get("records") or []) for r in results):
            with_records += 1
    return {"questions": total, "empty_query": empty, "with_records": with_records}


def prompt_for(case: dict[str, Any], cards: dict[str, Any]) -> tuple[str, str]:
    source = case["source"]
    card = cards.get(source) or next(iter(cards.values()))
    language = LANGUAGE.get(source, "gremlin")
    builder = LLMQueryBuilder(card=card, language=language)
    task = SpecialistTask(
        sub_question_id="probe",
        source=source,
        text=case["question"],
        seed_ids=case["seed_ids"],
    )
    resolved = ResolvedTask(
        task=task,
        dataset=source,
        labels=case["labels"],
        relationships=case["relationships"],
        seed_ids=case["seed_ids"],
    )
    return builder.prompt_for(resolved, None), language


def ask(base_url: str, model: str, prompt: str, budget: int, timeout: float) -> dict[str, Any]:
    import requests

    start = time.time()
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": budget,
                "temperature": 0,
            },
            timeout=timeout,
        )
        body = response.json()
        choice = body["choices"][0]
        content = choice["message"].get("content") or ""
        reasoning = choice["message"].get("reasoning") or ""
        query = ""
        try:
            slice_ = content[content.index("{") : content.rindex("}") + 1]
            query = str(json.loads(slice_).get("query") or "").strip()
        except (ValueError, TypeError):
            query = ""
        return {
            "budget": budget,
            "finish_reason": choice.get("finish_reason"),
            "completion_tokens": (body.get("usage") or {}).get("completion_tokens"),
            "content_chars": len(content),
            "reasoning_chars": len(reasoning),
            "produced_query": bool(query),
            "query_head": query[:160],
            "wall_s": round(time.time() - start, 1),
        }
    except Exception as exc:  # noqa: BLE001 — a probe records, it never crashes
        trial = {
            "budget": budget,
            "error": f"{type(exc).__name__}: {exc}"[:200],
            "wall_s": round(time.time() - start, 1),
        }
        # A relay that refuses or times out answers with a body, not an exception.
        # Recording it is the difference between "the model could not" and "the
        # endpoint would not" — two findings a bare traceback conflates.
        try:
            trial["response_head"] = response.text[:300]  # noqa: F821
            trial["status_code"] = response.status_code  # noqa: F821
        except Exception:  # noqa: BLE001
            pass
        return trial


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=2)
    parser.add_argument("--budgets", type=int, nargs="+", default=[2048, 8192, 32768])
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--census-only", action="store_true",
                        help="recount the arm and merge into an existing artifact; no LLM calls")
    args = parser.parse_args()

    if args.census_only:
        record = json.loads(args.out.read_text()) if args.out.exists() else {"probe": "builder-budget"}
        record["census"] = census(ANSWERS)
        record["arm_budget_as_run"] = int(DEFAULT_MAX_TOKENS)
        record["dotenv_value_not_used_by_arm"] = _declared_in_env_file(
            "SPECIALIST_LLM_MAX_TOKENS"
        )
        args.out.write_text(json.dumps(record, indent=2) + "\n")
        print(f"census -> {args.out}: {record['census']}")
        return

    config = SpecialistConfig.from_env()
    cards = load_source_cards(config.data_dir)
    cases = failing_cases(ANSWERS, args.cases)
    if not cases:
        print("no empty-query cases found — nothing to probe")
        return

    record: dict[str, Any] = {
        "probe": "builder-budget",
        # ``experiment_untruncated`` never calls ``load_env()``, so the arm ran on
        # the code defaults, not on .env. Recording the effective value rather
        # than the file's is the whole point: they differ, and the file's is the
        # one that looks right.
        "arm_budget_as_run": int(DEFAULT_MAX_TOKENS),
        "dotenv_value_not_used_by_arm": _declared_in_env_file("SPECIALIST_LLM_MAX_TOKENS"),
        "base_url": config.llm_base_url,
        "model": config.llm_model,
        "census": census(ANSWERS),
        "cases": [],
    }
    for case in cases:
        prompt, language = prompt_for(case, cards)
        print(f"\n[{case['id']}]  {language}  prompt={len(prompt)} chars", flush=True)
        trials = []
        for budget in args.budgets:
            trial = ask(config.llm_base_url, config.llm_model, prompt, budget, args.timeout)
            trials.append(trial)
            print(
                f"  budget={budget:6}  finish={trial.get('finish_reason')!r:12}"
                f"  content_chars={trial.get('content_chars')}"
                f"  produced_query={trial.get('produced_query')}"
                f"  {trial['wall_s']}s",
                flush=True,
            )
        record["cases"].append(
            {
                "id": case["id"],
                "source": case["source"],
                "language": language,
                "question": case["question"],
                "prompt_chars": len(prompt),
                "trials": trials,
            }
        )

    emitted = [
        t for c in record["cases"] for t in c["trials"] if t.get("produced_query")
    ]
    record["verdict"] = (
        "no budget tried produced a query — the model never finishes reasoning on "
        "this prompt, so the arm's empty queries measure the budget, not the model's "
        "ability to write a query"
        if not emitted
        else f"a query appeared at budget(s) {sorted({t['budget'] for t in emitted})} — "
        "the arm as run was budget-limited below that"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2) + "\n")
    print(f"\nbudget probe -> {args.out}")
    print(f"verdict: {record['verdict']}")


if __name__ == "__main__":
    main()
