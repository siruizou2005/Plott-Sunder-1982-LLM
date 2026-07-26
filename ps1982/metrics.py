"""Post-hoc metrics (design doc §11), computed from a run's JSONL event log.

Three groups:
  §11.1  the paper's own measures — figure 4, tables 5, 6, 7, 8, and the efficiency
         measures E and TE of section III
  §11.2  measures the standing-quote book makes available and an oral auction does not
  §11.3  measures only an LLM market makes available: elicited beliefs, the stated basis
         of each decision, and the potential demand curve recovered from broadcast votes

Nothing here reads the engine; it reads the log. The log is the single source of truth.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict

from .events import read_events
from .markets import INITIAL_CERTS, MARKETS


def _allocation_value(mkt, holdings: dict[str, int], state: str) -> float:
    """Expected return of an allocation given the state actually realized."""
    return float(sum(n * mkt.dividend(seat, state) for seat, n in holdings.items()))


def _allocation_value_prior(mkt, holdings: dict[str, int]) -> float:
    """Expected return under the prior — the benchmark in a no-information period, where
    'the information in the market' is just the prior (paper §III)."""
    return float(sum(n * mkt.prior_ev[mkt.seat_type[seat]] for seat, n in holdings.items()))


def _benchmarks(mkt, info: str, state: str) -> dict[str, float]:
    """Expected returns of the RE and no-trade allocations: the denominators of E and TE.

    Sanity values for market 3: state X -> RE 9600 / no-trade 6600; state Y -> 4200 / 3400;
    a no-information period -> 5280 / 4680.
    """
    no_trade = {s: INITIAL_CERTS for s in mkt.seats}
    seats = mkt.holder_seats(mkt.theory_at(info, state)[1]["RE"])
    per_seat = mkt.market_supply // len(seats)
    re_alloc = {s: (per_seat if s in seats else 0) for s in mkt.seats}
    if info == "none":
        return {"re": _allocation_value_prior(mkt, re_alloc),
                "no_trade": _allocation_value_prior(mkt, no_trade)}
    return {"re": _allocation_value(mkt, re_alloc, state),
            "no_trade": _allocation_value(mkt, no_trade, state)}

# Which market a run is, and everything derived from it, now arrives as an argument. It
# used to be imported: every efficiency benchmark, theory price and predicted holder was
# market 3's, so scoring any other market produced numbers that looked fine and were
# wrong. `compute` reads the market number out of `session_start` and threads it down.

# The market actions the paper reports in table 8.
TABLE8_ACTIONS = (1, 2, 3, 6, 18)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


class RunData:
    """Everything the metrics need, indexed once."""

    def __init__(self, events: list[dict]) -> None:
        self.events = events
        self.sessions: dict[int, dict] = defaultdict(lambda: {
            "periods": {}, "start": None, "end": None})
        self._index()

    def _index(self) -> None:
        cur = None
        for e in self.events:
            sid = e.get("session", 0)
            s = self.sessions[sid]
            t, p = e["type"], e["period"]
            if t == "session_start":
                s["start"] = e["payload"]
                continue
            if t == "session_end":
                s["end"] = e["payload"]
                continue
            if t == "period_start":
                cur = {
                    "period": p, "state": e["payload"]["state"], "info": e["payload"]["info"],
                    "cards": e["payload"]["cards"], "actions": [], "trades": [],
                    "books": [], "views": [], "violations": [], "broadcasts": [],
                    "results": None,
                }
                s["periods"][p] = cur
                continue
            if cur is None:
                continue
            if t == "action":
                cur["actions"].append({**e["payload"], "seat": e["seat"]})
            elif t == "trade":
                cur["trades"].append(e["payload"])
            elif t == "book":
                cur["books"].append(e["payload"])
            elif t == "agent_view":
                cur["views"].append({**e["payload"], "seat": e["seat"]})
            elif t == "violation":
                cur["violations"].append({**e["payload"], "seat": e["seat"]})
            elif t == "broadcast":
                cur["broadcasts"].append(e["payload"])
            elif t == "period_end":
                cur["results"] = e["payload"]["results"]


# ------------------------------------------------------------------ §11.1 paper measures


def period_prices(mkt, per: dict) -> dict:
    """Mean / first / last trade price, against the two models' predictions (figure 4)."""
    prices = [t["price"] for t in per["trades"]]
    key = (per["info"], per["state"])
    theory = mkt.theory_at(*key, per.get('period'))[0]
    return {
        "period": per["period"], "state": per["state"], "info": per["info"],
        "n_trades": len(prices),
        "mean_price": _mean(prices), "first_price": prices[0] if prices else None,
        "last_price": prices[-1] if prices else None,
        "pi_price": theory["PI"], "re_price": theory["RE"],
        "separating": theory["PI"] != theory["RE"],
    }


