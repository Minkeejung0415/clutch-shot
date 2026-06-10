"""
Scoring math: form score, shot probability, fatigue, and points.

Everything here is deliberately transparent - simple weighted sums and
linear ramps with every constant in config.py - so the game's "AI" can
be explained in one paragraph and tuned in one file.

No randomness lives here (the make/miss dice roll happens in
game_manager.py), which keeps every function in this file unit-testable.
"""

import config


def clamp(value, low, high):
    """Pin value into the inclusive range [low, high]."""
    return max(low, min(high, value))


def _ramp(value, zero_at, one_at):
    """
    Linearly map value onto 0.0-1.0.

    Returns 0.0 at `zero_at`, 1.0 at `one_at`, and is clamped outside
    that range. Works whether the ramp goes up (zero_at < one_at) or
    down (zero_at > one_at), which lets one helper handle both
    "bigger angle is better" (elbow) and "smaller angle is better" (knee).
    """
    if zero_at == one_at:           # degenerate config; avoid div by zero
        return 1.0 if value >= one_at else 0.0
    t = (value - zero_at) / (one_at - zero_at)
    return clamp(t, 0.0, 1.0)


# ----------------------------------------------------------------------
# FORM SCORE (0 - 100)
# ----------------------------------------------------------------------
def compute_form_score(metrics):
    """
    Convert raw shot measurements into a 0-100 form score.

    The score is a weighted sum of five components, each scored 0.0-1.0:

      elbow extension (30%) - how straight the arm was at release.
          Ramp: FORM_ELBOW_MIN_ANGLE deg -> 0.0, FORM_ELBOW_MAX_ANGLE -> 1.0
      knee bend       (20%) - how deep the legs loaded before the shot.
          Ramp: FORM_KNEE_WORST_ANGLE (standing) -> 0.0,
                FORM_KNEE_BEST_ANGLE (athletic dip) -> 1.0
      vertical rise   (20%) - how far the wrist rose above idle height.
          Ramp: 0 rise -> 0.0, FORM_FULL_RISE -> 1.0
      balance         (15%) - half from body tilt (level shoulders/hips),
          half from how little the hips slid sideways during the shot.
      smoothness      (15%) - fraction of the rise that moved upward;
          a hitchy, stop-start stroke scores lower.

    Args:
        metrics: dict produced by MotionDetector._build_shot_metrics().

    Returns:
        float in [0.0, 100.0].
    """
    elbow_component = _ramp(
        metrics["release_elbow_angle"],
        config.FORM_ELBOW_MIN_ANGLE,
        config.FORM_ELBOW_MAX_ANGLE,
    )

    # NOTE: ramp runs "downhill" - a SMALLER knee angle is a deeper,
    # better dip, so worst angle maps to 0 and best angle maps to 1.
    knee_component = _ramp(
        metrics["min_knee_angle"],
        config.FORM_KNEE_WORST_ANGLE,
        config.FORM_KNEE_BEST_ANGLE,
    )

    rise_component = _ramp(metrics["wrist_rise"], 0.0, config.FORM_FULL_RISE)

    # Balance penalizes two things equally: leaning (tilt) and sliding
    # sideways (hip drift). Each half starts at 0.5 and melts to 0.
    tilt_half = 0.5 * (1.0 - clamp(metrics["avg_tilt"] / config.FORM_MAX_TILT, 0.0, 1.0))
    drift_half = 0.5 * (1.0 - clamp(metrics["hip_drift"] / config.FORM_MAX_HIP_DRIFT, 0.0, 1.0))
    balance_component = tilt_half + drift_half

    smoothness_component = clamp(metrics["smoothness"], 0.0, 1.0)

    # Weighted sum -> 0.0-1.0, then scale to 0-100.
    total = (
        config.FORM_WEIGHT_ELBOW_EXTENSION * elbow_component
        + config.FORM_WEIGHT_KNEE_BEND * knee_component
        + config.FORM_WEIGHT_VERTICAL_RISE * rise_component
        + config.FORM_WEIGHT_BALANCE * balance_component
        + config.FORM_WEIGHT_SMOOTHNESS * smoothness_component
    )
    return clamp(total * 100.0, 0.0, 100.0)


