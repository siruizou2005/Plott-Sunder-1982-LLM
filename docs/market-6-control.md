# Market 6 — the equidistant control

**Not one of Plott & Sunder's markets.** It is the control design of Table 7 in the
companion paper, and it exists to remove one confound: everywhere in the published family
the two informed-trade directions sit at different distances from the uninformed level, so
any normalised measure flatters one side. Here both are 80 francs.

`docs/markets-1-to-5.md` records the paper's five. This file records the sixth, and every
number in it is labelled with where it came from.

## The design

| type | state X | state Y | prior expectation |
|---|---:|---:|---:|
| I | 300 | 100 | **220 — marginal** |
| II | 230 | 130 | 190 |
| III | 225 | 140 | 191 |

Prior: **24 of 40 balls pay X**, i.e. p(X) = .6.

|  | value | required move | separating? |
|---|---:|---:|---|
| uninformed level v̄ | 220 | — | — |
| informed **buy** (state X) | re = 300 | **+80** | no |
| informed **sell** (state Y) | re = 140 | **−80** | yes |

The buy side is still non-separating. Equation (1) — re ≠ pi ⟺ the informed profit by
selling — is algebraic and holds for any parameters in this family, so equidistance removes
the *distance* confound and not the blind spot in the classic price test. They are separate
problems and only the first is fixable by reparameterisation.

### What equidistance does not fix: the competitive interval

With 24 certificates and four agents of the top type, any price between the second-highest
and the highest informed valuation supports the competitive allocation, so a fully
competitive price occupies a *range* of D rather than a point. The width of that range is
(top − second) / |re − v̄|, and equidistance equalises the denominator without touching the
numerator:

| market | buy side, D of a competitive price | width | sell side | width |
|---|---|---:|---|---:|
| 3 | 0.444 … 1.000 | **0.556** | 1.000 … 1.556 | **0.556** |
| 4 | 0.394 … 1.000 | 0.606 | 1.000 … 1.714 | 0.714 |
| 5 | Y: −1.308 … 1.000 | 2.308 | X: 1.000 … 1.769 | 0.769 |
| **6** | **0.125 … 1.000** | **0.875** | 1.000 … 1.125 | **0.125** |

Market 3's two sides happen to be *exactly* equal (100/180 = 25/45). Market 6 is the most
lopsided two-state market in the set: on the buy side the top two valuations are 70 francs
apart against an 80-franc target, on the sell side 10 francs apart. A buy-side price at
D = 0.3 in market 6 may be fully competitive; a sell-side price at D = 0.3 cannot be.

So market 6 trades one confound for another rather than removing both, and a buy–sell gap
measured on it in D still has a mechanical component — from interval width now rather than
from distance. Francs remain the safer measure. This is visible in the scripted gate below:
the buy side never reaches 1.0 because its competitive range starts at 0.125, while the
sell side is pinned to [1.000, 1.125] and is therefore either right or badly wrong.

Whether a parameter set exists that is equidistant *and* equal-width — it needs
top − second to be equal in both states, on top of p > 1/2 — has not been searched.

## Provenance of every parameter

| parameter | value | source |
|---|---|---|
| dividends | 300/100, 230/130, 225/140 | **Table 7** |
| prior | 24 of 40 balls on X | **Table 7** (states the cage itself) |
| bingo cage total | 40 | **Table 7** |
| states | X, Y | Table 7 (two states) |
| types | I, II, III | Table 7 (three types) |
| investors, per type | 12, 4 | inherited from **market 3** |
| insiders per type | 2 (six insiders) | inherited from market 3 |
| periods | 12 | inherited from market 3 |
| information design | none 1–2, insider 3–10, all 11–12 | inherited from market 3 |
| no-information periods announced | no (blank cards) | inherited from market 3 |
| dividends-constant is common knowledge | yes | inherited from market 3 |
| endowments, fixed cost | 2 certificates, 10,000 / 10,000 | identical in all markets |
| `franc_to_usd` | 0.003 | **ours** — market 3's; Table 7 does not state one |
| `sequence_states` for `paper_exact` | `XXXYYXYXXYXY` | **ours** — see below |

