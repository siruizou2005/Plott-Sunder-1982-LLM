"""The markets, checked against what they claim to be.

Three kinds of check, and the distinctions matter:

  * Against the PAPER — expected dividends (Table 2's rightmost column), the market-1
    posteriors (Table 1), period counts and information spans (Table 1, body text).
    These catch a transcription slip in markets.py, and they run over PAPER_MARKETS.
  * Against params.py — market 3 must come out byte-identical to the constants already
    running. This is what licenses rewiring ~200 call sites onto Market later: if the new
    representation reproduces the old one exactly, the rewiring cannot change a result.
  * Against TABLE 7 — market 6 is ours, the equidistant control, so every claim made for
    it is recomputed here rather than asserted. That section also pins how far each
    published market asks each side to move, which is the confound the control removes.
"""

from __future__ import annotations

import pytest

from ps1982 import params
from ps1982.markets import MARKETS, PAPER_MARKETS, CONTROL_MARKETS, sample_posterior

ALL = list(MARKETS.values())
# The paper's own five. A guard that asserts something Plott & Sunder DID — which markets
# announced a no-information period, which one ends uninformed — iterates this: market 6
# is our control design and is not in that experiment, so making it satisfy a claim about
# the experiment would be asserting the wrong thing about it.
PAPER = [MARKETS[n] for n in PAPER_MARKETS]


# ---------------------------------------------------------------- Table 2


@pytest.mark.parametrize("number,expected", [
    (1, {"I": 283.3, "II": 283.3, "III": 166.7}),
    (2, {"I": 266.7, "II": 266.7, "III": 196.6}),
    (3, {"I": 220.0, "II": 210.0, "III": 155.0}),
    (4, {"I": 210.0, "II": 200.0, "III": 145.0}),
    (5, {"I": 212.5, "II": 169.5, "III": 152.0}),
])
def test_expected_dividends_match_table_2(number, expected):
    """Recomputed from the prior, not transcribed — a wrong dividend shows up here.

    Tolerance 0.1 rather than exact equality on the printed digit, because Table 2 is not
    self-consistent about the last place: market 1's type III is 166.666... printed 166.7
    (rounded) while market 2's type III is 196.666... printed 196.6 (truncated). The
    dividends are what this test is really pinning — nothing but 240/175 under a 1/3 prior
    lands within 0.1 of the printed value — and prior_ev is computed, never transcribed,
    so the paper's last digit cannot reach the experiment.
    """
    ev = MARKETS[number].prior_ev
    for t, want in expected.items():
        assert abs(ev[t] - want) < 0.1, f"market {number} type {t}: {ev[t]} != {want}"


def test_priors_sum_to_one():
    for m in ALL:
        assert round(sum(m.prior.values()), 9) == 1.0, f"market {m.number}"
        assert set(m.prior) == set(m.states), f"market {m.number}"


def test_every_type_has_a_dividend_for_every_state():
    for m in ALL:
        for t in m.types:
            assert set(m.dividends[t]) == set(m.states), f"market {m.number} type {t}"


# ---------------------------------------------------------------- Table 1


@pytest.mark.parametrize("number,periods,agents", [
    (1, 11, 9), (2, 11, 12), (3, 12, 12), (4, 14, 12), (5, 13, 12),
])
def test_period_and_roster_counts(number, periods, agents):
    m = MARKETS[number]
    assert m.n_periods == periods
    assert m.n_agents == agents
    assert len(m.sequence_info) == periods


@pytest.mark.parametrize("number,spans", [
    # (condition, first period, last period) — from Table 1 and the body text
    (1, [("none", 1, 4), ("insider", 5, 8), ("all", 9, 11)]),
    (2, [("none", 1, 4), ("all", 5, 6), ("insider", 7, 11)]),
    (3, [("none", 1, 2), ("insider", 3, 10), ("all", 11, 12)]),
    (4, [("none", 1, 4), ("insider", 5, 13), ("none", 14, 14)]),
    (5, [("none", 1, 3), ("insider", 4, 13)]),
])
def test_information_design(number, spans):
    info = MARKETS[number].sequence_info
    for cond, lo, hi in spans:
        for p in range(lo, hi + 1):
            assert info[p - 1] == cond, f"market {number} period {p}: {info[p-1]} != {cond}"


def test_market_4_is_the_only_one_ending_uninformed():
    """The body text singles this out; it is easy to lose in a span table."""
    for m in PAPER:
        ends_none = m.sequence_info[-1] == "none"
        assert ends_none == (m.number == 4), f"market {m.number}"


def test_states_are_drawn_from_the_declared_state_set():
    for m in ALL:
        assert set(m.sequence_states) <= set(m.states), f"market {m.number}"
    assert set(MARKETS[5].sequence_states) == {"X", "Y", "Z"}, "market 5 uses all three"


def test_insider_counts():
    """Six insiders, two of each type — except market 1, where it is three, one each."""
    for m in ALL:
        want = 1 if m.number == 1 else 2
        assert m.insiders_per_type == want
        assert len(m.insiders) == 3 * want, f"market {m.number}"
        for t in m.types:
            n = sum(1 for s in m.insiders if m.seat_type[s] == t)
            assert n == want, f"market {m.number} type {t}"


# ---------------------------------------------------------------- footnote 5


@pytest.mark.parametrize("card,paper", [
    ("0100101010", .150), ("0000000011", .555), ("0100110100", .150),
    ("0000010000", .770), ("1110000011", .062), ("1010000011", .150),
    ("1111111001", .003),
])
def test_market_1_posteriors_match_the_paper(card, paper):
    """All seven values the paper prints for market 1, from the footnote-5 urn model.

    This is what makes market 1 implementable rather than approximated: the generating
    process is stated, and reproducing every printed posterior confirms we read it right.
    """
    got = sample_posterior(card, MARKETS[1].prior)["X"]
    assert abs(got - paper) < 0.001, f"{card}: {got:.4f} != {paper}"


def test_market_1_cards_cover_every_informed_period():
    m = MARKETS[1]
    informed = [p for p in range(1, m.n_periods + 1) if m.sequence_info[p - 1] != "none"]
    assert sorted(m.paper_clue_cards) == informed


def test_only_market_1_is_imperfect():
    for m in ALL:
        assert m.imperfect == (m.number == 1), f"market {m.number}"
        if not m.imperfect:
            assert m.posterior_from_card("X")["X"] == 1.0, f"market {m.number}"


# ---------------------------------------------------------------- common knowledge


def test_no_information_periods_were_announced_in_markets_1_2_5():
    for m in PAPER:
        assert m.announce_no_info == (m.number in (1, 2, 5)), f"market {m.number}"


