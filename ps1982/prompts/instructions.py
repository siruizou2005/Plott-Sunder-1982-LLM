"""The per-seat system prompt: an adaptation of Instruction Set 2 (paper Appendix).

Three hard constraints, all taken from the paper or the design doc:

1. The word "probability" NEVER appears. The paper is explicit that subjects were trained
   on the bingo cage as a mechanism and that probability language was kept out of the
   instructions; we keep it out of ours. This is what forces every market's prior to be
   expressible as whole balls in a cage, and market 1's imperfect clue to be described as
   two boxes of chips rather than as a likelihood.
2. Nothing is said about how many investor types exist, what anyone else's dividends are,
   whether the informed agents stay the same across periods, or how likely either state
   is (design doc §3.3). This describes the BASELINE: `Rules.disclose_structure` is the
   one deliberate, flag-gated treatment exception, and it discloses the type structure
   and the per-type informed count — never identities, never the schedule of card years,
   and never whether the card holders stay the same across years.
3. The common-knowledge facts of design doc §3.2 ARE stated explicitly, because subjects
   could deduce them from the physical setup and our agents cannot. Which facts qualify
   is per-market: market 1's subjects could NOT deduce that dividends stay constant
   ("agents could deduce in all but market 1 that the dividend values for every agent
   remained constant from period to period"), so market 1 does not get that sentence.

Everything that varies between the paper's five markets — roster size, period count, the
state set, the prior's cage, whether the clue is a letter or a ten-draw sample — is taken
from the Market rather than hard-coded, because all five differ in at least one of them.

The text below is byte-stable for a given seat across an entire session, which is exactly
what DeepSeek's automatic prefix caching rewards.
"""

from __future__ import annotations

from ..config import Rules
from ..markets import CLUE_DRAWS, FIXED_COST, INITIAL_CASH, INITIAL_CERTS, URN, Market

_NUMBER_WORD = {2: "two", 3: "three", 4: "four", 6: "six", 9: "nine",
                12: "twelve", 15: "fifteen"}
_ROMAN = ("i", "ii", "iii", "iv", "v")

_GENERAL = """\
This is an experiment in the economics of market decision making. The instructions are
simple, and if you follow them carefully and make good decisions, you might earn a
considerable amount of money.

You are one of {n_word} investors in a market where certificates are bought and sold over
a sequence of {n_periods} market years. You are investor {seat}.

The currency of this market is francs. All trading and earnings are in francs. Each franc
is worth ${franc_to_usd} to you. Do not reveal this number to anyone.\
"""

# Rules.objective_profit_max. Its own block of the SHARED preamble, so it reaches the
# turn, broadcast and reflection prompts alike — the baseline states its purpose only in
# _TURN_TASK, which is the paper's own wording and therefore never reaches a broadcast
# reply or a year-end note. Placed after _GENERAL and before _EARNINGS: it must not sit
# between the earnings block and the mechanism, because _EARNINGS_DISCLOSED ("further
# down") and _FACT_HOW_MANY_DISCLOSED ("the section above") both encode that ordering.
_OBJECTIVE = """\
== YOUR OBJECTIVE ==

Your objective is to earn as many francs as you can, over the whole experiment rather
than in any single year. Judge every decision — what to quote, what to accept, and what
to let pass — by what it does to your own francs, and take the one that leaves you with
the most.\
"""

_EARNINGS = """\
== YOUR PRIVATE INFORMATION AND RECORD ==

Your profits come from two sources: from collecting certificate earnings on the
certificates you hold at the end of the year, and from buying and selling certificates.

For each certificate you hold at the end of a year, you receive ONE of the {n_word}
amounts below. Which one is paid is determined by the mechanism described further down.

{dividend_lines}

{privacy}

At the start of every year you are given an initial holding of {certs} certificates and
{cash:,} francs on hand. You may sell your certificates or hold them; you may keep your
francs or use them to buy certificates.

At the end of each year:
  - every certificate you still hold pays you its earnings per certificate;
  - all your remaining holdings are then automatically sold to the experimenter at a
    price of 0, so a certificate is worth nothing to you after the year ends;
  - a fixed cost of {fixed_cost:,} francs is subtracted from your francs on hand.
Whatever remains is your profit for that year, and it is yours to keep. Your profits
accumulate across years.\
"""

