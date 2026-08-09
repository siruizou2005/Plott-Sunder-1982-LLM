"""The per-turn briefing (design doc §6 ①).

The engine PUSHES this; the agent never asks for anything. That is the main structural
difference from the GMS project's tool-loop agents, and it means the agent call can be
stateless — every scrap of memory an agent has is in this text.

Seven blocks, in the order the design doc gives them:
  identity · private information · standing quotes · binding constraints ·
  this year's public record · your recent notes · your record across years
"""

from __future__ import annotations

from ..config import Rules
from ..markets import FIXED_COST


Names = dict[str, str] | None


def _nm(names: Names, seat: str | None) -> str:
    """Seat -> the name agents use for it.

    S01..S12 must never reach a prompt: the numbering encodes structure no subject had —
    types run in blocks and the insiders are every first-and-second of four. Falling back
    to the raw seat keeps the pure render helpers usable in tests without a mapping.
    """
    if seat is None:
        return ""
    return (names or {}).get(seat, seat)


def _fmt_quote(q: dict | None, label: str, names: Names = None) -> str:
    if q is None:
        return f"  {label}: none"
    return f"  {label}: {q['price']} francs (announced by {_nm(names, q['seat'])})"


def render_book(book: dict, rules: Rules, names: Names = None) -> str:
    """Standing quotes, the spread, and the constraint a new quote must satisfy."""
    bid, ask = book.get("bid"), book.get("ask")
    lines = ["== STANDING QUOTES ==", _fmt_quote(bid, "Standing bid", names),
             _fmt_quote(ask, "Standing ask", names)]
    spread = book.get("spread")
    lines.append(f"  Spread: {spread}" if spread is not None
                 else "  Spread: not defined (one side is empty)")
    if rules.price_improvement:
        hints = []
        hints.append(f"a new bid must be strictly above {bid['price']}" if bid
                     else "the bid side is empty, so any bid price takes effect")
        hints.append(f"a new ask must be strictly below {ask['price']}" if ask
                     else "the ask side is empty, so any ask price takes effect")
        lines.append("  To take effect: " + "; ".join(hints) + ".")
    return "\n".join(lines)


def _outcome_text(e: dict, names: Names = None) -> str:
    """Spell out what happened, naming buyer and seller.

    The quote's side alone is ambiguous for an acceptance: whoever accepts a standing BID
    is the one selling. Stating both roles removes the trap.
    """
    outcome = e.get("outcome")
    if outcome == "posted":
        return "no one accepted; it is now the standing quote"
    if outcome == "superseded":
        return "replaced by a later quote on the same side"
    buyer, seller = e.get("buyer"), e.get("seller")
    who = (f"{_nm(names, seller)} sold to {_nm(names, buyer)}"
           if buyer and seller else "traded")
    if outcome == "crossed_auto":
        return f"crossed the standing quote; {who}"
    return who


def render_market_log(entries: list[dict], window: int = 0, names: Names = None) -> str:
    """This year's public record: every quote that took effect, and what became of it.

    A rejected quote never appears here — no one but its author learns of it (design doc
    §5.2). Acceptors who lost a random tie-break never appear either (§0.2).
    """
    if not entries:
        return "== THIS YEAR'S PUBLIC RECORD ==\n  Nothing has been announced yet this year."
    shown = entries[-window:] if window and window > 0 else entries
    head = "== THIS YEAR'S PUBLIC RECORD =="
    if len(shown) < len(entries):
        head += f"\n  (showing the most recent {len(shown)} of {len(entries)} entries)"
    rows = [head, "   #  investor   what they did          price  outcome"]
    for e in shown:
        verb = ("accepted the standing " + e["side"]) if e.get("action") == "accept_standing" \
            else f"announced a{'n' if e['side'] == 'ask' else ''} {e['side']}"
        rows.append(f"  {e['seq']:>2}  {_nm(names, e['seat']):<9}  {verb:<21}  "
                    f"{e['price']:>5}  {_outcome_text(e, names)}")
    return "\n".join(rows)


def render_history(history: list[dict]) -> str:
    """Your own results, year by year. Design doc §8: this is the cross-period learning
    channel — it corresponds to a subject copying profit onto the Profit Sheet."""
    if not history:
        return "== YOUR RECORD SO FAR ==\n  This is the first market year."
    rows = ["== YOUR RECORD SO FAR ==",
            "  year  dividend paid  certificates held at end  profit (francs)"]
    for h in history:
        rows.append(f"  {h['period']:>4}  {h['state']:^13}  {h['certs']:^24}"
                    f"  {h['profit']:>+15,}")
    total = sum(h["profit"] for h in history)
    rows.append(f"  Cumulative profit: {total:+,} francs")
    return "\n".join(rows)


