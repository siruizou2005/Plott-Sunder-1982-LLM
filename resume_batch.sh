#!/usr/bin/env bash
# Resume every session in the plan that has a checkpoint but is not finished.
#
# Safe to run repeatedly: a session already running is skipped, and one whose meta says
# "done" is left alone. This is the recovery path after a server reboot, an OOM kill, or a
# config fix applied between periods.
set -uo pipefail
cd "$(dirname "$0")"
STAGGER=${STAGGER:-3}
PY=${PY:-./.venv/bin/python}
mkdir -p logs

# bash 3.2 on macOS has no `mapfile`; see run_batch.sh.
ROWS=""
while IFS= read -r line; do ROWS="$ROWS$line"$'\n'; done < <("$PY" batch_plan.py)
n=0
while IFS=$'\t' read -r name scenario seed; do
  [ -z "$name" ] && continue
  ck=$(ls "runs/$name"/*.checkpoint.json 2>/dev/null | tail -1) || true
  meta=$(ls "runs/$name"/*.meta.json 2>/dev/null | tail -1) || true
  [ -z "$ck" ] && { echo "  SKIP $name (never started — use run_batch.sh)"; continue; }
  if [ -n "$meta" ] && grep -q '"status": "done"' "$meta"; then
    echo "  SKIP $name (finished)"; continue
  fi
  if pgrep -f -- "--run-name $name " >/dev/null 2>&1; then
    echo "  SKIP $name (running)"; continue
  fi
  "$PY" -m ps1982 run -s "$scenario" --run-name "$name" --seed "$seed" --resume \
      >> "logs/$name.log" 2>&1 &
  echo "  RESUME $name  pid=$!"
  n=$((n+1)); [ "$STAGGER" != "0" ] && sleep "$STAGGER"
done <<< "$ROWS"
echo "resumed $n session(s)"
wait
