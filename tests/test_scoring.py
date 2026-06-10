"""
Unit tests for game/scoring.py and game/defender.py.

All headless - no camera, no Pygame window needed.

Run from the project root:
    pytest tests/ -v
"""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from game.defender import PRESSURE_LEVELS, Defender, DefenderManager
from game.scoring import (
    FatigueSystem,
    clamp,
    compute_form_score,
    form_label,
    points_for_made_shot,
    shot_probability,
)


def make_metrics(**overrides):
    """A reasonable mid-quality shot; override fields per test."""
    metrics = {
        "release_elbow_angle": 160.0,
        "min_knee_angle": 150.0,
        "wrist_rise": 0.15,
        "avg_tilt": 5.0,
        "hip_drift": 0.03,
        "smoothness": 0.9,
    }
    metrics.update(overrides)
    return metrics


# ----------------------------------------------------------------------
# clamp
# ----------------------------------------------------------------------
class TestClamp:
    def test_value_inside_range_is_unchanged(self):
        assert clamp(0.5, 0.0, 1.0) == 0.5

    def test_value_below_range_pins_to_low(self):
        assert clamp(-3, 0.0, 1.0) == 0.0

    def test_value_above_range_pins_to_high(self):
        assert clamp(99, 0.0, 1.0) == 1.0


# ----------------------------------------------------------------------
# Probability clamping
# ----------------------------------------------------------------------
class TestShotProbability:
    def test_terrible_shot_never_goes_below_minimum(self):
        # Worst case: zero form, heavy contest, fully gassed.
        prob = shot_probability(0, "HEAVY_CONTEST", config.FATIGUE_MAX, False)
        assert prob >= config.MIN_SHOT_PROBABILITY

    def test_perfect_shot_never_exceeds_maximum(self):
        # Best case: perfect form, wide open, fresh, fake bonus active.
        prob = shot_probability(100, "OPEN", 0, True)
        assert prob <= config.MAX_SHOT_PROBABILITY

    def test_probability_always_in_clamp_range(self):
        rng = random.Random(42)
        for _ in range(500):
            prob = shot_probability(
                rng.uniform(0, 100),
                rng.choice(list(PRESSURE_LEVELS)),
                rng.uniform(0, config.FATIGUE_MAX),
                rng.random() < 0.5,
            )
            assert config.MIN_SHOT_PROBABILITY <= prob <= config.MAX_SHOT_PROBABILITY

    def test_open_shot_beats_heavy_contest(self):
        open_prob = shot_probability(70, "OPEN", 20, False)
        heavy_prob = shot_probability(70, "HEAVY_CONTEST", 20, False)
        assert open_prob > heavy_prob

    def test_better_form_means_better_odds(self):
        low = shot_probability(30, "LIGHT_CONTEST", 20, False)
        high = shot_probability(90, "LIGHT_CONTEST", 20, False)
        assert high > low

    def test_fatigue_hurts(self):
        fresh = shot_probability(70, "LIGHT_CONTEST", 0, False)
        gassed = shot_probability(70, "LIGHT_CONTEST", config.FATIGUE_MAX, False)
        assert fresh > gassed


# ----------------------------------------------------------------------
# Form score range
# ----------------------------------------------------------------------
class TestFormScore:
    def test_great_shot_scores_high(self):
        great = make_metrics(release_elbow_angle=172, min_knee_angle=128,
                             wrist_rise=0.3, avg_tilt=1.0, hip_drift=0.0,
                             smoothness=1.0)
        assert compute_form_score(great) >= config.FORM_EXCELLENT_THRESHOLD

    def test_awful_shot_scores_low(self):
        awful = make_metrics(release_elbow_angle=110, min_knee_angle=178,
                             wrist_rise=0.0, avg_tilt=40.0, hip_drift=0.3,
                             smoothness=0.0)
        assert compute_form_score(awful) < config.FORM_DECENT_THRESHOLD

    def test_form_score_always_between_0_and_100(self):
        # Fuzz with wild values including out-of-range garbage.
        rng = random.Random(7)
        for _ in range(500):
            metrics = make_metrics(
                release_elbow_angle=rng.uniform(0, 250),
                min_knee_angle=rng.uniform(0, 250),
                wrist_rise=rng.uniform(-1, 2),
                avg_tilt=rng.uniform(0, 90),
                hip_drift=rng.uniform(0, 1),
                smoothness=rng.uniform(-1, 2),
            )
            score = compute_form_score(metrics)
            assert 0.0 <= score <= 100.0

    def test_form_labels_match_config_bands(self):
        assert form_label(config.FORM_EXCELLENT_THRESHOLD) == "EXCELLENT"
        assert form_label(config.FORM_GOOD_THRESHOLD) == "GOOD"
        assert form_label(config.FORM_DECENT_THRESHOLD) == "DECENT"
        assert form_label(0) == "UNSTABLE"