# The two fillings of _EARNINGS's {privacy} slot. _EARNINGS_PRIVATE is the baseline and
# must stay byte-identical to the pre-slot wording — the completed runs were prompted
# with exactly these sentences, and prefix caching keys on the bytes.
_EARNINGS_PRIVATE = """\
These numbers are YOUR earnings per certificate. They are your own private information;
do not reveal them to anyone. Earnings may be different for different investors."""

_EARNINGS_DISCLOSED = """\
These numbers are YOUR earnings per certificate. Every investor knows the {n_types} sets
of amounts that exist in this market — they are listed further down — but which set is
YOURS is your own private information; do not reveal it to anyone."""

_MECHANISM_HEAD = """\
== HOW THE DIVIDEND IS DETERMINED ==

At the beginning of each year, before trading starts, the experimenter rotates a bingo
cage containing {total} balls numbered 1 through {total}, and draws one ball.

{cage_lines}

The draw is made once per year and its outcome is fixed for the whole year.\
"""

# Perfect information: the card names the state outright. "letter" is accurate for two
# states and for three.
_CLUE_PERFECT = """\
Also at the beginning of each year, before trading starts, every investor receives a clue
card. A clue card carries one of {n_options} things:
{card_lines}

{certainty}\
"""

# The two fillings of _CLUE_PERFECT's {certainty} slot. _CERTAINTY_PLAIN must stay
# byte-identical to the pre-slot sentence. _CERTAINTY_EMPHATIC (Rules.clue_is_certain)
# states no new fact — the card already was always correct — it removes the room an agent
# has to hedge on it. It CONTAINS the plain sentence verbatim, so every guard written
# against the baseline wording still passes under the flag.
_CERTAINTY_PLAIN = "A clue card that carries a letter is always correct."
_CERTAINTY_EMPHATIC = """\
A clue card that carries a letter is always correct. This has no exceptions and no
qualifications: if your card carries a letter, the dividend that letter names is the one
that WILL be paid at the end of this year. You may treat it as settled.\
"""

# Market 1's imperfect clue (footnote 5). Described as a physical sampling device, because
# the instructions may not say "probability" and an agent given only "the clue is noisy"
# could not compute anything. The chip counts ARE the urn compositions: box X is 4 zeros
# and 1 one (pr(0|X) = 4/5), box Y is 3 zeros and 2 ones (pr(0|Y) = 3/5).
_CLUE_IMPERFECT = """\
Also at the beginning of each year, after the ball is drawn, some investors receive a clue
card. A clue card carries one of two things:
  (i)  a row of {draws} marks, each mark either 0 or 1;
  (ii) a blank — this tells you nothing about which dividend will be paid.

A clue card of marks is made as follows. There are two boxes of chips:

    Box X holds {x_total} chips: {x_zero} marked 0 and {x_one} marked 1.
    Box Y holds {y_total} chips: {y_zero} marked 0 and {y_one} marked 1.

If the X-dividend is the one that will be paid this year, the experimenter draws from box
X; if the Y-dividend is the one that will be paid, from box Y. One chip is drawn, its mark
is written down, and the chip is PUT BACK in the box. This is done {draws} times, and the
{draws} marks in the order drawn are the clue card.

The card does not tell you which dividend will be paid. Either box can produce any row of
marks. What differs is how often: 1s come out of box Y more often than out of box X, so a
row with many 1s is more in keeping with box Y and a row with few 1s with box X.\
"""

# The structural-disclosure treatment (Rules.disclose_structure). What goes in: the full
# per-type dividend table, the agent's own type, and the two-per-type card allocation.
# What stays out: identities, whether the card holders are the same investors across
# years, and which years are card years — the closing sentence keeps a blank card
# ambiguous between "I am one of the uninformed" and "no one holds a letter this year".
# Wording stays inside the instruction vocabulary: no probability language, the prior
# never as a number, "clue card that is not blank" rather than any theory term, and the
# only digits are the dividend values themselves.
_DISCLOSURE = """\
== THE {n_types_upper} TYPES OF INVESTORS ==

The facts in this section are known to all {n_word} investors in this market.

There are {n_types} types of investors, with {per_type} investors of each type. Investors
of the same type have the same earnings per certificate; investors of different types
have different earnings. The {n_types} types earn:

{type_lines}

You are a Type {own} investor. No one is told which type any OTHER investor is.

In a year in which clue cards that are not blank are handed out, exactly {informed} of
the {per_type} investors of each type receive such a card; the other {uninformed} receive
blanks. {tail}\
"""

