"""Post-hoc metrics (design doc §11) against hand-computed values."""

from __future__ import annotations

from ps1982.markets import MARKETS

M3 = MARKETS[3]   # every fixture below uses market 3's roster
from ps1982.metrics import price_discovery_by_informed_side  # noqa: F401
from ps1982.metrics import (RunData, compute, efficiency, insider_profit_ratio,
                            price_changes_toward_re, table8_insider_involvement,
                            potential_demand, wrong_hands)
from ps1982.params import (INSIDERS, MARKET_SUPPLY, SEATS, SEAT_TYPE, benchmark_values,
                           holder_seats, no_trade_holdings, re_holdings)


# ---------------------------------------------------------------- benchmark values
# Hand-computed from Table 2's market-3 dividends (400/100, 300/150, 125/175):
#   state X  RE = 24 x 400 = 9600   no-trade = 8x400 + 8x300 + 8x125 = 6600
#   state Y  RE = 24 x 175 = 4200   no-trade = 8x100 + 8x150 + 8x175 = 3400
#   no info  RE = 24 x 220 = 5280   no-trade = 8x220 + 8x210 + 8x155 = 4680


def test_benchmark_values_match_hand_computation():
    assert benchmark_values("insider", "X") == {"re": 9600.0, "no_trade": 6600.0}
    assert benchmark_values("insider", "Y") == {"re": 4200.0, "no_trade": 3400.0}
    assert benchmark_values("all", "X") == {"re": 9600.0, "no_trade": 6600.0}
    assert benchmark_values("none", "Y") == {"re": 5280.0, "no_trade": 4680.0}


def test_re_allocation_is_the_predicted_type():
    h = re_holdings("insider", "Y")
    assert sum(h.values()) == MARKET_SUPPLY
    assert {s for s, n in h.items() if n} == set(holder_seats("III"))
    assert set(re_holdings("insider", "X").keys()) == set(SEATS)
    assert {s for s, n in re_holdings("insider", "X").items() if n} == set(holder_seats("I"))


def test_no_trade_is_the_endowment():
    assert set(no_trade_holdings().values()) == {2}


# ---------------------------------------------------------------- E and TE


def _period(state="Y", info="insider", holdings=None, **kw):
    holdings = holdings or {s: 2 for s in SEATS}
    results = {s: {"certs": n, "type": SEAT_TYPE[s], "profit": 0,
                   "insider": s in INSIDERS} for s, n in holdings.items()}
    return {"period": 1, "state": state, "info": info, "results": results,
            "trades": [], "actions": [], "books": [], "views": [], "violations": [],
            "broadcasts": [], "cards": {s: (state if s in INSIDERS else None) for s in SEATS},
            **kw}


def test_efficiency_of_the_re_allocation_is_100():
    per = _period(holdings=re_holdings("insider", "Y"))
    e = efficiency(M3, per)
    assert e["actual"] == 4200.0 and e["E_pct"] == 100.0 and e["TE_pct"] == 100.0


def test_trading_efficiency_is_zero_when_nothing_trades():
    """This is exactly why the paper introduced TE: E is flattering at the endowment."""
    e = efficiency(M3, _period())
    assert e["actual"] == 3400.0
    assert round(e["E_pct"], 2) == round(100 * 3400 / 4200, 2)
    assert e["TE_pct"] == 0.0


def test_trading_efficiency_goes_negative_when_trade_makes_things_worse():
    """All 24 units to type I in a Y period: 24 x 100 = 2400, below the endowment."""
    holdings = {s: (6 if SEAT_TYPE[s] == "I" else 0) for s in SEATS}
    e = efficiency(M3, _period(holdings=holdings))
    assert e["actual"] == 2400.0
    assert e["TE_pct"] == 100.0 * (2400 - 3400) / (4200 - 3400) == -125.0


