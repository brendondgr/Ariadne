"""Adversarial gate probes — drafts crafted to tempt a write or unbounded scan.

Each probe is a raw query the pre-run gate MUST reject. They are fed straight to
the validator (no builder), so they test the gate's last line of defence against
a query the builder would never emit but a future LLM builder might. A probe
that is NOT blocked is a hard safety failure, not a rate.

Note: a *missing* LIMIT is deliberately absent here — the gate injects a cap for
that rather than rejecting, so it is audited (score_safety) not probed.
"""

from __future__ import annotations

# (name, query, why-it-must-be-blocked)
ATTACK_PROBES = [
    ("write_create", "MATCH (t:Technique) CREATE (e:Evil) RETURN t", "write clause CREATE"),
    ("write_detach_delete", "MATCH (t:Technique) DETACH DELETE t", "write clause DETACH DELETE"),
    ("write_set", "MATCH (t:Technique) SET t.owned = true RETURN t", "write clause SET"),
    ("write_merge", "MERGE (t:Technique {attack_id:'T1'}) RETURN t", "write clause MERGE"),
    ("call_subquery", "MATCH (t:Technique) CALL { CREATE (x) } RETURN t", "CALL { } subquery"),
    ("load_csv", "LOAD CSV FROM 'file:///etc/passwd' AS r RETURN r", "LOAD CSV"),
    ("unbounded_varlen", "MATCH (t:Technique)-[:MITIGATES*]-(m) RETURN m", "unbounded variable-length path"),
    ("over_depth_varlen", "MATCH (t:Technique)-[:MITIGATES*1..9]-(m) RETURN m", "var-length path over depth cap"),
    ("unknown_label", "MATCH (x:Secret) RETURN x", "label not in the card schema"),
    ("no_match", "RETURN 1", "not a MATCH...RETURN read"),
]

GREMLIN_PROBES = [
    ("write_addv", "g.addV('Evil')", "write step addV"),
    ("write_adde", "g.V().addE('pwn')", "write step addE"),
    ("write_drop", "g.V().drop()", "write step drop"),
    ("write_property", "g.V().property('owned', true)", "write step property"),
    ("over_depth", "g.V().out('MAPS_TO').out('MAPS_TO').out('MAPS_TO').out('MAPS_TO')", "traversal over depth cap"),
    ("unknown_label", "g.V().hasLabel('Secret')", "label not in the card schema"),
    ("not_traversal", "g.addE('x')", "does not start g.V( / g.E("),
]

# The 17 hand-written probes above are kept verbatim: they are the historical
# suite every prior C-008 figure was measured against, and one of them found the
# only bypass this project has had. The generated suite below multiplies coverage
# by crossing each rejection category with syntactic mutations the hand-written
# set never tried — case, comment, subquery and union placement.
from utils.specialists.tests.fixtures.probe_generator import (  # noqa: E402
    generated_probes,
)

HAND_WRITTEN = {"attack": ATTACK_PROBES, "capec": GREMLIN_PROBES}

_GENERATED = generated_probes()

#: Hand-written first so a leak in the historical suite is unmissable, then the
#: generated ones. Names are unique across both by construction.
PROBES = {
    source: list(HAND_WRITTEN[source]) + list(_GENERATED.get(source, []))
    for source in HAND_WRITTEN
}
