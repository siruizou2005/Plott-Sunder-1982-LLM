# The disclosure ladder: design, run, and price convergence

Ten sessions run 2026-08-09 on `gcp-la` at commit `5dad182`. 40,072 model calls, $27.88,
7.3 hours wall clock, **zero API failures and zero unparseable replies** — nothing is
excluded for contamination.

The headline is that price convergence rose from **0.34 to 0.85 on the buying side and
0.49 to 0.75 on the selling side** against the same markets' own baselines, and that the
two sides were fixed by *different* rungs.

---

## 1. What the ladder is

`disclose_structure` (2026-08-07, `runs/disclosed/`) wrote the market's type structure into
every agent's system prompt and produced a result nobody predicted: discovery did not rise
uniformly. Market 8 improved on both sides, market 7 fell on both, market 4 sat still
(`docs/disclosure-results.md`). The mechanism was a **deletion**, not an addition — a
baseline agent watching the price climb to 340 has two explanations it cannot separate,
*someone holds a letter* or *someone simply values it more*, and both point at following
the price. Not knowing what anyone else's certificate is worth was doing the price
discovery.

Disclosure removes the second reading, so extracting information now needs one more step:
*a price above every uninformed valuation can only mean someone is informed.* Market 7's
agents stopped at "260 is the ceiling, I will not chase" and never took it.

The ladder asks what else an agent needs before it takes that step. Two things rung 1 left
deliberately ambiguous are the candidates, and each higher rung removes one.

| rung | flag added | what the prompt now says | sessions |
|---|---|---|---|
| **0** baseline | — | Table 1's "How Many: No" | `runs/control/` (4) |
| **1** structure | `disclose_structure` | the per-type dividend table, the agent's own type, two of each type's four hold a card in a card year | `runs/disclosed/` (2 of 3 used here) |
| **1b** passengers | *(no new disclosure)* | + explicit earnings objective, emphatic card certainty, memo-style year-end summary | `runs/ladder1b/` (2) |
| **2** card years | `disclose_card_years` | + each year announced as a card year or not, **in both directions** | `runs/ladder2/` (4) |
| **3** fixedness | `disclose_insiders_fixed` | + the investors holding the cards are the same ones every card year | `runs/ladder3/` (4) |

**What no rung ever discloses is WHICH investors hold the cards.** That clause is in all
four tail literals of the disclosure section and no flag removes it.

### Why rung 1b exists

Three dials ride with rungs 2 and 3 and are constant across them: `objective_profit_max`,
`clue_is_certain`, and `period_end_style: memo`. Without 1b, rung 2 minus rung 1 would move
**four** things at once and no result could be attributed. Rung 1b runs rung 1's disclosure
*plus all three passengers* and **not** `disclose_card_years`, which turns one four-dial
step into two single-dial ones:

```
rung 1  → rung 1b     isolates the three passengers
rung 1b → rung 2      isolates the card-year announcement
rung 2  → rung 3      isolates the fixedness sentence
```

Every step of the ladder is a single-dial contrast.

### The three passengers, precisely

- **`objective_profit_max`** puts an explicit earnings objective in the *shared preamble*,
  the only place that reaches the turn, broadcast and reflection prompts alike. The baseline
  states its purpose once, in the turn task — the paper's own "You are free to make as much
  profit as you can" — so a broadcast reply and a year-end note were written with no stated
  objective at all, and those two channels are 73% of calls and all of the durable memory.
- **`clue_is_certain`** states no new fact. The instructions already said a lettered card
  "is always correct"; the stronger wording *contains* that sentence verbatim.
- **`period_end_style: memo`** replaces the ~100-word year-end note with one standing
  document the agent rewrites in full each year, the new version replacing the old. See §5.

---

## 2. The markets, and why these two

Markets 7 and 8 are ours, not Plott & Sunder's (`docs/markets-7-8-equal-width.md`). They are
the first in the family that are **equidistant** (informed-buy and informed-sell targets both
100 francs from the uninformed level), **equal-width** (a merely-competitive price occupies
the same share of the D scale on each side), and **unanimous in insider direction**.

| | type I | type II | type III | v̄ | buy RE | sell RE |
|---|---|---|---|---|---|---|
| market 7 | 360 / 110 → **260** | 330 / 130 → 250 | 290 / 160 → 238 | 260 | 360 (+100) | 160 (−100) |
| market 8 | 380 / 180 → **300** | 350 / 200 → 290 | 400 / 100 → 280 | 300 | 400 (+100) | 200 (−100) |

