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

import hashlib
import itertools
import re

import pytest

from ps1982.config import Config, Rules
from ps1982.markets import MARKETS
from ps1982.params import SEAT_NAMES, SEATS, SEAT_TYPE
from ps1982.prompts import (build_brief, build_broadcast_brief, build_period_end_brief,
                            build_trade_feedback_brief, broadcast_system_prompt,
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
                       reflect_system_prompt(seat, RULES, market)])


# ------------------------------------------------------------------- byte stability
#
# Every session in runs/ was prompted with exact bytes, and three things rest on those
# bytes not moving. The paired comparisons: a treatment session and the baseline it is
# read against must differ ONLY in the treatment, which is the whole claim the disclosure
# arm makes. Prefix caching: DeepSeek keys on the system prompt, which is built once per
# agent and reused for the session (llm_agent.py:64). And reproducibility: a scenario file
# is supposed to describe the run it produced.
#
# Every treatment field in Rules therefore defaults to the value that reproduces the
# baseline, and these digests are what turns that convention into a guarantee. They are
# the acceptance criterion for any prompt edit: a failure means a prompt that has already
# been paid for has changed. Regenerate them ONLY when you intend exactly that, and say so
# in the commit message.
#
# To regenerate: run this file, read the digest out of the assertion message, paste it in.

# Markets whose information design never deals a card to everyone — the ones Config lets
# disclose_structure run on. Derived, so a new market joins the guard automatically.
DISC_NUMBERS = [n for n in sorted(MARKETS) if "all" not in MARKETS[n].sequence_info]

# Two year-end notes and one post-trade note, so the digests cover render_reflections —
# the renderer the memo tier swaps out — and not just the empty-memory placeholder.
FROZEN_NOTES = [
    {"kind": "period_end", "period": 3, "round": 0, "at": None, "text": "year three note"},
    {"kind": "trade_feedback", "period": 4, "round": 2,
     "at": "after you bought one certificate at 250", "text": "bought high"},
    {"kind": "period_end", "period": 4, "round": 0, "at": None, "text": "year four note"},
]


def _prompt_blob(rules: Rules, numbers: list[int]) -> str:
    """Every system prompt of every kind, for every seat of every listed market."""
    out = []
    for n in numbers:
        m = MARKETS[n]
        for s in m.seats:
            out += [system_prompt(s, rules, m, NAMES[s]),
                    broadcast_system_prompt(s, rules, m, NAMES[s]),
                    reflect_system_prompt(s, rules, m, NAMES[s])]
    return "\n".join(out)


def _brief_blob(rules: Rules, numbers: list[int]) -> str:
    """Every user message of every kind, over every information condition a market has.

    All four builders, because the treatments reach them unevenly: _clue_line is in three
    of them and the year-end task in the fourth, and a guard that watched only the turn
    brief would have let the memo tier rewrite a broadcast unnoticed.
    """
    out = []
    for n in numbers:
        m = MARKETS[n]
        # Market 1's card is a row of marks; every other market's is a letter.
        card = "0101010101" if m.imperfect else m.states[0]
        quote = {"side": "bid", "price": 250, "seat": m.seats[1]}
        for s in m.seats:
            for info, c in (("none", None), ("insider", None), ("insider", card),
                            ("all", card)):
                out.append(build_brief(
                    market=m, seat=s, period=5, round_no=1, turn_seq=1, info=info, card=c,
                    certs=2, cash=10_000, book=EMPTY_BOOK, market_log=[],
                    reflections=FROZEN_NOTES, history=[], not_selected=[], names=NAMES,
                    rules=rules))
                out.append(build_broadcast_brief(
                    market=m, seat=s, period=5, quote=quote, info=info, card=c, certs=2,
                    cash=10_000, book=EMPTY_BOOK, market_log=[], reflections=FROZEN_NOTES,
                    history=[], not_selected=[], names=NAMES, rules=rules))
                out.append(build_trade_feedback_brief(
                    market=m, seat=s, period=5, round_no=1, side="buy", price=250,
                    counterparty=m.seats[1], info=info, card=c, certs=2, cash=10_000,
                    book=EMPTY_BOOK, market_log=[], reflections=FROZEN_NOTES, history=[],
                    not_selected=[], names=NAMES, rules=rules))
            out.append(build_period_end_brief(
                market=m, seat=s, period=5, state=m.states[0], certs=2, cash=10_000,
                dividend_paid=500, profit=100, reflections=FROZEN_NOTES, history=[],
                market_log=[], not_selected=[], names=NAMES, rules=rules))
    return "\n".join(out)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


