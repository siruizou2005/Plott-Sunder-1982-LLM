# The structural-disclosure treatment

`Rules.disclose_structure`, off by default. Three sessions in wave `disclosed`
(`./run_proposed.sh disclosed`), each paired to a completed baseline by seed:

| session | market | seed | sequence | paired baseline |
|---|---|---|---|---|
| `disclosed/m4_disc_paper` | 4 | 20250755 | `paper_exact` (Table 1) | `runs/m4/m4_paper_0` |
| `disclosed/m7_disc_42` | 7 | 42 | `random_prior` | `runs/control/m7_ctrl_42` |
| `disclosed/m8_disc_42` | 8 | 42 | `random_prior` | `runs/control/m8_ctrl_42` |

`Market.redrawn` keys its RNG on `ps1982-m{number}-seq-{seed}`, so the two `random_prior`
sessions draw the same fourteen states their baselines drew. Everything else in the
scenario files is the paired baseline's value — model, three thinking budgets, 3 rounds,
W=12, rules — so the prompt disclosure is the only difference and the comparison is
paired period by period.

## The question

Plott & Sunder's subjects sat in one room. They could count twelve people, watch the
experimenter walk the same envelope route every period, and accumulate a sense of the
design's shape that the instructions never stated. The baseline prompt gives an LLM agent
none of that: it learns its own two dividend amounts and is told only that "earnings may
be different for different investors" — the number of types, everyone else's amounts and
the informed count are all unbounded. Any shortfall against the paper is therefore
ambiguous between *failed aggregation* and *starved common knowledge*. This arm removes
the second reading by handing the structure over and measuring what moves.

## What is disclosed, and what is not

In: the full per-type dividend table (all three types, both states), the agent's own type
named, four investors per type, and that in a year when lettered cards are handed out
exactly two of each type's four hold one.

Out, deliberately:

- **Identities.** No one is told which investors hold the cards, and seat ids stay out of
  every prompt as before.
- **Fixedness.** The true mechanism fixes the same two per type for the whole session,
  but the text says only that no one is told "whether they are the same investors from
  year to year" — silence in both directions, as the baseline is silent.
- **The schedule.** Which years are card years (5–13 in all three markets) is not stated.
  The allocation sentence is conditional — "in a year in which clue cards that are not
  blank are handed out" — and the section closes by saying such all-blank years may
  exist and are not announced, so a blank card stays ambiguous between "I am one of the
  uninformed two" and "no one holds a letter this year". `announce_no_info_period` stays
  unset.

## Wording constraints

The section lives inside the instruction vocabulary and the prompt guards hold it there
(`tests/test_prompts.py`, the structural-disclosure block):

- No probability language, no theory words — "clue card that is not blank", never
  "insider"; the same forbidden-word lists that guard the baseline run against the
  disclosed prompts.
- The prior is never a number; it exists only as the bingo cage.
- The only digits in the section are the dividend values themselves — the guard asserts
  the integer set of the section equals the market's dividend set, so a leaked period
  number or schedule fails loudly.
- The baseline's common-knowledge fact 1 ("No one is told how many…") would contradict
  the section outright, so under the flag it is replaced by one that points at the
  section and restates the one thing still hidden: WHICH investors they are.
- The baseline prompt is byte-identical with the flag off — the completed sessions'
  prompts are unchanged, which prefix caching and the pairing both require.

`Config` refuses the flag on any market whose `sequence_info` contains `"all"` periods
(markets 1, 2, 3, 6, 92): in those periods every investor holds a card, which would make
the two-per-type sentence false. The treatment is defined for markets 4, 5, 7, 8 and the
stopped variants 93–95; only 4, 7 and 8 are run.

## Reading the results

- **Market 4** is the published-family case: the informed buy side sits 165 francs from
  its target and period 14 ends uninformed. Read D per period against `m4_paper_0` and
  the period-14 level against the same session's.
- **Markets 7/8** are where the free-rider identity bites: v̄ is the largest uninformed
  valuation, so no uninformed agent can push the buy-side price toward RE without
  learning, and these markets have no free riders on either side. A disclosed agent knows
  enough structure to reason "a price above every uninformed valuation means someone with
  a letter is buying" — the price-based inference the scripted-RE rule needs and the
  baseline sell side never triggered. Whether disclosure closes any of the measured
  buy/sell gap (−0.337 on market 7, −0.509 on market 8, against +0.297 on market 3) is
  the measurement. Read as differences from the scripted baselines (seed 42, unchanged),
  never against 1.0 on the buy side — the identity is about *learning*, and disclosure
  changes what there is to learn from, not the identity itself.
- **Do not pool with the baselines.** These sessions test the baselines' external
  validity; folding them into the replication counts would launder the treatment into
  the result.

Cost: three 3-round sessions, ~$2.5 and ~8 h each in parallel (36 requests in flight at
ceiling). The disclosure block adds ~1.4k characters to a cached prefix; the cost effect
is noise.
