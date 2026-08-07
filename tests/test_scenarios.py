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
    for path in ("scenarios/m4_paper.yaml", "scenarios/m7_control.yaml",
                 "scenarios/m8_control.yaml"):
        assert load_config(ROOT / path).rules.disclose_structure is False, path


def test_disclosed_wave_matches_the_scenario_files():
    """The launcher reads membership from PROPOSED_WAVES; the files carry run_name and
    seed. Both halves must exist or the wave silently shrinks."""
    wave = batch_plan.PROPOSED_WAVES["disclosed"]
    assert wave == ("m4_disclosed_paper", "m7_disclosed_s42", "m8_disclosed_s42")
    for name in wave:
        assert (ROOT / "scenarios" / f"{name}.yaml").is_file(), name