BASELINE_PROMPTS = "0aad73df09002ed7e2e67a91b5b000cc6a48b4d20af8a22788e576bb55acb4c9"
TIER1_PROMPTS = "4abbef9bb71e0ef76afaf7047f0df9d60e8f3587f48850ba5fc3beba8b6cefcf"
BASELINE_BRIEFS = "f017482e7ac41aeec1b3392babceb4ee347f2c07ef8fd3471ccc74f60cc9c33a"
ANNOUNCE_BRIEFS = "bfe0ddc4b062c5cbe0d7254f55acf3ac062134e00b92e09abd121166c42a6dfe"
TIER1_BRIEFS = "4151caea26296227b13b4b0c1d6472621da114caf3eca51d83becdfd5b5e1db4"


def test_byte_stable_baseline_prompts():
    """The prompts every completed baseline session was sent."""
    got = _digest(_prompt_blob(Rules(), sorted(MARKETS)))
    assert got == BASELINE_PROMPTS, f"baseline system prompts changed; digest is {got!r}"


def test_byte_stable_tier1_prompts():
    """The prompts runs/disclosed/ was sent. A ladder rung that perturbs these has
    changed the arm the ladder is measured against."""
    got = _digest(_prompt_blob(Rules(disclose_structure=True), DISC_NUMBERS))
    assert got == TIER1_PROMPTS, f"tier-1 system prompts changed; digest is {got!r}"


def test_byte_stable_baseline_briefs():
    got = _digest(_brief_blob(Rules(), sorted(MARKETS)))
    assert got == BASELINE_BRIEFS, f"baseline briefs changed; digest is {got!r}"


def test_byte_stable_announce_briefs():
    """The §14.4 arm's briefs. disclose_card_years shares its 'no investor has received'
    sentence, so this digest is what stops the two treatments from drifting apart."""
    got = _digest(_brief_blob(Rules(announce_no_info_period=True), sorted(MARKETS)))
    assert got == ANNOUNCE_BRIEFS, f"announce-arm briefs changed; digest is {got!r}"


def test_byte_stable_tier1_briefs():
    got = _digest(_brief_blob(Rules(disclose_structure=True), DISC_NUMBERS))
    assert got == TIER1_BRIEFS, f"tier-1 briefs changed; digest is {got!r}"


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
    text = reflect_system_prompt(seat, RULES, M3, NAMES[seat])
    assert "40 balls numbered 1 through 40" in text
    assert "is numbered 1 through 16" in text and "is numbered 17 through 40" in text
    mine = M3.dividends[SEAT_TYPE[seat]]
    assert f"{mine['X']} francs per certificate" in text
    for s in SEATS:
        assert s not in text
    lowered = text.lower()
    for word in ("probability", "expected value", "equilibrium"):
        assert word not in lowered


# ---------------------------------------------------------------- structural disclosure
#
# Rules.disclose_structure is the one deliberate exception to the "nothing about types,
# others' dividends or the informed count" constraint. These guards hold the exception to
# exactly its charter: structure in, identities / fixedness / schedule / vocabulary out.

DISC = Rules(disclose_structure=True)
DISC_MARKETS = [MARKETS[4], MARKETS[7], MARKETS[8]]
DISC_SEATS = [(m, s) for m in DISC_MARKETS for s in m.seats]
DISC_HEADER = "== THE THREE TYPES OF INVESTORS =="


def _all_prompts_disclosed(market, seat):
    return "\n".join([system_prompt(seat, DISC, market),
                      broadcast_system_prompt(seat, DISC, market),
                      reflect_system_prompt(seat, DISC, market)])


