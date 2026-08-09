# Deviations from the paper and from the v0.2 design document

Two lists: where this implementation departs from Plott & Sunder (1982), and where it
departs from `plott-sunder-1982-LLM复现设计.md` v0.2.

---

## 1. Corrections to the design document

Both come from reading the paper directly and have been confirmed against the original; see
`docs/paper-verification.md`.

| Design doc §2.3 | Paper (Table 1) |
|---|---|
| Period 1 state = X | Period 1 state = **Y** |
| Periods 3–12 all "6 insiders" | Periods **11–12 are "All"** |

The paper's sequence is the only one implemented:

```
Y Y Y X Y Y X Y X Y Y X     none none | insider×8 | all all
^                           period 1 is Y
        ^ ^ ^   ^   ^       separating periods: 3, 5, 6, 8, 10   (five)
                    ^ ^     periods 11-12 inform everyone, so PI ≡ RE
```

The correction is not cosmetic. It removes one separating period and adds two in which the
two models are indistinguishable by construction, so a single session carries **five**
identifying observations rather than the six the design document assumed. Anything that
reads statistical power off this experiment has to start from five.

### One more, quieter correction

The design document's §14.4 frames "say nothing in a no-information period" as the *market 4*
condition, implying market 3 announced it. Table 1 records market 3's common knowledge about
informed agents as **How Many: No** — subjects holding a blank card could not tell whether
anyone else was informed. So `announce_no_info_period` **defaults to False**, and True is the
treatment arm.

---

## 2. Deviations from the paper

### 2.1 Price improvement — the main one

| | Paper | Baseline here |
|---|---|---|
| Rule | Footnote 3: "Only one (**the last**) bid and offer are outstanding at any time" | A new quote must strictly improve the standing quote on its own side |
| Told to subjects? | Not at all — footnote 3 addresses the reader, not the subject | Stated explicitly as trading rule 5 |
| Consequence | A worse quote can displace a better one, burying its signal | The spread narrows monotonically; that strategy is unavailable |

Why keep it: the spread becomes a well-defined, monotone quantity and can serve as an
information-transmission measure; it matches the price priority of a modern limit book.

Why it matters that it is a deviation: the excluded strategy — posting a deliberately worse
quote to obscure what an earlier quote revealed — sits precisely on the channel this study is
about. So:

- `market3_no_improvement.yaml` runs the paper's literal rule as a robustness arm.
- Every blocked attempt is logged as `violation.reason = "no_improvement"` with its price and
  side, so the counterfactual can be examined offline before deciding to spend on the arm
  (`metrics.book.violations.no_improvement_attempts`).

### 2.2 The rest

| Item | Paper | Here | Note |
|---|---|---|---|
| Disclosure of the book rule | Footnote to the reader only | Trading rules 3–6 state it | The engine needs a determinate rule, and an agent cannot infer one from a blackboard's physical layout |
| Time pressure | 7 minutes per period, warnings at 5 / 6 / 6½ | 2–3 rounds per period | No way to map real-time pressure; the paper's own record sheet has 18 rows, and 3 rounds × 12 seats brackets that |
| Speaking order | Free — raise your hand, calls may collide | Strict rotation, reshuffled each round | Removes both the race to speak and genuine concurrency |
| When you may accept | Continuously | One broadcast at announcement, plus acceptance on any later turn | A hybrid: keeps both immediacy and persistence |
| Crossing quotes | The subject simply accepts the standing quote | The engine settles automatically at the standing price | The closest mechanical equivalent |
| Emotional leakage | "Cursing, laughter, etc. may reveal information" | Absent | An LLM market has no such channel |
| Visible log | Blackboard held the latest four or five | Whole period by default | Both have precedent — market 5 handed out a photocopy of the full log. `market_log_window: 4` reproduces the blackboard |
| Belief elicitation | None. Footnote 4: "we still had no way of knowing their subjective probabilities" | Every turn | Net new data, but a reactivity risk — hence `market3_no_beliefs.yaml` |
| Broadcast reasons | n/a | One line of ≤15 words per response | Another elicitation channel; off in the no-beliefs arm |

---

## 3. Deviations forced by the medium

- **No autonomous tool use.** The engine pushes a complete briefing; the agent replies with
  one JSON object. There is no read loop, so an agent cannot choose what to look at — but it
  also cannot fail to look at something. Design document §6 ① specifies this.
