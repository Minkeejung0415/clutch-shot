"""
Unit tests for the five-move classifier (vision/motion_detector.py).

No camera needed: we feed hand-crafted joint dictionaries that act out
each move frame by frame, plus the fast combos the game is built for.

Geometry (normalized coords, y = 0 at the TOP of the frame):
- shoulders sit at y = 0.35
- a hand at y = 0.20 is clearly UP (above the shoulder line)
- a hand at y = 0.55 is clearly DOWN

Run from the project root:
    pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from vision.motion_detector import (
    DRIBBLE,
    LAYUP,
    SHOT,
    SHOT_FAKE,
    STEPBACK,
    MotionClassifier,
)

FRAME_DT = 0.05  # 20 fps worth of simulated time


def joints(left_wrist_y=0.55, right_wrist_y=0.55, shoulder_half_width=0.05):
    """A full pose with adjustable wrist heights and shoulder width."""
    return {
        "left_shoulder": (0.5 - shoulder_half_width, 0.35, 1.0),
        "right_shoulder": (0.5 + shoulder_half_width, 0.35, 1.0),
        "left_elbow": (0.42, 0.45, 1.0),
        "right_elbow": (0.58, 0.45, 1.0),
        "left_wrist": (0.40, left_wrist_y, 1.0),
        "right_wrist": (0.60, right_wrist_y, 1.0),
        "left_hip": (0.46, 0.60, 1.0),
        "right_hip": (0.54, 0.60, 1.0),
        "left_knee": (0.46, 0.75, 1.0),
        "right_knee": (0.54, 0.75, 1.0),
        "left_ankle": (0.46, 0.90, 1.0),
        "right_ankle": (0.54, 0.90, 1.0),
    }


class Player:
    """Drives a classifier with simulated frames and collects events."""

    def __init__(self):
        self.classifier = MotionClassifier()
        self.t = 1000.0

    def frame(self, pose, dt=FRAME_DT):
        self.t += dt
        return self.classifier.update(pose, self.t)

    def hold(self, pose, seconds):
        """Feed the same pose for `seconds`; return all events."""
        events = []
        elapsed = 0.0
        while elapsed < seconds:
            events += self.frame(pose)
            elapsed += FRAME_DT
        return events

    def types(self, events):
        return [e["type"] for e in events]


# ----------------------------------------------------------------------
# SHOT: both hands up, held over 1 second
# ----------------------------------------------------------------------
class TestShot:
    def test_holding_both_hands_up_one_second_fires_shot(self):
        p = Player()
        p.hold(joints(), 0.3)  # settle standing
        events = p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2),
                        config.SHOT_HOLD_TIME + 0.2)
        assert p.types(events) == [SHOT]

    def test_shot_fires_exactly_once_per_raise(self):
        p = Player()
        p.hold(joints(), 0.3)
        events = p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2), 3.0)
        assert p.types(events).count(SHOT) == 1

    def test_dropping_hands_after_shot_is_not_a_fake(self):
        p = Player()
        p.hold(joints(), 0.3)
        events = p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2), 1.3)
        events += p.hold(joints(), 0.3)  # hands come down after the shot
        assert SHOT_FAKE not in p.types(events)

    def test_two_shots_in_a_row_both_count(self):
        p = Player()
        p.hold(joints(), 0.3)
        first = p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2), 1.2)
        p.hold(joints(), 0.3)  # reset between shots
        second = p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2), 1.2)
        assert SHOT in p.types(first) and SHOT in p.types(second)


# ----------------------------------------------------------------------
# SHOT FAKE: both hands up and back down inside 1 second
# ----------------------------------------------------------------------
class TestShotFake:
    def test_quick_up_and_down_is_a_fake(self):
        p = Player()
        p.hold(joints(), 0.3)
        events = p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2), 0.4)
        events += p.frame(joints())  # both back below the shoulders
        assert p.types(events) == [SHOT_FAKE]

    def test_fake_then_immediate_real_shot_both_detected(self):
        # The exact chain the game is designed around.
        p = Player()
        p.hold(joints(), 0.3)
        events = p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2), 0.4)
        events += p.hold(joints(), 0.2)                       # fake lands
        events += p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2), 1.2)
        assert p.types(events).count(SHOT_FAKE) == 1
        assert p.types(events).count(SHOT) == 1


# ----------------------------------------------------------------------
# LAYUP: exactly one hand up
# ----------------------------------------------------------------------
class TestLayup:
    def test_one_hand_up_is_a_layup(self):
        p = Player()
        p.hold(joints(), 0.3)
        events = p.hold(joints(right_wrist_y=0.2), 0.4)
        assert p.types(events) == [LAYUP]
        assert events[0]["hand"] == "right"

    def test_layup_fires_once_until_hand_drops(self):
        p = Player()
        p.hold(joints(), 0.3)
        events = p.hold(joints(left_wrist_y=0.2), 2.0)
        assert p.types(events).count(LAYUP) == 1
        p.hold(joints(), 0.3)  # hand comes down
        events = p.hold(joints(left_wrist_y=0.2), 0.4)
        assert LAYUP in p.types(events)

    def test_second_hand_arriving_quickly_means_shot_not_layup(self):
        # Raising both hands with a tiny offset must NOT fire a layup.
        p = Player()
        p.hold(joints(), 0.3)
        events = p.hold(joints(right_wrist_y=0.2), 0.1)  # right leads...
        events += p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2), 1.2)
        assert LAYUP not in p.types(events)
        assert SHOT in p.types(events)

    def test_dropping_one_hand_from_a_raise_is_not_a_layup(self):
        p = Player()
        p.hold(joints(), 0.3)
        events = p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2), 0.3)
        events += p.hold(joints(left_wrist_y=0.2), 0.4)  # right drops first
        assert LAYUP not in p.types(events)


# ----------------------------------------------------------------------
# DRIBBLE: a below-shoulder hand bouncing
# ----------------------------------------------------------------------
class TestDribble:
    def test_bouncing_hand_below_shoulders_dribbles(self):
        p = Player()
        p.hold(joints(), 0.3)
        events = []
        # Pump the right hand between y=0.55 and y=0.75: each frame
        # moves 0.05 in 0.05s = speed 1.0, well over the threshold.
        for _ in range(4):  # 4 down-up cycles
            for y in (0.60, 0.65, 0.70, 0.75, 0.70, 0.65, 0.60, 0.55):
                events += p.frame(joints(right_wrist_y=y))
        dribbles = [e for e in events if e["type"] == DRIBBLE]
        assert len(dribbles) >= 4
        assert all(e["hand"] == "right" for e in dribbles)

    def test_hands_held_still_do_not_dribble(self):
        p = Player()
        events = p.hold(joints(), 2.0)
        assert DRIBBLE not in p.types(events)

    def test_hand_above_shoulders_does_not_dribble(self):
        p = Player()
        p.hold(joints(), 0.3)
        events = []
        # Same oscillation but ABOVE the shoulder line: not a dribble.
        for _ in range(4):
            for y in (0.30, 0.25, 0.20, 0.15, 0.20, 0.25, 0.30):
                events += p.frame(joints(left_wrist_y=0.55, right_wrist_y=y))
        assert DRIBBLE not in p.types(events)


# ----------------------------------------------------------------------
# STEPBACK: shoulders shrink = body moved away from the camera
# ----------------------------------------------------------------------
class TestStepback:
    def test_shrinking_shoulders_is_a_stepback(self):
        p = Player()
        p.hold(joints(shoulder_half_width=0.06), 0.6)
        events = []
        # Shrink shoulder width by ~25% over half a second.
        for half_width in (0.058, 0.055, 0.052, 0.049, 0.046, 0.045,
                           0.045, 0.045, 0.045, 0.045):
            events += p.frame(joints(shoulder_half_width=half_width))
        assert STEPBACK in p.types(events)

    def test_stepback_has_a_cooldown(self):
        p = Player()
        p.hold(joints(shoulder_half_width=0.06), 0.6)
        events = []
        # One continuous retreat must not fire two stepbacks instantly.
        for half_width in (0.057, 0.054, 0.051, 0.048, 0.045, 0.043,
                           0.041, 0.039, 0.037, 0.035, 0.033, 0.031):
            events += p.frame(joints(shoulder_half_width=half_width))
        assert p.types(events).count(STEPBACK) == 1

    def test_standing_at_fixed_distance_never_steps_back(self):
        p = Player()
        events = p.hold(joints(), 2.0)
        assert STEPBACK not in p.types(events)


# ----------------------------------------------------------------------
# Fast combos: the whole point of the per-frame classifier
# ----------------------------------------------------------------------
class TestCombos:
    def test_fake_dribble_stepback_shot_chain(self):
        """Shot fake -> dribble -> stepback -> shot, back to back."""
        p = Player()
        p.hold(joints(shoulder_half_width=0.06), 0.6)
        events = []

        # 1. quick pump fake
        events += p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2,
                                shoulder_half_width=0.06), 0.35)
        events += p.frame(joints(shoulder_half_width=0.06))

        # 2. two hard dribbles
        for y in (0.62, 0.68, 0.74, 0.68, 0.62, 0.68, 0.74, 0.68, 0.62):
            events += p.frame(joints(right_wrist_y=y, shoulder_half_width=0.06))

        # 3. stepback (shoulders shrink)
        for hw in (0.057, 0.054, 0.051, 0.048, 0.046, 0.045):
            events += p.frame(joints(shoulder_half_width=hw))

        # 4. rise and hold for the shot
        events += p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2,
                                shoulder_half_width=0.045), 1.2)

        types = [e["type"] for e in events]
        assert SHOT_FAKE in types
        assert DRIBBLE in types
        assert STEPBACK in types
        assert SHOT in types
        # And they arrive in the order they were performed.
        assert (types.index(SHOT_FAKE) < types.index(DRIBBLE)
                < types.index(STEPBACK) < types.index(SHOT))


class TestRobustness:
    def test_losing_the_player_resets_without_events(self):
        p = Player()
        p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2), 0.4)
        assert p.frame(None) == []
        assert p.classifier.status()["posture"] == "NO PLAYER"

    def test_status_reports_shot_progress(self):
        p = Player()
        p.hold(joints(), 0.3)
        p.hold(joints(left_wrist_y=0.2, right_wrist_y=0.2), 0.5)
        status = p.classifier.status()
        assert status["posture"] == "BOTH HANDS UP"
        assert 0.3 < status["shot_progress"] < 0.8
