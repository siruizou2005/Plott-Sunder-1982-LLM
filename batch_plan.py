#!/usr/bin/env python3
"""The batch plan: the paper's five markets, five DeepSeek sessions each, plus Gemini on 3.

The single source of the seed scheme, so the launcher, the resumer and the status view
cannot disagree about which run is which. Prints one `name<TAB>scenario<TAB>seed` line per
session, or a readable table with --show.

The five groups are Plott & Sunder's five MARKETS, not five replications of one of them.
They differ in roster size, prior, number of states, information design and period count
(see docs/markets-1-to-5.md), so they are five treatments, not five samples. Only market 3
is implemented today; the rest are listed in MARKETS with implemented=False so the seed
scheme is fixed now and adding them later cannot renumber — and therefore cannot silently
re-draw — the runs already completed.

Why the seed matters twice over. On `paper_exact` the sequence is fixed and the seed only
varies the round order, the tie-breaks and the seat->name mapping — that arm replicates
one sequence. On `random_prior` the seed DERIVES the sequence by redrawing each period's
state from that market's own prior, holding the information design fixed, so those runs
are independent draws. Both are needed: the first says whether a result on Table 1's
sequence is stable, the second whether it generalises beyond that one realisation.
"""

from __future__ import annotations

import sys

BASE_SEED = 20250725
PAPER_PER_MARKET = 2
RANDOM_PER_MARKET = 3
# 10 seeds of headroom per market, so adding a fourth random arm later does not renumber
# the runs already completed.
MARKET_STRIDE = 10

# market -> (implemented?, paper scenario, random scenario)
MARKETS = {n: (True, f"scenarios/m{n}_paper.yaml", f"scenarios/m{n}_random.yaml")
           for n in (1, 2, 3, 4, 5)}

# Gemini replicates ONE market (3) with two sessions, thinking off. Their seeds are
# DELIBERATELY reused from the DeepSeek plan — the first paper run and the first random
# run — so each Gemini session faces a market identical to a DeepSeek one down to the
# drawn sequence, the round order, the tie-breaks and the seat->name mapping. Paired that
# way, a difference in outcome is the model; unpaired, it could be the draw.
# Gemini is ~7x the cost per session (no implicit caching below 4,096 input tokens), so
# it gets two paired runs rather than ten.
GEMINI_MARKET = 3
GEMINI_SCENARIO = ("scenarios/gemini_paper.yaml",)


def plan(with_gemini: bool = True, markets: list[int] | None = None):
    out = []
    for m in sorted(markets or MARKETS):
        implemented, paper_sc, random_sc = MARKETS[m]
        if not implemented:
            continue
        base = BASE_SEED + (m - 1) * MARKET_STRIDE
        for i in range(PAPER_PER_MARKET):
            out.append((f"m{m}_paper_{i}", paper_sc, base + i))
        for i in range(RANDOM_PER_MARKET):
            out.append((f"m{m}_random_{i}", random_sc, base + PAPER_PER_MARKET + i))
        if with_gemini and m == GEMINI_MARKET:
            # pairs with m{m}_paper_0: same seed, so the same market to the tie-breaks
            out.append((f"m{m}_gem_paper", GEMINI_SCENARIO[0], base))
    return out


# The rounds arm. Six market-4 sessions at 4, 5 and 6 rounds per period, each reusing the
# seed of a 3-round session already reported, so the whole gradient 3/4/5/6 runs on two
# fixed sequences — Table 1's and m4_random_0's redraw — and rounds is the only thing that
# moves. Deliberately NOT folded into plan(): those 26 sessions are the replication, this is
# a follow-up that varies a design parameter the paper did not have.
ROUNDS_ARM_SEEDS = {"paper": 20250755, "random": 20250757}   # = m4_paper_0, m4_random_0
ROUNDS_ARM = (4, 5, 6)


def rounds_arm():
    """[(name, scenario, seed, rounds)] — market 4 at 4, 5 and 6 rounds per period."""
    return [(f"rounds/m4_r{r}_{arm}", f"scenarios/m4_{arm}_r{r}.yaml", seed, r)
            for r in ROUNDS_ARM for arm, seed in sorted(ROUNDS_ARM_SEEDS.items())]