# ----------------------------------------------------------------------
# Defender pressure modifiers
# ----------------------------------------------------------------------
class TestDefenderPressure:
    def test_modifiers_exist_for_every_pressure_level(self):
        assert set(config.PRESSURE_MODIFIERS) == set(PRESSURE_LEVELS)

    def test_open_helps_and_heavy_hurts(self):
        assert config.PRESSURE_MODIFIERS["OPEN"] > 0
        assert config.PRESSURE_MODIFIERS["HEAVY_CONTEST"] < 0

    def test_every_defender_rolls_valid_pressure_levels(self):
        for type_name in config.DEFENDER_PROFILES:
            defender = Defender(type_name)
            for _ in range(50):
                assert defender.roll_pressure() in PRESSURE_LEVELS

    def test_fake_window_forces_open_look(self):
        manager = DefenderManager()
        manager.fake_window = 1.5
        assert manager.pressure_for_shot() == "OPEN"

    def test_fake_window_is_consumed_by_one_shot(self):
        manager = DefenderManager()
        manager.fake_window = 1.5
        assert manager.consume_fake_window() is True
        # Second shot gets no leftover bonus.
        assert manager.consume_fake_window() is False

    def test_boss_enters_when_clock_runs_down(self):
        manager = DefenderManager()
        messages = manager.update(dt=0.1,
                                  time_remaining=config.BOSS_ENTER_TIME_REMAINING - 1)
        assert manager.defender.is_boss
        assert "BOSS DEFENDER ENTERS!" in messages


# ----------------------------------------------------------------------
# Fatigue range
# ----------------------------------------------------------------------
class TestFatigue:
    def test_starts_fresh(self):
        assert FatigueSystem().value == 0.0

    def test_shots_add_fatigue(self):
        fatigue = FatigueSystem()
        fatigue.add_shot()
        assert fatigue.value == config.FATIGUE_PER_SHOT

    def test_never_exceeds_max_even_when_spamming(self):
        fatigue = FatigueSystem()
        for _ in range(100):
            fatigue.add_shot()
        assert fatigue.value == config.FATIGUE_MAX

    def test_recovers_while_resting_but_not_below_zero(self):
        fatigue = FatigueSystem()
        fatigue.add_shot()
        fatigue.update(dt=1.0)
        assert fatigue.value == pytest.approx(
            config.FATIGUE_PER_SHOT - config.FATIGUE_RECOVERY_PER_SEC
        )
        fatigue.update(dt=1000.0)  # rest a very long time
        assert fatigue.value == 0.0


# ----------------------------------------------------------------------
# Points
# ----------------------------------------------------------------------
class TestPoints:
    def test_plain_make_is_two_points(self):
        points, bonuses = points_for_made_shot("LIGHT_CONTEST", False, 60)
        assert points == config.POINTS_MADE_SHOT
        assert bonuses == []

    def test_all_bonuses_stack(self):
        points, bonuses = points_for_made_shot("OPEN", True,
                                               config.FORM_EXCELLENT_THRESHOLD)
        expected = (config.POINTS_MADE_SHOT + config.BONUS_OPEN_SHOT
                    + config.BONUS_AFTER_FAKE + config.BONUS_EXCELLENT_FORM)
        assert points == expected
        assert len(bonuses) == 3


# ----------------------------------------------------------------------
# Config sanity
# ----------------------------------------------------------------------
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


def test_dominant_arm_is_valid():
    assert config.DOMINANT_ARM in ("right", "left")
