"""The five markets, checked against what the paper prints.

Two kinds of check, and the distinction matters:

  * Against the PAPER — expected dividends (Table 2's rightmost column), the market-1
    posteriors (Table 1), period counts and information spans (Table 1, body text).
    These catch a transcription slip in markets.py.
  * Against params.py — market 3 must come out byte-identical to the constants already
    running. This is what licenses rewiring ~200 call sites onto Market later: if the new
    representation reproduces the old one exactly, the rewiring cannot change a result.
"""

from __future__ import annotations

import pytest

from ps1982 import params
from ps1982.markets import MARKETS, sample_posterior

ALL = list(MARKETS.values())


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
    for m in ALL:
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
    for m in ALL:
        assert m.announce_no_info == (m.number in (1, 2, 5)), f"market {m.number}"


def test_only_market_1_lacks_the_constant_dividends_fact():
    for m in ALL:
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
    """The paper's own total, which only comes out right if every market agrees."""
    total = sum(len([p for p in range(1, MARKETS[n].n_periods + 1)
                     if MARKETS[n].theory_price(p)["RE"] != MARKETS[n].theory_price(p)["PI"]])
                for n in MARKETS)
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
