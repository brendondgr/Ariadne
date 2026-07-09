#!/usr/bin/env python3
"""Correctness judge: grade an answer against the golden expected answer.

This is the harness's core capability and the analyst's actual ask — *how
correct is the answer*, graded against the known answer key (the bank
``assertions``), not merely how faithful it is to its own evidence (which
``utils.evaluation.llm_judge`` already covers).

Two graders, mirroring the repo's deterministic-floor discipline:

* :class:`DeterministicCorrectness` — mechanical id recall/precision of the
  golden expected ids against the ids the answer states. Always available and
  fully reproducible; the floor every LLM verdict also carries.
* :class:`LocalLLMCorrectness` — asks the **local LLM** to rate correctness,
  label, and rationale. On any transport/parse failure it raises
  :class:`CorrectnessUnavailable` so :class:`HybridCorrectness` falls back to the
  deterministic floor. The id recall/precision numbers are computed
  mechanically even on an LLM verdict, so they are never model-invented.

Note: the deterministic composer lists *representative* related ids in prose
("Found 4 item(s) … e.g. M1038, M1040, M1018"), so deterministic recall can read
below 1.0 even for an essentially-correct answer — which is exactly why the LLM
correctness grade is the headline and the id math is a reproducible backstop.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

from utils.evaluation.harness.contracts import LABELS, AnswerRecord, CorrectnessVerdict
from utils.evaluation.harness.ids import canonical_set
from utils.evaluation.llm_judge.config import EvalConfig
from utils.evaluation.llm_judge.llm_judge import extract_json_object

logger = logging.getLogger("ariadne.evaluation.harness.correctness")


class CorrectnessUnavailable(Exception):
    """Raised when the LLM correctness grader cannot produce a usable verdict."""


# --- deterministic id math (shared by both graders) -------------------------

def grade_ids(record: AnswerRecord) -> dict:
    """Mechanical correctness of ``record`` against its golden expected ids."""
    if record.error:
        return {
            "correctness": 0.0,
            "label": "incorrect",
            "id_recall": 0.0,
            "id_precision": 0.0,
            "missing_ids": [],
            "extra_ids": [],
            "rationale": f"run failed: {record.error}",
        }

    gold = canonical_set(record.gold_expected_ids)
    produced = canonical_set(record.produced_ids)

    if record.expect_empty:
        honest = not record.claims  # no fabricated facts where none were expected
        return {
            "correctness": 1.0 if honest else 0.0,
            "label": "correct" if honest else "incorrect",
            "id_recall": 1.0 if honest else 0.0,
            "id_precision": 1.0 if honest else 0.0,
            "missing_ids": [],
            "extra_ids": [] if honest else sorted(produced),
            "rationale": (
                "honest abstention (no facts expected)"
                if honest
                else "asserted facts where the correct answer is an abstention"
            ),
        }

    if not gold:
        answered = bool(record.claims)
        return {
            "correctness": 1.0 if answered else 0.0,
            "label": "correct" if answered else "incorrect",
            "id_recall": 1.0 if answered else 0.0,
            "id_precision": 1.0 if answered else 0.0,
            "missing_ids": [],
            "extra_ids": [],
            "rationale": "no id-level gold; graded on whether the system answered",
        }

    matched = gold & produced
    recall = len(matched) / len(gold)
    precision = len(matched) / len(produced) if produced else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    if recall >= 1.0 and precision >= 0.5:
        label = "correct"
    elif recall > 0.0:
        label = "partial"
    else:
        label = "incorrect"
    return {
        "correctness": f1,
        "label": label,
        "id_recall": recall,
        "id_precision": precision,
        "missing_ids": sorted(gold - produced),
        "extra_ids": sorted(produced - gold),
        "rationale": f"id recall {recall:.2f}, precision {precision:.2f}",
    }


# --- prompt (pure; testable without HTTP) -----------------------------------

_SYSTEM_PROMPT = """\
You grade the CORRECTNESS of an answer produced by a federated graph-database \
question-answering system, against a known ANSWER KEY (the identifiers a fully \
correct answer must convey). You are given the analyst QUESTION, the SYSTEM \
ANSWER (its narrative, verified claims, and any abstentions), and the EXPECTED \
ANSWER KEY.

Rate the answer:
- correctness: a number from 0.0 to 1.0 (1.0 = conveys the expected answer with \
nothing incorrect; give partial credit when only some expected items are \
conveyed; 0.0 = wrong or empty).
- label: exactly one of "correct", "partial", or "incorrect".
- rationale: one short sentence.

An honest abstention is fully correct when the EXPECTED ANSWER KEY is empty (the \
correct answer is that nothing matches). Do not reward an answer for naming ids \
that are not in the key.

