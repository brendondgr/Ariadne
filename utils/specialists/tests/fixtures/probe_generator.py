#!/usr/bin/env python3
"""Adversarial gate probes, generated rather than hand-written.

C-008 rests on 17 hand-written probes, and the suite that produced them also
found the one bypass that was then fixed — so it partly grades against its own
answer key. Seventeen cases is weak evidence for "blocks adversarial probes
without leakage" however clean the rate looks.

This generates several hundred by crossing each **rejection category** with a
set of **syntactic mutations**, so the gate is tested against the same intent
expressed many ways rather than against one phrasing per intent. The mutations
are the part that matters: a gate that greps for `CREATE` and misses `cReAtE`,
or one that checks the first keyword and misses a write after a line comment, is
exactly the failure a hand-written suite does not find.

**Every generated probe must be something the gate is required to reject**, and
the categories are chosen for that:

* write clauses and steps — read-only is the whole property
* labels and relationship types outside the declared card schema
* unbounded and over-depth traversal
* shapes that are not a bounded read at all (procedure calls, bare RETURN)
* Groovy/Cypher injection through a parameter slot

**Deliberately excluded, because the gate is specified to *repair* rather than
reject them:** a missing `LIMIT` (injected) and an over-cap `LIMIT` (clamped).
Probing those would manufacture leaks that are correct behaviour — the trap this
module exists to avoid, and the reason the hand-written suite left the
missing-LIMIT case to the adherence audit instead.

Generation is deterministic: no randomness, stable ordering, so the suite is a
fixture and a leak reproduces exactly.
"""

from __future__ import annotations

# --- Cypher ----------------------------------------------------------------

#: Write clauses the card's safety block disallows. Each is planted into a
#: query that is otherwise a perfectly ordinary read.
_CYPHER_WRITES = (
    "CREATE (e:Evil)",
    "MERGE (e:Evil {id:'x'})",
    "DELETE t",
    "DETACH DELETE t",
    "SET t.owned = true",
    "REMOVE t.name",
    "DROP INDEX idx",
    "FOREACH (x IN [1] | SET t.owned = true)",
)

#: Where a write can hide. A gate that only inspects the leading keyword, or
#: only the first line, fails on the later ones.
_CYPHER_PLACEMENTS = (
    ("head", "MATCH (t:Technique) {write} RETURN t LIMIT 10"),
    ("after_with", "MATCH (t:Technique) WITH t LIMIT 10 {write} RETURN t"),
    ("after_line_comment", "MATCH (t:Technique) // harmless\n{write} RETURN t LIMIT 10"),
    ("after_block_comment", "MATCH (t:Technique) /* harmless */ {write} RETURN t LIMIT 10"),
    ("in_union", "MATCH (t:Technique) RETURN t LIMIT 10 UNION {write} RETURN t LIMIT 10"),
    ("in_subquery", "MATCH (t:Technique) CALL {{ WITH t {write} RETURN t AS x }} RETURN x LIMIT 10"),
)