def test_disclosure_is_a_treatment_switch():
    """On: the section is in all three prompts. Off: in none of them, and the baseline
    privacy sentence is byte-exactly the one the completed runs were prompted with."""
    m = MARKETS[4]
    for build in (system_prompt, broadcast_system_prompt, reflect_system_prompt):
        assert DISC_HEADER in build("S05", DISC, m)
        assert DISC_HEADER not in build("S05", RULES, m)
    off = system_prompt("S05", RULES, m)
    assert "Type I" not in off
    assert ("These numbers are YOUR earnings per certificate. They are your own private "
            "information;\ndo not reveal them to anyone. Earnings may be different for "
            "different investors.") in off


@pytest.mark.parametrize("market,seat", DISC_SEATS, ids=_ids(DISC_SEATS))
def test_disclosed_prompts_keep_forbidden_vocabulary_out(market, seat):
    """The treatment discloses structure, not vocabulary: probability language, theory
    words and the prior-as-a-number stay out of the disclosed prompts too."""
    text = _all_prompts_disclosed(market, seat)
    lowered = text.lower()
    for word in ("probability", "probabilities", "probable", "likelihood",
                 "expected value", "bayes", "chance", "odds", "random sample",
                 "rational expectation", "equilibrium", "prior information model",
                 "insider", "efficiency"):
        assert word not in lowered, f"market {market.number} {seat} contains {word!r}"
    for token in ("0.4", "0.6", "40%", "60%", "16/40", "24/40"):
        assert token not in text, f"market {market.number} states the prior as {token!r}"


@pytest.mark.parametrize("market,seat", DISC_SEATS, ids=_ids(DISC_SEATS))
def test_disclosed_prompt_carries_every_types_dividends_and_your_own(market, seat):
    """The mirror of test_only_your_own_dividends_appear: under disclosure every type's
    amounts are in the prompt, and the agent is told which type is its own — and only
    that one."""
    text = system_prompt(seat, DISC, market)
    for t, d in market.dividends.items():
        for v in d.values():
            assert f"{v} francs per certificate" in text, \
                f"market {market.number} {seat} misses type {t}'s {v}"
    assert f"You are a Type {market.seat_type[seat]} investor" in text
    for t in market.dividends:
        if t != market.seat_type[seat]:
            assert f"You are a Type {t} investor" not in text


@pytest.mark.parametrize("market", DISC_MARKETS, ids=lambda m: f"m{m.number}")
def test_disclosed_section_states_allocation_not_identity_or_schedule(market):
    """The section names counts and amounts, never who or when. The only digits it may
    contain are the dividend values themselves, so a leaked period number, seat id or
    schedule shows up as a failing integer — and the fixedness of the card holders is
    deliberately NOT stated, in either direction."""
    text = system_prompt(market.seats[0], DISC, market)
    section = text[text.index(DISC_HEADER):text.index("== WHAT EVERY INVESTOR KNOWS ==")]
    values = {str(v) for d in market.dividends.values() for v in d.values()}
    assert set(re.findall(r"\d+", section)) == values
    assert "exactly two of" in section
    assert "or whether they are the same investors" in section
    assert "a blank card looks the same" in section
    assert "the SAME two" not in section
    for s in market.seats:
        assert s not in section


def test_disclosed_fact_one_replaces_the_baseline_fact():
    """The baseline fact — no one is told how many — would contradict the disclosure
    section outright, so under the treatment it points at the section instead."""
    on = system_prompt("S01", DISC, MARKETS[4])
    off = system_prompt("S01", RULES, MARKETS[4])
    assert "No one is told how many investors receive" not in on
    assert "is stated in the section above" in on
    assert "No one is told how many investors receive" in off
    assert "is stated in the section above" not in off


@pytest.mark.parametrize("number", [1, 2, 3, 6, 92])
def test_disclosure_rejects_markets_with_all_periods(number):
    """A market with 'all' periods hands a lettered card to everybody in those periods,
    which would make the disclosed two-per-type sentence false. Config refuses the
    combination rather than prompting agents with a lie."""
    with pytest.raises(ValueError, match="disclose_structure"):
        Config(market=number, rules={"disclose_structure": True})
    Config(market=number)                                    # baseline still loads
    Config(market=4, rules={"disclose_structure": True})     # the treatment markets do too


