#!/usr/bin/env bash
# The rounds arm: six market-4 sessions at 4, 5 and 6 rounds per period.
#
#   ./run_rounds_arm.sh                      # all six
#   DRY=1 ./run_rounds_arm.sh                # print the plan, launch nothing
#   ./run_rounds_arm.sh rounds/m4_r6_paper   # just these
#
# Each session reuses the seed of a 3-round session already reported (m4_paper_0 and
# m4_random_0), so the gradient 3/4/5/6 runs on two fixed sequences and rounds is the only
# thing that varies. The scenarios differ from scenarios/m4_{paper,random}.yaml in exactly
# one line — same model, same three thinking budgets, same W=12, same rules.
#
# W stays at 12 on purpose. Six sessions leave ~17 requests in flight against Bailian's
# 50-80, so a higher W would shorten the broadcast phase — and would also add a throughput
# difference to an arm whose whole question is what more trading time does. One variable.
#
# Measured from the 3-round sessions (4,208 calls, $2.42, 7.8h each; 96% of calls scale
# with rounds, the 168 period-end notes do not):
#     4 rounds  ~5,555 calls  ~$3.19  ~10.2h
#     5 rounds  ~6,902 calls  ~$3.97  ~12.7h
#     6 rounds  ~8,248 calls  ~$4.74  ~15.2h
# Six in parallel: ~41,200 calls, ~$24, ~15h wall clock. No market-4 period has ever hit
# the "stop early if a whole round passed with no action" rule (0 of 70), so a session set
# to N rounds runs N.
set -uo pipefail
cd "$(dirname "$0")"

STAGGER=${STAGGER:-3}
PY=${PY:-./.venv/bin/python}
DRY=${DRY:-0}
mkdir -p logs
: > logs/rounds_arm.pids

# macOS ships bash 3.2, which has no `mapfile`; read the plan the portable way.
ROWS=""
while IFS= read -r line; do ROWS="$ROWS$line"$'\n'; done < <("$PY" batch_plan.py --rounds-arm)
WANT=" $* "

launched=0
while IFS=$'\t' read -r name scenario seed rounds; do
  [ -z "$name" ] && continue
  if [ "$WANT" != "  " ] && [ "${WANT#* $name }" = "$WANT" ]; then continue; fi
  if pgrep -f -- "--run-name $name " >/dev/null 2>&1; then
    echo "  SKIP $name (already running)"; continue
  fi
  flat=$(echo "$name" | tr '/' '_')
  if [ "$DRY" != "0" ]; then
    echo "  DRY  $name  seed=$seed  rounds=$rounds  <- $scenario"
    launched=$((launched + 1)); continue
  fi
  "$PY" -m ps1982 run -s "$scenario" --run-name "$name" --seed "$seed" \
      > "logs/$flat.log" 2>&1 &
  echo "$!	$name" >> logs/rounds_arm.pids
  echo "  $name  seed=$seed  rounds=$rounds  pid=$!"
  launched=$((launched + 1))
  [ "$STAGGER" != "0" ] && sleep "$STAGGER"
done <<< "$ROWS"

echo "launched $launched session(s)"
echo "watch:  $PY watch_batch.py          resume: ./resume_batch.sh"
echo "stop:   kill PIDs one at a time from logs/rounds_arm.pids, and verify with ps -o stat="
[ "$DRY" != "0" ] && exit 0
wait
echo "rounds arm finished"
