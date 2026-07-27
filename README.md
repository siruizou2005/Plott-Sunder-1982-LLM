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

# 2. free — 381 offline tests
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

## The five markets

They are five **treatments, not five repetitions** — roster size, prior, number of states,
information precision and period count all differ.

| Market | Periods | Agents | States | Prior | Information design | What makes it different |
|---:|---:|---:|---|---|---|---|
| 1 | 11 | **9** | X/Y | 1/3 | 1-4 none · 5-8 insider · 9-11 all | **Imperfect information**: the clue is a ten-draw 0/1 sample, not a letter; one insider per type |
| 2 | 11 | 12 | X/Y | 1/3 | 1-4 none · 5-6 all · 7-11 insider | Everyone is informed *before* the insider periods — the reverse of market 3 |
| 3 | 12 | 12 | X/Y | .4 | 1-2 none · 3-10 insider · 11-12 all | The paper's most-analysed market, and where this codebase started |
| 4 | 14 | 12 | X/Y | .4 | 1-4 none · 5-13 insider · **14 none** | The only market with a no-information period at the **end** as well as the start |
| 5 | 13 | 12 | **X/Y/Z** | .35/.25/.40 | 1-3 none · 4-13 insider | **Three states** |

Every parameter's provenance is in [`docs/markets-1-to-5.md`](docs/markets-1-to-5.md).
`ps1982/markets.py` is that document as executable data, and `tests/test_markets.py` checks
it back against the paper's Table 1, Table 2, Table 3 and footnote 5, cell by cell.

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
make gate
```

| Agent | Y insider periods | X insider periods | E% (insider periods) | Reading |
|---|---|---|---|---|
| `re` | closes at **175** = RE | closes at **354–400** = RE | 95–100 | prices and holdings reach the RE equilibrium |
| `pi` | sits at **220** = PI | 367–400 | **65–69** | never learns from price; certificates end in the wrong hands |
| `zi` | noise near 400 | noise near 400 | 60–90 | ~48% of price changes move toward RE, i.e. chance |

The point is not that `re` converges — it is that `pi` **does not**. The engine can express
both models, so a run that lands on one of them is telling you something about the agents.

> **A known limitation.** The scripted `re` baseline cannot read market 1's ten-mark card
> (it tests `card in states`, which a sample never satisfies) and falls back to price
> inference. LLM agents are unaffected — the mechanism is in their prompt — but `re` is not
> a valid reference for market 1.

---

## Layout

```
ps1982/
  markets.py     all five markets: parameters, clue model, RE/PI derivation, redraw
  params.py      market 3 as module-level constants, now derived from markets.py
  config.py      pydantic scenario config — every treatment variable is a flag
  book.py        the standing-quote book: validation, price improvement, crossing
  engine.py      Session → Period → Round → Turn; broadcast, matching, settlement
  events.py      the JSONL event model and sinks
  metrics.py     post-hoc measures, read back off the log
  agents/        llm_agent.py · scripted.py (zi / pi / re baselines)
  prompts/       instructions.py (Instruction Set 2, adapted) · brief.py · schemas.py
  llm/           openai_compat.py (DeepSeek / Bailian) · gemini.py (Vertex) · base.py
scenarios/       one YAML per experimental arm, 32 of them
runs/            not in git — see below
web/server/      Express + WebSocket; reads runs/, paces replay, tails live runs
  timeline.js    the only definition of a playback step: one step = one agent's TURN
web/src/         React + ECharts + zustand; i18n.ts holds the whole 中/EN dictionary
docs/            markets-1-to-5.md · paper-verification.md · design-deltas.md
tests/           381 offline tests; nothing here touches the network
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

The plan is **26 sessions**: five per market for DeepSeek (two on the paper's own sequence,
three on redraws) plus one Gemini session on market 3. Measured cost ≈ $50 over 5–6 hours.

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
