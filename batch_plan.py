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


def pending():
    """Markets specified but not yet runnable — printed so the gap is never invisible."""
    return [m for m, (impl, _, _) in sorted(MARKETS.items()) if not impl]


if __name__ == "__main__":
    if "--rounds-arm" in sys.argv:
        for name, sc, seed, r in rounds_arm():
            print(f"{name}\t{sc}\t{seed}\t{r}")
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