#: Case mutations. A keyword matcher that is not case-insensitive fails these.
_CASE_MUTATIONS = (
    ("upper", str.upper),
    ("lower", str.lower),
    ("mixed", lambda s: "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(s))),
)

#: Labels no source card declares.
_UNKNOWN_LABELS = ("Secret", "User", "Password", "InternalOnly", "AdminAccount")

#: Traversals with no upper bound, or one past the depth cap of 3.
_CYPHER_PATHS = (
    ("unbounded", "MATCH (t:Technique)-[:MITIGATES*]-(m) RETURN m LIMIT 10"),
    ("unbounded_lower", "MATCH (t:Technique)-[:MITIGATES*2..]-(m) RETURN m LIMIT 10"),
    ("over_depth_4", "MATCH (t:Technique)-[:MITIGATES*1..4]-(m) RETURN m LIMIT 10"),
    ("over_depth_9", "MATCH (t:Technique)-[:MITIGATES*1..9]-(m) RETURN m LIMIT 10"),
    ("over_depth_99", "MATCH (t:Technique)-[:MITIGATES*..99]-(m) RETURN m LIMIT 10"),
    ("chained_over_depth",
     "MATCH (a:Technique)-[:MITIGATES]-(b)-[:MITIGATES]-(c)-[:MITIGATES]-(d)-[:MITIGATES]-(e) "
     "RETURN e LIMIT 10"),
)

#: Shapes that are not a bounded read of the declared graph at all.
_CYPHER_NOT_A_READ = (
    ("bare_return", "RETURN 1"),
    ("call_dbms", "CALL dbms.components() YIELD name RETURN name LIMIT 10"),
    ("call_apoc", "CALL apoc.cypher.doIt('CREATE (e:Evil)', {}) YIELD value RETURN value"),
    ("call_db_labels", "CALL db.labels() YIELD label RETURN label LIMIT 10"),
    ("show_databases", "SHOW DATABASES"),
    ("load_csv", "LOAD CSV FROM 'file:///etc/passwd' AS r RETURN r LIMIT 10"),
    ("load_csv_headers",
     "LOAD CSV WITH HEADERS FROM 'http://evil.test/x.csv' AS r RETURN r LIMIT 10"),
    ("profile_write", "PROFILE MATCH (t:Technique) SET t.owned = true RETURN t LIMIT 10"),
    ("explain_write", "EXPLAIN MATCH (t:Technique) DELETE t"),
    ("use_other_db", "USE system MATCH (t) RETURN t LIMIT 10"),
)

#: Injection through a parameter slot. The seed is attacker-controlled text, so a
#: builder that interpolates instead of binding produces exactly these.
_CYPHER_INJECTIONS = (
    ("statement_split", "MATCH (n:Technique) RETURN n LIMIT 10; CREATE (e:Evil)"),
    ("backtick_label", "MATCH (n:`Technique` ) WITH n MATCH (x:`Secret`) RETURN x LIMIT 10"),
    ("label_injection", "MATCH (n:Technique:Secret) RETURN n LIMIT 10"),
)

#: **Not probes.** Queries the gate accepts and *should* accept: each is a
#: read-only, row-capped read over a declared label. They were written as probes
#: and the gate "leaked" all of them, which was a defect in the probe suite, not
#: in the gate — the mistake this module's docstring warns about, made anyway.
#:
#: They are kept, and exercised by a test asserting the gate accepts them,
#: because they document the gate's *scope boundary*: it enforces structural
#: safety — read-only, bounded, declared schema — and does not attempt semantic
#: intent. A tautological `OR '1'='1'` returns rows the analyst was entitled to
#: read anyway. The risk they gesture at is a builder interpolating attacker text
#: instead of binding a parameter, and that is a different layer with a different
#: control (no LLM writes a query here at all, C-012).
CYPHER_ACCEPTED_BY_DESIGN = (
    ("tautology", "MATCH (n:Technique) WHERE n.attack_id = 'T1' OR '1'='1' RETURN n LIMIT 10",
     "read-only, bounded, declared label — a tautology is not a safety breach"),
    ("comment_terminator", "MATCH (n:Technique) WHERE n.attack_id = 'T1' // ' RETURN n",
     "the comment truncates to a legal read; the row cap is then injected"),
)


def cypher_probes() -> list[tuple[str, str, str]]:
    """(name, query, why) triples the Cypher gate must reject."""
    out: list[tuple[str, str, str]] = []

    for write in _CYPHER_WRITES:
        keyword = write.split()[0].split("(")[0]
        for place_name, shape in _CYPHER_PLACEMENTS:
            out.append((
                f"write_{keyword.lower()}_{place_name}",
                shape.format(write=write),
                f"write clause {keyword} in position {place_name}",
            ))
            for case_name, fn in _CASE_MUTATIONS:
                if fn(keyword) == keyword:
                    continue  # no mutation, no extra coverage
                mutated = write.replace(keyword, fn(keyword), 1)
                out.append((
                    f"write_{keyword.lower()}_{place_name}_{case_name}",
                    shape.format(write=mutated),
                    f"write clause {keyword} ({case_name} case) in position {place_name}",
                ))

    for label in _UNKNOWN_LABELS:
        out.append((
            f"unknown_label_{label.lower()}",
            f"MATCH (x:{label}) RETURN x LIMIT 10",
            f"label {label} is not in the card schema",
        ))
        out.append((
            f"unknown_label_{label.lower()}_joined",
            f"MATCH (t:Technique)-[:MITIGATES]-(x:{label}) RETURN x LIMIT 10",
            f"label {label} is not in the card schema, reached through a legal one",
        ))

    out.extend(
        (f"path_{name}", query, "traversal is unbounded or past the depth cap")
        for name, query in _CYPHER_PATHS
    )
    out.extend(
        (f"shape_{name}", query, "not a bounded read of the declared graph")
        for name, query in _CYPHER_NOT_A_READ
    )
    out.extend(
        (f"inject_{name}", query, "parameter-slot injection")
        for name, query in _CYPHER_INJECTIONS
    )
    return out


# --- Gremlin ---------------------------------------------------------------

_GREMLIN_WRITES = (
    ".addV('Evil')",
    ".addE('pwn')",
    ".drop()",
    ".property('owned', true)",
    ".mergeV([:])",
    ".mergeE([:])",
)

_GREMLIN_PLACEMENTS = (
    ("head", "g{write}.limit(10)"),
    ("after_haslabel", 'g.V().hasLabel("AttackPattern"){write}.limit(10)'),
    ("after_filter", 'g.V().has("id", "capec:attack-pattern:66"){write}.limit(10)'),
    ("inside_sideeffect", 'g.V().hasLabel("AttackPattern").sideEffect(__{write}).limit(10)'),
    ("inside_union", 'g.V().hasLabel("AttackPattern").union(__.identity(), __{write}).limit(10)'),
)

_GREMLIN_UNKNOWN_LABELS = ("Secret", "User", "Credential", "InternalOnly")

_GREMLIN_PATHS = (
    ("repeat_unbounded", 'g.V().hasLabel("AttackPattern").repeat(__.out()).limit(10)'),
    ("repeat_over_depth",
     'g.V().hasLabel("AttackPattern").repeat(__.out()).times(9).limit(10)'),
    ("chained_over_depth",
     'g.V().hasLabel("AttackPattern").out("MAPS_TO").out("MAPS_TO")'
     '.out("MAPS_TO").out("MAPS_TO").limit(10)'),
    ("both_unbounded", 'g.V().hasLabel("AttackPattern").both().both().both().both().limit(10)'),
)

_GREMLIN_NOT_A_READ = (
    ("not_traversal", "g.addE('x')"),
    ("system_call", "System.exit(0)"),
    ("groovy_eval", "Eval.me('1+1')"),
    ("file_read", "new File('/etc/passwd').text"),
    ("no_g_start", 'V().hasLabel("AttackPattern").limit(10)'),
    ("graph_handle", 'graph.traversal().V().limit(10)'),
)

#: The escape class this project has already been bitten by: a raw backslash in
#: an inline Gremlin string is a Groovy syntax error, so a term must be
#: wildcard-sanitised rather than regex-escaped into a query.
_GREMLIN_INJECTIONS = (
    ("statement_split", 'g.V().limit(10); g.addV("Evil")'),
    ("closure_injection", 'g.V().filter{ it.get().value("id") != null }.limit(10)'),
)

#: **Not probes**, for the same reason as the Cypher list above.
GREMLIN_ACCEPTED_BY_DESIGN = (
    ("tautology", 'g.V().has("id", "x").or().has("id", "").limit(10)',
     "read-only and bounded; an always-true filter is not a breach"),
    ("backslash_escape", 'g.V().has("name", "a\\\\b").limit(10)',
     "read-only. A raw backslash is a Groovy *syntax* hazard the builder must "
     "avoid by wildcard-sanitising rather than regex-escaping, not something "
     "the safety gate is specified to reject"),
    ("string_concat", 'g.V().has("id", "a" + "b").limit(10)',
     "read-only and bounded; literal concatenation reaches no new data"),
)


def accepted_by_design() -> dict[str, tuple[tuple[str, str, str], ...]]:
    """(name, query, why) triples the gate is *correct* to accept."""
    return {"attack": CYPHER_ACCEPTED_BY_DESIGN, "capec": GREMLIN_ACCEPTED_BY_DESIGN}


def gremlin_probes() -> list[tuple[str, str, str]]:
    """(name, query, why) triples the Gremlin gate must reject."""
    out: list[tuple[str, str, str]] = []

    for write in _GREMLIN_WRITES:
        step = write.split("(")[0].lstrip(".")
        for place_name, shape in _GREMLIN_PLACEMENTS:
            out.append((
                f"write_{step.lower()}_{place_name}",
                shape.format(write=write),
                f"write step {step} in position {place_name}",
            ))

    for label in _GREMLIN_UNKNOWN_LABELS:
        out.append((
            f"unknown_label_{label.lower()}",
            f'g.V().hasLabel("{label}").limit(10)',
            f"label {label} is not in the card schema",
        ))
        out.append((
            f"unknown_label_{label.lower()}_joined",
            f'g.V().hasLabel("AttackPattern").out("MAPS_TO").hasLabel("{label}").limit(10)',
            f"label {label} is not in the card schema, reached through a legal one",
        ))

    out.extend(
        (f"path_{name}", query, "traversal is unbounded or past the depth cap")
        for name, query in _GREMLIN_PATHS
    )
    out.extend(
        (f"shape_{name}", query, "not a bounded traversal of the declared graph")
        for name, query in _GREMLIN_NOT_A_READ
    )
    out.extend(
        (f"inject_{name}", query, "parameter-slot injection")
        for name, query in _GREMLIN_INJECTIONS
    )
    return out


def generated_probes() -> dict[str, list[tuple[str, str, str]]]:
    """Every generated probe, keyed by source, in stable order."""
    return {"attack": cypher_probes(), "capec": gremlin_probes()}


if __name__ == "__main__":
    for source, probes in generated_probes().items():
        print(f"{source}: {len(probes)} probes")
