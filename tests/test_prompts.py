"""Prompt content guards.

These are the tests that protect the experiment's validity. A prompt that names the
theory, quotes the prior as a number, or leaks another agent's dividends would make the
whole run meaningless — and it would do so silently.

Every guard runs against ALL FIVE markets. They differ in the things these guards are
about: nine investors instead of twelve, a prior of 1/3 or a three-way split instead of
.4, a third state, a clue that is a row of marks instead of a letter, and one market whose
subjects could not deduce that dividends stay constant. A guard that only ever saw market
3 would pass while another market's prompt said something false.
"""

from __future__ import annotations

import itertools

import pytest

from ps1982.config import Rules
from ps1982.markets import MARKETS
from ps1982.params import SEAT_NAMES, SEATS, SEAT_TYPE
from ps1982.prompts import (build_brief, build_broadcast_brief, broadcast_system_prompt,
                            coerce_broadcast, coerce_turn, reflect_system_prompt,
                            system_prompt, validate)

RULES = Rules()
M3 = MARKETS[3]
EMPTY_BOOK = {"bid": None, "ask": None, "spread": None}
# Agents address each other by name; S01..S12 must never appear in a prompt.
NAMES = {s: n for s, n in zip(SEATS, SEAT_NAMES)}

# (market, seat) for every seat of every market — 57 pairs, not 12.
ALL_SEATS = [(m, s) for m in MARKETS.values() for s in m.seats]
ALL_MARKETS = list(MARKETS.values())


def _ids(pairs):
    return [f"m{m.number}-{s}" for m, s in pairs]


def _brief(**kw):
    args = dict(market=M3, seat="S01", period=3, round_no=1, turn_seq=1, info="insider", card="Y",
                certs=2, cash=10_000, book=EMPTY_BOOK, market_log=[], reflections=[],
                history=[], not_selected=[], names=NAMES, rules=RULES)
    args.update(kw)
    return build_brief(**args)


def _all_prompts(market, seat):
    """Turn, broadcast and reflection. A guard that checked only one would miss the
    others, and the reflection prompt is exactly where the mechanism block went missing
    once before."""
    return "\n".join([system_prompt(seat, RULES, market),
                       broadcast_system_prompt(seat, RULES, market),
                       reflect_system_prompt(seat, market)])


# ---------------------------------------------------------------- forbidden language


@pytest.mark.parametrize("market,seat", ALL_SEATS, ids=_ids(ALL_SEATS))
def test_no_probability_language_anywhere(market, seat):
    """The paper is explicit that subjects were trained on the bingo cage as a mechanism
    and that probability language stayed out of the instructions.

    Market 1 is the sharp case: its clue is genuinely probabilistic, and the temptation
    is to explain it with a likelihood. It has to be two boxes of chips instead.
    """
    lowered = _all_prompts(market, seat).lower()
    # "likely" is NOT on this list: the paper's own turn instruction says "There are
    # likely to be many quotes that are not accepted", which is English about the market,
    # not probability language about the dividend. The words that matter are the ones that
    # would hand an agent the inference the experiment is testing for.
    for word in ("probability", "probabilities", "probable", "likelihood",
                 "expected value", "bayes", "chance", "odds", "random sample"):
        assert word not in lowered, f"market {market.number} {seat} contains {word!r}"


@pytest.mark.parametrize("market,seat", ALL_SEATS, ids=_ids(ALL_SEATS))
def test_no_theory_leaks(market, seat):
    lowered = _all_prompts(market, seat).lower()
    for word in ("rational expectation", "equilibrium", "prior information model",
                 "insider", "efficiency"):
        assert word not in lowered, f"market {market.number} {seat} contains {word!r}"


@pytest.mark.parametrize("market", ALL_MARKETS, ids=lambda m: f"m{m.number}")
def test_prior_is_never_stated_as_a_number(market):
    """The prior exists for the agent ONLY as a cage of balls, never as a figure."""
    text = system_prompt(market.seats[0], RULES, market)
    for token in ("0.4", "0.6", "0.35", "0.25", "1/3", "2/3", "40%", "60%", "33%"):
        assert token not in text, f"market {market.number} states the prior as {token!r}"
    assert f"{market.bingo_total} balls numbered 1 through {market.bingo_total}" in text
    # ...and the cage must partition into exactly the market's states
    for state, lo, hi in market.cage_ranges:
        span = f"is numbered {lo}" if lo == hi else f"is numbered {lo} through {hi}"
        assert span in text, f"market {market.number}: missing {span}"
        assert f"the {state}-dividend is paid" in text


