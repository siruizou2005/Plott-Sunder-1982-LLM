# Markets 7 and 8 — the equal-width controls

**Neither is one of Plott & Sunder's**, and neither is Table 7's. Market 6 was the first
attempt at a control and it half-worked; these two are what replaced it. `docs/markets-1-to-5.md`
records the paper's five, `docs/market-6-control.md` records the sixth, and this file
records these two — every number labelled with where it came from.

## Why market 6 was not enough

`D = (price − v̄) / (re − v̄)`. Market 6 equalised the denominator: both informed-trade
directions sit 80 francs from the uninformed level. It left two things standing, and a
third that nobody had named.

**One: the numerator has slack.** With 24 certificates and four agents of the top type, any
price between the second-highest and the highest informed valuation supports the
competitive allocation, so a *fully competitive* price occupies a range of D, of width
(top − second)/|re − v̄|. Market 6 is the most lopsided market in the family on that measure.

**Two: the informed do not agree.** A "buy state" means re > v̄, and re is the top type's
valuation — it says where the RE price belongs, not what the informed will do. In markets 3
and 4 the buy state X has two of six insiders below v̄ and therefore *wanting to sell*.

**Three: the sell side gets free help and the buy side never can.** Below.

| market | buy dist | sell dist | buy width | sell width | insider direction | sell-side free riders |
|---|---:|---:|---:|---:|---|---:|
| 3 | +180 | −45 | 0.556 | 0.556 | X 4 buy / 2 sell | 2 of 6 |
| 4 | +165 | −35 | 0.606 | 0.714 | X 4 buy / 2 sell | 2 of 6 |
| 5 | +107.5 | −32.5 | 2.308 | 0.769 | all three states net sell | 4 of 6 |
| 6 | +80 | −80 | **0.875** | **0.125** | X 6/0, Y 0/6 | 0 of 6 |
| **7** | **+100** | **−100** | **0.300** | **0.300** | X 6/0, Y 0/6 | 0 of 6 |
| **8** | **+100** | **−100** | **0.200** | **0.200** | X 6/0, Y 0/6 | 0 of 6 |

Markets 7 and 8 are the first in the family that are equidistant *and* equal-width *and*
unanimous in insider direction. Every row is recomputed from the dividends in
`tests/test_markets.py`, not transcribed.

## The two designs

Both have prior **24 of 40 balls pay X**, p(X) = .6 — forced, as market 6's was, by
Proposition 1: equidistance needs the buy state above 1/2. The prior is *derived*, not
assumed: 260 = .6(360) + .4(110) holds for all three of market 7's rows only at p = .6, and
all three are solved and compared rather than one being taken on trust.

### Market 7 — the family's structure, made symmetric

| type | state X | state Y | prior expectation |
|---|---:|---:|---:|
| I | 360 | 110 | **260 — marginal** |
| II | 330 | 130 | 250 |
| III | 290 | 160 | 238 |

v̄ = 260. Informed buy re = 360 (**+100**), informed sell re = 160 (**−100**). Competitive
interval 30 francs on both sides = **0.300 of D** either way.

### Market 8 — the same, with the three types' roles separated

| type | state X | state Y | prior expectation | role |
|---|---:|---:|---:|---|
| I | 380 | 180 | **300 — marginal** | sets v̄, tops neither state |
| II | 350 | 200 | 290 | tops the sell state |
| III | 400 | 100 | 280 | tops the buy state |

v̄ = 300. Informed buy re = 400 (**+100**), informed sell re = 200 (**−100**). Competitive
interval 20 francs on both sides = **0.200 of D**, the tightest in the family.

**The one thing that differs between the twins.** In markets 3, 4, 6 and 7 the marginal
type is *also* the buy-state holder, so when the buy signal arrives the units are already
in the right hands and only the price has to move — while the sell state additionally
requires a reallocation. That is a buy/sell asymmetry equidistance and equal width do not
touch. Market 8 removes it: both states demand the same reallocation away from the same
incumbent. Running only one of the two would leave it untested, which is why there are two.

## Provenance of every parameter

| parameter | value | source |
|---|---|---|
| dividends | market 7 and market 8's tables above | **ours** — the design under test |
| prior | 24 of 40 balls on X | **derived** from the stated prior expectations |
| bingo cage total | 40 | ours: 40 is the smallest total .6 divides into wholes |
| states, types | X/Y, I/II/III | ours |
| investors, per type | 12, 4 | inherited from **market 4** |
| insiders per type | 2 (six insiders) | inherited from market 4 |
| periods | 14 | inherited from market 4 |
| information design | none 1–4, insider 5–13, none 14 | inherited from market 4 |
| `sequence_states` | `XYYXYXYYXYXYXY` | inherited from market 4 — see below |
| no-information periods announced | no (blank cards) | inherited from market 4 |
| dividends-constant is common knowledge | yes | inherited from market 4 |
| endowments, fixed cost | 2 certificates, 10,000 / 10,000 | identical in all markets |
| `franc_to_usd` | 0.003 | inherited from market 4 |