# ------------------------------------------------------------- the ladder: tiers 2 and 3
#
# Tier 2 adds the per-year card announcement, tier 3 adds that the card holders do not
# change. Both are gated behind disclose_structure, so these guards are the tier-1 guards
# above with one more fact each — and the digests at the top of this file are what proves
# the rungs below them did not move.

TIER2 = Rules(disclose_structure=True, disclose_card_years=True,
              objective_profit_max=True, clue_is_certain=True)
TIER3 = Rules(disclose_structure=True, disclose_card_years=True,
              disclose_insiders_fixed=True, objective_profit_max=True,
              clue_is_certain=True)
TIERS = [("tier2", TIER2), ("tier3", TIER3)]
TIER_SEATS = [(m, s, n, r) for m in DISC_MARKETS for s in m.seats for n, r in TIERS]
OBJECTIVE_HEADER = "== YOUR OBJECTIVE =="


def _section(market, rules):
    """The disclosure section only, cut out of the turn prompt."""
    text = system_prompt(market.seats[0], rules, market)
    return text[text.index(DISC_HEADER):text.index("== WHAT EVERY INVESTOR KNOWS ==")]


def _flat(text: str) -> str:
    """Whitespace collapsed to single spaces.

    The section is hard-wrapped at ~87 columns and the four tails wrap differently, so a
    sentence sits on one line in one rung and straddles two in the next. Asserting on the
    raw bytes would make every guard here a test of the line breaks.
    """
    return " ".join(text.split())


@pytest.mark.parametrize("market", DISC_MARKETS, ids=lambda m: f"m{m.number}")
def test_each_rung_adds_exactly_one_fact(market):
    """The three rungs differ in two sentences and nothing else: whether the holders are
    said to be the same investors, and whether the card years are said to be announced."""
    one, two, three = (_flat(_section(market, r)) for r in (DISC, TIER2, TIER3))

    # Identities: withheld at every rung. There is no flag that removes this clause.
    for s in (one, two, three):
        assert "No one is told which investors they are" in s

    # Fixedness: withheld on tiers 1 and 2, stated on tier 3.
    for s in (one, two):
        assert "or whether they are the same investors from year to year" in s
        assert "they are the same investors in every year" not in s
    assert "or whether they are the same investors from year to year" not in three
    assert "they are the same investors in every year in which such cards are handed out" \
        in three

    # Card years: withheld on tier 1, announced on tiers 2 and 3.
    assert "no one is told which years are which" in one
    assert "a blank card looks the same to its holder either way" in one
    for s in (two, three):
        assert "no one is told which years are which" not in s
        assert "you are told whether clue cards that are not blank were handed out" in s


@pytest.mark.parametrize("market", DISC_MARKETS, ids=lambda m: f"m{m.number}")
@pytest.mark.parametrize("name,rules", TIERS, ids=[n for n, _ in TIERS])
def test_higher_rungs_state_no_new_digits(market, name, rules):
    """The mirror of the tier-1 digit guard on the rungs above it. The only digits the
    section may contain are the dividend values, so a leaked period number, informed count
    or schedule shows up as a failing integer."""
    values = {str(v) for d in market.dividends.values() for v in d.values()}
    assert set(re.findall(r"\d+", _section(market, rules))) == values


@pytest.mark.parametrize("market,seat,name,rules", TIER_SEATS,
                         ids=[f"m{m.number}-{s}-{n}" for m, s, n, _ in TIER_SEATS])
def test_higher_rungs_keep_forbidden_vocabulary_out(market, seat, name, rules):
    """The ladder discloses structure, not vocabulary. Same lists as the tier-1 guard,
    over all three prompt kinds."""
    # Named, because the seat-id assertion below is only meaningful when a name is
    # supplied — `seat` is the fallback the builders print when it is not.
    text = "\n".join([system_prompt(seat, rules, market, NAMES[seat]),
                      broadcast_system_prompt(seat, rules, market, NAMES[seat]),
                      reflect_system_prompt(seat, rules, market, NAMES[seat])])
    lowered = text.lower()
    for word in ("probability", "probabilities", "probable", "likelihood",
                 "expected value", "bayes", "chance", "odds", "random sample",
                 "rational expectation", "equilibrium", "prior information model",
                 "insider", "efficiency"):
        assert word not in lowered, f"m{market.number} {seat} {name} contains {word!r}"
    for token in ("0.4", "0.6", "40%", "60%", "16/40", "24/40"):
        assert token not in text, f"m{market.number} {name} states the prior as {token!r}"
    for s in market.seats:
        assert s not in text, f"m{market.number} {name} names seat {s}"


