"""Scripted (non-LLM) baseline agents — design doc §14.2.

Three roles:

  zi  — Zero Intelligence (Gode & Sunder 1993). Redraws a random reservation price every
        time it acts, constrained only by its budget and inventory. Answers "how much of
        the result is the institution rather than the traders?"
  pi  — Prior Information. Values a certificate at its own dividend under its clue card if
        it holds one, and at the prior expectation otherwise. NEVER learns from price.
  re  — Rational Expectations. Informed agents use the true dividend; uninformed agents
        INFER the state from the prices that have traded, then use that dividend.

`re` is the engine's correctness gate: a market of RE agents must converge to 400 in X
periods and 175 in Y periods, with the certificates ending in the RE-predicted hands. If
it does not, the bug is in the engine and not in the LLM. Run it before spending an API
call.

Trading behaviour is the same for all three; only the valuation differs. It is a
competitive-concession rule rather than truthful quoting, because truthful quoting under a
price-improvement book collapses to the sellers' reservation value: sellers undercut each
other down to cost and nothing pushes the price back up to what buyers would pay. Instead:

  - take any standing quote that is profitable at your own valuation;
  - otherwise improve the book by conceding a fraction of the gap between the standing
    quote and your own valuation, never crossing your own valuation;
  - decide which side you are on by comparing your valuation with the going price.

Carrying a per-state price anchor across periods reproduces the cross-period learning the
paper measures in its table 7 — agents learning the price/state correspondence.
"""

from __future__ import annotations

import numpy as np

from ..markets import Market
from .base import (ACCEPT_STANDING, Agent, BroadcastContext, BroadcastDecision, NO_QUOTE,
                   QUOTE, TurnContext, TurnDecision)

# Fraction of the distance to your own valuation given up with each successive quote. A
# larger value converges faster but overshoots the clearing price.
_CONCESSION = 0.25
# How far from the remembered price an opening quote is placed when a side is empty.
_OPENING_MARGIN = 0.20


def _trade_prices(market_log: list[dict]) -> list[int]:
    """Prices that actually traded, however the trade was triggered (a broadcast
    acceptance, an accept_standing, or an automatic cross)."""
    return [e["price"] for e in market_log
            if e.get("outcome", "").startswith(("traded", "crossed_auto"))]


# How much belief a scripted agent's implied posterior puts on the state its valuation is
# nearest to, when there are more than two states. Only two-state markets can be inverted
# exactly; this is a reporting convenience so metrics see one shape, never an input to a
# decision.
_MULTI_STATE_MASS = 0.8