@pytest.mark.parametrize("market,seat", ALL_SEATS, ids=_ids(ALL_SEATS))
def test_only_your_own_dividends_appear(market, seat):
    """An agent learns its own amounts and nobody else's (design doc §3.3)."""
    text = system_prompt(seat, RULES, market)
    mine = market.dividends[market.seat_type[seat]]
    for v in mine.values():
        assert f"{v} francs per certificate" in text
    for t, d in market.dividends.items():
        if t == market.seat_type[seat]:
            continue
        for v in d.values():
            if v in mine.values():
                continue
            assert f"{v} francs per certificate" not in text, \
                f"market {market.number} {seat} leaks type {t}'s {v}"


@pytest.mark.parametrize("market", ALL_MARKETS, ids=lambda m: f"m{m.number}")
def test_number_of_types_is_not_disclosed_but_market_size_is(market):
    text = system_prompt(market.seats[0], RULES, market).lower()
    assert "three types" not in text and "type i" not in text
    word = {9: "nine", 12: "twelve"}[market.n_agents]
    assert f"{word} investors" in text, f"market {market.number} should say {word}"
    wrong = "twelve" if word == "nine" else "nine"
    assert f"{wrong} investors" not in text


# ---------------------------------------------------------------- required content


@pytest.mark.parametrize("market", ALL_MARKETS, ids=lambda m: f"m{m.number}")
def test_common_knowledge_facts_are_stated(market):
    """Design doc §3.2 — human subjects could deduce these from the physical setup.

    The third fact is per-market: "agents could deduce in all but market 1 that the
    dividend values for every agent remained constant from period to period", so market 1
    must NOT be told it.
    """
    text = system_prompt(market.seats[0], RULES, market)
    assert "how many investors receive a clue card that is not blank" in text
    assert "carries the SAME" in text
    constant = "stay the same in every year" in text
    assert constant == (market.number != 1), \
        f"market {market.number}: constant-dividends fact should be {market.number != 1}"


@pytest.mark.parametrize("market", ALL_MARKETS, ids=lambda m: f"m{m.number}")
def test_period_count_matches_the_market(market):
    text = system_prompt(market.seats[0], RULES, market)
    assert f"{market.n_periods} market years" in text


@pytest.mark.parametrize("market", ALL_MARKETS, ids=lambda m: f"m{m.number}")
def test_exchange_rate_is_the_market_s_own_and_is_private(market):
    text = system_prompt(market.seats[0], RULES, market)
    assert f"${market.franc_to_usd}" in text and "Do not reveal this number" in text


@pytest.mark.parametrize("market", ALL_MARKETS, ids=lambda m: f"m{m.number}")
def test_communication_ban_is_stated(market):
    assert "not to communicate with any other" in system_prompt(market.seats[0], RULES,
                                                                market)


# ---------------------------------------------------------------- clue card form


@pytest.mark.parametrize("market", ALL_MARKETS, ids=lambda m: f"m{m.number}")
def test_clue_card_form_matches_the_market(market):
    """Markets 2-5 hand out a letter. Market 1 hands out a row of ten 0/1 marks, and an
    agent told "a letter" would be reasoning about a card it will never see."""
    text = system_prompt(market.seats[0], RULES, market)
    if market.imperfect:
        assert "a row of 10 marks" in text
        assert "Box X holds 5 chips: 4 marked 0 and 1 marked 1" in text
        assert "Box Y holds 5 chips: 3 marked 0 and 2 marked 1" in text
        assert "PUT BACK" in text                    # with replacement
        assert "always correct" not in text          # it is NOT
    else:
        assert "always correct" in text
        for s in market.states:
            assert f"the letter {s}" in text
        assert "chips" not in text


def test_market_5_offers_three_letters_and_a_blank():
    text = system_prompt("S01", RULES, MARKETS[5])
    assert "one of four things" in text
    for s in ("X", "Y", "Z"):
        assert f"the letter {s}" in text


def test_two_state_markets_offer_two_letters_and_a_blank():
    for n in (2, 3, 4):
        text = system_prompt("S01", RULES, MARKETS[n])
        assert "one of three things" in text
        assert "the letter Z" not in text


# ---------------------------------------------------------------- reply schema


@pytest.mark.parametrize("market", ALL_MARKETS, ids=lambda m: f"m{m.number}")
def test_posterior_schema_covers_every_state(market):
    text = system_prompt(market.seats[0], RULES, market)
    for s in market.states:
        assert f'"{s}": <number between 0 and 1>' in text
    if len(market.states) == 2:
        assert '"Z"' not in text
    assert f"the {'three' if len(market.states) == 3 else 'two'} numbers must sum to 1" in text


# ---------------------------------------------------------------- improvement rule


def test_improvement_rule_text_follows_the_config():
    on = system_prompt("S01", Rules(price_improvement=True), M3)
    off = system_prompt("S01", Rules(price_improvement=False), M3)
    assert "STRICTLY HIGHER" in on and "STRICTLY HIGHER" not in off
    assert "replaces the standing bid whatever its price" in off