def price_changes_toward_re(mkt, periods: list[dict]) -> dict:
    """Of all non-zero price changes within a period, how many moved toward the RE price?

    The paper's own version of this test (section IV) found 284 of 398, 8.5 SD from chance.
    Only separating periods carry information, so they are reported separately.
    """
    tally = {"all": Counter(), "separating": Counter()}
    for per in periods:
        prices = [t["price"] for t in per["trades"]]
        key = (per["info"], per["state"])
        tp = mkt.theory_at(*key, per.get("period"))[0]
        re_p, pi_p = tp["RE"], tp["PI"]
        buckets = ["all"] + (["separating"] if re_p != pi_p else [])
        for a, b in zip(prices, prices[1:]):
            if b == a:
                continue
            toward = abs(b - re_p) < abs(a - re_p)
            for k in buckets:
                tally[k]["toward" if toward else "away"] += 1
    out = {}
    for k, c in tally.items():
        n = c["toward"] + c["away"]
        out[k] = {"toward_re": c["toward"], "away_from_re": c["away"], "n": n,
                  "share_toward_re": (c["toward"] / n) if n else None}
    return out


def wrong_hands(mkt, per: dict) -> dict:
    """Certificates NOT held by the type each model predicts (paper table 5)."""
    if not per["results"]:
        return {}
    key = (per["info"], per["state"])
    out = {}
    for model in ("PI", "RE"):
        want = set(mkt.holder_seats(mkt.theory_at(*key, per.get("period"))[1][model]))
        held_right = sum(r["certs"] for s, r in per["results"].items() if s in want)
        out[model] = {"predicted_holder": mkt.theory_at(*key, per.get("period"))[1][model],
                      "in_right_hands": held_right,
                      "in_wrong_hands": mkt.market_supply - held_right}
    return out


def insider_profit_ratio(mkt, per: dict) -> dict | None:
    """Mean insider profit as a percentage of mean uninformed profit (paper table 6).

    The paper's finding is that this ratio falls toward 100 with repetition: the insiders'
    advantage is competed away as prices come to reveal the state.
    """
    if not per["results"] or per["info"] != "insider":
        return None
    ins = [r["profit"] for s, r in per["results"].items() if r["insider"]]
    unf = [r["profit"] for s, r in per["results"].items() if not r["insider"]]
    mi, mu = _mean(ins), _mean(unf)
    return {"insider_mean": mi, "uninformed_mean": mu,
            "ratio_pct": (100.0 * mi / mu) if (mi is not None and mu) else None}


def re_side_profit_ratio(mkt, per: dict) -> dict | None:
    """Profit of the agents RE says should BUY vs those RE says should SELL (table 7).

    RE says the predicted holders end up holding, so they are the buyers; everyone else
    sells. If agents have learned the price/state correspondence, both sides profit.
    """
    if not per["results"]:
        return None
    key = (per["info"], per["state"])
    buyers = set(mkt.holder_seats(mkt.theory_at(*key, per.get("period"))[1]["RE"]))
    b = [r["profit"] for s, r in per["results"].items() if s in buyers]
    s_ = [r["profit"] for s, r in per["results"].items() if s not in buyers]
    mb, ms = _mean(b), _mean(s_)
    return {"re_buyer_mean": mb, "re_seller_mean": ms,
            "ratio_pct": (100.0 * mb / ms) if (mb is not None and ms) else None}