# The control arm. Markets 7 and 8 are the equal-width controls — neither is one of Plott &
# Sunder's — where the informed-buy and informed-sell targets are both 100 francs from the
# uninformed level AND a merely-competitive price occupies the same share of the D scale on
# each side. Six `random_prior` sessions on DeepSeek, three per market.
#
# It supersedes the market-6 arm, which was designed first and half-solved the problem:
# market 6 is equidistant but its competitive interval is 0.875 of D on the buy side against
# 0.125 on the sell side, the most lopsided in the family. Market 6's scenarios and
# `make gate6` are kept — the market is still the one Table 7 prints — but it is not what
# this arm runs. See docs/markets-7-8-equal-width.md.
#
# Deliberately NOT folded into plan(), for the same reason as the rounds arm: those 26
# sessions are the replication of a published experiment, and these are markets that
# experiment does not contain. Folding them in would make `batch_plan.py` claim they are
# the paper's.
#
# The seeds are the user's 42/43/44 rather than the BASE_SEED scheme, which keeps them
# unambiguously outside it. UNFILTERED, and the imbalance that produces is a known cost, not
# an oversight: Proposition 1 forces p(X) > 1/2 on any equidistant market, so nine insider
# periods are buy-heavy in expectation (5.4 against 3.6) and the sell side — the only
# separating side — is under-sampled by construction. Market 7 draws 18 buy / 9 sell across
# the three seeds, market 8 draws 15 / 12, and market 8's seeds 42 and 43 draw the same nine
# insider periods. Filtering seeds on a stated balance criterion and designing the sequence
# outright were both considered and declined; the seeds were given, not searched.
# `tests/test_markets.py::test_the_seeds_the_arm_actually_runs_are_imbalanced_and_that_is_recorded`
# pins every number above so it survives to the write-up.
CONTROL_ARM_SEEDS = (42, 43, 44)
CONTROL_ARM_MARKETS = (7, 8)


def control_arm(markets: tuple[int, ...] = CONTROL_ARM_MARKETS):
    """[(name, scenario, seed)] — the equal-width controls, markets 7 and 8.

    Both markets run the SAME three seeds. That does not pair them: `Market.redrawn` keys
    its RNG on `ps1982-m{number}-seq-{seed}`, so seed 42 draws a different sequence for
    market 7 than for market 8, and the A-vs-B comparison therefore rests on two balanced-
    enough draws rather than on one shared one. Pairing was available (market 8 reproduces
    market 7's seed-42 draw at seed 940) and was declined for the same reason the seeds were
    not filtered.
    """
    return [(f"control/m{n}_ctrl_{s}", f"scenarios/m{n}_control.yaml", s)
            for n in markets for s in CONTROL_ARM_SEEDS]


# ---------------------------------------------------------------- the proposed arms
#
# Sixteen sessions in four waves, written for the LLM-agent paper. Each wave is one arm
# and answers one threat; docs/proposed-sessions.md states which. They are NOT folded into
# plan() for the same reason the control and rounds arms are not: those 26 sessions are the
# replication of a published experiment and these are follow-ups that vary something the
# experiment did not have.
#
# Seed and run_name live in the scenario files here rather than in this table, because
# every session in these arms differs from its neighbours in a parameter (rounds, market,
# stop period) that has to be readable in the file that sets it. This table therefore
# carries the wave membership and nothing else, and the launcher reads names from it.
#
# Waves exist because of the endpoint, not the science. A session holds at most
# `broadcast_workers` requests in flight, so sessions x W is a structural ceiling against
# Bailian's tolerated 50-80: the rounds arm alone is 6 x 12 = 72, and all thirteen at once
# would be 156. W stays at 12 in every file because the 26 sessions these are read against
# all ran at 12.
PROPOSED_WAVES: dict[str, tuple[str, ...]] = {
    # Truncation. Six rounds per period on the six seeds the control arm already ran, so
    # the comparison is paired period by period. ~13h and ~$3.9 a session, measured on the
    # market-4 rounds arm above — nearly double a 3-round session, which is why this wave
    # is the long one.
    "rounds": ("m7_control_r6_s42", "m7_control_r6_s43", "m7_control_r6_s44",
               "m8_control_r6_s42", "m8_control_r6_s43", "m8_control_r6_s44"),
    # The uninformed resting level, on the published markets' own parameters. Markets 2, 3
    # and 5 have no mature no-information period at all; market 4 has eleven sessions of
    # one and is here to validate the design rather than to fill a gap.
    "stopped": ("m92_stopped", "m93_stopped", "m94_stopped", "m95_stopped"),
    # Sell-side sample for the control arm: the next consecutive seeds, unfiltered.
    "sellside": ("m7_control_s45", "m7_control_s46", "m8_control_s45"),
    # Structural disclosure (Rules.disclose_structure). Three sessions, each on the seed
    # of a completed baseline — m4_paper_0 (20250755, paper_exact), m7_ctrl_42 and
    # m8_ctrl_42 (random_prior) — so each pair faces the same drawn market and the prompt
    # disclosure is the only difference. 3 x 12 = 36 in flight; one wave.
    # docs/disclosure-treatment.md.
    "disclosed": ("m4_disclosed_paper", "m7_disclosed_s42", "m8_disclosed_s42"),
}


