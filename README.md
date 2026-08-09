# Plott & Sunder (1982) — an LLM-agent replication

**English** · [中文](README.zh-CN.md)

A replication of all **five markets** in Plott & Sunder, *"Efficiency of Experimental
Security Markets with Insider Information: An Application of Rational-Expectations
Models"*, JPE 90(4), with LLM agents in place of human subjects.

In each market, 9 or 12 agents trade single-period certificates over 11–14 "market years".
A bingo cage decides at the start of each year which dividend will be paid, and some agents
receive a clue card. The question is whether prices and holdings settle on the
**rational-expectations (RE)** equilibrium rather than the **prior-information (PI)** one —
that is, whether uninformed agents can read the state off the price.

Two pieces:

- **Python** (`ps1982/`) runs the market and the model calls, writing one append-only JSONL
  event stream per run.
- **Node.js** (`web/`) reads those logs and serves a bilingual (中/EN) replay viewer and
  metrics dashboard.

Three model endpoints are supported: DeepSeek's own API, Alibaba Bailian (same weights,
roughly half the price, OpenAI-compatible), and Gemini on Google Vertex AI. Switching
vendor is one line in a scenario file.

---

## Quick start

```bash
python3 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
cd web && npm install && cd ..
cp .env.example .env          # add your own keys

# 1. free — check parameters and rendered prompts
./.venv/bin/python -m ps1982 validate -s scenarios/m3_paper.yaml

# 2. free — 550 offline tests
./.venv/bin/pytest

# 3. free — the engine correctness gate (see below); run this first
make gate

# 4. real API, ~11 min, ~$0.07 — connectivity, JSON stability, token accounting
./.venv/bin/python -m ps1982 run -s scenarios/smoke.yaml

# 5. the experiment
./.venv/bin/python -m ps1982 run -s scenarios/m3_paper.yaml

# 6. the viewer
cd web && npm start           # http://127.0.0.1:8100
```

`make setup / test / gate / smoke / run / metrics / web` wrap the same commands.

---

## The five markets, plus three controls and four baselines

The paper's five are five **treatments, not five repetitions** — roster size, prior, number of states,
information precision and period count all differ.

| Market | Periods | Agents | States | Prior | Information design | What makes it different |
|---:|---:|---:|---|---|---|---|
| 1 | 11 | **9** | X/Y | 1/3 | 1-4 none · 5-8 insider · 9-11 all | **Imperfect information**: the clue is a ten-draw 0/1 sample, not a letter; one insider per type |
| 2 | 11 | 12 | X/Y | 1/3 | 1-4 none · 5-6 all · 7-11 insider | Everyone is informed *before* the insider periods — the reverse of market 3 |
| 3 | 12 | 12 | X/Y | .4 | 1-2 none · 3-10 insider · 11-12 all | The paper's most-analysed market, and where this codebase started |
| 4 | 14 | 12 | X/Y | .4 | 1-4 none · 5-13 insider · **14 none** | The only market with a no-information period at the **end** as well as the start |
| 5 | 13 | 12 | **X/Y/Z** | .35/.25/.40 | 1-3 none · 4-13 insider | **Three states** |
| 6 | 12 | 12 | X/Y | **.6** | 1-2 none · 3-10 insider · 11-12 all | **Not the paper's.** The equidistant control: both informed-trade directions are 80 francs from the uninformed level |
| 7 | 14 | 12 | X/Y | **.6** | market 4's | **Not the paper's.** Equidistant at ±100 **and** equal-width: a competitive price occupies 0.300 of the discovery scale on each side |
| 8 | 14 | 12 | X/Y | **.6** | market 4's | **Not the paper's.** Market 7 with the three types' **roles separated** — one sets the uninformed level, one tops each state. 0.200 on each side |
| 92–95 | base's | 12 | base's | base's | the base market's, **stopped** after period 8 / 5 / 7 / 6 | **Not the paper's, and not designs.** Market 2, 3, 4 or 5 run unchanged to a stated period and uninformed after it, to measure where price rests against v̄ at the indices the insider periods occupy |

