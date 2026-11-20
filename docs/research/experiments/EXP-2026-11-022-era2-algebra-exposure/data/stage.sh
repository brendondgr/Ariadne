#!/bin/bash
# EXP-2026-11-022, Stages 1-2: one configuration, the probe tune half + the 60 controls.
# Usage: stage.sh <out root> <config: off|core|core+ext> <arm: T-lazy|T-full|T-lazy-G>
set -u
cd /home/bdgr/Agents/Ariadne
ROOT=$1; CFG=$2; ARM=$3
O=$ROOT/$CFG/$ARM; mkdir -p $O; P=$ROOT/progress.log
unset ARIADNE_ALGEBRA_CORE ARIADNE_ALGEBRA_EXTENDED
case $CFG in core) export ARIADNE_ALGEBRA_CORE=1;; core+ext) export ARIADNE_ALGEBRA_CORE=1 ARIADNE_ALGEBRA_EXTENDED=1;; off) ;; *) echo bad cfg; exit 2;; esac
export ORCH_MAX_HOPS=5
case $ARM in T-lazy) DA=planned_llm_typed_lazy; MOD=();; T-full) DA=planned_llm_typed_full; MOD=();; T-lazy-G) DA=planned_llm_typed_lazy; MOD=(--model gemma4-31b);; esac
wait_relay() { for i in $(seq 1 120); do curl -sf localhost:9090/v1/models >/dev/null && return 0; sleep 5; done; echo "RELAY DOWN $(date)" >> $P; return 1; }
git rev-parse HEAD > $O/TREE; git status --short | grep -v '^?? \.\./' > $O/STATUS
cp $ROOT/variants.json $ROOT/reference.json $O/
wait_relay; uv run python scripts/variant_harness.py compare --out $O --arm $ARM --no-gold --workers 12 > $O/var.log 2>&1; echo "$CFG $ARM var rc=$? $(date)" >> $P
uv run python scripts/era2_modelless.py $O/$ARM.json >> $P 2>&1
wait_relay; uv run python -m utils.evaluation.experiment_untruncated --arm $DA --bank docs/evaluation/composition/bank/bank-dev.json --root $O/dev --workers 12 --only "$(cat $ROOT/dev_ids.txt)" "${MOD[@]}" > $O/dev.log 2>&1; echo "$CFG $ARM dev rc=$? $(date)" >> $P
uv run python scripts/era2_modelless.py $O/dev/$DA >> $P 2>&1
wait_relay; uv run python -m utils.evaluation.experiment_untruncated --arm $DA --bank docs/evaluation/algebra-2026-11/probe/probe-tune.json --root $O/probe --workers 12 "${MOD[@]}" > $O/probe.log 2>&1; echo "$CFG $ARM probe rc=$? $(date)" >> $P
uv run python scripts/era2_modelless.py $O/probe/$DA >> $P 2>&1
uv run python scripts/algebra_probe_score.py $O/probe/$DA docs/evaluation/algebra-2026-11/probe/probe-tune.json --out $O/probe-score.json > $O/probe-score.txt 2>&1
echo "$CFG $ARM DONE $(date)" >> $P
