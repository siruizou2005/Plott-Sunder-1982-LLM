# The disclosure ladder

What every investor is told about the structure of the market, as an ordered dial. Rung 0
is the faithful baseline; each rung above it states one more fact and states nothing else
new. All of it is flag-gated and off by default, so the baseline and every completed
session render byte-identical prompts.

| rung | flag added | what it adds to the prompt | status |
|---|---|---|---|
| 0 | — | Table 1's "How Many: No" | run: `runs/control/`, `runs/m4/` |
| 1 | `disclose_structure` | the per-type dividend table, the agent's own type, two of each type's four hold a card in a card year | run: `runs/disclosed/` |
| 2 | `disclose_card_years` | and each year is announced as a card year or not, in both directions | designed, not run |
| 3 | `disclose_insiders_fixed` | and the investors holding the cards are the same ones every card year | designed, not run |

Three more dials ride with rungs 2 and 3 and are **held constant across them**:
`objective_profit_max`, `clue_is_certain`, and `period_end_style: memo` (all below). So
**rung 2 minus rung 1 is a bundle of four dials, and only rung 3 minus rung 2 is a
single-dial contrast.** Being constant across the two top rungs is exactly what keeps that
one contrast clean; what the passengers cost is attribution against the completed rung-1
sessions. A large rung-2 effect will not say which of the four caused it.

**That decomposition is now a wave of its own**, `ladder1b`: two sessions, market 7 and
market 8, on the seed both already have a rung-1 session on. It runs rung 1's disclosure
plus all three passengers and **not** `disclose_card_years`, which turns one four-dial step
into two single-dial ones:

| contrast | isolates |
|---|---|
| `runs/disclosed/` → `ladder1b` | the three passengers (objective, certainty, memo) |
| `ladder1b` → `ladder2` | the card-year rung alone |
| `ladder2` → `ladder3` | the fixedness sentence alone |

With it, every step of the ladder is a single-dial contrast.

## What is never disclosed, at any rung

**Which investors hold the cards.** Every rung's text opens the same clause — "No one is
told which investors they are" — and there is no flag that removes it. Seat ids stay out
of every prompt as before, and the section's only digits are the dividend values, so a
leaked period number, informed count or schedule fails the guard rather than reaching an
agent.

## The question the ladder answers

Plott & Sunder's subjects sat in one room. They could count twelve people, watch the
experimenter walk the same envelope route every period, and accumulate a sense of the
design's shape that the instructions never stated. The baseline prompt gives an LLM agent
none of that: it learns its own two dividend amounts and is told only that "earnings may
be different for different investors" — the number of types, everyone else's amounts and
the informed count are all unbounded. Any shortfall against the paper is therefore
ambiguous between *failed aggregation* and *starved common knowledge*.

Rung 1 removed the second reading and produced a result nobody predicted
(`docs/disclosure-results.md`): discovery did not rise uniformly. Market 8 improved on
both sides, market 7 fell on both, market 4 sat still. The mechanism is a **deletion**. A
baseline agent watching the price climb to 340 has two explanations it cannot separate —
someone holds a letter, or someone simply values it more — and both point at following the
price. Not knowing what anyone else's certificate is worth was doing the price discovery.
Disclosure removes the second reading, so extracting information now needs one more step:
*a price above every uninformed valuation can only mean someone is informed.* Market 7's
agents stopped at "260 is the ceiling, I will not chase" and never took it.

Rungs 2 and 3 exist because that step has two remaining obstacles, and each rung removes
one.

## Rung 2 — the card years, in both directions

`disclose_card_years`. Under rung 1 a blank card is still ambiguous between "I am one of
the uninformed two" and "no one holds a letter this year" — the section says so
explicitly, and the rung-1 sell side is where the whole result sat. Rung 2 announces the
condition of every year, so a blank card in a card year means *I am one of the uninformed*
and nothing else. That is the premise the price-based inference needs.

Two properties of the wording matter:

