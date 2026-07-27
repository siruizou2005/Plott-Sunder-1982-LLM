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

from ps1982.markets import MARKETS

# Everything below is derived from the run's OWN market. It used to be market 3's
# constants applied to every run: a 4/4/4 seat->type map (market 1 is 3/3/3, so S04 was
# scored as type I when it is type II), market 3's expected dividends as the "right"
# arithmetic answer, market 3's RE/PI in the footer, `/12` as every market's period count,
# and state Y as the separating state (it is X in markets 2 and 5, and in market 1 it
# depends on the drawn sample). batch_plan.py --show was fixed for exactly this once
# already, on the principle that a status view that lies is worse than none; this file was
# missed.


def levels(mkt):
    """(seat->type, correct expected dividend, the equal-weight answer) for one market.

    NAIVE is what an agent gets by ignoring the bingo cage and weighting the states
    equally — the specific error this column exists to catch, and it has to be computed
    per market because the states and dividends differ.
    """
    true = {t: round(v) for t, v in mkt.prior_ev.items()}
    naive = {t: round(sum(mkt.dividends[t][s] for s in mkt.states) / len(mkt.states))
             for t in mkt.types}
    return mkt.seat_type, true, naive


def arithmetic(pairs, seat_type, true, naive):
    right = wrong = 0
    for seat, text in pairs:
        ty = seat_type.get(seat)
        if ty is None:
            continue                             # a seat this market does not have
        nums = {int(x) for x in re.findall(r"\b\d{3}\b", text)}
        right += true[ty] in nums and naive[ty] not in nums
        wrong += naive[ty] in nums and true[ty] not in nums
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

    # Logs written before `market` was recorded are market 3 — a fact about those logs,
    # which is how metrics.py reads them too, not a guess.
    start = next((e["payload"] for e in evs if e["type"] == "session_start"), {})
    mkt = MARKETS[start.get("market") or 3]
    seat_type, true, naive = levels(mkt)

    state, info, cards, closes, means = {}, {}, {}, {}, {}
    prices = collections.defaultdict(list)
    mt, notes, vio = [], collections.Counter(), collections.Counter()
    for e in evs:
        t = e["type"]
        if t == "period_start":
            state[e["payload"]["period"]] = e["payload"]["state"]
            info[e["payload"]["period"]] = e["payload"]["info"]
            cards[e["payload"]["period"]] = next(
                (c for c in (e["payload"].get("cards") or {}).values() if c), None)
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
                       if e["type"] == "reflection"], seat_type, true, naive)
    bc = arithmetic([(r["seat"], r.get("why") or "") for b in evs
                     if b["type"] == "broadcast" for r in b["payload"]["responses"]],
                    seat_type, true, naive)
    leak = sum(1 for e in evs if e["type"] == "brief"
               for s in seat_type if s in e["payload"]["text"])

    # This market's own separating periods, on the sample this run actually drew.
    sep = []
    for p in done:
        if info.get(p) != "insider" or p not in means:
            continue
        th = mkt.theory_at(info[p], state[p], p, cards.get(p))[0]
        if th["RE"] != th["PI"]:
            sep.append((p, means[p], th["RE"], th["PI"]))
    return dict(periods=len(done), n_periods=mkt.n_periods, market=mkt.number,
                calls=len(mt), tokens=u, no_reason=no_reason, notes=notes, vio=vio,
                refl=refl, bc=bc, leak=leak, sep=sep, size=os.path.getsize(path))


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

    print(f"{'run':16s} {'市场':>4s} {'期':>7s} {'调用':>6s} {'缓存':>5s} {'算术ok/naive':>13s} "
          f"{'笔记':>9s} {'违规':>6s} {'推理缺':>6s} {'泄漏':>4s} {'MB':>5s}  可分离期均价")
    tot_calls = tot_bad = 0
    for name, s in rows:
        pt, hit = s["tokens"]["prompt_tokens"], s["tokens"]["cache_hit_tokens"]
        bad = sum(v for k, v in s["vio"].items() if k in ("malformed", "empty_note"))
        tot_calls += s["calls"]; tot_bad += bad
        sep = " ".join(f"p{p}={m:.0f}(RE{re}/PI{pi})" for p, m, re, pi in s["sep"][-3:]) or "—"
        print(f"{name:16s} {s['market']:>4d} {s['periods']:>3d}/{s['n_periods']:<3d} "
              f"{s['calls']:>6d} "
              f"{100*hit/max(1,pt):>4.0f}% "
              f"{s['refl'][0]+s['bc'][0]:>6d}/{s['refl'][1]+s['bc'][1]:<6d} "
              f"{s['notes'].get('period_end',0):>4d}+{s['notes'].get('trade_feedback',0):<4d} "
              f"{bad:>6d} {s['no_reason']:>6d} {s['leak']:>4d} {s['size']/1e6:>5.1f}  {sep}")
    seen = sorted({s["market"] for _, s in rows})
    print(f"\n{len(rows)} runs · {tot_calls:,} calls · {tot_bad} malformed/empty · "
          f"markets {seen} — RE/PI are per period and shown in the last column, because "
          f"they differ by market and, in market 1, by the drawn sample")


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
