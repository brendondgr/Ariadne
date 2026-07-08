#!/usr/bin/env python3
"""Conversational agents wrapping the existing pipeline.

* ``router`` — the redirect agent (quick vs graph).
* ``answer`` — the final conversational reply (memory-grounded on the quick path).
* ``graph_extraction`` — wraps ``utils.orchestration`` as a subgraph (Step 4).
* ``validation`` — the bounded sufficiency-retry gate (Step 4).
"""