def render_reflections(notes: list[dict]) -> str:
    """Your own past notes, split by kind and stamped with when you wrote them.

    Two things were wrong with pooling them into one undated list. The kinds compete for
    the same slots, so a busy year evicts the year-end reflection (design doc §8's main
    learning node) behind a handful of post-trade jottings. And rendered as bare bullets,
    an agent cannot tell a snap note written seconds after a trade from a considered
    year-end summary, nor which year either came from.
    """
    year_end = [n for n in notes if n.get("kind") == "period_end"]
    trades = [n for n in notes if n.get("kind") != "period_end"]
    blocks = []

    if year_end:
        rows = ["== YOUR NOTES FROM PAST YEAR-ENDS =="]
        for n in year_end:
            rows.append(f"  (year {n['period']}) {n['text'].strip()}")
        blocks.append("\n".join(rows))
    else:
        blocks.append("== YOUR NOTES FROM PAST YEAR-ENDS ==\n"
                      "  You have not finished a market year yet.")

    if trades:
        rows = ["== YOUR NOTES AFTER RECENT TRADES =="]
        for n in trades:
            where = f"year {n['period']}, round {n['round']}"
            if n.get("at"):
                where += f", {n['at']}"
            rows.append(f"  ({where}) {n['text'].strip()}")
        blocks.append("\n".join(rows))
    else:
        blocks.append("== YOUR NOTES AFTER RECENT TRADES ==\n"
                      "  You have not traded yet.")

    return "\n\n".join(blocks)


def render_not_selected(entries: list[dict], names: Names = None) -> str:
    """Acceptances you called out this year that did not go through.

    A subject who accepted a bid and then watched the experimenter point at someone else
    knows it happened. A stateless agent does not — it has no memory of having said yes.
    That gap was an artifact of the architecture, not a design choice: design doc §0.2
    erases the losing acceptors from the PUBLIC record, and says nothing about hiding the
    attempt from the agent who made it.

    What is deliberately withheld is the NUMBER of other acceptors. In a noisy oral
    auction nobody could count the raised hands, and that count is exactly the latent
    demand curve — the one measurement no human experiment can produce (§0.2, §11.3).
    Handing it to agents would let them read demand at a price straight off, contaminating
    the thing the design exists to collect.
    """
    if not entries:
        return ""
    rows = ["== YOUR ACCEPTANCES THIS YEAR THAT DID NOT GO THROUGH =="]
    for e in entries:
        # Accepting a bid means selling; accepting an ask means buying. Spell it out, or
        # the side reads backwards.
        would = "sold" if e["side"] == "bid" else "bought"
        rows.append(f"  Round {e['round']}, action #{e['seq']}: {_nm(names, e['quote_seat'])} "
                    f"announced a {e['side']} of {e['price']} francs and you accepted it, "
                    f"so you would have {would} one certificate.")
        if e.get("why"):
            # The agent's own words at the time. It cannot remember them otherwise: each
            # call is stateless, so without this the attempt has no trace it can reason from.
            rows.append(f"      Your reason at the time: \"{e['why'].strip()}\"")
        if e.get("reason") == "could_not_settle":
            rows.append("      By then you could no longer complete it, so you were not "
                        "included in the draw.")
        else:
            rows.append("      Another investor accepted it as well, and the random draw "
                        "chose them instead of you.")
    return "\n".join(rows)


