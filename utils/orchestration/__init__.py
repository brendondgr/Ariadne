"""LangGraph orchestration for the federated Q/A pipeline.

This package hosts the LangGraph ``StateGraph`` wiring that composes the
existing domain logic — planner (``utils/planner``), source specialists
(``utils/specialists``), and synthesis (``utils/synthesis``) — into the
analyst-question workflow:

    probe → plan → [sequenced specialists] → bundle → synthesize → done

Layout (per ``docs/skills/repository-structure/structures/langgraph.md``):

* ``state.py`` — shared graph state schemas over the existing contracts
* ``config.py`` — ``OrchestrationConfig`` (``ORCH_*`` env knobs)
* ``agents/planner`` — draft → gate → revise/degrade subgraph
* ``agents/specialists`` — dependency-ordered specialist execution subgraph
* ``agents/synthesis`` — compose → narrate → verify subgraph
* ``main.py`` — the top-level super-graph and its streaming entry points

The domain logic itself is *not* re-implemented here: nodes wrap the same
drafters, gate, ``QuerySpecialist``, federation bundling, and
composer/narrator/verifier the rest of the repo tests. Public facades
(``PlanningAgent.plan``, ``iter_pipeline``, ``synthesize``) delegate to these
graphs so their contracts stay stable.
"""