def efficiency(mkt, per: dict) -> dict | None:
    """E and TE (paper section III).

        E  = value(actual) / value(RE allocation)
        TE = [value(actual) - value(no trade)] / [value(RE) - value(no trade)]

    Both conditioned on the information in the market: the realized state when someone is
    informed, the prior when nobody is. TE is zero when no trading takes place, which is
    why the paper introduced it.
    """
    if not per["results"]:
        return None
    holdings = {s: r["certs"] for s, r in per["results"].items()}
    info, state = per["info"], per["state"]
    actual = (_allocation_value_prior(mkt, holdings) if info == "none"
              else _allocation_value(mkt, holdings, state))
    bench = _benchmarks(mkt, info, state)
    re_v, nt_v = bench["re"], bench["no_trade"]
    denom = re_v - nt_v
    return {"actual": actual, "re": re_v, "no_trade": nt_v,
            "E_pct": 100.0 * actual / re_v if re_v else None,
            "TE_pct": (100.0 * (actual - nt_v) / denom) if denom else None}


def price_discovery_by_informed_side(mkt, periods: list[dict]) -> dict:
    """How much of the distance from the uninformed price to RE the market actually covers,
    split by whether the informed want to BUY or to SELL.

    Not in the paper, and invisible to every measure that is. The paper's separating
    periods are those where RE != PI, so a state in which BOTH models predict the same
    price is dropped from the analysis — yet market 3's state X is exactly such a cell, and
    across three completed runs (two vendors) the price there sat at 229 / 215 / 226
    against a prediction of 400 and an uninformed level of 220. The market did not
    aggregate at all, and nothing in the standard battery would say so.

    The proposed reason is an asymmetry in incentive. When the informed hold an asset worth
    less than the uninformed believe, selling is how they profit, and selling pushes the
    price down toward RE — the information leaks through the act of exploiting it. When the
    asset is worth MORE than the uninformed believe, the informed profit by buying quietly;
    bidding the price up to RE would destroy their own surplus, so they have both the
    motive and the means to keep it near the uninformed level.

    discovery = (price - uninformed_level) / (RE - uninformed_level)
        1.0  price is at RE — full aggregation
        0.0  price is where the uninformed alone would put it — none
    Reported for insider periods only: with everyone informed there is no asymmetry, and
    with no one informed there is nothing to discover.
    """
    base = max(mkt.prior_ev.values())
    out = {"buyer": [], "seller": []}
    detail = []
    for per in periods:
        if per["info"] != "insider" or not per["trades"]:
            continue
        re_p = mkt.theory_at(per["info"], per["state"], per.get("period"))[0]["RE"]
        if abs(re_p - base) < 1e-9:
            continue                      # nothing to discover in this state
        side = "buyer" if re_p > base else "seller"
        price = _mean([t["price"] for t in per["trades"]])
        d = (price - base) / (re_p - base)
        out[side].append(d)
        detail.append({"period": per["period"], "state": per["state"], "side": side,
                       "uninformed_level": round(base, 1), "re": re_p,
                       "mean_price": round(price, 1), "discovery": round(d, 3)})
    return {"by_side": {k: {"n": len(v), "mean_discovery": _mean(v)} for k, v in out.items()},
            "periods": detail}


def table8_insider_involvement(mkt, periods: list[dict]) -> dict:
    """Share of the Nth market action of a period that involved an insider (table 8).

    This is the paper's most direct evidence on WHICH quotes leak information: in markets
    3, 4 and 5 the opening contract lands near the RE price, so something was revealed
    before any trade took place.
    """
    hits: dict[int, list[bool]] = {n: [] for n in TABLE8_ACTIONS}
    cumulative: dict[int, list[float]] = {n: [] for n in TABLE8_ACTIONS}
    for per in periods:
        if per["info"] != "insider":
            continue
        cards = per["cards"]
        acts = [a for a in per["actions"] if a.get("action") != "no_quote"]
        flags = [cards.get(a["seat"]) is not None for a in acts]
        for n in TABLE8_ACTIONS:
            if len(flags) >= n:
                hits[n].append(flags[n - 1])
                cumulative[n].append(sum(flags[:n]) / n)
    return {
        str(n): {"n_periods": len(hits[n]),
                 "share_insider": (sum(hits[n]) / len(hits[n])) if hits[n] else None,
                 "cumulative_share_insider": _mean(cumulative[n])}
        for n in TABLE8_ACTIONS
    }


