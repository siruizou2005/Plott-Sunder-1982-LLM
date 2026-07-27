"""The market engine: Session -> Period -> Round -> Turn (design doc §4-§9).

The seven-phase turn is the heart of it:

  ① BRIEF     engine pushes; the agent asks for nothing
  ② COMMIT    posterior / reservation prices / basis
  ③ ACT       no_quote | quote | accept_standing        (② and ③ are ONE model call)
  ④ VALIDATE  budget/inventory -> price improvement -> crossing
  ⑤ BROADCAST push concurrently to every feasible counterparty
  ⑥ MATCH     0 acceptors -> post; 1 -> trade; >1 -> random winner, losers erased
  ⑦ SETTLE    move cash and certificates, short trade note

Concurrency: turn decisions are strictly serial — the design requires a rotating order with
each agent seeing the market as it stands. Broadcast responses are the ONLY parallel step,
which is safe because respondents cannot see each other and the engine resolves them all
afterwards.
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import numpy as np

from .agents import (ACCEPT_STANDING, Agent, BroadcastContext, NO_QUOTE, QUOTE,
                     TurnContext, build_agent)
from .book import BID, Book, Holding, MALFORMED, Quote, settle
from .config import Config
from .events import EventStream
from .llm.base import Usage
from .markets import FIXED_COST, INITIAL_CASH, INITIAL_CERTS
from .params import SEAT_NAMES
from .prompts import build_period_end_brief, build_trade_feedback_brief

# Market-log outcome codes (design doc §10.1).
TRADED = "traded"
POSTED = "posted"
SUPERSEDED = "superseded"
CROSSED_AUTO = "crossed_auto"


@dataclass
class SeatState:
    seat: str
    holding: Holding
    # {kind, period, round, at, text} — kind is period_end or trade_feedback. The two are
    # windowed separately when a briefing is built; see Engine._notes_for.
    reflections: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    # Acceptances this period that did not go through. Reset every period, like the
    # market log, since holdings reset with it.
    not_selected: list[dict] = field(default_factory=list)
    total_profit: int = 0


class Engine:
    def __init__(self, config: Config, stream: EventStream, *, session: int = 0,
                 resume: dict | None = None) -> None:
        self.cfg = config
        self.stream = stream
        self.session = session
        self.rules = config.rules
        # The market being run: roster, dividends, prior, state set, realized sequence.
        # Resolved ONCE here rather than read per use, because `random_prior` redraws from
        # the seed and re-resolving would be a fresh draw each time it was touched.
        self.mkt = config.market_spec
        # One seeded generator, used for exactly two things: the per-round seat order and
        # the random tie-break when several agents accept the same quote. The paper:
        # "Any ties in bids or acceptance will be resolved by random choice."
        self.rng = np.random.default_rng(config.seed + session)
        self.book = Book(price_improvement=self.rules.price_improvement)
        self.state: dict[str, SeatState] = {
            s: SeatState(s, Holding(INITIAL_CERTS, INITIAL_CASH)) for s in self.mkt.seats}
        # Seat -> the name agents call each other by. Shuffled per session from the same
        # seeded generator: a fixed map would tie whatever prior the model holds about a
        # name to the same type and the same insider status in every repetition, so it
        # would never average out. See params.SEAT_NAMES.
        # A resumed run must keep the mapping it started with, or the same seat would be a
        # different person to everyone for the rest of the session.
        self.names: dict[str, str] = dict(resume["names"]) if resume else dict(
            zip(self.mkt.seats, [SEAT_NAMES[i] for i in self.rng.permutation(len(SEAT_NAMES))]))
        self.agents: dict[str, Agent] = {
            s: build_agent(s, config.spec_for(s), self.rules,
                           np.random.default_rng(config.seed + session + i),
                           self.mkt, self.names[s])
            for i, s in enumerate(self.mkt.seats)}
        self.market_log: list[dict] = []      # agent-visible, reset each period
        self.action_seq = 0                   # market actions within the current period
        self.global_trade_seq = 0
        self.usage = Usage()
        self.calls = 0
        self.cards: dict[str, str | None] = {}
        self.info = "none"
        self.theta = "X"
        self.period = 0
        self.completed_periods = 0
        self.prior_elapsed_s = 0.0
        # Set by the CLI so a checkpoint lands the moment a period settles.
        self.on_period_done = None
        if resume:
            self._restore(resume)

    # ------------------------------------------------------------------ resume

    def snapshot(self) -> dict:
        """Everything needed to carry on from the last settled period.

        Period granularity is the natural unit: a half-finished period has paid no
        dividends, so it is not a scientifically usable partial anyway, and at a period
        boundary holdings, the book and the market log have all just been reset — which
        leaves only the state that genuinely crosses periods.

        The RNG state is the part that is easy to forget. Reseeding from `seed` would
        replay the round orders and tie-breaks already used, so a resumed run would no
        longer be the same experiment as the one it continues.
        """
        return {
            "version": 1,
            "session": self.session,
            "completed_periods": self.completed_periods,
            "names": dict(self.names),
            "rng_state": self.rng.bit_generator.state,
            "global_trade_seq": self.global_trade_seq,
            "calls": self.calls,
            "usage": self.usage.to_dict(),
            "elapsed_s": round(self.prior_elapsed_s, 1),
            "next_event_id": self.stream.next_id(),
            "seats": {s: {"reflections": st.reflections, "history": st.history,
                          "total_profit": st.total_profit}
                      for s, st in self.state.items()},
        }

    def _restore(self, snap: dict) -> None:
        if snap.get("version") != 1:
            raise ValueError(f"unsupported checkpoint version {snap.get('version')!r}")
        if snap["session"] != self.session:
            raise ValueError("checkpoint is for a different session index")
        self.rng.bit_generator.state = snap["rng_state"]
        self.completed_periods = snap["completed_periods"]
        self.global_trade_seq = snap["global_trade_seq"]
        self.calls = snap["calls"]
        self.usage = Usage(**snap["usage"])
        self.prior_elapsed_s = snap.get("elapsed_s", 0.0)
        for seat, st in snap["seats"].items():
            self.state[seat].reflections = list(st["reflections"])
            self.state[seat].history = list(st["history"])
            self.state[seat].total_profit = st["total_profit"]

    # ------------------------------------------------------------------ helpers

    def h(self, seat: str) -> Holding:
        return self.state[seat].holding

    def _account(self, raw: dict | None) -> None:
        """Fold one model exchange into the session token/cost totals."""
        if not raw or "usage" not in raw:
            return
        u = raw.get("usage") or {}
        self.usage += Usage(
            prompt_tokens=u.get("prompt_tokens", 0),
            completion_tokens=u.get("completion_tokens", 0),
            cache_hit_tokens=u.get("cache_hit_tokens", 0),
            cache_miss_tokens=u.get("cache_miss_tokens", 0),
            reasoning_tokens=u.get("reasoning_tokens", 0))
        self.calls += 1

    def _emit_book(self) -> None:
        self.stream.emit("book", self.book.snapshot(), agent_visible=True)

    def _log_entry(self, seat: str, side: str, price: int, outcome: str, *,
                   action: str = QUOTE, buyer: str | None = None,
                   seller: str | None = None) -> dict:
        """Append to the agent-visible market log.

        ``side`` is the side of the QUOTE, which on its own is ambiguous for an
        acceptance — accepting a standing bid means the acceptor sold. So buyer and seller
        are recorded explicitly and the briefing spells them out; otherwise an agent
        reading "S10 bid 200" would conclude S10 was buying when it was selling.
        """
        self.action_seq += 1
        entry = {"seq": self.action_seq, "seat": seat, "action": action, "side": side,
                 "price": price, "outcome": outcome, "buyer": buyer, "seller": seller}
        self.market_log.append(entry)
        return entry

    def _mark_superseded(self, old: Quote) -> None:
        """The replaced quote's log line changes from 'posted' to 'superseded' — subjects
        watching a blackboard would see the old quote wiped, so agents see it too."""
        for e in reversed(self.market_log):
            if e["seat"] == old.seat and e["side"] == old.side and e["price"] == old.price \
                    and e["outcome"] == POSTED:
                e["outcome"] = SUPERSEDED
                return

    def _visible_log(self) -> list[dict]:
        return [dict(e) for e in self.market_log]

    def _notes_for(self, seat: str) -> list[dict]:
        """The notes carried into a prompt: the two kinds windowed SEPARATELY.

        Under one shared window the post-trade notes crowd out the year-end reflection —
        measured at 3.4 trade notes per seat per period at three rounds, against a window
        of three — and §8 calls that reflection the design's main learning node.
        """
        notes = self.state[seat].reflections
        year_end = [n for n in notes if n["kind"] == "period_end"][-self.rules.period_end_notes:]
        trades = [n for n in notes if n["kind"] != "period_end"][-self.rules.trade_notes:]
        keep = {id(n) for n in year_end} | {id(n) for n in trades}
        return [n for n in notes if id(n) in keep]      # chronological, as written

    def _memory(self, seat: str) -> dict:
        """Private memory, identical for every kind of call this seat receives."""
        st = self.state[seat]
        return {"reflections": self._notes_for(seat), "history": list(st.history),
                "not_selected": st.not_selected[-self.rules.not_selected_window:]}

    def _turn_ctx(self, seat: str, round_no: int, turn_seq: int) -> TurnContext:
        st = self.state[seat]
        return TurnContext(
            seat=seat, period=self.period, round_no=round_no, turn_seq=turn_seq,
            info=self.info, card=self.cards[seat], certs=st.holding.certs,
            cash=st.holding.cash, book=self.book.snapshot(),
            market_log=self._visible_log(), names=self.names, **self._memory(seat))

    def _violation(self, seat: str, attempted: str, side: str | None, price: int | None,
                   reason: str, extra: dict | None = None) -> None:
        """A rejected attempt. It is INVISIBLE to everyone else — the design deliberately
        keeps it off the public record so it cannot become an information channel
        (design doc §5.2)."""
        payload = {"attempted_action": attempted, "side": side, "price": price,
                   "reason": reason}
        if extra:
            payload.update(extra)
        self.stream.emit("violation", payload, seat=seat, agent_visible=False)

    # ------------------------------------------------------------------ trading

    def _settle_trade(self, buyer: str, seller: str, price: int, trigger: str) -> None:
        settle(self.h(buyer), self.h(seller), price)
        self.global_trade_seq += 1
        self.stream.emit("trade", {
            "buyer": buyer, "seller": seller, "price": price, "trigger": trigger,
            "global_seq": self.global_trade_seq,
            "buyer_after": self.h(buyer).to_dict(),
            "seller_after": self.h(seller).to_dict(),
        }, agent_visible=True)
        self._emit_book()
        self._trade_feedback(buyer, seller, price)

    def _trade_feedback(self, buyer: str, seller: str, price: int) -> None:
        """A one-or-two sentence note from each side of a trade (design doc §6 ⑦).

        Both sides are asked CONCURRENTLY. These calls sit on the turn's critical path —
        no other agent can act until they return — and with thinking on each one costs
        seconds, so running them one after the other would add hours across a full session
        for no reason: the two notes are independent.

        Scripted agents return nothing and cost no call.
        """
        jobs = [(buyer, "buy", seller), (seller, "sell", buyer)]
        jobs = [j for j in jobs if hasattr(self.agents[j[0]], "reflect_system_text")]
        if not jobs:
            return

        def ask(job):
            seat, side, counterparty = job
            st = self.state[seat]
            user = build_trade_feedback_brief(
                market=self.mkt, seat=seat, period=self.period, round_no=self.stream.round, side=side,
                price=price, counterparty=counterparty, info=self.info,
                card=self.cards[seat], certs=st.holding.certs, cash=st.holding.cash,
                book=self.book.snapshot(), market_log=self._visible_log(),
                names=self.names, rules=self.rules, **self._memory(seat))
            try:
                out = self.agents[seat].reflect("trade_feedback",
                                                self.agents[seat].reflect_system_text, user)
            except Exception as e:  # noqa: BLE001 — a failed note must not kill the trade
                out = {"text": "", "raw": {"error": str(e)}}
            return seat, side, out

        if len(jobs) == 1:
            results = [ask(jobs[0])]
        else:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(ask, jobs))

        for seat, side, out in results:
            self._account(out.get("raw"))
            text = (out.get("text") or "").strip()
            if out.get("raw", {}).get("usage"):
                self.stream.emit("model_turn", {"purpose": "trade_feedback", **out["raw"]},
                                 seat=seat, agent_visible=False)
            if not text:
                # Never drop this quietly. Reasoning shares the output budget, so a note
                # can come back empty having spent the lot thinking — and a lost note is
                # lost memory, which changes every later decision this seat makes.
                self._violation(seat, "reflect", None, None, "empty_note",
                                {"kind": "trade_feedback",
                                 "usage": (out.get("raw") or {}).get("usage")})
                continue
            verb = "bought" if side == "buy" else "sold"
            self.state[seat].reflections.append({
                "kind": "trade_feedback", "period": self.period, "round": self.stream.round,
                "at": f"after you {verb} one certificate at {price}", "text": text})
            self.stream.emit("reflection", {"kind": "trade_feedback", "text": text},
                             seat=seat, agent_visible=False)

    # ------------------------------------------------------------------ broadcast

    def _feasible_counterparties(self, quote: Quote) -> list[str]:
        """bid -> everyone else holding at least one certificate;
        ask -> everyone else with enough francs (design doc §6 ⑤)."""
        out = []
        for s in self.mkt.seats:
            if s == quote.seat:
                continue
            h = self.h(s)
            if quote.side == BID and h.certs >= 1:
                out.append(s)
            elif quote.side != BID and h.cash >= quote.price:
                out.append(s)
        return out

    def _broadcast(self, quote: Quote) -> None:
        recipients = self._feasible_counterparties(quote)
        snapshot = self.book.snapshot()
        vlog = self._visible_log()
        qd = quote.to_dict()

        def ask_one(seat: str):
            st = self.state[seat]
            ctx = BroadcastContext(
                seat=seat, period=self.period, quote=qd, info=self.info,
                card=self.cards[seat], certs=st.holding.certs, cash=st.holding.cash,
                book=snapshot, market_log=vlog, names=self.names, **self._memory(seat))
            try:
                return seat, self.agents[seat].respond_broadcast(ctx)
            except Exception as e:  # noqa: BLE001 — one agent's failure must not kill the round
                from .agents.base import BroadcastDecision
                return seat, BroadcastDecision(response="decline", malformed=True,
                                               raw={"error": str(e)})

        results: list[tuple[str, object]] = []
        if recipients:
            workers = max(1, min(self.cfg.broadcast_workers, len(recipients)))
            if workers > 1 and self.cfg.uses_llm:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    results = list(pool.map(ask_one, recipients))
            else:
                results = [ask_one(s) for s in recipients]

        responses = []
        for seat, dec in results:
            responses.append({"seat": seat, "response": dec.response, "why": dec.why,
                              "malformed": dec.malformed})
            self._account(dec.raw)
            if dec.raw and "usage" in dec.raw:
                self.stream.emit("model_turn", {"purpose": "broadcast", **dec.raw},
                                 seat=seat, agent_visible=False)
            if dec.malformed:
                self._violation(seat, "broadcast_response", quote.side, quote.price,
                                MALFORMED)

        said_yes = [r["seat"] for r in responses if r["response"] == "accept"]
        # Re-check every acceptor: an earlier trade this turn may have drained them. In the
        # engine as it stands this can never fire — _feasible_counterparties applies the
        # same test up front and nothing mutates holdings in between — so it is a guard
        # against a future change, not a live branch.
        acceptors = [s for s in said_yes if self._can_take(quote, s)]
        could_not_settle = [s for s in said_yes if s not in acceptors]

        winner = None
        losers: list[str] = []
        if len(acceptors) == 1:
            winner = acceptors[0]
        elif len(acceptors) > 1:
            winner = str(self.rng.choice(acceptors))
            losers = [s for s in acceptors if s != winner]

        # Tell the ones who missed out. A subject who called an acceptance and watched the
        # experimenter point at someone else remembers doing it; a stateless agent has no
        # trace of it at all, which was an artifact of the architecture rather than a
        # design choice. What stays hidden is HOW MANY accepted — that count is the latent
        # demand curve, the one thing a human experiment cannot record (design doc §0.2).
        why_of = {r["seat"]: r.get("why") for r in responses}
        for seat, reason in ([(s, "not_drawn") for s in losers]
                             + [(s, "could_not_settle") for s in could_not_settle]):
            self.state[seat].not_selected.append({
                "period": self.period, "round": self.stream.round,
                "seq": qd.get("posted_at"), "quote_seat": quote.seat,
                "side": quote.side, "price": quote.price,
                "why": why_of.get(seat), "reason": reason,
            })

        # The FULL response set including losers goes in the computer log only. Aggregating
        # acceptor counts by price is how the potential demand curve is built — data no
        # human experiment can obtain (design doc §0.2).
        self.stream.emit("broadcast", {
            "quote": qd, "recipients": recipients, "responses": responses,
            "n_accept": len(acceptors), "winner": winner, "losers": losers,
        }, seat=quote.seat, agent_visible=False)

        if winner is None:
            # ⑥ n == 0: the quote becomes the standing quote on its side.
            old = self.book.get(quote.side)
            if old is not None:
                self._mark_superseded(old)
            self.book.set(quote)
            self._log_entry(quote.seat, quote.side, quote.price, POSTED)
            self.stream.emit("action", {"action": QUOTE, "side": quote.side,
                                        "price": quote.price, "outcome": POSTED,
                                        "seq": self.action_seq},
                             seat=quote.seat, agent_visible=True)
            self._emit_book()
            return

        # ⑥ n >= 1: trade. The quote never reaches the book.
        buyer, seller = ((quote.seat, winner) if quote.side == BID else (winner, quote.seat))
        self._log_entry(quote.seat, quote.side, quote.price, TRADED,
                        buyer=buyer, seller=seller)
        self.stream.emit("action", {"action": QUOTE, "side": quote.side,
                                    "price": quote.price, "outcome": TRADED,
                                    "counterparty": winner, "buyer": buyer, "seller": seller,
                                    "seq": self.action_seq},
                         seat=quote.seat, agent_visible=True)
        self._settle_trade(buyer, seller, quote.price, "broadcast")

    def _can_take(self, quote: Quote, seat: str) -> bool:
        h = self.h(seat)
        return h.certs >= 1 if quote.side == BID else h.cash >= quote.price

    # ------------------------------------------------------------------ turn

    def run_turn(self, seat: str, round_no: int, turn_seq: int) -> bool:
        """Run one agent's turn. Returns True if it took any market action."""
        ctx = self._turn_ctx(seat, round_no, turn_seq)
        agent = self.agents[seat]

        # ① BRIEF — recorded verbatim so the log holds the exact bytes the model saw.
        #
        # Rendered from the same TurnContext the agent is about to render from, so the two
        # cannot disagree. Keep every argument sourced from `ctx`: reading some from `ctx`
        # and some from `self` is how this call and LLMAgent.decide_turn drift apart.
        if agent.kind == "llm":
            from .prompts import build_brief
            brief_text = build_brief(
                market=self.mkt, seat=ctx.seat, period=ctx.period, round_no=ctx.round_no,
                turn_seq=ctx.turn_seq, info=ctx.info, card=ctx.card, certs=ctx.certs,
                cash=ctx.cash, book=ctx.book, market_log=ctx.market_log,
                reflections=ctx.reflections, history=ctx.history,
                not_selected=ctx.not_selected, names=ctx.names, rules=self.rules)
            self.stream.emit("brief", {"text": brief_text}, seat=seat, agent_visible=False)

        # ②③ COMMIT + ACT — one model call.
        try:
            dec = agent.decide_turn(ctx)
        except Exception as e:  # noqa: BLE001 — a failed agent holds; the round survives
            self._violation(seat, "decide_turn", None, None, MALFORMED, {"error": str(e)})
            return False

        self._account(dec.raw)
        if dec.raw and "usage" in dec.raw:
            self.stream.emit("model_turn", {"purpose": "turn", **dec.raw},
                             seat=seat, agent_visible=False)
        if self.rules.elicit_beliefs and dec.posterior is not None:
            self.stream.emit("agent_view", dec.view(), seat=seat, agent_visible=False)
        if dec.malformed:
            self._violation(seat, "decide_turn", dec.side, dec.price, MALFORMED,
                            {"schema_errors": (dec.raw or {}).get("schema_errors")})
            return False

        if dec.action == NO_QUOTE:
            self.stream.emit("action", {"action": NO_QUOTE}, seat=seat, agent_visible=False)
            return False

        if dec.action == ACCEPT_STANDING:
            return self._do_accept(seat, dec)
        if dec.action == QUOTE:
            return self._do_quote(seat, dec)

        self._violation(seat, str(dec.action), dec.side, dec.price, MALFORMED)
        return False

    def _do_accept(self, seat: str, dec) -> bool:
        side = dec.side
        ok, reason = self.book.validate_accept(seat, side, self.h(seat))
        if not ok:
            self._violation(seat, ACCEPT_STANDING, side, None, reason)
            return False
        standing = self.book.get(side)
        # Second check on the POSTER (design doc §5.5): they may have spent the cash or
        # sold the certificate since posting.
        if not self.book.poster_can_still_settle(standing, self.h(standing.seat)):
            self.book.set(None, side)
            self._violation(standing.seat, "standing_quote", side, standing.price, "stale_quote")
            self._emit_book()
            return False

        self.book.set(None, side)
        # Accepting an ask means buying; accepting a bid means selling.
        buyer, seller = ((seat, standing.seat) if side != BID else (standing.seat, seat))
        self._log_entry(seat, side, standing.price, TRADED, action=ACCEPT_STANDING,
                        buyer=buyer, seller=seller)
        self.stream.emit("action", {"action": ACCEPT_STANDING, "side": side,
                                    "price": standing.price, "outcome": TRADED,
                                    "counterparty": standing.seat, "buyer": buyer,
                                    "seller": seller, "seq": self.action_seq},
                         seat=seat, agent_visible=True)
        self._settle_trade(buyer, seller, standing.price, ACCEPT_STANDING)
        return True

    def _do_quote(self, seat: str, dec) -> bool:
        side, price = dec.side, dec.price
        if side not in ("bid", "ask") or not isinstance(price, int):
            self._violation(seat, QUOTE, side, price, MALFORMED)
            return False

        # ④ VALIDATE
        ok, reason = self.book.validate_quote(seat, side, price, self.h(seat))
        if not ok:
            self._violation(seat, QUOTE, side, price, reason)
            return False

        # ④ crossing -> automatic trade at the STANDING quote's price (design doc §5.3)
        opp = self.book.crosses(side, price)
        if opp is not None and opp.seat != seat:
            if not self.book.poster_can_still_settle(opp, self.h(opp.seat)):
                self.book.set(None, opp.side)
                self._violation(opp.seat, "standing_quote", opp.side, opp.price, "stale_quote")
                self._emit_book()
                return self._post_or_broadcast(seat, side, price)
            # The taker must be able to afford the standing price, which may differ from
            # the price they named.
            h = self.h(seat)
            if side == BID and h.cash < opp.price:
                self._violation(seat, QUOTE, side, price, "budget")
                return False
            self.book.set(None, opp.side)
            buyer, seller = ((seat, opp.seat) if side == BID else (opp.seat, seat))
            self._log_entry(seat, side, opp.price, CROSSED_AUTO, buyer=buyer, seller=seller)
            self.stream.emit("action", {"action": QUOTE, "side": side, "price": price,
                                        "outcome": CROSSED_AUTO, "settled_at": opp.price,
                                        "counterparty": opp.seat, "buyer": buyer,
                                        "seller": seller, "seq": self.action_seq},
                             seat=seat, agent_visible=True)
            self._settle_trade(buyer, seller, opp.price, CROSSED_AUTO)
            return True

        return self._post_or_broadcast(seat, side, price)

    def _post_or_broadcast(self, seat: str, side: str, price: int) -> bool:
        quote = Quote(seat=seat, side=side, price=price, posted_at=self.action_seq + 1)
        self._broadcast(quote)      # ⑤⑥⑦ — posts to the book if nobody accepts
        return True

    # ------------------------------------------------------------------ period

    def _theory_of(self, period: int) -> dict:
        """This period's RE/PI, conditioned on the clue that period actually carries.

        "The clues of all insiders were identical", so one card identifies the period;
        None in a no-information period, which is the prior for both models.
        """
        card = next((c for c in self.mkt.cards_for_period(period).values() if c), None)
        return {**self.mkt.theory_price(period, card),
                "holder": self.mkt.theory_holder(period, card),
                "info": self.mkt.sequence_info[period - 1],
                "state": self.mkt.sequence_states[period - 1]}

    def run_period(self, period: int, theta: str, info: str) -> None:
        self.period = period
        self.theta = theta
        self.info = info
        self.stream.period = period
        self.stream.round = 0
        self.cards = self.mkt.clue_cards(info, theta, period)
        self.book.clear()
        self.market_log = []
        self.action_seq = 0
        for s in self.mkt.seats:
            self.state[s].holding = Holding(INITIAL_CERTS, INITIAL_CASH)
            # Scoped to the year, like the market log: holdings reset with it, so last
            # year's missed acceptances say nothing about this year's position.
            self.state[s].not_selected = []

        # theta, the clue cards and the insider roster are all hidden from agents.
        # The authoritative prediction for THIS period, computed from the clue actually
        # dealt above. period_start is the only place that is guaranteed correct: a
        # redrawn market-1 run can land on Table 1's state for a period and still hold a
        # different sample, and nothing keyed by (info, state) can tell the two apart.
        _card = next((c for c in self.cards.values() if c), None)
        self.stream.emit("period_start", {
            "period": period, "state": theta, "info": info,
            "cards": dict(self.cards),
            "theory": {**self.mkt.theory_price(period, _card),
                       "holder": self.mkt.theory_holder(period, _card)},
            "insiders": [s for s in self.mkt.seats if self.cards[s] is not None] if info != "none" else [],
            "fixed_insiders": list(self.mkt.insiders),
        }, agent_visible=False)
        self._emit_book()

        for round_no in range(1, self.cfg.max_rounds_per_period + 1):
            self.stream.round = round_no
            order = [self.mkt.seats[i] for i in self.rng.permutation(len(self.mkt.seats))]
            self.stream.emit("round_start", {"round": round_no, "order": order},
                             agent_visible=False)
            acted = False
            for turn_seq, seat in enumerate(order, start=1):
                if self.run_turn(seat, round_no, turn_seq):
                    acted = True
            # ⑦ design doc §7: stop early if a whole round passed with no market action.
            if not acted:
                break

        self._settle_period(period, theta, info)

    def _settle_period(self, period: int, theta: str, info: str) -> None:
        results = {}
        for s in self.mkt.seats:
            st = self.state[s]
            certs = st.holding.certs
            div = certs * self.mkt.dividend(s, theta)
            cash_after = st.holding.cash + div
            profit = cash_after - FIXED_COST
            st.total_profit += profit
            st.history.append({"period": period, "state": theta, "certs": certs,
                               "dividend": div, "profit": profit})
            results[s] = {"certs": certs, "type": self.mkt.seat_type[s], "dividend": div,
                          "cash_before_cost": cash_after, "profit": profit,
                          "cumulative": st.total_profit,
                          "insider": self.cards[s] is not None}
        self.stream.emit("period_end", {"period": period, "state": theta, "info": info,
                                        "results": results}, agent_visible=False)

        # The most important learning node in the design (§8): each agent sees the outcome
        # and writes ~100 words before the next period begins.
        self._period_end_reflections(period, theta, results)
        self.book.clear()

    def _period_end_reflections(self, period: int, theta: str, results: dict) -> None:
        targets = [s for s in self.mkt.seats if hasattr(self.agents[s], "reflect_system_text")]
        if not targets:
            return
        vlog = self._visible_log()

        def one(seat: str):
            agent = self.agents[seat]
            st = self.state[seat]
            r = results[seat]
            user = build_period_end_brief(
                market=self.mkt, seat=seat, period=period, state=theta, certs=r["certs"],
                cash=st.holding.cash, dividend_paid=r["dividend"], profit=r["profit"],
                market_log=vlog, names=self.names, rules=self.rules,
                **self._memory(seat))
            try:
                return seat, agent.reflect("period_end", agent.reflect_system_text, user)
            except Exception as e:  # noqa: BLE001
                return seat, {"text": "", "raw": {"error": str(e)}}

        workers = max(1, min(self.cfg.broadcast_workers, len(targets)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            out = list(pool.map(one, targets))

        for seat, res in out:
            self._account(res.get("raw"))
            text = (res.get("text") or "").strip()
            if res.get("raw", {}).get("usage"):
                self.stream.emit("model_turn", {"purpose": "period_end", **res["raw"]},
                                 seat=seat, agent_visible=False)
            if not text:
                # §8 calls this the session's main learning node; losing one silently is
                # the worst kind of failure here. On the probe run 6 of 12 came back empty
                # because reasoning consumed the whole token budget.
                self._violation(seat, "reflect", None, None, "empty_note",
                                {"kind": "period_end",
                                 "usage": (res.get("raw") or {}).get("usage")})
                continue
            self.state[seat].reflections.append({
                "kind": "period_end", "period": period, "round": 0, "at": None,
                "text": text})
            self.stream.emit("reflection", {"kind": "period_end", "text": text},
                             seat=seat, agent_visible=False)

    # ------------------------------------------------------------------ session

    def run_session(self, stop: "threading.Event | None" = None) -> dict:
        seq = self.cfg.sequence
        n = self.cfg.n_periods
        self.stream.session = self.session
        # A resumed session appends to the same log, which already holds its session_start.
        if self.completed_periods == 0:
            self.stream.emit("session_start", {
            "session": self.session, "seed": int(self.cfg.seed + self.session),
            # Which of the paper's five markets, so a log can be re-scored later without
            # anyone having to remember or guess. The metrics read it from here.
            "market": self.mkt.number,
            # The RE/PI predictions for every (info, state) this market can realize, and
            # the roster they are scored against. Written here so the viewer and any
            # downstream reader take them from the run rather than keeping their own copy
            # — the viewer's copy was market 3's, hard-coded, and would have been silently
            # wrong for every other market.
            "state_set": list(self.mkt.states),
            # Keyed by PERIOD, not by (info, state). Market 1's prediction depends on the
            # ten-draw sample that period actually got, so one cell per (info, state)
            # cannot hold it: `insider|Y` is RE 320 in period 5 and RE 262 in period 8,
            # and whichever was written last silently stood for both. The other four
            # markets have a lettered clue, so their (info, state) cells were adequate —
            # which is why this went unnoticed. `theory_by_state` is still written for
            # readers that predate this, and is correct for markets 2-5.
            "theory": {str(p): self._theory_of(p) for p in range(1, n + 1)},
            # Correct for markets 2-5, where a lettered clue makes (info, state) enough to
            # identify the prediction. NOT written for market 1: there it would hold the
            # state-contingent price (RE 350 in state Y) where the sample's posterior says
            # 320 or 262, and a reader picking it up would be silently wrong. A missing
            # key fails loudly; a wrong one does not.
            "theory_by_state": None if self.mkt.imperfect else {
                f"{i}|{st}": {**self.mkt.theory_at(i, st)[0],
                              "holder": self.mkt.theory_at(i, st)[1]}
                for i in ("none", "insider", "all") for st in self.mkt.states},
            "sequence_preset": seq.name, "sequence_note": seq.note,
            "states": list(seq.states[:n]), "info": list(seq.info[:n]),
            "config": json.loads(self.cfg.model_dump_json()),
            "seat_types": dict(self.mkt.seat_type), "insiders": list(self.mkt.insiders),
            # This session's seat -> name mapping. Agents only ever see the name; the
            # viewer and the metrics only ever see the seat.
                "seat_names": dict(self.names),
            }, agent_visible=False)

        t0 = time.monotonic()
        for period in range(self.completed_periods + 1, n + 1):
            self.run_period(period, seq.states[period - 1], seq.info[period - 1])
            self.completed_periods = period
            self.prior_elapsed_s += time.monotonic() - t0
            t0 = time.monotonic()
            if self.on_period_done:
                self.on_period_done(self)
            # Stop only on a period boundary, where the checkpoint just landed and the
            # dividends have been paid. Stopping mid-period would discard that period's
            # calls with nothing settled to show for them.
            if stop is not None and stop.is_set():
                return None

        totals = {s: {"francs": self.state[s].total_profit,
                      "usd": round(self.state[s].total_profit * self.mkt.franc_to_usd, 4),
                      "type": self.mkt.seat_type[s], "insider": s in self.mkt.insiders}
                  for s in self.mkt.seats}
        summary = {
            "session": self.session,
            "totals": totals,
            "calls": self.calls,
            "usage": self.usage.to_dict(),
            "cost_usd": round(self.usage.cost_usd(self.cfg.pricing), 4),
            "wall_clock_s": round(self.prior_elapsed_s, 1),
        }
        self.stream.emit("session_end", summary, agent_visible=False)
        return summary


def write_checkpoint(path: str, payload: dict) -> None:
    """Atomic checkpoint: write to a temp file then rename, so a crash mid-write cannot
    corrupt the previous checkpoint."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
