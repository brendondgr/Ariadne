#!/usr/bin/env python3
"""Planner subgraph nodes: classify, canonicalize, draft, gate, finalize, degrade.

Each node wraps the exact domain logic ``PlanningAgent.plan`` used to inline —
the configured ``PlanDrafter``, the deterministic gate (``utils.planner.gate.
evaluate``), and honest degradation (``utils.planner.degrade``). Nodes are
built by a factory closure so the drafter/cards/iteration-cap live outside the
graph state (they are collaborators, not data).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from utils.orchestration.state import PlanningState
from utils.planner.cards import SourceCardView
from utils.planner.config import PlannerConfig
from utils.planner.degrade import degrade_to_partial
from utils.planner.drafter import PlanDrafter
from utils.planner.gate import evaluate
from utils.planner.intent import IntentClassifier

logger = logging.getLogger("ariadne.planner.agent")

NodeFn = Callable[[PlanningState], dict[str, Any]]


#: What the record says when the stage is switched off. A rung of ``off`` is
#: not the same as a rung that ran and bound nothing, and the difference is the
#: whole point of recording it.
RUNG_OFF = "off"
RUNG_DETERMINISTIC = "deterministic"
RUNG_MODEL = "model"
RUNG_ABSTAIN = "abstain"
#: The question already cites an identifier, and ``rewrite_only_without_identifier``
#: is set, so the stage stood down. Distinct from ``RUNG_OFF`` on purpose: off
#: means the flag is not set, this means the flag is set and the gate declined.
RUNG_SKIPPED_ID = "skipped_identifier"
#: The anchor was not bound by an exact lookup, and
#: ``rewrite_require_resolved_anchor`` is set, so the stage stood down rather
#: than let a model choose which entity the question is about.
RUNG_SKIPPED_ANCHOR = "skipped_unresolved_anchor"

#: Anchor provenances that count as "we know who this question is about".
#: `deterministic_fill` writes these into the form's `sources`; anything else --
#: a model pick, an ambiguity, or nothing at all -- is a guess.
_EXACT_ANCHOR_SOURCES = frozenset({"exact-id", "exact-name"})


def build_nodes(
    drafter: PlanDrafter,
    cards: dict[str, SourceCardView],
    max_iterations: int,
    classifier: IntentClassifier,
    config: PlannerConfig | None = None,
) -> dict[str, NodeFn]:
    """Return the planner subgraph's node functions, closed over collaborators."""

    def classify(state: PlanningState) -> dict[str, Any]:
        # Planner step one: name the analyst intent before any drafting. The
        # label biases the draft; the gate remains the authority on what ships.
        intent = classifier.classify(state["request"], cards)
        logger.info(
            "intent classified: %s (%.2f, %s)",
            intent.label, intent.confidence, intent.source,
        )
        return {"intent": intent}

    def canonicalize(state: PlanningState) -> dict[str, Any]:
        """Rewrite the request into the tier-0 question the engine answers best.

        Between ``classify`` and ``draft`` on purpose: the deterministic fill
        reads the classified intent to decide the mode, and everything after
        this node — the drafter, the gate, the specialists, the composer — is
        untouched and sees only a ``request`` string, exactly as it always has.

        The request is replaced **only** when the form binds and renders. A form
        with an outstanding slot, a render that cannot be built, and the flag
        being off are all the same outcome here: the analyst's own words go
        forward, which is today's behaviour, byte for byte.
        """
        original = state.get("original_request") or state["request"]
        if config is None or not config.rewrite_enabled:
            return {"rewrite_trace": {"rung": RUNG_OFF}, "original_request": original}

        # Stand down when the analyst already named an identifier.
        #
        # EXP-2026-09-021 Step 4 split the stage's effect by this exact
        # condition: with an identifier present it broke 32 answers and fixed
        # 10; with none it fixed 44 and broke 7. Canonicalising rewrites the
        # question into the source card's vocabulary, which is what the stage is
        # for -- but an identifier is the strongest routing signal the template
        # ladder has, and rendering it away costs more than the canonical form
        # returns. The predicate delegates to the resolver's own `_native_ids`
        # rather than matching identifiers here, for the reason `_ids_in`
        # records: a second opinion about what an identifier is, is the one
        # thing this design exists not to have.
        if config.rewrite_only_without_identifier:
            from utils.planner.canonical import _ids_in

            cited = sorted(
                {i for dataset in cards for i in _ids_in(original, dataset)}
            )
            if cited:
                logger.info("rewrite stood down: question cites %s", cited)
                return {
                    "rewrite_trace": {"rung": RUNG_SKIPPED_ID, "identifiers": cited},
                    "original_request": original,
                }

        # Imported here rather than at module scope: the canonical module pulls
        # in the name index and the schema registry, and the flag is off by
        # default, so a run that never rewrites should never pay for them.
        from utils.planner.canonical import (
            SLOT_ANCHORS, FormError, deterministic_fill, render,
        )

        form = deterministic_fill(
            original, cards, state.get("intent"),
            anchor_first=bool(getattr(config, "anchor_before_routing", False)),
        )
        trace: dict[str, Any] = {
            "rung": RUNG_DETERMINISTIC,
            "cache_hit": False,
            "served_model": "",
            "unbound": list(form.unbound),
            "sources": dict(form.sources),
        }

        # Never let the model choose the entity.
        #
        # `deterministic_fill` binds an anchor from an identifier or a complete
        # name and refuses to guess: EXP-2026-08-020 measured the ranked name
        # index's accept decision at 68% precision, so a slot it would have
        # filled is left unbound on purpose. The model rung then fills it from a
        # candidate list -- and AMENDMENT A-1 measured what that costs. At T3,
        # where the exact name is present, the anchor is an `exact-name` bind 64
        # times of 101. At T4/T5, where it is not, the model picks 82 and 88
        # times of 104 and `wrong_entity` roughly triples against baseline.
        #
        # So the rung is allowed to fill relation, direction, mode and target
        # labels -- schema facts, recoverable from the label pair -- and never
        # the anchor. Without a resolved anchor there is no question to
        # canonicalise, only a guess to dress up, and the analyst's own words
        # are the safer thing to forward.
        if config.rewrite_require_resolved_anchor and (
            trace["sources"].get(SLOT_ANCHORS) not in _EXACT_ANCHOR_SOURCES
        ):
            trace["rung"] = RUNG_SKIPPED_ANCHOR
            trace.setdefault("rejected", []).append(
                "anchor not bound by an exact lookup: "
                f"{trace['sources'].get(SLOT_ANCHORS)!r}"
            )
            return {"rewrite_trace": trace, "original_request": original,
                    "intent_form": form.to_dict()}

        if not form.is_bound and config.rewrite_model_enabled:
            from utils.planner import rewrite_llm

            form, model_trace = rewrite_llm.fill(
                original, form, cards, config.llm_settings(),
                cache=rewrite_llm.RewriteCache(config.rewrite_cache_dir),
            )
            trace.update(model_trace)
            trace["unbound"] = list(form.unbound)
            trace["sources"] = dict(form.sources)

        if not form.is_bound:
            trace["rung"] = RUNG_ABSTAIN
            trace.setdefault("rejected", []).append(
                f"slots still unbound: {list(form.unbound)}"
            )
            return {
                "rewrite_trace": trace, "original_request": original,
                "intent_form": form.to_dict(),
            }

        try:
            canonical = render(form, cards)
        except FormError as exc:
            trace["rung"] = RUNG_ABSTAIN
            trace.setdefault("rejected", []).append(f"could not render: {exc}")
            return {
                "rewrite_trace": trace, "original_request": original,
                "intent_form": form.to_dict(),
            }

        logger.info("rewrote via %s: %s", trace["rung"], canonical)
        update: dict[str, Any] = {
            "request": canonical,
            "canonical_question": canonical,
            "original_request": original,
            "intent_form": form.to_dict(),
            "rewrite_trace": trace,
        }

        # Execute the form, do not re-parse its rendering.
        #
        # EXP-2026-09-021 Step 4 measured the render round trip breaking 13 T1
        # answers whose form held the right identifier and the schema-resolved
        # relation; EXP-2026-09-023 measured three more on the sealed bank. A
        # form already *is* a sub-question -- anchor, label, relation, target
        # labels, source -- so under the flag the plan is built from it directly
        # and the drafter is bypassed on the first iteration. The gate still
        # judges it; a rejected form plan falls back to drafting the rendered
        # sentence, exactly as before.
        if getattr(config, "form_execute", False):
            from utils.planner.form_plan import plan_from_form

            form_plan = plan_from_form(form, cards, original)
            if form_plan is not None:
                trace["executed"] = "form"
                update["form_plan"] = form_plan
            else:
                trace["executed"] = "render"
        return update

    def draft(state: PlanningState) -> dict[str, Any]:
        iteration = int(state.get("iteration") or 0) + 1
        form_plan = state.get("form_plan")
        if form_plan is not None and iteration == 1:
            # The bound form's own plan, on the first pass only: if the gate
            # rejects it, the next iteration drafts from the rendered request.
            return {"iteration": iteration, "last_plan": form_plan, "drafter_used": "form"}
        plan = drafter.draft(
            state["request"], cards, state["live_view"], state.get("feedback"),
            state.get("intent"),
        )
        drafter_used = getattr(drafter, "last_used", "") or type(drafter).__name__
        return {"iteration": iteration, "last_plan": plan, "drafter_used": drafter_used}

    def gate(state: PlanningState) -> dict[str, Any]:
        plan = state["last_plan"]
        result = evaluate(plan, cards, state["live_view"])
        entry = {
            "iteration": state["iteration"],
            "drafter": state["drafter_used"],
            "gate_ok": result.ok,
            "reasons": list(result.reasons),
            "sub_questions": len(plan.sub_questions),
            "unsupported": len(plan.unsupported),
        }
        update: dict[str, Any] = {"gate_ok": result.ok, "trace": [entry]}
        if not result.ok:
            logger.info(
                "iteration %d rejected (%d reason(s)); revising",
                state["iteration"], len(result.reasons),
            )
            update["feedback"] = list(result.reasons)
        return update

    def finalize(state: PlanningState) -> dict[str, Any]:
        plan = state["last_plan"]
        logger.info(
            "plan converged on iteration %d (%s)", state["iteration"], state["drafter_used"]
        )
        plan.trace = list(state["trace"])
        plan.intent = state.get("intent")  # carry the classified intent onto the plan
        plan.rewrite = _provenance(state)
        return {"plan": plan}

    def degrade(state: PlanningState) -> dict[str, Any]:
        logger.info("max iterations reached; degrading to partial plan")
        plan = degrade_to_partial(
            state.get("last_plan"),
            state["request"],
            state["live_view"],
            list(state.get("feedback") or []),
            list(state["trace"]),
            cards=cards,
            max_iterations=max_iterations,
        )
        plan.intent = state.get("intent")  # even a degraded plan reports its intent
        plan.rewrite = _provenance(state)
        return {"plan": plan}

    def route_after_gate(state: PlanningState) -> str:
        if state["gate_ok"]:
            return "finalize"
        if state["iteration"] < max_iterations:
            return "draft"
        return "degrade"

    return {
        "classify": classify,
        "canonicalize": canonicalize,
        "draft": draft,
        "gate": gate,
        "finalize": finalize,
        "degrade": degrade,
        "route_after_gate": route_after_gate,
    }


def _provenance(state: PlanningState) -> dict[str, Any] | None:
    """The rewrite block for the plan, or ``None`` when the stage never ran.

    ``None`` rather than ``{"rung": "off"}`` for a run with the flag off, because
    ``Plan.to_dict`` omits the key entirely then — and a plan JSON that gains a
    field is a plan JSON that no longer matches the captured baselines. The
    distinction the record needs is between a stage that ran and declined and a
    stage that was not there, and that is what ``rung`` carries when it *is*
    present.
    """
    trace = state.get("rewrite_trace")
    if not trace or trace.get("rung") == RUNG_OFF:
        return None
    block = {k: v for k, v in trace.items() if v not in ((), [], {}, None, "")}
    block["rung"] = trace.get("rung", RUNG_OFF)
    original = state.get("original_request")
    canonical = state.get("canonical_question")
    if original:
        block["original_question"] = original
    if canonical:
        block["canonical_question"] = canonical
    if state.get("intent_form"):
        block["form"] = state["intent_form"]
    return block