- **Stateless calls.** An agent keeps no conversation. Its entire memory is what the briefing
  carries: its own recent notes and its year-by-year record. This makes memory an explicit,
  auditable design parameter (`period_end_notes` / `trade_notes`) rather than a property of a
  context window.
- **No byte-exact replay.** Model output is not reproducible, so the JSONL log *is* the
  artifact. The seeded RNG covers only the round order and the tie-break; both are recorded.
  "Replay" in the viewer means replaying the log, not re-running the simulation.

---

## 4. Reasoning configuration is a validity constraint, not a cost knob

Design doc §13.2 identifies broadcast replies as "the only step worth downgrading" — they
are ~70% of all calls and a simpler decision than posting a quote. It also warns to check
sensitivity before committing. The check was run, and it failed.

From the first smoke run, with `broadcast_thinking: false`:

| Channel | Reasoning | Stated the correct prior EV | Traded against its own stated reservation |
|---|---|---:|---:|
| own turn | thinking **on** | 22 / 24 | **0 / 11** |
| broadcast reply | thinking **off** | 23 / 69 | **6 / 11** |

The errors were structured, not random. Type I agents said their certificate was worth 250
and type II said 225 — exactly (400+100)/2 and (300+150)/2. The downgraded channel falls
back on a 50/50 prior instead of deriving 0.4 from the bingo cage's 16 of 40 balls. One
agent (S12, type III) declined a bid of 200 with the reason *"Price 200 is below expected
value of 145"* — wrong number (its EV is 155) and the inequality reversed — then accepted
the same standing bid one turn later, on its own turn, with a correctly stated reservation
of 155.

Two reasons this is not patchable in the prompt:

1. Deriving 0.4 from the bingo cage is **part of what the experiment measures**. Handing
   agents their expected value would contaminate the belief data that §11.3 exists to
   collect.
2. Broadcast replies are the channel through which **most trades are actually struck**
   (8 of 11 in the smoke run). A market whose trades rest on wrong arithmetic measures the
   model's arithmetic, not whether prices aggregate information.

So `broadcast_thinking` now defaults to **true**, and the cheap configuration lives on as
`scenarios/market3_broadcast_fast.yaml` — kept because the comparison is itself evidence,
and because it roughly halves cost and runtime for anyone who needs that trade.

---

## 5. What an agent remembers, and what it is called

Four changes to agent memory, all made after reading the first smoke run's prompts back.

### 5.1 Every call carries the same memory

A turn brief used to carry the agent's own notes and its year-by-year record; a broadcast
reply carried neither. That asymmetry had no counterpart in the paper — a subject hearing a
bid is sitting at the table with their record sheet — and it fell on the channel that
settles most trades (**8 of 11** in the smoke run). Post-trade and year-end reflections were
thinner still. All four calls now assemble memory from one place (`brief._memory_blocks`),
differing only in task framing.

**This is expected to raise measured RE convergence**, because what it upgrades is exactly
the uninformed agent's ability to infer the state from price. It is a fidelity fix, not a
neutral one, and the older configuration should be kept as a comparison arm.

### 5.2 Reflections reason

Reflections ran with thinking off as a cost saving. Of the smoke run's notes that stated a
prior expected value, **20 of 20 stated the wrong one** — type I said 250, type II said 225,
the 50/50 answer instead of the bingo cage's 16 of 40. Not one was right. That is worse than
the broadcast channel's 67%, and it does more damage: a note is *durable memory*, so the
next turn — reasoning with thinking on — reads "my expected value is 250" as its own past
conclusion. `reflect_thinking` now defaults to true and the token cap rose, since reasoning
draws on the same budget.

It rose twice. 1,200 was the first move and was still too tight: on the probe run **6 of 12
year-end calls spent the entire budget reasoning and returned nothing at all**, which the
engine records as `empty_note`. `reflect_max_output_tokens` is now **3,000**, and even there
about 3% of year-end notes come back empty in a completed session. Reasoning is roughly four
times the note it produces — median 376 tokens of thinking against 142 of body.

### 5.3 The two kinds of note get separate slots

One shared three-slot window meant post-trade notes evicted the year-end reflection, which
design doc §8 calls the main learning node. Measured rate: 0.9 post-trade notes per seat per
period at one round — nothing evicted — but **3.4 on average and up to 14** at the three
rounds the real experiment runs. Now `period_end_notes: 2` and `trade_notes: 3`, each
stamped with the year and round it was written in; previously they were undated bullets an
agent could not tell apart.