@pytest.mark.parametrize("market", DISC_MARKETS, ids=lambda m: f"m{m.number}")
def test_fixedness_disclosure_matches_the_engine(market):
    """The tier-3 sentence says the card holders are the same investors every card year.
    This is the test that keeps it from being a lie: the engine's own card dealing must
    hand the letters to the same seats in every insider period, whatever the state."""
    seen = set()
    for period, info in enumerate(market.sequence_info, start=1):
        if info != "insider":
            continue
        for state in market.states:
            cards = market.clue_cards(info, state)
            seen.add(frozenset(s for s, c in cards.items() if c is not None))
    assert len(seen) == 1, f"market {market.number} deals letters to different seats"
    assert seen.pop() == set(market.insiders)


def test_card_year_announcement_runs_in_both_directions():
    """Tier 2's whole content is that a blank card becomes informative, which needs the
    announcement in BOTH directions — a sentence only in the 'none' years would leave an
    insider year silent and indistinguishable from the baseline."""
    none = _brief(rules=TIER2, market=MARKETS[4], info="none", card=None)
    ins = _brief(rules=TIER2, market=MARKETS[4], info="insider", card=None)
    assert none.count("This year no investor has received a lettered clue card.") == 1
    assert "lettered clue cards have been handed out" not in none
    assert ins.count("This year lettered clue cards have been handed out.") == 1
    assert "no investor has received" not in ins


def test_card_year_announcement_cannot_double_print():
    """announce_no_info_period and disclose_card_years write the same sentence in the
    'none' direction. They share one branch, so no configuration prints it twice."""
    both = Rules(disclose_structure=True, disclose_card_years=True,
                 announce_no_info_period=True)
    text = _brief(rules=both, market=MARKETS[4], info="none", card=None)
    assert text.count("This year no investor has received a lettered clue card.") == 1


def test_card_year_announcement_is_silent_below_tier_two():
    """Markets 4, 7 and 8 do not announce their no-information periods, so neither
    sentence may appear at the baseline or at tier 1 — otherwise the completed sessions
    were prompted with something this ladder invented."""
    for rules in (RULES, DISC):
        for info in ("none", "insider"):
            text = _brief(rules=rules, market=MARKETS[4], info=info, card=None)
            assert "no investor has received" not in text
            assert "lettered clue cards have been handed out" not in text


@pytest.mark.parametrize("market,seat", ALL_SEATS, ids=_ids(ALL_SEATS))
def test_objective_reaches_all_three_prompts_only_under_the_flag(market, seat):
    """The baseline states its purpose in _TURN_TASK alone, so a broadcast reply and a
    year-end note are written without one. objective_profit_max goes in the shared
    preamble, which is the only place that reaches all three — and it is not gated on a
    market, so every market and seat must render it cleanly."""
    on = Rules(objective_profit_max=True)
    for build in (system_prompt, broadcast_system_prompt, reflect_system_prompt):
        assert OBJECTIVE_HEADER in build(seat, on, market, NAMES[seat])
        assert OBJECTIVE_HEADER not in build(seat, RULES, market, NAMES[seat])
    # The paper's own sentence stays: this adds to it rather than replacing it.
    assert "You are free to make as much profit as you can." in system_prompt(
        seat, on, market, NAMES[seat])
    lowered = "\n".join(build(seat, on, market, NAMES[seat]) for build in
                        (system_prompt, broadcast_system_prompt, reflect_system_prompt)).lower()
    for word in ("probability", "expected value", "equilibrium", "chance", "odds"):
        assert word not in lowered, f"m{market.number} {seat} objective block has {word!r}"