- **Both directions, every year.** A sentence only in the no-card years would leave an
  insider year silent and indistinguishable from the baseline, and the blank card would
  stay ambiguous.
- **Silent on how many.** "This year lettered clue cards have been handed out" is true of
  an `"all"` period as well as an `"insider"` one, and reads identically for every seat, so
  an agent holding a letter learns nothing there that a blank-card holder does not.

It also replaces the rung-1 section's closing sentence, which says such years are *not*
announced and would otherwise become false.

**It subsumes `announce_no_info_period`** (the §14.4 arm), which speaks only in the no-card
direction. The two write the same sentence there and share one branch in `brief.py`, so no
configuration can print it twice; `Config` refuses `announce_no_info_period: false` beside
the rung, because that asks for silence and an announcement at once and the winner would
be invisible in the log.

## Rung 3 — the card holders do not change

`disclose_insiders_fixed`. One sentence, replacing "or whether they are the same investors
from year to year" with "but they are the same investors in every year in which such cards
are handed out".

**This is true of the engine, not asserted.** `Market.insiders` is the first
`insiders_per_type` seats of each type block, derived from the roster; `clue_cards` tests
membership in it for every insider period; `redrawn()` touches only the realized states.
`engine.py` already records it as `fixed_insiders` in `period_start`.
`test_fixedness_disclosure_matches_the_engine` walks every insider period of every market
the rung runs on and asserts the lettered cards land on the same seats every time — the
wording and the dealing move together or the suite fails.

What it makes available is cross-period inference: an agent that identifies a likely card
holder in year 6 can carry the suspicion to year 7. Rung 1 explicitly denied it that.

## The three dials that ride along

All are on in rungs 2 and 3 and off below, so none is separable from rung 2.

**`objective_profit_max`** puts an explicit earnings objective in the *shared preamble*,
which is the only place that reaches the turn, the broadcast and the reflection prompts
alike. The baseline states its purpose once, in `_TURN_TASK` — the paper's own "You are
free to make as much profit as you can" — so a broadcast reply and a year-end note are
written without any objective at all, and between them those two channels are 73% of calls
and all of the durable memory. The paper's sentence stays; this adds to it.

**`clue_is_certain`** states no new fact. The instructions already say a card carrying a
letter "is always correct" and the year's card line already says the dividend WILL be paid.
The stronger wording *contains* the baseline sentence verbatim, so guards written against
the old text still hold. It is an **insider-side** dial — only a lettered-card holder reads
the changed sentence — where the two disclosure rungs are uninformed-side, and the write-up
should not lump them together. `Config` refuses it on market 1, whose card is a ten-draw
sample either box can produce; the imperfect-clue branch means it could not render there
anyway.

**`period_end_style: memo`** replaces the 100-word year-end note with one standing document
the agent rewrites in full each year, the new version replacing the old
(`docs/design-deltas.md` §5.7). It is the one passenger that changes nothing about what an
agent *knows* — only how much it writes and how much of its own reasoning it carries
forward. It rides here because the ladder's whole subject is what an agent does with an
inference it has the material for, and the baseline's fourteen disconnected notes behind a
window of two give it nowhere to keep one. `Config` forces `period_end_notes: 1` under it,
refuses a reflect budget that could not pay for a memo at `memo_max_words` alongside
reasoning's worst measured run, and requires an empty memo to be retried rather than
discarded; the scenarios run a 16,384 budget and 3 retries.

## Wording constraints, unchanged from rung 1

The section lives inside the instruction vocabulary and the prompt guards hold it there,
at every rung:

- No probability language, no theory words — "clue card that is not blank", never
  "insider". The same forbidden-word lists that guard the baseline run against every rung.
- The prior is never a number; it exists only as the bingo cage.
- The only digits in the section are the dividend values themselves, asserted as a set
  equality on every rung, so a leaked period number or schedule fails loudly. Counts are
  spelled as words for this reason.