def form_label(form_score):
    """Human-readable band for a form score (used by the UI)."""
    if form_score >= config.FORM_EXCELLENT_THRESHOLD:
        return "EXCELLENT"
    if form_score >= config.FORM_GOOD_THRESHOLD:
        return "GOOD"
    if form_score >= config.FORM_DECENT_THRESHOLD:
        return "DECENT"
    return "UNSTABLE"


# ----------------------------------------------------------------------
# SHOT SUCCESS PROBABILITY
# ----------------------------------------------------------------------
def shot_probability(form_score, pressure_level, fatigue_value, fake_bonus_active):
    """
    The whole "will it go in?" formula, in one readable place:

        probability = base
                    + form_score / 200          (perfect form = +0.50)
                    + pressure modifier         (open +0.15 ... heavy -0.20)
                    - fatigue penalty           (up to -0.15 when gassed)
                    + fake bonus                (+0.10 if defender bit)

    clamped to [MIN_SHOT_PROBABILITY, MAX_SHOT_PROBABILITY] so shots are
    never automatic and never hopeless.

    Args:
        form_score: 0-100 from compute_form_score().
        pressure_level: "OPEN", "LIGHT_CONTEST" or "HEAVY_CONTEST".
        fatigue_value: 0-100 from the FatigueSystem.
        fake_bonus_active: True if this is the follow-up after a
            defender bit on a shot fake.

    Returns:
        float probability in [MIN_SHOT_PROBABILITY, MAX_SHOT_PROBABILITY].
    """
    form_bonus = form_score / config.FORM_BONUS_DIVISOR
    pressure_modifier = config.PRESSURE_MODIFIERS[pressure_level]
    fatigue_penalty = (fatigue_value / config.FATIGUE_MAX) * config.FATIGUE_MAX_PENALTY
    fake_bonus = config.FAKE_SHOT_BONUS if fake_bonus_active else 0.0

    probability = (
        config.BASE_SHOT_PROBABILITY
        + form_bonus
        + pressure_modifier
        - fatigue_penalty
        + fake_bonus
    )
    return clamp(probability, config.MIN_SHOT_PROBABILITY, config.MAX_SHOT_PROBABILITY)


# ----------------------------------------------------------------------
# POINTS
# ----------------------------------------------------------------------
def points_for_made_shot(pressure_level, fake_bonus_active, form_score):
    """
    Points awarded for a MADE shot, plus a list of bonus labels for the UI.

    Base: 2 points. Bonuses (+1 each):
      - the shot was OPEN
      - it was the follow-up after a defender bit on a fake
      - form score reached the EXCELLENT band

    A missed shot is always worth 0, so callers only call this on makes.
    """
    points = config.POINTS_MADE_SHOT
    bonuses = []

    if pressure_level == "OPEN":
        points += config.BONUS_OPEN_SHOT
        bonuses.append("OPEN +1")
    if fake_bonus_active:
        points += config.BONUS_AFTER_FAKE
        bonuses.append("FAKE +1")
    if form_score >= config.FORM_EXCELLENT_THRESHOLD:
        points += config.BONUS_EXCELLENT_FORM
        bonuses.append("FORM +1")

    return points, bonuses


# ----------------------------------------------------------------------
# FATIGUE (0 - 100)
# ----------------------------------------------------------------------
class FatigueSystem:
    """
    Simple stamina meter.

    Every shot ATTEMPT (made or missed) adds FATIGUE_PER_SHOT. Standing
    still recovers FATIGUE_RECOVERY_PER_SEC per second. The value is
    always within [0, FATIGUE_MAX] and converts to a probability penalty
    inside shot_probability().
    """

    def __init__(self):
        self.value = 0.0

    def add_shot(self):
        """Call once per shot attempt."""
        self.value = clamp(self.value + config.FATIGUE_PER_SHOT, 0.0, config.FATIGUE_MAX)

    def update(self, dt):
        """Recover while resting. dt is seconds since the last frame."""
        self.value = clamp(
            self.value - config.FATIGUE_RECOVERY_PER_SEC * dt, 0.0, config.FATIGUE_MAX
        )
