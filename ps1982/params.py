"""Market 3's parameters, as module-level names.

Every number originates in `markets.py` now: this module DERIVES market 3 from
`MARKETS[3]` rather than restating it. The two were byte-identical when markets.py was
written (tests/test_markets.py pins that), and deriving is what stops them drifting apart
the first time someone corrects one and forgets the other.

The module-level shape is kept because ~76 call sites in engine, prompts, metrics and cli
still import these names directly. Those move to taking a `Market` argument; until they
do, this is the bridge, and market 3 keeps behaving exactly as it did.

Everything here is therefore market 3 ONLY. Code that needs to work for markets 1, 2, 4
and 5 must take a Market — there is no module-level form of "the roster" once the roster
can be nine agents instead of twelve.

IMPORTANT: THEORY_* values are for post-hoc analysis and the visualiser ONLY. They must
never reach an agent prompt — the whole point of the experiment is whether agents find
the RE price on their own (design doc §2.4).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .markets import FIXED_COST, INITIAL_CASH, INITIAL_CERTS, MARKETS

_M3 = MARKETS[3]

# ---------------------------------------------------------------- dividends (Table 2)

DIVIDENDS: dict[str, dict[str, int]] = _M3.dividends
PRIOR: dict[str, float] = _M3.prior
PRIOR_EV: dict[str, float] = _M3.prior_ev

# The prior is described to subjects ONLY as a bingo cage of 40 balls, numbers 1-16 paying
# the X-dividend and 17-40 the Y-dividend; the word "probability" never appears in the
# subject instructions and must not appear in ours either. These two numbers are the
# mechanism, not a restatement of PRIOR — a different market needs a different mechanism.
BINGO_TOTAL = 40
BINGO_X_MAX = 16

# ---------------------------------------------------------------- endowments (Table 2)

FRANC_TO_USD = _M3.franc_to_usd
N_PERIODS = _M3.n_periods
MARKET_SUPPLY = _M3.market_supply

# ---------------------------------------------------------------- seats

SEATS: list[str] = _M3.seats
SEAT_TYPE: dict[str, str] = _M3.seat_type
INSIDERS: list[str] = _M3.insiders
TYPES: list[str] = _M3.types
STATES: list[str] = list(_M3.states)

# ---------------------------------------------------------------- display names
#
# Agents address each other by NAME; S01..S12 never appears in a prompt and stays a
# backend label for the log, the metrics and the viewer.
#
# The seat numbers carry structure an agent could read: types run in blocks (S01-S04 are
# all type I) and the insiders are S01, S02, S05, S06, S09, S10 — two out of every four,
# in order. Nothing in the paper gave subjects a comparably ordered handle on each other.
#
# The pool is SHUFFLED per session (Engine, from the seeded RNG) rather than mapped
# one-to-one. A fixed map would tie any name prior the model holds to the same seat — and
# therefore to the same type and insider status — in every repetition, so it would not
# average out across sessions. Shuffling makes it a nuisance factor instead of a
# confound. The realized mapping is recorded in `session_start`.
#
# Deliberately not in alphabetical order, which would reintroduce an ordering; all twelve
# initials differ, so no two are easy to confuse.
SEAT_NAMES: tuple[str, ...] = (
    "Nora", "Felix", "Priya", "Anton", "Wendell", "Chika",
    "Marcus", "Ines", "Teodor", "Bela", "Yusuf", "Delphine",
)
assert len(set(SEAT_NAMES)) >= len(SEATS), "at least one distinct name per seat"
assert len({n[0] for n in SEAT_NAMES}) == len(SEAT_NAMES), "distinct initials"

# ---------------------------------------------------------------- state / info sequences


@dataclass(frozen=True)
class Sequence:
    """Per-period realized state and information condition.

    info ∈ {"none", "insider", "all"}:
      none    — every agent receives a BLANK clue card (markets 3 and 4 distributed blank
                cards in no-information periods; markets 1, 2, 5 distributed none at all)
      insider — 6 agents (two of each type) receive a card bearing the state; the other 6
                receive blanks, which is what conceals the insiders' identity
      all     — every agent receives a card bearing the state (PI ≡ RE, no identification)
    """
    name: str
    states: tuple[str, ...]
    info: tuple[str, ...]
    note: str = ""

    def __post_init__(self) -> None:
        # Internal consistency only. This used to assert exactly 12 periods and exactly
        # the states {X, Y}, both of which are market 3's parameters rather than
        # properties of a sequence: markets 1 and 2 run 11 periods, market 4 runs 14,
        # and market 5 has a third state Z. The length and state-set checks now belong to
        # Market, which knows what they should be for the market at hand.
        assert len(self.states) == len(self.info), "one info condition per period"
        assert self.states, "a sequence must have at least one period"
        assert set(self.info) <= {"none", "insider", "all"}


def random_sequence(seed: int) -> Sequence:
    """A fresh draw from the bingo cage, keeping market 3's information design.

    Table 1's sequence is ONE realization of a 16-in-40 chance of X, not a property of the
    experiment. Running a second market on an independent draw is what separates "this is
    what markets do" from "this is what that particular twelve-year run did" — with five
    identifying periods per session, a single realization is thin evidence.

    The information design stays fixed at market 3's: two no-information years, eight
    insider years, two in which everyone is told. Only the realized states are redrawn.

    Deterministic in ``seed``, so the draw is reproducible and is recorded in
    ``session_start.states`` and in the run's meta.

    NOTE: this is market 3's redraw. `Market.redrawn()` generalises it to any market's own
    prior and period count, and is what markets 1, 2, 4 and 5 use.
    """
    rnd = random.Random(f"ps1982-sequence-{seed}")
    states = tuple("X" if rnd.randint(1, BINGO_TOTAL) <= BINGO_X_MAX else "Y"
                   for _ in range(N_PERIODS))
    return Sequence(
        name=f"random_prior_{seed}",
        states=states,
        info=("none", "none") + ("insider",) * 8 + ("all", "all"),
        note=(f"Fresh draw from the bingo cage (seed {seed}), market 3's information "
              f"design. Table 1's own sequence is one such draw."),
    )


SEQUENCES: dict[str, Sequence] = {
    # Two-period shakedown for a new vendor, not a replication: year 1 no information (X),
    # year 2 the separating cell (six insiders, Y — RE 175 vs PI 220). The least that shows
    # both "does it price the prior" and "does the price move once someone knows".
    # Periods 3-12 are filler and never run; scenarios cap this at two.
    "probe_none_then_insider": Sequence(
        name="probe_none_then_insider",
        states=("X", "Y") + tuple("YXYYXYXYYX"),
        info=("none", "insider") + ("insider",) * 8 + ("all", "all"),
        note="Shakedown: year 1 no information (X), year 2 six insiders (Y, separating).",
    ),
    # Table 1, market 3 — now taken from MARKETS[3] rather than retyped.
    "paper_exact": Sequence(
        name="paper_exact",
        states=_M3.sequence_states,
        info=_M3.sequence_info,
        note="Table 1, market 3, verbatim. Periods 11-12 are 'All' (everyone informed).",
    ),
}

# ---------------------------------------------------------------- theory (Table 3)
# NEVER put these in a prompt.
#
# Derived from MARKETS[3] rather than transcribed. The derivation reproduces the paper's
# Table 3 for markets 2, 3, 4 and 5 cell by cell (tests/test_markets.py), which is a
# stronger warrant than a transcription can have — and it is the only way to get market
# 1's predictions at all, since the paper omits them ("information given to insiders was
# probabilistic. Predictions are not given here in order to save space.").


def _theory() -> tuple[dict, dict]:
    price: dict[tuple[str, str], dict[str, int]] = {}
    holder: dict[tuple[str, str], dict[str, str]] = {}
    for p in range(1, _M3.n_periods + 1):
        key = (_M3.sequence_info[p - 1], _M3.sequence_states[p - 1])
        price[key] = _M3.theory_price(p)
        holder[key] = _M3.theory_holder(p)
    # Market 3's own sequence never realizes ("none", "X") or ("all", "Y") in a period we
    # score, but the viewer and the metrics index this table by (info, state) and would
    # KeyError on a redrawn sequence that does. Fill every combination.
    for info in ("none", "insider", "all"):
        for state in _M3.states:
            if (info, state) in price:
                continue
            probe = _probe_period(info, state)
            price[(info, state)] = probe[0]
            holder[(info, state)] = probe[1]
    return price, holder


def _probe_period(info: str, state: str) -> tuple[dict[str, int], dict[str, str]]:
    """Predictions for an (info, state) pair market 3's own sequence does not realize."""
    from dataclasses import replace
    n = _M3.n_periods
    probe = replace(_M3, sequence_info=(info,) * n, sequence_states=(state,) * n)
    return probe.theory_price(1), probe.theory_holder(1)