class ScriptedAgent(Agent):
    def __init__(self, seat: str, rng: np.random.Generator, market: Market) -> None:
        super().__init__(seat)
        self.rng = rng
        # These used to come from module constants, i.e. from market 3, so a scripted run
        # of any other market valued certificates at market 3's dividends while settling
        # them at its own. It ran, and every number it produced was wrong.
        self.mkt = market
        self.states = list(market.states)
        self.dividends = market.dividends[market.seat_type[seat]]
        self.prior_ev = market.prior_ev[market.seat_type[seat]]
        # Remembered clearing price per state; seeded with this agent's own prior
        # expectation and updated at each period boundary.
        self.anchor: dict[str, float] = {s: self.prior_ev for s in self.states}
        self._period = None
        self._pending: tuple[str, int] | None = None   # (state guess, last price seen)

    # ------------------------------------------------------------------ valuation

    def value(self, ctx) -> float:  # pragma: no cover - interface
        raise NotImplementedError

    def state_guess(self, ctx) -> str:
        """Which state this agent is acting as if it were. Used only to index the anchor."""
        if getattr(ctx, "card", None) in self.states:
            return ctx.card
        v = self.value(ctx)
        return min(self.states, key=lambda s: abs(v - self.dividends[s]))

    def _roll_period(self, ctx) -> None:
        """At a period boundary, commit the previous period's closing price to the anchor
        for whichever state that period turned out to be about. This is the scripted
        counterpart of a subject copying the year's outcome onto their profit sheet, and it
        is what produces convergence ACROSS periods rather than only within one."""
        if self._period == ctx.period:
            return
        if self._pending:
            state, price = self._pending
            self.anchor[state] = float(price)
        self._period = ctx.period
        self._pending = None

    def _remember(self, ctx) -> None:
        prices = _trade_prices(ctx.market_log)
        if prices:
            self._pending = (self.state_guess(ctx), prices[-1])

    # ------------------------------------------------------------------ pricing

    @staticmethod
    def _reference(ctx) -> float | None:
        """The going price: the last trade if there has been one, else the midpoint of the
        book, else nothing to go on."""
        prices = _trade_prices(ctx.market_log)
        if prices:
            return float(prices[-1])
        bid, ask = ctx.book.get("bid"), ctx.book.get("ask")
        if bid and ask:
            return (bid["price"] + ask["price"]) / 2.0
        return None

    def _open_from(self, ref: float | None, anchor: float) -> float:
        """Where to place a quote when that side of the book is empty.

        Once something has traded this period, the going price is the base — otherwise a
        quote posted after a trade would reset the market back to the anchor and the price
        could never climb, because each fill empties the side that was making progress.
        """
        return ref if ref is not None else anchor

    def _ask_price(self, v: float, standing: int | None, base: float) -> int | None:
        """An ask that improves the book without going below my own valuation."""
        if standing is None:
            return max(int(v) + 1, int(round(max(base, v) * (1 + _OPENING_MARGIN))))
        if standing <= v:
            return None                     # cannot undercut without selling at a loss
        return standing - max(1, int(_CONCESSION * (standing - v)))

    def _bid_price(self, v: float, standing: int | None, base: float,
                   cash: int) -> int | None:
        """A bid that improves the book without going above my own valuation."""
        if standing is None:
            px = min(int(v), int(round(max(base, 1.0) * (1 + _OPENING_MARGIN))))
        elif standing >= v:
            return None                     # cannot outbid without paying above value
        else:
            px = standing + max(1, int(_CONCESSION * (v - standing)))
        px = min(px, int(v), cash)
        return px if px >= 1 else None

    # ------------------------------------------------------------------ decisions

    def _posterior(self, v: float) -> dict:
        """The belief implied by treating the valuation as an expected dividend. Reported
        for parity with LLM agents so the metrics code has one shape to read.

        Two states invert exactly. Three or more do not — many beliefs give the same
        expected dividend — so the valuation is attributed to the nearest state and the
        rest share what is left, which is honest about being an approximation rather than
        pretending market 5's belief can be recovered from one number.
        """
        d = self.dividends
        if len(self.states) == 2:
            a, b = self.states
            if d[a] == d[b]:
                return {a: 0.5, b: 0.5}
            p = float(min(1.0, max(0.0, (v - d[b]) / (d[a] - d[b]))))
            return {a: round(p, 6), b: round(1 - p, 6)}
        near = min(self.states, key=lambda s: abs(v - d[s]))
        rest = (1.0 - _MULTI_STATE_MASS) / (len(self.states) - 1)
        return {s: round(_MULTI_STATE_MASS if s == near else rest, 6) for s in self.states}

    def decide_turn(self, ctx: TurnContext) -> TurnDecision:
        self._roll_period(ctx)
        v = self.value(ctx)
        bid, ask = ctx.book.get("bid"), ctx.book.get("ask")
        base = dict(posterior=self._posterior(v), reservation_buy=int(v),
                    reservation_sell=int(v), basis=self.basis,
                    raw={"scripted": self.kind, "value": round(v, 2),
                         "anchor": {k: round(a, 1) for k, a in self.anchor.items()}})
        self._remember(ctx)

        # 1. Take anything already on the book that is profitable at my valuation.
        if (ask and ask["seat"] != self.seat and ask["price"] <= v
                and ctx.cash >= ask["price"]):
            return TurnDecision(action=ACCEPT_STANDING, side="ask", **base)
        if bid and bid["seat"] != self.seat and bid["price"] >= v and ctx.certs >= 1:
            return TurnDecision(action=ACCEPT_STANDING, side="bid", **base)

        # 2. Otherwise improve the book on whichever side I belong to. With no going price
        #    yet, either side is defensible and the choice is random.
        ref = self._reference(ctx)
        open_base = self._open_from(ref, self.anchor[self.state_guess(ctx)])
        options: list[tuple[str, int]] = []
        if ctx.certs >= 1 and (ref is None or v < ref):
            p = self._ask_price(v, ask["price"] if ask else None, open_base)
            if p is not None and (ask is None or p < ask["price"]):
                options.append(("ask", p))
        if ctx.cash >= 1 and (ref is None or v > ref):
            p = self._bid_price(v, bid["price"] if bid else None, open_base, ctx.cash)
            if p is not None and (bid is None or p > bid["price"]):
                options.append(("bid", p))

        if not options:
            return TurnDecision(action=NO_QUOTE, **base)
        side, price = options[0] if len(options) == 1 else options[int(self.rng.integers(2))]
        return TurnDecision(action=QUOTE, side=side, price=price, **base)

    def respond_broadcast(self, ctx: BroadcastContext) -> BroadcastDecision:
        v = self.value(ctx)
        price = ctx.quote["price"]
        raw = {"scripted": self.kind, "value": round(v, 2)}
        if ctx.quote["side"] == "bid":                 # they buy, so I would sell
            ok = price >= v and ctx.certs >= 1
        else:                                          # they sell, so I would buy
            ok = price <= v and ctx.cash >= price
        return BroadcastDecision(response="accept" if ok else "decline", raw=raw)