- The baseline's common-knowledge fact 1 ("No one is told how many…") would contradict the
  section outright, so under `disclose_structure` it points at the section instead and
  restates what is still hidden: WHICH investors they are.

### Why the tails are four literals

The section's closing paragraph is a `{tail}` slot with four hand-wrapped literals, one per
`(fixedness, card years)` combination, rather than three composable sentences. The
paragraph is hard-wrapped at ~87 columns and its first line *continues* `blanks. `, so a
sentence swapped into the middle has to be re-wrapped anyway — the same reason
`_EARNINGS_PRIVATE`/`_EARNINGS_DISCLOSED` and `_IMPROVEMENT_ON`/`_OFF` are literals. The
`(False, False)` tail is the pre-ladder bytes.

Because the four wrap differently, a sentence sits on one line in one rung and straddles
two in the next. The guards flatten whitespace before matching, or every one of them would
be a test of the line breaks.

### The byte-stability contract

`tests/test_prompts.py` opens with five SHA-256 digests: the baseline prompts, the rung-1
prompts, and the briefs under three configurations. They cover every system prompt of every
kind for every seat of every market, and all four user-message builders over every
information condition.

They are the acceptance criterion for any prompt edit. A failure means a prompt that has
**already been paid for** has changed, which breaks three things at once: the paired
comparisons, whose whole claim is that a treatment session differs from its baseline in the
treatment and nothing else; DeepSeek's prefix cache, which keys on the system prompt; and
the scenario files, which are supposed to describe the runs they produced. Regenerate only
when that is the intent, and say so in the commit message.

## Which markets a rung can run on

`Config` refuses `disclose_structure` on any market whose `sequence_info` contains `"all"`
periods (markets 1, 2, 3, 6, 92): every investor holds a card there, which would make the
two-per-type sentence false. Rungs 2 and 3 require `disclose_structure` — without it,
fixedness has no sentence to modify and the per-year announcement would report on a
structure never introduced — so they inherit that rejection rather than repeating it. The
ladder is defined for markets 4, 5, 7, 8 and the stopped variants 93–95.

## The sessions

Rung 1 ran three sessions (`./run_proposed.sh disclosed`), each seed-paired to a completed
baseline:

| session | market | seed | paired baseline |
|---|---|---|---|
| `disclosed/m4_disc_paper` | 4 | 20250755 (`paper_exact`) | `runs/m4/m4_paper_0` |
| `disclosed/m7_disc_42` | 7 | 42 | `runs/control/m7_ctrl_42` |
| `disclosed/m8_disc_42` | 8 | 42 | `runs/control/m8_ctrl_42` |

Rungs 2 and 3 are designed and **not run**: `./run_proposed.sh ladder2` and
`./run_proposed.sh ladder3`, four sessions each.

| session | market | seed | drawn buy/sell | paired baseline | rung-1 pair |
|---|---|---|---|---|---|
| `ladder{2,3}/m7_lad{2,3}_42` | 7 | 42 | 5 / 4 | `runs/control/m7_ctrl_42` | yes |
| `ladder{2,3}/m7_lad{2,3}_45` | 7 | 45 | 4 / 5 | `runs/control/m7_ctrl_45` | no |
| `ladder{2,3}/m8_lad{2,3}_42` | 8 | 42 | 6 / 3 | `runs/control/m8_ctrl_42` | yes |
| `ladder{2,3}/m8_lad{2,3}_44` | 8 | 44 | 3 / 6 | `runs/control/m8_ctrl_44` | no |

`Market.redrawn` keys its RNG on `ps1982-m{number}-seq-{seed}`, so every session on a seed
draws the same fourteen states, and every comparison is paired period by period.

### The seeds were chosen on their draws, and that needs an argument

Each market's pair pools to **9 buy / 9 sell** over the informed periods.
`scenarios/m7_control.yaml` and `docs/proposed-sessions.md` §Arm 3 both record that
filtering seeds on the buy/sell balance was considered and **declined**, so this needs the
distinction that refusal does not cover.

