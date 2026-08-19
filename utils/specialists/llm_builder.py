#!/usr/bin/env python3
"""An LLM writes the query directly — the baseline C-012 has never had.

`CLAIMS.md` C-012 is the paper's intended headline: *"routing to a fixed library
of validated parameterised templates outperforms letting an LLM plan and
generate the queries."* Its note says, in the ledger's own words, **"This is the
paper's intended headline and no experiment supports it."** No arm in the study
lets a model write Cypher or Gremlin. Arm G disables the templates but still
composes queries from schema primitives; nothing has ever handed a language
model a schema and asked for a query string.

This is that arm. It is deliberately the *fair* version of the baseline, not a
strawman:

* the model is given the real schema — node labels, relationship types, limit
  bounds and entity glosses, rendered from the same source card the templates
  are validated against;
* it is given the resolved seed identifiers, so it is not asked to guess ids;
* it is told the constraints the gate actually enforces, and the harness's
  output-column convention, so it fails on reasoning rather than on trivia it
  was never told. This is levelling, not coaching: the templated builders have
  the column names and the id-binding idiom baked in by construction, so a
  baseline left to guess them would be measuring the harness rather than the
  model. What the model still has to work out — the traversal, the direction,
  the labels, the filter — is untouched; and
* when the gate rejects a draft, the rejection reasons are fed back and it may
  try again, using the retry loop `QuerySpecialist` already runs. A baseline
  with no repair loop would be a strawman.

What it is *not* given is any template, any example query, or any hint about the
routing library. That is the whole point.

**Nothing about the safety gate is relaxed for this arm.** `BaseValidator`
operates on the query string, never on `draft.template`, so an LLM-written query
is checked exactly as a templated one: single statement, read-only, labels and
relationships that exist in the card, bounded traversal depth, and a row cap
injected before execution. A model that emits `DETACH DELETE` is refused by the
same code that refuses it today, and `test_llm_builder.py` asserts that rather
than assuming it.

**On failure, this builder does not fall back to templates.** A fallback would
silently convert the baseline into the treatment and the resulting comparison
would be meaningless. An unreachable model yields an empty draft, which the gate
rejects with a recorded reason, and the specialist reports an honest failure.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from utils.specialists.resolve import ResolvedTask
from utils.specialists.validation import QueryDraft

#: This arm's model configuration reuses the `SPECIALIST_LLM_*` block that
#: `SpecialistConfig` has parsed since the beginning and no builder has ever
#: read. `docs/query-safety.md` calls it "the reserved LLM query-builder seam";
#: this is the thing it was reserved for.
DEFAULT_MAX_TOKENS = int(os.environ.get("SPECIALIST_LLM_MAX_TOKENS", "4096"))

_CYPHER_RULES = """\
- Emit exactly ONE Cypher statement. No semicolons, no multiple statements.
- It MUST contain both MATCH and RETURN. A bare RETURN, a CALL, or a
  procedure invocation will be refused.
- Read-only only. CREATE, MERGE, DELETE, SET, REMOVE, DROP, DETACH DELETE,
  LOAD CSV, FOREACH and CALL { ... } are all refused.
- Use only node labels and relationship types from the schema above. A label
  that is not listed does not exist.
- Do not use unbounded variable-length paths (`-[:REL*]->`). A bounded one
  within the depth limit is fine.
- Bind values through $parameters and put them in "params". Do not inline
  string literals.
- OUTPUT CONTRACT — name your returned columns `<entity>_id` and
  `<entity>_name`, lower-case, e.g. `g.attack_id AS group_id, g.name AS
  group_name, t.attack_id AS technique_id, t.name AS technique_name`. The
  reader dispatches on these names; `group_attack_id` will not be understood."""

_GREMLIN_RULES = """\
- Emit exactly ONE Gremlin traversal, starting with `g.V(` or `g.E(`.
- Read-only only. addV, addE, drop, property, sideEffect and io are refused.
- Use only labels and relationship types from the schema above, and only in a
  direction the schema allows.
- Do not chain more than the traversal-depth limit of out/in/both steps.
- Bind values through named parameters (e.g. `within(ids)`) and put them in
  "params". Do not inline literals.
- Bind identifiers by PROPERTY, never by vertex id: write
  `g.V().has("id", within(ids))`, not `g.V(ids)`. `g.V(ids)` asks for internal
  vertex ids and fails on the string identifiers this graph uses.
- Prefer elementMap() so properties come back with the vertex."""

_PROMPT = """\
You are writing ONE database query against a security knowledge graph.

SCHEMA — this is the complete set of labels and relationships that exist:
{schema}

QUESTION: {question}
{seeds}
Language: {language}

