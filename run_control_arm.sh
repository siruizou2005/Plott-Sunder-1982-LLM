#!/usr/bin/env bash
# The control arm: three market-6 sessions at seeds 42, 43 and 44.
#
#   ./run_control_arm.sh                       # the three DeepSeek sessions
#   DRY=1 ./run_control_arm.sh                 # print the plan, launch nothing
#   ./run_control_arm.sh control/m6_ctrl_43    # just these
#   GEMINI=1 ./run_control_arm.sh control/m6_gem_quick   # the five-period Gemini prefix
#
# Market 6 is the equidistant control of Table 7 — NOT one of Plott & Sunder's. Both
# informed-trade directions sit 80 francs from the uninformed level of 220, so a
# difference between the two sides is not the distance. Everything else is market 3's.
#
# W stays at 12. Three sessions leave at most 36 requests in flight against Bailian's
# tolerated 50-80, and the measured mean is 1.9 per session. The comparison this arm feeds
# is against the 26 sessions of the main result, which all ran at W=12; changing it here
# would add a throughput difference to an arm whose whole question is about direction.
#
# The Gemini session is EXCLUDED by default: it goes to Vertex, whose dynamic shared quota
# is a different bottleneck and which the main batch runs one session at a time. Launch it
# on its own with GEMINI=1, and never alongside another Vertex run.
#
# Measured from the market-3 sessions this inherits its shape from (12 periods, 3 rounds,
# ~3,700 calls, ~$2.00, ~5.6h each):
#     three DeepSeek sessions in parallel  ~11,100 calls  ~$6   ~6h wall clock
#     the Gemini five-period prefix        ~1,700 calls   ~$8   ~0.7h
set -uo pipefail
cd "$(dirname "$0")"

STAGGER=${STAGGER:-3}
PY=${PY:-./.venv/bin/python}
DRY=${DRY:-0}
GEMINI=${GEMINI:-0}
mkdir -p logs
: > logs/control_arm.pids

# macOS ships bash 3.2, which has no `mapfile`; read the plan the portable way.
PLAN_ARGS="--control-arm"
[ "$GEMINI" = "0" ] && PLAN_ARGS="$PLAN_ARGS --no-gemini"
ROWS=""
while IFS= read -r line; do ROWS="$ROWS$line"$'\n'; done < <("$PY" batch_plan.py $PLAN_ARGS)
WANT=" $* "

launched=0
while IFS=$'\t' read -r name scenario seed; do
  [ -z "$name" ] && continue
  if [ "$WANT" != "  " ] && [ "${WANT#* $name }" = "$WANT" ]; then continue; fi
  if pgrep -f -- "--run-name $name " >/dev/null 2>&1; then
    echo "  SKIP $name (already running)"; continue
  fi
  flat=$(echo "$name" | tr '/' '_')
  if [ "$DRY" != "0" ]; then
    echo "  DRY  $name  seed=$seed  <- $scenario"
    launched=$((launched + 1)); continue
  fi
  "$PY" -m ps1982 run -s "$scenario" --run-name "$name" --seed "$seed" \
      > "logs/$flat.log" 2>&1 &
  echo "$!	$name" >> logs/control_arm.pids
  echo "  $name  seed=$seed  pid=$!  <- $scenario"
  launched=$((launched + 1))
  [ "$STAGGER" != "0" ] && sleep "$STAGGER"
done <<< "$ROWS"

echo "launched $launched session(s)"
echo "watch:  $PY watch_batch.py          resume: ./resume_batch.sh"
echo "stop:   kill PIDs one at a time from logs/control_arm.pids, and verify with ps -o stat="
[ "$DRY" != "0" ] && exit 0
wait
echo "control arm finished"
