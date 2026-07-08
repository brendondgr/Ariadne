"""The Ariadne workbench launcher (``python app.py``).

The launcher is the workbench's works-the-first-time gate. Instead of
blind-spawning uvicorn and ``npm run dev`` and hoping, it:

* **preflights** every dependency the LangGraph pipeline needs
  (``preflight.py``) — toolchain, ports, source cards, live graph backends,
  the LLM endpoint, and a compile of the orchestration super-graph — each
  check reporting pass/warn/fail with a concrete remediation command;
* **streams** both child processes' output with source prefixes and shows an
  honest status board of every subsystem (``display.py``);
* **gates readiness** on real probes — the API's ``/api/health`` and the web
  port serving — before declaring the stack up (``supervise.py``);
* **proves the pipeline** end-to-end with a startup smoke query streamed over
  the same SSE contract the UI uses (``smoke.py``).

Hard failures (ports, toolchain, graph compilation) abort with the failing
check named; degraded-but-survivable subsystems (graph backends, LLM) warn
with remediation and the stack starts anyway — the UI renders Live/Dead
pills and the planner degrades honestly.
"""
