"""Standing quote book rules (design doc §5)."""

from __future__ import annotations

import pytest

from ps1982.book import (BID, BUDGET, Book, Holding, ILLEGAL_ACCEPT, NO_IMPROVEMENT,
                         NO_INVENTORY, Quote, settle)


def rich() -> Holding:
    return Holding(certs=2, cash=10_000)


def test_empty_side_accepts_any_price():
    b = Book()
    assert b.validate_quote("S01", "bid", 1, rich()) == (True, None)
    assert b.validate_quote("S01", "ask", 9_999, rich()) == (True, None)


def test_bid_must_strictly_improve():
    b = Book()
    b.set(Quote("S01", "bid", 300, 1))
    assert b.validate_quote("S02", "bid", 301, rich()) == (True, None)
    assert b.validate_quote("S02", "bid", 300, rich()) == (False, NO_IMPROVEMENT)
    assert b.validate_quote("S02", "bid", 299, rich()) == (False, NO_IMPROVEMENT)


def test_ask_must_strictly_improve():
    b = Book()
    b.set(Quote("S01", "ask", 300, 1))
    assert b.validate_quote("S02", "ask", 299, rich()) == (True, None)
    assert b.validate_quote("S02", "ask", 300, rich()) == (False, NO_IMPROVEMENT)
    assert b.validate_quote("S02", "ask", 301, rich()) == (False, NO_IMPROVEMENT)


def test_self_improvement_is_allowed():
    """An agent may replace its own standing quote with a better one (§5.2)."""
    b = Book()
    b.set(Quote("S01", "bid", 300, 1))
    assert b.validate_quote("S01", "bid", 310, rich()) == (True, None)
    assert b.validate_quote("S01", "bid", 290, rich()) == (False, NO_IMPROVEMENT)


def test_no_improvement_rule_disabled_replaces_at_any_price():
    """rules.price_improvement=False reproduces the paper's footnote 3 literally:
    'Only one (the last) bid and offer are outstanding'."""
    b = Book(price_improvement=False)
    b.set(Quote("S01", "bid", 300, 1))
    assert b.validate_quote("S02", "bid", 100, rich()) == (True, None)


def test_budget_and_inventory():
    b = Book()
    assert b.validate_quote("S01", "bid", 501, Holding(2, 500)) == (False, BUDGET)
    assert b.validate_quote("S01", "bid", 500, Holding(2, 500)) == (True, None)
    assert b.validate_quote("S01", "ask", 200, Holding(0, 500)) == (False, NO_INVENTORY)


def test_crossing_detection():
    b = Book()
    b.set(Quote("S09", "ask", 340, 1))
    assert b.crosses("bid", 339) is None
    assert b.crosses("bid", 340).seat == "S09"
    assert b.crosses("bid", 400).seat == "S09"
    b.clear()
    b.set(Quote("S03", "bid", 300, 1))
    assert b.crosses("ask", 301) is None
    assert b.crosses("ask", 300).seat == "S03"
    assert b.crosses("ask", 250).seat == "S03"


def test_cannot_accept_own_quote():
    b = Book()
    b.set(Quote("S01", "ask", 300, 1))
    assert b.validate_accept("S01", "ask", rich()) == (False, ILLEGAL_ACCEPT)
    assert b.validate_accept("S02", "ask", rich()) == (True, None)


def test_accept_requires_the_right_resource():
    b = Book()
    b.set(Quote("S01", "ask", 300, 1))
    assert b.validate_accept("S02", "ask", Holding(2, 299)) == (False, BUDGET)
    b.clear()
    b.set(Quote("S01", "bid", 300, 1))
    assert b.validate_accept("S02", "bid", Holding(0, 999)) == (False, NO_INVENTORY)


def test_accept_missing_quote():
    assert Book().validate_accept("S02", "ask", rich()) == (False, ILLEGAL_ACCEPT)


def test_stale_quote_second_check():
    """A quote can go stale: its poster may have spent the cash or sold the certificate
    since posting (§5.5)."""
    b = Book()
    q = Quote("S01", "bid", 300, 1)
    assert b.poster_can_still_settle(q, Holding(0, 300)) is True
    assert b.poster_can_still_settle(q, Holding(0, 299)) is False
    a = Quote("S01", "ask", 300, 1)
    assert b.poster_can_still_settle(a, Holding(1, 0)) is True
    assert b.poster_can_still_settle(a, Holding(0, 9999)) is False


def test_spread_needs_both_sides():
    b = Book()
    assert b.spread is None
    b.set(Quote("S01", "bid", 300, 1))
    assert b.spread is None
    b.set(Quote("S09", "ask", 340, 2))
    assert b.spread == 40


def test_period_end_clears_both_sides():
    b = Book()
    b.set(Quote("S01", "bid", 300, 1))
    b.set(Quote("S09", "ask", 340, 2))
    b.clear()
    assert b.bid is None and b.ask is None


def test_settle_moves_one_certificate():
    buyer, seller = Holding(2, 1000), Holding(2, 1000)
    settle(buyer, seller, 300)
    assert (buyer.certs, buyer.cash) == (3, 700)
    assert (seller.certs, seller.cash) == (1, 1300)


def test_settle_refuses_to_go_negative():
    with pytest.raises(AssertionError):
        settle(Holding(0, 100), Holding(1, 0), 300)