def test_brief_states_the_improvement_constraint():
    book = {"bid": {"seat": "S03", "price": 305}, "ask": {"seat": "S09", "price": 340},
            "spread": 35}
    text = _brief(book=book)
    assert "Spread: 35" in text
    assert "strictly above 305" in text and "strictly below 340" in text


def test_brief_states_binding_constraints():
    text = _brief(certs=0)
    assert "You hold no certificates" in text


def test_brief_forbids_accepting_your_own_quote():
    book = {"bid": None, "ask": {"seat": "S01", "price": 340}, "spread": None}
    assert "your own; you may not accept it" in _brief(book=book)


# ---------------------------------------------------------------- clue card wording


def test_blank_card_says_nothing():
    text = _brief(card=None)
    assert "BLANK" in text
    assert "This year no investor" not in text     # announcement is off by default


def test_no_info_announcement_is_a_treatment_switch():
    """§14.4. The faithful baseline says nothing: market 3's subjects were not told how
    many investors held a lettered card."""
    off = _brief(card=None, info="none", rules=Rules(announce_no_info_period=False))
    on = _brief(card=None, info="none", rules=Rules(announce_no_info_period=True))
    assert "no investor has received a lettered clue card" not in off
    assert "no investor has received a lettered clue card" in on


def test_lettered_card_is_stated_as_certain():
    assert "The Y-dividend WILL" in _brief(card="Y")


# ---------------------------------------------------------------- market log


def test_market_log_window_truncates():
    log = [{"seq": i, "seat": "S01", "side": "bid", "price": 100 + i, "outcome": "posted"}
           for i in range(1, 11)]
    full = _brief(market_log=log)
    windowed = _brief(market_log=log, rules=Rules(market_log_window=4))
    assert "101" in full and "101" not in windowed
    assert "110" in windowed and "most recent 4 of 10" in windowed


def test_broadcast_brief_explains_which_way_the_trade_goes():
    kw = dict(seat="S09", period=3, info="insider", card=None, certs=2, cash=10_000,
              book=EMPTY_BOOK, market_log=[], reflections=[], history=[],
              not_selected=[], names=NAMES, rules=RULES)
    bid = build_broadcast_brief(market=M3, quote={"seat": "S01", "side": "bid", "price": 300}, **kw)
    ask = build_broadcast_brief(market=M3, quote={"seat": "S01", "side": "ask", "price": 300}, **kw)
    assert "YOU SELL" in bid and "YOU BUY" in ask


# ---------------------------------------------------------------- reply coercion


def test_turn_reply_accepts_clean_json():
    data = coerce_turn({"posterior": {"X": 0.72, "Y": 0.28}, "reservation_buy": 310,
                        "reservation_sell": 340, "basis": "price",
                        "action": {"type": "quote", "side": "bid", "price": 310}},
                       elicit_beliefs=True)
    assert validate("turn", data) == []


@pytest.mark.parametrize("raw,expected", [
    ({"type": "quote", "side": "BID", "price": "310"}, ("quote", "bid", 310)),
    ({"type": "quote", "side": "buy", "price": 310.0}, ("quote", "bid", 310)),
    ({"type": "quote", "side": "sell", "price": 310}, ("quote", "ask", 310)),
    ("no_quote", ("no_quote", None, None)),
])
def test_action_coercion(raw, expected):
    out = coerce_turn({"action": raw}, elicit_beliefs=False)["action"]
    assert (out.get("type"), out.get("side"), out.get("price")) == expected


def test_posterior_is_renormalized():
    """Models emit percentages, or two numbers that miss 1.0 slightly."""
    out = coerce_turn({"posterior": {"X": 72, "Y": 28}, "action": {"type": "no_quote"}},
                      elicit_beliefs=True)
    assert out["posterior"] == {"X": 0.72, "Y": 0.28}


def test_posterior_completes_a_missing_side():
    out = coerce_turn({"posterior": {"X": 0.3}, "action": {"type": "no_quote"}},
                      elicit_beliefs=True)
    assert out["posterior"] == {"X": 0.3, "Y": 0.7}


def test_fractional_price_is_rejected_not_rounded():
    out = coerce_turn({"action": {"type": "quote", "side": "bid", "price": 310.5}},
                      elicit_beliefs=False)
    assert "price" not in out["action"]
    assert validate("turn_no_beliefs", out) != []      # a quote without a price is invalid


def test_broadcast_coercion():
    for raw, want in ((True, "accept"), ("YES", "accept"), ("Decline", "decline"),
                      ("no", "decline")):
        assert coerce_broadcast({"response": raw})["response"] == want


def test_invalid_basis_fails_validation():
    data = coerce_turn({"posterior": {"X": 0.5, "Y": 0.5}, "reservation_buy": 1,
                        "reservation_sell": 1, "basis": "vibes",
                        "action": {"type": "no_quote"}}, elicit_beliefs=True)
    assert validate("turn", data) != []