A third group, `STOPPED_MARKETS = (92, 93, 94, 95)`, is not a design at all. Each runs its
base market — the units digit names it — unchanged through a stated period and then
transmits nothing, so its uninformed tail measures where price rests against v̄ at the
indices that market's insider periods occupy. That level is not a detail: discovery divides
by (re − v̄), which on the published selling side is −26.7 to −45 francs, so the 32.5-franc
sag measured at market 4's period 14 is a correction of about 1.0 to a selling-side D —
the same size as the result it corrects. Markets 2, 3 and 5 have no mature no-information
period at all; market 4 has one, and its variant is there to validate the design rather
than to fill a gap. See [`docs/markets-92-95-stopped.md`](docs/markets-92-95-stopped.md).

Every parameter's provenance is in [`docs/markets-1-to-5.md`](docs/markets-1-to-5.md),
market 6's in [`docs/market-6-control.md`](docs/market-6-control.md), markets 7 and 8's
in [`docs/markets-7-8-equal-width.md`](docs/markets-7-8-equal-width.md), and markets 92–95's
in [`docs/markets-92-95-stopped.md`](docs/markets-92-95-stopped.md).
`ps1982/markets.py` is that document as executable data, and `tests/test_markets.py` checks
it back against the paper's Table 1, Table 2, Table 3 and footnote 5, cell by cell.
`PAPER_MARKETS`, `CONTROL_MARKETS` and `STOPPED_MARKETS` keep the three provenances apart,
so a guard asserting something Plott & Sunder did can never be satisfied by a market they
never ran.

### Why three controls and not one

Price discovery is measured as `D = (price − v̄) / (re − v̄)`, the share of the distance from
the uninformed level to the rational-expectations price that the price actually travelled.
Three separate things make that number mean different things on the buy and the sell side,
and the published family has all three.

1. **The distance differs.** Market 4 asks the buy side for +165 francs and the sell side
   for −35, so the same franc of movement scores five times higher on the sell side.
   **Market 6** equalises it at 80 each way.
2. **The target is a range, not a point.** With 24 certificates and four agents of the top
   type, any price between the second-highest and the highest informed valuation supports
   the competitive allocation — so a *merely competitive* price already occupies a band of
   D. In market 6 that band is 0.875 wide on the buy side and 0.125 on the sell side, the
   most lopsided in the family. **Markets 7 and 8** make it equal: 0.300 and 0.200 each way.
3. **The informed do not always agree.** A "buy state" only means `re > v̄`, and re is the
   *top* type's valuation. In markets 3 and 4 two of six insiders want to **sell** in the
   buy state; in market 5 all three states carry net sell pressure among insiders. In
   markets 6, 7 and 8 all six insiders want the same thing in each state.

Markets 7 and 8 are identical except for **which type holds when**. Everywhere else in the
family the type that sets v̄ is also the buy-state holder, so the buy signal needs no
reallocation while the sell signal does — an asymmetry the first two fixes do not touch.
Market 8 gives each type one job, so both states demand the same reallocation.

### The free-rider identity

Building those controls turned up something that applies to the published markets too.

**On the buy side no uninformed agent can ever help.** v̄ is `max_t E[dividend_t]`, the
largest valuation any uninformed agent can hold, and a buy state is *defined* by `re > v̄`.
So no uninformed agent values a certificate above the buy-side RE price — in any market, at
any parameters. Every franc of buy-side discovery must come from someone who learned
something.

**The sell side has no such identity, and every published market has helpers**: some type's
prior expectation falls *below* the sell-side RE price, so those agents sell at it having
inferred nothing.

| | market 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---:|---:|---:|---:|---:|---:|---:|
| uninformed agents who reach the **sell** target without learning | 2/6 | 2/6 | 2/6 | **4/6** | 0 | 0 | 0 |
| the same on the **buy** side | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

So part of "informed sellers reveal, informed buyers conceal" is an accounting property of
the parameters. It is measurable: run the *scripted* RE baseline — algorithms that already
know the state — and market 3 shows a buy/sell gap of **+0.297** with no strategy involved,
while markets 7 and 8 show −0.337 and −0.509. Markets 6, 7 and 8 are the only markets in
which both directions require genuine inference, which is also why their scripted sell side
sits near zero: with no free riders the price never reaches the level a price-based
inference rule needs, so nobody learns.

The scripted rule is deliberately **not** changed for them — it is the fixed comparison
point for the completed sessions. LLM runs on these markets are read as a difference from
that measured baseline, never against 1.0.

