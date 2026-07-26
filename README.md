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

# 2. free — 372 offline tests
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
scenarios/       one YAML per experimental arm, 30 of them
runs/            not in git — see below
web/server/      Express + WebSocket; reads runs/, paces replay, tails live runs
  timeline.js    the only definition of a playback step: one step = one agent's TURN
web/src/         React + ECharts + zustand; i18n.ts holds the whole 中/EN dictionary
docs/            markets-1-to-5.md · paper-verification.md · design-deltas.md
tests/           372 offline tests; nothing here touches the network
```

### runs/ is grouped by purpose

Run logs are **not committed** — they are large and they are outputs, not source. The
layout the viewer expects, and that `runs/README.md` documents:

| group | what it holds |
|---|---|
| `m3/` | complete market-3 sessions from the main batch |
| `m3_local/` | earlier complete market-3 sessions on DeepSeek's own API |
| `baselines/` | scripted agents and the smoke shakedown; zero API cost |
| `probes/` | one- or two-period vendor shakedowns, not experiments |

The viewer scans recursively and shows the group alongside each run.

### Getting the data

Run logs are outputs, not source, and they are large — the eight complete market-3
sessions alone are 473 MB — so they are not in this repository. Two ways to get them:

- **Re-run them.** `./run_batch.sh` reproduces the whole batch; every run is deterministic
  in its seed down to the round order, the tie-breaks and the seat→name mapping, so a
  rerun of `m3_paper_0` faces exactly the market the reported one did. Measured cost is
  about $50 for all 26 sessions. A single session is ~$2 and about an hour.
- **Ask.** The logs from the sessions reported above are available on request —
  siruizou2005@gmail.com.

---

## Results so far (market 3, eight complete sessions)

**The market does aggregate information.** Twenty-five separating-period observations
(RE = 175, PI = 220, midpoint 197.5):

| | five DeepSeek sessions pooled |
|---|---:|
| mean price, separating periods | **173.1** |
| price changes toward RE | 62% |
| efficiency E | 88–94% |

Prices do not merely *move toward* RE — they **land on it**, 1.9 francs away. DeepSeek and
Gemini agree on every headline measure.

### A pattern the standard analysis cannot see

The paper's separating periods are those where RE ≠ PI, so a state in which **both models
predict the same price is dropped from the analysis** — and that is exactly where
aggregation fails completely.

`metrics.price_discovery_by_informed_side()` fills that gap:

```
discovery = (actual mean price − uninformed level) / (RE − uninformed level)
```

| | mean | n (independent unit = session) |
|---|---:|---:|
| informed are **sellers** | **1.02** | 6 |
| informed are **buyers** | **0.03** | 6 |

**When the informed want to sell, the market covers the whole distance; when they want to
buy, it covers essentially none.** All six sessions agree in sign — sign test p = 0.016,
within-session permutation test p < 0.0001.

The proposed reason is an asymmetry in incentive. When the informed hold an asset worth
*less* than the uninformed believe, selling is how they profit, and selling pushes the
price toward RE — the information leaks through the act of exploiting it. When the asset is
worth *more*, they profit by buying quietly; bidding the price up to RE would destroy their
own surplus, so they have both the motive and the means to keep it near the uninformed
level.

**This is still a hypothesis.** It rests on one market design, and market 3's X state has
four times as far to travel (180 francs) as its Y state (45), so part of the gap may be
distance rather than willingness. **Markets 2 and 5 reverse the buy/sell direction**, which
is the direct way to tell the two explanations apart.

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
