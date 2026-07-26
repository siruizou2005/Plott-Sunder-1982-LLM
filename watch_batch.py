#!/usr/bin/env python3
"""Status across every run in the batch.

Reports the things that would silently invalidate a run rather than crash it — arithmetic
drifting back to the 50/50 prior, notes failing to land, seat ids leaking into prompts,
reasoning not being captured — alongside progress and spend. Reads the logs, so it is safe
to run against sessions that are still going.

  ./watch_batch.py            one snapshot
  ./watch_batch.py --loop 60  refresh every 60s
"""

from __future__ import annotations

import collections
import glob
import json
import os
import re
import sys
import time

ST = {**{f"S{i:02d}": "I" for i in range(1, 5)},
      **{f"S{i:02d}": "II" for i in range(5, 9)},
      **{f"S{i:02d}": "III" for i in range(9, 13)}}
TRUE = {"I": 220, "II": 210, "III": 155}
NAIVE = {"I": 250, "II": 225, "III": 150}          # the 50/50 answer
RE_P, PI_P = 175, 220


def arithmetic(pairs):
    right = wrong = 0
    for seat, text in pairs:
        ty = ST[seat]
        nums = {int(x) for x in re.findall(r"\b\d{3}\b", text)}
        right += TRUE[ty] in nums and NAIVE[ty] not in nums
        wrong += NAIVE[ty] in nums and TRUE[ty] not in nums
    return right, wrong


def scan(path):
    evs = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                evs.append(json.loads(line))
            except json.JSONDecodeError:
                break                                # a run mid-write: torn last line
    if not evs:
        return None

    state, info, closes, means = {}, {}, {}, {}
    prices = collections.defaultdict(list)
    mt, notes, vio = [], collections.Counter(), collections.Counter()
    for e in evs:
        t = e["type"]
        if t == "period_start":
            state[e["payload"]["period"]] = e["payload"]["state"]
            info[e["payload"]["period"]] = e["payload"]["info"]
        elif t == "trade":
            prices[e["period"]].append(e["payload"]["price"])
        elif t == "model_turn":
            mt.append(e)
        elif t == "reflection":
            notes[e["payload"]["kind"]] += 1
        elif t == "violation":
            vio[e["payload"].get("reason")] += 1
    done = sorted({e["payload"]["period"] for e in evs if e["type"] == "period_end"})
    for p in done:
        if prices[p]:
            closes[p] = prices[p][-1]
            means[p] = sum(prices[p]) / len(prices[p])

    u = collections.Counter()
    for e in mt:
        d = e["payload"].get("usage") or {}
        for k in ("prompt_tokens", "completion_tokens", "cache_hit_tokens"):
            u[k] += d.get(k, 0)
    no_reason = sum(1 for e in mt if not (e["payload"].get("reasoning") or "").strip())

    refl = arithmetic([(e["seat"], e["payload"]["text"]) for e in evs
                       if e["type"] == "reflection"])
    bc = arithmetic([(r["seat"], r.get("why") or "") for b in evs
                     if b["type"] == "broadcast" for r in b["payload"]["responses"]])
    leak = sum(1 for e in evs if e["type"] == "brief"
               for s in ST if s in e["payload"]["text"])

    sep = [(p, means[p]) for p in done
           if info.get(p) == "insider" and state.get(p) == "Y" and p in means]
    return dict(periods=len(done), calls=len(mt), tokens=u, no_reason=no_reason,
                notes=notes, vio=vio, refl=refl, bc=bc, leak=leak, sep=sep,
                size=os.path.getsize(path))


def snapshot():
    rows = []
    for d in sorted(glob.glob("runs/*/")):
        name = d.strip("/").split("/")[-1]
        logs = sorted(glob.glob(f"{d}*.jsonl"))
        if not logs:
            continue
        s = scan(logs[-1])
        if s:
            rows.append((name, s))
    if not rows:
        print("no runs yet")
        return

    print(f"{'run':16s} {'期':>5s} {'调用':>6s} {'缓存':>5s} {'算术ok/naive':>13s} "
          f"{'笔记':>9s} {'违规':>6s} {'推理缺':>6s} {'泄漏':>4s} {'MB':>5s}  可分离期均价")
    tot_calls = tot_bad = 0
    for name, s in rows:
        pt, hit = s["tokens"]["prompt_tokens"], s["tokens"]["cache_hit_tokens"]
        bad = sum(v for k, v in s["vio"].items() if k in ("malformed", "empty_note"))
        tot_calls += s["calls"]; tot_bad += bad
        sep = " ".join(f"p{p}={m:.0f}" for p, m in s["sep"][-4:]) or "—"
        print(f"{name:16s} {s['periods']:>3d}/12 {s['calls']:>6d} "
              f"{100*hit/max(1,pt):>4.0f}% "
              f"{s['refl'][0]+s['bc'][0]:>6d}/{s['refl'][1]+s['bc'][1]:<6d} "
              f"{s['notes'].get('period_end',0):>4d}+{s['notes'].get('trade_feedback',0):<4d} "
              f"{bad:>6d} {s['no_reason']:>6d} {s['leak']:>4d} {s['size']/1e6:>5.1f}  {sep}")
    print(f"\n{len(rows)} runs · {tot_calls:,} calls · "
          f"{tot_bad} malformed/empty · RE={RE_P} PI={PI_P} (中点 {(RE_P+PI_P)/2})")


if __name__ == "__main__":
    every = 0
    if "--loop" in sys.argv:
        every = int(sys.argv[sys.argv.index("--loop") + 1])
    while True:
        os.system("clear") if every else None
        snapshot()
        if not every:
            break
        time.sleep(every)
