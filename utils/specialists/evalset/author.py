#!/usr/bin/env python3
"""The Author role, automated — one question per anchor, blind to the system.

``docs/plans/robustness/02-holdout-question-generation.md`` separates three
roles and permits no agent to hold two of them. The Author is the only one with
a context restriction, and it is absolute: it sees a category description, an
identifier, an entity type and a name, and nothing else. Never the templates,
never the schema, never an example question.

For holdout v1 that restriction was enforced by hand — thirty separate subagent
conversations, no shared context, no repository access. This module enforces the
same restriction mechanically: the only thing sent to the model is
``holdout_protocol.author_prompt(entry)``, which is built from four fields of one
anchor. There is no system prompt carrying repository context, no tool access,
and no conversation history between anchors. That makes the Author reproducible
and cheap without making it better informed.

**What automating this does and does not change.** It does not weaken blindness:
the prompt is the same prompt, and a model that cannot see the templates cannot
be led by them whether a human pastes the prompt or a loop does. It does change
*phrasing diversity* — thirty calls to one model at one temperature will explore
a narrower band of wording than thirty separate authors would, and question
phrasing is part of what a question set tests. A generated bank is therefore a
strong regression and arm-comparison instrument and a weaker basis for a
published headline figure. That limitation belongs in the dataset card, and
``make_bank`` writes it there.

The output is validated, not trusted. A question that names an identifier other
than its own anchor is rejected and re-drawn, because gold is computed from the
anchor alone: a stray ``T1055`` in the text would make the question ask for
something the gold does not cover, and nothing downstream would notice.

Run through :mod:`utils.specialists.evalset.make_bank` rather than directly.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from utils.specialists.evalset.holdout_protocol import author_prompt

#: The Author must not be the model the pipeline runs on. A model grading or
#: authoring for a pipeline that shares its weights shares its blind spots, and
#: the whole point of a blind bank is to not share blind spots with the system
#: under test. Overridable, because which alias is free depends on the relay.
DEFAULT_BASE_URL = os.environ.get("AUTHOR_LLM_BASE_URL", "http://localhost:4000/v1")
DEFAULT_MODEL = os.environ.get("AUTHOR_LLM_MODEL", "local")
# Measured, not guessed: this model spends ~1900-2100 tokens of reasoning before
# emitting a one-line question, so a 2048 budget truncates to an *empty* reply
# often enough to burn three retries on a single anchor. An empty completion
# reads exactly like a dead server, which is the same trap the judge runner hit.
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT_S = 600.0
DEFAULT_WORKERS = 8
DEFAULT_ATTEMPTS = 4

#: Models that serve strictly one request at a time. Sending these concurrent
#: work does not merely fail to help — it queues every request behind the first
#: and pushes them all towards the timeout, so a bank that would have generated
#: slowly instead fails slowly. `local` is llama.cpp single-stream; `skynet` is
#: vLLM and batches happily. Override with AUTHOR_LLM_SERIAL="a,b" when the
#: relay's backing changes.
SERIAL_MODELS = frozenset(
    m.strip() for m in os.environ.get("AUTHOR_LLM_SERIAL", "local").split(",") if m.strip()
)


def workers_for(model: str, requested: int) -> int:
    """Clamp concurrency to what the model can actually serve.

    Returning a smaller number than asked for is the right behaviour here: the
    caller's `--workers 8` expresses impatience, not a fact about the backend.
    """
    return 1 if model in SERIAL_MODELS else max(1, requested)

#: Identifier shapes the Author is forbidden from introducing. Deliberately
#: broad: a false positive costs one retry, a false negative silently corrupts
#: a question's gold.
_ID_PATTERNS = (
    re.compile(r"\bT\d{4}(?:\.\d{3})?\b"),        # technique / sub-technique
    re.compile(r"\bTA\d{4}\b"),                    # tactic
    re.compile(r"\b[GSMC]\d{4}\b"),                # group / software / mitigation / campaign
    re.compile(r"\bCAPEC-\d+\b", re.IGNORECASE),
    re.compile(r"\bCWE-\d+\b", re.IGNORECASE),
)


class AuthorUnavailable(RuntimeError):
    """The Author model could not be reached, or never returned usable text."""


@dataclass(frozen=True)
class AuthorConfig:
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    timeout_s: float = DEFAULT_TIMEOUT_S
    temperature: float = 1.0   # phrasing variety is the point; this is not a graded task
    attempts: int = DEFAULT_ATTEMPTS


def identifiers_in(text: str) -> set[str]:
    """Every MITRE-shaped identifier appearing in ``text``, upper-cased."""
    found: set[str] = set()
    for pattern in _ID_PATTERNS:
        found.update(match.group(0).upper() for match in pattern.finditer(text))
    return found


def rejection_reason(question: str, anchor: str) -> str | None:
    """Why this question is unusable, or ``None`` if it is fine.

    Checks the three ways an authored question silently breaks its own gold:
    it is empty, it never names the anchor (so the pipeline has nothing to
    resolve), or it names some *other* entity (so the gold no longer covers
    what was asked).
    """
    text = (question or "").strip()
    if not text:
        return "empty"
    if len(text) > 600:
        return f"too long ({len(text)} chars) — the model probably explained itself"
    upper_anchor = anchor.upper()
    found = identifiers_in(text)
    if upper_anchor not in found:
        return f"does not name its anchor {anchor}"
    strays = found - {upper_anchor}
    # A sub-technique's parent is not a stray: "T1055.011" legitimately contains
    # "T1055" only as a substring, and the regex already prefers the longer form.
    strays = {s for s in strays if not upper_anchor.startswith(s + ".")}
    if strays:
        return f"names other identifiers: {', '.join(sorted(strays))}"
    return None


def _post(config: AuthorConfig, prompt: str) -> str:
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
    }
    request = urllib.request.Request(
        f"{config.base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=config.timeout_s) as response:
                body = json.load(response)
            return (body["choices"][0]["message"]["content"] or "").strip()
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(2**attempt)
    raise AuthorUnavailable(f"{config.model} at {config.base_url}: {last}")


def author_one(entry: dict[str, Any], config: AuthorConfig) -> tuple[str, list[str]]:
    """Author one question. Returns ``(question, rejected_attempts)``.

    Rejections are returned rather than swallowed so the bank can record how
    often the Author had to be asked again — a quality signal about the model
    that would otherwise be invisible.
    """
    prompt = author_prompt(entry)
    anchor = entry["anchor"]
    rejected: list[str] = []
    for _ in range(config.attempts):
        text = _post(config, prompt)
        # Reasoning models sometimes wrap the answer; take the last non-empty
        # line, which is where the bare question lands.
        candidate = next(
            (line.strip().strip('"') for line in reversed(text.splitlines()) if line.strip()),
            "",
        )
        reason = rejection_reason(candidate, anchor)
        if reason is None:
            return candidate, rejected
        rejected.append(f"{reason} :: {candidate[:120]}")
    raise AuthorUnavailable(
        f"{entry['id']} ({anchor}): {config.attempts} attempts all rejected — {rejected}"
    )


def author_all(
    anchors: list[dict[str, Any]],
    config: AuthorConfig | None = None,
    workers: int = DEFAULT_WORKERS,
) -> dict[str, Any]:
    """Author every anchor. Returns the ``authored.json`` payload."""
    config = config or AuthorConfig()
    effective = workers_for(config.model, workers)
    if effective != workers:
        print(
            f"[author] {config.model} serves one request at a time — "
            f"using 1 worker, not {workers}",
            flush=True,
        )
    workers = effective
    questions: dict[str, str] = {}
    retries: dict[str, list[str]] = {}
    failures: dict[str, str] = {}

    total = len(anchors)
    done = 0

    def one(entry: dict[str, Any]) -> None:
        nonlocal done
        try:
            text, rejected = author_one(entry, config)
            questions[entry["id"]] = text
            if rejected:
                retries[entry["id"]] = rejected
        except AuthorUnavailable as exc:
            failures[entry["id"]] = str(exc)
        done += 1
        print(f"[author] {done}/{total} {entry['id']}", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, anchors))

    return {
        "author_model": f"{config.model} @ {config.base_url}",
        "author_temperature": config.temperature,
        "spawns": (
            "one stateless completion per anchor, no shared context, no tool access, "
            "no repository access; prompt is holdout_protocol.author_prompt(entry) verbatim"
        ),
        "validation": (
            "each question must name its own anchor and no other MITRE identifier; "
            "rejected drafts were re-requested up to "
            f"{config.attempts} times and are recorded under 'retries'"
        ),
        "questions": dict(sorted(questions.items())),
        "retries": dict(sorted(retries.items())),
        "failures": dict(sorted(failures.items())),
    }