The one difference between them is the one they were built to carry: **market 7's marginal
type also wins the buy state**, so when the buy signal arrives the units are already in the
right hands. **Market 8's type I sets v̄ and tops neither state**, so both states demand the
same reallocation away from the same incumbent.

Both use market 4's information design — no information in periods 1–4, insiders in 5–13,
no information in period 14 — and `random_prior`, which redraws each period's realized state
from that market's own prior.

### The free-rider identity — read before reading any number below

v̄ is the largest valuation any uninformed agent can hold, and a buy state is *defined* by
re > v̄. So **no uninformed agent can ever push the buy-side price toward RE without
learning something** — algebraic, not a parameter choice. Markets 7 and 8 have no free
riders on either side, which is what makes them the sharp test and also why their scripted
null is not 1.0. Read every number as a **difference from the same market's own baseline**,
never against 1.0.

### The seeds

| market | seed | drawn sequence | informed periods, buy / sell |
|---|---|---|---|
| 7 | 42 | `XXXXYXYXYYXXXX` | 5 / 4 |
| 7 | 45 | `XYYXXXYXYYYYXY` | 4 / 5 |
| 8 | 42 | `XXXXYYXXXXXXYY` | 6 / 3 |
| 8 | 44 | `XYYXXYYYXYXYYX` | 3 / 6 |

Each market's pair pools to **9 buy / 9 sell**. These seeds *were* chosen on their draws,
which `scenarios/m7_control.yaml` refuses to do — and the distinction is the estimand. That
refusal governs a reported **level** (discovery against 1.0), where selecting on the variable
under study biases the estimate. The ladder reports a **paired within-market difference**,
and because `Market.redrawn` keys its RNG on the seed and the treatment is a prompt, the same
drawn sequence appears on both sides of every comparison. Balancing moves the *precision* of
the difference, not its expectation: blocking on a pre-treatment covariate, not sample
selection. Pinned in `tests/test_markets.py`.

Rungs 1 and 1b exist only at seed 42, which is the only seed carrying a completed rung-1
session — so the **full five-rung ladder exists at seed 42 on both markets**, and seeds 45/44
carry rungs 0, 2 and 3.

---

## 3. How it was actually run

```bash
# on gcp-la, commit 5dad182
FORCE=1 ./run_proposed.sh ladder1b     # 2 sessions
FORCE=1 ./run_proposed.sh ladder2      # 4 sessions
FORCE=1 ./run_proposed.sh ladder3      # 4 sessions
```

All ten ran **concurrently**, not in three waves. Every session drives its phases on one
thread, so at most `broadcast_workers` of its requests are in flight at any instant and
`sessions × W` is a structural ceiling: 10 × 12 = **120**, against a measured mean in flight
of ~19.

This overturned a figure that had governed the repo. "Bailian tolerates 50–80 concurrent"
was never measured — it was inferred from batches that happened to top out at 72 — and on
that basis these ten sessions were originally scheduled back to back for a 24-hour wall
clock. Run together they took **7.3 hours at zero retries**, so `run_proposed.sh` no longer
serialises waves by default (`SERIAL=1` restores it). A concurrency figure is a fact about an
endpoint, never about the design: Vertex, serving Gemini from a dynamic shared quota,
produced 54 retries in 75 calls at the same W=12.

Every session: `deepseek-v4-flash` via Bailian, 12 LLM agents, 14 periods, 3 rounds per
period, `broadcast_workers: 12`, thinking on for turns, broadcasts and reflections.

| run | calls | cost | wall | api_error | malformed | empty_note | truncated_note |
|---|---:|---:|---:|---:|---:|---:|---:|
| `ladder1b/m7_lad1b_42` | 4,041 | $2.73 | 6.2 h | 0 | 0 | 0 | 0 |
| `ladder1b/m8_lad1b_42` | 3,946 | $2.90 | 6.3 h | 0 | 0 | 0 | 1 |
| `ladder2/m7_lad2_42` | 4,048 | $2.85 | 6.1 h | 0 | 0 | 0 | 0 |
| `ladder2/m7_lad2_45` | 3,765 | $2.53 | 5.6 h | 0 | 0 | 0 | 0 |
| `ladder2/m8_lad2_42` | 4,336 | $3.20 | 7.3 h | 0 | 0 | 0 | 0 |
| `ladder2/m8_lad2_44` | 3,954 | $2.70 | 5.8 h | 0 | 0 | 0 | 0 |
| `ladder3/m7_lad3_42` | 3,774 | $2.39 | 4.9 h | 0 | 0 | 0 | 0 |
| `ladder3/m7_lad3_45` | 4,248 | $2.98 | 6.5 h | 0 | 0 | 0 | 0 |
| `ladder3/m8_lad3_42` | 4,126 | $3.00 | 6.4 h | 0 | 0 | 0 | 0 |
| `ladder3/m8_lad3_44` | 3,834 | $2.60 | 5.5 h | 0 | 0 | 0 | 0 |
| **total** | **40,072** | **$27.88** | 7.3 h | **0** | **0** | **0** | **1** |