def _clue_line(card: str | None, info: str, rules: Rules, market) -> str:
    lines = ["== YOUR CLUE CARD THIS YEAR =="]
    if card is None:
        lines.append("  Your clue card is BLANK. It tells you nothing about which dividend "
                     "will be paid.")
    elif market.imperfect:
        # Market 1's card is a row of marks, and it is NOT decisive. Telling an agent the
        # dividend "WILL" be paid would be false, and would hand it a certainty the whole
        # point of market 1 is that it does not have.
        lines.append(f"  Your clue card carries the marks {card}. It was drawn from the box "
                     f"matching this year's dividend, but either box can produce any row.")
    else:
        # Rules.clue_is_certain states no new fact: the instructions already say a card
        # carrying a letter is always correct. Config refuses the flag on market 1, and
        # the imperfect branch above is why it could not reach that market anyway.
        certain = (" A card that carries a letter is never wrong, so treat this as certain."
                   if rules.clue_is_certain else "")
        lines.append(f"  Your clue card carries the letter {card}. The {card}-dividend WILL "
                     f"be paid at the end of this year.{certain}")
    # Two treatments write here. §14.4's announce_no_info_period speaks only in the "none"
    # direction; the disclosure ladder's disclose_card_years speaks in both. They share the
    # "none" sentence and therefore share one branch, so no configuration can print it
    # twice — and Config refuses announce_no_info_period: false beside the ladder flag,
    # which is the only way the two could have disagreed.
    announce = (market.announce_no_info if rules.announce_no_info_period is None
                else rules.announce_no_info_period)
    if info == "none":
        if announce or rules.disclose_card_years:
            lines.append("  This year no investor has received a lettered clue card.")
    elif rules.disclose_card_years:
        # Deliberately silent on HOW MANY, which keeps the sentence true of an "all"
        # period as well as an "insider" one and keeps it identical for every seat: an
        # agent holding a letter learns nothing here that a blank-card holder does not.
        lines.append("  This year lettered clue cards have been handed out.")
    return "\n".join(lines)


def _constraints(seat: str, certs: int, cash: int, book: dict) -> str:
    """The binding constraints, spelled out. A human subject reads them off their own
    record sheet; an agent gets them stated so a rejected attempt is never a surprise."""
    bid, ask = book.get("bid"), book.get("ask")
    lines = ["== WHAT YOU CAN DO THIS TURN =="]

    if certs < 1:
        lines.append("  You hold no certificates: you cannot announce an ask, and you "
                     "cannot accept the standing bid.")
    if cash < 1:
        lines.append("  You have no francs on hand: you cannot buy.")

    if ask is not None:
        if ask["seat"] == seat:
            lines.append("  The standing ask is your own; you may not accept it.")
        elif cash < ask["price"]:
            lines.append(f"  The standing ask is {ask['price']} but you hold {cash:,} "
                         f"francs, so you cannot accept it.")
        else:
            lines.append(f"  You may accept the standing ask ({ask['price']}) to buy one "
                         f"certificate.")
    if bid is not None:
        if bid["seat"] == seat:
            lines.append("  The standing bid is your own; you may not accept it.")
        elif certs >= 1:
            lines.append(f"  You may accept the standing bid ({bid['price']}) to sell one "
                         f"certificate.")

    lines.append(f"  Any bid you announce must be at most your {cash:,} francs on hand.")
    return "\n".join(lines)


def _identity(seat: str, certs: int, cash: int, *, market, period: int,
              names: Names = None, round_no: int | None = None,
              turn_seq: int | None = None, with_cost: bool = True) -> str:
    # `market` is required, with no fallback to a module default on purpose: a default
    # would quietly print market 3's dividends to a market-1 agent, which is a wrong
    # experiment that still runs to completion.
    d = market.dividends[market.seat_type[seat]]
    where = f"This is market year {period}"
    if round_no is not None and turn_seq is not None:
        where += f", round {round_no}, turn {turn_seq}"
    lines = [
        "== YOUR POSITION ==",
        f"  You are investor {_nm(names, seat)}. {where}.",
        "  Your earnings per certificate: "
        + ", ".join(f"{d[s]} francs if the {s}-dividend is paid" for s in d) + ".",
        f"  You currently hold {certs} certificate(s) and {cash:,} francs.",
    ]
    if with_cost:
        lines.append(f"  At the end of this year a fixed cost of {FIXED_COST:,} francs is "
                     f"subtracted, and whatever remains is your profit.")
    return "\n".join(lines)


def _memory_blocks(*, reflections: list[dict], history: list[dict],
                   not_selected: list[dict], names: Names = None) -> list[str]:
    """The private memory an agent carries, identical in every kind of call.

    Every call gets the same memory because a human subject's memory does not depend on
    whose turn it is. Keeping this in one place is what stops the four call sites from
    drifting apart again.
    """
    return [b for b in (render_not_selected(not_selected, names),
                        render_reflections(reflections),
                        render_history(history)) if b]


def build_brief(*, market, seat: str, period: int, round_no: int, turn_seq: int, info: str,
                card: str | None, certs: int, cash: int, book: dict,
                market_log: list[dict], reflections: list[dict], history: list[dict],
                not_selected: list[dict], names: Names, rules: Rules) -> str:
    """Assemble the whole briefing. Returned verbatim into the ``brief`` event, so the log
    contains the exact bytes the model saw."""
    blocks = [
        _identity(seat, certs, cash, market=market, period=period, names=names, round_no=round_no, turn_seq=turn_seq),
        _clue_line(card, info, rules, market),
        render_book(book, rules, names),
        _constraints(seat, certs, cash, book),
        render_market_log(market_log, rules.market_log_window, names),
        *_memory_blocks(reflections=reflections, history=history,
                        not_selected=not_selected, names=names),
        "It is your turn. Choose your action and reply with the json object.",
    ]
    return "\n\n".join(blocks)