THEORY_PRICE, THEORY_HOLDER = _theory()


def holder_seats(spec: str) -> list[str]:
    """Expand a THEORY_HOLDER spec into the seats it names."""
    return _M3.holder_seats(spec)


def dividend(seat: str, state: str) -> int:
    return _M3.dividend(seat, state)


def is_insider_period(info: str) -> bool:
    return info == "insider"


def clue_cards(info: str, state: str) -> dict[str, str | None]:
    """Seat -> clue card content. ``None`` means a blank card.

    Market 3 distributed blank cards even in no-information periods, so every agent
    always receives a card; only its content varies.
    """
    if info == "none":
        return {s: None for s in SEATS}
    if info == "all":
        return {s: state for s in SEATS}
    return {s: (state if s in INSIDERS else None) for s in SEATS}


# ---------------------------------------------------------------- efficiency baselines


def allocation_value(holdings: dict[str, int], state: str) -> float:
    """Expected return of an allocation given the state actually realized."""
    return float(sum(n * dividend(seat, state) for seat, n in holdings.items()))


def allocation_value_prior(holdings: dict[str, int]) -> float:
    """Expected return of an allocation under the prior (used in no-information periods,
    where 'the information in the market' is just the prior)."""
    return float(sum(n * PRIOR_EV[SEAT_TYPE[seat]] for seat, n in holdings.items()))


