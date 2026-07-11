# Iterative Retrieval Loop

A bounded evidence-gathering cycle between the specialists and synthesis. Before
this, the pipeline was plan-once-then-execute: the planner fixed every
sub-question up front and synthesis was terminal, so a question whose next step
only becomes reachable *after* seeing intermediate results could not be fully
answered. The loop closes that gap: an **`assess`** node judges whether the
accumulated evidence answers the question and, if not, feeds what was discovered
back into a **re-plan** that emits only the *missing* sub-questions, runs them
through the same specialists, and repeats — under a hard hop cap.

It does **not** change the query-safety model. Specialists still fill read-only
templates through the existing gates; only the *set* of queries becomes dynamic.

## The cycle

```
check_cards → probe → plan → announce_querying → specialists → bundle → assess ─┐
                                        ▲                                        │
                                        │              sufficient / hop-capped   ▼
                                        └───────── replan ◀── insufficient ── (route)
                                                     │                          │
                                                     └── nothing new ──────────▶ synthesize → END
```

* **`assess`** (`utils/orchestration/agents/assess/`) runs after `bundle`, folds
  the hop's evidence delta into `frontier`/`visited`, and writes an
  `Assessment` verdict.
* **`route_sufficiency`** sends the run to `synthesize` when sufficient (or
  hop-capped) and to `replan` otherwise.
* **`replan`** grafts the next hop's expansion onto the plan and bumps `hop`.
  `route_after_replan` re-enters the specialists only if new sub-questions were
  added; otherwise it goes straight to `synthesize` (the "nothing left to chase"
  terminal case).

The specialist subgraph is unchanged: `cursor` is left where the previous hop
stopped, and because `execution_order` keeps appended sub-questions after the
originals, re-entering the loop runs **only** the newly added sub-questions,
seeded from their already-run producers via the existing declared-join
machinery.

## Sufficiency policy

Default judge is **deterministic** (keeps the LLM-off build byte-reproducible).
Evidence is *sufficient* when there is nothing left to **productively chase**:

> A join key is *chaseable* when a producer source surfaced it, it has not yet
> resolved across sources, and the consumer side of its declared join has not
> been queried yet. Sufficient ⇔ no chaseable frontier.

This subsumes the intent of "every declared join resolved **and** novelty
exhausted": the loop keeps going exactly while an unresolved join-key can still
be carried into a not-yet-queried source, and stops — synthesizing with what it
has — the moment that chase is dry, whether the join closed or simply cannot.
The assess predicate and `PlanningAgent.replan` share this rule, so the loop
re-plans *iff* there is real work to do: no wasted cycles, guaranteed
convergence.

* **No declared join** → sufficient in one pass (nothing to chase).
* **Hop cap** (`ORCH_MAX_HOPS`) is the hard backstop: at `hop >= max_hops` the
  verdict is *forced* `sufficient` (`hop_capped=True`), so the loop always
  terminates even if the predicate never converges.

### First-cut expansion strategy

Re-planning is deterministic **cross-source join-key chasing**: for each declared
canonical join, take the values a producer surfaced but that have not resolved,
and — when the consumer source has not been queried and is live — emit a consumer
sub-question plus the join declaration that seeds it from the producer's
harvested join values. Relevance-scored neighbour/relation expansion
(Think-on-Graph style within a source) is the documented follow-on, not part of
this cut. Re-planned sub-questions are de-duplicated against the answered set on
`(source, sorted(entities), normalized_text)` and tagged with their `hop`.

## Optional LLM critic

`ORCH_ASSESS_MODE=llm` opts into an LLM "what's missing" critic that refines the
deterministic verdict. It is injected and, per the standing fallback policy, any
failure — LLM off, endpoint down, malformed reply — degrades cleanly to the
deterministic judge with the fallback recorded in `Assessment.mode`
(`"deterministic (llm fallback)"`). The default (`deterministic`) never calls an
LLM.

## Configuration

| Env var | Default | Meaning |
| --- | --- | --- |
| `ORCH_MAX_HOPS` | `5` | Hard cap on assess → re-plan → specialists iterations. `1` forces the historical strict single pass. Values `< 1` clamp to the default. |
| `ORCH_ASSESS_MODE` | `deterministic` | `deterministic` (reproducible) or `llm` (opt-in critic with deterministic fallback). Unknown values fall back to `deterministic`. |

The loop shares the triple termination guard: `ORCH_MAX_HOPS`, the
`PIPELINE_TIMEOUT_S` deadline (specialists skip past-deadline sub-questions), and
`recursion_limit=200`.

## Streaming & inspectability

When the loop is enabled (`max_hops > 1`) the `assess` node emits an `assess`
stream event carrying the verdict, hop, and cap; the re-plan emits a
`status(planning, hop=N)` frame. The SSE layer renders both, and the web run
state folds the latest `assessment` and `hop` onto the accumulator. At
`ORCH_MAX_HOPS=1` no loop events are emitted and the event stream is
byte-identical to the pre-loop contract.

## Reproducibility

The default was flipped from `1` to `5` only after confirming the end-to-end
evaluation is **byte-identical** at `ORCH_MAX_HOPS` 1 vs 5 across the committed
golden catalogue: those questions are well-formed federated plans that already
close their joins in a single pass, so the extra hops add internal assess/replan
bookkeeping but no new evidence. Multi-hop behaviour (an under-routed first pass
that the loop completes) is proven hermetically in
`utils/orchestration/tests/test_iterative_loop.py`.

## Key files

| Concern | Location |
| --- | --- |
| Loop config knobs | `utils/orchestration/config.py` |
| Loop state envelope (`hop`/`frontier`/`visited`/`assessment`) | `utils/orchestration/state.py` |
| Frontier/visited extraction | `utils/orchestration/agents/assess/frontier.py` |
| Assess node + sufficiency policy + `Assessment` | `utils/orchestration/agents/assess/{node,policy,contracts}.py` |
| Re-plan entry + merge/dedupe + `SubQuestion.hop` | `utils/planner/agent.py`, `utils/planner/schema.py` |
| Loop wiring in the super-graph | `utils/orchestration/main.py` |
| Tests | `utils/orchestration/agents/assess/tests/`, `utils/orchestration/tests/test_iterative_loop.py`, `utils/planner/tests/test_replan_dedup.py` |