Output ONLY a single JSON object (no prose, no markdown fences):
{"correctness": <0..1>, "label": "correct|partial|incorrect", "rationale": "<one line>"}
"""

_MAX_CLAIMS = 40


def build_correctness_messages(record: AnswerRecord) -> list[dict[str, str]]:
    """Build the chat messages for grading one answer (pure)."""
    claim_lines = [f"- {c.get('text', '')}" for c in record.claims[:_MAX_CLAIMS]]
    abstention_lines = [
        f"- ({a.get('source', '?')}) {a.get('statement', '')}"
        for a in record.abstentions
    ]
    key = ", ".join(record.gold_expected_ids) if record.gold_expected_ids else "(empty)"
    context = [
        f"QUESTION:\n{record.question}",
        "",
        "SYSTEM ANSWER:",
        f"  narrative: {record.narrative or '(none)'}",
        "  claims:",
        "\n".join(claim_lines) if claim_lines else "    (none)",
        "  abstentions:",
        "\n".join(abstention_lines) if abstention_lines else "    (none)",
        "",
        f"EXPECTED ANSWER KEY (ids a correct answer must convey): {key}",
    ]
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(context)},
    ]


def _coerce_label(data: dict, correctness: float) -> str:
    label = str(data.get("label", "")).strip().lower()
    if label in LABELS:
        return label
    # derive from the numeric score when the model omitted/garbled the label
    if correctness >= 0.85:
        return "correct"
    if correctness > 0.3:
        return "partial"
    return "incorrect"


def _clamp01(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def parse_correctness(data: dict, record: AnswerRecord) -> CorrectnessVerdict:
    """Turn the model JSON into a verdict; id math stays deterministic."""
    floor = grade_ids(record)
    correctness = _clamp01(data.get("correctness"))
    label = _coerce_label(data, correctness)
    rationale = str(data.get("rationale") or "").strip()
    if not rationale:
        reasons = data.get("reasons")
        if isinstance(reasons, list) and reasons:
            rationale = str(reasons[0])
    return CorrectnessVerdict(
        question_id=record.question_id,
        source="llm",
        correctness=correctness,
        label=label,
        id_recall=floor["id_recall"],
        id_precision=floor["id_precision"],
        missing_ids=floor["missing_ids"],
        extra_ids=floor["extra_ids"],
        rationale=rationale or floor["rationale"],
    )


# --- graders ----------------------------------------------------------------

class CorrectnessGrader(Protocol):
    name: str

    def judge(self, record: AnswerRecord) -> CorrectnessVerdict: ...


class DeterministicCorrectness:
    """Mechanical id recall/precision grader — always available, reproducible."""

    name = "deterministic"

    def judge(self, record: AnswerRecord) -> CorrectnessVerdict:
        g = grade_ids(record)
        return CorrectnessVerdict(
            question_id=record.question_id,
            source="deterministic",
            correctness=g["correctness"],
            label=g["label"],
            id_recall=g["id_recall"],
            id_precision=g["id_precision"],
            missing_ids=g["missing_ids"],
            extra_ids=g["extra_ids"],
            rationale=g["rationale"],
        )


class LocalLLMCorrectness:
    """Grades correctness via a configurable OpenAI-compatible (local) endpoint."""

    name = "llm"

    def __init__(self, config: EvalConfig) -> None:
        self._config = config

    @property
    def endpoint(self) -> str:
        return self._config.llm_base_url.rstrip("/") + "/chat/completions"

    def _post(self, messages: list[dict[str, str]]) -> str:
        import requests

        payload = {
            "model": self._config.llm_model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self._config.llm_max_tokens,
        }
        try:
            resp = requests.post(
                self.endpoint, json=payload, timeout=self._config.llm_timeout_s
            )
        except requests.RequestException as exc:
            raise CorrectnessUnavailable(f"request failed: {exc}") from exc
        if resp.status_code != 200:
            raise CorrectnessUnavailable(f"HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise CorrectnessUnavailable(f"unexpected response shape: {exc}") from exc
        if not content:
            raise CorrectnessUnavailable("model returned no content (raise max_tokens?)")
        return content

    def judge(self, record: AnswerRecord) -> CorrectnessVerdict:
        messages = build_correctness_messages(record)
        content = self._post(messages)
        try:
            data = extract_json_object(content)
        except Exception as exc:  # llm_judge raises JudgeUnavailable on bad JSON
            raise CorrectnessUnavailable(str(exc)) from exc
        verdict = parse_correctness(data, record)
        logger.info(
            "LLM graded %s: %.2f (%s)",
            record.question_id,
            verdict.correctness,
            verdict.label,
        )
        return verdict


class HybridCorrectness:
    """Tries the LLM grader, falling back to the deterministic floor on failure."""

    name = "hybrid"

    def __init__(self, primary: CorrectnessGrader, fallback: CorrectnessGrader) -> None:
        self._primary = primary
        self._fallback = fallback
        self.last_used = ""

    def judge(self, record: AnswerRecord) -> CorrectnessVerdict:
        try:
            verdict = self._primary.judge(record)
            self.last_used = self._primary.name
            return verdict
        except CorrectnessUnavailable as exc:
            logger.info("LLM correctness unavailable (%s); using deterministic", exc)
            self.last_used = self._fallback.name
            return self._fallback.judge(record)


def select_grader(config: EvalConfig, *, use_llm: bool) -> CorrectnessGrader:
    """Return the configured grader (hybrid LLM when requested, else floor)."""
    deterministic = DeterministicCorrectness()
    if use_llm:
        logger.info(
            "LLM correctness enabled: %s (model=%s)",
            config.llm_base_url,
            config.llm_model,
        )
        return HybridCorrectness(LocalLLMCorrectness(config), deterministic)
    return deterministic


def judge_answers(
    records: list[AnswerRecord],
    *,
    config: EvalConfig | None = None,
    use_llm: bool = False,
    sample_size: int | None = None,
) -> list[CorrectnessVerdict]:
    """Grade a batch of answers; only the first ``sample_size`` get the LLM."""
    config = config or EvalConfig.from_env()
    grader = select_grader(config, use_llm=use_llm)
    floor = DeterministicCorrectness()
    cap = sample_size if sample_size is not None else config.sample_size

    verdicts: list[CorrectnessVerdict] = []
    for index, record in enumerate(records):
        if use_llm and index < cap:
            verdicts.append(grader.judge(record))
        else:
            verdicts.append(floor.judge(record))
    return verdicts