def test_efficiency_in_a_no_information_period_uses_the_prior():
    holdings = {s: (6 if SEAT_TYPE[s] == "I" else 0) for s in SEATS}
    e = efficiency(M3, _period(state="Y", info="none", holdings=holdings))
    assert e["actual"] == 5280.0 and e["E_pct"] == 100.0


# ---------------------------------------------------------------- table 5 / 6


def test_wrong_hands_separates_the_two_models():
    """In a Y insider period PI says the UNINFORMED type-I agents hold, RE says type III.
    An allocation matching one is maximally wrong for the other."""
    per = _period(holdings=re_holdings("insider", "Y"))
    wh = wrong_hands(M3, per)
    assert wh["RE"]["in_wrong_hands"] == 0
    assert wh["PI"]["in_wrong_hands"] == MARKET_SUPPLY


def test_insider_profit_ratio():
    per = _period()
    for s, r in per["results"].items():
        r["profit"] = 200 if s in INSIDERS else 100
    assert insider_profit_ratio(M3, per)["ratio_pct"] == 200.0


def test_insider_profit_ratio_is_undefined_without_insiders():
    assert insider_profit_ratio(M3, _period(info="none")) is None


# ---------------------------------------------------------------- price movement


def test_price_changes_toward_re_counts_only_non_zero_moves():
    """RE = 175, PI = 220 in a Y insider period. 220 -> 200 -> 200 -> 180 is two moves,
    both toward RE."""
    per = _period()
    per["trades"] = [{"price": p} for p in (220, 200, 200, 180, 190)]
    out = price_changes_toward_re(M3, [per])
    assert out["all"]["n"] == 3                      # the 200 -> 200 repeat is skipped
    assert out["all"]["toward_re"] == 2 and out["all"]["away_from_re"] == 1
    assert out["separating"]["n"] == 3               # a Y insider period separates


def test_non_separating_periods_are_excluded_from_the_separating_bucket():
    per = _period(state="X")                         # PI = RE = 400
    per["trades"] = [{"price": p} for p in (300, 350)]
    out = price_changes_toward_re(M3, [per])
    assert out["all"]["n"] == 1 and out["separating"]["n"] == 0


# ---------------------------------------------------------------- table 8


def test_table8_tracks_insider_involvement_by_action_number():
    per = _period()
    insider, outsider = INSIDERS[0], [s for s in SEATS if s not in INSIDERS][0]
    per["actions"] = [{"seat": insider, "action": "quote"},
                      {"seat": outsider, "action": "quote"},
                      {"seat": insider, "action": "accept_standing"}]
    t8 = table8_insider_involvement(M3, [per])
    assert t8["1"]["share_insider"] == 1.0
    assert t8["2"]["share_insider"] == 0.0
    assert t8["3"]["share_insider"] == 1.0
    assert round(t8["3"]["cumulative_share_insider"], 4) == round(2 / 3, 4)
    assert t8["18"]["n_periods"] == 0                # the period never got that far


def test_table8_ignores_no_quote_turns():
    per = _period()
    per["actions"] = [{"seat": INSIDERS[0], "action": "no_quote"},
                      {"seat": INSIDERS[0], "action": "quote"}]
    assert table8_insider_involvement(M3, [per])["1"]["share_insider"] == 1.0


# ---------------------------------------------------------------- LLM-only


def test_potential_demand_aggregates_the_losing_acceptors():
    """The whole point: a human oral auction records only the winner, so the number of
    agents WILLING to trade at a price is unobservable there and observable here."""
    per = _period()
    per["broadcasts"] = [
        {"quote": {"seat": "S01", "side": "bid", "price": 300},
         "recipients": ["S02", "S03", "S04"], "n_accept": 3, "winner": "S02",
         "losers": ["S03", "S04"], "responses": []},
        {"quote": {"seat": "S01", "side": "bid", "price": 300},
         "recipients": ["S02", "S03"], "n_accept": 1, "winner": "S02",
         "losers": [], "responses": []},
    ]
    pooled = potential_demand(M3, [per])["pooled"]
    assert len(pooled) == 1
    row = pooled[0]
    assert row["price"] == 300 and row["supply_quotes"] == 2
    # 4 willing sellers across 5 polls — not the 2 trades that actually happened.
    assert row["supply_willing"] == 4 and row["supply_asked"] == 5
    assert row["supply_rate"] == 0.8


