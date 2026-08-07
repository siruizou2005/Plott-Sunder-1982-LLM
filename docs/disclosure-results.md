# The disclosure arm: what three paired sessions found

Wave `disclosed`, run 2026-08-07 on gcp-la at commit `bf96f64`. Three sessions, each on the
seed of a completed baseline, with `Rules.disclose_structure` the only difference. Design
and wording constraints: `docs/disclosure-treatment.md`.

| session | paired baseline | calls | cost | wall clock | api_error | malformed |
|---|---|---|---|---|---|---|
| `disclosed/m4_disc_paper` | `runs/m4/m4_paper_0` | 4,336 | $2.70 | 8.4 h | 0 | 0 |
| `disclosed/m7_disc_42` | `runs/control/m7_ctrl_42` | 4,269 | $2.47 | 7.3 h | 0 | 0 |
| `disclosed/m8_disc_42` | `runs/control/m8_ctrl_42` | 4,545 | $2.81 | 8.0 h | 0 | 0 |

13,150 calls, zero API failures and zero unparseable replies, so nothing is excluded for
contamination. Violations stayed in their usual band (`empty_note` 10–22 per session, one
`illegal_accept`), which is data rather than error.

**Read every number below as three observations of n = 1.** Each market contributes one
session and nine informed periods. The direction of the market-8 result is consistent
across periods, but none of these differences carries a test.

## Headline: disclosure did not raise discovery uniformly — it replaced the uninformed's mode of reasoning, and discovery followed only where that replacement bit

Paired period by period (same seed, same drawn sequence, so the market is identical):

| | buy side | sell side |
|---|---|---|
| market 4 | +0.058 (1 better / 3 worse) | −0.036 (3 better / 2 worse) |
| market 7 | −0.070 (2 / 3) | **−0.310 (0 better / 3 worse)** |
| market 8 | **+0.123 (4 / 2)** | **+0.324 (2 / 1)** |

Market 8 improved on both sides, market 7 fell on both, market 4 sat still. The split is
not noise-shaped: it lines up with a behavioural measure in every case.

## The mechanism: prior-anchoring was replaced by price-reading — in two of three markets

Basis cited by **uninformed** agents in informed periods (5–13), n = 162 per cell:

| | cites price | cites prior |
|---|---|---|
| market 8 | 70.4% → **93.8%** | 27.2% → **4.9%** |
| market 4 | 68.5% → 80.2% | 27.8% → 18.5% |
| market 7 | 78.4% → 76.5% | 12.3% → 15.4% |

Uninformed posteriors on the true state moved the same way: market 8 0.636 → 0.703,
market 4 0.575 → 0.646, market 7 0.645 → 0.601.

The rank order of the effect is the rank order of the baseline's prior-reliance. Market 7's
baseline was already the most price-oriented of the three; there was nothing to convert,
and it went backwards.

## Why market 7 went backwards: disclosure removed the ambiguity that was doing the work

Direction was never wrong — **magnitude collapsed.** Signed deviation of uninformed
reservation prices from their own prior EV, split by the realized state (X periods should
pull up, Y periods down):

| | X periods | Y periods | directional swing |
|---|---|---|---|
| market 7 baseline | +139.5 | −27.2 | **+166.6** |
| market 7 disclosed | +23.6 | −19.3 | **+42.9** |
| market 8 baseline | +77.0 | +1.3 | +75.7 |
| market 8 disclosed | +229.7 | −14.9 | **+244.5** |
| market 4 baseline | +80.3 | −17.1 | +97.5 |
| market 4 disclosed | +44.1 | +45.4 | −1.3 |

Market 7's baseline uninformed drifted 95 francs from their own EV over an informed period
and the drift **grew within the period** (round 1 → 2 → 3: 14.7 → 123.0 → 149.8): they were
chasing the price. Disclosed, the drift is 36 francs and **flat across rounds**
(26.1 → 46.6 → 35.6). Types I and II collapsed onto their own arithmetic almost exactly:
deviation +83.6 → **+3.1** and +96.2 → **+4.8**.