# The tail of the disclosure section's last paragraph: one literal per (fixedness, card
# years) combination, i.e. per rung of the ladder. Four hand-wrapped literals rather than
# three composable sentences, for the same reason _EARNINGS_PRIVATE/_EARNINGS_DISCLOSED
# and _IMPROVEMENT_ON/_OFF are literals — the paragraph is hard-wrapped and its first line
# CONTINUES "blanks. ", so a sentence swapped into the middle has to be re-wrapped anyway.
#
# (False, False) is byte-identical to the pre-slot paragraph. The baseline and the three
# completed tier-1 sessions were prompted with exactly these bytes, and the digests at the
# top of tests/test_prompts.py are what holds them there.
#
# Every sentence is checked against the engine rather than asserted. Fixedness:
# Market.insiders is the first `insiders_per_type` seats of each type block, and neither
# the period nor `redrawn` moves it — test_fixedness_disclosure_matches_the_engine pins
# the wording to the dealing. Card years: `_clue_line` reports the condition in both
# directions, every year, in the same words for every seat, under disclose_card_years.
#
# What no rung states: WHICH investors hold the cards. The first clause of every tail
# below says so, and there is no flag that removes it.
_TAIL_HIDDEN_HIDDEN = """\
No one is told which investors they are, or whether they are the same investors
from year to year. There may also be years in which every investor's card is blank, and
no one is told which years are which: a blank card looks the same to its holder either
way.\
"""

_TAIL_HIDDEN_YEARS = """\
No one is told which investors they are, or whether they are the same investors
from year to year. There may also be years in which every investor's card is blank. Each
year, along with your own card, you are told whether clue cards that are not blank were
handed out that year.\
"""

_TAIL_FIXED_HIDDEN = """\
No one is told which investors they are, but they are the same investors in
every year in which such cards are handed out. There may also be years in which every
investor's card is blank, and no one is told which years are which: a blank card looks
the same to its holder either way.\
"""

_TAIL_FIXED_YEARS = """\
No one is told which investors they are, but they are the same investors in
every year in which such cards are handed out. There may also be years in which every
investor's card is blank. Each year, along with your own card, you are told whether clue
cards that are not blank were handed out that year.\
"""

# (disclose_insiders_fixed, disclose_card_years) -> tail.
_DISCLOSURE_TAILS = {
    (False, False): _TAIL_HIDDEN_HIDDEN,
    (False, True): _TAIL_HIDDEN_YEARS,
    (True, False): _TAIL_FIXED_HIDDEN,
    (True, True): _TAIL_FIXED_YEARS,
}

_COMMON_KNOWLEDGE = """\
== WHAT EVERY INVESTOR KNOWS ==

The following {n_facts} things are known to all {n_word} investors:
{fact_lines}\
"""

_FACT_HOW_MANY = """\
  1. No one is told how many investors receive a clue card that is not blank, or which
     investors they are."""
# The disclosed variant of fact 1. The baseline sentence would contradict the disclosure
# section outright, so under the treatment the fact points at the section instead — and
# restates the one thing that is still never revealed.
_FACT_HOW_MANY_DISCLOSED = """\
  1. How many investors receive a clue card that is not blank, in a year when such cards
     are handed out, is stated in the section above. WHICH investors they are is never
     revealed to anyone."""
_FACT_SAME_CARD = """\
  2. Every clue card that is not blank, handed out in a given year, carries the SAME
     content."""
_FACT_CONSTANT = """\
  3. Each investor's earnings-per-certificate amounts stay the same in every year of the
     experiment. Yours will not change."""

