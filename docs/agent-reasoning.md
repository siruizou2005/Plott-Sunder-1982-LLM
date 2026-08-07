# Agent reasoning — how the uninformed form a belief

`docs/experiments.md` records what the prices did. This records what the agents said while
doing it, and whether the two agree. It is a reading of the four channels the log carries
alongside the book: the elicited belief attached to every turn, the reasoning trace behind
it, the private note written at a period end or after a trade, and the one-line
justification attached to every broadcast vote.

Its subject is the **uninformed** side. `docs/experiments.md` §E settles the informed side
— they state their exact private value about 60% of the time and within 1 franc at p90, so
the buyer-side failure is not that the insiders do not know what a certificate is worth.
What was still open is the other half: whether the uninformed ever read the price, what
they think they are reading, and why the reading stops where it does.

All numbers below are produced by `./reasoning_report.py` over the **25 `deepseek-v4-flash`
sessions** in `runs/m1` … `runs/m5`, and by the same script over `runs/control` for markets
7 and 8. Nothing is transcribed from an earlier note.

`docs/experiments.md` counts a 26th session in the same directories — `m3_gem_paper`, the
seed-paired Gemini run. **It is excluded from every table here and reported on its own**
under [one session on another vendor](#one-session-on-another-vendor), because it does not
behave like the other twenty-five and pooling 4% of the sessions into a claim about how a
model reasons is not worth the ambiguity.

**Contents** — [what the log carries](#what-the-log-carries) ·
[the basis is validated](#the-stated-basis-is-behaviourally-validated) ·
[the cliff](#the-cliff-written-down-likelihood-against-constructed-likelihood) ·
[three mechanisms](#three-mechanisms-behind-the-constructed-side) ·
[adverse selection](#adverse-selection-is-reached-and-then-discarded) ·
[no learning](#no-learning-across-a-session) ·
[markets 7 and 8](#markets-7-and-8-name-the-cause) ·
[the notes](#what-the-notes-contain) ·
[the Gemini session](#one-session-on-another-vendor) ·
[artifacts](#two-artifacts-that-will-bite) · [reproducing](#reproducing)

## What the log carries

| channel | event | n over the 25 sessions | what it is |
|---|---|---:|---|
| elicited belief | `agent_view` | 10,464 | `posterior`, `reservation_buy`, `reservation_sell`, `basis` |
| reasoning trace | `model_turn` | 10,464 | the model's own thinking, mean 9,400 characters |
| private note | `reflection` | 13,814 | written to itself, carried to its future turns |
| broadcast vote | `broadcast` | 59,397 | accept/decline with a ≤15-word reason |

`basis` is a forced choice among `prior | clue | price | others_behavior | spread`
(`ps1982/prompts/schemas.py`), described to the agent as "the single thing that most drove
this turn's judgement". It is the only place in the design where an agent states, in its
own voice, that it is reading the state off the market.

## The stated basis is behaviourally validated

Everything downstream assumes the label means something, so it is checked first. Against
the belief it is attached to, for uninformed agents:

| basis | periods | n | \|implied − prior EV\| | corr(implied, last trade) | belief is exactly the prior |
|---|---|---:|---:|---:|---:|
| `prior` | insider | 929 | **0.1 f** | 0.43 | **99%** |
| `price` | insider | 2,185 | **25.3 f** | **0.62** | 30% |
| `others_behavior` | insider | 83 | 31.5 f | **0.72** | 13% |
| `prior` | none | 1,820 | 0.1 f | 0.51 | **100%** |
| `price` | none | 1,164 | 11.3 f | 0.50 | **58%** |

`implied` is the certificate's value under the agent's own stated posterior and its own
dividends. An agent that says `prior` is sitting on the prior to within a tenth of a franc.
An agent that says `price` has moved 25 francs and moved *with* the price. The label is not
decoration.

It is also not free of narrative. In no-information periods, where no card exists to be
read, **58% of the agents claiming `price` report a belief identical to the prior** — and
the share saying `price` at all rises from 36% to 39% across the three rounds of a period in
which nothing whatever is knowable. The label carries content differentially: it means
something when there is something to mean.

The share does track the information condition:

| | round 1 | round 2 | round 3 |
|---|---|---|---|
| insider periods | 65% `price`, 32% `prior` | 71% / 25% | 66% / 30% |
| no-information periods | 36% `price`, 63% `prior` | 40% / 59% | 39% / 58% |

Reservation prices track the stated belief closely — `reservation_buy` sits about 5 francs
below `implied` throughout — so the beliefs are the input to the decision, not a gloss on
it.

## The cliff: written-down likelihood against constructed likelihood

The same agents, on the same model, get a posterior two ways. One of them they do
perfectly.

### Market 1 hands over the likelihood, and they are exact Bayesians

Market 1's clue is a ten-draw sample from one of two boxes of chips, so a correct posterior
exists and is computable. The prompt never uses the word "probability" — constraint 1 of
`docs/experiments.md` — and describes the mechanism as physical sampling. 585 insider views
against `sample_posterior`:

```
mean |stated − correct|  0.0085
median                   0.0003
within 0.01 of correct   95%
```

| sample | 1s | correct p(X) | stated mean |
|---|---:|---:|---:|
| `0000010000` | 1 | 0.769 | 0.769 |
| `0000000011` | 2 | 0.555 | 0.555 |
| `0000010101` | 3 | 0.319 | 0.313 |
| `0100101010` | 4 | 0.149 | 0.150 |
| `1110000011` | 5 | 0.062 | 0.086 |
| `1111111001` | 8 | 0.003 | 0.005 |

Nine agents, independently, land on the third decimal of a posterior nobody told them how
to compute.

### Price hands over nothing, and they barely move

The same population, uninformed, in insider periods, on the buy side — the only side whose
gap is large enough for a ratio to mean anything:

| market | prior EV | belief-implied value | RE | francs moved | % of gap |
|---:|---:|---:|---:|---:|---:|
| 1 | 244.4 | 247.1 | 323 | +2.7 | **3%** |
| 2 | 243.3 | 247.4 | 350 | +4.1 | **4%** |
| 3 | 195.0 | 210.2 | 400 | +15.2 | **7%** |
| 4 | 185.0 | 202.1 | 375 | +17.1 | **9%** |
| 5 | 178.0 | 180.3 | 290 | +2.3 | **2%** |

In absolute francs the movement is the same on both sides of the market and independent of
how far it has to go — +15.2 on market 3's buy side against a 205-franc gap, −18.5 on its
sell side against a 20-franc gap. This is the belief-side counterpart of the normalisation
caveat in `docs/experiments.md`: both sides push the price a similar absolute amount, and
the sell side "aggregates" mostly because its target is close. **The elicited beliefs say
the same thing the prices do, independently.** The sell-side ratio is not quoted here at
all: market 2's sell gap is −3.3 francs and market 5's is +2.0, and a ratio on that
denominator is noise, not a finding.

## Three mechanisms behind the constructed side

The reasoning traces name why, and each mechanism is separately measurable.

### 1. Own-dividend price inversion, which is a fixed point

Market 3, period 7, round 1. Ines is type I (X 400, Y 100), uninformed, watching trades at
250:

> "Assume the market price equals the expected value conditional on all public
> information. Then `250 = 400p + 100(1−p)` ⇒ `300p = 150` ⇒ **p = 0.5**. That is a
> reasonable posterior."

She reports `{X: 0.5, Y: 0.5}`, whose implied value is 250, and a reservation price of 250
— **exactly the price she read**. An agent that recovers its belief by inverting the price
in its own dividend scale arrives at a valuation equal to the price by construction, so its
reservation never exceeds the price and it cannot move one. The inversion is self-sealing.

Measured, over uninformed views where the price lies inside the agent's own dividend range:
**38% of `price`-based beliefs put the agent's own valuation within 5 francs of the last
trade.**

The alternative is available and it works. Bela, type II, same period, same trades:

> "If X is true, informed investors know it is worth 400, so a bid of 250 is quite
> plausible. If Y is true, informed investors know it is worth 150, so they would not bid
> 250. So P(E|X) > P(E|Y)."

Bela goes from 0.4 to **0.8** and posts a reservation of 270, above the price. **Likelihood
reasoning moves the price; inversion pins it.** Markets 3 and 4, where reservation prices
exceed the last trade in 46–49% of price-based views on the buy side, are the two markets
that move; markets 1 and 2, at 19–25%, are the two that do not.

### 2. The withheld base rate, correctly identified as fatal

Market 4, period 9, `m4_random_1`. Wendell is uninformed and reasons the adverse-selection
case out correctly:

> "If he knows it is X (worth 275), selling below value is irrational; if he has a Y clue
> (worth 150), selling at 200 is a good profit. **So posting an ask at 200 is more
> consistent with Y knowledge.** … But we need P(Bela posts an ask at 200 | each state).
> This is complicated because we do not know Bela's type, **and we do not know how many
> investors have clues**. The instructions say: 'No one is told how many investors receive
> a clue card that is not blank.' So we have no base rate. **Rational updating is very
> difficult. Our posterior should probably stay near the prior.**"

He reports `basis: prior` and a posterior equal to the prior to the digit.

This is prompt constraint 2 doing exactly what it was written to do. The paper withholds
the number of insiders; the agent identifies that withheld quantity as precisely the term
its likelihood ratio needs, and declines to invent it. **The blocked inference is a
property of the design, not a deficiency of the model** — and it should be reported that
way, because it is the one mechanism here that a treatment could lift. `docs/proposed-sessions.md`
already carries the disclosed wave; this is the measurement that motivates it.

### 3. The label is chosen before the belief

Market 5, period 7, `m5_paper_1`. Priya, uninformed, caught mid-decision:

> "I have no clue, so I should use the prior: X=0.35, Y=0.25, Z=0.4. But the market
> behaviour might inform me? … **However the instruction says 'basis' should be one of the
> listed options. I think 'price' is the most relevant, because the price has fallen to
> 160. So I will use price as the basis, but my posterior might shift.** … I am not sure.
> Let us say X=0.4, Y=0.1, Z=0.5."

The schema forces a label, the label is picked for plausibility, and the belief is then
improvised to match it. This is the mechanism behind the 30% of insider-period `price`
views and the 59% of no-information `price` views that report the prior unchanged. It is an
artifact of the forced-choice field, and it caps how strongly the `basis` series alone can
be read.

## Adverse selection is reached, and then discarded

Across 59,397 broadcast votes — every accept/decline in the 25 sessions, each with a stated
reason:

| reason | share |
|---|---:|
| own expected value | **43.1%** |
| dominance (above my max / below my min) | 15.1% |
| names the clue | 10.5% |
| price as a signal about the state | 7.9% |
| **the counterparty may know something** | **0.5%** |

The consideration is not absent from thought. It is absent from *memory*:

| where | incidence |
|---|---:|
| reasoning traces | **5.9%** (619 / 10,464) |
| private notes | **0.04%** (6 / 13,814) |

It is raised in the moment, roughly once every seventeen turns, and it is written down six
times in fourteen thousand notes. Nothing carries it into the next period.

The dominant rule instead is the unconditional one — *buy below my prior expected value* —
and in an insider period that rule buys precisely when the informed are selling. Scoring
every trade side ex post against the dividend actually paid:

| market side | role | held a card | n | mean francs | % losing |
|---|---|---|---:|---:|---:|
| buy | buyer | yes | 1,381 | +74.7 | 0% |
| buy | seller | no | 1,259 | −8.9 | 54% |
| **sell** | **buyer** | **no** | **910** | **−52.4** | **79%** |
| sell | seller | yes | 755 | +44.2 | 3% |

An uninformed agent buying in a bad-news period loses on 79% of its purchases, 52.4 francs
each. Informed agents lose on 0–3% of theirs. Pooled over insider periods the informed
sides realize **+190,732 francs** and the uninformed **−5,662**, i.e. essentially all of the
realized gain from trade. (The two are not a zero sum: the sides hold different dividend
schedules, so the total is the gain from trade, and the question is who captures it. The
no-information control is +20.5 francs a side with 38% losing, so this is the information
condition and not the institution.)

## No learning across a session

| period | n | % `price` | mean gap closed |
|---:|---:|---:|---:|
| 3 | 90 | 74% | 33.9% |
| 5 | 324 | 68% | 18.6% |
| 7 | 438 | 68% | 30.0% |
| 9 | 360 | 68% | 16.8% |
| 11 | 252 | 69% | 19.9% |
| 13 | 168 | 65% | 31.9% |

Ten periods of experience, three rounds each, with written notes carried forward, and
neither the propensity to read the price nor the quality of the reading moves. This is
consistent with §D of `docs/experiments.md`, which finds buyer-side price discovery
improving by +0.23 first-to-last as a noisy drift; the belief series shows no gradient at
all, which suggests the price improvement there is not coming from better inference.

## Markets 7 and 8 name the cause

The equal-width controls behave nothing like the published five:

| | markets 1–5 | markets 7 and 8 |
|---|---|---|
| `price` share, rounds 1→3 | 65% → 71% → 66% (flat) | **67% → 80% → 86%** |
| belief in the true state, sell side | flat | m7 0.484 → **0.637**; m8 0.437 → **0.644** |
| within-period drift, sell side | +0.001 to +0.081 | **+0.153 / +0.207** |

The design difference is the one `docs/markets-7-8-equal-width.md` was built around:
markets 7 and 8 are the first in the family **unanimous in insider direction** — all three
types rank the states the same way (m7: 360/110, 330/130, 290/160). Every one of the paper's
five markets contains a contrarian type: market 3's and 4's type III prefers Y where I and
II prefer X, market 1's and 2's type III prefers X where I and II prefer Y.

That is exactly the condition mechanism 1 needs. When the types agree in direction, reading
the price in your own dividend scale is approximately valid and the price has a common
meaning; when a contrarian type exists, it has none, and the inversion that 38% of agents
perform returns a number about a market that does not exist.

The clearest single case is a contrarian reading a *correct* price as a bubble.
`m2_paper_0`, market 2, where type III is the contrarian (X 240, Y 175, prior EV 196.7):

| period | info | state | RE | closing price |
|---:|---|---|---:|---:|
| 8 | insider | Y | 350 | 349 |
| 9 | insider | X | 240 (PI 267, **separating**) | 239 |

The market aggregated almost exactly in both. Yusuf, type III, in period 9, round 1:

> "The price has been around 347–349. **Our notes from past years indicate we should be
> cautious: in year 8 prices surged to 349 but Y was paid, so we learned not to trust
> momentum.**"

His memory of period 8 is factually correct and his inference from it is exactly wrong: 349
was not momentum, it was RE. In his own dividend scale a price of 349 is impossible — his
certificate can never pay more than 240 — so a correct price is indistinguishable from a
bubble, and the lesson he extracted from it makes him distrust the correct price of period
9. He reports the prior, in a separating period whose RE holder is **his own type**. This
same pattern — an uninformed agent in an insider period that names an insider, cites its own
notes, and still reports the prior — occurs on **250 of 3,240** such turns, 7.7%.

The three-way comparison is therefore: markets 7 and 8 remove the contrarian and the belief
updating appears; the paper's markets keep it and the updating does not. Markets 7 and 8
change equidistance, equal width and direction unanimity at once, so this is consistent
with mechanism 1 rather than a clean test of it. A design isolating direction unanimity
alone would settle it.

## What the notes contain

Incidence over the 13,814 private notes. These are keyword hits, not a classification — a
note can match several, and the shares do not sum to 1.

| | share |
|---|---:|
| claims to detect an insider | 16.3% |
| dominance — above my max / below my min | 12.2% |
| attributes a lost tie-break to speed | 10.6% |
| reads price as the signal | 8.7% |
| mentions the fixed cost | 4.1% |
| explicit Bayes / likelihood language | 2.2% |
| names a specific rival | 1.8% |
| suspects the price is noise | 1.3% |
| infers others hold different dividends | 1.2% |
| **adverse selection / being picked off** | **0.04%** |

Six things in them are worth knowing about.

**They rediscover the free-rider identity unprompted.** `CLAUDE.md` records it as an
identity of the design; the agents state it as a trading rule. Yusuf, market 5, type III,
top dividend 180: *"the market traded almost entirely at 190, well above my max dividend of
180. I sold both certificates at 190 for a risk-free profit, which was correct."* Nora,
market 3, type III holding a Y clue, top dividend 175: *"price stayed at 170–173, well below
175, so buying at those prices locked risk-free profit."* This is the 12.2% row, and the
15.1% dominance row in the broadcast votes.

**They read the ceiling, not the level.** Ines, market 3 period 8: *"I correctly identified
the state from the price ceiling of 195."* The highest price anyone will pay bounds the top
informed valuation, which is a sharper instrument than the price level and does not require
the base rate mechanism 2 lacks.

**They infer from the absence of movement.** Felix, market 4: *"The price stayed flat at
149–150 all year, giving no signal. The flat price tells me informed traders either did not
act or cancelled each other out."*

**They hallucinate insiders in no-information periods, and the notes sometimes save them.**
Market 4 period 4 is a no-information period — nobody holds a card. Wendell nonetheless
concludes *"Ines might have a clue that it is Y, and she is trying to sell high to
uninformed buyers"*, then overrides himself: *"our notes say the market seems driven by
uninformed traders or low private valuations, not reliable dividend clues, so we should not
rely on price movements."* Here the note is correct and the live inference is not. Compare
Yusuf above, where it is the other way round. The notes are a low-pass filter on the price
signal, and they help or hurt depending on whether the signal was real — which is the same
thing as saying they do not distinguish the two.

**They attribute a random tie-break to speed.** 10.6% of notes, the third most common
theme. The rules state that when several agents accept the same quote one is chosen at
random; the notes read this as a skill deficit and resolve to fix it — *"I missed several
acceptances due to random draws"*, *"others were faster"*, *"next year I will announce bids
faster."* No such lever exists.

**They separate ex ante from ex post inconsistently.** Teodor, market 3: *"I bought at 180,
a good deal ex ante, but Y paid 100, so I lost on that trade"* — correct. Wendell, same
market, same evidence: *"I will now only buy when the price is below 100, my Y value"* —
a rule fitted to one realized state. Both readings persist into later periods.

## One session on another vendor

`m3_gem_paper` is `gemini-3.5-flash` on Vertex, seed-paired with `m3_paper_0` and counted in
the main result of `docs/experiments.md`. It is excluded above. On this document's measures
it is not a twenty-sixth replicate of the same behaviour:

| market 3, uninformed | 5 DeepSeek sessions | the Gemini session |
|---|---|---|
| `price` share, insider rounds 1→3 | 69% → 76% → 75% | **83% → 100% → 100%** |
| \|implied − prior EV\| when it says `price` | 32.3 f | **57.4 f** |
| `prior` share of insider-period views | 152 of 720 (21%) | **7 of 144 (5%)** |
| `prior` views that are exactly the prior | 99% | 100% |

It reads the price roughly twice as hard, abandons the `prior` label almost entirely once
an insider period is under way, and still correctly falls back to the prior when nothing is
knowable. That is the direction mechanisms 1 and 3 would predict a stronger model to move
in, and it is **one session** — enough to say the vendor is not a nuisance parameter here,
not enough to say anything about which model reasons better. It also cost 28% of the
project's entire API bill, so a matched arm is a real decision rather than a formality.

## Two artifacts that will bite

**`reservation_sell` is not usable without filtering on holdings.** An agent holding no
certificates has nothing to price and says so in the trace — *"I have none, so I will set it
to a high number like 1000 to indicate I would not sell. But that might be misleading"*
(Delphine, market 4). Over uninformed views the median is 197 and the maximum is 999,999;
1.3% exceed twice the agent's own top dividend. Any mean over the raw field is meaningless,
and this is the source of the 483.4-franc uninformed seller reservation in
`docs/experiments.md` §E. Use the median, or filter on `certs > 0`.

**`basis` must not be pooled across information conditions.** 58% of the agents claiming
`price` in a no-information period report an unchanged prior, against 30% in insider
periods. A `basis_drift` series that weights the two conditions equally is reporting the
forced-choice field's failure mode as a behavioural finding.

## Reproducing

    # the 25 sessions this document reports — note the m3 globs exclude m3_gem_paper
    ./reasoning_report.py runs/m[124]/*/*.jsonl runs/m5/*/*.jsonl \
        runs/m3/m3_paper_[01]/*.jsonl runs/m3/m3_random_*/*.jsonl

    ./reasoning_report.py --only cliff,fixpoint runs/m3/m3_paper_[01]/*.jsonl
    ./reasoning_report.py --only basis,converge runs/control/m[78]_ctrl_4[234]/*.jsonl
    ./reasoning_report.py --only basis runs/m3/m3_gem_paper/*.jsonl   # the Gemini session
    ./reasoning_report.py --dump /tmp/text runs/m3/*/*.jsonl          # the text itself

| section | table it produces |
|---|---|
| `basis` | the validation table, the by-round shares, the `reservation_sell` spread |
| `cliff` | market 1 against exact Bayes, and the buy-side gap closure |
| `fixpoint` | the share of price-based beliefs landing on the price |
| `pnl` | realized francs per trade side |
| `drift` | basis share and gap closure by period |
| `converge` | belief in the true state by round — the markets 7/8 comparison |
| `notes` | keyword incidence, and adverse selection in traces against notes |
| `override` | notes standing against a live inference |

`--dump` writes `reasoning.jsonl`, `notes.jsonl` and `why.jsonl` with market, period, side,
RE and informed status attached to every record, so the qualitative reading is a grep rather
than a re-parse of 1.5 GB of logs. It is large — about 94 MB for four markets — and belongs
outside the repository.

The sections take a few minutes over the full family: a substring pre-filter skips most of
each log before `json.loads` sees it, but `notes` must parse every `model_turn` and is the
slow one.

## Conclusions

1. The elicited `basis` is honest. Agents that say `prior` are on the prior to 0.1 franc;
   agents that say `price` have moved 25 francs and correlate 0.62 with the last trade. It is
   honest differentially: in a no-information period, where nothing is knowable, 58% of the
   agents claiming `price` report the prior unchanged.
2. The same model is a near-exact Bayesian when the likelihood is handed to it — 95% of 585
   market-1 insider posteriors within 0.01 of correct — and closes 2–9% of the buy-side gap
   when the likelihood has to be built from strategic behaviour.
3. Three mechanisms account for the difference, and each is separately measurable:
   own-dividend price inversion, which is a fixed point and covers 38% of price-based
   beliefs; the withheld insider count, which the agents correctly identify as the missing
   term and respond to by declining to update; and a forced-choice label chosen ahead of the
   belief it is supposed to summarize. Only the second is a property of the design rather
   than of the agents, and it is the only one a treatment can lift directly.
4. Adverse selection is reached in 5.9% of reasoning traces and recorded in 0.04% of notes.
   The rule that replaces it — buy below the unconditional expected value — loses on 79% of
   uninformed purchases in bad-news periods. Informed sides capture essentially the whole
   realized gain from trade.
5. None of this improves over a session, with or without notes.
6. Markets 7 and 8, which remove the contrarian type, are the only place in the family where
   uninformed beliefs visibly move. That is what mechanism 1 predicts, and it is consistent
   with rather than a test of it — the two markets change three things at once.
7. The one Gemini session reads the price about twice as hard as the twenty-five DeepSeek
   ones. One session settles nothing, but it does mean the vendor cannot be treated as a
   nuisance parameter in any of the above.
