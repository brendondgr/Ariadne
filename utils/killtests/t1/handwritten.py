"""Thirty hand-written Gremlin translations of sampled test questions.

They exist to prove the mirror, not to score anything: if every one returns the
same normalised records as CypherBench's reference Cypher, then a model-written
Gremlin query that misses is the model's miss, not the mirror's. Keyed by the
first 8 characters of the CypherBench qid.
"""

NA = "constant(null)"

HANDWRITTEN = {
    # flight_accident
    "99313abe": "g.V().hasLabel('AircraftModel').values('name')",
    "f34ae1cf": "g.V().hasLabel('Airport').where(__.in('departsFrom').hasLabel('FlightAccident'))"
                f".project('name','location').by('name').by(coalesce(values('location'),{NA}))",
    "916f5e4c": "g.V().has('AircraftModel','name','Ford Trimotor').in('involves').hasLabel('FlightAccident')"
                ".out('destinedFor').hasLabel('Airport').dedup().values('name')",
    "79a90866": "g.V().has('FlightAccident','name','2015 Juba plane crash').out('involves').hasLabel('AircraftModel')"
                f".dedup().project('name','len').by('name').by(coalesce(values('length_metre'),{NA}))",
    "c5f302f2": "g.V().hasLabel('FlightAccident').where(out('operatedBy').has('Operator','name','Korean Air'))"
                ".where(out('destinedFor').has('Airport','name','Mactan–Cebu International Airport'))"
                f".dedup().project('name','date').by('name').by(coalesce(values('date'),{NA}))",
    "9d433b20": "g.V().hasLabel('Airport').as('n').where(__.in('departsFrom').hasLabel('FlightAccident')"
                ".out('destinedFor').where(eq('n'))).values('name')",
    "9af6d17e": f"g.V().has('FlightAccident','name','Emirates Flight 521').project('x').by(coalesce(values('number_of_injuries'),{NA}))",
    "821c6b82": "g.V().has('FlightAccident','name','Tatarstan Airlines Flight 363').values('number_of_injuries').as('a')"
                ".V().has('FlightAccident','name','Mandala Airlines Flight 091').values('number_of_injuries').as('b').math('a - b')",
    "d3359ea1": "g.V().has('AircraftManufacturer','name','Sukhoi').in('manufacturedBy').hasLabel('AircraftModel').dedup()"
                ".project('name','num').by('name').by(__.in('involves').hasLabel('FlightAccident').dedup().count())",
    "203c08d7": "g.V().hasLabel('Operator').project('name','num').by('name').by(__.in('operatedBy').hasLabel('FlightAccident')"
                ".where(out('involves').has('AircraftModel','name','Il-62')).dedup().count()).where(select('num').is(gt(0)))",
    "7eef8610": "g.V().hasLabel('FlightAccident').where(or(out('destinedFor').has('Airport','name','Gimpo International Airport'),"
                "out('involves').has('AircraftModel','name','Boeing 707'))).values('name')",
    "d40780b7": f"g.V().hasLabel('Airport').project('name','iata').by('name').by(coalesce(values('iata_code'),{NA}))",
    "11305436": "g.V().hasLabel('Airport').where(__.in('departsFrom').hasLabel('FlightAccident')).values('name')",
    "9ced4ba6": "g.V().has('Airport','name','Skopje International Airport').in('departsFrom').hasLabel('FlightAccident')"
                ".out('operatedBy').hasLabel('Operator').dedup().values('name')",
    "64cf4f37": "g.V().has('FlightAccident','name','Air Ontario Flight 1363').out('destinedFor').hasLabel('Airport').dedup().values('name')",
    # nba
    "7960644e": f"g.V().hasLabel('Player').project('g').by(coalesce(values('gender'),{NA})).select('g').dedup()",
    "15cc498b": "g.V().hasLabel('Player').where(out('draftedBy').hasLabel('Team')).values('name')",
    "896b0995": "g.V().has('Team','name','Toronto Raptors').in('playsFor').hasLabel('Player').out('playsPosition')"
                ".hasLabel('Position').dedup().values('name')",
    "66818788": "g.V().has('Conference','name','Eastern Conference').in('partOfConference').hasLabel('Division').dedup().values('name')",
    "8b7627b8": "g.V().hasLabel('Player').where(out('playsPosition').has('Position','name','center'))"
                ".where(out('draftedBy').has('Team','name','Atlanta Hawks')).values('name')",
    "d182fb58": "g.V().hasLabel('Team').as('n').where(__.in('draftedBy').hasLabel('Player').out('playsFor').where(eq('n')))"
                f".project('name','coach').by('name').by(coalesce(values('head_coach'),{NA}))",
    "0480c6db": f"g.V().has('Player','name','George Lehmann').project('d').by(coalesce(values('date_of_birth'),{NA}))",
    "99d50929": "g.V().has('Player','name','Skeeter Swift').as('n').V().has('Player','name','Lee Knorek').as('m')"
                ".choose(select('n').values('date_of_death').as('a').select('m').values('date_of_death').as('b')"
                ".where('a',gt('b')), select('n').values('name'), select('m').values('name'))",
    "b08c1bf4": "g.V().has('Team','name','Houston Rockets').in('playsFor').hasLabel('Player').dedup()"
                ".project('name','num').by('name').by(out('receivesAward').hasLabel('Award').dedup().count())",
    "d6badaed": "g.V().hasLabel('Award').project('name','num').by('name').by(__.in('receivesAward').hasLabel('Player')"
                ".where(out('playsPosition').has('Position','name','swingman')).dedup().count()).where(select('num').is(gt(0)))",
    "65b5ad24": "g.V().has('Team','name','Washington Wizards').inE('playsFor').has('start_year',lte(1964))"
                ".or(has('end_year',gte(1964)), hasNot('end_year')).outV().hasLabel('Player').dedup().values('name')",
    "26414c4a": "g.V().hasLabel('Player').where(or(out('receivesAward').has('Award','name',"
                "'NBA All-Star Game Kobe Bryant Most Valuable Player Award'),"
                "out('playsPosition').has('Position','name','power forward'))).values('name')",
    "254422cc": "g.V().hasLabel('Player').values('name')",
    "d332a07b": "g.V().has('Venue','name','Hy-Vee Arena').in('hasHomeVenue').hasLabel('Team').in('draftedBy')"
                ".hasLabel('Player').dedup().has('date_of_birth',lt('1950-01-22')).values('name')",
    "3b950840": "g.V().has('Award','name','Silbernes Lorbeerblatt').in('receivesAward').hasLabel('Player').dedup()"
                ".project('name','schools').by('name').by(choose(has('schools_attended'),"
                f"values('schools_attended').fold(), {NA}))",
}