**Market 4 rather than market 3 as the skeleton.** Market 4 is the only information design
in the family with a no-information period at the END (period 14). That period is the only
place the uninformed resting price can be measured *after* experience, and it is the one
measurement that separates a cold-start artefact from a real baseline bias: pooled over
every market the no-information price sits 20–40 francs below v̄, but market 4's own period
14 sits only 10.9 below, so the pooled figure is contaminated and the mature one is not.
A baseline bias δ inflates sell-side D and deflates buy-side D by δ/|re − v̄| on each side,
so it is first-order and cannot be estimated at all without that period. Six sessions add
six mature observations to the current five, and 24 cold-start ones to trace the curve.

The cost is that market 4 has **no full-information period**, so this arm adds nothing to
the institutional-component estimate of Section 3 — which markets 3 and 6 do feed.

**The inherited sequence is not this market's own.** `sequence_states` must hold something
and it holds market 4's row, because inventing one would be a design decision made
silently. It was realized under a .4 prior on X and carries 6 X in 14 periods against the
8.4 this .6 cage expects, so **`paper_exact` is not recommended here** — it would show
agents a sequence that argues against their own cage. The arm runs `random_prior`.

## The arm as run

Six DeepSeek sessions, three per market, at seeds 42, 43 and 44.

| | seed 42 | seed 43 | seed 44 | total |
|---|---|---|---|---|
| market 7 | 5 buy / 4 sell | 6 / 3 | 7 / 2 | **18 buy / 9 sell** |
| market 8 | 6 buy / 3 sell | 6 / 3 | 3 / 6 | **15 buy / 12 sell** |

**Unfiltered, and the imbalance is a known cost rather than an oversight.** Proposition 1
forces p(X) > 1/2 on any equidistant market, so nine insider periods are buy-heavy in
expectation (5.4 against 3.6) and this arm under-samples the sell side — the only
*separating* side — by construction, not by bad luck. Two remedies were considered and
declined:

- **Filtering seeds** on criteria fixed in advance (nine insider periods split 5/4 or 4/5;
  the two sides' mean ordinal position within the insider block differing by ≤ 1.0; the
  whole 14-period X count in 7–10). 75 of the first 500 seeds pass for market 7 and 74 for
  market 8, but only 8 pass in *both*; scanning from 1, the first three are 111, 206 and
  210, which give 13/14 in both markets. Declined: a filtered seed is a chosen seed, and
  calling it random would be worse than choosing openly.
- **Designing the sequence**, as market 6 does. A 5-buy/4-sell insider block with both
  sides' mean ordinal position at exactly 5.00 and a whole-sequence X count of 8 exists
  (`XYXXYXXYXYXXYY`). Declined: it fixes the state draw as one realization repeated three
  times per market.

Two consequences the analysis has to carry:

1. **Market 7's sell periods land late in two of three sessions** (mean ordinal position of
   the sell periods exceeds the buy periods' by 3.50 at seed 43 and 3.86 at seed 44; seed 42
   is 2.25 the other way). Since the uninformed resting price *rises* over a session, a late
   sell period is measured against a higher baseline than an early buy period, which
   inflates sell-side D on its own.
2. **Market 8's seeds 42 and 43 draw the same nine insider periods** and differ only at
   period 14. That market has two distinct sequences across three sessions, not three.

Both are pinned in
`tests/test_markets.py::test_the_seeds_the_arm_actually_runs_are_imbalanced_and_that_is_recorded`
so they survive to the write-up.

The seeds are also *not* paired across the two markets: `Market.redrawn` keys its RNG on
`ps1982-m{number}-seq-{seed}`, so seed 42 draws differently for market 7 than for market 8.
Pairing was available — market 8 reproduces market 7's seed-42 draw at seed 940 — and was
declined for the same reason the seeds were not filtered.

## The free-rider identity — read this before reading the runs

This is the largest thing the two markets turned up, and it was found by their engine gate
failing.

**On the buy side, no uninformed agent can ever help.** v̄ is `max_t E_prior[d_t]`, the
largest valuation any uninformed agent can hold, and a buy state is *defined* by re > v̄.
So no uninformed agent values a certificate above the buy-side RE price — in any market, at
any parameters. Every franc of buy-side price discovery must come from someone who learned
something. This has the same status as equation (1): algebraic, and not fixable by
reparameterisation.

**On the sell side there is no such identity, and every published market has helpers.**
re < v̄ leaves room for a type's prior expectation to fall *below* the sell-side RE price,
and then those uninformed agents sell at the RE price having inferred nothing:

