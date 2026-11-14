"""The typed arm for kill test T1: typed requests compiled to Cypher and to Gremlin.

The model never writes a query. It fills in a typed request (``request.py``)
whose every label, relationship and property must come from the graph's card,
and two compilers (``cypher.py``, ``gremlin.py``) turn the same request into each
backend's query. See ``request.py`` for the format and its semantics.
"""
