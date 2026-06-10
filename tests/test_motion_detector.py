"""
Unit tests for the shot-motion state machine (vision/motion_detector.py).

No camera needed: we feed the detector hand-crafted joint dictionaries
that act out a shot, a pump fake, and some non-shots, frame by frame.

Geometry used (normalized coords, y = 0 at the TOP of the frame):
- standing: wrist hangs at y=0.55, knees straight (~180 deg)
- loading:  knees bent to ~135 deg, shooting elbow flexed to ~63 deg
- release:  wrist overhead at y=0.15 (above the shoulder at 0.35) with
            the elbow fully extended (~180 deg)

Run from the project root:
    pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision.motion_detector import COOLDOWN, IDLE, MotionDetector

FRAME_DT = 0.05  # 20 fps worth of simulated time between frames


def standing_joints():
    """A neutral standing pose: arms down, legs straight."""
    return {
        "left_shoulder": (0.45, 0.35, 1.0),
        "right_shoulder": (0.55, 0.35, 1.0),
        "left_elbow": (0.42, 0.45, 1.0),
        "right_elbow": (0.55, 0.45, 1.0),
        "left_wrist": (0.40, 0.55, 1.0),
        "right_wrist": (0.55, 0.55, 1.0),
        "left_hip": (0.46, 0.60, 1.0),
        "right_hip": (0.54, 0.60, 1.0),
        "left_knee": (0.46, 0.75, 1.0),
        "right_knee": (0.54, 0.75, 1.0),
        "left_ankle": (0.46, 0.90, 1.0),
        "right_ankle": (0.54, 0.90, 1.0),
    }


def loaded_joints(wrist_y=0.45):
    """
    The "dip": knees bent (~135 deg) and the shooting elbow cocked
    (~63 deg). wrist_y lets tests slide the still-flexed arm up/down
    to simulate the rise of a pump fake.
    """
    joints = standing_joints()
    # Ankles step out so hip->knee->ankle bends to ~135 degrees.
    joints["left_ankle"] = (0.36, 0.85, 1.0)
    joints["right_ankle"] = (0.64, 0.85, 1.0)
    # Flexed shooting arm; the whole forearm translates with wrist_y.
    joints["right_elbow"] = (0.60, wrist_y, 1.0)
    joints["right_wrist"] = (0.50, wrist_y, 1.0)
    joints["left_elbow"] = (0.40, wrist_y, 1.0)
    joints["left_wrist"] = (0.50, wrist_y, 1.0)
    return joints


def release_joints():
    """Full extension overhead: wrist well above the shoulder."""
    joints = standing_joints()
    joints["right_elbow"] = (0.55, 0.25, 1.0)
    joints["right_wrist"] = (0.55, 0.15, 1.0)
    joints["left_elbow"] = (0.45, 0.25, 1.0)
    joints["left_wrist"] = (0.45, 0.15, 1.0)
    return joints


class Clock:
    """Hands out evenly spaced timestamps for simulated frames."""

    def __init__(self):
        self.t = 1000.0

    def tick(self, dt=FRAME_DT):
        self.t += dt
        return self.t


def settle(detector, clock, frames=5):
    """Feed neutral standing frames so the wrist baseline settles."""
    for _ in range(frames):
        assert detector.update(standing_joints(), clock.tick()) is None


def perform_shot(detector, clock):
    """Act out one complete shot; return the last event produced."""
    event = detector.update(loaded_joints(), clock.tick())          # dip
    event = detector.update(loaded_joints(wrist_y=0.40), clock.tick()) or event  # rise
    event = detector.update(release_joints(), clock.tick()) or event             # release
    return event


class TestShotDetection:
    def test_full_shot_motion_emits_shot_event(self):
        detector, clock = MotionDetector(), Clock()
        settle(detector, clock)
        event = perform_shot(detector, clock)
        assert event is not None and event["type"] == "shot"

    def test_shot_metrics_are_complete_and_sane(self):
        detector, clock = MotionDetector(), Clock()
        settle(detector, clock)
        metrics = perform_shot(detector, clock)["metrics"]

        # The release pose had a straight arm and the dip bent the knees.
        assert metrics["release_elbow_angle"] > 150
        assert metrics["min_knee_angle"] < 160
        # Wrist traveled from y=0.55 up to y=0.15.
        assert metrics["wrist_rise"] > 0.3
        assert 0.0 <= metrics["smoothness"] <= 1.0

    def test_shot_enters_cooldown_and_blocks_double_counting(self):
        detector, clock = MotionDetector(), Clock()
        settle(detector, clock)
        assert perform_shot(detector, clock)["type"] == "shot"
        assert detector.state == COOLDOWN

        # Acting out a second shot immediately must produce nothing.
        assert perform_shot(detector, clock) is None

    def test_new_shot_works_after_cooldown_expires(self):
        detector, clock = MotionDetector(), Clock()
        settle(detector, clock)
        perform_shot(detector, clock)

        clock.tick(dt=5.0)  # wait out the cooldown
        settle(detector, clock, frames=3)
        event = perform_shot(detector, clock)
        assert event is not None and event["type"] == "shot"


class TestFakeDetection:
    def test_pump_fake_emits_fake_event(self):
        detector, clock = MotionDetector(), Clock()
        settle(detector, clock)

        # Dip, rise with the elbow still flexed, then come back DOWN
        # without ever extending: a classic pump fake.
        assert detector.update(loaded_joints(), clock.tick()) is None
        assert detector.update(loaded_joints(wrist_y=0.40), clock.tick()) is None
        assert detector.update(loaded_joints(wrist_y=0.37), clock.tick()) is None
        event = detector.update(loaded_joints(wrist_y=0.50), clock.tick())
        assert event is not None and event["type"] == "fake"


class TestNonShots:
    def test_standing_still_produces_no_events(self):
        detector, clock = MotionDetector(), Clock()
        for _ in range(50):
            assert detector.update(standing_joints(), clock.tick()) is None
        assert detector.state == IDLE

    def test_losing_the_player_mid_motion_resets_safely(self):
        detector, clock = MotionDetector(), Clock()
        settle(detector, clock)
        detector.update(loaded_joints(), clock.tick())   # start an attempt
        assert detector.update(None, clock.tick()) is None  # player gone
        assert detector.state == IDLE