# ------------------------------------------------------------------ §11.2 book measures


def spread_trajectory(per: dict) -> list[dict]:
    """Spread after every book change, so its narrowing within a period is visible."""
    return [{"i": i, "spread": b["spread"],
             "bid": b["bid"]["price"] if b["bid"] else None,
             "ask": b["ask"]["price"] if b["ask"] else None}
            for i, b in enumerate(per["books"]) if b["spread"] is not None]


def first_quote_information(mkt, per: dict) -> dict | None:
    """How far the period's FIRST quote sits from the RE price, split by whether its author
    was informed. A small distance from an insider is information leaking through a quote
    before any trade happens."""
    acts = [a for a in per["actions"] if a.get("action") == "quote"]
    if not acts:
        return None
    a = acts[0]
    re_p = mkt.theory_at(per["info"], per["state"], per.get("period"))[0]["RE"]
    return {"seat": a["seat"], "side": a["side"], "price": a["price"],
            "insider": per["cards"].get(a["seat"]) is not None,
            "distance_to_re": abs(a["price"] - re_p)}


def quote_survival(per: dict) -> list[int]:
    """How many market actions a standing quote survives before being taken or replaced."""
    out, open_at = [], {}
    for a in per["actions"]:
        seq, side = a.get("seq"), a.get("side")
        if a.get("outcome") == "posted":
            if side in open_at:
                out.append(seq - open_at[side])
            open_at[side] = seq
        elif a.get("outcome") in ("traded", "crossed_auto") and side in open_at:
            out.append(seq - open_at.pop(side))
    return out


def active_vs_passive(periods: list[dict]) -> dict:
    """Do informed agents PROVIDE liquidity (quote) or CONSUME it (accept)?

    The Bloomfield-O'Hara-Saar (2005) question. A reversal within a period — quoting early,
    taking late — is the signature they report.
    """
    tally = defaultdict(Counter)
    for per in periods:
        if per["info"] != "insider":
            continue
        cards = per["cards"]
        for a in per["actions"]:
            act = a.get("action")
            if act not in ("quote", "accept_standing"):
                continue
            who = "insider" if cards.get(a["seat"]) is not None else "uninformed"
            tally[who][act] += 1
    out = {}
    for who, c in tally.items():
        n = c["quote"] + c["accept_standing"]
        out[who] = {"quote": c["quote"], "accept_standing": c["accept_standing"],
                    "share_active": (c["quote"] / n) if n else None}
    return out


def violation_profile(periods: list[dict]) -> dict:
    """Counts by reason and by period. ``no_improvement`` is the interesting one: those are
    the quotes the improvement rule blocked, and they are exactly what a counterfactual
    "no improvement requirement" arm (design doc §14.3) would have allowed."""
    by_reason = Counter()
    by_period = defaultdict(Counter)
    blocked_prices = []
    for per in periods:
        for v in per["violations"]:
            by_reason[v["reason"]] += 1
            by_period[per["period"]][v["reason"]] += 1
            if v["reason"] == "no_improvement":
                blocked_prices.append({"period": per["period"], "seat": v["seat"],
                                       "side": v.get("side"), "price": v.get("price")})
    return {"by_reason": dict(by_reason),
            "by_period": {str(k): dict(v) for k, v in sorted(by_period.items())},
            "no_improvement_attempts": blocked_prices}


# ------------------------------------------------------------------ §11.3 LLM-only