`api_error` and malformed JSON are counted separately and mean different things: an API
failure is **contamination** — the model never answered, so the skipped turn was not the
agent's choice — while unparseable JSON is model behaviour and part of the result. Both are
zero here, so no turn is excluded.

---

## 4. Price convergence

### 4.1 How the number is computed

```
D = (mean trade price in the period − v̄) / (RE price for that period − v̄)
```

where **v̄ = max over types of the prior expected dividend** — the highest valuation any
uninformed agent can hold — and **RE** is derived from the market's dividends and the clue
actually dealt, not transcribed from a table (`Market.theory_price`).

- `D = 0` — price sits where the uninformed alone would put it. No aggregation.
- `D = 1` — price is at the rational-expectations prediction. Full aggregation.

Implementation: `ps1982/metrics.py:price_discovery_by_informed_side`. Four rules matter:

1. **Insider periods only.** With everyone informed there is no asymmetry; with no one
   informed there is nothing to discover. Periods 1–4 and 14 are excluded.
2. **Periods with no trades are dropped**, because a mean price does not exist. This is why
   the same market and seed can show a different `n` at different rungs.
3. **States where RE = v̄ are dropped** — nothing to discover there.
4. **Side is assigned by RE, not by what the informed do**: `buyer` if RE > v̄ (the informed
   want to buy), `seller` if RE < v̄.

`metrics.py` never imports the engine. It reconstructs the `Market` from `session_start`
in the JSONL and recomputes everything from the log, so the scoring path is independent of
the run path.

**Pairing is per period, not per session.** Both sides of a comparison face the same drawn
sequence, so period 7 of rung 2 is differenced against period 7 of rung 0 and the
differences are then averaged. Averaging session means instead would discard that structure.

### 4.2 The ladder, period by period, seed 42

Both markets have all five rungs on this seed. Every cell is one period's `D`.

**Market 7, seed 42**

| period | side | rung 0 | rung 1 | rung 1b | rung 2 | rung 3 |
|---:|:--|---:|---:|---:|---:|---:|
| 5 | sell | 0.695 | 0.298 | −0.019 | 0.996 | 1.008 |
| 6 | buy | 0.104 | 0.376 | 0.071 | 0.206 | 0.989 |
| 7 | sell | 0.013 | −0.387 | 0.109 | 1.012 | 1.010 |
| 8 | buy | 0.212 | 0.399 | 0.137 | 0.324 | 0.878 |
| 9 | sell | 0.238 | 0.104 | 0.191 | 1.009 | 1.010 |
| 11 | buy | 0.368 | 0.170 | 0.372 | 0.611 | 0.990 |
| 12 | buy | 0.740 | 0.282 | 0.877 | 0.922 | 0.990 |
| 13 | buy | 0.679 | 0.524 | 0.990 | 0.865 | 0.990 |

**Market 8, seed 42**

| period | side | rung 0 | rung 1 | rung 1b | rung 2 | rung 3 |
|---:|:--|---:|---:|---:|---:|---:|
| 5 | sell | 0.009 | 0.624 | 0.911 | — | 0.602 |
| 6 | sell | 0.187 | 1.009 | 1.011 | 0.942 | 1.005 |
| 7 | buy | 0.000 | 0.448 | 0.453 | 0.594 | 0.657 |
| 8 | buy | 0.522 | 0.448 | 0.419 | 0.658 | 0.940 |
| 9 | buy | 0.530 | 0.557 | 0.776 | 0.792 | 0.990 |
| 10 | buy | 0.619 | 0.758 | 0.857 | 0.951 | 0.954 |
| 11 | buy | 0.645 | 0.871 | 0.711 | 0.841 | 0.990 |
| 12 | buy | 0.836 | 0.808 | 0.803 | 0.562 | 0.991 |
| 13 | sell | 0.376 | −0.088 | 1.028 | 0.948 | 0.397 |

The dash at market 8 period 5 rung 2 is rule 2: that period settled no trades.

### 4.3 Each step of the ladder, paired

