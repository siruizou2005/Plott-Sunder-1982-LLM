"""The five Plott & Sunder (1982) markets as data, plus our equidistant control.

`params.py` holds market 3 as module-level constants — one roster, two states, twelve
periods, one prior. The other four markets each break at least one of those assumptions
(see docs/markets-1-to-5.md), so they cannot be expressed as a config override; the
parameters have to become a value that code takes as an argument.

`MARKETS[6]` is NOT one of the paper's. It is the control design of Table 7 in the
companion paper, whose two informed-trade directions sit the same distance from the
uninformed level — impossible anywhere in the published family, which needs p > 1/2.
`PAPER_MARKETS` is what separates the two provenances, and every guard that asserts a
fact about Plott & Sunder iterates that rather than `MARKETS`. See
docs/market-6-control.md.

This module is that value. It deliberately does NOT rewire anything yet: `params.py` is
untouched and MARKETS[3] is asserted to reproduce it exactly (tests/test_markets.py), so
the data is proven right before ~200 call sites start depending on it.

Every number was read off the paper — Table 1 (pp. 7-8), Table 2 (p. 10) and footnote 5 —
and re-derived here where the paper prints a derived value, so a transcription slip shows
up as a failing test rather than as a quietly wrong experiment.

THEORY_* predictions are DERIVED from the parameters rather than transcribed, because a
derivation can be checked against Table 3 while a transcription can only be trusted. They
are for analysis and the viewer ONLY and must never reach an agent prompt.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from fractions import Fraction

# ---------------------------------------------------------------- the clue model
#
# Market 1 alone gave insiders IMPERFECT information (footnote 5): instead of a letter,
# a sample of 10 draws with replacement from an urn whose composition depends on the
# realized state. Every other market's card is the state itself.
#
#     urn X: pr(0) = 4/5, pr(1) = 1/5
#     urn Y: pr(0) = 3/5, pr(1) = 2/5
#
# so a sample s with k ones and 10-k zeros yields
#
#     P(X | s) ∝ P(X) · (4/5)^(10-k) · (1/5)^k
#     P(Y | s) ∝ P(Y) · (3/5)^(10-k) · (2/5)^k
#
# Verified against all seven posteriors the paper prints for market 1 (see the test).
URN = {"X": (Fraction(4, 5), Fraction(1, 5)),
       "Y": (Fraction(3, 5), Fraction(2, 5))}
CLUE_DRAWS = 10


def sample_posterior(sample: str, prior: dict[str, float]) -> dict[str, float]:
    """Posterior over states given a market-1 clue sample of '0'/'1' characters."""
    ones = sample.count("1")
    zeros = len(sample) - ones
    w = {s: Fraction(str(prior[s])) * URN[s][0] ** zeros * URN[s][1] ** ones
         for s in URN}
    tot = sum(w.values())
    return {s: float(v / tot) for s, v in w.items()}


def draw_sample(state: str, rnd: random.Random) -> str:
    """A fresh 10-draw sample from the urn matching `state`.

    Needed whenever market 1's states are redrawn: a clue is drawn CONDITIONAL on the
    realized state, so a redrawn state with the paper's original card would be a sample
    from the wrong urn — an incoherent world, not a new draw of the same one.
    """
    p1 = float(URN[state][1])
    return "".join("1" if rnd.random() < p1 else "0" for _ in range(CLUE_DRAWS))


# ---------------------------------------------------------------- the market


@dataclass(frozen=True)
class Market:
    """One of the paper's five markets, complete enough to run and to score."""

    number: int
    n_per_type: int                          # 3 in market 1, 4 elsewhere
    insiders_per_type: int                   # 1 in market 1, 2 elsewhere
    states: tuple[str, ...]                  # ("X","Y") or ("X","Y","Z") in market 5
    prior: dict[str, float]
    dividends: dict[str, dict[str, int]]     # type -> state -> francs
    franc_to_usd: float
    sequence_states: tuple[str, ...]         # Table 1's realized state per period
    sequence_info: tuple[str, ...]           # "none" | "insider" | "all" per period
    # Balls in the bingo cage the prior is DESCRIBED to subjects with. The instructions
    # never say "probability" — the prior exists for the agent only as this device — so a
    # market's prior needs a cage whose ranges express it exactly in whole balls.
    #   market 3: 40 is the paper's own (Instruction Set 2: balls 1-16 pay X).
    #   market 4: same prior, so the same cage.
    #   markets 1, 2 (1/3) and 5 (.35/.25/.40): the paper does not print their cages, so
    #   30 and 20 are OURS — the smallest round totals that divide exactly. Marked here
    #   rather than derived so that "the paper said this" stays distinguishable from
    #   "we chose this".
    bingo_total: int = 40
    imperfect: bool = False                  # market 1's 10-draw samples
    announce_no_info: bool = False           # markets 1, 2, 5 told subjects
    dividends_constant_is_common_knowledge: bool = True   # false in market 1 only
    paper_clue_cards: dict[int, str] = field(default_factory=dict)  # market 1, periods->sample
    public_clue_periods: tuple[int, ...] = ()             # market 1 period 11
    note: str = ""

    # -------------------------------------------------------------- derived roster

    @property
    def types(self) -> list[str]:
        return ["I", "II", "III"]

    @property
    def n_agents(self) -> int:
        return 3 * self.n_per_type

    @property
    def n_periods(self) -> int:
        return len(self.sequence_states)

    @property
    def seats(self) -> list[str]:
        return [f"S{i:02d}" for i in range(1, self.n_agents + 1)]

    @property
    def seat_type(self) -> dict[str, str]:
        """Types run in contiguous blocks, as in market 3's current SEAT_TYPE."""
        out = {}
        for i, s in enumerate(self.seats):
            out[s] = self.types[i // self.n_per_type]
        return out

    @property
    def insiders(self) -> list[str]:
        """The first `insiders_per_type` seats of each type, fixed for the session.

        Fixed insiders are the paper's design ("the insiders are the same agents
        throughout"), and subjects were not told this.
        """
        out = []
        for t in self.types:
            block = [s for s in self.seats if self.seat_type[s] == t]
            out.extend(block[: self.insiders_per_type])
        return out

    @property
    def market_supply(self) -> int:
        return self.n_agents * INITIAL_CERTS

    @property
    def prior_ev(self) -> dict[str, float]:
        """Expected dividend per type under the prior — Table 2's rightmost column."""
        return {t: sum(self.prior[s] * d[s] for s in self.states)
                for t, d in self.dividends.items()}

    def dividend(self, seat: str, state: str) -> int:
        return self.dividends[self.seat_type[seat]][state]

    @property
    def cage_ranges(self) -> list[tuple[str, int, int]]:
        """[(state, first ball, last ball)] partitioning the cage in the states' order.

        Raises rather than rounding: a cage that cannot express the prior in whole balls
        would misstate the prior to every agent for the whole session, and silently.
        """
        out, lo = [], 1
        for s in self.states:
            n = self.prior[s] * self.bingo_total
            if abs(n - round(n)) > 1e-9:
                raise ValueError(f"market {self.number}: prior {self.prior[s]} for {s} is "
                                 f"not a whole number of balls out of {self.bingo_total}")
            out.append((s, lo, lo + round(n) - 1))
            lo += round(n)
        assert lo - 1 == self.bingo_total, f"market {self.number}: cage does not add up"
        return out

    # -------------------------------------------------------------- clue cards

    def clue_cards(self, info: str, state: str, period: int | None = None,
                   rnd: random.Random | None = None) -> dict[str, str | None]:
        """Seat -> card content. ``None`` is a blank card.

        Takes the information condition and the state EXPLICITLY rather than reading them
        off `sequence_*`, because the engine's `run_period(period, theta, info)` is
        parameterised by them: tests and the scripted-agent runs drive (state, info)
        combinations the market's own sequence never realizes, and silently substituting
        the sequence's values would hand out blank cards in a period the caller declared
        to be an insider period. `cards_for_period` is the convenience that does read the
        sequence.

        Markets 3 and 4 handed out blank cards in no-information periods; 1, 2 and 5
        handed out none at all and announced the fact. Either way the agent learns
        nothing, and `announce_no_info` is what carries the difference into the prompt.
        """
        if info == "none":
            return {s: None for s in self.seats}
        card = self.card_for(period, state, rnd)
        if info == "all":
            return {s: card for s in self.seats}
        return {s: (card if s in self.insiders else None) for s in self.seats}

    def cards_for_period(self, period: int, rnd: random.Random | None = None
                         ) -> dict[str, str | None]:
        """`clue_cards` for the state and condition this market's sequence actually has."""
        return self.clue_cards(self.sequence_info[period - 1],
                               self.sequence_states[period - 1], period, rnd)

    def card_for(self, period: int | None, state: str,
                 rnd: random.Random | None = None) -> str:
        """What a lettered card carries: the state, or market 1's 10-draw sample.

        "The clues of all insiders were identical" — one card per period, not one per
        insider.
        """
        if not self.imperfect:
            return state
        card = self.paper_clue_cards.get(period)
        if card is not None and state == self.sequence_states[period - 1]:
            return card              # Table 1's own realized sample, states unchanged
        if rnd is None:
            raise ValueError(f"market {self.number} period {period}: states were redrawn, "
                             f"so the clue must be redrawn too — pass an RNG")
        return draw_sample(state, rnd)

    def posterior_from_card(self, card: str | None) -> dict[str, float]:
        """What a correctly-reasoning agent believes after seeing `card`."""
        if card is None:
            return dict(self.prior)
        if self.imperfect:
            return sample_posterior(card, self.prior)
        return {s: (1.0 if s == card else 0.0) for s in self.states}

    # -------------------------------------------------------------- theory (vs Table 3)

    def theory_price(self, period: int, card: str | None = None) -> dict[str, int]:
        """RE and PI price predictions for a period.

        RE  — the market aggregates the information that is IN it, so every agent ends up
              conditioning on the clue, and the units go to whoever values them most
              under it.
        PI  — no aggregation: each agent values a certificate at its own expected
              dividend given its OWN information, and the price is the highest such
              valuation (the marginal buyer among 24 units and 2 units of endowment
              each is still within the top type's block).
        The two coincide except where insiders are a minority AND the clue is one the
        uninformed would misprice — market 3's famous separating cell.

        **RE conditions on the clue, not on the state.** For markets 2-5 that is the same
        thing: the clue is a letter, so its posterior is degenerate on the realized state
        and this reduces to `max(dividends[t][state])`, which is what those markets used
        before and what Table 3 prints. Market 1's clue is a ten-draw sample, and there
        the difference is the whole point — a market cannot reveal more than it knows, and
        what its insiders know is a sample, not the state. Computing market 1's RE from the
        state instead put it at 350 (state Y) where the sample's posterior says 320, and
        inverted the SIGN of the prediction in the separating periods: the true RE lies
        BELOW the uninformed 283.3 when the sample is bad news, not above it. That made
        four of market 1's periods look separating where the paper counts two, taking its
        footnote-6 total from 17 to 19. See test_separating_periods_match_footnote_6.
        """
        info = self.sequence_info[period - 1]
        state = self.sequence_states[period - 1]

        if info == "none":
            # nobody knows anything; both models are the prior
            return {"RE": round(max(self.prior_ev.values())),
                    "PI": round(max(self.prior_ev.values()))}

        post = self.posterior_from_card(card if card is not None
                                        else self.card_for(period, state))
        informed = max(sum(post[s] * self.dividends[t][s] for s in self.states)
                       for t in self.types)
        re_price = informed
        if info == "all":
            pi_price = informed          # everyone holds the clue, so PI collapses onto RE
        else:
            pi_price = max(informed, max(self.prior_ev.values()))
        return {"RE": round(re_price), "PI": round(pi_price)}

    def _argmax_types(self, value: dict[str, float]) -> str:
        """The type(s) with the highest value, joined with '+' when they tie.

        Ties are real, not a corner case: market 2 gives types I and II an identical
        prior expected value of 266.67, and Table 3 records its holder as "I and II
        uninformed". Picking one arbitrarily with max() would score half those agents as
        holding against prediction when they are exactly on it.
        """
        best = max(value.values())
        return "+".join(t for t in self.types if abs(value[t] - best) < 1e-9)

    def theory_holder(self, period: int, card: str | None = None) -> dict[str, str]:
        """Which group the units should end up with, under each model."""
        info = self.sequence_info[period - 1]
        state = self.sequence_states[period - 1]
        if info == "none":
            best = self._argmax_types(self.prior_ev)
            return {"RE": best, "PI": best}
        # Conditions on the clue, not the state — see theory_price. Degenerate for a
        # lettered clue, so markets 2-5 keep scoring against `dividends[t][state]`.
        post = self.posterior_from_card(card if card is not None
                                        else self.card_for(period, state))
        ev_informed = {t: sum(post[s] * self.dividends[t][s] for s in self.states)
                       for t in self.types}
        re_best = self._argmax_types(ev_informed)
        if info == "all":
            return {"RE": re_best, "PI": re_best}
        if max(ev_informed.values()) >= max(self.prior_ev.values()):
            pi = f"{self._argmax_types(ev_informed)}_insider"
        else:
            pi = f"{self._argmax_types(self.prior_ev)}_uninformed"
        return {"RE": re_best, "PI": pi}

    def theory_at(self, info: str, state: str, period: int | None = None,
                  card: str | None = None) -> tuple[dict[str, int], dict[str, str]]:
        """(price, holder) predictions for an (info, state) pair, period optional.

        The metrics index periods by (info, state) rather than by number, and a redrawn
        sequence can realize combinations this market's own Table 1 row never did. When a
        period IS given it is used, which matters only for market 1: its prediction depends
        on the actual clue sample drawn, not just on the state.

        Which is why `card` exists. Matching on (info, state, period) is NOT enough to
        identify market 1's sample: a redrawn run can land on the paper's state for a
        period and still have drawn a different ten-mark sample, and then the paper's card
        gets used and the period is scored against the wrong theory — measured on
        m1_random_0, where periods 5, 6 and 8 all took the wrong RE and two of the three
        flipped the separating flag. Callers that have the realized card (the log records
        it) must pass it; deriving it from the period number is a fallback for callers that
        do not, such as the fixed benchmark table.
        """
        if period is not None and 1 <= period <= self.n_periods \
                and self.sequence_info[period - 1] == info \
                and self.sequence_states[period - 1] == state:
            return self.theory_price(period, card), self.theory_holder(period, card)
        from dataclasses import replace
        n = max(self.n_periods, 1)
        probe = replace(self, sequence_info=(info,) * n, sequence_states=(state,) * n,
                        paper_clue_cards={})
        if probe.imperfect:
            # Prefer the realized sample; fall back to the paper's card for this period if
            # there is one, else the prior — and say so rather than inventing a draw.
            clue = card if card is not None else self.paper_clue_cards.get(period or -1)
            probe = replace(probe, paper_clue_cards={1: clue} if clue else {},
                            imperfect=bool(clue))
            if clue:
                return probe.theory_price(1, clue), probe.theory_holder(1, clue)
        return probe.theory_price(1), probe.theory_holder(1)

    def holder_seats(self, spec: str) -> list[str]:
        """Expand a theory_holder spec ('III', 'I_insider', 'I+II_uninformed') to seats."""
        which = "all"
        for suffix in ("_insider", "_uninformed"):
            if spec.endswith(suffix):
                spec, which = spec[: -len(suffix)], suffix[1:]
                break
        wanted = set(spec.split("+"))
        out = []
        for s in self.seats:
            if self.seat_type[s] not in wanted:
                continue
            if which == "insider" and s not in self.insiders:
                continue
            if which == "uninformed" and s in self.insiders:
                continue
            out.append(s)
        return out

    # -------------------------------------------------------------- redraw

    def redrawn(self, seed: int) -> "Market":
        """The same market with each period's state redrawn from its OWN prior.

        The information design is held fixed — which periods have no one, six insiders
        or everyone informed is the treatment, and redrawing it would change the
        experiment rather than resample it. Only the realized states move, which is what
        Table 1's row is: one realization, not a property.

        Market 1's clue samples are redrawn as a consequence, not as a separate choice:
        a sample is drawn from the urn matching the realized state, so keeping the paper's
        card against a redrawn state would describe a world that cannot occur.
        """
        rnd = random.Random(f"ps1982-m{self.number}-seq-{seed}")
        pool = list(self.states)
        weights = [self.prior[s] for s in pool]
        states = tuple(rnd.choices(pool, weights=weights, k=self.n_periods))
        cards: dict[int, str] = {}
        if self.imperfect:
            crnd = random.Random(f"ps1982-m{self.number}-clue-{seed}")
            for p, st in enumerate(states, start=1):
                if self.sequence_info[p - 1] != "none":
                    cards[p] = draw_sample(st, crnd)
        return Market(**{**self.__dict__, "sequence_states": states,
                         "paper_clue_cards": cards,
                         "note": f"states redrawn from the prior (seed {seed}); "
                                 f"information design unchanged"})


# ---------------------------------------------------------------- shared endowments
# Identical in all five markets (Table 2 notes).

INITIAL_CERTS = 2
INITIAL_CASH = 10_000
FIXED_COST = 10_000


def _info(n_periods: int, spans: list[tuple[int, int, str]]) -> tuple[str, ...]:
    """Expand [(first, last, condition), ...] into a per-period tuple, 1-indexed."""
    out = ["none"] * n_periods
    for lo, hi, cond in spans:
        for p in range(lo, hi + 1):
            out[p - 1] = cond
    return tuple(out)


# ---------------------------------------------------------------- the five markets

MARKETS: dict[int, Market] = {
    1: Market(
        number=1,
        n_per_type=3,                       # 9 investors, not 12
        insiders_per_type=1,                # "only one out of three ... was an insider"
        states=("X", "Y"),
        prior={"X": 1 / 3, "Y": 2 / 3},
        dividends={"I": {"X": 150, "Y": 350},
                   "II": {"X": 250, "Y": 300},
                   "III": {"X": 300, "Y": 100}},
        franc_to_usd=0.002,
        bingo_total=30,          # ours: 1/3 needs a cage divisible by 3
        sequence_states=tuple("YYXYYXYYYXY"),
        sequence_info=_info(11, [(5, 8, "insider"), (9, 11, "all")]),
        imperfect=True,
        announce_no_info=True,
        dividends_constant_is_common_knowledge=False,
        paper_clue_cards={5: "0100101010", 6: "0000000011", 7: "0100110100",
                          8: "0000010000", 9: "1110000011", 10: "1010000011",
                          11: "1111111001"},
        public_clue_periods=(11,),
        note="Imperfect information: a 10-draw sample, not a letter. Nine investors.",
    ),
    2: Market(
        number=2,
        n_per_type=4,
        insiders_per_type=2,
        states=("X", "Y"),
        prior={"X": 1 / 3, "Y": 2 / 3},
        dividends={"I": {"X": 100, "Y": 350},
                   "II": {"X": 200, "Y": 300},
                   "III": {"X": 240, "Y": 175}},
        franc_to_usd=0.002,
        bingo_total=30,          # ours: same 1/3 prior as market 1
        sequence_states=tuple("XXYYYYXYXYY"),
        sequence_info=_info(11, [(5, 6, "all"), (7, 11, "insider")]),
        announce_no_info=True,
        note="Everyone informed BEFORE the insider periods, the reverse of market 3. "
             "Table 1 prints a 'Y' card for period 4, but the body text counts the "
             "first four periods as no-information; the text is taken as authoritative.",
    ),
    3: Market(
        number=3,
        n_per_type=4,
        insiders_per_type=2,
        states=("X", "Y"),
        prior={"X": 0.4, "Y": 0.6},
        dividends={"I": {"X": 400, "Y": 100},
                   "II": {"X": 300, "Y": 150},
                   "III": {"X": 125, "Y": 175}},
        franc_to_usd=0.003,
        sequence_states=tuple("YYYXYYXYXYYX"),
        sequence_info=_info(12, [(3, 10, "insider"), (11, 12, "all")]),
        note="The market already implemented in params.py.",
    ),
    4: Market(
        number=4,
        n_per_type=4,
        insiders_per_type=2,
        states=("X", "Y"),
        prior={"X": 0.4, "Y": 0.6},
        dividends={"I": {"X": 375, "Y": 100},
                   "II": {"X": 275, "Y": 150},
                   "III": {"X": 100, "Y": 175}},
        franc_to_usd=0.003,
        sequence_states=tuple("XYYXYXYYXYXYXY"),
        sequence_info=_info(14, [(5, 13, "insider")]),
        note="The only market with a no-information period at the END as well as the "
             "start (period 14). Table 1 prints its posterior as '.04'; under a .4 prior "
             "a no-information period must be .4, and it is read that way.",
    ),
    5: Market(
        number=5,
        n_per_type=4,
        insiders_per_type=2,
        states=("X", "Y", "Z"),
        prior={"X": 0.35, "Y": 0.25, "Z": 0.40},
        dividends={"I": {"X": 120, "Y": 170, "Z": 320},
                   "II": {"X": 155, "Y": 245, "Z": 135},
                   "III": {"X": 180, "Y": 100, "Z": 160}},
        franc_to_usd=0.003,
        bingo_total=20,          # ours: .35/.25/.40 -> 7/5/8 balls
        sequence_states=tuple("ZXZXXYZZYYXYZ"),
        sequence_info=_info(13, [(4, 13, "insider")]),
        announce_no_info=True,
        note="Three states. Every X/Y assumption elsewhere in the codebase breaks here.",
    ),
    # ------------------------------------------------------------ not the paper's
    6: Market(
        number=6,
        # Everything structural is market 3's, unchanged: twelve investors, four per type,
        # two insiders per type, twelve periods, blank cards rather than an announcement,
        # and dividends-are-constant as common knowledge. Table 7 changes the dividends,
        # the prior and nothing else, and this follows it — the fewer things that differ
        # from the market the control is read against, the less the comparison has to
        # carry. The one free parameter Table 7 does not state is franc_to_usd, taken
        # from market 3 for the same reason.
        n_per_type=4,
        insiders_per_type=2,
        states=("X", "Y"),
        prior={"X": 0.6, "Y": 0.4},
        dividends={"I": {"X": 300, "Y": 100},
                   "II": {"X": 230, "Y": 130},
                   "III": {"X": 225, "Y": 140}},
        franc_to_usd=0.003,          # ours: market 3's, Table 7 does not state one
        bingo_total=40,              # Table 7's own: "24 of 40 balls paying X"
        # OURS, not a realized sequence from any paper — there is no Table 1 row for a
        # market that was never run. Balanced on purpose: the eight insider periods split
        # 4 X / 4 Y, and each side's mean ordinal position among them is 6.5, so neither
        # side is systematically early or late in a session. The runs reported use
        # `random_prior` instead (independent draws from the .6 prior); this sequence is
        # what `paper_exact` yields for market 6 and what `validate` displays, and the
        # preset's NAME is a misnomer here. Overall 7 X / 5 Y, against the 7.2 the prior
        # would give in expectation.
        sequence_states=tuple("XXXYYXYXXYXY"),
        sequence_info=_info(12, [(3, 10, "insider"), (11, 12, "all")]),
        announce_no_info=False,
        note="NOT a Plott & Sunder market. The equidistant control of Table 7: prior "
             "24/40 on X, so the informed-buy target (re 300) and the informed-sell "
             "target (re 140) are both 80 francs from the uninformed level of 220. "
             "Structure otherwise identical to market 3. The buy side is still "
             "non-separating — equation (1) is independent of the parameters — so "
             "equidistance removes the distance confound and not the blind spot.",
    ),
}

# The markets that are Plott & Sunder's. Market 6 is ours, and a guard that asserts
# something the PAPER says — which markets announced a no-information period, which one
# ends uninformed, how many insiders each has — must iterate this and not `MARKETS`,
# or a control design starts having to satisfy claims about an experiment it is not in.
PAPER_MARKETS: tuple[int, ...] = (1, 2, 3, 4, 5)
