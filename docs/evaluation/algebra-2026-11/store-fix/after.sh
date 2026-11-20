#!/bin/bash
set -u
cd /home/bdgr/Agents/Ariadne
S=/tmp/claude-1000/-home-bdgr-Agents-Ariadne/e287aee2-08ba-47b4-b868-f26f2b870fe3/scratchpad/storefix
mkdir -p $S/after; P=$S/after/progress.log
uv run main.py --build all > $S/after/build.log 2>&1; echo "build rc=$? $(date)" >> $P
uv run python -c "
from gremlin_python.driver import client as gc
c=gc.Client('ws://localhost:6455/gremlin','g'); c.submit('g.V().drop().iterate()').all().result(); print(c.submit('g.V().count()').all().result())
" >> $P 2>&1; echo "gremlin wiped $(date)" >> $P
WT=/home/bdgr/Agents/Ariadne bash $S/capture.sh after
uv run python scripts/algebra_verify_stores.py load > $S/after/verify-load.json 2>&1; echo "verify load rc=$? $(date)" >> $P
echo "ALL DONE $(date)" >> $P
