# Markets 92–95 — the information-stops variants

**None of these is a Plott & Sunder market, and none of them is a design.** Each runs its
base market — 2, 3, 4 or 5 — unchanged through a stated period and then transmits nothing
for the rest of the session. They exist to measure one nuisance parameter: where price
rests against v̄ when nothing is known, at the period indices the base market's insider
periods occupy.

`STOPPED_MARKETS = (92, 93, 94, 95)` in `ps1982/markets.py`. The units digit names the
base, as it does nowhere else in the family: 93 is market 3's.

| | base | periods | schedule | measured tail | insider indices in the base |
|---|---|---|---|---|---|
| **92** | 2 | 11 | none 1–4 · all 5–6 · insider 7–8 · **none 9–11** | 9–11 (3) | 7–11, median 9 |
| **93** | 3 | 12 | none 1–2 · insider 3–5 · **none 6–12** | 6–12 (7) | 3–10, median 6.5 |
| **94** | 4 | 14 | none 1–4 · insider 5–7 · **none 8–14** | 8–14 (7) | 5–13, median 9 |
| **95** | 5 | 13 | none 1–3 · insider 4–6 · **none 7–13** | 7–13 (7) | 4–13, median 8.5 |

Roster, prior, dividends, period count, realized states, bingo cage, and every rule are
the base market's. `tests/test_markets.py::test_stopped_variants_change_only_the_information_schedule`
asserts it field by field, and
`test_stopped_variants_run_the_base_design_then_stop` asserts that the schedule before the
stop is the base market's own.

## Why the parameter decides a result

Discovery divides by (re − v̄). On the selling side of the published family that
denominator is small:

| market | v̄ | selling re | denominator | a 32.5-franc sag becomes |
|---|---|---|---|---|
| 2 | 266.7 | X = 240 | −26.7 | **1.22** |
| 3 | 220.0 | Y = 175 | −45.0 | **0.72** |
| 4 | 210.0 | Y = 175 | −35.0 | **0.93** |
| 5 | 212.5 | X = 180 | −32.5 | **1.00** |

32.5 francs is not a guess. Market 4's period 14 — the one mature no-information
observation the published family contains — puts price that far below v̄ across eleven
completed sessions. Carried onto those denominators it is a correction of about 1.0 to a
selling-side D, against the **1.08** the agents post on the conceded cells of markets 2–5
(p = 0.24). Whether that 1.08 is aggregation or institutional sag is therefore not a
refinement of the result; it is the result.

The conceded cells are the selling cells. That follows from the free-rider identity
recorded in `CLAUDE.md`: v̄ is by definition the largest uninformed valuation and a buy
state is one where re > v̄, so no uninformed agent can ever push the buy side toward RE
without learning. Free riders exist only on the sell side, which is why markets 7 and 8
— which have none on either side — have no conceded cell at all and sit out of that row.

## Why the gap cannot be closed from what already exists

The no-information periods of the published markets:

```
market 2   periods 1, 2, 3, 4        four cold starts, no mature period
market 3   periods 1, 2              two cold starts, no mature period
market 4   periods 1, 2, 3, 4, 14    four cold starts and ONE mature period
market 5   periods 1, 2, 3           three cold starts, no mature period
```

Market 4 is the only published market that ends uninformed. Three of the four markets
behind the 1.08 have no observation anywhere of where their price rests, uninformed, past
period 4 — and the sag is what is being extrapolated across ten periods to correct them.

The sag is also not the same size in every market: the within-session SD of the
no-information sag is 4.6 francs in market 3, 13.0 in market 5, 17.5 in market 2 and 22.4
in market 4. A baseline measured on one market does not transfer to another, which is why
there is a variant per market rather than one arm.

## Why the information STOPS rather than being removed

The first design of this arm removed information from every period. That measures a
different object. A market that never had an insider is not a market that has had insiders
and then stops: if being picked off makes the uninformed shade their bids, a
never-informed market **understates** the sag, and the correction then under-corrects in
the same direction as the effect under study.

Stopping instead of removing makes every period before the stop design-identical to the
real market, so the first uninformed period after the stop is that market's own next
period with the information removed and nothing else changed. The stop is placed as the
earliest period that still leaves three informed periods behind it, so that the market has
been traded against insiders before the first period anyone measures.

## Market 94 is the validation case

Markets 92, 93 and 95 measure a gap. Market 94 does not: market 4's real period 14 already
measures the sag at −32.5 francs over eleven sessions. Variant 94 reaches that same period
14 of that same market with six uninformed periods before it instead of nine insider ones.

If the two agree, the assumption the other three variants rest on — that a stopped
market's sag is the real market's sag — has been tested rather than asserted. If they
disagree, the size of the disagreement is the bias in the whole arm. It is better to learn
that from one eight-hour session than from a referee.

## What the scripted gate already tells you, for free

`make gate-stopped` runs the PI baseline on all four: agents value a certificate at their
own expected dividend and never learn, so in the tail the price should be v̄. Measured:

```
market 92   cold  -1.9   mature tail -17.5    p9:-47  p10:-4  p11:-1
market 93   cold  -5.3   mature tail  -5.7    p6..p12 all between -4 and -10
market 94   cold  -5.7   mature tail  -5.7    p8..p14 all between -3 and -10
market 95   cold  -5.5   mature tail  -6.2    p7..p13 all between -1 and -11
```

Two things follow, and both belong in the analysis rather than in a footnote.

**The double auction has its own floor of about −5 francs.** That is mechanism, not
behaviour: it is what a correctly-reasoning agent that never learns produces in this
institution. Market 4's period 14 measures −4.9 francs scripted against −32.5 francs for
the agents, so of the measured sag roughly 5 francs is the institution and roughly 28 is
behaviour. **The LLM sag must be read against the scripted floor, not against zero**, and
the floor is available for $0 on every market this arm touches.

**The first period of a tail can reprice on inventory alone.** Market 92's period 9 — the
first uninformed period after an insider period — sits 47 francs below v̄ where its
periods 10 and 11 sit 4 and 1 francs below. Nothing was learned and nothing was
remembered: the scripted agent ignores price. What moved is the allocation, and with it
which agent is marginal. The analysis should therefore drop or flag the first period of
each tail. For markets 93, 94 and 95 that costs one observation of seven; for market 92 it
costs one of three, which makes market 92 the weakest of the four and is the price of its
eleven-period design.