def no_trade_holdings() -> dict[str, int]:
    return {s: INITIAL_CERTS for s in SEATS}


def re_holdings(info: str, state: str) -> dict[str, int]:
    """The RE-predicted allocation: all 24 units held by the predicted type, split evenly."""
    seats = holder_seats(THEORY_HOLDER[(info, state)]["RE"])
    per = MARKET_SUPPLY // len(seats)
    return {s: (per if s in seats else 0) for s in SEATS}


def benchmark_values(info: str, state: str) -> dict[str, float]:
    """Expected returns of the RE and no-trade allocations, used as the denominators of
    E and TE. In a no-information period we condition on the prior, otherwise on the
    realized state ('conditioned upon information in the market', paper §III).

    Sanity values for market 3:
      state X  -> RE 9600, no-trade 6600
      state Y  -> RE 4200, no-trade 3400
      none     -> RE 5280, no-trade 4680
    """
    if info == "none":
        return {"re": allocation_value_prior(re_holdings(info, state)),
                "no_trade": allocation_value_prior(no_trade_holdings())}
    return {"re": allocation_value(re_holdings(info, state), state),
            "no_trade": allocation_value(no_trade_holdings(), state)}


__all__ = [
    "DIVIDENDS", "PRIOR", "PRIOR_EV", "BINGO_TOTAL", "BINGO_X_MAX",
    "INITIAL_CERTS", "INITIAL_CASH", "FIXED_COST", "FRANC_TO_USD", "N_PERIODS",
    "MARKET_SUPPLY", "SEATS", "SEAT_TYPE", "INSIDERS", "TYPES", "STATES", "SEAT_NAMES",
    "Sequence", "SEQUENCES", "random_sequence", "THEORY_PRICE", "THEORY_HOLDER",
    "holder_seats", "dividend", "is_insider_period", "clue_cards",
    "allocation_value", "allocation_value_prior", "no_trade_holdings", "re_holdings",
    "benchmark_values",
]
