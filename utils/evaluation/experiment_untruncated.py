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
        "llm_query", "merged", "generic_composed", "generic_planned",
        "generic_local_narrator", "generic_local_full", "generic_narrator_off",
        "rewrite_off", "rewrite_det", "rewrite_model")

#: The small-model endpoint (EXP-2026-09-019). Read at call time, never at
#: import: an import-time environment read is how "LLM-off" runs reached a live
#: model before (`Q12`, and `api/main.py`'s load_env leak).
#:
#: The defaults are the *llama.cpp router* on :7070, not the relay on :4000.
#: The plan named :4000 / `local`, but that alias resolved to `gemma-4-26B-it`
#: on 2026-09-13 while MiniCPM5-2B was loaded behind :7070 — which is exactly
#: what the probe's identity gate is for.
def _local_llm_base_url() -> str:
    return os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:7070/v1")


def _local_llm_model() -> str:
    return os.environ.get("LOCAL_LLM_MODEL", "minicpm-5-2B")


def _local_llm_max_tokens() -> str:
    """16384 of MiniCPM's 131072-token context (its `--ctx-size` at launch).

    Not probed. The endpoint accepts any `max_tokens` and clamps silently, so a
    ceiling cannot be discovered by asking it; this number comes from the served
    model's launch arguments.
    """
    return os.environ.get("LOCAL_LLM_MAX_TOKENS", "16384")