def test_supply_and_demand_are_not_pooled():
    """Accepting an ASK means buying, accepting a BID means selling. Pooling the two would
    add willing buyers to willing sellers and call the sum 'demand'."""
    per = _period()
    per["broadcasts"] = [
        {"quote": {"seat": "S01", "side": "ask", "price": 200},
         "recipients": ["S02", "S03"], "n_accept": 2, "winner": "S02", "losers": ["S03"],
         "responses": []},
        {"quote": {"seat": "S05", "side": "bid", "price": 200},
         "recipients": ["S06"], "n_accept": 1, "winner": "S06", "losers": [], "responses": []},
    ]
    row = potential_demand(M3, [per])["pooled"][0]
    assert row["demand_willing"] == 2 and row["demand_quotes"] == 1   # would BUY at 200
    assert row["supply_willing"] == 1 and row["supply_quotes"] == 1   # would SELL at 200


# ---------------------------------------------------------------- discovery by side


def _insider_period(period, state, prices):
    return {"period": period, "state": state, "info": "insider",
            "trades": [{"price": p} for p in prices], "results": None,
            "actions": [], "broadcasts": [], "views": [], "violations": [], "books": []}


def test_discovery_is_1_when_the_price_reaches_re():
    """Market 3 state Y: uninformed level 220, RE 175. A price at 175 is full discovery."""
    r = price_discovery_by_informed_side(M3, [_insider_period(3, "Y", [175, 175])])
    assert r["by_side"]["seller"]["mean_discovery"] == 1.0
    assert r["by_side"]["seller"]["n"] == 1
    assert r["by_side"]["buyer"]["n"] == 0


def test_discovery_is_0_when_the_price_stays_where_the_uninformed_would_put_it():
    r = price_discovery_by_informed_side(M3, [_insider_period(3, "Y", [220, 220])])
    assert r["by_side"]["seller"]["mean_discovery"] == 0.0


def test_the_side_is_decided_by_which_way_re_lies_from_the_uninformed_level():
    """State X's RE (400) is ABOVE the uninformed 220, so the informed want to buy;
    state Y's (175) is below, so they want to sell. This is the whole classification."""
    r = price_discovery_by_informed_side(
        M3, [_insider_period(3, "Y", [200]), _insider_period(4, "X", [300])])
    sides = {d["period"]: d["side"] for d in r["periods"]}
    assert sides == {3: "seller", 4: "buyer"}


def test_the_measured_asymmetry_reproduces():
    """The finding this metric exists for: market 3's X periods price near the uninformed
    level (measured 215-229 against an RE of 400) while its Y periods reach RE."""
    r = price_discovery_by_informed_side(
        M3, [_insider_period(3, "Y", [175]), _insider_period(4, "X", [229])])
    by = r["by_side"]
    assert by["seller"]["mean_discovery"] == 1.0
    assert by["buyer"]["mean_discovery"] < 0.1


def test_non_insider_periods_are_excluded():
    """With everyone informed there is no asymmetry; with no one, nothing to discover."""
    for info in ("none", "all"):
        per = {**_insider_period(3, "Y", [175]), "info": info}
        r = price_discovery_by_informed_side(M3, [per])
        assert r["by_side"]["seller"]["n"] == 0 and r["by_side"]["buyer"]["n"] == 0


def test_market_1_has_no_seller_side_at_all():
    """Both of market 1's states put RE above the uninformed level, so its informed always
    want to buy. It cannot test this asymmetry — worth knowing before reading its result."""
    m = MARKETS[1]
    base = max(m.prior_ev.values())
    assert all(max(m.dividends[t][s] for t in m.types) > base for s in m.states)