def posterior_convergence(mkt, periods: list[dict]) -> list[dict]:
    """Mean belief in the TRUE state, split by whether the agent held a clue card.

    The uninformed series is the direct observable the paper could not have: footnote 4
    says "even though individuals were trained, we still had no way of knowing their
    subjective probabilities."
    """
    out = []
    for per in periods:
        truth, cards = per["state"], per["cards"]
        groups = defaultdict(list)
        for v in per["views"]:
            post = v.get("posterior") or {}
            if truth not in post:
                continue
            groups["insider" if cards.get(v["seat"]) is not None else "uninformed"].append(
                float(post[truth]))
        out.append({"period": per["period"], "state": truth, "info": per["info"],
                    "insider_mean": _mean(groups["insider"]),
                    "uninformed_mean": _mean(groups["uninformed"]),
                    "n_views": len(per["views"])})
    return out


def basis_drift(periods: list[dict]) -> list[dict]:
    """How the self-reported basis of decisions shifts across periods. A migration from
    ``prior``/``clue`` toward ``price``/``spread`` is agents saying, unprompted, that they
    are reading the state off the market — the RE mechanism describing itself."""
    out = []
    for per in periods:
        c = Counter(v.get("basis") for v in per["views"] if v.get("basis"))
        n = sum(c.values())
        out.append({"period": per["period"],
                    "counts": dict(c),
                    "shares": {k: v / n for k, v in c.items()} if n else {}})
    return out


def belief_action_consistency(mkt, periods: list[dict]) -> dict:
    """Gap between a stated reservation price and the value its stated belief implies.

    A large systematic gap means the elicited beliefs are decoration rather than the input
    to the decision — which would undercut every belief-based reading of the run.
    """
    gaps = []
    for per in periods:
        for v in per["views"]:
            post, rb, rs = v.get("posterior"), v.get("reservation_buy"), v.get("reservation_sell")
            if not post or rb is None or rs is None:
                continue
            d = mkt.dividends[mkt.seat_type[v["seat"]]]
            implied = sum(float(post.get(st, 0)) * d[st] for st in mkt.states)
            gaps.append({"period": per["period"], "seat": v["seat"], "implied": implied,
                         "reservation_buy": rb, "reservation_sell": rs,
                         "gap_buy": rb - implied, "gap_sell": rs - implied})
    return {"n": len(gaps),
            "mean_gap_buy": _mean([g["gap_buy"] for g in gaps]),
            "mean_gap_sell": _mean([g["gap_sell"] for g in gaps]),
            "detail": gaps}


def potential_demand(mkt, periods: list[dict]) -> dict:
    """Latent supply and demand schedules, recovered from broadcast votes.

    Every broadcast records how many agents WOULD have taken a quote at that price, not just
    the one who won the random tie-break. In an oral auction the losers never speak, so this
    is data a human experiment structurally cannot record (design doc §0.2).

    The two sides must NOT be pooled — they measure opposite things:

        an ASK at price p accepted by k agents  ->  k agents would BUY at p   (demand)
        a BID at price p accepted by k agents   ->  k agents would SELL at p  (supply)

    ``*_asked`` is how many feasible counterparties the engine actually polled, which is the
    denominator that makes rates comparable across prices — a high ask excludes everyone who
    cannot afford it, so a raw count would understate demand there.
    """
    def _blank(price: int) -> dict:
        return {"price": price,
                "demand_quotes": 0, "demand_willing": 0, "demand_asked": 0,
                "supply_quotes": 0, "supply_willing": 0, "supply_asked": 0}

    by_price_all: dict[int, dict] = {}
    by_period: dict[int, dict] = defaultdict(dict)
    for per in periods:
        for b in per["broadcasts"]:
            price = b["quote"]["price"]
            kind = "demand" if b["quote"]["side"] == "ask" else "supply"
            for bucket in (by_price_all, by_period[per["period"]]):
                row = bucket.setdefault(price, _blank(price))
                row[f"{kind}_quotes"] += 1
                row[f"{kind}_willing"] += b["n_accept"]
                row[f"{kind}_asked"] += len(b["recipients"])

    def _clean(d: dict) -> list[dict]:
        out = []
        for _, v in sorted(d.items()):
            r = dict(v)
            for k in ("demand", "supply"):
                asked = r[f"{k}_asked"]
                r[f"{k}_rate"] = (r[f"{k}_willing"] / asked) if asked else None
            out.append(r)
        return out

    return {"pooled": _clean(by_price_all),
            "by_period": {str(k): _clean(v) for k, v in sorted(by_period.items())}}