_TRADING = """\
== TRADING RULES ==

 1. All transactions are for one certificate at a time.
 2. Anyone wishing to buy may announce a BID: an offer to buy one certificate at a stated
    price. Anyone wishing to sell may announce an ASK: an offer to sell one certificate at
    a stated price. All bids and asks are announced publicly and recorded.
 3. At most ONE bid and ONE ask stand in the market at any moment. A standing bid or ask
    leaves the market when it is accepted, when it is replaced by a new quote on the same
    side, or when the year ends.
 4. Any investor holding a certificate may accept the standing bid; any investor with
    enough francs may accept the standing ask. You may not accept your own quote.
 5. {improvement_rule}
 6. If a new bid is at or above the standing ask (or a new ask is at or below the standing
    bid), the trade happens immediately at the price of the quote that was already
    standing.
 7. Your certificate holdings may never go below zero — you cannot sell a certificate you
    do not hold. Your francs on hand may never go below zero.
 8. If several investors accept the same quote, one of them is chosen at random and the
    others are not told that anyone else tried.
 9. Except for making quotes and accepting them, you are not to communicate with any other
    investor in any way.\
"""

_IMPROVEMENT_ON = """\
A new bid takes effect only if its price is STRICTLY HIGHER than the standing bid;
    a new ask takes effect only if its price is STRICTLY LOWER than the standing ask. When
    the corresponding side is empty, any price takes effect. You may replace your own
    standing quote with a better one. A quote that does not improve on the standing quote
    is rejected by the market and no one else learns that you attempted it.\
"""

_IMPROVEMENT_OFF = """\
A new bid replaces the standing bid whatever its price, and a new ask replaces the
    standing ask whatever its price. Only the most recent quote on each side stands.\
"""

_TURN_TASK = """\
== WHAT YOU DO ON YOUR TURN ==

The market gives each investor turns in a rotating order. On your turn you are shown your
own position, your clue card, the current standing quotes, and the public record of every
quote and trade so far this year. You then choose exactly one of:

  - post a quote (a bid or an ask at a price you name),
  - accept a standing quote,
  - or do nothing this turn.

You are free to make as much profit as you can. There are likely to be many quotes that
are not accepted, but you are free to keep trying.\
"""

_OUTPUT_FULL = """\
== YOUR REPLY ==

Reply with a single json object and nothing else — no prose, no code fences.

{{
  "posterior": {{{posterior_schema}}},
  "reservation_buy": <integer francs: the most you would pay for one certificate now>,
  "reservation_sell": <integer francs: the least you would accept for one certificate now>,
  "basis": "<one of: prior | clue | price | others_behavior | spread>",
  "action": <one of the three action objects below>
}}

"posterior" is how strongly you currently lean toward each dividend being the one that
will be paid this year; the {n_states} numbers must sum to 1.
"basis" is the single thing that most drove this turn's judgement:
  prior            — only the bingo cage mechanism
  clue             — your own clue card
  price            — the prices at which certificates have actually traded
  others_behavior  — who has been quoting or accepting, and how
  spread           — the gap between the standing bid and the standing ask

The three action objects:
  {{"type": "no_quote"}}
  {{"type": "quote", "side": "bid" | "ask", "price": <integer francs>}}
  {{"type": "accept_standing", "side": "bid" | "ask"}}

For "accept_standing", "side" names the quote you are accepting: "ask" means you buy at
the standing ask, "bid" means you sell at the standing bid.\
"""

_OUTPUT_NO_BELIEFS = """\
== YOUR REPLY ==

Reply with a single json object and nothing else — no prose, no code fences.

{{
  "action": <one of the three action objects below>
}}

The three action objects:
  {{"type": "no_quote"}}
  {{"type": "quote", "side": "bid" | "ask", "price": <integer francs>}}
  {{"type": "accept_standing", "side": "bid" | "ask"}}

For "accept_standing", "side" names the quote you are accepting: "ask" means you buy at
the standing ask, "bid" means you sell at the standing bid.\
"""


def _word(n: int) -> str:
    return _NUMBER_WORD.get(n, str(n))


