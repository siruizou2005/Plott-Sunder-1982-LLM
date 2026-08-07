# Experiments — what was run, where it lives, what it shows

The experimental design, every session this project has run, the directory holding its log,
and the numbers computed from those logs.

Related files, which this one does not duplicate: `docs/markets-1-to-5.md` records where each
market *parameter* was read off the paper and the two places the paper's table and body text
disagree; `docs/paper-verification.md` checks market 3 against the paper line by line;
`docs/design-deltas.md` argues each deliberate departure from the 1982 procedure.

All numbers below were recomputed from the logs with the current code, not transcribed from
an earlier report. Where a number here disagrees with an older note, this one is current.

**Contents** — [design](#the-design) · [where the data is](#where-the-data-is) ·
[inventory](#inventory) · [main result](#main-result--the-five-markets) ·
[rounds arm](#the-rounds-arm--does-more-trading-time-fix-the-buyer-side) ·
[conclusions](#conclusions) · [reproducing](#reproducing) · [traps](#traps-that-have-bitten-here)

## The design

### What is being replicated

Plott & Sunder (1982), *"Efficiency of Experimental Security Markets with Insider
Information"*, JPE 90(4). Human subjects trade a one-period asset whose dividend depends on
both the trader's *type* and an unknown *state*. In some periods a subset of traders is told
the state. The question is whether the price comes to reflect what only those insiders know —
the **rational expectations (RE)** prediction — or only what the market as a whole knew before
trading — the **prior information (PI)** prediction.

Here the subjects are LLM agents. Everything else — the parameters, the information design,
the sequence of periods — is the paper's.

### The asset and the agents

Each market seats 9 or 12 agents, split evenly into three types. Types differ *only* in what
the certificate pays them:

| market | seats | types × n | insiders per type | states | prior (bingo balls) | periods | supply |
|---:|---:|---|---:|---|---|---:|---:|
| 1 | 9 | 3 × 3 | 1 | X, Y | 10/30, 20/30 | 11 | 18 |
| 2 | 12 | 3 × 4 | 2 | X, Y | 10/30, 20/30 | 11 | 24 |
| 3 | 12 | 3 × 4 | 2 | X, Y | 16/40, 24/40 | 12 | 24 |
| 4 | 12 | 3 × 4 | 2 | X, Y | 16/40, 24/40 | 14 | 24 |
| 5 | 12 | 3 × 4 | 2 | X, Y, Z | 7/20, 5/20, 8/20 | 13 | 24 |

Dividends in francs, by type × state:

| market | type I | type II | type III |
|---:|---|---|---|
| 1 | X 150, Y 350 | X 250, Y 300 | X 300, Y 100 |
| 2 | X 100, Y 350 | X 200, Y 300 | X 240, Y 175 |
| 3 | X 400, Y 100 | X 300, Y 150 | X 125, Y 175 |
| 4 | X 375, Y 100 | X 275, Y 150 | X 100, Y 175 |
| 5 | X 120, Y 170, Z 320 | X 155, Y 245, Z 135 | X 180, Y 100, Z 160 |

Every period is financially independent and starts from the same endowment: **2 certificates
and 10,000 francs**, with a **10,000 franc fixed cost** deducted at period end, so a period's
profit is `cash + dividends − 10,000`. Holdings, cash and the visible market log all reset at
the period boundary; only each agent's own history and written notes carry across.

### The information structure

The prior is a **bingo cage** — a physical mechanism with a whole number of balls — not a
stated probability. This is load-bearing rather than decorative: it is why every market's
prior has to be expressible in whole balls, and why market 1's imperfect clue is described as
two boxes of chips instead of a likelihood.

Each period is one of three information conditions, fixed by the market's sequence:

- **`none`** — nobody is told anything. Whether the period is *announced* as uninformative is
  itself a per-market treatment (`announce_no_info`: on in markets 1, 2 and 5; off in 3 and 4).
- **`insider`** — a subset gets a clue card. In markets 2–5 the card names the state exactly,
  so an insider's posterior is degenerate. In **market 1** it is a **ten-draw 0/1 sample** from
  one of two urns (urn X draws 0 with 4/5, urn Y with 3/5), so market 1's insiders hold
  *evidence*, not the answer — which is why market 1 is the one market where full aggregation
  is not predicted, and why its prediction is identified by the period rather than by the state.
- **`all`** — everyone gets the card. RE and PI then coincide by construction.

### The trading institution

    period
      └─ round 1..N        all seats, in a fresh random order each round
           └─ turn         one seat, one model call
                ├─ BRIEF          rendered and logged verbatim — the exact bytes the model saw
                ├─ DECIDE         no_quote | quote(side, price) | accept_standing(side)
                └─ if quote:
                     ├─ VALIDATE  budget / inventory, then the price-improvement rule
                     ├─ CROSS     a crossing quote trades immediately at the STANDING price
                     └─ BROADCAST poll every feasible counterparty in parallel
                          ├─ ≥1 accept → trade; ties broken at random; the quote never books
                          └─ 0 accept  → the quote becomes the standing quote on its side
      └─ settle            dividends paid on the realized state, fixed cost deducted
      └─ reflect           every agent writes ~100 words before the next period

A round ends when all seats have had one turn. **A period stops early if an entire round
passes with no market action** — in market 4 this has never fired, so a session set to N
rounds runs N. Agents are told the current round number but **never the total**, so they
cannot pace themselves to the budget.

The **price-improvement rule** (on in every run reported here) means a new bid must beat the
standing bid and a new ask must undercut the standing ask; an empty slot accepts any price,
and improving your own quote is allowed. Rejected attempts are recorded as violations rather
than discarded — `no_improvement`, `no_inventory`, `budget`, `empty_note` are **data, not
errors**, and are how a blocked intention stays visible.

**Why broadcast instead of a continuous order book.** When a quote is made, every agent who
could feasibly take it is asked, and the log records *all* their answers — not just the one
who won the random tie-break. Aggregating acceptances by price recovers the latent demand and
supply schedules. In an oral auction the losers never speak, so this is data a human
experiment structurally cannot produce. Agents who accepted but were not drawn are told they
missed out; what stays hidden is *how many* others accepted.

### Three prompt constraints

Guarded for every (market, seat) pair in `tests/test_prompts.py`:

1. **The word "probability" never appears.** The paper trained subjects on the bingo cage as a
   mechanism, so the replication does too.
2. **Nothing is disclosed** about how many types exist, what others' dividends are, whether
   insiders are the same people each period, or how likely a state is. Market size is stated;
   type structure is not. This is the baseline: `Rules.disclose_structure` is the one
   deliberate, flag-gated treatment exception (`docs/disclosure-treatment.md`), and even it
   never discloses identities, fixedness or the schedule of card years.
3. **Common knowledge is per-market.** The paper notes subjects could deduce "in all but
   market 1" that dividends stay constant across periods, so market 1's agents are not told.

`THEORY_*` values must never reach a prompt.

### Theory is derived, not transcribed

`Market.theory_price()` and `theory_holder()` compute RE and PI from the dividends and the
prior. They condition on the **clue**, not on the realized state — for markets 2–5 a lettered
clue makes the two coincide, but market 1's ten-draw sample does not, and reading its RE off
the state inverts the prediction. `TABLE_3` pins markets 2–5 against the paper; `FOOTNOTE_6`
pins which periods separate in all five and that they total 17, the only published check on
market 1.

### Two arms per market

- **`paper_exact`** — Table 1's own state and information sequence, verbatim.
- **`random_draw`** — the states redrawn from that market's own prior, with the information
  schedule kept. A redrawn run can land on Table 1's state for a period while holding a
  different market-1 sample, which is why anything scoring a period must pass the realized
  card rather than infer it from the period number.

Two `paper` and three `random` sessions per market.

### Configuration used in every run reported here

| | |
|---|---|
| model | `deepseek-v4-flash` (Bailian), `temperature: 0.7`, thinking **on** in all three channels |
| token budgets | 8,192 turn / 8,192 broadcast / 3,000 reflect |
| `broadcast_workers` | 12 (2 for the Gemini session) |
| rules | `price_improvement: true`, `elicit_beliefs: true`, `broadcast_reason: true`, `market_log_window: 0` (whole period), `period_end_notes: 2`, `trade_notes: 3`, `not_selected_window: 5` |

Thinking is not optional. With it off, this class of model answered a bingo-cage expected
value of 150 instead of 220 after four output tokens, and 67% of broadcast replies cited the
wrong expected value.

Concurrency is bounded **structurally**: a session drives its phases on one thread, so at most
`broadcast_workers` of its requests are in flight at any instant and `sessions × W` is a
mathematical ceiling rather than a statistical hope. Measured mean is ~1.9 per session.

### What each measure means

    discovery = (mean price − uninformed level) / (RE − uninformed level)
        1.0 = price is at RE          0.0 = price is where the uninformed alone would put it
    E   = value(actual allocation) / value(RE allocation)
    TE  = [value(actual) − value(no trade)] / [value(RE) − value(no trade)]

`E` and `TE` are conditioned on the information in the market: the realized state when someone
is informed, the prior when nobody is. `TE` exists because `E` is nonzero even when no trading
happens at all.

## Where the data is

    runs/<group>/<run_name>/<stamp>.jsonl              the log — the only interface to analysis
                            <stamp>.meta.json          scenario, status, sequence, totals
                            <stamp>.metrics.json       metrics.compute() output, written at session end
                            <stamp>.checkpoint.json    per-period resume state

**`runs/` is not in git** (1.5 GB+, `.gitignore` line 2). The logs live only on the machine
that produced them and on the GPU/cloud box they were run on. `docs/` and `scenarios/` are
tracked, so a run is reproducible from this repo even when its log is not present.

`status` in `meta.json` is `done` only after `session_end` is written. A `running` status on
a run whose process is gone means it was interrupted; `./resume_batch.sh` continues from the
last settled period.

| group | what it holds |
|---|---|
| `runs/m1/` … `runs/m5/` | **The main result.** Five sessions per market — two on Table 1's own sequence (`_paper_*`), three on redraws from that market's prior (`_random_*`). `m3/` has a sixth, `m3_gem_paper`, seed-paired with `m3_paper_0` on a different vendor. |
| `runs/rounds/` | **The rounds arm.** Six market-4 sessions at 4, 5 and 6 rounds per period. |
| `runs/m3_local/` | Two market-3 sessions run on DeepSeek's own API before the batch. Same engine, different endpoint. |
| `runs/baselines/` | Scripted agents (`scripted_re`, `scripted_pi`, `scripted_zi`) and the `smoke` shakedown. No model calls except `smoke`. |
| `runs/probes/` | Vendor and throughput shakedowns, one period each. Not experiments. `load25_20sess/` is the 20-session concurrency probe that preceded the batch and has no `meta.json`. |

## Inventory

Model is `deepseek-v4-flash` on Alibaba Bailian unless noted. `W` is `broadcast_workers`.

### Main result — 26 sessions, 88,122 calls, $66.56

| run | dir | market | scenario | periods | rd | W | calls | $ | h |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|
| m1_paper_0 | `runs/m1/m1_paper_0` | 1 | `scenarios/m1_paper.yaml` | 11 | 3 | 12 | 1,738 | 1.04 | 3.42 |
| m1_paper_1 | `runs/m1/m1_paper_1` | 1 | `scenarios/m1_paper.yaml` | 11 | 3 | 12 | 1,813 | 1.18 | 4.09 |
| m1_random_0 | `runs/m1/m1_random_0` | 1 | `scenarios/m1_random.yaml` | 11 | 3 | 12 | 1,745 | 1.14 | 4.02 |
| m1_random_1 | `runs/m1/m1_random_1` | 1 | `scenarios/m1_random.yaml` | 11 | 3 | 12 | 1,836 | 1.15 | 3.75 |
| m1_random_2 | `runs/m1/m1_random_2` | 1 | `scenarios/m1_random.yaml` | 11 | 3 | 12 | 1,834 | 1.14 | 3.84 |
| m2_paper_0 | `runs/m2/m2_paper_0` | 2 | `scenarios/m2_paper.yaml` | 11 | 3 | 12 | 3,129 | 1.75 | 5.48 |
| m2_paper_1 | `runs/m2/m2_paper_1` | 2 | `scenarios/m2_paper.yaml` | 11 | 3 | 12 | 3,215 | 1.83 | 5.84 |
| m2_random_0 | `runs/m2/m2_random_0` | 2 | `scenarios/m2_random.yaml` | 11 | 3 | 12 | 3,123 | 1.69 | 5.30 |
| m2_random_1 | `runs/m2/m2_random_1` | 2 | `scenarios/m2_random.yaml` | 11 | 3 | 12 | 3,061 | 1.59 | 4.85 |
| m2_random_2 | `runs/m2/m2_random_2` | 2 | `scenarios/m2_random.yaml` | 11 | 3 | 12 | 3,121 | 1.73 | 5.60 |
| m3_paper_0 | `runs/m3/m3_paper_0` | 3 | `scenarios/bailian_paper.yaml` | 12 | 3 | 12 | 3,498 | 1.89 | 5.58 |
| m3_paper_1 | `runs/m3/m3_paper_1` | 3 | `scenarios/bailian_paper.yaml` | 12 | 3 | 12 | 3,882 | 2.09 | 5.58 |
| m3_random_0 | `runs/m3/m3_random_0` | 3 | `scenarios/bailian_random.yaml` | 12 | 3 | 12 | 3,604 | 1.88 | 5.43 |
| m3_random_1 | `runs/m3/m3_random_1` | 3 | `scenarios/bailian_random.yaml` | 12 | 3 | 12 | 3,967 | 2.12 | 5.65 |
| m3_random_2 | `runs/m3/m3_random_2` | 3 | `scenarios/bailian_random.yaml` | 12 | 3 | 12 | 3,726 | 2.07 | 5.92 |
| m3_gem_paper | `runs/m3/m3_gem_paper` | 3 | `scenarios/gemini_paper.yaml` | 12 | 3 | **2** | 4,132 | **18.95** | 1.54 |
| m4_paper_0 | `runs/m4/m4_paper_0` | 4 | `scenarios/m4_paper.yaml` | 14 | 3 | 12 | 4,250 | 2.44 | 7.87 |
| m4_paper_1 | `runs/m4/m4_paper_1` | 4 | `scenarios/m4_paper.yaml` | 14 | 3 | 12 | 3,993 | 2.28 | 7.68 |
| m4_random_0 | `runs/m4/m4_random_0` | 4 | `scenarios/m4_random.yaml` | 14 | 3 | 12 | 4,322 | 2.50 | 7.98 |
| m4_random_1 | `runs/m4/m4_random_1` | 4 | `scenarios/m4_random.yaml` | 14 | 3 | 12 | 4,407 | 2.52 | 7.52 |
| m4_random_2 | `runs/m4/m4_random_2` | 4 | `scenarios/m4_random.yaml` | 14 | 3 | 12 | 4,069 | 2.36 | 7.71 |
| m5_paper_0 | `runs/m5/m5_paper_0` | 5 | `scenarios/m5_paper.yaml` | 13 | 3 | 12 | 3,867 | 2.26 | 7.47 |
| m5_paper_1 | `runs/m5/m5_paper_1` | 5 | `scenarios/m5_paper.yaml` | 13 | 3 | 12 | 3,868 | 2.21 | 6.96 |
| m5_random_0 | `runs/m5/m5_random_0` | 5 | `scenarios/m5_random.yaml` | 13 | 3 | 12 | 3,974 | 2.26 | 6.99 |
| m5_random_1 | `runs/m5/m5_random_1` | 5 | `scenarios/m5_random.yaml` | 13 | 3 | 12 | 3,965 | 2.18 | 6.69 |
| m5_random_2 | `runs/m5/m5_random_2` | 5 | `scenarios/m5_random.yaml` | 13 | 3 | 12 | 3,983 | 2.30 | 7.44 |

`m3_gem_paper` is `gemini-3.5-flash` on Vertex. It is 28% of the whole bill for 4% of the
sessions, and ran at W=2 because Vertex serves Gemini from a dynamic shared quota — W=12
there produced 54 retries in 75 calls and 5 corrupted turns.

The market-3 logs record no `market` field in `config` (they predate it). `metrics._market_for`
defaults those to market 3, which is a fact about when they were written rather than a guess.

### Rounds arm — 6 sessions, 35,284 calls, $21.93

Each reuses the seed of a 3-round session already reported, so the 3/4/5/6 gradient runs on
two fixed sequences and rounds per period is the only thing that varies.

| run | dir | scenario | seed source | rd | calls | $ | h |
|---|---|---|---|---:|---:|---:|---:|
| m4_r4_paper | `runs/rounds/m4_r4_paper` | `scenarios/m4_paper_r4.yaml` | `m4_paper_0` | 4 | 4,967 | 3.09 | 9.91 |
| m4_r4_random | `runs/rounds/m4_r4_random` | `scenarios/m4_random_r4.yaml` | `m4_random_0` | 4 | 5,752 | 3.32 | 8.90 |
| m4_r5_paper | `runs/rounds/m4_r5_paper` | `scenarios/m4_paper_r5.yaml` | `m4_paper_0` | 5 | 5,990 | 3.76 | 11.92 |
| m4_r5_random | `runs/rounds/m4_r5_random` | `scenarios/m4_random_r5.yaml` | `m4_random_0` | 5 | 6,468 | 3.95 | 11.34 |
| m4_r6_paper | `runs/rounds/m4_r6_paper` | `scenarios/m4_paper_r6.yaml` | `m4_paper_0` | 6 | 6,221 | 4.04 | 13.24 |
| m4_r6_random | `runs/rounds/m4_r6_random` | `scenarios/m4_random_r6.yaml` | `m4_random_0` | 6 | 5,886 | 3.77 | 13.02 |

Each `m4_*_r{4,5,6}.yaml` differs from `scenarios/m4_{paper,random}.yaml` in exactly one
line, `max_rounds_per_period`. Same model, same three thinking budgets, same W=12, same
rules. Run with `./run_rounds_arm.sh`; the plan is `./.venv/bin/python batch_plan.py --rounds-arm`.

### Supporting runs

| run | dir | note |
|---|---|---|
| m3_local/paper, m3_local/random | `runs/m3_local/` | market 3 on DeepSeek's own API, 3,947 / 4,029 calls |
| scripted_re, scripted_pi, scripted_zi | `runs/baselines/` | algorithmic agents, no model calls — the reference the LLM runs are read against |
| smoke | `runs/baselines/smoke` | 1 period, 221 calls |
| bailian_check, gemini_check, gemini_probe, probe | `runs/probes/` | vendor shakedowns |
| gemini_tiers | `runs/probes/gemini_tiers` | ran a **willingness-tier** feature that no longer exists. Its scenario was deliberately not copied back in: `AgentSpec` silently drops unknown fields, so the file would load without error and run a plain session with no tiers. |
| load25_20sess | `runs/probes/load25_20sess` | the 20-session concurrency probe. No `meta.json`. It caught `broadcast_max_output_tokens: 512` truncating 29% of broadcasts to empty before the real batch ran. |

## Main result — the five markets

26 sessions. Recomputed from the logs.

### Prices against the two models, separating periods only

Separating = the periods where RE ≠ PI, which is the only place the paper scores prices.
Two different things are reported because they answer different questions: the mean price
against the mean prediction says where the market settles on average; the mean of the
per-period absolute distance says how tightly.

| market | sessions | sep. periods | mean price | RE | PI | mean \|p−RE\| | mean \|p−PI\| |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 5 | 8 | 273.1 | 267 | 283 | 12.1 | **9.9** |
| 2 | 5 | 8 | 236.4 | 240 | 267 | **43.2** | 49.9 |
| 3 | 6 | 30 | 172.4 | 175 | 220 | **12.8** | 48.0 |
| 4 | 5 | 26 | 164.9 | 175 | 210 | **19.3** | 45.1 |
| 5 | 5 | 17 | 179.7 | 180 | 212 | **9.6** | 32.3 |

Markets 2–5 land on RE rather than PI. Market 1 sits slightly closer to PI period by period
(9.9 against 12.1) — which is the paper's own exception: its insiders get a ten-draw 0/1
sample instead of a letter, so their posterior is not degenerate and full aggregation is not
predicted. Market 2 reaches RE in the mean (236.4 against 240) but scatters widely around
it (43.2 per period).

### Efficiency and volume

| market | E% | TE% | trades/period |
|---:|---:|---:|---:|
| 1 | 92.2 | 67.4 | 11.2 |
| 2 | 95.1 | 79.4 | 16.9 |
| 3 | 91.2 | 58.0 | 19.2 |
| 4 | 91.2 | 55.1 | 19.1 |
| 5 | 91.2 | 59.0 | 19.6 |

### The identity

In an insider period PI = max(informed value, uninformed level). So

> RE ≠ PI  ⟺  RE < the uninformed level  ⟺  the informed profit by **selling**

This is an algebraic consequence of the design, not an empirical claim, and it means the
paper's separating periods and the periods where insiders are sellers are the *same set*.
Checked on every insider period with something to discover:

| market | holds |
|---:|---|
| 1 | 20/20 |
| 2 | 25/25 |
| 3 | 48/48 |
| 4 | 45/45 |
| 5 | 50/50 |
| **all** | **188/188, no exceptions** |

The consequence is that the paper's own yardstick can only ever see the seller side. The 99
buyer-side periods are exactly the ones it drops.

### Price discovery by informed side

    discovery = (mean price − uninformed level) / (RE − uninformed level)
    1.0 = price is at RE     0.0 = price is where the uninformed alone would put it

| market | buyer n | buyer disc | buyer francs moved | seller n | seller disc | seller francs moved |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 12 | −0.56 | −9.3 | 8 | 0.78 | −10.2 |
| 2 | 17 | 0.25 | +20.9 | 8 | 1.13 | −30.3 |
| 3 | 18 | 0.06 | +11.7 | 30 | 1.06 | −47.6 |
| 4 | 19 | 0.11 | +18.5 | 26 | 1.29 | −45.1 |
| 5 | 33 | −0.30 | −11.4 | 17 | 1.01 | −32.8 |
| **all** | **99** | **−0.09** | **+4.3** | **89** | **+1.10** | **−39.1** |

Every market's seller side reaches RE (0.78–1.29). No market's buyer side does; markets 1
and 5 move the price the *wrong way*.

**Read the francs column, not only the ratio.** The two sides do not have equally distant
targets — in market 4 the buyer side must travel +165 francs and the seller side only −35 —
so the ratio flatters the seller side. See "the normalisation caveat" below.

## The rounds arm — does more trading time fix the buyer side?

Market 4, 3/4/5/6 rounds per period, on two fixed sequences. Eleven sessions: the six new
ones plus the five 3-round market-4 sessions from the main result.

In market 4 the sides are cleanly separated by the realized state:

| | state | RE | PI | uninformed level | distance | separating? |
|---|---|---:|---:|---:|---:|---|
| **seller side** | Y | 175 (type III) | 210 | 210 | −35 | yes |
| **buyer side** | X | 375 (type I) | 375 | 210 | +165 | no |

### Design integrity (checked before anything was read)

- **No early stopping.** Every one of the eleven sessions ran its full round cap in all 14
  periods. The "stop early if a whole round passed with no action" rule never fired, so the
  extra rounds were actually delivered.
- **Pairing is exact.** All six new sessions match their seed-paired 3-round original on the
  full 14-period state *and* info sequence.
- **The cap is never disclosed to agents, so pacing is ruled out.** `prompts/brief.py` tells a
  seat the current round number and never the total — no string in `ps1982/prompts/` mentions
  a round count — so agents cannot pace themselves to the budget, and "6 rounds" is genuinely
  extra time rather than a different announced game. Round 1 is therefore identical in
  construction across all four caps, which makes round-1 outcomes across caps a free
  measurement of pure session-to-session noise.
- **Power is low by construction.** Two seeds × four caps, n=1 per cell. This is a paired
  descriptive gradient, not a design that supports a significance test on the cap. The three
  extra 3-round sessions measure the noise floor the gradient has to beat.

### Hygiene

| cap | sessions | turns | empty completions | api_error | parse errors | retries | violations / 1k turns |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 5 | 21,041 | 71 (0.34%) | 0 | 0 | 0 | 28.2 |
| 4 | 2 | 10,719 | 32 (0.30%) | 0 | 0 | 0 | 23.8 |
| 5 | 2 | 12,458 | 41 (0.33%) | 0 | 0 | 0 | 24.4 |
| 6 | 2 | 12,107 | 52 (0.43%) | 0 | 0 | 0 | 27.8 |

Dividend settlement: **1,848 / 1,848** seat-periods equal `dividend(type, state) × certs`
exactly. Violation rate does not rise with the cap, so the extra rounds are not decaying into
rejected attempts.

### A — rounds do not move prices

Session-level discovery, period mean price:

| arm | 3 rd | 4 rd | 5 rd | 6 rd |
|---|---:|---:|---:|---:|
| paper, buyer | 0.23 | −0.15 | 0.13 | 0.12 |
| random, buyer | −0.09 | 0.03 | 0.18 | 0.17 |
| paper, seller | 1.17 | 1.39 | 1.52 | 1.12 |
| random, seller | 1.46 | **−0.37** | 0.94 | 1.15 |

Noise floor from the five 3-round sessions, which differ only by seed: buyer mean 0.10,
**sd 0.12**; seller mean 1.28, sd 0.29. Round-1 discovery across the four caps of one seed —
four independent draws, since the cap cannot be known in round 1 — spans 0.24 / −0.10 / 0.06
/ 0.10 on the paper arm. **The entire gradient sits inside the noise.**

`m4_r4_random`'s seller side is the one broken session of the eight: in period 7 the price
rose from 150 to 301 against RE = 175 (period mean 292). With n=1 per cell it drags the whole
cap-4 row. Worth a separate look; it is not a rounds effect.

### B — the buyer side does find the price, just after everyone has stopped trading

Discovery of the trades occurring **in** round *k*, and volume in that round (cap 6):

| | r1 | r2 | r3 | r4 | r5 | r6 |
|---|---:|---:|---:|---:|---:|---:|
| buyer discovery in round | 0.09 | 0.18 | 0.10 | **0.44** | **0.48** | **0.45** |
| buyer trades in round | 9.29 | 6.86 | 3.00 | **0.43** | 1.71 | 1.14 |
| seller discovery in round | 0.95 | 1.02 | 1.02 | 1.19 | 1.21 | 1.22 |
| seller trades in round | 8.00 | 6.64 | 3.64 | 2.82 | 2.91 | 3.27 |

Cumulative discovery through round *k* — where the market has actually got to:

| cap | r1 | r2 | r3 | r4 | r5 | r6 |
|---:|---:|---:|---:|---:|---:|---:|
| buyer, 3 | 0.10 | 0.10 | 0.11 | | | |
| buyer, 5 | 0.06 | 0.09 | 0.11 | 0.12 | 0.15 | |
| buyer, 6 | 0.09 | 0.13 | 0.10 | 0.10 | 0.13 | **0.14** |
| seller, 6 | **0.95** | 0.98 | 1.02 | 1.06 | 1.10 | 1.13 |

The seller side is essentially finished in round 1. The buyer side's late trades *are*
informed — 0.44–0.48 against 0.06–0.18 early — but almost no volume transacts there, so the
cumulative price stays at 0.14. **The information reaches the price only after the allocation
has already happened at the uninformed level.**

### D — weak learning across periods, in both directions

Buyer-side discovery by the order of buyer periods within a session (cap 6): −0.02, 0.17,
0.13, 0.43. First to last same-side period, over all eleven sessions:

| side | first | last | delta | improved |
|---|---:|---:|---:|---:|
| buyer (discovery) | — | — | **+0.23** | **10/11** |
| seller (discovery) | — | — | −0.10 | 4/11 |
| buyer, as \|disc − 1\| | 1.02 | 0.79 | −0.23 | 10/11 |
| seller, as \|disc − 1\| | 1.00 | 0.31 | −0.69 | 9/11 |

`|disc − 1|` is the fairer seller measure, because seller discovery above 1 is *overshoot*
past RE, not better aggregation. On that measure both sides improve across a session.

The improvement is a noisy drift, not a clean curve: step by step, only 17/29 consecutive
buyer periods rise (59%, barely above chance), and the endpoint is still ≈ 0.45, far from
1.0. Ten of eleven sessions improving first-to-last is a sign test at p ≈ 0.01.

### E — they know the value; they simply do not bid it

Informed agents' stated reservation price against their own dividend in the realized state:

| side | n views | median error | p90 | exact | mean (outlier-inflated) |
|---|---:|---:|---:|---:|---:|
| seller | 2,912 | **0 f** | 1 f | 57.8% | 5.7 |
| buyer | 1,941 | **0 f** | 1 f | 59.6% | 19.4 |

Knowledge is not the constraint. Where the money goes (cap 6):

| side | RE | informed reservation | trade price | uninformed reservation |
|---|---:|---:|---:|---:|
| buyer | 375 | 248.7 | **240.4** | 204.0 |
| seller | 175 | 146.8 | **170.2** | 483.4 |

Informed agents quote rather than accept in 99.6–100% of their actions on both sides, and the
uninformed in 91.5–99%, so this is not a liquidity-provision difference either. Insider profit
edge over the uninformed, in francs:

| cap | buyer side | seller side |
|---:|---:|---:|
| 3 | +339.9 | +107.3 |
| 4 | +407.6 | +234.8 |
| 5 | +344.9 | +113.6 |
| 6 | +391.7 | +131.3 |
| **pooled** | **+361.7** | **+136.7** |

The informed earn **2.65× more on the buyer side** — precisely where prices reveal least — and
the edge does not erode with more rounds. Per cap the ratio is 3.17 / 1.74 / 3.04 / 2.98; the
low cell is cap 4, dragged by the one broken session. This is the asymmetry hypothesis's own
prediction: an informed buyer keeps their surplus by *not* moving the price, and an informed
seller cannot sell without moving it.

### F — rounds buy allocation, not prices

| | 3 rd | 4 rd | 5 rd | 6 rd |
|---|---:|---:|---:|---:|
| buyer discovery | 0.10 | −0.06 | 0.15 | 0.14 |
| buyer RE-holder share | 60.6% | 57.6% | 69.1% | **74.7%** |
| buyer TE | 69.1 | 63.7 | 75.2 | **79.5** |
| seller TE | 38.6 | 0.0 | 48.0 | 40.9 |
| E (all periods) | 91.2 | 88.5 | 92.6 | 92.7 |
| trades per period | 19.1 | 22.2 | 26.9 | **28.5** |

A clean duality: **the buyer side gets prices wrong and the allocation right (TE 80%); the
seller side gets prices right and the allocation wrong (TE 41%).** More rounds improve the
buyer side's allocation and volume while leaving its price untouched.

### The normalisation caveat

The buyer side must move the price +165 francs and the seller side only −35. In francs:

| | mean move | required | ratio (= discovery) |
|---|---:|---:|---:|
| seller (59 periods) | **−37.9 f** | −35 | 1.13 |
| buyer (40 periods) | **+14.9 f** | +165 | 0.09 |
| mean \|move\| | 43.1 vs **34.9** | | |

Both sides push the price by a similar *absolute* amount. The seller side "fully aggregates"
in large part because its target is 4.7× closer. The directional gap is real — −37.9 against
+14.9, and the buyer side is noisier (sd 42.4 against 28.1) — but it is roughly **2.5×, not
the 11× the discovery ratio suggests**. Any statement of the asymmetry should quote francs
alongside the ratio.

## Conclusions

1. Markets 2–5 reach RE; market 1 does not, which is the paper's own exception and follows
   from its imperfect clue.
2. RE ≠ PI ⟺ the informed are sellers, on all 188 insider periods. The paper's yardstick can
   only see the seller side.
3. The seller side aggregates and the buyer side does not — but by ~2.5× in francs, not the
   ~11× the normalised measure implies.
4. Doubling trading time from 3 to 6 rounds does not move buyer-side prices at all. The whole
   gradient lies within the seed-to-seed noise floor.
5. It does move certificates: RE-holder share 61% → 75%, buyer TE 69 → 80, volume +49%.
   **More time lets the right people buy more at the wrong price.**
6. The failure is not informational. Informed agents state their exact private value ~60% of
   the time and within 1 franc at p90, and earn 2.6–3.2× more on the side where the price
   moves least.

## Reproducing

    ./.venv/bin/python -m ps1982 run -s scenarios/m4_paper_r6.yaml --run-name rounds/m4_r6_paper --seed 20250755
    ./.venv/bin/python -m ps1982 metrics -r runs/rounds/m4_r6_paper/<stamp>.jsonl
    ./.venv/bin/python batch_plan.py --show          # the 26-session plan
    ./.venv/bin/python batch_plan.py --rounds-arm    # the 6-session rounds arm
    cd web && npm start                              # viewer, scans runs/ recursively

`make gate` is the engine-correctness gate; run it before spending on API. `make validate`
renders one seat's prompts with no API calls.

## Traps that have bitten here

- **`AgentSpec` silently drops unknown YAML fields.** A scenario using a removed feature loads
  without error and runs something else entirely (see `gemini_tiers` above).
- **A cap that is not sent is not a cap.** `broadcast_max_output_tokens` was dead config for
  the project's whole life; when the argument finally reached the provider, the scenarios'
  512 truncated 29% of broadcasts to empty. All runs listed here use 8192, the value the
  completed market-3 sessions had actually been running under.
- **`model_turn.payload.error` carries two different things.** An API failure means the model
  never answered — contamination. Unparseable JSON means it answered and the answer was
  malformed — model behaviour, and part of the result.
- **The market-1 logs in `runs/m1/` carry a wrong theory table and the viewer discards it.**
  They were written before the engine keyed that table by period, and market 1's prediction
  depends on the ten-draw sample the period drew. `metrics.py` never reads that table — it
  recomputes from the market number and the realized cards — so every number here is correct.
- **Violations are data, not errors.** `no_improvement`, `no_inventory` and `empty_note` are
  recorded and expected at low rates.
