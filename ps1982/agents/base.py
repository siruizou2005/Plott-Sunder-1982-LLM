"""Agent protocol.

Three things an agent does, all pushed by the engine — an agent never queries the market:

  decide_turn      once per turn         -> TurnDecision
  respond_broadcast when someone quotes  -> "accept" | "decline"
  reflect          after a trade / at period end -> a short note

``TurnContext`` and ``BroadcastContext`` carry everything a decision may legally use. A
scripted agent reads the fields; an LLM agent renders them into a briefing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

NO_QUOTE = "no_quote"
QUOTE = "quote"
ACCEPT_STANDING = "accept_standing"


@dataclass
class TurnContext:
    seat: str
    period: int
    round_no: int
    turn_seq: int
    info: str                       # none | insider | all
    card: str | None                # the clue card: "X", "Y" or None for a blank
    certs: int
    cash: int
    book: dict                      # Book.snapshot()
    market_log: list[dict]          # agent-visible entries for this period
    reflections: list[dict]         # {kind, period, round, at, text}
    history: list[dict]
    not_selected: list[dict]        # this period's acceptances that did not go through
    names: dict[str, str]           # seat -> the name agents call it by


@dataclass
class BroadcastContext:
    """What a feasible counterparty gets when someone announces a quote.

    Carries the same private memory as a turn. The asymmetry it used to have — no notes,
    no year-by-year record — had no counterpart in the paper: a subject hearing a bid is
    sitting at the table with their own record sheet in front of them. It was an artifact
    of the stateless design, and it fell on the channel that settles most trades (8 of 11
    in the smoke run).
    """
    seat: str
    period: int
    quote: dict                     # {"seat","side","price"}
    info: str
    card: str | None
    certs: int
    cash: int
    book: dict
    market_log: list[dict]
    reflections: list[dict]
    history: list[dict]
    not_selected: list[dict]
    names: dict[str, str]


@dataclass
class TurnDecision:
    """What the agent chose, plus the elicited beliefs (design doc §6 ②③, merged into a
    single model call). ``raw`` carries the full model exchange for the log."""

    action: str = NO_QUOTE
    side: str | None = None
    price: int | None = None
    posterior: dict | None = None
    reservation_buy: int | None = None
    reservation_sell: int | None = None
    basis: str | None = None
    malformed: bool = False
    raw: dict = field(default_factory=dict)

    def view(self) -> dict:
        return {"posterior": self.posterior, "reservation_buy": self.reservation_buy,
                "reservation_sell": self.reservation_sell, "basis": self.basis}


@dataclass
class BroadcastDecision:
    response: str = "decline"
    why: str | None = None
    malformed: bool = False
    raw: dict = field(default_factory=dict)


class Agent:
    kind = "base"

    def __init__(self, seat: str) -> None:
        self.seat = seat

    def decide_turn(self, ctx: TurnContext) -> TurnDecision:  # pragma: no cover - interface
        raise NotImplementedError

    def respond_broadcast(self, ctx: BroadcastContext) -> BroadcastDecision:  # pragma: no cover
        raise NotImplementedError

    def reflect(self, kind: str, system: str, user: str) -> dict:
        """Return {"text": str, "raw": dict}. Scripted agents return an empty note."""
        return {"text": "", "raw": {}}