def _mechanism(market: Market, certain: bool = False) -> str:
    """The bingo cage, then the clue card — the only two devices an agent may reason from."""
    cage = []
    for state, lo, hi in market.cage_ranges:
        span = (f"is numbered {lo}" if lo == hi
                else f"is numbered {lo} through {hi}")
        cage.append(f"  If the drawn ball {span}, the {state}-dividend is paid at the end "
                    f"of that year.")
    head = _MECHANISM_HEAD.format(total=market.bingo_total, cage_lines="\n".join(cage))

    if market.imperfect:
        zx, ox = URN["X"]
        zy, oy = URN["Y"]
        clue = _CLUE_IMPERFECT.format(
            draws=CLUE_DRAWS,
            x_total=zx.denominator, x_zero=zx.numerator, x_one=ox.numerator,
            y_total=zy.denominator, y_zero=zy.numerator, y_one=oy.numerator)
    else:
        lines = []
        for i, s in enumerate(market.states):
            lines.append(f"  ({_ROMAN[i]:<4s}) the letter {s}  — the {s}-dividend WILL "
                         f"be paid at the end of this year;")
        lines.append(f"  ({_ROMAN[len(market.states)]:<4s}) a blank       — this tells you "
                     f"nothing about which dividend will be paid.")
        # The imperfect branch above never reaches this, so market 1 cannot be told its
        # sample is certain even if a Rules is built by hand: Config refuses the flag
        # there, and the code path could not honour it anyway.
        clue = _CLUE_PERFECT.format(n_options=_word(len(market.states) + 1),
                                    card_lines="\n".join(lines),
                                    certainty=(_CERTAINTY_EMPHATIC if certain
                                               else _CERTAINTY_PLAIN))
    return f"{head}\n\n{clue}"


def _disclosure(market: Market, seat: str, rules: Rules) -> str:
    """The structural-disclosure section. Every number is derived from the Market —
    type count, per-type roster, informed count, the dividend table — so the section is
    correct for any market Config._check lets it run on.

    The closing paragraph's tail is the ladder: which of the two facts the higher rungs
    disclose are stated here, and which stay withheld."""
    width = max(len(s) for s in market.states)
    blocks = []
    for t, d in market.dividends.items():
        rows = "\n".join(
            f"        If the {s:<{width}s}-dividend is paid:  {d[s]} francs per certificate"
            for s in market.states)
        blocks.append(f"    Type {t}:\n{rows}")
    n_types = _word(len(market.dividends))
    return _DISCLOSURE.format(
        n_types_upper=n_types.upper(),
        n_types=n_types,
        n_word=_word(market.n_agents),
        per_type=_word(market.n_per_type),
        informed=_word(market.insiders_per_type),
        uninformed=_word(market.n_per_type - market.insiders_per_type),
        own=market.seat_type[seat],
        type_lines="\n".join(blocks),
        tail=_DISCLOSURE_TAILS[(rules.disclose_insiders_fixed, rules.disclose_card_years)])


def _common_knowledge(market: Market, disclose: bool) -> str:
    facts = [_FACT_HOW_MANY_DISCLOSED if disclose else _FACT_HOW_MANY, _FACT_SAME_CARD]
    # "agents could deduce in ALL BUT MARKET 1 that the dividend values for every agent
    # remained constant from period to period" — so market 1 must not be told.
    if market.dividends_constant_is_common_knowledge:
        facts.append(_FACT_CONSTANT)
    return _COMMON_KNOWLEDGE.format(n_facts=_word(len(facts)),
                                    n_word=_word(market.n_agents),
                                    fact_lines="\n".join(facts))


