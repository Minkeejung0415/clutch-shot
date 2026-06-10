"""
Unit tests for vision/biomechanics.py.

These run without a camera or MediaPipe model - they only test the math.

Run from the project root:
    pytest tests/ -v
"""

import math
import sys
from pathlib import Path

import pytest

# Make the project root importable when pytest is run from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision.biomechanics import (
    average_visibility,
    calculate_angle,
    midpoint,
    tilt_degrees,
    vertical_movement,
)


class TestCalculateAngle:
    def test_straight_line_is_180_degrees(self):
        # Three points in a row: a fully extended joint.
        angle = calculate_angle((0, 0), (1, 0), (2, 0))
        assert angle == pytest.approx(180.0, abs=0.01)

    def test_right_angle_is_90_degrees(self):
        # An L shape: like an elbow bent at 90.
        angle = calculate_angle((0, 1), (0, 0), (1, 0))
        assert angle == pytest.approx(90.0, abs=0.01)

    def test_fully_folded_joint_is_0_degrees(self):
        # Both end points in the same direction from the middle joint.
        angle = calculate_angle((1, 0), (0, 0), (2, 0))
        assert angle == pytest.approx(0.0, abs=0.01)

    def test_45_degree_angle(self):
        angle = calculate_angle((1, 1), (0, 0), (1, 0))
        assert angle == pytest.approx(45.0, abs=0.01)

    def test_overlapping_points_return_zero_not_crash(self):
        # Tracking glitches can put two landmarks at the same spot.
        assert calculate_angle((0, 0), (0, 0), (1, 1)) == 0.0

    def test_angle_is_always_in_valid_range(self):
        # Sweep a point around the middle joint; angle must stay 0-180.
        for i in range(36):
            theta = math.radians(i * 10)
            point = (math.cos(theta), math.sin(theta))
            angle = calculate_angle((1, 0), (0, 0), point)
            assert 0.0 <= angle <= 180.0


class TestMidpoint:
    def test_midpoint_of_symmetric_points(self):
        assert midpoint((0, 0), (2, 2)) == (1.0, 1.0)

    def test_midpoint_of_identical_points(self):
        assert midpoint((0.5, 0.5), (0.5, 0.5)) == (0.5, 0.5)

    def test_midpoint_with_normalized_coords(self):
        # Typical hip-center calculation with MediaPipe-style values.
        mid = midpoint((0.4, 0.6), (0.6, 0.62))
        assert mid[0] == pytest.approx(0.5)
        assert mid[1] == pytest.approx(0.61)


class TestVerticalMovement:
    def test_moving_up_is_positive(self):
        # y DECREASES when moving up (screen coordinates), so the
        # helper must report that as positive movement.
        assert vertical_movement(previous_y=0.8, current_y=0.5) == pytest.approx(0.3)

    def test_moving_down_is_negative(self):
        assert vertical_movement(previous_y=0.5, current_y=0.8) == pytest.approx(-0.3)

    def test_no_movement_is_zero(self):
        assert vertical_movement(0.5, 0.5) == 0.0


class TestTiltDegrees:
    def test_horizontal_line_has_zero_tilt(self):
        assert tilt_degrees((0, 0.5), (1, 0.5)) == pytest.approx(0.0)

    def test_point_order_does_not_matter(self):
        a, b = (0.3, 0.4), (0.7, 0.5)
        assert tilt_degrees(a, b) == pytest.approx(tilt_degrees(b, a))

    def test_45_degree_lean(self):
        assert tilt_degrees((0, 0), (1, 1)) == pytest.approx(45.0)

    def test_tilt_never_exceeds_90(self):
        assert tilt_degrees((0, 0), (0, 1)) == pytest.approx(90.0)

    def test_identical_points_return_zero(self):
        assert tilt_degrees((0.5, 0.5), (0.5, 0.5)) == 0.0


class _FakeLandmark:
    """Minimal stand-in for a MediaPipe landmark in tests."""

    def __init__(self, visibility):
        self.visibility = visibility


class TestAverageVisibility:
    def test_average_of_known_values(self):
        landmarks = [_FakeLandmark(1.0), _FakeLandmark(0.5), _FakeLandmark(0.0)]
        assert average_visibility(landmarks) == pytest.approx(0.5)

    def test_empty_list_returns_zero(self):
        assert average_visibility([]) == 0.0

    def test_result_stays_in_unit_range(self):
        landmarks = [_FakeLandmark(v / 10) for v in range(11)]
        assert 0.0 <= average_visibility(landmarks) <= 1.0