Seed 42, both markets pooled, differenced period by period.

| step | what it isolates | side | n | mean Δ | better / worse |
|---|---|:--|---:|---:|---|
| 0 → 1 | structural disclosure | buy | 11 | **+0.035** | 6 / 5 |
| | | sell | 6 | **+0.007** | 2 / 4 |
| 1 → 1b | the three passengers | buy | 11 | **+0.075** | 6 / 5 |
| | | sell | 7 | **+0.199** | 5 / 2 |
| 1b → 2 | the card-year announcement | buy | 11 | **+0.078** | 9 / 2 |
| | | sell | 6 | **+0.563** | 4 / 2 |
| 2 → 3 | the fixedness sentence | buy | 11 | **+0.276** | **11 / 0** |
| | | sell | 6 | −0.080 | 3 / 3 |

**Overall, rung 0 → rung 3, seed 42:** buy `0.478 → 0.942` (Δ +0.464, n = 11), sell
`0.253 → 0.839` (Δ +0.586, n = 6).

### 4.4 All four seeds

Rungs 0, 2 and 3 exist on every seed, so these pool 18 buy and 16 sell periods.

| step | side | n | D before → after | mean Δ | improved |
|---|:--|---:|---|---:|---|
| 0 → 2 | buy | 18 | 0.342 → 0.701 | **+0.358** | **17 / 18** |
| | sell | 16 | 0.567 → 1.006 | **+0.439** | 14 / 16 |
| 0 → 3 | buy | 18 | 0.342 → 0.848 | **+0.505** | **18 / 18** |
| | sell | 16 | 0.492 → 0.750 | +0.258 | 14 / 16 |
| 2 → 3 | buy | 18 | 0.701 → 0.848 | +0.147 | 14 / 18 |
| | sell | 16 | 1.006 → 0.776 | **−0.230** | 4 / 16 |

### 4.5 What this says

**The two sides are fixed by different rungs, and each rung fixes the side the free-rider
identity says it should.**

The **card-year announcement is the sell-side rung** (+0.563 paired, and 1.006 pooled — at
RE). Under rung 1 a blank card was still ambiguous between "I am one of the uninformed two"
and "no one holds a letter this year"; the section said so explicitly. Announcing the
condition of every year makes a blank card in a card year mean *I am one of the uninformed*
and nothing else. That is the premise the price-based inference needs, and the sell side is
where an uninformed agent can act on it — selling below one's own valuation requires only
the belief that someone knows better.

The **fixedness sentence is the buy-side rung** (+0.276 paired, **11 of 11 periods**, and
18 of 18 pooled). The buy side is where the free-rider identity bites: no uninformed agent
can push the price toward buy-side RE without learning, so every franc of buy-side discovery
must come from someone who inferred something. Fixedness is the first thing on the ladder
that makes inference **cumulative across periods** — an agent that identifies a likely card
holder in year 6 can carry the suspicion into year 7. Rung 1 explicitly denied it that.

**Structural disclosure alone did almost nothing here** (+0.035 / +0.007), which reproduces
`docs/disclosure-results.md` on the two markets it shares. It supplies the material for the
inference and stops there.

**The passengers are not free** (+0.075 buy, +0.199 sell). Rung 1b was built to make the
other contrasts clean, and it turns out to carry a real sell-side effect of its own. Which
of the three did it — the stated objective, the emphatic card certainty, or the memo — is
not identified by this design.

**Rung 2's sell side is already at RE (1.006), so rung 3 has nowhere to go and falls back**
(−0.230, 4 of 16). Read that as a ceiling, not a regression: the sell side is finished at
rung 2 and the fixedness sentence adds nothing there while it is busy fixing the buy side.

### 4.6 Efficiency and who ends up holding

| rung | E% (allocative) | TE% (of the achievable surplus) | insider advantage |
|---|---|---|---|
| 0 baseline | 91–96 | **25–50** | 127–149% |
| 1 structure | 92–95 | 29–46 | 120–145% |
| 1b passengers | 92–98 | 27–66 | 103–135% |
| 2 card years | 96–100 | **73–98** | 96–107% |
| 3 fixedness | 95–100 | **66–98** | 100–110% |

TE% — the share of the *achievable* gain from trade the market actually captures, against a
no-trade baseline — moves far more than E% does, from a quarter to nearly all of it.

**Insider advantage falls to ~100%.** Insiders earned 27–49% more than the uninformed at
baseline and essentially the same at rungs 2 and 3. That is what aggregation looks like from
the other end: when the price carries the information, holding the card stops paying.

