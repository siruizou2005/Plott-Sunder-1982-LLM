#!/usr/bin/env bash
# Resume every session in a proposed wave that has a checkpoint but is not finished.
#
#   ./resume_proposed.sh rounds
#
# Safe to run repeatedly: a session already running is skipped, and one whose meta says
# "done" is left alone. This is the recovery path after a reboot, an OOM kill, or a config
# fix applied between periods — per-period checkpoints mean it loses at most the period
# that was in flight.
#
# The run directory is the scenario's own `run_name`, which for these arms is grouped
# (control/..., stopped/...), so the checkpoint lives one level deeper than for the 26
# replication sessions. Read it from the scenario rather than guessing.
set -uo pipefail
cd "$(dirname "$0")"

WAVE=${1:-}
if [ -z "$WAVE" ]; then
  echo "usage: ./resume_proposed.sh <rounds|stopped|sellside>" >&2
  exit 2
fi

STAGGER=${STAGGER:-3}
PY=${PY:-./.venv/bin/python}
mkdir -p logs

ROWS=""
while IFS= read -r line; do ROWS="$ROWS$line"$'\n'; done \
    < <("$PY" batch_plan.py --proposed "$WAVE") || exit 1

n=0
while IFS=$'\t' read -r wave scenario; do
  [ -z "$scenario" ] && continue
  base=$(basename "$scenario" .yaml)
  name=$("$PY" -c "import sys,yaml;print(yaml.safe_load(open(sys.argv[1]))['run_name'])" "$scenario")
  ck=$(ls "runs/$name"/*.checkpoint.json 2>/dev/null | tail -1) || true
  meta=$(ls "runs/$name"/*.meta.json 2>/dev/null | tail -1) || true
  [ -z "$ck" ] && { echo "  SKIP $base (never started — use run_proposed.sh)"; continue; }
  if [ -n "$meta" ] && grep -q '"status": "done"' "$meta"; then
    echo "  SKIP $base (finished)"; continue
  fi
  if ps -eo args= | grep -q -- "-s $scenario\$\|-s $scenario "; then
    echo "  SKIP $base (running)"; continue
  fi
  "$PY" -m ps1982 run -s "$scenario" --resume >> "logs/$base.log" 2>&1 &
  echo "  RESUME $base  pid=$!"
  n=$((n + 1)); [ "$STAGGER" != "0" ] && sleep "$STAGGER"
done <<< "$ROWS"

echo "resumed $n session(s)"
wait