def _preamble(market: Market, seat: str, name: str | None, rules: Rules) -> list[str]:
    """The market knowledge every prompt shares: who you are, what you earn, how it is
    decided, and what everyone knows. Identical across turn, broadcast and reflection —
    a reflection that lacked the mechanism block once left 50/50 as the only inference
    available, and that wrong belief then became durable memory.

    Every treatment that varies the market knowledge belongs here rather than in one of
    the three task blocks, for that same reason: a fact stated only on a turn is a fact
    the agent does not have when it answers a broadcast or writes a note."""
    disclose = rules.disclose_structure
    d = market.dividends[market.seat_type[seat]]
    width = max(len(s) for s in market.states)
    lines = "\n".join(f"    If the {s:<{width}s}-dividend is paid:  {d[s]} francs per certificate"
                      for s in market.states)
    privacy = (_EARNINGS_DISCLOSED.format(n_types=_word(len(market.dividends)))
               if disclose else _EARNINGS_PRIVATE)
    parts = [
        _GENERAL.format(n_word=_word(market.n_agents), n_periods=market.n_periods,
                        seat=name or seat, franc_to_usd=market.franc_to_usd),
    ]
    if rules.objective_profit_max:
        parts.append(_OBJECTIVE)
    parts += [
        _EARNINGS.format(n_word=_word(len(market.states)), dividend_lines=lines,
                         privacy=privacy,
                         certs=INITIAL_CERTS, cash=INITIAL_CASH, fixed_cost=FIXED_COST),
        _mechanism(market, rules.clue_is_certain),
    ]
    # After the mechanism: the section leans on the clue-card vocabulary defined there,
    # and both _EARNINGS_DISCLOSED ("further down") and _FACT_HOW_MANY_DISCLOSED ("the
    # section above") encode this ordering.
    if disclose:
        parts.append(_disclosure(market, seat, rules))
    parts.append(_common_knowledge(market, disclose))
    return parts


def system_prompt(seat: str, rules: Rules, market: Market, name: str | None = None) -> str:
    # `name` is what the agent is called in every prompt; `seat` only selects the
    # dividend row. S01..S12 must not reach the model — the numbering encodes the type
    # blocks and the insider positions.
    schema = ", ".join(f'"{s}": <number between 0 and 1>' for s in market.states)
    parts = _preamble(market, seat, name, rules) + [
        _TRADING.format(improvement_rule=(_IMPROVEMENT_ON if rules.price_improvement
                                          else _IMPROVEMENT_OFF)),
        _TURN_TASK,
        (_OUTPUT_FULL.format(posterior_schema=schema, n_states=_word(len(market.states)))
         if rules.elicit_beliefs else _OUTPUT_NO_BELIEFS),
    ]
    return "\n\n".join(parts)


# --------------------------------------------------------------- broadcast + reflection

_BROADCAST_TASK_REASON = """\
== YOUR REPLY ==

Reply with a single json object and nothing else:

{"response": "accept" | "decline", "why": "<at most 15 words>"}\
"""

_BROADCAST_TASK_PLAIN = """\
== YOUR REPLY ==

Reply with a single json object and nothing else:

{"response": "accept" | "decline"}\
"""


def broadcast_system_prompt(seat: str, rules: Rules, market: Market,
                            name: str | None = None) -> str:
    """Same market knowledge, different task: answer one quote, right now."""
    parts = _preamble(market, seat, name, rules) + [
        _TRADING.format(improvement_rule=(_IMPROVEMENT_ON if rules.price_improvement
                                          else _IMPROVEMENT_OFF)),
        "== WHAT YOU DO NOW ==\n\n"
        "Another investor has just announced a quote. You are one of the investors who "
        "could take the other side of it. Decide whether to accept it. If more than one "
        "investor accepts, one of you is chosen at random and the others are not told "
        "that anyone else accepted.",
        _BROADCAST_TASK_REASON if rules.broadcast_reason else _BROADCAST_TASK_PLAIN,
    ]
    return "\n\n".join(parts)


_REFLECT_TASK = """\
== WHAT YOU DO NOW ==

You are writing a private note to yourself. No one else will ever read it. It is carried
forward to your future turns, so write down what will actually help you earn more francs:
what you inferred, what you got wrong, and what you will do differently.

Reply with the note text only — no json, no headings, no preamble.\
"""


def reflect_system_prompt(seat: str, rules: Rules, market: Market,
                          name: str | None = None) -> str:
    """The same market knowledge as a turn, with the task swapped for note-writing.

    This prompt used to state only the dividend amounts. It never described the bingo
    cage, so an agent writing a note had no mechanism to reason from and 50/50 was the only
    inference available to it — which is precisely what the notes said, and what then
    became durable memory. Turning reasoning on did not help and could not have: measured
    on the probe run, reflections still put type II at 225 and type III at 150 while
    spending 171 reasoning tokens doing it. The missing block was the cause, not the
    missing reasoning.
    """
    return "\n\n".join(_preamble(market, seat, name, rules)
                       + [_REFLECT_TASK])
