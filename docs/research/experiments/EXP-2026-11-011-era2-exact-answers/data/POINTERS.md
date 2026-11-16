# POINTERS — EXP-2026-11-011

No external artifacts: the hub stores are throwaway scratch containers (era2-hub-neo4j, era2-hub-gremlin) whose contents `scripts/era2_hub_bench.py load` recreates exactly, the fixture graphs are the kill-test stores reloaded from their committed loader, and the regression runs write to the session scratch directory, with their comparisons recorded in `data/exact.json`.