def test_clue_certainty_strengthens_both_places_and_states_no_new_fact():
    """clue_is_certain adds no fact — the baseline already says a lettered card is always
    correct and that the dividend WILL be paid. It removes the room to hedge, in the
    system prompt and in the year's card line, and it CONTAINS the baseline sentence so
    every guard written against that wording still holds."""
    on = Rules(clue_is_certain=True)
    sys_on = _flat(system_prompt("S01", on, MARKETS[4], NAMES["S01"]))
    sys_off = _flat(system_prompt("S01", RULES, MARKETS[4], NAMES["S01"]))
    assert "A clue card that carries a letter is always correct." in sys_on   # baseline
    assert "A clue card that carries a letter is always correct." in sys_off
    assert "no exceptions and no qualifications" in sys_on
    assert "no exceptions and no qualifications" not in sys_off

    card_on = _flat(_brief(rules=on, market=MARKETS[4], info="insider", card="Y"))
    card_off = _flat(_brief(rules=RULES, market=MARKETS[4], info="insider", card="Y"))
    for text in (card_on, card_off):
        assert "Your clue card carries the letter Y. The Y-dividend WILL be paid" in text
    assert "never wrong, so treat this as certain" in card_on
    assert "never wrong" not in card_off
    # A blank card says nothing extra: the flag is about the letter, not the blank.
    blank = _flat(_brief(rules=on, market=MARKETS[4], info="insider", card=None))
    assert "never wrong" not in blank


@pytest.mark.parametrize("seat", MARKETS[1].seats)
def test_clue_certainty_cannot_reach_the_imperfect_market(seat):
    """Config refuses the flag on market 1, but Rules is constructible without Config.
    The code path has to hold independently, because a hand-built Rules reaching the
    prompt builders is exactly how a test fixture would get there."""
    text = _flat(system_prompt(seat, Rules(clue_is_certain=True), MARKETS[1], NAMES[seat]))
    assert "always correct" not in text
    assert "no exceptions and no qualifications" not in text
    assert "Either box can produce any row of marks." in text      # the true wording


@pytest.mark.parametrize("flag", ["disclose_card_years", "disclose_insiders_fixed"])
def test_higher_rungs_require_the_structure(flag):
    """Both rungs write into the section disclose_structure creates. Without it there is
    no section, so the flag would either do nothing or state a fact never introduced."""
    with pytest.raises(ValueError, match="disclose_structure"):
        Config(market=4, rules={flag: True})
    Config(market=4, rules={flag: True, "disclose_structure": True})


@pytest.mark.parametrize("number", [1, 2, 3, 6, 92])
def test_higher_rungs_inherit_the_all_period_rejection(number):
    """Requiring disclose_structure means the 'all'-period rejection covers the ladder
    without a second check."""
    with pytest.raises(ValueError, match="disclose_structure"):
        Config(market=number, rules={"disclose_structure": True,
                                     "disclose_card_years": True})


def test_card_years_refuses_an_explicit_silence():
    """announce_no_info_period: false asks for silence in the very direction
    disclose_card_years announces. There is no right answer, and the winner would be
    invisible in the log."""
    with pytest.raises(ValueError, match="announce_no_info_period"):
        Config(market=4, rules={"disclose_structure": True, "disclose_card_years": True,
                                "announce_no_info_period": False})
    # Unset is the supported way to write it, and true is merely redundant.
    Config(market=4, rules={"disclose_structure": True, "disclose_card_years": True})
    Config(market=4, rules={"disclose_structure": True, "disclose_card_years": True,
                            "announce_no_info_period": True})


def test_clue_certainty_is_rejected_on_the_imperfect_market():
    """Market 1's card is a row of marks either box can produce. "Never wrong" would be
    false there, and it would hand that market's agents the one thing it withholds."""
    with pytest.raises(ValueError, match="clue_is_certain"):
        Config(market=1, rules={"clue_is_certain": True})
    Config(market=1)                                       # baseline still loads
    Config(market=4, rules={"clue_is_certain": True})      # the lettered markets do too


# --------------------------------------------------------- the period-end memo tier
#
# "note" is the baseline: about 100 words a year, written fresh, two carried forward.
# "memo" is one standing document the agent rewrites each year end, and the new version
# replaces the old one. The digests above cover the note style, so these guards are the
# positive half — what the memo style says, and where.