### 5.4 An agent learns when its acceptance lost the draw

| | Paper | Before | Now |
|---|---|---|---|
| Others learn who else accepted | No | No | No |
| **You** learn your own acceptance lost | Yes — you watched it | **No** | Yes |
| Anyone learns how many accepted | No | No | No |

Design doc §0.2 erases losing acceptors from the *public* record. It says nothing about
hiding the attempt from the agent that made it — a subject who called out an acceptance and
watched the experimenter point at someone else plainly knows it happened. Being stateless,
the agent had no trace of it at all. It is now told, in its own words from that broadcast,
that another investor was chosen instead.

What stays hidden is the **number** of acceptors. Nobody could count raised hands in a noisy
oral auction, and that count *is* the latent demand curve — the one measurement no human
experiment can produce. Handing it over would let agents read demand at a price directly.

### 5.5 The chain of thought is kept

`reasoning_content` is now stored on every `model_turn`. It was being discarded, which was
the single largest data loss in the project: reasoning is **91–96% of all output tokens** on
this model, so the run was paying for it and throwing it away.

It matters here more than it would elsewhere. The research question is whether uninformed
agents read the state off the price, and the `basis` field is a one-word self-report
(`prior` / `price` / `spread`). The reasoning is the actual derivation — this is one turn,
verbatim:

> our clue is blank. So we have no private information beyond the prior: probability
> X = 16/40 = 0.4 … Expected value per certificate = 0.4\*400 + 0.6\*100 = 160+60 = 220 francs

That distinguishes *computed 220* from *guessed 220*, which no self-report can. Measured at
~2,400 characters per call, roughly **9 MB** added per session.

Two constraints, both asserted in `tests/test_engine.py`:

- **Audience-only.** Written with `agent_visible: false`, like the clue cards and the
  losing acceptors. It is net-new data no human experiment could produce.
- **Never fed back.** No briefing quotes it. DeepSeek's own guidance is that
  `reasoning_content` must not re-enter the context, and independently it would hand an
  agent a transcript of its own deliberation that no subject ever had.

### 5.6 Agents address each other by name

Seat IDs never reach a prompt. `S01..S12` encodes structure no subject had: the types run in
blocks (S01–S04 are all type I) and the insiders are S01, S02, S05, S06, S09, S10 — every
first-and-second of four. The name pool is **shuffled per session** from the seeded RNG,
because a fixed map would tie whatever prior the model holds about a name to the same type
and insider status in every repetition, so it would not average out across sessions. The
realized mapping is in `session_start.seat_names`; the log, the metrics and the viewer keep
the seat IDs. `tests/test_prompts.py` asserts no seat ID appears in any prompt.

### 5.7 The year-end summary has a second style: one memo, rewritten

`Rules.period_end_style`. `"note"` is the baseline and the default; `"memo"` is a flag-gated
alternative, designed and not yet run.

**Why.** The baseline asks for "about 100 words" and gets them — median **105 words** over
two completed sessions, IQR 520–630 characters, the whole distribution inside 246–866. The
ask is being honoured tightly, which is the problem: fourteen years produce fourteen short,
disconnected notes behind a window of two (§5.3), so a conclusion reached in year 3 is gone
by year 6 unless the agent happens to restate it. Nothing in the design carries a view
forward. `docs/agent-reasoning.md` reports the consequence from the other end — neither the
propensity to read the price nor the quality of the reading improves over a session, with
notes or without them.

**What it is.** One standing document. At each year end the agent is shown its previous memo
verbatim and writes the whole thing again, **about 600 words** (`Rules.memo_words`) with a
stated ceiling of 1200 (`Rules.memo_max_words`). The new version **replaces** the old one,
and the prompt says so: *anything you leave out is gone, and you will not see it again.*
That sentence is the mechanism. A memo that merely accumulated would be a longer note; a
memo that replaces its predecessor forces the agent to decide each year what is still worth
carrying, which is what makes it continuous and what makes the length honest.

