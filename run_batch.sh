#!/usr/bin/env bash
# Launch the whole batch concurrently, one process per session.
#
#   ./run_batch.sh                 # all 25, Bailian
#   VENDOR=deepseek ./run_batch.sh # all 25, DeepSeek's own API
#   STAGGER=0 ./run_batch.sh       # no stagger at all
#   ./run_batch.sh g0_paper_0 g0_random_1     # just these
#
# Separate PROCESSES, not `--sessions 25`: turn decisions are strictly serial inside a
# session by design (design doc §6), so one process cannot use more throughput no matter
# how much the API allows.
#
# Concurrency is bounded structurally, not statistically. A session drives its phases on
# one thread, so at most `broadcast_workers` of its requests are in flight at any instant:
#   Bailian  5 sessions x 12 = 60 in flight, ceiling  (endpoint tolerates 50-80)
#   Vertex   2 sessions x 12 = 24 in flight, ceiling  (separate quota, does not add)
# Measured mean per session is 1.9 in flight, so the ceiling is reached only when every
# session happens to be mid-broadcast; it is a bound, not the expected load. Adding the
# four unimplemented markets takes Bailian to 25 sessions, which needs W=3 for 75.
# STAGGER spreads the cold start over a few seconds — negligible against a ~4.5h run, and
# it keeps the first cache-cold burst from landing in one instant.
set -uo pipefail
cd "$(dirname "$0")"

STAGGER=${STAGGER:-3}
PY=${PY:-./.venv/bin/python}
DRY=${DRY:-0}
mkdir -p logs

# macOS ships bash 3.2, which has no `mapfile` (a 4.0 builtin) — it would leave ROWS unset
# and, under `set -u`, abort before launching anything. Read the plan the portable way.
ROWS=""
while IFS= read -r line; do ROWS="$ROWS$line"$'\n'; done < <("$PY" batch_plan.py)
WANT=" $* "

launched=0
while IFS=$'\t' read -r name scenario seed; do
  [ -z "$name" ] && continue
  if [ "$WANT" != "  " ] && [ "${WANT#* $name }" = "$WANT" ]; then continue; fi
  if pgrep -f -- "--run-name $name " >/dev/null 2>&1; then
    echo "  SKIP $name (already running)"; continue
  fi
  if [ "$DRY" != "0" ]; then
    echo "  DRY  $name  seed=$seed  <- $scenario"
    launched=$((launched + 1)); continue
  fi
  "$PY" -m ps1982 run -s "$scenario" --run-name "$name" --seed "$seed" \
      > "logs/$name.log" 2>&1 &
  echo "  $name  seed=$seed  pid=$!  <- $scenario"
  launched=$((launched + 1))
  [ "$STAGGER" != "0" ] && sleep "$STAGGER"
done <<< "$ROWS"

echo "launched $launched session(s)"
echo "watch:  $PY watch_batch.py          resume: ./resume_batch.sh"
[ "$DRY" != "0" ] && exit 0
wait
echo "batch finished"