MEMO = Rules(period_end_style="memo", period_end_notes=1)
MEMO_HEADER = "== YOUR MEMO =="
NOTES_HEADER = "== YOUR NOTES FROM PAST YEAR-ENDS =="
ONE_NOTE = [{"kind": "period_end", "period": 4, "round": 0, "at": None,
             "text": "What I know so far: the price sits near 260 unless someone buys hard."}]


def _period_end(rules=RULES, market=M3, reflections=()):
    return build_period_end_brief(
        market=market, seat="S01", period=5, state=market.states[0], certs=2, cash=10_000,
        dividend_paid=500, profit=100, reflections=list(reflections), history=[],
        market_log=[], not_selected=[], names=NAMES, rules=rules)


def test_memo_replaces_the_hundred_word_ask_with_a_rewrite():
    """The year-end ask is what tells a memo agent this is the rewrite occasion — the
    shared reflect system prompt describes both occasions and defers to this line."""
    memo = _flat(_period_end(rules=MEMO, reflections=ONE_NOTE))
    note = _flat(_period_end(rules=RULES, reflections=ONE_NOTE))

    assert "Write your memo out again in full, between 500 and 800 words" in memo
    assert "this replaces it completely" in memo
    assert "about 100 words" not in memo

    assert "Write a note to yourself of about 100 words" in note
    assert "replaces it completely" not in note

    # The range comes from Rules, not from the sentence.
    wide = _flat(_period_end(rules=Rules(period_end_style="memo", period_end_notes=1,
                                         memo_words=(300, 400)), reflections=ONE_NOTE))
    assert "between 300 and 400 words" in wide


def test_memo_is_carried_into_every_kind_of_call():
    """The memo is the seat's whole long-term memory, so it has to be in the turn, the
    broadcast and the post-trade brief as well as the year-end one — that is the point of
    rewriting it rather than appending to a list."""
    builders = [
        lambda r: _brief(rules=r, reflections=ONE_NOTE),
        lambda r: build_broadcast_brief(
            market=M3, seat="S01", period=5,
            quote={"side": "bid", "price": 250, "seat": "S02"}, info="insider", card="Y",
            certs=2, cash=10_000, book=EMPTY_BOOK, market_log=[], reflections=ONE_NOTE,
            history=[], not_selected=[], names=NAMES, rules=r),
        lambda r: build_trade_feedback_brief(
            market=M3, seat="S01", period=5, round_no=1, side="buy", price=250,
            counterparty="S02", info="insider", card="Y", certs=2, cash=10_000,
            book=EMPTY_BOOK, market_log=[], reflections=ONE_NOTE, history=[],
            not_selected=[], names=NAMES, rules=r),
        lambda r: _period_end(rules=r, reflections=ONE_NOTE),
    ]
    for build in builders:
        memo, note = build(MEMO), build(RULES)
        assert MEMO_HEADER in memo and NOTES_HEADER not in memo
        assert NOTES_HEADER in note and MEMO_HEADER not in note
        # The text itself is carried whole either way, and dated only in the note style.
        assert "the price sits near 260" in memo and "the price sits near 260" in note
        assert "(year 4)" in note
        assert "as you last wrote it, at the end of year 4" in _flat(memo)


def test_memo_first_year_placeholder_says_there_is_no_memo_yet():
    """The note style says "you have not finished a market year yet", which under the memo
    style would be describing the wrong object."""
    empty = _period_end(rules=MEMO, reflections=[])
    assert "You have not written your memo yet; this is your first year." in empty
    assert "You have not finished a market year yet." not in empty


def test_memo_post_trade_block_is_untouched():
    """The tier changes the year-end summary and nothing else. Post-trade notes stay a
    dated list, because they are still a list."""
    notes = ONE_NOTE + [{"kind": "trade_feedback", "period": 5, "round": 2,
                         "at": "after you sold one certificate at 174", "text": "sold high"}]
    memo = _period_end(rules=MEMO, reflections=notes)
    assert "== YOUR NOTES AFTER RECENT TRADES ==" in memo
    assert "(year 5, round 2, after you sold one certificate at 174) sold high" in memo