Market 3 rather than market 4 as the skeleton, for three reasons: it is the paper's
most-analysed market and this codebase's base case; it keeps two full-information periods,
which is where the institutional component of Section 3 is estimated and where that
estimate is currently thinnest (32 periods, only 9 on the seller side); and it is 12
periods rather than 14, which is ~25% cheaper and ~30% faster. The cost is one insider
period per session.

### The `paper_exact` sequence is a misnomer here

Market 6 has no Table 1 row, because it was never run. `MARKETS[6].sequence_states` must
hold something, and it holds a **designed** sequence: the eight insider periods split 4 X /
4 Y, and each side's mean ordinal position among them is 6.5, so neither side is
systematically early or late. Overall 7 X / 5 Y, against the 7.2 the prior would give in
expectation. It is what `ps1982 validate` and the scripted gate display. **The reported
runs do not use it** — they use `random_prior`.

## The arm as run

Three DeepSeek sessions on `random_prior` at seeds 42, 43, 44, plus a five-period Gemini
prefix of the first.

| seed | drawn states | insider buy (X) | insider sell (Y) | full-info periods |
|---|---|---:|---:|---|
| 42 | `XYXYXXXYYXYX` | 5 | 3 | Y, X |
| 43 | `XYYYXYYYXXXX` | 3 | 5 | X, X |
| 44 | `YXYXXXXYYXXY` | 5 | 3 | X, Y |
| | | **13** | **11** | |

`random_prior` rather than the designed sequence: the seeds draw 13 buy-side and 11
sell-side insider periods between them, which is balanced enough that hand-picking buys
nothing, and independent draws need no defence of the ordering. The balance was **checked
before running, not chosen for it** — the seeds were given, not searched.

Note that the memorisation argument for the random arm does not apply here. That arm exists
elsewhere so a model cannot recall Table 1's realized sequence; market 6 has no published
sequence to recall, and no published result either.

The Gemini session (`scenarios/m6_gemini_quick.yaml`) is seed 42 truncated to five periods,
so it is a literal prefix of `control/m6_ctrl_42` — same draw, same round order, same
seat→name map. Period for period the only difference is the model, which is the same
pairing `m3_gem_paper` has with `m3_paper_0`. Its five periods cover both sides:

    p1 X none · p2 Y none · p3 X insider (buy) · p4 Y insider (sell) · p5 X insider (buy)

## What the scripted gate says — read this before reading the runs

`make gate6` runs the three algorithmic baselines on market 6 at the seeds the arm uses.
The engine passes: RE agents reach 276–293 in buy periods against a target of 300 and
133–136 in sell periods against 140, PI agents sit at the uninformed level in sell periods
and do not move, and ZI produces noise. Certificates end in the predicted hands.

But the RE baseline is **not symmetric on this market**, and it matters for how the LLM
runs are read. Pooled over seeds 42/43/44:

| | n | mean discovery | shape |
|---|---:|---:|---|
| market 6, scripted RE, buyer | 13 | 0.839 | tight, 0.71–0.96 |
| market 6, scripted RE, seller | 11 | 0.633 | **bimodal**: six near 1.0, five near 0.1 |
| market 3, scripted RE, buyer | 3 | 0.754 | |
| market 3, scripted RE, seller | 5 | 1.074 | |

Market 3's mechanical baseline overshoots on the sell side and undershoots on the buy side.
Market 6's does the opposite, and its sell-side failures cluster on the **first** insider
period of a session (seeds 43 and 44 both fail there, seed 42's first insider period is a
buy period and succeeds).

