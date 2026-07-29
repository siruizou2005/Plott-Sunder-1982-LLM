#!/usr/bin/env bash
# The control arm: six sessions, markets 7 and 8 at seeds 42, 43 and 44.
#
#   ./run_control_arm.sh                       # all six
#   DRY=1 ./run_control_arm.sh                 # print the plan, launch nothing
#   ./run_control_arm.sh control/m7_ctrl_43    # just these
#   MARKETS=-m8 ./run_control_arm.sh           # one market's three sessions
#
# Markets 7 and 8 are the EQUAL-WIDTH controls, and neither is one of Plott & Sunder's.
# Both informed-trade directions sit 100 francs from the uninformed level, AND a
# merely-competitive price occupies the same share of the D scale on each side (0.300 in
# market 7, 0.200 in market 8), AND every insider wants the same side in each state. Those
# are three separate confounds; the published family has all three and market 6 fixes only
# the first. So a buy/sell difference measured here is not the distance, not the interval
# width, and not disagreement among the informed about which way to trade.
#
# Markets 7 and 8 differ from each other in ONE thing: market 8 gives the three types
# separate roles (type I sets v-bar and tops neither state), so both of its states demand
# the same reallocation, while market 7 keeps the family's structure where the buy state
# needs no change of hands. Run them together or the comparison has nothing to compare.
#
# This arm SUPERSEDES the market-6 one. `scenarios/m6_control.yaml` and `make gate6` stay —
# market 6 is still the design Table 7 prints — but it is not what runs here.
#
# W stays at 12. Six sessions leave at most 72 requests in flight against Bailian's
# tolerated 50-80, and the measured mean is 1.9 per session (~11 typical). The comparison
# this arm feeds is against the 26 sessions of the main result, which all ran at W=12;
# changing it here would add a throughput difference to an arm whose question is direction.
# If Bailian starts refusing, run one market at a time with MARKETS=-m7 rather than
# lowering W.
#
# Measured from the market-4 sessions this inherits its shape from (14 periods, 3 rounds,
# ~4,290 calls, ~$2.47, ~7.9h each):
#     six sessions in parallel   ~25,700 calls   ~$15   ~8-10h wall clock
set -uo pipefail
cd "$(dirname "$0")"

STAGGER=${STAGGER:-3}
PY=${PY:-./.venv/bin/python}
DRY=${DRY:-0}
MARKETS=${MARKETS:-}
mkdir -p logs
: > logs/control_arm.pids

# macOS ships bash 3.2, which has no `mapfile`; read the plan the portable way.
ROWS=""
while IFS= read -r line; do ROWS="$ROWS$line"$'\n'; done \
    < <("$PY" batch_plan.py --control-arm $MARKETS)
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