@pytest.mark.parametrize("market,seat", ALL_SEATS, ids=_ids(ALL_SEATS))
def test_memo_reflect_prompt_names_both_writing_occasions(market, seat):
    """One system prompt serves BOTH reflection calls, so a block that only said "rewrite
    your memo" would land on every post-trade note too, where the brief asks for one or
    two sentences. It has to name both and let the brief say which is which."""
    text = reflect_system_prompt(seat, MEMO, market, NAMES[seat])
    flat = _flat(text)
    assert "You keep ONE private memo" in flat
    assert "You write in two situations" in flat
    assert "Straight after a trade" in flat
    assert "You are not rewriting the memo here." in flat
    assert "At the end of a market year" in flat
    assert "REPLACES your previous memo completely" in flat
    # The note style's block is gone, not merely appended to.
    assert "You are writing a private note to yourself" not in flat


def test_memo_post_trade_brief_still_asks_for_one_or_two_sentences():
    """The other half of the contract: the system prompt promises the brief will say which
    occasion this is, so the post-trade brief must keep saying so."""
    text = build_trade_feedback_brief(
        market=M3, seat="S01", period=5, round_no=1, side="buy", price=250,
        counterparty="S02", info="insider", card="Y", certs=2, cash=10_000,
        book=EMPTY_BOOK, market_log=[], reflections=ONE_NOTE, history=[],
        not_selected=[], names=NAMES, rules=MEMO)
    assert "In one or two sentences, note why you made this trade" in _flat(text)
    assert "Write your memo out again in full" not in text


@pytest.mark.parametrize("market,seat", ALL_SEATS, ids=_ids(ALL_SEATS))
def test_memo_prompts_keep_forbidden_vocabulary_out(market, seat):
    """The tier changes how much an agent writes, not what it is allowed to know."""
    text = "\n".join([system_prompt(seat, MEMO, market, NAMES[seat]),
                      broadcast_system_prompt(seat, MEMO, market, NAMES[seat]),
                      reflect_system_prompt(seat, MEMO, market, NAMES[seat])])
    lowered = text.lower()
    for word in ("probability", "probabilities", "probable", "likelihood",
                 "expected value", "bayes", "chance", "odds", "random sample",
                 "rational expectation", "equilibrium", "insider"):
        assert word not in lowered, f"m{market.number} {seat} memo prompt has {word!r}"
    for s in market.seats:
        assert s not in text


def test_memo_requires_a_window_of_one():
    """The memo is cumulative — each version rewrites the one before it — so carrying two
    hands the agent a superseded copy of its own conclusions beside the current one, and
    pays ~900 tokens per call in the ~96% of calls that carry notes to do it."""
    # The default reflect budget is 3,000, below the memo floor, so every memo config has
    # to raise it — which is the intent, and is why it appears here.
    roster = [{"kind": "llm", "reflect_max_output_tokens": 8192}]
    with pytest.raises(ValueError, match="period_end_notes"):
        Config(market=7, agents=roster,
               rules={"period_end_style": "memo", "period_end_notes": 2})
    Config(market=7, agents=roster,
           rules={"period_end_style": "memo", "period_end_notes": 1})
    # The default style is unaffected by the default window.
    Config(market=7)


def test_memo_requires_a_reflect_budget_that_can_hold_it():
    """Reasoning shares the reflect budget. At 3,000 and a 100-word ask, 3% of year-end
    notes already come back empty having spent the lot thinking; a 500-800 word memo is
    ~1,100 tokens of body before any reasoning at all, and a truncated memo is the seat's
    whole memory."""
    memo = {"period_end_style": "memo", "period_end_notes": 1}
    with pytest.raises(ValueError, match="reflect_max_output_tokens"):
        Config(market=7, rules=memo,
               agents=[{"kind": "llm", "reflect_max_output_tokens": 3000}])
    Config(market=7, rules=memo,
           agents=[{"kind": "llm", "reflect_max_output_tokens": 8192}])
    # Scripted agents never write a note, so the floor does not apply to them.
    Config(market=7, rules=memo, agents=[{"kind": "pi"}])
    # And the note style keeps the 3,000 default.
    Config(market=7, agents=[{"kind": "llm", "reflect_max_output_tokens": 3000}])