def test_only_market_1_lacks_the_constant_dividends_fact():
    for m in PAPER:
        assert m.dividends_constant_is_common_knowledge == (m.number != 1)


# ---------------------------------------------------------------- clue distribution


def test_clue_cards_go_to_the_right_seats():
    for m in ALL:
        for p in range(1, m.n_periods + 1):
            cards = m.cards_for_period(p)
            assert set(cards) == set(m.seats), f"market {m.number} period {p}"
            lettered = [s for s, c in cards.items() if c is not None]
            info = m.sequence_info[p - 1]
            if info == "none":
                assert lettered == []
            elif info == "all":
                assert sorted(lettered) == sorted(m.seats)
            else:
                assert sorted(lettered) == sorted(m.insiders)


def test_all_insiders_get_the_same_card():
    """"The clues of all insiders were identical" — including market 1's sample."""
    for m in ALL:
        for p in range(1, m.n_periods + 1):
            given = {c for c in m.cards_for_period(p).values() if c is not None}
            assert len(given) <= 1, f"market {m.number} period {p}: {given}"


# ---------------------------------------------------------------- redraw


def test_redraw_moves_states_but_never_the_information_design():
    for m in ALL:
        r = m.redrawn(20250725)
        assert r.sequence_info == m.sequence_info, f"market {m.number}"
        assert r.n_periods == m.n_periods
        assert set(r.sequence_states) <= set(m.states)
        assert r.number == m.number and r.prior == m.prior


def test_redraw_is_deterministic_in_the_seed():
    a, b = MARKETS[5].redrawn(7), MARKETS[5].redrawn(7)
    assert a.sequence_states == b.sequence_states
    assert MARKETS[5].redrawn(8).sequence_states != a.sequence_states


def test_redrawing_market_1_redraws_its_clue_samples_too():
    """A sample is drawn from the urn matching the state, so it cannot outlive a redraw."""
    r = MARKETS[1].redrawn(20250725)
    assert r.paper_clue_cards != MARKETS[1].paper_clue_cards
    informed = [p for p in range(1, r.n_periods + 1) if r.sequence_info[p - 1] != "none"]
    assert sorted(r.paper_clue_cards) == informed
    for p, card in r.paper_clue_cards.items():
        assert len(card) == 10 and set(card) <= {"0", "1"}
    # and every card must be usable without an RNG, i.e. consistent with its own state
    for p in informed:
        assert r.card_for(p, r.sequence_states[p - 1]) == r.paper_clue_cards[p]


def test_market_5_redraw_uses_all_three_states():
    """A two-state redraw would silently drop Z and still look plausible."""
    seen = set()
    for seed in range(40):
        seen |= set(MARKETS[5].redrawn(seed).sequence_states)
    assert seen == {"X", "Y", "Z"}


# ---------------------------------------------------------------- equivalence


# The literal values params.py held BEFORE it was rewritten to derive from markets.py.
# They are repeated here on purpose: params.py now computes these, so asserting
# MARKETS[3] against params.py would compare markets.py with itself and pass no matter
# what either one said. Frozen copies are the only thing that still constrains the
# derivation, and they are what the 146 pre-existing tests were written against.
M3_BEFORE = {
    "seats": [f"S{i:02d}" for i in range(1, 13)],
    "insiders": ["S01", "S02", "S05", "S06", "S09", "S10"],
    "dividends": {"I": {"X": 400, "Y": 100},
                  "II": {"X": 300, "Y": 150},
                  "III": {"X": 125, "Y": 175}},
    "prior": {"X": 0.4, "Y": 0.6},
    "prior_ev": {"I": 220.0, "II": 210.0, "III": 155.0},
    "n_periods": 12,
    "market_supply": 24,
    "franc_to_usd": 0.003,
    "states": ["X", "Y"],
    "sequence_states": tuple("YYYXYYXYXYYX"),
    "sequence_info": ("none", "none") + ("insider",) * 8 + ("all", "all"),
}

THEORY_BEFORE = {
    ("none", "X"): ({"PI": 220, "RE": 220}, {"PI": "I", "RE": "I"}),
    ("none", "Y"): ({"PI": 220, "RE": 220}, {"PI": "I", "RE": "I"}),
    ("insider", "X"): ({"PI": 400, "RE": 400}, {"PI": "I_insider", "RE": "I"}),
    ("insider", "Y"): ({"PI": 220, "RE": 175}, {"PI": "I_uninformed", "RE": "III"}),
    ("all", "X"): ({"PI": 400, "RE": 400}, {"PI": "I", "RE": "I"}),
    ("all", "Y"): ({"PI": 175, "RE": 175}, {"PI": "III", "RE": "III"}),
}


