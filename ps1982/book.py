"""The standing quote book (design doc §5).

At most one bid and one ask stand at any time — the paper's footnote 3: "Only one (the
last) bid and offer are outstanding at any time. Sellers (buyers) are free to accept any
public bid (offer) they wish."

The baseline adds a price-improvement requirement on top of that (design doc §0.4), which
is a deliberate deviation: the paper says "the last", not "the best". Setting
``price_improvement=False`` restores the paper's literal rule.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

BID, ASK = "bid", "ask"


def other_side(side: str) -> str:
    return ASK if side == BID else BID


@dataclass(frozen=True)
class Quote:
    seat: str
    side: str
    price: int
    posted_at: int          # global action sequence number when it was posted

    def to_dict(self) -> dict:
        return {"seat": self.seat, "side": self.side, "price": self.price,
                "posted_at": self.posted_at}


@dataclass
class Holding:
    """One agent's within-period position. Neither field may ever go negative — the
    subject instructions say so explicitly ("Your holdings of certificates may never go
    below zero. Your francs on hand may never go below zero.")."""

    certs: int
    cash: int

    def to_dict(self) -> dict:
        return {"certs": self.certs, "cash": self.cash}


# Rejection reasons, mirrored in the `violation` event and in metrics.
BUDGET = "budget"
NO_INVENTORY = "no_inventory"
NO_IMPROVEMENT = "no_improvement"
STALE_QUOTE = "stale_quote"
ILLEGAL_ACCEPT = "illegal_accept"
MALFORMED = "malformed"


class Book:
    def __init__(self, *, price_improvement: bool = True) -> None:
        self.price_improvement = price_improvement
        self.bid: Quote | None = None
        self.ask: Quote | None = None

    # ------------------------------------------------------------------ state

    def clear(self) -> None:
        """Period end: both sides are wiped, nothing carries over (design doc §5.5)."""
        self.bid = None
        self.ask = None

    def get(self, side: str) -> Quote | None:
        return self.bid if side == BID else self.ask

    def set(self, quote: Quote | None, side: str | None = None) -> None:
        side = side or (quote.side if quote else None)
        if side == BID:
            self.bid = quote
        else:
            self.ask = quote

    @property
    def spread(self) -> int | None:
        """Defined only when both sides are populated (design doc §1)."""
        if self.bid is None or self.ask is None:
            return None
        return self.ask.price - self.bid.price

    def snapshot(self) -> dict:
        return {"bid": self.bid.to_dict() if self.bid else None,
                "ask": self.ask.to_dict() if self.ask else None,
                "spread": self.spread}

    # ------------------------------------------------------------------ validation

    def validate_quote(self, seat: str, side: str, price: int, holding: Holding
                       ) -> tuple[bool, str | None]:
        """VALIDATE, in the order given by design doc §5.2. Returns (ok, reason).

        Crossing is NOT rejected here — a crossing quote is legal and triggers an
        automatic trade; see ``crosses``.
        """
        if not isinstance(price, int) or price <= 0:
            return False, MALFORMED

        # 1. budget / inventory
        if side == BID:
            if price > holding.cash:
                return False, BUDGET
        else:
            if holding.certs < 1:
                return False, NO_INVENTORY

        # 2. price improvement. An empty slot accepts any price; improving your OWN
        #    standing quote is allowed (design doc §5.2).
        if self.price_improvement:
            standing = self.get(side)
            if standing is not None:
                if side == BID and price <= standing.price:
                    return False, NO_IMPROVEMENT
                if side == ASK and price >= standing.price:
                    return False, NO_IMPROVEMENT

        return True, None

    def crosses(self, side: str, price: int) -> Quote | None:
        """The opposite standing quote this new quote would cross, if any (design doc §5.3).

        A quote from the same seat as the opposite standing quote does NOT count as a
        cross — that would be trading with yourself, which is forbidden.
        """
        opp = self.get(other_side(side))
        if opp is None:
            return None
        if side == BID and price >= opp.price:
            return opp
        if side == ASK and price <= opp.price:
            return opp
        return None

    def validate_accept(self, seat: str, side: str, holding: Holding) -> tuple[bool, str | None]:
        """Can ``seat`` accept the standing quote on ``side``?

        ``side`` names the quote being accepted: accepting the standing ask means buying.
        """
        standing = self.get(side)
        if standing is None:
            return False, ILLEGAL_ACCEPT
        if standing.seat == seat:
            return False, ILLEGAL_ACCEPT          # accepting your own quote is forbidden
        if side == ASK:                            # accepting an ask = buying
            if holding.cash < standing.price:
                return False, BUDGET
        else:                                      # accepting a bid = selling
            if holding.certs < 1:
                return False, NO_INVENTORY
        return True, None

    def poster_can_still_settle(self, quote: Quote, holding: Holding) -> bool:
        """Second check, run immediately before a trade settles (design doc §5.5).

        A quote can go stale: its poster may have spent the cash or sold the certificate
        in a later turn. Such a quote fails silently and is recorded as a violation.
        """
        if quote.side == BID:
            return holding.cash >= quote.price
        return holding.certs >= 1


def settle(buyer: Holding, seller: Holding, price: int) -> None:
    """Move one certificate for ``price`` francs. Callers must have validated both sides."""
    buyer.cash -= price
    buyer.certs += 1
    seller.cash += price
    seller.certs -= 1
    assert buyer.cash >= 0 and seller.certs >= 0, "settlement drove a balance negative"
