#!/usr/bin/env python3
"""What the agents said they were doing, and whether they were doing it.

Not a metrics module — `ps1982/metrics.py` scores the market. This reads the three text
channels the log carries alongside the prices, and the elicited fields attached to every
turn, and asks how the UNINFORMED form a belief. `docs/agent-reasoning.md` is written
from its output.

    ./reasoning_report.py runs/m1/*/*.jsonl runs/m2/*/*.jsonl ...      # all sections
    ./reasoning_report.py --only basis,cliff runs/m1/*/*.jsonl         # some of them
    ./reasoning_report.py --dump /tmp/text runs/m3/*/*.jsonl           # extract the text

Sections, in the order the doc uses them:

  basis      the stated basis against the belief it is attached to — the validation every
             downstream reading depends on
  cliff      market 1's insiders against the exact posterior their sample implies, and the
             same agents' price-based movement toward RE
  fixpoint   the share of price-based beliefs that land exactly on the price
  pnl        realized francs per trade side, split by who held a card
  drift      basis share and RE-gap closure by period — the learning question
  notes      keyword incidence over the private notes and the broadcast justifications

Every section takes the same log list. Sections that need a two-state market skip market 5
rather than silently pooling it.
"""

from __future__ import annotations

import collections
import json
import re
import statistics
import sys

from ps1982.markets import MARKETS, sample_posterior

# Only these event types are parsed; the rest of a 60 MB log is skipped on a substring
# test before `json.loads` ever sees it.
WANTED = ("session_start", "period_start", "agent_view", "trade", "reflection",
          "broadcast", "model_turn")


def load(path, types=WANTED):
    """Stream one log, keeping `types`. The substring pre-filter is what makes a
    26-session sweep finish in minutes rather than an hour."""
    keys = tuple(f'"{t}"' for t in types)
    out = []
    for line in open(path, encoding="utf-8"):
        if not any(k in line for k in keys):
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            break                                    # a run mid-write: torn last line
        if e.get("type") in types:
            out.append(e)
    return out


def periods(path, types=WANTED):
    """Yield (market, run_name, period_dict) with theory and side already attached.

    `side` is the market's side, not the agent's: buy where RE > v̄, sell where RE < v̄.
    It is read from `theory_at` with the REALIZED card, never from the period number —
    market 1's prediction depends on the sample the period actually drew.
    """
    ev = load(path, types)
    start = next((e["payload"] for e in ev if e["type"] == "session_start"), None)
    if start is None:
        return
    mkt = MARKETS[start.get("market", 3)]
    run = (start.get("config") or {}).get("run_name") or path
    vbar = max(mkt.prior_ev.values())
    cur = None
    for e in ev:
        t = e["type"]
        if t == "period_start":
            p = e["payload"]
            card = next((c for c in (p.get("cards") or {}).values() if c), None)
            price, _ = mkt.theory_at(p["info"], p["state"], e["period"], card)
            if cur is not None:
                yield mkt, run, cur
            cur = {"period": e["period"], "state": p["state"], "info": p["info"],
                   "cards": p.get("cards") or {}, "card": card,
                   "re": price["RE"], "pi": price["PI"],
                   "side": None if p["info"] == "none" else
                           ("buy" if price["RE"] > vbar else "sell"),
                   "views": [], "trades": [], "notes": [], "why": [], "last": None}
        elif cur is None:
            continue
        elif t == "trade":
            cur["trades"].append(e["payload"])
            cur["last"] = e["payload"]["price"]
        elif t == "agent_view":
            cur["views"].append({**e["payload"], "seat": e["seat"], "round": e["round"],
                                 "last": cur["last"]})
        elif t == "reflection":
            cur["notes"].append({**e["payload"], "seat": e["seat"]})
        elif t == "broadcast":
            for r in e["payload"].get("responses") or []:
                if r.get("why"):
                    cur["why"].append({**r, "quote": e["payload"].get("quote")})
    if cur is not None:
        yield mkt, run, cur


