"""
Unit tests for game/scoring.py and game/defender.py.

All headless - no camera, no Pygame window needed.

Run from the project root:
    pytest tests/ -v
"""

import random
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from game.defender import BEATEN, CONTEST, GUARD, IN_AIR, RECOVER, DefenderAI
from game.scoring import (
    BLOCKED,
    CONTESTED,
    OPEN,
    FatigueSystem,
    attempt_probability,
    clamp,
    points_for,
)


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
# Attempt probability
# ----------------------------------------------------------------------
class TestAttemptProbability:
    def test_probability_always_in_clamp_range(self):
        rng = random.Random(42)
        for _ in range(500):
            prob = attempt_probability(
                kind=rng.choice(["shot", "layup"]),
                contest=rng.choice([OPEN, CONTESTED]),
                contest_penalty=rng.uniform(0.0, 0.4),
                separation=rng.uniform(0, config.MAX_SEPARATION),
                fatigue_value=rng.uniform(0, config.FATIGUE_MAX),
                is_three=rng.random() < 0.5,
            )
            assert config.MIN_SHOT_PROBABILITY <= prob <= config.MAX_SHOT_PROBABILITY

    def test_open_beats_contested(self):
        open_prob = attempt_probability("shot", OPEN, 0.22, 0, 20)
        contested = attempt_probability("shot", CONTESTED, 0.22, 0, 20)
        assert open_prob > contested

    def test_layups_are_easier_than_jump_shots(self):
        layup = attempt_probability("layup", CONTESTED, 0.22, 0, 0)
        shot = attempt_probability("shot", CONTESTED, 0.22, 0, 0)
        assert layup > shot

    def test_separation_helps(self):
        tight = attempt_probability("shot", CONTESTED, 0.22, 0.0, 0)
        spaced = attempt_probability("shot", CONTESTED, 0.22, 2.0, 0)
        assert spaced > tight

    def test_fatigue_hurts(self):
        fresh = attempt_probability("shot", OPEN, 0.22, 0, 0)
        gassed = attempt_probability("shot", OPEN, 0.22, 0, config.FATIGUE_MAX)
        assert fresh > gassed

    def test_threes_are_harder(self):
        two = attempt_probability("shot", OPEN, 0.22, 1.0, 0, is_three=False)
        three = attempt_probability("shot", OPEN, 0.22, 1.0, 0, is_three=True)
        assert two > three


class TestPoints:
    def test_point_values(self):
        assert points_for("layup") == config.POINTS_LAYUP
        assert points_for("shot") == config.POINTS_SHOT
        assert points_for("shot", is_three=True) == config.POINTS_STEPBACK_SHOT