| market | sell-side re | uninformed prior expectations | free riders |
|---|---:|---|---:|
| 2 | 240 | 267 / 267 / **197** | 2 of 6 |
| 3 | 175 | 220 / 210 / **155** | 2 of 6 |
| 4 | 175 | 210 / 200 / **145** | 2 of 6 |
| 5 | 180 | 212 / **170** / **152** | 4 of 6 |
| 6 | 140 | 220 / 191 / 190 | **0** |
| 7 | 160 | 260 / 250 / 238 | **0** |
| 8 | 200 | 300 / 290 / 280 | **0** |

(Market 1 has no sell state at all under a lettered clue and is not in the contrast.)

So in the published family a third of the uninformed — two thirds in market 5 — push the
sell-side price toward RE without learning, while zero can ever do so on the buy side.
**Part of "informed sellers reveal, informed buyers conceal" is an accounting property of
the parameters.** Markets 6, 7 and 8 are the only markets in which both directions require
genuine inference.

### What that does to the scripted baseline

`make gate7` and `make gate8` run the three algorithmic baselines. The engine is correct:
allocations end in the predicted hands, PI agents sit at the uninformed level and do not
move, ZI produces noise, and every buy period lands. **The sell side does not**, and now the
reason is arithmetic rather than mysterious. The scripted RE agent infers the state from
the last trade *price*, accepting it as a signal only within 12% of a revealing price. With
no free riders the only agents willing to trade below v̄ are the six insiders — and they are
sellers who would rather take the uninformed's high bids than walk the price down. So the
price never enters the sell-side band, so nobody learns, so the price never enters the band:

| market | sell re | signal band | lowest uninformed valuation | |
|---|---:|---|---:|---|
| 3 | 175 | [154, 196] | 155 | inside — the gate bootstraps |
| 4 | 175 | [154, 196] | 145 | below — bootstraps |
| 6 | 140 | [123, 157] | 190 | **blocked by 33 francs** |
| 7 | 160 | [141, 179] | 238 | **blocked by 59 francs** |
| 8 | 200 | [176, 224] | 280 | **blocked by 56 francs** |

Pooled over the arm's three seeds, the scripted RE baseline — algorithms that *already know
the state* — gives:

| market | buyer n | buyer mean | seller n | seller mean | null buy/sell gap |
|---|---:|---:|---:|---:|---:|
| 3 | 9 | 0.733 | 15 | 1.030 | **+0.297** |
| 6 | 13 | 0.839 | 11 | 0.633 | −0.206 |
| 7 | 18 | 0.886 | 9 | 0.549 | −0.337 |
| 8 | 15 | 0.923 | 12 | 0.414 | −0.509 |

Two things follow, and both change how the runs are reported.

1. **Market 3's mechanical baseline already produces +0.297 of buy/sell gap in the paper's
   own direction**, from agents with no strategy at all. Any measured gap on market 3 has
   to clear that before it is evidence of concealment.
2. **The controls' null runs the other way**, and the sell side is bimodal rather than
   merely low — market 7's nine sell periods are 4 near 1.0 and 5 near 0.1, market 8's
   twelve are 3 and 9. It is a threshold, not a ceiling: the cascade fires or it does not.
   So LLM sessions on markets 7 and 8 must be read as a **difference from these numbers**,
   never against 1.0, and the sell side needs the n it has (9 in market 7) reported next to
   its variance.

The scripted rule was **not changed**. It is the fixed comparison point for the completed
sessions and rebasing it would silently move all of them. What an LLM agent has and the
scripted agent does not is the order-flow channel — it can see six different seats trying
to sell and nobody bidding. Whether that is enough is precisely what this arm measures.

## Running it

```bash
make gate7 && make gate8                     # engine gate, zero API cost
./.venv/bin/python -m ps1982 validate -s scenarios/m7_control.yaml
./.venv/bin/python batch_plan.py --control-arm
./run_control_arm.sh                         # all six sessions
MARKETS=-m7 ./run_control_arm.sh             # one market's three
```

Scenario files: `scenarios/m{7,8}_control.yaml`, `scenarios/m{7,8}_scripted_{re,pi,zi}.yaml`.

Measured from the market-4 sessions this inherits its shape from (14 periods, 3 rounds,
~4,290 calls, ~$2.47, ~7.9h each): six sessions in parallel is ~25,700 calls, ~$15 and
~8–10 hours of wall clock, at W=12 for a structural ceiling of 72 requests in flight
against Bailian's tolerated 50–80.

Market 6 is superseded as the arm to run but kept as a market: `scenarios/m6_control.yaml`
and `make gate6` still work, and Table 7 is still what that design is.
