#!/bin/bash
S=/tmp/claude-1000/-home-bdgr-Agents-Ariadne/e287aee2-08ba-47b4-b868-f26f2b870fe3/scratchpad/storefix
WT=$S/wt-preD bash $S/capture-noreload.sh F-preD
WT=/home/bdgr/Agents/Ariadne bash $S/capture-noreload.sh F-now
echo "F DONE $(date)" >> $S/F-now/progress.log