def build_broadcast_brief(*, market, seat: str, period: int, quote: dict, info: str,
                          card: str | None, certs: int, cash: int, book: dict,
                          market_log: list[dict], reflections: list[dict],
                          history: list[dict], not_selected: list[dict],
                          names: Names, rules: Rules) -> str:
    """The message sent to every feasible counterparty when a quote is announced
    (design doc §6 ⑤).

    Each recipient is asked PRIVATELY and in parallel: nobody learns who else was asked,
    who else accepted, or how many did. Only the outcome reaches the public record, which
    is what an oral auction's onlookers would observe anyway.
    """
    side = quote["side"]
    if side == "bid":
        headline = (f"Investor {_nm(names, quote['seat'])} has announced a BID: they will buy one "
                    f"certificate for {quote['price']} francs. Accepting means YOU SELL one "
                    f"certificate and receive {quote['price']} francs.")
    else:
        headline = (f"Investor {_nm(names, quote['seat'])} has announced an ASK: they will sell one "
                    f"certificate for {quote['price']} francs. Accepting means YOU BUY one "
                    f"certificate and pay {quote['price']} francs.")
    blocks = [
        "== A QUOTE HAS JUST BEEN ANNOUNCED ==\n  " + headline,
        _identity(seat, certs, cash, market=market, period=period, names=names, with_cost=False),
        _clue_line(card, info, rules, market),
        render_book(book, rules, names),
        render_market_log(market_log, rules.market_log_window, names),
        *_memory_blocks(reflections=reflections, history=history,
                        not_selected=not_selected, names=names),
        "Do you accept? Reply with the json object.",
    ]
    return "\n\n".join(blocks)


def build_trade_feedback_brief(*, market, seat: str, period: int, round_no: int, side: str,
                               price: int, counterparty: str, info: str, card: str | None,
                               certs: int, cash: int, book: dict, market_log: list[dict],
                               reflections: list[dict], history: list[dict],
                               not_selected: list[dict], names: Names, rules: Rules) -> str:
    """Write a note straight after a trade.

    Same information as a turn, deliberately NOT the same task: the turn brief's
    "what you can do this turn" block and its closing "it is your turn, choose your
    action" would be telling an agent to trade when it is being asked to reflect.
    """
    verb = "bought" if side == "buy" else "sold"
    blocks = [
        f"== YOU HAVE JUST TRADED ==\n"
        f"  You {verb} one certificate at {price} francs (counterparty: {_nm(names, counterparty)}) "
        f"in market year {period}, round {round_no}.",
        _identity(seat, certs, cash, market=market, period=period, names=names, with_cost=False),
        _clue_line(card, info, rules, market),
        render_book(book, rules, names),
        render_market_log(market_log, rules.market_log_window, names),
        *_memory_blocks(reflections=reflections, history=history,
                        not_selected=not_selected, names=names),
        "In one or two sentences, note why you made this trade and what you will watch "
        "for next.",
    ]
    return "\n\n".join(blocks)


def build_period_end_brief(*, market, seat: str, period: int, state: str, certs: int, cash: int,
                           dividend_paid: int, profit: int, reflections: list[dict],
                           history: list[dict], market_log: list[dict],
                           not_selected: list[dict], names: Names,
                           rules: Rules) -> str:
    blocks = [
        f"== MARKET YEAR {period} HAS ENDED ==\n"
        f"  The {state}-dividend was paid.\n"
        f"  You held {certs} certificate(s), so you collected {dividend_paid:,} francs in "
        f"certificate earnings.\n"
        f"  After the fixed cost of {FIXED_COST:,} francs, your profit for the year was "
        f"{profit:+,} francs.",
        _identity(seat, certs, cash, market=market, period=period, names=names, with_cost=False),
        render_market_log(market_log, rules.market_log_window, names),
        *_memory_blocks(reflections=reflections, history=history,
                        not_selected=not_selected, names=names),
        "Write a note to yourself of about 100 words. What did the prices this year tell "
        "you, or fail to tell you? What will you do differently next year?",
    ]
    return "\n\n".join(blocks)