def views(paths, informed=None, info=None):
    """Every elicited view, with its market, period context and own dividends resolved."""
    for path in paths:
        for mkt, run, per in periods(path, ("session_start", "period_start", "agent_view",
                                            "trade")):
            if info is not None and per["info"] != info:
                continue
            for v in per["views"]:
                has_card = per["cards"].get(v["seat"]) is not None
                if informed is not None and has_card != informed:
                    continue
                post = v.get("posterior") or {}
                if not all(s in post for s in mkt.states):
                    continue
                d = mkt.dividends[mkt.seat_type[v["seat"]]]
                yield {
                    "market": mkt.number, "run": run, "period": per["period"],
                    "round": v["round"], "seat": v["seat"],
                    "type": mkt.seat_type[v["seat"]], "informed": has_card,
                    "info": per["info"], "state": per["state"], "side": per["side"],
                    "re": per["re"], "card": per["card"], "last": v["last"],
                    "basis": v.get("basis"), "posterior": {s: float(post[s]) for s in mkt.states},
                    "rb": v.get("reservation_buy"), "rs": v.get("reservation_sell"),
                    "implied": sum(float(post[s]) * d[s] for s in mkt.states),
                    "prior_ev": mkt.prior_ev[mkt.seat_type[v["seat"]]],
                    "prior": dict(mkt.prior), "div": dict(d),
                }


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def corr(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    if sx == 0 or sy == 0:
        return float("nan")
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


# --------------------------------------------------------------------------- sections


def sec_basis(paths):
    """Is the stated basis attached to the belief it claims, or is it decoration?

    An agent that says `prior` should be sitting ON the prior; one that says `price`
    should have moved, and moved WITH the price. Everything downstream of this report
    assumes the label means something, so it is checked first.
    """
    print("=== the stated basis against the belief it is attached to ===")
    rows = [v for v in views(paths, informed=False) if v["basis"]]
    print(f"{'basis':>16} {'info':>8} {'n':>6} {'|implied-priorEV|':>18} "
          f"{'corr(implied,last)':>19} {'exactly at prior':>17}")
    for info in ("insider", "none"):
        for b in ("prior", "price", "others_behavior"):
            sel = [v for v in rows if v["basis"] == b and v["info"] == info]
            if len(sel) < 40:
                continue
            with_last = [v for v in sel if v["last"] is not None]
            at_prior = sum(1 for v in sel
                           if all(abs(v["posterior"][s] - v["prior"][s]) <= 0.005
                                  for s in v["prior"]))
            print(f"{b:>16} {info:>8} {len(sel):>6} "
                  f"{mean([abs(v['implied'] - v['prior_ev']) for v in sel]):>18.1f} "
                  f"{corr([v['implied'] for v in with_last], [v['last'] for v in with_last]):>19.3f} "
                  f"{at_prior / len(sel):>16.0%}")

    print("\n  stated basis by round, uninformed, insider periods vs no-information periods")
    for info in ("insider", "none"):
        for rnd in (1, 2, 3):
            c = collections.Counter(v["basis"] for v in rows
                                    if v["info"] == info and v["round"] == rnd)
            n = sum(c.values())
            if not n:
                continue
            print(f"    {info:>7} round {rnd}  n={n:5d}  " +
                  str({k: f"{v / n:.0%}" for k, v in c.most_common(4)}))

    print("\n  reservation_sell is unusable without filtering on holdings:")
    rs = [v["rs"] for v in rows if v["rs"] is not None]
    big = sum(1 for v in rows if v["rs"] is not None and v["rs"] > 2 * max(v["div"].values()))
    print(f"    n={len(rs)}  median {statistics.median(rs):.0f}  "
          f"max {max(rs)}  share above 2x own top dividend {big / len(rs):.1%}")


def sec_cliff(paths):
    """The same agents, two ways of getting a posterior.

    Market 1's clue is a ten-draw sample, so the correct posterior is computable and the
    prompt hands over the likelihood as two boxes of chips. Price-based inference hands
    over nothing: the base rate of insiders is withheld by design.
    """
    print("=== written-down likelihood: market 1's insiders against exact Bayes ===")
    errs, cells = [], collections.defaultdict(list)
    for v in views(paths, informed=True):
        if v["market"] != 1 or not v["card"]:
            continue
        correct = sample_posterior(v["card"], v["prior"])["X"]
        errs.append(abs(v["posterior"]["X"] - correct))
        cells[(v["card"], round(correct, 3))].append(v["posterior"]["X"])
    if errs:
        print(f"  n={len(errs)}  mean |stated - correct| {statistics.mean(errs):.4f}  "
              f"median {statistics.median(errs):.4f}  within 0.01 {sum(1 for e in errs if e <= .01) / len(errs):.0%}")
        print(f"  {'sample':>12} {'1s':>3} {'correct p(X)':>13} {'stated mean':>12} {'n':>4}")
        # One row per distinct sample, pooled over the runs that drew it.
        for (card, correct), xs in sorted(cells.items(), key=lambda kv: -kv[0][1]):
            print(f"  {card:>12} {card.count('1'):>3} {correct:>13.3f} "
                  f"{mean(xs):>12.3f} {len(xs):>4}")

    print("\n=== constructed likelihood: uninformed movement toward RE, insider periods ===")
    print("  the buy side only; the sell-side gap is 2-45 francs and the ratio is unusable")
    print(f"{'mkt':>4} {'n':>5} {'priorEV':>8} {'implied':>8} {'RE':>6} {'francs moved':>13} "
          f"{'% of gap':>9}")
    rows = [v for v in views(paths, informed=False, info="insider") if v["side"] == "buy"]
    for m in sorted({v["market"] for v in rows}):
        sel = [v for v in rows if v["market"] == m]
        if len(sel) < 20:
            continue
        pe, im, re_ = mean([v["prior_ev"] for v in sel]), mean([v["implied"] for v in sel]), \
            mean([v["re"] for v in sel])
        print(f"{m:>4} {len(sel):>5} {pe:>8.1f} {im:>8.1f} {re_:>6.0f} {im - pe:>13.1f} "
              f"{(im - pe) / (re_ - pe):>8.0%}")

    print("\n  the same in absolute francs, both sides — the movement is side-independent")
    for m in sorted({v["market"] for v in views(paths, informed=False, info="insider")}):
        for side in ("buy", "sell"):
            sel = [v for v in views(paths, informed=False, info="insider")
                   if v["market"] == m and v["side"] == side]
            if len(sel) < 20:
                continue
            print(f"    market {m} {side:>4}: {mean([v['implied'] - v['prior_ev'] for v in sel]):+7.1f} f"
                  f"   (gap to RE {mean([v['re'] - v['prior_ev'] for v in sel]):+7.1f} f)")


def sec_fixpoint(paths):
    """Own-dividend price inversion: solving `last = p*d[X] + (1-p)*d[Y]` for p.

    Such an agent's own valuation then EQUALS the price, so its reservation never exceeds
    the price and it can never move one. Two-state markets only — the inversion is not
    defined for market 5's three states.
    """
    print("=== does the price-based belief land on the price? ===")
    rows = []
    for v in views(paths, informed=False):
        if len(v["div"]) != 2 or v["last"] is None:
            continue
        lo, hi = min(v["div"].values()), max(v["div"].values())
        if not lo <= v["last"] <= hi:            # inversion undefined outside the range
            continue
        rows.append(v)
    print(f"  uninformed views with the price inside their own dividend range: {len(rows)}")
    print(f"{'basis':>16} {'info':>8} {'n':>6} {'implied within 5f of price':>27}")
    for info in ("insider", "none"):
        for b in ("price", "prior", "others_behavior"):
            sel = [v for v in rows if v["basis"] == b and v["info"] == info]
            if len(sel) < 40:
                continue
            on = sum(1 for v in sel if abs(v["implied"] - v["last"]) <= 5)
            print(f"{b:>16} {info:>8} {len(sel):>6} {on / len(sel):>26.0%}")

    print("\n  among price-based views in insider periods, how far past the price:")
    print(f"{'mkt':>4} {'side':>5} {'n':>5} {'implied-last':>13} {'frac rb>last':>13}")
    for m in sorted({v["market"] for v in rows}):
        for side in ("buy", "sell"):
            sel = [v for v in rows if v["market"] == m and v["basis"] == "price"
                   and v["info"] == "insider" and v["side"] == side and v["rb"] is not None]
            if len(sel) < 40:
                continue
            print(f"{m:>4} {side:>5} {len(sel):>5} "
                  f"{mean([v['implied'] - v['last'] for v in sel]):>13.1f} "
                  f"{sum(1 for v in sel if v['rb'] > v['last']) / len(sel):>12.0%}")


def sec_pnl(paths):
    """Score each trade side ex post against the dividend that was actually paid.

    Not zero-sum: the two sides hold different dividend schedules, so the total is the
    realized gain from trade. The question is who captures it.
    """
    rows = []
    for path in paths:
        for mkt, run, per in periods(path, ("session_start", "period_start", "trade")):
            for t in per["trades"]:
                for role in ("buyer", "seller"):
                    seat = t[role]
                    d = mkt.dividend(seat, per["state"])
                    rows.append({"market": mkt.number, "info": per["info"],
                                 "side": per["side"], "role": role,
                                 "informed": per["cards"].get(seat) is not None,
                                 "pnl": (d - t["price"]) if role == "buyer" else (t["price"] - d)})
    print("=== realized francs per trade side, insider periods ===")
    print(f"{'side':>6} {'role':>7} {'informed':>9} {'n':>6} {'mean pnl':>10} {'% losing':>9}")
    for side in ("buy", "sell"):
        for role in ("buyer", "seller"):
            for inf in (True, False):
                sel = [r for r in rows if r["info"] == "insider" and r["side"] == side
                       and r["role"] == role and r["informed"] == inf]
                if not sel:
                    continue
                print(f"{side:>6} {role:>7} {str(inf):>9} {len(sel):>6} "
                      f"{mean([r['pnl'] for r in sel]):>10.1f} "
                      f"{sum(1 for r in sel if r['pnl'] < 0) / len(sel):>8.0%}")
    ui = [r for r in rows if r["info"] == "insider" and not r["informed"]]
    ii = [r for r in rows if r["info"] == "insider" and r["informed"]]
    print(f"\n  informed sides   n={len(ii):>6}  total {sum(r['pnl'] for r in ii):>10,.0f} francs")
    print(f"  uninformed sides n={len(ui):>6}  total {sum(r['pnl'] for r in ui):>10,.0f} francs")
    nb = [r for r in rows if r["info"] == "none"]
    print(f"  control, no-information periods: n={len(nb)} "
          f"mean {mean([r['pnl'] for r in nb]):.1f} f, "
          f"{sum(1 for r in nb if r['pnl'] < 0) / len(nb):.0%} losing")


def sec_drift(paths):
    """Does any of this improve over a session? Periods with a small RE gap are dropped:
    a 2-franc denominator makes the ratio meaningless, not informative."""
    print("=== basis share and RE-gap closure by period ===")
    agg = collections.defaultdict(lambda: {"b": collections.Counter(), "mv": []})
    for v in views(paths, informed=False, info="insider"):
        gap = v["re"] - v["prior_ev"]
        if abs(gap) < 20:
            continue
        agg[v["period"]]["b"][v["basis"]] += 1
        agg[v["period"]]["mv"].append((v["implied"] - v["prior_ev"]) / gap)
    print(f"{'period':>7} {'n':>6} {'%price':>7} {'%prior':>7} {'mean gap closed':>16}")
    for p in sorted(agg):
        a = agg[p]
        n = sum(a["b"].values())
        if n < 30:
            continue
        print(f"{p:>7} {n:>6} {a['b']['price'] / n:>6.0%} {a['b']['prior'] / n:>6.0%} "
              f"{statistics.mean(a['mv']):>15.1%}")


NOTE_PATTERNS = {
    "dominance — above my max / below my min": r"risk-?free|guaranteed|regardless of (the )?(dividend|outcome|which)|no matter which|above my (maximum|max|highest)",
    "claims to detect an insider": r"insider|informed (trader|investor|buyer|seller)|someone (knows|has a clue)|has a clue|lettered clue",
    "reads price as the signal": r"price (signal|reveal|tells|indicat|suggest)|use the price|infer.{0,20}from the price",
    "suspects the price is noise": r"noise|no signal|uninformative|coincidence|means nothing",
    "infers others hold different dividends": r"different (earnings|dividend|values)|others.{0,20}(higher|lower).{0,15}(dividend|earnings)|their own (earnings|dividend)",
    "names a specific rival": r"\b(Nora|Wendell|Teodor|Ines|Yusuf|Chika|Priya|Bela|Anton|Delphine|Felix|Marcus)\b",
    "explicit Bayes / likelihood language": r"bayes|likelihood|posterior|conditional on",
    "adverse selection / picked off": r"picked off|adverse selection|winner'?s curse|why would (he|she|they|anyone|someone) .{0,20}(sell|buy)|whoever is selling|trading against|counterpart",
    "attributes a lost tie-break to speed": r"(faster|quicker|speed|first)|random (draw|selection|tie)|outcompeted|beat me to",
    "mentions the fixed cost": r"fixed cost|break even",
}

WHY_PATTERNS = {
    "own expected value": r"expected (value|dividend)|EV\b|my (value|valuation)",
    "dominance": r"above my (max|highest|best)|below my (min|lowest|worst)|risk-?free|guaranteed|regardless|either way|no matter",
    "price as a signal about the state": r"signal|indicat|suggest|imply|reveal|infer|points to",
    "names the clue": r"\bclue\b|my card|lettered|blank",
    "the counterparty may know something": r"insider|informed|they know|someone knows|may know|might know",
}


def sec_notes(paths):
    """Keyword incidence over the private notes and the broadcast justifications.

    Incidence, not classification: a note can match several patterns and the shares do not
    sum to 1. The number that matters here is the one that is near zero.
    """
    notes, why, reasoning = [], [], 0
    adv = re.compile(NOTE_PATTERNS["adverse selection / picked off"], re.I)
    adv_in_reasoning = 0
    for path in paths:
        for mkt, run, per in periods(path):
            notes += [n["text"] for n in per["notes"] if n.get("text")]
            why += [w["why"] for w in per["why"]]
        for e in load(path, ("model_turn",)):
            if e["payload"].get("purpose") != "turn":
                continue
            reasoning += 1
            if adv.search(e["payload"].get("reasoning") or ""):
                adv_in_reasoning += 1

    print(f"=== private notes (n={len(notes)}) ===")
    for k, p in NOTE_PATTERNS.items():
        r = re.compile(p, re.I)
        h = sum(1 for t in notes if r.search(t))
        print(f"  {h / len(notes):6.1%}  n={h:5d}  {k}")

    print(f"\n=== broadcast justifications (n={len(why)}) ===")
    for k, p in WHY_PATTERNS.items():
        r = re.compile(p, re.I)
        h = sum(1 for t in why if r.search(t))
        print(f"  {h / len(why):6.1%}  n={h:5d}  {k}")

    if reasoning:
        note_hits = sum(1 for t in notes if adv.search(t))
        print(f"\n=== adverse selection: raised in the moment, never written down ===")
        print(f"  in reasoning traces: {adv_in_reasoning / reasoning:5.1%}  ({adv_in_reasoning}/{reasoning})")
        print(f"  in private notes:    {note_hits / len(notes):5.2%}  ({note_hits}/{len(notes)})")


def dump(paths, outdir):
    """Write reasoning / notes / broadcast text to three JSONL files, context attached.

    The reasoning file is large — ~9 KB per turn — and exists so the qualitative reading
    can be grepped instead of re-parsing 1.5 GB of logs.
    """
    import os
    os.makedirs(outdir, exist_ok=True)
    with open(f"{outdir}/reasoning.jsonl", "w") as fr, \
         open(f"{outdir}/notes.jsonl", "w") as fn, \
         open(f"{outdir}/why.jsonl", "w") as fw:
        for path in paths:
            ev = load(path)
            start = next((e["payload"] for e in ev if e["type"] == "session_start"), None)
            if start is None:
                continue
            mkt = MARKETS[start.get("market", 3)]
            names = start.get("seat_names") or {}
            run = (start.get("config") or {}).get("run_name") or path
            vbar = max(mkt.prior_ev.values())
            cur, pending = None, None
            for e in ev:
                t = e["type"]
                if t == "period_start":
                    p = e["payload"]
                    card = next((c for c in (p.get("cards") or {}).values() if c), None)
                    pr, _ = mkt.theory_at(p["info"], p["state"], e["period"], card)
                    cur = {**p, "re": pr["RE"], "side": None if p["info"] == "none" else
                           ("buy" if pr["RE"] > vbar else "sell")}
                elif cur is None:
                    continue
                elif t == "model_turn" and e["payload"].get("purpose") == "turn":
                    pending = e["payload"]
                elif t == "agent_view" and pending is not None:
                    ctx = {"run": run, "market": mkt.number, "period": e["period"],
                           "round": e["round"], "seat": e["seat"],
                           "name": names.get(e["seat"], e["seat"]),
                           "type": mkt.seat_type[e["seat"]], "info": cur["info"],
                           "state": cur["state"], "side": cur["side"], "re": cur["re"],
                           "informed": cur["cards"].get(e["seat"]) is not None}
                    fr.write(json.dumps({**ctx, **e["payload"],
                                         "reasoning": pending.get("reasoning") or "",
                                         "completion": pending.get("completion") or ""},
                                        ensure_ascii=False) + "\n")
                    pending = None
                elif t == "reflection":
                    fn.write(json.dumps(
                        {"run": run, "market": mkt.number, "period": e["period"],
                         "seat": e["seat"], "name": names.get(e["seat"], e["seat"]),
                         "type": mkt.seat_type[e["seat"]], "info": cur["info"],
                         "state": cur["state"], "side": cur["side"],
                         "informed": cur["cards"].get(e["seat"]) is not None,
                         "kind": e["payload"].get("kind"),
                         "text": e["payload"].get("text") or ""}, ensure_ascii=False) + "\n")
                elif t == "broadcast":
                    q = e["payload"].get("quote")
                    for r in e["payload"].get("responses") or []:
                        if not r.get("why"):
                            continue
                        fw.write(json.dumps(
                            {"run": run, "market": mkt.number, "period": e["period"],
                             "seat": r["seat"], "info": cur["info"], "state": cur["state"],
                             "side": cur["side"], "quote": q, "response": r.get("response"),
                             "why": r["why"],
                             "informed": cur["cards"].get(r["seat"]) is not None},
                            ensure_ascii=False) + "\n")
    print(f"wrote reasoning.jsonl, notes.jsonl, why.jsonl to {outdir}")


def sec_converge(paths):
    """Belief in the TRUE state by round, split by whether the agent held a card.

    The uninformed series is the observable the paper could not have — footnote 4 says
    "even though individuals were trained, we still had no way of knowing their subjective
    probabilities." Round 1 is not a clean baseline: by the twelfth seat's turn eleven
    quotes have already been made, so the within-period drift below understates.
    """
    print("=== belief in the true state, by round, insider periods ===")
    print(f"{'mkt':>4} {'side':>5} {'group':>6} {'r1':>7} {'r2':>7} {'r3':>7} {'n(r1)':>6}")
    rows = [v for v in views(paths, info="insider")]
    for m in sorted({v["market"] for v in rows}):
        for side in ("buy", "sell"):
            for inf in (True, False):
                cells, n1 = [], 0
                for rnd in (1, 2, 3):
                    xs = [v["posterior"][v["state"]] for v in rows
                          if v["market"] == m and v["side"] == side
                          and v["informed"] == inf and v["round"] == rnd]
                    if rnd == 1:
                        n1 = len(xs)
                    cells.append(f"{mean(xs):7.3f}" if xs else "      -")
                if not n1:
                    continue
                print(f"{m:>4} {side:>5} {'ins' if inf else 'unin':>6} "
                      + " ".join(cells) + f" {n1:>6}")

    print("\n  uninformed within-period drift (last stated belief - first, true state)")
    for m in sorted({v["market"] for v in rows}):
        for side in ("buy", "sell"):
            first, last = {}, {}
            for v in sorted((v for v in rows if v["market"] == m and v["side"] == side
                             and not v["informed"]),
                            key=lambda v: (v["run"], v["period"], v["round"])):
                k = (v["run"], v["period"], v["seat"])
                first.setdefault(k, v["posterior"][v["state"]])
                last[k] = v["posterior"][v["state"]]
            d = [last[k] - first[k] for k in first]
            if len(d) < 20:
                continue
            print(f"    market {m} {side:>4}: {mean(d):+.3f}  n={len(d)}  "
                  f"rose in {sum(1 for x in d if x > 0) / len(d):.0%}")


# An uninformed agent, in a real insider period, that names an insider AND cites its own
# notes and still reports `prior`. Counted because the two verbatim cases in the doc pull
# in opposite directions and the frequency is what says whether either is typical.
_DETECTS = r"(might|may|probably|likely) (have|has|hold)s? (a |an )?(clue|Y clue|X clue)|has a clue|is informed|knows the dividend"
_CITES_NOTE = r"(my|our) notes? (say|said|says|from|indicate|warn)|notes? from (year|past)|according to my note"


def sec_override(paths):
    print("=== carried notes standing against a live inference ===")
    det, cite = re.compile(_DETECTS, re.I), re.compile(_CITES_NOTE, re.I)
    n = both = 0
    for path in paths:
        # Read the log directly rather than through `periods`: a trace has to be paired
        # with the view it produced, and the pairing is positional — the `agent_view` that
        # follows a `purpose: turn` model_turn is that turn's parsed reply.
        ev = load(path, ("session_start", "period_start", "agent_view", "model_turn"))
        start = next((e["payload"] for e in ev if e["type"] == "session_start"), None)
        if start is None:
            continue
        mkt = MARKETS[start.get("market", 3)]
        cur, pending = None, None
        for e in ev:
            if e["type"] == "period_start":
                cur = e["payload"]
            elif cur is None:
                continue
            elif e["type"] == "model_turn" and e["payload"].get("purpose") == "turn":
                pending = e["payload"].get("reasoning") or ""
            elif e["type"] == "agent_view" and pending is not None:
                informed = (cur.get("cards") or {}).get(e["seat"]) is not None
                if cur["info"] == "insider" and not informed:
                    n += 1
                    if (e["payload"].get("basis") == "prior"
                            and det.search(pending) and cite.search(pending)):
                        both += 1
                pending = None
    print(f"  uninformed turns in insider periods: {n}")
    print(f"  of those, report `prior` while naming an insider and citing own notes: {both}")


SECTIONS = {"basis": sec_basis, "cliff": sec_cliff, "fixpoint": sec_fixpoint,
            "pnl": sec_pnl, "drift": sec_drift, "converge": sec_converge,
            "notes": sec_notes, "override": sec_override}


def main(argv):
    only, outdir, paths = list(SECTIONS), None, []
    it = iter(range(len(argv)))
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--only":
            i += 1
            only = argv[i].split(",")
        elif a == "--dump":
            i += 1
            outdir = argv[i]
        else:
            paths.append(a)
        i += 1
    if not paths:
        print(__doc__)
        return 1
    if outdir:
        dump(paths, outdir)
        return 0
    for name in only:
        if name not in SECTIONS:
            print(f"unknown section {name!r}; have {', '.join(SECTIONS)}", file=sys.stderr)
            return 1
        SECTIONS[name](paths)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
