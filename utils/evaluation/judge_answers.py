#!/usr/bin/env python3
"""Grade saved arm answers into the committed judgment schema.

``experiment_untruncated`` writes one answer JSON per case; the blind holdout was
then graded by one independent Sonnet 5 agent per case, which wrote
``<case>.judgment.json`` beside it. Everything downstream — ``holdout_report``'s
bootstrap intervals and strata, ``answer_gap``'s loss decomposition — reads those
files. There was no runner: the judgments came from agents, one conversation at a
time, so no arm could be graded without a human driving it.

This is that runner. It grades any arm's saved answers against the same schema,
so an arm that has never been judged becomes judgeable in one command.

**It is not the same instrument.** The original rubric lived in the subagent
instructions rather than in a file, so the prompt here is a reconstruction, and
the model is local rather than cross-provider. Both differences matter and
neither is knowable in the abstract, which is why ``--calibrate`` exists: point
it at answers that already carry committed judgments and it reports agreement
against them instead of overwriting. Run that before trusting anything else this
produces.

Nothing here touches the system under test. It reads answers and writes
judgments.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from utils.llm.config import LLMSettings as _LLMSettings
from utils.llm.config import resolve as _resolve_llm

# Resolved through utils.llm so this harness inherits ARIADNE_LLM_* like every
# other stage: EVAL_LLM_* still wins when set, then the primary group, then this
# harness's own historical fallback of :4000/skynet -- which differs from the
# pipeline's :9090/default-model on purpose and is preserved exactly.
#
# The TRANSPORT here is deliberately left alone. This module is the offline
# grading harness, not a web path: it is stdlib-only by design, carries its own
# retry loop and budget escalation, and reads back the served model id to
# attribute a judgment to real weights rather than to a relay alias. Routing it
# through the shared client would drop all three for no benefit to the workbench.
_EVAL_LLM = _resolve_llm(
    "eval",
    defaults=_LLMSettings(base_url="http://localhost:4000/v1", model="skynet"),
)
DEFAULT_BASE_URL = _EVAL_LLM.base_url
DEFAULT_MODEL = _EVAL_LLM.model
# The judge reasons before answering, and the reasoning is billed against the
# same budget as the answer. Too small a budget truncates mid-thought and yields
# an *empty* reply — which reads as "the server is down" rather than as the
# ceiling it is. Observed on a chain question at 4096: reasoning consumed the
# lot. The escalation in ``judge_one`` is the belt to this braces.
DEFAULT_MAX_TOKENS = 8192
DEFAULT_WORKERS = 12
DEFAULT_TIMEOUT_S = 600.0

# Every field ``holdout_report`` and ``answer_gap`` read.
REQUIRED_FIELDS = (
    "verdict",
    "correctness",
    "faithfulness",
    "groundedness",
    "completeness",
    "rationale",
)
VERDICTS = ("CORRECT", "PARTIAL", "INCORRECT")

RUBRIC = """You are grading one answer produced by a federated graph-retrieval system \
over MITRE ATT&CK and CAPEC. Grade only what is in front of you.

Return ONLY a JSON object, no prose around it, with exactly these keys:

  verdict        "CORRECT" | "PARTIAL" | "INCORRECT"
  correctness    0.0-1.0. Does the answer answer the question that was asked?
                 An answer that states some of the gold entities and omits the
                 rest is partial in proportion. An answer that describes the
                 anchor but never addresses what was asked is not correct
                 however true its statements are.
  faithfulness   0.0-1.0. Is every statement supported by the evidence shown?
                 Deduct for anything asserted beyond the records.
  groundedness   0.0-1.0. Are claims tied to specific cited records rather than
                 to general knowledge about ATT&CK or CAPEC?
  completeness   0.0-1.0. Of the gold identifiers expected, what fraction does
                 the answer actually state?
  gold_expected  integer: how many gold identifiers the question expected.
  gold_present   integer: how many of them the answer states.
  abstained      true if the answer declines to assert rather than guessing.
  abstention_carries_query  true if an abstention shows the executed query as
                 proof. False when there is no abstention.
  fabricated_mapping  true if the answer asserts a cross-source correlation the
                 evidence does not contain. This is the most serious failure.
  hallucinations list of strings: any identifier or fact asserted that the
                 evidence does not support. Empty list if none.
  rationale      2-4 sentences. Name the specific identifiers involved.