RULES — a query violating any of these is rejected before it runs:
{rules}
{feedback}
Return ONLY a JSON object, no prose and no code fences:
{{"query": "<the query>", "params": {{"name": value}}}}
"""


class LLMBuilderUnavailable(RuntimeError):
    """The query model could not be reached or returned nothing usable."""


@dataclass
class LLMQueryBuilder:
    """A ``QueryBuilder`` that asks a language model for the query string.

    Satisfies the same protocol as ``CypherQueryBuilder`` and
    ``GremlinQueryBuilder`` — ``build(resolved, feedback) -> QueryDraft`` — so it
    drops into ``QuerySpecialist`` with no other change, and inherits the gate,
    the repair loop, the connector, the normalizer and the evidence contract.
    """

    card: Any
    language: str                      # "cypher" | "gremlin"
    base_url: str = "http://localhost:4000/v1"
    model: str = "skynet"
    timeout_s: float = 180.0
    max_tokens: int = DEFAULT_MAX_TOKENS
    #: Recorded per draft so the experiment can separate "the model reasoned
    #: badly" from "the model could not phrase a legal query" — two different
    #: findings that a single correctness number would conflate.
    attempts: int = 0
    last_error: str | None = None

    # -- prompt ------------------------------------------------------------

    def _schema_block(self) -> str:
        card = self.card
        labels = ", ".join(sorted(getattr(card, "node_labels", []) or []))
        rels = ", ".join(sorted(getattr(card, "relationship_types", []) or []))
        try:
            limits = card.limits()
        except Exception:  # noqa: BLE001 — a card without limits still yields a prompt
            limits = {}
        glosses = (getattr(card, "entity_descriptions", None) or {}).get("nodes", {})
        gloss_lines = "\n".join(
            f"    - {label}: {glosses[label]}"
            for label in sorted(getattr(card, "node_labels", []) or [])
            if label in glosses
        )
        return (
            f"  dataset: {getattr(card, 'dataset', '?')}\n"
            f"  node_labels: {labels}\n"
            f"  relationship_types: {rels}\n"
            f"  limits: {limits}\n"
            f"  entity notes:\n{gloss_lines}"
        )

    def prompt_for(self, resolved: ResolvedTask, feedback: list[str] | None) -> str:
        seeds = (
            f"KNOWN IDENTIFIERS in the question: {', '.join(resolved.seed_ids)}\n"
            if resolved.seed_ids
            else ""
        )
        repair = ""
        if feedback:
            repair = (
                "\nYour previous attempt was REJECTED for these reasons. Fix them:\n"
                + "\n".join(f"  - {r}" for r in feedback)
                + "\n"
            )
        return _PROMPT.format(
            schema=self._schema_block(),
            question=resolved.task.text,
            seeds=seeds,
            language=self.language,
            rules=_CYPHER_RULES if self.language == "cypher" else _GREMLIN_RULES,
            feedback=repair,
        )

    # -- transport ---------------------------------------------------------

    def _post(self, prompt: str) -> str:
        import requests

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": self.max_tokens,
        }
        try:
            response = requests.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                json=payload,
                timeout=self.timeout_s,
            )
        except requests.RequestException as exc:
            raise LLMBuilderUnavailable(f"request failed: {exc}") from exc
        if response.status_code != 200:
            raise LLMBuilderUnavailable(f"HTTP {response.status_code}: {response.text[:200]}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMBuilderUnavailable(f"unexpected response shape: {exc}") from exc
        if not content:
            # The local reasoning models spend their budget before emitting and
            # return an empty string, which reads exactly like a dead endpoint.
            raise LLMBuilderUnavailable("model returned no content (raise max_tokens?)")
        return content

    # -- the protocol ------------------------------------------------------

    def build(
        self, resolved: ResolvedTask, feedback: list[str] | None = None
    ) -> QueryDraft:
        self.attempts += 1
        try:
            raw = self._post(self.prompt_for(resolved, feedback))
            parsed = extract_json_object(raw)
            query = str(parsed.get("query") or "").strip()
            params = parsed.get("params") or {}
            if not isinstance(params, dict):
                params = {}
            self.last_error = None if query else "model returned no query field"
        except (LLMBuilderUnavailable, ValueError) as exc:
            # No template fallback, deliberately: falling back would turn the
            # baseline into the treatment and make the comparison meaningless.
            # An empty query is refused by the gate with a recorded reason.
            self.last_error = str(exc)
            query, params = "", {}

        return QueryDraft(
            query=query,
            params=params,
            template="llm_generated",
            meta={
                "builder": "llm",
                "language": self.language,
                "model": self.model,
                "attempt": self.attempts,
                "error": self.last_error,
                "repaired_from": list(feedback or ()),
            },
        )


def extract_json_object(text: str) -> dict[str, Any]:
    """First balanced top-level JSON object in model output.

    Same job as ``utils.planner.llm_drafter.extract_json_object`` and duplicated
    rather than imported: that one raises ``DrafterUnavailable``, a planner-layer
    error, and the specialist layer should not depend on the planner's exception
    hierarchy to draft a query. Handles the reasoning preamble and code fences
    these models wrap answers in.
    """
    if not text:
        raise ValueError("empty model response")
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in model response")
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : index + 1])
    raise ValueError("unbalanced JSON object in model response")