def test_market_3_reproduces_the_pre_refactor_constants():
    """The licence to rewire: the new representation must BE the old one for market 3."""
    m = MARKETS[3]
    b = M3_BEFORE
    assert m.seats == b["seats"]
    assert m.insiders == b["insiders"]
    assert m.dividends == b["dividends"]
    assert m.prior == b["prior"]
    assert {t: round(v, 6) for t, v in m.prior_ev.items()} == b["prior_ev"]
    assert m.n_periods == b["n_periods"]
    assert m.market_supply == b["market_supply"]
    assert m.franc_to_usd == b["franc_to_usd"]
    assert list(m.states) == b["states"]
    assert m.sequence_states == b["sequence_states"]
    assert m.sequence_info == b["sequence_info"]
    # types in contiguous blocks of four, as SEAT_TYPE spelled out
    for i, s in enumerate(b["seats"]):
        assert m.seat_type[s] == ["I", "II", "III"][i // 4]


def test_market_3_theory_reproduces_the_pre_refactor_table():
    """Derived predictions must equal the table params.py used to hard-code."""
    m = MARKETS[3]
    for p in range(1, m.n_periods + 1):
        key = (m.sequence_info[p - 1], m.sequence_states[p - 1])
        want_price, want_holder = THEORY_BEFORE[key]
        assert m.theory_price(p) == want_price, f"period {p} {key} price"
        assert m.theory_holder(p) == want_holder, f"period {p} {key} holder"


def test_params_still_exposes_market_3_unchanged():
    """params.py derives now; the names it exports must not have shifted meaning."""
    assert params.SEATS == M3_BEFORE["seats"]
    assert params.INSIDERS == M3_BEFORE["insiders"]
    assert params.DIVIDENDS == M3_BEFORE["dividends"]
    assert params.N_PERIODS == M3_BEFORE["n_periods"]
    assert params.STATES == M3_BEFORE["states"]
    assert params.SEQUENCES["paper_exact"].states == M3_BEFORE["sequence_states"]
    for key, (price, holder) in THEORY_BEFORE.items():
        assert params.THEORY_PRICE[key] == price, key
        assert params.THEORY_HOLDER[key] == holder, key
    assert params.benchmark_values("insider", "Y") == {"re": 4200.0, "no_trade": 3400.0}
    assert params.benchmark_values("insider", "X") == {"re": 9600.0, "no_trade": 6600.0}
    assert params.benchmark_values("none", "X") == {"re": 5280.0, "no_trade": 4680.0}


# ---------------------------------------------------------------- Table 3
#
# Read off the paper (p. 674, rendered and rotated). Market 1 is absent by the paper's own
# choice: "In market 1 information given to insiders was probabilistic. Predictions are
# not given here in order to save space." — so markets.py DERIVES market 1's predictions,
# and this table is what licenses trusting that derivation everywhere it can be checked.
#
# {market: {state_or_None: (RE_price, PI_price, RE_holder, PI_holder)}}
TABLE_3 = {
    2: {None: (266, 266, "I+II", "I+II"),
        "X": (240, 266, "III", "I+II_uninformed"),
        "Y": (350, 350, "I", "I_insider")},
    3: {None: (220, 220, "I", "I"),
        "X": (400, 400, "I", "I_insider"),
        "Y": (175, 220, "III", "I_uninformed")},
    4: {None: (210, 210, "I", "I"),
        "X": (375, 375, "I", "I_insider"),
        "Y": (175, 210, "III", "I_uninformed")},
    5: {None: (212, 212, "I", "I"),
        "X": (180, 212, "III", "I_uninformed"),
        "Y": (245, 245, "II", "II_insider"),
        "Z": (320, 320, "I", "I_insider")},
}


@pytest.mark.parametrize("number", sorted(TABLE_3))
def test_derived_predictions_match_table_3(number):
    """Every insider-period cell of Table 3, for all four markets the paper prints.

    markets.py computes these from the dividends and the prior rather than transcribing
    them, so agreement here is a check on the ECONOMICS, not on typing. Prices carry a
    tolerance of 1 because the paper truncates (market 2's 266.67 prints as 266) — the
    body text confirms the intent: "in market 2 the price will be 266 in state X because
    uninformed agents of both types I and II have an expected value of 266".
    """
    m = MARKETS[number]
    checked = set()
    for p in range(1, m.n_periods + 1):
        info, state = m.sequence_info[p - 1], m.sequence_states[p - 1]
        key = None if info == "none" else state
        if info == "all" or key not in TABLE_3[number]:
            continue                       # 'all' collapses PI onto RE; not a Table 3 row
        re_p, pi_p, re_h, pi_h = TABLE_3[number][key]
        price, holder = m.theory_price(p), m.theory_holder(p)
        assert abs(price["RE"] - re_p) <= 1, f"m{number} p{p} {key} RE {price['RE']}!={re_p}"
        assert abs(price["PI"] - pi_p) <= 1, f"m{number} p{p} {key} PI {price['PI']}!={pi_p}"
        assert holder["RE"] == re_h, f"m{number} p{p} {key} RE holder"
        assert holder["PI"] == pi_h, f"m{number} p{p} {key} PI holder"
        checked.add(key)
    assert checked, f"market {number}: no Table 3 cell was actually exercised"


# The paper counts its own separating periods: "across all periods of all markets, the
# price predictions of the competing models differed 17 times", with footnote 6 listing
# them. This is the ONLY published check on market 1, whose Table 3 row the paper omits
# ("in market 1 information given to insiders was probabilistic. Predictions are not given
# here in order to save space") — so it is what licenses market 1's derived predictions.
FOOTNOTE_6 = {1: [6, 8], 2: [7, 9], 3: [3, 5, 6, 8, 10],
              4: [5, 7, 8, 10, 12], 5: [4, 5, 11]}


@pytest.mark.parametrize("number,periods", sorted(FOOTNOTE_6.items()))
def test_separating_periods_match_footnote_6(number, periods):
    """Which periods separate on price, against the paper's own list.

    Market 1 is the reason this test exists. Deriving its RE price from the realized state
    rather than from the clue's posterior made periods 5 and 7 look separating too: with a
    good sample (posterior .149 on X) the insider values a certificate at 320.1, which is
    already the highest valuation in the market, so BOTH models name 320.1 and the period
    does not separate. Only the bad-news samples separate — period 6 (.555) and period 8
    (.770), where the insider's valuation falls BELOW the uninformed 283.3 and the two
    models disagree about whether the market learns it.
    """
    m = MARKETS[number]
    got = [p for p in range(1, m.n_periods + 1)
           if m.theory_price(p)["RE"] != m.theory_price(p)["PI"]]
    assert got == periods, f"market {number}: derived {got}, paper's footnote 6 {periods}"


def test_footnote_6_totals_seventeen():
    """The paper's own total, which only comes out right if every market agrees.

    Over PAPER_MARKETS, not MARKETS: 17 is a count of Plott & Sunder's periods, and our
    control market's separating periods are not part of it.
    """
    total = sum(len([p for p in range(1, MARKETS[n].n_periods + 1)
                     if MARKETS[n].theory_price(p)["RE"] != MARKETS[n].theory_price(p)["PI"]])
                for n in PAPER_MARKETS)
    assert total == 17, f"derived {total} price-separating periods; the paper reports 17"


def test_market_1_re_conditions_on_the_sample_not_the_state():
    """RE cannot exceed the information in the market, and market 1's is a sample.

    Period 11's sample puts posterior .003 on X, so a fully revealing price is 349.3 —
    just under, never at, the 350 that knowing state Y for certain would justify. Reading
    350 here would mean the market revealed more than any agent knew.
    """
    m = MARKETS[1]
    assert m.theory_price(11)["RE"] == 349
    assert m.theory_price(11)["RE"] < max(m.dividends[t]["Y"] for t in m.types)
    # and the bad-news separating periods sit BELOW the uninformed valuation, not above
    uninformed = round(max(m.prior_ev.values()))
    for p in (6, 8):
        assert m.theory_price(p)["RE"] < uninformed == m.theory_price(p)["PI"]


def test_table_3_divergence_is_tracked_separately_for_price_and_allocation():
    """A cell can separate on ALLOCATION while both models name the same PRICE.

    Market 2 state Y is exactly that: Table 3 gives 350 under both models, but RE has all
    four type-I agents holding while PI has only the two type-I insiders. Scoring
    "separating" on price alone would discard those periods, and they are half of market
    2's identifying power — the market with the fewest price-separating periods of the
    five. Price and allocation divergence are therefore asserted independently.
    """
    for number, rows in TABLE_3.items():
        m = MARKETS[number]
        for key, (re_p, pi_p, re_h, pi_h) in rows.items():
            for p in range(1, m.n_periods + 1):
                info, state = m.sequence_info[p - 1], m.sequence_states[p - 1]
                if info != "insider" or state != key:
                    continue
                price, holder = m.theory_price(p), m.theory_holder(p)
                assert (price["RE"] != price["PI"]) == (re_p != pi_p), \
                    f"m{number} p{p} {key}: price divergence"
                assert (holder["RE"] != holder["PI"]) == (re_h != pi_h), \
                    f"m{number} p{p} {key}: allocation divergence"


def test_allocation_separates_wherever_price_does_and_sometimes_more():
    """Allocation is the weakly finer test — never coarser than price."""
    for number in TABLE_3:
        m = MARKETS[number]
        for p in range(1, m.n_periods + 1):
            if m.sequence_info[p - 1] != "insider":
                continue
            price, holder = m.theory_price(p), m.theory_holder(p)
            if price["RE"] != price["PI"]:
                assert holder["RE"] != holder["PI"], f"m{number} p{p}"


def test_market_1_predictions_are_ours_because_the_paper_omits_them():
    """Not a gap in the transcription — the paper says it left them out.

    Which does not leave them unchecked: footnote 6 counts market 1's separating periods,
    and test_separating_periods_match_footnote_6 holds the derivation to that count.

    This test used to assert the separating set was `[5, 6, 7, 8]`, commented "exactly its
    insider periods" — and that comment was the bug. It froze the assumption that every
    insider period separates, which holds only when RE is read off the realized state.
    Under an imperfect clue a good sample leaves both models naming the same price, so only
    half of market 1's insider periods separate. A test that pins whatever the code does
    cannot catch the code being wrong; this one now pins what the paper reports.
    """
    assert 1 not in TABLE_3
    m = MARKETS[1]
    sep = [p for p in range(1, m.n_periods + 1)
           if m.theory_price(p)["RE"] != m.theory_price(p)["PI"]]
    insider = [p for p in range(1, m.n_periods + 1) if m.sequence_info[p - 1] == "insider"]
    assert sep == FOOTNOTE_6[1]
    assert set(sep) < set(insider), "separating periods are a strict subset of insider ones"


def test_market_3_clue_cards_match_params_py():
    m = MARKETS[3]
    for p in range(1, m.n_periods + 1):
        info, state = m.sequence_info[p - 1], m.sequence_states[p - 1]
        assert m.cards_for_period(p) == params.clue_cards(info, state), f"period {p}"


def test_market_1_theory_uses_the_realized_sample_not_the_periods_card():
    """A redrawn run can keep the paper's state for a period and still draw another sample.

    Then matching on (info, state, period) picks up Table 1's card and scores the period
    against a theory the run never faced. Measured on m1_random_0: periods 5, 6 and 8 all
    took the wrong RE and two of the three flipped the separating flag, because their
    redrawn states happened to coincide with Table 1's. Callers holding the realized card
    must be able to say so, which is what the `card` argument is for.
    """
    m = MARKETS[1]
    period = 6                                   # Table 1: state X, insider, and separating
    state = m.sequence_states[period - 1]
    paper_card = m.paper_clue_cards[period]       # '0000000011', posterior .555 -> separates
    other_card = "0101001001"                     # 4 ones, posterior .149 -> does not

    derived = m.theory_at("insider", state, period)[0]
    assert derived == m.theory_price(period), "no card given: falls back to Table 1's"
    assert derived["RE"] != derived["PI"]

    with_paper = m.theory_at("insider", state, period, paper_card)[0]
    with_other = m.theory_at("insider", state, period, other_card)[0]
    assert with_paper == derived
    assert with_other["RE"] == with_other["PI"], "a good sample leaves the models agreeing"
    assert with_other != with_paper, "the realized card must change the prediction"


# ---------------------------------------------------------------- Table 7: the control
#
# Market 6 is OURS, not Plott & Sunder's: the equidistant control of Table 7. These guards
# are what make it a control rather than a sixth guess — every claim the table makes about
# it is recomputed here from the dividends and the prior, exactly as TABLE_3 does for the
# paper's four.

M6 = MARKETS[6]


def test_market_6_expected_dividends_match_table_7():
    """Table 7's rightmost column, recomputed. 220 (marginal) / 190 / 191."""
    ev = M6.prior_ev
    for t, want in {"I": 220.0, "II": 190.0, "III": 191.0}.items():
        assert abs(ev[t] - want) < 1e-9, f"type {t}: {ev[t]} != {want}"
    # "a unique marginal type" — the design criterion the table says it was selected for.
    assert sorted(ev.values())[-1] > sorted(ev.values())[-2], "marginal type must be unique"
    assert M6._argmax_types(ev) == "I"


def test_market_6_is_equidistant():
    """The whole point: both informed-trade directions are 80 francs from v-bar.

    Throughout the rest of the design family they are not — market 4's buy side must move
    +165 and its sell side only -35 — so any normalised measure flatters the sell side.
    """
    vbar = max(M6.prior_ev.values())
    re_buy = M6.theory_at("insider", "X")[0]["RE"]
    re_sell = M6.theory_at("insider", "Y")[0]["RE"]
    assert (vbar, re_buy, re_sell) == (220.0, 300, 140)
    assert re_buy - vbar == vbar - re_sell == 80.0


# Every published market's informed-trade sides, as francs from the uninformed level,
# computed once here so the two guards below argue from the same numbers. A lettered clue
# throughout, which is exact for markets 2-5 and is NOT market 1's model — see below.
#   {market: {state: signed distance from v-bar}}
PAPER_DISTANCES = {
    1: {"X": +16.67, "Y": +66.67},
    2: {"X": -26.67, "Y": +83.33},
    3: {"X": +180.0, "Y": -45.0},
    4: {"X": +165.0, "Y": -35.0},
    5: {"X": -32.5, "Y": +32.5, "Z": +107.5},
}


@pytest.mark.parametrize("number,want", sorted(PAPER_DISTANCES.items()))
def test_how_far_each_published_market_asks_each_side_to_move(number, want):
    """The distance confound, pinned market by market rather than described.

    This is what the Table 7 control exists to remove, so the numbers it is measured
    against have to be fixed somewhere a change would break.
    """
    m = MARKETS[number]
    vbar = max(m.prior_ev.values())
    for st, d in want.items():
        got = max(m.dividends[t][st] for t in m.types) - vbar
        assert abs(got - d) < 0.01, f"market {number} state {st}: {got:+.2f} != {d:+.2f}"


def test_which_published_markets_proposition_1_actually_rules_out():
    """Proposition 1 is a TWO-STATE result, and the family is not uniformly two-state.

    It says equidistance needs p(buy state) > 1/2, so it rules out exactly those two-state
    markets whose buy state is at or below 1/2 — markets 3 and 4, and only those. It does
    NOT rule out markets 1 and 2, whose buy state is Y at 2/3, and it does not reach market
    5 at all, which has three states and whose v-bar mixes all of them.

    Getting this wrong is easy in the direction that matters: the buy state is Y, not X, in
    markets 1 and 2, and in market 5 the sell state is X while BOTH Y and Z are buy states.
    Reading 'the buy state' as 'X' in every market gives priors of 1/3, 1/3, .4, .4, .35 —
    all at or below 1/2 — and the false conclusion that the proposition excludes the whole
    family.
    """
    two_state = [m for m in PAPER if len(m.states) == 2]
    ruled_out = []
    for m in two_state:
        vbar = max(m.prior_ev.values())
        buy = [s for s in m.states if max(m.dividends[t][s] for t in m.types) > vbar]
        if all(m.prior[s] <= 0.5 for s in buy):
            ruled_out.append(m.number)
    assert ruled_out == [3, 4]
    assert MARKETS[2].prior["Y"] > 0.5 and PAPER_DISTANCES[2]["Y"] > 0, "m2 buys on Y at 2/3"
    assert len(MARKETS[5].states) == 3, "proposition 1's two-state hypothesis excludes m5"


def test_market_5_already_contains_an_equidistant_pair():
    """And it is not ruled out by anything: market 5's X and Y sit +/- 32.5 from v-bar.

    Found by this test file, not by the paper, which states that no market in the published
    family can be equidistant. That statement is right about the two-state markets the
    proposition covers and wrong about market 5, where v-bar = 212.5 mixes three states and
    lands exactly halfway between the sell-side X (180) and the buy-side Y (245). Market 5
    supplies a third of all buyer-side periods and its five completed sessions therefore
    already hold an equidistant buy-vs-sell comparison — on its X and Y periods only, since
    Z is +107.5 away and is not part of the pair.

    This does not make the Table 7 control redundant: market 5's uninformed level lies
    inside the competitive interval on both of its buy states, so no competitive force
    pushes its price up at all, which is a separate defect the control does not share.
    """
    m = MARKETS[5]
    vbar = max(m.prior_ev.values())
    sell = vbar - max(m.dividends[t]["X"] for t in m.types)
    buy = max(m.dividends[t]["Y"] for t in m.types) - vbar
    assert sell == buy == 32.5, "exact, not approximate"
    assert max(m.dividends[t]["Z"] for t in m.types) - vbar == 107.5, "Z is not in the pair"
    # market 6 is the only market that is equidistant on ALL of its informed states
    assert {abs(max(MARKETS[6].dividends[t][s] for t in MARKETS[6].types)
                - max(MARKETS[6].prior_ev.values())) for s in MARKETS[6].states} == {80.0}


def test_market_6_buy_side_is_still_non_separating():
    """Equation (1) is independent of the parameters, so equidistance does not fix it.

    re != pi iff the informed profit by selling — the identity that makes the classic price
    test a test of informed selling only. If the control accidentally separated on the buy
    side it would not be a control for this paper's claim, it would be a different market.
    """
    vbar = max(M6.prior_ev.values())
    for st in M6.states:
        price = M6.theory_at("insider", st)[0]
        informed_sell = price["RE"] < vbar
        assert (price["RE"] != price["PI"]) == informed_sell, f"state {st}"


def test_market_6_prior_is_a_whole_number_of_balls():
    """Table 7 states the cage itself: 24 of 40 balls pay X. The prompt has no other way
    to express a prior — the word 'probability' never appears — so this is load-bearing."""
    assert M6.bingo_total == 40
    assert M6.cage_ranges == [("X", 1, 24), ("Y", 25, 40)]


def test_market_6_keeps_market_3s_structure():
    """Table 7 was "selected to keep every other feature of the family intact", and so is
    this: the control differs from market 3 in the dividends, the prior and nothing else."""
    m3 = MARKETS[3]
    assert (M6.n_agents, M6.n_per_type, M6.insiders_per_type) == (12, 4, 2)
    assert M6.insiders == m3.insiders
    assert M6.states == m3.states
    assert M6.sequence_info == m3.sequence_info
    assert M6.n_periods == m3.n_periods == 12
    assert M6.announce_no_info is m3.announce_no_info is False
    assert M6.dividends_constant_is_common_knowledge is True
    assert M6.imperfect is False
    assert M6.franc_to_usd == m3.franc_to_usd


def test_market_6_designed_sequence_is_balanced_across_the_two_sides():
    """Our sequence, so it has to justify itself. Four insider periods per side, and the
    same mean ordinal position on each, so neither side is systematically early or late.

    `paper_exact` is a misnomer for a market with no paper; the reported runs use
    `random_prior`, and this sequence is what `validate` and the scripted gate display.
    """
    insider = [(p, M6.sequence_states[p - 1]) for p in range(1, M6.n_periods + 1)
               if M6.sequence_info[p - 1] == "insider"]
    by_side = {st: [p for p, s in insider if s == st] for st in M6.states}
    assert len(by_side["X"]) == len(by_side["Y"]) == 4
    order = {st: [i for i, (_, s) in enumerate(insider) if s == st] for st in M6.states}
    assert sum(order["X"]) / 4 == sum(order["Y"]) / 4
    # one full-information period per state, so the institutional baseline of Section 3
    # gets a measurable gap on both sides at equal distance
    full = [M6.sequence_states[p - 1] for p in range(1, M6.n_periods + 1)
            if M6.sequence_info[p - 1] == "all"]
    assert sorted(full) == ["X", "Y"]


def test_market_6_is_not_one_of_the_papers():
    """Provenance, asserted rather than commented: the tables that pin Plott & Sunder must
    not silently acquire a row for a market they never printed."""
    assert 6 not in PAPER_MARKETS
    assert 6 not in TABLE_3 and 6 not in FOOTNOTE_6
    assert set(MARKETS) == set(PAPER_MARKETS) | set(CONTROL_MARKETS)
    assert set(PAPER_MARKETS) & set(CONTROL_MARKETS) == set()
    for n in CONTROL_MARKETS:
        assert n not in TABLE_3 and n not in FOOTNOTE_6
        assert "NOT a Plott & Sunder market" in MARKETS[n].note


def test_market_6_redraw_keeps_the_information_design_and_the_prior():
    """The reported runs are `random_prior`, so the redraw is the experiment, not a detail."""
    for seed in (42, 43, 44):
        r = M6.redrawn(seed)
        assert r.sequence_info == M6.sequence_info
        assert r.prior == M6.prior and r.dividends == M6.dividends
        assert set(r.sequence_states) <= {"X", "Y"}
        assert r.redrawn(seed).sequence_states == r.sequence_states


def test_the_meta_block_the_viewer_reads_comes_from_this_module():
    """`ps1982 backfill-meta` and every new run write these; the viewer draws them.

    The viewer used to keep its own copy of market 3's dividend table and show it beside
    every seat of every run. This is the contract that replaced it, and it has to hold for
    all six markets — including market 5, whose three states broke the old two-element
    shape, and market 6, which must not be labelled as Plott & Sunder's.
    """
    from ps1982.cli import _market_block
    for m in ALL:
        b = _market_block(m)
        assert b["number"] == m.number
        assert b["paper"] == (m.number in PAPER_MARKETS)
        assert b["states"] == list(m.states)
        assert set(b["dividends"]) == set(m.types)
        for t in m.types:
            assert b["dividends"][t] == {s: m.dividends[t][s] for s in m.states}
        assert b["n_agents"] == m.n_agents and b["bingo_total"] == m.bingo_total
    assert _market_block(MARKETS[5])["states"] == ["X", "Y", "Z"]
    assert _market_block(MARKETS[6])["paper"] is False


# ---------------------------------------------------------------- markets 7 and 8
#
# The equal-width controls. Market 6 removed the distance confound and left two others
# standing; these remove all three. Ours, so — as with market 6 — every claim made for them
# is recomputed here from the dividends and the prior rather than asserted in a comment.

M7, M8 = MARKETS[7], MARKETS[8]

#: type -> the prior expectation the design states. Recomputed below, not trusted.
DESIGN_EV = {7: {"I": 260.0, "II": 250.0, "III": 238.0},
             8: {"I": 300.0, "II": 290.0, "III": 280.0}}


def competitive_interval(m, state):
    """[second-highest, highest] informed valuation — the prices that clear the market.

    With 24 certificates and four agents of the top type, the top type alone demands the
    whole supply at any price strictly between the second-highest and the highest
    valuation, so every such price supports the competitive allocation. re is the TOP edge,
    which is why a fully competitive price can still score D well below 1.
    """
    vals = sorted((m.dividends[t][state] for t in m.types), reverse=True)
    return vals[1], vals[0]


def interval_width_in_D(m, state):
    """How much of the D scale a merely-competitive price can occupy in this state."""
    lo, hi = competitive_interval(m, state)
    return (hi - lo) / abs(hi - max(m.prior_ev.values()))


@pytest.mark.parametrize("number", (7, 8))
def test_markets_7_and_8_expected_dividends_match_the_design(number):
    """The design states a prior-expectation column; this is it, recomputed."""
    ev = MARKETS[number].prior_ev
    for t, want in DESIGN_EV[number].items():
        assert abs(ev[t] - want) < 1e-9, f"market {number} type {t}: {ev[t]} != {want}"
    assert sorted(ev.values())[-1] > sorted(ev.values())[-2], "marginal type must be unique"
    assert MARKETS[number]._argmax_types(ev) == "I"


@pytest.mark.parametrize("number", (7, 8))
def test_markets_7_and_8_prior_is_derived_from_the_design_not_chosen(number):
    """p(X) = .6 is the ONLY prior under which all three stated expectations hold.

    The design gives dividends and expectations; the prior is what reconciles them. Solving
    from type I alone would leave two unused equations, and a transcription slip in either
    of the other rows would then pass unnoticed — so all three are solved and compared.
    """
    m = MARKETS[number]
    solved = set()
    for t, ev in DESIGN_EV[number].items():
        x, y = m.dividends[t]["X"], m.dividends[t]["Y"]
        solved.add(round((ev - y) / (x - y), 10))
    assert solved == {0.6}, f"market {number}: rows disagree about the prior -> {solved}"
    assert m.prior == {"X": 0.6, "Y": 0.4}


@pytest.mark.parametrize("number", (7, 8))
def test_markets_7_and_8_are_equidistant(number):
    """Both informed-trade directions 100 francs from the uninformed level."""
    m = MARKETS[number]
    vbar = max(m.prior_ev.values())
    re_buy = m.theory_at("insider", "X")[0]["RE"]
    re_sell = m.theory_at("insider", "Y")[0]["RE"]
    assert re_buy - vbar == vbar - re_sell == 100.0
    assert (vbar, re_buy, re_sell) == ({7: (260.0, 360, 160), 8: (300.0, 400, 200)}[number])


@pytest.mark.parametrize("number,want", ((7, 0.300), (8, 0.200)))
def test_markets_7_and_8_are_equal_width(number, want):
    """The defect market 6 has and these do not.

    Equidistance fixes D's denominator. The numerator keeps its own slack: a price anywhere
    inside the competitive interval is competitive, so the interval's width in D units is
    the buy/sell gap a perfectly competitive market would show for free. Market 6 is the
    most lopsided market in the whole family on this measure (0.875 against 0.125) — its
    buy side cannot be distinguished from competitive until D falls below 0.125, while the
    paper's measured agent buy-side D is 0.14.
    """
    m = MARKETS[number]
    widths = {s: interval_width_in_D(m, s) for s in m.states}
    assert widths["X"] == pytest.approx(widths["Y"]), "equal width is the point"
    for s in m.states:
        assert widths[s] == pytest.approx(want, abs=1e-9)


def test_the_competitive_interval_width_across_the_whole_family():
    """Pinned market by market, because this is the comparison the arm is read against.

    Two-state markets only: market 5's v-bar sits INSIDE the competitive interval on both
    of its buy states, which is a different defect and is pinned by its own test.
    """
    want = {3: (0.556, 0.556), 4: (0.606, 0.714), 6: (0.875, 0.125),
            7: (0.300, 0.300), 8: (0.200, 0.200)}
    for n, (buy, sell) in want.items():
        m = MARKETS[n]
        vbar = max(m.prior_ev.values())
        got = {}
        for s in m.states:
            side = "buy" if max(m.dividends[t][s] for t in m.types) > vbar else "sell"
            got[side] = interval_width_in_D(m, s)
        assert got["buy"] == pytest.approx(buy, abs=0.001), f"market {n} buy"
        assert got["sell"] == pytest.approx(sell, abs=0.001), f"market {n} sell"
    # only 7 and 8 are equal-width, and market 3's equality is a coincidence of 100/180 =
    # 25/45 rather than a design property — it is not equidistant, so D still flatters one
    # side there.
    assert want[3][0] == want[3][1] and MARKETS[3].prior["X"] == 0.4


@pytest.mark.parametrize("number", (7, 8))
def test_markets_7_and_8_have_every_insider_on_the_same_side(number):
    """The third defect, and the one that has no name in the paper.

    A "buy state" is defined by re > v-bar, and re is the TOP type's valuation — it says
    where the RE price belongs, not what the informed will do. In markets 3 and 4 the buy
    state X has two of six insiders below v-bar and therefore wanting to sell; in market 5
    every one of the three states carries net sell pressure among insiders, so its two
    nominal buy states are ones where the price is supposed to fall. Here all six insiders
    want the same thing in each state, so the direction of the test is the direction of the
    incentive.
    """
    m = MARKETS[number]
    vbar = max(m.prior_ev.values())
    for state, (want_buy, want_sell) in (("X", (6, 0)), ("Y", (0, 6))):
        buy = sum(m.insiders_per_type for t in m.types if m.dividends[t][state] > vbar)
        sell = sum(m.insiders_per_type for t in m.types if m.dividends[t][state] < vbar)
        assert (buy, sell) == (want_buy, want_sell), f"market {number} state {state}"
    # and the published markets that do NOT have this property, pinned so the contrast is
    # not just asserted in prose
    m3, m5 = MARKETS[3], MARKETS[5]
    v3 = max(m3.prior_ev.values())
    assert sum(2 for t in m3.types if m3.dividends[t]["X"] < v3) == 2, "m3 X: 2 of 6 sell"
    v5 = max(m5.prior_ev.values())
    for s in m5.states:
        sellers = sum(2 for t in m5.types if m5.dividends[t][s] < v5)
        assert sellers >= 4, f"market 5 state {s} has net sell pressure among insiders"


def test_market_8_separates_the_three_type_roles_and_market_7_does_not():
    """The one design difference between the twins, stated as the arithmetic that makes it.

    Everywhere else in the family the marginal type is ALSO the buy-state holder, so when
    the buy signal arrives the units are already in the right hands and only the price has
    to move; the sell state requires a reallocation the buy state does not. Market 8 gives
    each type one job — I sets v-bar and tops neither state, II tops the sell state, III
    tops the buy state — so both states demand the same reallocation away from the same
    incumbent. Market 7 keeps the family's structure, which is exactly why both are run.
    """
    def holder(m, state):
        return max(m.types, key=lambda t: m.dividends[t][state])

    for m in (MARKETS[3], MARKETS[4], MARKETS[6], M7):
        marginal = m._argmax_types(m.prior_ev)
        assert holder(m, "X") == marginal, f"market {m.number}: marginal type tops the buy state"
        assert holder(m, "Y") != marginal

    marginal8 = M8._argmax_types(M8.prior_ev)
    assert marginal8 == "I"
    assert holder(M8, "X") == "III" and holder(M8, "Y") == "II"
    assert marginal8 not in (holder(M8, "X"), holder(M8, "Y")), "type I tops neither state"
    # every type has exactly one role, which is what "role-separated" has to mean
    assert {marginal8, holder(M8, "X"), holder(M8, "Y")} == set(M8.types)


@pytest.mark.parametrize("number", (7, 8))
def test_markets_7_and_8_buy_side_is_still_non_separating(number):
    """Equation (1) is algebraic: re != pi iff the informed profit by selling.

    No reparameterisation touches it. Neither equidistance nor equal width nor unanimous
    insider direction makes the classic price test see informed buying, and a control that
    accidentally separated on the buy side would be a different market, not a better one.
    """
    m = MARKETS[number]
    vbar = max(m.prior_ev.values())
    for st in m.states:
        price = m.theory_at("insider", st)[0]
        assert (price["RE"] != price["PI"]) == (price["RE"] < vbar), f"state {st}"


@pytest.mark.parametrize("number", (7, 8))
def test_markets_7_and_8_prior_is_a_whole_number_of_balls(number):
    """The prompt has no way to say a prior except the bingo cage — 'probability' never
    appears — so a prior that does not divide the cage would misstate itself all session."""
    m = MARKETS[number]
    assert m.bingo_total == 40
    assert m.cage_ranges == [("X", 1, 24), ("Y", 25, 40)]


@pytest.mark.parametrize("number", (7, 8))
def test_markets_7_and_8_keep_market_4s_structure(number):
    """Market 4's, not market 3's, and the sequence is inherited rather than designed.

    Market 4 is the only information design in the family with a no-information period at
    the END (period 14). That period is the only place the uninformed resting price can be
    measured after experience, and it is the one estimate that separates a cold-start
    artefact from a real baseline bias. It costs the two full-information periods markets 3
    and 6 have, so this arm adds nothing to the institutional-component estimate.
    """
    m, m4 = MARKETS[number], MARKETS[4]
    assert (m.n_agents, m.n_per_type, m.insiders_per_type) == (12, 4, 2)
    assert m.insiders == m4.insiders
    assert m.states == m4.states
    assert m.sequence_info == m4.sequence_info
    assert m.sequence_states == m4.sequence_states, "inherited, not invented"
    assert m.n_periods == m4.n_periods == 14
    assert m.announce_no_info is m4.announce_no_info is False
    assert m.dividends_constant_is_common_knowledge is True
    assert m.imperfect is False
    assert m.franc_to_usd == m4.franc_to_usd
    # the end-of-session no-information period, which is the reason for choosing market 4
    assert m.sequence_info[-1] == "none" and m.sequence_info[3] == "none"
    assert m.sequence_info.count("all") == 0, "market 4 has no full-information period"


@pytest.mark.parametrize("number", (7, 8))
def test_the_inherited_sequence_is_prior_inconsistent_under_the_new_cage(number):
    """Why `paper_exact` is not the arm's preset, asserted rather than trusted to a comment.

    Market 4's row was realized under a .4 prior on X and carries 6 X in 14 periods. Under
    these markets' .6 cage the expectation is 8.4, so running `paper_exact` here would show
    agents a sequence that argues against the cage they were told about. The arm uses
    `random_prior`; this guard exists so that the day someone runs `paper_exact` on market 7
    the reason it is odd is already written down.
    """
    m = MARKETS[number]
    assert m.sequence_states.count("X") == 6
    assert m.prior["X"] * m.n_periods == pytest.approx(8.4)


def _free_riders(m, state):
    """Uninformed agents who already trade toward RE in `state` on their prior alone.

    An uninformed agent values a certificate at its own prior expectation. If that sits
    below the RE price in a sell state (or above it in a buy state) the agent trades in the
    RE direction having learned NOTHING — the price moves toward RE for free.
    """
    vbar = max(m.prior_ev.values())
    re = max(m.dividends[t][state] for t in m.types)
    if re > vbar:
        who = [t for t in m.types if m.prior_ev[t] > re]
    else:
        who = [t for t in m.types if m.prior_ev[t] < re]
    return len(who) * (m.n_per_type - m.insiders_per_type)


@pytest.mark.parametrize("number", sorted(MARKETS))
def test_no_uninformed_agent_can_ever_free_ride_on_the_buy_side(number):
    """An identity, not a parameter choice, and it holds in every market ever built.

    v-bar is `max_t E_prior[d_t]` — the LARGEST valuation any uninformed agent can hold —
    and a buy state is DEFINED by re > v-bar. So no uninformed agent values a certificate
    above the buy-side RE price, in any market, at any parameters. Every franc of buy-side
    price discovery has to come from someone who learned something.

    This has the same status as equation (1): algebraic, and therefore not fixable by
    reparameterisation. It is one half of why the two sides are not comparable.
    """
    m = MARKETS[number]
    vbar = max(m.prior_ev.values())
    for s in m.states:
        if max(m.dividends[t][s] for t in m.types) > vbar:
            assert _free_riders(m, s) == 0, f"market {number} state {s}"


def test_the_papers_sell_sides_are_helped_by_uninformed_agents_and_ours_are_not():
    """The other half, and the one that IS a parameter choice — so it can be controlled for.

    re < v-bar leaves room for some type's prior expectation to fall below the sell-side RE
    price, and in every published market with a sell state, some does. Those agents sell at
    the RE price without having inferred anything, so the sell side gets price discovery
    the buy side can never get. Markets 6, 7 and 8 have none on either side, which makes
    them the only markets in which both directions require genuine learning.

    This is measurable in the engine gate and it is large: pooled over seeds 42/43/44 the
    scripted RE baseline — algorithms that already know the state — produces a buy/sell gap
    of +0.297 on market 3 and -0.337 / -0.509 on markets 7 and 8. See
    docs/markets-7-8-equal-width.md.
    """
    got = {}
    for n in sorted(MARKETS):
        m = MARKETS[n]
        vbar = max(m.prior_ev.values())
        sell = [s for s in m.states if max(m.dividends[t][s] for t in m.types) < vbar]
        got[n] = max((_free_riders(m, s) for s in sell), default=None)
    # market 1 has no sell state at all under a lettered clue, so it is not in the contrast
    assert got[1] is None
    assert {n: got[n] for n in (2, 3, 4, 5)} == {2: 2, 3: 2, 4: 2, 5: 4}
    assert {n: got[n] for n in CONTROL_MARKETS} == {6: 0, 7: 0, 8: 0}


@pytest.mark.parametrize("number", (6, 7, 8))
def test_the_scripted_re_baseline_cannot_bootstrap_our_sell_sides(number):
    """Why `make gate7` shows a sell side near zero, stated as arithmetic rather than noise.

    The scripted RE agent infers the state from the last trade PRICE: it takes the nearer
    RE price and accepts it as a signal only within `_BAND` of it. With no free riders, the
    only agents willing to trade below v-bar are the six insiders — and they are sellers
    who would rather take the uninformed's high bids than walk the price down. So the price
    never enters the sell-side signal band, so nobody learns, so the price never enters the
    band. The baseline's failure here is a property of a price-level inference rule meeting
    a market with no free riders, and it is NOT evidence that the engine is broken.

    The rule is deliberately left alone: it is the fixed comparison point for the completed
    sessions, and changing it would silently rebase every one of them. An LLM agent has the
    channel the scripted agent lacks — it can see six different seats trying to sell — so
    the arm measures whether inference from order flow happens at all.
    """
    from ps1982.agents.scripted import REAgent
    m = MARKETS[number]
    vbar = max(m.prior_ev.values())
    sell = [s for s in m.states if max(m.dividends[t][s] for t in m.types) < vbar]
    for s in sell:
        re = max(m.dividends[t][s] for t in m.types)
        band_top = re * (1 + REAgent._BAND)
        assert min(m.prior_ev.values()) > band_top, (
            f"market {number} state {s}: lowest uninformed valuation "
            f"{min(m.prior_ev.values()):.0f} vs signal band top {band_top:.0f}")
    # and the published markets are the other way round, which is why their gate passes
    for n in (2, 3, 4, 5):
        p = MARKETS[n]
        pv = max(p.prior_ev.values())
        for s in p.states:
            re = max(p.dividends[t][s] for t in p.types)
            if re < pv:
                assert min(p.prior_ev.values()) <= re * (1 + REAgent._BAND)


def test_the_seeds_the_arm_actually_runs_are_imbalanced_and_that_is_recorded():
    """The arm runs seeds 42/43/44 unfiltered. This is what they draw. Not a target — a fact.

    Balance was NOT designed in and NOT selected for: with p(X) = .6 forced by Proposition 1
    on any equidistant market, an unfiltered draw over nine insider periods is buy-heavy in
    expectation (5.4 against 3.6), and the sell side is the only separating side. So this
    arm under-samples the side that carries the result, by construction rather than by
    accident, and the analysis has to say so. Pinned here so it cannot be quietly forgotten
    between running the sessions and reporting them.
    """
    def insider_states(m, seed):
        r = m.redrawn(seed)
        return [r.sequence_states[p - 1] for p in range(1, r.n_periods + 1)
                if r.sequence_info[p - 1] == "insider"]

    per_seed = {n: {s: insider_states(MARKETS[n], s) for s in (42, 43, 44)} for n in (7, 8)}
    totals = {n: (sum(v.count("X") for v in per_seed[n].values()),
                  sum(v.count("Y") for v in per_seed[n].values())) for n in (7, 8)}
    assert totals[7] == (18, 9), "market 7 draws two buy periods for every sell period"
    assert totals[8] == (15, 12)
    for n in (7, 8):
        assert sum(totals[n]) == 27, "nine insider periods x three sessions"

    # Market 8's seeds 42 and 43 draw the SAME nine insider periods and differ only at
    # period 14, so that market has two distinct sequences across three sessions, not three.
    assert per_seed[8][42] == per_seed[8][43]
    assert MARKETS[8].redrawn(42).sequence_states != MARKETS[8].redrawn(43).sequence_states

    # Market 7's sell periods land late in two of its three sessions, which matters because
    # the uninformed resting price rises over a session (market 4: -47.8 francs in periods
    # 1-4 against -10.9 in period 14). A late sell period is therefore measured against a
    # higher baseline than an early buy period, which inflates sell-side D on its own.
    late = {}
    for s in (42, 43, 44):
        ins = per_seed[7][s]
        px = [i for i, c in enumerate(ins, 1) if c == "X"]
        py = [i for i, c in enumerate(ins, 1) if c == "Y"]
        late[s] = sum(py) / len(py) - sum(px) / len(px)
    assert late[43] > 3 and late[44] > 3, "seeds 43 and 44 put the sell periods late"
    assert late[42] < 0, "seed 42 puts them early"
