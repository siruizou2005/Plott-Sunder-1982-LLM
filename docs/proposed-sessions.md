# Twenty-six proposed sessions

Written for the LLM-agent paper (`19-Analysis/paper-llm`). Each arm is justified by a
specific threat to a specific claim in that manuscript; the numbers below were computed
from the reported sessions, not estimated.

**Sixteen of the twenty-six have run — the first four waves, all of them.** The ten in `ladder2`,
`ladder3` and `ladder1b` have not. This header has been wrong before in both directions, so
check rather than read: for each scenario in a wave, take its `run_name` and read `status`
out of `runs/<run_name>/*.meta.json`.

Seven waves, one arm each, run **one wave at a time**. A session holds at most
`broadcast_workers` requests in flight, so sessions × W is a structural ceiling against
Bailian's tolerated 50–80: the waves are 72, 48, 36, 36, 48, 48 and 24, and the three unrun ones
together would be 120. W stays at 12 in every file because the 26 sessions these arms are
read against all ran at 12.

```
make gate-stopped                            # free: the engine gate on the new markets
DRY=1 ./run_proposed.sh ladder2              # print the wave, launch nothing
./run_proposed.sh ladder2                    # then ladder3
./resume_proposed.sh ladder2                 # after an interruption
```

| wave | sessions | wall clock | cost | threat | status |
|---|---|---|---|---|---|
| `rounds` | 6 | ~13–15 h | ~$23 | truncation | run |
| `stopped` | 4 | ~7–8 h | ~$10 | the sag benchmark | run |
| `sellside` | 3 | ~8 h | ~$7.5 | sell-side sample | run |
| `disclosed` | 3 | ~8 h | ~$7.5 | the common-knowledge deficit | run |
| `ladder2` | 4 | ~8 h | ~$15 | the deficit, dialled up one rung | **not run** |
| `ladder3` | 4 | ~8 h | ~$15 | and one rung further | **not run** |
| `ladder1b` | 2 | ~8 h | ~$7.3 | decomposes ladder2's four-dial step | **not run** |
| | **26** | **~62 h** | **~$82** | | |

Costs are measured, not projected: the market-4 rounds arm ran six sessions at 4, 5 and 6
rounds and recorded $3.77–$4.04 and 13.0–13.2 h for the 6-round pair, against ~$2.47 and
~7.9 h for a 3-round session of the same shape. Six rounds nearly doubles a session; that
is most of this budget.

## Arm 1 — six rounds per period, paired (6 sessions, wave `rounds`)

```
scenarios/m7_control_r6_s42.yaml    scenarios/m8_control_r6_s42.yaml
scenarios/m7_control_r6_s43.yaml    scenarios/m8_control_r6_s43.yaml
scenarios/m7_control_r6_s44.yaml    scenarios/m8_control_r6_s44.yaml
```

**Threat.** Truncation — the only threat that can overturn the control-market result. In
the reported three-round sessions the price is still moving when the period ends:
informed-selling discovery rises 0.29 between the penultimate and final round (n=19,
p=0.0004), buying 0.06 (p=0.084). "Both sides agree at D≈0.41" may be two unfinished paths
measured at the same arbitrary moment.

**Design.** The six existing seeds, `max_rounds_per_period` 3→6, everything else identical,
so the comparison is paired period by period. The arm draws 21 selling and 33 buying
periods; the paired test has power 0.65 against the final-round climb halving. If D instead
climbs toward 1.0 in rounds 4–6, no test is needed — the reported result is truncation.

The pairing is on the *market*, not on the path: `Market.redrawn` keys its RNG on
`ps1982-m{number}-seq-{seed}`, so each session here faces the drawn sequence its
three-round counterpart faced, but the agents are stochastic and the realized trades will
differ. That removes sequence variance from the comparison and nothing else.

Market 4's rounds arm already ran this in the published family and found the buyer's
failure was not a rounds artefact. That does not carry over: market 4's buy side is 165
francs from target against market 7's 100, on a different prior.

## Arm 2 — the uninformed resting level (4 sessions, wave `stopped`)

```
scenarios/m92_stopped.yaml    scenarios/m94_stopped.yaml
scenarios/m93_stopped.yaml    scenarios/m95_stopped.yaml
```

**Threat.** The sag benchmark, and it is not a refinement — it is the size of the result.
Discovery divides by (re − v̄), and on the selling side of markets 2–5 that denominator is
−26.7, −45.0, −35.0 and −32.5 francs. Market 4's period 14, the one mature no-information
observation the published family contains, puts price 32.5 francs below v̄ across eleven
sessions. Carried onto those denominators that is a correction of 1.22, 0.72, 0.93 and
1.00 to a selling-side D — against the **1.08 the agents post on the conceded cells of
markets 2–5** (p = 0.24). The conceded cells are the selling cells, by the free-rider
identity, which is also why markets 7–8 have no such cell and sit out of that row.

**Why it cannot be settled from what exists.** Markets 2, 3 and 5 carry no-information
periods only at 1–4, 1–2 and 1–3 — every one a cold start, not one mature. Market 4 alone
ends uninformed. And the sag does not transfer between markets: its within-session SD is
4.6 francs in market 3, 13.0 in market 5, 17.5 in market 2, 22.4 in market 4. Hence one
variant per market rather than one arm.