# ----------------------------------------------------------------------
# Defender AI
# ----------------------------------------------------------------------
class TestDefenderReactions:
    def test_every_difficulty_builds_a_defender(self):
        for name in config.DIFFICULTY_PROFILES:
            defender = DefenderAI(name)
            assert defender.state == GUARD

    def test_fake_bite_rate_follows_difficulty(self):
        """An EASY defender must bite far more often than a HARD one."""
        random.seed(123)
        rates = {}
        for name in ("EASY", "HARD"):
            bites = 0
            for _ in range(400):
                defender = DefenderAI(name)
                if defender.on_fake(deception=0, now=time.time()):
                    bites += 1
            rates[name] = bites / 400
        assert rates["EASY"] > rates["HARD"] + 0.2

    def test_deception_makes_the_defender_bite_more(self):
        random.seed(7)
        bites = {0: 0, 3: 0}
        for deception in bites:
            for _ in range(400):
                defender = DefenderAI("HARD")
                if defender.on_fake(deception, now=time.time()):
                    bites[deception] += 1
        assert bites[3] > bites[0]

    def test_airborne_defender_cannot_bite_again(self):
        defender = DefenderAI("EASY")
        defender.state = IN_AIR
        assert defender.on_fake(deception=3, now=time.time()) is False

    def test_airborne_defender_leaves_the_shot_open(self):
        now = time.time()
        for state in (IN_AIR, RECOVER, BEATEN):
            defender = DefenderAI("HARD")
            defender.state = state
            assert defender.challenge("shot", 0, now) == OPEN

    def test_big_separation_means_open_jumper(self):
        defender = DefenderAI("HARD")
        defender.separation = config.OPEN_SEPARATION
        assert defender.challenge("shot", 0, time.time()) == OPEN
        # ...but a layup attacks the rim, where he's still waiting.
        defender2 = DefenderAI("HARD")
        defender2.separation = config.OPEN_SEPARATION
        assert defender2.challenge("layup", 0, time.time()) in (BLOCKED, CONTESTED)

    def test_contesting_defender_jumps(self):
        defender = DefenderAI("MEDIUM")
        result = defender.challenge("shot", 0, time.time())
        assert result in (BLOCKED, CONTESTED)
        assert defender.state == CONTEST

    def test_challenge_outcomes_are_only_valid_values(self):
        random.seed(99)
        for _ in range(200):
            defender = DefenderAI("MEDIUM")
            outcome = defender.challenge(random.choice(["shot", "layup"]),
                                         random.randint(0, 3), time.time())
            assert outcome in (OPEN, CONTESTED, BLOCKED)

    def test_stepback_buys_capped_separation(self):
        defender = DefenderAI("MEDIUM")
        now = time.time()
        for _ in range(10):
            defender.on_stepback(deception=0, now=now)
        assert defender.separation == config.MAX_SEPARATION

    def test_guarding_defender_closes_separation_over_time(self):
        defender = DefenderAI("HARD")
        defender.separation = 2.0
        now = time.time()
        defender.update(dt=1.0, now=now)
        assert defender.separation < 2.0
        # And HARD closes faster than EASY.
        easy = DefenderAI("EASY")
        easy.separation = 2.0
        easy.update(dt=1.0, now=now)
        assert defender.separation < easy.separation

    def test_recovery_chain_air_to_recover_to_guard(self):
        defender = DefenderAI("MEDIUM")
        now = time.time()
        random.seed(0)
        # Force a bite by trying until it lands (EASY bite math aside).
        while not defender.on_fake(3, now):
            defender = DefenderAI("MEDIUM")
        assert defender.state == IN_AIR
        defender.update(dt=0.01, now=now + config.DEFENDER_AIR_TIME + 0.01)
        assert defender.state == RECOVER
        defender.update(dt=0.01,
                        now=now + config.DEFENDER_AIR_TIME
                        + defender.profile["recover_time"] + 0.05)
        assert defender.state == GUARD

    def test_dribble_pulls_the_defender_sideways(self):
        defender = DefenderAI("MEDIUM")
        now = time.time()
        defender.on_dribble("right", deception=0, now=now)
        for _ in range(30):
            defender.update(dt=1 / 30, now=now)
        assert defender.x > 0.3


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
        fatigue.update(dt=1000.0)
        assert fatigue.value == 0.0


# ----------------------------------------------------------------------
# Config sanity
# ----------------------------------------------------------------------
def test_probability_bounds_are_sane():
    assert 0.0 <= config.MIN_SHOT_PROBABILITY < config.MAX_SHOT_PROBABILITY <= 1.0


def test_difficulty_profiles_have_all_fields():
    required = {"bite_base", "bite_deception_bonus", "stumble_chance",
                "block_shot", "block_layup", "contest_penalty",
                "closing_speed", "recover_time", "shuffle_speed"}
    for name, profile in config.DIFFICULTY_PROFILES.items():
        assert required <= set(profile), f"{name} is missing fields"


def test_harder_difficulties_defend_better():
    easy = config.DIFFICULTY_PROFILES["EASY"]
    hard = config.DIFFICULTY_PROFILES["HARD"]
    assert hard["block_shot"] > easy["block_shot"]
    assert hard["bite_base"] < easy["bite_base"]
    assert hard["closing_speed"] > easy["closing_speed"]
