# Markets 1–5 — parameters read off the paper

`docs/paper-verification.md` covers market 3 only. This file covers the other four, read
the same way: the tables are landscape page images, so `pdftotext` returns noise for them
and they were rendered at 400 dpi, rotated −90° and read visually. Table 1 = PDF pp. 7–8,
Table 2 = p. 10. The body text (pp. 4–9) does have a clean text layer and is quoted where
it settles something the table leaves ambiguous.

**Implemented.** `ps1982/markets.py` is this specification as code and
`tests/test_markets.py` checks it back against the paper — Table 1's spans and period
counts, Table 2's expected dividends recomputed from each prior, all seven of market 1's
posteriors, and Table 3 cell by cell. A `Market` flows through config, engine, prompts,
agents, metrics and the viewer; nothing reads a market parameter from a module constant
any more.

---

## Table 2 — dividend parameters, all five markets

Every market: 2 certificates and 10,000 francs of working capital per investor, 10,000
francs fixed cost. All expected dividends below were recomputed from the stated prior and
matched the paper's own column to the digit.

| Market | N per type | $/franc | Prior | I | II | III |
|---:|---:|---:|---|---|---|---|
| 1 | **3** (9 investors) | .002 | X = **1/3** | 150 / 350 → 283.3 | 250 / 300 → 283.3 | 300 / 100 → 166.7 |
| 2 | 4 (12) | .002 | X = **1/3** | 100 / 350 → 266.7 | 200 / 300 → 266.7 | 240 / 175 → 196.6 |
| 3 | 4 (12) | .003 | X = .4 | 400 / 100 → 220 | 300 / 150 → 210 | 125 / 175 → 155 |
| 4 | 4 (12) | .003 | X = .4 | 375 / 100 → 210 | 275 / 150 → 200 | 100 / 175 → 145 |
| 5 | 4 (12) | .003 | **X .35 · Y .25 · Z .4** | 120 / 170 / **320** → 212.5 | 155 / 245 / **135** → 169.5 | 180 / 100 / **160** → 152 |

**Market 5 has three states.** Dividends are listed X / Y / Z.

---

## Table 1 — information design and realized states

`none` = no investor informed · `insider` = six, two of each type (market 1: **three**, one
of each type) · `all` = every investor gets a card.

| Market | Periods | States | Information |
|---:|---:|---|---|
| 1 | 11 | `Y Y X Y` `Y X Y Y` `Y X Y` | 1–4 none · 5–8 insider (**imperfect**) · 9–11 all |
| 2 | 11 | `X X Y Y` `Y Y` `X Y X Y Y` | 1–4 none · 5–6 all · 7–11 insider |
| 3 | 12 | `Y Y` `Y X Y Y X Y X Y` `Y X` | 1–2 none · 3–10 insider · 11–12 all |
| 4 | 14 | `X Y Y X` `Y X Y Y X Y X Y X` `Y` | 1–4 none · 5–13 insider · **14 none** |
| 5 | 13 | `Z X Z` `X X Y Z Z Y Y X Y Z` | 1–3 none · 4–13 insider |

Market 4 is the one with a no-information period at the END as well as the start — the body
text is explicit: *"the first four in 1, the first four in 2, the first two in 3, **the first
four and the last in 4**, and the first three in 5"*.

### Two cells where the table and the body text disagree

* **Market 2, period 4.** The table's card column reads `Y` with posterior 0, but the row is
  labelled `None` informed and the body text counts market 2's *first four* periods as
  no-information. Taking the body text as authoritative: period 4 is a no-information
  period, `No card`, posterior 1/3. The table cell is treated as a typesetting slip.
* **Market 4, period 14.** The posterior column reads `.04` where a no-information period
  under a .4 prior must be `.4`. Read as `.4`.

Both are recorded rather than silently resolved, because a reader who checks the table will
see something different from what the code does.

---

## Market 1's imperfect information — footnote 5, verbatim

> In market 1 only one out of three investors of each type was an insider, and the
> information received by insiders was less than certain. The "clue" given to the insiders
> was a sample of 10 draws with replacement. The sample was taken from urn X containing
> balls marked "0" and "1" [pr(0|X) = 4/5, pr(1|X) = 1/5] if the state randomly chosen was X
> and the sample was drawn from urn Y [pr(0|Y) = 3/5, pr(1|Y) = 2/5] if the randomly chosen
> state was Y.