---

## 5. The memo, measured

`period_end_style: memo` replaces the ~100-word year-end note with one standing document
rewritten in full each year, the previous version shown verbatim and **replaced** by the new
one. All ten sessions ran it; 1,680 memos in total.

| | |
|---|---|
| median length | **800 words** (asked for "about 600") |
| p10 / p90 | 606 / 1,053 |
| longest | 9,434 |
| over 1,200 words | 54 / 1,680 = 3.2% |
| **accumulating rather than rewriting** | **0 of 12 seats, in all ten sessions** |
| truncated | 1 / 1,680 |
| empty (and so lost) | **0** |

**"About N" beats a range, and this was measured twice.** A probe asking for "between 500
and 800 words" returned a median of 1,050 with a maximum of 5,168 and only 19% inside the
band. The same prompt asking "about 600 words" returns a median of 800. The model follows a
single soft target and ignores a two-ended one — which is why `memo_max_words` sizes the
token budget and never reaches a prompt.

**The rewrite is real.** No seat's memo grew monotonically across the session in any of the
ten runs. The mechanism is the sentence that says the new version replaces the old and
*anything you leave out is gone* — a memo that merely accumulated would be a longer note.

**Cost.** The memo rides in the user message, which no prefix cache covers, and appears in
~96% of turn and broadcast prompts. Measured: it adds ~1,500 tokens to every prompt that
carries it, about +39% on a session — nearly all of it on the input side. The fourteen calls
that *write* each memo are the cheap part.

**Two engine changes ride with the style**, both from measured failures, both leaving the
note style byte-identical:

- The year-end brief now shows **the year's clue card**. Without it an agent writing its
  durable record cannot tell "the price told me X" from "my own card told me X" — and under
  a ladder whose whole subject is inferring who is informed, the year-end summary was being
  written without knowing whether the writer was one of them.
- It shows **every trade note from that year**, not the last three. At three rounds a seat
  writes 3.4 a period and up to 14, so the annual summary was being written from the tail
  of its own year.

**An empty memo is now retried** (up to `reflect_empty_retries`, set to 3). Nothing retried
it before: `max_retries` covers transient API errors, `repair_retries` covers unparseable
JSON, and `complete_text` sets `repairs = 0`, so the text channel had no loop at all and an
empty note was discarded. It fired zero times in 40,072 calls — the 16,384-token budget
made it unnecessary — but it is the difference between losing a seat's entire long-term
memory for a year and not.

---

## 6. How to read this, and what it does not say

- **Read as differences from these markets' own baselines, never against 1.0.** The
  free-rider identity means markets 7 and 8 have no uninformed agent who can help on either
  side, and their scripted nulls are −0.337 and −0.509 of buy/sell gap against **+0.297** on
  market 3.
- **Each rung is one or two sessions per market.** The seed-42 ladder is n = 1 per market
  per rung; the pooled rung-0/2/3 comparisons are n = 2 per market. Directions are
  consistent across periods and across both markets, but none of these differences carries a
  test.
- **Rung 2 minus rung 1 is not identified without rung 1b**, and rung 1b's own effect is a
  bundle of three. If it needs decomposing, the next cut is a rung-1-plus-memo session.
- **Do not pool with the replication.** These sessions test the baselines' external validity;
  folding them into the replication counts would launder the treatment into the result.
- **`docs/agent-reasoning.md`'s note statistics do not carry over.** They were computed on
  ~105-word notes written fresh each year; a 800-word document rewritten annually is not the
  same object and per-note rates are not comparable across the two styles.

---

## 7. Reproducing every number here

```bash
# the runs themselves (not in git; 925 MB)
runs/ladder1b/  runs/ladder2/  runs/ladder3/
runs/control/   runs/disclosed/          # the paired baselines

# rescore any log from scratch — metrics.py reads only the JSONL
make metrics
./.venv/bin/python -m ps1982 metrics -r runs/ladder3/m7_lad3_42

# the prompts, rendered without an API call
./.venv/bin/python -m ps1982 validate -s scenarios/m7_ladder3_s42.yaml --show-prompt
```

`D` per period is `sessions.0.paper.discovery_by_informed_side.periods` in each run's
`*.metrics.json`; efficiency is `paper.efficiency`, insider advantage is
`paper.totals.insider_advantage_pct`. The scenario files carry seed, market and every flag,
and `tests/test_scenarios.py` asserts each one actually loads — pydantic drops unknown YAML
keys silently, so a misspelt flag would otherwise run a lower rung under a higher rung's
name.