**Design.** Markets 92–95 run their base market unchanged through a stated period and then
transmit nothing (`ps1982/markets.py`; `docs/markets-92-95-stopped.md`). Stopping rather
than removing is deliberate: a market that never had an insider understates the sag if
being picked off makes the uninformed shade their bids, and would under-correct in the same
direction as the effect under study. `paper_exact` on each base market's `m{n}_paper_0`
seed, so periods before the stop are identical to a reported session down to the round
order and the seat→name mapping.

**Market 94 is the validation case, not a gap.** Market 4's real period 14 already measures
−32.5 francs over eleven sessions; variant 94 reaches that same period with six uninformed
periods before it instead of nine insider ones. If they agree, the assumption the other
three rest on has been tested. If they disagree, the disagreement is the arm's bias.

**What one session per market can and cannot deliver.** The pooled intraclass correlation
of the sag across 39 completed sessions is 0.24 (95% CI [0.09, 0.43]) — session-level
variance is real, so 14 periods in one session are not 14 independent observations. One
session per market therefore gives a level, not an interval: with k = 1 the between-session
component is not estimable at all, and periods beyond about seven buy very little
(±5.5 → ±5.1 francs on markets 7/8's scale). **Report these as clustered by session and do
not quote an interval that assumes independence.** If the decomposition has to be settled
rather than bounded, that is ~8 sessions of one market, not one each of four.

## Arm 3 — more control sessions (3 sessions, wave `sellside`)

```
scenarios/m7_control_s45.yaml    scenarios/m7_control_s46.yaml    scenarios/m8_control_s45.yaml
```

**Threat.** Sell-side sample. The control markets' selling side rests on 20 scored periods
against 33 buying, and the shortage is structural: equidistance forces the prior above one
half (Proposition 1), the selling state is the 0.4 one, so nine insider periods yield 3.6
selling periods in expectation. Mirroring the design does not help — swapping both the
prior and the dividend columns relabels the states and leaves the likely state on the
buying side.

**Design.** The next consecutive seeds, unfiltered, `random_prior` as before. They draw 14
selling periods, taking the arm to about 34 and the selling-side interval from ±0.148 to
±0.119.

**Why market 7 gets two of the three sessions.** By a rule fixed on the *reported* draws,
not on the new ones: across seeds 42–44 market 7 drew 9 selling periods and market 8 drew
12, so the extra session goes to the sell-starved market. Stated because the allocation
that rule produces — m7 at 45 and 46, m8 at 45 — happens also to be the sell-heaviest of
the consecutive-seed options (m8 at 46 draws 3), and an unexplained 2:1 split sitting above
the paragraph below would read as the selection that paragraph refuses.

**Seed selection was rejected.** Sell-heavy seeds exist (m7: 27, 136, 145; m8: 76, 120 —
six or seven selling periods, against a 9.9% chance of six or more at random), but choosing
them selects the sample on the variable under study. `m7_control.yaml` records the same
refusal for the original seeds.

**Free side effect.** Each of these three sessions also contributes one mature
no-information observation at period 14, taking markets 7–8's mature sample from 6 sessions
to 9 and its interval from about ±6.6 to ±5.4 francs — which on their ±100 denominators is
±0.05 of D on both sides. The equidistant design is why Arm 2 does not need to touch
markets 7 and 8 at all.

## Arm 4 — structural disclosure (3 sessions, wave `disclosed`)

```
scenarios/m4_disclosed_paper.yaml    scenarios/m7_disclosed_s42.yaml    scenarios/m8_disclosed_s42.yaml
```

**Threat.** The common-knowledge deficit. Plott & Sunder's subjects sat in one room and
could deduce structure the instructions never stated; the baseline LLM agent knows its own
two dividend amounts and nothing else, so any shortfall against the paper may be starved
common knowledge rather than failed aggregation.

**Design.** `Rules.disclose_structure` writes the structure into every system prompt: the
full three-type dividend table with the agent's own type named, four investors per type,
and that in a card year exactly two of each type's four hold a lettered card. Identities,
whether the holders stay the same across years, and which years are card years stay
hidden; `announce_no_info_period` stays unset. Each session runs on the seed of a
completed baseline — `m4_paper_0` (20250755, `paper_exact`), `m7_ctrl_42` and `m8_ctrl_42`
(`random_prior` redraws the same sequence from the same seed) — so the comparison is
paired period by period and the prompt is the only difference. Full design and wording
constraints: `docs/disclosure-treatment.md`.

**This wave has run** (2026-08-07, commit `bf96f64`, $7.98, zero API failures). Results and
the mechanism they point at are in `docs/disclosure-results.md`: discovery did not rise
uniformly — market 8 improved on both sides, market 7 fell on both, market 4 sat still —
and the split tracks whether disclosure converted the uninformed from prior-anchoring to
price-reading. Arms 5 and 6 are what it turned into.

## Arm 5 and Arm 6 — two more rungs of the ladder (4 sessions each, waves `ladder2`, `ladder3`)

```
scenarios/m7_ladder2_s42.yaml  m7_ladder2_s45.yaml  m8_ladder2_s42.yaml  m8_ladder2_s44.yaml
scenarios/m7_ladder3_s42.yaml  m7_ladder3_s45.yaml  m8_ladder3_s42.yaml  m8_ladder3_s44.yaml
```

**Threat.** The same one as Arm 4 — the common-knowledge deficit — but Arm 4's result says
the deficit is not a single quantity. Disclosure *deleted* an ambiguity that had been doing
useful work, and whether an agent then performed the inference it needs instead depended on
what the disclosure left its own type able to believe. Two things Arm 4 deliberately kept
hidden are the remaining obstacles, and one rung removes each.

**Design.** Rung 2 (`disclose_card_years`) announces each year as a card year or not, in
both directions, so a blank card in a card year means *I am one of the uninformed* rather
than *either that or nobody is informed*. Rung 3 (`disclose_insiders_fixed`) adds that the
card holders are the same investors every card year, which makes cross-period inference
available for the first time. Full design, wording and the truth-check of each new sentence
against the engine: `docs/disclosure-treatment.md`.

**The caveat that has to travel with any result.** `objective_profit_max`,
`clue_is_certain` and `period_end_style: memo` all ride with both rungs, so **rung 2 −
rung 1 is a bundle of four dials.** Only **rung 3 − rung 2 is a single-dial contrast** —
the three passengers are constant across the two tiers, which is precisely what keeps it
clean. A large rung-2 effect will not say which of the four produced it; the ladder is a
dose-response against `runs/disclosed/`, not four clean comparisons.

**Arm 7 decomposes it** (2 sessions, wave `ladder1b`): rung 1's disclosure plus all three
passengers and NOT `disclose_card_years`, on market 7 and market 8 at seed 42, where both
already have a completed rung-1 session. `runs/disclosed/` → `ladder1b` isolates the three
passengers; `ladder1b` → `ladder2` isolates the card-year rung. With `ladder3` − `ladder2`
for the fixedness sentence, every step of the ladder becomes a single-dial contrast.
2 × 12 = 24 in flight, ~$7.3.

**Seeds, and why these ones.** m7 runs {42, 45}, m8 runs {42, 44}; each market's pair pools
to 9 buy / 9 sell over the informed periods. That is a departure from Arm 3, which declined
to filter seeds on the balance — and the distinction is the estimand. Arm 3 reports a
**level** (discovery against 1.0), where selecting on the variable under study biases the
estimate. The ladder reports a **paired within-market difference**, and the treatment is a
prompt, so the same drawn sequence sits on both sides of every comparison: balancing moves
the precision of the difference, not its expectation. That is blocking on a pre-treatment
covariate. It is worth doing because the entire Arm 4 result lived on the sell side (three
periods per market), and m7's unfiltered seeds 43 and 44 are its two most buy-heavy draws.
`tests/test_markets.py` pins the counts and the argument together.

Seed 42 is in both pairs because it is the only seed with a completed rung-1 session, so
the full four-rung ladder exists there and nowhere else.

**Cost.** ~$12.7 and ~8 h per wave, ~$25 for both. The per-seed base comes from the
completed sessions on those exact draws ($2.54–$2.87, and seeds 44/45 are the pricier ones
because they provoke more trading); the memo adds ~16%, almost all of it on the input side
— notes ride in the user message, which no prefix cache covers, and the memo is in ~96% of
turn and broadcast prompts. 4 × 12 = 48 in flight; both waves at once would be 96, past the
ceiling.

## Reading the results

**Against the scripted floor, not against zero.** `make gate-stopped` measures what a PI
agent that never learns produces in this institution: about −5 francs of sag in every one
of markets 92–95, and −4.9 at market 4's period 14 against the agents' −32.5. Roughly 5
francs of the measured sag is the double auction and roughly 28 is behaviour. The floor
costs nothing and is available for every market this arm touches.

**Drop or flag the first period of each tail.** Market 92's period 9 — the first uninformed
period after an insider period — sits 47 francs below v̄ under scripted PI where its
periods 10 and 11 sit 4 and 1 below. Nothing was learned; the allocation moved, and with it
which agent is marginal. That costs one observation of seven for markets 93–95 and one of
three for market 92, which makes market 92 the weakest of the four.

**Drawn is not scored.** Selling and buying counts above are *drawn* periods. The analysis
scores only periods that produced a trade, so the usable counts will be slightly lower —
the reported control arm drew 21 selling periods and scored 20.

**The stopped arm's own insider periods are a robustness sample, not a pooled one.** Each
stopped session retains three or four informed periods, but on a schedule no reported
session ran. Do not fold them into the main counts.

After the runs, re-run the analysis package (`19-Analysis/paper-llm/code/`) —
`results_within.py` for the truncation test, `results_reachability.py` for the concession
decomposition, `inventory.py` for the counts. The ladder waves add two run groups it does
not know about (`runs/ladder2/`, `runs/ladder3/`) and one violation reason
(`truncated_note`, which unlike `empty_note` keeps the note).
