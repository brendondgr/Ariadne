# 1. Copy config (first time only)
cp .env.example .env

# 2. Start both Neo4j (ATT&CK) and Gremlin (CAPEC) containers
uv run main.py --docker start

# 3. Build graph artifacts (if not already done)
uv run main.py --build attack
uv run main.py --build capec

# 4. Load ATT&CK into Neo4j
uv run main.py --dataset attack --graph neo4j

# 5. Load CAPEC into Gremlin
uv run main.py --dataset capec --graph gremlin

# 6. Verify both are healthy
uv run main.py --graph health
uv run main.py --dataset attack --graph verify
uv run main.py --dataset capec --graph verify