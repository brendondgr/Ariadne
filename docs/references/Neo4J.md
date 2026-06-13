Here's a comprehensive breakdown of building a Neo4j knowledge graph from start to finish, assuming your data is ready.

***

## Step 1: Design Your Graph Schema

Before writing a single line of Cypher, plan your graph model — this is arguably the most important step. Your schema maps directly to three core concepts:

- **Node Labels** — represent entity types (e.g., `Person`, `Company`, `Product`)
- **Relationships** — directed edges between nodes with meaningful names (e.g., `WORKS_FOR`, `LOCATED_IN`, `RELATED_TO`)
- **Properties** — key-value attributes stored on nodes or relationships (e.g., `name: "Alice"`, `since: 2020`)

Organize entities into hierarchies if needed, and define how they relate before touching Neo4j. Sketch it on paper or use a tool like [arrows.app](https://arrows.app).

***

## Step 2: Set Up Constraints & Indexes

Before loading data, create uniqueness constraints on your primary identifiers to prevent duplicates and speed up lookups. Run this in the Neo4j Browser or Cypher Shell:

```cypher
CREATE CONSTRAINT FOR (p:Person) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT FOR (c:Company) REQUIRE c.name IS UNIQUE;
```

Indexes are created automatically when you add a constraint, so your MERGE and MATCH operations will be fast even at scale.

***

## Step 3: Import Nodes First

Always import nodes before relationships. If your data is in CSV format, use `LOAD CSV` with `MERGE` to safely upsert records:

```cypher
LOAD CSV WITH HEADERS FROM 'file:///persons.csv' AS row
MERGE (p:Person {id: row.id})
  ON CREATE SET p.name = row.name, p.age = toInteger(row.age);
```

Use `MERGE` instead of `CREATE` to avoid inserting duplicates if you re-run the import. For very large datasets (millions of rows), use `CALL { ... } IN TRANSACTIONS OF 500 ROWS` to batch commits and avoid memory issues.

***

## Step 4: Create Relationships

Once nodes exist, wire them together using a second CSV pass or inline Cypher:

```cypher
LOAD CSV WITH HEADERS FROM 'file:///works_for.csv' AS row
MATCH (p:Person {id: row.person_id})
MATCH (c:Company {name: row.company_name})
MERGE (p)-[:WORKS_FOR {since: row.since}]->(c);
```

Key rules for relationships:
- **Direction matters** — use `(a)-[:REL]->(b)` consistently
- **Properties on relationships** are valid and useful (e.g., weight, date, score)
- Use `MERGE` here too to prevent duplicate edges

***

## Step 5: Verify the Graph

Run exploratory queries to confirm your graph looks correct:

```cypher
-- See a sample of the graph
MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50;

-- Count nodes by label
MATCH (n) RETURN labels(n) AS label, COUNT(*) AS count;

-- Check a specific path
MATCH (p:Person)-[:WORKS_FOR]->(c:Company)
RETURN p.name, c.name LIMIT 10;
```

The Neo4j Browser provides a visual rendering of the graph, making it easy to spot missing connections or mislabeled nodes.

***

## Import Method

| Method | Best For | Notes |
|---|---|---|
| `LOAD CSV` (Cypher) | Medium datasets, flexible mapping | Transactional; supports `MERGE`  |
| `neo4j-admin import` | Massive bulk loads (millions+) | Non-transactional, fastest option  |
| Data Importer (UI) | Beginners, drag-and-drop CSV mapping | Auto-applies `MERGE` by default  |
| Python/JS Driver | Programmatic pipelines | Full control; handles preprocessing in code  |

***

## Key Cypher Cheat Sheet

```cypher
-- Create a node
CREATE (n:Label {property: "value"})

-- Merge (upsert) a node
MERGE (n:Label {id: "unique_id"})
  ON CREATE SET n.created = timestamp()
  ON MATCH SET n.updated = timestamp()

-- Create a relationship between existing nodes
MATCH (a:Person {name: "Alice"}), (b:Company {name: "Acme"})
CREATE (a)-[:WORKS_FOR]->(b)

-- Query a path
MATCH path = (a)-[:WORKS_FOR*1..3]->(b) RETURN path
```

The `MERGE` + `ON CREATE SET` / `ON MATCH SET` pattern is the workhorse of any production knowledge graph import.

What format is your data in (CSV, JSON, relational DB, etc.)? That would help narrow down the best import strategy for your specific case.