**The theory predictions are derived, not transcribed.** `Market.theory_price()` computes
RE and PI from the dividends and the prior; the result matches every cell the paper prints
for markets 2, 3, 4 and 5. Market 1's are absent from the paper by its own choice
("information given to insiders was probabilistic. Predictions are not given here in order
to save space"), so market 1's predictions are ours — warranted by the agreement everywhere
a check exists.

### Two arms

- **`paper`** — the realized sequence Table 1 records. The seed only varies the round
  order, the tie-breaks and the seat→name mapping, so this arm **replicates one sequence**.
- **`random`** — each period's state is redrawn from **that market's own prior**, holding
  the information design fixed. The seed derives the sequence, so this arm asks whether a
  result **generalises beyond that one realisation**.

Market 1's clue samples are redrawn along with its states: a sample is drawn *conditional
on* the realized state, so keeping the paper's card against a redrawn state would describe
a world that cannot occur.

---

## The engine correctness gate

Before spending anything on model calls, run a market of **scripted** agents. Each kind
should produce its own model's outcome; if it does not, the bug is in the engine.

```bash
make gate                    # market 3, the base case
make gate6                   # the equidistant control
make gate7 && make gate8     # the equal-width controls, on the seeds their arm runs
make gate-stopped            # markets 92-95, PI only — see below
```

`gate-stopped` is worth reading rather than just passing. What is new about markets 92–95
is a long uninformed tail, and the PI baseline says what this institution does there when
nobody learns: **about −5 francs below v̄, not zero.** At market 4's period 14 that is −4.9
scripted against −32.5 for the agents, so roughly 5 francs of the measured sag is the
double auction and roughly 28 is behaviour. The floor is free and belongs in the
denominator of any sag correction.

| Agent | Y insider periods | X insider periods | E% (insider periods) | Reading |
|---|---|---|---|---|
| `re` | closes at **175** = RE | closes at **354–400** = RE | 95–100 | prices and holdings reach the RE equilibrium |
| `pi` | sits at **220** = PI | 367–400 | **65–69** | never learns from price; certificates end in the wrong hands |
| `zi` | noise near 400 | noise near 400 | 60–90 | ~48% of price changes move toward RE, i.e. chance |

The point is not that `re` converges — it is that `pi` **does not**. The engine can express
both models, so a run that lands on one of them is telling you something about the agents.

The gates are kept separate rather than folded together, so that a red `make gate` always
means *the replication* is broken. The control markets have their own gate because their
baseline behaves differently — and that difference is a result, not a fault:

| market | scripted `re`, buy side | sell side | the arm's own null gap |
|---|---:|---:|---:|
| 3 | 0.733 (n=9) | 1.030 (n=15) | **+0.297** |
| 6 | 0.839 (n=13) | 0.633 (n=11) | −0.206 |
| 7 | 0.886 (n=18) | 0.549 (n=9) | −0.337 |
| 8 | 0.923 (n=15) | 0.414 (n=12) | −0.509 |

Pooled over seeds 42/43/44. The sell side of markets 6–8 is *bimodal* rather than merely
low — market 7's nine sell periods are four near 1.0 and five near 0.1 — because with no
free riders (above) the price never reaches the level a price-based inference rule needs.
An LLM agent has the channel the scripted agent lacks: it can see six different seats
trying to sell and nobody bidding. Whether that is enough is what the control arm measures.

> **Two known limitations.** The scripted `re` baseline cannot read market 1's ten-mark card
> (it tests `card in states`, which a sample never satisfies) and falls back to price
> inference, so it is not a valid reference for market 1. And its inference is over price
> *level* only, which is what the table above is measuring. LLM agents are unaffected by
> the first — the mechanism is in their prompt. Neither is fixed, because the rule is the
> fixed comparison point for every completed session.

---

## Layout

```
ps1982/
  markets.py     five paper markets + three controls + four stopped baselines:
                 parameters, clue model, RE/PI derivation
  params.py      market 3 as module-level constants, now derived from markets.py
  config.py      pydantic scenario config — every treatment variable is a flag
  book.py        the standing-quote book: validation, price improvement, crossing
  engine.py      Session → Period → Round → Turn; broadcast, matching, settlement
  events.py      the JSONL event model and sinks
  metrics.py     post-hoc measures, read back off the log
  agents/        llm_agent.py · scripted.py (zi / pi / re baselines)
  prompts/       instructions.py (Instruction Set 2, adapted) · brief.py · schemas.py
  llm/           openai_compat.py (DeepSeek / Bailian) · gemini.py (Vertex) · base.py
scenarios/       one YAML per experimental arm, 75 of them
runs/            not in git — see below
web/server/      Express + WebSocket; reads runs/, paces replay, tails live runs
  timeline.js    the only definition of a playback step: one step = one agent's TURN
web/src/         React + ECharts + zustand; i18n.ts holds the whole 中/EN dictionary
docs/            experiments.md · agent-reasoning.md · markets-1-to-5.md
                 market-6-control.md · markets-7-8-equal-width.md
                 markets-92-95-stopped.md · proposed-sessions.md
                 paper-verification.md · design-deltas.md
tests/           746 offline tests; nothing here touches the network
```

### runs/ is grouped by purpose

Run logs are **not committed** — they are large and they are outputs, not source. The
layout the viewer expects, and that `runs/README.md` documents:

| group | what it holds |
|---|---|
| `m1/` … `m5/` | the five markets, five complete sessions each (`m3/` has a sixth, on Gemini) |
| `m3_local/` | earlier complete market-3 sessions on DeepSeek's own API |
| `baselines/` | scripted agents and the smoke shakedown; zero API cost |
| `probes/` | one-period vendor and throughput shakedowns, not experiments |

The viewer scans recursively and shows the group alongside each run.

### Getting the data

Run logs are outputs, not source, and they are large — the 26 complete sessions are 1.5 GB
— so they are not in this repository. Two ways to get them:

- **Re-run them.** `./run_batch.sh` reproduces the whole batch; every run is deterministic
  in its seed down to the round order, the tie-breaks and the seat→name mapping, so a
  rerun of `m3_paper_0` faces exactly the market the reported one did. Measured cost for
  all 26 is $66.56, of which $18.95 is the single Gemini session; the 25 Bailian sessions
  come to $47.61. One session is $1.04–2.52 and 3.4–8.0 hours depending on the market,
  and the whole batch runs concurrently.
- **Ask.** The logs from the sessions reported above are available on request —
  siruizou2005@gmail.com.

---

## Results (all five markets, 26 complete sessions)

**Prices reach the rational-expectations level in every market but the one the paper itself
says they should not.** Eighty-nine separating-period observations:

| market | sessions | separating obs | mean price | closing price | RE | PI | efficiency E |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 5 | 8 | 273.1 | 275.9 | 262–272 | 283 | 80–94% |
| 2 | 5 | 8 | 236.4 | 216.0 | **240** | 267 | 86–98% |
| 3 | 6 | 30 | 172.4 | 166.6 | **175** | 220 | 84–91% |
| 4 | 5 | 26 | 164.9 | 161.8 | **175** | 210 | 88–92% |
| 5 | 5 | 17 | 179.7 | 170.3 | **180** | 212 | 86–92% |

Market 5 lands 0.3 francs from RE, market 3 within 2.6, market 2 within 3.6; market 4
overshoots it by 10. Market 1 is the exception — and market 1 is where the paper writes
that the results "provided little support for the RE model," its insiders holding a
ten-draw sample rather than the state.

**The derivation agrees with the paper period by period.** `Market.theory_price()` computes
RE and PI from the dividends and the prior; Table 3's cells pin markets 2–5, and footnote
6 — the only published check on market 1, whose row Table 3 omits — pins which periods
separate, and how many there are in total:

| | market 1 | market 2 | market 3 | market 4 | market 5 | total |
|---|---|---|---|---|---|---:|
| paper, footnote 6 | 6, 8 | 7, 9 | 3, 5, 6, 8, 10 | 5, 7, 8, 10, 12 | 4, 5, 11 | 17 |
| derived here | 6, 8 | 7, 9 | 3, 5, 6, 8, 10 | 5, 7, 8, 10, 12 | 4, 5, 11 | **17** |

### What the separating-period criterion cannot see

In an insider period the prior-information price is the highest valuation in the market,
`PI = max(informed, uninformed)`, and the rational-expectations price is the informed one.
So

```
RE ≠ PI   ⟺   RE < uninformed level   ⟺   the informed want to SELL
```

That is an identity, not a tendency: across 26 sessions the separating periods and the
seller-side periods are the same 89 periods, with no exceptions. **The paper's headline
result, and the table above, are therefore statements about the seller side alone.** The
periods where the informed are buyers are outside the criterion by construction — not
overlooked, unreachable.

`metrics.price_discovery_by_informed_side()` scores them anyway:

```
discovery = (price − uninformed level) / (RE − uninformed level)
```

| | LLM agents, 26 sessions | humans, market 3 | humans, market 5 |
|---|---:|---:|---:|
| informed are **sellers** | **+1.13** (89 periods) | +1.08 | +1.09 |
| informed are **buyers** | **+0.04** (99 periods) | +0.80 | +0.66 |

The human columns are the paper's own average prices from figures 4 and 6, scored with the
same formula. **The asymmetry is in the paper's data too** — this measures it rather than
discovers it. Twenty-three of twenty-six sessions agree in sign, median paired gap +1.05.

What differs is not whether the asymmetry exists but whether it goes away:

```
by repetition of the state       1st     2nd     3rd     4th     5th
  seller side, LLM              +1.17   +1.30   +1.10   +1.02   +1.03
  buyer side,  LLM              −0.01   +0.13   +0.04   +0.10   −0.51
  buyer side,  humans (m3, X)   +0.63   +0.80   +0.98
  buyer side,  humans (m5, Z)   −0.06   +0.60   +0.78
```

and, within a period, the seller side never converges because it never has to:

```
                    first trade    mean    close
  informed selling      +1.14      +1.13   +1.11
  informed buying       −0.11      +0.04   +0.04
```

**Selling leaks the information through the act of exploiting it** — an insider who wants
to sell must undercut, so the first transaction of the period already carries the state,
for humans and LLM agents alike. Buying does not: bidding up to RE destroys the buyer's own
surplus. Human subjects nonetheless learn to price it in, reaching RE by a state's third
occurrence, which is the convergence the paper reports as insiders' advantage vanishing
"completely" upon replication. These agents do not, over five.

Market 1's period 11 shows the mechanism directly, in a period where everyone holds the
same clue and the certificate is worth 349.3 to type I. The three type-I agents state
reservation prices of 349, 349 and 348 — they have the number — and then transact at
300–302, which is type II's valuation, stopping the moment they outbid the second-highest
type. Human subjects in the same period traded at 347. The certificates still end up in
type I's hands (17 or 18 of 18, as RE predicts): **the allocation hypothesis holds while
the price hypothesis fails, because the entire surplus goes to the buyers.**

**What is still open.** The human columns rest on one realized sequence per market — the
paper's formal convergence test is Table 6's profit ratios, not these trajectories. And
these sessions run three rounds per period against continuous oral trading, so buyer-side
under-competition could be a truncation artifact; the first-trade row above argues against
it, since a price that never moves from the first transaction to the last is not a price
that ran out of time. A five-round arm on market 4, seed-paired with the five sessions
reported here, is the direct test.

---

## Three hard constraints

Binding on every prompt, and guarded for every (market, seat) pair in
`tests/test_prompts.py`:

1. **The word "probability" never appears.** The paper is explicit that subjects were
   trained on the bingo cage as a *mechanism* and that probability language was kept out of
   the instructions. This constraint is load-bearing: it forces every market's prior to be
   expressible in **whole balls** (hence `Market.bingo_total`) and market 1's imperfect
   clue to be described as **two boxes of chips** rather than as a likelihood.
2. **Nothing is disclosed** about how many investor types exist, what anyone else's
   dividends are, whether the informed agents stay the same, or how likely a state is.
   This is the baseline, and the bottom rung of a flag-gated **disclosure ladder**
   ([docs/disclosure-treatment.md](docs/disclosure-treatment.md)) whose three flags all
   default off. No rung discloses **which** investors hold the cards.
3. **Common knowledge is per-market.** The paper notes that agents could deduce "in all but
   market 1" that dividends stay constant across periods — so market 1 is not told.

`THEORY_*` values are for post-hoc analysis and the viewer only. They never reach a prompt.

---

## What is in a run log

One JSONL file, one event per line, `agent_visible` marking whether it entered the record
the agents can see. The agent-visible market log is *derived by filtering*, not stored
separately.

| Event | Contents |
|---|---|
| `session_start` | config, seed, market number, realized sequence, clue cards, insider roster, and **that market's RE/PI theory table** (all hidden from agents) |
| `brief` | the briefing text pushed to the agent, byte for byte |
| `model_turn` | full prompt, full completion, chain of thought, token usage, retries, latency |
| `action` / `broadcast` / `trade` / `violation` | decisions, responses, fills, and attempts the market rejected |
| `reflection` | year-end and post-trade notes |
| `period_end` / `session_end` | settlement and totals |

The theory table is written into the log so the viewer — and any downstream reader — takes
it **from the run** rather than keeping its own copy. The viewer's copy used to be market
3's, hard-coded, and would have been silently wrong for every other market.

---

## Batch runs

```bash
./.venv/bin/python batch_plan.py --show    # the plan, without running it
./run_batch.sh                             # launch everything
./run_batch.sh m3_paper_0 m3_gem_paper     # or just these
./.venv/bin/python watch_batch.py --loop 60
./resume_batch.sh                          # resume from the last settled period
```

The main plan is **26 sessions**: five per market for DeepSeek (two on the paper's own
sequence, three on redraws) plus one Gemini session on market 3. Measured cost ≈ $50 over
5–6 hours.

Two follow-up arms sit outside it, deliberately — those 26 sessions are the replication of
a published experiment, and these vary something the experiment did not have:

```bash
./.venv/bin/python batch_plan.py --rounds-arm    # market 4 at 4, 5 and 6 rounds
./run_rounds_arm.sh                              # 6 sessions

./.venv/bin/python batch_plan.py --control-arm   # markets 7 and 8, seeds 42/43/44
./run_control_arm.sh                             # 6 sessions, ≈ $15 over 8–10 hours
MARKETS=-m7 ./run_control_arm.sh                 # one market's three
```

A third group of twenty-six sessions runs in seven waves. **Sixteen have run** — six at six
rounds per period (truncation), four on the stopped baselines (the sag benchmark), three
more control seeds (sell-side sample), and three with the type structure disclosed in every
prompt (the common-knowledge deficit). **Ten are designed and not yet run**: `ladder2`
and `ladder3`, the two rungs above `disclosed` on the
[disclosure ladder](docs/disclosure-treatment.md), plus `ladder1b`, which decomposes the
first of those steps. ≈ $37 over ~24 hours. One wave at a time: sessions × W is a
structural ceiling against the endpoint, and the three together would put 120 requests
against a tolerated 50–80.

```bash
./.venv/bin/python batch_plan.py --proposed      # all seven waves
DRY=1 ./run_proposed.sh ladder2                  # print a wave, launch nothing
./run_proposed.sh ladder1b && ./run_proposed.sh ladder2   # waves may overlap
SERIAL=1 ./run_proposed.sh ladder3               # refuse if another wave is running
./resume_proposed.sh ladder2                     # after an interruption
```

Each arm's threat, design and measured cost is in
[`docs/proposed-sessions.md`](docs/proposed-sessions.md).

The control arm runs its seeds **unfiltered**, and the imbalance that produces is recorded
rather than fixed: equidistance forces `p(buy) > 1/2`, so nine insider periods are
buy-heavy in expectation and the *separating* side is under-sampled by construction —
market 7 draws 18 buy / 9 sell, market 8 draws 15 / 12. Filtering seeds on a criterion
fixed in advance, and designing the sequence outright, were both considered and declined; a
filtered seed is a chosen seed. Every consequence is pinned in `tests/test_markets.py`
rather than left to prose.

**Concurrency is bounded structurally, not statistically.** A session drives its phases on
one thread, so at most `broadcast_workers` of its requests are in flight at any instant —
`sessions × W` is a mathematical ceiling, not a hope. Bailian tolerates 50–80 concurrent;
Vertex serves Gemini from a dynamic shared quota, where there is no limit to raise and the
only lever is to ask for less. The scenario files record the measurements behind each
setting.

---

## Licence and citation

The experiment being replicated is:

> Plott, C. R., & Sunder, S. (1982). Efficiency of Experimental Security Markets with
> Insider Information: An Application of Rational-Expectations Models.
> *Journal of Political Economy*, 90(4), 663–698.
