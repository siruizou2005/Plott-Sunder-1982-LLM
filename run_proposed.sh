#!/usr/bin/env bash
# The proposed arms, one wave at a time.
#
#   ./run_proposed.sh rounds        # 6 sessions, ~13-15h, ~$23   truncation
#   ./run_proposed.sh stopped       # 4 sessions, ~7-8h,  ~$10    uninformed resting level
#   ./run_proposed.sh sellside      # 3 sessions, ~8h,    ~$7.5   sell-side sample
#   ./run_proposed.sh disclosed     # 3 sessions, ~8h,    ~$7.5   structural disclosure
#   ./run_proposed.sh ladder2       # 4 sessions, ~8h,    ~$10.5  ladder tier 2
#   ./run_proposed.sh ladder3       # 4 sessions, ~8h,    ~$10.5  ladder tier 3
#   DRY=1 ./run_proposed.sh rounds  # print the plan, launch nothing
#   ./run_proposed.sh stopped m94_stopped   # just these scenarios from the wave
#
# ONE WAVE AT A TIME, and the constraint is the endpoint rather than the box. A session
# drives its phases on one thread, so at most `broadcast_workers` of its requests are in
# flight at any instant and sessions x W is a structural ceiling against Bailian's
# tolerated 50-80. The waves are 72, 48, 36, 36, 48 and 48. All twenty-one unrun sessions
# at once would be 252, and the two ladder waves alone would be 96. W
# stays at 12 in every scenario file because the 26 sessions these arms are read against
# all ran at 12; lowering it here would put a throughput difference between an arm and its
# own comparison. The script refuses to start a wave while another one is running, for the
# same reason.
#
# Unlike run_control_arm.sh this passes NEITHER --run-name NOR --seed: every session in
# these arms differs from its neighbours in a parameter that has to be readable in the file
# that sets it, so run_name and seed live in the scenario. `batch_plan.py --proposed`
# carries the wave membership and nothing else.
#
# Resume after an interruption with ./resume_proposed.sh <wave>; a session ignores SIGTERM
# until a period boundary, so stopping one mid-period needs SIGKILL.
set -uo pipefail
cd "$(dirname "$0")"

WAVE=${1:-}
if [ -z "$WAVE" ]; then
  echo "usage: ./run_proposed.sh <rounds|stopped|sellside|disclosed|ladder2|ladder3>" \
       "[scenario ...]" >&2
  exit 2
fi
shift

STAGGER=${STAGGER:-3}
PY=${PY:-./.venv/bin/python}
DRY=${DRY:-0}
mkdir -p logs

# bash 3.2 on macOS has no `mapfile`; read the plan the portable way.
ROWS=""
while IFS= read -r line; do ROWS="$ROWS$line"$'\n'; done \
    < <("$PY" batch_plan.py --proposed "$WAVE") || exit 1
[ -z "${ROWS// /}" ] && { echo "no sessions in wave $WAVE" >&2; exit 1; }

# A wave already in flight is the one thing that breaks the ceiling, so refuse rather than
# add to it. Match the launched command line, not a bare pattern: `pgrep -f ps1982` also
# matches this script and the check itself.
#
# FORCE=1 overrides, and there is a real case for it. The provider client retries transient
# rejections -- 429 and the 408/409/5xx family, plus the SDK's rate-limit, timeout and
# connection errors -- with exponential backoff and FULL JITTER (`llm/base.py:_jittered`,
# base 2.0, 5 attempts, windows sampled uniformly over 2/4/8/16/32s), on top of a 0.25s
# pace before every request. That turns overload into latency instead of failure, which is
# what makes running all three waves at once viable at all.
#
# What it does NOT do is raise the endpoint's capacity. Past five retries the call returns
# `api_error: true`, and that is CONTAMINATION rather than model behaviour: the model never
# answered, so the skipped turn was not the agent's choice. Vertex has done exactly this
# here -- 54 retries in 75 calls and 5 corrupted turns at W=12. So when forcing, watch the
# retry counts rather than only the error counts:
#
#   grep -o '"retries":[0-9]*' runs/<group>/<run>/*.jsonl | sort | uniq -c
#
# and pull a wave if they climb. The default stays refuse, because the ceiling arithmetic
# in the scenario files is only true one wave at a time.
FORCE=${FORCE:-0}
running=$(ps -eo args= | grep -c '^[^ ]*\.venv/bin/python -m ps1982 run' || true)
if [ "$running" -gt 0 ] && [ "$DRY" = "0" ] && [ "$FORCE" = "0" ]; then
  echo "REFUSING: $running ps1982 session(s) already running." >&2
  echo "  ps -eo pid,stat,args | grep '[p]s1982 run'" >&2
  echo "  FORCE=1 to add this wave anyway — see the comment in this script first." >&2
  exit 1
fi
if [ "$running" -gt 0 ] && [ "$FORCE" != "0" ]; then
  echo "FORCED: adding this wave to $running session(s) already running." >&2
fi

WANT=" $* "
: > "logs/proposed_$WAVE.pids"
launched=0
while IFS=$'\t' read -r wave scenario; do
  [ -z "$scenario" ] && continue
  base=$(basename "$scenario" .yaml)
  if [ "$WANT" != "  " ] && [ "${WANT#* $base }" = "$WANT" ]; then continue; fi
  if [ "$DRY" != "0" ]; then
    echo "  DRY  $base  <- $scenario"
    launched=$((launched + 1)); continue
  fi
  "$PY" -m ps1982 run -s "$scenario" > "logs/$base.log" 2>&1 &
  echo "$!	$base" >> "logs/proposed_$WAVE.pids"
  echo "  $base  pid=$!  <- $scenario"
  launched=$((launched + 1))
  [ "$STAGGER" != "0" ] && sleep "$STAGGER"
done <<< "$ROWS"

echo "wave $WAVE: launched $launched session(s), $((launched * 12)) requests in flight at ceiling"
echo "watch:  https://plott.siruizou.com   or  $PY watch_batch.py"
echo "resume: ./resume_proposed.sh $WAVE"
echo "stop:   kill PIDs one at a time from logs/proposed_$WAVE.pids, verify with ps -o pid=,stat="
[ "$DRY" != "0" ] && exit 0
wait
echo "wave $WAVE finished"
