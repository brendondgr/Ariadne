"""The three in-context examples, the same questions in both languages.

Drawn from CypherBench's *training* split on ``terrorist_attack`` (a training
graph, loaded alongside the test graphs only so these examples can be checked).
The Cypher is CypherBench's gold; the Gremlin is hand-written and verified to
return the same normalised records (``tests/test_t1.py``).
"""

SHOTS = [
    {
        "question": "What are the names and dates of terrorist attacks carried out by Oussama Zariouh?",
        "cypher": "MATCH (n:TerroristAttack)-[r0:perpetratedBy]->(m0:Terrorist {name: 'Oussama Zariouh'}) "
                  "WITH DISTINCT n RETURN n.name, n.date",
        "gremlin": "g.V().has('Terrorist', 'name', 'Oussama Zariouh').in('perpetratedBy').hasLabel('TerroristAttack')"
                   ".dedup().project('name', 'date').by('name').by(coalesce(values('date'), constant(null)))",
    },
    {
        "question": "What are the names of targets in Iraq that have been attacked by terrorists, and how many such "
                    "attacks have occurred for each target?",
        "cypher": "MATCH (n:Target)<-[r0:targets]-(m0:TerroristAttack)-[r1:occursIn]->(m1:Country {name: 'Iraq'}) "
                  "WITH n, count(DISTINCT m0) AS num RETURN n.name, num",
        "gremlin": "g.V().hasLabel('Target').project('name', 'num').by('name')"
                   ".by(__.in('targets').hasLabel('TerroristAttack').where(out('occursIn').has('Country', 'name', 'Iraq'))"
                   ".dedup().count()).where(select('num').is(gt(0)))",
    },
    {
        "question": "How many more deaths occurred in the 2002 Immanuel bus attack compared to the Droppin Well bombing?",
        "cypher": "MATCH (n:TerroristAttack {name: '2002 Immanuel bus attack'}), (m0:TerroristAttack {name: 'Droppin Well "
                  "bombing'}) RETURN n.number_of_deaths - m0.number_of_deaths AS answer",
        "gremlin": "g.V().has('TerroristAttack', 'name', '2002 Immanuel bus attack').values('number_of_deaths').as('a')"
                   ".V().has('TerroristAttack', 'name', 'Droppin Well bombing').values('number_of_deaths').as('b')"
                   ".math('a - b')",
    },
]