def proposed(wave: str | None = None):
    """[(wave, scenario)] for one wave or all of them, in the order they should run."""
    waves = [wave] if wave else list(PROPOSED_WAVES)
    bad = [w for w in waves if w not in PROPOSED_WAVES]
    if bad:
        raise SystemExit(f"unknown wave {bad}; expected one of {list(PROPOSED_WAVES)}")
    return [(w, f"scenarios/{s}.yaml") for w in waves for s in PROPOSED_WAVES[w]]


def pending():
    """Markets specified but not yet runnable — printed so the gap is never invisible."""
    return [m for m, (impl, _, _) in sorted(MARKETS.items()) if not impl]


if __name__ == "__main__":
    if "--proposed" in sys.argv:
        # `--proposed [wave]` — one `wave<TAB>scenario` line per session. run_name and seed
        # come from the scenario file, so the launcher passes neither.
        rest = [a for a in sys.argv[1:] if not a.startswith("-")]
        for w, sc in proposed(rest[0] if rest else None):
            print(f"{w}\t{sc}")
        sys.exit(0)
    if "--rounds-arm" in sys.argv:
        for name, sc, seed, r in rounds_arm():
            print(f"{name}\t{sc}\t{seed}\t{r}")
        sys.exit(0)
    if "--control-arm" in sys.argv:
        # -m7 / -m8 narrows to one market; with neither, both run. There is no Gemini
        # session in this arm.
        only = tuple(int(a[2:]) for a in sys.argv[1:]
                     if a.startswith("-m") and a[2:].isdigit())
        for name, sc, seed in control_arm(only or CONTROL_ARM_MARKETS):
            print(f"{name}\t{sc}\t{seed}")
        sys.exit(0)
    show = "--show" in sys.argv
    only = [int(a[2:]) for a in sys.argv[1:] if a.startswith("-m") and a[2:].isdigit()]
    rows = plan(with_gemini="--no-gemini" not in sys.argv, markets=only or None)
    if not show:
        for name, sc, seed in rows:
            print(f"{name}\t{sc}\t{seed}")
        sys.exit(0)

    from ps1982.config import load_config
    # Read the sequence off the SCENARIO, not off params: params holds market 3's, so this
    # view used to print twelve X/Y periods for every market — including market 5, which
    # has thirteen periods and three states. A status view that lies is worse than none.
    print(f"{'run_name':16s} {'market':>6s} {'seed':>9s}  {'states':28s} separating")
    total = 0
    for name, sc, seed in rows:
        cfg = load_config(sc).model_copy(update={"seed": seed})
        m = cfg.market_spec
        sep = [p for p in range(1, m.n_periods + 1)
               if m.theory_price(p)["RE"] != m.theory_price(p)["PI"]]
        alloc = [p for p in range(1, m.n_periods + 1)
                 if m.theory_holder(p)["RE"] != m.theory_holder(p)["PI"]]
        total += len(sep)
        print(f"{name:16s} {m.number:>6d} {seed:>9d}  {' '.join(m.sequence_states):28s} "
              f"price={sep} alloc(n={len(alloc)})")
    print(f"\n{len(rows)} sessions · {total} price-separating period observations")
    if pending():
        print(f"NOT YET RUNNABLE: markets {pending()} — see docs/markets-1-to-5.md")