So a market-1 clue card is a ten-character string of `0`/`1`, not a letter, and the insider's
correct posterior is Bayesian rather than 0 or 1:

    P(X | s) ∝ P(X) · (4/5)^(#0) · (1/5)^(#1)
    P(Y | s) ∝ P(Y) · (3/5)^(#0) · (2/5)^(#1)          with P(X) = 1/3

**Verified against the paper's own posterior column**, which is what makes this usable
rather than a guess:

| Period | Card | #1s | Recomputed P(X) | Paper |
|---:|---|---:|---:|---:|
| 5 | `0100101010` | 4 | 0.1493 | .15 |
| 6 | `0000000011` | 2 | 0.5554 | .555 |
| 7 | `0100110100` | 4 | 0.1493 | .15 |
| 8 | `0000010000` | 1 | 0.7702 | .77 |
| 9 | `1110000011` | 5 | 0.0616 | .062 |
| 10 | `1010000011` | 4 | 0.1493 | .15 |
| 11 | `1111111001` | 8 | 0.0033 | .003 |

The cards in the table are the realized samples the three insiders actually got, and all
three insiders got the **same** card ("the clues of all insiders were identical").

---

## Common knowledge, per market

The `announce_no_info_period` flag is currently global and defaults to False, which is right
for market 3. It is **per-market**:

> The exceptions are periods 1 through 4 of market 1, 1 through 4 of market 2, 1 through 3
> of market 5, in all of which the fact that no one had any information was announced, and
> also in period 11 of market 1 in which the clue was publicly announced.

* markets **1, 2, 5** — no-information periods **were** announced
* markets **3, 4** — were **not** (Table 1's "How Many: No")
* market 1 period 11 — the clue itself was public
* *"agents could deduce in all but market 1 that the dividend values for every agent
  remained constant from period to period"* — market 1 lacks even that common-knowledge fact

---

## What it cost to implement

Each of these is load-bearing; none is a configuration change.

1. **Three states (market 5).** `posterior` schema, clue cards, the bingo-cage wording, the
   theory tables, the efficiency benchmarks and every metric keyed on X/Y.
2. **Variable roster (market 1 has 9).** `SEATS`, `SEAT_TYPE` and `INSIDERS` are module-level
   constants shaped 4/4/4 with six fixed insiders.
3. **Imperfect information (market 1).** Clue cards become ten-character samples; the correct
   posterior is Bayesian, so "the insider knows the state" stops being true anywhere it is
   currently assumed.
4. **Variable period count.** `N_PERIODS = 12` is a constant and `Sequence.__post_init__`
   asserts exactly twelve.
5. **Per-market priors** — 1/3, .4, and a three-way split. The prompt describes the prior
   only as a bingo cage of 40 balls with 1–16 paying X; 1/3 needs a different mechanism
   description that still never says "probability".
6. **Per-market common knowledge** — announcement of no-information periods, and market 1's
   missing "dividends are constant" fact.


---

## What the implementation added to this specification

**Table 3 (p. 674), read after this document was first written.** It gives RE/PI prices
and predicted holders for markets 2, 3, 4 and 5 and states that market 1's are omitted
("information given to insiders was probabilistic. Predictions are not given here in order
to save space"). `markets.py` DERIVES all five from the dividends and the prior rather
than transcribing them, and the derivation reproduces every cell the paper prints. Market
1's predictions are therefore ours, and warranted by agreement everywhere a check exists.

**Allocation separates where price does not.** Table 3 daggers market 2's state-Y cell for
its holder while both models name the same price 350: RE has all four type-I agents
holding, PI only the two type-I insiders. Scoring "separating" on price alone discards
those periods.

| market | price-separating | allocation-separating |
|---:|---:|---:|
| 1 | 4 | 4 |
| 2 | **2** | **5** |
| 3 | 5 | 8 |
| 4 | 5 | 9 |
| 5 | **3** | **10** |
| total | **19** | **36** |

Nearly half the identifying power of the five markets is in allocation, not price, and
market 5 has more than three times as much of it as its price-separating count suggests.

**Bingo cages for markets 1, 2 and 5 are OURS.** The paper prints Instruction Set 2 for
market 3 (40 balls, 1-16 pay X) and does not give the others' devices. The prior may not
reach an agent as a figure, so each market needs a cage that expresses it in whole balls:
30 balls for the 1/3 markets (1-10 / 11-30) and 20 for market 5 (1-7 / 8-12 / 13-20).
`Market.bingo_total` records them as data so the paper's own device stays distinguishable
from ours.

**Market 1's clue is described as two boxes of chips.** Box X holds 4 chips marked 0 and 1
marked 1; box Y holds 3 and 2; one chip is drawn, recorded and put back, ten times. That
is footnote 5's urn model stated mechanically, which is the only way to give an agent
something to reason from without using the word this experiment forbids.

**A known limitation.** The scripted `re` baseline cannot read market 1's ten-mark card —
it tests `card in states`, which a sample never satisfies, so it falls back to price
inference. The LLM agents are unaffected (the mechanism is in their prompt), but the RE
bot is not a valid reference for market 1.