The reading. A baseline agent watching the price climb to 340 has two explanations and
cannot separate them: *someone holds a letter*, or *someone simply values it higher than
me*. **Both point at the same action — follow.** Not knowing what anyone else's
certificate is worth was doing the price discovery.

Disclosure deletes the second explanation. The agent now knows 260 is the highest
uninformed valuation in the market, so 340 stops reading as "someone values it more" and
starts reading as "that price is wrong". Extracting information from it now requires one
extra step — *a price above every uninformed valuation can only mean someone is
informed* — which is exactly the inference the free-rider identity says these markets
depend on. Market 7's agents stopped at "260 is the ceiling, I will not chase" and never
took it.

## Why market 8 took the step and market 7 did not: the two markets say different things to the marginal type

The one design difference between them is the one the markets were built to carry
(`docs/markets-7-8-equal-width.md`):

| | tops the X state | tops the Y state | what disclosure tells type I, which sets v̄ |
|---|---|---|---|
| market 7 | **I** (360) | III (160) | "your EV of 260 is the market's highest uninformed value, **and** you win in X" |
| market 8 | III (400) | II (200) | "you set v̄ = 300, **and you top neither state**" |

Market 7's message is reassuring — it reads as confirmation that 260 is the right price.
Market 8's is unsettling: someone else is the right holder in *both* states, so sitting at
v̄ is never correct. The behaviour follows exactly:

| type I, uninformed | deviation from own EV | never moved (≤2 francs) |
|---|---|---|
| market 7 baseline → disclosed | +83.6 → **+3.1** | 28.8% → 24.1% |
| market 8 baseline → disclosed | +10.7 → **+115.8** | 43.4% → **9.4%** |

Market 8's whole roster came unstuck (never-moved rate 43/42/30% → 9/9/13% across the three
types); market 7's did not move at all on that measure, but shrank its steps when it did.

**Disclosure supplies the material for the RE inference. Whether agents perform it depends
on whether what they are told leaves them able to sit still.**

Market 4 is the intermediate case and confirms the reading from the other side: its
structure matches market 7's (type I both sets v̄ and wins X), and its directional swing
collapsed the same way (+97.5 → −1.3). Its discovery did *not* collapse with it, because
market 4 has free riders — 2 of 6 uninformed on the selling side — so the sell-side price
can reach RE without anyone learning anything.

## Secondary findings

**Disclosure paid the insiders, not the uninformed.** Insider profit as a share of
uninformed: market 4 171% → 204%, market 7 **24% → 133%**, market 8 236% → 346%. Market 7's
baseline is the striking one — its insiders earned *a quarter* of what the uninformed
earned, an information advantage completely given away. The plausible route is that
price-reading uninformed agents are more willing to take the other side of an informed
quote, and the counterparty to an insider is the one being picked off. Unverified.

**Allocation moved only in market 4** (certificates in the RE-predicted holder's hands
49.1% → 60.7%; market 7 53.9% → 44.6%, market 8 51.5% → 53.0%). Efficiency was flat
everywhere (91–96%, ±1.5 points).

**Agents used their disclosed type, but not the structural inference.** Uninformed notes
began carrying self-identification — "as a Type III who gains most from X", "the expected
value of a Type III certificate" — which is absent from the baseline by construction. But
it appears in only ~1% of notes, and the load-bearing inference ("a price above every
uninformed valuation means someone holds a letter") essentially never appears in writing.
Meanwhile "someone else may be informed" was **already** present in the baselines at
10–21% of uninformed notes and disclosure did not raise it (m4 10.3% → 16.4%, m7 21.2% →
22.5%, m8 20.6% → **14.7%**). What disclosure changed is not whether agents suspect
others are informed; it is whether they act on the price.

## What to run next

The market-7 reversal and the market-8 improvement are the two results worth confirming,
and each rests on one session. Three or four seeds per market would settle whether the
split is the type-role difference or the draw. Seeds 43 and 44 already have completed
baselines on both markets, so two more sessions per market extend the pairing at no design
cost.

The market-4 result — directional swing collapsed while discovery held — is the cleanest
test of the free-rider reading, because it separates "did the uninformed learn" from "did
the price arrive". Its stopped-market companion (`m94_stopped`) measures the same market's
uninformed resting level and would pin the denominator.