**"about N", not a range — and this was measured, not guessed.** The first version asked for
"between 500 and 800 words" and `runs/probes/ladder2_smoke` (3 periods, 12 seats, 36 memos,
exactly this configuration) shows what that produced: **median 1050 words, maximum 5168,
19% inside the band.** The same model honours the note style's "about 100 words" to a median
of 105. A single soft target is the phrasing that works; the ceiling is a separate sentence
so the runaway tail has something explicit to hit.

**The rewrite is real.** In that same probe, 0 of 12 seats grew monotonically across the
three years (medians 1082 → 1071 → 971). The memo is being rewritten, not appended to.

**One prompt, two occasions.** Both reflection calls share `reflect_system_text` — the
year-end one and the one written straight after a trade. A task block that simply said
"rewrite your memo" would land on every post-trade note too, where the brief asks for one or
two sentences, and the two would contradict each other several times a period. The memo
block names both occasions and defers to the closing line of the brief to say which is in
force. Guards pin both halves.

**Two hard constraints, both enforced by `Config`:**

- **`period_end_notes` must be 1.** The memo already contains its own history, so carrying
  two hands the agent a superseded copy of its own conclusions beside the current one.
- **`reflect_max_output_tokens` must clear a floor derived from the ceiling**, not a fixed
  number: `memo_max_words × 1.25 + 7500`, which is 9,000 at the default 1200. Both constants
  are measured on the same probe — the body runs **1.25 tokens per word** (range 1.22–1.34)
  and reasoning, which shares this budget, ran a **median of 1,800, a p90 of 4,021 and a
  maximum of 7,450**. The floor is therefore "a memo at the ceiling, still intact when
  reasoning has its worst measured run". The scenarios use 16,384.

**Cost lands on the input side, not the output side.** Notes ride in the user message, which
no prefix cache covers, and they appear in ~96% of turn and broadcast prompts (3,494 of
3,621 in a completed session). Replacing two ~105-word notes with one ~650-word memo adds
tokens to each of ~4,100 prompts. **Measured** on the probe rather than projected: the memo
adds **1,521 tokens** to every prompt that carries it (median 2,246 in the memo-less first
year against 3,767 in the third), which is **~+$0.88 of input against ~+$0.13 of output,
about +39% on a $2.6 session.** The fourteen calls that write the memo are the cheap part.
The first estimate here said +16%, from a 650-word memo; the measured memos were 1050 words,
and the "about 600" wording is partly an attempt to bring that back down.

**An empty memo is now retried.** Nothing retried it before, and that was a real hole:
`max_retries` covers transient API errors, `repair_retries` covers unparseable JSON, and
`complete_text` sets `repairs = 0` outright, so the text channel had no loop at all. An
empty note went straight to an `empty_note` violation and was **discarded**. It is almost
never a model with nothing to say — reasoning shares the output budget, so an empty note is
a call that spent the whole cap thinking (3% of year-end notes at a 3,000 cap; one probe run
lost 6 of 12). Under this style the loss is worse than a missing note, because the memo is
the seat's *entire* long-term memory, so losing one year silently reverts that agent to the
previous year's view. `AgentSpec.reflect_empty_retries` defaults to 0, so no completed
scenario changes meaning; the memo scenarios set 3. Usage is summed across attempts — as
`complete_json` already does across its repairs — and the envelope records `attempts`, so a
retried note is billed for what it cost and is visible in the log.

**A truncated memo is worse than a truncated note**, which is why `truncated_note` was added
first: a note cut off mid-sentence is non-empty, so it passes the `empty_note` guard and is
stored and carried forward with nothing in the log to say it is a fragment. One is already
in `runs/disclosed/m7_disc_42` (seat S07, year 2 — 2,943 tokens reasoning, 58 of body). Under
the memo style that fragment would be the seat's entire long-term memory. The violation
records it and keeps it; the budget floor is what makes it rare.

---

## 6. Known properties of the scripted baselines

The scripted agents are diagnostics, not research objects. Two behaviours worth knowing:

- **Within-period rise.** Prices climb toward the equilibrium within a period and the
  *closing* price is the one that lands on it; the period mean sits below. Human markets do
  the same, and the paper's figure 4 plots period means.
- **The RE agent needs a decisive price.** It infers the state only when the last trade sits
  within 12% of a fully revealing price (400 or 175). Without that test, a no-information
  period collapses into a self-confirming false consensus: the price happens to sit near the
  state-Y level for no reason, everyone reads it as a signal, and their selling keeps it
  there. The band is `REAgent._BAND`.
