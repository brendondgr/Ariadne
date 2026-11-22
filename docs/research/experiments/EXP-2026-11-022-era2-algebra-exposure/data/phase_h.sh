#!/bin/bash
# EXP-2026-11-022, Stage 3 (Phase H): one sitting = one configuration, every arm.
# Usage: phase_h.sh <sitting: off-A|core|core+ext|off-B>
#
# Each sitting writes docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h/<sitting>/:
#   variants/{T-lazy,T-full,T-lazy-G}.json   the variant set (579 + 120 gold = 699 rows)
#   dev/planned_llm_typed_{lazy,full}         dev 284, Qwen
#   dev-gemma/planned_llm_typed_lazy          dev 284, Gemma
#   probe/..., probe-gemma/...                the probe measure half (115)
# off-A also runs R (captured twice, compared) and E (variants and dev), once for the whole step.
# Differences from EXP-2026-11-018's run.sh:
#   - wait_model checks the arm's model BY TOKEN ID every 30 s (up to 60 min), not only that the
#     relay answers /v1/models: the relay lists its endpoints while every backend is down.
#   - each arm is re-run once if H1 (model-less answers) fails, as in EXP-2026-11-018.
set -u
cd /home/bdgr/Agents/Ariadne
SIT=$1
case $SIT in off-A|off-B) CFG=off;; core) CFG=core;; core+ext) CFG=core+ext;; *) echo "bad sitting $SIT"; exit 2;; esac
RUNS=docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h
O=$RUNS/$SIT; L=$O/logs; mkdir -p $O/variants $L
P=$RUNS/progress.log
B=docs/evaluation/composition/bank/bank-dev.json
PM=docs/evaluation/algebra-2026-11/probe/probe-measure.json
unset ARIADNE_ALGEBRA_CORE ARIADNE_ALGEBRA_EXTENDED
case $CFG in core) export ARIADNE_ALGEBRA_CORE=1;; core+ext) export ARIADNE_ALGEBRA_CORE=1 ARIADNE_ALGEBRA_EXTENDED=1;; esac
export ORCH_MAX_HOPS=5
git rev-parse HEAD > $O/TREE; git status --short | grep -v '^?? \.\./' > $O/STATUS
env | grep '^ARIADNE_ALGEBRA' > $O/SWITCHES || true
echo "== $SIT ($CFG) start $(date)" >> $P

wait_model() {  # $1 = registry name
  uv run python - "$1" <<'EOF' >> $L/wait.log 2>&1 && return 0
import sys, time
from utils.llm.registry import load, check_identity, clear_identity_cache
spec = load()[sys.argv[1]]
for _ in range(120):
    clear_identity_cache()
    try:
        i = check_identity(spec)
        if i.verified:
            print(time.strftime("%F %T"), sys.argv[1], "verified", i.last_token_id); sys.exit(0)
        print(time.strftime("%F %T"), sys.argv[1], "not verified:", i.reason)
    except Exception as e:
        print(time.strftime("%F %T"), sys.argv[1], type(e).__name__, str(e)[:120])
    time.sleep(30)
sys.exit(1)
EOF
  echo "MODEL $1 DOWN $(date)" >> $P; return 1
}
model_of() { case $1 in *-G|gemma) echo gemma4-31b;; *) echo qwen38-27b;; esac; }

var() {  # var <arm>
  local a=$1
  for attempt in 1 2; do
    wait_model $(model_of $a)
    uv run python scripts/variant_harness.py compare --out $O/variants --arm $a --workers 16 > $L/var-$a.$attempt.log 2>&1; rc=$?
    uv run python scripts/era2_modelless.py $O/variants/$a.json >> $L/H1.log 2>&1; h=$?
    echo "$SIT var $a attempt=$attempt rc=$rc H1=$h $(date)" >> $P
    [ $h -eq 0 ] && return 0
    mv $O/variants/$a.json $L/dropped-var-$a.$attempt.json
  done
}
run_bank() {  # run_bank <label> <bank> <dev arm> <root> <model name> [extra args]
  local lab=$1 bank=$2 a=$3 root=$4 m=$5; shift 5
  for attempt in 1 2; do
    wait_model $m
    uv run python -m utils.evaluation.experiment_untruncated --arm $a --bank $bank --root $root --workers 16 "$@" \
      > $L/$lab-$a-$(basename $root).$attempt.log 2>&1; rc=$?
    uv run python scripts/era2_modelless.py $root/$a >> $L/H1.log 2>&1; h=$?
    echo "$SIT $lab $a ($(basename $root)) attempt=$attempt rc=$rc H1=$h $(date)" >> $P
    [ $h -eq 0 ] && return 0
    mv $root/$a $L/dropped-$lab-$(basename $root)-$a.$attempt
  done
}

cp docs/evaluation/variants-2026-09-15/variants.json $O/variants/variants.json
if [ "$SIT" = off-A ]; then
  uv run python scripts/variant_harness.py capture --out $O/variants --name reference.json --workers 8 > $L/R-capture1.log 2>&1; echo "R capture1 rc=$? $(date)" >> $P
  uv run python scripts/variant_harness.py capture --out $O/variants --name reference_check.json --workers 8 > $L/R-capture2.log 2>&1; echo "R capture2 rc=$? $(date)" >> $P
  cmp $O/variants/reference.json $O/variants/reference_check.json > $L/R-cmp.log 2>&1 && echo IDENTICAL >> $L/R-cmp.log || echo DIFFER >> $L/R-cmp.log
  uv run python scripts/variant_harness.py compare --out $O/variants --name R.json --workers 8 > $L/R-compare.log 2>&1; echo "R compare rc=$? $(date)" >> $P
else
  cp $RUNS/off-A/variants/reference.json $O/variants/reference.json
fi

(
 [ "$SIT" = off-A ] && var E
 var T-lazy; var T-full
 [ "$SIT" = off-A ] && run_bank dev $B planned_llm_english $O/dev qwen38-27b
 run_bank dev $B planned_llm_typed_lazy $O/dev qwen38-27b
 run_bank dev $B planned_llm_typed_full $O/dev qwen38-27b
 run_bank probe $PM planned_llm_typed_lazy $O/probe qwen38-27b
 run_bank probe $PM planned_llm_typed_full $O/probe qwen38-27b
) &
(
 var T-lazy-G
 run_bank dev $B planned_llm_typed_lazy $O/dev-gemma gemma4-31b --model gemma4-31b
 run_bank probe $PM planned_llm_typed_lazy $O/probe-gemma gemma4-31b --model gemma4-31b
) &
wait
for d in probe/planned_llm_typed_lazy probe/planned_llm_typed_full probe-gemma/planned_llm_typed_lazy; do
  n=$(echo $d | tr / -)
  uv run python scripts/algebra_probe_score.py $O/$d $PM --out $O/score-$n.json > $O/score-$n.txt 2>&1
done
echo "== $SIT DONE $(date)" >> $P
