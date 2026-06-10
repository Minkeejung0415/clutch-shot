"""
Attempt resolution math: make probability, points, and fatigue.

Blocks are decided by the DefenderAI before this module is consulted -
scoring only answers "given how contested the attempt was, does the
ball go in, and what is it worth?". Everything is a simple sum of
config constants so the whole system can be explained in a sentence
and tuned in one file.

No randomness lives here (the dice roll happens in game_manager.py),
which keeps every function unit-testable.
"""

import config

# How an attempt was defended (decided by DefenderAI.challenge()).
OPEN = "OPEN"            # defender airborne / beaten / too far away
CONTESTED = "CONTESTED"  # defender got a hand up
BLOCKED = "BLOCKED"      # defender got ALL of it (no probability roll)


def clamp(value, low, high):
    """Pin value into the inclusive range [low, high]."""
    return max(low, min(high, value))


def attempt_probability(kind, contest, contest_penalty, separation,
                        fatigue_value, is_three=False):
    """
    Probability that a non-blocked attempt goes in:

        base (layup 0.80 / shot 0.62)
        + OPEN_BONUS            if the defender couldn't contest
        - contest_penalty       if he got a hand up (difficulty-specific)
        + separation bonus      space bought by stepbacks (capped 2 steps)
        - fatigue penalty       up to -0.15 when gassed
        - THREE_PENALTY         stepback threes are longer shots

    clamped to [MIN_SHOT_PROBABILITY, MAX_SHOT_PROBABILITY].

    Args:
        kind: "shot" or "layup".
        contest: OPEN or CONTESTED (BLOCKED never reaches this).
        contest_penalty: from the active difficulty profile.
        separation: current space in steps (0..MAX_SEPARATION).
        fatigue_value: 0-100 from the FatigueSystem.
        is_three: True for a stepback three attempt.
    """
    base = config.LAYUP_BASE_PROB if kind == "layup" else config.SHOT_BASE_PROB

    if contest == OPEN:
        base += config.OPEN_BONUS
    else:
        base -= contest_penalty

    base += min(separation, 2.0) * config.SEPARATION_PROB_BONUS
    base -= (fatigue_value / config.FATIGUE_MAX) * config.FATIGUE_MAX_PENALTY
    if is_three:
        base -= config.THREE_PENALTY

    return clamp(base, config.MIN_SHOT_PROBABILITY, config.MAX_SHOT_PROBABILITY)


def points_for(kind, is_three=False):
    """Point value of a MADE attempt (misses and blocks are always 0)."""
    if kind == "layup":
        return config.POINTS_LAYUP
    return config.POINTS_STEPBACK_SHOT if is_three else config.POINTS_SHOT


# ----------------------------------------------------------------------
# FATIGUE (0 - 100)
# ----------------------------------------------------------------------
class FatigueSystem:
    """
    Simple stamina meter.

    Every shot/layup ATTEMPT adds FATIGUE_PER_SHOT. Standing still
    recovers FATIGUE_RECOVERY_PER_SEC per second. The value is always
    within [0, FATIGUE_MAX] and converts to a probability penalty inside
    attempt_probability().
    """

    def __init__(self):
        self.value = 0.0

    def add_shot(self):
        """Call once per shot or layup attempt."""
        self.value = clamp(self.value + config.FATIGUE_PER_SHOT, 0.0, config.FATIGUE_MAX)

    def update(self, dt):
        """Recover while resting. dt is seconds since the last frame."""
        self.value = clamp(
            self.value - config.FATIGUE_RECOVERY_PER_SEC * dt, 0.0, config.FATIGUE_MAX
        )
