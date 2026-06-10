"""
Unit tests for game/scoring.py (PHASE 4 - placeholder).

Will cover, once scoring is implemented:
- probability clamping to [MIN_SHOT_PROBABILITY, MAX_SHOT_PROBABILITY]
- form score always within 0-100
- defender pressure modifiers match config.PRESSURE_MODIFIERS
- fatigue stays within 0-100 and recovers over time

For now this only sanity-checks the config values those tests rely on.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config


def test_probability_bounds_are_sane():
    assert 0.0 <= config.MIN_SHOT_PROBABILITY < config.MAX_SHOT_PROBABILITY <= 1.0


def test_form_weights_sum_to_one():
    total = (
        config.FORM_WEIGHT_ELBOW_EXTENSION
        + config.FORM_WEIGHT_KNEE_BEND
        + config.FORM_WEIGHT_VERTICAL_RISE
        + config.FORM_WEIGHT_BALANCE
        + config.FORM_WEIGHT_SMOOTHNESS
    )
    assert abs(total - 1.0) < 1e-9


def test_pressure_modifiers_have_all_levels():
    assert set(config.PRESSURE_MODIFIERS) == {"OPEN", "LIGHT_CONTEST", "HEAVY_CONTEST"}
    # Open looks must help, heavy contests must hurt.
    assert config.PRESSURE_MODIFIERS["OPEN"] > 0
    assert config.PRESSURE_MODIFIERS["HEAVY_CONTEST"] < 0


def test_dominant_arm_is_valid():
    assert config.DOMINANT_ARM in ("right", "left")
