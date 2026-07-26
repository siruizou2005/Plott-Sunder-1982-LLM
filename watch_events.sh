#!/usr/bin/env bash
# Emit one line per STATE CHANGE across the batch, for a Monitor to consume.
#
# Polls rather than tailing seven logs: `tail -F` reprints a "==> file <==" header every
# time it switches files, which on seven concurrently-written logs is most of the output.
# Polling also lets a run's period count, its permanent failures and its exit all be
# reported in one line, and lets "finished" be reported from the meta rather than guessed
# from log text.
#
# Coverage: emits on progress, on rate limiting, on permanent API failure, on the process
# disappearing, and on completion — so silence means "nothing changed", never "it died".
set -uo pipefail
cd "$(dirname "$0")"
PY=${PY:-./.venv/bin/python}
INTERVAL=${INTERVAL:-60}

declare_state() { :; }
prev=""
while true; do
  cur=$("$PY" - <<'PY'
import glob, json, os, subprocess

ps = subprocess.run(["ps", "ax", "-o", "command="], capture_output=True, text=True).stdout
for d in sorted(glob.glob("runs/m3_*/")):
    name = d.strip("/").split("/")[-1]
    alive = f"--run-name {name} " in ps + " "
    logs = sorted(glob.glob(f"{d}*.jsonl"))
    if not logs:
        continue
    periods = calls = retries = errs = viol = 0
    for line in open(logs[-1], encoding="utf-8"):
        try:
            e = json.loads(line)
        except Exception:
            break                                   # a run mid-write: torn last line
        t = e["type"]
        periods += t == "period_end"
        viol += t == "violation"
        if t == "model_turn":
            calls += 1
            retries += e["payload"].get("retries", 0) or 0
            errs += bool(e["payload"].get("error"))
    meta = sorted(glob.glob(f"{d}*.meta.json"))
    status = "?"
    if meta:
        try:
            status = json.load(open(meta[-1])).get("status", "?")
        except Exception:
            pass
    print(f"{name}|{periods}|{calls}|{retries}|{errs}|{viol}|{status}|{int(alive)}")
PY
)
  while IFS='|' read -r name per calls retries errs viol status alive; do
    [ -z "$name" ] && continue
    key="$name:$per:$errs:$status:$alive"
    case "$prev" in *"[$key]"*) continue ;; esac
    flag=""
    [ "$errs" -gt 0 ] && flag=" API永久失败=$errs"
    [ "$retries" -gt 0 ] && flag="$flag 重试=$retries"
    [ "$viol" -gt 0 ] && flag="$flag 违规=$viol"
    if [ "$alive" = "0" ] && [ "$status" != "done" ]; then
      echo "$name ✗ 进程消失 于第 $per 期 (status=$status)$flag"
    elif [ "$status" = "done" ]; then
      echo "$name ✓ 完成 12/12 · $calls 次调用$flag"
    else
      echo "$name 第 $per/12 期 · $calls 次调用$flag"
    fi
  done <<< "$cur"
  prev=$(echo "$cur" | awk -F'|' '{printf "[%s:%s:%s:%s:%s]", $1,$2,$5,$7,$8}')
  sleep "$INTERVAL"
done
