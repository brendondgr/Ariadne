"""Kill tests for the era-2 candidate mechanisms (EXP-2026-11-001..003).

Three small, pre-registered experiments, each with a numeric kill rule written
before it runs:

- ``t1`` — free Cypher vs free Gremlin on CypherBench graphs mirrored into Gremlin;
- ``t2`` — the answer-invariance gate: run every card-valid interpretation, answer
  only when they agree;
- ``t3`` — label-free calibration: abstention thresholds set on card-generated
  questions, applied unchanged to real ones.

Every stage is resumable (``stages.py``), writes a heartbeat (``heartbeat.py``)
and stamps its outputs with provenance (``provenance.py``).
"""
