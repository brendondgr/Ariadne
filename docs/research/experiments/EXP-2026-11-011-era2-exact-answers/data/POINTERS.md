# POINTERS — EXP-2026-11-011

No external artifacts are hashed. The hub stores are throwaway scratch containers (era2-hub-neo4j, era2-hub-gremlin) whose contents `scripts/era2_hub_bench.py load` recreates exactly. The regression runs write to the session scratch directory, and their comparisons are recorded in `data/exact.json`.