# ---------------------------------------------------------------- market log wording


def test_market_log_names_buyer_and_seller_not_just_the_quote_side():
    """Accepting a standing BID means the acceptor SOLD. A log that only shows the quote's
    side would read exactly backwards, so both roles are spelled out."""
    log = [{"seq": 6, "seat": "S10", "action": "accept_standing", "side": "bid",
            "price": 200, "outcome": "traded", "buyer": "S04", "seller": "S10"}]
    text = _brief(market_log=log)
    assert "accepted the standing bid" in text
    assert f"{NAMES['S10']} sold to {NAMES['S04']}" in text


def test_market_log_wording_by_outcome():
    base = {"seq": 1, "seat": "S03", "action": "quote", "side": "bid", "price": 200}
    posted = _brief(market_log=[{**base, "outcome": "posted", "buyer": None, "seller": None}])
    assert "no one accepted; it is now the standing quote" in posted
    sup = _brief(market_log=[{**base, "outcome": "superseded", "buyer": None, "seller": None}])
    assert "replaced by a later quote" in sup
    crossed = _brief(market_log=[{**base, "outcome": "crossed_auto",
                                  "buyer": "S03", "seller": "S09"}])
    assert f"crossed the standing quote; {NAMES['S09']} sold to {NAMES['S03']}" in crossed


# ---------------------------------------------------------------- names and memory


@pytest.mark.parametrize("seat", SEATS)
def test_no_seat_id_ever_reaches_a_prompt(seat):
    """S01..S12 is a backend label. The numbering encodes structure no subject had: the
    types run in blocks and the insiders are every first-and-second of four."""
    text = (system_prompt(seat, RULES, M3, NAMES[seat])
            + broadcast_system_prompt(seat, RULES, M3, NAMES[seat])
            + _brief(seat=seat, market_log=[
                {"seq": 1, "seat": "S04", "action": "quote", "side": "bid", "price": 200,
                 "outcome": "traded", "buyer": "S04", "seller": "S11"}]))
    for s in SEATS:
        assert s not in text, f"{s} leaked into a prompt"
    assert NAMES[seat] in text


def test_notes_are_split_by_kind_and_dated():
    notes = [{"kind": "period_end", "period": 2, "round": 0, "at": None, "text": "year two"},
             {"kind": "trade_feedback", "period": 3, "round": 1,
              "at": "after you sold one certificate at 174", "text": "sold high"}]
    text = _brief(reflections=notes)
    assert "== YOUR NOTES FROM PAST YEAR-ENDS ==" in text
    assert "(year 2) year two" in text
    assert "== YOUR NOTES AFTER RECENT TRADES ==" in text
    assert "(year 3, round 1, after you sold one certificate at 174) sold high" in text


def test_missed_acceptance_says_it_lost_the_draw_without_the_count():
    """The agent is told another investor was chosen — a subject who called out an
    acceptance and watched someone else get it would know that. It is NOT told how many
    accepted: that count is the latent demand curve (design doc §0.2)."""
    ns = [{"period": 5, "round": 2, "seq": 7, "quote_seat": "S07", "side": "bid",
           "price": 175, "why": "175 clears my reservation.", "reason": "not_drawn"}]
    text = _brief(not_selected=ns)
    assert "you would have sold one certificate" in text
    assert "175 clears my reservation." in text          # its own words, else no trace
    assert "the random draw chose them instead of you" in text
    for leak in ("2 other", "two other", "3 investors", "how many"):
        assert leak not in text


def test_could_not_settle_is_worded_differently_from_losing_the_draw():
    base = {"period": 5, "round": 2, "seq": 7, "quote_seat": "S07", "side": "ask",
            "price": 175, "why": None}
    drawn = _brief(not_selected=[{**base, "reason": "not_drawn"}])
    unable = _brief(not_selected=[{**base, "reason": "could_not_settle"}])
    assert "random draw chose them instead of you" in drawn
    assert "not included in the draw" in unable
    assert "you would have bought one certificate" in unable


@pytest.mark.parametrize("seat", SEATS)
def test_reflect_prompt_carries_the_mechanism(seat):
    """A note is durable memory, so an agent writing one needs the same market knowledge
    it decides with. Without the bingo cage block it can only assume 50/50 — measured on
    the probe run, which is how this was found."""
    text = reflect_system_prompt(seat, M3, NAMES[seat])
    assert "40 balls numbered 1 through 40" in text
    assert "is numbered 1 through 16" in text and "is numbered 17 through 40" in text
    mine = M3.dividends[SEAT_TYPE[seat]]
    assert f"{mine['X']} francs per certificate" in text
    for s in SEATS:
        assert s not in text
    lowered = text.lower()
    for word in ("probability", "expected value", "equilibrium"):
        assert word not in lowered
