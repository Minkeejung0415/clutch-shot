"""
Biomechanics helper functions.

These are PURE math functions: they take simple (x, y) points or landmark
objects and return numbers. They never touch the camera or MediaPipe
directly, which makes them easy to unit test (see tests/test_biomechanics.py).

Coordinate convention (matches MediaPipe normalized landmarks):
- x: 0.0 = left edge of frame, 1.0 = right edge
- y: 0.0 = TOP of frame, 1.0 = BOTTOM
  -> a body part moving UP on screen means its y value DECREASES.
"""

import math


def calculate_angle(point_a, point_b, point_c):
    """
    Return the angle at point_b (the middle joint) in degrees, 0-180.

    Example: calculate_angle(shoulder, elbow, wrist) gives the elbow angle.
    A straight arm is ~180 degrees; a fully bent arm approaches 0.

    Each point is anything indexable as (x, y), e.g. a tuple or list.

    How it works:
    1. Build two vectors that both start at the middle joint B:
       BA = A - B   and   BC = C - B
    2. The angle between two vectors comes from the dot-product formula:
       cos(theta) = (BA . BC) / (|BA| * |BC|)
    3. Convert from radians to degrees.
    """
    ax, ay = point_a[0], point_a[1]
    bx, by = point_b[0], point_b[1]
    cx, cy = point_c[0], point_c[1]

    # Vectors from the middle joint out to each end point.
    ba_x, ba_y = ax - bx, ay - by
    bc_x, bc_y = cx - bx, cy - by

    # Dot product and vector lengths for the cosine formula.
    dot = ba_x * bc_x + ba_y * bc_y
    mag_ba = math.hypot(ba_x, ba_y)
    mag_bc = math.hypot(bc_x, bc_y)

    # If two points overlap the angle is undefined; return 0 safely
    # instead of dividing by zero (can happen if tracking glitches).
    if mag_ba == 0 or mag_bc == 0:
        return 0.0

    # Clamp to [-1, 1] to protect acos from tiny floating-point overshoot.
    cos_angle = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))

    return math.degrees(math.acos(cos_angle))


def midpoint(point_a, point_b):
    """
    Return the (x, y) point halfway between two points.

    Useful for estimating body centers, e.g.:
    - midpoint(left_hip, right_hip)       -> hip center
    - midpoint(left_shoulder, right_shoulder) -> chest center
    """
    return (
        (point_a[0] + point_b[0]) / 2.0,
        (point_a[1] + point_b[1]) / 2.0,
    )


def vertical_movement(previous_y, current_y):
    """
    Return how far a point moved UP between two frames, in normalized units.

    Positive result = moved up, negative = moved down.

    Remember the y axis is flipped (0 at the top of the frame), so moving
    up means y got SMALLER -> previous_y - current_y is positive.
    """
    return previous_y - current_y


def tilt_degrees(point_a, point_b):
    """
    Return how far the line A->B deviates from horizontal, in degrees (0-90).

    Used for balance checks: a level shoulder line (left_shoulder to
    right_shoulder) returns ~0; leaning sideways increases the value.
    """
    dx = point_b[0] - point_a[0]
    dy = point_b[1] - point_a[1]

    # Two points on top of each other: treat as level rather than crash.
    if dx == 0 and dy == 0:
        return 0.0

    # atan2 gives the line's angle from horizontal; abs() because we only
    # care about the amount of tilt, not the direction.
    angle = abs(math.degrees(math.atan2(dy, dx)))

    # atan2 can return up to 180 (line pointing left); fold it so a
    # perfectly horizontal line is always 0 regardless of point order.
    if angle > 90:
        angle = 180 - angle
    return angle


def average_visibility(landmarks):
    """
    Return the mean visibility (0.0-1.0) of a list of landmark objects.

    Each landmark must have a .visibility attribute (MediaPipe provides
    this). Used to decide whether the whole body is reliably in frame.
    Returns 0.0 for an empty list.
    """
    if not landmarks:
        return 0.0
    return sum(lm.visibility for lm in landmarks) / len(landmarks)