def _local_llm_thinking_budget() -> str:
    """0 — "send no cap". MiniCPM is not a reasoning model.

    Overridable because the same arm is re-pointed at the 27B reasoning model to
    get the cost comparison, and *that* model must have its deliberation capped
    or it spends the whole token budget thinking and returns empty content.
    """
    return os.environ.get("LOCAL_LLM_THINKING_BUDGET", "0")

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
            # Raising the token budget without raising the clock does nothing.
            # The served model reasons for 170 s at 8192 and 230 s at 16384
            # (budget-cost.json, 2026-09-04), and the builder's timeout is 120 s,
            # so every call was aborted mid-reasoning and returned nothing --
            # which the gate then correctly refused as an empty query. The
            # 2026-09-04 re-run built no query on 282 of 284 questions and its
            # answers record wall_s = 360.3, exactly three gate attempts at 120 s.
            # A bound that cuts off a reasoning model is indistinguishable
            # downstream from a model with nothing to say; this is the third
            # instance of that shape in this arm, after the import-time budget
            # freeze and the ignored .env value.
            "SPECIALIST_LLM_TIMEOUT_S": str(max(900, llm_max_tokens // 8)),
            # Operator directive 2026-09-05: cap deliberation, floor the clock.
            # This model over-thinks a task that does not need it -- see
            # llm_sampling.sampling_params -- and the cap is what makes the arm
            # affordable enough to be worth re-running at all.
            "LLM_THINKING_BUDGET": os.environ.get("LLM_THINKING_BUDGET", "512"),
        })
    elif arm == "generic_composed":
        # The control the merged arm actually needed, and the one that did not
        # exist. `generic` disables the templates but ALSO turns on the LLM
        # narrator and the facet loop, so reading `merged` against it compares
        # two things at once — one store against two, and a deterministic
        # composer against a language model. This is `generic` with the language
        # model taken back out: schema-derived primitives, deterministic
        # composition, two stores. Against `merged` the only remaining
        # difference is how many stores there are, and both sides are
        # byte-reproducible, so a difference between them cannot be run
        # variance. EXP-2026-08-001 measured this configuration's retrieval and
        # called it Arm H; it has never been judged.
        env.update({
            "SPECIALIST_GENERIC_ONLY": "true",
            "PLANNER_LLM_ENABLED": "false",
            "SPECIALIST_LLM_ENABLED": "false",
            "SYNTHESIS_LLM_ENABLED": "false",
            "CONVERSATION_LLM_ENABLED": "false",
        })
    elif arm == "generic_planned":
        # The arm that isolates the *plan*, and the one this programme never
        # had. Every headline figure replays an authored decomposition:
        # `generic` and `generic_composed` are both driven by gold-replay
        # runners that hand the pipeline its plan. So 0.92 is the ceiling for
        # retrieval and composition *given a correct plan*, and what it costs to
        # produce that plan has never been measured on any run on record.
        #
        # This is `generic_composed` with exactly one thing changed — the plan
        # comes from the planner instead of from the bank. That is why it drives
        # `run_rewrite`, which runs the REAL pipeline, rather than
        # `run_deterministic`, which replays the authored plan and never
        # executes the stage under test. Every LLM seam is off on both sides, so
        # a paired difference is the planner and nothing else.
        #
        # The rewrite flags are *stated* rather than inherited. They default
        # falsy in `utils/planner/config.py`, so "0" is the shipped posture, and
        # rewrite is a separate stage with its own experiment
        # (EXP-2026-09-014) — letting it move here would confound two answers
        # into one number.
        env.update({
            "SPECIALIST_GENERIC_ONLY": "true",
            "PLANNER_LLM_ENABLED": "false",
            "SPECIALIST_LLM_ENABLED": "false",
            "SYNTHESIS_LLM_ENABLED": "false",
            "CONVERSATION_LLM_ENABLED": "false",
            "ARIADNE_REWRITE": "0",
            "ARIADNE_REWRITE_MODEL": "0",
        })
    elif arm == "generic_local_narrator":
        # EXP-2026-09-019 Step 3 — the 2B model on the seam where it is least
        # dangerous. This is `generic_composed` with one thing added: a small
        # local model rewrites the narrative prose over claims that were already
        # composed deterministically and already verified.
        #
        # The reason this seam is safe is structural, not optimistic. The
        # composer stays deterministic, so the *claims* are not the model's; the
        # verifier runs unconditionally and grounds every asserted identifier;
        # and when the narrator fails outright `utils/synthesis/factory.py`
        # falls back to the composed text and records `fallback_reason`. A weak
        # narrator therefore produces worse prose rather than worse facts, and
        # the failure is counted rather than hidden.
        #
        # The budget is NOT inherited and NOT probed. The probe established that
        # this server accepts any `max_tokens` and clamps silently, so a ceiling
        # cannot be discovered by asking; 131072 is the `--ctx-size` the loaded
        # model was launched with. The thinking budget is 0 because MiniCPM is
        # not a reasoning model — the >=2048 floor `skynet` needs does not apply,
        # and a positive budget must in any case stay below max_tokens.
        env.update({
            "SPECIALIST_GENERIC_ONLY": "true",
            "PLANNER_LLM_ENABLED": "false",
            "SPECIALIST_LLM_ENABLED": "false",
            "CONVERSATION_LLM_ENABLED": "false",
            "SYNTHESIS_LLM_ENABLED": "true",
            "SYNTHESIS_LLM_BASE_URL": _local_llm_base_url(),
            "SYNTHESIS_LLM_MODEL": _local_llm_model(),
            "SYNTHESIS_LLM_MAX_TOKENS": _local_llm_max_tokens(),
            "SYNTHESIS_LLM_THINKING_BUDGET": _local_llm_thinking_budget(),
            # The narrator's failures were read time-outs at the 120 s default
            # (`EXP-2026-09-010`), and a time-out is indistinguishable
            # downstream from a model with nothing to say.
            "SYNTHESIS_LLM_TIMEOUT_S": "600.0",
            "ARIADNE_REWRITE": "0",
            "ARIADNE_REWRITE_MODEL": "0",
        })
    elif arm == "generic_narrator_off":
        # The control Steps 3 and 4 actually need, and the one that did not
        # exist. `generic_composed` is NOT it, for a reason the claim-identity
        # gate caught at n=40: `_run_gold_replay` builds `SynthesisConfig()` —
        # the bare constructor, every cap at its dataclass default — when
        # synthesis is deterministic, and `SynthesisConfig.from_env()` when it is
        # not. So `generic_composed` composes at `max_citations=8` while any
        # narrator arm composes at the un-truncated 200, and two of forty
        # enumeration claims differed on that alone. Reading the narrator
        # against it would have attributed a composer cap to the model.
        #
        # This arm is `generic_local_narrator` with the seam off and nothing
        # else changed, so it loads its config the same way through the same
        # runner. The difference between them is the narrator.
        env.update({
            "SPECIALIST_GENERIC_ONLY": "true",
            "PLANNER_LLM_ENABLED": "false",
            "SPECIALIST_LLM_ENABLED": "false",
            "CONVERSATION_LLM_ENABLED": "false",
            "SYNTHESIS_LLM_ENABLED": "false",
            "SYNTHESIS_LLM_BASE_URL": _local_llm_base_url(),
            "SYNTHESIS_LLM_MODEL": _local_llm_model(),
            "SYNTHESIS_LLM_MAX_TOKENS": _local_llm_max_tokens(),
            "SYNTHESIS_LLM_THINKING_BUDGET": _local_llm_thinking_budget(),
            "SYNTHESIS_LLM_TIMEOUT_S": "600.0",
            "ARIADNE_REWRITE": "0",
            "ARIADNE_REWRITE_MODEL": "0",
        })
    elif arm == "generic_local_full":
        # EXP-2026-09-019 Step 4 — the 2B model on the seam that can lose.
        # Everything `generic_local_narrator` sets, plus a model drafting the
        # queries. This is the seam with a measured downside: on the 27B control
        # the model rewrote the query on 49 of 284 questions and at least one
        # went backwards, and `llm_query` scored 0.4039 on the holdout.
        #
        # **The flag is SPECIALIST_LLM_QUERY_BUILDER, not
        # SPECIALIST_LLM_ENABLED.** The plan names the latter, but no builder
        # reads it — four other arms set it to mean "LLM drafter/synthesis", and
        # `llm_query`'s own comment records the distinction. An arm built to the
        # plan's literal wording would have run with no model writing any query
        # and reported that as a healthy specialist seam, which is the same
        # failure shape as `I-4`: a configuration that cannot do the thing under
        # test, completing successfully.
        #
        # The budget is small and the clock is long, for the reason `llm_query`
        # records: raising the token budget without raising the timeout aborts
        # every call mid-draft, and a bound that cuts a model off is
        # indistinguishable downstream from a model with nothing to say.
        env.update({
            "SPECIALIST_GENERIC_ONLY": "true",
            "PLANNER_LLM_ENABLED": "false",
            "CONVERSATION_LLM_ENABLED": "false",
            "SPECIALIST_LLM_ENABLED": "false",
            "SPECIALIST_LLM_QUERY_BUILDER": "true",
            "SPECIALIST_LLM_BASE_URL": _local_llm_base_url(),
            "SPECIALIST_LLM_MODEL": _local_llm_model(),
            "SPECIALIST_LLM_MAX_TOKENS": "4096",
            "SPECIALIST_LLM_TIMEOUT_S": "600.0",
            "SYNTHESIS_LLM_ENABLED": "true",
            "SYNTHESIS_LLM_BASE_URL": _local_llm_base_url(),
            "SYNTHESIS_LLM_MODEL": _local_llm_model(),
            "SYNTHESIS_LLM_MAX_TOKENS": _local_llm_max_tokens(),
            "SYNTHESIS_LLM_THINKING_BUDGET": _local_llm_thinking_budget(),
            "SYNTHESIS_LLM_TIMEOUT_S": "600.0",
            "LLM_THINKING_BUDGET": _local_llm_thinking_budget(),
            "ARIADNE_REWRITE": "0",
            "ARIADNE_REWRITE_MODEL": "0",
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
    elif arm in ("rewrite_off", "rewrite_det", "rewrite_model"):
        # EXP-2026-09-014. Three arms that differ from each other in exactly one
        # variable: the REAL pipeline (planner included) with no language model
        # anywhere, and the rewrite stage off / deterministic / model-assisted.
        #
        # `rewrite_off` is the control and it is NOT `deterministic`: that arm
        # replays the authored plan and never runs the planner at all, so the
        # stage under test would never execute in it. Comparing against it would
        # measure gold-replay-vs-planner and call it the rewrite.
        #
        # `rewrite_det` fills the form from the shipped machinery alone and is
        # byte-reproducible; `rewrite_model` additionally lets a model choose,
        # from candidate lists it cannot add to, for the slots left unbound.
        #
        # The model here is NOT the drafter, the query builder or the composer:
        # every one of those stays off. It picks indices out of lists, and the
        # gate in `utils/planner/canonical.py` refuses anything else.
        env.update({
            "PLANNER_LLM_ENABLED": "false",
            "SPECIALIST_LLM_ENABLED": "false",
            "SYNTHESIS_LLM_ENABLED": "false",
            "CONVERSATION_LLM_ENABLED": "false",
            "ARIADNE_REWRITE": "0" if arm == "rewrite_off" else "1",
            "ARIADNE_REWRITE_MODEL": "1" if arm == "rewrite_model" else "0",
        })
        if arm == "rewrite_model":
            env["ARIADNE_LLM_MODEL"] = llm_model
    elif arm == "deterministic":
        # Reproducible mode: no LLM in planning, drafting, or synthesis.
        env.update({
            "PLANNER_LLM_ENABLED": "false",
            "SPECIALIST_LLM_ENABLED": "false",
            "SYNTHESIS_LLM_ENABLED": "false",
            "CONVERSATION_LLM_ENABLED": "false",
            # Stated, not left unset: an arm that inherits the operator's `.env`
            # flags is not the arm its name claims.
            "ARIADNE_REWRITE": "0",
            "ARIADNE_REWRITE_MODEL": "0",
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


def _run_real_pipeline(entry: dict, kind: str, *, use_llm: bool) -> tuple[Any, Any, dict]:
    """Drive the REAL pipeline — planner included — at an explicit LLM posture.

    ``use_llm`` is a parameter rather than a constant because it is **not**
    merely a hint that the environment can overrule. ``iter_pipeline`` applies it
    as ``dataclasses.replace(PlannerConfig.from_env(), llm_enabled=use_llm)`` and
    does the same to the specialist and synthesis configs, so it *overwrites*
    whatever ``PLANNER_LLM_ENABLED`` / ``SPECIALIST_LLM_ENABLED`` /
    ``SYNTHESIS_LLM_ENABLED`` resolved to. An arm that sets those three to
    ``false`` and then calls this with ``use_llm=True`` runs every seam live
    against ``ARIADNE_LLM_BASE_URL`` while its own env says it is model-free.

    That was observed directly on 2026-09-13: a socket trace of
    ``generic_planned`` — every seam pinned ``false`` — caught the planner's
    ``OpenAICompatibleDrafter`` opening a connection to the configured endpoint
    on the first question. The posture is therefore stated at the call site,
    where it is visible, and asserted in
    ``utils/evaluation/tests/test_experiment_arms.py``.
    """
    from utils.orchestration.main import PipelineRun, iter_pipeline

    injected: dict[str, Any] | None = None
    mode = entry.get("partial_mode")
    if mode == "attack_down":
        injected = {"attack": None}
    elif mode == "capec_down":
        injected = {"capec": None}

    run = PipelineRun(question=entry["question"], mode="query")
    plan = evidence = answer = None
    for event, payload in iter_pipeline(
        entry["question"], mode="query", use_llm=use_llm, specialists=injected, run=run
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
    # Observed, not asserted. These fields used to be the literals
    # "deterministic" regardless of what ran, which is how an arm with live
    # model seams could write a provenance record claiming it had none.
    return evidence, answer, {
        "planner": "deterministic" if not use_llm else "llm",
        "synthesis": "deterministic" if not use_llm else "llm",
        "use_llm": use_llm,
        "rewrite": getattr(plan, "rewrite", None),
        "observed_plan": _plan_dict(plan),
        "exit_code": run.exit_code,
        "status": run.status,
    }


def run_rewrite(entry: dict, kind: str, _pool: Any) -> tuple[Any, Any, dict]:
    """EXP-2026-09-014's three rewrite arms, at the posture they were run at.

    ``use_llm=True`` is preserved exactly as committed. It is almost certainly
    not what those arms intended — their env pins every seam ``false`` and their
    comment says "no language model anywhere" — but their figures are in the
    record and were produced this way, so changing it here would silently
    re-describe published numbers. See `Q40`.
    """
    return _run_real_pipeline(entry, kind, use_llm=True)


def run_planned(entry: dict, kind: str, _pool: Any) -> tuple[Any, Any, dict]:
    """The real pipeline with the planner running and **no model anywhere**.

    This is what `generic_planned` needs and what :func:`run_rewrite` cannot
    give it: the planner executes for real, and the drafter it selects is the
    deterministic one rather than the hybrid that reaches for an endpoint.
    """
    return _run_real_pipeline(entry, kind, use_llm=False)


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
    # And again: this arm differs from `deterministic` only by an env flag the
    # query builders read, so it needs no driver of its own.
    "generic_composed": run_deterministic,
    # NOT `run_deterministic`: that runner replays the authored plan, which is
    # precisely the variable this arm exists to remove. `run_rewrite` drives the
    # real pipeline with the planner in it and no language model anywhere.
    "generic_planned": run_planned,
    # Same gold-replay driver as `gold_llm`: the arm differs only in its env —
    # generic primitives on, the specialist seam off, and the narrator pointed
    # at the local small model. The claims are composed deterministically in
    # both, which is what makes them comparable.
    "generic_local_narrator": run_gold_llm,
    # Same driver again: the query builder is decided by the pool's
    # SpecialistConfig, not by the runner, exactly as in `llm_query`.
    "generic_local_full": run_gold_llm,
    # The same runner as the arms it controls for, which is the entire point:
    # `_run_gold_replay` loads a DIFFERENT SynthesisConfig depending on the
    # llm_synthesis flag, so a control reached through the other branch is
    # composing at different caps. `SYNTHESIS_LLM_ENABLED=false` in its env is
    # what turns the narrator off, via from_env().
    "generic_narrator_off": run_gold_llm,
    # EXP-2026-09-014's three arms all drive the REAL pipeline (planner
    # included, no language model in it) and differ only by the two rewrite
    # flags their env sets. `run_deterministic` would be wrong here: it replays
    # the authored plan and never runs the planner, which is where the stage
    # under test lives.
    "rewrite_off": run_rewrite,
    "rewrite_det": run_rewrite,
    "rewrite_model": run_rewrite,
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
    if arm in ("llm", "llm_loop", "gold_loop_llm", "generic", "generic_planned",
               "rewrite_off", "rewrite_det", "rewrite_model"):
        pool = None
    elif arm == "merged":
        pool = _MergedPool()
    else:
        pool = _RouterPool(
            llm_enabled=(arm == "gold_llm"),
            llm_query_builder=(arm in ("llm_query", "generic_local_full")),
        )

    manifest: list[dict[str, Any]] = []
    total = len(work)
    # Imported here, not at module scope: this module is imported by tooling that
    # must not trigger utils.llm's config resolution as a side effect.
    from utils.llm import reset_token_meter, token_meter

    reset_token_meter()
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
        # Q38: C-012 claims templates beat a model writing the queries in
        # correctness *and in cost*, and only the correctness half had a number.
        # Read off the transport, not estimated. ``calls`` is reported beside the
        # totals because a server that omits usage contributes zero tokens and a
        # zero total must not read as "this arm spent nothing".
        "tokens": token_meter(),
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


#: Arms with no model seam. A preflight against a relay they never call would
#: fail a run that cannot be affected by the relay at all.
_MODEL_FREE_ARMS = frozenset({
    "deterministic", "generic_composed", "generic_planned", "merged",
    # No live seam: SYNTHESIS_LLM_ENABLED=false, and every other seam off. It
    # names an endpoint only so that its config resolves identically to the
    # arms it is the control for.
    "generic_narrator_off",
})


def _preflight_llm(arm: str, model: str) -> None:
    """Refuse to start an LLM arm whose endpoint does not serve the model.

    The default was ``skynet`` and the configured endpoint is ``:9090``, which
    serves ``default-model``. Asking :9090 for ``skynet`` returns HTTP 404, the
    pipeline raises ``LLMUnavailable``, every seam falls back to its
    deterministic path, and the run **completes** — 284 answers, no error, a
    plausible wrong number. That is `I-4`'s failure shape and it is the third
    time this project has hit it, so it is now a hard stop rather than a habit.

    Probing costs one 32-token completion. The served model is read off the
    *response* envelope, never from the alias, because this project's aliases
    have pointed at three different architectures (`D-028`, `Q12`).
    """
    if arm in _MODEL_FREE_ARMS:
        return
    import json as _json
    import urllib.error
    import urllib.request

    base = (
        os.environ.get("SYNTHESIS_LLM_BASE_URL")
        or os.environ.get("ARIADNE_LLM_BASE_URL")
        or "http://localhost:9090/v1"
    ).rstrip("/")
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=_json.dumps(
            {
                "model": model,
                "max_tokens": 32,
                "temperature": 0.0,
                "messages": [{"role": "user", "content": "ready"}],
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        served = _json.loads(urllib.request.urlopen(request, timeout=300).read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        raise SystemExit(
            f"LLM preflight failed: {base} returned HTTP {exc.code} for model "
            f"{model!r}: {detail}\n"
            f"Arm {arm!r} has live model seams; running it now would fall back "
            f"silently on every question and report a number that is not this "
            f"arm's. Pass --llm-model with a model this endpoint serves."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            f"LLM preflight failed: {base} unreachable for arm {arm!r}: {exc}"
        ) from exc
    print(
        f"[preflight] {base} model {model!r} serves "
        f"{served.get('model')!r} — ok",
        flush=True,
    )


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
        default="default-model",
        help="model id for every LLM seam. Default 'default-model' on :9090.",
    )
    parser.add_argument("--llm-max-tokens", type=int, default=16384)
    args = parser.parse_args(argv)

    from utils.config import load_env

    load_env()
    overlay = untruncated_env(
        arm=args.arm, llm_model=args.llm_model, llm_max_tokens=args.llm_max_tokens
    )
    apply_env(overlay)
    # Probe the model the arm will ACTUALLY use, not the one on the command
    # line. An arm that pins its own endpoint (the EXP-2026-09-019 local arms)
    # would otherwise be preflighted against `--llm-model`'s default and pass or
    # fail for a model it never calls — which is the preflight reporting on the
    # wrong thing, the same shape of error it exists to prevent.
    _preflight_llm(
        args.arm,
        overlay.get("SYNTHESIS_LLM_MODEL")
        or overlay.get("SPECIALIST_LLM_MODEL")
        or args.llm_model,
    )
    only = {s.strip() for s in args.only.split(",")} if args.only else None
    run_arm(
        args.arm, root=args.root, workers=args.workers,
        limit=args.limit, only=only, bank=args.bank,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