Two rules that decide most hard cases:

1. An honest abstention is not a wrong answer. If the graph genuinely contains
   no mapping and the system says so and shows the query it ran, that is
   CORRECT. Reward it. Guessing an answer instead would be the failure.
2. Retrieving a record is not the same as answering. If the evidence contains
   the neighbours the question asked for and the answer text does not state
   them, completeness is low even though retrieval succeeded."""


@dataclass
class JudgeConfig:
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    timeout_s: float = DEFAULT_TIMEOUT_S
    temperature: float = 0.0
    retries: int = 3
    #: Zero-based position of this cell in its grading session, when the caller
    #: knows it. EXP-2026-08-022 measured a position effect of about 0.01 -- the
    #: condition graded second scores lower, whichever it is -- which is the size
    #: of several differences this project reports. Recording it makes a paired
    #: comparison correctable after the fact; `utils/evaluation/grading_order.py`
    #: prevents it up front. None means the caller did not say.
    position: int | None = None


#: The relay's hard ceiling on prompt + completion. `max_tokens` alone is not
#: the limit: the server rejects when `prompt_tokens + max_tokens` exceeds this,
#: and it rejects with HTTP 400 rather than truncating.
MAX_TOTAL_TOKENS = int(os.environ.get("JUDGE_MAX_TOTAL_TOKENS", "84000"))
#: Characters per token, deliberately low. Under-estimating tokens would ask for
#: a budget the server refuses; over-estimating only costs headroom.
CHARS_PER_TOKEN = 3

#: A 4xx the relay recovers from on its own. `:9090` is an SSH tunnel, and when
#: it drops the alias stops resolving: the relay answers **400 "model
#: 'default-model' not found"** rather than refusing the connection. That looks
#: exactly like a malformed request and is nothing of the kind — it is the
#: endpoint being briefly absent, and the only correct response is to wait.
#:
#: Worth recording how this was found: 22 cases failed with "HTTP Error 400: Bad
#: Request" and I spent an afternoon reasoning about token ceilings. The moment
#: the response body was actually read, the server turned out to have been
#: saying something else entirely all along.
TRANSIENT_400 = re.compile(
    r"model\s+\S*\s*not found|no healthy upstream|temporarily unavailable|"
    r"service unavailable", re.I
)
#: A tunnel flap outlasts an ordinary retry ladder, so this one is longer and
#: slower. Raised to thirty minutes on 2026-09-13: the operator warned the
#: server goes down for roughly twenty minutes around 04:00, and eight minutes
#: of patience would have turned a planned outage into a few hundred ungraded
#: cases that the sweep then has to re-run.
TRANSIENT_RETRIES = 30
TRANSIENT_BACKOFF_S = 60


def _budgets(config: JudgeConfig, prompt: str) -> list[int]:
    """The escalation ladder, clamped to what the server can actually accept.

    The ladder exists because an empty or unparseable reply is usually the token
    ceiling rather than a broken model, and `EXP-2026-08-021` showed those
    failures are not random — all six were in the top 5% of answers by size, so
    losing them skews a judged mean rather than thinning it.

    Unclamped it defeated itself. At a base of 32768 it asked for 32768, 65536
    and 131072; the third exceeds `max_total_tokens=84000` unconditionally and
    the second exceeds it for any prompt over roughly 18k tokens. So every case
    that reached escalation was guaranteed to fail, and on 2026-09-13 that was
    22 of 284 on the LLM arm — whose answers are the longest, which is exactly
    the population the ladder was written to rescue.

    Clamping keeps the intent and makes every rung requestable. Duplicate rungs
    after clamping are dropped: asking twice for the same budget cannot succeed
    the second time.
    """
    room = max(1024, MAX_TOTAL_TOKENS - len(prompt) // CHARS_PER_TOKEN - 512)
    ladder = [
        config.max_tokens,
        config.max_tokens * 2,
        max(config.max_tokens * 4, 32768),
    ]
    budgets: list[int] = []
    for rung in ladder:
        clamped = min(rung, room)
        if clamped not in budgets:
            budgets.append(clamped)
    return budgets


def _post(config: JudgeConfig, prompt: str, max_tokens: int | None = None) -> tuple[str, str | None]:
    """Returns ``(content, served_model)``.

    The second element is the `model` field off the *response* envelope, which
    names the weights that actually served the call. ``config.model`` is a relay
    *alias* and has resolved to three different models over this project's life
    (`D-028`, `Q12`); recording it alone records nothing. The relay does not
    accept the concrete id as a routing target, so detection at response time is
    the only way to attribute a judgment to a model.
    """
    body = json.dumps(
        {
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens or config.max_tokens,
            "temperature": config.temperature,
        }
    ).encode()
    last: Exception | None = None
    transient = 0
    # A transient rejection does not consume an ordinary attempt: the request
    # was never considered, so counting it against the retry budget would give
    # up on a healthy case because the tunnel blinked.
    attempt = 0
    while attempt < config.retries:
        attempt += 1
        try:
            request = urllib.request.Request(
                f"{config.base_url.rstrip('/')}/chat/completions",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=config.timeout_s) as response:
                payload = json.load(response)
            return payload["choices"][0]["message"]["content"] or "", payload.get("model")
        except urllib.error.HTTPError as exc:  # noqa: PERF203
            # Read the BODY. `str(HTTPError)` is "HTTP Error 400: Bad Request"
            # and nothing else, so a rejection the server explains precisely —
            # "max_tokens=131072 cannot be greater than max_model_len=84000" —
            # reaches the log as four useless words. That cost an afternoon of
            # inferring a cause the server had been stating all along.
            try:
                detail = exc.read().decode("utf-8", "replace")[:400]
            except Exception:  # noqa: BLE001
                detail = "<body unreadable>"
            last = RuntimeError(f"HTTP {exc.code}: {detail}")
            if 400 <= exc.code < 500 and TRANSIENT_400.search(detail):
                # The endpoint is absent, not objecting. Wait for it.
                transient += 1
                if transient >= TRANSIENT_RETRIES:
                    break
                time.sleep(TRANSIENT_BACKOFF_S)
                continue
            # Any other 4xx is the server declining THIS request; retrying the
            # identical body cannot change its mind.
            if 400 <= exc.code < 500:
                break
            if attempt < config.retries:
                time.sleep(min(2**attempt, 30))
        except urllib.error.URLError as exc:
            # The endpoint is UNREACHABLE rather than objecting — the tunnel is
            # down, not the request bad. Same treatment as a missing alias: wait
            # it out rather than burning the retry budget in ninety seconds.
            # A read timeout is NOT this: it means the server accepted the
            # request and is still thinking, which is an ordinary slow case.
            reason = str(getattr(exc, "reason", exc))
            if isinstance(getattr(exc, "reason", None), TimeoutError) or "timed out" in reason:
                last = exc
                if attempt < config.retries:
                    time.sleep(min(2**attempt, 30))
                continue
            last = exc
            transient += 1
            if transient >= TRANSIENT_RETRIES:
                break
            time.sleep(TRANSIENT_BACKOFF_S)
            continue
        except Exception as exc:  # noqa: BLE001 — the server restarts; that is the point
            last = exc
            if attempt < config.retries:
                time.sleep(min(2**attempt, 30))
    raise RuntimeError(f"judge call failed after {config.retries} attempts: {last}")


def _json_objects(text: str) -> list[dict[str, Any]]:
    r"""Every top-level JSON object in ``text``, in order.

    Replaces a greedy ``\{.*\}`` that spanned from the first brace to the last.
    On a reply carrying two objects — a reasoning model emitting a draft and then
    a verdict — that match covered both plus the prose between them, and
    ``json.loads`` raised "Extra data" on a judgment the model had produced
    perfectly well. EXP-2026-08-021 recorded two such losses (ISSUES I-7, I-8);
    they were discarded judgments, not missing ones.

    ``raw_decode`` stops at the end of the first complete value, so scanning from
    each ``{`` collects the objects rather than smearing them together.
    """
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    index = 0
    while True:
        start = text.find("{", index)
        if start == -1:
            return objects
        try:
            value, end = decoder.raw_decode(text, start)
        except ValueError:
            # Not the start of a complete object — a brace inside prose, or a
            # truncated tail. Step past it and keep looking.
            index = start + 1
            continue
        if isinstance(value, dict):
            objects.append(value)
        index = end


def _parse(reply: str) -> dict[str, Any]:
    """Pull the judgment object out of a reply that may carry reasoning around it.

    Prefers the first object that actually looks like a judgment. A reply can
    contain several objects and the *first* is not always the answer: EXP-2026-08-021
    saw one whose leading object carried only ``verdict``, which parsed cleanly
    and then failed schema validation as "missing 5 fields". Choosing by content
    rather than by position fixes that case and the "Extra data" case together.
    """
    text = reply.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text[4:] if text.lower().startswith("json") else text
    objects = _json_objects(text)
    if not objects:
        raise ValueError(f"no JSON object in reply: {reply[:200]!r}")
    for candidate in objects:
        if all(field in candidate for field in REQUIRED_FIELDS):
            return candidate
    # None is complete. Return the richest one so `_normalise` can report
    # precisely which fields are missing, rather than whichever came first.
    return max(objects, key=lambda o: sum(f in o for f in REQUIRED_FIELDS))


def _prompt_for(answer: dict[str, Any]) -> str:
    gold = answer.get("gold") or {}
    body = {
        "question": answer.get("question"),
        "gold_expectations": gold,
        "answer": answer.get("answer"),
        "evidence_volume": answer.get("evidence_volume"),
        "logic_flow": answer.get("logic_flow"),
    }
    return f"{RUBRIC}\n\n--- CASE ---\n{json.dumps(body, indent=1)[:24000]}\n"


def _normalise(case_id: str, raw: dict[str, Any], served_model: str | None = None) -> dict[str, Any]:
    """Coerce the model's object into the committed schema, or fail loudly."""
    missing = [field for field in REQUIRED_FIELDS if field not in raw]
    if missing:
        raise ValueError(f"{case_id}: judgment missing {missing}")
    verdict = str(raw["verdict"]).strip().upper()
    if verdict not in VERDICTS:
        raise ValueError(f"{case_id}: verdict {verdict!r} not one of {VERDICTS}")

    def _num(key: str) -> float:
        value = float(raw.get(key) or 0.0)
        return max(0.0, min(1.0, value))

    hallucinations = raw.get("hallucinations") or []
    if isinstance(hallucinations, str):
        hallucinations = [hallucinations]
    return {
        "case_id": case_id,
        "verdict": verdict,
        "correctness": _num("correctness"),
        "faithfulness": _num("faithfulness"),
        "groundedness": _num("groundedness"),
        "completeness": _num("completeness"),
        "gold_expected": int(raw.get("gold_expected") or 0),
        "gold_present": int(raw.get("gold_present") or 0),
        "abstained": bool(raw.get("abstained")),
        "abstention_carries_query": bool(raw.get("abstention_carries_query")),
        "fabricated_mapping": bool(raw.get("fabricated_mapping")),
        "hallucinations": [str(h) for h in hallucinations],
        "rationale": str(raw.get("rationale") or ""),
        "judge": {
            # `alias` is what was asked for; `served_model` is what answered.
            # They differ, and the difference is the whole of D-028.
            "model": DEFAULT_MODEL,
            "alias": DEFAULT_MODEL,
            "served_model": served_model,
            "runner": "utils/evaluation/judge_answers.py",
        },
    }


def answer_files(root: Path, arm: str) -> list[Path]:
    """Answer files only — never a judgment this or an earlier pass wrote.

    A suffixed pass writes ``<case>.judgment.run2.json``, which does *not* end
    in ``.judgment.json``. Matching on the suffix alone let a later pass grade
    an earlier pass's judgments as though they were answers, doubling ``n`` and
    poisoning the roll-up. Any ``.judgment`` in the name disqualifies the file.
    """
    answers = root / arm / "answers"
    return [p for p in sorted(answers.glob("*.json")) if ".judgment" not in p.name]


def judge_one(path: Path, config: JudgeConfig, suffix: str) -> tuple[str, str]:
    """Grade one case. Returns ``(case_id, status)``; never raises for one case."""
    case_id = path.stem
    out = path.with_name(f"{case_id}.judgment{suffix}.json")
    try:
        answer = json.loads(path.read_text())
        prompt = _prompt_for(answer)
        # An unparseable or empty reply is usually the token ceiling, not a broken
        # model, so the budget escalates before a failure is recorded. A case
        # dropped for a budget is a case silently missing from the night's
        # numbers, and EXP-2026-08-021 showed those absences are not random:
        # all six of its failures were in the top 5% of answers by size, i.e. one
        # question *type*, so the loss skews a judged mean rather than thinning it.
        # The third rung is EXP-2026-08-009's 32768, which recovered exactly this
        # class of oversized case.
        budgets = _budgets(config, prompt)
        raw, served_model, used_budget, last_error = None, None, None, None
        for budget in budgets:
            try:
                content, served_model = _post(config, prompt, max_tokens=budget)
                raw = _parse(content)
                used_budget = budget
                break
            except ValueError as exc:
                last_error = exc
        if raw is None:
            raise last_error or ValueError("no reply")
        judgment = _normalise(case_id, raw, served_model=served_model)
        # Recorded because a case recovered at a larger budget is not measured
        # under the same conditions as its neighbours. A spread computed across
        # passes must be able to exclude these rather than absorb them --
        # a per-case budget change would inflate the very quantity being measured.
        judgment["judge"]["max_tokens"] = used_budget
        judgment["judge"]["escalated"] = used_budget != config.max_tokens
        judgment["judge"]["position"] = config.position
        # Written as soon as it exists: a run that dies at case 90 keeps 89.
        out.write_text(json.dumps(judgment, indent=1) + "\n")
        return case_id, "ok"
    except Exception as exc:  # noqa: BLE001
        out.with_suffix(".error.txt").write_text(f"{type(exc).__name__}: {exc}\n")
        return case_id, f"FAILED {type(exc).__name__}: {exc}"


def run(
    root: Path,
    arm: str,
    config: JudgeConfig,
    workers: int = DEFAULT_WORKERS,
    suffix: str = "",
    force: bool = False,
    limit: int | None = None,
    shard: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """``shard=(i, n)`` grades every nth case starting at i.

    Added so one grading pass can be split across several endpoints without
    changing its ORDER. The pass sequence stays counterbalanced; only which
    endpoint answers a given case changes. Sharding by stride rather than by
    block keeps each shard a uniform sample of the bank, so a shard that dies
    does not remove a contiguous region of question shapes.
    """
    paths = answer_files(root, arm)
    if not force:
        paths = [
            p
            for p in paths
            if not p.with_name(f"{p.stem}.judgment{suffix}.json").is_file()
        ]
    if shard is not None:
        i, n = shard
        paths = [p for k, p in enumerate(paths) if k % n == i]
    if limit:
        paths = paths[:limit]
    started = time.time()
    done, failed = 0, []
    print(f"[judge] {root.name}/{arm}{suffix or ''}: {len(paths)} case(s), {workers} workers", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(judge_one, p, config, suffix): p for p in paths}
        for future in as_completed(futures):
            case_id, status = future.result()
            done += 1
            if status != "ok":
                failed.append({"case": case_id, "status": status})
            if done % 10 == 0 or done == len(paths):
                print(f"[judge]   {done}/{len(paths)} ({time.time() - started:.0f}s)", flush=True)
    return {
        "root": str(root),
        "arm": arm,
        "suffix": suffix,
        "attempted": len(paths),
        "failed": failed,
        "wall_s": round(time.time() - started, 1),
    }


# -- calibration -------------------------------------------------------------


def calibrate(root: Path, arm: str, config: JudgeConfig, workers: int) -> dict[str, Any]:
    """Grade answers that already carry committed judgments, and compare.

    Writes to a ``.local`` suffix so the committed judgments are never touched.
    Agreement here is the only evidence that this runner's rubric and model
    reproduce the instrument the holdout was measured with.
    """
    summary = run(root, arm, config, workers=workers, suffix=".local", force=True)
    reference, local = [], []
    verdict_match, rows = 0, []
    for path in answer_files(root, arm):
        ref_path = path.with_name(f"{path.stem}.judgment.json")
        loc_path = path.with_name(f"{path.stem}.judgment.local.json")
        if not (ref_path.is_file() and loc_path.is_file()):
            continue
        ref, loc = json.loads(ref_path.read_text()), json.loads(loc_path.read_text())
        reference.append(float(ref["correctness"]))
        local.append(float(loc["correctness"]))
        verdict_match += int(ref["verdict"] == loc["verdict"])
        rows.append(
            {
                "case": path.stem,
                "reference_correctness": ref["correctness"],
                "local_correctness": loc["correctness"],
                "reference_verdict": ref["verdict"],
                "local_verdict": loc["verdict"],
            }
        )
    n = len(rows)
    deltas = [l - r for l, r in zip(local, reference)]
    return {
        **summary,
        "n_compared": n,
        "reference_mean": round(mean(reference), 4) if n else None,
        "local_mean": round(mean(local), 4) if n else None,
        "mean_delta": round(mean(deltas), 4) if n else None,
        "mean_abs_delta": round(mean(abs(d) for d in deltas), 4) if n else None,
        "verdict_agreement": round(verdict_match / n, 4) if n else None,
        "pearson_r": round(_pearson(reference, local), 4) if n > 1 else None,
        "cases": rows,
    }


def _pearson(a: list[float], b: list[float]) -> float:
    ma, mb = mean(a), mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    return num / (da * db) if da and db else 0.0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--root", required=True, help="experiment run root")
    parser.add_argument("--arm", required=True, help="arm directory under the root")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--suffix", default="", help="e.g. .run2 for a repeat pass")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="re-judge existing")
    parser.add_argument("--calibrate", action="store_true",
                        help="grade answers that already have judgments and compare")
    parser.add_argument("--out", default=None, help="write the run summary here")
    parser.add_argument(
        "--position", type=int, default=None,
        help="zero-based position of this cell in its grading session; recorded on "
             "every judgment so a paired comparison stays correctable (EXP-2026-08-022)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    config = JudgeConfig(model=args.model, max_tokens=args.max_tokens, position=args.position)
    root = Path(args.root)
    if args.calibrate:
        summary = calibrate(root, args.arm, config, args.workers)
    else:
        summary = run(root, args.arm, config, args.workers, args.suffix,
                      args.force, args.limit)
    text = json.dumps(summary, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text if not summary.get("cases") else json.dumps(
        {k: v for k, v in summary.items() if k != "cases"}, indent=2))
    return 1 if summary.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