That refusal is about a reported **level** — the control arm's discovery against 1.0 —
where selecting the sample on the variable under study biases the estimate. The ladder
reports a paired within-market **difference**, and because the treatment is a prompt, the
same drawn sequence appears on both sides of every comparison. Balancing the states
therefore moves the *precision* of the paired difference, not its expectation. It is
blocking on a pre-treatment covariate, not sample selection.

The sell side is what makes it worth doing: the entire rung-1 result lived there (market 7
−0.310, market 8 +0.324, three periods each), and market 7's unfiltered seeds 43 and 44 are
its two most buy-heavy draws (6/3 and 7/2).
`test_the_seeds_the_ladder_runs_are_balanced_and_that_is_a_choice` pins the counts and the
argument together, so neither can drift without the other.

Seed 42 is in both pairs because it is the only seed carrying a completed rung-1 session,
which is what makes the full four-rung ladder exist anywhere.

## Reading the results

- **Read as differences from the measured baselines, never against 1.0 on the buy side.**
  The free-rider identity is algebraic: v̄ is the largest uninformed valuation and a buy
  state is defined by re > v̄, so no uninformed agent can push the buy-side price toward RE
  without learning. Markets 7 and 8 have no free riders on either side. The scripted null
  buy/sell gaps are −0.337 on market 7 and −0.509 on market 8, against **+0.297** on market
  3, and the scripted rule has not changed.
- **The prediction the ladder tests.** Rung 1's split tracked whether what was disclosed
  left the marginal type able to sit still: market 7 tells type I it both sets v̄ and wins
  the buy state, market 8 tells type I it tops neither. If that reading is right, rungs 2
  and 3 should widen market 8's gain and do less for market 7 — and if the split was the
  draw rather than the type roles, they should not.
- **Rung 3 minus rung 2 is the only clean contrast.** Attribute a rung-2 effect to the
  bundle of four, not to the card-year announcement.
- **The memo changes what the notes measure.** `docs/agent-reasoning.md`'s note statistics
  — keyword incidence, the 10.6% who blame a lost tie-break on being slow — were computed
  on ~105-word notes written fresh each year. A 500–800 word document rewritten annually is
  not the same object, and per-note rates are not comparable across the two styles.
- **Do not pool with the baselines.** These sessions test the baselines' external validity;
  folding them into the replication counts would launder the treatment into the result.

## Cost

~**$12.7 a wave, ~$25 for both**, and ~8 h per wave (48 requests in flight at the ceiling). The waves may run
together and did — all ten ladder sessions at once, a ceiling of 120, zero retries — so the
wall clock for the whole ladder is ~8 h rather than ~24.

The per-seed base is the measured cost of the completed session on that exact draw — same
seed, same fourteen states, so the same amount of trading to pay for:

| seed | measured base | note |
|---|---|---|
| m7 42 | $2.54 | mean of rung-1 $2.47 and baseline $2.61 |
| m7 45 | $2.86 | baseline only |
| m8 42 | $2.66 | mean of rung-1 $2.81 and baseline $2.51 |
| m8 44 | $2.87 | baseline only |

Seeds 44 and 45 are the pricier draws (4,728 and 5,159 calls against ~4,300–4,600), which
is about the sequence and not the treatment.

Two things add to that base, and they are very different sizes:

- **The disclosure text: ~$0.025 a session, i.e. noise.** The objective block and the
  certainty wording sit in the system prompt, which is the cached prefix; the card-year
  line is ~16 tokens in the brief.
- **The memo: ~+16%.** Almost all of it on the *input* side. Notes ride in the user
  message, which no prefix cache covers, and the memo appears in ~96% of turn and broadcast
  prompts. Replacing two ~105-word notes with one ~650-word memo adds ~600 tokens to each
  of ~4,100 prompts — ~+$0.35 of input against ~+$0.06 of output. The fourteen calls that
  *write* the memo are the cheap part.