class ZIAgent(ScriptedAgent):
    """Budget-constrained Zero Intelligence. Ignores its own dividends entirely."""

    kind = "zi"
    basis = "prior"

    def value(self, ctx) -> float:
        lo, hi = 1, max(2, min(getattr(ctx, "cash", 500), 500))
        return float(self.rng.integers(lo, hi))

    def state_guess(self, ctx) -> str:
        return "X"      # ZI has no view; the anchor is unused noise for it


class PIAgent(ScriptedAgent):
    """Prior Information: uses its clue card if it has one and the prior expectation
    otherwise, and never updates on observed prices."""

    kind = "pi"
    basis = "clue"

    def value(self, ctx) -> float:
        if getattr(ctx, "card", None) in self.states:
            return float(self.dividends[ctx.card])
        return float(self.prior_ev)


class REAgent(ScriptedAgent):
    """Rational Expectations: informed agents use the truth; uninformed agents read the
    state off the prices that have traded.

    Inference: compare the last trade price against what the market's strongest holder
    would pay in each state (400 under X, 175 under Y — the RE prices) and take the nearer.
    Until something trades there is nothing to infer from, so the prior is used.
    """

    kind = "re"
    basis = "price"

    # The fully-revealing price in each state: what the type with the highest dividend
    # there would pay (400 under X, 175 under Y in market 3). Per instance, not per class:
    # as a class attribute it was market 3's table for every market.
    @property
    def _RE_PRICE(self) -> dict[str, float]:
        return {s: max(d[s] for d in self.mkt.dividends.values()) for s in self.states}
    # A price must land this close to a revealing price before it is read as a signal.
    _BAND = 0.12

    def value(self, ctx) -> float:
        if getattr(ctx, "card", None) in self.states:
            return float(self.dividends[ctx.card])
        prices = _trade_prices(ctx.market_log)
        if not prices:
            return float(self.prior_ev)
        last = prices[-1]
        guess = min(self.states, key=lambda s: abs(last - self._RE_PRICE[s]))
        # Only a DECISIVE price reveals a state. Without this test the agent reads a
        # prior-driven price as a signal, and a no-information period collapses into a
        # self-confirming false consensus — the price sits near the state-Y level for no
        # reason, so everyone concludes Y, which keeps the price there.
        if abs(last - self._RE_PRICE[guess]) > self._BAND * self._RE_PRICE[guess]:
            return float(self.prior_ev)
        return float(self.dividends[guess])


BOT_REGISTRY = {"zi": ZIAgent, "pi": PIAgent, "re": REAgent}
