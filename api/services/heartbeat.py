"""Keep a long-lived SSE stream provably alive while a stage is silent.

The pipeline is a *blocking* iterator: `next()` sits inside a planner, specialist
or synthesis LLM call for as long as that call takes, and nothing can be written
to the socket in the meantime. Measured over 12 concurrent questions against a
local endpoint, 5 of 12 runs went quiet for more than 90 s — the longest for
429 s — and the gap almost always followed ``status(planning)``.

That matters because the browser cannot tell a working run from a dead one by
looking at a silent socket, so ``web/lib/api.ts`` cancels any stream idle past
``SSE_STALL_MS`` (90 s). The run was fine; the client gave up on it. Roughly
half of all LLM-drafter questions died that way, always on the line the analyst
was last shown.

So the stream says something while it waits. :func:`with_heartbeat` drains the
pipeline on a worker thread and yields a keep-alive whenever the queue is idle
past ``interval_s``, which turns the client's watchdog back into what it was
meant to be — a check that the *connection* is alive, not a guess at how long a
model may think.

**The keep-alive is an SSE comment, not an event.** A comment frame resets the
reader's inactivity timer exactly like data does, and ``parseSseFrame`` drops it
(no ``data:`` line ⇒ ``None``), so the typed event union in ``web/lib/types.ts``,
the run machine, and every recorded fixture stay byte-identical. A new named
event would have meant touching all of them to say nothing.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Iterable, Iterator

from utils.config import env_str

logger = logging.getLogger("ariadne.api.heartbeat")

#: Comfortably inside the client's 90 s budget and inside ``SSE_SLOW_MS`` (25 s),
#: so a lowered client threshold does not immediately start failing runs.
DEFAULT_INTERVAL_S = 10.0

#: Operator override, read per call rather than at import so a value can be
#: changed (or a test can shorten it) without reloading the module.
INTERVAL_ENV_VAR = "SSE_HEARTBEAT_INTERVAL_S"


def heartbeat_interval_s() -> float:
    """The keep-alive period, from the environment with the default as fallback."""
    try:
        value = float(env_str(INTERVAL_ENV_VAR, ""))
    except ValueError:
        return DEFAULT_INTERVAL_S
    return value if value > 0 else DEFAULT_INTERVAL_S

#: Yielded in place of a real item when the producer has been quiet. The caller
#: turns it into whatever its own wire format wants.
HEARTBEAT = object()


def with_heartbeat(
    source: Iterable[Any],
    *,
    interval_s: float | None = None,
) -> Iterator[Any]:
    """Yield everything ``source`` yields, plus :data:`HEARTBEAT` while it is quiet.

    Order and content are preserved exactly — heartbeats are only ever inserted
    *between* items, never in place of one, and an exception raised by ``source``
    is re-raised here on the consuming thread so existing ``except`` blocks around
    the stream keep working.

    The producer thread is a daemon: a consumer that stops early (the client
    disconnected) leaves it to finish into a queue nobody reads rather than
    holding up interpreter shutdown, which is the same trade
    ``utils/planner/discovery.py`` makes for its probes.
    """
    period = heartbeat_interval_s() if interval_s is None else interval_s
    items: queue.Queue[tuple[str, Any]] = queue.Queue()

    def produce() -> None:
        try:
            for item in source:
                items.put(("item", item))
        except BaseException as exc:  # noqa: BLE001 - re-raised on the consumer
            items.put(("error", exc))
            return
        items.put(("done", None))

    worker = threading.Thread(target=produce, daemon=True, name="sse-heartbeat")
    worker.start()

    while True:
        try:
            kind, payload = items.get(timeout=period)
        except queue.Empty:
            yield HEARTBEAT
            continue
        if kind == "item":
            yield payload
        elif kind == "error":
            raise payload  # type: ignore[misc]
        else:
            return
