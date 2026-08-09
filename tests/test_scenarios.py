"""Scenario files load into the Config they claim to be.

Every model in config.py is a bare pydantic BaseModel, so an unknown YAML key is
DROPPED SILENTLY — a misspelled treatment flag runs the baseline under the treatment's
run_name, and nothing fails until the money is spent (runs/README.md records two such
traps). These tests load the treatment scenarios through the real loader and assert the
flag and the pairing parameters actually arrived.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import batch_plan
from ps1982.config import Rules, load_config

ROOT = Path(__file__).resolve().parent.parent

# (file, run_name, market, seed, preset) for the disclosure wave. Everything else in
# these files is the baseline of the run each is paired with: 3 rounds, W=12, 1 session.
DISCLOSED = [
    ("scenarios/m4_disclosed_paper.yaml", "disclosed/m4_disc_paper", 4, 20250755,
     "paper_exact"),
    ("scenarios/m7_disclosed_s42.yaml", "disclosed/m7_disc_42", 7, 42, "random_prior"),
    ("scenarios/m8_disclosed_s42.yaml", "disclosed/m8_disc_42", 8, 42, "random_prior"),
]


@pytest.mark.parametrize("path,run_name,market,seed,preset", DISCLOSED,
                         ids=[p.split("/")[1] for p, *_ in DISCLOSED])
def test_disclosed_scenario_loads_its_flag_and_pairing(path, run_name, market, seed,
                                                       preset):
    cfg = load_config(ROOT / path)
    assert cfg.rules.disclose_structure is True, \
        f"{path}: the ONE thing this arm varies did not load — check the key's spelling"
    assert (cfg.run_name, cfg.market, cfg.seed, cfg.sequence_preset) == \
        (run_name, market, seed, preset)
    # The pairing holds only if everything else is the paired baseline's value.
    assert (cfg.sessions, cfg.max_rounds_per_period, cfg.broadcast_workers) == (1, 3, 12)
    baseline = Rules()
    for field in Rules.model_fields:
        if field == "disclose_structure":
            continue
        assert getattr(cfg.rules, field) == getattr(baseline, field), \
            f"{path}: rules.{field} differs from the paired baseline"


def test_baseline_scenarios_do_not_disclose():
    """Every rung of the ladder is off in the baselines, not just the first one."""
    rungs = ("disclose_structure", "disclose_card_years", "disclose_insiders_fixed",
             "objective_profit_max", "clue_is_certain")
    for path in ("scenarios/m4_paper.yaml", "scenarios/m7_control.yaml",
                 "scenarios/m8_control.yaml"):
        rules = load_config(ROOT / path).rules
        for flag in rungs:
            assert getattr(rules, flag) is False, f"{path}: {flag}"
        assert rules.period_end_style == "note", path


def test_disclosed_wave_matches_the_scenario_files():
    """The launcher reads membership from PROPOSED_WAVES; the files carry run_name and
    seed. Both halves must exist or the wave silently shrinks."""
    wave = batch_plan.PROPOSED_WAVES["disclosed"]
    assert wave == ("m4_disclosed_paper", "m7_disclosed_s42", "m8_disclosed_s42")
    for name in wave:
        assert (ROOT / "scenarios" / f"{name}.yaml").is_file(), name


# --------------------------------------------------------------- the ladder waves
#
# (file, run_name, market, seed) for tiers 2 and 3. The two markets run two seeds each,
# chosen so that each market's pair pools to 9 buy / 9 sell over the informed periods;
# the scenario headers carry the argument for why that is blocking and not selection.

LADDER = {
    2: [("scenarios/m7_ladder2_s42.yaml", "ladder2/m7_lad2_42", 7, 42),
        ("scenarios/m7_ladder2_s45.yaml", "ladder2/m7_lad2_45", 7, 45),
        ("scenarios/m8_ladder2_s42.yaml", "ladder2/m8_lad2_42", 8, 42),
        ("scenarios/m8_ladder2_s44.yaml", "ladder2/m8_lad2_44", 8, 44)],
    3: [("scenarios/m7_ladder3_s42.yaml", "ladder3/m7_lad3_42", 7, 42),
        ("scenarios/m7_ladder3_s45.yaml", "ladder3/m7_lad3_45", 7, 45),
        ("scenarios/m8_ladder3_s42.yaml", "ladder3/m8_lad3_42", 8, 42),
        ("scenarios/m8_ladder3_s44.yaml", "ladder3/m8_lad3_44", 8, 44)],
}
TIER_FLAGS = {
    2: {"disclose_structure", "disclose_card_years", "objective_profit_max",
        "clue_is_certain"},
    3: {"disclose_structure", "disclose_card_years", "disclose_insiders_fixed",
        "objective_profit_max", "clue_is_certain"},
}

LADDER_CASES = [(t, *row) for t, rows in LADDER.items() for row in rows]


@pytest.mark.parametrize("tier,path,run_name,market,seed", LADDER_CASES,
                         ids=[r[1].split("/")[1] for r in LADDER_CASES])
def test_ladder_scenario_loads_its_rung_and_pairing(tier, path, run_name, market, seed):
    """Every flag this rung sets must arrive, and every flag it does NOT set must still
    be at the baseline value.

    The second half is the one that matters. A tier-3 file miscopied from its tier-2 twin
    differs in exactly one line, and pydantic drops a misspelled key silently — so without
    the else branch, `disclose_insiders_fixed: disclose_insiders_fixd: true` would run
    tier 2 for eight hours under a tier-3 run_name.
    """
    cfg = load_config(ROOT / path)
    assert (cfg.run_name, cfg.market, cfg.seed, cfg.sequence_preset) == \
        (run_name, market, seed, "random_prior")
    # The pairing holds only if everything else is the paired baseline's value.
    assert (cfg.sessions, cfg.max_rounds_per_period, cfg.broadcast_workers) == (1, 3, 12)

    baseline = Rules()
    for field in Rules.model_fields:
        want = True if field in TIER_FLAGS[tier] else getattr(baseline, field)
        assert getattr(cfg.rules, field) == want, \
            f"{path}: rules.{field} is {getattr(cfg.rules, field)!r}, expected {want!r}"


def test_the_two_ladder_tiers_differ_in_exactly_one_flag():
    """tier3 - tier2 is the ladder's only single-dial contrast, and it is the reason the
    rungs are ordered this way. If a second flag ever drifts between them, the contrast
    stops being one."""
    for row2, row3 in zip(LADDER[2], LADDER[3]):
        r2 = load_config(ROOT / row2[0]).rules
        r3 = load_config(ROOT / row3[0]).rules
        differ = {f for f in Rules.model_fields
                  if getattr(r2, f) != getattr(r3, f)}
        assert differ == {"disclose_insiders_fixed"}, \
            f"{row2[0]} vs {row3[0]}: differ in {sorted(differ)}"


@pytest.mark.parametrize("wave", ["ladder2", "ladder3"])
def test_ladder_waves_match_the_scenario_files(wave):
    members = batch_plan.PROPOSED_WAVES[wave]
    tier = int(wave[-1])
    assert members == tuple(Path(p).stem for p, *_ in LADDER[tier])
    for name in members:
        assert (ROOT / "scenarios" / f"{name}.yaml").is_file(), name
    # Four sessions x 12 workers = 48 in flight, inside the tolerated 50-80.
    assert len(members) * 12 == 48