# ------------------------------------------------------------------ assembly


def _market_for(start: dict | None):
    """The Market a session was run as, reconstructed from its own `session_start`.

    Taken from the log rather than assumed, so re-scoring an old run cannot quietly apply
    the wrong market's dividends. Logs written before `market` was recorded are market 3 —
    that is the only market that existed then, so the default is a fact about the past
    rather than a guess. The realized states come from the log too, because a
    `random_prior` run's sequence is a draw and is not recoverable from the market alone.
    """
    from dataclasses import replace
    start = start or {}
    mkt = MARKETS[start.get("market", 3)]
    states, info = start.get("states"), start.get("info")
    if states and info and len(states) == len(info):
        mkt = replace(mkt, sequence_states=tuple(states), sequence_info=tuple(info))
    return mkt


def compute(events: list[dict]) -> dict:
    data = RunData(events)
    out = {"sessions": {}}
    for sid, s in sorted(data.sessions.items()):
        periods = [s["periods"][k] for k in sorted(s["periods"])]
        mkt = _market_for(s["start"])
        out["sessions"][str(sid)] = {
            "meta": {
                "market": mkt.number,
                "sequence_preset": (s["start"] or {}).get("sequence_preset"),
                "seed": (s["start"] or {}).get("seed"),
                "n_periods": len(periods),
                "summary": s["end"],
            },
            "paper": {
                "prices": [period_prices(mkt, p) for p in periods],
                "price_changes_toward_re": price_changes_toward_re(mkt, periods),
                "wrong_hands": {str(p["period"]): wrong_hands(mkt, p) for p in periods},
                "insider_profit_ratio": {str(p["period"]): insider_profit_ratio(mkt, p)
                                         for p in periods},
                "re_side_profit_ratio": {str(p["period"]): re_side_profit_ratio(mkt, p)
                                         for p in periods},
                "efficiency": {str(p["period"]): efficiency(mkt, p) for p in periods},
                "table8": table8_insider_involvement(mkt, periods),
                "discovery_by_informed_side": price_discovery_by_informed_side(
                    mkt, periods),
                "totals": _session_totals(s),
            },
            "book": {
                "spread_trajectory": {str(p["period"]): spread_trajectory(p) for p in periods},
                "first_quote": {str(p["period"]): first_quote_information(mkt, p) for p in periods},
                "quote_survival": {str(p["period"]): quote_survival(p) for p in periods},
                "active_vs_passive": active_vs_passive(periods),
                "violations": violation_profile(periods),
            },
            "llm": {
                "posterior_convergence": posterior_convergence(mkt, periods),
                "basis_drift": basis_drift(periods),
                "belief_action_consistency": belief_action_consistency(mkt, periods),
                "potential_demand": potential_demand(mkt, periods),
            },
        }
    return out


def _session_totals(s: dict) -> dict:
    end = s.get("end") or {}
    totals = end.get("totals") or {}
    ins = [v["francs"] for k, v in totals.items() if v.get("insider")]
    unf = [v["francs"] for k, v in totals.items() if not v.get("insider")]
    return {
        "per_seat": totals,
        "insider_mean_francs": _mean(ins),
        "uninformed_mean_francs": _mean(unf),
        "insider_advantage_pct": (100.0 * _mean(ins) / _mean(unf))
                                 if (ins and unf and _mean(unf)) else None,
        "calls": end.get("calls"),
        "usage": end.get("usage"),
        "cost_usd": end.get("cost_usd"),
        "wall_clock_s": end.get("wall_clock_s"),
    }


def compute_from_file(path: str) -> dict:
    return compute(read_events(path))


def write_metrics(log_path: str, out_path: str | None = None) -> str:
    out_path = out_path or log_path.rsplit(".", 1)[0] + ".metrics.json"
    m = compute_from_file(log_path)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=2)
    return out_path