The cause is the one the paper already predicts qualitatively. Proposition 1 forces
p > 1/2, so the informed-buy state is now the *likely* state, and an uninformed agent
begins already leaning toward it. Concretely: the scripted agent anchors each state's price
from what it has seen, and in market 6 every type's prior expectation is closer to its own
X dividend than to its Y dividend, so the two no-information periods leave every agent with
an anchor for X and nothing for Y. A sell period arriving next has to overcome that.

This is a property of the scripted baseline's inference rule, not of the engine, and the
rule was **not changed** — it is a fixed comparison point for 32 completed sessions. But it
means the control's own null is tilted, and the LLM runs should be reported against it
rather than against a presumption of symmetry.

## A correction this file's tests forced

Section 10 states: *"The buy-side state in Plott and Sunder (1982) carries prior probability
1/3 in markets 1 and 2, 0.4 in markets 3 and 4, and 0.35 in market 5 — all at or below 1/2.
No market in the published design can be equidistant."*

Recomputed from the dividends (`test_how_far_each_published_market_asks_each_side_to_move`,
`test_which_published_markets_proposition_1_actually_rules_out`,
`test_market_5_already_contains_an_equidistant_pair`):

| market | v̄ | sell side | buy side |
|---|---:|---|---|
| 1 | 283.33 | *(none under a lettered clue)* | X +16.67 (p=1/3), Y +66.67 (p=2/3) |
| 2 | 266.67 | X −26.67 (p=1/3) | **Y** +83.33 (**p=2/3**) |
| 3 | 220 | Y −45 (p=.6) | X +180 (p=.4) |
| 4 | 210 | Y −35 (p=.6) | X +165 (p=.4) |
| 5 | 212.5 | X −32.5 (p=.35) | **Y +32.5** (p=.25), Z +107.5 (p=.40) |
| 6 | 220 | Y −80 (p=.4) | X +80 (p=.6) |

Three things follow.

1. **The buy-side state is not X in every market.** It is Y in markets 1 and 2, at prior
   2/3, and in market 5 the *sell* side is X (.35) while both Y (.25) and Z (.40) are buy
   states. The quoted priors are the priors of state X, which is the buy state only in
   markets 3 and 4.
2. **Proposition 1 rules out markets 3 and 4, and only those.** It is a two-state result
   and it is correctly proved; markets 1 and 2 have a buy state above 1/2 and are therefore
   *permitted* to be equidistant (they happen not to be), and market 5 has three states, so
   the proposition's hypothesis does not reach it at all.
3. **Market 5 already contains an equidistant pair.** v̄ = 212.5 sits exactly halfway
   between the sell-side X at 180 and the buy-side Y at 245 — ±32.5, exact rather than
   approximate. (Z is +107.5 and is not part of the pair.)

The Section 10 sentence therefore needs rewriting. **The equidistant pair is not, however,
a usable test of the asymmetry**, and it is worth being precise about why, because the
reason applies to market 6 as well. Scored on the five completed market-5 sessions the pair
looks decisive — seller X at D = +1.008 (n = 17), buyer Y at D = −0.717 (n = 13), a gap of
56 francs at equal distance — but state Y's competitive interval runs from D = −1.31 to
D = +1.00, so −0.717 lies *inside* it and the market has not failed by any competitive
standard. This is the "Interpretation of D = 1" limitation, quantified: market 5's
uninformed level sits inside the interval on both of its buy states, so no competitive
force pushes its price up there at all. Market 6 does not share that defect — its v̄ lies
outside both intervals — which is why the control is still needed.

## Running it

```bash
make gate6                                   # engine gate on market 6, zero API cost
./.venv/bin/python -m ps1982 validate -s scenarios/m6_control.yaml
./.venv/bin/python batch_plan.py --control-arm
./run_control_arm.sh                         # the three DeepSeek sessions
GEMINI=1 ./run_control_arm.sh control/m6_gem_quick    # the Vertex prefix, on its own
```

Scenario files: `scenarios/m6_control.yaml`, `scenarios/m6_gemini_quick.yaml`,
`scenarios/m6_scripted_{re,pi,zi}.yaml`.
